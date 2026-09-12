## Hotfix vs Proper Fix

| Situation | Hotfix | Proper Fix |
|-----------|--------|------------|
| Production is broken NOW | `docker cp` + `docker restart` | Rebuild image |
| Single file fix | `docker cp` | Commit + rebuild |
| Config change | Update env var, restart | Validate in staging first |
| DB data fix | Run migration or management command | Never manual SQL in prod |

**Hotfix is always temporary.** Always follow up with a proper fix ticket in TASKS.md.

### After Every Hotfix
1. Log it in TASK-RESULTS.md under "Hotfixes Applied"
2. Create a follow-up TASKS.md entry for the proper fix
3. Verify the hotfix is actually running: `docker exec <CONTAINER> grep -c "<marker>" /app/<file>`

---

*Source: ~/ai-toolkit/universal/rules/hotfix-vs-proper.md*
