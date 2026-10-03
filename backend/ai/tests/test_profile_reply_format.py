"""Profile/identity answers must use a labelled, emoji-free presentation (ADR-0057).

The observed defect: a model-drafted Arabic identity answer echoed the host's
English ``org_unit.name`` ("CEO Office") and ``job_title`` inline in a run-on
sentence and decorated them with emoji (🌙/📊). The owning layer for
model-generated text is the bound pack's persona + the endpoint's own catalog
description; the deterministic renderer for a declared profile read is
``render_catalog_read`` (kind: detail → pack ``field_labels``).

These tests fail before the fix: the pack carried no reply-format contract and
the profile description carried no presentation rule.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from ai.engine.cognition.turn.catalog_render import render_catalog_read
from ai.engine.cognition.turn.ess_read import resolve_profile_api

REPO = Path(__file__).resolve().parents[3]
NIBRAS = REPO / "domain_packs" / "nibras" / "instance.yaml"

# The emoji seen in the defect. A presentation is decorative-emoji-free when
# none of these code points appear.
_DECORATIVE_EMOJI = ("\U0001F319", "\U0001F4CA", "\U0001F464", "\U0001F4C7")


def _nibras_config() -> dict:
    return yaml.safe_load(NIBRAS.read_text(encoding="utf-8"))


def _profile_entry(cfg: dict) -> dict:
    for entry in cfg.get("api_catalog") or []:
        if isinstance(entry, dict) and entry.get("name") == "get_my_profile":
            return entry
    raise AssertionError("get_my_profile is not declared in nibras instance.yaml")


def _has_decorative_emoji(text: str) -> bool:
    return any(ch in text for ch in _DECORATIVE_EMOJI)


def test_persona_states_the_reply_format_contract():
    persona = str(_nibras_config().get("persona") or "")
    assert "decorative emoji" in persona
    assert "labelled lines" in persona
    assert "sentence" in persona


def test_profile_description_states_the_presentation_rule():
    desc = str(_profile_entry(_nibras_config()).get("description") or "")
    assert "labelled lines" in desc
    assert "no decorative emoji" in desc


def test_profile_render_uses_pack_labels_and_no_emoji():
    cfg = _nibras_config()
    entry = _profile_entry(cfg)
    # The declared render is a single labelled record (kind: detail).
    assert entry.get("kind") == "detail"
    assert "org_unit" in (entry.get("field_labels") or {})

    profile = {
        "full_name": "Ali Mohamed Saad AlAjmi",
        "employee_no": "2378",
        "job_title": "Director of Shared Services",
        "org_unit": {"id": 3, "name": "CEO Office"},
        "manager": {"id": 9, "name": "Ashraf Ahmed Oshi"},
        "is_active": True,
    }
    row = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "get_my_profile"},
        "result": {"status_code": 200, "data": profile},
    }
    out = render_catalog_read(row, "get_my_profile", "ar", catalog_entry=entry) or ""

    # Pack-owned Arabic labels, one fact per cell — not a run-on sentence.
    assert "الإدارة" in out
    assert "المسمى الوظيفي" in out
    # Host values stay exactly as returned (never translated, never dropped).
    assert "CEO Office" in out
    assert "Director of Shared Services" in out
    # No decorative emoji.
    assert not _has_decorative_emoji(out)


# ── Deterministic identity routing (ADR-0057) ──────────────────────────────
#
# The ask must resolve to the declared profile read *before* the conversational
# writer, so the reply is the pack's labelled detail render above. The
# vocabulary is the pack's own catalog ``examples`` / ``field_labels`` — the
# core carries no identity words (ADR-0050) and adds no phrase table.

_PROFILE_API = "get_my_profile"


def test_identity_ask_resolves_to_the_profile_read():
    cat = _nibras_config().get("api_catalog")
    # Direct asks: the existing first-person detector and the pack's examples.
    for ask in ("who am I", "my profile", "بياناتي"):
        assert resolve_profile_api(ask, catalog=cat) == _PROFILE_API, ask
    # The pack declares {ar: "من أنا؟"} as an example; a trailing ? is noise.
    assert resolve_profile_api("من أنا؟", catalog=cat) == _PROFILE_API
    assert resolve_profile_api("من أنا", catalog=cat) == _PROFILE_API


def test_compound_identity_ask_resolves_to_one_detail_read():
    cat = _nibras_config().get("api_catalog")
    compound = "من أنا ووش مسماي الوظيفي وقسمي ومديري؟"
    assert resolve_profile_api(compound, catalog=cat) == _PROFILE_API


def test_non_identity_ask_is_not_bound_to_the_profile():
    cat = _nibras_config().get("api_catalog")
    assert resolve_profile_api("what is the weather today", catalog=cat) is None
    # A longer ask that merely contains an example word is not over-bound.
    assert resolve_profile_api("my salary slip", catalog=cat) is None
    assert resolve_profile_api("", catalog=cat) is None


def test_profile_field_followup_continues_on_typed_state():
    cat = _nibras_config().get("api_catalog")
    after_read = SimpleNamespace(last_results=[{"api": _PROFILE_API}])
    # A follow-up that names a declared field right after the profile read
    # stays on the profile read (typed state, not a history scan).
    assert resolve_profile_api("من الإدارة؟", state=after_read, catalog=cat) == _PROFILE_API
    # No prior profile read → not a continuation.
    assert resolve_profile_api("من الإدارة؟", state=None, catalog=cat) is None
    other = SimpleNamespace(last_results=[{"api": "list_my_leave"}])
    assert resolve_profile_api("من الإدارة؟", state=other, catalog=cat) is None


def test_resolved_identity_ask_renders_labelled_and_value_intact():
    cfg = _nibras_config()
    entry = _profile_entry(cfg)
    api = resolve_profile_api("من أنا؟", catalog=cfg.get("api_catalog"))
    assert api == _PROFILE_API
    profile = {
        "full_name": "Bilagot Panta Suerte",
        "employee_no": "1067",
        "job_title": "Heavy Duty Driver",
        "org_unit": {"id": 2, "name": "Coiled Tubing"},
        "manager": {"id": 9, "name": "Mohammad Bolto Ali"},
        "is_active": True,
    }
    row = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": api},
        "result": {"status_code": 200, "data": profile},
    }
    out = render_catalog_read(row, api, "ar", catalog_entry=entry) or ""
    assert "الإدارة" in out and "المسمى الوظيفي" in out
    assert "Coiled Tubing" in out and "Heavy Duty Driver" in out
    assert not _has_decorative_emoji(out)
