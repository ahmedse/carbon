"""Gold-oracle coder — for calibration / canary only, NOT student grading.

Indexes held-out segments across known Semantics devices so non-NAA packs
can opt in via ``pipeline.coder: gold_oracle``.
"""
from __future__ import annotations

from gradevance.services.coders import register_coder
from gradevance.services.pipeline import _SegDraft, _heuristic_sd, code_segment
from gradevance.services.publish import load_held_out_rows

_GOLD_INDEX: dict[str, dict] | None = None

# Devices whose held_out.jsonl may supply gold labels.
_DEVICE_PACKS = (
    "engines/lct_semantics/naa_reflective_v1",
    "engines/lct_semantics/medicine_clinical_reflection_v1",
    "engines/lct_semantics/medicine_cbl_v1",
    "engines/lct_semantics/article_argumentative_v1",
)


def clear_gold_index() -> None:
    global _GOLD_INDEX
    _GOLD_INDEX = None


def _gold_index() -> dict[str, dict]:
    global _GOLD_INDEX
    if _GOLD_INDEX is not None:
        return _GOLD_INDEX
    idx: dict[str, dict] = {}
    for pack in _DEVICE_PACKS:
        for row in load_held_out_rows(pack):
            for seg in row.get("segments") or []:
                text = (seg.get("text") or "").strip().lower()
                if text and text not in idx:
                    idx[text] = seg
    _GOLD_INDEX = idx
    return idx


def gold_oracle_coder(seg: _SegDraft, anchors: list[dict], lct_enabled: bool) -> list[dict]:
    if not lct_enabled:
        return []
    hit = _gold_index().get((seg.text or "").strip().lower())
    if hit:
        codes = [
            {
                "dimension": "semantic_gravity",
                "value": hit.get("sg_label") or "SG-",
                "numeric": hit.get("sg_numeric"),
                "confidence": 1.0,
                "evidence": {"method": "gold_oracle", "segment_index": hit.get("segment_index")},
            }
        ]
        sd_label = hit.get("sd_label")
        if sd_label:
            codes.append(
                {
                    "dimension": "semantic_density",
                    "value": sd_label,
                    "numeric": None,
                    "confidence": 1.0,
                    "evidence": {"method": "gold_oracle"},
                }
            )
        else:
            sd_val, sd_conf = _heuristic_sd(seg.text)
            codes.append(
                {
                    "dimension": "semantic_density",
                    "value": sd_val,
                    "numeric": None,
                    "confidence": sd_conf,
                    "evidence": {"method": "heuristic"},
                }
            )
        return codes
    return code_segment(seg, anchors, lct_enabled)


register_coder("gold_oracle", gold_oracle_coder)
