"""
Dataclasses for representing database schema structure.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    default: Optional[str]
    is_primary_key: bool
    is_foreign_key: bool
    fk_target_table: Optional[str] = None
    fk_target_column: Optional[str] = None


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    row_count: int
    primary_keys: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str = "many_to_one"  # many_to_one, one_to_many, many_to_many


@dataclass
class SchemaGraph:
    tables: list[TableInfo]
    relationships: list[Relationship]
    introspected_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Serialize the schema graph to a JSON-friendly dict."""
        return {
            "tables": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "primary_keys": t.primary_keys,
                    "columns": [
                        {
                            "name": c.name,
                            "data_type": c.data_type,
                            "is_nullable": c.is_nullable,
                            "default": c.default,
                            "is_primary_key": c.is_primary_key,
                            "is_foreign_key": c.is_foreign_key,
                            "fk_target_table": c.fk_target_table,
                            "fk_target_column": c.fk_target_column,
                        }
                        for c in t.columns
                    ],
                }
                for t in self.tables
            ],
            "relationships": [
                {
                    "source_table": r.source_table,
                    "source_column": r.source_column,
                    "target_table": r.target_table,
                    "target_column": r.target_column,
                    "relationship_type": r.relationship_type,
                }
                for r in self.relationships
            ],
            "introspected_at": self.introspected_at.isoformat(),
        }

    def get_table(self, name: str) -> Optional[TableInfo]:
        """Lookup a table by name."""
        for t in self.tables:
            if t.name == name:
                return t
        return None

    def get_related_tables(self, table_name: str) -> list[str]:
        """Get all tables related to the given table via FK relationships."""
        related = set()
        for r in self.relationships:
            if r.source_table == table_name:
                related.add(r.target_table)
            elif r.target_table == table_name:
                related.add(r.source_table)
        return sorted(related)

    def summary(self) -> str:
        """One-paragraph text summary of the schema."""
        table_names = [t.name for t in self.tables]
        total_rows = sum(t.row_count for t in self.tables)
        return (
            f"Schema contains {len(self.tables)} tables and "
            f"{len(self.relationships)} foreign key relationships. "
            f"Total rows across all tables: {total_rows}. "
            f"Key tables: {', '.join(table_names[:10])}"
            f"{'...' if len(table_names) > 10 else ''}."
        )
