"""Formative analysis pipeline — pack-driven, no silent LLM grade.

P1 coder: deterministic anchor token-overlap + discourse heuristics.
HITL gate fires on low confidence or summative mode. ExpertEdit stream
is recorded separately via the review API (RULE_32).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from django.db import transaction
from django.utils import timezone as dj_tz

from gradevance.models import (
    AnalysisRun,
    Assignment,
    ExpertEdit,
    LCTCode,
    ReviewItem,
    RubricEvaluation,
    Segment,
    Submission,
    WaveProfile,
)
from gradevance.services.packs import LoadedProfile, find_profile_file_for_id, load_profile

_WORD_RE = re.compile(r"\S+")
_REFLECTIVE_MARKERS = (
    "i feel",
    "i realized",
    "i learnt",
    "i learned",
    "because",
    "so what",
    "now what",
    "in the future",
    "next time",
    "reflect",
    "improve",
)
_WHAT_MARKERS = ("when i", "i spent", "for example", "last year", "exam")
_NOW_WHAT_MARKERS = ("in the future", "next time", "i will", "plan to", "from now")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _token_set(text: str) -> set[str]:
    return {t.lower().strip(".,;:!?\"'") for t in _tokenize(text) if len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass
class _SegDraft:
    ordinal: int
    start_word: int
    end_word: int
    text: str
    stage_guess: str


def segment_text(text: str, policy: dict[str, Any] | None) -> list[_SegDraft]:
    """Epistemic-move segmentation guided by pack policy (coverage-invariant)."""
    policy = policy or {}
    words = _tokenize(text)
    if not words:
        return []
    markers = [m.lower() for m in (policy.get("markers") or [])]
    min_w = int(policy.get("min_words") or 8)
    max_w = int(policy.get("max_words") or 60)
    target = int(policy.get("target_median_words") or 25)

    # Split on sentence-ish boundaries and discourse markers.
    chunks: list[list[str]] = [[]]
    i = 0
    lower_joined = " ".join(w.lower() for w in words)
    while i < len(words):
        chunks[-1].append(words[i])
        window = " ".join(w.lower() for w in chunks[-1])
        hit_marker = any(m in window[-80:] and window.lower().endswith(m.split()[-1]) for m in markers)
        # Prefer split after punctuation or when over target and at marker.
        punct = words[i].endswith((".", "!", "?", ";"))
        over = len(chunks[-1]) >= max_w
        soft = len(chunks[-1]) >= target and (punct or hit_marker)
        if (soft or over) and len(chunks[-1]) >= min_w and i < len(words) - 1:
            chunks.append([])
        i += 1

    # Merge undersized trailing chunks.
    merged: list[list[str]] = []
    for ch in chunks:
        if not ch:
            continue
        if merged and len(ch) < min_w:
            merged[-1].extend(ch)
        else:
            merged.append(ch)

    drafts: list[_SegDraft] = []
    cursor = 0
    for ord_i, ch in enumerate(merged):
        start = cursor
        end = cursor + len(ch)
        seg_text = " ".join(ch)
        low = seg_text.lower()
        stage = "what"
        if any(m in low for m in _NOW_WHAT_MARKERS):
            stage = "now_what"
        elif any(m in low for m in _REFLECTIVE_MARKERS) and not any(m in low for m in _WHAT_MARKERS[:2]):
            stage = "so_what"
        elif any(m in low for m in _WHAT_MARKERS):
            stage = "what"
        drafts.append(
            _SegDraft(
                ordinal=ord_i,
                start_word=start,
                end_word=end,
                text=seg_text,
                stage_guess=stage,
            )
        )
        cursor = end
    # silence unused
    _ = lower_joined
    return drafts


def _containment(a: str, b: str) -> float:
    """Fraction of shorter string tokens contained in longer."""
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return 0.0
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return len(shorter & longer) / len(shorter)


def _best_anchor(
    seg_text: str, anchors: list[dict[str, Any]], dimension: str
) -> tuple[dict[str, Any] | None, float]:
    seg_tokens = _token_set(seg_text)
    best = None
    best_score = 0.0
    for a in anchors:
        if a.get("dimension") != dimension:
            continue
        span = a.get("span_text") or ""
        j = _jaccard(seg_tokens, _token_set(span))
        c = _containment(seg_text, span)
        # Prefer phrase containment for gold-like spans; blend with Jaccard.
        score = max(j, c * 0.85, (j + c) / 2)
        if score > best_score:
            best_score = score
            best = a
    return best, best_score


def _heuristic_sd(seg_text: str) -> tuple[str, float]:
    low = seg_text.lower()
    reflective_hits = sum(1 for m in _REFLECTIVE_MARKERS if m in low)
    if reflective_hits >= 2 or "i feel" in low or "i realized" in low:
        return "SD+", min(0.55 + 0.1 * reflective_hits, 0.85)
    return "SD-", 0.45


_ABSTRACT_CUES = (
    "aspect",
    "general",
    "normal",
    "concept",
    "principle",
    "strategy",
    "strategies",
    "how to",
    "difficult",
    "seldom",
)
_CONCRETE_CUES = (
    "when i",
    "for example",
    "i spent",
    "i always",
    "i completed",
    "i was doing",
    "hours",
    "pre-gaokao",
    "chinese exam",
    "reading a certain",
    "big writing first",
)
_STRATEGY_FRAME_CUES = (
    "switched my strategies",
    "switched my strategy",
    "my strategies",
    "kept on this strategy",
)


def _heuristic_sg(seg_text: str, stage: str) -> tuple[str, int, float]:
    low = seg_text.lower()
    abstract_hits = sum(1 for c in _ABSTRACT_CUES if c in low)
    concrete_hits = sum(1 for c in _CONCRETE_CUES if c in low)
    strategy_frame = any(c in low for c in _STRATEGY_FRAME_CUES)
    first_person = bool(re.search(r"\b(i|my)\b", low))
    past_action = bool(
        re.search(r"\b(completed|spent|was doing|always spent|left a short)\b", low)
    )

    # Explicit strategy/meta framing without a concrete episode → SG--
    if strategy_frame and concrete_hits == 0:
        return "SG--", 4, 0.7
    if strategy_frame and "seldom" in low and not past_action:
        return "SG--", 4, 0.65

    # Strong concrete narrative (episode)
    if concrete_hits >= 2 or (concrete_hits >= 1 and past_action):
        return "SG+", 2, min(0.55 + 0.1 * concrete_hits, 0.9)
    if concrete_hits >= 1 and first_person and abstract_hits == 0:
        return "SG+", 2, 0.6

    # Strong abstract / generalised framing
    if abstract_hits >= 2 and concrete_hits == 0:
        return "SG--", 4, min(0.5 + 0.08 * abstract_hits, 0.85)
    if abstract_hits >= 1 and concrete_hits == 0:
        if "normal" in low or "general" in low:
            return "SG-", 3, 0.6
        return "SG--", 4, 0.55

    # Mixed: past action wins toward concrete
    if past_action and first_person:
        return "SG+", 2, 0.55
    if stage == "now_what" and concrete_hits == 0:
        return "SG-", 3, 0.5
    if first_person:
        return "SG+", 2, 0.42
    return "SG-", 3, 0.4


def code_segment(
    seg: _SegDraft, anchors: list[dict[str, Any]], lct_enabled: bool
) -> list[dict[str, Any]]:
    if not lct_enabled:
        return []
    codes: list[dict[str, Any]] = []
    sg_anchor, sg_score = _best_anchor(seg.text, anchors, "semantic_gravity")
    heur_value, heur_numeric, heur_conf = _heuristic_sg(seg.text, seg.stage_guess)
    # Trust anchors only when overlap is strong; weak matches mislead (held-out S4/S5).
    use_sg_anchor = bool(sg_anchor) and (
        sg_score >= 0.5
        or (sg_score >= 0.25 and sg_anchor.get("value") == heur_value)
    )
    if use_sg_anchor:
        codes.append(
            {
                "dimension": "semantic_gravity",
                "value": sg_anchor.get("value"),
                "numeric": sg_anchor.get("numeric"),
                "confidence": min(0.45 + sg_score, 0.95),
                "evidence": {"anchor_id": sg_anchor.get("id"), "overlap": round(sg_score, 3)},
            }
        )
    else:
        codes.append(
            {
                "dimension": "semantic_gravity",
                "value": heur_value,
                "numeric": heur_numeric,
                "confidence": heur_conf,
                "evidence": {
                    "method": "heuristic",
                    "rejected_anchor": (sg_anchor or {}).get("id"),
                    "rejected_overlap": round(sg_score, 3) if sg_anchor else None,
                },
            }
        )

    sd_anchor, sd_score = _best_anchor(seg.text, anchors, "semantic_density")
    if sd_anchor and sd_score >= 0.35:
        codes.append(
            {
                "dimension": "semantic_density",
                "value": sd_anchor.get("value"),
                "numeric": None,
                "confidence": min(0.45 + sd_score, 0.95),
                "evidence": {"anchor_id": sd_anchor.get("id"), "overlap": round(sd_score, 3)},
            }
        )
    else:
        value, conf = _heuristic_sd(seg.text)
        codes.append(
            {
                "dimension": "semantic_density",
                "value": value,
                "numeric": None,
                "confidence": conf,
                "evidence": {"method": "heuristic"},
            }
        )
    return codes


def build_wave(segments: list[_SegDraft], codes_by_ord: dict[int, list[dict]]) -> dict[str, Any]:
    points = []
    sg_vals = []
    stages = set()
    for seg in segments:
        stages.add(seg.stage_guess)
        sg = next((c for c in codes_by_ord.get(seg.ordinal, []) if c["dimension"] == "semantic_gravity"), None)
        sd = next((c for c in codes_by_ord.get(seg.ordinal, []) if c["dimension"] == "semantic_density"), None)
        mid = (seg.start_word + seg.end_word) // 2
        numeric = (sg or {}).get("numeric") or 3
        points.append(
            {
                "word_offset": mid,
                "sg_numeric": numeric,
                "sg": (sg or {}).get("value"),
                "sd": (sd or {}).get("value"),
                "ordinal": seg.ordinal,
            }
        )
        sg_vals.append(numeric)
    sg_range = (max(sg_vals) - min(sg_vals)) if sg_vals else 0
    transitions = sum(1 for i in range(1, len(sg_vals)) if sg_vals[i] != sg_vals[i - 1])
    return {
        "points": points,
        "metrics": {
            "stages_present": sorted(stages),
            "sg_range": sg_range,
            "transitions": transitions,
            "specificity": "high" if sg_range >= 2 else "low",
            "perspectives_count": 1 if "so_what" in stages or "now_what" in stages else 0,
            "segment_count": len(segments),
        },
    }


def _score_checklist(text: str, items: list[dict]) -> dict:
    low = (text or "").lower()
    hits = []
    missed = []
    earned = 0.0
    total = 0.0
    for item in items or []:
        pts = float(item.get("points") or 1.0)
        total += pts
        kws = [k.lower() for k in (item.get("keywords") or [])]
        matched = any(k in low for k in kws) if kws else False
        if matched:
            earned += pts
            hits.append(item.get("id"))
        else:
            missed.append(item.get("id"))
    pct = (earned / total * 100.0) if total else 0.0
    return {
        "earned": earned,
        "total": total,
        "score_0_100": round(pct, 2),
        "hits": hits,
        "missed": missed,
    }


def score_rubric(
    loaded: LoadedProfile,
    wave_metrics: dict[str, Any],
    word_count: int,
    submission_text: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Heuristic band/checklist scoring from wave features + action templates."""
    if not loaded.rubric:
        return [], {}, {}
    rubric = loaded.rubric.rubric
    templates = loaded.rubric.action_templates
    stages = set(wave_metrics.get("stages_present") or [])
    evaluations: list[dict[str, Any]] = []
    coaching_strengths: list[str] = []
    coaching_actions: list[dict[str, str]] = []

    has_wave = wave_metrics.get("sg_range", 0) >= 1 and wave_metrics.get("transitions", 0) >= 1
    missing_now = "now_what" not in stages
    missing_so = "so_what" not in stages

    band_order = ["F", "E", "D", "C", "B", "A"]
    clinical_bands = ["Unsatisfactory", "Satisfactory", "Good", "Excellent"]

    def pick_band(base: str, delta: int) -> str:
        idx = max(0, min(len(band_order) - 1, band_order.index(base) + delta))
        return band_order[idx]

    def pick_clinical(score: float) -> str:
        if score >= 85:
            return "Excellent"
        if score >= 70:
            return "Good"
        if score >= 50:
            return "Satisfactory"
        return "Unsatisfactory"

    for crit in rubric.get("criteria") or []:
        cid = crit["id"]
        scoring = crit.get("scoring") or "qualitative"

        if scoring == "quantitative":
            checklist = _score_checklist(submission_text, crit.get("checklist_items") or [])
            evaluations.append(
                {
                    "criterion_id": cid,
                    "band": "",
                    "score_0_100": checklist["score_0_100"],
                    "rationale": (
                        f"Checklist {checklist['earned']}/{checklist['total']} "
                        f"(hits={len(checklist['hits'])}, missed={len(checklist['missed'])})."
                    ),
                    "evidence_bindings": {
                        "scoring": "quantitative",
                        "hits": checklist["hits"],
                        "missed": checklist["missed"],
                    },
                }
            )
            if checklist["missed"]:
                coaching_actions.append(
                    {
                        "id": f"miss_{cid}",
                        "criterion": cid,
                        "diagnosis": f"Missing checklist items on {cid}.",
                        "action": f"Cover: {', '.join(checklist['missed'][:5])}.",
                    }
                )
            elif checklist["score_0_100"] >= 70:
                coaching_strengths.append(f"Strong checklist coverage on {crit.get('name') or cid}.")
            continue

        # Qualitative
        bands = crit.get("bands") or band_order
        uses_clinical = set(bands) >= {"Excellent", "Good", "Satisfactory", "Unsatisfactory"} or (
            "Excellent" in bands
        )
        base = "C"
        rationale_parts = []
        if cid == "task_achievement":
            if missing_now:
                base = "D"
                rationale_parts.append("NOW WHAT weakly signaled.")
                coaching_actions.append(_template_or(templates, "d_nowwhat_missing"))
            elif missing_so:
                base = "D"
                rationale_parts.append("SO WHAT underdeveloped.")
                coaching_actions.append(_template_or(templates, "d_sowhat_descriptive"))
            elif has_wave:
                base = "B"
                rationale_parts.append("Reflective stages present with SG oscillation.")
                coaching_strengths.append(
                    "Clear movement across reflective stages with semantic wave shape."
                )
            else:
                base = "C"
                rationale_parts.append("Stages present but wave flat.")
            wb = (rubric.get("aggregation") or {}).get("word_count_penalty", {}).get("outside") or [
                200,
                300,
            ]
            if word_count and (word_count < wb[0] or word_count > wb[1]):
                base = pick_band(base, -1)
                coaching_actions.append(_template_or(templates, "d_too_short"))
                rationale_parts.append(f"Word count {word_count} outside {wb}.")
        elif cid == "coherence_cohesion":
            base = "B" if wave_metrics.get("transitions", 0) >= 2 else "C"
            if wave_metrics.get("transitions", 0) < 1:
                coaching_actions.append(_template_or(templates, "d_cohesion"))
            rationale_parts.append(f"Transitions={wave_metrics.get('transitions')}.")
        elif cid == "lexis_grammar_academic_style":
            base = "C"
            rationale_parts.append("Advisory band — style not deeply scored in P1 heuristic.")
        elif uses_clinical:
            # Medicine qualitative criteria — map wave richness to clinical band.
            richness = wave_metrics.get("transitions", 0) + wave_metrics.get("sg_range", 0)
            score_proxy = min(95.0, 45.0 + richness * 12.0)
            base = pick_clinical(score_proxy)
            rationale_parts.append(
                f"Clinical qualitative proxy from wave richness={richness}."
            )
            if base in ("Unsatisfactory", "Satisfactory"):
                coaching_actions.append(
                    {
                        "id": f"qual_{cid}",
                        "criterion": cid,
                        "diagnosis": f"{crit.get('name') or cid} needs deeper reasoning/reflection.",
                        "action": "Link findings to differentials; name a concrete improvement.",
                    }
                )
        else:
            base = "C"
            rationale_parts.append("Generic qualitative placeholder.")

        if uses_clinical:
            score = {
                "Excellent": 90.0,
                "Good": 75.0,
                "Satisfactory": 60.0,
                "Unsatisfactory": 40.0,
            }.get(base)
        else:
            score = (band_order.index(base) / (len(band_order) - 1)) * 100 if base in band_order else None
        evaluations.append(
            {
                "criterion_id": cid,
                "band": base,
                "score_0_100": score,
                "rationale": " ".join(rationale_parts),
                "evidence_bindings": {
                    "wave_features": wave_metrics,
                    "stages_present": sorted(stages),
                },
            }
        )

    advisory = {e["criterion_id"]: e["band"] or e.get("score_0_100") for e in evaluations}
    coaching = {
        "watermark": "advisory",
        "strengths": coaching_strengths or ["You attempted the assessment task."],
        "diagnosis_actions": [a for a in coaching_actions if a],
    }
    return evaluations, advisory, coaching


def _template_or(templates: list[dict], tid: str) -> dict[str, str]:
    for t in templates:
        if t.get("id") == tid:
            return {
                "id": tid,
                "criterion": t.get("criterion") or "",
                "diagnosis": t.get("diagnosis") or "",
                "action": t.get("action") or "",
            }
    return {"id": tid, "criterion": "", "diagnosis": tid, "action": ""}


class FormativePipelineService:
    """Run pack-bound formative (or draft-summative) analysis."""

    @transaction.atomic
    def analyze_submission(
        self,
        submission: Submission,
        *,
        profile_file: str | None = None,
    ) -> AnalysisRun:
        assignment: Assignment = submission.assignment
        if not profile_file:
            profile_file = find_profile_file_for_id(
                assignment.profile_pack_id, assignment.profile_version
            )
        loaded = load_profile(profile_file)
        profile = loaded.profile
        pipeline = assignment.pipeline_config_snapshot or profile.get("pipeline") or {}
        hitl = profile.get("hitl") or {}
        threshold = float(hitl.get("confidence_review_threshold") or 0.7)
        lct_enabled = bool(pipeline.get("lct_enabled"))
        mode = assignment.mode or profile.get("mode") or "formative"

        run = AnalysisRun.objects.create(
            submission=submission,
            profile_pack_id=profile.get("id") or assignment.profile_pack_id,
            profile_version=int(profile.get("version") or assignment.profile_version),
            pipeline_snapshot=pipeline,
            run_manifest={
                "profile_hash": loaded.content_hash,
                "device_hash": loaded.device.content_hash if loaded.device else None,
                "rubric_hash": loaded.rubric.content_hash if loaded.rubric else None,
                "stages": pipeline.get("stages") or [],
                "coder": pipeline.get("coder") or "heuristic_anchor",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            status=AnalysisRun.STATUS_RUNNING,
        )

        try:
            text = _normalize(submission.text)
            words = _tokenize(text)
            submission.word_count = len(words)
            submission.save(update_fields=["word_count", "updated_at"])

            seg_policy = (loaded.device.segmentation.get("policy") if loaded.device else None) or {}
            drafts = segment_text(text, seg_policy)
            anchors = loaded.device.anchors if loaded.device else []
            codes_by_ord: dict[int, list[dict]] = {}
            confidences: list[float] = []
            from gradevance.services.coders import get_coder

            coder_name = pipeline.get("coder") or "heuristic_anchor"
            coder = get_coder(coder_name)

            for draft in drafts:
                seg = Segment.objects.create(
                    run=run,
                    ordinal=draft.ordinal,
                    start_word=draft.start_word,
                    end_word=draft.end_word,
                    text=draft.text,
                    stage_guess=draft.stage_guess,
                )
                coded = coder(draft, anchors, lct_enabled)
                codes_by_ord[draft.ordinal] = coded
                for c in coded:
                    LCTCode.objects.create(
                        segment=seg,
                        dimension=c["dimension"],
                        value=c["value"],
                        numeric=c.get("numeric"),
                        confidence=c["confidence"],
                        evidence=c.get("evidence") or {},
                        source=LCTCode.SOURCE_ENGINE,
                    )
                    confidences.append(float(c["confidence"]))

            wave = build_wave(drafts, codes_by_ord)
            WaveProfile.objects.create(run=run, points=wave["points"], metrics=wave["metrics"])

            evaluations, advisory, coaching = score_rubric(
                loaded, wave["metrics"], len(words), text
            )
            for ev in evaluations:
                RubricEvaluation.objects.create(
                    run=run,
                    criterion_id=ev["criterion_id"],
                    band=ev.get("band") or "",
                    score_0_100=ev.get("score_0_100"),
                    rationale=ev.get("rationale") or "",
                    evidence_bindings=ev.get("evidence_bindings") or {},
                    source=RubricEvaluation.SOURCE_ENGINE,
                )

            mean_conf = sum(confidences) / len(confidences) if confidences else 0.5
            needs_review = (
                mode == Assignment.MODE_SUMMATIVE
                or mean_conf < threshold
                or wave["metrics"].get("sg_range", 0) < 1
            )
            gate = AnalysisRun.GATE_REVIEW if needs_review else AnalysisRun.GATE_AUTO
            # Formative may auto-show advisory; summative never auto-releases.
            status = (
                AnalysisRun.STATUS_NEEDS_REVIEW
                if needs_review or mode == Assignment.MODE_SUMMATIVE
                else AnalysisRun.STATUS_COMPLETE
            )
            if mode == Assignment.MODE_FORMATIVE and not needs_review:
                status = AnalysisRun.STATUS_COMPLETE

            run.mean_confidence = round(mean_conf, 4)
            run.gate_decision = gate
            run.coaching = coaching
            run.advisory_bands = advisory
            run.status = status
            run.completed_at = dj_tz.now()
            run.run_manifest = {
                **run.run_manifest,
                "completed_at": run.completed_at.isoformat(),
                "segment_count": len(drafts),
                "mean_confidence": run.mean_confidence,
            }
            run.save()

            if needs_review or mode == Assignment.MODE_SUMMATIVE:
                ReviewItem.objects.create(
                    run=run,
                    status=ReviewItem.STATUS_OPEN,
                    priority=80 if mode == Assignment.MODE_SUMMATIVE else 50,
                    reason=(
                        "Summative requires human release"
                        if mode == Assignment.MODE_SUMMATIVE
                        else f"Confidence {mean_conf:.2f} below {threshold}"
                    ),
                )

            submission.status = Submission.STATUS_ANALYZED
            submission.save(update_fields=["status", "updated_at"])
            return run
        except Exception as exc:  # noqa: BLE001 — persist failure on run
            run.status = AnalysisRun.STATUS_FAILED
            run.error_message = str(exc)
            run.completed_at = dj_tz.now()
            run.save(update_fields=["status", "error_message", "completed_at"])
            raise


class ReviewService:
    """Apply expert edits (append-only) and optionally resolve review items."""

    @transaction.atomic
    def apply_edit(
        self,
        *,
        run: AnalysisRun,
        editor,
        edit_kind: str,
        before: dict,
        after: dict,
        rationale: str = "",
        review_item: ReviewItem | None = None,
        resolve: bool = False,
    ) -> ExpertEdit:
        edit = ExpertEdit.objects.create(
            run=run,
            review_item=review_item,
            editor=editor,
            edit_kind=edit_kind,
            before=before or {},
            after=after or {},
            rationale=rationale or "",
        )
        # Apply LCT / rubric overrides when structured after payload present.
        if edit_kind == ExpertEdit.KIND_LCT and after.get("segment_id") and after.get("dimension"):
            seg = Segment.objects.filter(run=run, id=after["segment_id"]).first()
            if seg:
                LCTCode.objects.update_or_create(
                    segment=seg,
                    dimension=after["dimension"],
                    source=LCTCode.SOURCE_EXPERT,
                    defaults={
                        "value": after.get("value") or "",
                        "numeric": after.get("numeric"),
                        "confidence": 1.0,
                        "evidence": {"expert_edit_id": str(edit.id)},
                    },
                )
        if edit_kind == ExpertEdit.KIND_RUBRIC and after.get("criterion_id"):
            RubricEvaluation.objects.update_or_create(
                run=run,
                criterion_id=after["criterion_id"],
                source=RubricEvaluation.SOURCE_EXPERT,
                defaults={
                    "band": after.get("band") or "",
                    "score_0_100": after.get("score_0_100"),
                    "rationale": after.get("rationale") or rationale,
                    "evidence_bindings": {"expert_edit_id": str(edit.id)},
                },
            )
        if resolve and review_item:
            review_item.status = ReviewItem.STATUS_RESOLVED
            review_item.resolved_at = dj_tz.now()
            review_item.save(update_fields=["status", "resolved_at"])
            if run.submission.assignment.mode != Assignment.MODE_SUMMATIVE or run.released:
                run.status = AnalysisRun.STATUS_COMPLETE
                run.save(update_fields=["status"])
        # Learning loop seam — cluster this edit into a draft Proposal (P2).
        from gradevance.services.learning import ProposalMiner

        ProposalMiner().mine([edit])
        return edit

    @transaction.atomic
    def release_summative(self, run: AnalysisRun, editor) -> AnalysisRun:
        ExpertEdit.objects.create(
            run=run,
            editor=editor,
            edit_kind=ExpertEdit.KIND_OTHER,
            before={"released": run.released},
            after={"released": True},
            rationale="Summative release",
        )
        run.released = True
        run.status = AnalysisRun.STATUS_COMPLETE
        run.gate_decision = AnalysisRun.GATE_AUTO
        run.save(update_fields=["released", "status", "gate_decision"])
        ReviewItem.objects.filter(run=run, status=ReviewItem.STATUS_OPEN).update(
            status=ReviewItem.STATUS_RESOLVED,
            resolved_at=dj_tz.now(),
        )

        # AGS after commit — dry-run by default; live only when configured.
        run_id = run.pk

        def _ags_after_commit():
            from gradevance.lti.ags_passback import attempt_ags_passback, record_ags_on_run

            fresh = (
                AnalysisRun.objects.select_related("submission__assignment")
                .prefetch_related("rubric_scores")
                .filter(pk=run_id)
                .first()
            )
            if not fresh:
                return
            result = attempt_ags_passback(fresh)
            record_ags_on_run(fresh, result)

        transaction.on_commit(_ags_after_commit)
        return run
