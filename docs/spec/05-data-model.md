# 05 — Data Model (ERD)

PostgreSQL. Conventions: every table has `id` (UUID PK), `created_at`, `updated_at`, and soft-delete `deleted_at` where relevant. Money stored as integer minor units + `currency`, or `numeric(14,4)` for rates; **never floats for money**. Flexible per-option payloads use `jsonb`. Names below are indicative; adjust casing to your ORM.

### Tenant-scoping rule (explicit — do not guess)
`tenant_id` (UUID, FK → `tenants`) is present on:
1. **Every top-level/aggregate-root table** (templates, option_groups, orders, quotes, suppliers, seo_pages, price_snapshots, jobs, etc.), and
2. **Every table you query directly, filter on, cache by, or apply row-level security to** (the "hot" tables).

Pure child rows that are *only ever reached through a scoped parent* (e.g. `template_components`, `production_steps`, `qc_photos`, `bespoke_revisions`, `ring_size_standards`) inherit tenancy through their parent FK and need not carry `tenant_id` — **unless** you enable Postgres RLS, in which case denormalize `tenant_id` onto them too and add composite FKs `(tenant_id, parent_id)`. Pick one policy per table and record it in the migration comment. The rule is: *no query may ever cross tenants*; denormalize `tenant_id` wherever that guarantee would otherwise depend on a join.

Design rule restated: **templates + options + rules + snapshots.** Do not persist generated variants — with one deliberate exception: a small **curated** set of commercial/SEO variants (see `indexable_configurations`, Group N). That is curation, not SKU explosion.

---

## Group A — Tenancy
- **tenants**(id, name, slug, status)
- **tenant_settings**(tenant_id, key, value jsonb) — branding, feature flags, defaults
- **tenant_domains**(id, tenant_id, host, is_primary)
- **tenant_locales**(id, tenant_id, locale, is_default)
- **tenant_currencies**(id, tenant_id, currency, is_default, rounding_rule)

## Group B — Catalog & templates
- **categories**(id, tenant_id, parent_id, name, slug, type) — MVP seeds "engagement-ring"
- **product_templates**(id, tenant_id, category_id, code, name, style, status, base_config jsonb, default_supplier_id, is_bespoke_base bool) — the `ProductGroup`
- **template_components**(id, template_id, kind[shank|head|prongs|center_stone|side_stones|halo|gallery|engraving_surface|prototype], name, cad_volume_mm3, metal_assignable bool, sort)
- **template_manufacturability**(id, template_id, component_id nullable, min_band_thickness_mm, min_wall_thickness_mm, min_prong_thickness_mm, prong_count nullable, setting_type, stone_seat_tolerance_mm, stone_measurement_min_mm, stone_measurement_max_mm, requires_manual_cad_check bool) — hard manufacturing limits so the configurator/AI can't produce a beautiful-but-impossible or structurally weak design; validated at price/validate time and again at CAD
- **option_groups**(id, tenant_id, key[metal|purity|metal_color|finish|stone_type|stone_shape|stone_quality|carat|ring_size|engraving|side_stone|setting], name, ui_type[select|swatch|slider], sort)
- **options**(id, option_group_id, code, label, value jsonb, sort, is_active) — e.g. metal=`platinum_950`, shape=`oval`
- **template_option_groups**(id, template_id, option_group_id, step_order, is_required, default_option_id, min_qty, max_qty)
- **template_component_options**(id, template_component_id, option_group_id) — which components a group applies to (e.g. metal per component)
- **media_assets**(id, tenant_id, kind[static_angle|ai_render|cad|prototype_stl|texture|env_map], url, width, height, meta jsonb, approved bool)
- **template_media**(id, template_id, media_asset_id, purpose, sort)
- **option_media_map**(id, template_id, option_id, media_asset_id) — which asset to show for an option (for image-swap previews)

## Group C — Ring-specific
- **ring_sizes**(id, tenant_id, standard[EU|US|UK], label, diameter_mm, circumference_mm)
- **ring_size_standards**(id, from_standard, from_label, to_standard, to_label) — conversion map
- **template_size_weight_factors**(id, template_id, ring_size_id, weight_factor) — size→metal-weight multiplier
- **ring_profiles**(id, template_id, band_width_mm, band_profile) — optional, for weight/fit notes

## Group D — Metals
- **metals**(id, tenant_id, key[gold|platinum|silver], name)
- **metal_purities**(id, metal_id, karat, fineness, label) — gold: 585/750/833/916; platinum 950; silver 925
- **metal_colors**(id, metal_id, key[yellow|white|rose], label)
- **metal_densities**(id, metal_purity_id, metal_color_id nullable, specific_gravity numeric(6,3), source) — see `06` for values
- **material_options**(id, tenant_id, metal_id, purity_id, color_id nullable, label, fineness, density_id, is_active bool, recommended_for_engagement_rings bool) — **the normalized valid-combination table.** The configurator offers *material_options*, not free metal×purity×color, so nonsense like `silver+18k`, `platinum+rose`, or `22k white gold` cannot be produced by default. Rules (Group G) still handle template-specific edge cases. Note: keep 20k/22k/silver-925 `is_active` but `recommended_for_engagement_rings=false` (high-karat gold is soft; silver is not a premium diamond-ring metal) — allow them only on specific templates or quote_only paths.
- **metal_price_sources**(id, tenant_id, provider[goldapi|metalsdev|metalpriceapi|manual], config jsonb, priority, is_active)
- **metal_price_snapshots**(id, tenant_id, metal, karat, currency, price_per_gram numeric(14,4), source, fetched_at) — time series
- **metal_compatibility_rules**(id, tenant_id, rule jsonb) — e.g. disallow silver+gold in one piece (also representable in Group G)

## Group E — Stones
- **stone_types**(id, tenant_id, key[natural_diamond|lab_diamond|sapphire|ruby|emerald], name, is_active)
- **stone_shapes**(id, tenant_id, key[round|oval|pear|princess|emerald|cushion|marquise|asscher|radiant], name)
- **stone_quality_grades**(id, stone_type_id, attribute[color|clarity|cut|polish|symmetry|fluorescence], code, label, sort)
- **diamond_price_tables**(id, tenant_id, stone_type_id, shape_id, carat_min, carat_max, color, clarity, price_per_carat numeric(14,4), currency, supplier_id nullable, valid_from, valid_to)
- **gemstone_price_tables**(id, tenant_id, stone_type_id, shape_id, carat_min, carat_max, grade, price_per_carat, currency) — LATER
- **carat_price_bands**(id, tenant_id, stone_type_id, carat_threshold, multiplier) — "magic size" (1.00/1.50/2.00)
- **supplier_stones**(id, tenant_id, supplier_id, stone_type_id, shape_id, carat, color, clarity, cut, polish, symmetry, fluorescence, cert_lab, cert_number, cert_url, measurements, ratio, depth_pct, table_pct, price, currency, availability, image_url, video_url, external_id, synced_at) — populated by feeds LATER
- **stone_certificates**(id, supplier_stone_id, lab, number, url, meta jsonb)

## Group F — CAD / visual
- **cad_files**(id, tenant_id, template_id, component_id nullable, url, format[3dm|stl|step|glb], volume_mm3, meta jsonb)
- **render_jobs**(id, tenant_id, config_hash, status, provider, input jsonb, output_media_id, created_at)
- **future_3d_assets**(id, template_id, glb_url, material_map jsonb, mesh_map jsonb) — LATER (interactive 3D)

## Group G — Rules
- **rule_sets**(id, tenant_id, template_id nullable, version, status[draft|published], published_at)
- **rules**(id, rule_set_id, type[compatibility|exclusion|requirement|conditional_visibility|price_modifier], scope jsonb, condition jsonb, effect jsonb, message, sort)
  - `scope`: which template/component/option groups it applies to
  - `condition`: JSON logic over selected options (e.g. `carat > 0.30`, `metal in [silver] and other_metal in [gold,platinum]`)
  - `effect`: block / require / show-hide / add-surcharge / apply-discount
- **option_dependencies**(id, rule_set_id, when_option_id, requires_option_id nullable, excludes_option_id nullable)

## Group H — Pricing
- **price_formula**(id, tenant_id, template_id nullable, components jsonb, version) — ordered list of components + how each is computed
- **labor_costs**(id, tenant_id, operation[setting|casting|polishing|finishing|assembly], basis[per_piece|per_stone|per_hour|per_gram], amount, currency, supplier_id nullable)
- **setting_costs**(id, tenant_id, setting_type, per_stone_cost, currency)
- **engraving_costs**(id, tenant_id, type[standard|special], base_cost, per_char_cost, currency, makes_non_returnable bool)
- **prototype_costs**(id, tenant_id, kind[plastic_stl], base_cost, currency, credited_above_order_value nullable)
- **design_fees**(id, tenant_id, amount, currency, refundable bool, credited bool)
- **margins**(id, tenant_id, template_id nullable, market nullable, band nullable, type[percent|fixed], value)
- **buffers**(id, tenant_id, kind[shipping|payment_fee|production_risk|warranty], type[percent|fixed], value, currency)
- **vat_rules**(id, tenant_id, market, category nullable, rate numeric(6,4), price_includes_vat bool)
- **fx_rates**(id, tenant_id, base_currency, quote_currency, rate numeric(18,8), source, fetched_at)
- **price_calculations**(id, tenant_id, config_hash, itemized jsonb, total, currency, computed_at) — ephemeral cache
- **price_snapshots**(id, tenant_id, quote_id nullable, order_item_id nullable, inputs jsonb, itemized jsonb, total, currency, metal_prices jsonb, fx_rate, stone_price, margin_applied, vat_applied, created_at, **_version-pinning:_** template_version, price_formula_version, rule_set_version, density_source_version, labor_cost_version, margin_rule_version, vat_rule_version, metal_price_snapshot_id (FK), fx_rate_snapshot_id (FK)) — **immutable & fully reproducible.** Pinning only `rule_set_version` is not enough: if a formula, density table, labor cost, margin, or VAT rule later changes, an old order must still recompute to the exact same total. Every input that can drift is version-referenced here.

## Group I — Suppliers & factories
- **suppliers**(id, tenant_id, name, type[factory|wholesaler|diamond_feed|gem_feed], country, contact jsonb, markup_rule jsonb, is_active)
- **factories**(id, tenant_id, supplier_id nullable, name, country, capabilities jsonb, lead_time_days, min_order, handles_hallmarking bool)
- **factory_manufacturability**(id, tenant_id, factory_id, can_cast bool, can_set_stone bool, can_engrave bool, can_prototype bool, supported_metals jsonb, supported_settings jsonb, max_stone_carat, notes) — what each factory can actually make; a config routed to a factory is checked against this before the order is accepted. *(This structured table replaces the earlier generic `factory_capabilities` key/value idea — do not build both.)*
- **supplier_price_lists**(id, tenant_id, supplier_id, kind[metal|labor|stone|product], url_or_ref, valid_from)
- **supplier_import_jobs**(id, tenant_id, supplier_id, source[manual|excel|csv|xml|ftp|api|graphql], status, mapping jsonb, dry_run bool, stats jsonb, created_at)
- **supplier_import_rows**(id, import_job_id, raw jsonb, mapped jsonb, status[ok|warn|error], messages jsonb)
- **factory_product_overrides**(id, tenant_id, template_id, factory_id, weight_override_g nullable, cost_override jsonb)

## Group J — Bespoke
- **bespoke_requests**(id, tenant_id, customer_id, source[upload|ai_designer], brief jsonb, status, price_range_min, price_range_max, currency, created_at)
- **bespoke_uploads**(id, bespoke_request_id, media_asset_id, kind[photo|sketch|inspiration|existing_jewelry])
- **bespoke_quotes**(id, bespoke_request_id, itemized jsonb, total, currency, valid_until)
- **bespoke_deposits**(id, bespoke_request_id, payment_id, amount, currency, non_refundable bool, credited bool)
- **bespoke_revisions**(id, bespoke_request_id, round_no, cad_media_id, render_media_id, status[sent|approved|revision_requested], notes)
- **bespoke_approvals**(id, bespoke_request_id, approved_by, approved_at, becomes_order_id)

## Group K — Orders & payments
- **carts**(id, tenant_id, customer_id nullable, currency, market)
- **cart_items**(id, cart_id, template_id, configuration jsonb, price_calculation_id, qty)
- **quotes**(id, tenant_id, customer_id nullable, configuration jsonb, price_snapshot_id, status, expires_at)
- **orders**(id, tenant_id, customer_id, type[made_to_order|bespoke|ready_made|prototype], status, currency, market, totals jsonb, placed_at)
- **order_items**(id, order_id, template_id nullable, configuration jsonb, price_snapshot_id, engraving_text nullable, ring_size_id, stone_ref nullable, non_returnable bool, qty)
- **order_configurations**(id, order_item_id, resolved_spec jsonb) — fully resolved factory spec
- **payments**(id, tenant_id, order_id nullable, bespoke_request_id nullable, psp, psp_ref, amount, currency, kind[deposit_design|deposit_production|balance|full|prototype], status)
- **deposits**(id, order_id nullable, bespoke_request_id nullable, kind, amount, currency, credited_to_order_id nullable)
- **refunds**(id, payment_id, amount, currency, reason, status)
- **withdrawal_requests**(id, tenant_id, order_id, customer_id, eligibility_status[eligible|exempt_custom|exempt_personalised|unknown], reason, submitted_at, confirmed_at, acknowledged_at, ack_medium[email|account], status[initiated|confirmed|acknowledged|refunded]) — backs the mandatory EU withdrawal function (see `12`). Two-step: `submitted` → `confirmed`, then an acknowledgement on a durable medium with content+date+time. Eligibility is derived from `order_items.non_returnable` (bespoke/engraved = exempt) but the *function itself* must exist for eligible items.

## Group L — Production & QC
- **production_jobs**(id, tenant_id, order_item_id, factory_id, status, priority, spec_sheet_media_id, due_at)
- **production_steps**(id, production_job_id, step[cad|awaiting_approval|casting|stone_setting|polishing|hallmarking|qc|shipping], status, started_at, completed_at, notes)
- **production_files**(id, production_job_id, media_asset_id, kind[cad|render|spec|other])
- **production_notes**(id, production_job_id, author, note, created_at)
- **qc_checks**(id, production_job_id, checklist jsonb, passed bool, checked_by, checked_at)
- **qc_photos**(id, production_job_id, media_asset_id)
- **hallmark_records**(id, production_job_id, required bool, metal, fineness, responsibility_mark, assay_office[waarborg_holland|ewn|ccm|other], status[not_required|pending|applied], applied_at)
- **shipments**(id, order_id, carrier, tracking, insured bool, shipped_at, delivered_at)

## Group M — Customers & auth
- **customers**(id, tenant_id, email, name, locale, currency, marketing_consent bool, created_at)
- **addresses**(id, customer_id, kind[billing|shipping], fields jsonb, country)
- **users**(id, tenant_id, email, role[admin|editor|merchandiser|factory|finance|tenant_admin], status) — staff/portal
- **consents**(id, subject_type, subject_id, kind[gdpr_terms|marketing|cookies], granted_at, revoked_at) — GDPR

## Group N — SEO / GEO
- **seo_pages**(id, tenant_id, page_type[template|category|landing|guide], ref_id, locale, market, slug, canonical_url, indexable bool, follow bool, schema_type)
- **seo_metadata**(id, seo_page_id, seo_title, seo_description, h1, primary_keyword, secondary_keywords jsonb, search_intent)
- **seo_indexing_rules**(id, tenant_id, pattern, indexable bool, reason) — controls configurator-state indexation
- **seo_redirects**(id, tenant_id, from_path, to_path, status_code)
- **seo_internal_links**(id, tenant_id, from_ref, to_ref, anchor, context)
- **hreflang_groups**(id, tenant_id, key)
- **hreflang_urls**(id, hreflang_group_id, locale, market, url)
- **sitemaps**(id, tenant_id, kind[pages|products|images|localized], url, generated_at)
- **sitemap_items**(id, sitemap_id, loc, lastmod, changefreq, priority, images jsonb)
- **content_blocks**(id, tenant_id, ref_type, ref_id, locale, kind[intro|trust|guide|expert_note], body, sort)
- **faq_blocks**(id, tenant_id, ref_type, ref_id, locale, question, answer, sort)
- **answer_blocks**(id, tenant_id, topic, locale, question, concise_answer, supporting jsonb) — GEO/AI-search
- **topic_clusters**(id, tenant_id, name, pillar_ref, members jsonb)
- **image_metadata**(id, media_asset_id, alt, caption, filename, title)
- **indexable_configurations**(id, tenant_id, template_id, config_hash, sku, slug, selections jsonb, market, locale, indexable bool, merchant_feed_enabled bool, canonical_url, price_snapshot_id nullable, created_at) — **the curated commercial/SEO variants.** This is the deliberate exception to "don't persist variants": only a hand-picked or rule-selected set (e.g. *Oval Solitaire · 18k White Gold · 1ct Lab*, *Hidden Halo · 18k Yellow · Oval Lab*) gets a stable `sku` + `slug` + canonical URL so schema, sitemaps and the Merchant feed have something durable to point at. Everything else stays computed-on-demand and `noindex`. `sku` here == schema variant `sku` == feed `id`; `template.code` == schema `productGroupID` == feed `item_group_id`.

## Group O — Merchant feeds
- **merchant_feeds**(id, tenant_id, channel[google], market, locale, currency, url, generated_at)
- **merchant_feed_items**(id, merchant_feed_id, offer_id, item_group_id, title, description, link, image_link, additional_image_link jsonb, price, sale_price, availability[in_stock|out_of_stock|preorder|backorder], availability_date nullable, condition, brand nullable, gtin nullable, mpn nullable, identifier_exists bool, google_product_category, material, color, size (ring size), custom_label_0..4, shipping_label nullable, return_policy_label nullable)
  - **Availability mapping (important):** Merchant Center `availability` only accepts `in_stock` / `out_of_stock` / `preorder` / `backorder`. **`MadeToOrder` is a schema.org value, not a feed value** — use it in JSON-LD, but map made-to-order rings to a feed value (typically `preorder` or `backorder` **with** `availability_date` up to a year out, or `in_stock` if you can fulfil normally). Never put `MadeToOrder` in the feed.
  - **identifier_exists:** for custom/made-to-order rings with no GTIN/MPN/manufacturer brand, set `identifier_exists=false` and omit `gtin`/`mpn`/`brand`. Never send a placeholder or internal SKU as a GTIN. If you *do* have a brand/identifier, set `true` and include it (a mismatch causes disapproval).
- **merchant_feed_rules**(id, tenant_id, rule jsonb)
- **merchant_category_mappings**(id, tenant_id, internal_category_id, google_product_category)

## Group P — System / audit
- **jobs**(id, tenant_id, kind[price_refresh|fx_refresh|feed_sync|render|import|feed_gen|sitemap_gen], status, payload jsonb, run_at, finished_at, error)
- **audit_log**(id, tenant_id, actor, action, entity_type, entity_id, before jsonb, after jsonb, created_at)
- **price_refresh_log**(id, tenant_id, source, metal_or_pair, value, fetched_at, ok bool)

---

## Key relationships (summary)
- `product_templates` 1—N `template_components`, N—N `option_groups` (via `template_option_groups`).
- `option_groups` 1—N `options`; `options` map to `media_assets` via `option_media_map` for image-swap.
- `rule_sets` (per template, versioned) 1—N `rules`; a `quote`/`order_item` records the `rule_set_version` used (plus template/formula/density/labor/margin/vat versions — see below).
- `metals`/`metal_purities`/`metal_colors` → `material_options` (valid combos) → `metal_densities` → used by CAD/Weight; `metal_price_snapshots` feed the Pricing Engine.
- `price_snapshots` are attached to `quotes` and `order_items` and are **immutable** and self-contained: a price is reproducible from its snapshot alone because it pins every drifting input (formula, rule-set, density, labor, margin, VAT versions + the exact `metal_price_snapshot_id` and `fx_rate_snapshot_id`).
- `indexable_configurations` is the only place curated variants persist; `orders`/`quotes` still store their own `configuration` jsonb + snapshot independently of whether the config is indexable.
- `orders` → `order_items` → `production_jobs` → `production_steps`/`qc_*`/`hallmark_records`/`shipments`.
- `bespoke_requests` → `bespoke_revisions`/`bespoke_deposits` → on approval, becomes an `order`.
- Every `seo_pages`/`merchant_feed_items` row derives from a template/category/configuration; `productGroupID` in schema == `item_group_id` in feed == template code.

## Indexing & integrity notes
- Composite indexes on `(tenant_id, …)` for every hot query; partial index on `orders(status)`, `production_steps(status)`.
- Unique: `(tenant_id, template_id, code)`, `(tenant_id, slug, locale, market)` for SEO pages, `(merchant_feed_id, offer_id)`, `(tenant_id, sku)` and `(tenant_id, template_id, config_hash, market, locale)` for `indexable_configurations`.
- Foreign keys enforced; money columns `NOT NULL` with currency; `price_snapshots.inputs` validated on write.
- Consider Postgres RLS keyed on `tenant_id` when SaaS goes live.
