from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.admin_pricing import router as admin_pricing_router
from app.api.bespoke import admin_router as bespoke_admin_router
from app.api.bespoke import router as bespoke_router
from app.api.production import router as production_router
from app.api.public import router as public_router
from app.api.public_orders import router as public_orders_router
from app.api.public_withdrawals import router as public_withdrawals_router
from app.api.routes import router
from app.db import dispose_engine
from app.services.config_service import close_redis
from app.tenancy.middleware import TenantContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()
    await dispose_engine()


app = FastAPI(
    title="Jewelry Configuration Engine",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(TenantContextMiddleware)
app.include_router(router)
app.include_router(public_router)
app.include_router(public_orders_router)
app.include_router(public_withdrawals_router)
app.include_router(production_router)
app.include_router(bespoke_router)
app.include_router(bespoke_admin_router)
app.include_router(admin_router)
app.include_router(admin_pricing_router)
