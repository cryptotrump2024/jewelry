"""Bearer-token guard for /admin (pre-SaaS staff auth).

Empty ADMIN_API_TOKEN disables the check for local development; deployed
environments must set it. The users/roles table takes over when the admin
grows real staff accounts.
"""

from fastapi import HTTPException, Request

from app.config import get_settings


async def require_admin(request: Request) -> None:
    token = get_settings().admin_api_token
    if not token:
        return
    header = request.headers.get("authorization", "")
    if header != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="admin token required")
