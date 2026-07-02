"""SEO/feed endpoints (docs/spec/13 §9). Public reads + admin curation."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.admin_auth import require_admin
from app.api.routes import DbSession
from app.models import IndexableConfiguration, ProductTemplate
from app.services.seo import (
    build_jsonld,
    build_merchant_feed_xml,
    build_sitemap_xml,
    curate_configuration,
)
from app.tenancy.context import get_current_tenant

router = APIRouter(prefix="/api/v1", tags=["seo"])
admin_router = APIRouter(
    prefix="/admin/seo", tags=["admin-seo"], dependencies=[Depends(require_admin)]
)


@router.get("/seo/schema")
async def seo_schema(
    session: DbSession, template_id: uuid.UUID, market: str = "NL", locale: str = "en"
) -> dict:
    tid = get_current_tenant().tenant_id
    template = (
        await session.execute(
            select(ProductTemplate).where(
                ProductTemplate.tenant_id == tid, ProductTemplate.id == template_id
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "template not found")
    return await build_jsonld(session, tid, template, market=market, locale=locale)


@router.get("/seo/sitemap.xml")
async def sitemap(session: DbSession) -> Response:
    tid = get_current_tenant().tenant_id
    xml = await build_sitemap_xml(session, tid)
    return Response(content=xml, media_type="application/xml")


@router.get("/merchant/feed/google")
async def merchant_feed(
    session: DbSession, market: str = "NL", locale: str = "en"
) -> Response:
    tid = get_current_tenant().tenant_id
    xml = await build_merchant_feed_xml(session, tid, market=market, locale=locale)
    return Response(content=xml, media_type="application/xml")


class CurateInput(BaseModel):
    template_id: uuid.UUID
    selections: dict[str, Any] = Field(default_factory=dict)
    market: str = "NL"
    locale: str = "en"
    sku: str | None = None
    slug: str | None = None


@admin_router.post("/indexable-configurations", status_code=201)
async def curate(payload: CurateInput, session: DbSession) -> dict:
    tid = get_current_tenant().tenant_id
    template = (
        await session.execute(
            select(ProductTemplate).where(
                ProductTemplate.tenant_id == tid, ProductTemplate.id == payload.template_id
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "template not found")
    try:
        row = await curate_configuration(
            session,
            tid,
            template,
            payload.selections,
            market=payload.market,
            locale=payload.locale,
            sku=payload.sku,
            slug=payload.slug,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    await session.commit()
    return {
        "id": str(row.id),
        "sku": row.sku,
        "slug": row.slug,
        "canonical_url": row.canonical_url,
        "indexable": row.indexable,
        "merchant_feed_enabled": row.merchant_feed_enabled,
    }


@admin_router.get("/indexable-configurations")
async def list_curated(session: DbSession) -> list[dict]:
    tid = get_current_tenant().tenant_id
    rows = (
        (
            await session.execute(
                select(IndexableConfiguration).where(
                    IndexableConfiguration.tenant_id == tid
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "sku": r.sku,
            "slug": r.slug,
            "market": r.market,
            "locale": r.locale,
            "indexable": r.indexable,
            "merchant_feed_enabled": r.merchant_feed_enabled,
        }
        for r in rows
    ]
