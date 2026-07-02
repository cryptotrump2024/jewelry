"""FX source adapter — ECB daily euro reference rates (docs/spec/06 §7).

ECB rates are informational (not transaction rates): used for displayed
prices; the PSP settlement rate governs the charge. The rate used is always
stored in the price snapshot. Cached daily; hot path reads fx_rates.
"""

import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FxRate, PriceRefreshLog

ECB_DAILY_CSV_URL = (
    "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.csv"  # base EUR
)


class FxProviderError(RuntimeError):
    pass


def parse_ecb_csv(text: str) -> dict[str, Decimal]:
    """ECB daily CSV: header 'Date, USD, JPY, ...' + one data row."""
    reader = csv.reader(io.StringIO(text.strip()))
    rows = [row for row in reader if row]
    if len(rows) < 2:
        raise FxProviderError("ecb: malformed CSV")
    header = [cell.strip() for cell in rows[0]]
    values = [cell.strip() for cell in rows[1]]
    rates: dict[str, Decimal] = {}
    for name, value in zip(header, values, strict=False):
        if name and name != "Date" and value and value != "N/A":
            try:
                rates[name] = Decimal(value)
            except ArithmeticError:
                continue
    if not rates:
        raise FxProviderError("ecb: no rates parsed")
    return rates


async def refresh_fx_rates(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    quote_currencies: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[FxRate]:
    """Fetch ECB daily rates (base EUR) and append fx_rates rows."""
    now = datetime.now(UTC)
    try:
        if client is None:
            async with httpx.AsyncClient() as own_client:
                resp = await own_client.get(ECB_DAILY_CSV_URL, timeout=15)
        else:
            resp = await client.get(ECB_DAILY_CSV_URL, timeout=15)
        if resp.status_code != 200:
            raise FxProviderError(f"ecb: HTTP {resp.status_code}")
        rates = parse_ecb_csv(resp.text)
    except (FxProviderError, httpx.HTTPError):
        session.add(
            PriceRefreshLog(
                tenant_id=tenant_id,
                source="ecb",
                metal_or_pair="EUR/*",
                value=None,
                fetched_at=now,
                ok=False,
            )
        )
        await session.flush()
        return []

    wanted = set(quote_currencies) if quote_currencies else set(rates)
    stored: list[FxRate] = []
    for currency, rate in rates.items():
        if currency not in wanted:
            continue
        row = FxRate(
            tenant_id=tenant_id,
            base_currency="EUR",
            quote_currency=currency,
            rate=rate,
            source="ecb",
            fetched_at=now,
        )
        session.add(row)
        stored.append(row)
        session.add(
            PriceRefreshLog(
                tenant_id=tenant_id,
                source="ecb",
                metal_or_pair=f"EUR/{currency}",
                value=rate,
                fetched_at=now,
                ok=True,
            )
        )
    await session.flush()
    return stored


async def latest_rate(
    session: AsyncSession, tenant_id: uuid.UUID, base: str, quote: str
) -> FxRate | None:
    return (
        await session.execute(
            select(FxRate)
            .where(
                FxRate.tenant_id == tenant_id,
                FxRate.base_currency == base,
                FxRate.quote_currency == quote,
            )
            .order_by(FxRate.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
