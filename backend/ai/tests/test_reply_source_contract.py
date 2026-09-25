"""Reply text has two sources: a catalog-declared renderer or the grounded writer (ADR-0057).

The tool digest is the model's memory of a turn. It is never user text.
"""
import ast
import json
from pathlib import Path

import pytest

from ai.engine.cognition.plan.export_bind import render_bound_catalog_read
from ai.engine.cognition.tool_digest import build_tool_digest
from ai.engine.cognition.turn.ess_read import answer_bound_ess_tools

BACKEND = Path(__file__).resolve().parents[2]

# Modules that write or replay model memory. A reply path is not one of them.
MEMORY_MODULES = {
    "ai/engine/cognition/tool_digest.py",
    "ai/engine/cognition/state_store.py",
    "ai/engine_runtime.py",
}

PROFILE = {
    "id": 7,
    "employee_no": "E-100",
    "full_name": "Test Person",
    "org_unit": {"id": 3, "name": "Operations"},
    "manager": {"id": 9, "name": "Line Manager"},
    "job_title": "Engineer",
}


def _row(api: str, payload) -> dict:
    return {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": api},
        "result": json.dumps(payload),
    }


def _imports_digest(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ai.engine.cognition.tool_digest":
            if any(alias.name == "build_tool_digest" for alias in node.names):
                return True
    return False


def test_digest_builder_is_imported_only_by_memory_modules():
    offenders = []
    for path in sorted((BACKEND / "ai").rglob("*.py")):
        rel = path.relative_to(BACKEND).as_posix()
        if "/tests/" in rel or rel in MEMORY_MODULES:
            continue
        if _imports_digest(path):
            offenders.append(rel)
    assert offenders == []


def test_undeclared_read_has_no_restatement():
    assert render_bound_catalog_read(_row("get_my_profile", PROFILE), "get_my_profile", "en") is None


@pytest.mark.parametrize("lang_msg", ["tell me about my profile", "بياناتي"])
def test_undeclared_read_never_speaks_the_digest(lang_msg):
    row = _row("get_my_profile", PROFILE)
    digest = build_tool_digest([row], None)
    assert digest
    text = answer_bound_ess_tools(
        [row], api_name="get_my_profile", user_message=lang_msg, unread_text=False,
    )
    assert text == ""
    assert digest not in text


def test_failed_read_stays_honest():
    row = {"tool_name": "call_host_api", "tool_args": {"api_name": "get_my_profile"},
           "error": "timeout"}
    text = answer_bound_ess_tools([row], api_name="get_my_profile", user_message="who am I")
    assert text == "Could not read that data from the host."
