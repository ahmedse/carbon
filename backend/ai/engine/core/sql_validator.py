"""
SQL safety validator — ensures only SELECT queries are executed on the host DB.

Uses sqlparse for AST-based validation instead of regex-only filtering.
Both agent/tools.py and knowledge_graph/execution_engine.py import from here.
"""
import logging
import re

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML

from ai.engine.core.exceptions import ToolExecutionError

logger = logging.getLogger("pulse.core.sql_validator")

# Statements that are absolutely forbidden — catches edge cases sqlparse may not flag
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"EXECUTE|EXEC|COPY|LOAD|INTO\s+OUTFILE|LOAD_FILE|VACUUM|REINDEX|"
    r"SET\s+ROLE|SET\s+SESSION\s+AUTHORIZATION)\b",
    re.IGNORECASE,
)

# Comment stripping — prevent bypass via SQL comments
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def validate_sql(sql: str) -> None:
    """
    Validate that a SQL string is a safe, read-only SELECT statement.

    Raises ToolExecutionError if the query is unsafe.
    """
    if not sql or not sql.strip():
        raise ToolExecutionError("Empty SQL query")

    # Strip comments first — prevents hiding DML inside comments
    cleaned = _LINE_COMMENT.sub("", sql)
    cleaned = _BLOCK_COMMENT.sub("", cleaned)
    cleaned = cleaned.strip().rstrip(";").strip()

    if not cleaned:
        raise ToolExecutionError("Empty SQL query after removing comments")

    # Parse with sqlparse
    parsed_statements = sqlparse.parse(cleaned)
    if not parsed_statements:
        raise ToolExecutionError("Could not parse SQL query")

    # Only allow a single statement
    if len(parsed_statements) > 1:
        raise ToolExecutionError(
            "Multiple SQL statements detected. Only a single SELECT query is allowed."
        )

    stmt: Statement = parsed_statements[0]

    # Check statement type via sqlparse
    stmt_type = stmt.get_type()
    if stmt_type and stmt_type.upper() not in ("SELECT", "UNKNOWN"):
        raise ToolExecutionError(
            f"Only SELECT queries are allowed. Detected: {stmt_type}"
        )

    # Walk tokens to find any DML/DDL that isn't SELECT
    first_dml_found = False
    for token in stmt.flatten():
        if token.ttype is DML:
            if token.normalized.upper() == "SELECT":
                first_dml_found = True
            else:
                raise ToolExecutionError(
                    f"Forbidden DML statement: {token.normalized}. Only SELECT is allowed."
                )

    # Must start with SELECT or WITH (CTE)
    if not re.match(r"^\s*(SELECT|WITH)\b", cleaned, re.IGNORECASE):
        raise ToolExecutionError("Query must start with SELECT or WITH (CTE)")

    # Regex safety net for edge cases sqlparse might miss
    if _FORBIDDEN_KEYWORDS.search(cleaned):
        raise ToolExecutionError(
            "Query contains forbidden SQL keywords. Only read-only SELECT queries are allowed."
        )

    # Reject multiple statements via semicolons embedded in the query
    if ";" in cleaned:
        raise ToolExecutionError(
            "Semicolons within the query body are not allowed. Use a single SELECT statement."
        )

    logger.debug("SQL validation passed")
