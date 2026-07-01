"""Phase 1 exit test (docs/spec/14-roadmap-and-open-decisions.md):

  "you can persist a template with components, option groups/options,
   manufacturability limits, and a versioned rule-set by hand (SQL/fixtures);
   invalid metal combos are impossible to select because only material_options
   are offered."

The session fixture applies all migrations and runs seed_all(), which includes
the demo-template fixture — so these tests read back what was persisted.
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import (
    MaterialOption,
    Metal,
    MetalColor,
    MetalPurity,
    Option,
    OptionGroup,
    ProductTemplate,
    RuleSet,
    TemplateManufacturability,
    Tenant,
)

# Combinations that must never be offered (nonsense materials).
FORBIDDEN_COMBOS = {
    ("silver", 750),  # silver has no 18k
    ("silver", 585),
    ("platinum", 750),
    ("gold", 950),  # 950 is platinum fineness
    ("gold", 925),
}
FORBIDDEN_COLORED = {("platinum", "rose"), ("platinum", "yellow"), ("silver", "rose")}


async def _session():
    return get_session_factory()()


async def test_template_persisted_with_components_and_limits():
    async with await _session() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        assert template.status == "active"

        await session.refresh(template, ["components", "option_group_links"])
        kinds = {c.kind for c in template.components}
        assert {"shank", "head", "prongs", "center_stone"} <= kinds
        # CAD volumes present on metal parts (weight engine input).
        assert all(
            c.cad_volume_mm3 is not None for c in template.components if c.metal_assignable
        )

        limits = (
            (
                await session.execute(
                    select(TemplateManufacturability).where(
                        TemplateManufacturability.template_id == template.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert limits and limits[0].min_band_thickness_mm is not None


async def test_option_groups_attached_in_step_order_with_default():
    async with await _session() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        await session.refresh(template, ["option_group_links"])
        links = template.option_group_links
        assert [link.step_order for link in links] == sorted(
            link.step_order for link in links
        )
        keys = []
        for link in links:
            group = (
                await session.execute(
                    select(OptionGroup).where(OptionGroup.id == link.option_group_id)
                )
            ).scalar_one()
            keys.append(group.key)
            if group.key == "metal":
                assert link.default_option_id is not None  # fresh configurator is complete
        assert keys == ["metal", "stone_type", "stone_shape", "carat", "ring_size"]


async def test_versioned_rule_set_published():
    async with await _session() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        rule_set = (
            await session.execute(
                select(RuleSet).where(
                    RuleSet.template_id == template.id, RuleSet.version == 1
                )
            )
        ).scalar_one()
        assert rule_set.status == "published"
        await session.refresh(rule_set, ["rules"])
        types = {r.type for r in rule_set.rules}
        assert {"requirement", "exclusion", "price_modifier"} <= types
        # Rules are data, not code: JSON-logic condition + effect present.
        assert all(r.condition and r.effect for r in rule_set.rules)


async def test_invalid_metal_combos_impossible():
    """The exit rule: the configurator offers material_options, never free

    metal x purity x color — so nonsense combos must not exist anywhere in
    material_options NOR in the generated metal option group.
    """
    async with await _session() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == "default"))
        ).scalar_one()

        rows = (
            await session.execute(
                select(Metal.key, MetalPurity.fineness, MetalColor.key)
                .select_from(MaterialOption)
                .join(Metal, Metal.id == MaterialOption.metal_id)
                .join(MetalPurity, MetalPurity.id == MaterialOption.purity_id)
                .join(MetalColor, MetalColor.id == MaterialOption.color_id, isouter=True)
                .where(MaterialOption.tenant_id == tenant.id)
            )
        ).all()
        assert rows, "material_options must be seeded"
        for metal_key, fineness, color_key in rows:
            assert (metal_key, fineness) not in FORBIDDEN_COMBOS
            if color_key:
                assert (metal_key, color_key) not in FORBIDDEN_COLORED

        # The metal option group mirrors material_options exactly.
        metal_group = (
            await session.execute(
                select(OptionGroup).where(
                    OptionGroup.tenant_id == tenant.id, OptionGroup.key == "metal"
                )
            )
        ).scalar_one()
        option_codes = {
            o.code
            for o in (
                await session.execute(
                    select(Option).where(Option.option_group_id == metal_group.id)
                )
            )
            .scalars()
            .all()
        }
        valid_codes = set()
        for metal_key, fineness, color_key in rows:
            valid_codes.add(
                "_".join([metal_key, str(fineness)] + ([color_key] if color_key else []))
            )
        assert option_codes == valid_codes
        assert "silver_750" not in option_codes
        assert "platinum_950_rose" not in option_codes


async def test_seed_all_idempotent_for_demo_template():
    from app.seeds import seed_all

    await seed_all()
    async with await _session() as session:
        templates = (
            (
                await session.execute(
                    select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
                )
            )
            .scalars()
            .all()
        )
        assert len(templates) == 1
        rule_sets = (
            (
                await session.execute(
                    select(RuleSet).where(RuleSet.template_id == templates[0].id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rule_sets) == 1