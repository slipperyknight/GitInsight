"""Phase 1 acceptance test: RLS provably isolates two orgs through the app pool.

Run:  uv run python -m db.test_isolation
Inserts two throwaway orgs via the admin (superuser) pool, then reads through the app
(app_user) pool with the org-GUC helper and asserts isolation + no stale-context leak.
Cleans up after itself.
"""

import asyncio

from db.session import admin_session, get_app_pool, org_session, close_pools


async def main() -> None:
    # --- seed two orgs (superuser bypasses RLS, so it can write across orgs) ---
    async with admin_session() as conn:
        org_a = await conn.fetchval(
            "INSERT INTO organizations (name) VALUES ('ISO-TEST-A') RETURNING id"
        )
        org_b = await conn.fetchval(
            "INSERT INTO organizations (name) VALUES ('ISO-TEST-B') RETURNING id"
        )
        await conn.execute(
            "INSERT INTO users (org_id, email, name) VALUES ($1, 'a@iso.test', 'Alice-A')",
            org_a,
        )
        await conn.execute(
            "INSERT INTO users (org_id, email, name) VALUES ($1, 'b@iso.test', 'Bob-B')",
            org_b,
        )

    ok = True
    try:
        # --- scoped to Org A: see only Org A's user ---
        async with org_session(str(org_a)) as conn:
            rows = await conn.fetch("SELECT name FROM users")
            names = {r["name"] for r in rows}
            print(f"[Org A] users visible: {sorted(names)}")
            assert names == {"Alice-A"}, f"Org A leaked: {names}"
            orgs = await conn.fetch("SELECT name FROM organizations")
            assert {o["name"] for o in orgs} == {"ISO-TEST-A"}, "org table leaked to A"

        # --- scoped to Org B: see only Org B's user (same pool, flipped GUC) ---
        async with org_session(str(org_b)) as conn:
            rows = await conn.fetch("SELECT name FROM users")
            names = {r["name"] for r in rows}
            print(f"[Org B] users visible: {sorted(names)}")
            assert names == {"Bob-B"}, f"Org B leaked: {names}"

        # --- stale-context check: a bare app-pool connection with NO GUC sees nothing ---
        pool = await get_app_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name FROM users WHERE email LIKE '%@iso.test'")
            print(f"[no GUC] users visible: {len(rows)} (expect 0)")
            assert rows == [], f"unset session leaked {len(rows)} rows"

        print("\n✅ RLS isolation test PASSED")
    except AssertionError as e:
        ok = False
        print(f"\n❌ RLS isolation test FAILED: {e}")
    finally:
        # cleanup
        async with admin_session() as conn:
            await conn.execute(
                "DELETE FROM users WHERE org_id = ANY($1::uuid[])", [org_a, org_b]
            )
            await conn.execute(
                "DELETE FROM organizations WHERE id = ANY($1::uuid[])", [org_a, org_b]
            )
        await close_pools()

    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
