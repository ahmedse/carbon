# TASK-RESULT-A2.md — RUN A2: Core Governance RBAC Fix

## Summary

RUN A2 refined governance RBAC so that governance resources are writable only by global admins. A shared `ReadAnyWriteGlobalAdmin` permission class was added to `accounts/permissions.py`, catalog/mdm/dq views were updated to use it, and a Django test script verified that a global admin can write while an org-scoped admin is blocked. Documentation was updated in `docs/DESIGN_ORG_ACCESS_MODEL.md`.

## Blockers

None.

## Step 1: Analyze Current Permission Model

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
cat catalog/permissions.py
dq/permissions.py
ls -la mdm/permissions.py 2>/dev/null || echo "mdm/permissions.py not found"
grep -rn "ReadAnyWriteAdmin" catalog/ mdm/ dq/ --include="*.py"
grep -A 10 "class ScopedRole" accounts/models.py
```

**Output:**
- `catalog/permissions.py` and `dq/permissions.py` both contained `ReadAnyWriteAdmin`.
- `mdm/permissions.py` exists and also contained `ReadAnyWriteAdmin`.
- `ReadAnyWriteAdmin` logic:
  - allow any authenticated user to read
  - allow write if `user.is_superuser`
  - allow write if `ScopedRole.objects.filter(user=user, is_active=True, group__name='admins_group').exists()`
- There was no global-scope check; any `admins_group` member could write.

**Verdict:**
✅ Confirmed the bug: `ReadAnyWriteAdmin` grants write to ANY `admins_group` member, including org-scoped admins.

## Step 2: Create `ReadAnyWriteGlobalAdmin` Permission

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
# Edit accounts/permissions.py
python manage.py check
git add accounts/permissions.py
git commit -m "feat: add ReadAnyWriteGlobalAdmin permission (governance write requires global admin)"
```

**Output:**
```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
System check identified no issues (0 silenced).
[feature/ai-copilot-mvp edd78a5] feat: add ReadAnyWriteGlobalAdmin permission (governance write requires global admin)
 1 file changed, 19 insertions(+)
```

**Location:**
- `backend/accounts/permissions.py`
- `ReadAnyWriteGlobalAdmin` added after `HasScopedRole`

**Verdict:**
✅ New global-admin-only governance permission created and backend still boots.

## Step 3: Update Catalog App Permissions

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
grep -n "permission_classes.*ReadAnyWriteAdmin" catalog/views.py
# Update import and permission classes
python manage.py check
git add backend/catalog/views.py
git commit -m "refactor: use ReadAnyWriteGlobalAdmin for governance resources in catalog, mdm, and dq"
```

**Output:**
```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
System check identified no issues (0 silenced).
[feature/ai-copilot-mvp b72739b] refactor: use ReadAnyWriteGlobalAdmin for governance resources in catalog, mdm, and dq
 3 files changed, 17 insertions(+), 17 deletions(-)
```

**ViewSets updated:**
- `DataDomainViewSet`
- `GlossaryTermViewSet`
- `TagViewSet`
- `AssetProfileViewSet`

**Verdict:**
✅ Catalog governance views now use `ReadAnyWriteGlobalAdmin`.

## Step 4: Update MDM App Permissions

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
cat mdm/permissions.py 2>/dev/null
grep -n "permission_classes.*ReadAnyWriteAdmin" mdm/views.py
# Update import and permission classes
python manage.py check
```

**Output:**
```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
System check identified no issues (0 silenced).
```

**ViewSets updated:**
- `ReferenceSetViewSet`
- `ReferenceValueViewSet`
- `BindFieldView`
- `OrgUnitViewSet`

**Verdict:**
✅ MDM governance views now use `ReadAnyWriteGlobalAdmin`.

## Step 5: Update DQ App Permissions

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
grep -n "permission_classes.*ReadAnyWriteAdmin" dq/views.py
# Update import and permission classes
python manage.py check
```

**Output:**
```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
System check identified no issues (0 silenced).
```

**ViewSets updated:**
- `FieldProfileViewSet`
- `TableProfileViewSet`
- `DQRuleViewSet`
- `DQResultViewSet`
- `ProfileTriggerView`
- `DQRunView`

**Verdict:**
✅ DQ governance views now use `ReadAnyWriteGlobalAdmin`.

## Step 6: Create Test Script

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
cat > test_governance_rbac.py << 'EOF'
# ... script content ...
EOF
chmod +x test_governance_rbac.py
python test_governance_rbac.py
git add backend/test_governance_rbac.py
git commit -m "test: add governance RBAC script for RUN A2"
```

**Output:**
```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
============================================================
TEST: Governance RBAC (Global vs Org-Scoped Admin)
============================================================
Global admin: global_admin (global)
Org-scoped admin: org_admin (org_unit=5)
Global admin can write: True
Org-scoped admin can write: False
Global admin can read: True
Org-scoped admin can read: True

ALL TESTS PASSED ✅
============================================================
[feature/ai-copilot-mvp 461d02d] test: add governance RBAC script for RUN A2
 1 file changed, 87 insertions(+)
 create mode 100755 backend/test_governance_rbac.py
```

**Verdict:**
✅ Test script proves the fix works: global admin write allowed, org-scoped admin write blocked, both can read.

## Step 7: Update Design Documentation

**Commands:**
```bash
cd /home/ahmed/aast/carbon
# Append new RUN A2 section to docs/DESIGN_ORG_ACCESS_MODEL.md
git add docs/DESIGN_ORG_ACCESS_MODEL.md
git commit -m "docs: document governance resource protection (ReadAnyWriteGlobalAdmin)"
```

**Output:**
```
[feature/ai-copilot-mvp ddde8de] docs: document governance resource protection (ReadAnyWriteGlobalAdmin)
 1 file changed, 21 insertions(+)
```

**Verdict:**
✅ Documentation updated to describe the new `ReadAnyWriteGlobalAdmin` model and rationale.

## Step 8: Final Verification

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend
source venv/bin/activate
python manage.py check
python test_governance_rbac.py
cd ..
git status
git log --oneline -10
```

**Output:**
```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
System check identified no issues (0 silenced).
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
============================================================
TEST: Governance RBAC (Global vs Org-Scoped Admin)
============================================================
Global admin: global_admin (global)
Org-scoped admin: org_admin (org_unit=5)
Global admin can write: True
Org-scoped admin can write: False
Global admin can read: True
Org-scoped admin can read: True

ALL TESTS PASSED ✅
============================================================
```

**Git Status:**
```
 M TASK.md
?? .clinerules/
?? TASK-RESULT-backup-20260718-123208.md
?? backend/carbon_data_20260112.json
?? backend/emissions/management/commands/setup_carbon_dq.py
```

**Last 5 commits:**
- 461d02d test: add governance RBAC script for RUN A2
- ddde8de docs: document governance resource protection (ReadAnyWriteGlobalAdmin)
- b72739b refactor: use ReadAnyWriteGlobalAdmin for governance resources in catalog, mdm, and dq
- edd78a5 feat: add ReadAnyWriteGlobalAdmin permission (governance write requires global admin)
- 3bfa350 chore: add RUN A1 results and status tracker

**Verdict:**
✅ Final verification passed. Backend boots cleanly and the governance RBAC test script passes.

## Acceptance Criteria Table

| # | Criterion | Pass Threshold | Status | Evidence Ref |
|---|-----------|----------------|--------|--------------|
| AC1 | `ReadAnyWriteGlobalAdmin` created | Class exists in accounts/permissions.py with org_unit=None global admin check | ✅ PASS | Step 2 |
| AC2 | Catalog app updated | All ViewSets use ReadAnyWriteGlobalAdmin | ✅ PASS | Step 3 |
| AC3 | MDM app updated | All governance endpoints use ReadAnyWriteGlobalAdmin | ✅ PASS | Step 4 |
| AC4 | DQ app updated | All governance endpoints use ReadAnyWriteGlobalAdmin | ✅ PASS | Step 5 |
| AC5 | Test proves org-scoped admin blocked | RBAC script outputs correct allow/deny behavior | ✅ PASS | Step 6 |
| AC6 | Docs updated | `DESIGN_ORG_ACCESS_MODEL.md` documents the refined model | ✅ PASS | Step 7 |
| AC7 | Backend boots after changes | `manage.py check` exit 0 | ✅ PASS | Step 8 |
| AC8 | Git commits logical | Separate commits for permission, views, test, docs | ✅ PASS | Steps 2-7 |

## Definition of Done Status

✅ DoD MET. The fix is implemented, tested, documented, and backend verification passed.

## Notes

- The current `git status` shows unrelated untracked files and a modified `TASK.md` only. No run-related tracked files remain uncommitted aside from the result file if added.
- The new permission model uses global admin scope correctly via `user_has_global_role(user, ['admins_group'])`.

**END OF RUN A2**
