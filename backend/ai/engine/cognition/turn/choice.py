"""A clarify with options is a typed choice. The model names them; the client paints the form."""
from __future__ import annotations

KIND = "choice"


def choice_question(op: str, options: list | None, key: str = "") -> dict | None:
    """``None`` unless this is a clarify with at least two distinct labels."""
    if op != "clarify":
        return None
    labels: list[str] = []
    seen: set[str] = set()
    for raw in options or []:
        label = " ".join(str(raw).split())
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
        if len(labels) == 8:
            break
    if len(labels) < 2:
        return None
    return {
        "kind": KIND,
        "key": (key or "").strip() or "choice",
        "allow_free": True,
        "options": [{"value": label, "label": label} for label in labels],
    }
