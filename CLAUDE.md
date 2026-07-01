# CLAUDE.md — working memory for AI agents on this repo

## What this project is

A **headless jewelry configuration engine** (configuration + pricing +
supplier + production + SEO), MVP scope = engagement rings. The storefront is
just one client. Same engine later becomes white-label SaaS. Owner is
non-technical; agents do the building.

The full spec lives in `docs/spec/` (16 documents). **`docs/spec/README.md` is
the index.** The two contract documents where most bugs will hide — unit-test
them first and hardest:

- `docs/spec/06-pricing-engine.md` (formulas, snapshot, never-NaN, validity states)
- `docs/spec/07-configurator-rules-engine.md` (rule types, evaluation, conflicts)

## Hard rules

1. Read `PRINCIPLES.md` before writing code — six non-negotiables + derived
   engineering rules (no floats for money, never NaN, determinism, tenant
   scoping everywhere).
2. Build strictly in the phase order of
   `docs/spec/14-roadmap-and-open-decisions.md`; enforce each phase's exit
   test before advancing. **Do not start the storefront early.**
3. Update `PROGRESS.md` in the same commit as the work (phase status, decision
   log, work log).
4. Business decisions are the owner's: anything in the open-decisions list
   (Part D of doc 14) gets the documented default unless the owner confirms
   otherwise in chat — record confirmations in `PROGRESS.md`.
5. Never commit secrets. `.env` is gitignored and holds the owner's tokens;
   `.env.example` documents required variables with placeholder values.

## Confirmed decisions

- **Backend: Python 3.11 + FastAPI** (decision #11, confirmed 2026-07-01).
  SQLAlchemy 2.0 + Alembic, PostgreSQL 16, Redis, Meilisearch, S3-compatible
  object storage (MinIO locally). Package manager: **uv**.
- Storefront/admin will be Next.js (App Router) — later phases.

## Conventions

- Backend lives in `backend/`, package name `app`.
- UUID primary keys, `created_at`/`updated_at` everywhere, soft-delete
  `deleted_at` where relevant. Money as integer minor units + `currency`
  column; rates as `numeric`.
- `tenant_id` on every business table (see the explicit scoping rule in
  `docs/spec/05-data-model.md`); all queries go through the tenant-scoped
  repository layer — never raw unscoped queries on tenant tables.
- Migrations: Alembic, one revision per coherent change, comment which
  tenant-scoping policy each table uses (carries `tenant_id` vs inherits via
  parent FK).
- Tests: pytest; pricing/rules engines get exhaustive unit tests (the spec
  lists required test cases in docs 06 §9 and 07 §9).
- Run tests with `cd backend && uv run pytest`. Lint: `uv run ruff check .`.

## Environment notes

- Local infra via `docker-compose.yml` at repo root (Postgres 16, Redis,
  Meilisearch, MinIO).
- Remote sessions: work on the designated `claude/...` branch, push there.
- The engine must never hardcode brand or domain — both are tenant/config
  values (brand name is still an open decision).
