# TASK-DELETE-SAFETY-ENTERPRISE.md

## Task: Enterprise-Grade Deletion Safety — All Unprotected Entities

**Created:** 2026-08-10 | **Architect:** Master Architect  
**Status:** Spec written, ready for delegation  
**Context:** Deep audit of 35 entity deletion paths found 17 unprotected ViewSets (49%) performing default hard-deletes with zero dependency gates, plus 2 partially-protected entities and 5 frontend UX gaps.

---

## Scope Overview

| Priority | Entities | Backend files | Frontend files | Est. Hours |
|----------|----------|---------------|----------------|------------|
| 🔴 Critical | 7 (ReportingPeriod, EmissionFactor, Calculation, CalculationRule, SBTiTarget, ExportProject, ImportJob) | `emissions/views.py`, `importexport/views.py` | 4 pages | 6 |
| 🟠 High | 5 (GWP, OrganizationalBoundary, BaseYear, DataSource, ConsumingConnection) | `emissions/views.py`, `connections/views.py` | 2 pages | 2 |
| 🟡 Partial fix | 2 (DataField dependency check, DataRow soft-delete+audit) | `dataschema/views.py` | 0 | 1 |
| 🔵 Frontend | 5 UX gaps | — | 5 pages | 1 |
| **Total** | **19** | **5 files** | **8 pages** | **~10 hours** |

---

## Design Principles (Non-Negotiable)

1. **Every ViewSet with DELETE MUST override `destroy()`.** No silent inheritance.
2. **Soft-delete is the default.** Use existing `is_active`/`is_archived` model fields where they exist. Entities WITHOUT such a field (GWP, SBTiTarget) hard-delete WITH an audit event — never add a migration just for soft-delete. Hard delete only when there are zero dependencies AND an audit event is emitted.
3. **Dependency checks must return structured `AppFeedback`.** Never let `IntegrityError` / `ProtectedError` reach the user as a 500.
4. **Every delete MUST emit a governance audit event.** Use `emit_governance_event()` (from `catalog.audit_utils` — NOTE: `catalog.events` does NOT exist) or `_log_schema_change()` (dataschema pattern).
5. **The `?force=true` escape hatch is reserved for superusers only** and only on entities where data loss is acceptable (tables, modules, rows — already implemented).

---

## Deliverable 1: Critical Emissions Entities (6 hours)

### 1A. `ReportingPeriodViewSet` — `emissions/views.py:57`

**Current:** No `destroy()` override. Deleting a period with `on_delete=CASCADE` on Verification silently destroys all verifications.

**Fix:**
- Block deletion if `status` is NOT in `('draft', 'closed')` → `AppFeedback`
- Block deletion if `calculations.exists()` → `AppFeedback` with `?force=true` for superuser
- If no calculations: soft-delete by setting `status='closed'` and archiving
- Emit governance audit event before save
- Tests: 3 test methods (blocked active period, blocked with calculations, soft-delete draft)

```python
def destroy(self, request, *args, **kwargs):
    period = self.get_object()
    can_delete_statuses = ('draft', 'closed')
    if period.status not in can_delete_statuses:
        raise AppFeedback(
            code="period_not_deletable",
            title=f"Cannot delete a '{period.status}' reporting period",
            detail=f"'{period.name}' is in '{period.status}' status.",
            reasons=[f"Only periods in 'draft' or 'closed' status can be deleted."],
            remediation=["Close the period first, then retry deletion."],
            context={"period_id": period.id, "status": period.status},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    calc_count = period.calculations.count()
    if calc_count > 0:
        force = request.query_params.get("force", "").lower() == "true"
        if not (force and request.user.is_superuser):
            raise AppFeedback(
                code="period_has_calculations",
                title="Cannot delete: calculations exist",
                detail=f"'{period.name}' has {calc_count} emission calculation(s).",
                reasons=["Deleting the period would lose verified emission data."],
                remediation=["Use ?force=true as a superuser if you understand the consequences."],
                context={"period_id": period.id, "calculation_count": calc_count},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    # Soft-delete: set status to closed
    period.status = 'closed'
    period.save(update_fields=['status', 'updated_at'])
    # Audit
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='ReportingPeriod', entity_id=period.id,
        action='delete', before={'status': 'draft'}, after={'status': 'closed'},
        user=request.user,
    )
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 1B. `EmissionFactorViewSet` — `emissions/views.py:282`

**Current:** No `destroy()` override. `CalculationRule.emission_factor` uses `PROTECT` → raw DB `ProtectedError` 500 if any rule references it.

**Fix:**
- Check `calculation_rules.exists()` → `AppFeedback` listing referencing rules
- If no dependencies: soft-delete `is_active = False`
- Emit governance audit event

```python
def destroy(self, request, *args, **kwargs):
    factor = self.get_object()
    ref_rules = factor.calculation_rules.select_related('data_table').values_list('name', 'data_table__name')[:10]
    ref_count = factor.calculation_rules.count()
    if ref_count > 0:
        rule_names = ", ".join(f"'{r[0]}' (table: {r[1]})" for r in ref_rules)
        if ref_count > 10:
            rule_names += f" ... and {ref_count - 10} more"
        raise AppFeedback(
            code="factor_in_use",
            title="Cannot delete emission factor",
            detail=f"'{factor.name}' is referenced by {ref_count} calculation rule(s): {rule_names}.",
            reasons=["Emission factors with active calculation rules cannot be removed."],
            remediation=["Deactivate or reassign the calculation rules first."],
            context={"factor_id": factor.id, "referencing_rules_count": ref_count},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    factor.is_active = False
    factor.save(update_fields=['is_active', 'updated_at'])
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='EmissionFactor', entity_id=factor.id,
        action='delete', before={'is_active': True}, after={'is_active': False},
        user=request.user,
    )
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 1C. `CalculationViewSet` — `emissions/views.py:380`

**Current:** No `destroy()` override. Deleting a calculation silently removes emission results. `PROTECT` on `reporting_period` and `emission_factor` (irrelevant for delete direction — only reverse lookups matter).

**Fix:**
- Block hard delete. Always archive.
- Emit governance audit event.

```python
def destroy(self, request, *args, **kwargs):
    calc = self.get_object()
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='Calculation', entity_id=calc.id,
        action='delete',
        before={'data_row_id': calc.data_row_id, 'co2e_kg': str(calc.co2e_kg), 'scope': calc.scope},
        after={'archived': True},
        user=request.user,
    )
    calc.delete()  # CALCULATIONS ARE RECALCULATABLE — hard delete is OK with audit
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 1D. `CalculationRuleViewSet` — `emissions/views.py:604`

**Current:** No `destroy()` override. `CalculationAudit.calculation_rule` → `SET_NULL` — audit trail goes cold.

**Fix:**
- Check `calculationaudit_set.exists()` → archive instead of hard delete
- If no audits: allow hard delete with audit event
- Pattern mirrors DQRule (archive when results exist)

```python
def destroy(self, request, *args, **kwargs):
    rule = self.get_object()
    audit_count = rule.calculationaudit_set.count()
    if audit_count > 0:
        rule.is_active = False
        rule.save(update_fields=['is_active', 'updated_at'])
        from catalog.audit_utils import emit_governance_event
        emit_governance_event(
            entity_type='CalculationRule', entity_id=rule.id,
            action='archive', before={'is_active': True}, after={'is_active': False, 'audit_count': audit_count},
            user=request.user,
        )
        return Response({
            'archived': True,
            'audit_count': audit_count,
            'detail': f'Rule archived. {audit_count} audit records preserved.',
        }, status=status.HTTP_200_OK)
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='CalculationRule', entity_id=rule.id,
        action='delete', before={'name': rule.name}, after={'deleted': True},
        user=request.user,
    )
    return super().destroy(request, *args, **kwargs)
```

### 1E. `SBTiTargetViewSet` — `emissions/views.py:1113`

**Current:** No `destroy()` override. `PROTECT` on `reporting_period` would block period deletion. M2M with org_units.

**Fix (VERIFIED):** `SBTiTarget` has NO `is_active` field — hard-delete WITH an audit event (no migration). Import is `catalog.audit_utils`, not `catalog.events`.

```python
def destroy(self, request, *args, **kwargs):
    target = self.get_object()
    # SBTiTarget has no is_active field — hard delete with audit trail
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='SBTiTarget', entity_id=target.id,
        action='delete',
        before={'name': target.name, 'base_year': target.base_year, 'target_year': target.target_year},
        after={'deleted': True},
        user=request.user,
    )
    target.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 1F. `ExportProjectViewSet` — `importexport/views.py:18`

**Current:** No `destroy()` override. `ExportJob.export_project` → `SET_NULL` — export job history loses project context.

**Fix:** Soft-delete `is_active = False` if export jobs exist. Audit event.

```python
def destroy(self, request, *args, **kwargs):
    project = self.get_object()
    job_count = project.export_jobs.count()
    if job_count > 0:
        project.is_active = False
        project.save(update_fields=['is_active', 'updated_at'])
        return Response({
            'archived': True,
            'job_count': job_count,
            'detail': f'Export project archived. {job_count} export jobs preserved.',
        }, status=status.HTTP_200_OK)
    return super().destroy(request, *args, **kwargs)
```

### 1G. `ImportJobViewSet` — `importexport/views.py:43`

**Current:** No `destroy()` override. Delete silently destroys import audit trail.

**Fix:** Block hard delete entirely — import jobs are audit records. Return 405.

```python
def destroy(self, request, *args, **kwargs):
    return Response({
        'detail': 'Import job records are part of the audit trail and cannot be deleted.',
        'resource': 'ImportJob',
    }, status=status.HTTP_405_METHOD_NOT_ALLOWED)
```

---

## Deliverable 2: High-Priority Entities (2 hours)

### 2A. `GWPViewSet` — `emissions/views.py:341`

**Current:** No `destroy()` override. GWPs are climate science reference data.

**Fix (VERIFIED):** `GWP` has NO `is_active` field — hard-delete WITH an audit event (no migration). Import is `catalog.audit_utils`.

```python
def destroy(self, request, *args, **kwargs):
    gwp = self.get_object()
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='GWP', entity_id=gwp.id,
        action='delete',
        before={'gas_name': gwp.gas_name, 'gas_formula': gwp.gas_formula},
        after={'deleted': True},
        user=request.user,
    )
    gwp.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 2B. `OrganizationalBoundaryViewSet` — `emissions/views.py:1243`

**Current:** No `destroy()` override. Referenced by `ReportingPeriod.organizational_boundary` (SET_NULL). Deleting silently breaks period boundary link.

**Fix:** Check for referencing periods → block. Soft-delete.

```python
def destroy(self, request, *args, **kwargs):
    boundary = self.get_object()
    ref_periods = boundary.reporting_periods.count()
    if ref_periods > 0:
        raise AppFeedback(
            code="boundary_in_use",
            title="Cannot delete organizational boundary",
            detail=f"'{boundary.name}' is referenced by {ref_periods} reporting period(s).",
            reasons=["Organizational boundaries linked to reporting periods cannot be removed."],
            remediation=["Reassign those periods to a different boundary first."],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    boundary.is_active = False
    boundary.save(update_fields=['is_active'])
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='OrganizationalBoundary', entity_id=boundary.id,
        action='delete', before={'is_active': True}, after={'is_active': False},
        user=request.user,
    )
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 2C. `BaseYearViewSet` — `emissions/views.py:1256`

**Current:** No `destroy()` override. Referenced by `RecalculationTrigger.base_year`.

**Fix:** Check for recalculation triggers → block. Soft-delete if clean.

```python
def destroy(self, request, *args, **kwargs):
    base_year = self.get_object()
    trigger_count = base_year.recalculation_triggers.count()
    if trigger_count > 0:
        raise AppFeedback(
            code="base_year_in_use",
            title="Cannot delete base year",
            detail=f"'{base_year}' has {trigger_count} recalculation trigger(s).",
            reasons=["Base years with recalculation history are immutable."],
            remediation=[],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='BaseYear', entity_id=base_year.id,
        action='delete', before={'year': base_year.year}, after={'deleted': True},
        user=request.user,
    )
    return super().destroy(request, *args, **kwargs)
```

Check: does `BaseYear` model have `recalculation_triggers` related_name? The `RecalculationTrigger` model uses `models.ForeignKey('BaseYear', ...)` — check the actual `related_name`:

Read the model to confirm. If no related_name, use `recalculationtrigger_set`.

### 2D. `DataSourceViewSet` — `connections/views.py:14`

**Current:** No `destroy()` override. `ImportJob.source` → `SET_NULL`.

**Fix:** Soft-delete `is_active = False`. Emit audit event.

```python
def destroy(self, request, *args, **kwargs):
    source = self.get_object()
    source.is_active = False
    source.save(update_fields=['is_active'])
    from catalog.audit_utils import emit_governance_event
    emit_governance_event(
        entity_type='DataSource', entity_id=source.id,
        action='delete', before={'is_active': True}, after={'is_active': False},
        user=request.user,
    )
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### 2E. `ConsumingConnectionViewSet` — `connections/views.py:35`

**Current:** No `destroy()` override.

**Fix:** Soft-delete `is_active = False`. Emit audit event. (Same pattern as DataSource.)

---

## Deliverable 3: Partial Fixes — Dataschema (1 hour)

### 3A. `DataFieldViewSet.perform_destroy()` — `dataschema/views.py:228`

**Current:** Has audit log, but no dependency checks. Deleting a field with DQ rule assignments or reference bindings silently orphanes them.

**Fix:** Add dependency guards before the existing `instance.delete()`:

```python
def perform_destroy(self, instance):
    # Dependency check: DQ rule assignments
    rule_assignments = instance.rule_assignments.count()
    if rule_assignments > 0:
        raise AppFeedback(
            code="field_has_rules",
            title="Cannot delete field",
            detail=f"'{instance.name}' is assigned to {rule_assignments} DQ rule(s).",
            reasons=["Remove the DQ rule assignments from this field first."],
            remediation=[],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    # Dependency check: reference set bindings
    if instance.reference_set_id:
        raise AppFeedback(
            code="field_bound_to_reference_set",
            title="Cannot delete field",
            detail=f"'{instance.name}' is bound to reference set '{instance.reference_set.name}'.",
            reasons=["Remove the reference set binding first."],
            remediation=[],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    # Dependency check: catalog profile
    if hasattr(instance, 'catalog_profile') and instance.catalog_profile:
        raise AppFeedback(
            code="field_has_catalog_profile",
            title="Cannot delete field",
            detail=f"'{instance.name}' has a catalog profile.",
            reasons=["Delete the catalog profile first."],
            remediation=[],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    # Existing audit + delete
    before = DataFieldSerializer(instance).data
    parent_table = instance.data_table
    _log_schema_change(
        self.request.user, "delete", data_table=parent_table, data_field=instance,
        before=before,
        notes=f"Deleted field '{instance.name}' (id={instance.id})",
    )
    instance.delete()
```

### 3B. `DataRowViewSet.destroy()` — `dataschema/views.py:329`

**Current:** Only checks lock. `is_archived` field exists on the model but is never used. No audit event.

**Fix:** Convert to soft-delete using `is_archived`. Add audit event.

```python
def destroy(self, request, *args, **kwargs):
    """Soft-delete: set is_archived=True. Guard against writes on locked tables."""
    instance = self.get_object()
    self._check_table_not_locked(instance.data_table, request)
    instance.is_archived = True
    instance.save(update_fields=['is_archived', 'updated_at'])
    _log_schema_change(
        self.request.user, "archive", data_table=instance.data_table,
        notes=f"Archived row {instance.id} (table '{instance.data_table.title}')",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## Deliverable 4: Frontend Fixes (1 hour)

### 4A. DQ Rule Delete — Archive Awareness

**File:** `carbon-frontend/src/pages/catalog/DQHubPage.jsx` (~line 331)

The backend returns `{archived: true, results_count: N}` for rules with results. The frontend currently shows a generic "Rule deleted" — it should distinguish:

```jsx
const handleDeleteRule = async (rule) => {
  if (!window.confirm(`Archive rule "${rule.name || 'DQ rule'}"?`)) return;
  try {
    const result = await deleteDQRule(token, rule.id);
    if (result.archived) {
      notify({
        message: `Rule archived. ${result.results_count} historical results preserved.`,
        type: 'info'
      });
    } else {
      notify({ message: 'Rule deleted', type: 'success' });
    }
    loadRules();
  } catch (err) {
    notify({ message: err.message || 'Delete failed', type: 'error' });
  }
};
```

Also replace `window.confirm()` with a proper MUI `<Dialog>` (like `EmissionFactorsPage` does).

### 4B. Calculation Rule Delete — Archive Awareness

**File:** `carbon-frontend/src/pages/emissions/CalculationRulesPage.jsx` (~line 344)

Same pattern — check for `{archived: true}` in the response.

### 4C. Emission Factor Delete — Dependency Error Handling

**File:** `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` (~line 108)

The "This action cannot be undone" dialog should be enhanced to catch and display the structured `AppFeedback` from `factor_in_use` code with rule names.

### 4D. Metadata Management — 405 Handling

**File:** `carbon-frontend/src/pages/catalog/MetadataManagementPage.jsx` (~line 188)

DataDomain, GlossaryTerm, Tag return 405. NOTE: these models have NO `is_active` field (only `AssetProfile` does), so "Archive via PATCH" is NOT implementable. Implement the error-handler fallback instead: display the 405 remediation message (`err.data?.detail`) and close the dialog. This is what shipped.

### 4E. Import/Export — Import Job Delete

**File:** `carbon-frontend/src/pages/catalog/ImportExportPage.jsx` (~line 177)

Import jobs will return 405 after fix. Either remove the delete button for import jobs or handle the 405 with appropriate messaging.

---

## Files Checklist

### Backend (5 files to edit)

| File | # of destroy() to add/modify | Entity |
|------|------------------------------|--------|
| `backend/emissions/views.py` | 5 new + 1 modified | ReportingPeriod, EmissionFactor, Calculation, CalculationRule, SBTiTarget, GWP |
| `backend/emissions/views.py` | 2 new | OrganizationalBoundary, BaseYear |
| `backend/connections/views.py` | 2 new | DataSource, ConsumingConnection |
| `backend/importexport/views.py` | 2 new | ExportProject, ImportJob |
| `backend/dataschema/views.py` | 2 modified | DataField, DataRow |

### Frontend (5 files to edit)

| File | Change |
|------|--------|
| `carbon-frontend/src/pages/catalog/DQHubPage.jsx` | Archive-aware message + proper Dialog |
| `carbon-frontend/src/pages/emissions/CalculationRulesPage.jsx` | Archive-aware message |
| `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` | Dependency error display |
| `carbon-frontend/src/pages/catalog/MetadataManagementPage.jsx` | 405 handling / Archive button |
| `carbon-frontend/src/pages/catalog/ImportExportPage.jsx` | Import job delete removal |

### Tests (1 new file)

| File | Content |
|------|---------|
| `backend/emissions/tests/test_delete_safety.py` | ~15 tests covering all 12 new destroy methods |

---

## Import Requirements (add to each views.py)

```python
from core.feedback import AppFeedback
from catalog.audit_utils import emit_governance_event  # NOTE: catalog.events does NOT exist
```

---

## Acceptance Gates

### Backend
- [ ] All 12 unprotected ViewSets have `destroy()` overrides
- [ ] `DELETE /carbon-api/carbon/periods/{id}/` on active period → 400 with `period_not_deletable`
- [ ] `DELETE /carbon-api/carbon/periods/{id}/` on draft period with calculations → 400 with `period_has_calculations`
- [ ] `DELETE /carbon-api/carbon/periods/{id}/?force=true` as superuser on draft with calculations → 204
- [ ] `DELETE /carbon-api/carbon/factors/{id}/` with active rules → 400 with `factor_in_use`
- [ ] `DELETE /carbon-api/carbon/factors/{id}/` with no rules → 204, `is_active=False`
- [ ] `DELETE /carbon-api/carbon/rules/{id}/` with audit records → 200 with `{archived: true}`
- [ ] `DELETE /carbon-api/carbon/rules/{id}/` with no audit → 204
- [ ] `DELETE /carbon-api/carbon/sbti-targets/{id}/` → 204 (hard delete + audit event; no `is_active` field)
- [ ] `DELETE /carbon-api/carbon/gwp/{id}/` → 204 (hard delete + audit event; no `is_active` field)
- [ ] `DELETE /carbon-api/carbon/boundaries/{id}/` referenced by periods → 400
- [ ] `DELETE /carbon-api/carbon/base-years/{id}/` with triggers → 400
- [ ] `DELETE /connections/sources/{id}/` → 204, `is_active=False`
- [ ] `DELETE /connections/consuming/{id}/` → 204, `is_active=False`
- [ ] `DELETE /importexport/export-projects/{id}/` with jobs → 200 with `{archived: true}`
- [ ] `DELETE /importexport/export-projects/{id}/` no jobs → 204
- [ ] `DELETE /importexport/import/{id}/` → 405
- [ ] `DELETE /dataschema/fields/{id}/` with DQ rule assignments → 400
- [ ] `DELETE /dataschema/rows/{id}/` → 204, row archived (is_archived=True)
- [ ] `python manage.py check` passes (no new warnings)
- [ ] All existing tests still pass: `pytest --reuse-db --nomigrations -n auto --dist loadscope -q`
- [ ] New tests in `emissions/tests/test_delete_safety.py` all pass

### Frontend
- [ ] DQ Hub: delete button shows proper Dialog (not `window.confirm`)
- [ ] DQ Hub: archived rules show "archived" message with result count
- [ ] Calculation Rules: archived rules show "archived" message with audit count
- [ ] Emission Factors: dependency error shows rule names in alert
- [ ] Metadata page: domain/tag/glossary delete shows 405 remediation message (no `is_active` field on these models)
- [ ] Import/Export page: import job delete button removed or shows 405 message  
- [ ] `npm run build` passes

---

## DO NOT TOUCH

- `backend/dq/executor.py` — active DQ work in progress
- `backend/config/settings.py` — no structural changes
- `backend/accounts/models.py` — EmailConfig model is complete
- `backend/accounts/email_config.py` — complete
- `backend/catalog/policy_engine.py` — complete
- `backend/emissions/models.py` — NO model changes (use existing is_active/is_archived fields)
- Any migration files
- Already-protected entities: DataTable, Module, DQRule, ReferenceSet, ReferenceValue, OrgUnit, DataDomain, GlossaryTerm, Tag, GovernancePolicy, Evidence, Group, ScopedRole, RecalculationTrigger

## Architecture Rules

- All new `destroy()` methods MUST import `AppFeedback` from `core.feedback`
- All governance audit events MUST use `emit_governance_event()` from `catalog.audit_utils` (NOT `catalog.events`, which does not exist)
- Soft-delete MUST use `update_fields=[...]` for performance (avoid full model save)
- Structured errors MUST use `AppFeedback` with `code`, `title`, `detail`, `reasons`, `remediation`, `context`
- Never let a raw Django exception (`ProtectedError`, `IntegrityError`) reach the user
- No new pip packages required
- No new npm packages required
