"""Query-key bind: a placeholder is unbound; latest_by fills it."""
from types import SimpleNamespace

from ai.engine.cognition.plan.bindings import declare_bindings, resolve_bindings


class _Surface:
    writes = frozenset()

    def __init__(self):
        self._entries = {
            "list_payroll_runs": {
                "name": "list_payroll_runs",
                "kind": "list",
                "latest_by": "period_end",
                "returns": ["id", "period_end", "status"],
                "path": "/payroll-runs/",
            },
            "analyze_gosi_committed": {
                "name": "analyze_gosi_committed",
                "path": "/gosi-summary/",
                "parameters": {
                    "type": "object",
                    "required": ["period_end", "dimension"],
                    "properties": {
                        "period_end": {"type": "string"},
                        "dimension": {"type": "string"},
                    },
                },
            },
        }

    def entry(self, name):
        return self._entries.get(name)

    def schema(self, name):
        params = (self.entry(name) or {}).get("parameters")
        return params if isinstance(params, dict) else None

    def path_keys(self, name):
        return set()

    def missing_path_keys(self, name, args):
        return []

    def supplied_by(self, name):
        entry = self.entry(name) or {}
        keys = {str(item) for item in (entry.get("returns") or []) if item}
        latest = str(entry.get("latest_by") or "").strip()
        if latest:
            keys.add(latest)
        return keys


def _step(step_id, api, *, args=None, depends_on=None):
    return SimpleNamespace(
        step_id=step_id,
        tool_name="call_host_api",
        tool_args={"api_name": api, **(args or {})},
        depends_on=depends_on or [],
    )


def test_placeholder_query_is_unbound_and_latest_fills():
    listing = _step(0, "list_payroll_runs")
    analyze = _step(
        1,
        "analyze_gosi_committed",
        args={
            "query_params": {
                "dimension": "nationality",
                "period_end": "[PLACEHOLDER: select period_end from payroll run or specify YYYY-MM-DD]",
            },
        },
        depends_on=[0],
    )
    surface = _Surface()
    declare_bindings(analyze, {0: listing, 1: analyze}, surface)
    bind = (analyze.tool_args or {}).get("bind") or {}
    assert bind["period_end"]["field"] == "period_end"
    assert bind["period_end"]["select"] == "latest"
    assert bind["period_end"]["step"] == 0

    result = resolve_bindings(
        analyze.tool_args,
        surface,
        {
            0: {
                "data": {
                    "results": [
                        {"id": 57, "period_end": "2026-07-31", "status": "committed"},
                        {"id": 56, "period_end": "2026-08-31", "status": "committed"},
                    ]
                }
            }
        },
        {0: "list_payroll_runs", 1: "analyze_gosi_committed"},
    )
    assert result.status == "bound"
    assert result.tool_args["query_params"]["period_end"] == "2026-08-31"
