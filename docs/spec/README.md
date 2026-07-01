# Jewelry Configuration Engine — Technical Blueprint

Engine-first technical documentation for a headless jewelry configuration, pricing, 3D, supplier and production platform. The storefront is one client of the engine; the same core later powers a white-label SaaS.

**MVP product scope:** engagement rings only. **Positioning:** high-end bespoke + affordable luxury. **Markets:** Netherlands → Europe → worldwide.

## How to use these docs

Feed this whole folder into Claude Code as the working spec. Build in the order given in `14-roadmap-and-open-decisions.md`. Do not start with the storefront. The build sequence is: data model → rules engine → pricing engine → supplier/price imports → admin → configurator API → storefront → 3D → AI designer → SaaS.

Every doc is written so a developer (or an agent) can implement directly from it. Where a technical value matters (metal density, API endpoint, schema property, legal threshold) the concrete value is in the doc rather than a vague "TBD". A small number of **business** decisions are genuinely still open (brand name and domain, backend language, deposit amounts, first diamond feed, etc.) — these are listed explicitly in `14-roadmap-and-open-decisions.md` Part D with a sensible default for each, and none of them block starting the build.

## Index

| File | What it covers |
|---|---|
| `00-project-overview.md` | Vision, business model, four product lines, MVP definition, brand |
| `01-competitor-research.md` | DiamondsByMe teardown, competitor configurators, engine benchmarks |
| `02-srs.md` | Software Requirements Specification (numbered, testable) |
| `03-frd.md` | Functional Requirements Document (per module, per role) |
| `04-architecture.md` | Headless architecture, module map, tech stack, multi-tenancy, deployment |
| `05-data-model.md` | Database design — all table groups, columns, relationships, keys |
| `06-pricing-engine.md` | The heart. Formulas, densities, price sources, snapshots, worked examples |
| `07-configurator-rules-engine.md` | Templates, options, rules, compatibility, config sessions |
| `08-3d-and-ai-designer.md` | 3D pipeline, render engine, AI Jewelry Designer, source-of-truth separation |
| `09-integrations-and-suppliers.md` | Nivoda, metal-price APIs, FX, supplier import framework |
| `10-workflows.md` | Ready-made, made-to-order, bespoke, prototype, production, deposits |
| `11-seo-geo-engine.md` | Structured data, Merchant feed, hreflang, indexing rules, GEO content |
| `12-compliance-hallmarking-tax.md` | Dutch/EU hallmarking, VAT/OSS, returns, GDPR |
| `13-api-specification.md` | Engine API surface (REST + GraphQL), key endpoints, payloads |
| `14-roadmap-and-open-decisions.md` | Build phases, milestones, and decisions still needed from you |

## Non-negotiable design principles

1. **The engine is the source of truth, not the AI image.** Price and order spec derive from structured configuration data. AI/rendered images are for inspiration and conversion only.
2. **Rules over hardcoding.** Which metals, stones, shapes, sizes and settings are valid is admin-defined data, not code.
3. **No SKU explosion.** Store templates + options + rules. Generate configurations on demand. Never persist millions of variant rows.
4. **Every quote/order stores an immutable price snapshot.** Gold spot, FX rate, supplier stone price, margin rule, VAT rule, timestamp — all frozen at purchase.
5. **`tenant_id` on every business table from day one.** SaaS is hidden in the MVP UI but never blocked by the schema.
6. **SEO/GEO is engine output, not a frontend afterthought.** Structured data, feeds, hreflang and indexing rules come from the same source of truth.

## Glossary

- **Template** — a configurable ring model (e.g. "Oval Solitaire"). The `ProductGroup` in schema terms.
- **Configuration** — one valid set of chosen options against a template. A `Product` variant in schema terms.
- **Option group** — a dimension of choice (metal, stone shape, carat…).
- **Rule** — a data-defined constraint (compatibility, requirement, exclusion, price modifier).
- **Snapshot** — frozen pricing inputs stored on a quote/order.
- **GEO** — dual meaning: Generative Engine Optimization (AI answers) *and* Geographic optimization (markets/locales). Both are designed in.
- **Bespoke** — customer-uploaded idea → CAD → render → approval → production. Deposit-gated.
- **Made-to-order** — configured from a template, manufactured after purchase.
