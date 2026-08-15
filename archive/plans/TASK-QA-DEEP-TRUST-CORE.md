# TASK: QA-DEEP-TRUST-CORE — Comprehensive Data Trust Core Audit
# =============================================================
# Phase: Full Data Trust Platform End-to-End Deep Test
# Assigned to: QA/Validator (High budget, DeepSeek-V3 / Claude 4)
# Author: Master Architect
# Date: 2026-08-05
# Status: READY FOR ASSIGNMENT
# Delivers: TASK-RESULTS-QA-TRUST-CORE.md

---

## 0. CONTEXT — What This Covers

The Carbon Data Trust Platform has **4 trust-core apps** built but never deep-tested:
`catalog`, `mdm`, `dq`, `evidence`. + the **integration seams** between them and with `dataschema`.

This task audits **every model, every endpoint, every RBAC path, every state machine**
across all 4 trust apps, plus governance/lineage/audit. ~250 test points.

### Trust Core Architecture (recap)

```
                    ┌──────────────────────────┐
                    │   Carbon app (emissions/)  │
                    │   Calculation, Reporting,  │
                    │   Factors, GWP, Targets    │
                    └──────────┬────────────────┘
                               │ reads trusted data
┌──────────────────────────────┼──────────────────────────────────┐
│  DATA TRUST CORE             │                                   │
│  ┌──────────┐  ┌──────────┐  │  ┌──────────┐  ┌─────────────┐ │
│  │ catalog/ │  │  mdm/    │  │  │   dq/    │  │  evidence/   │ │
│  │ Domains  │  │ RefSets  │  │  │ Rules    │  │ Upload/DL    │ │
│  │ Glossary │  │ OrgUnits │  │  │ Profiles │  │ Soft-delete  │ │
│  │ Tags     │  │ Values   │  │  │ Executor │  │ Bulk         │ │
│  │ Assets   │  │ Steward  │  │  │ Scores   │  │ RBAC         │ │
│  │ GovEvents│  │ Lifecycle│  │  │ Metrics  │  │              │ │
│  │ Policies │  │          │  │  │          │  │              │ │
│  └──────────┘  └──────────┘  │  └──────────┘  └─────────────┘ │
│                               │                                   │
│  ┌────────────────────────────┴──────────────────────────────┐  │
│  │  dataschema/ — DataTable, DataField, DataRow (substrate)  │  │
│  │  accounts/ — User, Group, ScopedRole, RBAC utilities      │  │
│  │  core/ — Module, OrgUnit                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Files Covered (source under test)

| App | Files |
|-----|-------|
| catalog | `models.py`, `views.py`, `services.py`, `policy_engine.py`, `audit_utils.py`, `permissions.py`, `serializers.py` |
| mdm | `models.py`, `views.py`, `services.py`, `permissions.py`, `serializers.py` |
| dq | `models.py`, `views.py`, `services.py`, `executor.py`, `permissions.py`, `serializers.py` |
| evidence | `models.py`, `views.py`, `services.py`, `permissions.py`, `serializers.py` |

---

## 1. PRE-FLIGHT GATE

```bash
cd /home/ahmed/aast/carbon

# L1 Structural gate
./.ai-toolkit/scripts/verify.sh full
cd carbon-frontend && npm run build 2>&1 | tail -5

# Run existing unit tests for all 4 apps
cd /home/ahmed/aast/carbon
.venv/bin/python backend/manage.py test catalog dq mdm evidence --verbosity=2 2>&1 | tail -30

# Check all trust-core endpoints exist (swagger)
curl -s http://localhost:8009/carbon-api/swagger/?format=json | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)
paths=[p for p in d.get('paths',{}).keys()]
trust=[p for p in paths if any(x in p for x in ['catalog','mdm','dq','evidence'])]
print(f'Trust-core endpoints: {len(trust)}')
for p in sorted(trust): print(f'  {p}')
"

# Mint fresh tokens for all test users
.venv/bin/python backend/manage.py shell -c "
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
U = get_user_model()
for uname in ['ahmed','alamein.admin','alamein.medical','alamein.finance','alamein.transport','alamein.hotels']:
    u = U.objects.get(username=uname)
    t = RefreshToken.for_user(u)
    print(f'{uname}: {str(t.access_token)}')
" 2>&1 | grep -v "objects imported" > /tmp/trust_tokens.txt
```

### Expected pre-flight:
- Build: clean (0 errors)
- `verify.sh full`: 0 hardcoded hex, 0 naive datetimes, 0 `print()` in app code
- Unit tests: 0 failures in catalog/dq/mdm/evidence
- Swagger: all trust-core endpoints registered

---

## 2. AUTHENTICATION SETUP

For all API tests below, use these token variables:
```bash
TOKEN_A=$(grep '^ahmed:' /tmp/trust_tokens.txt | cut -d' ' -f2)
TOKEN_LA=$(grep '^alamein.admin:' /tmp/trust_tokens.txt | cut -d' ' -f2)
TOKEN_MD=$(grep '^alamein.medical:' /tmp/trust_tokens.txt | cut -d' ' -f2)
TOKEN_FI=$(grep '^alamein.finance:' /tmp/trust_tokens.txt | cut -d' ' -f2)
TOKEN_TR=$(grep '^alamein.transport:' /tmp/trust_tokens.txt | cut -d' ' -f2)
TOKEN_HO=$(grep '^alamein.hotels:' /tmp/trust_tokens.txt | cut -d' ' -f2)
API="http://localhost:8009/carbon-api"
```

---

## 3. CATALOG — Comprehensive Audit

### 3.1 DataDomain CRUD (endpoints: `/carbon-api/catalog/domains/`)

| # | Check | Method | Expected |
|---|---|---|---|
| CD1 | List domains (admin) | `curl -s -H "Auth: Bearer $TOKEN_A" "$API/catalog/domains/"` | 200, 5 domains returned |
| CD2 | List domains (data owner) | `curl -s -w "%{http_code}" -H "Auth: Bearer $TOKEN_TR" "$API/catalog/domains/"` | 403 (AdminOrSuperuserOnly) |
| CD3 | Create domain (admin) | POST `{"name":"Test Domain QA","description":"QA audit"}` | 201, slug auto-generated |
| CD4 | Create domain dup name (admin) | POST same name again | 400 "already exists" |
| CD5 | Update domain (admin) | PATCH `{"description":"Updated"}` | 200, description changed |
| CD6 | Hard-delete blocked (admin) | DELETE domain id | 405 "Hard delete not supported" |
| CD7 | Create with parent | POST `{"name":"Child QA","parent":<parent_id>}` | 201, parent set |
| CD8 | Owner assignment | POST `{"name":"Owned QA","owner":3}` | 201, owner=medical user |
| CD9 | Pagination | GET `?page_size=2` | 2 results, next/prev links |
| CD10 | Search by name | GET `?search=Medicine` | 1 result, Medicine Carbon |

### 3.2 GlossaryTerm CRUD (endpoints: `/carbon-api/catalog/glossary/`)

| # | Check | Method | Expected |
|---|---|---|---|
| CG1 | List terms (admin) | GET `/catalog/glossary/` | 200, 15 terms |
| CG2 | Create term → governance event | POST `{"term":"QA Test Term","definition":"A test","domain":1,"steward":3}` | 201, governance event emitted (verify via `/catalog/governance-events/`) |
| CG3 | Update term → event with diff | PATCH `{"definition":"Updated def"}` | 200, event shows before/after diff only on changed fields |
| CG4 | Delete term (admin) | DELETE term id | 204, governance event emitted |
| CG5 | Hard-delete blocked for non-admin | DELETE as data owner | 403 |
| CG6 | Term with synonyms | POST `{"term":"Syn Test","synonyms":["alt1","alt2"]}` | 201, synonyms array stored |
| CG7 | Filter by domain | GET `?domain=1` | terms in Medicine Carbon only |
| CG8 | Filter by status | GET `?status=approved` | only approved terms |
| CG9 | Slug auto-generation | POST `{"term":"  Space Padded  "}` | slug = `space-padded` |
| CG10 | Status transitions | Create draft → PATCH `{"status":"approved"}` → PATCH `{"status":"deprecated"}` | each 200 |

### 3.3 Tags (endpoints: `/carbon-api/catalog/tags/`)

| # | Check | Method | Expected |
|---|---|---|---|
| CT1 | List tags | GET `/catalog/tags/` | 200, returns existing tags |
| CT2 | Create tag | POST `{"name":"QA Tag","color":"#FF6600"}` | 201 |
| CT3 | Create dup name | POST `{"name":"QA Tag"}` | 400 unique constraint |
| CT4 | Update tag color | PATCH `{"color":"#0066FF"}` | 200 |
| CT5 | Delete tag | DELETE tag id | 204 |

### 3.4 AssetProfile (endpoints: `/carbon-api/catalog/assets/`)

| # | Check | Method | Expected |
|---|---|---|---|
| CA1 | List assets (admin) | GET `/catalog/assets/` | 200, 1 per DataTable + 1 per DataField |
| CA2 | Asset count = tables + fields | Count returned vs `DataTable.objects.count() + DataField.objects.count()` | Match |
| CA3 | Asset for specific table | GET `?data_table=3` | 1 result, linked to fleet_fuel_log |
| CA4 | Asset for specific field | GET `?data_field=4` | 1 result if profile exists |
| CA5 | Update asset description | PATCH asset id `{"description":"QA updated"}` | 200 |
| CA6 | Update classification | PATCH `{"classification":"confidential"}` | 200, governance event emitted |
| CA7 | Assign domain | PATCH `{"domain":2}` | 200 |
| CA8 | Assign tags | PATCH `{"tags":[1,2]}` | 200, M2M updated |
| CA9 | Assign steward | PATCH `{"steward":3}` | 200 |
| CA10 | Filter by domain | GET `?domain=1` | only Medicine assets |
| CA11 | Filter by classification | GET `?classification=confidential` | only confidential |
| CA12 | Filter by quality_status | GET `?quality_status=passing` | only passing |
| CA13 | Search text | GET `?search=fuel` | fleet_fuel_log + its fields |
| CA14 | Access by data owner (own scope) | GET as alamein.transport | only Transport assets (org 5) |
| CA15 | Access by data owner (cross scope) | GET transport → verify no Medicine assets returned | no org 3 / org 7 assets |
| CA16 | Asset write by data owner (own) | PATCH own table's asset `{"description":"owner update"}` | 200/403 (depends on permission class) |
| CA17 | Asset write by data owner (other) | PATCH medicine table's asset as transport | 403 |
| CA18 | ensure_asset_profiles idempotent | Call twice, second call | returns 0 (all already exist) |
| CA19 | New table auto-gets AssetProfile | Create DataTable → GET `/catalog/assets/?data_table=<new>` | 1 profile exists |

### 3.5 GovernanceEvent (endpoints: `/carbon-api/catalog/governance-events/`)

| # | Check | Method | Expected |
|---|---|---|---|
| GE1 | List events (admin) | GET `/catalog/governance-events/` | 200, all events |
| GE2 | Pagination (50/page) | GET | 50 events per page |
| GE3 | Filter by entity_type | GET `?entity_type=GlossaryTerm` | only glossary events |
| GE4 | Filter by action | GET `?action=create` | only create events |
| GE5 | Filter by user | GET `?user=2` | only admin's events |
| GE6 | Filter by date range | GET `?timestamp_after=2026-01-01&timestamp_before=2026-12-31` | only 2026 events |
| GE7 | Event has before/after | Inspect a single event | JSON fields populated |
| GE8 | Event has user info | Inspect | user id + username in response |
| GE9 | Data owner cannot list events | GET as transport | 403 or empty results |
| GE10 | Event on GlossaryTerm create | Find event for "QA Test Term" create | before={}, after=full term data |
| GE11 | Event on AssetProfile update | Find event for classification change | before/after diff present |
| GE12 | Event on ReferenceSet lifecycle | Find event for lifecycle transition | before/after state in after |

### 3.6 GovernancePolicy (endpoints: `/carbon-api/catalog/policies/`)

| # | Check | Method | Expected |
|---|---|---|---|
| GP1 | List policies (admin) | GET `/catalog/policies/` | 200, 5 policies (1 per domain) |
| GP2 | Create policy | POST `{"name":"QA Delete Block","policy_type":"table_delete","scope_type":"domain","domain":1,"enabled":true}` | 201 |
| GP3 | Update policy | PATCH `{"enabled":false}` | 200 |
| GP4 | Policy enforcement: table_delete blocked | Attempt DELETE DataTable with domain=1 and table_delete policy enabled | blocked by policy_engine |
| GP5 | Policy enforcement: module_delete blocked | Same for module_delete | blocked |
| GP6 | Policy doesn't block unrelated action | Create policy for table_delete → attempt table_update | NOT blocked |
| GP7 | Policy scoped to org_unit | Create policy with scope_type=org_unit, test only that org | blocked for matching org, allowed for other |
| GP8 | Policy scoped to emission_scope | Create policy with scope_type=scope, emission_scope=1 | blocks scope-1 modules/tables |
| GP9 | Disabled policy has no effect | Disable a policy → retry blocked action | now allowed |
| GP10 | check_policy() returns (allowed, blocked_by) | Call programmatically | tuple with list of blocking policy names |

### 3.7 Asset Search (endpoints: `/carbon-api/catalog/assets/search/`)

| # | Check | Method | Expected |
|---|---|---|---|
| CS1 | Full-text search | GET `?q=electricity` | returns electricity-related assets |
| CS2 | Search by glossary term | GET `?glossary_term=<id>` | assets linked to that term |
| CS3 | Search by tag | GET `?tag=<id>` | assets with given tag |
| CS4 | Combined filters | GET `?domain=1&classification=internal&search=kWh` | intersection |

---

## 4. MDM — Comprehensive Audit

### 4.1 ReferenceSet CRUD (endpoints: `/carbon-api/mdm/reference-sets/`)

| # | Check | Method | Expected |
|---|---|---|---|
| MR1 | List reference sets (admin) | GET `/mdm/reference-sets/` | 200, 7 sets |
| MR2 | List reference sets (data owner) | GET as transport | only sets in their org scope |
| MR3 | Create reference set | POST `{"name":"QA Reference Set","description":"Test","domain":2}` | 201, steward=current user |
| MR4 | Update reference set (steward) | PATCH as creating user `{"description":"Updated"}` | 200 |
| MR5 | Update reference set (non-steward) | PATCH as different user | 403 "Only steward can edit" |
| MR6 | Update reference set (staff override) | PATCH as ahmed (staff) | 200 (staff bypass) |
| MR7 | Soft delete (admin) | DELETE set id | 204, is_active=False, governance event |
| MR8 | Soft delete (non-admin) | DELETE as transport | 403 |
| MR9 | Annotated value count | GET list → each set has `values_count` | matches ReferenceValue count |
| MR10 | Search by name | GET `?search=Building` | returns Building Codes set |
| MR11 | Order by name/created_at | GET `?ordering=name` / `?ordering=-created_at` | correct order |
| MR12 | Empty result for user with no org | Create user with 0 ScopedRole entries → GET reference-sets | empty array |

### 4.2 ReferenceSet Lifecycle (state machine)

| # | Check | Method | Expected |
|---|---|---|---|
| ML1 | Default lifecycle | Inspect newly created set | `draft` |
| ML2 | draft → active | `POST /mdm/reference-sets/{id}/transition/ {"state":"active"}` | 200, state=active |
| ML3 | active → deprecated | POST transition `{"state":"deprecated"}` | 200, state=deprecated |
| ML4 | deprecated → active | POST transition `{"state":"active"}` | 200 (re-activate) |
| ML5 | deprecated → archived | POST transition `{"state":"archived"}` | 200, state=archived, is_active=False |
| ML6 | archived → (any) | POST transition to any state | 400, blocked |
| ML7 | Invalid transition | POST draft→deprecated | 400, ValueError |
| ML8 | Same-state transition | POST draft→draft | 200, no-op |
| ML9 | Empty state | POST transition `{"state":""}` | 400 "This field is required" |
| ML10 | Invalid state value | POST transition `{"state":"nonsense"}` | 400 "Invalid state" |
| ML11 | Governance event on transition | After transition → GET governance-events for ReferenceSet | event with before/after state |
| ML12 | Transition as non-steward | POST transition as non-steward user | 403 or 400 |

### 4.3 ReferenceValue CRUD (endpoints: `/carbon-api/mdm/reference-values/`)

| # | Check | Method | Expected |
|---|---|---|---|
| MV1 | List values for a set | GET `/mdm/reference-values/?reference_set=1` | values for Building Codes |
| MV2 | List values filtered by active | GET `?reference_set=1&is_active=true` | only active values |
| MV3 | Create value | POST `{"reference_set":1,"code":"QA-001","label":"QA Value","sort_order":99}` | 201 |
| MV4 | Duplicate code in same set | POST same code to same set | 400 unique constraint |
| MV5 | Update value | PATCH `{"label":"Updated Label"}` | 200 |
| MV6 | Deactivate value | PATCH `{"is_active":false}` | 200, value hidden from active-only queries |
| MV7 | valid_from/valid_to temporal | Create value with `valid_from: 2026-01-01, valid_to: 2026-06-30` | temporal fields stored |
| MV8 | get_current_values(as_of=date) | Test: value valid 2026-01→06, query as_of=2026-03 | returned |
| MV9 | get_current_values outside window | Same value, query as_of=2026-08 | NOT returned |
| MV10 | Metadata JSON | Create value with `{"metadata":{"source":"QA","confidence":0.95}}` | metadata stored and returned |
| MV11 | Sort order respected | Create 3 values with different sort_order | returned in sort_order ASC, then code |

### 4.4 Bulk ReferenceValue Operations

| # | Check | Method | Expected |
|---|---|---|---|
| MB1 | Bulk create values | POST `/mdm/reference-sets/{id}/bulk-values/` with array of 5 values | 201, 5 created, governance event |
| MB2 | Bulk create with one invalid | POST array where one has empty code | 400, error details, none created (atomic) |
| MB3 | Bulk archive sets | POST `/mdm/reference-sets/bulk-archive/` `{"ids":[id1,id2]}` | 200, success/failed arrays |
| MB4 | Bulk archive non-existent | POST with invalid id | entry in "failed" array, not error |

### 4.5 OrgUnit (endpoints: `/carbon-api/mdm/org-units/`)

| # | Check | Method | Expected |
|---|---|---|---|
| MO1 | List org units (admin) | GET `/mdm/org-units/` | 200, 7 units, tree structure |
| MO2 | List org units (data owner) | GET as transport | 200, all 7 (currently unscoped — see F-07) |
| MO3 | Create org unit | POST `{"name":"QA Unit","parent":2,"org_type":"department","code":"QA-001"}` | 201 |
| MO4 | Duplicate name under same parent | POST same name under same parent | 400 unique_together |
| MO5 | Update org unit | PATCH `{"description":"Updated"}` | 200 |
| MO6 | Soft delete (admin) | PATCH `{"is_active":false}` | 200 |
| MO7 | Tree structure: get ancestors | Check new child unit's ancestors | includes parent chain to root |
| MO8 | Tree structure: get descendants | Check parent's tree (via service) | includes all nested children |
| MO9 | get_descendant_ids(include_self=True) | Test OrgUnitService.get_tree() | returns self + all deep children |
| MO10 | Slug auto-generation | POST `{"name":"  QA Unit 2  ","parent":2}` | slug = `qa-unit-2` |
| MO11 | Org-type filtering | GET `?org_type=campus` | only Alamein Campus |
| MO12 | Parent filtering | GET `?parent=2` | only children of org 2 |

### 4.6 MDM Field Binding (endpoints: `/carbon-api/mdm/bind-field/`, `/carbon-api/mdm/field-options/`)

| # | Check | Method | Expected |
|---|---|---|---|
| MF1 | Bind field to reference set | POST `{"data_field":<id>,"reference_set":1}` | 200, field now references Building Codes |
| MF2 | Field options from reference set | GET `/mdm/field-options/?data_field=<id>` | returns active values from bound reference set |
| MF3 | Field options respect temporal | Create time-limited value, query as_of outside window | not returned |
| MF4 | Field options respect is_active | Deactivate a value → query options | not returned |
| MF5 | Re-bind field | POST bind-field to different reference set | 200, old binding replaced |
| MF6 | Unbind field | POST bind-field with `{"reference_set":null}` | 200, field unbound |

---

## 5. DQ — Comprehensive Audit

### 5.1 DQRule CRUD (endpoints: `/carbon-api/dq/rules/`)

| # | Check | Method | Expected |
|---|---|---|---|
| DR1 | List rules (admin) | GET `/dq/rules/` | 200, 50 rules |
| DR2 | List rules (data owner) | GET as transport | only rules on Transport tables |
| DR3 | Create field-level rule | POST `{"scope":"field","data_table":3,"data_field":<id>,"name":"QA NotNull","rule_type":"not_null","severity":"error"}` | 201 |
| DR4 | Create table-level rule | POST `{"scope":"table","data_table":3,"name":"QA Table Rule","rule_type":"unique","severity":"warn"}` | 201 |
| DR5 | Create rule without name | POST without name | 201 (name has default="") or 400 |
| DR6 | Create rule with params | POST `{"rule_type":"range","params":{"min":0,"max":10000}}` | 201, params stored |
| DR7 | Create rule with invalid type | POST `{"rule_type":"invalid_type"}` | 400 |
| DR8 | Create rule without scope+target | POST without data_table and data_field | 400 |
| DR9 | Update rule | PATCH `{"severity":"warn"}` | 200 |
| DR10 | Deactivate rule | PATCH `{"is_active":false}` | 200 |
| DR11 | Delete rule (admin) | DELETE rule id | 204 |
| DR12 | Delete rule (data owner) | DELETE own table's rule | 403 (admin only) |
| DR13 | created_by auto-assignment | Inspect created rule | created_by=request.user |
| DR14 | Filter by rule_type | GET `?rule_type=not_null` | only not_null rules |
| DR15 | Filter by severity | GET `?severity=error` | only error-severity rules |
| DR16 | Filter by is_active | GET `?is_active=true` | only active rules |
| DR17 | Filter by data_table | GET `?data_table=3` | only rules on table 3 |

### 5.2 DQ Rule Types (6 types — executor verification)

| # | Check | Method | Expected |
|---|---|---|---|
| DT1 | not_null rule passes | Execute rule on `[{field:"value"}]` | passed=True, failed=0 |
| DT2 | not_null rule fails | Execute on `[{field:null}, {field:""}]` | passed=False, failed=2 |
| DT3 | unique rule passes | Execute on `[{field:"a"}, {field:"b"}]` | passed=True |
| DT4 | unique rule fails | Execute on `[{field:"a"}, {field:"a"}, {field:"b"}]` | passed=False, sample_failures lists duplicate |
| DT5 | allowed_values passes | params=`{"allowed_values":["a","b","c"]}`, data=`[{field:"a"},{field:"b"}]` | passed=True |
| DT6 | allowed_values fails | data=`[{field:"a"},{field:"d"}]` | passed=False, "d" in failures |
| DT7 | range rule passes | params=`{"min":0,"max":100}`, data=`[{field:50}]` | passed=True |
| DT8 | range rule fails (below) | data=`[{field:-1}]` | passed=False |
| DT9 | range rule fails (above) | data=`[{field:101}]` | passed=False |
| DT10 | regex rule passes | params=`{"pattern":"^[A-Z]{2}-\\d{3}$"}`, data=`[{field:"AB-123"}]` | passed=True |
| DT11 | regex rule fails | data=`[{field:"abc"}]` | passed=False |
| DT12 | reference_integrity | rule validates against ReferenceSet values | passed if value exists in ref set |
| DT13 | Score calculation: 100% | All pass | score=100 |
| DT14 | Score calculation: 50% | Half fail | score=50 |
| DT15 | Sample failures capped at 10 | 20 failures | sample_failures list length ≤ 10 |
| DT16 | Empty data → all pass | Execute with empty `data_sample` | passed=True, checked=0, score=100 |

### 5.3 DQ Profiling (endpoints: `/carbon-api/dq/profile/`, profiles list)

| # | Check | Method | Expected |
|---|---|---|---|
| DP1 | Trigger profile on table | POST `/dq/profile/` `{"data_table":3}` | 202, profiling started |
| DP2 | TableProfile created | GET `/dq/table-profiles/?data_table=3` | profile exists with row_count |
| DP3 | FieldProfiles created | GET `/dq/profiles/?data_table=3` | 1 per field in table |
| DP4 | Profile: completeness_pct | Inspect field profile | pct = (non-null/total)*100 |
| DP5 | Profile: distinct_count | Inspect field profile | count of unique values |
| DP6 | Profile: uniqueness_pct | Inspect field profile | (distinct/total)*100 |
| DP7 | Profile: min/max | Inspect string/number field | values populated |
| DP8 | Profile: top_values | Inspect field profile | array of most frequent values |
| DP9 | Profile: null_count | Inspect field profile | count of nulls |
| DP10 | Re-profile updates timestamp | Profile same table twice | 2 profiles, latest first |
| DP11 | Bulk profile | POST `/dq/profile/bulk/` `{"data_tables":[3,4,5]}` | 202, profiles for all 3 |
| DP12 | Profile non-existent table | POST `/dq/profile/` `{"data_table":99999}` | 404 |
| DP13 | Profile as data owner (own) | POST as transport for table 3 | 202 |
| DP14 | Profile as data owner (cross) | POST as transport for table 1 | 403 |
| DP15 | RBAC on table-profile list | GET as transport | only Transport table profiles |
| DP16 | RBAC on field-profile list | GET as transport | only Transport field profiles |

### 5.4 DQ Execution & Results (endpoints: `/carbon-api/dq/run/`, results list)

| # | Check | Method | Expected |
|---|---|---|---|
| DE1 | Run DQ on table | POST `/dq/run/` `{"data_table":3}` | 202, results created |
| DE2 | Run single rule | POST `/dq/run/` `{"rule":<id>}` | 202, single result |
| DE3 | Run on empty table | Find empty table, run DQ | 202, passed=True, checked=0 |
| DE4 | DQResult score field | Inspect result | positon integer 0-100 |
| DE5 | DQResult sample_failures | Inspect result where failed>0 | array with row/value/reason |
| DE6 | DQResult checked_count | Inspect result | matches actual data rows |
| DE7 | DQResult failed_count | Inspect result | number of failing rows |
| DE8 | Results list (admin) | GET `/dq/results/` | 200, all results |
| DE9 | Results list (data owner) | GET as transport | only results for their tables' rules |
| DE10 | Results filter by rule | GET `?rule=<id>` | only that rule's results |
| DE11 | Results filter by passed | GET `?passed=true` | only passing results |
| DE12 | Results ordering by run_at | GET | most recent first |
| DE13 | RBAC gate on run endpoint | POST as transport on table 1 (cross) | 403 |
| DE14 | RBAC gate on result detail | GET result id for other org's table as transport | 403 or 404 |

### 5.5 DQ Metrics (endpoints: `/carbon-api/dq/metrics/`, `/dq/metrics/table/<id>/`, `/dq/metrics/field/<id>/`)

| # | Check | Method | Expected |
|---|---|---|---|
| DM1 | Overall metrics | GET `/dq/metrics/` | returns aggregate scores |
| DM2 | Table metrics | GET `/dq/metrics/table/3/` | table-specific stats |
| DM3 | Field metrics | GET `/dq/metrics/field/<id>/` | field-specific stats |
| DM4 | Metrics: passing rules count | Inspect metrics response | sum of rules with passed=true |
| DM5 | Metrics: failing rules count | Inspect | sum of rules with passed=false |
| DM6 | Metrics: overall score | Inspect | weighted average |
| DM7 | RBAC on table metrics | GET as transport for table 1 | 403/404 |
| DM8 | RBAC on overall metrics | GET as transport | scoped to their modules only |

---

## 6. EVIDENCE — Comprehensive Audit

### 6.1 Evidence CRUD (endpoints: `/carbon-api/evidence/`)

| # | Check | Method | Expected |
|---|---|---|---|
| EV1 | Upload evidence for row | POST multipart `{"data_row":<row_id>,"file":@test.pdf}` | 201, evidence created |
| EV2 | List evidence for row | GET `?data_row=<row_id>` | evidence list, non-deleted only |
| EV3 | Evidence has metadata | Inspect response | original_filename, file_size, mime_type, uploaded_by, uploaded_at |
| EV4 | Download evidence | GET `/evidence/{id}/download/` | file content returned, Content-Disposition header |
| EV5 | Download non-existent | GET download for deleted/deleted evidence | 404 |
| EV6 | Soft delete evidence | DELETE evidence id | 204, is_deleted=True, deleted_at populated |
| EV7 | Soft delete audit | Inspect deleted evidence | deleted_by = request.user, deleted_at = timestamp |
| EV8 | Delete again (idempotent) | DELETE same id | 204, no error |
| EV9 | Hard delete prevention | Check model.delete() override | sets is_deleted, doesn't remove row |

### 6.2 Bulk Upload

| # | Check | Method | Expected |
|---|---|---|---|
| EB1 | Bulk upload 3 files | POST `/evidence/bulk-upload/` with 3 files | 201, results array with 3 successes |
| EB2 | Bulk upload with 1 corrupt file | POST with 1 empty file in mix | 201 (partial), 2 success + 1 failed in results |
| EB3 | Bulk upload response shape | Inspect | `{results:[], total:3, success:2, failed:1}` |
| EB4 | Bulk upload to invalid row | POST with data_row=99999 | 400 |

### 6.3 Evidence RBAC

| # | Check | Method | Expected |
|---|---|---|---|
| ER1 | Upload to own module's row | POST as transport to table-3 row | 201 |
| ER2 | Upload to other module's row | POST as transport to table-1 row | 403 |
| ER3 | List evidence: admin sees all | GET as ahmed | all non-deleted evidence |
| ER4 | List evidence: owner sees own | GET as transport | only evidence in Transport module |
| ER5 | Download own evidence | GET download as transport for own module evidence | 200 |
| ER6 | Download cross-module evidence | GET download as transport for medicine evidence | 403/404 |
| ER7 | Delete own evidence | DELETE as uploader | 204 |
| ER8 | Delete other's evidence (admin) | DELETE as ahmed for transport's evidence | 204 |
| ER9 | Delete other's evidence (non-admin) | DELETE as transport for medicine evidence | 403/404 |
| ER10 | Filter by uploaded_by | GET `?uploaded_by=<user_id>` | only that user's uploads |

---

## 7. GOVERNANCE & LINEAGE — Cross-Cutting Audit

### 7.1 Audit Trail Completeness

| # | Check | Method | Expected |
|---|---|---|---|
| GA1 | GlossaryTerm create → event | Create term → find event in governance-events | entity_type=GlossaryTerm, action=create |
| GA2 | GlossaryTerm update → event | Update term definition → find event | action=update, before/after diff |
| GA3 | GlossaryTerm delete → event | Delete term → find event | action=delete, before populated |
| GA4 | ReferenceSet create → event | Create ref set → find event | entity_type=ReferenceSet |
| GA5 | ReferenceSet lifecycle → event | Transition active→deprecated → find event | action=update, before={'lifecycle_state':'active'} |
| GA6 | ReferenceSet bulk archive → event | Archive 2 sets → find events | 2 events, action=delete |
| GA7 | ReferenceValue bulk create → event | Bulk create 5 values → find event | 1 event, after={'bulk_create':5} |
| GA8 | AssetProfile update → event | Change classification → find event | entity_type=AssetProfile |
| GA9 | ReportingPeriod transition → event | Transition draft→open via emissions | entity_type=ReportingPeriod |
| GA10 | Calculation create → event (if implemented) | Create calculation → find event | entity_type=Calculation (or verify not yet implemented) |

### 7.2 Policy Engine (catalog/policy_engine.py)

| # | Check | Method | Expected |
|---|---|---|---|
| GP1 | No policies → allowed | Call check_policy with no matching policies | (True, []) |
| GP2 | Global policy blocks all | Global table_delete policy → test on any table | (False, ['Policy Name']) |
| GP3 | Org-scoped policy matches | Org-unit-scoped policy for org 5 → test on org 5 table | blocked |
| GP4 | Org-scoped policy doesn't match | Same policy → test on org 3 table | NOT blocked |
| GP5 | Scope-type policy matches | Scope-scoped policy for scope=1 → test scope-1 module | blocked |
| GP6 | Domain-scoped policy matches | Domain=1 policy → test table with domain=1 AssetProfile | blocked |
| GP7 | Multiple matching policies | 2 global delete policies → test | both names in blocked_by |
| GP8 | Disabled policy ignored | enabled=False → test | not in blocked_by |
| GP9 | Non-existent action | check_policy('nonexistent_action') | (True, []) — no policies match |

### 7.3 State Machine Validations

| # | Check | Method | Expected |
|---|---|---|---|
| GS1 | ReferenceSet draft→active | transition_to('active') | success |
| GS2 | ReferenceSet draft→deprecated | transition_to('deprecated') | ValueError (invalid) |
| GS3 | ReferenceSet archived→any | transition_to('active') | ValueError (terminal) |
| GS4 | ReportingPeriod draft→open | transition_to('open') | success |
| GS5 | ReportingPeriod open→locked | transition_to('locked') | success |
| GS6 | ReportingPeriod locked→submitted | transition_to('submitted') | success |
| GS7 | ReportingPeriod submitted→verified | transition_to('verified') | success (admin) |
| GS8 | ReportingPeriod verified→closed | transition_to('closed') | success |
| GS9 | ReportingPeriod closed→any | transition_to('open') | ValueError (terminal) |
| GS10 | ReportingPeriod submitted→rejected | transition_to('rejected') | success |
| GS11 | ReportingPeriod rejected→submitted | transition_to('submitted') | success (re-submit) |
| GS12 | Same-state transition | transition_to(current_state) | no-op, returns self |

---

## 8. RBAC & TRUST ISOLATION — Multi-User Audit

Test every trust-core endpoint with all 6 users. Record access pattern.

### 8.1 Access Matrix Template

Fill this matrix for each trust-core API root:

| Endpoint | ahmed (super) | alamein.admin (carbon_lead) | .medical (owner) | .transport (owner) | .finance (owner) | .hotels (owner) |
|---|---|---|---|---|---|---|
| `GET /catalog/domains/` | 200 (5) | | | | | |
| `GET /catalog/glossary/` | 200 | | | | | |
| `GET /catalog/tags/` | 200 | | | | | |
| `GET /catalog/assets/` | 200 | | | | | |
| `GET /catalog/governance-events/` | 200 | | | | | |
| `GET /catalog/policies/` | 200 | | | | | |
| `GET /mdm/reference-sets/` | 200 | | | | | |
| `GET /mdm/reference-values/` | 200 | | | | | |
| `GET /mdm/org-units/` | 200 | | | | | |
| `GET /dq/rules/` | 200 | | | | | |
| `GET /dq/results/` | 200 | | | | | |
| `GET /dq/profiles/` | 200 | | | | | |
| `GET /dq/table-profiles/` | 200 | | | | | |
| `GET /evidence/` | 200 | | | | | |
| `POST /dq/run/` | 202 | | | | | |
| `POST /dq/profile/` | 202 | | | | | |
| `POST /evidence/` | 201 | | | | | |

### 8.2 Cross-App RBAC Verification

| # | Check | Expected |
|---|---|---|
| RB1 | Catalog assets list scoped per user's visible orgs | Transport sees only org-5 assets |
| RB2 | DQ rules list scoped per user's visible tables | Transport sees only table 3-4 rules |
| RB3 | Evidence list scoped per user's visible modules | Transport sees only Transport evidence |
| RB4 | User with no org units gets empty catalog | Create user, 0 ScopedRoles → empty asset list |
| RB5 | User with no org units gets empty reference sets | same → empty reference sets |
| RB6 | User with no org units gets empty DQ | same → empty rules/results |
| RB7 | Staff bypass on ReferenceSet update | ahmed can edit any set |
| RB8 | Steward enforcement on ReferenceSet | non-steward, non-staff → 403 |
| RB9 | Admin-only write on catalog domains/glossary/tags | data owner → 403 |
| RB10 | Admin-only write on DQ rules | data owner → 403 on create/update/delete |
| RB11 | Evidence object-level permission | user can only access own-module evidence objects |

### 8.3 Data Leak Prevention

| # | Check | Expected |
|---|---|---|
| DL1 | GET /catalog/assets/ as transport → no Medicine asset names in response | Search response for "Medicine" or "Hospital" — none |
| DL2 | GET /dq/rules/ as transport → no rules tied to non-Transport tables | All rule data_table_id in [3,4] |
| DL3 | GET /evidence/ as transport → no evidence from non-Transport rows | All data_row → table → module in org 5 |
| DL4 | GET /catalog/governance-events/ as non-admin | 403 or filtered |
| DL5 | `org-units/` exposure (known F-07) | all 7 returned — document as finding, confirm RBAC path |

---

## 9. STATE COVERAGE & ERROR HANDLING

### 9.1 Empty States

| # | Check | Expected |
|---|---|---|
| ES1 | Catalog assets for user with 0 visible tables | "No assets found" or empty array, NOT 500 |
| ES2 | DQ rules for table with 0 rules | empty array |
| ES3 | DQ results for rule never run | empty array |
| ES4 | Evidence for row with 0 files | empty array |
| ES5 | Governance events filtered to no results | empty array, proper pagination |
| ES6 | Reference values for set with 0 values | empty array |

### 9.2 Error States

| # | Check | Expected |
|---|---|---|
| ER1 | GET non-existent AssetProfile id | 404, JSON error body |
| ER2 | GET non-existent ReferenceSet id | 404 |
| ER3 | GET non-existent DQRule id | 404 |
| ER4 | GET non-existent Evidence id | 404 |
| ER5 | POST with invalid JSON body | 400, parse error |
| ER6 | POST with missing required fields | 400, field-level errors |
| ER7 | POST with wrong field type | 400, type validation |
| ER8 | POST reference-set with empty name | 400 "This field is required" |
| ER9 | Server error (simulate by breaking DB) | 500, correlated error response |
| ER10 | Auth header missing | 401/403 |

### 9.3 Concurrency & Edge Cases

| # | Check | Expected |
|---|---|---|
| EC1 | Simultaneous profile runs on same table | 2 requests, both succeed or one queues |
| EC2 | Delete reference set with values | cascade or protected (check FK on_delete) |
| EC3 | Delete DataTable → cascade to AssetProfile | AssetProfile deleted (CASCADE) |
| EC4 | Delete DataField → cascade to AssetProfile | AssetProfile deleted (CASCADE) |
| EC5 | Delete DataTable → cascade to DQRules | DQRules deleted (CASCADE) |
| EC6 | Very long tag name (255 chars) | 400 if max_length exceeded |
| EC7 | Very long glossary definition (10k chars) | handled (TextField, no limit) |
| EC8 | Unicode in entity names | Arabic text in name fields → 201, stored correctly |
| EC9 | Special chars in search query | URL-encoded query → no injection/error |

---

## 10. DATASCHEMA INTEGRATION SEAMS

### 10.1 AssetProfile ↔ DataTable/DataField

| # | Check | Expected |
|---|---|---|
| SI1 | New DataTable creates AssetProfile | Create table → AssetProfile auto-created |
| SI2 | New DataField creates AssetProfile | Create field → AssetProfile auto-created |
| SI3 | AssetProfile survives table update | Update table name → profile still linked |
| SI4 | AssetProfile deleted on table delete | Delete table → profile cascade-deleted |

### 10.2 DQRule ↔ DataTable/DataField

| # | Check | Expected |
|---|---|---|
| SI5 | Rule on deleted table | Delete table → rules cascade-deleted |
| SI6 | Rule with non-existent field_id | 400 on create |
| SI7 | Rule execution against rows from other module | blocked by RBAC |

### 10.3 Evidence ↔ DataRow

| # | Check | Expected |
|---|---|---|
| SI8 | Evidence survives row update | Update row values → evidence still linked |
| SI9 | Evidence on archived row | Row archived → evidence still accessible |
| SI10 | Row delete cascade | Delete row → evidence cascade-deleted |

---

## 11. VERIFICATION GATE (run before reporting)

```bash
cd /home/ahmed/aast/carbon

# Full structural gate
./.ai-toolkit/scripts/verify.sh full 2>&1 | tee /tmp/verify-trust-core.txt

# Frontend build
cd carbon-frontend && npm run build 2>&1 | tail -10

# All unit tests
cd /home/ahmed/aast/carbon
.venv/bin/python backend/manage.py test catalog dq mdm evidence --verbosity=2 2>&1 | tee /tmp/test-trust-core.txt

# Run catalog-specific tests
.venv/bin/python backend/manage.py test catalog.tests.test_catalog_audit catalog.tests.test_policy_engine catalog.tests.test_scoped_access catalog.tests.test_services catalog.tests.test_api_errors catalog.tests.test_bulk_operations --verbosity=2

# Run mdm-specific tests
.venv/bin/python backend/manage.py test mdm.tests.test_org_units mdm.tests.test_reference_data mdm.tests.test_reference_sets mdm.tests.test_reference_governance mdm.tests.test_mdm_audit mdm.tests.test_swagger_docs --verbosity=2

# Run dq-specific tests
.venv/bin/python backend/manage.py test dq.tests.test_dq dq.tests.test_executor dq.tests.test_api --verbosity=2

# Count total test assertions
grep -rn "def test_" backend/catalog/tests/ backend/mdm/tests/ backend/dq/tests/ backend/evidence/tests/ | wc -l
```

---

## 12. DELIVERABLE — TASK-RESULTS-QA-TRUST-CORE.md

Write at repo root. Structure:

1. **Executive Summary** — test point counts by app, pass/fail/blocked, high-severity findings
2. **Pre-Flight Results** — all gate output (verify.sh, unit tests, swagger)
3. **Catalog Findings** — Domain/Glossary/Tag/Asset/Event/Policy matrix with evidence
4. **MDM Findings** — ReferenceSet/Value/Lifecycle/OrgUnit/Binding matrix
5. **DQ Findings** — Rule/Executor/Profile/Results/Metrics matrix
6. **Evidence Findings** — CRUD/Bulk/RBAC/Download matrix
7. **Governance & Lineage** — Audit completeness, policy enforcement, state machines
8. **RBAC & Trust Matrix** — 6 users × ~20 endpoints = filled table with HTTP codes + scoping notes
9. **Integration Seams** — dataschema↔trust-core cross-checks
10. **Findings by Severity** — P0 (blocks production) → P1 (blocks journey) → P2 (data gap) → P3 (hygiene) → P4 (cosmetic)
11. **Recommendations** — prioritized dispatch list for Master Architect

### Finding format (every finding):
```
ID: TRUST-[APP]-[NNN]
Severity: P0/P1/P2/P3/P4
Symptom: (what user sees)
Reproduction: (exact curl/browser steps)
Root Cause: (code reference if known)
Impact: (which personas affected)
Evidence: (HTTP response, screenshot, console output)
Suggested Fix: (high-level, not implementation)
```

---

## 13. FILES YOU WILL READ

**Catalog:**
- `backend/catalog/models.py` — DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy
- `backend/catalog/views.py` — ViewSets + actions
- `backend/catalog/services.py` — ensure_asset_profiles()
- `backend/catalog/policy_engine.py` — check_policy()
- `backend/catalog/audit_utils.py` — emit_governance_event()
- `backend/catalog/permissions.py` — AdminOrSuperuserOnly
- `backend/catalog/serializers.py` — All serializers
- `backend/catalog/filters.py` — GovernanceEventFilter

**MDM:**
- `backend/mdm/models.py` — ReferenceSet, ReferenceValue, OrgUnit
- `backend/mdm/views.py` — ViewSets + bind-field/field-options/transition/bulk
- `backend/mdm/services.py` — ReferenceSetService, OrgUnitService
- `backend/mdm/permissions.py`
- `backend/mdm/serializers.py`

**DQ:**
- `backend/dq/models.py` — DQRule, DQResult, TableProfile, FieldProfile
- `backend/dq/views.py` — ViewSets + profile/run/metrics
- `backend/dq/services.py` — profile_table, run_dq, bulk_profile
- `backend/dq/executor.py` — DQRuleExecutor (6 rule validators)
- `backend/dq/permissions.py`

**Evidence:**
- `backend/evidence/models.py` — Evidence
- `backend/evidence/views.py` — EvidenceViewSet (CRUD + download + bulk)
- `backend/evidence/services.py` — EvidenceService
- `backend/evidence/permissions.py` — IsEvidenceOwnerOrAdmin
- `backend/evidence/serializers.py`

**Cross-cutting:**
- `backend/accounts/rbac_utils.py` — get_allowed_module_ids, user_is_global_admin, user_has_global_role
- `backend/accounts/permissions.py` — HasScopedRole, ReadAnyWriteGlobalAdmin, ReadScopedWriteAdmin
- `backend/dataschema/models.py` — DataTable, DataField, DataRow (the substrate)
- `backend/core/feedback.py` — AppFeedback exception class

---

## 14. DO NOT TOUCH

- Do NOT edit any source file — this is an audit, not a fix phase
- Do NOT run database migrations or seed commands that modify data
- Do NOT modify .env or configuration
- If you need a temporary test entity, create it via API — document it, then clean up at the end
- Report findings ONLY — fixes are dispatched separately by the Master Architect

---

*End of TASK spec. Assigned to QA/Validator worker. Expected duration: 4-6 hours for full coverage. ~250 test points across 4 apps + integration seams + RBAC.*
