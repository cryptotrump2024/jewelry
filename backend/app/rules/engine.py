"""Rules-engine validate() (docs/spec/07 §4).

Pure and DB-free: callers (config service, pricing, admin rule-simulator)
pass plain data in and get a ValidationResult back. Deterministic conflict
priority (07 §4): hard blocks > requirements > visibility > price modifiers;
modifiers stack in sort order. Status meanings are canonical per docs/spec/06
§6: invalid = no price; quote_only = valid but not firmly priceable;
purchasable otherwise. Pricing-input freshness can further downgrade
purchasable → quote_only in the pricing engine, never the reverse.

Rule-type contracts (condition/effect shapes):
- compatibility: condition is an implication that must hold; False → block.
- exclusion: condition True → block.
- requirement: condition True → effect.require_option_group must be selected.
- conditional_visibility: condition True → effect.show_option_group /
  effect.hide_option_group toggles group visibility.
- price_modifier: condition True → effect collected for the pricing engine.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.rules.evaluator import JsonLogicError, evaluate

PURCHASABLE = "purchasable"
QUOTE_ONLY = "quote_only"
INVALID = "invalid"

_TYPE_PRIORITY = {
    "exclusion": 0,
    "compatibility": 0,
    "requirement": 1,
    "conditional_visibility": 2,
    "price_modifier": 3,
}


@dataclass(frozen=True)
class RuleData:
    """DB-independent mirror of the rules table rows."""

    type: str
    condition: Mapping[str, Any]
    effect: Mapping[str, Any]
    message: str | None = None
    scope: Mapping[str, Any] | None = None
    sort: int = 0


@dataclass(frozen=True)
class ManufacturabilityLimits:
    """Mirror of template_manufacturability (+ factory limits merged in)."""

    min_band_thickness_mm: float | None = None
    min_wall_thickness_mm: float | None = None
    min_prong_thickness_mm: float | None = None
    stone_measurement_min_mm: float | None = None
    stone_measurement_max_mm: float | None = None
    requires_manual_cad_check: bool = False


@dataclass
class ValidationResult:
    status: str
    reasons: list[dict[str, str]] = field(default_factory=list)
    visible_groups: list[str] = field(default_factory=list)
    required_groups: list[str] = field(default_factory=list)
    modifiers: list[dict[str, Any]] = field(default_factory=list)
    degraded: bool = False


def _scope_matches(rule: RuleData, template_groups: Sequence[str]) -> bool:
    if not rule.scope:
        return True
    scoped_group = rule.scope.get("option_group")
    if scoped_group and scoped_group not in template_groups:
        return False
    return True


def _selected(selections: Mapping[str, Any], group_key: str) -> bool:
    value = selections.get(group_key)
    if isinstance(value, Mapping):
        return any(v is not None for v in value.values())
    return value is not None and value != ""


def validate(
    selections: Mapping[str, Any],
    rules: Sequence[RuleData],
    template_groups: Sequence[str],
    required_groups: Sequence[str] = (),
    limits: ManufacturabilityLimits | None = None,
    attributes: Mapping[str, float] | None = None,
) -> ValidationResult:
    """Evaluate a configuration against a template's active rule set.

    selections: chosen option codes per group key (values may be nested dicts
        for per-component choices, e.g. {"metal": {"shank": "silver"}}).
    rules: the published rule-set rows.
    template_groups: option-group keys the template offers.
    required_groups: groups the template marks is_required.
    limits: manufacturability limits; attributes: resolved physical values
        (band thickness, stone mm...) to check against them.
    """
    reasons: list[dict[str, str]] = []
    blocked = False
    unmet: list[str] = []
    visible = set(template_groups)
    modifiers: list[dict[str, Any]] = []
    quote_only_flags: list[str] = []

    applicable = [r for r in rules if _scope_matches(r, template_groups)]
    ordered = sorted(applicable, key=lambda r: (_TYPE_PRIORITY.get(r.type, 99), r.sort))

    for rule in ordered:
        try:
            triggered = bool(evaluate(rule.condition, selections))
        except JsonLogicError as exc:
            # A malformed rule must never silently pass (fail safe, not silent).
            blocked = True
            reasons.append({"code": "rule_error", "message": f"Rule error: {exc}"})
            continue

        if rule.type == "exclusion":
            if triggered:
                blocked = True
                reasons.append(
                    {"code": "blocked", "message": rule.message or "Combination not available."}
                )
        elif rule.type == "compatibility":
            if not triggered:
                blocked = True
                reasons.append(
                    {"code": "incompatible", "message": rule.message or "Combination invalid."}
                )
        elif rule.type == "requirement":
            if triggered:
                group = rule.effect.get("require_option_group")
                if group:
                    if group not in visible:
                        visible.add(group)
                    if not _selected(selections, group):
                        unmet.append(group)
                        reasons.append(
                            {
                                "code": "requirement_unmet",
                                "message": rule.message or f"'{group}' selection required.",
                            }
                        )
        elif rule.type == "conditional_visibility":
            show = rule.effect.get("show_option_group")
            hide = rule.effect.get("hide_option_group")
            if triggered:
                if show:
                    visible.add(show)
                if hide:
                    visible.discard(hide)
            elif show and show not in template_groups:
                # a show-only group stays hidden unless its condition holds
                visible.discard(show)
        elif rule.type == "price_modifier":
            if triggered:
                modifiers.append(dict(rule.effect) | {"message": rule.message or ""})

    # Requirements from the template itself (is_required flags).
    for group in required_groups:
        if group in visible and not _selected(selections, group):
            unmet.append(group)
            reasons.append(
                {"code": "requirement_unmet", "message": f"'{group}' selection required."}
            )

    # Manufacturability (docs/spec/07 §4: breach → invalid; borderline/manual
    # CAD check → quote_only, never purchasable).
    if limits:
        attrs = attributes or {}

        def _breach(limit: float | None, value: float | None, label: str, minimum: bool) -> None:
            nonlocal blocked
            if limit is None or value is None:
                return
            if (minimum and value < limit) or (not minimum and value > limit):
                blocked = True
                reasons.append(
                    {
                        "code": "manufacturability",
                        "message": f"{label} of {value} breaches limit {limit}.",
                    }
                )

        _breach(
            limits.min_band_thickness_mm, attrs.get("band_thickness_mm"), "Band thickness", True
        )
        _breach(
            limits.min_wall_thickness_mm, attrs.get("wall_thickness_mm"), "Wall thickness", True
        )
        _breach(
            limits.min_prong_thickness_mm, attrs.get("prong_thickness_mm"), "Prong thickness", True
        )
        _breach(
            limits.stone_measurement_min_mm, attrs.get("stone_measurement_mm"), "Stone size", True
        )
        _breach(
            limits.stone_measurement_max_mm, attrs.get("stone_measurement_mm"), "Stone size", False
        )
        if limits.requires_manual_cad_check and not blocked:
            quote_only_flags.append("Manual CAD check required before firm pricing.")

    if blocked or unmet:
        status = INVALID
    elif quote_only_flags:
        status = QUOTE_ONLY
        reasons.extend({"code": "quote_only", "message": m} for m in quote_only_flags)
    else:
        status = PURCHASABLE

    return ValidationResult(
        status=status,
        reasons=reasons,
        visible_groups=sorted(visible),
        required_groups=sorted(set(unmet) | set(required_groups)),
        modifiers=modifiers,
    )
