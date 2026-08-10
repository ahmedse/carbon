# Design — Data Trust Core (with Carbon as the first hosted app)

> **Type:** Architecture & design specification (the *what* and *why*).
> **Audience:** The implementing worker(s). This doc is authoritative; the phased plan in
> [PLAN_DATA_TRUST_PHASES.md](PLAN_DATA_TRUST_PHASES.md) says *when* and *in what order* to build it.
> **Status:** Approved direction. Do not implement beyond what the phase plan authorizes.

---

## 1. Purpose & scope

Turn the existing Carbon backend into a lightweight **Data Trust Core** — a governed, metadata-driven
data layer — and run **Carbon as the first application hosted on top of it**.

**In scope (this core):** Catalog & Governance, Reference/Master Data (RDM/MDM), Data Quality & Profiling,
and the seams that let apps (Carbon) and external systems (**Pulse**) sit on top.

**Out of scope (explicitly):**
- AI / semantic / agentic / RAG / LLM — **owned by Pulse** (separate system, integrates via API). The
  in-repo `ai_copilot` app is **superseded by Pulse** and frozen.
- Supabase / PostgREST / RLS migration — not now (see strategy doc).
- Enterprise "deploy-anywhere-at-scale" heaviness — deliberately dropped to stay lighter than Ataccama.

---

## 2. Principles & constraints (non-negotiable)

1. **Trust is the product** — data must be *governed, quality-checked, cataloged, and explainable*.
2. **Metadata-driven first** — new capability is described *as metadata* over the existing engine, not hard-coded.
3. **Lighter than Ataccama** — one Django + Postgres core; no service sprawl.
4. **Carbon is an app, not the platform** — platform code and Carbon domain code must be *separable*.
5. **Pulse is a peer system** — the core exposes clean read APIs that Pulse (and future apps) consume.
6. **Strangler, never big-bang** — build alongside the working system; do not rewrite the moat.
7. **RBAC everywhere** — every new resource is protected by the existing `ScopedRole` model.

---

## 3. Current foundation (what already exists)

| App | Key models | Role in the target |
|---|---|---|
| `accounts` | `User`, `ScopedRole`, `RoleAssignmentAuditLog`, `Group` | Governance/RBAC substrate. Stewardship & ownership build on this. |
| `core` | `OrgUnit`, `Module` | Organizational scope for assets. [^1] |
| `dataschema` | `DataTable`, `DataField` (typed, `reference_table` FK, `validation` JSON), `DataRow` (JSON `values`), `SchemaChangeLog` | **The metadata-driven engine.** The catalog/DQ/MDM layers annotate and observe these. |
| `emissions` | `EmissionFactor`, `GWP`, `Calculation`, `ReportingPeriod`, `CalculationRule` | **Becomes the Carbon app** — consumer of trusted data. |
| `ai_copilot` | — | **Frozen. Superseded by Pulse.** |

[^1]: Note: Project model was replaced by OrgUnit in Phase 1 (see RUN A0 results)

Key facts to build on:
- `DataField.type` already includes `reference` + `reference_table` FK → the hook for **Reference Data**.
- `DataField.validation` (JSON) + `required` → the hook for **DQ rules**.
- `DataRow.values` (JSON, field-keyed) → the substrate for **profiling**.
- `SchemaChangeLog` → the pattern for audit; reuse it for catalog/governance events.

---

## 4. Target architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │  Hosted apps & peer systems                                    │
        │   Carbon app (emissions)   ·   Pulse (AI/semantic, external)   │
        └───────────────▲───────────────────────────▲───────────────────┘
                        │ consume trusted data + metadata (REST)
        ┌───────────────┴───────────────────────────────────────────────┐
        │  DATA TRUST CORE (new)                                          │
        │   catalog/  ·  mdm/  ·  dq/                                     │
        │   Catalog & Glossary · Reference/Master Data · Profiling & DQ   │
        └───────────────▲───────────────────────────────────────────────┘
                        │ annotates / observes
        ┌───────────────┴───────────────────────────────────────────────┐
        │  dataschema engine  (DataTable / DataField / DataRow)          │
        │  accounts (RBAC) · core (OrgUnit/Module)                       │
        │  Django + DRF · PostgreSQL · Redis                             │
        └────────────────────────────────────────────────────────────────┘
```

New Django apps: **`catalog`**, **`mdm`**, **`dq`**. Carbon domain code stays in `emissions` (later renamed/factored as the "Carbon app").

---

## 5. Component design

### 5.1 `catalog` — Catalog & Governance

Purpose: make every data asset *findable, described, owned, classified, and trust-scored*.

**Models**
- `DataDomain` — business domain grouping (e.g. Energy, Transport, Emissions).
  `name`, `slug`, `description`, `parent` (self-FK, optional), `owner` (User).
- `GlossaryTerm` — business glossary.
  `term`, `slug`, `definition`, `domain` (FK), `synonyms` (JSON), `steward` (User), `status` (draft/approved/deprecated).
- `Tag` — free classification. `name`, `slug`, `color`.
- `AssetProfile` — catalog metadata attached to a schema asset (generic to table *or* field).
  `content_type`+`object_id` (GenericFK to `DataTable`/`DataField`) **or** two nullable FKs
  (`data_table`, `data_field`) — implementer picks one, document it.
  Fields: `description`, `domain` (FK), `owner` (User), `steward` (User),
  `classification` (public/internal/confidential/pii/sensitive),
  `semantic_type` (free text, e.g. "email", "emission_factor"),
  `glossary_term` (FK, optional), `tags` (M2M Tag),
  `quality_status` (unknown/passing/warning/failing — *denormalized from `dq`*),
  `quality_score` (0–100, nullable), timestamps + `updated_by`.
- `GovernanceEvent` — audit for catalog/governance changes (mirror `SchemaChangeLog` shape).

**API** (`/carbon-api/catalog/…`, all `ScopedRole`-protected)
- `GET/POST/PUT/DELETE domains/`, `glossary/`, `tags/`
- `GET/PUT assets/` — list/search assets with their catalog metadata; filter by domain, owner, classification, quality_status, tag, `project_id`/`module_id`.
- `GET assets/{id}/` — full asset detail (schema + catalog + latest DQ snapshot).
- `GET search/?q=` — keyword search across assets + glossary (semantic search is **Pulse's** job later).

**RBAC:** stewards/owners set via `admins_group`/data-owner roles. Read open to any project role.

### 5.2 `mdm` — Reference & Master Data

Split into two tiers; **RDM is the non-negotiable slice**, MDM golden records come later.

**Tier A — Reference Data Management (RDM)** *(build first)*
- `ReferenceSet` — a governed code list. `name`, `slug`, `description`, `domain` (FK), `steward` (User), `is_active`, `version`.
- `ReferenceValue` — `reference_set` (FK), `code`, `label`, `description`, `is_active`, `sort_order`, `valid_from`/`valid_to` (optional), `metadata` (JSON).
- Integration: `DataField.type == 'reference'` may point at a `ReferenceSet` (via a new nullable
  `reference_set` FK on `DataField`, additive) so dropdowns/lookups are governed centrally.

**Tier B — Master Data Management (MDM)** *(later phase)*
- `MasterEntityType` — e.g. "Vehicle", "Facility", "Supplier". `name`, `slug`, `domain`, `match_rules` (JSON).
- `MasterRecord` — the golden record. `entity_type` (FK), `attributes` (JSON), `status` (active/merged/archived), `survivorship` (JSON), steward.
- `SourceRecord` — a contributing record. `entity_type`, `source` (str), `external_id`, `attributes` (JSON), `master` (FK nullable).
- `MatchRun` / `MergeLog` — matching + merge audit.

**API** (`/carbon-api/mdm/…`)
- RDM: `reference-sets/`, `reference-values/` full CRUD + `GET reference-sets/{slug}/values/`.
- MDM (later): `entity-types/`, `master-records/`, `master-records/{id}/candidates/`, `merge/`.

### 5.3 `dq` — Data Quality & Profiling

Purpose: produce the *trust signal* surfaced in the catalog.

**Models**
- `FieldProfile` — snapshot per `DataField`. `data_field` (FK), `row_count`, `null_count`,
  `distinct_count`, `completeness_pct`, `uniqueness_pct`, `min`, `max`, `mean` (nullable),
  `top_values` (JSON), `pattern_summary` (JSON), `profiled_at`.
- `TableProfile` — rollup per `DataTable`. `data_table`, `row_count`, `completeness_pct`, `profiled_at`.
- `DQRule` — `scope` (table|field), `data_table`/`data_field` (FK), `rule_type`
  (not_null | unique | allowed_values | range | regex | reference_integrity | threshold | nl_check),
  `params` (JSON), `severity` (info|warn|error), `is_active`.
  Note: Carbon pushes tasks to Pulse (see PULSE_CONTRACT_SPEC v2.0).
- `DQResult` — `rule` (FK), `run_at`, `passed` (bool), `failed_count`, `sample_failures` (JSON), `score` (0–100).
- Rollup: latest results → `AssetProfile.quality_status` / `quality_score` (denormalized write-back).

**Execution**
- Profiling & rule runs are **synchronous management commands / service functions first**
  (`profile_table`, `run_dq`), invokable via API `POST dq/profile/` and `POST dq/run/`.
- Async (Celery/Redis) deferred — Redis already present; do **not** wire it in Phase 1.

**API** (`/carbon-api/dq/…`)
- `GET profiles/?data_table=…`, `POST profile/` (trigger), `GET rules/` CRUD, `POST run/`, `GET results/`.

### 5.4 Carbon app on top

- `emissions` stays the domain app; it **consumes** the core:
  - Emission-factor category/scope lookups → migrate to **RDM `ReferenceSet`s** (governed).
  - Emission data tables → appear as **catalog assets** with owners + DQ status.
  - No emissions business logic moves into the core; the core stays domain-agnostic.
- Full platform/app *code* separation (SDK, plugin contract) is a **later phase** — for now, just keep
  the dependency direction one-way: `emissions → core`, never `core → emissions`.

---

## 6. Cross-cutting concerns

- **RBAC:** every new ViewSet uses `HasScopedRole` with `required_role`; reads allowed for any project role, writes for `admins_group`/data-owner/steward. No new tenant concept — tenant is gone for good.
- **Audit:** reuse the `SchemaChangeLog` pattern (`before`/`after` JSON) via `GovernanceEvent` and `MergeLog`.
- **API conventions:** all under `/carbon-api/`, DRF ViewSets, `project_id`/`module_id` query scoping, pagination, `drf_yasg` documented.
- **Pulse integration contract:** the core exposes **read** endpoints (`catalog/assets`, `catalog/search`, `dq/profiles`, `mdm/reference-sets`) that Pulse consumes. The core never calls Pulse; Pulse pulls. Auth via service token/JWT. (Contract detail finalized when Pulse integration phase starts.)
- **Domain-agnostic core:** `catalog`/`mdm`/`dq` must not import from `emissions`.

---

## 7. Data-model summary (new)

```
catalog:  DataDomain, GlossaryTerm, Tag, AssetProfile(→DataTable/DataField), GovernanceEvent
mdm:      ReferenceSet, ReferenceValue            (RDM — first)
          MasterEntityType, MasterRecord, SourceRecord, MatchRun, MergeLog  (MDM — later)
dq:       FieldProfile, TableProfile, DQRule, DQResult
schema:   DataField += reference_set (nullable FK)  ·  += (optional) catalog hooks
```

---

## 8. Non-goals / deferred (record so nobody builds them early)

- Vector search / embeddings / RAG / LLM / agents → **Pulse**.
- Async DQ pipelines (Celery), streaming, observability dashboards → later phase.
- Golden-record MDM (matching/merge/survivorship) → later phase (RDM first).
- Data lineage graph, marketplace, approval workflows → later phase.
- Platform/app SDK & multi-app hosting → later phase.
- Any infra migration (Supabase, K8s) → out of scope.
