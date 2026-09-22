# ADR-0044 — Nibras dual-catalog SSOT (pack ↔ instance)

**Status:** Accepted  
**Date:** 2026-09-21  
**Context:** Nibras Agent tools vs domain-pack governance catalogs drifted (GOSI tools in pack only; loan/onboarding tools in instance only). Deep sim could PASS while Agent plans failed tool bind.

## Decision

1. **Live Agent SSOT** is `backend/ai/engine/instances/nibras/instance.yaml` `api_catalog`.
2. **Governance pack** `domain_packs/nibras/api_catalog.yaml`:
   - `capabilities:` own process fail-closed contracts (registry)
   - `tools:` must be a **subset** of instance api_catalog names
3. CI drift test `ai/tests/test_nibras_catalog_parity.py` fails when pack tools are missing from instance.
4. GOSI/WPS uses **distinct** host paths: generate → validate → submit (persisted `WpsFiling`), not a second WPS CSV download.

## Consequences

- Adding an Agent-callable host API: update **instance.yaml first**, then pack `tools:` (+ capability if governed).
- Pack-only tool names without instance entries are forbidden.
- Operators prove Chat·Plan·Run via `simulate_nibras_operator_processes` + deep sim.

## Links

- [domain_packs/nibras/README.md](../../domain_packs/nibras/README.md)
- [instance.yaml](../../backend/ai/engine/instances/nibras/instance.yaml)
- ADR-0017 (instance.yaml prompt config), ADR-0043 (four-view cockpit)
