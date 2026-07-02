"""Public headless API — /api/v1 (docs/spec/13 §1–2).

The storefront (and any future client) consumes only this surface. The hot
path (/config/price) reads caches only: metal/FX come from snapshot rows
refreshed by background jobs, and full responses are cached in Redis keyed by
config_hash, which embeds the latest source stamp so a metal refresh
invalidates it naturally. Deterministic; target < 300 ms p95.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import DbSession
from app.models import (
    Category,
    MetalPriceSnapshot,
    Option,
    OptionGroup,
    ProductTemplate,
    RingSize,
    RuleSet,
    TemplateComponent,
    TemplateOptionGroup,
)
from app.services.config_service import (
    cache_price,
    cached_price,
    compute_config_hash,
    decode_share_state,
    encode_share_state,
)
from app.services.pricing_resolver import resolve_and_price
from app.tenancy.context import get_current_tenant

router = APIRouter(prefix="/api/v1", tags=["public"])


# --- Catalog (public, read) ---


@router.get("/categories")
async def list_categories(session: DbSession) -> list[dict]:
    tid = get_current_tenant().tenant_id
    rows = (
        (
            await session.execute(
                select(Category).where(
                    Category.tenant_id == tid, Category.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    return [{"id": str(c.id), "name": c.name, "slug": c.slug, "type": c.type} for c in rows]


@router.get("/templates")
async def list_templates(
    session: DbSession, category: str | None = None, style: str | None = None
) -> list[dict]:
    tid = get_current_tenant().tenant_id
    query = select(ProductTemplate).where(
        ProductTemplate.tenant_id == tid,
        ProductTemplate.status == "active",
        ProductTemplate.deleted_at.is_(None),
    )
    if category:
        query = query.join(Category, Category.id == ProductTemplate.category_id).where(
            Category.slug == category
        )
    if style:
        query = query.where(ProductTemplate.style == style)
    rows = (await session.execute(query)).scalars().all()
    return [
        {"id": str(t.id), "code": t.code, "name": t.name, "style": t.style} for t in rows
    ]


@router.get("/templates/by-code/{code}")
async def get_template_by_code(code: str, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    template = (
        await session.execute(
            select(ProductTemplate).where(
                ProductTemplate.tenant_id == tid,
                ProductTemplate.code == code,
                ProductTemplate.status == "active",
                ProductTemplate.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "template not found")
    return await get_template(template.id, session)


async def _template_or_404(session: AsyncSession, template_id: uuid.UUID) -> ProductTemplate:
    tid = get_current_tenant().tenant_id
    template = (
        await session.execute(
            select(ProductTemplate).where(
                ProductTemplate.tenant_id == tid,
                ProductTemplate.id == template_id,
                ProductTemplate.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if template is None or template.status != "active":
        raise HTTPException(404, "template not found")
    return template


async def _option_groups_payload(session: AsyncSession, template_id: uuid.UUID) -> list[dict]:
    links = (
        await session.execute(
            select(TemplateOptionGroup, OptionGroup)
            .join(OptionGroup, OptionGroup.id == TemplateOptionGroup.option_group_id)
            .where(TemplateOptionGroup.template_id == template_id)
            .order_by(TemplateOptionGroup.step_order)
        )
    ).all()
    payload = []
    for link, group in links:
        options = (
            (
                await session.execute(
                    select(Option)
                    .where(Option.option_group_id == group.id, Option.is_active.is_(True))
                    .order_by(Option.sort)
                )
            )
            .scalars()
            .all()
        )
        payload.append(
            {
                "key": group.key,
                "name": group.name,
                "ui_type": group.ui_type,
                "step_order": link.step_order,
                "is_required": link.is_required,
                "default_option_code": next(
                    (o.code for o in options if o.id == link.default_option_id), None
                ),
                "options": [
                    {"code": o.code, "label": o.label, "value": o.value} for o in options
                ],
            }
        )
    return payload


@router.get("/templates/{template_id}")
async def get_template(template_id: uuid.UUID, session: DbSession) -> dict:
    template = await _template_or_404(session, template_id)
    components = (
        (
            await session.execute(
                select(TemplateComponent)
                .where(TemplateComponent.template_id == template.id)
                .order_by(TemplateComponent.sort)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(template.id),
        "code": template.code,
        "name": template.name,
        "style": template.style,
        "is_bespoke_base": template.is_bespoke_base,
        "components": [
            {"kind": c.kind, "name": c.name, "metal_assignable": c.metal_assignable}
            for c in components
        ],
        "option_groups": await _option_groups_payload(session, template.id),
    }


@router.get("/templates/{template_id}/option-groups")
async def get_template_option_groups(template_id: uuid.UUID, session: DbSession) -> list[dict]:
    template = await _template_or_404(session, template_id)
    return await _option_groups_payload(session, template.id)


@router.get("/templates/{template_id}/rules")
async def get_template_rules(template_id: uuid.UUID, session: DbSession) -> dict:
    """Published rule set for client-side hinting; the server stays authority."""
    template = await _template_or_404(session, template_id)
    tid = get_current_tenant().tenant_id
    rule_set = (
        await session.execute(
            select(RuleSet)
            .where(
                RuleSet.tenant_id == tid,
                RuleSet.template_id == template.id,
                RuleSet.status == "published",
            )
            .order_by(RuleSet.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rule_set is None:
        return {"version": None, "rules": []}
    await session.refresh(rule_set, ["rules"])
    return {
        "version": rule_set.version,
        "rules": [
            {
                "type": r.type,
                "scope": r.scope,
                "condition": r.condition,
                "effect": r.effect,
                "message": r.message,
            }
            for r in rule_set.rules
        ],
    }


@router.get("/ring-sizes")
async def list_ring_sizes(session: DbSession, standard: str = "EU") -> list[dict]:
    tid = get_current_tenant().tenant_id
    rows = (
        (
            await session.execute(
                select(RingSize)
                .where(RingSize.tenant_id == tid, RingSize.standard == standard)
                .order_by(RingSize.circumference_mm)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "standard": r.standard,
            "label": r.label,
            "diameter_mm": str(r.diameter_mm),
            "circumference_mm": str(r.circumference_mm),
        }
        for r in rows
    ]


# --- Configuration & pricing (hot path) ---


class ConfigRequest(BaseModel):
    template_id: uuid.UUID
    selections: dict[str, Any] = Field(default_factory=dict)
    market: str = "NL"
    locale: str = "en"
    currency: str = "EUR"


@router.post("/config/validate")
async def config_validate(payload: ConfigRequest, session: DbSession) -> dict:
    template = await _template_or_404(session, payload.template_id)
    tid = get_current_tenant().tenant_id
    resolved = await resolve_and_price(
        session, tid, template, payload.selections, market=payload.market,
        currency=payload.currency,
    )
    v = resolved.validation
    return {
        "status": v.status,
        "reasons": v.reasons,
        "visible_groups": v.visible_groups,
        "required_groups": v.required_groups,
        "modifiers": v.modifiers,
    }


async def _latest_source_stamp(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    """One indexed query: any metal refresh moves this stamp and thereby

    invalidates every cached price (conservative and correct).
    """
    latest = (
        await session.execute(
            select(func.max(MetalPriceSnapshot.fetched_at)).where(
                MetalPriceSnapshot.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    return latest.isoformat() if latest else "no-metal-snapshots"


@router.post("/config/price")
async def config_price(payload: ConfigRequest, session: DbSession) -> dict:
    template = await _template_or_404(session, payload.template_id)
    tid = get_current_tenant().tenant_id

    stamp = await _latest_source_stamp(session, tid)
    config_hash = compute_config_hash(
        tid, template.id, payload.selections, payload.market, payload.currency, [stamp]
    )
    cached = await cached_price(config_hash)
    if cached is not None:
        return cached

    resolved = await resolve_and_price(
        session, tid, template, payload.selections, market=payload.market,
        currency=payload.currency,
    )
    v = resolved.validation
    price = resolved.price

    response: dict[str, Any] = {
        "validity": {
            "status": price.status if price else v.status,
            "reasons": (price.reasons if price else []) + v.reasons,
            "degraded": price.degraded if price else False,
        },
        "config_hash": config_hash,
    }
    if price is not None:
        response["itemized"] = price.itemized
        if price.total_minor is not None:
            response["total"] = {"amount_minor": price.total_minor, "currency": price.currency}
        if price.range_min_minor is not None and price.range_max_minor is not None:
            response["estimated_range"] = {
                "min": price.range_min_minor,
                "max": price.range_max_minor,
                "currency": price.currency,
            }
        response["non_returnable"] = price.non_returnable
        if price.snapshot is not None:
            response["weight"] = price.snapshot["weight"]

    await cache_price(config_hash, response)
    return response


class ShareRequest(ConfigRequest):
    pass


@router.post("/config/share")
async def config_share(payload: ShareRequest, session: DbSession) -> dict:
    await _template_or_404(session, payload.template_id)
    code = encode_share_state(
        payload.template_id, payload.selections, payload.market, payload.locale
    )
    # The storefront owns the display URL; the engine returns the state code
    # and a canonical API path (share pages are noindex — docs/spec/11).
    return {"code": code, "share_url": f"/api/v1/config/{code}"}


@router.get("/config/{code}")
async def config_resolve(code: str, session: DbSession) -> dict:
    state = decode_share_state(code)
    if state is None:
        raise HTTPException(404, "unknown configuration")
    try:
        template_id = uuid.UUID(state["t"])
    except ValueError:
        raise HTTPException(404, "unknown configuration") from None
    payload = ConfigRequest(
        template_id=template_id,
        selections=state["s"],
        market=state.get("m", "NL"),
        locale=state.get("l", "en"),
    )
    price = await config_price(payload, session)
    return {
        "template_id": str(template_id),
        "selections": state["s"],
        "market": payload.market,
        "locale": payload.locale,
        "price": price,
    }
