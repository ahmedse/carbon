"""
core/management/commands/seed_carbon_metadata.py

Seed the Carbon DATA QUALITY RULES + CATALOG metadata from CSV source files in
raw/csv/ (see raw/SEED_SPEC_METADATA.md). Complements seed_carbon_raw.py, which
seeds only the activity rows; this command seeds the metadata layer on top.

Scope (agreed, no fabrication):
  - DQ rules are AUTHORED metadata — min>=0 range, completeness (not_null),
    allowed-values, and reference-integrity rules grounded in the seeded
    Carbon tables' field types and observed values. Not numbers invented from
    thin air.
  - Catalog entries (domain, glossary terms, tags, asset profiles, governance
    policies) describe the seeded assets.

Idempotent: get_or_create throughout. Safe to re-run. Does NOT touch Users/Groups
or any other app's data.
"""
import csv
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

CSV_DIR = Path(settings.BASE_DIR).parent / "raw" / "csv"
User = get_user_model()


class Command(BaseCommand):
    help = "Seed Carbon DQ rules + catalog metadata from raw/csv metadata CSVs (idempotent)."

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        self._seed_dq_rules(admin)
        self._seed_catalog(admin)
        self.stdout.write(self.style.SUCCESS("\nCarbon metadata seed complete."))

    # ── helpers ──────────────────────────────────────────────────────────
    def _csv(self, name):
        # utf-8-sig strips the UTF-8 BOM that export_csv.py writes on every file.
        with open(CSV_DIR / name, newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def _flag(value):
        return (value or "true").strip().lower() != "false"

    @staticmethod
    def _parse_config(raw):
        """Parse 'k=v|k2=v2' into a dict (values coerced to int/float/bool/str)."""
        out = {}
        for part in (raw or "").split("|"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if v == "true":
                out[k] = True
            elif v == "false":
                out[k] = False
            elif v.isdigit():
                out[k] = int(v)
            else:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
        return out

    def _resolve_table(self, module_token, table_name):
        from dataschema.models import DataTable
        return DataTable.objects.filter(
            module__name__icontains=module_token, name=table_name
        ).first()

    def _params(self, rule_type, r, ReferenceSet):
        rule_type = rule_type.strip()
        if rule_type == "range":
            p = {}
            if (r.get("min") or "").strip() != "":
                p["min"] = float(r["min"])
            if (r.get("max") or "").strip() != "":
                p["max"] = float(r["max"])
            return p
        if rule_type == "allowed_values":
            vals = (r.get("values") or "").strip()
            if vals:
                return {"values": [v.strip() for v in vals.split("|") if v.strip()]}
            rs_name = (r.get("reference_set") or "").strip()
            if rs_name:
                rs = ReferenceSet.objects.filter(name=rs_name).first()
                if rs:
                    return {"reference_set": rs.id}
            return {}
        if rule_type == "reference_integrity":
            rs = ReferenceSet.objects.filter(name=(r.get("reference_set") or "").strip()).first()
            return {"reference_set_id": rs.id} if rs else {}
        if rule_type == "threshold":
            return {
                "operator": (r.get("operator") or "gte").strip(),
                "value": float(r["value"]),
            }
        return {}

    # ── DQ rules ─────────────────────────────────────────────────────────
    def _seed_dq_rules(self, admin):
        from dq.models import DQRule, RuleFieldAssignment
        from dataschema.models import DataField
        from mdm.models import ReferenceSet

        rows = self._csv("carbon_dq_rules.csv")

        # Reuse: rows sharing `rule_name` are ONE rule bound to many fields.
        # The CSV is binding-centric (one row per field) but collapses into
        # reusable DQRule objects keyed by rule_name.
        grouped = {}
        for r in rows:
            grouped.setdefault((r["rule_name"] or "").strip(), []).append(r)

        created_rules = created_assignments = skipped = 0
        for rule_name, group in grouped.items():
            if not rule_name:
                skipped += len(group)
                continue

            meta = group[0]
            rule_type = (meta["rule_type"] or "").strip()
            level = (meta["level"] or "field").strip()
            dimension = (meta["dimension"] or "").strip()
            severity = (meta["severity"] or "error").strip()
            active = self._flag(meta.get("active", "true"))
            description = (meta["description"] or "").strip() or rule_name
            params = self._params(rule_type, meta, ReferenceSet)

            bindings = []
            assignments = []  # (DataTable, DataField|None)
            for r in group:
                module = (r["module"] or "").strip()
                table = (r["table"] or "").strip()
                field_name = (r["field"] or "").strip()

                tbl = self._resolve_table(module, table)
                if not tbl:
                    self.stderr.write(f"SKIP: table not found '{module}'/'{table}'")
                    skipped += 1
                    continue

                bindings.append(
                    {"table": table, "field": field_name} if field_name else {"table": table}
                )

                field = None
                if field_name:
                    field = DataField.objects.filter(data_table=tbl, name=field_name).first()
                    if not field:
                        self.stderr.write(
                            f"SKIP: field not found '{module}'/'{table}'.{field_name}"
                        )
                        skipped += 1
                        continue
                assignments.append((tbl, field))

            definition = {
                "schema_version": 1,
                "name": rule_name,
                "level": level,
                "dimension": dimension,
                "type": rule_type,
                "severity": severity,
                "active": active,
                "description": description,
                "bindings": bindings,
                "params": params,
            }

            rule, created = DQRule.objects.get_or_create(
                name=rule_name,
                defaults={
                    "rule_level": "field_validation" if level == "field" else "business_rule",
                    "rule_type": rule_type,
                    "dimension": dimension,
                    "severity": severity,
                    "is_active": active,
                    "description": description,
                    "definition": definition,
                    "params": params,
                    "created_by": admin,
                },
            )
            if created:
                created_rules += 1
            else:
                # CSV is the source of truth — refresh definition/bindings in place.
                rule.definition = definition
                rule.params = params
                if not rule.description:
                    rule.description = description
                rule.save()

            for tbl, field in assignments:
                if field is not None:
                    _, a_created = RuleFieldAssignment.objects.get_or_create(
                        rule=rule, data_field=field, defaults={"data_table": tbl}
                    )
                else:
                    _, a_created = RuleFieldAssignment.objects.get_or_create(
                        rule=rule, data_table=tbl, data_field=None
                    )
                if a_created:
                    created_assignments += 1

        self.stdout.write(
            f"DQ rules: {created_rules} created / {len(grouped)} reusable rules; "
            f"{created_assignments} new field assignments; {skipped} skipped."
        )

    # ── Catalog ──────────────────────────────────────────────────────────
    def _seed_catalog(self, admin):
        from catalog.models import (
            DataDomain, GlossaryTerm, Tag, AssetProfile, GovernancePolicy,
        )
        from dataschema.models import DataField
        from mdm.models import OrgUnit

        # Domains
        domains = {}
        for r in self._csv("carbon_catalog_domains.csv"):
            d, _ = DataDomain.objects.get_or_create(
                name=r["name"].strip(),
                defaults={
                    "slug": r["slug"].strip(),
                    "description": r["description"].strip(),
                    "owner": admin,
                },
            )
            domains[r["name"].strip()] = d

        # Tags
        tags = {}
        for r in self._csv("carbon_catalog_tags.csv"):
            t, _ = Tag.objects.get_or_create(
                name=r["name"].strip(),
                defaults={"slug": r["slug"].strip(), "color": r["color"].strip()},
            )
            tags[r["name"].strip()] = t

        # Glossary
        terms = {}
        for r in self._csv("carbon_catalog_glossary.csv"):
            g, _ = GlossaryTerm.objects.get_or_create(
                term=r["term"].strip(),
                defaults={
                    "slug": r["slug"].strip(),
                    "definition": r["definition"].strip(),
                    "domain": domains.get(r["domain"].strip()),
                    "status": "approved",
                },
            )
            terms[r["term"].strip()] = g

        # Asset profiles (table-level and field-level)
        profiles = 0
        for r in self._csv("carbon_catalog_asset_profiles.csv"):
            entity_type = (r["entity_type"] or "").strip()
            tbl = self._resolve_table((r["module"] or "").strip(), (r["table"] or "").strip())
            if not tbl:
                self.stderr.write(f"SKIP profile: table not found '{r['module']}'/'{r['table']}'")
                continue
            defaults = {
                "description": (r["description"] or "").strip(),
                "domain": domains.get((r["domain"] or "").strip()),
                "owner": admin,
                "classification": (r["classification"] or "internal").strip(),
                "semantic_type": (r["semantic_type"] or "").strip(),
                "glossary_term": terms.get((r["glossary_term"] or "").strip()),
                "is_active": True,
            }
            field_name = (r["field"] or "").strip()
            if entity_type == "field" and field_name:
                fld = DataField.objects.filter(data_table=tbl, name=field_name).first()
                if not fld:
                    continue
                profile, _ = AssetProfile.objects.get_or_create(data_field=fld, defaults=defaults)
            else:
                profile, _ = AssetProfile.objects.get_or_create(data_table=tbl, defaults=defaults)
            tag_names = [t.strip() for t in (r["tags"] or "").split("|") if t.strip()]
            if tag_names:
                profile.tags.set([tags[n] for n in tag_names if n in tags])
            profiles += 1

        # Governance policies
        policies = 0
        for r in self._csv("carbon_catalog_policies.csv"):
            ou_name = (r["org_unit"] or "").strip()
            ou = OrgUnit.objects.filter(name=ou_name).first() if ou_name else None
            es = (r["emission_scope"] or "").strip()
            _, _ = GovernancePolicy.objects.get_or_create(
                name=r["name"].strip(), policy_type=r["policy_type"].strip(),
                defaults={
                    "description": (r["description"] or "").strip(),
                    "enabled": self._flag(r.get("enabled", "true")),
                    "scope_type": (r["scope_type"] or "global").strip(),
                    "emission_scope": int(es) if es.isdigit() else None,
                    "org_unit": ou,
                    "domain": domains.get((r["domain"] or "").strip()),
                    "config": self._parse_config(r.get("config", "")),
                    "error_message": (r["error_message"] or "").strip(),
                },
            )
            policies += 1

        self.stdout.write(
            f"Catalog: {len(domains)} domain(s), {len(tags)} tags, "
            f"{len(terms)} glossary terms, {profiles} asset profiles, "
            f"{policies} governance policies."
        )
