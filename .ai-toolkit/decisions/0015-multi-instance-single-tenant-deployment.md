# ADR-0015 — Multi-instance single-tenant deployment model

- **Status:** Accepted
- **Date:** 2026-08-22
- **Deciders:** Master Architect
- **Area:** deploy + backend (cross-cutting)

## Context

The platform must serve multiple organisations — AASTMT, Nibras, and Healthy Foods —
each with its own domain apps, data, and branding. The two obvious answers are both
wrong:

- **Forking the repo (3 repos)** → code drift, every bug fix applied 3×, eventual
  corruption. The platform is still under active development, so this would be the
  worst time to fork.
- **Multi-tenancy (`tenant_id` on every model)** → explicitly banned. RULE_1 ("Tenant
  model/code is FULLY removed"), DESIGN-PLATFORM §7.1 ("no multi-tenancy, one
  deployment = one organisation"), and the Pulse engine is single-tenant
  (`app_identifier='carbon'`, `host_user_id`). The team deliberately migrated AWAY from
  Tenant/Project (accounts migrations 0001→0006, core migration 0004).

The model must keep a single upstream (still under development) while giving each org
provable data isolation.

## Decision

Deploy **one codebase, N isolated deployments** (cell-based / siloed single-tenant):

1. **One repo, one Docker image.** All domain apps live in the single codebase. A bug
   fix lands once and reaches every deployment on next release.
2. **One isolated database per org.** No `tenant_id` anywhere. Isolation is a database
   boundary, not a `WHERE` clause — the strongest guarantee a data-trust product can
   give (RULE_20 exists precisely because cross-tenant leakage is the failure mode).
3. **Per-instance config is env-only** — `DJANGO_INSTANCE_NAME` (branding), DB creds,
   domain, port. Already env-driven in `config/settings.py` (`PLATFORM_TITLE`) and
   mirrored by frontend `VITE_*` branding.
4. **The app activation set is the only per-instance difference.** `appregistry` already
   supports "same code, different apps": each deployment activates its `AppManifest`
   subset via the `activate_apps` management command. AAST → people+emissions, Healthy →
   healthy, Nibras → nibras apps. System apps (is_system=True) stay active everywhere.
5. **The deploy kit is a template.** `deploy/carbon/` is one instantiation of the
   generic `deploy/instance/` template. New orgs are stamped via `stamp-instance.sh`,
   never by forking the repo.

## Alternatives Considered

- **Fork the repo per org** — rejected: code drift, triple maintenance, divergence.
- **Multi-tenancy (`tenant_id`)** — rejected: RULE_1; would require threading tenancy
  through the Pulse engine (KG, embeddings, memory, six-witness pipeline) — a massive,
  leak-prone rewrite for no benefit at 3 orgs.

## Consequences

- **Positive:** provable per-org data isolation; single upstream (no drift); branding and
  app activation are config, not code; new org = new deployment, not new repo.
- **Negative / trade-off:** N databases to back up/monitor; no cross-org analytics in one
  query (by design — a feature for a trust product); per-instance infra management.
- **Do NOT re-try:** `tenant_id`/multi-tenancy, Tenant/Project models, forking the repo,
  cross-org data sharing in a single database.

## References

- `.ai-toolkit/project.config.md` — RULE_1 (no tenant), RULE_20 (no cross-app leakage)
- `docs/DESIGN-PLATFORM.md §7.1` — "no multi-tenancy"
- `backend/appregistry/models.py` — AppManifest / AppActivation
- `backend/appregistry/management/commands/activate_apps.py` — per-instance activation
- `deploy/instance/` — parameterized deploy template + stamp/deploy scripts
- `backend/config/settings.py` — `INSTANCE_NAME` / `PLATFORM_TITLE` env branding
