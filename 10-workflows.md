# 10 — Workflows (Orders, Bespoke, Prototype, Production, Deposits)

## 1. Made-to-order (configured ring)
```
configure ring → live price → add to cart → checkout (full or deposit)
→ price snapshot LOCKED → order created → production job created
→ CAD/spec generated → factory assigned
→ casting → stone setting → polishing → hallmarking (if required) → QC
→ shipment → delivered
```
Customer-visible status tracking throughout. Engraved/special-engraving items are flagged non-returnable before purchase.

## 2. Bespoke (customer idea → made)
```
Step 0 (FREE): upload photo/sketch/reference OR AI-Designer prompt
   → structured brief + rough price RANGE + inspiration render
Step 1 (PAID): non-refundable DESIGN DEPOSIT (credited to final)
   → CAD concept + 1 realistic render + 1–2 revision rounds
Step 2: customer approves OR requests revision (bounded rounds)
Step 3: final price computed → PRODUCTION DEPOSIT to start
   → production; optional plastic prototype before final
Step 4: BALANCE before shipment → hallmark/QC → ship
```
Don't make bespoke free end-to-end — it attracts low-quality leads. Free rough estimate filters interest; paid design deposit filters serious buyers.

## 3. Plastic prototype (separate, priced service)
```
lock/approve configuration → prototype order → export STL/CAD
→ factory prints gray/plastic model → QC dimensions → ship prototype
→ customer approves OR requests changes → convert to final production order
```
Strong conversion tool for high-ticket rings; can be credited above an order-value threshold.

## 4. Ready-made (LATER)
```
supplier/factory import → normalize (category/material/stone) → fixed price
→ stock availability → publish → order → ship from stock/supplier/factory
```
Drives SEO traffic, gifts, entry-price and trust. Schema-ready now, not in MVP.

## 5. Deposit model (recommended — based on verified benchmarks)

| Stage | Amount | Refundable? | Credited? |
|---|---|---|---|
| Initial estimate | €0 | — | — |
| **Design/CAD deposit** | **€250** (high-end) or €150 (entry) | **Non-refundable** | **Yes, to final** |
| Production deposit | **50%** (or 70% for special/expensive stone sourcing) | Per terms | Applied to total |
| Balance | remainder before shipment | — | — |
| Plastic prototype | €25–€75 (or free/credited above threshold) | Per terms | Optional credit |

Rationale from market data: design fees commonly $200–$750 (often $250) and credited; production deposits commonly 50% (some 70–75%) with balance before shipment; for high-value/special stone sourcing, take a larger upfront or full stone payment. Choose **€250** design deposit for the high-end positioning (filters buyers, signals premium). Store deposit rules in `design_fees` / `deposits`; make them configurable per market/tenant.

Returns/changes: bespoke and engraved items are **final sale / non-returnable**; made-to-order change requests after production starts may carry a restocking fee (configurable). Surface all of this pre-purchase.

## 6. Production status lifecycle (canonical)
`pending → cad → awaiting_approval → casting → stone_setting → polishing → hallmarking → qc → shipped`
- `hallmarking` is conditional on the compliance flag (see `12`). If not required, step is auto-skipped with `not_required`.
- Each transition timestamped in `production_steps`; QC photos + hallmark record required before `shipped`.

## 7. Factory spec sheet (generated per job)
Bundle attached to `production_jobs`:
- Template + resolved configuration (`order_configurations.resolved_spec`)
- CAD/render references, engraving text, ring size (with standard), metal + karat + color + finish
- Stone spec (type, shape, carat, color, clarity, cut, cert if any) or specific `supplier_stones` row
- Estimated weight + waste/size factors; place to record **actual** weight
- Hallmark requirement (required?, fineness, responsibility mark, assay office)
- QC checklist

## 8. Payments across a bespoke order (example, Gem-Breakfast-style)
```
€250 design deposit (credited)
→ 50–75% production deposit on design approval
→ remaining balance before shipping
```
All amounts and the price snapshot are frozen at the point each is agreed; `deposits.credited_to_order_id` links credited deposits to the final order.

## 9. Test cases
1. Made-to-order: deposit locks a snapshot; production job + spec sheet generated with hallmark flag.
2. Bespoke: free range → €250 non-refundable-but-credited design deposit → CAD/render → approval → production deposit → balance → ship.
3. Prototype ordered mid-bespoke: STL exported, printed, shipped, then converted to final order with credit if above threshold.
4. Hallmark-required item cannot reach `shipped` without a `hallmark_records` entry marked `applied`.
5. Engraved item is non-returnable and says so before payment.
6. A credited design deposit reduces the final order total and is traceable via `deposits.credited_to_order_id`.
