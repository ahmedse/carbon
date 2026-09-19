"""Demo / gold example texts for Student desk + seed_gradevance_demo."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gradevance.services.packs import eduos_pack_root
from gradevance.services.publish import load_held_out_rows

DEMO_SPECS: list[dict[str, Any]] = [
    {
        "profile_pack_id": "naa_cycle1_exam_prep",
        "profile_version": 1,
        "device_rel": "engines/lct_semantics/naa_reflective_v1",
        "gold_files": ["gold/naa/AR-CYCLE1-18-week1.json"],
        "title": "NAA Cycle 1 — Exam prep (demo)",
    },
    {
        "profile_pack_id": "medicine_cbl_appendicitis",
        "profile_version": 1,
        "device_rel": "engines/lct_semantics/medicine_cbl_v1",
        "gold_files": [],
        "title": "Medicine CBL — Appendicitis (demo)",
    },
    {
        "profile_pack_id": "medicine_osce_abdominal",
        "profile_version": 1,
        "device_rel": "engines/lct_semantics/medicine_clinical_reflection_v1",
        "gold_files": [],
        "title": "Medicine OSCE abdominal reflection (demo)",
    },
    {
        "profile_pack_id": "article_generic_formative",
        "profile_version": 1,
        "device_rel": "engines/lct_semantics/article_argumentative_v1",
        "gold_files": [],
        "title": "Article formative (demo)",
    },
]

NAA_SD_EXAMPLE = {
    "id": "RAW-LCT-SD-IELTS",
    "source": "raw/LCT Reflective Wave criteria (Category 2 + 4 anchors)",
    "text": (
        "I spent 4 hours each day on rewriting IELTS writing test and I studies "
        "hundreds of vocabularies like nouns and academic word list. "
        "My performance within GaoKao exam was not good enough because it did "
        "not reflect my English speaking skills, skill that I tested via IELTS and got 7. "
        "Exams in high school they take about 7-9 hours of learning and preparing "
        "each day. Last year more than 7 millions students had to compete in Gao Kao. "
        "So what I learned is that concrete daily practice on IELTS tasks built density "
        "in my reflection that the high-stakes Gaokao score never showed. "
        "Now what I will do is keep timed writing drills twice a week and ask a tutor "
        "to mark one draft for wave movement from abstract goals to specific examples."
    ),
}

# Long reflective essay with 10 explicit epistemic moves — for rich wave demos.
# Texts alternate concrete (SG+) and abstract (SG−) so the 4-level profile oscillates.
WAVE_10_SEGMENTS: list[dict[str, str]] = [
    {
        "stage_guess": "what",
        "text": (
            "In my first week on the ward I felt overwhelmed by the pace of handover "
            "and the noise of monitors. I spent hours describing what happened to me "
            "on each shift rather than asking why the protocols existed."
        ),
    },
    {
        "stage_guess": "so_what",
        "text": (
            "Later I noticed a general principle: junior voices were discounted when "
            "they questioned routines, which is a normal aspect of hierarchy that "
            "makes practice-based knowing difficult to legitimize."
        ),
    },
    {
        "stage_guess": "what",
        "text": (
            "For example, when I raised a missed observation about a patient I had "
            "just completed checks on, a senior smiled and moved on without recording "
            "my concern in the notes that afternoon."
        ),
    },
    {
        "stage_guess": "so_what",
        "text": (
            "However I began to connect this to epistemic injustice as a concept: "
            "some knowers are treated as less credible because of status, a strategy "
            "of silencing that transfers across wards and specialties."
        ),
    },
    {
        "stage_guess": "what",
        "text": (
            "Therefore I started writing short notes after each shift. I always "
            "recorded whose knowledge counted in the room and which claims were "
            "treated as optional when I was doing evening handover."
        ),
    },
    {
        "stage_guess": "so_what",
        "text": (
            "Thus the concrete incident of being ignored became a theoretical claim "
            "about how semantic gravity moves from feelings toward transferable "
            "ideas about justice and knowledge principles."
        ),
    },
    {
        "stage_guess": "what",
        "text": (
            "Later I realized my earlier diary entries were almost all narration. "
            "For example in week three I only wrote that I feel tired and that "
            "handover was scary, with no evaluation of why."
        ),
    },
    {
        "stage_guess": "now_what",
        "text": (
            "So I designed a tiny experiment: ask one clarifying question in every "
            "handover for five days. I completed the drills and tracked whether my "
            "contribution was taken up by the team on each occasion."
        ),
    },
    {
        "stage_guess": "so_what",
        "text": (
            "Later I reflected that legitimation codes helped me see the wave as a "
            "general strategy: from concrete incident, through theory, back to "
            "action. Naming weaker gravity made tutoring feedback sharper in principle."
        ),
    },
    {
        "stage_guess": "now_what",
        "text": (
            "Therefore next month I will keep a two-column notebook: episode on the "
            "left, principle and next action on the right, so the reflective wave "
            "stays intentional rather than accidental when I am tired after nights."
        ),
    },
]


def wave_10_essay_text() -> str:
    return " ".join(s["text"].strip() for s in WAVE_10_SEGMENTS)


def wave_10_segment_spans() -> list[dict]:
    """Word-span ExpertEdit payload for the 10-move wave essay."""
    words: list[str] = []
    spans: list[dict] = []
    for i, s in enumerate(WAVE_10_SEGMENTS):
        toks = (s["text"] or "").split()
        start = len(words)
        words.extend(toks)
        end = len(words)
        spans.append(
            {
                "ordinal": i,
                "start_word": start,
                "end_word": end,
                "stage_guess": s["stage_guess"],
                "text": " ".join(toks),
            }
        )
    return spans


WAVE_10_EXAMPLE = {
    "id": "DEMO-WAVE-10",
    "source": "gradevance.services.demo_examples.WAVE_10_SEGMENTS",
    "text": wave_10_essay_text(),
    "segments": WAVE_10_SEGMENTS,
}


def collect_demo_texts(spec: dict) -> list[dict]:
    root = eduos_pack_root()
    out: list[dict] = []
    seen: set[str] = set()

    for rel in spec.get("gold_files") or []:
        path = root / rel
        if not path.is_file():
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        text = (row.get("text") or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(
                {
                    "id": row.get("id") or Path(rel).stem,
                    "source": row.get("source") or rel,
                    "text": text,
                }
            )

    for row in load_held_out_rows(spec["device_rel"]):
        text = (row.get("text") or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(
                {
                    "id": row.get("id") or "held_out",
                    "source": row.get("source") or spec["device_rel"],
                    "text": text,
                }
            )

    if spec["profile_pack_id"] == "naa_cycle1_exam_prep":
        t = NAA_SD_EXAMPLE["text"]
        if t not in seen:
            out.append(dict(NAA_SD_EXAMPLE))
        w10 = WAVE_10_EXAMPLE["text"]
        if w10 not in seen:
            out.append(
                {
                    "id": WAVE_10_EXAMPLE["id"],
                    "source": WAVE_10_EXAMPLE["source"],
                    "text": w10,
                }
            )

    return out


def list_demo_examples() -> list[dict]:
    results = []
    for spec in DEMO_SPECS:
        for ex in collect_demo_texts(spec):
            results.append(
                {
                    "id": ex["id"],
                    "profile_pack_id": spec["profile_pack_id"],
                    "profile_version": spec["profile_version"],
                    "title": f"{spec['title']} · {ex['id']}",
                    "source": ex.get("source") or "",
                    "text": ex["text"],
                    "word_count": len(ex["text"].split()),
                }
            )
    return results
