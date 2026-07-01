"""Reference-data seeds for Phase 1 (docs/spec/14 Phase 1):

metals/purities/colors/densities (values from docs/spec/06 §2),
material_options (valid combos only), ring sizes, stone types/shapes/grades,
carat price bands, and the engagement-ring category.

Idempotent: every insert is keyed get-or-create.
"""

import math
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CaratPriceBand,
    Category,
    MaterialOption,
    Metal,
    MetalColor,
    MetalDensity,
    MetalPurity,
    RingSize,
    StoneQualityGrade,
    StoneShape,
    StoneType,
    Tenant,
)

DENSITY_SOURCE = "docs/spec/06-pricing-engine.md §2 (Stuller/bench casting factors)"

# (metal, karat, fineness, label, color -> SG). None color = colorless metal.
# 20k is an interpolation placeholder — open decision #9 (factory must confirm).
DENSITIES: list[tuple[str, int | None, int, str, str | None, Decimal]] = [
    ("gold", 14, 585, "14k", "yellow", Decimal("13.90")),
    ("gold", 14, 585, "14k", "white", Decimal("13.50")),
    ("gold", 14, 585, "14k", "rose", Decimal("13.60")),
    ("gold", 18, 750, "18k", "yellow", Decimal("15.58")),
    ("gold", 18, 750, "18k", "white", Decimal("15.45")),
    ("gold", 18, 750, "18k", "rose", Decimal("15.20")),
    ("gold", 20, 833, "20k", "yellow", Decimal("16.50")),  # placeholder — decision #9
    ("gold", 22, 916, "22k", "yellow", Decimal("17.80")),  # confirm spread 17.3–17.8
    ("platinum", None, 950, "Pt 950", None, Decimal("20.76")),
    ("silver", None, 925, "925", None, Decimal("10.36")),
]

METAL_NAMES = {"gold": "Gold", "platinum": "Platinum", "silver": "Sterling Silver"}
COLOR_LABELS = {"yellow": "Yellow", "white": "White", "rose": "Rose"}

# Combos recommended for engagement rings; high-karat gold is soft and silver
# is not a premium diamond-ring metal (kept active, not recommended).
RECOMMENDED = {("gold", 585), ("gold", 750), ("platinum", 950)}

STONE_TYPES = [
    ("natural_diamond", "Natural Diamond", True),
    ("lab_diamond", "Lab-Grown Diamond", True),
    ("sapphire", "Sapphire", False),  # schema-ready, not launched
    ("ruby", "Ruby", False),
    ("emerald", "Emerald", False),
]

STONE_SHAPES = [
    ("round", "Round"),
    ("oval", "Oval"),
    ("pear", "Pear"),
    ("princess", "Princess"),
    ("emerald", "Emerald"),
    ("cushion", "Cushion"),
    ("marquise", "Marquise"),
    ("asscher", "Asscher"),
    ("radiant", "Radiant"),
]

DIAMOND_GRADES = {
    "color": ["D", "E", "F", "G", "H", "I", "J", "K"],
    "clarity": ["FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "I1"],
    "cut": ["EX", "VG", "G"],
    "polish": ["EX", "VG", "G"],
    "symmetry": ["EX", "VG", "G"],
    "fluorescence": ["NON", "FNT", "MED", "STG"],
}

# Magic-size multipliers (docs/spec/06 §3: crossing 1.00/1.50/2.00 adds 15–25%).
# Admin-tunable defaults; decision #3/#10 may adjust.
CARAT_BANDS = [
    (Decimal("1.00"), Decimal("1.20")),
    (Decimal("1.50"), Decimal("1.20")),
    (Decimal("2.00"), Decimal("1.25")),
]

# EU ring sizes = inner circumference in mm.
EU_RING_SIZES = list(range(44, 63))


async def _get_or_create(session: AsyncSession, model, defaults: dict | None = None, **keys):
    row = (await session.execute(select(model).filter_by(**keys))).scalar_one_or_none()
    if row is None:
        row = model(**keys, **(defaults or {}))
        session.add(row)
        await session.flush()
    return row


async def seed_reference_data(session: AsyncSession, tenant: Tenant) -> None:
    tid = tenant.id

    # --- Metals, purities, colors, densities, material options ---
    metals: dict[str, Metal] = {}
    for key, name in METAL_NAMES.items():
        metals[key] = await _get_or_create(
            session, Metal, tenant_id=tid, key=key, defaults={"name": name}
        )

    gold_colors: dict[str, MetalColor] = {}
    for ckey, clabel in COLOR_LABELS.items():
        gold_colors[ckey] = await _get_or_create(
            session,
            MetalColor,
            metal_id=metals["gold"].id,
            key=ckey,
            defaults={"label": clabel},
        )

    for metal_key, karat, fineness, plabel, color_key, sg in DENSITIES:
        metal = metals[metal_key]
        purity = await _get_or_create(
            session,
            MetalPurity,
            metal_id=metal.id,
            fineness=fineness,
            defaults={"karat": karat, "label": plabel},
        )
        color = gold_colors[color_key] if color_key else None
        density = await _get_or_create(
            session,
            MetalDensity,
            metal_purity_id=purity.id,
            metal_color_id=color.id if color else None,
            defaults={"specific_gravity": sg, "source": DENSITY_SOURCE},
        )
        label = f"{plabel} {COLOR_LABELS[color_key]} {METAL_NAMES[metal_key]}" if color_key else (
            f"{METAL_NAMES[metal_key]} {plabel}"
        )
        await _get_or_create(
            session,
            MaterialOption,
            tenant_id=tid,
            metal_id=metal.id,
            purity_id=purity.id,
            color_id=color.id if color else None,
            defaults={
                "label": label,
                "fineness": fineness,
                "density_id": density.id,
                "is_active": True,
                "recommended_for_engagement_rings": (metal_key, fineness) in RECOMMENDED,
            },
        )

    # --- Category ---
    await _get_or_create(
        session,
        Category,
        tenant_id=tid,
        slug="engagement-ring",
        defaults={"name": "Engagement Rings", "type": "ring"},
    )

    # --- Ring sizes (EU standard: label == circumference mm) ---
    for size in EU_RING_SIZES:
        await _get_or_create(
            session,
            RingSize,
            tenant_id=tid,
            standard="EU",
            label=str(size),
            defaults={
                "circumference_mm": Decimal(size),
                "diameter_mm": Decimal(str(round(size / math.pi, 2))),
            },
        )

    # --- Stones ---
    stone_types: dict[str, StoneType] = {}
    for key, name, active in STONE_TYPES:
        stone_types[key] = await _get_or_create(
            session,
            StoneType,
            tenant_id=tid,
            key=key,
            defaults={"name": name, "is_active": active},
        )

    for key, name in STONE_SHAPES:
        await _get_or_create(
            session, StoneShape, tenant_id=tid, key=key, defaults={"name": name}
        )

    for diamond_key in ("natural_diamond", "lab_diamond"):
        st = stone_types[diamond_key]
        for attribute, codes in DIAMOND_GRADES.items():
            for sort, code in enumerate(codes):
                await _get_or_create(
                    session,
                    StoneQualityGrade,
                    stone_type_id=st.id,
                    attribute=attribute,
                    code=code,
                    defaults={"label": code, "sort": sort},
                )
        for threshold, multiplier in CARAT_BANDS:
            await _get_or_create(
                session,
                CaratPriceBand,
                tenant_id=tid,
                stone_type_id=st.id,
                carat_threshold=threshold,
                defaults={"multiplier": multiplier},
            )
