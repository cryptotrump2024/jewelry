# 02 — Software Requirements Specification (SRS)

Version 1.1 · MVP = engagement rings. Requirements are numbered and testable.

### Scope tiers (read this before building)
"MVP" was too coarse and made the first release look enormous. Requirements are tiered, and the tiers map directly to the build phases in `14-roadmap-and-open-decisions.md`:

| Tier | Meaning | Roadmap phases |
|---|---|---|
| **[CORE]** | The engine itself — build first | Phases 1–4 (data model, rules, pricing, price sources/imports) |
| **[LAUNCH]** | Needed to actually sell — build second | Phases 5–9 (admin, config API, storefront, orders/bespoke/production/compliance, SEO/feeds) |
| **[POST]** | Differentiators after launch | Phases 10–11 (full AI Designer, interactive 3D, live diamond feeds, ready-made) |
| **[SAAS]** | White-label multi-tenant product | after M5 |

Legacy note: items still tagged `[MVP]` below mean CORE **or** LAUNCH per the phase map; `[LATER]` means POST **or** SAAS. Where it matters, the sharper tier is given. **Design for every tier now; build in tier order.** In particular: AI renders/static previews are `[LAUNCH]`, but the full conversational **AI Jewelry Designer is `[POST]`**; interactive 3D and live diamond feeds are `[POST]`; the SaaS UI is `[SAAS]`.

## 1. Purpose & scope

Specify the headless jewelry configuration engine and its MVP storefront/admin. The engine computes valid configurations and live prices for engagement rings, manages bespoke/production workflows, and emits SEO/GEO data. Non-MVP categories, ready-made catalog, live diamond feeds, interactive 3D and SaaS UI are anticipated but out of MVP scope.

## 2. Actors / roles

| Role | Description |
|---|---|
| Visitor | Anonymous shopper; can configure and get live prices, save/share configs |
| Customer | Registered; places orders, pays deposits, tracks orders, uploads bespoke refs |
| Admin/Editor | Manages templates, options, rules, pricing, content, SEO |
| Merchandiser | Manages catalog, imports, supplier/factory records, indexing choices |
| Factory/Production | Views jobs, downloads specs/CAD, updates status, uploads QC/hallmark |
| Finance | Views snapshots, refunds, tax config |
| Tenant Admin `[LATER]` | Manages a white-label tenant's branding, catalog, pricing, domains |
| System | Scheduled jobs: price refresh, FX refresh, feed sync, sitemap/feed generation |

## 3. Product template & catalog

- **SRS-001 [MVP]** Support ring **templates** with configurable components.
- **SRS-002 [MVP]** Components may include shank, head, prongs, center stone, side stones, halo, gallery, engraving surface, optional prototype.
- **SRS-003 [MVP]** Each template defines allowed **option groups** and their step order.
- **SRS-004 [MVP]** Admin can activate/deactivate options and templates without code changes.
- **SRS-005 [LATER]** Support additional ring types and non-ring categories via the same template model.
- **SRS-006 [MVP]** Each template carries SEO fields (see §12) and CAD/asset references (see §9–10).

## 4. Rules & configuration validation

- **SRS-010 [MVP]** Validate every option combination before a price is shown.
- **SRS-011 [CORE]** Prevent invalid metal combinations by default via the normalized `material_options` table (only valid metal+purity+color combos are offered), with exclusion rules for template-specific edge cases (e.g. no silver-with-gold/platinum in one piece).
- **SRS-012 [CORE]** Support rules scoped per template, metal, purity, stone type, shape, carat, ring size, component and supplier.
- **SRS-013 [CORE]** Support required options and default selections per template.
- **SRS-014 [CORE]** Support conditional options (e.g. side stones only when the template supports them; certificate required when carat > threshold).
- **SRS-015 [CORE]** A configuration is in exactly one of `purchasable` / `quote_only` / `invalid`, defined canonically in `06-pricing-engine.md` §6. `purchasable` returns an exact price; `quote_only` may return an estimated range but disables exact checkout; `invalid` returns actionable reasons and no price.
- **SRS-016 [CORE]** Rules are versioned; a stored quote/order references the rule-set version used (plus the other pinned versions per the snapshot spec in `06`).
- **SRS-017 [CORE]** Enforce **manufacturability limits** (min band/wall/prong thickness, stone-seat tolerance, stone size range, factory capability) at validate/price time; a config that violates them is `invalid` or `quote_only` (flagged for manual CAD check), never silently sold.

## 5. Pricing engine

- **SRS-020 [MVP]** Compute a live price **instantly** (< 300 ms server compute target) after any option change.
- **SRS-021 [MVP]** Compute metal cost from estimated weight (CAD-volume × density) or a manual weight override.
- **SRS-022 [MVP]** Compute diamond/gemstone cost from admin price tables now; from supplier feeds later — without schema change.
- **SRS-023 [MVP]** Price carat in **non-linear bands** with configurable "magic-size" multipliers (1.00/1.50/2.00 ct etc.).
- **SRS-024 [MVP]** Apply labor, setting, casting, polishing, engraving, prototype, design, packaging, shipping-buffer, payment-fee-buffer, margin, and VAT/tax components (each individually configurable).
- **SRS-025 [MVP]** Support live metal spot prices from an external provider, with per-metal-per-karat resolution.
- **SRS-026 [MVP]** Support currency conversion (FX) with a configurable source and cache.
- **SRS-027 [MVP]** Store an **immutable price snapshot** for every quote and order (all inputs + sources + rates + timestamp). See §5 of `06-pricing-engine.md` for the required snapshot fields.
- **SRS-028 [CORE]** Provide **fallback pricing** if any external feed is stale/unavailable: use last-good cached value within a configurable max-age; beyond that, set the config to `quote_only` (estimated range where computable, exact checkout disabled) and never render `NaN`, `0`, or a wrong price. The three validity states (`purchasable` / `quote_only` / `invalid`) are defined canonically in `06-pricing-engine.md` §6.
- **SRS-029 [MVP]** Never display a price component that failed to compute; a failed component invalidates purchasability with a clear reason (learned from the DiamondsByMe `+ NaN` defect).
- **SRS-030 [LATER]** Support tenant-specific pricing rules, markups and margin policies.

## 6. CAD / weight engine

- **SRS-035 [MVP]** Store CAD volume (mm³) per template and per component.
- **SRS-036 [MVP]** Estimate metal weight = volume(cm³) × metal specific-gravity × (1 + casting/waste buffer).
- **SRS-037 [MVP]** Adjust estimated weight by ring size using a per-template size→weight factor.
- **SRS-038 [MVP]** Allow supplier/factory/manual weight override at template, component or supplier level; override wins over estimate.
- **SRS-039 [MVP]** Track estimated vs actual production weight and expose the delta for reconciliation.

## 7. Stones

- **SRS-045 [MVP]** Support natural and lab-grown diamonds with shape, carat, color, clarity, cut, polish, symmetry, fluorescence, certificate lab/number, measurements, ratio.
- **SRS-046 [MVP]** Support admin-entered price tables keyed by (type, shape, carat band, color, clarity).
- **SRS-047 [MVP]** Switch to a supplier lookup above a configurable carat threshold (e.g. > 0.30 ct) when a feed is connected.
- **SRS-048 [LATER]** Support gemstones (sapphire, ruby, emerald, …) via the same stone model and price tables.
- **SRS-049 [MVP]** Persist the specific stone (or stone spec) chosen on a configuration/order for the factory spec sheet.

## 8. Rendering & AI designer

- **SRS-055 [LAUNCH]** Generate/serve **AI-rendered** and **static-angle** previews per configuration; images are inspiration/conversion assets, never the pricing/spec source of truth.
- **SRS-056 [CORE]** Clearly separate customer-facing preview from internal production CAD.
- **SRS-057 [LAUNCH]** Store generated previews per configuration/session; allow admin approval/replacement.
- **SRS-058 [POST]** **AI Jewelry Designer:** accept a text prompt and/or reference image and produce a **structured design intent** (product type, style, metal, stone type/shape/carat, detail tags, optional budget). *(Not in the first launch — needs the catalog/rules/pricing core stable first.)*
- **SRS-059 [POST]** Map design intent to matching templates + supplier stones, return a price range, and generate an inspiration render; require human/CAD validation before production.
- **SRS-060 [POST]** Real interactive 3D configurator (rotate/zoom, live material/stone swaps, live price), and AR try-on.

## 9. Suppliers, factories & imports

- **SRS-065 [MVP]** Manage supplier and factory records with capabilities, lead times, and cost overrides.
- **SRS-066 [MVP]** Manual admin entry is a first-class data path.
- **SRS-067 [MVP]** Import framework must support (now or via adapters): manual, Excel, CSV, XML, FTP, JSON API, GraphQL.
- **SRS-068 [MVP]** Every import runs as a job with per-row validation, dry-run preview, and mapping to internal fields.
- **SRS-069 [LATER]** Live diamond feeds (Nivoda GraphQL first; RapNet/IDEX/Polygon adapters) with per-supplier markup/filter rules.

## 10. Orders, deposits & payments

- **SRS-075 [MVP]** Support made-to-order and bespoke order types (ready-made `[LATER]`).
- **SRS-076 [MVP]** Lock a price snapshot at order/quote acceptance.
- **SRS-077 [MVP]** Support deposits: non-refundable design deposit (credited), production deposit, balance-before-shipment; each configurable.
- **SRS-078 [MVP]** Integrate a PSP (e.g. Mollie/Stripe/Adyen) for deposits and balances; store payment references, never raw card data.
- **SRS-079 [MVP]** Enforce returnability rules (e.g. engraved/bespoke = non-returnable) and surface them pre-purchase.
- **SRS-080 [MVP]** Support order status lifecycle and customer-visible tracking.

## 11. Production & QC

- **SRS-085 [MVP]** Create factory production jobs from orders with full spec (config, CAD/render refs, engraving, ring size, stone spec, hallmark requirement).
- **SRS-086 [MVP]** Track statuses: pending → CAD → awaiting approval → casting → stone-setting → polishing → hallmarking → QC → shipped.
- **SRS-087 [MVP]** Assign jobs to a factory; store QC photos and notes.
- **SRS-088 [MVP]** Capture hallmark records (required flag, fineness, responsibility mark, assay office, status) — see §12.

## 12. SEO / GEO

- **SRS-090 [MVP]** Generate SEO-ready product, category and landing pages from engine data.
- **SRS-091 [MVP]** Emit `ProductGroup` structured data for templates and `Product`/`Offer` for indexable variants; `productGroupID` must match the Merchant feed `item_group_id`.
- **SRS-092 [MVP]** Generate canonical URLs for indexable pages; **prevent low-value configurator states from being indexed** (indexing rules; see `11-seo-geo-engine.md`).
- **SRS-093 [MVP]** Generate XML sitemaps (pages, localized, images, products).
- **SRS-094 [MVP]** Support hreflang groups for multilingual/multi-regional pages.
- **SRS-095 [MVP]** Generate Google Merchant Center-compatible product feeds.
- **SRS-096 [MVP]** Store SEO metadata per template/category/market/locale; store image alt/caption/filename metadata.
- **SRS-097 [MVP]** Support FAQ/answer/content blocks connected to product attributes and buyer questions (for AI-search/GEO).
- **SRS-098 [MVP]** Support internal-linking rules across styles, metals, shapes, guides and configurator entry points.
- **SRS-099 [MVP]** Store business-policy data (shipping, returns, warranty, production time, hallmarking, deposits) for structured output.

## 13. Localization & currency

- **SRS-105 [MVP]** Support multiple currencies with market-specific display and rounding.
- **SRS-106 [MVP]** Support multiple languages with **native-tone** translation overrides (not machine-literal); localized slugs and metadata.
- **SRS-107 [MVP]** Store market-specific VAT/tax, shipping and return-policy settings.

## 14. Compliance

- **SRS-110 [MVP]** Encode Dutch/EU hallmarking thresholds and mark requirements; flag each order item's hallmark obligation from its metal + estimated weight (see `12-compliance-hallmarking-tax.md`).
- **SRS-111 [MVP]** Support EU VAT handling incl. cross-border/OSS-relevant fields; store tax basis in the snapshot.
- **SRS-112 [MVP]** GDPR: consent records, data export/erasure, minimal PII, no raw card storage.

## 15. Multi-tenancy (SaaS-ready)

- **SRS-115 [MVP]** Include `tenant_id` on all core business tables from day one.
- **SRS-116 [LATER]** Tenant-specific branding, catalog, pricing, suppliers, languages, domains and billing.
- **SRS-117 [MVP]** MVP UI may hide tenancy, but no query or constraint may assume a single tenant.

## 16. Non-functional requirements

- **NFR-1 Performance** — live price compute < 300 ms server-side (p95); configurator interaction < 100 ms perceived via optimistic UI; storefront LCP < 2.5 s.
- **NFR-2 Availability** — engine 99.9%; degrade gracefully when a price/FX/feed source is down (fallbacks per SRS-028).
- **NFR-3 Scalability** — stateless API, horizontally scalable; no SKU-explosion writes; heavy work (renders, imports, feeds) on a queue.
- **NFR-4 Consistency & audit** — every price is reproducible from its snapshot; imports and price/FX refreshes are logged.
- **NFR-5 Security** — role-based access; signed asset URLs; PSP tokenization; secrets in a vault; per-tenant data isolation.
- **NFR-6 Observability** — structured logs, metrics, alerting on stale feeds/failed jobs/price anomalies.
- **NFR-7 Internationalization** — full i18n/l10n; all customer-facing strings translatable; currency/locale correct per market.
- **NFR-8 Accessibility** — storefront WCAG 2.2 AA.
- **NFR-9 Maintainability** — engine logic (rules, pricing) is data/config-driven and unit-tested; adding a metal/stone/rule needs no deploy.
