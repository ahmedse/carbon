"""
dq/workflows.py — Declarative DQ job workflow specs (Phase 24-E).

De-hardcodes the if/elif dispatch in ``dq/jobs.py``: every job type
(rule_run / profile / freshness / schema / nl_check / suggest / anomaly) is
now a *spec row*, not a dispatcher branch. The runner resolves handlers by
name at call time, so adding a job type = one spec row + one handler
function — the dispatcher is never touched again (ADR-0008: "a new workflow
= a spec, not an app").

Spec shape (all keys optional unless noted):
    kind            'deterministic' | 'pulse'        (required)
    requires        list of view-validated refs: 'rule' | 'table'
    needs_prompt    True if the pulse submit handler requires a prompt
                    (validated inside the handler — prompt may come from the
                    rule definition, so the view cannot pre-check it)
    run             handler name for deterministic jobs
    submit          submit handler name for pulse jobs
    on_completed    result-persistence handler name for pulse jobs
    on_failed       fail-visible handler name for pulse jobs
    label           human-readable label for the workflow

Handlers are resolved via :func:`resolve_handler` against the owning module
(``dq.jobs``) by name at call time — tests that patch a handler on the jobs
module keep working (no captured references in the specs).

No model imports (mirrors ``dq/catalog.py``): importable at module load
time without a database.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

__all__ = [
    'WORKFLOW_SPECS',
    'get_workflow',
    'has_workflow',
    'list_workflows',
    'workflow_requires',
    'workflow_needs_prompt',
    'validate_job_payload',
    'resolve_handler',
]

# ── Workflow specs ─────────────────────────────────────────────────────────
# key = job_type value on DQJob. Handlers are *names* resolved at dispatch
# time from the dq.jobs module namespace.
WORKFLOW_SPECS: Dict[str, Dict[str, Any]] = {
    'rule_run': {
        'kind': 'deterministic',
        'requires': ['rule'],
        'run': '_run_rule_job',
        'label': 'Rule Run',
    },
    'profile': {
        'kind': 'deterministic',
        'requires': ['table'],
        'run': '_run_profile_job',
        'label': 'Profile',
    },
    'freshness': {
        'kind': 'deterministic',
        'requires': ['table'],
        'run': '_run_freshness_job',
        'label': 'Freshness',
    },
    'schema': {
        'kind': 'deterministic',
        'requires': ['table'],
        'run': '_run_schema_job',
        'label': 'Schema',
    },
    'nl_check': {
        'kind': 'pulse',
        'requires': ['rule'],
        'needs_prompt': True,
        'submit': '_submit_nl_check_job',
        'on_completed': '_write_nl_check_results',
        'on_failed': '_write_skipped_result',
        'label': 'NL Check',
    },
    'suggest': {
        'kind': 'pulse',
        'requires': ['table'],
        'submit': '_submit_suggest_job',
        'on_completed': '_persist_suggestions',
        'label': 'Suggest',
    },
    'anomaly': {
        'kind': 'pulse',
        'requires': ['table'],
        'submit': '_submit_anomaly_job',
        'on_completed': '_write_anomaly_results',
        'label': 'Anomaly',
    },
}


def get_workflow(job_type: str) -> Dict[str, Any]:
    """Return the workflow spec for ``job_type`` (raises ValueError)."""
    spec = WORKFLOW_SPECS.get(job_type)
    if spec is None:
        raise ValueError(
            f'Unknown job_type: {job_type!r}. '
            f'Registered workflows: {sorted(WORKFLOW_SPECS)}'
        )
    return spec


def has_workflow(job_type: str) -> bool:
    """True if ``job_type`` has a registered workflow spec."""
    return job_type in WORKFLOW_SPECS


def list_workflows() -> List[str]:
    """Return all registered workflow job_type codes (sorted)."""
    return sorted(WORKFLOW_SPECS)


def workflow_requires(job_type: str) -> List[str]:
    """Return the list of refs ('rule'/'table') a job type needs."""
    return list(get_workflow(job_type).get('requires', []))


def workflow_needs_prompt(job_type: str) -> bool:
    """True if the workflow's pulse submit handler requires a prompt."""
    return bool(get_workflow(job_type).get('needs_prompt', False))


def resolve_handler(name: str, module: Any) -> Any:
    """Resolve a spec handler name to a callable on ``module``.

    Looked up at call time (not captured in the spec) so ``unittest.mock``
    patches on the owning module take effect during tests.
    """
    handler = getattr(module, name, None)
    if handler is None:
        raise ValueError(f'Workflow handler {name!r} not found on {module.__name__}')
    return handler


def validate_job_payload(
    job_type: str, *, rule: Any = None, table: Any = None,
) -> Tuple[bool, str]:
    """Validate a payload against the workflow spec's required refs.

    Replaces the hardcoded ``if job_type in ('rule_run', 'nl_check') ...``
    checks in ``dq/views.py``: the requirements now live in the spec, so a
    new job type only declares its needs there. Prompt needs are validated
    inside the submit handler (the prompt may come from the rule definition).
    """
    spec = get_workflow(job_type)
    for ref in spec.get('requires', []):
        if ref == 'rule' and rule is None:
            return False, f'{job_type} job requires rule_id'
        if ref == 'table' and table is None:
            return False, f'{job_type} job requires data_table_id'
    return True, ''
