"""Phase 9 core (FRD criterion 6): curated variants get stable sku/slug/

canonical; JSON-LD carries ProductGroup + Product + Offer; the sitemap lists
indexable pages; the Merchant feed uses feed-legal values (preorder +
availability_date, identifier_exists=false, no MadeToOrder ever).
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import ProductTemplate

SELECTIONS = {
    "metal": "gold_750_yellow",
    "stone_type": "lab_diamond",
    "stone_shape": "oval",
    "carat": "1.00",
    "certificate": "igi",
}


async def _template_id() -> str:
    async with get_session_factory()() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        return str(template.id)


async def _curate(client, selections=None, sku=None) -> dict:
    resp = await client.post(
        "/admin/seo/indexable-configurations",
        json={
            "template_id": await _template_id(),
            "selections": selections or SELECTIONS,
            "sku": sku,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_curation_creates_stable_sku_slug_canonical(client):
    row = await _curate(client, sku="oval-18ky-1ct-lab")
    assert row["sku"] == "oval-18ky-1ct-lab"
    assert row["canonical_url"].endswith("/rings/oval-solitaire?v=oval-18ky-1ct-lab")
    assert row["indexable"] is True

    # Idempotent by sku.
    again = await _curate(client, sku="oval-18ky-1ct-lab")
    assert again["id"] == row["id"]


async def test_unpriceable_config_cannot_be_curated(client):
    resp = await client.post(
        "/admin/seo/indexable-configurations",
        json={
            "template_id": await _template_id(),
            "selections": SELECTIONS | {"carat": "5.00"},
        },
    )
    assert resp.status_code == 409


async def test_jsonld_productgroup_with_variant_offers(client):
    await _curate(client, sku="oval-18ky-1ct-lab")
    resp = await client.get(f"/api/v1/seo/schema?template_id={await _template_id()}")
    schema = resp.json()
    assert schema["@type"] == "ProductGroup"
    assert schema["productGroupID"] == "oval-solitaire"
    variant = next(v for v in schema["hasVariant"] if v["sku"] == "oval-18ky-1ct-lab")
    offer = variant["offers"]
    assert offer["priceCurrency"] == "EUR"
    assert float(offer["price"]) > 0
    # Schema.org MAY use MadeToOrder (the feed may not).
    assert offer["availability"] == "https://schema.org/MadeToOrder"


async def test_sitemap_lists_indexable_pages(client):
    row = await _curate(client, sku="oval-18ky-1ct-lab")
    resp = await client.get("/api/v1/seo/sitemap.xml")
    assert resp.status_code == 200
    xml = resp.text
    assert "<urlset" in xml
    assert "/rings/oval-solitaire</loc>" in xml
    assert row["canonical_url"] in xml


async def test_merchant_feed_is_feed_legal(client):
    await _curate(client, sku="oval-18ky-1ct-lab")
    resp = await client.get("/api/v1/merchant/feed/google")
    assert resp.status_code == 200
    xml = resp.text

    assert "MadeToOrder" not in xml  # never a schema value in the feed
    assert "<g:availability>preorder</g:availability>" in xml
    assert "<g:availability_date>" in xml
    assert "<g:identifier_exists>false</g:identifier_exists>" in xml
    assert "<g:gtin>" not in xml and "<g:mpn>" not in xml  # omitted, not faked
    assert "<g:id>oval-18ky-1ct-lab</g:id>" in xml
    assert "<g:item_group_id>oval-solitaire</g:item_group_id>" in xml
    assert " EUR</g:price>" in xml
