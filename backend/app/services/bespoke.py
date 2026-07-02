"""Bespoke workflow (docs/spec/10): idea → design deposit → CAD/render

revisions → quote → approval → order (production deposit → balance handled
by the order flow). The design deposit is non-refundable but credited to the
final order (decision #4 default €250).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BespokeApproval,
    BespokeDeposit,
    BespokeQuote,
    BespokeRequest,
    BespokeRevision,
    Deposit,
    Order,
    OrderConfiguration,
    OrderItem,
    Payment,
    PriceSnapshot,
    ProductionJob,
)
from app.services.orders import OrderFlowError, deposit_amount_minor

DESIGN_DEPOSIT_MINOR = 25000  # €250 — decision #4 default (credited)
QUOTE_VALIDITY = timedelta(days=14)


async def create_bespoke_request(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    source: str,
    brief: dict[str, Any],
    currency: str = "EUR",
) -> BespokeRequest:
    if source not in ("upload", "ai_designer"):
        raise OrderFlowError(f"unknown bespoke source '{source}'")
    budget = brief.get("budget_minor")
    range_min = range_max = None
    if isinstance(budget, int) and budget > 0:
        range_min = int(budget * 0.8)
        range_max = int(budget * 1.2)
    request = BespokeRequest(
        tenant_id=tenant_id,
        source=source,
        brief=brief,
        status="new",
        price_range_min_minor=range_min,
        price_range_max_minor=range_max,
        currency=currency,
    )
    session.add(request)
    await session.flush()
    return request


async def create_design_deposit_intent(
    session: AsyncSession, tenant_id: uuid.UUID, request: BespokeRequest
) -> tuple[Payment, dict[str, Any]]:
    if request.status not in ("new",):
        raise OrderFlowError(f"design deposit not applicable in status '{request.status}'")
    payment = Payment(
        tenant_id=tenant_id,
        bespoke_request_id=request.id,
        psp="mock",
        amount_minor=DESIGN_DEPOSIT_MINOR,
        currency=request.currency or "EUR",
        kind="deposit_design",
        status="pending",
    )
    session.add(payment)
    await session.flush()
    payment.psp_ref = f"mock_{payment.id.hex[:12]}"
    return payment, {
        "psp": payment.psp,
        "client_token": payment.psp_ref,
        "amount": {"amount_minor": payment.amount_minor, "currency": payment.currency},
    }


async def on_design_deposit_paid(session: AsyncSession, payment: Payment) -> BespokeRequest:
    request = (
        await session.execute(
            select(BespokeRequest).where(BespokeRequest.id == payment.bespoke_request_id)
        )
    ).scalar_one()
    session.add(
        BespokeDeposit(
            bespoke_request_id=request.id,
            payment_id=payment.id,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            non_refundable=True,
            credited=True,
        )
    )
    if request.status == "new":
        request.status = "in_design"
    await session.flush()
    return request


async def add_revision(
    session: AsyncSession,
    request: BespokeRequest,
    cad_media_id: uuid.UUID | None,
    render_media_id: uuid.UUID | None,
    notes: str | None,
) -> BespokeRevision:
    if request.status not in ("in_design", "quoted"):
        raise OrderFlowError(
            f"revisions require a paid design deposit (status is '{request.status}')"
        )
    round_no = (
        len(
            (
                await session.execute(
                    select(BespokeRevision).where(
                        BespokeRevision.bespoke_request_id == request.id
                    )
                )
            )
            .scalars()
            .all()
        )
        + 1
    )
    revision = BespokeRevision(
        bespoke_request_id=request.id,
        round_no=round_no,
        cad_media_id=cad_media_id,
        render_media_id=render_media_id,
        status="sent",
        notes=notes,
    )
    session.add(revision)
    await session.flush()
    return revision


async def add_quote(
    session: AsyncSession,
    request: BespokeRequest,
    itemized: dict[str, int],
    total_minor: int,
) -> BespokeQuote:
    if request.status not in ("in_design", "quoted"):
        raise OrderFlowError(f"cannot quote in status '{request.status}'")
    if total_minor <= 0 or total_minor != sum(itemized.values()):
        raise OrderFlowError("total must be positive and equal the itemized sum")
    quote = BespokeQuote(
        bespoke_request_id=request.id,
        itemized=itemized,
        total_minor=total_minor,
        currency=request.currency or "EUR",
        valid_until=datetime.now(UTC) + QUOTE_VALIDITY,
    )
    session.add(quote)
    request.status = "quoted"
    await session.flush()
    return quote


async def approve(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    request: BespokeRequest,
    approved_by: str,
) -> Order:
    """Customer approval converts the latest bespoke quote into an order.

    The snapshot is quote-based (bespoke prices are human-set, not formula-
    derived) but still immutable and version-stamped. The credited design
    deposit is attached to the order and reduces the balance.
    """
    if request.status != "quoted":
        raise OrderFlowError(f"approval requires a quote (status is '{request.status}')")
    quote = (
        await session.execute(
            select(BespokeQuote)
            .where(BespokeQuote.bespoke_request_id == request.id)
            .order_by(BespokeQuote.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    if quote.valid_until and quote.valid_until < datetime.now(UTC):
        raise OrderFlowError("the quote has expired — request a refreshed quote")

    snapshot = PriceSnapshot(
        tenant_id=tenant_id,
        inputs={
            "bespoke": True,
            "bespoke_request_id": str(request.id),
            "bespoke_quote_id": str(quote.id),
            "brief": request.brief,
        },
        itemized=quote.itemized,
        total_minor=quote.total_minor,
        currency=quote.currency,
        metal_prices={"source": "bespoke_quote"},
        template_version=0,
        price_formula_version=0,
        rule_set_version=0,
        density_source_version=0,
        labor_cost_version=0,
        margin_rule_version=0,
        vat_rule_version=0,
    )
    session.add(snapshot)
    await session.flush()

    order = Order(
        tenant_id=tenant_id,
        customer_id=request.customer_id,
        type="bespoke",
        status="awaiting_deposit",
        currency=quote.currency,
        market="NL",
        totals={
            "total_minor": quote.total_minor,
            "deposit_minor": deposit_amount_minor(quote.total_minor),
        },
        placed_at=datetime.now(UTC),
    )
    session.add(order)
    await session.flush()

    item = OrderItem(
        order_id=order.id,
        template_id=None,
        configuration={"bespoke_request_id": str(request.id)},
        price_snapshot_id=snapshot.id,
        non_returnable=True,  # bespoke = custom-made, always exempt
        qty=1,
    )
    session.add(item)
    await session.flush()
    snapshot.order_item_id = item.id

    session.add(
        OrderConfiguration(
            order_item_id=item.id,
            resolved_spec={"bespoke_request_id": str(request.id), "brief": request.brief},
        )
    )
    session.add(
        ProductionJob(tenant_id=tenant_id, order_item_id=item.id, status="awaiting_deposit")
    )

    # Credit the design deposit against this order.
    bespoke_deposits = (
        (
            await session.execute(
                select(BespokeDeposit).where(
                    BespokeDeposit.bespoke_request_id == request.id,
                    BespokeDeposit.credited.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for bd in bespoke_deposits:
        session.add(
            Deposit(
                bespoke_request_id=request.id,
                order_id=order.id,
                kind="deposit_design",
                amount_minor=bd.amount_minor,
                currency=bd.currency,
                credited_to_order_id=order.id,
            )
        )

    session.add(
        BespokeApproval(
            bespoke_request_id=request.id,
            approved_by=approved_by,
            approved_at=datetime.now(UTC),
            becomes_order_id=order.id,
        )
    )
    request.status = "approved"
    await session.flush()
    return order
