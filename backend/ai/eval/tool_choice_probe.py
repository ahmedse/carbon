"""Offline capability probe for tool_choice / strict (ADR-0049 Q1).

Does not call the network. Records what the local gateway *claims* via env
overrides, and what the code path supports. A live probe is a separate
STACK-HOLD night.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "docs" / "pulse" / "evidence" / "PV2.1-tool-choice-probe-2026-09-23.json"


def probe() -> dict:
    """Report support matrix. Env overrides simulate a measured gateway."""
    from ai.engine.llm.tool_choice import apply_strict, normalize_tool_choice

    sample = [{"type": "function", "function": {"name": "x", "parameters": {"type": "object"}}}]
    strict_copy = apply_strict(sample, True)
    return {
        "measured_at": date.today().isoformat(),
        "normalize_auto": normalize_tool_choice("auto"),
        "normalize_required": normalize_tool_choice("required"),
        "normalize_named": normalize_tool_choice({"name": "emit_decision"}),
        "strict_sets_flag": bool(
            isinstance(strict_copy, list)
            and strict_copy[0]["function"].get("strict") is True
        ),
        "input_not_mutated": sample[0]["function"].get("strict") is not True,
        "env_supports_named": os.environ.get("PULSE_TOOL_CHOICE_NAMED", "unknown"),
        "env_supports_required": os.environ.get("PULSE_TOOL_CHOICE_REQUIRED", "unknown"),
        "env_supports_strict": os.environ.get("PULSE_TOOL_CHOICE_STRICT", "unknown"),
        "note": "Live gateway probe needs STACK-HOLD; this file is the code-path contract.",
    }


def main() -> None:
    payload = probe()
    DEFAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
