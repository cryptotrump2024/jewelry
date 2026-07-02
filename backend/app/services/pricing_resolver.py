"""Pricing resolver — the DB-facing layer over the pure engines.

Given a template + selections, it: (1) validates via the rules engine using
the published rule set, (2) resolves every pricing input from tenant data
(densities via material_options, latest metal-price snapshot, diamond price
tables + carat bands, labor, margin, buffers, VAT, weight from CAD volumes
with size factors and overrides), (3) calls compute_price. Missing data never
raises — it flows through the engines' quote_only/invalid semantics
(fail safe, not silent).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Buffer,
    CaratPriceBand,
    DiamondPriceTable,
    LaborCost,
    Margin,
    MaterialOption,
    Metal,
    MetalDensity,
    MetalPurity,
    Option,
    OptionGroup,
    ProductTemplate,
    RuleSet,
    StoneShape,
    StoneType,
    TemplateComponent,
    TemplateManufacturability,
    TemplateOptionGroup,
    VatRule,
)
from app.pricing import (
    BufferInput,
    FeeInput,
    MarginInput,
    MetalPriceInput,
    PriceResult,
    PricingInputs,
    StonePricingInput,
    WeightInput,
    compute_price,
)
from app.rules.engine import (
    INVALID,
    ManufacturabilityLimits,
    RuleData,
    ValidationResult,
    validate,
)
from app.sources.metal import latest_snapshot

DEFAULT_QUALITY = ("G", "SI1")  # spec 07 §6 mid-tier default
DEFAULT_WASTE = Decimal("0.02")  # decision #10 default
DEFAULT_PREMIUM = Decimal("1.05")  # decision #10 default

# Freshness thresholds per source kind (manual prices age slower by design).
STALE_AFTER = {"manual": timedelta(days=30), "default": timedelta(hours=1)}
TOO_STALE_AFTER = {"manual": timedelta(days=90), "default": timedelta(hours=24)}


@dataclass
class ResolvedPrice:
    validation: ValidationResult
    price: PriceResult | None  # None when validation is invalid


async def _load_rules(
    session: AsyncSession, tenant_id: uuid.UUID, template_id: uuid.UUID
) -> tuple[list[RuleData], int]:
    rule_set = (
        await session.execute(
            select(RuleSet)
            .where(
                RuleSet.tenant_id == tenant_id,
                RuleSet.template_id == template_id,
                RuleSet.status == "published",
            )
            .order_by(RuleSet.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rule_set is None:
        return [], 0
    await session.refresh(rule_set, ["rules"])
    return [
        RuleData(
            type=r.type,
            condition=r.condition,
            effect=r.effect,
            message=r.message,
            scope=r.scope,
            sort=r.sort,
        )
        for r in rule_set.rules
    ], rule_set.version


async def _template_groups(
    session: AsyncSession, template_id: uuid.UUID
) -> tuple[list[str], list[str]]:
    links = (
        await session.execute(
            select(TemplateOptionGroup, OptionGroup)
            .join(OptionGroup, OptionGroup.id == TemplateOptionGroup.option_group_id)
            .where(TemplateOptionGroup.template_id == template_id)
            .order_by(TemplateOptionGroup.step_order)
        )
    ).all()
    keys = [group.key for _link, group in links]
    required = [group.key for link, group in links if link.is_required]
    return keys, required


async def _resolve_material(
    session: AsyncSession, tenant_id: uuid.UUID, metal_code: str | None
) -> tuple[MaterialOption | None, Decimal | None, str | None, int | None]:
    """metal option code → (material_option, specific_gravity, metal_key, karat)."""
    if not metal_code:
        return None, None, None, None
    option = (
        await session.execute(
            select(Option)
            .join(OptionGroup, OptionGroup.id == Option.option_group_id)
            .where(
                OptionGroup.tenant_id == tenant_id,
                OptionGroup.key == "metal",
                Option.code == metal_code,
            )
        )
    ).scalar_one_or_none()
    mo_id = (option.value or {}).get("material_option_id") if option else None
    if not mo_id:
        return None, None, None, None
    mo = (
        await session.execute(
            select(MaterialOption).where(MaterialOption.id == uuid.UUID(mo_id))
        )
    ).scalar_one_or_none()
    if mo is None:
        return None, None, None, None
    density = (
        await session.execute(select(MetalDensity).where(MetalDensity.id == mo.density_id))
    ).scalar_one_or_none()
    metal = (
        await session.execute(select(Metal).where(Metal.id == mo.metal_id))
    ).scalar_one()
    purity = (
        await session.execute(select(MetalPurity).where(MetalPurity.id == mo.purity_id))
    ).scalar_one()
    return mo, density.specific_gravity if density else None, metal.key, purity.karat


async def _resolve_stone(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    selections: dict[str, Any],
) -> StonePricingInput | None:
    type_key = selections.get("stone_type")
    shape_key = selections.get("stone_shape")
    carat_raw = selections.get("carat")
    if not (type_key and shape_key and carat_raw):
        return None
    try:
        carat = Decimal(str(carat_raw))
    except InvalidOperation:
        return None

    stone_type = (
        await session.execute(
            select(StoneType).where(StoneType.tenant_id == tenant_id, StoneType.key == type_key)
        )
    ).scalar_one_or_none()
    shape = (
        await session.execute(
            select(StoneShape).where(
                StoneShape.tenant_id == tenant_id, StoneShape.key == shape_key
            )
        )
    ).scalar_one_or_none()
    if stone_type is None or shape is None:
        return None

    color = selections.get("stone_color") or DEFAULT_QUALITY[0]
    clarity = selections.get("stone_clarity") or DEFAULT_QUALITY[1]

    table_row = (
        await session.execute(
            select(DiamondPriceTable).where(
                DiamondPriceTable.tenant_id == tenant_id,
                DiamondPriceTable.stone_type_id == stone_type.id,
                DiamondPriceTable.shape_id == shape.id,
                DiamondPriceTable.carat_min <= carat,
                DiamondPriceTable.carat_max >= carat,
                DiamondPriceTable.color == color,
                DiamondPriceTable.clarity == clarity,
            )
        )
    ).scalar_one_or_none()

    # Magic-size multiplier: the highest crossed threshold applies.
    band = (
        await session.execute(
            select(CaratPriceBand)
            .where(
                CaratPriceBand.tenant_id == tenant_id,
                CaratPriceBand.stone_type_id == stone_type.id,
                CaratPriceBand.carat_threshold <= carat,
            )
            .order_by(CaratPriceBand.carat_threshold.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return StonePricingInput(
        stone_type=type_key,
        shape=shape_key,
        carat=carat,
        color=color,
        clarity=clarity,
        price_per_carat=table_row.price_per_carat if table_row else None,
        magic_size_multiplier=band.multiplier if band else Decimal(1),
    )


def _staleness(source: str, fetched_at: datetime) -> tuple[bool, bool]:
    age = datetime.now(UTC) - fetched_at
    stale = age > STALE_AFTER.get(source, STALE_AFTER["default"])
    too_stale = age > TOO_STALE_AFTER.get(source, TOO_STALE_AFTER["default"])
    return stale, too_stale


async def resolve_and_price(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template: ProductTemplate,
    selections: dict[str, Any],
    market: str = "NL",
    currency: str = "EUR",
) -> ResolvedPrice:
    # 1. Rules first — invalid configs are never priced (docs/spec/07 §4).
    rules, rule_set_version = await _load_rules(session, tenant_id, template.id)
    group_keys, required = await _template_groups(session, template.id)
    limits_row = (
        await session.execute(
            select(TemplateManufacturability).where(
                TemplateManufacturability.template_id == template.id,
                TemplateManufacturability.component_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    limits = (
        ManufacturabilityLimits(
            min_band_thickness_mm=(
                float(limits_row.min_band_thickness_mm)
                if limits_row.min_band_thickness_mm is not None
                else None
            ),
            requires_manual_cad_check=limits_row.requires_manual_cad_check,
        )
        if limits_row
        else None
    )
    validation = validate(
        selections, rules, template_groups=group_keys, required_groups=required, limits=limits
    )
    if validation.status == INVALID:
        return ResolvedPrice(validation=validation, price=None)

    # 2. Resolve pricing inputs from data.
    _mo, sg, metal_key, karat = await _resolve_material(
        session, tenant_id, selections.get("metal")
    )

    metal_price_input = None
    if metal_key:
        snap = await latest_snapshot(session, tenant_id, metal_key, karat, currency)
        if snap is not None:
            fetched = snap.fetched_at
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=UTC)
            stale, too_stale = _staleness(snap.source, fetched)
            metal_price_input = MetalPriceInput(
                price_per_gram=snap.price_per_gram,
                currency=snap.currency,
                source=snap.source,
                fetched_at=fetched,
                is_stale=stale,
                is_too_stale=too_stale,
                snapshot_id=str(snap.id),
            )

    total_volume = Decimal(0)
    components = (
        (
            await session.execute(
                select(TemplateComponent).where(
                    TemplateComponent.template_id == template.id,
                    TemplateComponent.metal_assignable.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for component in components:
        if component.cad_volume_mm3 is not None:
            total_volume += component.cad_volume_mm3

    stone = await _resolve_stone(session, tenant_id, selections)

    labor_rows = (
        (await session.execute(select(LaborCost).where(LaborCost.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    margin_row = (
        await session.execute(
            select(Margin).where(
                Margin.tenant_id == tenant_id,
                Margin.template_id.is_(None),
                Margin.market.is_(None),
            )
        )
    ).scalar_one_or_none()
    buffer_rows = (
        (await session.execute(select(Buffer).where(Buffer.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    vat_row = (
        await session.execute(
            select(VatRule).where(VatRule.tenant_id == tenant_id, VatRule.market == market)
        )
    ).scalar_one_or_none()

    from app.pricing.inputs import VatInput, VersionPins

    inputs = PricingInputs(
        currency=currency,
        metal_price=metal_price_input,
        weight=WeightInput(
            cad_volume_mm3=total_volume if total_volume > 0 else None,
            specific_gravity=sg,
            casting_waste_factor=DEFAULT_WASTE,
            fabrication_premium=DEFAULT_PREMIUM,
        ),
        stone=stone,
        labor=tuple(
            FeeInput(kind=row.operation, amount_minor=row.amount_minor) for row in labor_rows
        ),
        buffers=tuple(
            BufferInput(
                kind=row.kind,
                type=row.type,
                value=row.value if row.type == "percent" else Decimal(row.value),
            )
            for row in buffer_rows
        ),
        margin=(
            MarginInput(type=margin_row.type, value=margin_row.value) if margin_row else None
        ),
        vat=(
            VatInput(
                market=vat_row.market,
                rate=vat_row.rate,
                price_includes_vat=vat_row.price_includes_vat,
            )
            if vat_row
            else None
        ),
        rule_modifiers=tuple(validation.modifiers),
        versions=VersionPins(rule_set_version=rule_set_version),
    )

    price = compute_price(inputs)

    # Rules can independently force quote_only (e.g. manual CAD check).
    if validation.status == "quote_only" and price.status == "purchasable":
        price.status = "quote_only"
        price.reasons.extend(validation.reasons)
        price.range_min_minor = price.total_minor
        price.range_max_minor = price.total_minor
        price.total_minor = None
        price.snapshot = None

    return ResolvedPrice(validation=validation, price=price)
