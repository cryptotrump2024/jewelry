"""Rule-simulator publish check (docs/spec/07 §4 + §9 case 8).

A rule set that produces contradictory requirements (A requires B while B is
excluded, or every configuration blocks) is a configuration error that must
be caught at publish time, never by a customer. The simulator exhaustively
validates the cartesian product of offered options (bounded — rule sets are
per-template and option counts are small) and reports:

- contradictions: configs where a required group's every option is blocked,
  or requirements that can never be satisfied
- dead_options: options that appear in no valid configuration
- always_blocked: True when no configuration at all validates

The admin publish flow refuses to publish when `ok` is False.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from typing import Any

from app.rules.engine import INVALID, RuleData, validate

MAX_COMBINATIONS = 100_000  # hard cap; beyond this sample deterministically


@dataclass
class SimulationReport:
    ok: bool
    total_combinations: int
    valid_count: int
    invalid_count: int
    quote_only_count: int
    always_blocked: bool
    dead_options: dict[str, list[str]] = field(default_factory=dict)
    contradictions: list[str] = field(default_factory=list)
    sampled: bool = False


def simulate_rule_set(
    rules: Sequence[RuleData],
    group_options: Mapping[str, Sequence[Any]],
    required_groups: Sequence[str] = (),
) -> SimulationReport:
    """Exhaustively validate every option combination for a template.

    group_options: {group_key: [option codes]} as the configurator would
    offer them (metal values may be nested dicts for per-component metals).
    """
    keys = list(group_options.keys())
    pools = [list(group_options[k]) for k in keys]

    total = 1
    for pool in pools:
        total *= max(len(pool), 1)

    sampled = total > MAX_COMBINATIONS
    combos = product(*pools)

    valid = invalid = quote_only = 0
    seen_valid_option: dict[str, set] = {k: set() for k in keys}
    requirement_failures: dict[str, int] = {}
    checked = 0

    for combo in combos:
        if sampled and checked >= MAX_COMBINATIONS:
            break
        checked += 1
        selections = dict(zip(keys, combo, strict=True))
        result = validate(
            selections, rules, template_groups=keys, required_groups=required_groups
        )
        if result.status == INVALID:
            invalid += 1
            for reason in result.reasons:
                if reason["code"] == "requirement_unmet":
                    requirement_failures[reason["message"]] = (
                        requirement_failures.get(reason["message"], 0) + 1
                    )
        else:
            if result.status == "quote_only":
                quote_only += 1
            valid += 1
            for key, value in selections.items():
                seen_valid_option[key].add(_hashable(value))

    always_blocked = valid == 0 and checked > 0

    dead_options: dict[str, list[str]] = {}
    if not always_blocked:
        for key in keys:
            dead = [
                str(opt)
                for opt in group_options[key]
                if _hashable(opt) not in seen_valid_option[key]
            ]
            if dead:
                dead_options[key] = dead

    contradictions: list[str] = []
    if always_blocked:
        contradictions.append(
            "No combination of offered options validates — the rule set blocks everything."
        )
    for message, count in requirement_failures.items():
        # A requirement that fails in every checked combination can never be
        # satisfied by the offered options (e.g. requires a group with no
        # selectable option): mutual require/exclude shows up here.
        if count == checked:
            contradictions.append(f"Requirement can never be satisfied: {message}")

    return SimulationReport(
        ok=not always_blocked and not contradictions,
        total_combinations=total,
        valid_count=valid,
        invalid_count=invalid,
        quote_only_count=quote_only,
        always_blocked=always_blocked,
        dead_options=dead_options,
        contradictions=contradictions,
        sampled=sampled,
    )


def _hashable(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    return value
