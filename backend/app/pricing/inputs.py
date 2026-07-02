"""Pricing-engine input structures (docs/spec/06).

The engine is pure: services resolve these from DB/caches and pass them in.
Every input that can be missing/stale is Optional + carries freshness — the
engine decides purchasable/quote_only/invalid, never the caller.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class MetalPriceInput:
    price_per_gram: Decimal
    currency: str
    source: str
    fetched_at: datetime
    is_stale: bool = False  # beyond refresh cadence but within cache_max_age
    is_too_stale: bool = False  # beyond cache_max_age — unusable
    snapshot_id: str | None = None  # metal_price_snapshots.id pin


@dataclass(frozen=True)
class WeightInput:
    cad_volume_mm3: Decimal | None
    specific_gravity: Decimal | None
    casting_waste_factor: Decimal = Decimal("0.02")
    ring_size_weight_factor: Decimal = Decimal("1.0")
    override_g: Decimal | None = None
    fabrication_premium: Decimal = Decimal("1.05")  # supplier alloy/fab surcharge


@dataclass(frozen=True)
class StonePricingInput:
    """Center stone, price-table mode (MVP)."""

    stone_type: str
    shape: str
    carat: Decimal
    color: str | None = None
    clarity: str | None = None
    price_per_carat: Decimal | None = None  # None = no table row → quote_only
    magic_size_multiplier: Decimal = Decimal("1.0")
    supplier_id: str | None = None
    cert: str | None = None


@dataclass(frozen=True)
class SideStoneInput:
    per_stone_minor: int
    qty: int


@dataclass(frozen=True)
class FeeInput:
    """A fixed-amount component (labor row, engraving, design fee...)."""

    kind: str
    amount_minor: int


@dataclass(frozen=True)
class EngravingInput:
    type: str  # standard|special
    base_cost_minor: int
    per_char_cost_minor: int
    char_count: int
    makes_non_returnable: bool


@dataclass(frozen=True)
class BufferInput:
    kind: str  # shipping|payment_fee|production_risk|warranty
    type: str  # percent|fixed
    value: Decimal  # percent as 0.02, fixed as minor units


@dataclass(frozen=True)
class MarginInput:
    type: str  # percent|fixed
    value: Decimal


@dataclass(frozen=True)
class VatInput:
    market: str
    rate: Decimal  # 0.21
    price_includes_vat: bool = True


@dataclass(frozen=True)
class FxInput:
    base: str
    quote: str
    rate: Decimal
    source: str
    fetched_at: datetime
    is_too_stale: bool = False
    snapshot_id: str | None = None  # fx_rates.id pin


@dataclass(frozen=True)
class VersionPins:
    """Every drifting input version (docs/spec/06 §5)."""

    template_version: int = 1
    price_formula_version: int = 1
    rule_set_version: int = 1
    density_source_version: int = 1
    labor_cost_version: int = 1
    margin_rule_version: int = 1
    vat_rule_version: int = 1


@dataclass(frozen=True)
class PricingInputs:
    currency: str
    metal_price: MetalPriceInput | None
    weight: WeightInput
    stone: StonePricingInput | None  # None = no center stone
    side_stones: tuple[SideStoneInput, ...] = ()
    labor: tuple[FeeInput, ...] = ()  # setting/casting/polishing/finishing
    engraving: EngravingInput | None = None
    design_fee_minor: int | None = None  # bespoke only
    prototype_fee_minor: int | None = None
    packaging_minor: int = 0
    buffers: tuple[BufferInput, ...] = ()
    margin: MarginInput | None = None
    vat: VatInput | None = None
    fx: FxInput | None = None  # None when pricing in base currency
    rule_modifiers: tuple[dict[str, Any], ...] = ()  # from the rules engine
    versions: VersionPins = field(default_factory=VersionPins)
    metal_price_snapshot_id: str | None = None
    fx_rate_snapshot_id: str | None = None
