"""Production / factory endpoints (docs/spec/13 §7, workflow in 10).

Hard compliance gate (Phase 8 exit): a hallmark-required item cannot ship
without an applied hallmark record. Dutch thresholds (docs/spec/12,
confirmed by WaarborgHolland): gold ≥ 1 g, silver ≥ 8 g, platinum ≥ 0.5 g.

Guarded by the admin token for now; dedicated factory accounts arrive with
the factory portal.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.admin_auth import require_admin
from app.api.routes import DbSession
from app.models import (
    HallmarkRecord,
    Order,
    OrderConfiguration,
    OrderItem,
    PriceSnapshot,
    ProductionJob,
    ProductionStep,
    QcCheck,
    Shipment,
)
from app.tenancy.context import get_current_tenant

router = APIRouter(
    prefix="/api/v1/production", tags=["production"], dependencies=[Depends(require_admin)]
)

HALLMARK_THRESHOLDS_G = {
    "gold": Decimal("1"),
    "silver": Decimal("8"),
    "platinum": Decimal("0.5"),
}

STEP_VALUES = [
    "cad",
    "awaiting_approval",
    "casting",
    "stone_setting",
    "polishing",
    "hallmarking",
    "qc",
    "shipping",
]


async def _job_or_404(session, job_id: uuid.UUID) -> ProductionJob:
    tid = get_current_tenant().tenant_id
    job = (
        await session.execute(
            select(ProductionJob).where(
                ProductionJob.tenant_id == tid, ProductionJob.id == job_id
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "production job not found")
    return job


async def _job_context(session, job: ProductionJob) -> tuple[OrderItem, dict[str, Any]]:
    item = (
        await session.execute(select(OrderItem).where(OrderItem.id == job.order_item_id))
    ).scalar_one()
    snapshot = (
        await session.execute(
            select(PriceSnapshot).where(PriceSnapshot.id == item.price_snapshot_id)
        )
    ).scalar_one()
    resolved = (
        await session.execute(
            select(OrderConfiguration).where(OrderConfiguration.order_item_id == item.id)
        )
    ).scalar_one_or_none()
    spec = resolved.resolved_spec if resolved else {}
    return item, {"snapshot": snapshot, "resolved": resolved, "spec": spec}


def _metal_key(selections: dict[str, Any]) -> str | None:
    metal_code = selections.get("metal")
    if isinstance(metal_code, str) and "_" in metal_code:
        return metal_code.split("_", 1)[0]
    return metal_code if isinstance(metal_code, str) else None


def _weight_g(spec: dict[str, Any], snapshot: PriceSnapshot) -> Decimal | None:
    actual = spec.get("actual_weight_g")
    if actual is not None:
        return Decimal(str(actual))
    weight = (snapshot.inputs or {}).get("weight") or {}
    for key in ("override_g", "estimated_g"):
        if weight.get(key) is not None:
            return Decimal(str(weight[key]))
    return None


def hallmark_required(metal_key: str | None, weight_g: Decimal | None) -> bool:
    """Unknown metal/weight counts as required — fail safe for compliance."""
    if metal_key is None or weight_g is None:
        return True
    threshold = HALLMARK_THRESHOLDS_G.get(metal_key)
    if threshold is None:
        return True
    return weight_g >= threshold


@router.get("/jobs")
async def list_jobs(session: DbSession, status: str | None = None) -> list[dict]:
    tid = get_current_tenant().tenant_id
    query = select(ProductionJob).where(ProductionJob.tenant_id == tid)
    if status:
        query = query.where(ProductionJob.status == status)
    jobs = (await session.execute(query.order_by(ProductionJob.created_at))).scalars().all()
    return [
        {
            "id": str(j.id),
            "order_item_id": str(j.order_item_id),
            "status": j.status,
            "priority": j.priority,
            "due_at": j.due_at.isoformat() if j.due_at else None,
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, session: DbSession) -> dict:
    """The factory spec sheet: configuration, stone, weight, hallmark flag."""
    job = await _job_or_404(session, job_id)
    item, ctx = await _job_context(session, job)
    snapshot: PriceSnapshot = ctx["snapshot"]
    spec = ctx["spec"]
    metal = _metal_key(item.configuration)
    weight = _weight_g(spec, snapshot)

    steps = (
        (
            await session.execute(
                select(ProductionStep)
                .where(ProductionStep.production_job_id == job.id)
                .order_by(ProductionStep.created_at)
            )
        )
        .scalars()
        .all()
    )
    hallmarks = (
        (
            await session.execute(
                select(HallmarkRecord).where(HallmarkRecord.production_job_id == job.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(job.id),
        "status": job.status,
        "spec_sheet": {
            "configuration": item.configuration,
            "engraving_text": item.engraving_text,
            "stone": (snapshot.inputs or {}).get("stone"),
            "weight": (snapshot.inputs or {}).get("weight"),
            "actual_weight_g": spec.get("actual_weight_g"),
            "non_returnable": item.non_returnable,
            "hallmark_required": hallmark_required(metal, weight),
            "metal": metal,
        },
        "steps": [
            {"step": s.step, "status": s.status, "notes": s.notes} for s in steps
        ],
        "hallmark_records": [
            {
                "required": h.required,
                "status": h.status,
                "fineness": h.fineness,
                "responsibility_mark": h.responsibility_mark,
                "assay_office": h.assay_office,
            }
            for h in hallmarks
        ],
    }


class StepUpdate(BaseModel):
    step: str
    status: str = "completed"
    notes: str | None = None


@router.post("/jobs/{job_id}/steps", status_code=201)
async def record_step(job_id: uuid.UUID, payload: StepUpdate, session: DbSession) -> dict:
    if payload.step not in STEP_VALUES:
        raise HTTPException(422, f"unknown step '{payload.step}'")
    job = await _job_or_404(session, job_id)
    now = datetime.now(UTC)
    step = ProductionStep(
        production_job_id=job.id,
        step=payload.step,
        status=payload.status,
        notes=payload.notes,
        started_at=now,
        completed_at=now if payload.status == "completed" else None,
    )
    session.add(step)
    job.status = f"{payload.step}_{payload.status}"[:30]
    await session.commit()
    return {"id": str(step.id), "job_status": job.status}


class ActualWeight(BaseModel):
    grams: Decimal


@router.post("/jobs/{job_id}/actual-weight")
async def record_actual_weight(
    job_id: uuid.UUID, payload: ActualWeight, session: DbSession
) -> dict:
    """Est-vs-actual tracking; the actual weight also drives hallmark checks."""
    if payload.grams <= 0:
        raise HTTPException(422, "grams must be positive")
    job = await _job_or_404(session, job_id)
    _item, ctx = await _job_context(session, job)
    resolved: OrderConfiguration | None = ctx["resolved"]
    if resolved is None:
        raise HTTPException(409, "job has no resolved configuration")
    resolved.resolved_spec = dict(resolved.resolved_spec) | {
        "actual_weight_g": str(payload.grams)
    }
    await session.commit()
    estimated = ((ctx["snapshot"].inputs or {}).get("weight") or {}).get("estimated_g")
    return {
        "actual_weight_g": str(payload.grams),
        "estimated_g": estimated,
    }


class QcInput(BaseModel):
    checklist: dict[str, Any]
    passed: bool
    checked_by: str | None = None


@router.post("/jobs/{job_id}/qc", status_code=201)
async def record_qc(job_id: uuid.UUID, payload: QcInput, session: DbSession) -> dict:
    job = await _job_or_404(session, job_id)
    qc = QcCheck(
        production_job_id=job.id,
        checklist=payload.checklist,
        passed=payload.passed,
        checked_by=payload.checked_by,
        checked_at=datetime.now(UTC),
    )
    session.add(qc)
    job.status = "qc_passed" if payload.passed else "qc_failed"
    await session.commit()
    return {"id": str(qc.id), "passed": qc.passed, "job_status": job.status}


class HallmarkInput(BaseModel):
    fineness: int
    responsibility_mark: str
    assay_office: str  # waarborg_holland|ewn|ccm|other
    status: str = "applied"


@router.post("/jobs/{job_id}/hallmark", status_code=201)
async def record_hallmark(
    job_id: uuid.UUID, payload: HallmarkInput, session: DbSession
) -> dict:
    if payload.assay_office not in ("waarborg_holland", "ewn", "ccm", "other"):
        raise HTTPException(422, "unknown assay office")
    job = await _job_or_404(session, job_id)
    item, ctx = await _job_context(session, job)
    metal = _metal_key(item.configuration)
    record = HallmarkRecord(
        production_job_id=job.id,
        required=hallmark_required(metal, _weight_g(ctx["spec"], ctx["snapshot"])),
        metal=metal,
        fineness=payload.fineness,
        responsibility_mark=payload.responsibility_mark,
        assay_office=payload.assay_office,
        status=payload.status,
        applied_at=datetime.now(UTC) if payload.status == "applied" else None,
    )
    session.add(record)
    await session.commit()
    return {"id": str(record.id), "status": record.status}


class ShipmentInput(BaseModel):
    carrier: str
    tracking: str
    insured: bool = True


@router.post("/jobs/{job_id}/shipment", status_code=201)
async def ship(job_id: uuid.UUID, payload: ShipmentInput, session: DbSession) -> dict:
    """THE compliance gate: hallmark-required items cannot ship without an

    applied hallmark record (Phase 8 exit test).
    """
    job = await _job_or_404(session, job_id)
    item, ctx = await _job_context(session, job)
    metal = _metal_key(item.configuration)
    weight = _weight_g(ctx["spec"], ctx["snapshot"])

    if hallmark_required(metal, weight):
        applied = (
            await session.execute(
                select(HallmarkRecord).where(
                    HallmarkRecord.production_job_id == job.id,
                    HallmarkRecord.status == "applied",
                )
            )
        ).scalar_one_or_none()
        if applied is None:
            raise HTTPException(
                409,
                "hallmark required for this item (metal/weight above the legal "
                "threshold) — record an applied hallmark before shipping",
            )

    order = (
        await session.execute(select(Order).where(Order.id == item.order_id))
    ).scalar_one()
    shipment = Shipment(
        order_id=order.id,
        carrier=payload.carrier,
        tracking=payload.tracking,
        insured=payload.insured,
        shipped_at=datetime.now(UTC),
    )
    session.add(shipment)
    job.status = "shipped"
    order.status = "shipped"
    await session.commit()
    return {"id": str(shipment.id), "job_status": job.status, "order_status": order.status}
