# 01 — Market & Competitor Research

The competitive advantage in this category is **not** visual design. It is the configuration + pricing + supplier engine underneath. Every serious player wins or loses on the engine. Below is what the market exposes and what we should copy, avoid, or beat.

## 1. DiamondsByMe — engine teardown

DiamondsByMe is a made-to-order configurator, not a fixed catalog. Publicly observable engine behaviour:

| Area | Behaviour | Engine implication for us |
|---|---|---|
| Product template | Start from an existing model | Templates are the unit, not SKUs |
| Visual preview | Image changes as options change | Option → asset mapping table |
| Stone-first flow | Center stone chosen before metal | Configurator step order is data-driven |
| Stone size / quality | Adjustable; default mid-quality (e.g. SI/G), upgrades optional | Quality tiers as option groups w/ price deltas |
| Diamond database | Larger stones (≈>0.30 ct) draw on a diamond exchange/list | Threshold rule switches from price-table to feed lookup |
| Side stones | Conditional on the model | Conditional option groups per template |
| Metal + purity | Gold/platinum, multiple karats | Metal + purity option groups |
| Multi-metal rules | Some rings allow multiple metal elements (e.g. head vs shank) | Per-component metal assignment |
| Compatibility rules | Blocks silver+gold/platinum mixing, purity mixing | Exclusion rules engine |
| Engraving | Standard free, special extra; engraved = non-returnable | Add-on (not a variant); returnability flag |
| Ring size | Integrated step; affects metal weight | Size → weight adjustment factor |
| Pricing | Fluctuates with international precious-metal rates | Live metal spot in the price formula |
| Bespoke pipeline | Sketch/photo → consult → quote → 3D model/render (~8 business days) → optional gray plastic 3D print at exact size → production | Bespoke workflow with deposit + prototype step |
| Prototype | "Order 3D plastic replica" ≈ €15 | Prototype as a separately priced service |
| Categories | Rings, earrings, pendants, bracelets, cufflinks, accessories; "design your own" per category | One engine, many categories (we start rings) |
| Filters (listing) | Gemstone, stone shape, metal, carat weight | Faceted catalog from option data |

**Observed defect to learn from:** at least one product page showed an Express delivery price rendering as `+ NaN`. Lesson baked into our spec: **every computed price component must have validation, a fallback, and an audit snapshot.** A price must never render `NaN`; a missing input must degrade to a safe fallback and flag the config as non-purchasable rather than show garbage.

## 2. Competitor configurators (engine benchmarks)

- **StoneAlgo** — markets an AI + 3D engagement-ring builder: style, prongs, band, pavé, halo, hidden details; share design with jewelers; jewelers update the 3D with exact diamond dimensions. Signal: AI + 3D + supplier collaboration is now table stakes at the top.
- **Blue Nile — Creative Studio** — shape, setting, metal, shank, extras; 360° that updates in real time; **two-metal designs** (different metals for head vs shank). Signal: per-component metal is expected.
- **Brilliant Earth** — two paths: fully custom with a consultant, and "design it yourself" from curated styles. Custom flow: quote → concept → CAD → final creation → QA. Also virtual try-on (hand-photo upload, resize, shape/carat/metal changes, stacking, save/share). Signal: split "guided/custom" vs "self-serve"; try-on is a conversion lever.
- **VRAI** — lab-grown only, limited materials, custom pricing after consultation. A premium, controlled benchmark (less flexible than our vision, useful for tone).
- **The Art of Jewels** — "start with a lab diamond / fancy colored lab diamond / a setting" entry paths + 3D positioning. Signal: multiple entry points into the same engine.
- **GemFind RingBuilder** (B2B app) — ready-made ring builder with supplier integrations, markup management, cart integration; compatible with **IDEX, Polygon, RapNet/Rapaport, Nivoda**. Limitation: moissanite / other gemstones not supported. Pricing publicly ≈ **$295/mo** (RingBuilder), **$345/mo** with TryOn. Signal: this is roughly the SaaS price band and feature floor we'd later compete with.
- **Zakeke / Salsita / Threekit** — generic 3D configurator platforms: real-time 3D, manufacturing rules, production-ready files, AR, quick quotes, dynamic pricing (Zakeke); photorealistic jewelry models, engraving, AI assistant, live-camera try-on, instant pricing (Salsita); jewelry/watch 3D visualizer with metal/stone/engraving customization (Threekit). Signal: buy-vs-build reference points for the 3D layer.
- **iJewel3D** — jewelry-specialized 3D SDK built on three.js/threepipe: viewer + material configurator web component, diamond rendering modules, HDR editor, batch render app (BatchX). Signal: a specialized 3D toolkit exists if we don't want to build diamond shaders from scratch.

## 3. Where we can beat DiamondsByMe

1. **Rule-based pricing** instead of static price tables — add materials, gemstones, labor rules without code changes; live metal spot + FX; immutable snapshots.
2. **Fully data-driven configurator** — options and rules are admin data; the configurator adapts automatically; no per-model hardcoding.
3. **Per-component metal + richer rule model** — head/shank/accent metals, conditional side stones, "magic-size" carat pricing, certificate-required thresholds.
4. **AI Jewelry Designer** — prompt/image → structured design intent → template match + price range + render, with human/CAD validation before production. (See §5.)
5. **SEO/GEO as engine output** — structured `ProductGroup` data, Merchant feeds, hreflang, controlled indexing, GEO answer blocks — generated, not hand-built.
6. **Prototype workflow as a first-class, priced conversion step** — not a hidden add-on.
7. **Headless + multi-tenant** — a path to SaaS that DiamondsByMe (a single brand) doesn't obviously have.

## 4. Diamond data & supplier landscape (verified)

- **Nivoda** — public **GraphQL** API for verified customers (staging + production endpoints, GraphiQL explorer, code samples on GitHub: `github.com/Nivoda/nivoda-api`). ~1.6M natural + lab diamonds and colored gemstones. Also offers CSV/XML via FTP or download link. "Pro" tier allows placing orders/holds/requests via API. You request only the fields you need. This is the strongest first diamond feed for us.
- **Rapaport / RapNet** — Instant Inventory API; filtering, ring-builder use cases, carts, multi-language/currency; developer-built integration.
- **IDEX, Polygon** — additional B2B feeds; commonly supported by ring builders (per GemFind). Prepare importer abstractions for all four (Nivoda, RapNet, IDEX, Polygon) even though MVP starts with manual/price-table data.

## 5. AI jewelry design — current reality (2026)

The market clearly separates **concept** from **production**:

- Text/image → concept image: Midjourney, DALL·E, Fotor, **Tashvi AI** (jewelry-specific guided mode: asks stone shape, setting, metal, inspiration), Diatech Studio (photorealistic renders for client presentations).
- Text → 3D mesh (emerging, **not** production-grade): Tripo AI, Meshy.AI; research-stage depth-map → 2.5D pipelines (per GIA).
- Production CAD stays in **Rhino / MatrixGold / 3Design / ZBrush** with real tolerances.

Explicit industry consensus: **AI does not replace CAD for production.** Correct workflow = "design in AI until concept approved, then build production CAD." This validates our source-of-truth rule: AI generates *intent and inspiration*; structured config + human CAD produce the *buildable* artifact.

## 6. Deposit & pricing conventions (verified benchmarks)

- **Design/CAD fee:** commonly **$200–$750**, often **$250**, usually **credited toward the final purchase**. Example (Whiteflash): full payment on quote acceptance, refundable minus a $250 design fee before production; non-refundable once production begins.
- **Staged deposits (Gem Breakfast pattern):** ~$200 project deposit (credited) → **75% deposit** after stone/design approval → **final 25% before shipping**. Others use **50% to start production, 50% before shipment**.
- **Custom is not a separate high tier:** typical custom ring ≈ $3,000–$12,000; 2025 US average engagement ring ≈ $5,200–$5,500. Custom often equals or undercuts retail once markup/inventory are removed.
- **"Magic sizes":** crossing 1.00 / 1.50 / 2.00 ct spikes diamond price 15–25% (a 1.00 ct costs far more than a 0.95 ct). → the pricing engine must price carat in **non-linear bands**, not a linear per-carat rate.
- **Lab vs natural spread:** lab center stones are dramatically cheaper (e.g. ≈ $2,600 lab vs ≈ $6,700 natural for comparable look). → stone-type is a major price lever, surface it early in the flow.

Our recommended deposit model is specified in `10-workflows.md`.

## 7. Epistemic status & sources

This doc mixes three kinds of statement — treat them differently, especially for investor/legal use:
- **Observed** — behaviour visible on a live product or in official docs (e.g. Nivoda's GraphQL API and CSV/XML/FTP feed options; Google's ProductGroup support). Reliable.
- **Market claim** — figures/patterns reported by vendors or industry write-ups (deposit ranges, magic-size premiums, lab-vs-natural spreads, average ring prices). Directionally sound; verify exact numbers before quoting them externally.
- **Assumption / needs verification** — anything about a competitor's *internal* implementation (e.g. exactly which stone DB DiamondsByMe switches to, precise thresholds). Inferred from behaviour; confirm before relying on it.

Primary sources to cite/verify against (fetch live before external use):
- Nivoda API docs — `github.com/Nivoda/nivoda-api`; Nivoda site for feed/FTP options.
- Rapaport/RapNet Instant Inventory API; IDEX; Polygon — official developer pages.
- Google Merchant Center product data spec + ProductGroup structured-data docs (support.google.com/merchants; developers.google.com/search).
- GoldAPI.io / Metals.Dev / MetalpriceAPI docs for per-karat pricing; ECB euro reference rates.
- Competitor configurators (Blue Nile Creative Studio, Brilliant Earth, StoneAlgo, VRAI, GemFind RingBuilder, Zakeke/Salsita/Threekit, iJewel3D) — their own product/pricing pages.
- Deposit/pricing benchmarks (Whiteflash, Gem Breakfast, and jewelry-industry write-ups) — treat as market claims.

Where a claim above says "verified", it means checked against web sources during research, not audited to a primary contract — re-confirm anything load-bearing for a pitch or legal decision.
