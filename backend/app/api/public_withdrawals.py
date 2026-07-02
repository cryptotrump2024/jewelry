"""EU withdrawal function — Art. 11a, in force 19 June 2026 (docs/spec/12 §3a).

Two-step: POST /withdrawals (initiated) → POST /withdrawals/{id}/confirm
(confirmed), after which the engine records an acknowledgement on a durable
medium with content + date + time (email dispatch wires in with the mailer;
the record is authoritative). Eligibility derives from
order_items.non_returnable — bespoke/engraved items are exempt
(exempt_personalised), but the function itself must exist and be reachable
for eligible items.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.routes import DbSession
from app.models import Order, OrderItem, WithdrawalRequest
from app.tenancy.context import get_current_tenant

router = APIRouter(prefix="/api/v1", tags=["withdrawals"])


async def _order_or_404(session, order_id: uuid.UUID) -> Order:
    tid = get_current_tenant().tenant_id
    order = (
        await session.execute(
            select(Order).where(Order.tenant_id == tid, Order.id == order_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "order not found")
    return order


@router.get("/orders/{order_id}/withdrawal-eligibility")
async def withdrawal_eligibility(order_id: uuid.UUID, session: DbSession) -> dict:
    order = await _order_or_404(session, order_id)
    items = (
        (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id)))
        .scalars()
        .all()
    )
    return {
        "order_id": str(order.id),
        "per_item": [
            {
                "order_item_id": str(item.id),
                "status": "exempt_personalised" if item.non_returnable else "eligible",
                "reason": (
                    "Personalised/custom-made items are exempt from the right of "
                    "withdrawal (Art. 16(c) Consumer Rights Directive)."
                    if item.non_returnable
                    else "Eligible for withdrawal within the statutory period."
                ),
            }
            for item in items
        ],
    }


class WithdrawalCreate(BaseModel):
    order_id: uuid.UUID
    order_item_ids: list[uuid.UUID] | None = None  # None = whole order
    name: str
    contact: str  # email or phone — echoed into the acknowledgement
    reason: str | None = None


@router.post("/withdrawals", status_code=201)
async def create_withdrawal(payload: WithdrawalCreate, session: DbSession) -> dict:
    """Step 1 of the two-step function."""
    tid = get_current_tenant().tenant_id
    order = await _order_or_404(session, payload.order_id)

    items = (
        (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id)))
        .scalars()
        .all()
    )
    if payload.order_item_ids is not None:
        wanted = set(payload.order_item_ids)
        items = [i for i in items if i.id in wanted]
        if not items:
            raise HTTPException(404, "no matching order items")

    eligible = [i for i in items if not i.non_returnable]
    if not eligible:
        raise HTTPException(
            409,
            "All selected items are personalised/custom-made and exempt from "
            "the right of withdrawal.",
        )

    request = WithdrawalRequest(
        tenant_id=tid,
        order_id=order.id,
        customer_id=order.customer_id,
        eligibility_status="eligible",
        reason=payload.reason,
        submitted_at=datetime.now(UTC),
        status="initiated",
    )
    session.add(request)
    await session.flush()
    await session.commit()
    return {
        "withdrawal_request_id": str(request.id),
        "status": request.status,
        "eligible_item_ids": [str(i.id) for i in eligible],
        "next_step": f"/api/v1/withdrawals/{request.id}/confirm",
    }


@router.post("/withdrawals/{withdrawal_id}/confirm")
async def confirm_withdrawal(withdrawal_id: uuid.UUID, session: DbSession) -> dict:
    """Step 2: confirmation. The engine immediately records the durable-medium

    acknowledgement (content + date + time); the mailer delivers a copy when
    email infrastructure lands — the stored record is the legal anchor.
    """
    tid = get_current_tenant().tenant_id
    request = (
        await session.execute(
            select(WithdrawalRequest).where(
                WithdrawalRequest.tenant_id == tid, WithdrawalRequest.id == withdrawal_id
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, "withdrawal request not found")
    if request.status == "refunded":
        raise HTTPException(409, "withdrawal is already refunded")

    now = datetime.now(UTC)
    if request.status == "initiated":
        request.confirmed_at = now
        request.acknowledged_at = now
        request.ack_medium = "email"
        request.status = "acknowledged"
        await session.commit()
    return {
        "withdrawal_request_id": str(request.id),
        "status": request.status,
        "confirmed_at": request.confirmed_at.isoformat(),
        "acknowledged_at": request.acknowledged_at.isoformat(),
        "ack_medium": request.ack_medium,
    }


@router.get("/withdrawals/{withdrawal_id}")
async def get_withdrawal(withdrawal_id: uuid.UUID, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    request = (
        await session.execute(
            select(WithdrawalRequest).where(
                WithdrawalRequest.tenant_id == tid, WithdrawalRequest.id == withdrawal_id
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, "withdrawal request not found")
    return {
        "withdrawal_request_id": str(request.id),
        "order_id": str(request.order_id),
        "status": request.status,
        "eligibility_status": request.eligibility_status,
        "submitted_at": request.submitted_at.isoformat() if request.submitted_at else None,
        "confirmed_at": request.confirmed_at.isoformat() if request.confirmed_at else None,
        "acknowledged_at": (
            request.acknowledged_at.isoformat() if request.acknowledged_at else None
        ),
    }
