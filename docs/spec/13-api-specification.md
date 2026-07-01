# 13 — API Specification

Headless engine surface. REST for most operations; consider GraphQL for the catalog/configurator read side (flexible field selection like Nivoda's own API). All endpoints are tenant-scoped (tenant resolved by host/context). AuthN via session/JWT; AuthZ by role. Money always `{ amount_minor, currency }`. Every mutating call is idempotent where feasible.

Base: `/api/v1`. Below is the key surface, not exhaustive.

## 1. Catalog (public, read)
```
GET  /categories
GET  /templates?category=engagement-ring&filter[style]=solitaire&locale=&market=
GET  /templates/{id}                 # template + components + option groups + defaults + media + SEO
GET  /templates/{id}/option-groups   # groups, options, step order, required flags
GET  /templates/{id}/rules           # published rule-set (for client-side hinting; server is authority)
GET  /ring-sizes?standard=EU
```

## 2. Configuration & pricing (core hot path)
```
POST /config/validate
     body: { template_id, selections:{group:option,...}, market, locale }
     → { status: purchasable|quote_only|invalid,
         reasons:[...], visible_groups:[...], required_groups:[...], modifiers:[...] }

POST /config/price
     body: { template_id, selections, market, locale }
     → { validity:{ status: purchasable|quote_only|invalid, reasons:[...], degraded:bool },
         itemized:{ metal, center_stone, side_stones, setting, casting, polishing,
                    engraving, buffers, margin, vat, ... },      # present when priceable
         total:{amount_minor,currency},                          # present iff purchasable
         estimated_range:{min,max,currency},                     # present iff quote_only & computable
         weight:{estimated_g, override_g?, size_factor, waste_factor},
         preview:{ ai_render_url?, static_image_url? },
         config_hash }
     # Canonical states (06-pricing-engine.md §6):
     #  purchasable → exact `total`, checkout enabled
     #  quote_only  → `estimated_range` where computable, exact checkout disabled, request-quote enabled
     #  invalid     → no price, `reasons[]` say what to change
     # Never returns NaN / null / fake 0.

POST /config/share      → { share_url }          # encoded state, noindex
GET  /config/{hash}      → resolved config + latest price
```
Contract guarantees: deterministic; < 300 ms p95; reads caches only; identical input+source-timestamps ⇒ identical output (cacheable by `config_hash`).

## 3. AI Jewelry Designer
```
POST /ai/design-intent
     body: { prompt?, image_ref?, market, locale }
     → { intent:{product_type,style,metal,center_stone,details[],budget?},
         matched_templates:[{template_id, score}],
         price_range:{min,max,currency},
         inspiration_render_url,
         suggested_path: "configurator" | "bespoke",
         notes[] }
POST /ai/load-into-configurator   body:{ intent } → { template_id, selections }
POST /ai/to-bespoke               body:{ intent, uploads[] } → { bespoke_request_id }
```

## 4. Cart, quotes, orders
```
POST /cart                         # create/get cart
POST /cart/items                   body:{ template_id, configuration, qty }
POST /quotes                       body:{ configuration } → freezes a price_snapshot, returns quote
GET  /quotes/{id}
POST /orders                       body:{ cart_id|quote_id, customer, payment_intent }
     → order + LOCKED snapshot(s) + production job(s) created
GET  /orders/{id}                  # status, items, snapshots, payments
GET  /orders/{id}/status
```

### Withdrawal function (EU, Art. 11a — see `12`)
```
GET  /orders/{id}/withdrawal-eligibility   → { per_item:[{order_item_id, eligible|exempt, reason}] }
POST /withdrawals                          body:{ order_id, order_item_ids[], name, contact }
                                           → { withdrawal_request_id, status:"initiated" }   # step 1
POST /withdrawals/{id}/confirm             → { status:"confirmed" }                          # step 2
     # engine then sends acknowledgement on a durable medium (content + date + time)
GET  /withdrawals/{id}                      → { status, submitted_at, confirmed_at, acknowledged_at }
```
Must be reachable via a prominent, continuously available control ("withdraw from contract here"); exempt items (bespoke/engraved) are filtered out of eligibility.

## 5. Payments & deposits
```
POST /payments/intent   body:{ order_id|bespoke_request_id, kind:[deposit_design|deposit_production|balance|full|prototype], amount }
     → { psp, client_token }       # via Mollie/Stripe; no raw card data
POST /payments/webhook  (PSP → engine)   # updates payments.status, triggers workflow transitions
GET  /payments?order_id=
```

## 6. Bespoke
```
POST /bespoke/requests             body:{ source:[upload|ai_designer], brief, uploads[] } → request + rough range
POST /bespoke/requests/{id}/design-deposit   → payment intent (non-refundable, credited)
POST /bespoke/requests/{id}/revisions         body:{ cad_ref, render_ref } (admin)
POST /bespoke/requests/{id}/approve           → becomes order
POST /bespoke/requests/{id}/prototype         → prototype order (STL export)
GET  /bespoke/requests/{id}
```

## 7. Production / factory portal
```
GET  /production/jobs?factory_id=&status=
GET  /production/jobs/{id}          # spec sheet, CAD/render refs, stone/size/engraving, hallmark flag
POST /production/jobs/{id}/steps    body:{ step, status, notes }
POST /production/jobs/{id}/qc       body:{ checklist, passed, photos[] }
POST /production/jobs/{id}/hallmark body:{ fineness, responsibility_mark, assay_office, status }
POST /production/jobs/{id}/actual-weight  body:{ grams }
POST /production/jobs/{id}/shipment body:{ carrier, tracking, insured }
```

## 8. Admin (auth: admin/editor/merchandiser)
```
# Templates / options / rules
POST /admin/templates ; PUT /admin/templates/{id} ; POST /admin/templates/{id}/clone
POST /admin/option-groups ; POST /admin/options
POST /admin/templates/{id}/rule-sets ; POST /admin/rule-sets/{id}/publish
POST /admin/rules ; POST /admin/rules/preview   body:{ rule, sample_configs[] }
# Pricing
PUT  /admin/price-formula ; POST /admin/labor-costs ; POST /admin/margins ; POST /admin/vat-rules
POST /admin/diamond-price-tables ; POST /admin/carat-bands
GET  /admin/price-sources ; PUT /admin/price-sources/{id}
# Suppliers / imports
POST /admin/suppliers ; POST /admin/factories
POST /admin/imports        body:{ supplier_id, source, mapping } (dry_run first)
GET  /admin/imports/{id}   # stats + row errors
# Media
POST /admin/media          # upload; returns signed url + id
```

## 9. SEO / GEO / feeds
```
GET  /seo/page-data?url=            # metadata, canonical, indexable, hreflang, content blocks
GET  /seo/schema?template_id=&locale=&market=      # JSON-LD (ProductGroup+Product+Offer, Breadcrumb, FAQ)
GET  /seo/sitemap?kind=pages|products|images|localized
GET  /seo/hreflang-group/{page_id}
GET  /merchant/feed/google?market=&locale=          # Merchant Center feed (id==sku, item_group_id==productGroupID)
GET  /content/answer-blocks?topic=
POST /admin/seo/pages ; PUT /admin/seo/indexing-rules ; POST /admin/seo/redirects
```

## 10. System / jobs (internal)
```
POST /jobs/price-refresh     # pull metal spot → metal_price_snapshots
POST /jobs/fx-refresh        # pull ECB daily → fx_rates
POST /jobs/feed-sync         # LATER: Nivoda/RapNet → supplier_stones
POST /jobs/render            # generate AI/static render for config_hash
POST /jobs/feed-gen          # regenerate Merchant feed
POST /jobs/sitemap-gen       # regenerate sitemaps
GET  /health ; GET /health/sources   # source freshness + fallbacks
```

## 11. Conventions
- **Errors**: RFC-7807 problem+json; validation errors list per-field reasons.
- **Pagination**: cursor-based for large lists (imports, stones, orders).
- **Idempotency-Key** header on order/payment mutations.
- **Versioning**: `/api/v1`; additive changes preferred; snapshots pin rule-set + source versions.
- **Rate limits** on public config/price endpoints; heavier limits on admin.
- **Auth**: short-lived tokens; role scopes; per-tenant credentials for external providers (later).
- **Observability**: every price response carries `config_hash` + source timestamps for debugging/repro.
