# 09 — Integrations & Supplier Imports

MVP data is manual, but the engine is built import-ready so feeds slot in without schema change. All external calls happen in background jobs; the pricing hot path only reads caches.

## 1. Metal price providers (live — MVP)
Adapter pattern behind `metal_price_sources` (provider + config + priority + fallback).

| Provider | Strength | Notes |
|---|---|---|
| **GoldAPI.io** (recommended) | Returns **per-gram price at each karat** (24/22/21/20/18/16/14/10k) + spot/bid/ask/timestamp, multi-currency (EUR/USD/…) | Removes manual purity math for gold; XAU/XAG/XPT/XPD |
| **Metals.Dev** | ≤60s delay even on free tier; LBMA/LME/MCX sources; FX included | Good primary or fallback |
| **MetalpriceAPI** | Metals + FX, troy oz/g/kg | Affordable general option |
| **Metals-API** | Wide coverage; carat endpoint is **per-carat** (÷0.2 → per-gram-per-purity) | Historical + fluctuation |

- Ingest intraday (5–15 min) into `metal_price_snapshots`; pricing reads cache only.
- Silver 925 / platinum 950: use per-purity where available, else spot × fineness.
- 20k/833: prefer factory-confirmed casting factor; fallback derive from 24k × (833/999).
- **LBMA**: benchmark data has licensing terms for valuation/pricing — use commercial APIs instead of ingesting fixings directly.
- Fallback chain: primary provider → secondary provider → last-good cache (within max-age) → `quote_only` (never NaN).

## 2. FX (currency)
- **ECB** SDMX API / daily euro reference rates — free, authoritative, EUR-based; refresh daily into `fx_rates`.
- Caveat: ECB rates are informational, **not** transaction rates. Use for **display/estimation**; the PSP settlement rate governs the actual charge. Store the rate used in the snapshot.
- Optionally add a commercial FX API (many metal providers bundle FX) for non-EUR base pairs.

## 3. Diamonds & gemstones (feeds — LATER, abstractions now)
Build `SupplierStoneAdapter` with concrete adapters:

| Source | Access | Notes |
|---|---|---|
| **Nivoda** (recommended first) | **GraphQL** (verified customers); also CSV/XML via FTP/link | ~1.6M natural+lab diamonds + colored gems; request only needed fields; Pro tier can place orders/holds. Public docs: `github.com/Nivoda/nivoda-api`. Requires signed Nivoda Feed Agreement + account-manager activation. |
| **Rapaport / RapNet** | Instant Inventory API | filtering, ring-builder, cart, multi-lang/currency |
| **IDEX** | API/feed | common ring-builder source |
| **Polygon** | API/feed | common ring-builder source |

- Normalize every feed into `supplier_stones` (shape, carat, color, clarity, cut, polish, symmetry, fluorescence, cert lab/number/url, measurements, ratio, depth%, table%, price, currency, availability, media, external_id).
- Apply per-supplier `markup_rule` + filters. Cache and sync on cadence (`jobs.kind = feed_sync`).
- MVP center-stone pricing uses `diamond_price_tables`; when a feed is connected, configs above the carat threshold resolve a real `supplier_stones` row and persist it on the order.

## 4. Supplier product / factory imports (files + manual — MVP)
Because factories are local/manual (photos/WhatsApp/Excel), manual entry is first-class and file import is the near-term automation.

Import job lifecycle (`supplier_import_jobs` / `supplier_import_rows`):
```
choose source (manual | excel | csv | xml | ftp | api | graphql)
  → upload/fetch
  → map columns → internal fields (saved mapping per supplier)
  → dry-run: per-row validation (types, required, referential)
  → preview stats (ok / warn / error counts)
  → commit (idempotent; re-runnable)
  → view row-level errors; fix + re-run
```
Field targets: templates/products, factory price lists (metal/labor/stone), factory weight overrides, ready-made stock (later). Keep a saved column-mapping per supplier so repeat imports are one click.

## 5. Payments (PSP)
- **Mollie** (strong NL/EU, iDEAL, Bancontact, cards, SEPA) recommended for the Dutch/EU market; **Stripe/Adyen** are alternatives (Adyen if scaling internationally).
- Support **partial payments**: design deposit, production deposit, balance, prototype, full.
- Store only PSP references/tokens; never raw card data. Webhooks update `payments.status`.
- Record the PSP settlement/FX context alongside the snapshot where available.

## 6. Rendering / AI providers
- Image/render provider for AI previews; LLM (structured output) for AI-Designer intent extraction. Pluggable behind an interface so the model/provider can change. Secrets in the vault; storefront never holds these keys.

## 7. Other integrations
- **Object storage** (S3-compatible) for CAD/renders/images/feeds; signed URLs for private assets.
- **Search** (Meilisearch) index built from catalog/option data for faceted browse.
- **Google Merchant Center** feed output (see `11-seo-geo-engine.md`).
- **Analytics/consent**: server-side events preferred; consent-gated; GDPR-compliant.

## 8. Integration principles
- Everything external is an **adapter** with a common interface + provider-agnostic normalized model.
- Every sync is a **logged, idempotent job**; failures alert and fall back, never crash the hot path.
- **Secrets** in a vault; per-tenant credentials later.
- Rate-limit and cache aggressively; respect provider ToS and licensing (esp. LBMA, ECB, Nivoda feed agreement).
