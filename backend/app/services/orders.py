"""Quote → order → deposit flow (docs/spec/10, 13 §4–5).

The client-side price is advisory only: quoting re-runs the full validate +
price authoritatively and freezes an immutable PriceSnapshot row. An order
locks that snapshot, stores the resolved factory spec, and opens a production
job. Payments go through a PSP adapter — mock provider until Mollie keys
exist (decision #6 default is Mollie).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Customer,
    Order,
    OrderConfiguration,
    OrderItem,
    Payment,
    PriceSnapshot,
    ProductionJob,
    ProductTemplate,
    Quote,
)
from app.services.pricing_resolver import resolve_and_price

QUOTE_VALIDITY = timedelta(days=7)
# Decision #5 default: 50% production deposit (70–75% for special stones later).
PRODUCTION_DEPOSIT_FRACTION = Decimal("0.50")


class OrderFlowError(ValueError):
    """Business-rule violation surfaced as 409/422 by the API layer."""


async def create_quote(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template: ProductTemplate,
    selections: dict[str, Any],
    market: str = "NL",
    currency: str = "EUR",
) -> tuple[Quote, PriceSnapshot]:
    resolved = await resolve_and_price(
        session, tenant_id, template, selections, market=market, currency=currency
    )
    price = resolved.price
    if resolved.validation.status == "invalid" or price is None:
        raise OrderFlowError("configuration is invalid and cannot be quoted")
    if price.status != "purchasable" or price.snapshot is None:
        raise OrderFlowError(
            "configuration is not firmly priceable right now — request a manual quote"
        )

    snap = price.snapshot
    snapshot_row = PriceSnapshot(
        tenant_id=tenant_id,
        inputs=snap,
        itemized=snap["itemized"],
        total_minor=price.total_minor,
        currency=price.currency,
        metal_prices=snap["metal_prices"],
        fx_rate=snap.get("fx_rate"),
        stone_price=snap.get("stone"),
        margin_applied=snap.get("margin_applied"),
        vat_applied=snap.get("vat_applied"),
        template_version=1,
        price_formula_version=snap["versions"]["price_formula_version"],
        rule_set_version=snap["versions"]["rule_set_version"],
        density_source_version=snap["versions"]["density_source_version"],
        labor_cost_version=snap["versions"]["labor_cost_version"],
        margin_rule_version=snap["versions"]["margin_rule_version"],
        vat_rule_version=snap["versions"]["vat_rule_version"],
        metal_price_snapshot_id=(
            uuid.UUID(snap["source_refs"]["metal_price_snapshot_id"])
            if snap["source_refs"].get("metal_price_snapshot_id")
            else None
        ),
        fx_rate_snapshot_id=(
            uuid.UUID(snap["source_refs"]["fx_rate_snapshot_id"])
            if snap["source_refs"].get("fx_rate_snapshot_id")
            else None
        ),
    )
    session.add(snapshot_row)
    await session.flush()

    quote = Quote(
        tenant_id=tenant_id,
        configuration={
            "template_id": str(template.id),
            "selections": selections,
            "market": market,
            "currency": currency,
            "non_returnable": price.non_returnable,
        },
        price_snapshot_id=snapshot_row.id,
        status="open",
        expires_at=datetime.now(UTC) + QUOTE_VALIDITY,
    )
    session.add(quote)
    await session.flush()
    snapshot_row.quote_id = quote.id
    return quote, snapshot_row


async def _get_or_create_customer(
    session: AsyncSession, tenant_id: uuid.UUID, email: str, name: str | None
) -> Customer:
    customer = (
        await session.execute(
            select(Customer).where(Customer.tenant_id == tenant_id, Customer.email == email)
        )
    ).scalar_one_or_none()
    if customer is None:
        customer = Customer(tenant_id=tenant_id, email=email, name=name)
        session.add(customer)
        await session.flush()
    elif name and not customer.name:
        customer.name = name
    return customer


async def create_order_from_quote(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    quote: Quote,
    customer_email: str,
    customer_name: str | None = None,
) -> Order:
    if quote.status != "open":
        raise OrderFlowError(f"quote is {quote.status}, not open")
    if quote.expires_at and quote.expires_at < datetime.now(UTC):
        quote.status = "expired"
        raise OrderFlowError("quote has expired — reprice the configuration")

    snapshot = (
        await session.execute(
            select(PriceSnapshot).where(PriceSnapshot.id == quote.price_snapshot_id)
        )
    ).scalar_one()

    customer = await _get_or_create_customer(session, tenant_id, customer_email, customer_name)
    config = quote.configuration

    order = Order(
        tenant_id=tenant_id,
        customer_id=customer.id,
        type="made_to_order",
        status="awaiting_deposit",
        currency=snapshot.currency,
        market=config.get("market", "NL"),
        totals={
            "total_minor": snapshot.total_minor,
            "deposit_minor": deposit_amount_minor(snapshot.total_minor),
        },
        placed_at=datetime.now(UTC),
    )
    session.add(order)
    await session.flush()

    item = OrderItem(
        order_id=order.id,
        template_id=uuid.UUID(config["template_id"]),
        configuration=config["selections"],
        price_snapshot_id=snapshot.id,
        non_returnable=bool(config.get("non_returnable")),
        qty=1,
    )
    session.add(item)
    await session.flush()
    snapshot.order_item_id = item.id

    # Fully resolved factory spec: selections + frozen pricing inputs.
    session.add(
        OrderConfiguration(
            order_item_id=item.id,
            resolved_spec={
                "selections": config["selections"],
                "weight": snapshot.inputs.get("weight"),
                "stone": snapshot.inputs.get("stone"),
                "market": config.get("market"),
            },
        )
    )
    # Production job opens immediately; factory routing is an admin step.
    session.add(
        ProductionJob(tenant_id=tenant_id, order_item_id=item.id, status="awaiting_deposit")
    )

    quote.status = "converted"
    await session.flush()
    return order


def deposit_amount_minor(total_minor: int) -> int:
    return int(
        (Decimal(total_minor) * PRODUCTION_DEPOSIT_FRACTION).quantize(
            Decimal("1"), rounding=ROUND_CEILING
        )
    )


async def create_payment_intent(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    kind: str,
) -> tuple[Payment, dict[str, Any]]:
    """PSP adapter boundary. Mock provider until a Mollie key is configured;

    the storefront never sees provider secrets either way.
    """
    if kind not in ("deposit_production", "balance", "full"):
        raise OrderFlowError(f"unsupported payment kind '{kind}'")
    total = int(order.totals["total_minor"])
    amount = deposit_amount_minor(total) if kind == "deposit_production" else total

    payment = Payment(
        tenant_id=tenant_id,
        order_id=order.id,
        psp="mock",  # switches to "mollie" when decision #6 is finalized + key set
        amount_minor=amount,
        currency=order.currency,
        kind=kind,
        status="pending",
    )
    session.add(payment)
    await session.flush()
    payment.psp_ref = f"mock_{payment.id.hex[:12]}"
    client_payload = {
        "psp": payment.psp,
        "client_token": payment.psp_ref,
        "checkout_url": f"/checkout/mock-pay/{payment.id}",
        "amount": {"amount_minor": amount, "currency": order.currency},
    }
    return payment, client_payload


async def complete_mock_payment(session: AsyncSession, payment: Payment) -> Order:
    """Stand-in for the PSP webhook: marks the payment paid and advances the

    order/production workflow exactly like the real webhook will.
    """
    if payment.psp != "mock":
        raise OrderFlowError("only mock payments can be completed manually")
    if payment.status == "paid":
        order = (
            await session.execute(select(Order).where(Order.id == payment.order_id))
        ).scalar_one()
        return order  # idempotent

    payment.status = "paid"
    order = (
        await session.execute(select(Order).where(Order.id == payment.order_id))
    ).scalar_one()
    if payment.kind == "deposit_production":
        order.status = "in_production"
    elif payment.kind in ("full", "balance"):
        order.status = "paid"

    items = (
        (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id)))
        .scalars()
        .all()
    )
    for item in items:
        job = (
            await session.execute(
                select(ProductionJob).where(ProductionJob.order_item_id == item.id)
            )
        ).scalar_one_or_none()
        if job and job.status == "awaiting_deposit":
            job.status = "queued"
    await session.flush()
    return order
