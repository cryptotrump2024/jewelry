from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.admin_pricing import router as admin_pricing_router
from app.api.routes import router
from app.db import dispose_engine
from app.tenancy.middleware import TenantContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(
    title="Jewelry Configuration Engine",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(TenantContextMiddleware)
app.include_router(router)
app.include_router(admin_router)
app.include_router(admin_pricing_router)
