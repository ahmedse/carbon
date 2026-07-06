# Plan — Data Trust Core, Phased Execution

> **Type:** Execution plan (the *when* and *in what order*). Pairs with
> [DESIGN_DATA_TRUST_CORE.md](DESIGN_DATA_TRUST_CORE.md) (the *what/why*),
> [DESIGN_ORG_ACCESS_MODEL.md](DESIGN_ORG_ACCESS_MODEL.md) (org structure + access control), and
> [STRATEGY_DATA_TRUST_PLATFORM.md](STRATEGY_DATA_TRUST_PLATFORM.md) (the *vision*).
> **For the implementing worker:** Do **only** the phase you are told to do. Each task has explicit
> acceptance criteria. Do not pull work forward from later phases. Ask before deviating from the design.

---

## Progress log (RUN history)

- ✅ RUN 1–3: Data Trust core — `catalog`, `mdm`, `dq` apps (built + verified).
- ✅ RUN 4: Carbon wired onto the core (reference data + catalog + DQ).
- ✅ RUN 5: `Project` removed; replaced by `OrgUnit` (self-referencing MDM tree in `mdm/`).
- ▶️ **RUN 6 (current): Org Access — Phase A.** Link `OrgUnit → Module`, org-scoped RBAC
  (permission + querysets + subtree expansion), add `campus` org type, seed the AASTMT slice +
  Transportation Gas Bills scenario + a department data-owner. See [DESIGN_ORG_ACCESS_MODEL.md](DESIGN_ORG_ACCESS_MODEL.md).
- ⏭️ RUN 7: Org Access — Phase B (frontend org context + steward-scoped admin screens).

---

## How to read this plan

- **🔴 NON-NEGOTIABLE (now)** — the minimum that makes this "a Data Trust core with Carbon on top."
- **🟡 IMPORTANT (next)** — high value, but only after the red set is solid.
- **⚪ LATER** — deferred by decision; do not start without explicit approval.
- Every task: **Deliverable → Acceptance criteria**. A phase is "done" only when all its criteria pass.

Global rules:
- One-way dependency: `emissions → core`, never `core → emissions`. `catalog`/`mdm`/`dq` must not import `emissions`.
- Every new API is `ScopedRole`-protected and `drf_yasg`-documented.
- No tenant. No Pulse-side/AI/LLM work here. No async/Celery in the red set.
- Additive migrations only; never drop existing columns without an explicit instruction.

---

## Phase 0 — Scaffolding & guardrails  🔴 NON-NEGOTIABLE

**Goal:** create the three core apps and the seams, with zero behavior change to Carbon.

- **0.1** Create Django apps `catalog`, `mdm`, `dq`; register in `INSTALLED_APPS`; URL-mount under `/carbon-api/`.
  - *Acceptance:* `python manage.py check` passes; empty routers return 200 on their list roots.
- **0.2** Add a `platform` vs `app` boundary note in code (docstrings/`README` per app) stating the one-way dependency rule.
  - *Acceptance:* each new app has a top README stating "domain-agnostic, must not import emissions".
- **0.3** Add additive field `DataField.reference_set` (nullable FK to `mdm.ReferenceSet`), migration only, unused yet.
  - *Acceptance:* migration applies cleanly; existing dataschema APIs unchanged.

**Exit criteria:** apps exist, mount, migrate, and Carbon still works end-to-end (login → modules 200).

---

## Phase 1 — Trust MVP (Catalog + RDM + DQ + Carbon wiring)  🔴 NON-NEGOTIABLE

The heart of the deliverable. Build in this order (each builds on the previous).

### 1A. Catalog & Governance (`catalog`)
- **1A.1** Models: `DataDomain`, `GlossaryTerm`, `Tag`, `AssetProfile`, `GovernanceEvent` (per design §5.1).
- **1A.2** DRF ViewSets + serializers + routes: `domains/`, `glossary/`, `tags/`, `assets/`, `assets/{id}/`, `search/?q=`.
- **1A.3** `assets/` lists **every `DataTable` and `DataField`** with catalog metadata (auto-create `AssetProfile` on first read if missing), filterable by `domain`, `owner`, `classification`, `quality_status`, `tag`, `project_id`, `module_id`.
- **1A.4** Writes (owner/steward/description/classification/tags/domain/glossary link) restricted to `admins_group`/data-owner; every write emits a `GovernanceEvent`.
- *Acceptance:*
  - Can create domains/glossary/tags via API.
  - `GET assets/` returns all schema assets with editable catalog metadata.
  - Setting owner/description/classification persists and is audited.
  - `search/?q=` matches asset title/name/description and glossary terms.

### 1B. Reference Data Management (`mdm`, RDM tier only)
- **1B.1** Models: `ReferenceSet`, `ReferenceValue` (per design §5.2 Tier A).
- **1B.2** ViewSets/routes: `reference-sets/` CRUD, `reference-values/` CRUD, `reference-sets/{slug}/values/`.
- **1B.3** Wire `DataField.reference_set` → when a field is `type='reference'`, its allowed values can come from a `ReferenceSet`; expose those values to the data-entry API.
- *Acceptance:*
  - Can create a reference set (e.g. "Emission Scopes") with values and steward.
  - A `reference` field bound to a set returns governed values via API.
  - Deactivating a value hides it from new entry but doesn't corrupt existing rows.

### 1C. Data Quality & Profiling (`dq`)
- **1C.1** Models: `FieldProfile`, `TableProfile`, `DQRule`, `DQResult` (per design §5.3).
- **1C.2** Service functions + management commands: `profile_table(table_id)`, `run_dq(table_id)` (synchronous).
- **1C.3** API: `POST dq/profile/`, `POST dq/run/`, `GET dq/profiles/`, `GET/CRUD dq/rules/`, `GET dq/results/`.
- **1C.4** Rule types (red set): `not_null`, `unique`, `allowed_values` (from a `ReferenceSet`), `range`, `regex`.
- **1C.5** Write-back: latest results roll up into `AssetProfile.quality_status` + `quality_score`.
- *Acceptance:*
  - Profiling a table produces completeness/uniqueness/distinct/top-values per field.
  - A `not_null`/`unique`/`allowed_values` rule runs and reports pass/fail + sample failures.
  - Catalog asset reflects the resulting quality status/score.

### 1D. Carbon app wiring
- **1D.1** Migrate emission-factor category/scope lookups to RDM `ReferenceSet`s (governed) — additive; keep existing behavior working.
- **1D.2** Ensure emissions data tables surface as catalog assets with owner + DQ status.
- *Acceptance:*
  - Carbon still calculates emissions unchanged.
  - Emission lookups resolve from reference sets.
  - Emissions tables appear in `catalog/assets/` with a quality status.

**Phase 1 exit criteria (the non-negotiable bar):**
1. Any schema asset is **cataloged** (owned, described, classified, tagged, glossary-linked).
2. Lookups are **governed** via reference data.
3. Every table can be **profiled** and **quality-scored**, and that status shows in the catalog.
4. **Carbon runs on top** of it all, unchanged for end users.
5. All of the above is RBAC-protected, audited, and API-documented.

---

## Phase 2 — Deepen trust  🟡 IMPORTANT (next, not now)

- **2A** MDM golden records: `MasterEntityType`, `MasterRecord`, `SourceRecord`, deterministic matching, merge + `MergeLog`, stewardship review UI/API.
- **2B** Data **lineage**: table/field-level lineage edges; expose `assets/{id}/lineage`.
- **2C** Data **observability**: profile history → freshness/completeness/drift trends per asset.
- **2D** DQ depth: `reference_integrity` rule, scheduled runs (introduce Celery/Redis here), DQ dashboards.
- *Acceptance (high level):* duplicates resolve to golden records; lineage renders; quality trends over time are queryable.

---

## Phase 3 — Collaboration & Pulse integration  🟡 IMPORTANT

- **3A** Stewardship workflows: requests, approvals, glossary approval lifecycle.
- **3B** **Pulse integration**: finalize the read-API contract; service auth; expose catalog + profiles + reference data for Pulse's semantic/agentic layer to consume. (AI stays in Pulse.)
- **3C** Self-service discovery UI (search, data "shopping"/access requests).

---

## Phase 4 — Platform / multi-app  ⚪ LATER

- **4A** Factor Carbon into a formal hosted "app" with a plugin/SDK contract.
- **4B** Onboard a second app on the same core to prove the model.
- **4C** Revisit infra (managed Postgres/Storage) only if ops demands it.

---

## Sequencing summary

```
Phase 0  🔴  scaffolding + seams            (blocks everything)
Phase 1  🔴  Catalog → RDM → DQ → Carbon    (the MVP bar)
Phase 2  🟡  MDM · lineage · observability · DQ depth
Phase 3  🟡  workflows · Pulse contract · self-service
Phase 4  ⚪  platform/app SDK · 2nd app · infra
```

**Do now:** Phase 0 + Phase 1 only. Everything else waits for explicit go.

---

## Definition of Done (per task, for the executor)
- Models + migrations (additive) applied; `manage.py check` clean.
- DRF serializers + ViewSets + routes; `ScopedRole`-protected; `drf_yasg` shows them.
- Writes audited where the design says so.
- Acceptance criteria demonstrably pass (curl/pytest evidence).
- No import from `emissions` into core apps; no tenant; no AI/LLM.
- Frontend untouched unless the task explicitly says otherwise.
