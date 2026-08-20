"""
dq/contradiction.py — Semantic layer for DQ rule contradiction detection.

Pure functions. No model imports (mirrors `rule_schema.py` and `engine.py`).
Builds on top of the existing rule-type <-> field-type applicability check
(which is enforced at bind time): that check ensures each rule *can* apply to
the field; this module checks whether multiple rules on the SAME field can
*coexist*.

Three verdict buckets, one per finding `kind`:

  1. ``conflict``    — two rules that provably cannot both pass:
                       * disjoint numeric ``range`` intervals
                       * disjoint ``allowed_values`` sets (both static)
                       * ``allowed_values`` fully outside a ``range``

  2. ``redundant``   — duplicate coverage:
                       * duplicate ``not_null`` / duplicate ``unique``
                       * ``unique`` alongside ``not_null``

  3. ``undecidable`` — semantically-overlapping rules whose joint verdict cannot
                       be decided statically (``nl_check`` vs ``regex``, two
                       ``regex`` rules, ``allowed_values`` via ``reference_set``
                       whose members are unknown, etc.). Callers emit a composite
                       "conflict" verdict at *runtime* for these.

Every rule spec is ``{'rule_id', 'name', 'rule_type', 'params'}``. The analysis
is order-independent and side-effect free.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

__all__ = [
    'analyze_rules',
    'CONFLICT',
    'REDUNDANT',
    'UNDECIDABLE',
]

CONFLICT = 'conflict'
REDUNDANT = 'redundant'
UNDECIDABLE = 'undecidable'

# Rule types that make a value/format claim whose joint satisfaction with another
# such rule cannot be decided by static analysis (needs a runtime/LLM verdict).
SEMANTIC_AMBIGUOUS = frozenset({'nl_check', 'regex', 'anomaly_detect'})


def _finding(kind: str, rules: List[Dict[str, Any]], message: str) -> Dict[str, Any]:
    """Build a single finding dict from the rules involved."""
    return {
        'kind': kind,
        'rule_ids': [r['rule_id'] for r in rules],
        'rule_names': [r['name'] for r in rules],
        'rule_types': [r['rule_type'] for r in rules],
        'message': message,
    }


# ── Parameter extraction (static) ──────────────────────────────────────────

def _range_bounds(params: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Return (lo, hi) for a ``range`` rule; ``None`` means an open bound."""
    lo, hi = params.get('min'), params.get('max')

    def _num(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return _num(lo), _num(hi)


def _allowed_values(params: Dict[str, Any]) -> Optional[Set[str]]:
    """Return the static allowed set, or ``None`` if unresolvable statically.

    ``reference_set`` rules resolve against the MDM reference catalog at runtime,
    so their members are unknown here -> ``None``.
    """
    if 'reference_set' in params:
        return None
    vals = params.get('values')
    if not isinstance(vals, list):
        return None
    return {str(v) for v in vals}


# ── Deterministic disjointness predicates ──────────────────────────────────

def _ranges_disjoint(a: Tuple[Optional[float], Optional[float]],
                     b: Tuple[Optional[float], Optional[float]]) -> bool:
    """True if two inclusive numeric ranges share no value."""
    a_lo, a_hi = a
    b_lo, b_hi = b
    if a_hi is not None and b_lo is not None and a_hi < b_lo:
        return True
    if b_hi is not None and a_lo is not None and b_hi < a_lo:
        return True
    return False


def _range_excludes_set(bounds: Tuple[Optional[float], Optional[float]],
                        values: Set[str]) -> bool:
    """True if no value in ``values`` (as a float) falls inside ``bounds``.

    Non-numeric values never fall inside a numeric range, so they are "excluded"
    by definition — this matches the engine, which marks them failed for ``range``.
    """
    lo, hi = bounds
    for v in values:
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if lo is not None and fv < lo:
            continue
        if hi is not None and fv > hi:
            continue
        return False  # some allowed value is inside the range
    return True


# ── Main entry point ────────────────────────────────────────────────────────

def analyze_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze a set of rules bound to the same field for conflicts.

    Args:
        rules: list of ``{'rule_id', 'name', 'rule_type', 'params'}`` dicts.
            ``rule_id`` may be any hashable/comparable value (int, uuid, str).

    Returns:
        list of finding dicts (order-independent). Empty list = no issues.
    """
    findings: List[Dict[str, Any]] = []
    if not rules:
        return findings

    by_type: Dict[str, List[int]] = {}
    for i, r in enumerate(rules):
        by_type.setdefault(r['rule_type'], []).append(i)

    # ── Redundant: duplicate not_null / unique ─────────────────────────────
    for t in ('not_null', 'unique'):
        idxs = by_type.get(t, [])
        if len(idxs) >= 2:
            findings.append(_finding(
                REDUNDANT,
                [rules[i] for i in idxs],
                f'{len(idxs)} {t} rules on the same field are redundant.',
            ))

    # ── Redundant: unique alongside not_null ───────────────────────────────
    if 'unique' in by_type and 'not_null' in by_type:
        findings.append(_finding(
            REDUNDANT,
            [rules[by_type['unique'][0]], rules[by_type['not_null'][0]]],
            "A 'unique' rule alongside a 'not_null' rule on the same field is redundant.",
        ))

    # ── Pairwise: deterministic conflicts + undecidable overlaps ───────────
    n = len(rules)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = rules[i], rules[j]
            kinds = {a['rule_type'], b['rule_type']}
            pair = [a, b]

            if kinds == {'range'}:
                ab = _range_bounds(a['params'])
                bb = _range_bounds(b['params'])
                if _ranges_disjoint(ab, bb):
                    findings.append(_finding(
                        CONFLICT, pair,
                        'Disjoint numeric ranges cannot both pass.',
                    ))

            elif kinds == {'allowed_values'}:
                av = _allowed_values(a['params'])
                bv = _allowed_values(b['params'])
                if av is None or bv is None:
                    findings.append(_finding(
                        UNDECIDABLE, pair,
                        "Two allowed_values rules (>=1 via reference_set) cannot be "
                        "compared statically; verify at runtime.",
                    ))
                elif av.isdisjoint(bv):
                    findings.append(_finding(
                        CONFLICT, pair,
                        'Disjoint allowed-value sets cannot both pass.',
                    ))

            elif kinds == {'range', 'allowed_values'}:
                rng_rule = a if a['rule_type'] == 'range' else b
                av_rule = a if a['rule_type'] == 'allowed_values' else b
                av = _allowed_values(av_rule['params'])
                if av is None:
                    findings.append(_finding(
                        UNDECIDABLE, pair,
                        "allowed_values via reference_set vs a numeric range cannot be "
                        "compared statically; verify at runtime.",
                    ))
                elif _range_excludes_set(_range_bounds(rng_rule['params']), av):
                    findings.append(_finding(
                        CONFLICT, pair,
                        'No allowed value falls inside the numeric range; the two rules '
                        'cannot both pass.',
                    ))

            elif kinds <= SEMANTIC_AMBIGUOUS:
                # Two semantic rules (nl_check/regex/anomaly_detect) on the same
                # field: their joint satisfaction is undecidable statically.
                findings.append(_finding(
                    UNDECIDABLE, pair,
                    f"{' and '.join(sorted(kinds))} rules on the same field overlap "
                    "semantically; a composite verdict must be decided at runtime.",
                ))

            elif 'reference_integrity' in kinds and (
                'allowed_values' in kinds or 'reference_integrity' in kinds
            ):
                # Value-set constraints whose members are DB-resolvable, not static.
                findings.append(_finding(
                    UNDECIDABLE, pair,
                    'Reference-set membership rules overlap; their joint verdict cannot '
                    'be decided statically.',
                ))

    return findings
