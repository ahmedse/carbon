"""Consent resume: a bare "yes" must run the action the assistant proposed.

Regression cover for the Nibras leave loop — "ايوة" was hard-refused as
off-limits, "نعم" produced "complete the confirmation in the system first",
and nothing was ever submitted.
"""
from __future__ import annotations

import pytest

from ai.engine.cognition.dialogue.affirmation import (
    is_affirmation,
    normalize,
    starts_with_affirmation,
)
from ai.engine.cognition.dialogue.deixis import is_confirm_reply
from ai.engine.cognition.dialogue.pending_mutation import (
    PendingMutationStore,
    build_resume_message,
    detect_action_proposal,
)
from ai.engine_runtime import (
    _apply_consent_resume,
    _human_action_label,
    _record_consent_proposal,
    _strip_staged_deflection,
    apply_anti_hallucination_gate,
)


# ── Affirmation vocabulary ───────────────────────────────────────────────────

@pytest.mark.parametrize("message", [
    "ايوة",        # teh-marbuta spelling — the one that hard-refused
    "أيوة",
    "ايوه",
    "نعم",
    "أيوه",
    "تمام",
    "ماشي",
    "اوك",
    "yes",
    "Yes!",
    "ok",
    "go ahead",
    "do it",
    "yes please",
])
def test_short_affirmatives_are_recognised(message):
    assert is_affirmation(message) is True


@pytest.mark.parametrize("message", [
    "لا",
    "no",
    "not now",
    "ايه ده",                      # Egyptian "what is this?" — not a yes
    "yes but only if there is balance left",
    "هل أقدمها؟",
    "",
])
def test_non_affirmatives_are_rejected(message):
    assert is_affirmation(message) is False


def test_arabic_normalization_folds_orthography():
    assert normalize("أيوة") == normalize("ايوه")
    assert normalize("نَعَم") == "نعم"


def test_confirm_reply_delegates_to_affirmation():
    assert is_confirm_reply("ايوة") is True
    assert is_confirm_reply("yes, the annual one") is True
    assert starts_with_affirmation("yes, the annual one") is True


# ── Proposal detection ───────────────────────────────────────────────────────

ARABIC_PROPOSAL = (
    "سأقوم بإعداد طلب إجازة سنوية لمدة يومين بدءًا من يوم غد. "
    "يرجى التأكيد قبل تقديم الطلب. نوع الإجازة: سنوية، تاريخ البداية: "
    "22 سبتمبر 2026. هل أتابع بتقديم الطلب؟"
)

ENGLISH_PROPOSAL = (
    "I'll submit two days of annual leave starting tomorrow. "
    "Shall I proceed?"
)


#: Wordings that previously reopened the loop — each one is the same offer
#: phrased differently, which is why detection is marker-based, not phrasal.
REWORDED_PROPOSALS = [
    "هل تريدني الآن أن أبدأ تعديل الخطة (Replan)؟",
    "لإكمال الخطة، يمكنني الآن إنشاء خطة جديدة أو تعديل الخطة الحالية. "
    "هل تريدني أن أبدأ التنفيذ؟",
    "سأقوم بتحديث التفاصيل لتشمل طلب إجازة عادية ليوم واحد. هل أتابع؟",
    "I can update the plan to one day starting tomorrow. Shall I proceed?",
    "Let me know if you'd like me to submit this leave request.",
]


@pytest.mark.parametrize("text", [ARABIC_PROPOSAL, ENGLISH_PROPOSAL, *REWORDED_PROPOSALS])
def test_detects_prose_action_proposal(text):
    assert detect_action_proposal(text) == text


@pytest.mark.parametrize("affirmation", ["نعم", "تمام كمل", "كمل", "yes"])
def test_reworded_plan_offer_resumes_on_any_affirmation(affirmation):
    conv = f"conv-replan-{affirmation}"
    _record_consent_proposal(
        conv, "هل تريدني الآن أن أبدأ تعديل الخطة (Replan)؟",
        pending_actions=[], user_message="عدل الخطة", was_resume=False,
    )
    message, resumed = _apply_consent_resume(conv, affirmation)
    assert resumed is True
    assert "تعديل الخطة" in message


@pytest.mark.parametrize("text", [
    "You have 23 days of annual leave remaining.",
    "رصيدك من الإجازات الطارئة هو صفر.",
    "",
])
def test_plain_answers_are_not_proposals(text):
    assert detect_action_proposal(text) is None


def test_resume_message_carries_the_proposal_details():
    resumed = build_resume_message(ARABIC_PROPOSAL, original_request="اريد اجازة")
    assert "22 سبتمبر 2026" in resumed
    assert "اريد اجازة" in resumed
    assert "do not ask the same confirmation question again" in resumed


# ── Store lifecycle ──────────────────────────────────────────────────────────

def test_store_returns_proposal_only_on_affirmation():
    store = PendingMutationStore()
    store.set_pending("c1", ENGLISH_PROPOSAL)
    assert store.take_if_affirmed("c1", "what is my balance?") is None
    assert store.take_if_affirmed("c1", "ايوة")["proposal"] == ENGLISH_PROPOSAL
    # Consumed — a second yes must not re-fire the same action.
    assert store.take_if_affirmed("c1", "yes") is None


def test_store_ages_out_stale_proposals():
    store = PendingMutationStore()
    store.set_pending("c1", ENGLISH_PROPOSAL, ttl_turns=2)
    store.age_out("c1")
    assert store.get("c1") is not None
    store.age_out("c1")
    assert store.get("c1") is None


# ── Runtime wiring ───────────────────────────────────────────────────────────

def test_affirmation_of_leave_proposal_reissues_original_not_tool_force():
    """ADR-0046: Chat yes on leave prose must not CALL THE TOOL."""
    conv = "conv-consent-1"
    _record_consent_proposal(
        conv, ARABIC_PROPOSAL, pending_actions=[], user_message="اريد اجازة",
        was_resume=False,
    )
    message, resumed = _apply_consent_resume(conv, "ايوة")
    assert resumed is True
    assert message == "اريد اجازة"
    assert "CALL" not in message.upper()
    assert "stages the action" not in message


def test_no_proposal_leaves_the_message_untouched():
    message, resumed = _apply_consent_resume("conv-consent-2", "ايوة")
    assert resumed is False
    assert message == "ايوة"


def test_staged_card_supersedes_the_prose_proposal():
    conv = "conv-consent-3"
    _record_consent_proposal(
        conv, ARABIC_PROPOSAL,
        pending_actions=[{"kind": "host", "execution_id": "e1"}],
        user_message="اريد اجازة", was_resume=False,
    )
    message, resumed = _apply_consent_resume(conv, "نعم")
    assert resumed is False
    assert message == "نعم"


# ── Staged-action copy ───────────────────────────────────────────────────────

def test_human_action_label_has_no_method_or_path():
    label = _human_action_label({
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "submit_my_leave"},
    })
    assert label == "Your leave"
    assert "POST" not in label and "/" not in label


@pytest.mark.parametrize("prose", [
    "يبدو أن هناك خطوة تأكيد مطلوبة من النظام الأساسي قبل تقديم طلب الإجازة. "
    "يُرجى إكمال عملية التأكيد المطلوبة أولاً، ثم المحاولة مرة أخرى.",
    "Submitting your leave request requires additional confirmation through "
    "the system. Please complete the confirmation process there first, and "
    "then try again.",
])
def test_staged_turn_strips_go_confirm_elsewhere_prose(prose):
    staged_tool = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "submit_my_leave"},
        "result": {
            "requires_confirmation": True,
            "execution_id": "e1",
            "method": "POST",
            "endpoint": "/carbon-api/people/me/leave/",
        },
    }
    corrected, flags = apply_anti_hallucination_gate(prose, [staged_tool])
    assert "staged_deflection_corrected" in flags
    assert "try again" not in corrected.lower()
    assert "إكمال عملية التأكيد" not in corrected


def test_deflection_strip_keeps_the_useful_sentences():
    text = (
        "Your leave request is drafted for 22-23 September. "
        "Please complete the confirmation process there first."
    )
    corrected, removed = _strip_staged_deflection(text)
    assert removed is True
    assert "22-23 September" in corrected
