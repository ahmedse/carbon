"""
Schema introspector — connects to host PostgreSQL and reads schema.
Uses psycopg2 (sync) via asyncio.to_thread.
"""
import asyncio
import logging
from datetime import datetime

from ai.engine.core.clock import utcnow
import psycopg2
import psycopg2.extras

from ai.engine.core.exceptions import HostConnectionError, IntrospectionError
from ai.engine.knowledge.schema_graph import ColumnInfo, Relationship, SchemaGraph, TableInfo

logger = logging.getLogger("pulse.knowledge.introspector")


class SchemaIntrospector:
    def __init__(self, db_url: str, schema: str = "public"):
        self.db_url = db_url
        self.schema = schema

    async def introspect(self) -> SchemaGraph:
        """
        Connect to host PostgreSQL (read-only), introspect schema.
        Returns a SchemaGraph dataclass.
        """
        try:
            return await asyncio.to_thread(self._introspect_sync)
        except HostConnectionError:
            raise
        except Exception as e:
            raise IntrospectionError(f"Schema introspection failed: {e}")

    def _introspect_sync(self) -> SchemaGraph:
        """Synchronous introspection — runs in a thread."""
        try:
            conn = psycopg2.connect(self.db_url)
        except psycopg2.Error as e:
            raise HostConnectionError(f"Cannot connect to host database: {e}")

        try:
            conn.set_session(readonly=True, autocommit=True)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Set statement timeout to prevent long-running queries
            cursor.execute("SET statement_timeout = '30s'")

            tables = self._get_tables(cursor)
            pk_map = self._get_primary_keys(cursor)
            fk_list = self._get_foreign_keys(cursor)

            # Build FK lookup: (table, column) → (target_table, target_column)
            fk_map: dict[tuple[str, str], tuple[str, str]] = {}
            for fk in fk_list:
                fk_map[(fk["source_table"], fk["source_column"])] = (
                    fk["target_table"],
                    fk["target_column"],
                )

            table_infos = []
            for table_name in tables:
                columns = self._get_columns(cursor, table_name)
                row_count = self._get_row_count(cursor, table_name)
                pks = pk_map.get(table_name, [])

                col_infos = []
                for col in columns:
                    is_pk = col["column_name"] in pks
                    fk_key = (table_name, col["column_name"])
                    is_fk = fk_key in fk_map
                    fk_target = fk_map.get(fk_key)

                    col_infos.append(
                        ColumnInfo(
                            name=col["column_name"],
                            data_type=col["data_type"],
                            is_nullable=col["is_nullable"] == "YES",
                            default=col["column_default"],
                            is_primary_key=is_pk,
                            is_foreign_key=is_fk,
                            fk_target_table=fk_target[0] if fk_target else None,
                            fk_target_column=fk_target[1] if fk_target else None,
                        )
                    )

                table_infos.append(
                    TableInfo(
                        name=table_name,
                        columns=col_infos,
                        row_count=row_count,
                        primary_keys=pks,
                    )
                )

            # Build relationships
            relationships = []
            for fk in fk_list:
                relationships.append(
                    Relationship(
                        source_table=fk["source_table"],
                        source_column=fk["source_column"],
                        target_table=fk["target_table"],
                        target_column=fk["target_column"],
                        relationship_type="many_to_one",
                    )
                )

            return SchemaGraph(
                tables=table_infos,
                relationships=relationships,
                introspected_at=utcnow(),
            )
        finally:
            conn.close()

    def _get_tables(self, cursor) -> list[str]:
        """Get all table names in the schema."""
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (self.schema,),
        )
        return [row["table_name"] for row in cursor.fetchall()]

    def _get_columns(self, cursor, table_name: str) -> list[dict]:
        """Get all columns for a table."""
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (self.schema, table_name),
        )
        return cursor.fetchall()

    def _get_primary_keys(self, cursor) -> dict[str, list[str]]:
        """Get primary key columns grouped by table."""
        cursor.execute(
            """
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = %s
            ORDER BY tc.table_name, kcu.ordinal_position
            """,
            (self.schema,),
        )
        pk_map: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            pk_map.setdefault(row["table_name"], []).append(row["column_name"])
        return pk_map

    def _get_foreign_keys(self, cursor) -> list[dict]:
        """Get all foreign key relationships."""
        cursor.execute(
            """
            SELECT
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
            """,
            (self.schema,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_row_count(self, cursor, table_name: str) -> int:
        """Get approximate row count for a table."""
        try:
            # Use the identifier safely via psycopg2's sql module
            from psycopg2 import sql

            query = sql.SQL("SELECT count(*) AS cnt FROM {}.{}").format(
                sql.Identifier(self.schema),
                sql.Identifier(table_name),
            )
            cursor.execute(query)
            row = cursor.fetchone()
            return row["cnt"] if row else 0
        except Exception as e:
            logger.warning(f"Could not get row count for {table_name}: {e}")
            return 0
