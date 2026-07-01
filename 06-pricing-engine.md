# 06 — Pricing Engine (the heart)

If the price is right and instant, the engine is real. This module owns: weight estimation, metal/stone/labor costs, margin/VAT/FX, the "never NaN" guarantee, and the immutable snapshot.

## 1. Master formula

```
final_price =
    metal_cost
  + center_stone_cost
  + side_stone_cost
  + setting_labor
  + casting_labor
  + polishing_labor
  + finishing_labor
  + engraving_cost
  + design_fee            (bespoke only)
  + prototype_fee         (if selected)
  + packaging_cost
  + shipping_buffer
  + payment_fee_buffer
  + production_risk_buffer
  + warranty_allowance
  + margin                (percent or fixed, per template/market/band)
  ─────────────────────
  = pre_tax_subtotal
  + VAT / tax             (per market; price may be VAT-inclusive)
  = final_price
```

Every component is individually configurable and individually itemized in the response and snapshot. A component that cannot be computed does **not** silently become 0 — it flags the configuration (see §6).

## 2. Metal cost

```
estimated_weight_g =
    (cad_volume_cm3 × specific_gravity × (1 + casting_waste_factor)) × ring_size_weight_factor
    -- unless a manual/factory weight override exists, which wins outright

metal_cost = estimated_weight_g × price_per_gram(metal, karat, currency)
           × supplier_fabrication_premium
```

- `cad_volume_cm3` = Rhino/CAD volume; note Rhino reports **mm³**, so `cm3 = mm3 / 1000`.
- `casting_waste_factor` ≈ 0.01–0.05 (sprue/loss); configurable per factory. Many bench factors already bake in ~1–2%.
- `ring_size_weight_factor` from `template_size_weight_factors` (larger size → more metal).
- `price_per_gram` comes from the metal-price provider **already per karat** (see §7) — no manual purity math needed if using GoldAPI-style per-karat output.
- `supplier_fabrication_premium` = factory's alloy/fabrication surcharge (multiplier), configurable.

### Specific-gravity table (casting weight = volume × SG)
Use these as defaults in `metal_densities`; a factory override always wins. Values are industry casting-weight factors (SG relative to water; wax SG ≈ 0.98 ≈ 1, so wax-weight × SG ≈ casting weight).

| Metal / purity | Color | Specific gravity (g/cm³) |
|---|---|---|
| 24k gold (pure) | — | 19.32 |
| 22k gold (916) | yellow | 17.80 |
| 20k gold (833) | yellow | ~16.5 (interpolate; confirm with factory) |
| 18k gold (750) | yellow | 15.58 |
| 18k gold (750) | white | ~15.45 (alloy-dependent; Pd-white higher, Ni-white lower) |
| 18k gold (750) | rose | ~15.20 |
| 14k gold (585) | yellow | 13.90 (incl. small buffer) / ~13.0 raw |
| 14k gold (585) | white | 13.50 |
| 14k gold (585) | rose | 13.60 |
| Platinum 950 | — | 20.76 |
| Sterling silver 925 | — | 10.36 |
| Fine silver (999) | — | 10.49 |

Notes: white-gold density varies materially with alloy (palladium-white ≈ 16–17; nickel-white ≈ 14–15). **22k (916) casting factors also vary across bench references (≈17.3–17.8)** — confirm with your factory like 20k. Treat `metal_densities` as authoritative data, seeded from this table, overridable per supplier. **20k (833)** is uncommon — get the real casting factor from the factory and store it rather than trusting an interpolation for production.

### Worked example (metal only)
Oval solitaire, 18k yellow gold, CAD volume 380 mm³, size EU 54 factor 1.00, waste 2%, gold 18k spot €112.50/g, premium 1.05:
```
vol_cm3 = 380 / 1000 = 0.380
weight  = 0.380 × 15.58 × 1.02 × 1.00 = 6.038 g
metal   = 6.038 × 112.50 × 1.05 = €713.2
```

## 3. Stone cost

### Center stone (price-table mode, MVP)
```
base = price_per_carat(type, shape, carat_band, color, clarity) × carat
center_stone_cost = base × magic_size_multiplier(type, carat)
```
- `carat_band` from `diamond_price_tables` (ranges, not points).
- `magic_size_multiplier` from `carat_price_bands`: crossing 1.00/1.50/2.00 ct adds 15–25%. Diamond pricing is **non-linear** — never a flat €/ct across all sizes.
- Lab vs natural is a different price table entirely (lab ≈ ⅓–½ of natural for comparable look). Surface stone-type early; it's the biggest lever.

### Center stone (feed mode, LATER)
Above a configurable carat threshold (e.g. > 0.30 ct), resolve an actual `supplier_stones` row (Nivoda et al.) and use `supplier_price × (1 + supplier_markup)`. Persist the chosen stone (or its spec) on the order for the factory.

### Side stones
```
side_stone_cost = Σ (per_stone_price × qty)   -- from price table or melee cost per ct
```
Conditional: only when the template's side-stone group is active (rule-gated).

## 4. Labor, fees, buffers, margin, VAT
- **Labor** (`labor_costs`): setting (per stone), casting (per piece or per gram), polishing/finishing (per piece or per hour). Basis configurable; supplier-specific overrides allowed.
- **Setting cost** (`setting_costs`): per-stone by setting type (prong/pavé/bezel…).
- **Engraving** (`engraving_costs`): standard (often free) vs special (base + per-char); `makes_non_returnable = true` sets the item non-returnable.
- **Design fee** (`design_fees`): bespoke only; non-refundable but credited (see workflows).
- **Prototype fee** (`prototype_costs`): plastic STL print; may be credited above an order-value threshold.
- **Buffers** (`buffers`): shipping, payment-fee, production-risk, warranty — percent or fixed.
- **Margin** (`margins`): percent or fixed; resolvable per template/market/price-band (later per tenant).
- **VAT** (`vat_rules`): per market; `price_includes_vat` controls inclusive/exclusive display. NL standard VAT applies to jewelry; store rate + basis in the snapshot. See `12-compliance-hallmarking-tax.md`.

## 5. The immutable price snapshot (mandatory)
Written on every quote and every order item; self-contained and reproducible. Minimum fields:

```
price_snapshot {
  metal_prices:    { gold_18k_per_g, platinum_per_g, ... , source, fetched_at }
  fx_rate:         { base, quote, rate, source, fetched_at }
  weight:          { estimated_g, override_g?, source, size_factor, waste_factor }
  stone:           { type, shape, carat, color, clarity, price_per_carat|supplier_price,
                     magic_size_multiplier, supplier_id?, cert? }
  side_stones:     [ { price, qty } ]
  labor:           { setting, casting, polishing, finishing }
  fees:            { engraving, design?, prototype? }
  buffers:         { shipping, payment_fee, production_risk, warranty }
  margin_applied:  { type, value }
  vat_applied:     { market, rate, inclusive }
  discounts:       [ { code, amount } ]
  itemized:        { ...each component total... }
  total, currency
  versions:        { template_version, price_formula_version, rule_set_version,
                     density_source_version, labor_cost_version,
                     margin_rule_version, vat_rule_version }
  source_refs:     { metal_price_snapshot_id, fx_rate_snapshot_id }
  computed_at, computed_by[server]
}
```
Without snapshots, support and accounting are impossible once gold/FX/supplier prices move. **Pin every drifting input, not just the rule-set** — a later change to the formula, a density value, a labor rate, a margin or a VAT rule must not alter what an old order recomputes to. The `versions` + `source_refs` block guarantees byte-for-byte reproduction. The client-side price is advisory; checkout **re-computes authoritatively** and freezes this.

## 6. The "never NaN" contract (learned from DiamondsByMe `+ NaN`)
Every component computation is wrapped:
1. If all inputs are present and fresh → compute normally.
2. If an input is **stale** but within `cache_max_age` → use last-good cached value, mark `degraded: true`.
3. If an input is **missing/too stale** → do **not** output a number for that component. Set the configuration to `quote_only`, attach a human reason (e.g. "live gold price unavailable — request a quote"), and disable "add to cart".
4. Never render `NaN`, `null`, `0`, or a partial total as if it were the price.

A validity object always accompanies the price: `{ status: purchasable|quote_only|invalid, reasons: [...] , degraded: bool }`.

### The three validity states (canonical — same meaning everywhere)
This is the single source of truth; `02-srs.md`, `07`, and `13-api-specification.md` all defer to it.

| Status | Price returned | Checkout | When |
|---|---|---|---|
| **purchasable** | exact `total` | add-to-cart / pay **enabled** | all inputs present & fresh (or within cache max-age) |
| **quote_only** | an **estimated range** `{min,max}` where computable, else no total | exact checkout **disabled**; "request a quote" **enabled** | a valid config that can't be firm-priced now — stale/missing feed, feed-only stone unavailable, or inherently bespoke |
| **invalid** | **no** price | disabled | a rule blocks the combination or a required option is unmet; `reasons[]` says what to change |

So `quote_only` is **valid but not firmly priceable** — it may still show a range for orientation; it just can't be checked out at an exact price. It never emits `NaN`, `null`, or a fake `0` total.

## 7. Price sources & refresh

### Metals (recommended: GoldAPI.io)
GoldAPI.io returns **per-gram prices at each karat directly** (24/22/21/20/18/16/14/10k) plus spot, bid/ask, currency (EUR/USD/etc.), and timestamp — which removes manual purity math. Example response fields include `price_gram_24k … price_gram_10k`. Alternatives with equivalent capability: **Metals.Dev** (≤60s delay, LBMA/LME sources), **MetalpriceAPI**, **Metals-API** (carat endpoint is per-carat; convert ÷0.2 for per-gram-per-purity). Design `metal_price_sources` with a provider adapter + priority + fallback so you can switch/stack providers.

- **Silver 925 / platinum 950**: use XAG/XPT spot × fineness × per-gram, or provider per-purity where available.
- **20k/833**: if the provider lacks 20k, derive from 24k per-gram × (833/999) as a fallback, but prefer a factory-confirmed figure.
- **Refresh cadence**: intraday (e.g. every 5–15 min) into `metal_price_snapshots`; hot path reads cache only.
- **LBMA note**: LBMA benchmark data has licensing conditions for pricing/valuation use — don't ingest LBMA fixings directly for commercial pricing without checking terms; commercial APIs above are the practical route.

### FX (recommended: ECB)
ECB publishes official daily euro reference rates via an SDMX API (and CSV). Free and authoritative for **display/estimation**. Caveat: ECB explicitly says reference rates are informational, **not** transaction rates — so for the actual charged currency, the PSP's settlement rate governs; use ECB for shown prices and store the rate used in the snapshot. Cache daily; refresh on schedule.

### Stones
MVP: admin `diamond_price_tables` + `carat_price_bands`. LATER: Nivoda GraphQL feed → `supplier_stones` with markup; threshold switches center-stone pricing from table to feed lookup.

## 8. Performance
- Hot path never calls an external API; it reads Redis caches for metal spot + FX + resolved rule-set + density.
- Target < 300 ms p95 server compute; storefront shows optimistic price then reconciles.
- Cache `price_calculations` by `config_hash` (hash of template + selected options + market + source timestamps) for repeat requests; invalidate when any source timestamp changes.

## 9. Test cases (must pass)
1. Change 14k→18k→platinum: metal_cost scales by density×spot; total updates < 300 ms.
2. Cross 0.95→1.00 ct: center_stone_cost jumps by the configured magic-size multiplier, not linearly.
3. Lab vs natural toggle at same specs: uses different price table; large delta.
4. Gold feed stale > max-age: config becomes quote_only with reason; no NaN; add-to-cart disabled.
5. Manual factory weight override present: overrides volume estimate; snapshot records `override_g` and source.
6. Engraving "special": adds cost and sets `non_returnable = true`, surfaced pre-purchase.
7. Second market/currency: FX applied, VAT rule swapped, rounding correct; snapshot stores both rates.
8. Reproduce any historical order's price purely from its snapshot: byte-for-byte total match.
9. **Version-pin proof:** change the price formula, a margin rule, and a density value *after* an order exists → the historical order still reproduces its original total exactly (via its pinned versions + `metal_price_snapshot_id`/`fx_rate_snapshot_id`), while a fresh identical config prices under the new rules.
