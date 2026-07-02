"""Phase 4 exit tests (docs/spec/14):

  "live gold spot flows into a real price; a CSV import dry-runs, validates
   per row, and commits idempotently."

GoldAPI/ECB are exercised through httpx.MockTransport with recorded-shape
responses; the manual provider covers the no-API-key path (fallback chain).
"""

import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.db import get_session_factory
from app.imports.framework import run_diamond_price_import
from app.models import (
    DiamondPriceTable,
    MetalPriceSource,
    PriceRefreshLog,
    SupplierImportRow,
    Tenant,
)
from app.pricing import MetalPriceInput, PricingInputs, WeightInput, compute_price
from app.pricing.inputs import MarginInput, VatInput
from app.sources.fx import parse_ecb_csv, refresh_fx_rates
from app.sources.metal import latest_snapshot, refresh_metal_prices

GOLDAPI_XAU = {
    "price": 3800.55,
    "price_gram_24k": 122.18,
    "price_gram_22k": 111.99,
    "price_gram_20k": 101.85,
    "price_gram_18k": 91.63,
    "price_gram_14k": 71.47,
}
GOLDAPI_XAG = {"price": 46.10}
GOLDAPI_XPT = {"price": 1450.00}

ECB_CSV = "Date, USD, JPY, GBP, \n01 July 2026, 1.1042, 170.35, 0.8523, \n"


def goldapi_transport(fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(500, text="boom")
        if "XAU" in request.url.path:
            return httpx.Response(200, json=GOLDAPI_XAU)
        if "XAG" in request.url.path:
            return httpx.Response(200, json=GOLDAPI_XAG)
        if "XPT" in request.url.path:
            return httpx.Response(200, json=GOLDAPI_XPT)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def _tenant_id(session):
    return (
        await session.execute(select(Tenant).where(Tenant.slug == "default"))
    ).scalar_one().id


@pytest.fixture
async def db():
    async with get_session_factory()() as session:
        yield session
        await session.rollback()


async def _add_source(session, tenant_id, provider, priority, config):
    session.add(
        MetalPriceSource(
            tenant_id=tenant_id,
            provider=provider,
            priority=priority,
            config=config,
            is_active=True,
        )
    )
    await session.flush()


# --- Metal sources ---


async def test_goldapi_refresh_writes_per_karat_snapshots(db):
    tid = await _tenant_id(db)
    await _add_source(db, tid, "goldapi", 0, {"api_key": "test-key"})

    async with httpx.AsyncClient(transport=goldapi_transport()) as client:
        snaps = await refresh_metal_prices(db, tid, "EUR", client=client)

    by_key = {(s.metal, s.karat): s for s in snaps}
    assert by_key[("gold", 18)].price_per_gram == Decimal("91.6300")
    assert by_key[("gold", 20)].price_per_gram == Decimal("101.8500")
    # Spot metals converted per gram: 46.10 / 31.1034768.
    assert by_key[("silver", None)].price_per_gram == Decimal("1.4821")
    assert by_key[("platinum", None)].price_per_gram == Decimal("46.6186")

    logs = (
        (
            await db.execute(
                select(PriceRefreshLog).where(
                    PriceRefreshLog.tenant_id == tid, PriceRefreshLog.ok.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    assert {log.metal_or_pair for log in logs} >= {"gold_18k", "silver", "platinum"}


async def test_fallback_chain_goldapi_down_manual_wins(db):
    tid = await _tenant_id(db)
    await _add_source(db, tid, "goldapi", 0, {"api_key": "test-key"})
    await _add_source(
        db,
        tid,
        "manual",
        1,
        {"prices": [{"metal": "gold", "karat": 18, "price_per_gram": "112.50"}]},
    )

    async with httpx.AsyncClient(transport=goldapi_transport(fail=True)) as client:
        snaps = await refresh_metal_prices(db, tid, "EUR", client=client)

    assert len(snaps) == 1
    assert snaps[0].source == "manual"
    assert snaps[0].price_per_gram == Decimal("112.50")
    failed = (
        await db.execute(
            select(func.count())
            .select_from(PriceRefreshLog)
            .where(PriceRefreshLog.tenant_id == tid, PriceRefreshLog.ok.is_(False))
        )
    ).scalar_one()
    assert failed == 1  # the goldapi failure was logged, not raised


async def test_all_sources_down_returns_empty_and_logs(db):
    tid = await _tenant_id(db)
    # Disable the seeded manual fallback for this test (rolled back after).
    from sqlalchemy import update

    await db.execute(
        update(MetalPriceSource)
        .where(MetalPriceSource.tenant_id == tid)
        .values(is_active=False)
    )
    await _add_source(db, tid, "goldapi", 0, {})  # missing api_key → ProviderError

    snaps = await refresh_metal_prices(db, tid, "EUR")
    assert snaps == []
    failed = (
        await db.execute(
            select(func.count())
            .select_from(PriceRefreshLog)
            .where(PriceRefreshLog.tenant_id == tid, PriceRefreshLog.ok.is_(False))
        )
    ).scalar_one()
    assert failed >= 1


async def test_live_spot_flows_into_a_real_price(db):  # Phase 4 exit, part 1
    tid = await _tenant_id(db)
    await _add_source(db, tid, "goldapi", 0, {"api_key": "test-key"})
    async with httpx.AsyncClient(transport=goldapi_transport()) as client:
        await refresh_metal_prices(db, tid, "EUR", client=client)

    snap = await latest_snapshot(db, tid, "gold", 18, "EUR")
    assert snap is not None

    result = compute_price(
        PricingInputs(
            currency="EUR",
            metal_price=MetalPriceInput(
                price_per_gram=snap.price_per_gram,
                currency=snap.currency,
                source=snap.source,
                fetched_at=snap.fetched_at,
                snapshot_id=str(snap.id),
            ),
            weight=WeightInput(
                cad_volume_mm3=Decimal("380"), specific_gravity=Decimal("15.58")
            ),
            stone=None,
            margin=MarginInput(type="percent", value=Decimal("0.60")),
            vat=VatInput(market="NL", rate=Decimal("0.21")),
        )
    )
    assert result.status == "purchasable"
    # 6.039 g × 91.63 × 1.05 → €581.02 → then margin+VAT.
    assert result.itemized["metal_cost"] == 58102
    assert result.snapshot["source_refs"]["metal_price_snapshot_id"] == str(snap.id)


# --- FX ---


def test_parse_ecb_csv():
    rates = parse_ecb_csv(ECB_CSV)
    assert rates["USD"] == Decimal("1.1042")
    assert rates["GBP"] == Decimal("0.8523")
    assert "Date" not in rates


async def test_refresh_fx_rates_writes_rows(db):
    tid = await _tenant_id(db)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=ECB_CSV))
    async with httpx.AsyncClient(transport=transport) as client:
        rows = await refresh_fx_rates(db, tid, ["USD"], client=client)
    assert len(rows) == 1
    assert rows[0].base_currency == "EUR" and rows[0].quote_currency == "USD"
    assert rows[0].rate == Decimal("1.1042")


# --- CSV import (Phase 4 exit, part 2) ---

# H/VS2 quality is deliberately NOT in the seeded tables (those are G/SI1),
# so these rows are genuine creates.
CSV_OK = """stone_type,shape,carat_min,carat_max,color,clarity,price_per_carat,currency
lab_diamond,oval,0.30,0.49,H,VS2,950,EUR
lab_diamond,oval,0.50,0.69,H,VS2,1200,EUR
natural_diamond,round,1.00,1.49,F,VS1,8200,EUR
"""

CSV_WITH_ERRORS = """stone_type,shape,carat_min,carat_max,color,clarity,price_per_carat,currency
lab_diamond,oval,0.30,0.49,G,SI1,950,EUR
moissanite,oval,0.50,0.69,G,SI1,600,EUR
lab_diamond,heart,0.50,0.69,G,SI1,1200,EUR
lab_diamond,oval,0.90,0.70,G,SI1,abc,EURO
"""


async def _price_table_count(db, tid) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(DiamondPriceTable)
            .where(DiamondPriceTable.tenant_id == tid)
        )
    ).scalar_one()


async def test_dry_run_validates_rows_touches_nothing(db):
    tid = await _tenant_id(db)
    before = await _price_table_count(db, tid)
    job = await run_diamond_price_import(db, tid, CSV_WITH_ERRORS, dry_run=True)

    assert job.dry_run is True
    assert job.stats == {"rows": 4, "ok": 1, "errors": 3, "created": 0, "updated": 0}
    assert await _price_table_count(db, tid) == before  # dry-run never writes targets

    rows = (
        (
            await db.execute(
                select(SupplierImportRow).where(SupplierImportRow.import_job_id == job.id)
            )
        )
        .scalars()
        .all()
    )
    errors = {
        msg for r in rows if r.messages for msg in r.messages["errors"]
    }
    assert any("moissanite" in e for e in errors)  # unknown stone type (by design)
    assert any("heart" in e for e in errors)  # unknown shape
    assert any("carat_min must be < carat_max" in e for e in errors)


async def test_commit_writes_then_recommit_is_idempotent(db):
    tid = await _tenant_id(db)
    before = await _price_table_count(db, tid)
    job1 = await run_diamond_price_import(db, tid, CSV_OK, dry_run=False)
    assert job1.stats["created"] == 3 and job1.stats["errors"] == 0

    job2 = await run_diamond_price_import(db, tid, CSV_OK, dry_run=False)
    assert job2.stats["created"] == 0 and job2.stats["updated"] == 0  # unchanged

    assert await _price_table_count(db, tid) == before + 3

    # Price change in a re-imported file updates in place, no duplicates.
    job3 = await run_diamond_price_import(
        db, tid, CSV_OK.replace("950,EUR", "999,EUR"), dry_run=False
    )
    assert job3.stats["updated"] == 1 and job3.stats["created"] == 0


async def test_import_with_column_mapping(db):
    tid = await _tenant_id(db)
    csv_foreign = (
        "Steen,Vorm,Van,Tot,Kleur,Zuiverheid,Prijs,Valuta\n"
        "lab_diamond,oval,0.30,0.49,G,SI1,950,EUR\n"
    )
    mapping = {
        "stone_type": "Steen",
        "shape": "Vorm",
        "carat_min": "Van",
        "carat_max": "Tot",
        "color": "Kleur",
        "clarity": "Zuiverheid",
        "price_per_carat": "Prijs",
        "currency": "Valuta",
    }
    job = await run_diamond_price_import(db, tid, csv_foreign, mapping=mapping, dry_run=True)
    assert job.stats["ok"] == 1 and job.stats["errors"] == 0


def test_goldapi_fixture_is_valid_json():
    # Guard: the recorded response shape stays serializable (fixture hygiene).
    assert json.loads(json.dumps(GOLDAPI_XAU))["price_gram_18k"] == 91.63
