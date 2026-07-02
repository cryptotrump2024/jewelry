"""Metal-price source adapters + refresh job (docs/spec/06 §7, 09).

Provider chain: metal_price_sources rows ordered by priority; the first
provider that succeeds writes metal_price_snapshots (one row per metal/karat)
and a price_refresh_log entry. The pricing hot path never calls these — it
reads the freshest snapshot (cached).

GoldAPI returns per-gram prices at each karat directly (price_gram_24k …
price_gram_10k), which removes manual purity math. The `manual` provider
reads admin-entered values from the source row's config — this is the
Phase 3/4 bridge and the permanent fallback.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MetalPriceSnapshot, MetalPriceSource, PriceRefreshLog

# GoldAPI symbol per metal; silver/platinum are spot per troy ounce → per gram.
GOLDAPI_SYMBOLS = {"gold": "XAU", "silver": "XAG", "platinum": "XPT"}
GRAMS_PER_TROY_OUNCE = Decimal("31.1034768")

# Karats we snapshot for gold (launch purities; 20k derived if absent).
GOLD_KARATS = [24, 22, 20, 18, 14]


@dataclass(frozen=True)
class FetchedPrice:
    metal: str
    karat: int | None
    currency: str
    price_per_gram: Decimal
    source: str


class ProviderError(RuntimeError):
    pass


async def fetch_goldapi(
    config: dict, currency: str, client: httpx.AsyncClient
) -> list[FetchedPrice]:
    """One GoldAPI call per metal. config: {"api_key": "..."}."""
    api_key = config.get("api_key")
    if not api_key:
        raise ProviderError("goldapi: missing api_key in source config")
    prices: list[FetchedPrice] = []
    for metal, symbol in GOLDAPI_SYMBOLS.items():
        resp = await client.get(
            f"https://www.goldapi.io/api/{symbol}/{currency}",
            headers={"x-access-token": api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            raise ProviderError(f"goldapi: HTTP {resp.status_code} for {symbol}")
        data = resp.json()
        if metal == "gold":
            for karat in GOLD_KARATS:
                value = data.get(f"price_gram_{karat}k")
                if value is None and karat == 20:
                    # Derive 20k from 24k when the provider lacks it
                    # (docs/spec/06 §7): 24k per-gram × 833/999.
                    pure = data.get("price_gram_24k")
                    if pure is None:
                        continue
                    value = Decimal(str(pure)) * Decimal(833) / Decimal(999)
                if value is None:
                    continue
                prices.append(
                    FetchedPrice(
                        metal="gold",
                        karat=karat,
                        currency=currency,
                        price_per_gram=Decimal(str(value)).quantize(Decimal("0.0001")),
                        source="goldapi",
                    )
                )
        else:
            spot = data.get("price")  # per troy ounce
            if spot is None:
                raise ProviderError(f"goldapi: no price for {symbol}")
            prices.append(
                FetchedPrice(
                    metal=metal,
                    karat=None,
                    currency=currency,
                    price_per_gram=(Decimal(str(spot)) / GRAMS_PER_TROY_OUNCE).quantize(
                        Decimal("0.0001")
                    ),
                    source="goldapi",
                )
            )
    if not prices:
        raise ProviderError("goldapi: empty result")
    return prices


def fetch_manual(config: dict, currency: str) -> list[FetchedPrice]:
    """Admin-entered per-gram prices. config example:

    {"prices": [{"metal": "gold", "karat": 18, "price_per_gram": "112.50"},
                {"metal": "platinum", "price_per_gram": "35.00"}]}
    """
    rows = config.get("prices") or []
    if not rows:
        raise ProviderError("manual: no prices configured")
    return [
        FetchedPrice(
            metal=r["metal"],
            karat=r.get("karat"),
            currency=r.get("currency", currency),
            price_per_gram=Decimal(str(r["price_per_gram"])),
            source="manual",
        )
        for r in rows
    ]


async def refresh_metal_prices(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    currency: str = "EUR",
    client: httpx.AsyncClient | None = None,
) -> list[MetalPriceSnapshot]:
    """Try active sources by priority; first success writes snapshots.

    Idempotent per run (each run appends a new snapshot generation — the time
    series is the design). Failures are logged, never raised past the job.
    """
    sources = (
        (
            await session.execute(
                select(MetalPriceSource)
                .where(
                    MetalPriceSource.tenant_id == tenant_id,
                    MetalPriceSource.is_active.is_(True),
                )
                .order_by(MetalPriceSource.priority)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for source in sources:
        try:
            if source.provider == "goldapi":
                if client is None:
                    async with httpx.AsyncClient() as own_client:
                        prices = await fetch_goldapi(source.config or {}, currency, own_client)
                else:
                    prices = await fetch_goldapi(source.config or {}, currency, client)
            elif source.provider == "manual":
                prices = fetch_manual(source.config or {}, currency)
            else:
                raise ProviderError(f"unknown provider '{source.provider}'")
        except ProviderError as exc:
            session.add(
                PriceRefreshLog(
                    tenant_id=tenant_id,
                    source=source.provider,
                    metal_or_pair="*",
                    value=None,
                    fetched_at=now,
                    ok=False,
                )
            )
            last_error = str(exc)  # noqa: F841 — kept for debugging/log payloads
            continue

        snapshots = []
        for p in prices:
            snap = MetalPriceSnapshot(
                tenant_id=tenant_id,
                metal=p.metal,
                karat=p.karat,
                currency=p.currency,
                price_per_gram=p.price_per_gram,
                source=p.source,
                fetched_at=now,
            )
            session.add(snap)
            snapshots.append(snap)
            session.add(
                PriceRefreshLog(
                    tenant_id=tenant_id,
                    source=p.source,
                    metal_or_pair=f"{p.metal}{'_' + str(p.karat) + 'k' if p.karat else ''}",
                    value=p.price_per_gram,
                    fetched_at=now,
                    ok=True,
                )
            )
        await session.flush()
        return snapshots

    return []  # every source failed — logged; pricing degrades to quote_only


async def latest_snapshot(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    metal: str,
    karat: int | None,
    currency: str,
) -> MetalPriceSnapshot | None:
    query = (
        select(MetalPriceSnapshot)
        .where(
            MetalPriceSnapshot.tenant_id == tenant_id,
            MetalPriceSnapshot.metal == metal,
            MetalPriceSnapshot.currency == currency,
        )
        .order_by(MetalPriceSnapshot.fetched_at.desc())
        .limit(1)
    )
    if karat is None:
        query = query.where(MetalPriceSnapshot.karat.is_(None))
    else:
        query = query.where(MetalPriceSnapshot.karat == karat)
    return (await session.execute(query)).scalar_one_or_none()
