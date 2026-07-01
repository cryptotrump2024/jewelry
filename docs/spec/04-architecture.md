# 04 — System Architecture

## 1. Shape: headless, modular, multi-tenant-ready

One **engine** (API + services + DB) with multiple clients: storefront, admin, AI designer, factory portal, and future white-label tenants. No business logic lives in the frontend. Pricing, rules, weight, SEO output and workflows are all engine-side and API-exposed.

```
                       ┌───────────────────────────────────────────────┐
   Clients             │                 ENGINE (headless)             │
 ┌──────────┐   HTTPS  │  API Gateway  (REST + GraphQL, authN/authZ)   │
 │ Storefront│────────▶│                                               │
 │ (Next.js) │         │  ┌───────────── Core Services ─────────────┐  │
 └──────────┘         │  │ Template/Catalog   Rules Engine          │  │
 ┌──────────┐         │  │ Configuration      Pricing Engine        │  │
 │  Admin   │────────▶│  │ CAD/Weight         Stone Service         │  │
 │ (Next.js)│         │  │ Render/AI Designer Supplier/Import       │  │
 └──────────┘         │  │ Orders/Deposits    Production/QC         │  │
 ┌──────────┐         │  │ SEO/GEO/Feeds      Localization/Currency │  │
 │ Factory  │────────▶│  │ Tenancy            Media/Assets          │  │
 │  portal  │         │  └──────────────────────────────────────────┘  │
 └──────────┘         │        │            │             │            │
 ┌──────────┐         │   PostgreSQL     Redis/Queue    Search (Meili) │
 │ AI design│────────▶│   (source of     (cache, jobs)  Object store   │
 │   UI     │         │    truth)                        (S3-compat)   │
 └──────────┘         └───────────────────────────────────────────────┘
                              │            │             │
                External:  Metal-price   FX (ECB)   Diamond feeds (Nivoda…)
                           API           PSP (Mollie/Stripe)  Render/AI providers
```

## 2. Recommended tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python + FastAPI** | Pricing/rules/import logic is Python-friendly; fast, typed, async. (Node/NestJS is an acceptable alternative if the team is JS-first.) |
| DB | **PostgreSQL** | Relational integrity for rules/pricing/orders; JSONB for flexible option payloads; strong constraints. |
| Cache / queue | **Redis** + a task runner (RQ/Celery/Arq) | Price/FX caches, config sessions, background renders/imports/feeds. |
| Search | **Meilisearch** (OpenSearch later) | Fast faceted catalog search; simple ops for MVP. |
| Storefront | **Next.js (App Router)** | SSR/SSG for SEO/GEO; ISR for template/landing pages; i18n routing. |
| Admin | **Next.js/React** admin app | Same stack; shared types. |
| 3D (later) | **Three.js / React Three Fiber**, glTF/GLB assets | Web-standard, PBR materials; optional iJewel3D SDK for diamond shaders. |
| AI | Image/render provider + an LLM for design-intent extraction | Concept only; human/CAD before production. |
| Object storage | **S3-compatible** | CAD/renders/images/feeds; signed URLs. |
| Payments | **Mollie** (strong NL/EU, iDEAL) or Stripe/Adyen | Deposits + balances; tokenized, no raw card data. |
| Infra | **Docker**, Cloudflare (CDN/WAF), Hetzner/DigitalOcean/AWS | Cost-flexible; CDN for assets + edge caching. |

## 3. Module responsibilities

- **Template/Catalog** — templates, components, option groups/options, categories, media links, SEO fields.
- **Rules Engine** — evaluate compatibility/exclusion/requirement/conditional/price-modifier rules against a configuration; return validity + reasons + applicable modifiers. Versioned.
- **Configuration** — hold a config session (selected options), call Rules + Pricing, return state + price + preview refs. Stateless per request; session in Redis; sharable via encoded state.
- **Pricing Engine** — the formula runner (see `06-pricing-engine.md`). Pulls metal spot, FX, stone price, weight, labor, rules → itemized price + snapshot. Owns fallbacks and the "never NaN" guarantee.
- **CAD/Weight** — volume→weight estimation, size factor, overrides, est-vs-actual tracking.
- **Stone** — stone specs, price tables, feed lookup abstraction, carat-band logic.
- **Render/AI Designer** — request/store renders; extract structured design intent from prompt/image; match templates/stones; return range + render.
- **Supplier/Import** — supplier/factory records; import jobs (manual/file/API adapters); markup/filter rules.
- **Orders/Deposits** — cart/quote/order lifecycle, deposits, PSP integration, returnability, snapshot locking.
- **Production/QC** — jobs, statuses, spec-sheet generation, QC/hallmark capture.
- **SEO/GEO/Feeds** — page-data, JSON-LD, sitemaps, Merchant feeds, hreflang, indexing rules, content/answer blocks.
- **Localization/Currency** — locales, markets, translations, FX display, VAT/policy per market.
- **Tenancy** — tenant resolution, scoping, settings, domains (active later; scoping present now).
- **Media/Assets** — upload, transform, signed URLs, image metadata.

## 4. Data flow: a live price request (hot path)

1. Client sends current selections + template id + market/locale to `POST /config/price`.
2. Configuration service loads template + option groups + active rule-set (cached).
3. Rules Engine validates → valid/quote-only/invalid + applicable modifiers.
4. CAD/Weight resolves weight (override else volume×density×buffer×size-factor).
5. Pricing Engine pulls **cached** metal spot + FX + stone price; runs the formula; itemizes; applies modifiers, margin, VAT.
6. Returns price + breakdown + preview refs + validity reasons. Target < 300 ms p95.
7. On add-to-cart/checkout, the same computation is **re-run authoritatively** and frozen into a snapshot (client price is advisory only).

Metal spot, FX and stone prices are refreshed by background jobs and cached; the hot path never blocks on an external call.

## 5. Multi-tenancy strategy

- **Shared-schema, row-level tenancy:** `tenant_id` (UUID) on every business table; a default tenant seeded for the own-brand MVP.
- Enforce scoping in a repository/query layer (and optionally Postgres RLS later) so no query can leak across tenants.
- Tenant-resolved by host/domain at the edge → injected into request context.
- Tenant settings (branding, locales, currencies, margins, suppliers, feature flags) in a `tenant_settings` store.
- MVP hides all tenant UI and runs single-tenant, but the schema, queries and API are already tenant-aware.

## 6. Environments & deployment

- **Environments:** local (Docker Compose) → staging → production. Seed + migration scripts for reproducible data.
- **CI/CD:** migrations gated; contract tests on the pricing/rules engine; preview deploys for storefront.
- **Config:** all secrets (PSP keys, metal-API keys, Nivoda creds, S3) in a vault/secret manager; never in code. Storefront never holds provider secrets — it calls the engine.
- **Caching/CDN:** Cloudflare in front of assets and SSG/ISR pages; Redis for engine caches; signed URLs for private CAD/renders.
- **Backups & audit:** nightly DB backups; append-only logs for price/FX refreshes, imports, and snapshot creation.

## 7. Key cross-cutting rules for implementers

- **Determinism:** given a snapshot, a price is fully reproducible. No hidden global state in pricing.
- **No SKU explosion:** never persist the cartesian product of options. Configurations are computed; only *ordered* configurations persist.
- **Idempotent jobs:** imports, feed syncs, feed/sitemap generation are safe to re-run.
- **Fail safe, not silent:** a missing/stale input downgrades a config to quote-only with a reason; it never yields a wrong or `NaN` price.
- **Everything localizable and tenant-scoped** by default.
