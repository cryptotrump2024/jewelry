# 07 — Configurator & Rules Engine

Turns admin-defined data (templates, option groups, options, rules) into a validated, priced, previewable configuration. **No option or rule is hardcoded** — everything is data.

## 1. Model recap
- **Template** = a `ProductGroup` (e.g. "Oval Solitaire"). Has components + attached option groups (with step order + defaults) + a versioned rule-set + SEO fields + CAD/asset refs.
- **Option group** = a choice dimension (metal, purity, metal color, finish, stone type, stone shape, stone quality, carat, ring size, engraving, side stone, setting).
- **Option** = one value in a group (`metal=platinum_950`, `shape=oval`).
- **Configuration** = one selected option per (relevant) group. Becomes a `Product` variant in schema terms once it's a valid, indexable combination.

## 2. Configurator flow (engagement-ring MVP, data-driven order)
Step order comes from `template_option_groups.step_order`; below is the default:
1. Template/style
2. Metal (per-component if template allows head/shank differences)
3. Metal color
4. Center stone type (natural vs lab) — surface early; biggest price lever
5. Center stone shape
6. Carat
7. Diamond/gemstone quality (color/clarity/cut; default mid-tier e.g. G/SI, upgrades optional)
8. Side stones (only if template supports — rule-gated)
9. Setting/finish
10. Ring size
11. Engraving (add-on; returnability warning if special/engraved)
12. (Optional) request bespoke adjustment
13. (Optional) request plastic prototype
14. Add to cart / deposit

Start with **5–10 templates** (solitaire, hidden halo, halo, pavé, three-stone, plus a bespoke base). Don't launch hundreds.

## 3. Rule types (all evaluated by one engine)
| Type | Purpose | Example |
|---|---|---|
| **compatibility** | allow-list valid combos | this head type only with round/oval |
| **exclusion** | block invalid combos | silver ✕ (gold/platinum) in one piece; purity mixing |
| **requirement** | force a choice | carat > 0.30 ⇒ certificate required; shape ⇒ specific prong head |
| **conditional_visibility** | show/hide a group | side-stone group visible only if template supports it |
| **price_modifier** | surcharge/discount | special engraving surcharge; magic-size band multiplier |

Rules live in `rule_sets` (versioned per template) → `rules(type, scope, condition, effect, message)`.

### Condition/effect shape (JSON logic)
```json
{
  "type": "requirement",
  "scope": { "template_id": "…", "option_group": "carat" },
  "condition": { ">": [ { "var": "carat" }, 0.30 ] },
  "effect": { "require_option_group": "certificate" },
  "message": "Diamonds above 0.30 ct require a certificate selection."
}
```
```json
{
  "type": "exclusion",
  "scope": { "template_id": "…" },
  "condition": { "and": [
    { "in": [ { "var": "metal.shank" }, ["silver"] ] },
    { "in": [ { "var": "metal.head" }, ["gold","platinum"] ] }
  ]},
  "effect": { "block": true },
  "message": "Silver cannot be combined with gold or platinum in the same ring."
}
```
Use a small, safe JSON-logic evaluator (allow-list of operators; no arbitrary code). Keep it deterministic and unit-testable.

## 4. Evaluation algorithm
```
validate(config):
  load template, active rule_set (cached), option groups
  resolve per-component option values
  applicable = rules where scope matches config
  for r in applicable (sorted):
      if r.type in [compatibility, exclusion, requirement]:
          evaluate r.condition
          collect block/require outcomes + messages
      if r.type == conditional_visibility:
          compute visible/hidden groups
      if r.type == price_modifier:
          collect modifiers (passed to Pricing Engine)
  check manufacturability limits (template_manufacturability + factory_manufacturability)
  status =
      invalid          if any hard block, unmet requirement, or hard manufacturability breach
      quote_only       if valid but not firmly priceable — feed-only stone unavailable,
                       stale/missing price input, or requires_manual_cad_check
      purchasable      otherwise
  return { status, reasons[], visible_groups[], required_groups[], modifiers[] }
```
Status meanings are canonical in `06-pricing-engine.md` §6 (`purchasable` = exact price; `quote_only` = estimated range, no exact checkout; `invalid` = no price). Pricing runs for `purchasable`/`quote_only` only. Invalid returns actionable reasons so the UI can disable options and explain why.

**Rule-conflict priority.** When rules disagree, resolve deterministically: (1) hard `exclusion`/`block` always wins over anything permissive; (2) `requirement` next; (3) `conditional_visibility`; (4) `price_modifier` last (modifiers stack in `sort` order). Two blocks → both messages surface. A rule set that produces contradictory *requirements* (A requires B, B excludes A) is a config error caught by the rule simulator (see §9) before publish, not at runtime.

## 5. Configuration session
- Held in Redis keyed by session/config id; contains selected options + market/locale.
- `POST /config/validate` and `POST /config/price` are stateless w.r.t. the DB (read caches), read/write the session.
- **Shareable state**: encode the full selection into a URL query/param (e.g. base64 of the option map). Shareable ≠ indexable — indexability is decided separately (see `11-seo-geo-engine.md`).
- `config_hash` = stable hash of (template, resolved options, market, source timestamps) → used for price cache and render cache.

## 6. Defaults, upgrades and quality tiers
- Each group has a template default (`default_option_id`) so a fresh configurator shows a complete, priced ring immediately.
- Quality is modeled as ordered `stone_quality_grades`; UI offers "good/better/best" with live price deltas. Default mid-tier (e.g. G color / SI clarity), upgrades priced from the table.

## 7. Preview binding
- Each option can map to a preview asset via `option_media_map` (image-swap like DiamondsByMe) for MVP.
- Later, options map to meshes/materials in `future_3d_assets` for live 3D swaps (see `08`).
- Preview is cosmetic; it never affects price or spec.

## 8. Extensibility (why this scales beyond rings)
- New ring types / categories = new templates + option groups + rules; **no engine changes**.
- New metal/stone/finish = new options + density/price rows.
- New constraint = new rule row. Adding any of these needs no deploy (NFR-9).

## 9. Test cases
1. Fresh configurator loads a fully-defaulted, priced ring.
2. Selecting an incompatible metal disables the conflicting option with the rule's message.
3. Setting carat to 0.35 makes the certificate group required and blocks checkout until chosen.
4. A template without side-stone support never shows the side-stone group.
5. Special engraving both adds cost and flips `non_returnable`, shown before purchase.
6. Sharing a config URL reproduces the exact selection and price on load (subject to live spot).
7. Publishing a new rule-set version doesn't alter historical orders (they pin the old version).
8. **Rule simulator** flags contradictory rule sets (e.g. mutual require/exclude) at publish time, before they reach a customer.
9. A config breaching a manufacturability limit (e.g. band below min thickness) returns `invalid`, or `quote_only` flagged for manual CAD when borderline — never `purchasable`.
