"""Pricing configuration seeds (Phase 5 — everything admin-replaceable).

ALL money values here are PLACEHOLDERS with sensible magnitudes so the demo
template prices end-to-end out of the box:
- labor/margins/buffers/VAT: spec defaults (decision #3/#10 pending)
- manual metal prices: replace with a live GoldAPI source before launch
- diamond price tables: replace via CSV import with real supplier prices

Idempotent like all seeds.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Buffer,
    DiamondPriceTable,
    LaborCost,
    Margin,
    MetalPriceSource,
    StoneShape,
    StoneType,
    Tenant,
    VatRule,
)
from app.seeds.reference import _get_or_create

LABOR = [
    ("setting", "per_stone", 4500),
    ("casting", "per_piece", 6000),
    ("polishing", "per_piece", 2500),
]

BUFFERS = [
    ("shipping", "fixed", Decimal(2500)),
    ("payment_fee", "percent", Decimal("0.02")),
]

# Manual per-gram EUR prices (placeholder magnitudes; GoldAPI replaces them).
MANUAL_METAL_PRICES = [
    {"metal": "gold", "karat": 24, "price_per_gram": "111.00"},
    {"metal": "gold", "karat": 22, "price_per_gram": "102.00"},
    {"metal": "gold", "karat": 20, "price_per_gram": "93.00"},
    {"metal": "gold", "karat": 18, "price_per_gram": "84.00"},
    {"metal": "gold", "karat": 14, "price_per_gram": "65.00"},
    {"metal": "platinum", "price_per_gram": "36.00"},
    {"metal": "silver", "price_per_gram": "0.95"},
]

# (carat_min, carat_max, price_per_carat lab) — natural = lab × 3.3.
DIAMOND_BANDS = [
    (Decimal("0.30"), Decimal("0.49"), Decimal("800")),
    (Decimal("0.50"), Decimal("0.69"), Decimal("950")),
    (Decimal("0.70"), Decimal("0.99"), Decimal("1100")),
    (Decimal("1.00"), Decimal("1.49"), Decimal("1500")),
    (Decimal("1.50"), Decimal("1.99"), Decimal("1900")),
    (Decimal("2.00"), Decimal("2.99"), Decimal("2400")),
]
DIAMOND_SHAPES = ["oval", "round"]
DEFAULT_QUALITY = ("G", "SI1")  # spec 07 §6 default mid-tier
NATURAL_FACTOR = Decimal("3.3")


async def seed_pricing_config(session: AsyncSession, tenant: Tenant) -> None:
    tid = tenant.id

    for operation, basis, amount in LABOR:
        await _get_or_create(
            session,
            LaborCost,
            tenant_id=tid,
            operation=operation,
            basis=basis,
            defaults={"amount_minor": amount, "currency": "EUR"},
        )

    await _get_or_create(
        session,
        Margin,
        tenant_id=tid,
        template_id=None,
        market=None,
        band=None,
        defaults={"type": "percent", "value": Decimal("0.60")},
    )

    for kind, type_, value in BUFFERS:
        await _get_or_create(
            session,
            Buffer,
            tenant_id=tid,
            kind=kind,
            defaults={"type": type_, "value": value, "currency": "EUR"},
        )

    await _get_or_create(
        session,
        VatRule,
        tenant_id=tid,
        market="NL",
        defaults={"rate": Decimal("0.21"), "price_includes_vat": True, "category": None},
    )

    # Manual metal source (lowest priority so a GoldAPI source wins later).
    existing = (
        await session.execute(
            select(MetalPriceSource).where(
                MetalPriceSource.tenant_id == tid, MetalPriceSource.provider == "manual"
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            MetalPriceSource(
                tenant_id=tid,
                provider="manual",
                priority=100,
                is_active=True,
                config={"prices": MANUAL_METAL_PRICES},
            )
        )
        await session.flush()

    # Diamond price tables for both diamond types.
    color, clarity = DEFAULT_QUALITY
    stone_types = {
        st.key: st
        for st in (
            (
                await session.execute(
                    select(StoneType).where(
                        StoneType.tenant_id == tid,
                        StoneType.key.in_(["lab_diamond", "natural_diamond"]),
                    )
                )
            )
            .scalars()
            .all()
        )
    }
    shapes = {
        s.key: s
        for s in (
            (
                await session.execute(
                    select(StoneShape).where(
                        StoneShape.tenant_id == tid, StoneShape.key.in_(DIAMOND_SHAPES)
                    )
                )
            )
            .scalars()
            .all()
        )
    }
    for type_key, stone_type in stone_types.items():
        factor = NATURAL_FACTOR if type_key == "natural_diamond" else Decimal(1)
        for shape in shapes.values():
            for carat_min, carat_max, lab_price in DIAMOND_BANDS:
                await _get_or_create(
                    session,
                    DiamondPriceTable,
                    tenant_id=tid,
                    stone_type_id=stone_type.id,
                    shape_id=shape.id,
                    carat_min=carat_min,
                    carat_max=carat_max,
                    color=color,
                    clarity=clarity,
                    supplier_id=None,
                    defaults={
                        "price_per_carat": (lab_price * factor).quantize(Decimal("0.01")),
                        "currency": "EUR",
                    },
                )
