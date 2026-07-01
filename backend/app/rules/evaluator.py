"""Safe JSON-logic evaluator (docs/spec/07 §3).

Deterministic, allow-listed operators only — no arbitrary code, no attribute
access, no callables in data. Unknown operators raise instead of guessing
(fail safe, not silent).

Condition shape examples:
    {">": [{"var": "carat"}, 0.30]}
    {"and": [{"in": [{"var": "metal.shank"}, ["silver"]]},
             {"in": [{"var": "metal.head"}, ["gold", "platinum"]]}]}

`var` resolves dotted paths against the selection dict; a missing path
resolves to None (rules must tolerate partially-filled configurations).
"""

from collections.abc import Mapping
from typing import Any

MAX_DEPTH = 32


class JsonLogicError(ValueError):
    """Malformed or disallowed rule logic."""


def _resolve_var(path: Any, data: Mapping[str, Any]) -> Any:
    if not isinstance(path, str):
        raise JsonLogicError(f"var path must be a string, got {type(path).__name__}")
    current: Any = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _to_number(value: Any) -> float | None:
    """Numeric coercion for comparisons; strings like "0.50" (carat option

    codes) compare numerically. Returns None when not coercible.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _loose_eq(a: Any, b: Any) -> bool:
    na, nb = _to_number(a), _to_number(b)
    if na is not None and nb is not None:
        return na == nb
    return a == b


def _compare(op: str, args: list[Any]) -> bool:
    if len(args) != 2:
        raise JsonLogicError(f"'{op}' expects exactly 2 arguments")
    na, nb = _to_number(args[0]), _to_number(args[1])
    if na is None or nb is None:
        return False  # missing/non-numeric input can never satisfy a comparison
    match op:
        case ">":
            return na > nb
        case ">=":
            return na >= nb
        case "<":
            return na < nb
        case "<=":
            return na <= nb
    raise JsonLogicError(f"unknown comparison '{op}'")


def evaluate(logic: Any, data: Mapping[str, Any], _depth: int = 0) -> Any:
    """Evaluate a JSON-logic expression against a selection dict."""
    if _depth > MAX_DEPTH:
        raise JsonLogicError("rule nesting too deep")

    # Literals evaluate to themselves.
    if logic is None or isinstance(logic, bool | int | float | str):
        return logic
    if isinstance(logic, list):
        return [evaluate(item, data, _depth + 1) for item in logic]
    if not isinstance(logic, Mapping):
        raise JsonLogicError(f"cannot evaluate {type(logic).__name__}")
    if len(logic) != 1:
        raise JsonLogicError("rule object must have exactly one operator")

    op, raw_args = next(iter(logic.items()))

    if op == "var":
        return _resolve_var(raw_args, data)

    args = raw_args if isinstance(raw_args, list) else [raw_args]

    match op:
        case "and":
            return all(bool(evaluate(a, data, _depth + 1)) for a in args)
        case "or":
            return any(bool(evaluate(a, data, _depth + 1)) for a in args)
        case "not" | "!":
            if len(args) != 1:
                raise JsonLogicError("'not' expects exactly 1 argument")
            return not bool(evaluate(args[0], data, _depth + 1))
        case "==":
            if len(args) != 2:
                raise JsonLogicError("'==' expects exactly 2 arguments")
            return _loose_eq(
                evaluate(args[0], data, _depth + 1), evaluate(args[1], data, _depth + 1)
            )
        case "!=":
            if len(args) != 2:
                raise JsonLogicError("'!=' expects exactly 2 arguments")
            return not _loose_eq(
                evaluate(args[0], data, _depth + 1), evaluate(args[1], data, _depth + 1)
            )
        case ">" | ">=" | "<" | "<=":
            return _compare(op, [evaluate(a, data, _depth + 1) for a in args])
        case "in":
            if len(args) != 2:
                raise JsonLogicError("'in' expects exactly 2 arguments")
            needle = evaluate(args[0], data, _depth + 1)
            haystack = evaluate(args[1], data, _depth + 1)
            if haystack is None:
                return False
            if isinstance(haystack, str):
                return isinstance(needle, str) and needle in haystack
            if isinstance(haystack, list):
                return needle in haystack
            raise JsonLogicError("'in' haystack must be a list or string")
        case "missing":
            checked = [a for a in args if _resolve_var(a, data) is None]
            return checked
        case "if":
            # if [cond, then, elif_cond, elif_then, ..., else]
            i = 0
            while i + 1 < len(args):
                if bool(evaluate(args[i], data, _depth + 1)):
                    return evaluate(args[i + 1], data, _depth + 1)
                i += 2
            return evaluate(args[i], data, _depth + 1) if i < len(args) else None

    raise JsonLogicError(f"operator '{op}' is not allow-listed")
