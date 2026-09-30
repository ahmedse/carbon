"""Carbon answers to the questions its guide pack asks (domain_packs/carbon/guide/guide.yaml).

Every probe is read-only and reads only the caller's own scope. No payload
carries a kilogram, a tonne or a factor value: counts, names, states and
timestamps only.
"""
from __future__ import annotations

from guide.registry import probe

PACK = "carbon"
PERIODS_PATH = "/carbon/reporting/periods"
COVERAGE_PATH = "/carbon/admin/inventory-coverage"
MANAGE_PERIODS = "carbon:manage_reporting_periods"
MANAGE_COVERAGE = "carbon:manage_inventory_coverage"
ENTER_DATA = "carbon:enter_data"
MAX_SOURCES = 8
MAX_MY_DATA = 20
MAX_PERIODS = 24


# ── Reads (memoised per request) ───────────────────────────────────────────

def _periods(ctx) -> list[dict]:
    def load():
        from emissions.models import ReportingPeriod

        return [
            {
                "id": row.id,
                "name": row.name,
                "status": row.status,
                "start_date": row.start_date.isoformat() if row.start_date else "",
                "end_date": row.end_date.isoformat() if row.end_date else "",
            }
            for row in ReportingPeriod.objects.all().order_by("-start_date", "-id")[:MAX_PERIODS]
        ]

    return ctx.once("periods", load)


def _open_periods(ctx) -> list[dict]:
    return [row for row in _periods(ctx) if row["status"] == "open"]


def _open_boundary(ctx) -> dict | None:
    """The open period's organisational boundary as name and approach. No figures."""

    def load():
        from emissions.models import ReportingPeriod

        opened = _open_periods(ctx)
        if len(opened) != 1:
            return None
        row = (
            ReportingPeriod.objects.filter(id=opened[0]["id"])
            .select_related("organizational_boundary").first()
        )
        boundary = row.organizational_boundary if row else None
        if boundary is None:
            return None
        return {"name": boundary.name, "approach": boundary.consolidation_approach}

    return ctx.once("boundary", load)


def _factor_scopes(ctx) -> set[int]:
    def load():
        from emissions.models import EmissionFactor

        return set(EmissionFactor.objects.filter(is_active=True).values_list("scope", flat=True))

    return ctx.once("factor_scopes", load)


def _sources(ctx, cap: str) -> list[dict]:
    """Active sources inside the caller's scope for ``cap``, with counts. No emission figures."""

    def load():
        from accounts.rbac_utils import org_scope_for_capability
        from dataschema.models import DataRow
        from emissions.models import InventorySource, InventorySourceStatus

        scope = org_scope_for_capability(ctx.user, cap)
        if not scope.unrestricted and not scope.ids:
            return []
        sources = InventorySource.objects.filter(is_active=True).select_related("org_unit")
        if not scope.unrestricted:
            sources = sources.filter(org_unit_id__in=scope.ids)
        opened = _open_periods(ctx)
        statuses = {}
        if len(opened) == 1:
            for row in InventorySourceStatus.objects.filter(
                reporting_period_id=opened[0]["id"], source__in=sources,
            ).prefetch_related("linked_tables"):
                statuses[row.source_id] = row
        factor_scopes = _factor_scopes(ctx)
        items = []
        for src in sources.order_by("id")[:MAX_SOURCES]:
            status = statuses.get(src.id)
            table_ids = [t.id for t in status.linked_tables.all()] if status else []
            rows = (
                DataRow.objects.filter(data_table_id__in=table_ids, is_archived=False).count()
                if table_ids else None
            )
            items.append({
                "id": src.id,
                "name": src.source_name,
                "scope": src.scope,
                "org_unit": src.org_unit.name if src.org_unit_id else "",
                "linked_tables": len(table_ids),
                "row_count": rows,
                "status": status.status if status else "declared",
                "tier": status.data_quality_tier if status else None,
                "exclusion_reason": (status.exclusion_reason or "") if status else "",
                "has_factor": src.scope in factor_scopes,
            })
        return items

    return ctx.once(("sources", cap), load)


def _lesson_sources(ctx, lesson) -> list[dict]:
    return _sources(ctx, lesson.get("scope_cap") or "carbon:view_console")


def _my_data(ctx, cap: str) -> list[dict]:
    """The same modules Data Entry lists, empties first. Counts and quality only."""

    def load():
        from accounts.rbac_utils import org_scope_for_capability
        from catalog.models import AssetProfile
        from core.models import Module
        from dataschema.models import DataRow, DataTable
        from django.db.models import Count, Max, Q

        scope = org_scope_for_capability(ctx.user, cap)
        modules = Module.objects.all()
        if scope.unrestricted:
            from accounts.rbac_utils import get_visible_org_units
            ids = [unit.id for unit in get_visible_org_units(ctx.user)]
            if ids:
                modules = modules.filter(org_unit_id__in=ids)
        elif scope.ids:
            modules = modules.filter(org_unit_id__in=scope.ids)
        else:
            return []
        modules = list(modules.order_by("name"))
        ids = [m.id for m in modules]
        tables = dict(
            DataTable.objects.filter(module_id__in=ids, is_archived=False)
            .values("module_id").annotate(n=Count("id")).values_list("module_id", "n")
        )
        rows = dict(
            DataRow.objects.filter(data_table__module_id__in=ids, is_archived=False)
            .values("data_table__module_id").annotate(n=Count("id"))
            .values_list("data_table__module_id", "n")
        )
        quality = {}
        for status, table_module, field_module in AssetProfile.objects.filter(
            Q(data_table__module_id__in=ids) | Q(data_field__data_table__module_id__in=ids)
        ).values_list("quality_status", "data_table__module_id", "data_field__data_table__module_id"):
            mid = table_module or field_module
            if mid:
                quality.setdefault(mid, []).append(status)
        items = []
        for module in modules:
            statuses = quality.get(module.id, [])
            if "failing" in statuses:
                state = "failing"
            elif "warning" in statuses:
                state = "warning"
            elif "passing" in statuses:
                state = "passing"
            else:
                state = "no_data"
            items.append({
                "id": module.id,
                "name": module.name,
                "scope": module.scope,
                "linked_tables": tables.get(module.id, 0),
                "row_count": rows.get(module.id, 0),
                "status": state,
            })
        items.sort(key=lambda row: (row["row_count"], row["name"]))
        return items[:MAX_MY_DATA]

    return ctx.once(("my_data", cap), load)


# ── need ───────────────────────────────────────────────────────────────────

@probe(PACK, "need", "one_open_period")
def need_one_open_period(ctx, lesson):
    count = len(_open_periods(ctx))
    if count == 1:
        return None
    return {
        "code": "no_open_period" if count == 0 else "many_open_periods",
        "path": PERIODS_PATH if ctx.has(MANAGE_PERIODS) else None,
    }


@probe(PACK, "need", "source_in_scope")
def need_source_in_scope(ctx, lesson):
    if _lesson_sources(ctx, lesson):
        return None
    return {"code": "no_source_in_scope", "path": COVERAGE_PATH if ctx.has(MANAGE_COVERAGE) else None}


# ── host ───────────────────────────────────────────────────────────────────

@probe(PACK, "host", "row_created")
def host_row_created(ctx, lesson):
    """A row the caller created, inside their own scope, since they started the lesson."""
    if ctx.started_at is None:
        return False
    from accounts.rbac_utils import org_scope_for_capability
    from dataschema.models import DataRow

    scope = org_scope_for_capability(ctx.user, ENTER_DATA)
    rows = DataRow.objects.filter(created_by=ctx.user, is_archived=False, created_at__gte=ctx.started_at)
    if not scope.unrestricted:
        rows = rows.filter(data_table__module__org_unit_id__in=scope.ids)
    return rows.exists()


@probe(PACK, "host", "one_open_period")
def host_one_open_period(ctx, lesson):
    return len(_open_periods(ctx)) == 1


@probe(PACK, "host", "source_has_factor")
def host_source_has_factor(ctx, lesson):
    return any(row["has_factor"] for row in _lesson_sources(ctx, lesson))


@probe(PACK, "host", "status_decided")
def host_status_decided(ctx, lesson):
    return any(
        row["status"] == "covered" or (row["status"] == "excluded" and row["exclusion_reason"])
        for row in _lesson_sources(ctx, lesson)
    )


@probe(PACK, "host", "boundary_set")
def host_boundary_set(ctx, lesson):
    return bool(_open_boundary(ctx))


@probe(PACK, "host", "calculation_run_by_me")
def host_calculation_run_by_me(ctx, lesson):
    """The caller has triggered a calculation run. Reads the audit row, not a result."""
    from emissions.models import CalculationAudit

    return CalculationAudit.objects.filter(triggered_by=ctx.user).exists()


# ── live ───────────────────────────────────────────────────────────────────

@probe(PACK, "live", "period")
def live_period(ctx, lesson):
    periods = _periods(ctx)
    opened = _open_periods(ctx)
    current = opened[0] if len(opened) == 1 else (periods[0] if periods else None)
    return {"kind": "period", "open_count": len(opened), "current": current}


@probe(PACK, "live", "boundary")
def live_boundary(ctx, lesson):
    return {"kind": "boundary", "period": (_open_periods(ctx) or [None])[0], "boundary": _open_boundary(ctx)}


@probe(PACK, "live", "sources")
def live_sources(ctx, lesson):
    return {"kind": "sources", "items": _lesson_sources(ctx, lesson)}


@probe(PACK, "live", "my_data")
def live_my_data(ctx, lesson):
    """Data Entry's own list. Empties first, so the first row is the source with the fewest rows."""
    return {"kind": "sources", "items": _my_data(ctx, lesson.get("scope_cap") or ENTER_DATA)}


# ── question ───────────────────────────────────────────────────────────────

@probe(PACK, "question", "scope_of_source")
def question_scope_of_source(ctx, lesson):
    """Which scope is the caller's first source in? Options are Scope 1, 2, 3 in order."""
    sources = _my_data(ctx, lesson.get("scope_cap") or ENTER_DATA)
    if not sources:
        return {"params": {"source": ""}, "correct": -1}
    return {"params": {"source": sources[0]["name"]}, "correct": int(sources[0]["scope"]) - 1}
