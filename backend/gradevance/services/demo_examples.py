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
