# People calls the domain-free lifecycle. This module registers the payroll
# plane and keeps the names create_draft, submit, publish, example_report,
# and floor_report so existing callers stay on one service.

from __future__ import annotations

from catalog import policy_lifecycle as lifecycle
from people.models import Employee
from people.policy_plane import PLANE

PolicyTransitionError = lifecycle.PolicyTransitionError


def create_draft(data, user):
    return lifecycle.create_draft(PLANE, data, user)


def update_draft(rule, data, user):
    return lifecycle.update_draft(PLANE, rule, data, user)


def delete_draft(rule, user):
    return lifecycle.delete_draft(PLANE, rule, user)


def copy_forward(rule, user, *, version=None, effective_date=None):
    return lifecycle.copy_forward(
        PLANE, rule, user, version=version, effective_date=effective_date,
    )


def submit(rule, user):
    return lifecycle.submit(PLANE, rule, user)


def publish(rule, user):
    return lifecycle.publish(PLANE, rule, user)


def example_report(rule):
    return PLANE.example_report(rule)


def floor_report(rule):
    return PLANE.floor_report(rule)


def preview(rule):
    report = lifecycle.preview(PLANE, rule)
    return {
        "lifecycle": rule.lifecycle,
        "citation": bool((rule.source_citation or "").strip()),
        "examples": report["examples"],
        "floors": report["floors"],
        "diff": report["diff"],
        "event": report["event"],
        "active_employees": Employee.objects.filter(is_active=True).count(),
    }
