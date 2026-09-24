"""Script schema, validators, and slot detectors for multi-turn coherence.

Loads declarative YAML scripts with validation, provides slot/language
detectors for coherence evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


# ── Slot regex table (bilingual) ─────────────────────────────────────────


SLOT_PATTERNS = {
    "amount": {
        "en": r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(sar|riyal|dinar|دينار|ر\.س|ريال)?",
        "ar": r"\d+(?:,\d{3})*(?:\.\d+)?",  # match numerals in Arabic
    },
    "loan_type": {
        "en": r"\b(emergency|personal|auto|home)\b",
        "ar": r"(طارئ|شخصي|سيارة|منزل)",
    },
    "leave_type": {
        "en": r"\b(annual|sick|compassionate|unpaid|sabbatical)\b",
        "ar": r"(سنوي|مرضي|استثنائي|بدون راتب|إجازة)",
    },
    "start_date": {
        "en": r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|January|February|March|April|May|June|July|August|September|October|November|December|Mon|Tue|Wed|Thu|Fri|Sat|Sun|today|tomorrow|next\s+\w+)\b",
        "ar": r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|اليوم|غدا|الاثنين|الثلاثاء|الأربعاء|الخميس|الجمعة|السبت|الأحد|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)",
    },
    "end_date": {
        "en": r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|January|February|March|April|May|June|July|August|September|October|November|December|Mon|Tue|Wed|Thu|Fri|Sat|Sun|today|tomorrow|next\s+\w+)\b",
        "ar": r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|اليوم|غدا|الاثنين|الثلاثاء|الأربعاء|الخميس|الجمعة|السبت|الأحد|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)",
    },
    "reason": {
        "en": r"\b(illness|family|emergency|personal|health|care|medical|injury)\b",
        "ar": r"(مرض|أسرة|طارئة|شخصية|صحة|رعاية|طبي|إصابة)",
    },
    "date": {
        "en": r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|January|February|March|April|May|June|July|August|September|October|November|December|Mon|Tue|Wed|Thu|Fri|Sat|Sun|today|tomorrow)\b",
        "ar": r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|اليوم|غدا|الاثنين|الثلاثاء|الأربعاء|الخميس|الجمعة|السبت|الأحد|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)",
    },
    "time_from": {
        "en": r"\b(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)\b",
        "ar": r"\d{1,2}:\d{2}",
    },
    "time_to": {
        "en": r"\b(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)\b",
        "ar": r"\d{1,2}:\d{2}",
    },
    "employee": {
        "en": r"\b(emp_\d+|employee\s*\d+|\d{4})\b",
        "ar": r"(موظف_\d+|\d{4})",
    },
}


def detect_language(text: str) -> str:
    """Detect language: 'ar', 'en', or 'mixed'.
    
    Uses Unicode range: Arabic ≥50% → 'ar', otherwise checks for English.
    """
    if not text:
        return "en"
    
    # Count Arabic script characters (U+0600–U+06FF)
    arabic_count = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    total_alpha = sum(1 for c in text if c.isalpha())
    
    if total_alpha == 0:
        return "en"
    
    arabic_ratio = arabic_count / total_alpha
    
    if arabic_ratio >= 0.5:
        return "ar"
    elif arabic_ratio >= 0.1:
        return "mixed"
    else:
        return "en"


def reasks_slot(reply: str, slot: str) -> bool:
    """Check if `reply` re-asks for a slot that should have been given.
    
    Looks for question patterns asking for the slot value.
    Examples:
    - "What is the amount?" → reasks "amount"
    - "ما المبلغ؟" → reasks "amount"
    """
    reask_patterns = {
        "amount": {
            "en": r"(how much|what.{1,5}amount|which amount|amount\?)",
            "ar": r"ما.{0,3}(مبلغ|قيمة)",
        },
        "loan_type": {
            "en": r"(type|kind).*loan.*\?",
            "ar": r"(ما|أي).نوع.قرض",
        },
        "leave_type": {
            "en": r"(type|kind).*leave.*\?",
            "ar": r"(ما|أي).نوع.إجازة",
        },
        "start_date": {
            "en": r"(when|start|begin).*\?",
            "ar": r"(متى|تاريخ.البداية)",
        },
        "end_date": {
            "en": r"(when|end|until).*\?",
            "ar": r"(متى|تاريخ.النهاية)",
        },
        "reason": {
            "en": r"(why|reason).*\?",
            "ar": r"(لماذا|السبب)",
        },
        "date": {
            "en": r"(when|date).*\?",
            "ar": r"(متى|التاريخ)",
        },
        "time_from": {
            "en": r"(start.*time|from).*\?",
            "ar": r"(الوقت.الابتدائي)",
        },
        "time_to": {
            "en": r"(end.*time|until).*\?",
            "ar": r"(الوقت.النهائي)",
        },
        "employee": {
            "en": r"(employee|which).*\?",
            "ar": r"(موظف|رقم)",
        },
    }
    
    if slot not in reask_patterns:
        return False
    
    lang = detect_language(reply)
    patterns = reask_patterns[slot]
    
    # Try both the detected language and English as fallback
    for l in [lang, "en"]:
        if l in patterns:
            if re.search(patterns[l], reply, re.IGNORECASE | re.DOTALL):
                return True
    
    return False


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class ExpectationBlock:
    """Per-turn expectation specification."""
    
    decision_in: list[str]  # which TurnDecision values are acceptable
    must_not_reask_slots: list[str] = field(default_factory=list)
    language: str = "en"  # expected language: ar | en | mixed
    max_llm_calls: int = 2  # upper bound on LLM invocations
    mentions_any: list[str] = field(default_factory=list)  # must mention ≥1 of these
    mentions_none: list[str] = field(default_factory=list)  # must not mention any of these
    focus_entity: Optional[str] = None  # entity/number the turn should focus on


@dataclass
class Turn:
    """Single conversation turn."""
    
    user: str  # user message
    stub_reply: str  # what the scripted LLM returns for this turn
    stub_tool_calls: Optional[list[dict]] = None  # tool calls stub (P1+)
    expect: Optional[ExpectationBlock] = None
    process_mode: str = "ask"


@dataclass
class Script:
    """Top-level declarative script."""
    
    id: str
    objective_ids: list[str]
    language: str  # ar | en | mixed
    surface: str  # chat | agent_discovery | agent_plan (P0: chat only)
    persona: str  # e.g. emp_1067
    turns: list[Turn]
    # Offline tier only: api_name → host payload. Bound 0-LLM reads restate
    # these rows instead of the empty throwaway database. Live tier ignores it.
    stub_host: dict = field(default_factory=dict)
    
    def validate(self) -> tuple[bool, str]:
        """Validate the script. Returns (ok, error_msg)."""
        if not self.id:
            return False, "Script must have an id"
        if not self.objective_ids:
            return False, f"Script {self.id} must have ≥1 objective_ids"
        for oid in self.objective_ids:
            if oid not in [f"C{i}" for i in range(1, 11)] + [f"A{i}" for i in range(1, 11)]:
                return False, f"Script {self.id}: invalid objective_id {oid}"
        if len(self.turns) < 7:
            return False, f"Script {self.id} must have ≥7 turns (has {len(self.turns)})"
        if self.language not in ["ar", "en", "mixed"]:
            return False, f"Script {self.id}: invalid language {self.language}"
        if self.surface != "chat":
            return False, f"Script {self.id}: P0 only supports surface='chat' (got {self.surface})"
        for i, turn in enumerate(self.turns):
            if not turn.user or not turn.stub_reply:
                return False, f"Script {self.id} turn {i}: user and stub_reply are required"
            # Validate slots referenced in must_not_reask_slots exist
            if turn.expect and turn.expect.must_not_reask_slots:
                for slot in turn.expect.must_not_reask_slots:
                    if slot not in SLOT_PATTERNS:
                        return False, f"Script {self.id} turn {i}: unknown slot {slot}"
        return True, ""


# ── YAML loader ───────────────────────────────────────────────────────────


def load_script_from_dict(data: dict) -> Script:
    """Load a script from a parsed YAML dict."""
    turns = []
    for turn_data in data.get("turns", []):
        expect_data = turn_data.get("expect", {})
        expect = ExpectationBlock(
            decision_in=expect_data.get("decision_in", ["answer"]),
            must_not_reask_slots=expect_data.get("must_not_reask_slots", []),
            language=expect_data.get("language", data.get("language", "en")),
            max_llm_calls=expect_data.get("max_llm_calls", 2),
            mentions_any=expect_data.get(
                "must_contain", expect_data.get("mentions_any", [])
            ),
            mentions_none=expect_data.get(
                "must_not_contain", expect_data.get("mentions_none", [])
            ),
            focus_entity=expect_data.get("focus_entity"),
        ) if expect_data else None
        
        turns.append(Turn(
            user=turn_data.get("user", ""),
            stub_reply=turn_data.get("stub_reply", ""),
            stub_tool_calls=turn_data.get("stub_tool_calls"),
            expect=expect,
            process_mode=(
                "plan" if turn_data.get("process_mode") == "plan" else "ask"
            ),
        ))
    
    script = Script(
        id=data.get("id", ""),
        objective_ids=data.get("objective_ids", []),
        language=data.get("language", "en"),
        surface=data.get("surface", "chat"),
        persona=data.get("persona", "emp_1067"),
        turns=turns,
        stub_host=dict(data.get("stub_host") or {}),
    )
    
    return script


def load_scripts_from_yaml(yaml_path: Path) -> Script:
    """Load a single script from YAML file."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"Empty YAML: {yaml_path}")
    
    script = load_script_from_dict(data)
    ok, err = script.validate()
    if not ok:
        raise ValueError(f"{yaml_path}: {err}")
    
    return script


def load_scripts_from_glob(pattern: str, base_dir: Path) -> list[Script]:
    """Load all scripts matching a glob pattern."""
    scripts = []
    for yaml_path in sorted(base_dir.glob(pattern)):
        try:
            script = load_scripts_from_yaml(yaml_path)
            scripts.append(script)
        except (yaml.YAMLError, ValueError) as e:
            raise ValueError(f"Failed to load {yaml_path}: {e}")
    return scripts
