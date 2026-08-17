# Carbon — AI-Driven Data Platform: Master Design
# Single source of truth for platform evolution beyond the current Carbon codebase.
# Updated: 2026-08-17 | Owner: Master Architect
# Audience: Backend Worker, Frontend Worker, QA Validator, DevOps Worker

---

## 0. What This Document Is

This document specifies **three new capabilities** to be added to Carbon, and **one new
domain app** built on top of them. Together they turn Carbon from an emissions-accounting
platform into a general **AI-Driven Data Platform**:

| New layer | Django app | Purpose |
|---|---|---|
| Dataset Hub | `datahub/` | Versioned, governed, contracted datasets — the trust anchor for all AI |
| TurnKey Bridge | `integrations/turnkey/` | Bidirectional link to the TurnKey ML serving tier |
| App Registry | `appregistry/` | Domain-app manifest, activation, and CBAC scoping |
| First domain app | `healthy/` | Healthy Foods Factory — 5 AI pipelines on ERP data |

Carbon's existing platform core (accounts, catalog, mdm, dq, dataschema, connections,
evidence, importexport, AI/CarbonIntelligence, emissions) is **not touched** except where
explicitly noted.

---

## 1. Platform Vision (3 sentences)

Carbon is the **single trusted source for enterprise data and AI**. Every piece of data
on the platform is governed, quality-scored, and auditable. Every AI prediction is traced
back to the dataset version it was trained on, and every outcome feeds back to improve both
the data quality rules and the model.

---

## 2. Three-System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Carbon (this repo) — Data Trust Core + AI + Domain Apps                      │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  Domain Apps  (may use core; core NEVER imports domain)                 │  │
│  │  emissions/   healthy/   (future: energy_forecast/, supply_chain/, …)   │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  New Platform Layers (this spec)                                        │  │
│  │  datahub/              integrations/turnkey/    appregistry/            │  │
│  │  Dataset versioning    Push artifacts           App manifests            │  │
│  │  Health scoring        Receive predictions      Activation + CBAC        │  │
│  │  Data contracts        Drift ↔ DQ link          Capability extension     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  Existing Platform Core (do not modify except where this doc says to)   │  │
│  │  accounts  catalog   mdm    dq    dataschema  connections                │  │
│  │  evidence  importexport  ai/  emissions  core                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
                              │ HTTP (async client)
                              ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  TurnKey (separate repo/service) — ML Serving Tier                            │
│  registry/  inference/  monitoring/  A-B testing  drift alerts  projects       │
│  API keys   model versions   predictions   SHAP   accuracy snapshots           │
└────────────────────────────────────────────────────────────────────────────────┘
                              │ Azure PostgreSQL (read-only connection via DataSource)
                              ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  Healthy ERP  (external, read-only)                                           │
│  healthy_legacy_2026 on Azure PostgreSQL                                       │
│  readable.* views — 1,047 decoded views over the legacy Arabic ERP            │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. What Is Already Done — Do Not Re-Implement

- **Platform core**: accounts (CBAC/ScopedRole), catalog (metadata, glossary, lineage),
  mdm (OrgUnit, ReferenceSet/Value), dq (engine, gate, jobs — 249 tests), dataschema
  (DataTable/DataField/DataRow), connections (DataSource, ConsumingConnection),
  evidence (file attachments for DataRows), importexport ✅
- **Emissions domain app**: full GHG Protocol stack ✅
- **AI system**: CarbonIntelligence, GuardChain (5 guards), six-witness pipeline, KG,
  memory tiers, 10 task types, 18 cognition tasks ✅
- **AI workspace**: conversation CRUD, message API, SSE, frontend shell ✅
- **QA**: 1,191 tests passing ✅
- **CBAC system**: `capabilities.py` — all capabilities declared there; `has_capability()`
  used in permission classes. Adding new capabilities = add to that file only. ✅

---

## 4. CBAC Extension Contract

Carbon's access control is Capability-Based (CBAC). The authority file is:
`backend/accounts/capabilities.py`. The scope anchor is `ScopedRole(user, group,
org_unit, module)`.

### 4.1 The scope anchor for datasets and apps

`Dataset` and `AppManifest` both carry a `module` FK (type `core.Module`). This means
the **existing ScopedRole module-level scoping already applies** to them with no model
changes. A user with `data-steward` role in `module=sales` can access all Datasets
whose `module=sales`. This is the primary access control mechanism.

No new ScopedRole FK is needed. The mapping is:

```
Dataset.module  →  existing ScopedRole(module=...)  →  Group permissions
AppManifest     →  AppActivation (boolean per app)  +  ScopedRole(module=...)
```

### 4.2 New capabilities to add to `capabilities.py`

Add the following to the `CAPABILITY_REGISTRY` in `accounts/capabilities.py`.
Follow the exact `Capability(...)` dataclass pattern that already exists in that file.

```python
# ── Dataset Hub capabilities ───────────────────────────────────────
DATAHUB_VIEW = Capability(
    key="datahub:view",
    domain="datahub",
    action="view",
    label="View Datasets",
    description="Browse dataset catalog, versions, health scores, contracts",
    category="data",
)
DATAHUB_INGEST = Capability(
    key="datahub:ingest",
    domain="datahub",
    action="ingest",
    label="Ingest Data",
    description="Upload files, trigger ERP snapshots, create dataset versions",
    category="data",
)
DATAHUB_APPROVE = Capability(
    key="datahub:approve",
    domain="datahub",
    action="approve",
    label="Approve Dataset Versions",
    description="Approve or reject a dataset version after DQ review",
    category="data",
)
DATAHUB_MANAGE = Capability(
    key="datahub:manage",
    domain="datahub",
    action="manage",
    label="Manage Datasets",
    description="Create/edit/archive datasets and their contracts",
    category="admin",
)

# ── TurnKey Bridge capabilities ────────────────────────────────────
TURNKEY_VIEW = Capability(
    key="turnkey:view",
    domain="turnkey",
    action="view",
    label="View TurnKey Links",
    description="View model links, prediction records, accuracy metrics",
    category="data",
)
TURNKEY_MANAGE = Capability(
    key="turnkey:manage",
    domain="turnkey",
    action="manage",
    label="Manage TurnKey Integration",
    description="Register/promote models, configure TurnKey connection",
    category="admin",
)

# ── App Registry capabilities ──────────────────────────────────────
APPREGISTRY_VIEW = Capability(
    key="appregistry:view",
    domain="appregistry",
    action="view",
    label="View App Registry",
    description="See available domain apps and their status",
    category="platform",
)
APPREGISTRY_MANAGE = Capability(
    key="appregistry:manage",
    domain="appregistry",
    action="manage",
    label="Manage App Registry",
    description="Activate/deactivate domain apps, edit manifests",
    category="platform",
)

# ── Healthy domain app capabilities ───────────────────────────────
HEALTHY_VIEW = Capability(
    key="healthy:view",
    domain="healthy",
    action="view",
    label="View Healthy App",
    description="View dashboards, forecasts, predictions in the Healthy app",
    category="data",
)
HEALTHY_MANAGE = Capability(
    key="healthy:manage",
    domain="healthy",
    action="manage",
    label="Manage Healthy App",
    description="Trigger ERP snapshots, run pipelines, manage model configs",
    category="admin",
)
```

Add group mappings in `GROUP_CAPABILITIES` for existing groups:
- `platform-admin` → add all new capabilities
- `data-steward` → `DATAHUB_VIEW`, `DATAHUB_INGEST`, `DATAHUB_APPROVE`, `TURNKEY_VIEW`,
  `APPREGISTRY_VIEW`, `HEALTHY_VIEW`
- `data-analyst` → `DATAHUB_VIEW`, `TURNKEY_VIEW`, `HEALTHY_VIEW`
- `data-entry` → `DATAHUB_VIEW`, `HEALTHY_VIEW`

### 4.3 DatasetAccessPolicy (optional per-dataset override)

For cases where the module-level scoping is not fine-grained enough (e.g. a user
can view the `sales` module but must NOT see the `customer_aging` dataset due to
sensitivity), add an explicit override model:

```python
# datahub/models.py
class DatasetAccessPolicy(models.Model):
    """Per-dataset access override. Takes precedence over module-level ScopedRole."""
    dataset = models.ForeignKey('Dataset', on_delete=models.CASCADE,
                                related_name='access_policies')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    # exactly one of user/group must be set (enforce in clean())
    can_view = models.BooleanField(default=True)
    can_ingest = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='granted_dataset_policies')
    granted_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
```

Resolution order: explicit `DatasetAccessPolicy` > ScopedRole module-level > deny.

---

## 5. Phase 1 — Dataset Hub (`datahub/`)

### 5.1 Purpose

The Dataset Hub is the **governed data product layer**. It sits between raw data
sources (ERP, CSV uploads, database connections) and the AI/ML pipelines (TurnKey,
domain app workflows). A Dataset is the unit of trust: before data flows to a model
or an app, it must have an approved DatasetVersion with a passing DQ run.

### 5.2 Dependency graph

```
datahub/
  imports:  dataschema (DataTable, DataField, DataRow)
            catalog    (DataDomain, AssetProfile, Tag)
            dq         (DQJob, DQResult)
            connections (DataSource)
            mdm        (OrgUnit)
            core       (Module)
            accounts   (User)
  imported by:  integrations/turnkey/   healthy/   appregistry/
```

`datahub/` MUST NOT import from `emissions/` or `healthy/` (domain isolation rule).

### 5.3 Models

File: `backend/datahub/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from dataschema.models import DataTable
from catalog.models import DataDomain
from catalog.models import CLASSIFICATION_CHOICES
from connections.models import DataSource
from core.models import Module
import uuid

User = get_user_model()

LIFECYCLE_STATES = [
    ('draft',       'Draft'),
    ('active',      'Active'),
    ('deprecated',  'Deprecated'),
    ('archived',    'Archived'),
]

VERSION_STATUSES = [
    ('pending',   'Pending DQ Review'),
    ('approved',  'Approved'),
    ('rejected',  'Rejected'),
]


class Dataset(models.Model):
    """Governed, versioned semantic data product.

    A Dataset is a named collection of data (backed by a DataTable in dataschema)
    with full governance: domain, classification, owner, module scope (CBAC anchor),
    lifecycle state, and a current approved version pointer.

    The 'module' FK is the primary CBAC scope anchor. ScopedRole(module=X) controls
    access to all Datasets with module=X.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    domain = models.ForeignKey(
        DataDomain, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='datasets',
    )
    module = models.ForeignKey(
        Module, on_delete=models.PROTECT, related_name='datasets',
        help_text='CBAC scope anchor — controls which ScopedRole grants access.',
    )
    classification = models.CharField(
        max_length=20, choices=CLASSIFICATION_CHOICES, default='internal',
    )
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_datasets',
    )
    source = models.ForeignKey(
        DataSource, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='datasets',
        help_text='Origin connection (ERP, CSV, API). Null = manually entered.',
    )
    # pointer to the latest approved version — updated automatically on approval
    current_version = models.OneToOneField(
        'DatasetVersion', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='current_for_dataset',
    )
    status = models.CharField(max_length=20, choices=LIFECYCLE_STATES, default='draft')
    tags = models.ManyToManyField('catalog.Tag', blank=True, related_name='datasets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_datasets',
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class DatasetVersion(models.Model):
    """Immutable snapshot of a Dataset at a point in time.

    Once status='approved', the version is frozen. New data = new version.
    The data itself lives in dataschema.DataTable/DataRow (existing storage).
    This model is governance metadata only.

    Lineage stored as: {"source": {"type": "erp_snapshot"/"csv_upload"/"api",
    "ref": "<id or filename>"}, "upstream_version_ids": ["<uuid>", ...],
    "transforms": [{"name": "...", "params": {...}}]}
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()  # auto-incremented per dataset
    # The actual storage: rows live in dataschema.DataRow linked to this DataTable
    data_table = models.ForeignKey(
        DataTable, on_delete=models.PROTECT, related_name='dataset_versions',
        help_text='The DataTable holding the rows for this version.',
    )
    row_count = models.BigIntegerField(null=True, blank=True)
    # Schema at version creation time: {field_name: {type, required, ...}}
    schema_snapshot = models.JSONField(default=dict)
    # Health: 0.0-1.0 composite, and per-dimension breakdown
    health_score = models.FloatField(null=True, blank=True)
    health_detail = models.JSONField(
        default=dict,
        help_text='{"completeness": 0.98, "validity": 0.95, "freshness": 1.0}',
    )
    # DQ link: which DQ job produced this health score
    dq_job_id = models.CharField(max_length=200, blank=True)
    # Provenance
    lineage = models.JSONField(default=dict)
    # Approval
    status = models.CharField(max_length=20, choices=VERSION_STATUSES, default='pending')
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_dataset_versions',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_dataset_versions',
    )

    class Meta:
        unique_together = ('dataset', 'version_number')
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.dataset.name} v{self.version_number} ({self.status})"


class DataContract(models.Model):
    """Formal promise on a Dataset — what downstream apps depend on.

    A contract is a binding SLA. If any version violates it, a
    DataContractViolation is created and the dataset status may be
    auto-set to 'warning'. Apps should check contract.is_satisfied()
    before ingesting a new version.
    """
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE,
                                   related_name='contract')
    # Schema promise: list of required field names
    required_fields = models.JSONField(
        default=list,
        help_text='Field names that must always be present.',
    )
    # Quality SLAs: minimum acceptable scores per dimension
    min_completeness = models.FloatField(null=True, blank=True)  # e.g. 0.95
    min_validity = models.FloatField(null=True, blank=True)
    min_health_score = models.FloatField(null=True, blank=True)  # overall
    # Freshness SLA: maximum acceptable age in hours
    freshness_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='If set, a version older than this many hours triggers a freshness violation.',
    )
    # Downstream apps that depend on this contract (informational)
    consumer_apps = models.JSONField(
        default=list,
        help_text='App slugs (from AppManifest) that consume this dataset.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Contract for {self.dataset.name}"


class DataContractViolation(models.Model):
    """Recorded when a DataContract check fails for a DatasetVersion."""
    VIOLATION_TYPES = [
        ('schema',     'Schema — missing required field'),
        ('quality',    'Quality — score below minimum SLA'),
        ('freshness',  'Freshness — version too old'),
    ]
    contract = models.ForeignKey(DataContract, on_delete=models.CASCADE,
                                 related_name='violations')
    dataset_version = models.ForeignKey(DatasetVersion, on_delete=models.CASCADE,
                                        related_name='contract_violations')
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    detail = models.JSONField(default=dict)  # {field, expected, actual} etc.
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ['-detected_at']


class DatasetAccessPolicy(models.Model):
    """Per-dataset access override. Takes precedence over module-level ScopedRole.

    Exactly one of user/group must be non-null (enforced in clean()).
    """
    from django.contrib.auth.models import Group
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE,
                                related_name='access_policies')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE,
                             related_name='dataset_policies')
    group = models.ForeignKey(
        'auth.Group', null=True, blank=True, on_delete=models.CASCADE,
        related_name='dataset_policies',
    )
    can_view = models.BooleanField(default=True)
    can_ingest = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='granted_dataset_policies')
    granted_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def clean(self):
        if (self.user is None) == (self.group is None):
            raise ValidationError('Exactly one of user or group must be set.')
```

### 5.4 API Surface

All endpoints under `/api/v1/datahub/`. Auth: same JWT/session as rest of platform.
Permission class: `HasCBACCapability` (same pattern as existing DQ/catalog endpoints).

| Method | Path | Capability | Description |
|--------|------|-----------|-------------|
| GET | `/datasets/` | `datahub:view` | List datasets (filtered by module/domain/status) |
| POST | `/datasets/` | `datahub:manage` | Create dataset |
| GET | `/datasets/{id}/` | `datahub:view` | Dataset detail |
| PATCH | `/datasets/{id}/` | `datahub:manage` | Update metadata |
| DELETE | `/datasets/{id}/` | `datahub:manage` | Archive (soft) |
| GET | `/datasets/{id}/versions/` | `datahub:view` | List versions newest-first |
| POST | `/datasets/{id}/versions/` | `datahub:ingest` | Create new version (triggers DQ) |
| GET | `/datasets/{id}/versions/{vid}/` | `datahub:view` | Version detail + health |
| POST | `/datasets/{id}/versions/{vid}/approve/` | `datahub:approve` | Approve + set as current |
| POST | `/datasets/{id}/versions/{vid}/reject/` | `datahub:approve` | Reject + reason |
| GET | `/datasets/{id}/contract/` | `datahub:view` | Get contract |
| PUT | `/datasets/{id}/contract/` | `datahub:manage` | Create/replace contract |
| GET | `/datasets/{id}/contract/violations/` | `datahub:view` | List violations |
| POST | `/datasets/{id}/ingest/erp/` | `datahub:ingest` | Trigger ERP snapshot ingest |
| POST | `/datasets/{id}/ingest/upload/` | `datahub:ingest` | Upload CSV/Excel |

### 5.5 Ingest Service

File: `backend/datahub/ingest.py`

Responsibilities:
1. Given a Dataset + ingest config, pull rows from the DataSource (ERP view or file).
2. Write rows into a new DataTable + DataRows (using existing dataschema layer).
3. Capture `schema_snapshot` from the DataTable's DataFields at write time.
4. Compute `health_detail`:
   - `completeness` = 1 - (null_count / total_cells)
   - `validity` = DQ gate pass rate (call existing `dq/gate.py` evaluate)
   - `freshness` = 1.0 if latest row timestamp ≤ freshness_hours, else 0.0
5. Create a `DatasetVersion(status='pending')`.
6. If the Dataset has a `DataContract`, run `check_contract(version)` — create
   `DataContractViolation` records for each breach.
7. If all contract checks pass AND auto-approve is enabled, set `status='approved'`
   and update `dataset.current_version`.
8. If manual approval required, leave `status='pending'` and notify the dataset owner.

### 5.6 Health Score Computation

```
health_score = (
    weight_completeness * completeness +
    weight_validity     * validity     +
    weight_freshness    * freshness
)
weights: completeness=0.4, validity=0.4, freshness=0.2
```

Store `health_score` and `health_detail` on `DatasetVersion`. Mirror to
`catalog.AssetProfile.quality_status` (passing ≥ 0.9, warning ≥ 0.7, failing < 0.7).

### 5.7 DQ Integration

The Dataset Hub does NOT duplicate DQ logic. It calls existing `dq/` infrastructure:
- On version creation: run the DataTable's existing DQ rules via `dq/jobs.py`
  `run_rule_job(data_table_id, user)`.
- The resulting `DQJob.id` is stored in `DatasetVersion.dq_job_id`.
- When the DQ job completes, a signal updates `health_detail.validity`.

### 5.8 Tests (required gates)

File: `backend/datahub/tests/`

| Test | Assert |
|------|--------|
| `test_create_dataset` | creates with module scope; unapproved user gets 403 |
| `test_version_lifecycle` | pending → approved sets `current_version`; rejected does not |
| `test_contract_schema_violation` | missing required field → violation created |
| `test_contract_quality_violation` | health below min_completeness → violation created |
| `test_contract_freshness_violation` | version older than freshness_hours → violation |
| `test_cbac_module_isolation` | user in module A cannot see datasets in module B |
| `test_access_policy_override` | explicit DatasetAccessPolicy overrides module ScopedRole |
| `test_ingest_erp_snapshot` | ERP snapshot → DataTable rows → version → health score |
| `test_ingest_csv_upload` | CSV upload → same pipeline |

Minimum: 20 tests. All must pass before Phase 2 begins.

---

## 6. Phase 2 — TurnKey Bridge (`integrations/turnkey/`)

### 6.1 Purpose

The TurnKey Bridge is the bidirectional connector between Carbon's trusted data and
TurnKey's ML serving tier. It enables:

- **Outbound**: push a trained artifact from a Carbon workflow to TurnKey, register
  the model, and promote it.
- **Inbound**: receive prediction results and drift alerts from TurnKey, store
  predictions as evidence on DataRows, and trigger DQ jobs when drift is detected.

The bridge is HTTP-based (TurnKey's public API). No shared database. No direct import.

### 6.2 Reference implementation

Gigacast already has `backend/aihub/turnkey_client.py` — a clean, Django-free
HTTP client. The Carbon bridge follows the same interface. Copy, do not invent.

### 6.3 Models

File: `backend/integrations/turnkey/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet
from django.conf import settings
import uuid

User = get_user_model()


class TurnKeyConfig(models.Model):
    """Connection config for a TurnKey deployment. One per platform (usually).

    api_key_encrypted: Fernet-encrypted TurnKey API key.
    Never store the plaintext key. Provide .get_api_key()/.set_api_key() helpers.
    """
    name = models.CharField(max_length=120, unique=True)
    base_url = models.CharField(max_length=500)
    api_key_encrypted = models.TextField(blank=True)  # Fernet b64 ciphertext
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL)

    def get_api_key(self) -> str:
        f = Fernet(settings.FERNET_KEY.encode())
        return f.decrypt(self.api_key_encrypted.encode()).decode()

    def set_api_key(self, plaintext: str):
        f = Fernet(settings.FERNET_KEY.encode())
        self.api_key_encrypted = f.encrypt(plaintext.encode()).decode()

    def __str__(self):
        return self.name


class TurnKeyModelLink(models.Model):
    """Links a Carbon DatasetVersion to a TurnKey registered model+version.

    This is the provenance record: model X in TurnKey was trained on
    DatasetVersion Y in Carbon (approved, health_score Z).

    purpose='training': the version was the training dataset for this model.
    purpose='inference': the version is the reference schema for live predictions.
    """
    PURPOSE_CHOICES = [
        ('training',   'Training dataset'),
        ('inference',  'Inference input schema'),
    ]
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('registered', 'Registered in TurnKey'),
        ('promoted',   'Promoted to production'),
        ('failed',     'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset_version = models.ForeignKey(
        'datahub.DatasetVersion', on_delete=models.PROTECT,
        related_name='turnkey_links',
    )
    turnkey_config = models.ForeignKey(TurnKeyConfig, on_delete=models.PROTECT)
    turnkey_model_id = models.CharField(max_length=200)
    turnkey_model_name = models.CharField(max_length=200, blank=True)
    turnkey_version_id = models.CharField(max_length=200, blank=True)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    linked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (f"{self.dataset_version.dataset.name} v{self.dataset_version.version_number}"
                f" → TurnKey:{self.turnkey_model_name}")


class PredictionRecord(models.Model):
    """A prediction received back from TurnKey, stored for provenance and DQ feedback.

    input_ref: reference to the DataRow that was the prediction input (if traceable).
    actual: the real outcome when known (feedback loop — enables accuracy monitoring).
    When actual is set, the health of the linked DatasetVersion can be re-evaluated.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_link = models.ForeignKey(TurnKeyModelLink, on_delete=models.CASCADE,
                                   related_name='predictions')
    # Source data row (optional — not always traceable)
    input_data_row = models.ForeignKey(
        'dataschema.DataRow', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='predictions',
    )
    input_hash = models.CharField(max_length=64, blank=True)  # SHA-256 of input JSON
    prediction = models.JSONField()
    actual = models.JSONField(null=True, blank=True)
    feedback_submitted_at = models.DateTimeField(null=True, blank=True)
    feedback_by = models.ForeignKey(User, null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='submitted_feedback')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class DriftAlert(models.Model):
    """Drift alert received from TurnKey. Triggers a DQ re-evaluation."""
    SEVERITY_CHOICES = [('low','Low'),('medium','Medium'),('high','High')]
    model_link = models.ForeignKey(TurnKeyModelLink, on_delete=models.CASCADE,
                                   related_name='drift_alerts')
    turnkey_alert_id = models.CharField(max_length=200, unique=True)
    metric = models.CharField(max_length=50)   # e.g. "mape", "rmse"
    value = models.FloatField()
    threshold = models.FloatField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    # After receiving a drift alert: mark linked dataset version health as degraded
    dq_job_triggered = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, null=True, blank=True,
                                        on_delete=models.SET_NULL)
```

### 6.4 HTTP Client

File: `backend/integrations/turnkey/client.py`

Based on Gigacast's `aihub/turnkey_client.py`. Django-free, testable standalone.

```python
class CarbonTurnKeyClient:
    """HTTP client for Carbon → TurnKey API calls.

    Usage:
        from integrations.turnkey.client import CarbonTurnKeyClient
        from integrations.turnkey.models import TurnKeyConfig

        config = TurnKeyConfig.objects.get(is_active=True)
        client = CarbonTurnKeyClient(config.base_url, config.get_api_key())

        model = client.register_or_get_model("healthy-returns", "lightgbm")
        version_id = client.push_version(
            model["id"],
            artifact_path="/tmp/returns_v2.bentomodel",
            metrics={"mape": 4.2},
            feature_names=["qty_lag_1", ...],
        )
        client.promote_to_production(model["id"], version_id)
    """

    def register_or_get_model(self, name, model_type) -> dict: ...
    def push_version(self, model_id, artifact_path, metrics, feature_names,
                     config=None) -> str: ...
    def promote_to_production(self, model_id, version_id) -> None: ...
    def get_model_metrics(self, model_id) -> dict: ...
    def list_models(self) -> list: ...
```

All methods raise `TurnKeyClientError` on non-2xx. Never swallow errors silently.

### 6.5 Callback Endpoints (inbound from TurnKey)

TurnKey pushes events to Carbon via signed HTTP POST. Carbon exposes:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/integrations/turnkey/callback/predictions/` | Receive prediction result |
| POST | `/api/v1/integrations/turnkey/callback/drift-alerts/` | Receive drift alert |

**Security**: callbacks are signed with a shared HMAC-SHA256 secret
(`TURNKEY_CALLBACK_SECRET` in settings). Validate signature before processing.
Reject with 401 if invalid.

**Prediction callback** creates a `PredictionRecord`. If the input can be traced
to a `DataRow` (via `input_hash` lookup), sets `input_data_row`.

**Drift callback** creates a `DriftAlert`, then:
1. Marks `dataset_version.health_detail.drift_alert = True`.
2. Creates a DQ anomaly job on the linked DataTable (calls `dq/jobs.py`).
3. Creates a `DataContractViolation(violation_type='quality')` if the drift
   metric exceeds the contract's `min_health_score` equivalent threshold.

### 6.6 API for managing links

| Method | Path | Capability | Description |
|--------|------|-----------|-------------|
| GET | `/api/v1/integrations/turnkey/configs/` | `turnkey:manage` | List TurnKey configs |
| POST | `/api/v1/integrations/turnkey/configs/` | `turnkey:manage` | Add config (API key via `set_api_key()`) |
| GET | `/api/v1/integrations/turnkey/links/` | `turnkey:view` | List model links |
| POST | `/api/v1/integrations/turnkey/links/` | `turnkey:manage` | Create link + register model |
| POST | `/api/v1/integrations/turnkey/links/{id}/promote/` | `turnkey:manage` | Promote to production |
| GET | `/api/v1/integrations/turnkey/links/{id}/predictions/` | `turnkey:view` | List predictions for this link |
| POST | `/api/v1/integrations/turnkey/links/{id}/predictions/{pid}/feedback/` | `turnkey:view` | Submit actual outcome |
| GET | `/api/v1/integrations/turnkey/links/{id}/drift-alerts/` | `turnkey:view` | List drift alerts |

### 6.7 Settings

Add to `config/settings.py` (or `.env`):

```
TURNKEY_CALLBACK_SECRET=<random 64-char hex>   # shared with TurnKey deployment
FERNET_KEY=<44-char Fernet key>                # for encrypting TurnKey API keys
```

Generate `FERNET_KEY` with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
Generate `TURNKEY_CALLBACK_SECRET` with: `python -c "import secrets; print(secrets.token_hex(32))"`.

### 6.8 Tests (required gates)

| Test | Assert |
|------|--------|
| `test_callback_signature_required` | unsigned POST → 401 |
| `test_prediction_callback_creates_record` | valid signed POST → PredictionRecord created |
| `test_drift_callback_triggers_dq` | drift alert → DQ job created + contract violation |
| `test_api_key_encrypted_at_rest` | `config.api_key_encrypted != plaintext` |
| `test_feedback_loop` | submit actual → PredictionRecord.actual set → health re-evaluated |
| `test_cbac_turnkey_view_required` | user without `turnkey:view` gets 403 on list |

---

## 7. Phase 3 — App Registry (`appregistry/`)

### 7.1 Purpose

The App Registry is the control plane for domain apps. It declares what apps exist,
what capabilities and modules they need, and whether they are active. It enables the
platform to guard AI calls, CBAC checks, and data access with `"which app is this
request coming from?"` context.

There is no multi-tenancy. One deployment = one organisation. The registry is
therefore simple: a flat list of AppManifests with activation state.

### 7.2 Models

File: `backend/appregistry/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class AppManifest(models.Model):
    """Declarative specification for a domain app.

    An AppManifest is declared once (usually in a data migration or management
    command) by the app itself. It is the contract between the app and the platform.

    required_modules: list of Module.name values this app needs to exist.
    required_capabilities: list of Capability.key values users need to use this app.
    datasets: list of Dataset.slug values this app will access (informational;
              actual access still governed by ScopedRole on dataset.module).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    version = models.CharField(max_length=20)  # semver string e.g. "1.0.0"
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=80, blank=True)  # e.g. "FactoryIcon"
    entry_route = models.CharField(
        max_length=200, blank=True,
        help_text='Frontend React router path e.g. /apps/healthy',
    )
    required_modules = models.JSONField(default=list)
    required_capabilities = models.JSONField(default=list)
    consumed_datasets = models.JSONField(
        default=list,
        help_text='Dataset.slug values this app reads (informational).',
    )
    is_system = models.BooleanField(
        default=False,
        help_text='System apps (emissions) cannot be deactivated.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} v{self.version}"


class AppActivation(models.Model):
    """Records that an AppManifest has been activated in this deployment.

    Deactivating an app hides it from the UI and blocks API access.
    System apps (is_system=True) cannot be deactivated.
    """
    app = models.OneToOneField(AppManifest, on_delete=models.CASCADE,
                               related_name='activation')
    is_active = models.BooleanField(default=True)
    activated_by = models.ForeignKey(User, null=True, blank=True,
                                     on_delete=models.SET_NULL,
                                     related_name='activated_apps')
    activated_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(User, null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='deactivated_apps')

    def __str__(self):
        return f"{self.app.name} — {'active' if self.is_active else 'inactive'}"
```

### 7.3 API Surface

| Method | Path | Capability | Description |
|--------|------|-----------|-------------|
| GET | `/api/v1/apps/` | `appregistry:view` | List all apps with activation state |
| GET | `/api/v1/apps/{slug}/` | `appregistry:view` | App detail + health status |
| POST | `/api/v1/apps/{slug}/activate/` | `appregistry:manage` | Activate app |
| POST | `/api/v1/apps/{slug}/deactivate/` | `appregistry:manage` | Deactivate (non-system only) |

### 7.4 App self-registration

Each domain app registers its manifest at startup via a management command or
data migration. Pattern:

```python
# healthy/management/commands/register_healthy_app.py
from django.core.management.base import BaseCommand
from appregistry.models import AppManifest, AppActivation

class Command(BaseCommand):
    def handle(self, *args, **options):
        manifest, _ = AppManifest.objects.update_or_create(
            slug='healthy',
            defaults={
                'name': 'Healthy Foods Factory',
                'version': '1.0.0',
                'description': 'AI-driven sales and operations intelligence for Healthy ERP',
                'icon': 'LocalDiningIcon',
                'entry_route': '/apps/healthy',
                'required_modules': ['healthy-sales', 'healthy-returns', 'healthy-inventory'],
                'required_capabilities': ['healthy:view'],
                'consumed_datasets': [
                    'healthy-sales-lines', 'healthy-customers', 'healthy-items',
                    'healthy-returns-panel', 'healthy-inventory-positions',
                ],
                'is_system': False,
            },
        )
        AppActivation.objects.get_or_create(app=manifest)
        self.stdout.write(f"Registered: {manifest}")
```

Add to `manage.sh` initial setup commands and to the deployment runbook.

### 7.5 GuardChain integration

`accounts/ai_scoping.py` builds the AI `Scope` before every `CarbonIntelligence` call.
Extend it to include app context:

```python
# In build_scope() / resolve_scope():
active_apps = [
    a.app.slug
    for a in AppActivation.objects.filter(is_active=True)
    if has_capability(user, a.app.required_capabilities[0] if a.app.required_capabilities else None)
]
scope.active_apps = active_apps
```

The `GuardChain` `ScopeGuard` then validates that the AI task type is allowed
for the current active apps (`app.required_capabilities`).

---

## 8. Phase 4 — Healthy Domain App (`healthy/`)

### 8.1 What Is Healthy

**Healthy Foods Factory** is a fresh-food company operating via a legacy Arabic ERP
(Al-Motakamel family, ~70 modules). The ERP database (`healthy_legacy_2026`) lives
on Azure PostgreSQL and exposes 1,047 decoded views in the `readable` schema.

Current AI production state (in TurnKey, `healthy` project):
- `healthy-returns` model (v1, production): DSD returns/load-out demand forecasting.
  18 features, 3 categorical (cust_segment, item_group, rep_code).
  Consumer key: `sk-turnkey-healthy-ehl3i6pm8uKxzkaqv0dx8YWXjmpiPA5idD06VOI9`.
- `healthy-churn` wrapper: ready in TurnKey, model not yet trained.

### 8.2 Data Connection

Carbon will connect to the Healthy ERP using its existing `connections/` module:
a `DataSource(source_type='database')` pointing to the Azure PostgreSQL instance.
Connection config stored encrypted in `DataSource.connection_config`.

The ERP is **read-only**. Carbon never writes to it.

Modules (core.Module) to create for Healthy:

| Module name | Description | CBAC scope |
|---|---|---|
| `healthy-sales` | Sales transactions, customers, items | Sales team + analysts |
| `healthy-returns` | Returns panel, loadout forecasting | Ops + logistics |
| `healthy-inventory` | Stock positions, movements | Warehouse + ops |
| `healthy-collections` | AR aging, customer balances | Finance team |
| `healthy-production` | Work orders, BOM, production cost | Production team |

Each module maps to one or more Datasets. ScopedRole on the module controls access.

### 8.3 Five AI Pipelines

Each pipeline is: **ERP snapshot → Dataset version (with DQ) → TurnKey (train/serve) → PredictionRecord → dashboard**.

---

#### Pipeline 1: Returns / Load-Out Demand (LIVE IN PRODUCTION)

**Status**: Model `healthy-returns` v1 is live in TurnKey. This pipeline is
Carbon's first integration of an existing model.

**Dataset**: `healthy-returns-panel`
- Source: `readable.invoice_lines` + `readable.invoice_headers` (ERP snapshot)
- Schema: `{rep_code, item_code, item_group, cust_segment, week_start, qty_sold,
  qty_returned, return_rate, lag_1w, lag_4w, lag_13w, is_ramadan, is_summer, ...}`
- Health contract: completeness ≥ 0.95, validity ≥ 0.90, freshness_hours = 168 (weekly)
- Module: `healthy-returns`

**Carbon's role for this pipeline**:
1. Weekly ERP snapshot ingest → new DatasetVersion
2. DQ gate: validate rep_code in MDM reference set, check date range, check qty ranges
3. Approve version → `TurnKeyModelLink(purpose='inference')` confirms schema matches live model
4. Prediction results (from TurnKey callback) → `PredictionRecord` linked to rep+item+week DataRow
5. When actuals arrive (following week): submit feedback → accuracy monitoring loop
6. Drift alert from TurnKey → DataContractViolation + DQ anomaly job

**Frontend screen**: Loadout Forecast — table per rep showing item demand predictions
with confidence, actual vs predicted comparison, and trend chart.

---

#### Pipeline 2: Customer Churn / Rep Retention

**Status**: `healthy-churn` model wrapper in TurnKey; training data NOT yet ingested
into Carbon. This pipeline completes the loop.

**Dataset**: `healthy-churn-panel`
- Source: `readable.salesman_performance` + `readable.invoice_headers` (rep-level weekly)
- Schema: `{rep_code, week, active_customers, visit_count, avg_order_value,
  days_since_last_sale, customer_30d_return_rate, churn_label}`
- Health contract: completeness ≥ 0.95, validity ≥ 0.90, freshness_hours = 168
- Module: `healthy-sales`

**Pipeline steps**:
1. Weekly snapshot → DatasetVersion
2. DQ: validate rep codes in MDM, check numeric ranges, check for historical completeness
3. Approve → `TurnKeyModelLink(purpose='training')` + trigger training job in TurnKey
4. Promote trained model
5. Inference: weekly predictions → PredictionRecord (churn probability per rep)
6. Dashboard: rep health cards, at-risk rep alerts, trend over time

---

#### Pipeline 3: Demand Forecast (Dead-Stock / Slow-Mover Detection)

**Status**: Dataset ready (`silver.fct_sales_line` has 948K rows, 2-year history).
Model not yet built. Directly addresses 17–35M EGP dead-stock risk.

**Dataset**: `healthy-sales-lines`
- Source: `readable.invoice_lines` + `readable.items` (ERP snapshot)
- Schema: (item_code, item_group, rep_code, week_start, qty_sold, unit_price, cost_price,
  movement_flag, days_since_last_sale, stock_position, ...)
- Health contract: completeness ≥ 0.95, freshness_hours = 168
- Module: `healthy-inventory`

**Pipeline steps**:
1. Weekly snapshot → DatasetVersion → DQ (flag fast-mover vs slow-mover threshold)
2. Approve → TurnKey training job: LightGBM demand forecaster
3. Predictions: item-level 4-week demand forecast
4. Dashboard: slow-mover heatmap, dead-stock alert table, recommended discount/bundle actions

---

#### Pipeline 4: AR Collections Prioritization

**Status**: Data available remotely (2,294 customers, 365M EGP aged 90+). Must extract.

**Dataset**: `healthy-ar-aging`
- Source: `readable.customer_aging` + `readable.customer_balance` (ERP snapshot)
- Schema: (customer_code, days_overdue, amount_overdue, credit_limit, last_payment_date,
  rep_code, sector, area, payment_reliability_score, ...)
- Health contract: completeness ≥ 0.95, freshness_hours = 48 (twice-weekly)
- Module: `healthy-collections`

**Pipeline steps**:
1. Twice-weekly snapshot → DatasetVersion → DQ (validate amounts, customer codes vs MDM)
2. Approve → TurnKey model: payment probability + days-to-collect regressor
3. Predictions: per-customer risk score
4. Dashboard: collections priority queue, rep assignment, escalation triggers, 30-day forecast

---

#### Pipeline 5: Transaction-Type Classifier (Data Integrity Guard)

**Status**: HIGHEST PRIORITY — this model protects the accuracy of ALL other pipelines
by correctly separating DSD sales from wholesale bulk transfers and credit-note corrections.

**Dataset**: `healthy-transaction-classifier-panel`
- Source: `readable.invoice_lines` (all transaction types, last 2 years)
- Schema: (qty, unit_price, customer_type, item_group, rep_code, doc_date, ...)
- Labels: P(DSD), P(bulk), P(credit-note) — derived from known examples
- Health contract: completeness = 1.0, validity ≥ 0.98 (labels must be clean)
- Module: `healthy-sales`

**Pipeline steps**:
1. One-time dataset creation (labeled sample for training)
2. DQ: validate labels — no row can have >1 label=1 (mutual exclusivity rule)
3. Approve → TurnKey training: LightGBM multi-class classifier
4. Inference: every new transaction line scored at ingest → score stored as DataRow metadata
5. DQ gate: if score < 0.7 for DSD, row flagged for review before flowing to Returns Pipeline

**This pipeline is a DQ guard, not a business dashboard.** Its output enriches every
subsequent dataset with a `transaction_type_confidence` field.

---

### 8.4 Healthy App Models

File: `backend/healthy/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class ERPSnapshot(models.Model):
    """Records each extract from the Healthy ERP database.

    Used for audit and debugging: if a DatasetVersion has wrong data,
    trace back to its ERPSnapshot to find the extraction parameters.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_view = models.CharField(max_length=200)  # e.g. "readable.invoice_lines"
    extract_params = models.JSONField(default=dict)  # date filters, row limit etc.
    row_count = models.BigIntegerField(null=True)
    # FK to the DatasetVersion this snapshot produced
    dataset_version_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('running','Running'),('done','Done'),('failed','Failed')
    ], default='running')
    error_detail = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_by = models.ForeignKey(User, null=True, blank=True,
                                     on_delete=models.SET_NULL)


class LoadoutSheet(models.Model):
    """The operational output artifact for Pipeline 1 (returns forecast).

    A loadout sheet is the per-rep, per-item recommendation for how much
    to load on the van. Generated weekly from TurnKey predictions.
    Replaces the legacy Excel-based van load sheet.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    week_start = models.DateField()
    rep_code = models.CharField(max_length=50)
    rep_name = models.CharField(max_length=200, blank=True)
    prediction_ref = models.UUIDField(null=True, blank=True)  # PredictionRecord.id
    line_items = models.JSONField(default=list)
    # [{item_code, item_name, qty_forecast, qty_actual, return_rate_forecast, ...}]
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, null=True, blank=True,
                                     on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('week_start', 'rep_code')


class RepHealthCard(models.Model):
    """Weekly snapshot of a rep's AI-derived health metrics.

    Produced by Pipeline 2 (churn model). Aggregates churn probability,
    customer retention, AR risk, and visit coverage into one record per rep per week.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    week_start = models.DateField()
    rep_code = models.CharField(max_length=50)
    churn_probability = models.FloatField(null=True)
    active_customer_count = models.IntegerField(null=True)
    visit_coverage = models.FloatField(null=True)  # visits / scheduled
    avg_order_value = models.FloatField(null=True)
    ar_overdue_amount = models.FloatField(null=True)
    prediction_ref = models.UUIDField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('week_start', 'rep_code')
```

### 8.5 API Surface

All under `/api/v1/healthy/`. Capability: `healthy:view` for reads, `healthy:manage`
for write/trigger actions.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/snapshots/` | List ERP snapshots |
| POST | `/snapshots/` | Trigger new ERP snapshot (manage) |
| GET | `/loadout/` | List loadout sheets (week filter) |
| GET | `/loadout/{week}/` | Full loadout for a week (all reps) |
| GET | `/loadout/{week}/{rep}/` | Single rep loadout sheet |
| POST | `/loadout/{week}/{rep}/actuals/` | Submit actual loadout outcomes |
| GET | `/rep-health/` | List rep health cards (week filter) |
| GET | `/rep-health/{week}/{rep}/` | Single rep health card |
| GET | `/dashboards/summary/` | Aggregated KPIs across all pipelines |
| GET | `/dashboards/ar-queue/` | AR collections priority queue |
| GET | `/dashboards/slow-movers/` | Dead-stock / slow-mover alert table |

### 8.6 CarbonIntelligence integration

Add a `HealthyDomainAI` in `backend/healthy/domain_ai.py` following the pattern
of `backend/ai/domain/emissions.py`:

```python
class HealthyDomainAI:
    """Domain vocabulary and context for the Healthy app AI tasks."""

    DOMAIN_VOCAB = {
        'DSD': 'Direct-Store-Delivery — van delivery to small shops/supermarkets',
        'rep_code': 'Sales representative identifier in the ERP',
        'loadout_sheet': 'Van loading plan — how much of each item a rep should take',
        'returns_panel': '72-week demand observation panel for the returns forecast model',
        'churn_probability': 'Model-predicted probability a rep loses a customer this month',
    }

    def enrich_scope(self, scope, user): ...
    def context_for_task(self, task_type, workspace_context): ...
```

Register this in `CarbonIntelligence` so that when `scope.active_apps` contains
`'healthy'`, the AI context is enriched with `HealthyDomainAI.context_for_task()`.

---

## 9. The Closed Loop — Full Data-to-Prediction-to-Quality Cycle

This is the platform's core value. Every step is implemented by the components above.

```
Step 1: INGEST
  ERP DataSource ──► datahub/ingest.py ──► DataTable + DataRows
  (or CSV upload)       (using connections/)  (dataschema layer)

Step 2: GOVERN
  New DatasetVersion(status='pending')
  dq/jobs.py runs field rules + business rules on the DataTable
  health_score computed: completeness + validity + freshness
  DataContract.check() → DataContractViolation if any SLA breached

Step 3: APPROVE
  Data steward reviews health score + violations in datahub frontend
  Approves → DatasetVersion(status='approved')
  dataset.current_version updated
  AppManifest.consumed_datasets notified (via Django signal)

Step 4: MODEL LINK
  CarbonTurnKeyClient.register_or_get_model(name)
  push_version(artifact_path, metrics, feature_names)
  promote_to_production()
  TurnKeyModelLink(status='promoted') saved
  DatasetVersion.turnkey_links now records: "this version produced this model"

Step 5: SERVE
  External app / healthy frontend calls TurnKey directly via API key
  (TurnKey's own auth — Carbon not in the prediction critical path)
  Predictions logged in TurnKey's PredictionLog

Step 6: FEEDBACK
  TurnKey pushes PredictionCallback → /api/v1/integrations/turnkey/callback/predictions/
  Carbon creates PredictionRecord (input_hash, prediction, model_link)
  Optionally traced back to DataRow via input_hash

Step 7: ACTUALS
  User submits actual outcome (loadout actuals, real churn, AR collected)
  PredictionRecord.actual set → feedback loop complete
  TurnKey accuracy monitoring uses this for MAPE/accuracy snapshots

Step 8: DRIFT RESPONSE
  TurnKey fires drift alert → /api/v1/integrations/turnkey/callback/drift-alerts/
  DriftAlert created in Carbon
  DQ anomaly job triggered on the source DataTable
  DataContractViolation(type='quality') created if threshold breached
  CarbonIntelligence learns: KgFeedbackRecord("dataset X drifted after week Y")
  Data steward notified to check dataset health and ingest a fresh version
  Loop returns to Step 1
```

---

## 10. Wiring Checklist (what to add to existing files)

When implementing the new apps, these existing files require additions:

| File | What to add |
|------|-------------|
| `config/settings.py` | `INSTALLED_APPS`: `'datahub'`, `'integrations.turnkey'`, `'appregistry'`, `'healthy'`. New settings: `FERNET_KEY`, `TURNKEY_CALLBACK_SECRET`. |
| `config/urls.py` | Include `datahub.urls`, `integrations.turnkey.urls`, `appregistry.urls`, `healthy.urls` |
| `backend/conftest.py` | Import new app models for test table creation |
| `accounts/capabilities.py` | New capabilities (§4.2) + group mappings |
| `accounts/ai_scoping.py` | Inject `active_apps` into Scope (§7.5) |
| `ai/intelligence.py` | Register `HealthyDomainAI` when app slug `'healthy'` is active |
| `manage.sh` | Add `python manage.py register_healthy_app` to the initial-data setup block |

---

## 11. Frontend — Key Screens to Add

React 19 + MUI v7 — follow Carbon's existing patterns (zinc/blue, compact density).

| Screen | Route | Components |
|--------|-------|-----------|
| Dataset Catalog | `/datahub` | DatasetList, DatasetCard (health badge, version count) |
| Dataset Detail | `/datahub/:id` | VersionTimeline, HealthScoreGauge, ContractPanel, ViolationTable |
| Version Approval | `/datahub/:id/versions/:vid` | SchemaPreview, DQResultSummary, ApproveRejectActions |
| TurnKey Links | `/integrations/turnkey` | ModelLinkTable, PredictionFeed, DriftAlertBadge |
| App Registry | `/apps` | AppCard (icon, status, activate/deactivate) |
| Healthy Dashboard | `/apps/healthy` | PipelineStatusRow (5 pipelines), SummaryKPIs |
| Loadout Sheet | `/apps/healthy/loadout` | WeekPicker, RepTable, ItemRows, ExportXLS button |
| Rep Health | `/apps/healthy/reps` | RepCards grid with churn probability badge |
| AR Queue | `/apps/healthy/collections` | PriorityTable sortable by risk score |
| Slow Movers | `/apps/healthy/inventory` | Heatmap + AlertTable |

Carbon's existing `sidebar.jsx` / navigation: add "Data Hub", "Integrations", "Apps"
sections. The Healthy app renders inside the existing `<MainLayout>` shell.

---

## 12. Deployment (single-org model)

No multi-tenancy. Each customer deployment is an isolated Docker Compose instance:
one Postgres database, one Carbon container, one reverse proxy.

```
# Additional environment variables for new modules
FERNET_KEY=<generated>
TURNKEY_CALLBACK_SECRET=<generated>
TURNKEY_BASE_URL=https://turnkey.clearturn.tech
# (TurnKey API key stored encrypted in TurnKeyConfig model, not in env)
```

For the Healthy deployment specifically, also set:
```
HEALTHY_ERP_DB_HOST=<azure-pg-host>
HEALTHY_ERP_DB_PORT=5432
HEALTHY_ERP_DB_NAME=healthy_legacy_2026
HEALTHY_ERP_DB_USER=<read-only user>
HEALTHY_ERP_DB_PASSWORD=<password>
```

These credentials go into `connections/` as a `DataSource(source_type='database')`
via the admin or a management command — never hardcoded.

---

## 13. Implementation Order (strict)

Dependencies enforce this order:

```
Phase 1: datahub/          ← depends on: dataschema, catalog, dq, connections
Phase 2: integrations/     ← depends on: datahub
Phase 3: appregistry/      ← depends on: catalog, accounts (can parallel-run with Phase 2)
Phase 4: healthy/          ← depends on: datahub, integrations, appregistry
```

**Gate to advance from each phase**: all required tests pass + `./manage.sh test` green.

---

## 14. Success Criteria

The platform is considered "Phase 4 complete" when all of the following are true:

- [ ] 40+ new tests added (≥20 datahub, ≥6 integrations, ≥5 appregistry, ≥10 healthy)
- [ ] Total test count ≥ 1,231 (1,191 existing + 40 new), all passing
- [ ] A `healthy-returns-panel` DatasetVersion can be created, DQ-reviewed, approved,
      and its `TurnKeyModelLink` verified against the live `healthy-returns` production model
- [ ] TurnKey drift alert received via callback → DQ job triggered → DataContractViolation created
- [ ] Prediction actual submitted → PredictionRecord.actual set
- [ ] Loadout sheet generated from TurnKey predictions and viewable in the Healthy frontend
- [ ] CBAC: a user with only `healthy:view` in `module=healthy-sales` cannot see datasets
      in `module=healthy-collections`
- [ ] All 5 AI pipelines have their Datasets created, contracted, and linked to TurnKey models
      (models may be pending training; links can be in `status='pending'`)
- [ ] CarbonIntelligence answers "what is the current health of the returns forecast dataset?"
      with real data from DatasetVersion.health_detail
