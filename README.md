# Jewelry Configuration Engine

Headless jewelry configuration, pricing, 3D, supplier and production platform.
The storefront is one client of the engine; the same core later powers a
white-label SaaS.

**MVP scope:** engagement rings only. **Positioning:** high-end bespoke +
affordable luxury. **Markets:** Netherlands → Europe → worldwide.

## Repository layout

| Path | What it is |
|---|---|
| `docs/spec/` | The full working specification (16 docs). Start at `docs/spec/README.md`. |
| `PRINCIPLES.md` | The six non-negotiable design principles. Read before writing code. |
| `PROGRESS.md` | Build-phase tracker + decision log. The current state of the build. |
| `CLAUDE.md` | Working memory / instructions for AI agents building this repo. |
| `backend/` | The engine: Python + FastAPI + PostgreSQL. |
| `docker-compose.yml` | Local infrastructure: Postgres, Redis, Meilisearch, MinIO. |

## Quick start (backend)

```bash
# 1. Infrastructure
docker compose up -d

# 2. Backend (requires uv: https://docs.astral.sh/uv/)
cd backend
cp ../.env.example .env        # adjust if needed
uv sync
uv run alembic upgrade head    # migrations
uv run python -m app.seeds     # seed default tenant + reference data
uv run uvicorn app.main:app --reload

# 3. Tests
uv run pytest
```

## Build order (do not deviate)

Data model → rules engine → pricing engine → supplier/price imports → admin →
configurator API → storefront → 3D → AI designer → SaaS.
Full roadmap with per-phase exit tests: `docs/spec/14-roadmap-and-open-decisions.md`.
Current phase and completed work: `PROGRESS.md`.
