"""
One-shot, idempotent offline migration: copy every SQLite relational table
into a Postgres (or alternate SQLite) destination.

Public API
----------
    result = await copy_sqlite_to_postgres(sqlite_url, postgres_url)
    # result: {table_name: rows_copied}  (-1 = skipped, already populated)

Constraints (match PR-7b spec):
- Never reads or writes ChromaDB / vector data (PR-7c territory).
- Never deletes, truncates, or upserts source or dest rows.
- Never logs full URLs — only the scheme prefix.
- Skip-whole-table if dest already has rows (idempotent, not upsert).
"""
from __future__ import annotations

import logging

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine

_log = logging.getLogger("pulse.storage_migration")


async def copy_sqlite_to_postgres(
    sqlite_url: str,
    postgres_url: str,
) -> dict[str, int]:
    """Copy every relational table from *sqlite_url* into *postgres_url*.

    Both URLs must be async-driver URLs (sqlite+aiosqlite://, postgresql+asyncpg://).
    Returns a dict mapping each table name to the number of rows copied,
    or -1 if the table was skipped because the destination already had rows.
    """
    # Lazy imports — avoid circular imports and keep module importable standalone
    from ai.engine.core.database import _ensure_pg_schema
    from ai.engine.core.models import Base
    import ai.engine.knowledge_graph.models  # noqa: F401 — registers KG tables with Base

    src_scheme = sqlite_url.split("://")[0]
    dst_scheme = postgres_url.split("://")[0]
    _log.info("Storage migration: %s → %s", src_scheme, dst_scheme)

    src_engine = create_async_engine(sqlite_url, echo=False)
    dst_engine = create_async_engine(postgres_url, echo=False)

    result: dict[str, int] = {}

    try:
        # Ensure pulse schema + vector extension on Postgres (no-op on SQLite)
        await _ensure_pg_schema(dst_engine)

        # Create any missing tables on dest (idempotent)
        async with dst_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        for table in Base.metadata.sorted_tables:
            # ── Read source rows ───────────────────────────────────────────
            async with src_engine.connect() as src_conn:
                rows = (await src_conn.execute(select(table))).mappings().all()

            if not rows:
                result[table.name] = 0
                continue

            # ── Idempotency: skip dest table if already populated ──────────
            async with dst_engine.connect() as dst_conn:
                dest_count: int = (
                    await dst_conn.execute(
                        select(func.count()).select_from(table)
                    )
                ).scalar_one()

            if dest_count > 0:
                _log.info("Table %s: skipped (already populated)", table.name)
                result[table.name] = -1
                continue

            # ── Bulk insert ────────────────────────────────────────────────
            async with dst_engine.begin() as dst_conn:
                await dst_conn.execute(insert(table), [dict(r) for r in rows])

            _log.info("Table %s: copied %d rows", table.name, len(rows))
            result[table.name] = len(rows)

        return result

    finally:
        await src_engine.dispose()
        await dst_engine.dispose()
