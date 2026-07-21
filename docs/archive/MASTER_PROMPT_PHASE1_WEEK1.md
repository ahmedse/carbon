# 🎯 MASTER PROMPT: PHASE 1 WEEK 1 EXECUTION

**From:** Zoo (Architect/Master)  
**To:** Claude (Code Copilot/Worker)  
**Task:** Execute PHASE 1 Week 1 — MDM APIs Foundation  
**Duration:** 5 days (50 hours)  
**Status:** READY TO START

---

## 🚀 Your Mission

Build the **Master Data Management (MDM) API foundation** for the Carbon Data Trust Platform. This is the critical first step that enables all future work.

**What you're building:**
- ✅ ReferenceSet + ReferenceValue serializers/views/routes (master data lookups)
- ✅ OrgUnit serializers/views/routes (organizational hierarchy)
- ✅ RBAC enforcement on every endpoint (users only see their data)
- ✅ Comprehensive tests (>90% coverage)

**Why this matters:**
- Reference data (status, department, location) is used everywhere
- Org hierarchy determines RBAC (who can see what data)
- Must be rock-solid before Phase 2 frontend is built

---

## 📋 What to Do

### Step 1: Read the TASK File
**File:** `plans/TASK_PHASE1_WEEK1.md`

This file contains **exact** specifications for each day:
- What files to create
- Exact code to write (templates provided)
- Tests that must pass
- Acceptance criteria

**Read carefully.** The file is detailed and non-negotiable.

### Step 2: Follow the Daily Sequence

```
Day 1 (4 hours): MDM ReferenceSet API
  └─ Serializers + Views + Permissions + Routes + Tests

Day 2 (6 hours): MDM OrgUnit API  
  └─ Serializers + Views + Hierarchy Logic + Tests

Days 3-5: (These follow in Week 1 Day 2-5 tasks)
```

**Do NOT skip ahead.** Complete Day 1 fully before starting Day 2.

### Step 3: Execute Each Task

For each task (Task 1.1, 1.2, etc.):

1. **Read** the requirements
2. **Create/modify** the exact file specified
3. **Copy code templates** (provided in TASK file)
4. **Adapt templates** to your understanding
5. **Run tests** specified
6. **Commit to git** with message provided
7. **Report back** before moving to next task

### Step 4: Handle Blockers

If you hit a blocker:

1. **Debug for 5 minutes** (is this really a blocker?)
2. **Check TASK file** (is answer documented?)
3. **Check existing code** (does a similar pattern exist?)
4. **Ask Master** (create detailed blocker description)

Master will respond with clarification within 1 message.

### Step 5: Report Results

After each day completes:

**Create file:** `TASK-RESULT-PHASE1-WEEK1-DAY{1,2,3,4,5}.md`

**Include:**
```markdown
# TASK RESULT: PHASE 1 WEEK 1 DAY 1

## ✅ Completed
- [ ] Task 1.1: ReferenceSetSerializer
- [ ] Task 1.2: ReferenceSetViewSet
- [ ] Task 1.3: Permissions
- [ ] Task 1.4: Routes
- [ ] Task 1.5: Tests

## ❌ Blocked
- [ ] (If any)

## 📊 Metrics
- Tests passing: 8/8
- Coverage: 92%
- Time spent: 4 hours
- Performance: list endpoint <100ms

## 🔗 Git Log
```
git log --oneline -5
```

## 🎯 Next Steps
Ready for Day 2: OrgUnit API

## ❓ Questions for Master
(Any ambiguities encountered?)
```

---

## ⚠️ CRITICAL RULES (NON-NEGOTIABLE)

### Rule 1: RBAC Enforcement
**Every endpoint must enforce user access control.**

✅ **Correct Pattern:**
```python
def get_queryset(self):
    user_orgs = get_user_org_units(self.request.user)
    return ReferenceSet.objects.filter(org_unit__in=user_orgs)

def perform_update(self, serializer):
    if not user_can_edit(self.request.user, obj):
        raise PermissionDenied("403: User not authorized")
```

❌ **Wrong (will be rejected):**
```python
def get_queryset(self):
    return ReferenceSet.objects.all()  # NO! User sees everything!
```

**Principle:** *User from Org A CANNOT see Org B data. Ever.*

### Rule 2: Tests Are Non-Optional
**Every task must include passing tests.**

- Unit tests (serializers, models)
- Integration tests (API endpoints)
- Permission tests (403 on unauthorized)
- Performance tests (benchmarks met)

**Minimum coverage:** 90% for Phase 1 code

### Rule 3: Commit After Each Task
**Not after each day. After each TASK.**

```bash
git commit -m "PHASE1-D1-T1: ReferenceSetSerializer implementation"
git commit -m "PHASE1-D1-T2: ReferenceSetViewSet CRUD endpoints"
git commit -m "PHASE1-D1-T3: RBAC Permission classes"
```

This makes debugging easier if something breaks later.

### Rule 4: Ask Before Deviating
**If TASK file seems unclear or wrong:**

DON'T guess. DON'T improvise. ASK MASTER.

I (Master/Ahmed) will clarify immediately. Better to ask than to build something wrong.

---

## 🛠️ Tech Stack Reference

**Backend:** Django 4.x + DRF + PostgreSQL  
**API Auth:** JWT (JWTAuthentication)  
**ORM:** Django ORM (no raw SQL)  
**Testing:** pytest + DRF's APITestCase  
**Code Style:** PEP 8 (Black formatter)

**Key URLs:**
- Development: http://localhost:8000
- Swagger API Docs: http://localhost:8000/api/v1/swagger/
- Django Admin: http://localhost:8000/api/v1/admin/

---

## 📞 Communication Protocol

### When to Report
- ✅ Each task complete → commit + short status
- ❌ Task blocked → create blocker description → ask Master
- 📊 Day complete → create TASK-RESULT file

### How to Ask Master
**Format for blocker:**

```
🔴 BLOCKER: Task 1.1 - ReferenceSetSerializer

Problem: Unsure if ReferenceValue.code should be unique globally or per ReferenceSet

Context:
- Model shows: unique_together = ('reference_set', 'code')
- Serializer validation unclear
- Tests assume per-set uniqueness

Question: Should I validate at model level or serializer level?

Investigation: Checked existing code at backend/emissions/models.py line 126 (similar pattern)
```

Master responds with answer. Continue.

---

## 🎓 Learning Resources (If Needed)

**DRF Serializers:** https://www.django-rest-framework.org/api-guide/serializers/  
**DRF ViewSets:** https://www.django-rest-framework.org/api-guide/viewsets/  
**DRF Permissions:** https://www.django-rest-framework.org/api-guide/permissions/  
**DRF Testing:** https://www.django-rest-framework.org/api-guide/testing/  

---

## ✨ Success = 5 Days of Green Lights

**Day 1 Green Light:** All ReferenceSet tests pass, RBAC enforced, committed  
**Day 2 Green Light:** All OrgUnit tests pass, hierarchy working, committed  
**Day 3-5 Green Light:** (Similar for DQ, Lineage, etc.)  

**Week 1 Complete:** All 50 hours delivered, all APIs tested, zero data leakage, ready for Phase 2 frontend team

---

## 🚦 Start Now

1. Open `plans/TASK_PHASE1_WEEK1.md`
2. Start with **DAY 1: MDM ReferenceSet Serializers & Views**
3. Follow the exact sequence
4. Run tests after each task
5. Commit after each task
6. Report results when day completes

**I'm here to help if you get stuck. But you've got this. The specs are clear, the requirements are explicit, the tests are written.**

**Go build great code.** 🚀

---

**From:** Zoo (Master/Architect)  
**Status:** APPROVED & READY  
**Next Handoff:** TASK-RESULT-PHASE1-WEEK1-DAY1.md

