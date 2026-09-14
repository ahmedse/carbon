"""Pure, deterministic answer-quality check functions (no LLM, no network).

Each function validates one invariant of a ``_people_analytics`` breakdown and
raises ``AssertionError`` with a clear message on failure (returns ``None`` on
success).  They are deliberately free of Django imports so the live judge
harness can reuse them against synthesized output without a DB connection.

A "breakdown" is the list of row dicts produced by ``_people_analytics``, e.g.::

    [
        {"label": "male",    "count": 6, "pct": 66.7, "merged_from": ["M"]},
        {"label": "female",  "count": 2, "pct": 22.2, "merged_from": ["F"]},
        {"label": "(blank)", "count": 1, "pct": 11.1},
    ]
"""

from __future__ import annotations

#: Keywords that mark a caveat as disclosing missing/unrecorded data.
_MISSING_DATA_MARKERS = (
    "missing",
    "unrecorded",
    "not recorded",
    "no '",
    "no ",
    "incomplete",
)


def _row(breakdown, label):
    """Return the first row whose label equals ``label`` (or ``None``)."""
    return next((r for r in breakdown if r.get("label") == label), None)


def assert_counts_match_db(breakdown, expected):
    """Assert every bucket ``count`` equals the DB-derived expected count.

    Args:
        breakdown: list of row dicts (``label`` / ``count``).
        expected: dict mapping canonical label → exact expected count.

    Raises:
        AssertionError: if a label is missing or its count differs.
    """
    actual = {r.get("label"): r.get("count") for r in breakdown}
    for label, count in expected.items():
        if label not in actual:
            raise AssertionError(
                f"missing bucket '{label}'; got {sorted(actual)}"
            )
        if actual[label] != count:
            raise AssertionError(
                f"bucket '{label}' count {actual[label]} != expected {count}"
            )


def assert_no_raw_pk_labels(breakdown):
    """Assert no bucket label is a bare integer PK (must be human-readable text).

    A label like ``"3"`` (or an int) leaks the database primary key into the
    rendered answer instead of a resolved title.
    """
    for r in breakdown:
        label = r.get("label")
        if isinstance(label, int) or (
            isinstance(label, str) and label.strip().isdigit()
        ):
            raise AssertionError(
                f"raw PK label leaked into breakdown: {label!r}"
            )


def assert_caveat_fires_for_blank(breakdown, caveats, threshold=50.0):
    """Assert the missing-data caveat fires when the blank share is high enough.

    If the ``(blank)`` bucket's share of the population is ``>= threshold``
    percent, at least one caveat must disclose that the dimension is
    missing/unrecorded/incomplete.  When the blank share is below the
    threshold the function passes (callers assert the *absence* of the caveat
    separately, mirroring the two-sided threshold contract).
    """
    blank = _row(breakdown, "(blank)")
    if blank is None:
        return
    total = sum(r.get("count", 0) for r in breakdown)
    blank_pct = (blank.get("count", 0) / total * 100) if total else 0.0
    if blank_pct < threshold:
        return
    text = " ".join(str(c) for c in caveats).lower()
    if not any(marker in text for marker in _MISSING_DATA_MARKERS):
        raise AssertionError(
            f"blank share {blank_pct}% >= {threshold}% but no caveat "
            f"discloses missing data; caveats={list(caveats)!r}"
        )


def assert_chart_type_rule(breakdown, suggested):
    """Assert ``suggested`` obeys the deterministic chart-type rule.

    Mirrors ``_suggest_chart_type`` in ``ai/host_executor.py``:
      * a dominant bucket (>= 70% — the production threshold) ⇒ ``"bar"``;
      * a balanced distribution across <= 8 buckets ⇒ ``"pie"``;
      * more than 8 buckets ⇒ ``"bar"``.
    """
    if not breakdown:
        if suggested != "bar":
            raise AssertionError(
                f"empty breakdown should suggest 'bar', got {suggested!r}"
            )
        return
    max_pct = max(r.get("pct", 0) for r in breakdown)
    n = len(breakdown)
    if max_pct >= 70:
        expected = "bar"
    elif n <= 8:
        expected = "pie"
    else:
        expected = "bar"
    if suggested != expected:
        raise AssertionError(
            f"suggested chart type {suggested!r} != expected {expected!r} "
            f"(max_pct={max_pct}, buckets={n})"
        )


def assert_truncation_collapsed_to_other(breakdown, max_buckets=15):
    """Assert a long tail is capped to ``max_buckets`` + a single "Other" row.

    If an "Other" bucket is present, the breakdown must be no longer than
    ``max_buckets + 1`` and the "Other" row must carry a positive count.
    Otherwise the breakdown must fit within ``max_buckets`` (no collapse
    needed).
    """
    other = _row(breakdown, "Other")
    if other is None:
        if len(breakdown) > max_buckets:
            raise AssertionError(
                f"{len(breakdown)} buckets exceed max_buckets={max_buckets} "
                f"but no 'Other' row collapsed the tail"
            )
        return
    if len(breakdown) > max_buckets + 1:
        raise AssertionError(
            f"collapsed breakdown has {len(breakdown)} rows "
            f"(expected <= {max_buckets + 1})"
        )
    if other.get("count", 0) < 1:
        raise AssertionError("'Other' row present but has no collapsed count")


def assert_synonym_merged(breakdown, canonical, raw_variant):
    """Assert ``raw_variant`` was merged into the ``canonical`` bucket.

    Passes when the canonical bucket's ``merged_from`` lists ``raw_variant``,
    OR when ``raw_variant`` no longer appears as its own bucket.  A canonical
    bucket that is entirely absent is a hard failure (the variant was neither
    merged nor preserved).
    """
    canonical_row = _row(breakdown, canonical)
    if canonical_row is None:
        raise AssertionError(
            f"canonical bucket '{canonical}' missing from breakdown"
        )
    merged = canonical_row.get("merged_from") or []
    labels = {r.get("label") for r in breakdown}
    if raw_variant in merged or raw_variant not in labels:
        return
    raise AssertionError(
        f"'{raw_variant}' not merged into '{canonical}' and still appears "
        f"as its own bucket; merged_from={merged!r}"
    )


# ── AnswerEnvelope invariants (typed structured-output path) ─────────────────

import re as _re

#: A headline that asserts the absence of data (allow up to 3 words between
#: "no" and the data noun, e.g. "no carbon emissions data").
_NO_DATA_HEADLINE_RE = _re.compile(
    r"\bno\s+(?:\w+\s+){0,3}(?:data|records?|results?|calculations?|emissions?|entries|rows)\b"
    r"|there (?:is|are) no \w"
    r"|\bnot available\b",
    _re.IGNORECASE,
)


def assert_envelope_has_data(envelope):
    """Assert a data-bearing envelope actually carries tables or charts.

    ``envelope`` is an :class:`AnswerEnvelope` or its ``model_dump()`` dict.
    Raises when both ``tables`` and ``charts`` are empty — the exact failure
    where a data question rendered as prose-only.
    """
    tables = _attr(envelope, "tables") or []
    charts = _attr(envelope, "charts") or []
    if not tables and not charts:
        raise AssertionError("envelope has neither tables nor charts for a data question")


def assert_envelope_not_no_data(envelope):
    """Assert the envelope headline does NOT falsely claim data is absent.

    Guards the "no data available" regression: a headline asserting absence is
    a hard failure whenever the envelope also carries tables/charts.
    """
    headline = str(_attr(envelope, "headline") or "")
    tables = _attr(envelope, "tables") or []
    charts = _attr(envelope, "charts") or []
    if (tables or charts) and _NO_DATA_HEADLINE_RE.search(headline):
        raise AssertionError(
            f"envelope carries data but headline claims none: {headline!r}"
        )


def _attr(obj, name):
    """Read ``name`` from a pydantic model or a plain dict (envelope-agnostic)."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)

