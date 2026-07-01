# Build progress & decision log

Single source of truth for *where the build is*. Update this file in the same
commit as the work it describes.

## Current phase

**Phase 0 — Foundation** (in progress)

## Phase tracker

Phases and exit tests are defined in `docs/spec/14-roadmap-and-open-decisions.md`.

| Phase | Name | Status | Exit test passed |
|---|---|---|---|
| 0 | Foundation (repo, compose, migrations, tenancy wiring) | 🟡 in progress | — |
| 1 | Data model (Groups A–P) | ⬜ not started | — |
| 2 | Rules engine | ⬜ not started | — |
| 3 | Pricing engine | ⬜ not started | — |
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
