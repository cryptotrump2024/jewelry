"""Snapshot reproduction (docs/spec/06 §5, §9 cases 8–9).

A price snapshot is self-contained: this module rebuilds PricingInputs from a
snapshot dict and recomputes — the result must match the stored total
byte-for-byte, regardless of what formulas/margins/densities changed since.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.pricing.engine import PriceResult, compute_price
from app.pricing.inputs import (
    BufferInput,
    EngravingInput,
    FeeInput,
    FxInput,
    MarginInput,
    MetalPriceInput,
    PricingInputs,
    SideStoneInput,
    StonePricingInput,
    VatInput,
    VersionPins,
    WeightInput,
)


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def inputs_from_snapshot(snap: dict[str, Any]) -> PricingInputs:
    mp = snap["metal_prices"]
    w = snap["weight"]
    stone = snap.get("stone")
    fx = snap.get("fx_rate")
    fees = snap.get("fees", {})
    engraving = fees.get("engraving")
    margin = snap.get("margin_applied")
    vat = snap.get("vat_applied")
    versions = snap.get("versions", {})
    refs = snap.get("source_refs", {})

    return PricingInputs(
        currency=snap["currency"],
        metal_price=MetalPriceInput(
            price_per_gram=_dec(mp["price_per_gram"]),
            currency=mp["currency"],
            source=mp["source"],
            fetched_at=datetime.fromisoformat(mp["fetched_at"]),
        ),
        weight=WeightInput(
            cad_volume_mm3=_dec(w.get("cad_volume_mm3")),
            specific_gravity=_dec(w.get("specific_gravity")),
            casting_waste_factor=_dec(w["waste_factor"]),
            ring_size_weight_factor=_dec(w["size_factor"]),
            override_g=_dec(w.get("override_g")),
            fabrication_premium=_dec(w.get("fabrication_premium", "1.0")),
        ),
        stone=(
            StonePricingInput(
                stone_type=stone["type"],
                shape=stone["shape"],
                carat=_dec(stone["carat"]),
                color=stone.get("color"),
                clarity=stone.get("clarity"),
                price_per_carat=_dec(stone["price_per_carat"]),
                magic_size_multiplier=_dec(stone["magic_size_multiplier"]),
                supplier_id=stone.get("supplier_id"),
                cert=stone.get("cert"),
            )
            if stone
            else None
        ),
        side_stones=tuple(
            SideStoneInput(per_stone_minor=s["price_minor"], qty=s["qty"])
            for s in snap.get("side_stones", [])
        ),
        labor=tuple(
            FeeInput(kind=k, amount_minor=v) for k, v in snap.get("labor", {}).items()
        ),
        engraving=(
            EngravingInput(
                type=engraving["type"],
                base_cost_minor=engraving["base_cost_minor"],
                per_char_cost_minor=engraving["per_char_cost_minor"],
                char_count=engraving["char_count"],
                makes_non_returnable=engraving["makes_non_returnable"],
            )
            if engraving
            else None
        ),
        design_fee_minor=fees.get("design_minor"),
        prototype_fee_minor=fees.get("prototype_minor"),
        packaging_minor=fees.get("packaging_minor", 0),
        buffers=tuple(
            BufferInput(kind=b["kind"], type=b["type"], value=_dec(b["value"]))
            for b in snap.get("buffers", [])
        ),
        margin=(
            MarginInput(type=margin["type"], value=_dec(margin["value"])) if margin else None
        ),
        vat=(
            VatInput(
                market=vat["market"],
                rate=_dec(vat["rate"]),
                price_includes_vat=vat["inclusive"],
            )
            if vat
            else None
        ),
        fx=(
            FxInput(
                base=fx["base"],
                quote=fx["quote"],
                rate=_dec(fx["rate"]),
                source=fx["source"],
                fetched_at=datetime.fromisoformat(fx["fetched_at"]),
            )
            if fx
            else None
        ),
        rule_modifiers=tuple(snap.get("rule_modifiers", [])),
        versions=VersionPins(**versions) if versions else VersionPins(),
        metal_price_snapshot_id=refs.get("metal_price_snapshot_id"),
        fx_rate_snapshot_id=refs.get("fx_rate_snapshot_id"),
    )


def reproduce_price(snap: dict[str, Any]) -> PriceResult:
    """Recompute a price purely from its snapshot."""
    return compute_price(inputs_from_snapshot(snap))
