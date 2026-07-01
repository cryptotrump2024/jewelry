import asyncio

from app.seeds.tenancy import seed_default_tenant


async def main() -> None:
    tenant = await seed_default_tenant()
    print(f"Seeded default tenant: {tenant.slug} ({tenant.id})")


if __name__ == "__main__":
    asyncio.run(main())
