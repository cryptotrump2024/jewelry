from app.db import get_session_factory
from app.models import Tenant
from app.seeds.demo_template import seed_demo_template
from app.seeds.pricing import seed_pricing_config
from app.seeds.reference import seed_reference_data
from app.seeds.tenancy import _seed as seed_tenancy


async def seed_all() -> Tenant:
    """Idempotently seed the default tenant + reference data + demo template

    + pricing config, then run one manual metal-price refresh so the demo
    prices out of the box (a GoldAPI source replaces it in production).
    """
    from app.sources.metal import refresh_metal_prices

    async with get_session_factory()() as session:
        async with session.begin():
            tenant = await seed_tenancy(session)
            await seed_reference_data(session, tenant)
            await seed_demo_template(session, tenant)
            await seed_pricing_config(session, tenant)
            await refresh_metal_prices(session, tenant.id, "EUR")
        return tenant
