"""Config-session helpers: config_hash, shareable state, Redis price cache.

config_hash (docs/spec/07 §5): stable hash of (template, resolved options,
market, source timestamps) — identical input + source timestamps ⇒ identical
output, so the hash is a safe cache key that self-invalidates when a metal/FX
snapshot changes.

Share state: the full selection is encoded in the URL (urlsafe base64 JSON),
so shared links need no storage and reproduce exactly (07 §9 case 6).
Shareable ≠ indexable — share URLs are noindex (docs/spec/11).

The Redis cache is fail-open: if Redis is down the hot path computes without
it (slower, never wrong, never 500).
"""

import base64
import binascii
import hashlib
import json
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

PRICE_CACHE_TTL_SECONDS = 300
_redis: aioredis.Redis | None = None


def _client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            get_settings().redis_url, decode_responses=True, socket_connect_timeout=0.5
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def compute_config_hash(
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    selections: dict[str, Any],
    market: str,
    currency: str,
    source_stamps: list[str],
) -> str:
    canonical = json.dumps(
        {
            "tenant": str(tenant_id),
            "template": str(template_id),
            "selections": selections,
            "market": market,
            "currency": currency,
            "sources": sorted(source_stamps),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def encode_share_state(
    template_id: uuid.UUID, selections: dict[str, Any], market: str, locale: str
) -> str:
    payload = json.dumps(
        {"t": str(template_id), "s": selections, "m": market, "l": locale},
        sort_keys=True,
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_share_state(code: str) -> dict[str, Any] | None:
    try:
        padded = code + "=" * (-len(code) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(payload, dict) or "t" not in payload or "s" not in payload:
        return None
    return payload


async def cached_price(config_hash: str) -> dict[str, Any] | None:
    try:
        raw = await _client().get(f"price:{config_hash}")
        return json.loads(raw) if raw else None
    except (aioredis.RedisError, OSError):
        return None


async def cache_price(config_hash: str, response: dict[str, Any]) -> None:
    try:
        await _client().set(
            f"price:{config_hash}", json.dumps(response), ex=PRICE_CACHE_TTL_SECONDS
        )
    except (aioredis.RedisError, OSError):
        pass
