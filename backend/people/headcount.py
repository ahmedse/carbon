"""Roster headcount aggregate: one named GET, closed dimensions, no amounts.

Host of ``analyze_employees``. Pulse restates. Do not hang pay, leave, or GOSI
on this function — those are other catalog lines.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

MAX_BUCKETS = 15
BLANK_CAVEAT_PCT = 50.0

ALLOWED_DIMENSIONS = frozenset({
    "gender", "is_active", "nationality",
    "employment_type", "contract_type",
    "position", "org_unit", "kuwaitization", "rotation",
})
DIMENSION_ALIASES = {
    "nationality_code": "nationality",
    "employment_type_code": "employment_type",
    "contract_type_code": "contract_type",
    "department": "org_unit",
    "department_name": "org_unit",
    "position_name": "position",
}
FK_LABEL_MAP = {
    "position": ("people.models.Position", "title"),
    "org_unit": ("mdm.models.OrgUnit", "name"),
    "gender": ("mdm.models.ReferenceValue", "code"),
    "nationality": ("mdm.models.ReferenceValue", "code"),
    "employment_type": ("mdm.models.ReferenceValue", "code"),
    "contract_type": ("mdm.models.ReferenceValue", "code"),
    "rotation": ("mdm.models.ReferenceValue", "code"),
}
FIELD_SYNONYMS: dict[str, dict[str, frozenset]] = {
    "gender": {
        "male": frozenset({"male", "m", "man", "boy", "males"}),
        "female": frozenset({"female", "f", "woman", "girl", "females"}),
    },
}


def _scoped(user, queryset, org_lookup: str):
    """RULE_12 — same verb as People list views (``people:view``)."""
    from people.permissions import is_global_admin

    if is_global_admin(user):
        return queryset
    from accounts.rbac_utils import org_scope_for_capability
    from mdm.models import OrgUnit

    scope = org_scope_for_capability(user, "people:view")
    if scope.unrestricted:
        ids = list(OrgUnit.objects.filter(is_active=True).values_list("id", flat=True))
    else:
        ids = list(scope.ids)
    if not ids:
        return queryset.none()
    return queryset.filter(**{org_lookup: ids})


def _normalise_value(dimension: str, raw_val) -> str:
    if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
        return "(blank)"
    synonyms = FIELD_SYNONYMS.get(dimension, {})
    low = str(raw_val).strip().lower()
    for canonical, values in synonyms.items():
        if low in values:
            return canonical
    return str(raw_val).strip()


def _suggest_chart_type(breakdown: list[dict]) -> str:
    if not breakdown:
        return "bar"
    max_pct = max((r["pct"] for r in breakdown), default=0)
    n = len(breakdown)
    if max_pct >= 70:
        return "bar"
    if n <= 8:
        return "pie"
    return "bar"


def _as_list(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return [v.strip() for v in raw.split(",") if v.strip()]
    return [raw]


def _as_filters(raw) -> tuple[int, dict | None, dict | None]:
    if raw in (None, "", {}):
        return 200, {}, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return 400, None, {"detail": "Analytics filters must be a JSON object."}
    if not isinstance(raw, dict):
        return 400, None, {"detail": "Analytics filters must be a JSON object."}
    return 200, raw, None


def summarize_headcount(user, params: dict | None = None) -> tuple[int, dict[str, Any]]:
    """``(status, payload)`` for GET /people/analytics/."""
    from django.db.models import Count, Q
    from people.models import Employee

    params = params or {}
    group_by = [
        DIMENSION_ALIASES.get(str(v).strip().lower(), str(v).strip().lower())
        for v in _as_list(params.get("group_by"))
    ]
    dimension = (params.get("dimension") or (group_by[-1] if group_by else "")).strip().lower()
    dimension = DIMENSION_ALIASES.get(dimension, dimension)
    requested = group_by or [dimension]
    invalid = [d for d in requested if d not in ALLOWED_DIMENSIONS]
    if dimension not in ALLOWED_DIMENSIONS or invalid:
        return 400, {
            "detail": (
                f"Unknown dimension(s) '{', '.join(invalid) or dimension}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_DIMENSIONS | set(DIMENSION_ALIASES)))}"
            ),
        }

    qs = _scoped(user, Employee.objects.all(), "org_unit_id__in")
    code, raw_filters, err = _as_filters(params.get("filters", params.get("filter", {})))
    if err is not None:
        return code, err

    applied_filters: dict[str, list | bool | str] = {}
    for raw_key, raw_value in (raw_filters or {}).items():
        key = DIMENSION_ALIASES.get(
            str(raw_key).strip().lower(), str(raw_key).strip().lower()
        )
        if key not in ALLOWED_DIMENSIONS:
            return 400, {
                "detail": (
                    f"Unknown analytics filter '{raw_key}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_DIMENSIONS | set(DIMENSION_ALIASES)))}"
                ),
            }
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        values = [v for v in values if v is not None and str(v).strip()]
        if not values:
            return 400, {"detail": f"Analytics filter '{raw_key}' has no values."}
        if key == "is_active":
            normalized = []
            for value in values:
                if isinstance(value, bool):
                    normalized.append(value)
                elif str(value).strip().lower() in {"true", "1", "yes"}:
                    normalized.append(True)
                elif str(value).strip().lower() in {"false", "0", "no"}:
                    normalized.append(False)
                else:
                    return 400, {"detail": f"Invalid boolean filter value {value!r}."}
            qs = qs.filter(is_active__in=normalized)
            applied_filters[key] = normalized
            continue

        if key in FK_LABEL_MAP:
            _model_path, label_field = FK_LABEL_MAP[key]
            lookup = f"{key}__{label_field}__iexact"
        else:
            lookup = f"{key}__iexact"
        matched = Q()
        unmatched: list[str] = []
        for value in values:
            if not qs.filter(**{lookup: value}).exists():
                unmatched.append(str(value))
            else:
                matched |= Q(**{lookup: value})
        if unmatched:
            return 400, {
                "detail": (
                    f"Unknown filter value(s) for '{raw_key}': "
                    f"{', '.join(unmatched)}. Resolve the exact host label first."
                ),
            }
        qs = qs.filter(matched)
        applied_filters[key] = [str(v) for v in values]

    total = qs.count()
    if total == 0:
        return 200, {
            "dimension": dimension,
            "total": 0,
            "breakdown": [],
            "caveats": ["No employees visible to this user."],
            "was_normalized": False,
            "normalization_notes": [],
            "suggested_chart_type": "bar",
            "label_resolved": False,
            "applied_filters": applied_filters,
            "group_by": requested,
        }

    if len(requested) > 1:
        value_fields: dict[str, str] = {}
        for dim in requested:
            if dim in FK_LABEL_MAP:
                _model_path, label_field = FK_LABEL_MAP[dim]
                value_fields[dim] = f"{dim}__{label_field}"
            else:
                value_fields[dim] = dim
        grouped = (
            qs.values(*value_fields.values())
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        breakdown: list[dict] = []
        for raw in grouped[:100]:
            row = {
                dim: _normalise_value(dim, raw.get(field))
                for dim, field in value_fields.items()
            }
            row["count"] = raw["count"]
            row["pct"] = round(raw["count"] / total * 100, 1)
            breakdown.append(row)
        caveats = []
        if grouped.count() > 100:
            caveats.append("The grouped breakdown was limited to the top 100 rows.")
        return 200, {
            "dimension": dimension,
            "group_by": requested,
            "applied_filters": applied_filters,
            "total": total,
            "breakdown": breakdown,
            "caveats": caveats,
            "was_normalized": False,
            "normalization_notes": [],
            "suggested_chart_type": "bar",
            "label_resolved": True,
        }

    raw_counts = (
        qs.values(dimension)
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    bucket_counts: dict[str, int] = defaultdict(int)
    bucket_merged_from: dict[str, list[str]] = defaultdict(list)
    label_resolved = False
    pk_to_label: dict = {}
    was_normalized = False

    if dimension in FK_LABEL_MAP:
        import importlib

        module_path, label_field = FK_LABEL_MAP[dimension]
        mod_name, cls_name = module_path.rsplit(".", 1)
        model_cls = getattr(importlib.import_module(mod_name), cls_name)
        pk_ids = [r[dimension] for r in raw_counts if r[dimension] is not None]
        for obj in model_cls.objects.filter(pk__in=pk_ids).values("pk", label_field):
            pk_to_label[obj["pk"]] = obj[label_field]
        label_resolved = True
        for row in raw_counts:
            raw_val = row[dimension]
            displayed = pk_to_label.get(raw_val) if raw_val is not None else None
            canonical = _normalise_value(dimension, displayed)
            bucket_counts[canonical] += row["count"]
            if displayed and str(displayed).strip() and str(displayed).strip() != canonical:
                bucket_merged_from[canonical].append(str(displayed).strip())
                was_normalized = True
    else:
        for row in raw_counts:
            raw_val = row[dimension]
            canonical = _normalise_value(dimension, raw_val)
            bucket_counts[canonical] += row["count"]
            displayed = str(raw_val).strip() if raw_val is not None else ""
            if displayed and displayed != canonical:
                bucket_merged_from[canonical].append(displayed)
                was_normalized = True

    sorted_buckets = sorted(bucket_counts.items(), key=lambda kv: -kv[1])
    blank_count = bucket_counts.get("(blank)", 0)
    breakdown = []
    other_count = 0
    other_labels: list[str] = []
    for i, (label, count) in enumerate(sorted_buckets):
        pct = round(count / total * 100, 1)
        row = {"label": label, "count": count, "pct": pct}
        if bucket_merged_from.get(label):
            row["merged_from"] = bucket_merged_from[label]
        if i < MAX_BUCKETS:
            breakdown.append(row)
        else:
            other_count += count
            other_labels.append(label)
    if other_count:
        breakdown.append({
            "label": "Other",
            "count": other_count,
            "pct": round(other_count / total * 100, 1),
            "collapsed_labels": other_labels[:20],
        })

    caveats = []
    blank_pct = round(blank_count / total * 100, 1) if total else 0
    if blank_pct >= BLANK_CAVEAT_PCT:
        caveats.append(
            f"{blank_pct}% of employees have no '{dimension}' recorded — "
            f"this distribution is incomplete and should not be used for compliance reporting."
        )
    if not label_resolved and dimension in FK_LABEL_MAP:
        caveats.append(f"'{dimension}' IDs could not be resolved to labels.")
    if other_count:
        caveats.append(
            f"The breakdown has been truncated to the top {MAX_BUCKETS} buckets; "
            f"{len(other_labels)} additional values ({other_count} employees) are grouped as 'Other'."
        )
    normalization_notes = []
    for canonical, raw_list in bucket_merged_from.items():
        if raw_list:
            merged_str = ", ".join(f"'{v}'" for v in sorted(set(raw_list)))
            normalization_notes.append(
                f"{merged_str} → '{canonical}' (likely data-entry variants; "
                f"recommend standardising the source data)"
            )
    return 200, {
        "dimension": dimension,
        "total": total,
        "breakdown": breakdown,
        "caveats": caveats,
        "was_normalized": was_normalized,
        "normalization_notes": normalization_notes,
        "suggested_chart_type": _suggest_chart_type(breakdown),
        "label_resolved": label_resolved,
        "applied_filters": applied_filters,
        "group_by": requested,
    }
