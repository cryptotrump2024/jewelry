"""Public quote/order/payment endpoints (docs/spec/13 §4–5)."""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.routes import DbSession
from app.models import Order, OrderItem, Payment, PriceSnapshot, ProductTemplate, Quote
from app.services.orders import (
    OrderFlowError,
    complete_mock_payment,
    create_order_from_quote,
    create_payment_intent,
    create_quote,
)
from app.tenancy.context import get_current_tenant

router = APIRouter(prefix="/api/v1", tags=["orders"])


class QuoteRequest(BaseModel):
    template_id: uuid.UUID
    selections: dict[str, Any] = Field(default_factory=dict)
    market: str = "NL"
    currency: str = "EUR"


@router.post("/quotes", status_code=201)
async def post_quote(payload: QuoteRequest, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    template = (
        await session.execute(
            select(ProductTemplate).where(
                ProductTemplate.tenant_id == tid,
                ProductTemplate.id == payload.template_id,
                ProductTemplate.status == "active",
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "template not found")
    try:
        quote, snapshot = await create_quote(
            session, tid, template, payload.selections, payload.market, payload.currency
        )
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {
        "id": str(quote.id),
        "status": quote.status,
        "expires_at": quote.expires_at.isoformat(),
        "total": {"amount_minor": snapshot.total_minor, "currency": snapshot.currency},
    }


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: uuid.UUID, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    quote = (
        await session.execute(
            select(Quote).where(Quote.tenant_id == tid, Quote.id == quote_id)
        )
    ).scalar_one_or_none()
    if quote is None:
        raise HTTPException(404, "quote not found")
    snapshot = (
        await session.execute(
            select(PriceSnapshot).where(PriceSnapshot.id == quote.price_snapshot_id)
        )
    ).scalar_one()
    return {
        "id": str(quote.id),
        "status": quote.status,
        "expires_at": quote.expires_at.isoformat() if quote.expires_at else None,
        "configuration": quote.configuration,
        "total": {"amount_minor": snapshot.total_minor, "currency": snapshot.currency},
        "itemized": snapshot.itemized,
    }


class OrderRequest(BaseModel):
    quote_id: uuid.UUID
    customer: dict[str, str]  # {email, name?}


@router.post("/orders", status_code=201)
async def post_order(payload: OrderRequest, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    quote = (
        await session.execute(
            select(Quote).where(Quote.tenant_id == tid, Quote.id == payload.quote_id)
        )
    ).scalar_one_or_none()
    if quote is None:
        raise HTTPException(404, "quote not found")
    email = payload.customer.get("email", "").strip().lower()
    if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(422, "customer.email is required and must be a valid address")
    try:
        order = await create_order_from_quote(
            session, tid, quote, email, payload.customer.get("name")
        )
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return await get_order(order.id, session)


@router.get("/orders/{order_id}")
async def get_order(order_id: uuid.UUID, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    order = (
        await session.execute(
            select(Order).where(Order.tenant_id == tid, Order.id == order_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "order not found")
    items = (
        (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id)))
        .scalars()
        .all()
    )
    payments = (
        (await session.execute(select(Payment).where(Payment.order_id == order.id)))
        .scalars()
        .all()
    )
    return {
        "id": str(order.id),
        "status": order.status,
        "type": order.type,
        "currency": order.currency,
        "market": order.market,
        "totals": order.totals,
        "items": [
            {
                "id": str(i.id),
                "template_id": str(i.template_id) if i.template_id else None,
                "configuration": i.configuration,
                "non_returnable": i.non_returnable,
                "price_snapshot_id": str(i.price_snapshot_id),
            }
            for i in items
        ],
        "payments": [
            {
                "id": str(p.id),
                "kind": p.kind,
                "status": p.status,
                "amount_minor": p.amount_minor,
                "currency": p.currency,
            }
            for p in payments
        ],
    }


class PaymentIntentRequest(BaseModel):
    order_id: uuid.UUID
    kind: str = "deposit_production"


@router.post("/payments/intent", status_code=201)
async def post_payment_intent(payload: PaymentIntentRequest, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    order = (
        await session.execute(
            select(Order).where(Order.tenant_id == tid, Order.id == payload.order_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "order not found")
    try:
        payment, client_payload = await create_payment_intent(session, tid, order, payload.kind)
    except OrderFlowError as exc:
        raise HTTPException(422, str(exc)) from None
    await session.commit()
    return {"payment_id": str(payment.id), **client_payload}


@router.post("/payments/{payment_id}/mock-complete")
async def post_mock_complete(payment_id: uuid.UUID, session: DbSession) -> dict:
    """Dev/test stand-in for the PSP webhook (removed when Mollie lands)."""
    tid = get_current_tenant().tenant_id
    payment = (
        await session.execute(
            select(Payment).where(Payment.tenant_id == tid, Payment.id == payment_id)
        )
    ).scalar_one_or_none()
    if payment is None:
        raise HTTPException(404, "payment not found")
    try:
        order = await complete_mock_payment(session, payment)
    except OrderFlowError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {"payment_status": payment.status, "order_status": order.status}
