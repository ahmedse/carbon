"""
Semantic enrichment of schema — uses LLM to generate business descriptions.
No fallbacks: if the LLM fails, the error propagates so it's visible.
"""
import asyncio
import json
import logging
import re

from pydantic import BaseModel

from ai.engine.core.exceptions import PulseError
from ai.engine.knowledge.schema_graph import SchemaGraph

logger = logging.getLogger("pulse.knowledge.semantic_layer")


class SemanticEnrichmentError(PulseError):
    """Raised when LLM enrichment fails after all retries."""

    def __init__(self, model: str, tables: list[str], cause: str):
        detail = (
            f"Semantic enrichment failed for tables {tables} "
            f"using model '{model}': {cause}"
        )
        super().__init__(detail=detail)


class TableDescriptions(BaseModel):
    """Pydantic model for validating introspection LLM output."""
    descriptions: dict[str, str]

    @classmethod
    def parse_llm_response(cls, raw: str, expected_tables: list[str]) -> "TableDescriptions":
        """Parse JSON from LLM response. Handles code fences, markdown wrapping."""
        text = raw.strip()
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        # Try to find JSON object if response has extra text
        if not text.startswith("{"):
            brace_start = text.find("{")
            if brace_start != -1:
                text = text[brace_start:]
                # Find matching closing brace
                depth = 0
                for i, ch in enumerate(text):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            text = text[: i + 1]
                            break
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        # Validate: every expected table must have a non-empty description
        missing = [t for t in expected_tables if not data.get(t)]
        if missing:
            raise ValueError(f"LLM response missing descriptions for: {missing}")
        # Drop keys that aren't in the expected list (model hallucinated extra tables)
        data = {k: str(v) for k, v in data.items() if k in expected_tables}
        return cls(descriptions=data)


class SemanticEnricher:
    def __init__(self, llm_client=None, instance_config: dict = None, instance_id: str = ""):
        self.llm_client = llm_client  # kept for backward compat
        self.instance_config = instance_config or {}
        self.instance_id = instance_id

    async def enrich_schema(self, schema_graph: SchemaGraph) -> list[dict]:
        """
        For each table in schema_graph, generate a business description using LLM.
        Returns list of dicts with: name, entity_type, schema_json, semantic_description, relationships.
        Batches up to 5 tables per LLM call. Raises on failure — no fallbacks.
        """
        from ai.engine.llm.prompts import build_introspect_messages

        entities = []
        tables = schema_graph.tables
        domain = self.instance_config.get("domain", "software")
        instance_name = self.instance_config.get("display_name", "Unknown System")
        instance_description = self.instance_config.get("description", "")

        # Process in batches of 5
        for i in range(0, len(tables), 5):
            batch = tables[i : i + 5]
            tables_block = self._format_tables_block(batch, schema_graph)

            messages = build_introspect_messages(
                domain=domain,
                instance_name=instance_name,
                instance_description=instance_description,
                tables_block=tables_block,
            )

            descriptions = await self._call_llm_for_descriptions(messages, batch)

            for table in batch:
                description = descriptions[table.name]
                related = schema_graph.get_related_tables(table.name)
                entities.append(
                    {
                        "name": table.name,
                        "entity_type": "table",
                        "schema_json": json.dumps(
                            {
                                "columns": [
                                    {
                                        "name": c.name,
                                        "type": c.data_type,
                                        "nullable": c.is_nullable,
                                        "is_primary_key": c.is_primary_key,
                                        "is_foreign_key": c.is_foreign_key,
                                        "fk_target_table": c.fk_target_table,
                                        "fk_target_column": c.fk_target_column,
                                        "default": c.default,
                                    }
                                    for c in table.columns
                                ],
                                "row_count": table.row_count,
                                "primary_keys": table.primary_keys,
                            }
                        ),
                        "semantic_description": description,
                        "relationships": json.dumps(related),
                    }
                )

        return entities

    def _format_tables_block(self, tables, schema_graph: SchemaGraph) -> str:
        """Format a batch of tables into text for the LLM prompt."""
        lines = []
        for table in tables:
            cols = ", ".join(
                f"{c.name} ({c.data_type}{'→' + c.fk_target_table if c.is_foreign_key else ''})"
                for c in table.columns
            )
            related = schema_graph.get_related_tables(table.name)
            lines.append(
                f"Table: {table.name} ({table.row_count} rows)\n"
                f"  Columns: {cols}\n"
                f"  Related tables: {', '.join(related) if related else 'none'}\n"
            )
        return "\n".join(lines)

    async def _call_llm_for_descriptions(self, messages: list[dict], tables) -> dict[str, str]:
        """Call LLM to get descriptions with retries. Raises on failure — no fallbacks."""
        from ai.engine.core.config import get_settings

        settings = get_settings()
        # Use the smart model for enrichment — this is a hard task
        model = settings.LLM_INTROSPECT_MODEL or settings.LLM_MODEL
        expected = [t.name for t in tables]
        max_attempts = 5
        backoff = 2  # seconds
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"Enriching {len(tables)} tables with model={model} "
                    f"(attempt {attempt}/{max_attempts}): {expected}"
                )
                if self.llm_client:
                    response = await self.llm_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.3,
                    )
                else:
                    from ai.engine.llm.router import route_chat
                    result = await route_chat(
                        task="introspect",
                        instance_id=self.instance_id or "system",
                        conversation_id=f"enrich-{self.instance_id or 'system'}",
                        messages=messages,
                        temperature=0.3,
                    )
                    # Wrap route_chat result to look like an OpenAI response
                    class _FakeChoice:
                        class _Msg:
                            content = result.get("content", "")
                        message = _Msg()
                    class _FakeResp:
                        choices = [_FakeChoice()]
                    response = _FakeResp()
                raw = response.choices[0].message.content
                parsed = TableDescriptions.parse_llm_response(raw, expected)
                logger.info(f"Enrichment OK: {list(parsed.descriptions.keys())}")
                return parsed.descriptions
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    logger.warning(
                        f"LLM enrichment attempt {attempt}/{max_attempts} failed "
                        f"(model={model}): {e} — retrying in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(
                        f"LLM enrichment FAILED after {max_attempts} attempts "
                        f"(model={model}): {e}"
                    )

        raise SemanticEnrichmentError(
            model=model, tables=expected, cause=str(last_error)
        )
