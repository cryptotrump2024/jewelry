from app.db import get_session_factory
from app.models import Tenant
from app.seeds.reference import seed_reference_data
from app.seeds.tenancy import _seed as seed_tenancy


async def seed_all() -> Tenant:
    """Idempotently seed the default tenant + all reference data."""
    async with get_session_factory()() as session:
        async with session.begin():
            tenant = await seed_tenancy(session)
            await seed_reference_data(session, tenant)
        return tenant
