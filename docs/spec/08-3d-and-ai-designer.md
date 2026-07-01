# 08 — 3D Preview & AI Jewelry Designer

Three visual layers, three purposes. **Only structured configuration data is the source of truth for price and spec.** Images (AI or 3D) are for inspiration and conversion.

| Layer | Purpose | Tier |
|---|---|---|
| Static-angle images | Trust/conversion | **[LAUNCH]** |
| AI render (per config) | Sales/inspiration preview | **[LAUNCH]** |
| Production CAD | Manufacturing truth (internal/factory) | **[LAUNCH]**, internal only |
| Interactive 3D | Advanced live configurator | **[POST]** |
| **AI Jewelry Designer** (prompt/image → intent → match) | Guided design entry | **[POST]** |

Tier note: AI **renders** (turning a chosen config into a pretty image) ship at launch. The conversational **AI Jewelry Designer** (§4) is **post-launch** — it depends on a stable catalog/rules/pricing core to match against, so don't build it in the first release.

Source of truth: `Template + options + rules + CAD volume/weight + stone data + pricing formula + factory spec`. **Not** the AI image.

## 1. MVP visual pipeline (AI + static)
- **Static-angle images** per template and, where useful, per key option (metal color, shape). Bound to options via `option_media_map` for image-swap on selection (DiamondsByMe-style).
- **AI renders** generated per configuration for inspiration; queued via `render_jobs`, stored in `media_assets` (kind `ai_render`), admin-approvable. Keyed by `config_hash` so identical configs reuse a render.
- Renders/images are cosmetic only; a mismatch between render and spec never changes the order — the resolved spec governs production.

## 2. Interactive 3D (LATER — designed for now)
When the engine is stable, add real-time 3D:
- **Stack**: Three.js / React Three Fiber; **glTF/GLB** assets (single binary, PBR materials, animations). Keep assets < 4–5 MB; Draco-compress; lazy-load variant textures; reduce polys/shadows on mobile.
- **Material/mesh mapping**: options map to meshes and PBR materials in `future_3d_assets.material_map` / `mesh_map` — metal color = material swap; stone type/shape = mesh/material swap; component visibility toggles (halo, side stones).
- **Diamond rendering** is hard (refraction/dispersion). Options: hand-tuned shaders, or a specialized SDK — **iJewel3D** (three.js/threepipe-based: viewer web component, diamond rendering modules, HDR editor, batch render) or platforms like **Threekit/Zakeke/Salsita** if buying beats building.
- **Live price on 3D change** reuses the exact same `POST /config/price` path — 3D is just another client of the engine.
- **AR try-on** even later (WebXR / `model-viewer` / SDK try-on).

## 3. Render service (for AI/static generation)
- Deterministic renders of approved templates/configs can be produced with a headless renderer (Blender/managed farm) or the 3D SDK's batch tool; store outputs as `media_assets`, reference by `config_hash`.
- Generation is a queued background job; the storefront shows a placeholder/last-good until ready.

## 4. AI Jewelry Designer

### What it is (and isn't)
Per the 2026 market: **AI generates concept/intent and inspiration renders; it does NOT produce manufacturable CAD.** Correct flow = design in AI until concept approved → then human builds production CAD (Rhino/MatrixGold/3Design). Our AI Designer therefore outputs **structured design intent + inspiration render + price range + template match**, and always hands off to human/CAD before production.

### Flow
```
Customer input:  prompt ("modern white-gold oval lab-diamond ring, hidden halo, thin band")
                 and/or reference image upload
        │
        ▼
LLM extraction → structured design intent:
{
  product_type: "engagement_ring",
  style: "modern",
  metal: { karat: 18, color: "white" },
  center_stone: { type: "lab_diamond", shape: "oval", carat: 1.5 },
  details: ["hidden_halo", "thin_band"],
  budget: optional
}
        │
        ▼
Rules + catalog match:
  - which templates match the intent?
  - which supplier stones / price-table entries match?
  - is it buildable now, or bespoke?
  - price range from the pricing engine
        │
        ▼
Customer sees:
  - matched template(s), preconfigured in the configurator
  - inspiration render (AI)
  - estimated price range
  - design notes / trade-offs
  - CTA: "Refine in configurator"  OR  "Start a bespoke request"
        │
        ▼
Human/CAD validation before any production (always).
```

### Implementation notes
- **Intent extraction**: LLM with a strict JSON schema (function-calling / structured output). Validate against the option vocabulary; unknown terms map to nearest option or flag for bespoke.
- **Image input**: extract style/metal/stone cues from an uploaded reference to seed the same intent object.
- **Matching**: score templates by intent overlap; if no close template, route to **bespoke** with the intent as the brief (`bespoke_requests.brief`).
- **Price range**: run the pricing engine across plausible option ranges → min/max; label clearly as an estimate.
- **Guardrails**: never promise manufacturability from AI output; never treat the AI render as the spec; keep the AI-vs-production separation explicit in copy and data.

## 5. Data touchpoints
- `render_jobs`, `media_assets` (ai_render/static_angle), `option_media_map`, `future_3d_assets` (later).
- AI Designer writes to `bespoke_requests.brief` (source `ai_designer`) or preloads a `configuration` for the configurator.
- Everything keyed by `config_hash` for reuse.

## 6. Test cases
1. Selecting rose→white gold swaps the preview asset instantly (MVP image-swap).
2. Identical configurations reuse the same cached render (no duplicate generation).
3. AI prompt returns a valid structured intent that loads into the configurator preconfigured.
4. An intent with no matching template opens a bespoke request pre-filled with the brief.
5. AI render is never used as the production spec — the factory job pulls `order_configurations.resolved_spec`.
6. (Later) Changing metal in 3D triggers a material swap and a live price update via the same pricing endpoint.
