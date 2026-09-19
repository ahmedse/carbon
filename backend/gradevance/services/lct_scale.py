"""LCT scale helpers — Maton SG± × SD± as product default; device.yaml is SoT.

Wisdom (Instrument Trust):
- Maton's pedagogic coding grid is binary SG+/SG- × SD+/SD-.
- Legacy 4-point SG++…SG-- was a wave-measurement extension that tutors rarely
  use; gold almost never labels SG++. Collapsing doubles → ± at load time keeps
  κ honest against device-declared binary levels without rewriting every JSONL.
- Devices may still declare ordinal if a faculty pack explicitly needs it —
  UI and coders must read ``device.scale``, never hardcode.
"""
from __future__ import annotations

from typing import Any

# Legacy ordinal → Maton binary (stronger SG = more concrete/context-dependent).
_SG_COLLAPSE = {
    "SG++": "SG+",
    "SG+": "SG+",
    "SG-": "SG-",
    "SG--": "SG-",
}

_DEFAULT_SG_BINARY = {
    "type": "binary",
    "levels": ["SG+", "SG-"],
    "numeric": [1, 2],
    "axis_note": (
        "Maton Semantics + Reflective Wave criteria: SG+ = specific/personal "
        "(stronger gravity); SG- = general (weaker gravity)."
    ),
}

_DEFAULT_SD_BINARY = {
    "type": "binary",
    "levels": ["SD-", "SD+"],
    "map": {"descriptive": "SD-", "reflective": "SD+"},
    "axis_note": (
        "Reflective Wave criteria: SD+ = reflective (evaluation / self-analysis); "
        "SD- = descriptive (report without deeper evaluation)."
    ),
}


def canonicalize_sg(value: str | None, *, collapse_legacy: bool = True) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if collapse_legacy and v in _SG_COLLAPSE:
        return _SG_COLLAPSE[v]
    return v


def canonicalize_sd(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    return v or None


def sg_numeric_for(value: str | None, scale: dict[str, Any] | None = None) -> int | None:
    """Map SG label → ordinal for wave charts (device numeric when present)."""
    v = canonicalize_sg(value)
    if not v:
        return None
    scale = scale or {}
    levels = list(scale.get("levels") or [])
    nums = list(scale.get("numeric") or [])
    if levels and nums and len(levels) == len(nums) and v in levels:
        return int(nums[levels.index(v)])
    # Binary Maton default: SG+ (concrete) = 1, SG- (abstract) = 2
    return {"SG+": 1, "SG-": 2, "SG++": 1, "SG--": 2}.get(v)


def scale_from_device(device: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize device.scale to a UI/coder contract."""
    raw = (device or {}).get("scale") or {}
    sg = dict(raw.get("semantic_gravity") or _DEFAULT_SG_BINARY)
    sd = dict(raw.get("semantic_density") or _DEFAULT_SD_BINARY)
    if not sg.get("levels"):
        sg = dict(_DEFAULT_SG_BINARY)
    if not sd.get("levels"):
        sd = dict(_DEFAULT_SD_BINARY)
    # Prefer Maton binary when device still lists legacy doubles without gold use.
    levels = [str(x) for x in sg.get("levels") or []]
    if set(levels) >= {"SG++", "SG+", "SG-", "SG--"} and sg.get("type") == "ordinal":
        # Auto-promote to binary Maton codes (product standard).
        sg = dict(_DEFAULT_SG_BINARY)
    return {
        "semantic_gravity": sg,
        "semantic_density": sd,
        "pedagogy": "maton_sg_sd_binary",
        "note": (
            "Semantic Gravity × Semantic Density use plus/minus codes "
            "(SG±, SD±). Device packs may declare ordinal only with explicit "
            "faculty gold that uses those levels."
        ),
    }


def normalize_label_to_device(value: str | None, dimension: str, scale: dict[str, Any]) -> str | None:
    """Force a label into the device's declared level set."""
    if dimension == "semantic_gravity":
        v = canonicalize_sg(value)
        levels = list((scale.get("semantic_gravity") or {}).get("levels") or [])
    else:
        v = canonicalize_sd(value)
        levels = list((scale.get("semantic_density") or {}).get("levels") or [])
    if not v:
        return None
    if levels and v not in levels:
        # Last resort: collapse then check again
        if dimension == "semantic_gravity":
            v2 = canonicalize_sg(v)
            if v2 in levels:
                return v2
        return levels[-1] if levels else v
    return v
