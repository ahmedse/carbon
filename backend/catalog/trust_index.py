# catalog/trust_index.py — Data Trust Index (ADR-0039 + DTR-5 freshness).
# Read-time aggregate: Quality ≤35 + Ownership ≤20 + Context ≤35 + Freshness ≤10.

from __future__ import annotations

from django.utils import timezone

TRUSTED_MIN = 70
LIMITED_MIN = 20

QUALITY_MAX = 35
OWNERSHIP_MAX = 20
CONTEXT_MAX = 35
FRESHNESS_MAX = 10

# Freshness points by SLA status (DTR-5).
FRESHNESS_FRESH = 10.0
FRESHNESS_UNKNOWN = 5.0  # no policy / not monitored — not proven bad
FRESHNESS_STALE = 0.0


def compute_trust_index(asset, *, freshness=None) -> dict:
    """
    Return {score, tier, breakdown} for an AssetProfile-like object.

    Expected attributes: quality_score, owner_id, steward_id, description,
    glossary_term_id, domain_id, and either .tags (manager) or prefetched tags.

    ``freshness`` — optional snapshot from ``freshness_snapshot_for_table`` /
    ``batch_freshness_for_table_ids``. When omitted, resolved from the asset's
    linked DataTable + FreshnessPolicy (may hit the DB).
    """
    if freshness is None:
        freshness = resolve_freshness_for_asset(asset)

    quality_pts, quality_detail = _quality_points(asset)
    ownership_pts, ownership_detail = _ownership_points(asset)
    context_pts, context_detail = _context_points(asset)
    freshness_pts, freshness_detail = _freshness_points(freshness)

    score = int(round(quality_pts + ownership_pts + context_pts + freshness_pts))
    score = max(0, min(100, score))
    tier = _tier(score)

    return {
        "score": score,
        "tier": tier,
        "breakdown": {
            "quality": {"points": quality_pts, "max": QUALITY_MAX, **quality_detail},
            "ownership": {"points": ownership_pts, "max": OWNERSHIP_MAX, **ownership_detail},
            "context": {"points": context_pts, "max": CONTEXT_MAX, **context_detail},
            "freshness": {"points": freshness_pts, "max": FRESHNESS_MAX, **freshness_detail},
        },
    }


def resolve_freshness_for_asset(asset) -> dict:
    """Resolve a freshness snapshot for an AssetProfile-like object."""
    table = _linked_table(asset)
    if table is None:
        return _unknown_snapshot()
    policy = getattr(table, "freshness_policy", None)
    if policy is None:
        # May be reverse OneToOne not loaded — try related manager / query
        try:
            from .models import FreshnessPolicy
            policy = FreshnessPolicy.objects.filter(table_id=table.pk, enabled=True).first()
        except Exception:
            policy = None
    elif getattr(policy, "enabled", True) is False:
        policy = None
    return freshness_snapshot_for_table(table, policy=policy)


def batch_freshness_for_table_ids(table_ids) -> dict:
    """
    Return {table_id: freshness_snapshot} for many tables in two queries.
    Missing ids → unknown snapshot.
    """
    ids = [tid for tid in set(table_ids or []) if tid is not None]
    if not ids:
        return {}

    from dataschema.models import DataTable
    from .models import FreshnessPolicy

    tables = {t.id: t for t in DataTable.objects.filter(id__in=ids).only(
        "id", "last_data_updated_at", "created_at",
    )}
    policies = {
        p.table_id: p
        for p in FreshnessPolicy.objects.filter(table_id__in=ids, enabled=True)
    }
    now = timezone.now()
    out = {}
    for tid in ids:
        table = tables.get(tid)
        if table is None:
            out[tid] = _unknown_snapshot()
        else:
            out[tid] = freshness_snapshot_for_table(
                table, policy=policies.get(tid), now=now,
            )
    return out


def freshness_snapshot_for_table(table, policy=None, *, now=None) -> dict:
    """
    Build {status, age_hours, max_age_hours} for a DataTable.

    status: fresh | stale | unknown
    """
    if table is None:
        return _unknown_snapshot()
    if policy is None or not getattr(policy, "enabled", True):
        # Still report age when we can (helpful in breakdown), status unknown.
        age = _age_hours(table, now=now)
        return {
            "status": "unknown",
            "age_hours": age,
            "max_age_hours": None,
        }

    now = now or timezone.now()
    age = _age_hours(table, now=now)
    max_age = int(policy.max_age_hours)
    if age is None:
        return {
            "status": "unknown",
            "age_hours": None,
            "max_age_hours": max_age,
        }
    status = "stale" if age > max_age else "fresh"
    return {
        "status": status,
        "age_hours": round(age, 2),
        "max_age_hours": max_age,
    }


def _unknown_snapshot() -> dict:
    return {"status": "unknown", "age_hours": None, "max_age_hours": None}


def _age_hours(table, *, now=None) -> float | None:
    reference = getattr(table, "last_data_updated_at", None) or getattr(table, "created_at", None)
    if reference is None:
        return None
    now = now or timezone.now()
    return max(0.0, (now - reference).total_seconds() / 3600.0)


def _linked_table(asset):
    """Return the DataTable for a table- or field-level AssetProfile."""
    table = getattr(asset, "data_table", None)
    if table is not None:
        return table
    table_id = getattr(asset, "data_table_id", None)
    if table_id:
        try:
            from dataschema.models import DataTable
            return DataTable.objects.only(
                "id", "last_data_updated_at", "created_at",
            ).get(pk=table_id)
        except Exception:
            return None
    field = getattr(asset, "data_field", None)
    if field is not None:
        return getattr(field, "data_table", None)
    field_id = getattr(asset, "data_field_id", None)
    if field_id:
        try:
            from dataschema.models import DataField
            return (
                DataField.objects.select_related("data_table")
                .only("id", "data_table_id", "data_table__last_data_updated_at", "data_table__created_at")
                .get(pk=field_id)
                .data_table
            )
        except Exception:
            return None
    return None


def table_id_for_asset(asset) -> int | None:
    tid = getattr(asset, "data_table_id", None)
    if tid:
        return tid
    table = getattr(asset, "data_table", None)
    if table is not None:
        return getattr(table, "id", None) or getattr(table, "pk", None)
    field = getattr(asset, "data_field", None)
    if field is not None:
        return getattr(field, "data_table_id", None) or getattr(
            getattr(field, "data_table", None), "id", None
        )
    return None


def _tier(score: int) -> str:
    if score >= TRUSTED_MIN:
        return "trusted"
    if score >= LIMITED_MIN:
        return "limited"
    return "untrustworthy"


def _quality_points(asset) -> tuple[float, dict]:
    raw = getattr(asset, "quality_score", None)
    if raw is None:
        return 0.0, {"quality_score": None, "note": "not_evaluated"}
    try:
        q = int(raw)
    except (TypeError, ValueError):
        return 0.0, {"quality_score": None, "note": "invalid"}
    q = max(0, min(100, q))
    pts = round(q / 100 * QUALITY_MAX, 2)
    return pts, {"quality_score": q}


def _ownership_points(asset) -> tuple[float, dict]:
    has_owner = bool(getattr(asset, "owner_id", None) or getattr(asset, "owner", None))
    has_steward = bool(getattr(asset, "steward_id", None) or getattr(asset, "steward", None))
    if has_owner:
        return 20.0, {"owner": True, "steward": has_steward}
    if has_steward:
        return 10.0, {"owner": False, "steward": True}
    return 0.0, {"owner": False, "steward": False}


def _context_points(asset) -> tuple[float, dict]:
    description = (getattr(asset, "description", None) or "").strip()
    has_description = bool(description)
    has_glossary = bool(
        getattr(asset, "glossary_term_id", None) or getattr(asset, "glossary_term", None)
    )
    has_domain = bool(getattr(asset, "domain_id", None) or getattr(asset, "domain", None))
    tag_count = _tag_count(asset)
    has_tags = tag_count > 0

    pts = 0.0
    if has_description:
        pts += 8
    if has_glossary:
        pts += 12
    if has_domain:
        pts += 10
    if has_tags:
        pts += 5

    return pts, {
        "description": has_description,
        "glossary_term": has_glossary,
        "domain": has_domain,
        "tags": has_tags,
        "tag_count": tag_count,
    }


def _freshness_points(snapshot) -> tuple[float, dict]:
    snap = snapshot or _unknown_snapshot()
    status = snap.get("status") or "unknown"
    detail = {
        "status": status,
        "age_hours": snap.get("age_hours"),
        "max_age_hours": snap.get("max_age_hours"),
    }
    if status == "fresh":
        return FRESHNESS_FRESH, detail
    if status == "stale":
        return FRESHNESS_STALE, detail
    return FRESHNESS_UNKNOWN, detail


def _tag_count(asset) -> int:
    tags = getattr(asset, "tags", None)
    if tags is None:
        return 0
    cache = getattr(asset, "_prefetched_objects_cache", {}) or {}
    if "tags" in cache:
        return len(cache["tags"])
    try:
        return tags.count()
    except Exception:
        try:
            return len(list(tags.all()))
        except Exception:
            return 0
