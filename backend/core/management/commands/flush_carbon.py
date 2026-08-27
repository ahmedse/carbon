"""
core/management/commands/flush_carbon.py

Fully wipe the Carbon domain layer — OrgUnits, Modules, DataTables/Fields/Rows,
ReferenceSets, emission factors, calculations, catalog metadata, and DQ profiles —
leaving Users and Groups (authentication) intact.

This is the "clean the whole carbon footprint data completely" step that precedes
`seed_carbon_raw.py`. Deletion is ordered to satisfy PROTECT foreign keys:

  - Calculation / CalculationRule PROTECT -> EmissionFactor, ReportingPeriod
  - BaseYear PROTECT -> ReportingPeriod
  - Dataset PROTECT -> Module
  - DatasetVersion / DatasetVersionMember PROTECT -> DataTable

Everything else is CASCADE or SET_NULL, so explicit ordered deletes leave no orphans.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

# Imported lazily inside handle() to avoid app-loading order surprises, but kept
# top-level for clarity. All apps are already loaded by the time handle() runs.


class Command(BaseCommand):
    help = "Delete ALL carbon-domain data (org units, modules, tables, rows, factors, calcs, catalog, DQ). Preserves Users/Groups."

    def handle(self, *args, **options):
        from emissions import models as em
        from catalog import models as cat
        from dq import models as dq
        from dataschema import models as ds
        from core.models import Module
        from mdm import models as mdm
        from accounts.models import ScopedRole

        order = [
            # ── emissions (children of PROTECT parents first) ──
            ("emissions.Calculation", em.Calculation),
            ("emissions.CalculationAudit", em.CalculationAudit),
            ("emissions.ExportAudit", em.ExportAudit),
            ("emissions.RecalculationTrigger", em.RecalculationTrigger),
            ("emissions.VerificationRecord", em.VerificationRecord),
            ("emissions.SBTiTarget", em.SBTiTarget),
            ("emissions.BaseYear", em.BaseYear),
            ("emissions.CalculationRule", em.CalculationRule),
            ("emissions.ReportConfig", em.ReportConfig),
            ("emissions.ReportingPeriod", em.ReportingPeriod),
            ("emissions.OrganizationalBoundary", em.OrganizationalBoundary),
            ("emissions.EmissionFactor", em.EmissionFactor),
            ("emissions.GWP", em.GWP),

            # ── DQ (children of DataTable/DataField first) ──
            ("dq.DQResult", dq.DQResult),
            ("dq.DQJob", dq.DQJob),
            ("dq.DQSuggestion", dq.DQSuggestion),
            ("dq.DQAnomaly", dq.DQAnomaly),
            ("dq.RuleFieldAssignment", dq.RuleFieldAssignment),
            ("dq.DQRule", dq.DQRule),
            ("dq.FieldProfile", dq.FieldProfile),
            ("dq.TableProfile", dq.TableProfile),
            ("dq.SchemaChange", dq.SchemaChange),
            ("dq.SchemaSnapshot", dq.SchemaSnapshot),
            ("dq.FreshnessCheck", dq.FreshnessCheck),
            ("dq.DQProfileConfig", dq.DQProfileConfig),
            ("dq.RuleTag", dq.RuleTag),

            # ── catalog (Dataset PROTECT -> Module must go before Module) ──
            ("catalog.GovernanceEvent", cat.GovernanceEvent),
            ("catalog.NoteReaction", cat.NoteReaction),
            ("catalog.NoteComment", cat.NoteComment),
            ("catalog.Note", cat.Note),
            ("catalog.DataContractViolation", cat.DataContractViolation),
            ("catalog.DataContract", cat.DataContract),
            ("catalog.DatasetAccessPolicy", cat.DatasetAccessPolicy),
            ("catalog.DatasetVersionMember", cat.DatasetVersionMember),
            ("catalog.DatasetVersion", cat.DatasetVersion),
            ("catalog.Dataset", cat.Dataset),
            ("catalog.LineageEdge", cat.LineageEdge),
            ("catalog.AssetProfile", cat.AssetProfile),
            ("catalog.FreshnessPolicy", cat.FreshnessPolicy),
            ("catalog.GovernancePolicy", cat.GovernancePolicy),
            ("catalog.GlossaryTerm", cat.GlossaryTerm),
            ("catalog.Tag", cat.Tag),
            ("catalog.DataDomain", cat.DataDomain),

            # ── dataschema ──
            ("dataschema.DataRow", ds.DataRow),
            ("dataschema.FieldAccessPolicy", ds.FieldAccessPolicy),
            ("dataschema.TableRelation", ds.TableRelation),
            ("dataschema.SchemaChangeLog", ds.SchemaChangeLog),
            ("dataschema.DataField", ds.DataField),
            ("dataschema.DataTable", ds.DataTable),

            # ── core Module ──
            ("core.Module", Module),
        ]

        totals = {}
        with transaction.atomic():
            for label, model in order:
                n = model.objects.count()
                if n:
                    model.objects.all().delete()
                    totals[label] = n

            # ── mdm: ReferenceValue/ReferenceSet, then OrgUnit (bottom-up) ──
            rv = mdm.ReferenceValue.objects.count()
            if rv:
                mdm.ReferenceValue.objects.all().delete()
                totals["mdm.ReferenceValue"] = rv
            rs = mdm.ReferenceSet.objects.count()
            if rs:
                mdm.ReferenceSet.objects.all().delete()
                totals["mdm.ReferenceSet"] = rs

            org_count = mdm.OrgUnit.objects.count()
            if org_count:
                self._delete_org_units_bottom_up(mdm.OrgUnit)
                totals["mdm.OrgUnit"] = org_count

            # ── accounts: ScopedRole (cascades with org/module, but explicit) ──
            sr = ScopedRole.objects.count()
            if sr:
                ScopedRole.objects.all().delete()
                totals["accounts.ScopedRole"] = sr

        self.stdout.write(self.style.SUCCESS("Carbon domain flushed completely."))
        for label, n in totals.items():
            self.stdout.write(f"  {label}: {n} deleted")
        self.stdout.write(self.style.SUCCESS(
            f"Preserved: Users, Groups, and other apps (evidence, mediafiles, "
            f"connections, ai, appregistry, integrations)."
        ))

    @staticmethod
    def _delete_org_units_bottom_up(org_model):
        """Delete OrgUnits deepest-first so self-referential SET_NULL parents don't orphan."""
        from mdm.models import OrgUnit
        remaining = set(OrgUnit.objects.values_list("id", flat=True))
        while remaining:
            # Leaf = no children still remaining
            leaves = OrgUnit.objects.filter(
                id__in=remaining
            ).exclude(children__id__in=remaining).values_list("id", flat=True)
            leaf_ids = list(leaves)
            if not leaf_ids:
                # cycle safety net (should not happen) — delete the rest directly
                OrgUnit.objects.filter(id__in=remaining).delete()
                remaining.clear()
                break
            OrgUnit.objects.filter(id__in=leaf_ids).delete()
            remaining -= set(leaf_ids)
