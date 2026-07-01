"""Phase 2 exit, DB half: validate() against the *seeded* template's

published rule set (demo Oval Solitaire from app.seeds.demo_template),
exactly as the spec words it — not just in-memory fixtures.
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import ProductTemplate, RuleSet
from app.rules import validate
from app.rules.engine import INVALID, PURCHASABLE, RuleData

GROUPS = ["metal", "stone_type", "stone_shape", "carat", "ring_size", "certificate", "engraving"]


async def _load_seeded_rules() -> list[RuleData]:
    async with get_session_factory()() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        rule_set = (
            await session.execute(
                select(RuleSet).where(
                    RuleSet.template_id == template.id,
                    RuleSet.status == "published",
                )
            )
        ).scalar_one()
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
        ]


async def test_seeded_ruleset_validates_purchasable_config():
    rules = await _load_seeded_rules()
    config = {
        "metal": {"shank": "gold", "head": "gold"},
        "stone_type": "lab_diamond",
        "stone_shape": "oval",
        "carat": "0.30",
        "ring_size": "54",
    }
    result = validate(config, rules, GROUPS)
    assert result.status == PURCHASABLE


async def test_seeded_ruleset_blocks_silver_gold_mix():
    rules = await _load_seeded_rules()
    config = {
        "metal": {"shank": "silver", "head": "gold"},
        "stone_type": "lab_diamond",
        "stone_shape": "oval",
        "carat": "0.30",
    }
    result = validate(config, rules, GROUPS)
    assert result.status == INVALID
    assert any("Silver" in r["message"] for r in result.reasons)


async def test_seeded_ruleset_requires_certificate_above_030ct():
    rules = await _load_seeded_rules()
    config = {
        "metal": {"shank": "gold", "head": "gold"},
        "stone_type": "natural_diamond",
        "stone_shape": "oval",
        "carat": "1.00",
    }
    result = validate(config, rules, GROUPS)
    assert result.status == INVALID
    assert "certificate" in result.required_groups

    result_ok = validate(config | {"certificate": "gia"}, rules, GROUPS)
    assert result_ok.status == PURCHASABLE


async def test_seeded_special_engraving_modifier_flows_through():
    rules = await _load_seeded_rules()
    config = {
        "metal": {"shank": "gold", "head": "gold"},
        "stone_type": "lab_diamond",
        "stone_shape": "oval",
        "carat": "0.30",
        "engraving": {"type": "special"},
    }
    result = validate(config, rules, GROUPS)
    assert result.status == PURCHASABLE
    assert result.modifiers and result.modifiers[0]["surcharge_minor"] == 2500
    assert result.modifiers[0]["makes_non_returnable"] is True
