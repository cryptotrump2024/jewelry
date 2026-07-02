"""Admin pricing configuration + imports (Phase 5).

Rules over hardcoding: every number the pricing engine uses is editable here
— labor, margins, buffers, VAT, metal prices (manual source or refresh),
diamond price tables via CSV import with dry-run.
"""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.admin_auth import require_admin
from app.api.routes import DbSession
from app.imports.framework import run_diamond_price_import
from app.models import (
    Buffer,
    LaborCost,
    Margin,
    MetalPriceSnapshot,
    MetalPriceSource,
    SupplierImportRow,
    VatRule,
)
from app.sources.metal import refresh_metal_prices
from app.tenancy.context import get_current_tenant
from app.tenancy.repository import TenantScopedRepository

router = APIRouter(
    prefix="/admin/pricing", tags=["admin-pricing"], dependencies=[Depends(require_admin)]
)


class LaborRepo(TenantScopedRepository[LaborCost]):
    model = LaborCost


class MarginRepo(TenantScopedRepository[Margin]):
    model = Margin


class BufferRepo(TenantScopedRepository[Buffer]):
    model = Buffer


class VatRepo(TenantScopedRepository[VatRule]):
    model = VatRule


class SourceRepo(TenantScopedRepository[MetalPriceSource]):
    model = MetalPriceSource


@router.get("/config")
async def pricing_config(session: DbSession) -> dict[str, Any]:
    """Everything the pricing engine reads, in one screenful."""
    tid = get_current_tenant().tenant_id
    labor = await LaborRepo(session).list()
    margins = await MarginRepo(session).list()
    buffers = await BufferRepo(session).list()
    vat = await VatRepo(session).list()
    sources = await SourceRepo(session).list()

    latest_prices = (
        (
            await session.execute(
                select(MetalPriceSnapshot)
                .where(MetalPriceSnapshot.tenant_id == tid)
                .order_by(MetalPriceSnapshot.fetched_at.desc())
                .limit(12)
            )
        )
        .scalars()
        .all()
    )
    return {
        "labor": [
            {
                "id": str(r.id),
                "operation": r.operation,
                "basis": r.basis,
                "amount_minor": r.amount_minor,
                "currency": r.currency,
            }
            for r in labor
        ],
        "margins": [
            {
                "id": str(r.id),
                "template_id": str(r.template_id) if r.template_id else None,
                "market": r.market,
                "band": r.band,
                "type": r.type,
                "value": str(r.value),
            }
            for r in margins
        ],
        "buffers": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "type": r.type,
                "value": str(r.value),
                "currency": r.currency,
            }
            for r in buffers
        ],
        "vat_rules": [
            {
                "id": str(r.id),
                "market": r.market,
                "rate": str(r.rate),
                "price_includes_vat": r.price_includes_vat,
            }
            for r in vat
        ],
        "metal_sources": [
            {
                "id": str(r.id),
                "provider": r.provider,
                "priority": r.priority,
                "is_active": r.is_active,
                "config": r.config if r.provider == "manual" else {"configured": bool(r.config)},
            }
            for r in sources
        ],
        "latest_metal_prices": [
            {
                "metal": p.metal,
                "karat": p.karat,
                "price_per_gram": str(p.price_per_gram),
                "currency": p.currency,
                "source": p.source,
                "fetched_at": p.fetched_at.isoformat(),
            }
            for p in latest_prices
        ],
    }


class AmountUpdate(BaseModel):
    amount_minor: int


class ValueUpdate(BaseModel):
    type: str | None = None  # percent|fixed
    value: Decimal


class VatUpdate(BaseModel):
    rate: Decimal
    price_includes_vat: bool | None = None


class ManualPricesUpdate(BaseModel):
    prices: list[dict[str, Any]]


@router.put("/labor/{row_id}")
async def update_labor(row_id: uuid.UUID, payload: AmountUpdate, session: DbSession) -> dict:
    row = await LaborRepo(session).get(row_id)
    if row is None:
        raise HTTPException(404, "labor cost not found")
    row.amount_minor = payload.amount_minor
    await session.commit()
    return {"id": str(row.id), "amount_minor": row.amount_minor}


@router.put("/margins/{row_id}")
async def update_margin(row_id: uuid.UUID, payload: ValueUpdate, session: DbSession) -> dict:
    row = await MarginRepo(session).get(row_id)
    if row is None:
        raise HTTPException(404, "margin not found")
    if payload.type:
        row.type = payload.type
    row.value = payload.value
    await session.commit()
    return {"id": str(row.id), "type": row.type, "value": str(row.value)}


@router.put("/buffers/{row_id}")
async def update_buffer(row_id: uuid.UUID, payload: ValueUpdate, session: DbSession) -> dict:
    row = await BufferRepo(session).get(row_id)
    if row is None:
        raise HTTPException(404, "buffer not found")
    if payload.type:
        row.type = payload.type
    row.value = payload.value
    await session.commit()
    return {"id": str(row.id), "type": row.type, "value": str(row.value)}


@router.put("/vat/{row_id}")
async def update_vat(row_id: uuid.UUID, payload: VatUpdate, session: DbSession) -> dict:
    row = await VatRepo(session).get(row_id)
    if row is None:
        raise HTTPException(404, "vat rule not found")
    row.rate = payload.rate
    if payload.price_includes_vat is not None:
        row.price_includes_vat = payload.price_includes_vat
    await session.commit()
    return {"id": str(row.id), "rate": str(row.rate)}


@router.put("/manual-metal-prices")
async def update_manual_prices(payload: ManualPricesUpdate, session: DbSession) -> dict:
    """Replace the manual source's price list, then refresh snapshots."""
    tid = get_current_tenant().tenant_id
    source = (
        await session.execute(
            select(MetalPriceSource).where(
                MetalPriceSource.tenant_id == tid, MetalPriceSource.provider == "manual"
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(404, "no manual metal source configured")
    source.config = {"prices": payload.prices}
    snaps = await refresh_metal_prices(session, tid, "EUR")
    await session.commit()
    return {"updated": True, "snapshots_written": len(snaps)}


@router.post("/refresh-metals")
async def refresh_metals(session: DbSession) -> dict:
    """Run the source chain now (normally a background job on a schedule)."""
    tid = get_current_tenant().tenant_id
    snaps = await refresh_metal_prices(session, tid, "EUR")
    await session.commit()
    return {
        "snapshots_written": len(snaps),
        "prices": [
            {"metal": s.metal, "karat": s.karat, "price_per_gram": str(s.price_per_gram)}
            for s in snaps
        ],
    }


class DiamondImportRequest(BaseModel):
    csv_text: str
    mapping: dict[str, str] | None = None
    dry_run: bool = True


@router.post("/imports/diamond-prices")
async def import_diamond_prices(payload: DiamondImportRequest, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    job = await run_diamond_price_import(
        session, tid, payload.csv_text, mapping=payload.mapping, dry_run=payload.dry_run
    )
    rows = (
        (
            await session.execute(
                select(SupplierImportRow).where(SupplierImportRow.import_job_id == job.id)
            )
        )
        .scalars()
        .all()
    )
    await session.commit()
    return {
        "job_id": str(job.id),
        "dry_run": job.dry_run,
        "status": job.status,
        "stats": job.stats,
        "rows": [
            {"status": r.status, "raw": r.raw, "messages": r.messages} for r in rows
        ],
    }
