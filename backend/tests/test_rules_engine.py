"""Phase 2 exit test (docs/spec/14):

  "validate() correctly returns purchasable/quote_only/invalid + reasons on a
   seeded template with real compatibility/exclusion/requirement/conditional
   rules. Unit tests green."

Covers the evaluator allow-list and the docs/spec/07 §9 cases that don't need
pricing (2, 3, 4, 9).
"""

import pytest

from app.rules import JsonLogicError, evaluate, validate
from app.rules.engine import (
    INVALID,
    PURCHASABLE,
    QUOTE_ONLY,
    ManufacturabilityLimits,
    RuleData,
)

# --- Evaluator ---


def test_var_dotted_paths_and_missing():
    data = {"metal": {"shank": "silver"}, "carat": "1.00"}
    assert evaluate({"var": "metal.shank"}, data) == "silver"
    assert evaluate({"var": "metal.head"}, data) is None
    assert evaluate({"var": "nope.deep"}, data) is None


def test_numeric_coercion_for_carat_strings():
    assert evaluate({">": [{"var": "carat"}, 0.30]}, {"carat": "0.50"}) is True
    assert evaluate({">": [{"var": "carat"}, 0.30]}, {"carat": "0.30"}) is False
    assert evaluate({">": [{"var": "carat"}, 0.30]}, {}) is False  # missing → never satisfied
    assert evaluate({"==": [{"var": "carat"}, 1]}, {"carat": "1.00"}) is True


def test_boolean_operators():
    logic = {
        "and": [
            {"in": [{"var": "metal.shank"}, ["silver"]]},
            {"in": [{"var": "metal.head"}, ["gold", "platinum"]]},
        ]
    }
    assert evaluate(logic, {"metal": {"shank": "silver", "head": "gold"}}) is True
    assert evaluate(logic, {"metal": {"shank": "gold", "head": "gold"}}) is False
    assert evaluate({"or": [False, {"!": [False]}]}, {}) is True


def test_disallowed_operator_raises():
    with pytest.raises(JsonLogicError, match="not allow-listed"):
        evaluate({"eval": ["__import__('os')"]}, {})
    with pytest.raises(JsonLogicError, match="exactly one operator"):
        evaluate({"and": [True], "or": [True]}, {})


def test_nesting_depth_capped():
    logic: dict = {"var": "x"}
    for _ in range(50):
        logic = {"not": [logic]}
    with pytest.raises(JsonLogicError, match="too deep"):
        evaluate(logic, {"x": True})


# --- validate(): docs/spec/07 §9 cases ---

RULES = [
    RuleData(
        type="exclusion",
        condition={
            "and": [
                {"in": [{"var": "metal.shank"}, ["silver"]]},
                {"in": [{"var": "metal.head"}, ["gold", "platinum"]]},
            ]
        },
        effect={"block": True},
        message="Silver cannot be combined with gold or platinum in the same ring.",
        sort=0,
    ),
    RuleData(
        type="requirement",
        condition={">": [{"var": "carat"}, 0.30]},
        effect={"require_option_group": "certificate"},
        message="Diamonds above 0.30 ct require a certificate selection.",
        sort=1,
    ),
    RuleData(
        type="conditional_visibility",
        condition={"==": [{"var": "style"}, "pave"]},
        effect={"show_option_group": "side_stone"},
        sort=2,
    ),
    RuleData(
        type="price_modifier",
        condition={"==": [{"var": "engraving.type"}, "special"]},
        effect={"surcharge_minor": 2500, "makes_non_returnable": True},
        message="Special engraving surcharge.",
        sort=3,
    ),
]

GROUPS = ["metal", "stone_type", "stone_shape", "carat", "ring_size", "certificate"]

BASE = {
    "metal": {"shank": "gold", "head": "gold"},
    "stone_type": "lab_diamond",
    "stone_shape": "oval",
    "carat": "0.30",
    "ring_size": "54",
}


def test_valid_configuration_is_purchasable():
    result = validate(BASE, RULES, GROUPS)
    assert result.status == PURCHASABLE
    assert result.reasons == []
    assert result.modifiers == []


def test_incompatible_metal_blocks_with_message():  # 07 §9 case 2
    config = BASE | {"metal": {"shank": "silver", "head": "gold"}}
    result = validate(config, RULES, GROUPS)
    assert result.status == INVALID
    assert any("Silver cannot be combined" in r["message"] for r in result.reasons)


def test_carat_above_threshold_requires_certificate():  # 07 §9 case 3
    config = BASE | {"carat": "0.35"}
    result = validate(config, RULES, GROUPS)
    assert result.status == INVALID
    assert "certificate" in result.required_groups
    assert any(r["code"] == "requirement_unmet" for r in result.reasons)

    # Choosing a certificate resolves it.
    result_ok = validate(config | {"certificate": "igi"}, RULES, GROUPS)
    assert result_ok.status == PURCHASABLE


def test_side_stone_group_hidden_without_support():  # 07 §9 case 4
    result = validate(BASE, RULES, GROUPS)
    assert "side_stone" not in result.visible_groups
    result_pave = validate(BASE | {"style": "pave"}, RULES, GROUPS)
    assert "side_stone" in result_pave.visible_groups


def test_special_engraving_collects_modifier():  # 07 §9 case 5 (rule side)
    config = BASE | {"engraving": {"type": "special"}}
    result = validate(config, RULES, GROUPS)
    assert result.status == PURCHASABLE
    assert result.modifiers == [
        {
            "surcharge_minor": 2500,
            "makes_non_returnable": True,
            "message": "Special engraving surcharge.",
        }
    ]


def test_template_required_group_unselected_is_invalid():
    result = validate(BASE | {"stone_type": None}, RULES, GROUPS, required_groups=["stone_type"])
    assert result.status == INVALID
    assert "stone_type" in result.required_groups


def test_manufacturability_breach_is_invalid():  # 07 §9 case 9
    limits = ManufacturabilityLimits(
        min_band_thickness_mm=1.6, stone_measurement_min_mm=4.0, stone_measurement_max_mm=10.5
    )
    result = validate(
        BASE, RULES, GROUPS, limits=limits, attributes={"band_thickness_mm": 1.2}
    )
    assert result.status == INVALID
    assert any(r["code"] == "manufacturability" for r in result.reasons)

    too_big = validate(
        BASE, RULES, GROUPS, limits=limits, attributes={"stone_measurement_mm": 11.0}
    )
    assert too_big.status == INVALID


def test_manual_cad_check_is_quote_only_never_purchasable():  # 07 §9 case 9
    limits = ManufacturabilityLimits(requires_manual_cad_check=True)
    result = validate(BASE, RULES, GROUPS, limits=limits, attributes={})
    assert result.status == QUOTE_ONLY
    assert any(r["code"] == "quote_only" for r in result.reasons)


def test_block_wins_over_everything():  # 07 §4 priority
    config = BASE | {
        "metal": {"shank": "silver", "head": "platinum"},
        "carat": "1.00",
        "engraving": {"type": "special"},
    }
    result = validate(config, RULES, GROUPS)
    assert result.status == INVALID
    # Both problems surface (two blocks → both messages).
    codes = {r["code"] for r in result.reasons}
    assert "blocked" in codes and "requirement_unmet" in codes


def test_malformed_rule_fails_safe():
    bad = [RuleData(type="exclusion", condition={"steal": ["x"]}, effect={"block": True})]
    result = validate(BASE, bad, GROUPS)
    assert result.status == INVALID
    assert any(r["code"] == "rule_error" for r in result.reasons)
