# 12 — Compliance: Hallmarking, VAT, Returns, GDPR

Not an afterthought. Hallmarking is a **legal gate on selling** precious-metal jewelry in NL/EU, and it directly affects your Asia-import supply chain.

## 1. Dutch/EU hallmarking (Waarborgwet)

**Law:** In the Netherlands, precious-metal items must carry a hallmark **before being sold or promoted to consumers** (Waarborgwet). Enforced by two appointed assay offices: **WaarborgHolland** and **Edelmetaal Waarborg Nederland (EWN)**.

**Mandatory weight thresholds (hallmark required at/above):**
| Metal | Threshold |
|---|---|
| Gold | **1 gram** |
| Silver | **8 grams** |
| Platinum | **0.5 grams** |

Below threshold → exempt from mandatory hallmarking (many still mark voluntarily for trust).

**Dutch fineness (content) marks:** gold **585** (14k), **750** (18k), **833** (20k), **916** (22k); silver **925**; platinum **950**. Two marks are mandatory under the Waarborgwet: the **content/fineness mark** and the **responsibility mark (RM / verantwoordelijkheidsteken)** identifying who placed the item on the market.

**Waarborgwet 2019 platinum nuance (matters for Asia factories):** the current law added platinum **900** and **850** fineness marks, and **iridium no longer counts as platinum** in the fineness determination. An alloy of 930‰ Pt + 20‰ Ir was hallmarked Pt 950 under the old law but no longer qualifies — it assays below 950. If a factory quotes a Pt/Ir alloy, get the Pt-only content in writing, or the piece may fail NL assay at the promised fineness.

**Mixed-metal rule:** an item with different finenesses of the same metal is hallmarked at the **lowest** fineness present (e.g. a 14k ring with an 18k setting → hallmarked 14k). Base-metal + precious-metal composites can be marked only if the base metal is clearly visible and marked "METAL/MET".

**Imports (directly relevant — factories in Asia):** imported precious-metal jewelry must carry a hallmark **recognised in the Netherlands** before sale/promotion. Options:
1. Have items **assayed + hallmarked in NL** (WaarborgHolland / EWN) — you'll also need a registered **Responsibility Mark**; before hallmarking, the RM is applied to the item.
2. Rely on a **foreign hallmark recognised in NL**, incl. the **Common Control Mark (CCM)** under the Vienna Convention on Hallmarks (NL is a member) — CCM is recognised across member states.

Practical note: unmarked qualifying items may be held only briefly (≈4 weeks) and **cannot be shown/offered** to customers during that time. Build hallmarking into the production/QC workflow, not post-hoc.

### Engine implications
- `hallmark_records`(required, metal, fineness, responsibility_mark, assay_office[waarborg_holland|ewn|ccm|other], status[not_required|pending|applied], applied_at).
- Compute **`hallmark_required`** per order item from metal + **estimated/actual weight** vs thresholds (with the mixed-metal lowest-fineness rule).
- Production status `hallmarking` is conditional; an item that requires it **cannot reach `shipped`** without `status=applied` (or a recognised foreign/CCM mark on file).
- Store fineness marks in catalog data (585/750/833/916/925/950) and surface trust content ("hallmarked precious metals") on product pages.
- Register a **Responsibility Mark** operationally before selling NL-hallmarked goods.

*Disclaimer: implement to the assay offices' current official guidance; the above reflects published rules as of 2026 and is not legal advice. Confirm specifics with WaarborgHolland/EWN.*

## 2. VAT / tax (EU)
- **NL standard VAT** (21% as of 2026) generally applies to jewelry; store the rate + basis per market in `vat_rules` and freeze it in the price snapshot.
- **Cross-border B2C in the EU — the €10,000 threshold:** below **€10,000/yr** total intra-EU distance sales you may charge your home (NL) VAT; **above it you must charge the destination country's VAT rate**, declared via **OSS (One-Stop-Shop)**. Since you import/manufacture in Asia and sell across the EU, you'll cross this quickly — model VAT **per destination market**, not one global rate.
- **Non-EU sales:** typically VAT-exempt/export with local import duties/taxes at destination (customer-side). For low-value imports **IOSS** may apply. Handle as market rules.
- `price_includes_vat` controls inclusive (typical EU B2C display) vs exclusive pricing. Show the correct inclusive price per market.
- Keep VAT logic in `vat_rules` (per market/category), never hardcoded. Capture on the order/snapshot: `vat_registration_country`, `oss_enabled`, `ioss_enabled`, `customer_country`, `ship_from_country`, `ship_to_country`, `vat_place_of_supply`.

*Confirm current rates/thresholds with a Dutch tax adviser; VAT rules change and OSS thresholds matter.*

## 3. Returns & consumer rights (EU)
- EU distance-selling generally grants a **14-day withdrawal right**, **but** **custom-made/clearly personalised goods are exempt** (Art. 16 CRD) — bespoke and engraved rings can be sold as **final sale / non-returnable**.
- Encode returnability per item: engraving (special)/bespoke ⇒ `non_returnable = true`, surfaced **before** purchase (also feeds `hasMerchantReturnPolicy` in schema/feed).
- Made-to-order change/cancel after production starts may carry a **restocking fee** (configurable).
- Publish clear, market-specific return/warranty policies (`content_blocks`) and reference them in structured data/feed.

### 3a. Mandatory EU withdrawal button (in force since 19 June 2026)
Directive (EU) 2023/2673 added **Article 11a** to the Consumer Rights Directive. Since **19 June 2026** every trader selling online to EU consumers — including **non-EU traders targeting the EU** — must provide a clearly labelled, easy-to-find, continuously available **electronic withdrawal function** for any contract that carries a statutory withdrawal right. This is not the same as your commercial return policy; it's a legal mechanism and must be built as one.

Requirements to implement:
- A prominent function labelled **"withdraw from contract here"** (or unambiguous equivalent), available throughout the withdrawal period, no login-wall or dark patterns.
- A **two-step flow**: (1) withdrawal declaration (name + order identification + contact for confirmation), then (2) a **"confirm withdrawal"** step.
- An **acknowledgement of receipt on a durable medium** (e.g. email) **without undue delay**, including the withdrawal content + **date and time**.
- Refund within 14 days of receiving the goods back (or proof of return).

Scope nuance (the reason this coexists with "final sale" above): the **button is required for eligible goods** (e.g. future ready-made stock, standard made-to-order where a withdrawal right exists), while **bespoke/personalised/engraved items are exempt from the withdrawal right** and so from the flow. Failing to provide the function can **extend the withdrawal window to 12 months + 14 days** and expose the business to fines (up to 4% of turnover / €2M in some states).

Engine support: `withdrawal_requests` table (Group K) records the two-step flow + acknowledgement; per-item `eligibility_status` is derived from `non_returnable`. Implementation lands in **Phase 8** (orders/compliance).

*Directive; national transposition (e.g. Germany §356a BGB, NL implementation) may vary in wording/placement — confirm the NL specifics with counsel. Not legal advice.*

## 4. GDPR / privacy
- Lawful basis + consent records (`consents`); cookie/marketing consent gating analytics.
- Data minimisation; **no raw card data** (PSP tokenization only); encrypt PII at rest; signed URLs for private assets.
- Support **data export & erasure**; retain order/tax records per legal retention while honouring erasure of non-required PII.
- Per-tenant data isolation (SaaS) — a tenant's customer data never leaks across tenants.

## 5. Other
- **Product/consumer safety & materials disclosure:** accurate metal/stone/fineness claims (mis-describing precious metal is an offence under the Waarborgwet).
- **Diamond provenance:** where feeds provide it (Nivoda etc.), retain origin/cert data for trust and any Kimberley-style expectations.
- **Insurance/valuation:** the immutable price snapshot + spec doubles as a valuation basis for the customer.

## 6. Compliance checkpoints in the build
1. Order item computes `hallmark_required` from metal + weight + thresholds (mixed-metal lowest-fineness).
2. `hallmarking` production step blocks `shipped` until satisfied (NL mark applied or recognised CCM/foreign mark on file).
3. VAT resolved per destination market; frozen in snapshot; correct inclusive display.
4. Bespoke/engraved items flagged non-returnable pre-purchase; policy shown + in schema/feed.
5. **Withdrawal function present** (two-step + durable-medium acknowledgement) for withdrawal-eligible items; `withdrawal_requests` wired; exempt items correctly excluded.
6. VAT: OSS/IOSS fields captured; destination-VAT applied once the €10,000 intra-EU threshold is crossed.
7. Consent + erasure flows implemented; no card data stored; assets access-controlled.

## 7. Compliance operational checklist (do before selling)
- [ ] Register a **Responsibility Mark** (RM) with an assay office.
- [ ] Choose **WaarborgHolland** or **EWN**; decide NL assay vs recognised foreign/**CCM** mark for Asia imports.
- [ ] Store each item's hallmark certificate/photo against `hallmark_records`.
- [ ] **Block publication** of hallmark-required *ready-made* stock that isn't yet legally sellable (made-to-order differs — the item doesn't exist yet, so gate at production/ship, not at listing).
- [ ] **Block shipping** if a required `hallmark_records` entry isn't `applied`.
- [ ] Register for **VAT OSS** if selling cross-border EU B2C; confirm rates/thresholds with a Dutch tax adviser.
- [ ] Ship the **EU withdrawal function** before taking EU consumer orders for eligible goods.
- [ ] Publish market-specific return/warranty/shipping/deposit policy content.
