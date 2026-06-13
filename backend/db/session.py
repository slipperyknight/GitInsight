"""Database connection pools + the org-GUC session helper.

Two pools, two trust levels:

  * admin pool  (DATABASE_URL, superuser)      — migrate / seed.py / enrich.py.
    Superuser BYPASSES Row-Level Security, which is what trusted batch writers want.
  * app pool    (APP_DATABASE_URL, app_user)   — the FastAPI request path.
    RLS is ENFORCED here. Every request must go through `org_session(org_id)`, which
    sets `app.org_id` *transaction-locally* so the RLS policy filters by it.

The load-bearing guarantee: `app.org_id` is set with SET LOCAL semantics
(`set_config(..., is_local => true)`) inside a transaction, so it can never leak onto a
connection that is later returned to the pool and reused by another org's request.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# Defaults match docker-compose.yml so the prototype runs with no .env file.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://gitinsight:gitinsight@localhost:5432/gitinsight"
)
APP_DATABASE_URL = os.getenv(
    "APP_DATABASE_URL", "postgresql://app_user:app_pw@localhost:5432/gitinsight"
)

_admin_pool: asyncpg.Pool | None = None
_app_pool: asyncpg.Pool | None = None


async def get_admin_pool() -> asyncpg.Pool:
    """Superuser pool — bypasses RLS. For migrate/seed/enrich only."""
    global _admin_pool
    if _admin_pool is None:
        _admin_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _admin_pool


async def get_app_pool() -> asyncpg.Pool:
    """Non-superuser pool — RLS enforced. For the FastAPI request path."""
    global _app_pool
    if _app_pool is None:
        _app_pool = await asyncpg.create_pool(APP_DATABASE_URL, min_size=1, max_size=10)
    return _app_pool


@asynccontextmanager
async def org_session(org_id: str) -> AsyncIterator[asyncpg.Connection]:
    """Yield an app-pool connection scoped to `org_id` for the duration of one transaction.

    RLS filters every query by `app.org_id`. The GUC is set transaction-locally, so it is
    automatically reset when the transaction ends and never leaks across pooled requests.
    """
    pool = await get_app_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # set_config(setting, value, is_local) — is_local=true => SET LOCAL semantics.
            # Parameterized (asyncpg cannot parameterize a bare SET statement).
            await conn.execute("SELECT set_config('app.org_id', $1, true)", str(org_id))
            yield conn


@asynccontextmanager
async def admin_session() -> AsyncIterator[asyncpg.Connection]:
    """Yield a superuser connection (RLS bypassed) inside a transaction. Batch writers."""
    pool = await get_admin_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def close_pools() -> None:
    global _admin_pool, _app_pool
    if _admin_pool is not None:
        await _admin_pool.close()
        _admin_pool = None
    if _app_pool is not None:
        await _app_pool.close()
        _app_pool = None
