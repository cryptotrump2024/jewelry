# 00 — Project Overview

## 1. Vision

Build **two businesses on one platform**:

1. A premium international jewelry brand (B2C) — high-end bespoke plus affordable-luxury made-to-order and (later) ready-made jewelry.
2. A jewelry configuration platform (B2B SaaS) — the same engine, white-labeled for other jewelers, later.

The strategic consequence: the engine must be **headless from day one**. The storefront, the admin, the AI designer and the future factory portal are all clients of one API. This is the single most important architectural decision and it drives everything in these docs.

## 2. What the engine actually is

Not a webshop with a configurator plugin. It is a configuration + pricing + supplier + production + SEO engine. The public site is one presentation layer. Concretely the engine owns:

- Product **templates** (configurable ring models), not fixed SKUs.
- An **option + rule engine** deciding what's valid.
- A **pricing engine** computing live prices from metal spot, stones, labor, margin, VAT, FX.
- A **CAD weight engine** estimating metal weight from CAD volume × density.
- **Supplier/price import** for metals (live), diamonds/gemstones (feeds later), factory data (manual now).
- A **render/preview layer** (AI + static images now, interactive 3D later).
- **Workflow engines** for made-to-order, bespoke, prototype and production.
- **SEO/GEO output** — structured data, feeds, hreflang, sitemaps, indexing rules.
- A **tenant layer** for future SaaS.

## 3. The four product lines

| Line | Pricing | Fulfilment | Margin | Role | In MVP? |
|---|---|---|---|---|---|
| Ready-made | Fixed | Stock / factory / wholesaler | Lower | SEO traffic, gifts, entry price, trust | No (schema-ready) |
| Made-to-order | Live, configured | Manufactured after order | High | Core configurator product | **Yes** |
| Bespoke | Quote after design | CAD → render → (prototype) → production | Highest | Premium differentiator, deposit-gated | **Yes** |
| SaaS / white-label | Subscription + usage | N/A (platform) | Recurring | Long-term platform play | No (schema-ready) |

## 4. MVP definition (locked)

**MVP = engagement-ring configuration engine** with:

- Engagement rings only (5–10 templates to start; other ring types and categories later).
- Live instant pricing on every option change.
- CAD-volume weight estimation, with manual/factory weight override per template/supplier.
- Manual supplier/factory data entry now, import-ready for CSV/XML/API/GraphQL later.
- Deposit-based bespoke workflow.
- AI-rendered + static-angle previews first; real interactive 3D is a later phase.
- SEO/GEO-ready page + structured-data + feed generation from engine data.
- `ProductGroup` schema, Merchant Center feed support, hreflang/multi-currency-ready.
- SaaS-ready database foundation (tenant scoping present, UI hidden).

**MVP success test:** a customer configures an engagement ring and gets a correct live price instantly, and the resulting order carries a complete, immutable spec + price snapshot the factory can build from. If that works, the engine is real; if not, the storefront is decoration.

### Launch metals

| Metal | Fineness | Notes |
|---|---|---|
| 14k gold | 585 | yellow / white / rose |
| 18k gold | 750 | yellow / white / rose |
| 20k gold | 833 | recognized Dutch fineness |
| 22k gold | 916 | recognized Dutch fineness |
| Platinum 950 | 950 | |
| Sterling silver 925 | 925 | entry-price line |

Moissanite is intentionally excluded (positioning: quality; lab-grown diamond is the value-tier stone instead). Gemstones (sapphire, ruby, emerald) are schema-ready for later.

### Stones at launch

Natural diamond + lab-grown diamond. Diamond price starts as **admin-entered price tables** (per shape / carat band / color / clarity), designed to be swapped for live supplier feeds (Nivoda et al.) without schema change. Gemstones prepared but not launched.

## 5. Brand

- Level: high-end bespoke **and** affordable luxury (mixed, deliberately). Ready-made is the more mixed-marketplace tier later.
- Layout direction: light backgrounds, accent color for buttons/CTAs (reference aesthetic: buybloombuild.com). The engine is layout-agnostic; the storefront owns visual identity.
- Domain: current `d-e.nl` is not suitable for a premium international brand or SaaS. Target a short, globally pronounceable `.com` with luxury feel. Name TBD (see open decisions). The engine must not hardcode brand or domain anywhere — both are tenant/config values.

## 6. Supply reality (constraints that shape the build)

- Manufacturing via **multiple local factories in Asia** + wholesalers (especially for ready-made). No single ERP feed; data arrives manually (photos/WhatsApp/Excel). → import framework must accept anything, and manual admin entry is a first-class path, not a fallback.
- Factory weight data is inconsistent. → weight must be **estimated from CAD volume by default**, with a per-supplier/per-template manual override when a factory does provide real weights.
- Importing finished precious-metal jewelry into NL/EU triggers **hallmarking obligations** (see `12-compliance-hallmarking-tax.md`). This is an operational constraint, not an afterthought.

## 7. Out of scope for MVP (but must not be blocked)

Other ring types (wedding/eternity/signet/toi-et-moi), other categories (earrings/pendants/bracelets/necklaces), ready-made catalog, real interactive 3D, AR try-on, live diamond feeds, SaaS multi-tenant UI, in-house payments beyond a PSP. All of these are anticipated by the data model and architecture so they slot in without a rewrite.
