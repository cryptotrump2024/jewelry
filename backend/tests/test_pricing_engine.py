"""Phase 3 exit tests — docs/spec/06 §9 cases 1–9 plus the §2 worked example.

All pure-engine: DB wiring (live sources, caches) is Phase 4/6.
"""

from datetime import UTC, datetime
from decimal import Decimal

from app.pricing import (
    BufferInput,
    EngravingInput,
    FeeInput,
    MarginInput,
    MetalPriceInput,
    PricingInputs,
    SideStoneInput,
    StonePricingInput,
    VatInput,
    WeightInput,
    compute_price,
    estimate_weight_g,
    reproduce_price,
)
from app.pricing.inputs import FxInput, VersionPins

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def metal(price: str, **kw) -> MetalPriceInput:
    return MetalPriceInput(
        price_per_gram=Decimal(price), currency="EUR", source="goldapi", fetched_at=NOW, **kw
    )


def weight_380() -> WeightInput:
    """The docs/spec/06 §2 worked example: 380 mm³ 18k yellow."""
    return WeightInput(
        cad_volume_mm3=Decimal("380"),
        specific_gravity=Decimal("15.58"),
        casting_waste_factor=Decimal("0.02"),
        ring_size_weight_factor=Decimal("1.0"),
        fabrication_premium=Decimal("1.05"),
    )


def base_inputs(**overrides) -> PricingInputs:
    defaults = dict(
        currency="EUR",
        metal_price=metal("112.50"),
        weight=weight_380(),
        stone=StonePricingInput(
            stone_type="lab_diamond",
            shape="oval",
            carat=Decimal("1.00"),
            color="G",
            clarity="SI1",
            price_per_carat=Decimal("1500"),
            magic_size_multiplier=Decimal("1.20"),
        ),
        labor=(
            FeeInput(kind="setting", amount_minor=4500),
            FeeInput(kind="casting", amount_minor=6000),
            FeeInput(kind="polishing", amount_minor=2500),
        ),
        buffers=(BufferInput(kind="shipping", type="fixed", value=Decimal(2500)),),
        margin=MarginInput(type="percent", value=Decimal("0.60")),
        vat=VatInput(market="NL", rate=Decimal("0.21"), price_includes_vat=True),
    )
    defaults.update(overrides)
    return PricingInputs(**defaults)


# --- Weight (worked example) ---


def test_weight_worked_example():
    result = estimate_weight_g(
        cad_volume_mm3=Decimal("380"),
        specific_gravity=Decimal("15.58"),
        casting_waste_factor=Decimal("0.02"),
        ring_size_weight_factor=Decimal("1.0"),
    )
    assert result.source == "estimated"
    assert result.weight_g == Decimal("6.039")  # 0.380 × 15.58 × 1.02


def test_weight_override_wins_outright():  # case 5
    result = estimate_weight_g(
        cad_volume_mm3=Decimal("380"),
        specific_gravity=Decimal("15.58"),
        override_g=Decimal("5.800"),
    )
    assert result.source == "override"
    assert result.weight_g == Decimal("5.800")


def test_weight_missing_inputs_returns_none_not_zero():
    assert estimate_weight_g(None, Decimal("15.58")) is None
    assert estimate_weight_g(Decimal("380"), None) is None
    assert estimate_weight_g(Decimal("0"), Decimal("15.58")) is None


# --- Master formula ---


def test_metal_cost_matches_worked_example():
    result = compute_price(base_inputs())
    assert result.status == "purchasable"
    # 6.039 g × €112.50 × 1.05 = €713.36 → 71336 minor
    assert result.itemized["metal_cost"] == 71336
    # 1500 × 1.00 × 1.20 = €1800
    assert result.itemized["center_stone_cost"] == 180000
    assert result.total_minor is not None and result.total_minor > 0
    # VAT is 21% of pre-tax sum.
    pre_tax = sum(v for k, v in result.itemized.items() if k != "vat")
    assert abs(result.itemized["vat"] - round(pre_tax * 0.21)) <= 1


def test_metal_change_scales_by_density_and_spot():  # case 1
    p18k = compute_price(base_inputs()).itemized["metal_cost"]
    p14k = compute_price(
        base_inputs(
            metal_price=metal("87.75"),
            weight=WeightInput(
                cad_volume_mm3=Decimal("380"),
                specific_gravity=Decimal("13.90"),
                fabrication_premium=Decimal("1.05"),
            ),
        )
    ).itemized["metal_cost"]
    ppt = compute_price(
        base_inputs(
            metal_price=metal("35.00"),
            weight=WeightInput(
                cad_volume_mm3=Decimal("380"),
                specific_gravity=Decimal("20.76"),
                fabrication_premium=Decimal("1.05"),
            ),
        )
    ).itemized["metal_cost"]
    # metal_cost ∝ density × spot: same volume, different SG and €/g.
    assert p18k == 71336  # 6.039 g × 112.50 × 1.05
    assert p14k == 49644  # 5.388 g × 87.75 × 1.05
    assert ppt == 29573  # 8.047 g × 35.00 × 1.05
    assert len({p18k, p14k, ppt}) == 3


def test_magic_size_jump_not_linear():  # case 2
    just_under = compute_price(
        base_inputs(
            stone=StonePricingInput(
                stone_type="lab_diamond",
                shape="oval",
                carat=Decimal("0.95"),
                price_per_carat=Decimal("1500"),
                magic_size_multiplier=Decimal("1.0"),
            )
        )
    ).itemized["center_stone_cost"]
    at_one = compute_price(
        base_inputs(
            stone=StonePricingInput(
                stone_type="lab_diamond",
                shape="oval",
                carat=Decimal("1.00"),
                price_per_carat=Decimal("1500"),
                magic_size_multiplier=Decimal("1.20"),
            )
        )
    ).itemized["center_stone_cost"]
    linear_expectation = just_under / Decimal("0.95") * Decimal("1.00")
    assert at_one > linear_expectation  # the band multiplier adds the jump
    assert at_one == 180000  # 1500 × 1.00 × 1.20 = €1800


def test_lab_vs_natural_large_delta():  # case 3
    lab = compute_price(base_inputs()).total_minor
    natural = compute_price(
        base_inputs(
            stone=StonePricingInput(
                stone_type="natural_diamond",
                shape="oval",
                carat=Decimal("1.00"),
                price_per_carat=Decimal("5000"),  # different table entirely
                magic_size_multiplier=Decimal("1.20"),
            )
        )
    ).total_minor
    assert natural > lab
    assert (natural - lab) > 100000  # > €1000 delta


def test_stale_feed_becomes_quote_only_with_range_never_nan():  # case 4
    result = compute_price(base_inputs(metal_price=metal("112.50", is_too_stale=True)))
    assert result.status == "quote_only"
    assert result.total_minor is None  # exact checkout disabled
    assert result.range_min_minor is not None and result.range_max_minor is not None
    assert result.range_min_minor < result.range_max_minor
    assert any(r["code"] == "metal_price_stale" for r in result.reasons)
    assert result.degraded is True
    assert result.snapshot is None  # nothing purchasable to freeze


def test_stale_within_max_age_is_degraded_but_purchasable():
    result = compute_price(base_inputs(metal_price=metal("112.50", is_stale=True)))
    assert result.status == "purchasable"
    assert result.degraded is True
    assert result.total_minor is not None


def test_missing_metal_price_no_total_no_fake_range():
    result = compute_price(base_inputs(metal_price=None))
    assert result.status == "quote_only"
    assert result.total_minor is None
    assert result.range_min_minor is None  # no basis at all → no range either
    assert all(v is not None for v in result.itemized.values())  # never NaN/None inside


def test_missing_stone_table_row_is_quote_only():
    result = compute_price(
        base_inputs(
            stone=StonePricingInput(
                stone_type="natural_diamond",
                shape="oval",
                carat=Decimal("3.00"),
                price_per_carat=None,  # outside admin tables
            )
        )
    )
    assert result.status == "quote_only"
    assert result.total_minor is None
    assert any(r["code"] == "stone_price_unavailable" for r in result.reasons)


def test_special_engraving_adds_cost_and_non_returnable():  # case 6
    result = compute_price(
        base_inputs(
            engraving=EngravingInput(
                type="special",
                base_cost_minor=2500,
                per_char_cost_minor=100,
                char_count=10,
                makes_non_returnable=True,
            )
        )
    )
    assert result.itemized["engraving_cost"] == 3500
    assert result.non_returnable is True


def test_second_market_fx_and_vat_swap():  # case 7
    result = compute_price(
        base_inputs(
            currency="USD",
            fx=FxInput(
                base="EUR",
                quote="USD",
                rate=Decimal("1.10"),
                source="ecb",
                fetched_at=NOW,
            ),
            vat=VatInput(market="US", rate=Decimal("0"), price_includes_vat=False),
        )
    )
    assert result.status == "purchasable"
    # metal converted: 6.039 × 112.50 × 1.10 × 1.05 = $784.69 → 78469
    assert result.itemized["metal_cost"] == 78469
    assert result.itemized.get("vat", 0) == 0
    snap = result.snapshot
    assert snap["fx_rate"]["rate"] == "1.10"  # both rates stored
    assert snap["metal_prices"]["price_per_gram"] == "112.50"


def test_side_stones_and_buffers_itemized():
    result = compute_price(
        base_inputs(
            side_stones=(SideStoneInput(per_stone_minor=1500, qty=8),),
            buffers=(
                BufferInput(kind="shipping", type="fixed", value=Decimal(2500)),
                BufferInput(kind="payment_fee", type="percent", value=Decimal("0.02")),
            ),
        )
    )
    assert result.itemized["side_stone_cost"] == 12000
    assert result.itemized["shipping_buffer"] == 2500
    base = (
        result.itemized["metal_cost"]
        + result.itemized["center_stone_cost"]
        + result.itemized["side_stone_cost"]
        + result.itemized["setting_labor"]
        + result.itemized["casting_labor"]
        + result.itemized["polishing_labor"]
    )
    assert abs(result.itemized["payment_fee_buffer"] - round(base * 0.02)) <= 1


def test_rule_modifier_surcharge_flows_into_price():
    plain = compute_price(base_inputs()).total_minor
    with_mod = compute_price(
        base_inputs(
            rule_modifiers=({"surcharge_minor": 2500, "makes_non_returnable": True},)
        )
    )
    assert with_mod.itemized["rule_modifiers"] == 2500
    assert with_mod.non_returnable is True
    assert with_mod.total_minor > plain


# --- Snapshot (cases 8 & 9) ---


def test_snapshot_reproduces_total_byte_for_byte():  # case 8
    result = compute_price(base_inputs())
    snap = result.snapshot
    assert snap["total_minor"] == result.total_minor
    reproduced = reproduce_price(snap)
    assert reproduced.total_minor == result.total_minor
    assert reproduced.itemized == result.itemized


def test_version_pin_proof():  # case 9
    """Change formula/margin/density AFTER an order exists: the historical

    snapshot still reproduces its original total; a fresh identical config
    prices under the new rules.
    """
    original = compute_price(
        base_inputs(versions=VersionPins(price_formula_version=1, margin_rule_version=1))
    )
    snap = original.snapshot

    # "Later": margin raised, density corrected, formula v2.
    new_result = compute_price(
        base_inputs(
            margin=MarginInput(type="percent", value=Decimal("0.75")),
            weight=WeightInput(
                cad_volume_mm3=Decimal("380"),
                specific_gravity=Decimal("15.60"),  # density table updated
                fabrication_premium=Decimal("1.05"),
            ),
            versions=VersionPins(price_formula_version=2, margin_rule_version=2),
        )
    )
    assert new_result.total_minor != original.total_minor  # fresh config → new rules

    reproduced = reproduce_price(snap)  # historical order → pinned inputs
    assert reproduced.total_minor == original.total_minor
    assert snap["versions"]["margin_rule_version"] == 1
    assert new_result.snapshot["versions"]["margin_rule_version"] == 2


def test_snapshot_carries_source_refs_and_versions():
    result = compute_price(
        base_inputs(
            metal_price=metal("112.50", snapshot_id="mps-123"),
            versions=VersionPins(rule_set_version=3),
        )
    )
    snap = result.snapshot
    assert snap["source_refs"]["metal_price_snapshot_id"] == "mps-123"
    assert snap["versions"]["rule_set_version"] == 3
    assert snap["computed_by"] == "server"
    assert snap["weight"]["source"] == "estimated"
