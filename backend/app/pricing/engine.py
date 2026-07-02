"""Pricing engine (docs/spec/06) — master formula, never-NaN, snapshots.

Pure and deterministic: given the same PricingInputs, the same result, always
(PRINCIPLES.md determinism). All money math is Decimal minor units; the
result carries ints. A component that cannot be computed never becomes 0 —
it downgrades the configuration (docs/spec/06 §6):

  purchasable — all inputs present & fresh (or within cache max-age)
  quote_only  — valid but not firmly priceable: estimated range where
                computable (degraded inputs), else no total at all
  invalid     — handled by the rules engine before pricing; pricing runs for
                purchasable/quote_only only
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.pricing.inputs import PricingInputs
from app.pricing.weight import estimate_weight_g

MINOR_PER_UNIT = Decimal(100)  # 2-decimal currencies (EUR launch)
RANGE_SPREAD = Decimal("0.10")  # ±10% band for degraded estimates

PURCHASABLE = "purchasable"
QUOTE_ONLY = "quote_only"


@dataclass
class PriceResult:
    status: str
    currency: str
    reasons: list[dict[str, str]] = field(default_factory=list)
    degraded: bool = False
    itemized: dict[str, int] = field(default_factory=dict)
    total_minor: int | None = None
    range_min_minor: int | None = None
    range_max_minor: int | None = None
    non_returnable: bool = False
    snapshot: dict[str, Any] | None = None


def _minor(amount: Decimal) -> int:
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_price(inputs: PricingInputs) -> PriceResult:  # noqa: C901
    result = PriceResult(status=PURCHASABLE, currency=inputs.currency)
    reasons = result.reasons
    itemized: dict[str, Decimal] = {}
    hard_missing = False  # a component with no basis at all → no total/range

    # --- Weight ---
    w = inputs.weight
    weight = estimate_weight_g(
        cad_volume_mm3=w.cad_volume_mm3,
        specific_gravity=w.specific_gravity,
        casting_waste_factor=w.casting_waste_factor,
        ring_size_weight_factor=w.ring_size_weight_factor,
        override_g=w.override_g,
    )
    if weight is None:
        hard_missing = True
        reasons.append(
            {"code": "weight_unavailable", "message": "Metal weight cannot be determined."}
        )

    # --- Metal cost ---
    mp = inputs.metal_price
    if mp is None:
        hard_missing = True
        reasons.append(
            {
                "code": "metal_price_unavailable",
                "message": "Live metal price unavailable — request a quote.",
            }
        )
    elif weight is not None:
        if mp.is_too_stale:
            result.status = QUOTE_ONLY
            result.degraded = True
            reasons.append(
                {
                    "code": "metal_price_stale",
                    "message": "Live gold price unavailable — request a quote.",
                }
            )
        elif mp.is_stale:
            result.degraded = True

        price_per_gram = mp.price_per_gram
        if mp.currency != inputs.currency:
            fx = inputs.fx
            if fx is None or fx.is_too_stale or fx.quote != inputs.currency:
                result.status = QUOTE_ONLY
                result.degraded = True
                reasons.append(
                    {"code": "fx_unavailable", "message": "Exchange rate unavailable."}
                )
                if fx is not None:
                    price_per_gram = price_per_gram * fx.rate
            else:
                price_per_gram = price_per_gram * fx.rate

        itemized["metal_cost"] = (
            weight.weight_g * price_per_gram * w.fabrication_premium * MINOR_PER_UNIT
        )

    # --- Center stone ---
    stone = inputs.stone
    if stone is not None:
        if stone.price_per_carat is None:
            hard_missing = True
            reasons.append(
                {
                    "code": "stone_price_unavailable",
                    "message": "Stone price unavailable for this specification.",
                }
            )
        else:
            itemized["center_stone_cost"] = (
                stone.price_per_carat
                * stone.carat
                * stone.magic_size_multiplier
                * MINOR_PER_UNIT
            )

    # --- Side stones, labor, fees ---
    if inputs.side_stones:
        itemized["side_stone_cost"] = Decimal(
            sum(s.per_stone_minor * s.qty for s in inputs.side_stones)
        )
    for fee in inputs.labor:
        itemized[f"{fee.kind}_labor"] = Decimal(fee.amount_minor)

    if inputs.engraving is not None:
        e = inputs.engraving
        itemized["engraving_cost"] = Decimal(
            e.base_cost_minor + e.per_char_cost_minor * e.char_count
        )
        if e.makes_non_returnable:
            result.non_returnable = True

    if inputs.design_fee_minor is not None:
        itemized["design_fee"] = Decimal(inputs.design_fee_minor)
    if inputs.prototype_fee_minor is not None:
        itemized["prototype_fee"] = Decimal(inputs.prototype_fee_minor)
    if inputs.packaging_minor:
        itemized["packaging_cost"] = Decimal(inputs.packaging_minor)

    # --- Rule modifiers (surcharges/discounts from the rules engine) ---
    modifier_total = Decimal(0)
    for mod in inputs.rule_modifiers:
        modifier_total += Decimal(mod.get("surcharge_minor", 0))
        modifier_total -= Decimal(mod.get("discount_minor", 0))
        if mod.get("makes_non_returnable"):
            result.non_returnable = True
    if modifier_total:
        itemized["rule_modifiers"] = modifier_total

    base_subtotal = sum(itemized.values(), Decimal(0))

    # --- Buffers (percent of base, or fixed) ---
    for buf in inputs.buffers:
        amount = (
            base_subtotal * buf.value if buf.type == "percent" else Decimal(buf.value)
        )
        itemized[f"{buf.kind}_buffer"] = amount

    with_buffers = sum(itemized.values(), Decimal(0))

    # --- Margin ---
    if inputs.margin is not None:
        m = inputs.margin
        margin_amount = with_buffers * m.value if m.type == "percent" else Decimal(m.value)
        itemized["margin"] = margin_amount

    pre_tax = sum(itemized.values(), Decimal(0))

    # --- VAT ---
    if inputs.vat is None:
        result.status = QUOTE_ONLY
        reasons.append(
            {"code": "vat_rule_missing", "message": "No VAT rule for this market."}
        )
        vat_amount = Decimal(0)
    else:
        vat_amount = pre_tax * inputs.vat.rate
        itemized["vat"] = vat_amount

    total = pre_tax + vat_amount

    result.itemized = {k: _minor(v) for k, v in itemized.items()}

    if hard_missing:
        # No basis for a full price: no total, no fake range (never NaN/0).
        result.status = QUOTE_ONLY
        result.total_minor = None
        result.range_min_minor = None
        result.range_max_minor = None
        result.snapshot = None
        return result

    if result.status == QUOTE_ONLY:
        # Computable but degraded → estimated range only, exact checkout stays
        # disabled (docs/spec/06 §6).
        result.total_minor = None
        result.range_min_minor = _minor(total * (Decimal(1) - RANGE_SPREAD))
        result.range_max_minor = _minor(total * (Decimal(1) + RANGE_SPREAD))
        result.snapshot = None
        return result

    result.total_minor = _minor(total)
    result.snapshot = _build_snapshot(inputs, weight, result)
    return result


def _build_snapshot(inputs: PricingInputs, weight: Any, result: PriceResult) -> dict[str, Any]:
    """The immutable price snapshot (docs/spec/06 §5) — self-contained and

    reproducible: pins every drifting input by value + version + source ref.
    """
    mp = inputs.metal_price
    stone = inputs.stone
    v = inputs.versions
    return {
        "metal_prices": {
            "price_per_gram": str(mp.price_per_gram),
            "currency": mp.currency,
            "source": mp.source,
            "fetched_at": mp.fetched_at.isoformat(),
        },
        "fx_rate": (
            {
                "base": inputs.fx.base,
                "quote": inputs.fx.quote,
                "rate": str(inputs.fx.rate),
                "source": inputs.fx.source,
                "fetched_at": inputs.fx.fetched_at.isoformat(),
            }
            if inputs.fx
            else None
        ),
        "weight": {
            "estimated_g": str(weight.estimated_g) if weight.estimated_g is not None else None,
            "override_g": str(weight.override_g) if weight.override_g is not None else None,
            "source": weight.source,
            "size_factor": str(weight.size_factor),
            "waste_factor": str(weight.waste_factor),
            "fabrication_premium": str(inputs.weight.fabrication_premium),
            "cad_volume_mm3": (
                str(inputs.weight.cad_volume_mm3)
                if inputs.weight.cad_volume_mm3 is not None
                else None
            ),
            "specific_gravity": (
                str(inputs.weight.specific_gravity)
                if inputs.weight.specific_gravity is not None
                else None
            ),
        },
        "stone": (
            {
                "type": stone.stone_type,
                "shape": stone.shape,
                "carat": str(stone.carat),
                "color": stone.color,
                "clarity": stone.clarity,
                "price_per_carat": str(stone.price_per_carat),
                "magic_size_multiplier": str(stone.magic_size_multiplier),
                "supplier_id": stone.supplier_id,
                "cert": stone.cert,
            }
            if stone
            else None
        ),
        "side_stones": [
            {"price_minor": s.per_stone_minor, "qty": s.qty} for s in inputs.side_stones
        ],
        "labor": {f.kind: f.amount_minor for f in inputs.labor},
        "fees": {
            "engraving": (
                {
                    "type": inputs.engraving.type,
                    "base_cost_minor": inputs.engraving.base_cost_minor,
                    "per_char_cost_minor": inputs.engraving.per_char_cost_minor,
                    "char_count": inputs.engraving.char_count,
                    "makes_non_returnable": inputs.engraving.makes_non_returnable,
                }
                if inputs.engraving
                else None
            ),
            "design_minor": inputs.design_fee_minor,
            "prototype_minor": inputs.prototype_fee_minor,
            "packaging_minor": inputs.packaging_minor,
        },
        "buffers": [
            {"kind": b.kind, "type": b.type, "value": str(b.value)} for b in inputs.buffers
        ],
        "margin_applied": (
            {"type": inputs.margin.type, "value": str(inputs.margin.value)}
            if inputs.margin
            else None
        ),
        "vat_applied": (
            {
                "market": inputs.vat.market,
                "rate": str(inputs.vat.rate),
                "inclusive": inputs.vat.price_includes_vat,
            }
            if inputs.vat
            else None
        ),
        "rule_modifiers": [dict(m) for m in inputs.rule_modifiers],
        "itemized": dict(result.itemized),
        "total_minor": result.total_minor,
        "currency": result.currency,
        "versions": {
            "template_version": v.template_version,
            "price_formula_version": v.price_formula_version,
            "rule_set_version": v.rule_set_version,
            "density_source_version": v.density_source_version,
            "labor_cost_version": v.labor_cost_version,
            "margin_rule_version": v.margin_rule_version,
            "vat_rule_version": v.vat_rule_version,
        },
        "source_refs": {
            "metal_price_snapshot_id": inputs.metal_price_snapshot_id
            or (mp.snapshot_id if mp else None),
            "fx_rate_snapshot_id": inputs.fx_rate_snapshot_id
            or (inputs.fx.snapshot_id if inputs.fx else None),
        },
        "computed_by": "server",
    }
