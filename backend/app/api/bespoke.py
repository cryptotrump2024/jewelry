"""Bespoke endpoints (docs/spec/13 §6). Customer-facing: create request,

design deposit, approve. Admin-facing (token-guarded): revisions + quote.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.admin_auth import require_admin
from app.api.routes import DbSession
from app.models import BespokeQuote, BespokeRequest, BespokeRevision
from app.services.bespoke import (
    add_quote,
    add_revision,
    approve,
    create_bespoke_request,
    create_design_deposit_intent,
)
from app.services.orders import OrderFlowError
from app.tenancy.context import get_current_tenant

router = APIRouter(prefix="/api/v1/bespoke", tags=["bespoke"])
admin_router = APIRouter(
    prefix="/api/v1/bespoke", tags=["bespoke-admin"], dependencies=[Depends(require_admin)]
)


async def _request_or_404(session, request_id: uuid.UUID) -> BespokeRequest:
    tid = get_current_tenant().tenant_id
    request = (
        await session.execute(
            select(BespokeRequest).where(
                BespokeRequest.tenant_id == tid, BespokeRequest.id == request_id
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, "bespoke request not found")
    return request


class BespokeCreate(BaseModel):
    source: str = "upload"
    brief: dict[str, Any] = Field(default_factory=dict)
    currency: str = "EUR"


@router.post("/requests", status_code=201)
async def post_request(payload: BespokeCreate, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    try:
        request = await create_bespoke_request(
            session, tid, payload.source, payload.brief, payload.currency
        )
    except OrderFlowError as exc:
        raise HTTPException(422, str(exc)) from None
    await session.commit()
    return {
        "id": str(request.id),
        "status": request.status,
        "price_range": (
            {
                "min_minor": request.price_range_min_minor,
                "max_minor": request.price_range_max_minor,
                "currency": request.currency,
            }
            if request.price_range_min_minor is not None
            else None
        ),
    }


@router.get("/requests/{request_id}")
async def get_request(request_id: uuid.UUID, session: DbSession) -> dict:
    request = await _request_or_404(session, request_id)
    revisions = (
        (
            await session.execute(
                select(BespokeRevision)
                .where(BespokeRevision.bespoke_request_id == request.id)
                .order_by(BespokeRevision.round_no)
            )
        )
        .scalars()
        .all()
    )
    quotes = (
        (
            await session.execute(
                select(BespokeQuote)
                .where(BespokeQuote.bespoke_request_id == request.id)
                .order_by(BespokeQuote.created_at)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(request.id),
        "status": request.status,
        "brief": request.brief,
        "revisions": [
            {"round_no": r.round_no, "status": r.status, "notes": r.notes} for r in revisions
        ],
        "quotes": [
            {
                "id": str(q.id),
                "total_minor": q.total_minor,
                "currency": q.currency,
                "itemized": q.itemized,
                "valid_until": q.valid_until.isoformat() if q.valid_until else None,
            }
            for q in quotes
        ],
    }


@router.post("/requests/{request_id}/design-deposit", status_code=201)
async def post_design_deposit(request_id: uuid.UUID, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    request = await _request_or_404(session, request_id)
    try:
        payment, client_payload = await create_design_deposit_intent(session, tid, request)
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {"payment_id": str(payment.id), **client_payload}


class ApproveInput(BaseModel):
    approved_by: str


@router.post("/requests/{request_id}/approve")
async def post_approve(
    request_id: uuid.UUID, payload: ApproveInput, session: DbSession
) -> dict:
    tid = get_current_tenant().tenant_id
    request = await _request_or_404(session, request_id)
    try:
        order = await approve(session, tid, request, payload.approved_by)
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {
        "order_id": str(order.id),
        "order_status": order.status,
        "totals": order.totals,
        "request_status": request.status,
    }


class RevisionInput(BaseModel):
    cad_media_id: uuid.UUID | None = None
    render_media_id: uuid.UUID | None = None
    notes: str | None = None


@admin_router.post("/requests/{request_id}/revisions", status_code=201)
async def post_revision(
    request_id: uuid.UUID, payload: RevisionInput, session: DbSession
) -> dict:
    request = await _request_or_404(session, request_id)
    try:
        revision = await add_revision(
            session, request, payload.cad_media_id, payload.render_media_id, payload.notes
        )
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {"id": str(revision.id), "round_no": revision.round_no}


class QuoteInput(BaseModel):
    itemized: dict[str, int]
    total_minor: int


@admin_router.post("/requests/{request_id}/quote", status_code=201)
async def post_bespoke_quote(
    request_id: uuid.UUID, payload: QuoteInput, session: DbSession
) -> dict:
    request = await _request_or_404(session, request_id)
    try:
        quote = await add_quote(session, request, payload.itemized, payload.total_minor)
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {
        "id": str(quote.id),
        "total_minor": quote.total_minor,
        "request_status": request.status,
    }
