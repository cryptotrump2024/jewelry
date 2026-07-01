import asyncio

from app.seeds import seed_all


async def main() -> None:
    tenant = await seed_all()
    print(f"Seeded tenant '{tenant.slug}' ({tenant.id}) + reference data")


if __name__ == "__main__":
    asyncio.run(main())
