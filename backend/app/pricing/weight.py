"""CAD-volume weight estimation (docs/spec/06 §2).

    estimated_weight_g =
        (cad_volume_cm3 x specific_gravity x (1 + casting_waste_factor))
        x ring_size_weight_factor
    -- unless a manual/factory weight override exists, which wins outright.

Rhino/CAD reports mm³: cm3 = mm3 / 1000. Pure Decimal, no floats.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class WeightResult:
    weight_g: Decimal
    source: str  # override|estimated
    estimated_g: Decimal | None
    override_g: Decimal | None
    size_factor: Decimal
    waste_factor: Decimal


def estimate_weight_g(
    cad_volume_mm3: Decimal | None,
    specific_gravity: Decimal | None,
    casting_waste_factor: Decimal = Decimal("0.02"),
    ring_size_weight_factor: Decimal = Decimal("1.0"),
    override_g: Decimal | None = None,
) -> WeightResult | None:
    """Returns None when weight cannot be determined (missing volume/density

    and no override) — the caller must then degrade the config, never guess.
    """
    if override_g is not None:
        return WeightResult(
            weight_g=override_g,
            source="override",
            estimated_g=None,
            override_g=override_g,
            size_factor=ring_size_weight_factor,
            waste_factor=casting_waste_factor,
        )

    if cad_volume_mm3 is None or specific_gravity is None:
        return None
    if cad_volume_mm3 <= 0 or specific_gravity <= 0:
        return None

    volume_cm3 = cad_volume_mm3 / Decimal(1000)
    weight = (
        volume_cm3
        * specific_gravity
        * (Decimal(1) + casting_waste_factor)
        * ring_size_weight_factor
    ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return WeightResult(
        weight_g=weight,
        source="estimated",
        estimated_g=weight,
        override_g=None,
        size_factor=ring_size_weight_factor,
        waste_factor=casting_waste_factor,
    )
