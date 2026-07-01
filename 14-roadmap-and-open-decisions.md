# 14 — Build Roadmap & Open Decisions

## Part A — Build order (do NOT start with the storefront)

The engine is the product. Build it inside-out so every later layer sits on a validated core. Each phase has an exit test; don't advance until it passes.

### Phase 0 — Foundation
- Repo, Docker Compose (Postgres, Redis, Meilisearch, object storage), CI, migrations, seed scripts.
- `tenants` + `tenant_settings` seeded with a single default tenant; `tenant_id` wired into the base repository/query layer.
- **Exit:** a request carries a tenant context end-to-end; migrations + seeds run clean.

### Phase 1 — Data model
- Implement Groups A–P from `05-data-model.md` (or at least A–L + N–O for MVP scope). UUID PKs, money as minor units, FKs, indexes.
- Seed metals/purities/colors/densities (values in `06`), **`material_options` (valid metal+purity+color combos)**, ring sizes, stone types/shapes, one category (`engagement-ring`). Seed `template_manufacturability` limits per template.
- **Exit:** you can persist a template with components, option groups/options, manufacturability limits, and a versioned rule-set by hand (SQL/fixtures); invalid metal combos are impossible to select because only `material_options` are offered.

### Phase 2 — Rules engine
- Safe JSON-logic evaluator (allow-listed operators). Implement the 5 rule types + `validate()` from `07`.
- **Exit:** validate() correctly returns purchasable/quote_only/invalid + reasons on a seeded template with real compatibility/exclusion/requirement/conditional rules. Unit tests green.

### Phase 3 — Pricing engine
- Weight estimation (volume×density×buffer×size-factor + overrides), metal/stone/labor/fees/buffers/margin/VAT, carat bands + magic-size, itemized breakdown, immutable snapshot with **full version-pinning** (template/formula/rule-set/density/labor/margin/vat versions + metal_price_snapshot_id + fx_rate_snapshot_id), "never NaN" contract, canonical purchasable/quote_only/invalid states.
- Metal-price + FX **cache read** first (hard-coded/manual values ok before Phase 4).
- **Exit:** the pricing test cases in `06` pass, including snapshot reproduction after a formula/margin change and the stale-feed→quote_only (estimated range) path.

### Phase 4 — Price sources & imports
- Metal-price adapter (GoldAPI first) + FX adapter (ECB) as background jobs → snapshots/caches; fallback chain.
- File/manual import framework (`supplier_import_jobs/rows`) with dry-run + mapping; diamond price tables + carat bands entry.
- **Exit:** live gold spot flows into a real price; a CSV import dry-runs, validates per row, and commits idempotently.

### Phase 5 — Admin app
- CRUD for templates/components/option groups/options/rules (with rule preview + publish), pricing config, suppliers/factories, media upload, SEO fields, imports UI.
- **Exit:** a non-developer builds a complete engagement-ring template with options + rules + pricing, no code, and sees a correct live breakdown.

### Phase 6 — Configurator + pricing API (headless)
- `/config/validate`, `/config/price`, `/config/share`, catalog read endpoints; Redis config sessions; `config_hash`.
- **Exit:** the FRD MVP acceptance criteria 1–3 pass against the API (curl/tests), < 300 ms p95.

### Phase 7 — Storefront (Next.js)
- Template listing + faceted filters, configurator UI (data-driven steps, disabled-with-reason, live price + breakdown, image-swap preview), size guide, engraving + returnability, save/share, i18n/currency, cart, deposit checkout via PSP.
- Server-rendered **SEO fundamentals ship here**: per-page title/meta/canonical, ProductGroup+Offer JSON-LD, hreflang, from the engine. (The systematic feed/sitemap/indexing layer is Phase 9 — but a page must never launch without its basic metadata + schema.)
- **Exit:** a visitor configures a ring, gets correct live price, and checks out with a deposit; page emits valid ProductGroup schema.

### Phase 8 — Orders, bespoke, production, compliance
- Order + snapshot locking; bespoke flow (range → design deposit → CAD/render → approval → prototype → production deposit → balance); production jobs + spec sheet + status lifecycle; hallmark gating; QC; **EU withdrawal function** (two-step + durable-medium acknowledgement) for withdrawal-eligible items.
- **Exit:** FRD MVP criteria 4–5 pass; a hallmark-required item can't ship without a hallmark record; an eligible order can be withdrawn via the two-step function and gets an acknowledgement.

### Phase 9 — SEO/GEO output + Merchant feed
- Build the **`indexable_configurations`** curated-variant set (stable sku/slug/canonical per commercial combo); sitemaps, indexing rules, canonical/hreflang, content/answer/FAQ blocks, priority landing pages.
- Merchant feed with correct **feed-not-schema** mapping: `availability` ∈ {in_stock,out_of_stock,preorder,backorder} (+`availability_date`), `identifier_exists=false` for GTIN-less rings; id==sku, item_group_id==productGroupID.
- **Exit:** FRD MVP criteria 6–7 pass; feed validates with no MadeToOrder/identifier disapprovals; configurator states are noindex, curated pages indexable.

### Phase 10 — AI Jewelry Designer
- `/ai/design-intent` (LLM structured output) → template match + price range + inspiration render → load into configurator or bespoke; human/CAD gate.
- **Exit:** a prompt yields a valid structured intent that preconfigures the configurator or opens a pre-filled bespoke request.

### Phase 11+ — Later (unblocked by design)
Interactive 3D (R3F/GLB, or iJewel3D/Threekit), live diamond feeds (Nivoda GraphQL → RapNet/IDEX/Polygon), ready-made catalog, AR try-on, additional ring types/categories, then **SaaS multi-tenant UI + billing + white-label domains**.

## Part B — Milestones (grouped)
- **M1 Engine core** = Phases 1–3 (data + rules + pricing). The real milestone; everything else is a client.
- **M2 Live + admin** = Phases 4–5 (real prices, admin builds templates).
- **M3 Configure + buy** = Phases 6–8 (headless config API, storefront, orders/bespoke/production/compliance).
- **M4 Found & discovered** = Phase 9 (SEO/GEO/feeds).
- **M5 Differentiators** = Phases 10–11 (AI designer, then 3D/feeds).
- **M6 Platform** = SaaS.

## Part C — MVP definition (restated, single source)
Engagement rings only. Admin-built templates + options + rules (no code). Instant correct live pricing (live gold spot, carat bands, never NaN) with itemized breakdown + immutable snapshot. CAD-volume weight + overrides. Manual/file supplier data, import-ready. Bespoke with deposits. AI + static previews (3D later). Orders → production → hallmark/QC → ship. SEO/GEO output (ProductGroup schema, feeds, hreflang, controlled indexing). Multi-language/currency. `tenant_id` everywhere, SaaS UI hidden.

---

## Part D — Open decisions (need your input — non-blocking)

These are the choices I made a sensible default on but you should confirm. Nothing here blocks starting Phase 0–1; most bite at the phase noted.

### Product / brand
1. **Brand name + `.com` domain.** `d-e.nl` is inadequate. Need the final name to seed tenant/brand config and URL structure. *(Needed by Phase 7; engine never hardcodes it.)*
2. **Launch template set.** I assumed solitaire, hidden-halo, halo, pavé, three-stone + a bespoke base (~6). Confirm the exact first 5–10. *(Phase 5.)*
3. **Positioning split.** Confirm the price bands you want to target (entry silver line vs core gold/platinum vs high-end bespoke) so margin rules can be seeded. *(Phase 3/5.)*

### Money / suppliers
4. **Design deposit amount.** I recommend **€250** (high-end signal, credited, non-refundable). Confirm, or set €150 for a softer entry. *(Phase 8.)*
5. **Production deposit %.** Default **50%** (70–75% when sourcing special/expensive stones). Confirm. *(Phase 8.)*
6. **PSP choice.** Default **Mollie** (NL/EU, iDEAL). Confirm vs Stripe/Adyen. *(Phase 7.)*
7. **First diamond feed.** Default **Nivoda GraphQL** first (then RapNet/IDEX/Polygon adapters). Confirm — and whether you already have (or will sign) the Nivoda Feed Agreement. *(Phase 11; abstractions built earlier.)*
8. **Carat threshold for feed vs price-table.** Default **> 0.30 ct** switches from admin price table to feed lookup. Confirm. *(Phase 4/11.)*
9. **20k (833) casting density.** Uncommon; I used an interpolation placeholder. **Get the real casting factor from your factory** and I'll set it authoritatively. *(Phase 1.)*
10. **Casting/waste factor + fabrication premium** per factory. Provide typical values (e.g. 2% waste, ×1.05 premium) or I keep defaults. *(Phase 3.)*

### Tech
11. **Backend language.** Default **Python + FastAPI** (pricing/rules/import fit). Confirm, or choose **Node/NestJS** if your team/Claude Code workflow is JS-first. *(Phase 0 — decide first.)*
12. **Buy vs build interactive 3D.** Default: **build later** on R3F/GLB, evaluate **iJewel3D** for diamond shaders vs **Threekit/Zakeke/Salsita** buy. Not needed for MVP. *(Phase 11.)*
13. **AI providers.** Confirm the image/render provider and the LLM for design-intent extraction (kept behind an adapter either way). *(Phase 10.)*
14. **Hosting.** Default Docker on Hetzner/DO + Cloudflare + Vercel-style storefront hosting. Confirm your preference (you already run Next.js/Vercel elsewhere). *(Phase 0.)*

### Compliance (confirm operationally, not code)
15. **Responsibility Mark registration.** You'll need a registered RM to sell NL-hallmarked goods, and a decision on **assay in NL (WaarborgHolland/EWN)** vs relying on a **recognised CCM/foreign mark** on imports. Flagged as an operational task; the engine models both. *(Before selling.)*
16. **VAT setup.** Confirm NL VAT handling and whether you'll register for **OSS** for EU cross-border B2C. Get a Dutch tax adviser to confirm rates/thresholds; the engine keeps VAT in data. *(Phase 8/9.)*

### Language rollout
17. **Locale launch order.** I have EN/NL as launch, then per your strategy: French, Turkish, Vietnamese, Hindi, Japanese; Tier 2 Indonesian, Arabic, Polish. Confirm the first 2–3 to actually ship copy for. *(Phase 7/9.)*

---

## Part E — How to hand this to Claude Code
1. Drop this whole folder in as the spec. Point it at `README.md` first.
2. Answer decision **#11 (backend)** and **#1 (brand)** before Phase 0; the rest can trail their phases.
3. Build strictly in phase order; enforce each phase's exit test before moving on.
4. Treat `06-pricing-engine.md` and `07-configurator-rules-engine.md` as the contracts — most bugs will hide there. Unit-test them first and hardest.
5. Keep the six non-negotiable principles (README) visible in the repo (e.g. `PRINCIPLES.md`) so no shortcut reintroduces SKU explosion, hardcoded rules, or a non-snapshotted price.

---

## Part F — Revision log (review pass v1.1)

Changes applied after a technical review, so the package is build-ready without mid-build reconciliation:

- **Scope tiers** — introduced `[CORE]`/`[LAUNCH]`/`[POST]`/`[SAAS]` mapped to build phases (SRS §Scope tiers). The AI Jewelry Designer and interactive 3D are now explicitly `[POST]`, not first-release.
- **Curated variants** — added `indexable_configurations` (data model Group N) as the stable source of SKUs/slugs/canonical URLs for SEO + feed; keeps the no-SKU-explosion rule intact.
- **Snapshot reproducibility** — `price_snapshots` now pins template/formula/rule-set/density/labor/margin/vat versions + `metal_price_snapshot_id` + `fx_rate_snapshot_id` (data model + `06` §5).
- **Validity states** — `purchasable`/`quote_only`/`invalid` defined canonically in `06` §6; `quote_only` returns an estimated range with exact-checkout disabled. `02`, `07`, `13` now defer to it.
- **Material modeling** — added `material_options` (valid metal+purity+color combos) so nonsense like silver+18k or platinum+rose can't be built by default; 20k/22k/silver kept but not default-recommended.
- **Manufacturability** — added `template_manufacturability` + `factory_manufacturability` (min thicknesses, tolerances, capability flags) enforced at validate/price time.
- **EU withdrawal button** — added the mandatory Art. 11a withdrawal function (in force 19 June 2026): compliance §3a, `withdrawal_requests` table, and `/withdrawals` endpoints. Bespoke/engraved remain exempt.
- **Merchant feed correctness** — `availability` mapped to Google's real values (never schema's `MadeToOrder`) + `availability_date`; `identifier_exists=false` for GTIN-less rings.
- **VAT/OSS** — €10,000 intra-EU threshold + OSS/IOSS fields made explicit.
- **Rule conflicts** — deterministic priority + a rule-simulator publish check added to `07`.
- **Competitor research** — added an epistemic-status split (observed / market claim / assumption) + a sources list.

Open decisions in Part D are unchanged and still non-blocking.

### Audit pass v1.2 (full re-verification)
External claims re-verified against primary sources: casting densities (18k 15.58, 14k 13.90 buffered, Pt950 20.76, 925 10.36 — match Stuller/bench references), Dutch hallmark thresholds (gold 1g / silver 8g / platinum 0.5g — confirmed by WaarborgHolland), and Dutch finenesses incl. 833 (20k). Internal defects found and fixed:
- Normalized `quote_only` spelling everywhere (was inconsistently hyphenated in `04`/`05`/`06`).
- `assay_office` enum now identical in `05` and `12` (added missing `ccm` to the data model).
- Moved `factory_manufacturability` from Group F (CAD) to Group I (Suppliers & factories); it replaces the redundant `factory_capabilities` key/value table — build one, not both.
- Restored ascending SRS numbering (016 before 017).
- Added pricing test case 9 (version-pin proof: historical order reproduces exactly after formula/margin/density changes; fresh config prices under new rules) — matches the Phase 3 exit.
- Added the hreflang value trap (`en-EU` is not a valid hreflang code; annotate `en` / `en-NL` etc.).
- Added Waarborgwet 2019 platinum nuance (Pt 900/850 marks exist; iridium no longer counts toward platinum fineness — get Pt-only content in writing from factories).
- Flagged 22k casting-factor spread (≈17.3–17.8) for factory confirmation alongside 20k.
