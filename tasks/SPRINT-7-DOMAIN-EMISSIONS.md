# Sprint 7 — ai/domain/emissions.py: GHG Vocabulary

**Status:** Ready for Backend Worker
**Workers:** Backend Worker (DeepSeek-V3) — single worker, backend-only
**Contract:** `.ai-toolkit/shared/ai-contract.md §8`
**Duration:** 3 days

---

## Goal

AI knows GHG Protocol vocabulary, scope 1/2/3, and emission factors. When a user
asks the AI anything in the **emissions** domain, the system prompt is enriched
with domain vocabulary so the AI answers in correct carbon-accounting terms
(tCO2e, AR6 GWP, location-based vs market-based, operational boundary, etc.).

This is backend-only. No frontend, no migrations, no new DB fields.

---

## Background (read these first)

1. `backend/ai/domain_protocol.py` — the `DomainAIOperations` ABC + `DomainContext`
   dataclass + `register_domain()` / `get_domain()` / `has_domain()` / `list_domains()`.
2. `backend/ai/domain/__init__.py` — currently empty (only docstring).
3. `backend/ai/intelligence.py` — `CarbonIntelligence` class. Injection target.
4. `.ai-toolkit/shared/ai-contract.md §8` — domain registration rules.

The **frontend already sets `app_identifier="emissions"`** for emissions pages
(see `carbon-frontend/src/shell/aiTaskTransferUtils.js` → `normalizeAppIdentifier`,
which maps `/emissions…` source pages to `"emissions"`). `CarbonIntelligence.send_message`
already copies `conversation.app_identifier` onto `scope.app_identifier`. So the
backend just needs to *consume* `scope.app_identifier` — no frontend change.

---

## Task 7-A — Implement `backend/ai/domain/emissions.py` (NEW file)

Create `backend/ai/domain/emissions.py`:

```python
"""Carbon AI Intelligence — Emissions (Carbon Footprint) Domain.

AI CONTRACT §8: domain-specific AI operations for the emissions app.
"""

from __future__ import annotations

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class EmissionsDomainAI(DomainAIOperations):
    """Emissions (carbon footprint) domain AI operations."""

    app_identifier = "emissions"
    app_display_name = "Carbon Footprint"

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="emissions",
            domain_knowledge={
                "protocol": "GHG Protocol Corporate Standard",
                "scopes": {
                    "scope_1": "Direct emissions from owned/controlled sources",
                    "scope_2": "Indirect emissions from purchased energy",
                    "scope_3": "All other indirect emissions in value chain",
                },
                "ar_version": "IPCC AR6",
                "units": ["tCO2e", "kgCO2e", "MtCO2e"],
                "calculation_methods": ["location-based", "market-based"],
            },
            domain_config={
                "default_gwp_version": "AR6",
                "boundary_approaches": ["operational", "equity share", "financial control"],
            },
        )


register_domain("emissions", EmissionsDomainAI)
```

Rules:
- `app_identifier` and `app_display_name` are class attributes (per §8 examples).
- `get_domain_context()` must return the exact shape above.
- `register_domain("emissions", EmissionsDomainAI)` at the bottom of the module.
- Do NOT import from `emissions` app models. Do NOT import other domain modules.
- No new DB fields, no migrations.

---

## Task 7-B — Inject domain context into emissions AI calls

Edit `backend/ai/intelligence.py`:

1. Add module-level imports at the top:
   ```python
   from ai.domain_protocol import DomainContext, get_domain, has_domain
   from ai.domain import emissions  # noqa: F401  (registers the emissions domain)
   ```
   (verify the existing import block; add only what is missing — do not
   duplicate an existing import.)

   > ⚠️ **CRITICAL — module naming.** The repo is importable under two names
   > (`ai.*` AND `backend.ai.*`), but they are **DIFFERENT module objects with
   > DIFFERENT registries**. `ai.domain_protocol._DOMAIN_REGISTRY` is NOT
   > `backend.ai.domain_protocol._DOMAIN_REGISTRY`. To keep `register_domain`
   > (in `emissions.py`) and `has_domain`/`get_domain` (in `intelligence.py`)
   > on the **same registry**, BOTH files MUST use the exact prefix
   > `from ai.domain_protocol import …` (NOT `backend.ai.domain_protocol`).
   > The `from ai.domain import emissions` line above is what actually runs
   > `register_domain("emissions", …)`; without it `has_domain("emissions")`
   > is always `False`. Do not "fix" these to `backend.ai.*`.

2. Add a helper method on `CarbonIntelligence`:

   ```python
   def _prepend_domain_context(self, scope: Scope, content: str) -> str:
       """Inject domain context (GHG vocabulary, etc.) when scope.app_identifier
       maps to a registered domain. AI CONTRACT §8: platform-level injection.

       NEVER crashes on missing/unregistered/malformed domain — returns
       content unchanged in every failure path.
       """
       if not scope or not getattr(scope, "app_identifier", None):
           return content
       if not has_domain(scope.app_identifier):
           return content
       try:
           ctx = get_domain(scope.app_identifier)().get_domain_context()
       except Exception:
           return content
       prefix = _domain_context_prompt_prefix(ctx)
       if not prefix:
           return content
       return f"{prefix}\n\n{content}"
   ```

3. Add a module-level renderer near the other module-level helpers:

   ```python
   def _domain_context_prompt_prefix(ctx: DomainContext) -> str:
       """Render a DomainContext into a compact system-prompt prefix."""
       lines = [f"[Domain: {ctx.app_identifier}]"]
       knowledge = ctx.domain_knowledge or {}
       config = ctx.domain_config or {}
       if knowledge.get("protocol"):
           lines.append(f"Protocol: {knowledge['protocol']}")
       scopes = knowledge.get("scopes") or {}
       if scopes:
           lines.append("Scopes:")
           for key, desc in scopes.items():
               lines.append(f"  - {key}: {desc}")
       if knowledge.get("ar_version"):
           lines.append(f"GWP version: {knowledge['ar_version']}")
       if knowledge.get("units"):
           lines.append(f"Units: {', '.join(knowledge['units'])}")
       if knowledge.get("calculation_methods"):
           lines.append(
               f"Calculation methods: {', '.join(knowledge['calculation_methods'])}"
           )
       if config:
           for key, value in config.items():
               if isinstance(value, list):
                   lines.append(f"{key}: {', '.join(value)}")
               else:
                   lines.append(f"{key}: {value}")
       if len(lines) == 1:
           return ""
       return "\n".join(lines)
   ```

4. Wire it into `_send_chat_message`. Locate the line:
   ```python
   message = self._prepend_workspace_context(conversation, content)
   ```
   and add immediately after it:
   ```python
   message = self._prepend_domain_context(scope, message)
   ```
   (Domain context is applied AFTER workspace context; the order is
   workspace context → domain context → user content.)

Notes:
- The injection is **general**: it works for any registered domain via
  `get_domain(scope.app_identifier)`, NOT emissions-specific. `"emissions"`
  is simply the first registered domain.
- The injection is **prompt-only**. Domain context is NOT a security boundary —
  `Scope` remains the security boundary (ai-contract §11.4).

---

## Task 7-C — Tests: `backend/ai/tests/test_domain_emissions.py` (NEW, ≥10 tests)

Create `backend/ai/tests/test_domain_emissions.py` with **at least 10** tests.

Imports (mirror `test_workspace_context.py`, all `ai.*` for domain):
```python
from ai.domain.emissions import EmissionsDomainAI
from ai.domain_protocol import (
    get_domain, has_domain, list_domains, register_domain,
)
from ai.intelligence import CarbonIntelligence
from backend.ai.protocol import ChatResponse, ConversationContext, Scope
```

Registration & lookup (pure, no DB — importing `ai.domain.emissions` already
runs `register_domain`; importing `ai.intelligence` also triggers it, so the
registry is populated exactly once — do NOT import these under `backend.ai.*`):
1. `test_emissions_domain_registered` — `has_domain("emissions")` is `True`.
2. `test_get_domain_returns_emissions_class` — `get_domain("emissions")` is
   `EmissionsDomainAI`.
3. `test_get_domain_unknown_raises_keyerror` — `get_domain("nope")` raises `KeyError`.
4. `test_list_domains_includes_emissions` — `"emissions" in list_domains()`.
5. `test_duplicate_registration_raises` — `register_domain("emissions",
   EmissionsDomainAI)` raises `ValueError`.

DomainContext content:
6. `test_app_identifier_and_display_name` — `EmissionsDomainAI.app_identifier ==
   "emissions"` and `.app_display_name == "Carbon Footprint"`.
7. `test_domain_context_knowledge_shape` — `ctx.domain_knowledge["protocol"]`,
   `ctx.domain_knowledge["scopes"]` has `scope_1/scope_2/scope_3`, `ar_version`,
   `units`, `calculation_methods` all present with expected values.
8. `test_domain_context_config_shape` — `ctx.domain_config["default_gwp_version"]
   == "AR6"` and `boundary_approaches` has 3 entries.

Injection tests use `Scope` from `backend.ai.protocol` (NOT `ai.protocol`) so the
`Scope` object matches what `ai.intelligence` actually uses:
9. `test_prepend_domain_context_emissions` — `ci._prepend_domain_context(Scope(app_identifier="emissions"), "hello")`
   starts with `"[Domain: emissions]"` and contains "GHG Protocol Corporate Standard".
10. `test_prepend_domain_context_no_app_identifier` — `Scope()` (no app_identifier)
    returns `"hello"` unchanged.
11. `test_prepend_domain_context_unknown_domain` — `Scope(app_identifier="water")`
    returns `"hello"` unchanged (no crash).
12. `test_chat_message_injects_domain_context` — call `ci._send_chat_message(...)`
    with a conversation whose `app_identifier="emissions"` and a
    `Scope(app_identifier="emissions")`, then assert `provider.chat.call_args[0][0].message`
    contains `"[Domain: emissions]"`.

Use the exact seam from `test_workspace_context.py` (`test_send_chat_message_prepends_context_prefix`):
```python
provider = MagicMock()
provider.provider_name = "dummy"
provider.chat.return_value = ChatResponse(status="completed", content="ok")
ci = CarbonIntelligence()
ci._provider = provider
ci._guard_workspace_operation = MagicMock(return_value=(MagicMock(), "workspace_chat"))
ci._send_chat_message(conversation, "hello", ConversationContext(conversation_id=str(conversation.id)), Scope(app_identifier="emissions"))
sent = provider.chat.call_args[0][0]   # a ChatRequest
```

---

## DO NOT TOUCH

- `backend/ai/protocol.py` — the platform ABC. Domain work is in `ai/domain/`.
- `backend/ai/guards.py` — security is automatic.
- `backend/ai/domain_protocol.py` — the ABC + registry already exist; reuse them.
- Frontend files — this sprint is backend-only.
- `backend/ai/domain/water.py` / `waste.py` — future domains.
- No migrations, no new model fields.

## HARD RULES

- Core apps never import `emissions` app code (and vice versa). The domain
  module lives in `ai/domain/` and imports only from `ai.domain_protocol`.
- Missing/unregistered/malformed domain context must NEVER crash — every failure
  path returns the content unchanged.
- No hardcoded secrets; no naive datetimes; no `print()` debugging.
- Use `django.utils.timezone.now()` where time is needed (not required here).

## GATES (all must pass before REPORT BACK)

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_domain_emissions.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai dq accounts -q
```

Do NOT run `manage.py test` (fails with a conflicting-model error unrelated to
this sprint). Use the pytest runner above.

## REPORT BACK

Report, in order:
1. Files created/modified (exact paths).
2. Each gate command + its exact pass/fail count (e.g. `759 passed`).
3. Any deviation from this spec and why.
4. Confirmation that `git status` shows ONLY your sprint's files.
