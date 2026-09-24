"""Dangerous-pattern scans — one function, inline ``re.search`` (ADR-0049 L7).

Shared by agent guardrails and the skills admission gate. Preserves the
exact flag / reason strings red-team tests expect.
"""
from __future__ import annotations

import re


def sql_danger_reasons(value: str) -> list[str]:
    reasons: list[str] = []
    if re.search(r"\bDROP\s+TABLE\b", value, re.IGNORECASE):
        reasons.append("DROP TABLE detected in tool args")
    if re.search(r"\bDELETE\s+FROM\b", value, re.IGNORECASE):
        reasons.append("DELETE FROM detected in tool args")
    if re.search(r"\bTRUNCATE\s+(TABLE\s+)?\w+", value, re.IGNORECASE):
        reasons.append("TRUNCATE detected in tool args")
    if re.search(r"\bALTER\s+TABLE\b", value, re.IGNORECASE):
        reasons.append("ALTER TABLE detected in tool args")
    if re.search(r"\bINSERT\s+INTO\b", value, re.IGNORECASE):
        reasons.append("INSERT INTO detected in tool args")
    if re.search(r"\bUPDATE\s+\w+\s+SET\b", value, re.IGNORECASE):
        reasons.append("UPDATE ... SET detected in tool args")
    return reasons


def shell_danger_reasons(value: str) -> list[str]:
    reasons: list[str] = []
    if re.search(r"\brm\s+(-[rRf]+\s+)*[/~]", value):
        reasons.append("rm with path detected in tool args")
    if re.search(r"\bsudo\b", value, re.IGNORECASE):
        reasons.append("sudo detected in tool args")
    return reasons


def sql_injection_reasons(value: str) -> list[str]:
    reasons: list[str] = []
    if re.search(
        r"'\s*OR\s+['\"]?\s*1\s*=\s*['\"]?\s*1", value, re.IGNORECASE,
    ):
        reasons.append("SQL injection pattern: ' OR 1=1")
    if re.search(
        r"'\s*OR\s+['\"]?\s*['\"]?\s*=\s*['\"]?\s*['\"]?", value, re.IGNORECASE,
    ):
        reasons.append("SQL injection pattern: OR ''=''")
    if re.search(r"'\s*OR\s+\S+\s*=\s*\S+", value, re.IGNORECASE):
        reasons.append("SQL injection pattern: ' OR x=y")
    if re.search(r";\s*--", value):
        reasons.append("SQL injection pattern: ;-- comment")
    if re.search(r"UNION\s+SELECT", value, re.IGNORECASE):
        reasons.append("UNION SELECT detected")
    return reasons


def scan_tool_args_danger(value: str) -> list[str]:
    """All guardrail reasons for a single string value."""
    return (
        sql_danger_reasons(value)
        + shell_danger_reasons(value)
        + sql_injection_reasons(value)
    )


def skill_danger_flags(text: str) -> list[str]:
    """Admission-gate flags (``dangerous_pattern: …`` labels)."""
    flags: list[str] = []
    if re.search(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: DROP statement")
    if re.search(r"\bDELETE\s+FROM\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: DELETE FROM statement")
    if re.search(r"\bTRUNCATE\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: TRUNCATE statement")
    if re.search(r"\bALTER\s+(TABLE|DATABASE)\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: ALTER statement")
    if re.search(r"\beval\s*\(", text, re.IGNORECASE):
        flags.append("dangerous_pattern: eval() call")
    if re.search(r"\bexec\s*\(", text, re.IGNORECASE):
        flags.append("dangerous_pattern: exec() call")
    if re.search(r"\bsubprocess\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: subprocess usage")
    if re.search(r"\bos\.system\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: os.system() call")
    if re.search(r"\bos\.popen\b", text, re.IGNORECASE):
        flags.append("dangerous_pattern: os.popen() call")
    if re.search(r"\b__import__\s*\(", text, re.IGNORECASE):
        flags.append("dangerous_pattern: __import__() call")
    if re.search(r"\bcompile\s*\(", text, re.IGNORECASE):
        flags.append("dangerous_pattern: compile() call")
    return flags
