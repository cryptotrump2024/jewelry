# 11 — SEO / GEO Engine

SEO/GEO is **engine output from the source of truth**, not frontend hand-work. The configurator data, structured data, Merchant feed, localized pages and AI-search content all derive from the same catalog.

"GEO" is dual-purpose here:
- **Generative Engine Optimization** — visibility in Google AI Overviews/AI Mode, ChatGPT/Perplexity-style answers.
- **Geographic optimization** — NL → EU → worldwide, multi-language, multi-currency, local trust/tax/shipping/hallmarking, country landing pages.

Google's guidance: AI-search visibility still rests on **strong SEO fundamentals** — crawlable pages, clean technical structure, helpful people-first content, and good ecommerce/product data. There is **no special required "AI markup" or `llms.txt`** for Google AI features. So: do SEO excellently; that *is* GEO for Google.

## 1. The indexing problem (critical)
A ring configurator can produce millions of combinations (metal × color × shape × carat × color × clarity × size × engraving × side stones). **Do not index them all** — it creates duplicate/thin content and wastes crawl budget.

**Index (curated landing pages):**
- Engagement-ring category; by **style** (solitaire, halo, hidden-halo, pavé, three-stone); by **shape** (oval, round, pear…); by **stone type** (lab, natural); by **metal** (white/yellow/rose gold, platinum); by **carat** (1 ct); plus custom/bespoke/designer/price-calculator pages.

**Do not index:**
- Every ring size, every engraving, every micro price change, every random configurator state, internal quote/session URLs.

Control this with `seo_indexing_rules` (pattern → indexable + reason) and `canonical` rules. Shareable configurator URLs use `noindex` (still shareable, just not crawlable). Real variant pages (metal/stone combos we *choose* to index) are indexable and canonicalized.

## 2. Structured data (verified current Google guidance)

Use **`ProductGroup`** for a template + **`Product`** + **`Offer`** for indexable variants.

- `variesBy` accepts only Google-supported values: **color, size, material, pattern, suggestedAge, suggestedGender** (full schema.org URIs). For rings, the real variant axes are **material** (metal) and (arguably) **color** (metal color); **carat/stone** can be modeled as material/variant naming.
- **Ring size and engraving are add-ons, not variants** — do NOT model them as `ProductGroup` variants (engraving is personalization).
- `productGroupID` is required-in-practice and **must equal** the Merchant feed `item_group_id` and your template code.
- Each variant `Product` needs a **unique sku/gtin** and an `offers.url` that **deep-links to that variant** (query params), with a real price (variant offer price must not be 0).
- Single-page implementation → nest variants under `hasVariant` and keep **one canonical** ProductGroup URL. Multi-page → each page self-contained, variants linked via `isVariantOf`/`inProductGroupWithID`. Don't mix approaches on one page.
- Structured data must **match visible content** and be **server-rendered**.

### Jewelry example (nested, single-page)
```json
{
  "@context": "https://schema.org/",
  "@type": "ProductGroup",
  "name": "Oval Solitaire Engagement Ring",
  "description": "Made-to-order oval solitaire with lab or natural diamond, in gold or platinum.",
  "url": "https://example.com/en-eu/oval-solitaire-engagement-ring",
  "brand": { "@type": "Brand", "name": "<BrandName>" },
  "productGroupID": "OVAL-SOLITAIRE",
  "variesBy": ["https://schema.org/material", "https://schema.org/color"],
  "hasVariant": [
    {
      "@type": "Product",
      "sku": "OVAL-SOLITAIRE-18KWG-LAB-1CT",
      "name": "Oval Solitaire — 18k White Gold, 1ct Lab Diamond",
      "material": "18k white gold",
      "color": "white",
      "image": "https://example.com/img/oval-18kwg-lab-1ct.jpg",
      "offers": {
        "@type": "Offer",
        "url": "https://example.com/en-eu/oval-solitaire-engagement-ring?metal=18kwg&stone=lab&carat=1",
        "price": "1890.00",
        "priceCurrency": "EUR",
        "availability": "https://schema.org/MadeToOrder",
        "hasMerchantReturnPolicy": { "@id": "#return-policy" },
        "shippingDetails": { "@id": "#shipping" }
      }
    }
  ]
}
```
Also emit, where visible: `Organization`/`LocalBusiness`, `BreadcrumbList`, `FAQPage` (only when Q&A is visible on the page), `ImageObject`, and `AggregateRating`/`Review` (only if real and shown). Engine endpoint `GET /seo/schema?template_id=…&locale=…&market=…` returns the JSON-LD; storefront injects it server-side.

## 3. Google Merchant Center feed
Even before ads, prepare feeds (free listings + future ads). Correct, consistent data avoids disapprovals.

`merchant_feed_items` fields: `id` (=variant sku), `item_group_id` (=`productGroupID`=template code), `title`, `description`, `link`, `image_link`, `additional_image_link`, `price`, `sale_price`, `availability`, `availability_date`, `condition`, `brand`, `gtin`/`mpn` (as available), `identifier_exists`, `google_product_category`, `material`, `color`, `size` (ring size where relevant), `custom_label_0..4`, `shipping_label`, `return_policy_label`.

**Two corrections that prevent disapprovals (feed ≠ schema):**
- **`availability` is not schema.org.** Merchant Center accepts only `in_stock`, `out_of_stock`, `preorder`, `backorder`. **Do not put `MadeToOrder` in the feed** — that's a schema.org value for JSON-LD only. Map made-to-order rings to `preorder` (or `backorder`) **with `availability_date`** (a date up to a year out), or `in_stock` if you fulfil normally. Keep these values in English regardless of locale; keep them matched to the landing page.
- **`identifier_exists` for custom rings.** Rings with no GTIN/MPN/manufacturer brand → set `identifier_exists=false` and **omit** `gtin`/`mpn`/`brand`. Never send an internal SKU as a GTIN. If a real brand/identifier exists, set `true` and include it — a mismatch (identifiers present but flagged false, or vice-versa) is a disapproval.

**Alignment rule (strong signal):** schema `productGroupID` == feed `item_group_id`, and each variant's schema `sku` == the feed item `id`. Keep feed and on-page data in lockstep (Google cross-references them).

**Where the stable IDs come from:** the durable `sku`/`slug`/`canonical_url` per curated variant live in the **`indexable_configurations`** table (see `05-data-model.md`, Group N). This is the deliberate, small exception to "don't persist variants" — only hand-picked commercial/SEO combinations (e.g. *Oval Solitaire · 18k White Gold · 1ct Lab*) get a row, a stable SKU and a canonical URL for schema + feed to point at. Every other configurator state stays computed-on-demand and `noindex`. This is curation, not SKU explosion.

## 4. Multi-language / multi-region
Use **distinct URLs per language/market** (not JS-only switching) + hreflang.

```
/nl-nl/verlovingsringen
/en-eu/engagement-rings
/de-de/verlobungsringe
/fr-fr/bagues-de-fiancailles
/en-us/engagement-rings
/en-gb/engagement-rings
```
- `hreflang_groups` + `hreflang_urls` produce reciprocal hreflang annotations (+ `x-default`).
- **hreflang value trap:** URL paths like `/en-eu/` are fine as *paths*, but `en-EU` is **not a valid hreflang value** — hreflang requires ISO 639-1 language alone (`en`) or language + ISO 3166-1 country (`en-NL`, `en-DE`, `en-US`). There is no "EU" country code. For a pan-European English page, annotate it as `en` (and/or list the specific countries) and use `x-default` for the fallback. The `hreflang_urls` table stores locale and market separately so the generator can emit valid values regardless of the URL path.
- Localized slugs, titles, descriptions, and **native-tone** copy (not literal MT). Store per (locale, market) in `seo_metadata` / `content_blocks`.
- Language expansion priority (per your strategy, targeting underserved languages for GEO/AI-citation advantage): beyond EN/DE — **French, Turkish, Vietnamese, Hindi, Japanese**; Tier 2: Indonesian, Arabic, Polish.
- Currency + VAT + shipping + return policy resolve per market (see `12`).

## 5. GEO / AI-search content
AI answers reward **unique, helpful, people-first** content — not recycled commodity copy. Build a content engine (`content_blocks`, `faq_blocks`, `answer_blocks`, `topic_clusters`, `seo_internal_links`):
- Buying guides; diamond education; **lab vs natural** explainer; metal comparison; ring-size guide; proposal guides; **bespoke process**; CAD/prototype explainer; country-specific delivery & hallmark pages; per-product FAQs; expert notes per style.
- `answer_blocks` = concise, quotable answers to real buyer questions (good for AI extraction), backed by supporting detail.
- These pages **connect to the configurator** — they're not thin SEO pages; each links to the relevant "design your own" entry.

### Priority landing/GEO pages (MVP)
1. Custom engagement rings 2. Bespoke engagement rings 3. Lab-diamond engagement rings 4. Natural-diamond engagement rings 5. Oval engagement rings 6. Solitaire engagement rings 7. Hidden-halo engagement rings 8. White-gold engagement rings 9. Platinum engagement rings 10. Engagement-ring price calculator 11. Engagement-ring configurator 12. Design your own engagement ring 13. Engagement-ring CAD & 3D prototype service 14. Lab vs natural (comparison) 15. Best metal for engagement rings.

## 6. Controlled taxonomy (MVP)
```
Product type: Engagement ring
Styles: solitaire, hidden-halo, halo, pavé, three-stone, toi-et-moi, vintage, modern, minimalist, bespoke
Stone shapes: round, oval, pear, princess, emerald, cushion, marquise, asscher, radiant
Stone types: lab diamond, natural diamond (sapphire/ruby/emerald LATER)
Metals: 14k/18k (yellow/white/rose), 20k, 22k, platinum 950, silver 925
```
This vocabulary drives options, rules, URLs, schema, feed attributes and internal links — one source, everywhere.

## 7. Engine SEO endpoints (headless)
```
GET /seo/page-data?url=/en-eu/oval-engagement-rings
GET /seo/schema?template_id=123&locale=en&market=eu
GET /seo/sitemap?kind=products|pages|images|localized
GET /seo/hreflang-group/{page_id}
GET /merchant/feed/google?market=eu&locale=en
GET /content/answer-blocks?topic=lab-diamond-engagement-rings
```
SEO is generated centrally; the storefront just renders what the engine returns (server-side).

## 8. Product-page SEO structure (per template)
`H1` (e.g. "Oval Solitaire Engagement Ring") → short human intro → configurator (metal/diamond/carat/size/engraving) → trust blocks (made-to-order, CAD-checked, optional 3D prototype, hallmarked metals, lab/natural options) → FAQ (choose lab/natural? see render first? how is price calculated? prototype? production time?) → JSON-LD (ProductGroup + variants + Offer + BreadcrumbList + FAQPage).

## 9. Test cases
1. Template page emits valid ProductGroup+Product+Offer (passes Rich Results Test); `productGroupID` == feed `item_group_id`.
2. Configurator share URLs are `noindex`; curated variant/landing pages are indexable + canonical.
3. Sitemaps include pages/products/images/localized; exclude session/quote URLs.
4. hreflang set is reciprocal with `x-default`; localized slugs correct.
5. Merchant feed validates; variant `id` matches schema `sku`; curated variant rows come from `indexable_configurations`; no 0-price variant offers.
6. Feed `availability` is one of in_stock/out_of_stock/preorder/backorder (never `MadeToOrder`); preorder/backorder rows carry `availability_date`.
7. Custom rings send `identifier_exists=false` with no gtin/mpn/brand; no internal SKU is sent as a GTIN.
8. FAQ JSON-LD only emitted when Q&A is visible on the page.
