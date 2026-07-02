# Build progress & decision log

Single source of truth for *where the build is*. Update this file in the same
commit as the work it describes.

## Current phase

**Phase 4 — Price sources & imports** (next up; Phases 0–3 complete)

## Phase tracker

Phases and exit tests are defined in `docs/spec/14-roadmap-and-open-decisions.md`.

| Phase | Name | Status | Exit test passed |
|---|---|---|---|
| 0 | Foundation (repo, compose, migrations, tenancy wiring) | ✅ complete | 2026-07-01 — 8 tests green: request carries tenant context end-to-end; migrations + seeds run clean |
| 1 | Data model (Groups A–P) | ✅ complete | 2026-07-01 — 13 tests green: full template + components + options + manufacturability + versioned rule-set persisted; invalid metal combos impossible (material_options only) |
| 2 | Rules engine | ✅ complete | 2026-07-01 — 32 tests green: validate() returns purchasable/quote_only/invalid + reasons on the seeded template with real compatibility/exclusion/requirement/conditional/price-modifier rules |
| 3 | Pricing engine | ✅ complete | 2026-07-01 — 50 tests green incl. all spec 06 §9 cases: worked example, magic-size jump, lab/natural delta, stale-feed→quote_only range, weight override, engraving/non-returnable, FX+VAT swap, snapshot byte-for-byte reproduction, version-pin proof |
| 4 | Price sources & imports | ⬜ not started | — |
| 5 | Admin app | ⬜ not started | — |
| 6 | Configurator + pricing API (headless) | ⬜ not started | — |
| 7 | Storefront (Next.js) | ⬜ not started | — |
| 8 | Orders, bespoke, production, compliance | ⬜ not started | — |
| 9 | SEO/GEO output + Merchant feed | ⬜ not started | — |
| 10 | AI Jewelry Designer | ⬜ not started | — |
| 11+ | 3D, live feeds, ready-made, SaaS | ⬜ not started | — |

## Decision log

Open decisions live in `docs/spec/14-roadmap-and-open-decisions.md` Part D.
Confirmed decisions are recorded here; the spec defaults apply to everything
not yet listed.

| # | Decision | Choice | Decided | By |
|---|---|---|---|---|
| 11 | Backend language | **Python + FastAPI** | 2026-07-01 | Owner (confirmed in chat) |

### Still open (using spec defaults for now)

- #1 Brand name + `.com` domain *(needed by Phase 7)*
- #2 Launch template set — default: solitaire, hidden-halo, halo, pavé, three-stone + bespoke base *(Phase 5)*
- #3 Positioning / price-band split *(Phase 3/5)*
- #4 Design deposit — default €250 *(Phase 8)*
- #5 Production deposit — default 50% *(Phase 8)*
- #6 PSP — default Mollie *(Phase 7)*
- #7 First diamond feed — default Nivoda GraphQL *(Phase 11)*
- #8 Feed vs price-table carat threshold — default > 0.30 ct *(Phase 4/11)*
- #9 20k (833) casting density — needs real factory figure *(Phase 1: interpolation placeholder seeded)*
- #10 Casting/waste factor + fabrication premium per factory — defaults 2% / ×1.05 *(Phase 3)*
- #12 Buy vs build interactive 3D *(Phase 11)*
- #13 AI providers *(Phase 10)*
- #14 Hosting — default Docker on Hetzner/DO + Cloudflare + Vercel-style storefront *(Phase 0; local Docker Compose for now)*
- #15 Responsibility Mark registration *(operational, before selling)*
- #16 VAT/OSS setup *(operational, Phase 8/9)*
- #17 Locale launch order — default EN/NL first *(Phase 7/9)*

## Work log

| Date | What |
|---|---|
| 2026-07-01 | Spec docs (16 files) received and moved to `docs/spec/`. Root docs created (README, PRINCIPLES, PROGRESS, CLAUDE). `.gitignore` + local `.env` (token, not committed). Backend decision #11 confirmed: Python + FastAPI. Phase 0 started. |
| 2026-07-01 | **Phase 3 complete.** `app/pricing/`: pure deterministic engine, all Decimal minor-unit math (no floats). weight.py (volume×SG×waste×size-factor, override wins, missing input → None never 0), inputs.py (explicit input dataclasses with freshness flags), engine.py (master formula: metal/stone+magic-size/side stones/labor/engraving/fees/buffers/margin/VAT + rule modifiers; canonical statuses; degraded-but-fresh-enough stays purchasable; too-stale → quote_only with ±10% estimated range; no basis at all → no total AND no range), snapshot.py (rebuild inputs from a snapshot and reproduce byte-for-byte). DB/cache wiring (GoldAPI/ECB adapters, Redis) is Phase 4 per roadmap. |
| 2026-07-01 | **Phase 2 complete.** `app/rules/`: safe JSON-logic evaluator (allow-listed operators only — var/and/or/not/==/!=/comparisons/in/missing/if, depth-capped, malformed rules fail safe to invalid) + pure DB-free validate() implementing the 5 rule types with deterministic conflict priority (blocks > requirements > visibility > modifiers), template required-groups, manufacturability limit checks (breach → invalid, manual-CAD flag → quote_only). Tested in-memory AND against the DB-seeded Oval Solitaire rule set. Rule-simulator publish check deferred to Phase 5 (admin publish flow) per spec. |
| 2026-07-01 | **Phase 1 complete.** All data-model groups A–P implemented (111 tables, migrations 0002–0006): catalog/templates/options, rings, metals + densities + material_options, stones + price tables + carat bands, CAD, versioned rules, pricing incl. fully version-pinned immutable price_snapshots, supplier imports, bespoke, orders/payments/withdrawals, production/QC/hallmarking, customers/GDPR, SEO/GEO + indexable_configurations, merchant feeds, jobs/audit. Reference seeds (densities from spec 06, EU ring sizes, diamond grades, magic-size bands) + demo "Oval Solitaire" template fixture with published rule-set v1. Exit test green (13 tests). Note: 20k density is a placeholder (decision #9 — factory must confirm). |
| 2026-07-01 | **Phase 0 complete.** `backend/`: FastAPI app, SQLAlchemy 2.0 async + Alembic, Group A tenancy tables (migration 0001), idempotent seeds (default tenant, EN/NL, EUR, localhost domain), tenant-resolution middleware (host → tenant_domains → default-slug fallback), tenant-scoped repository base, `/health` + `/tenant/me`. Root: docker-compose (Postgres/Redis/Meilisearch/MinIO), `.env.example`, GitHub Actions CI (ruff + pytest vs real Postgres). Exit test verified live: uvicorn served `/tenant/me` with resolved tenant + seeded data. |
