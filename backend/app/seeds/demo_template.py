"""Phase 1 exit-test fixture: one complete engagement-ring template.

Persists an "Oval Solitaire" with components, option groups/options,
manufacturability limits and a versioned published rule-set — exactly what
docs/spec/14 Phase 1 requires to be persistable. The metal option group is
generated FROM material_options, which is why invalid metal combos are
impossible to offer.

Idempotent like all seeds.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    MaterialOption,
    Metal,
    MetalColor,
    MetalPurity,
    Option,
    OptionGroup,
    ProductTemplate,
    Rule,
    RuleSet,
    StoneShape,
    StoneType,
    TemplateComponent,
    TemplateManufacturability,
    TemplateOptionGroup,
    Tenant,
)
from app.seeds.reference import _get_or_create

TEMPLATE_CODE = "oval-solitaire"

COMPONENTS = [
    ("shank", "Band", Decimal("290.000"), True),
    ("head", "Head", Decimal("62.000"), True),
    ("prongs", "Prongs (4)", Decimal("18.000"), True),
    ("center_stone", "Center stone", None, False),
]

CARAT_OPTIONS = ["0.30", "0.50", "0.70", "1.00", "1.50", "2.00"]
CERTIFICATE_OPTIONS = ["gia", "igi"]

STEP_ORDER = ["metal", "stone_type", "stone_shape", "carat", "certificate", "ring_size"]


async def _material_code(session: AsyncSession, mo: MaterialOption) -> str:
    metal = (await session.execute(select(Metal).where(Metal.id == mo.metal_id))).scalar_one()
    purity = (
        await session.execute(select(MetalPurity).where(MetalPurity.id == mo.purity_id))
    ).scalar_one()
    color = None
    if mo.color_id:
        color = (
            await session.execute(select(MetalColor).where(MetalColor.id == mo.color_id))
        ).scalar_one()
    parts = [metal.key, str(purity.fineness)] + ([color.key] if color else [])
    return "_".join(parts)


async def seed_demo_template(session: AsyncSession, tenant: Tenant) -> ProductTemplate:
    tid = tenant.id

    category = (
        await session.execute(
            select(Category).where(Category.tenant_id == tid, Category.slug == "engagement-ring")
        )
    ).scalar_one()

    template = await _get_or_create(
        session,
        ProductTemplate,
        tenant_id=tid,
        code=TEMPLATE_CODE,
        defaults={
            "category_id": category.id,
            "name": "Oval Solitaire",
            "style": "solitaire",
            "status": "active",
        },
    )

    components: dict[str, TemplateComponent] = {}
    for sort, (kind, name, volume, metal_assignable) in enumerate(COMPONENTS):
        components[kind] = await _get_or_create(
            session,
            TemplateComponent,
            template_id=template.id,
            kind=kind,
            defaults={
                "name": name,
                "cad_volume_mm3": volume,
                "metal_assignable": metal_assignable,
                "sort": sort,
            },
        )

    # Manufacturability limits (docs/spec/05 Group B).
    await _get_or_create(
        session,
        TemplateManufacturability,
        template_id=template.id,
        component_id=None,
        defaults={
            "min_band_thickness_mm": Decimal("1.600"),
            "min_prong_thickness_mm": Decimal("0.800"),
            "prong_count": 4,
            "setting_type": "prong",
            "stone_seat_tolerance_mm": Decimal("0.100"),
            "stone_measurement_min_mm": Decimal("4.000"),
            "stone_measurement_max_mm": Decimal("10.500"),
            "requires_manual_cad_check": False,
        },
    )

    # --- Option groups + options ---
    groups: dict[str, OptionGroup] = {}
    for sort, key in enumerate(STEP_ORDER):
        groups[key] = await _get_or_create(
            session,
            OptionGroup,
            tenant_id=tid,
            key=key,
            defaults={"name": key.replace("_", " ").title(), "ui_type": "select", "sort": sort},
        )

    # Metal options come ONLY from material_options (the Phase 1 exit rule).
    material_options = (
        (
            await session.execute(
                select(MaterialOption).where(
                    MaterialOption.tenant_id == tid, MaterialOption.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    default_metal_option: Option | None = None
    for sort, mo in enumerate(material_options):
        code = await _material_code(session, mo)
        option = await _get_or_create(
            session,
            Option,
            option_group_id=groups["metal"].id,
            code=code,
            defaults={
                "label": mo.label,
                "value": {
                    "material_option_id": str(mo.id),
                    "fineness": mo.fineness,
                    "recommended": mo.recommended_for_engagement_rings,
                },
                "sort": sort,
            },
        )
        if code == "gold_750_yellow":
            default_metal_option = option

    stone_types = (
        (
            await session.execute(
                select(StoneType).where(StoneType.tenant_id == tid, StoneType.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    for sort, st in enumerate(stone_types):
        await _get_or_create(
            session,
            Option,
            option_group_id=groups["stone_type"].id,
            code=st.key,
            defaults={"label": st.name, "value": {"stone_type_id": str(st.id)}, "sort": sort},
        )

    shapes = (
        (await session.execute(select(StoneShape).where(StoneShape.tenant_id == tid)))
        .scalars()
        .all()
    )
    for sort, shape in enumerate(shapes):
        await _get_or_create(
            session,
            Option,
            option_group_id=groups["stone_shape"].id,
            code=shape.key,
            defaults={"label": shape.name, "value": {"shape_id": str(shape.id)}, "sort": sort},
        )

    for sort, carat in enumerate(CARAT_OPTIONS):
        await _get_or_create(
            session,
            Option,
            option_group_id=groups["carat"].id,
            code=carat,
            defaults={"label": f"{carat} ct", "value": {"carat": carat}, "sort": sort},
        )

    # Certificate options (required conditionally by rule when carat > 0.30).
    for sort, cert in enumerate(CERTIFICATE_OPTIONS):
        await _get_or_create(
            session,
            Option,
            option_group_id=groups["certificate"].id,
            code=cert,
            defaults={"label": cert.upper(), "value": {"lab": cert}, "sort": sort},
        )

    # Attach groups to the template in step order. certificate and ring_size
    # are not unconditionally required: the rule set requires certificate
    # only above 0.30 ct.
    for step, key in enumerate(STEP_ORDER, start=1):
        await _get_or_create(
            session,
            TemplateOptionGroup,
            template_id=template.id,
            option_group_id=groups[key].id,
            defaults={
                "step_order": step,
                "is_required": key not in ("ring_size", "certificate"),
                "default_option_id": default_metal_option.id
                if key == "metal" and default_metal_option
                else None,
            },
        )

    # --- Versioned, published rule set (docs/spec/07 shapes) ---
    rule_set = await _get_or_create(
        session,
        RuleSet,
        tenant_id=tid,
        template_id=template.id,
        version=1,
        defaults={"status": "published", "published_at": datetime.now(UTC)},
    )

    rules = [
        {
            "type": "requirement",
            "scope": {"option_group": "carat"},
            "condition": {">": [{"var": "carat"}, 0.30]},
            "effect": {"require_option_group": "certificate"},
            "message": "Diamonds above 0.30 ct require a certificate selection.",
            "sort": 0,
        },
        {
            "type": "exclusion",
            "scope": {},
            "condition": {
                "and": [
                    {"in": [{"var": "metal.shank"}, ["silver"]]},
                    {"in": [{"var": "metal.head"}, ["gold", "platinum"]]},
                ]
            },
            "effect": {"block": True},
            "message": "Silver cannot be combined with gold or platinum in the same ring.",
            "sort": 1,
        },
        {
            "type": "price_modifier",
            "scope": {"option_group": "engraving"},
            "condition": {"==": [{"var": "engraving.type"}, "special"]},
            "effect": {"surcharge_minor": 2500, "makes_non_returnable": True},
            "message": "Special engraving adds a surcharge and makes the item non-returnable.",
            "sort": 2,
        },
    ]
    for spec in rules:
        await _get_or_create(
            session,
            Rule,
            rule_set_id=rule_set.id,
            type=spec["type"],
            sort=spec["sort"],
            defaults={
                "scope": spec["scope"],
                "condition": spec["condition"],
                "effect": spec["effect"],
                "message": spec["message"],
            },
        )

    return template
