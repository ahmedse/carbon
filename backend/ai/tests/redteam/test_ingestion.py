"""PATH 6 — INGESTION mutation attempts (ops workflow confirmation gate).

The ops workflow never mutates host data without confirmation: real writes
stage a ``pending_confirmation`` execution instead of being sent, the default
is a dry run, validation is a hard gate, and config/identity errors fail
closed before any host write.
"""

from __future__ import annotations

import asyncio
import types

import pytest

from ai.engine.ingestion.ops_workflow import OpsWorkflowError, OpsWorkflowRunner, StepResult

# ── Shared fixtures (offline) ─────────────────────────────────────────────

CATALOG = {
    "list_datasets": {"method": "GET", "path": "/api/datasets"},
    "get_dataset": {"method": "GET", "path": "/api/datasets/{id}"},
    "bulk_write_records": {"method": "POST", "path": "/api/datasets/{id}/records"},
    "trigger_inference": {"method": "POST", "path": "/api/engines/{id}/infer"},
    "get_daily_summaries": {"method": "GET", "path": "/api/engines/{id}/summaries"},
    "list_ai_engines": {"method": "GET", "path": "/api/engines"},
}

DATASET_DETAIL = {
    "fields_schema": {"temperature": {"type": "float", "min": 0, "max": 100}},
    "is_managed": False,
}

CSV = "datetime,temperature\n2024-01-01 00:00:00,21.5\n2024-01-02 00:00:00,22.0\n"

WF = {
    "name": "ops",
    "dataset": "123",
    "engine": "7",
    "api": {"bulk_write": "bulk_write_records",
            "trigger_inference": "trigger_inference"},
}


def _config(workflows=None, dataset_detail=None):
    return {
        "ops_workflows": workflows if workflows is not None else [dict(WF)],
        "api_catalog": CATALOG,
    }, (dataset_detail if dataset_detail is not None else dict(DATASET_DETAIL))


class FakeExecutor:
    def __init__(self, dataset_detail):
        self.dataset_detail = dataset_detail
        self.calls: list[tuple] = []
        self.pending: list[tuple] = []

    def get_catalog_entry(self, api_name):
        return CATALOG.get(api_name)

    async def call_api_direct(self, method, path, params=None, body=None):
        self.calls.append((method, path, params, body))
        if path == "/api/datasets":
            return {"data": [{"id": 123, "name": "ops"}]}
        if "/records" in path:
            return {"data": {"processed": 1}}
        if "/summaries" in path:
            return {"data": []}
        if "/infer" in path:
            return {"data": {"model_version": "v1"}}
        if "/datasets/" in path:
            return {"data": self.dataset_detail}
        return {"data": []}

    async def create_pending_execution(self, **kwargs):
        eid = f"exec-{len(self.pending) + 1}"
        self.pending.append((eid, kwargs))
        return types.SimpleNamespace(id=eid)


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


def _runner(executor=None, db=None, workflows=None, dataset_detail=None):
    config, detail = _config(workflows, dataset_detail)
    return OpsWorkflowRunner(
        db=db or FakeDB(),
        instance_id="redteam-instance",
        instance_config=config,
        executor=executor or FakeExecutor(detail),
        host_user_id="redteam-user",
        conversation_id="conv-1",
    ), executor


# ── Attempts ──────────────────────────────────────────────────────────────


def test_ingestion_01_real_write_without_confirm_is_pending():
    """A real bulk write (dry_run=False) without confirm never reaches the host."""
    executor = FakeExecutor(DATASET_DETAIL)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    result = asyncio.run(runner.ingest_csv(WF, CSV, dry_run=False, confirm=False))

    assert result.status == "pending_confirmation"
    assert result.data["wrote"] is False
    assert "execution_id" in result.data
    # The real write (params=None) was never sent; only the dry-run validation
    # (params={"dry_run":"true"}) reached the host.
    real_writes = [c for c in executor.calls if "/records" in c[1] and c[2] is None]
    assert real_writes == []


def test_ingestion_02_inference_without_confirm_is_pending():
    executor = FakeExecutor(DATASET_DETAIL)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    result = asyncio.run(runner.run_inference(WF, confirm=False))

    assert result.status == "pending_confirmation"
    assert "execution_id" in result.data
    assert not any("/infer" in c[1] for c in executor.calls)


def test_ingestion_03_full_run_without_confirm_needs_input():
    executor = FakeExecutor(DATASET_DETAIL)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    out = asyncio.run(runner.run(CSV, dry_run=False, confirm=False))

    assert out["status"] == "needs_input"
    assert out["needs_confirmation"] != []


def test_ingestion_04_default_dry_run_never_writes():
    executor = FakeExecutor(DATASET_DETAIL)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    out = asyncio.run(runner.run(CSV))  # dry_run defaults True

    assert out["status"] == "completed"
    assert out["dry_run"] is True
    # No pending execution and no real write.
    assert executor.pending == []
    assert not any("/records" in c[1] and c[2] is None for c in executor.calls)


def test_ingestion_05_managed_dataset_is_rejected():
    detail = dict(DATASET_DETAIL, is_managed=True)
    executor = FakeExecutor(detail)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    result = asyncio.run(runner.ingest_csv(WF, CSV, dry_run=False, confirm=True))

    assert result.status == "failed"
    assert "managed" in result.summary.lower()


def test_ingestion_06_dataset_without_schema_is_rejected():
    detail = {"is_managed": False}  # no fields_schema
    executor = FakeExecutor(detail)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    result = asyncio.run(runner.ingest_csv(WF, CSV))

    assert result.status == "failed"
    assert "fields_schema" in result.summary.lower()


def test_ingestion_07_unknown_dataset_name_is_rejected():
    executor = FakeExecutor(DATASET_DETAIL)
    wf = dict(WF, dataset="nonexistent")  # non-numeric → resolved by name
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    result = asyncio.run(runner.ingest_csv(wf, CSV))

    assert result.status == "failed"
    assert "not found" in result.summary.lower()


def test_ingestion_08_no_ops_workflows_config_raises():
    executor = FakeExecutor(DATASET_DETAIL)
    config = {"api_catalog": CATALOG}  # no ops_workflows
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=config,
        executor=executor, host_user_id="u",
    )

    with pytest.raises(OpsWorkflowError, match="No ops_workflows"):
        runner.get_workflow()


def test_ingestion_09_unknown_workflow_name_raises():
    executor = FakeExecutor(DATASET_DETAIL)
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=executor, host_user_id="u",
    )

    with pytest.raises(OpsWorkflowError, match="Unknown ops workflow"):
        asyncio.run(runner.run(CSV, workflow_name="nope"))


def test_ingestion_10_validation_gate_blocks_failed_ingest():
    runner = OpsWorkflowRunner(
        db=FakeDB(), instance_id="i", instance_config=_config()[0],
        executor=FakeExecutor(DATASET_DETAIL), host_user_id="u",
    )

    failed_ingest = StepResult("ingest_csv", "failed", "boom", errors=["boom"])
    result = runner.validate(WF, failed_ingest)

    assert result.status == "failed"
    assert result.errors == ["boom"]
