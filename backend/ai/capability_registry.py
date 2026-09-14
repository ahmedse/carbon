"""Host-side capability → host-action registry (P3-01).

Single source of truth for resolving a capability contract's ``host_action``
key to a host callable (or the human-task sentinel). Deliberately import-free
(stdlib only) so both :mod:`ai.models.capability` (the loader) and
:mod:`ai.models.process` (the process validator) may import it with no cycle and
no database access at import time.

Registry values are ``"module:qualname"`` paths. They are resolved **lazily**
with :func:`importlib.import_module` by the loader — never here — so this module
never imports ``dq``, ``ai.predicates``, or any Django app at import time.

The human-task sentinel marks capabilities whose effect is a durable human task
(the P3-09 inbox), not a synchronous host callable. The loader recognizes it and
permits it only for ``kind == "human_task"``.
"""

from __future__ import annotations

# Sentinel for human-task capabilities (P3-09 inbox; not a module path).
HUMAN_TASK_SENTINEL = "human_task:inbox"

# host_action key → "module:qualname" (or the human-task sentinel).
HOST_ACTION_REGISTRY: dict[str, str] = {
    # ── DQ pilot (P3-02 / docs/pulse/PILOT.md ``dq.rule.release``) ──────────
    # validate (read-only) → review (human task) → publish (mutation) → verify
    # (assertion). The DQ host today exposes rule-running as its single host
    # service; ``validate`` binds to it as the read-only projection and
    # ``publish`` binds to the same service as the post-approval mutation whose
    # consent gate (RULE_21) lives in the command boundary. A dedicated
    # ``dq.services.publish_rule`` will supersede the publish binding in P3-05a.
    "dq.rule.validate": "dq.services:run_single_rule",
    "dq.rule.publish": "dq.services:run_single_rule",
    "dq.rule.active_revision_matches_approved_revision": (
        "ai.predicates:dq_rule_active_revision_matches_approved_revision"
    ),
    # Human-task sentinel (recognized by the loader, not importable).
    HUMAN_TASK_SENTINEL: HUMAN_TASK_SENTINEL,
}
