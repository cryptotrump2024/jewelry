"""Rule-simulator publish check (docs/spec/07 §9 case 8): contradictory rule

sets are flagged before publish, never at runtime.
"""

from app.rules.engine import RuleData
from app.rules.simulator import simulate_rule_set

GROUP_OPTIONS = {
    "metal": ["gold_750_yellow", "platinum_950", "silver_925"],
    "stone_type": ["natural_diamond", "lab_diamond"],
    "carat": ["0.30", "0.50", "1.00"],
}


def test_healthy_rule_set_passes():
    rules = [
        RuleData(
            type="exclusion",
            condition={
                "and": [
                    {"==": [{"var": "metal"}, "silver_925"]},
                    {"==": [{"var": "stone_type"}, "natural_diamond"]},
                ]
            },
            effect={"block": True},
            message="Natural diamonds are not set in silver.",
        ),
    ]
    report = simulate_rule_set(rules, GROUP_OPTIONS)
    assert report.ok is True
    assert report.always_blocked is False
    assert report.total_combinations == 18
    assert report.invalid_count == 3  # silver × natural × 3 carats
    assert report.valid_count == 15
    assert report.dead_options == {}  # silver still valid with lab diamonds


def test_always_blocked_rule_set_flagged():
    rules = [
        RuleData(type="exclusion", condition={"==": [1, 1]}, effect={"block": True},
                 message="blocks everything"),
    ]
    report = simulate_rule_set(rules, GROUP_OPTIONS)
    assert report.ok is False
    assert report.always_blocked is True
    assert any("blocks everything" in c or "rule set blocks" in c for c in report.contradictions)


def test_mutual_require_exclude_contradiction_flagged():
    """A requires certificate, but certificate has no offered options →

    the requirement can never be satisfied (mutual require/exclude class).
    """
    rules = [
        RuleData(
            type="requirement",
            condition={">": [{"var": "carat"}, 0.0]},  # always triggers
            effect={"require_option_group": "certificate"},
            message="Certificate required.",
        ),
    ]
    report = simulate_rule_set(rules, GROUP_OPTIONS)  # no certificate group offered
    assert report.ok is False
    assert report.always_blocked is True
    assert any("never be satisfied" in c for c in report.contradictions)


def test_dead_option_detected():
    rules = [
        RuleData(
            type="exclusion",
            condition={"==": [{"var": "metal"}, "silver_925"]},
            effect={"block": True},
            message="Silver disabled on this template.",
        ),
    ]
    report = simulate_rule_set(rules, GROUP_OPTIONS)
    assert report.ok is True  # not contradictory, but reported
    assert report.dead_options == {"metal": ["silver_925"]}


def test_empty_optional_group_skipped_but_reported():
    report = simulate_rule_set([], GROUP_OPTIONS | {"ring_size": []})
    assert report.ok is True
    assert report.empty_groups == ["ring_size"]
    assert report.total_combinations == 18  # cartesian product ignores the empty group
    assert report.valid_count == 18  # not vacuously 0


def test_empty_required_group_is_a_contradiction():
    report = simulate_rule_set(
        [], GROUP_OPTIONS | {"ring_size": []}, required_groups=["ring_size"]
    )
    assert report.ok is False
    assert any("no selectable options" in c for c in report.contradictions)


def test_all_groups_empty_flagged():
    report = simulate_rule_set([], {"metal": []})
    assert report.ok is False
    assert report.always_blocked is True


def test_requirement_satisfiable_when_group_offered():
    rules = [
        RuleData(
            type="requirement",
            condition={">": [{"var": "carat"}, 0.30]},
            effect={"require_option_group": "certificate"},
            message="Certificate required above 0.30 ct.",
        ),
    ]
    options = GROUP_OPTIONS | {"certificate": ["gia", "igi"]}
    report = simulate_rule_set(rules, options)
    assert report.ok is True
    assert report.valid_count > 0
