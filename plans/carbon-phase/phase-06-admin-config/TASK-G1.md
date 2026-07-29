# TASK-G1 — Phase 06 Admin Configuration: Backend GWP CRUD Enabler

## Summary
GWP (Global Warming Potentials) is currently **ReadOnly** — admins can't add/edit/delete GWP values through the API. Upgrade to full CRUD so the Phase 06 frontend admin page can manage GWP reference data.

---

## Deliverables

### D1 — Upgrade GWPViewSet to full CRUD (views.py, 1 line)

In `backend/emissions/views.py`, change:
```python
class GWPViewSet(viewsets.ReadOnlyModelViewSet):
```
to:
```python
class GWPViewSet(viewsets.ModelViewSet):
```

That's it. The serializer already declares all fields; DRF ModelViewSet provides create/update/partial_update/destroy automatically.

### D2 — (Optional) Verify GWP permission is correct

Current: `AdminOrSuperuserOnly`. Verify this is suitable for write operations (CRUD). If `AdminOrSuperuserOnly` only allows GET, switch to `IsAuthenticated` — but RBAC is out of scope for this task, so just make a note if there's an issue.

### D3 — (Verification) Confirm GWPSerializer fields are complete

Current GWPSerializer:
```python
fields = ['id', 'gas_name', 'gas_formula',
          'gwp_ar5_100yr', 'gwp_ar6_100yr', 'gwp_ar5_20yr', 'gwp_ar6_20yr',
          'cas_number', 'notes']
```

These are all the fields on the model. ✅ No changes needed.

---

## Files to Change

| File | Action |
|------|--------|
| `backend/emissions/views.py` | D1: 1-word change ReadOnlyModelViewSet → ModelViewSet |

---

## DO-NOT-TOUCH

- ❌ No new models, no migrations
- ❌ No serializer changes
- ❌ No URL changes
- ❌ No frontend files
- ❌ No permissions system changes

---

## Verification

```bash
# 1. Django checks
cd backend && python manage.py check

# 2. No unexpected migrations
python manage.py makemigrations --check

# 3. Gateway
cd .. && bash .ai-toolkit/scripts/verify.sh backend

# 4. All tests pass
cd backend && python -m pytest emissions/tests/ -v

# 5. HTTP spot-checks (restart backend first):
./manage.sh restart backend

TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# CREATE (should work now)
curl -s -X POST http://localhost:8009/carbon-api/emissions/gwp/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"gas_name":"Test Gas","gas_formula":"TG","gwp_ar6_100yr":"1.0"}' | python3 -m json.tool

# GET (should still work)
curl -s http://localhost:8009/carbon-api/emissions/gwp/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -15

# DELETE the test gas (note the ID from create response)
curl -s -X DELETE http://localhost:8009/carbon-api/emissions/gwp/<ID>/ \
  -H "Authorization: Bearer $TOKEN"
```

## Success Criteria

- [ ] `python manage.py check` — exit 0
- [ ] `makemigrations --check` — No changes detected
- [ ] `verify.sh backend` — GATE PASSED
- [ ] All 50 emissions tests pass
- [ ] POST /emissions/gwp/ creates a new GWP entry
- [ ] GET /emissions/gwp/ lists all GWP entries (including new one)
- [ ] DELETE /emissions/gwp/{id}/ removes the entry
- [ ] Only 1 file changed
