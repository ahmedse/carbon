# Domain-free policy lifecycle.
# States, immutability, example gate, floor comparison, citation check,
# and the governance event in one transaction.
# A host app registers a plane. This module does not import a host app.
# The preparer check is a callable on the plane so the existing gate is reused.

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction

from catalog.audit_utils import emit_governance_event

DRAFT = "draft"
IN_REVIEW = "in_review"
AUTHORITATIVE = "authoritative"
SUPERSEDED = "superseded"
STATES = (DRAFT, IN_REVIEW, AUTHORITATIVE, SUPERSEDED)

_QUANT = Decimal("0.001")
_PLANES: list = []


class PolicyTransitionError(Exception):
    """A lifecycle write was refused. Map ``status_code`` at the HTTP boundary."""

    def __init__(self, detail, *, code, status_code=409, errors=None):
        super().__init__(detail)
        self.code = code
        self.status_code = status_code
        self.errors = errors or []


def register_plane(plane) -> None:
    """Replace any previous plane with the same key."""
    global _PLANES
    _PLANES = [item for item in _PLANES if item.key != plane.key]
    _PLANES.append(plane)


def registered_planes():
    return list(_PLANES)


def _quantize(value) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def evaluate_examples(cases, run_case) -> dict:
    """Run the version's own examples. Empty examples cannot pass."""
    rows = list(cases or [])
    if not rows:
        return {"passed": False, "code": "examples_required", "results": []}
    results = []
    passed = True
    for index, case in enumerate(rows):
        if not isinstance(case, dict):
            passed = False
            results.append({"index": index, "passed": False, "error": "example must be an object"})
            continue
        inputs = case.get("inputs") or {}
        try:
            out = run_case(inputs)
        except Exception as exc:  # noqa: BLE001 — a failing example blocks publish
            passed = False
            results.append({"index": index, "passed": False, "error": str(exc)})
            continue
        row = {"index": index, "actual": str(out["value"])}
        ok = True
        if "expected" in case:
            expected = _quantize(case["expected"])
            ok = out["value"] == expected
            row["expected"] = str(expected)
        lineage = out.get("lineage") or {}
        for key, lineage_key in (
            ("expected_employee", "employee_share"),
            ("expected_employer", "employer_share"),
        ):
            if key not in case:
                continue
            expected = _quantize(case[key])
            actual = lineage.get(lineage_key)
            row[key] = str(expected)
            row[lineage_key] = None if actual is None else str(actual)
            if actual is None or _quantize(actual) != expected:
                ok = False
        row["passed"] = ok
        if not ok:
            passed = False
        results.append(row)
    return {
        "passed": passed,
        "code": None if passed else "examples_failed",
        "results": results,
    }


def _fund_results(schema: dict, cited: dict) -> list:
    """Compare a declared fund table to the funds the cited version names."""
    declared = cited.get("funds") or []
    formula = schema.get("formula") or {}
    if not declared or formula.get("type") != "fund_table":
        return []
    tenant = {
        row.get("code"): row
        for row in ((formula.get("params") or {}).get("funds") or [])
    }
    results = []
    for fund in declared:
        code = fund.get("code")
        got = tenant.get(code)
        if not isinstance(got, dict):
            results.append({"field": code, "passed": False, "error": "fund missing"})
            continue
        for key in ("employee_rate", "employer_rate", "ceiling"):
            if key not in fund:
                continue
            try:
                actual = Decimal(str(got.get(key)))
                bound = Decimal(str(fund.get(key)))
            except (TypeError, ValueError, ArithmeticError):
                results.append({
                    "field": f"{code}.{key}",
                    "passed": False,
                    "error": "fund value is not numeric",
                })
                continue
            ok = actual >= bound if key != "ceiling" else actual == bound
            results.append({
                "field": f"{code}.{key}",
                "passed": ok,
                "actual": str(actual),
                "bound": str(bound),
                "op": "eq" if key == "ceiling" else "gte",
            })
    return results


def evaluate_floors(schema: dict, resolve) -> dict:
    """Compare declared parameters to floors on the cited version.

    ``resolve(schema)`` returns the cited document, a ``_missing`` dict, or
    None when nothing was cited. Operators and bounds come from that document.
    """
    parameters = schema.get("parameters") or {}
    packed = resolve(schema)
    if isinstance(packed, dict) and packed.get("_missing"):
        return {
            "passed": False,
            "code": packed["code"],
            "results": [{"error": packed["error"]}],
        }
    if packed is None:
        if not parameters:
            return {"passed": True, "results": []}
        return {
            "passed": False,
            "code": "regulation_required",
            "results": [{"error": "parameters require a regulation_ref"}],
        }
    floors = packed.get("floors") or []
    fund_rows = _fund_results(schema, packed)
    if not parameters and not fund_rows:
        return {"passed": True, "results": []}
    results = []
    passed = True
    for floor in floors:
        field = floor.get("field")
        if not field or field not in parameters:
            continue
        op = floor.get("op") or "gte"
        try:
            actual = Decimal(str(parameters[field]))
            bound = Decimal(str(floor.get("value")))
        except (TypeError, ValueError, ArithmeticError):
            passed = False
            results.append({"field": field, "passed": False, "error": "floor value is not numeric"})
            continue
        if op not in ("gte", "eq"):
            passed = False
            results.append({"field": field, "passed": False, "error": f"unsupported op {op}"})
            continue
        ok = actual >= bound if op == "gte" else actual == bound
        if not ok:
            passed = False
        results.append({
            "field": field,
            "passed": ok,
            "actual": str(actual),
            "bound": str(bound),
            "op": op,
        })
    for row in fund_rows:
        if not row["passed"]:
            passed = False
        results.append(row)
    return {
        "passed": passed,
        "code": None if passed else "floor_failed",
        "results": results,
    }


def _event(plane, row, action, before, after, user):
    emit_governance_event(
        entity_type=plane.entity_type,
        entity_id=row.pk,
        action=action,
        before=before,
        after=after,
        user=user,
        strict=True,
    )


def _publisher_id(plane, row):
    from catalog.models import GovernanceEvent

    event = (
        GovernanceEvent.objects.filter(
            entity_type=plane.entity_type,
            entity_id=row.pk,
            action="publish",
        )
        .order_by("-id")
        .first()
    )
    return event.user_id if event else None


def _latest_event(plane, row):
    from catalog.models import GovernanceEvent

    event = (
        GovernanceEvent.objects.filter(
            entity_type=plane.entity_type,
            entity_id=row.pk,
        )
        .order_by("-id")
        .first()
    )
    if event is None:
        return None
    return {
        "action": event.action,
        "before": event.before or {},
        "after": event.after or {},
        "at": event.timestamp.isoformat() if event.timestamp else None,
    }


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _flatten(snapshot: dict) -> dict:
    flat = {
        "name": snapshot.get("name") or "",
        "citation": snapshot.get("citation") or "",
        "effective_date": snapshot.get("effective_date") or "",
    }
    schema = snapshot.get("schema") or {}
    for key, value in (schema.get("parameters") or {}).items():
        flat[f"parameter.{key}"] = _stringify(value)
    formula = (schema.get("formula") or {}).get("params") or {}
    for key, value in formula.items():
        flat[f"formula.{key}"] = _stringify(value)
    flat["examples"] = _stringify(snapshot.get("examples") or [])
    return flat


def build_diff(current, previous) -> list:
    """Changed fields between this version and the prior authoritative one."""
    if not previous:
        return []
    left = _flatten(previous)
    right = _flatten(current or {})
    rows = []
    for key in sorted(set(left) | set(right)):
        before = left.get(key, "")
        after = right.get(key, "")
        if before == after:
            continue
        rows.append({"field": key, "before": before, "after": after})
    return rows


def to_public(plane, row) -> dict:
    return {
        "id": row.pk,
        "policy": plane.policy_id(row),
        "version": plane.version_of(row),
        "name": plane.display_name(row),
        "state": plane.state(row),
        "citation": plane.citation(row),
        "effective_date": plane.effective_on(row),
        "preparer_id": plane.preparer_id(row),
        "publisher_id": _publisher_id(plane, row),
    }


def locate(pk):
    for plane in _PLANES:
        row = plane.find(pk)
        if row is not None:
            return plane, row
    return None, None


def list_versions(*, state="", query=""):
    items = []
    for plane in _PLANES:
        for row in plane.iter_rows(state=state, query=query):
            items.append(to_public(plane, row))
    items.sort(key=lambda item: (item["policy"], item["version"]))
    return items


def preview(plane, row) -> dict:
    prior = plane.prior_authoritative(row)
    return {
        "state": plane.state(row),
        "citation": bool(plane.citation(row).strip()),
        "examples": plane.example_report(row),
        "floors": plane.floor_report(row),
        "diff": build_diff(plane.snapshot(row), plane.snapshot(prior) if prior else None),
        "event": _latest_event(plane, row),
    }


def detail(pk):
    plane, row = locate(pk)
    if row is None:
        return None
    body = to_public(plane, row)
    # preview() reports citation as a boolean. The desk record keeps the text.
    citation = body.get("citation") or ""
    body.update(preview(plane, row))
    body["citation"] = citation
    return body


def create_draft(plane, data, user):
    try:
        with transaction.atomic():
            row = plane.create(data)
            plane.stamp(row, user)
            _event(plane, row, "create", None, {"lifecycle": plane.state(row)}, user)
    except IntegrityError as exc:
        raise PolicyTransitionError(
            "A policy with this id and version already exists.",
            code="duplicate_version",
        ) from exc
    return row


def update_draft(plane, row, data, user):
    state = plane.state(row)
    if state == IN_REVIEW:
        raise PolicyTransitionError(
            "An in-review version is frozen. Publish it or copy a new draft.",
            code="frozen_draft",
        )
    if state != DRAFT:
        raise PolicyTransitionError(
            "Authoritative and superseded versions cannot be edited. "
            "Copy forward to a new draft.",
            code="immutable_rule",
        )
    with transaction.atomic():
        before = {"lifecycle": state}
        row = plane.apply(row, data)
        plane.stamp(row, user)
        _event(plane, row, "update", before, {"lifecycle": plane.state(row)}, user)
    return row


def delete_draft(plane, row, user):
    if plane.state(row) != DRAFT:
        raise PolicyTransitionError(
            "Only a draft can be deleted. Published versions are superseded.",
            code="immutable_rule",
        )
    with transaction.atomic():
        _event(
            plane, row, "delete",
            {
                "lifecycle": plane.state(row),
                "policy": plane.policy_id(row),
                "version": plane.version_of(row),
            },
            None,
            user,
        )
        plane.remove(row)


def copy_forward(plane, row, user, *, version=None, effective_date=None):
    if plane.state(row) not in (AUTHORITATIVE, SUPERSEDED):
        raise PolicyTransitionError(
            "Copy forward starts from a published version.",
            code="not_published",
        )
    new_version = (version or "").strip() or plane.next_version(row)
    if plane.version_exists(row, new_version):
        raise PolicyTransitionError(
            f"Version {new_version} already exists.",
            code="duplicate_version",
        )
    with transaction.atomic():
        draft = plane.clone(row, new_version, effective_date)
        plane.stamp(draft, user)
        _event(
            plane, draft, "copy_forward",
            {"source_id": row.pk, "source_version": plane.version_of(row)},
            {"lifecycle": plane.state(draft), "version": plane.version_of(draft)},
            user,
        )
    return draft


def submit(plane, row, user):
    if plane.state(row) != DRAFT:
        raise PolicyTransitionError("Only a draft can be submitted.", code="not_draft")
    with transaction.atomic():
        locked = plane.lock(row.pk)
        if plane.state(locked) != DRAFT:
            raise PolicyTransitionError("Only a draft can be submitted.", code="not_draft")
        before = plane.state(locked)
        plane.set_state(locked, IN_REVIEW, False)
        plane.stamp(locked, user)
        _event(
            plane, locked, "submit",
            {"lifecycle": before},
            {"lifecycle": plane.state(locked)},
            user,
        )
    return locked


def _supersede_earlier(plane, row, user):
    for other in plane.authoritative_others(row):
        if plane.effective_on(other) == plane.effective_on(row):
            raise PolicyTransitionError(
                "Another authoritative version already covers this policy and date.",
                code="authoritative_overlap",
            )
        if plane.effective_on(other) > plane.effective_on(row):
            raise PolicyTransitionError(
                "A later authoritative version already exists for this policy.",
                code="authoritative_overlap",
            )
        before = plane.state(other)
        plane.set_state(other, SUPERSEDED, False)
        _event(
            plane, other, "supersede",
            {"lifecycle": before},
            {"lifecycle": SUPERSEDED, "replaced_by": row.pk},
            user,
        )


def publish(plane, row, user):
    with transaction.atomic():
        locked = plane.lock(row.pk)
        if plane.state(locked) != IN_REVIEW:
            raise PolicyTransitionError(
                "Publish starts from in review.",
                code="not_in_review",
            )
        plane.require_distinct(locked, user)
        if not plane.citation(locked).strip():
            raise PolicyTransitionError(
                "Publish requires a citation.",
                code="citation_required",
            )
        examples = plane.example_report(locked)
        if not examples["passed"]:
            raise PolicyTransitionError(
                "Publish blocked: examples did not pass.",
                code=examples.get("code") or "examples_failed",
                errors=examples["results"],
            )
        floors = plane.floor_report(locked)
        if not floors["passed"]:
            raise PolicyTransitionError(
                "Publish blocked: a floor was not met.",
                code=floors.get("code") or "floor_failed",
                errors=floors["results"],
            )
        _supersede_earlier(plane, locked, user)
        before = plane.state(locked)
        plane.set_state(locked, AUTHORITATIVE, True)
        _event(
            plane, locked, "publish",
            {"lifecycle": before},
            {"lifecycle": AUTHORITATIVE, "version": plane.version_of(locked)},
            user,
        )
    return locked
