# Non-negotiable design principles

These six rules override convenience, deadlines and shortcuts. Every PR is
checked against them. They originate in `docs/spec/README.md` and are kept
here, at the repo root, so they stay visible.

1. **The engine is the source of truth, not the AI image.**
   Price and order spec derive from structured configuration data. AI/rendered
   images are for inspiration and conversion only.

2. **Rules over hardcoding.**
   Which metals, stones, shapes, sizes and settings are valid is admin-defined
   data, not code. Adding an option, template or constraint must never require
   a deploy.

3. **No SKU explosion.**
   Store templates + options + rules. Generate configurations on demand. Never
   persist millions of variant rows. (Single deliberate exception: the small
   curated `indexable_configurations` set for SEO/feeds.)

4. **Every quote/order stores an immutable price snapshot.**
   Gold spot, FX rate, supplier stone price, margin rule, VAT rule, timestamp —
   all frozen at purchase, with full version-pinning so a historical order
   reproduces its total byte-for-byte forever.

5. **`tenant_id` on every business table from day one.**
   SaaS is hidden in the MVP UI but never blocked by the schema. No query may
   ever cross tenants.

6. **SEO/GEO is engine output, not a frontend afterthought.**
   Structured data, feeds, hreflang and indexing rules come from the same
   source of truth as prices and specs.

## Derived engineering rules

- **Never floats for money.** Integer minor units + currency, or `numeric` for
  rates.
- **Never NaN.** A missing/stale pricing input downgrades the configuration to
  `quote_only` with a human reason; it never emits `NaN`, `null`, `0` or a
  partial total as if it were the price.
- **Determinism.** Given a snapshot, a price is fully reproducible. No hidden
  global state in pricing.
- **Hot path never blocks on an external call.** Metal spot, FX and stone
  prices are refreshed by background jobs and read from cache.
- **Idempotent jobs.** Imports, feed syncs and sitemap generation are safe to
  re-run.
- **Fail safe, not silent.** Canonical validity states: `purchasable` /
  `quote_only` / `invalid` (defined in `docs/spec/06-pricing-engine.md` §6).
