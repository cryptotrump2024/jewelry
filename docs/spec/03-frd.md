# 03 — Functional Requirements Document (FRD)

How the system behaves, per module and per role. Cross-references SRS IDs from `02-srs.md`.

**Scope tiers:** the `[MVP]`/`[LATER]` tags below follow the tier vocabulary defined in `02-srs.md` (§Scope tiers): `[MVP]` = `[CORE]` or `[LAUNCH]` per the build phases in `14-roadmap-and-open-decisions.md`; `[LATER]` = `[POST]` or `[SAAS]`. Notably the full **AI Jewelry Designer (§9) and interactive 3D are `[POST]`**, not first-release, even though the modules are described here.

## 1. Admin — Catalog & templates
- Create/edit/clone ring **templates**; set name, style, category, status. `[MVP]`
- Define template **components** (shank, head, prongs, center stone, side stones, halo, gallery, engraving surface). `[MVP]`
- Attach **option groups** to a template and set step order + defaults. `[MVP]`
- Define **options** within groups (metals, purities, colors, finishes, stone types/shapes/quality tiers, ring sizes, engraving types). `[MVP]`
- Set which option combinations are indexable for SEO (see SEO module). `[MVP]`
- Upload static-angle images and AI renders per template/configuration; approve/replace. `[MVP]`
- Store CAD volume per template/component; set ring-size→weight factor; set manual weight override. `[MVP]`
- Add expert notes, FAQ blocks and content blocks per template/attribute. `[MVP]`

## 2. Admin — Rules
- Create **compatibility** rules (allow-lists per template/component). `[MVP]`
- Create **exclusion** rules (e.g. silver ✕ gold/platinum; incompatible purity mixing). `[MVP]`
- Create **requirement** rules (e.g. certificate required if carat > threshold; head type required for a given shape). `[MVP]`
- Create **conditional-visibility** rules (e.g. side-stone group visible only if template supports side stones). `[MVP]`
- Create **price-modifier** rules (surcharges/discounts by option, component, quantity, magic-size band). `[MVP]`
- Preview a rule's effect against sample configurations before publishing; rules are versioned. `[MVP]`

## 3. Admin — Pricing
- Configure the price **formula components** and their order (metal, center stone, side stones, setting/casting/polishing labor, engraving, design fee, prototype fee, packaging, shipping buffer, payment-fee buffer, margin, VAT). `[MVP]`
- Configure **labor/cost tables** (per component / per hour / per operation / per supplier). `[MVP]`
- Configure **margin** rules (global, per template, per price band, per market; later per tenant). `[MVP]/[LATER]`
- Configure **carat price bands** and magic-size multipliers. `[MVP]`
- Choose metal-price and FX **sources**; set refresh cadence, cache max-age and fallback behaviour. `[MVP]`
- Enter/upload **diamond & gemstone price tables**; later map supplier feeds + markup. `[MVP]/[LATER]`
- Inspect a live **price breakdown** for any configuration (each component itemized). `[MVP]`

## 4. Admin — Suppliers, factories & imports
- CRUD suppliers and factories; capabilities, lead times, min order, cost overrides, hallmark handling. `[MVP]`
- Manual product/stone entry. `[MVP]`
- Create an **import job**: pick source (manual/Excel/CSV/XML/FTP/API/GraphQL), map columns→fields, dry-run preview with per-row validation, then commit. `[MVP for file/manual; adapters for API/GraphQL LATER]`
- View import history, row-level errors, and re-run. `[MVP]`

## 5. Admin — Content, SEO & GEO
- Create SEO landing pages from templates/categories/attributes. `[MVP]`
- Edit SEO title/description/H1/slug per **language and market**. `[MVP]`
- Manage canonical rules, indexable flags, redirects, hreflang mappings. `[MVP]`
- Generate/preview sitemaps and Merchant Center feeds; preview JSON-LD before publish. `[MVP]`
- Manage FAQ/answer blocks, expert notes, internal-linking rules, topic clusters. `[MVP]`
- Manage country-specific shipping/returns/deposit/warranty policy content. `[MVP]`

## 6. Admin — Orders, production & finance
- View orders, statuses, snapshots, payments, deposits, refunds. `[MVP]`
- Assign production jobs to factories; generate/download spec sheets + CAD/render bundles. `[MVP]`
- Advance production status; require QC photos + hallmark record before "shipped". `[MVP]`
- View estimated-vs-actual weight deltas and price reconciliation. `[MVP]`

## 7. Customer configurator (storefront)
- Browse engagement-ring templates with faceted filters (style, stone type, shape, metal, carat, price). `[MVP]`
- Step through configuration in template-defined order; invalid options are disabled with reasons; required options enforced. `[MVP]`
- See **live price** update on every change, with an expandable breakdown. `[MVP]`
- See AI/static preview update per selection. `[MVP]`
- Choose ring size (with size guide); add engraving (see returnability warning). `[MVP]`
- Save, name, and **share** a configuration via URL (state encoded; not necessarily indexable). `[MVP]`
- Add to cart / request; pay deposit or full amount. `[MVP]`
- Switch language and currency; prices and policies reflect the market. `[MVP]`

## 8. Customer — Bespoke
- Free initial step: upload photo/sketch/reference or use AI Designer prompt → get a rough price **range** and an inspiration render. `[MVP]`
- Pay a **non-refundable design deposit** (credited to final) to start CAD. `[MVP]`
- Receive CAD/render; approve or request a revision (bounded rounds). `[MVP]`
- Optionally order a **plastic prototype** at exact size. `[MVP]`
- Pay production deposit → track production → pay balance → receive shipment. `[MVP]`

## 9. Customer — AI Jewelry Designer
- Enter a natural-language prompt (e.g. "modern white-gold oval lab-diamond ring with a hidden halo") and/or upload an inspiration image. `[MVP]`
- System returns: structured interpretation, matching template(s), price range, an inspiration render, and design notes. `[MVP]`
- One click to load the interpretation into the configurator (preconfigured) or into a bespoke request. `[MVP]`
- Human/CAD validation is required before any production. `[MVP]`

## 10. Factory / production portal
- View assigned jobs and priorities. `[MVP]`
- Download spec sheet, CAD/renders, engraving text, ring size, stone spec, hallmark requirement. `[MVP]`
- Upload production updates, QC photos, actual weight, hallmark record. `[MVP]`
- Mark status transitions; flag issues back to admin. `[MVP]`

## 11. System / scheduled
- Refresh metal spot prices on cadence; refresh FX daily (and on demand). `[MVP]`
- Sync supplier feeds on cadence; recompute affected caches. `[LATER for live feeds]`
- Regenerate sitemaps and Merchant feeds on content/price change or schedule. `[MVP]`
- Detect stale sources / anomalous price jumps and alert; auto-apply fallbacks. `[MVP]`
- Generate/queue renders for new configurations. `[MVP]`

## 12. Tenant admin `[LATER]`
- Manage tenant branding, domains, catalog subset, pricing/margin rules, suppliers, languages, currencies, and billing.
- All behaviour above becomes tenant-scoped; nothing in MVP may assume a single tenant.

## 13. Acceptance criteria (MVP exit)
1. Admin builds an engagement-ring template with options + rules, no code. ✅
2. Visitor configures it; invalid combos are blocked with reasons; a correct **live price** shows instantly with a breakdown. ✅
3. Changing metal/karat/stone/carat/size updates price using **live gold spot** and **carat bands**; no `NaN`, ever. ✅
4. A bespoke request flows: upload/prompt → range → design deposit → CAD/render → approve → prototype (optional) → production deposit → status → balance → ship. ✅
5. Each order carries an **immutable snapshot** and a factory-ready spec (config + CAD/render + engraving + size + stone + hallmark flag). ✅
6. The template page emits valid `ProductGroup`+`Product`+`Offer` JSON-LD and appears in a generated sitemap + Merchant feed; non-indexable configurator states are excluded. ✅
7. The same template renders in a second language/currency with localized slug/metadata and correct VAT/policies. ✅
