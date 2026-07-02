"""SEO/GEO output (docs/spec/11): curated variants, JSON-LD, sitemap, feed.

Everything derives from the same source of truth as prices (PRINCIPLES.md 6).
The base URL comes from the tenant's primary domain — never hardcoded.

Key mappings (audit pass v1.2):
- JSON-LD availability may say schema.org MadeToOrder; the Merchant feed may
  NOT — made-to-order maps to `preorder` + availability_date there.
- GTIN-less rings: identifier_exists=false, no gtin/mpn/brand in the feed.
- sku == schema variant sku == feed id; template.code == productGroupID ==
  feed item_group_id.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    IndexableConfiguration,
    ProductTemplate,
    TenantDomain,
    TenantSetting,
)
from app.services.config_service import compute_config_hash
from app.services.pricing_resolver import resolve_and_price

MADE_TO_ORDER_LEAD_DAYS = 30  # availability_date offset for the feed


async def base_url(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    domain = (
        await session.execute(
            select(TenantDomain)
            .where(TenantDomain.tenant_id == tenant_id, TenantDomain.is_primary.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()
    host = domain.host if domain else "localhost"
    scheme = "http" if host in ("localhost", "127.0.0.1") else "https"
    port = ":3000" if host == "localhost" else ""
    return f"{scheme}://{host}{port}"


async def brand_name(session: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    setting = (
        await session.execute(
            select(TenantSetting).where(
                TenantSetting.tenant_id == tenant_id, TenantSetting.key == "branding"
            )
        )
    ).scalar_one_or_none()
    return (setting.value or {}).get("display_name") if setting else None


def _slugify(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-").replace("--", "-")


async def curate_configuration(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template: ProductTemplate,
    selections: dict[str, Any],
    market: str = "NL",
    locale: str = "en",
    sku: str | None = None,
    slug: str | None = None,
) -> IndexableConfiguration:
    """Persist one curated commercial variant — the deliberate exception to

    no-SKU-explosion. Refuses configurations that don't price as purchasable
    (a curated page must always be able to show an exact offer).
    """
    resolved = await resolve_and_price(session, tenant_id, template, selections, market=market)
    if resolved.price is None or resolved.price.status != "purchasable":
        raise ValueError("only purchasable configurations can be curated for indexing")

    config_hash = compute_config_hash(
        tenant_id, template.id, selections, market, "EUR", ["curated"]
    )
    parts = [template.code] + [
        str(selections[k]) for k in sorted(selections) if selections[k] is not None
    ]
    sku = sku or _slugify("-".join(parts))[:100]
    slug = (
        slug
        or _slugify(f"{template.code}-" + "-".join(str(v) for v in selections.values()))[:255]
    )

    existing = (
        await session.execute(
            select(IndexableConfiguration).where(
                IndexableConfiguration.tenant_id == tenant_id,
                IndexableConfiguration.sku == sku,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    root = await base_url(session, tenant_id)
    row = IndexableConfiguration(
        tenant_id=tenant_id,
        template_id=template.id,
        config_hash=config_hash,
        sku=sku,
        slug=slug,
        selections=selections,
        market=market,
        locale=locale,
        indexable=True,
        merchant_feed_enabled=True,
        canonical_url=f"{root}/rings/{template.code}?v={sku}",
    )
    session.add(row)
    await session.flush()
    return row


async def build_jsonld(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template: ProductTemplate,
    market: str = "NL",
    locale: str = "en",
) -> dict[str, Any]:
    """ProductGroup + Product variants + Offer from curated configurations."""
    brand = await brand_name(session, tenant_id)
    root = await base_url(session, tenant_id)
    variants = (
        (
            await session.execute(
                select(IndexableConfiguration).where(
                    IndexableConfiguration.tenant_id == tenant_id,
                    IndexableConfiguration.template_id == template.id,
                    IndexableConfiguration.indexable.is_(True),
                    IndexableConfiguration.market == market,
                    IndexableConfiguration.locale == locale,
                )
            )
        )
        .scalars()
        .all()
    )

    products = []
    for v in variants:
        resolved = await resolve_and_price(
            session, tenant_id, template, v.selections, market=market
        )
        price = resolved.price
        if price is None or price.total_minor is None:
            continue  # degraded variants drop out of schema rather than lie
        products.append(
            {
                "@type": "Product",
                "sku": v.sku,
                "name": f"{template.name} — {', '.join(str(x) for x in v.selections.values())}",
                "url": v.canonical_url,
                "offers": {
                    "@type": "Offer",
                    "price": f"{price.total_minor / 100:.2f}",
                    "priceCurrency": price.currency,
                    # Schema.org MAY say MadeToOrder (feed may not).
                    "availability": "https://schema.org/MadeToOrder",
                    "url": v.canonical_url,
                },
            }
        )

    return {
        "@context": "https://schema.org",
        "@type": "ProductGroup",
        "productGroupID": template.code,
        "name": template.name,
        "url": f"{root}/rings/{template.code}",
        **({"brand": {"@type": "Brand", "name": brand}} if brand else {}),
        "hasVariant": products,
    }


async def build_sitemap_xml(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    root = await base_url(session, tenant_id)
    templates = (
        (
            await session.execute(
                select(ProductTemplate).where(
                    ProductTemplate.tenant_id == tenant_id,
                    ProductTemplate.status == "active",
                    ProductTemplate.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    variants = (
        (
            await session.execute(
                select(IndexableConfiguration).where(
                    IndexableConfiguration.tenant_id == tenant_id,
                    IndexableConfiguration.indexable.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    urls = [f"{root}/rings"] + [f"{root}/rings/{t.code}" for t in templates]
    urls += [v.canonical_url for v in variants if v.canonical_url]

    entries = "\n".join(
        f"  <url><loc>{escape(u)}</loc><changefreq>daily</changefreq></url>" for u in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


async def build_merchant_feed_xml(
    session: AsyncSession, tenant_id: uuid.UUID, market: str = "NL", locale: str = "en"
) -> str:
    """Google Merchant feed (RSS 2.0 + g: namespace) from curated variants.

    availability: made-to-order maps to preorder + availability_date (never
    schema's MadeToOrder). identifier_exists=false for GTIN-less rings —
    gtin/mpn/brand omitted entirely.
    """
    brand = await brand_name(session, tenant_id)
    variants = (
        (
            await session.execute(
                select(IndexableConfiguration, ProductTemplate)
                .join(ProductTemplate, ProductTemplate.id == IndexableConfiguration.template_id)
                .where(
                    IndexableConfiguration.tenant_id == tenant_id,
                    IndexableConfiguration.merchant_feed_enabled.is_(True),
                    IndexableConfiguration.market == market,
                    IndexableConfiguration.locale == locale,
                )
            )
        )
        .all()
    )
    availability_date = (datetime.now(UTC) + timedelta(days=MADE_TO_ORDER_LEAD_DAYS)).strftime(
        "%Y-%m-%d"
    )

    items: list[str] = []
    for variant, template in variants:
        resolved = await resolve_and_price(
            session, tenant_id, template, variant.selections, market=market
        )
        price = resolved.price
        if price is None or price.total_minor is None:
            continue  # never feed an unpriceable offer
        title = f"{template.name} — {', '.join(str(x) for x in variant.selections.values())}"
        metal = str(variant.selections.get("metal", ""))
        size = str(variant.selections.get("ring_size", "")) or None
        items.append(
            "  <item>\n"
            f"    <g:id>{escape(variant.sku)}</g:id>\n"
            f"    <g:item_group_id>{escape(template.code)}</g:item_group_id>\n"
            f"    <title>{escape(title[:150])}</title>\n"
            f"    <link>{escape(variant.canonical_url or '')}</link>\n"
            f"    <g:price>{price.total_minor / 100:.2f} {price.currency}</g:price>\n"
            "    <g:availability>preorder</g:availability>\n"
            f"    <g:availability_date>{availability_date}</g:availability_date>\n"
            "    <g:condition>new</g:condition>\n"
            "    <g:identifier_exists>false</g:identifier_exists>\n"
            '    <g:google_product_category>Apparel &amp; Accessories &gt; Jewelry &gt; '
            "Rings</g:google_product_category>\n"
            + (f"    <g:material>{escape(metal)}</g:material>\n" if metal else "")
            + (f"    <g:size>{escape(size)}</g:size>\n" if size else "")
            + "  </item>"
        )

    channel_title = escape(brand or "Jewelry")
    body = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
        "<channel>\n"
        f"  <title>{channel_title}</title>\n"
        f"  <description>Made-to-order engagement rings ({market}/{locale})</description>\n"
        f"{body}\n"
        "</channel>\n"
        "</rss>\n"
    )
