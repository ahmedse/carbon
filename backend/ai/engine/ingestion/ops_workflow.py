"""
Autonomous ops-workflow runtime.

Drives the full ``ingest_csv → validate → run_inference → produce_ops_output``
sequence as discrete, individually-callable steps. Pulse acts **as the
authenticated user**, working entirely through the host's REST APIs (it never
writes the host DB directly and owns no host data of its own).

Design goals (the "living, resilient, reproducible" part):
  * Each step is independently callable and returns a structured
    :class:`StepResult` (status, summary, data, errors) — no hidden coupling.
  * Validation is a hard **gate**: a failed validation stops the workflow and
    surfaces *needs_input* rather than guessing.
  * Mutations (the real bulk write, triggering inference) go through the host's
    confirmation flow — dry-run is the read-only twin of the same code path.
  * Every run records a full provenance ledger row (:class:`core.models.OpsRun`)
    so it can be audited and reproduced.

Everything host-specific (dataset, engine, which columns are external, the API
names for each step) comes from the instance's declarative ``ops_workflows``
config — so the *same* runtime generalises to any host and any ops workflow.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ai.engine.core.clock import utcnow
from ai.engine.core.models import OpsRun, generate_uuid
from ai.engine.ingestion.csv_loader import FieldSchema, LoadResult, load_csv

logger = logging.getLogger("pulse.ingestion.ops_workflow")

# Validation thresholds (overridable per-workflow via config).
_DEFAULT_MAX_SKIP_RATIO = 0.5   # > 50% rows skipped → stop and ask


@dataclass
class StepResult:
    """Outcome of a single workflow step."""

    step: str
    status: str                       # ok | needs_input | failed | pending_confirmation
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "status": self.status,
            "summary": self.summary,
            "errors": self.errors,
            # data may carry large payloads; keep a compact view in the trail
            "data_keys": sorted(self.data.keys()),
        }


class OpsWorkflowError(Exception):
    """Raised for unrecoverable workflow configuration errors."""


class OpsWorkflowRunner:
    """Executes a declarative ops workflow for one instance, as one user.

    Parameters
    ----------
    db:
        Pulse SQLAlchemy async session (for the provenance ledger).
    instance_id:
        Pulse instance id.
    instance_config:
        Parsed instance config dict (contains ``ops_workflows`` + ``api_catalog``).
    executor:
        A :class:`agent.executor.HostAPIExecutor` bound to the user's host token.
    host_user_id:
        The authenticated host user (for tenancy on the ledger row).
    conversation_id:
        Optional conversation id, used when a mutation needs confirmation.
    """

    def __init__(
        self,
        db,
        instance_id: str,
        instance_config: dict,
        executor,
        host_user_id: str | None = None,
        conversation_id: str = "",
    ):
        self.db = db
        self.instance_id = instance_id
        self.config = instance_config or {}
        self.executor = executor
        self.host_user_id = host_user_id
        self.conversation_id = conversation_id

    # ── workflow resolution ──────────────────────────────────────────────

    def get_workflow(self, name: str | None = None) -> dict:
        """Return the named workflow spec (or the first one) from config."""
        workflows = self.config.get("ops_workflows") or []
        if not workflows:
            raise OpsWorkflowError(
                "No ops_workflows defined for this instance. Add an 'ops_workflows' "
                "section to the instance config."
            )
        if name:
            for wf in workflows:
                if wf.get("name") == name:
                    return wf
            raise OpsWorkflowError(f"Unknown ops workflow: {name!r}")
        return workflows[0]

    # ── host helpers ─────────────────────────────────────────────────────

    def _path(self, api_name: str, path_params: dict | None = None) -> tuple[str, str]:
        """Resolve an api_name from the catalog to ``(method, path)``."""
        entry = self.executor.get_catalog_entry(api_name)
        if not entry:
            raise OpsWorkflowError(f"API endpoint {api_name!r} not in catalog")
        method = entry["method"]
        path = entry["path"]
        for k, v in (path_params or {}).items():
            path = path.replace(f"{{{k}}}", str(v))
        return method, path

    async def _resolve_dataset_id(self, wf: dict) -> tuple[str, dict]:
        """Resolve the workflow's dataset to a host id and return its detail.

        Accepts a numeric/string id or a dataset name; matches by name against
        ``list_datasets`` when needed. Returns ``(dataset_id, dataset_detail)``.
        """
        ds_ref = str(wf.get("dataset", "")).strip()
        if not ds_ref:
            raise OpsWorkflowError("Workflow has no 'dataset' configured")

        api = wf.get("api", {})
        list_api = api.get("list_datasets", "list_datasets")
        get_api = api.get("get_dataset", "get_dataset")

        # If not obviously an id, resolve name → id via list endpoint.
        dataset_id = ds_ref
        if not ds_ref.isdigit():
            method, path = self._path(list_api)
            listing = await self.executor.call_api_direct(method, path)
            items = _extract_items(listing)
            match = next(
                (
                    it for it in items
                    if str(it.get("name")) == ds_ref
                    or str(it.get("display_name")) == ds_ref
                    or str(it.get("id")) == ds_ref
                ),
                None,
            )
            if not match:
                raise OpsWorkflowError(
                    f"Dataset {ds_ref!r} not found among the user's datasets"
                )
            dataset_id = str(match.get("id"))

        method, path = self._path(get_api, {"id": dataset_id})
        detail = await self.executor.call_api_direct(method, path)
        return dataset_id, _unwrap(detail)

    # ── STEP 1: ingest ───────────────────────────────────────────────────

    async def ingest_csv(
        self,
        wf: dict,
        csv_source: str | bytes,
        *,
        filename: str | None = None,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> StepResult:
        """Parse + validate the CSV against the live host schema and (optionally) write it.

        The loader maps headers to the dataset's ``fields_schema`` fetched live
        from the host. External-source columns (e.g. weather) are dropped from the
        file. With ``dry_run`` the host validates without persisting; otherwise the
        write is an idempotent upsert on ``(dataset, timestamp)`` performed host-side.
        """
        try:
            dataset_id, detail = await self._resolve_dataset_id(wf)
        except OpsWorkflowError as e:
            return StepResult("ingest_csv", "failed", str(e), errors=[str(e)])

        fields_schema = detail.get("fields_schema") or {}
        if not fields_schema:
            msg = f"Dataset {dataset_id} has no fields_schema; cannot validate CSV."
            return StepResult("ingest_csv", "failed", msg, errors=[msg])

        if detail.get("is_managed"):
            msg = (
                f"Dataset {dataset_id} is AI-managed and cannot be written to "
                "manually. Pick a user-owned dataset."
            )
            return StepResult("ingest_csv", "failed", msg, errors=[msg])

        external_fields = wf.get("external_fields", []) or []
        schema = FieldSchema.from_host_schema(fields_schema, external_fields)
        tz = wf.get("timezone") or self.config.get("timezone")

        # Pure, host-agnostic parse + validate.
        raw_bytes = csv_source if isinstance(csv_source, bytes) else None
        result: LoadResult = load_csv(csv_source, schema, tz=tz)

        provenance = result.summary()
        provenance["dataset_id"] = dataset_id

        # Host-side dry-run validation (read-only) for the records we built.
        payload = {"records": result.records}
        bulk_api = wf.get("api", {}).get("bulk_write", "bulk_write_records")
        try:
            method, path = self._path(bulk_api, {"id": dataset_id})
        except OpsWorkflowError as e:
            return StepResult("ingest_csv", "failed", str(e), errors=[str(e)])

        host_dry = await self.executor.call_api_direct(
            method, path, {"dry_run": "true"}, payload
        )
        if isinstance(host_dry, dict) and host_dry.get("error"):
            err = str(host_dry["error"])
            return StepResult(
                "ingest_csv", "failed",
                f"Host rejected the records during validation: {err}",
                data={"provenance": provenance}, errors=[err],
            )

        base_summary = (
            f"Parsed {result.total_rows} rows → {result.ingested_rows} valid, "
            f"{result.skipped_rows} skipped. "
            f"File columns: {result.file_columns or '—'}; "
            f"external (not from file): {result.external_columns or '—'}. "
            f"Range {result.date_start} → {result.date_end}."
        )

        data = {
            "dataset_id": dataset_id,
            "provenance": provenance,
            "records": result.records,
            "bulk_api": bulk_api,
            "input_hash": _sha256(raw_bytes) if raw_bytes else None,
            "filename": filename,
        }

        if dry_run:
            return StepResult(
                "ingest_csv", "ok",
                "DRY RUN — nothing written. " + base_summary,
                data={**data, "wrote": False},
            )

        # Real write mutates host state → confirmation flow unless pre-confirmed.
        if not confirm:
            confirmation_msg = (
                f"Upsert {result.ingested_rows} records into dataset {dataset_id} "
                f"({result.date_start} → {result.date_end}). This modifies host data."
            )
            execution = await self.executor.create_pending_execution(
                conversation_id=self.conversation_id,
                tool_name=f"ops_ingest_csv:{dataset_id}",
                method=method,
                endpoint=path,
                params=None,
                body=payload,
                confirmation_message=confirmation_msg,
            )
            return StepResult(
                "ingest_csv", "pending_confirmation",
                confirmation_msg,
                data={**data, "wrote": False, "execution_id": execution.id},
            )

        write_res = await self.executor.call_api_direct(method, path, None, payload)
        if isinstance(write_res, dict) and write_res.get("error"):
            err = str(write_res["error"])
            return StepResult(
                "ingest_csv", "failed",
                f"Bulk write failed: {err}", data=data, errors=[err],
            )
        processed = _unwrap(write_res).get("processed", result.ingested_rows)
        return StepResult(
            "ingest_csv", "ok",
            f"Wrote {processed} records (idempotent upsert). " + base_summary,
            data={**data, "wrote": True, "processed": processed},
        )

    # ── STEP 2: validate / quality gate ──────────────────────────────────

    def validate(self, wf: dict, ingest: StepResult) -> StepResult:
        """Hard gate on the ingest result. Stops the workflow on failure."""
        if ingest.status == "failed":
            return StepResult("validate", "failed", ingest.summary, errors=ingest.errors)

        prov = ingest.data.get("provenance", {})
        total = prov.get("total_rows", 0) or 0
        ingested = prov.get("ingested_rows", 0) or 0
        skipped = prov.get("skipped_rows", 0) or 0

        problems: list[str] = []
        if not prov.get("timestamp_header"):
            problems.append(
                "No timestamp column detected (expected DateTime / Date/Time / timestamp / time)."
            )
        if ingested == 0:
            problems.append("No valid rows after parsing — nothing to ingest.")
        if not prov.get("file_columns"):
            problems.append(
                "No feature columns mapped to the dataset schema — check headers."
            )

        max_ratio = float(wf.get("max_skip_ratio", _DEFAULT_MAX_SKIP_RATIO))
        if total and (skipped / total) > max_ratio:
            problems.append(
                f"{skipped}/{total} rows skipped (> {int(max_ratio * 100)}%). "
                "Likely a header/format mismatch."
            )

        if problems:
            return StepResult(
                "validate", "needs_input",
                "Validation failed — stopping for review.",
                data={"provenance": prov}, errors=problems,
            )

        return StepResult(
            "validate", "ok",
            f"Validation passed: {ingested} rows, {len(prov.get('file_columns') or [])} "
            f"feature columns, {skipped} skipped.",
            data={"provenance": prov},
        )

    # ── STEP 3: run inference ────────────────────────────────────────────

    async def run_inference(self, wf: dict, *, confirm: bool = False) -> StepResult:
        """Trigger inference on the configured engine (mutation → confirmation)."""
        engine_ref = str(wf.get("engine", "")).strip()
        if not engine_ref:
            return StepResult(
                "run_inference", "ok",
                "No engine configured — skipping inference step.",
                data={"skipped": True},
            )

        engine_id = await self._resolve_engine_id(wf, engine_ref)
        if engine_id is None:
            msg = f"Engine {engine_ref!r} not found among the user's engines."
            return StepResult("run_inference", "failed", msg, errors=[msg])

        infer_api = wf.get("api", {}).get("trigger_inference", "trigger_inference")
        method, path = self._path(infer_api, {"id": engine_id})

        if not confirm:
            confirmation_msg = f"Run inference on engine {engine_id} using its active model."
            execution = await self.executor.create_pending_execution(
                conversation_id=self.conversation_id,
                tool_name=f"ops_run_inference:{engine_id}",
                method=method,
                endpoint=path,
                params=None,
                body={},
                confirmation_message=confirmation_msg,
            )
            return StepResult(
                "run_inference", "pending_confirmation", confirmation_msg,
                data={"engine_id": engine_id, "execution_id": execution.id},
            )

        res = await self.executor.call_api_direct(method, path, None, {})
        if isinstance(res, dict) and res.get("error"):
            err = str(res["error"])
            return StepResult("run_inference", "failed", f"Inference failed: {err}",
                              data={"engine_id": engine_id}, errors=[err])
        payload = _unwrap(res)
        return StepResult(
            "run_inference", "ok",
            f"Inference triggered on engine {engine_id}.",
            data={"engine_id": engine_id, "result": payload,
                  "model_version": payload.get("model_version")},
        )

    async def _resolve_engine_id(self, wf: dict, engine_ref: str) -> str | None:
        if engine_ref.isdigit() or "-" in engine_ref and len(engine_ref) > 20:
            return engine_ref
        list_api = wf.get("api", {}).get("list_ai_engines", "list_ai_engines")
        method, path = self._path(list_api)
        listing = await self.executor.call_api_direct(method, path)
        items = _extract_items(listing)
        match = next(
            (it for it in items
             if str(it.get("name")) == engine_ref
             or str(it.get("display_name")) == engine_ref
             or str(it.get("id")) == engine_ref),
            None,
        )
        return str(match.get("id")) if match else None

    # ── STEP 4: produce ops output ───────────────────────────────────────

    async def produce_ops_output(self, wf: dict, inference: StepResult | None = None) -> StepResult:
        """Read back the ops output (forecast / daily summaries) for the engine."""
        engine_ref = str(wf.get("engine", "")).strip()
        if not engine_ref:
            return StepResult("produce_ops_output", "ok",
                              "No engine configured — no ops output to read.",
                              data={"skipped": True})

        engine_id = (
            inference.data.get("engine_id")
            if inference and inference.data.get("engine_id")
            else await self._resolve_engine_id(wf, engine_ref)
        )
        if engine_id is None:
            msg = f"Engine {engine_ref!r} not found; cannot read ops output."
            return StepResult("produce_ops_output", "failed", msg, errors=[msg])

        output_api = wf.get("api", {}).get("ops_output", "get_daily_summaries")
        method, path = self._path(output_api, {"engine_id": engine_id})
        res = await self.executor.call_api_direct(method, path)
        if isinstance(res, dict) and res.get("error"):
            err = str(res["error"])
            return StepResult("produce_ops_output", "failed",
                              f"Could not read ops output: {err}",
                              data={"engine_id": engine_id}, errors=[err])
        payload = _unwrap(res)
        count = len(_extract_items(res))
        return StepResult(
            "produce_ops_output", "ok",
            f"Ops output ready: {count} record(s) from {output_api}.",
            data={"engine_id": engine_id, "output_api": output_api,
                  "output": payload, "output_location": f"{output_api}:engine/{engine_id}"},
        )

    # ── orchestration + provenance ledger ────────────────────────────────

    async def run(
        self,
        csv_source: str | bytes,
        *,
        workflow_name: str | None = None,
        filename: str | None = None,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> dict:
        """Run the full workflow end to end, recording a provenance ledger row.

        Stops and returns early (status ``needs_input``) on a validation failure,
        or ``pending_confirmation`` when a real mutation awaits user approval.
        """
        wf = self.get_workflow(workflow_name)
        steps_cfg = wf.get("steps") or ["ingest_csv", "validate", "run_inference", "produce_ops_output"]

        run_row = OpsRun(
            id=generate_uuid(),
            instance_id=self.instance_id,
            workflow=wf.get("name", "default"),
            status="running",
            dry_run=dry_run,
            csv_filename=filename,
            host_user_id=self.host_user_id,
            visibility="private" if self.host_user_id else "shared",
            created_at=utcnow(),
        )
        self.db.add(run_row)
        await self.db.commit()

        trail: list[dict] = []
        final_status = "completed"
        steps_out: dict[str, StepResult] = {}

        try:
            # 1. ingest
            ingest = await self.ingest_csv(
                wf, csv_source, filename=filename, dry_run=dry_run, confirm=confirm
            )
            steps_out["ingest_csv"] = ingest
            trail.append(ingest.as_dict())
            self._apply_ingest_provenance(run_row, ingest)

            if ingest.status == "failed":
                final_status = "failed"
                run_row.error = "; ".join(ingest.errors) or ingest.summary
            elif ingest.status == "pending_confirmation":
                final_status = "needs_input"
            else:
                # 2. validate (gate)
                validation = self.validate(wf, ingest)
                steps_out["validate"] = validation
                trail.append(validation.as_dict())
                if validation.status != "ok":
                    final_status = "needs_input" if validation.status == "needs_input" else "failed"
                    run_row.error = "; ".join(validation.errors)
                elif dry_run:
                    final_status = "completed"  # dry run stops after validation
                else:
                    # 3. inference
                    if "run_inference" in steps_cfg:
                        inference = await self.run_inference(wf, confirm=confirm)
                        steps_out["run_inference"] = inference
                        trail.append(inference.as_dict())
                        if inference.status == "failed":
                            final_status = "failed"
                            run_row.error = "; ".join(inference.errors)
                        elif inference.status == "pending_confirmation":
                            final_status = "needs_input"
                        else:
                            run_row.engine_ref = inference.data.get("engine_id")
                            run_row.model_version = inference.data.get("model_version")
                            # 4. ops output
                            if "produce_ops_output" in steps_cfg:
                                ops = await self.produce_ops_output(wf, inference)
                                steps_out["produce_ops_output"] = ops
                                trail.append(ops.as_dict())
                                if ops.status == "failed":
                                    final_status = "failed"
                                    run_row.error = "; ".join(ops.errors)
                                else:
                                    run_row.output_location = ops.data.get("output_location")
        except Exception as exc:  # defensive: never leave a ledger row 'running'
            logger.exception("Ops workflow crashed")
            final_status = "failed"
            run_row.error = f"{type(exc).__name__}: {exc}"

        run_row.status = final_status
        run_row.steps_json = json.dumps(trail, default=str)
        run_row.completed_at = utcnow()
        await self.db.commit()

        return {
            "run_id": run_row.id,
            "workflow": run_row.workflow,
            "status": final_status,
            "dry_run": dry_run,
            "steps": [s.as_dict() for s in steps_out.values()],
            "summary": self._final_summary(run_row, steps_out),
            "provenance": {
                "rows_ingested": run_row.rows_ingested,
                "rows_skipped": run_row.rows_skipped,
                "date_start": run_row.date_start,
                "date_end": run_row.date_end,
                "dataset_ref": run_row.dataset_ref,
                "engine_ref": run_row.engine_ref,
                "model_version": run_row.model_version,
                "output_location": run_row.output_location,
                "input_hash": run_row.input_hash,
            },
            "needs_confirmation": [
                {"step": s.step, "execution_id": s.data.get("execution_id")}
                for s in steps_out.values()
                if s.status == "pending_confirmation"
            ],
        }

    def _apply_ingest_provenance(self, run_row: OpsRun, ingest: StepResult) -> None:
        prov = ingest.data.get("provenance", {})
        run_row.rows_ingested = prov.get("ingested_rows", 0) or 0
        run_row.rows_skipped = prov.get("skipped_rows", 0) or 0
        run_row.date_start = prov.get("date_start")
        run_row.date_end = prov.get("date_end")
        run_row.dataset_ref = ingest.data.get("dataset_id") or prov.get("dataset_id")
        run_row.input_hash = ingest.data.get("input_hash")
        run_row.provenance_json = json.dumps(prov, default=str)

    @staticmethod
    def _final_summary(run_row: OpsRun, steps: dict[str, StepResult]) -> str:
        lines = [
            f"Ops run `{run_row.id}` ({run_row.workflow}) — **{run_row.status}**"
            + (" [dry-run]" if run_row.dry_run else ""),
        ]
        for s in steps.values():
            mark = {"ok": "✓", "needs_input": "⏸", "failed": "✗",
                    "pending_confirmation": "⏳"}.get(s.status, "•")
            lines.append(f"  {mark} {s.step}: {s.summary}")
        lines.append(
            f"Provenance: {run_row.rows_ingested} ingested / {run_row.rows_skipped} skipped, "
            f"range {run_row.date_start} → {run_row.date_end}, "
            f"dataset={run_row.dataset_ref}, engine={run_row.engine_ref}, "
            f"model={run_row.model_version}, output={run_row.output_location}."
        )
        return "\n".join(lines)


# ── small response-shape helpers (host responses vary in nesting) ────────────

def _unwrap(res: Any) -> dict:
    """Return the meaningful body of a host response (handles {status_code,data})."""
    if isinstance(res, dict):
        if "data" in res and isinstance(res["data"], (dict, list)):
            inner = res["data"]
            return inner if isinstance(inner, dict) else {"items": inner}
        return res
    return {}


def _extract_items(res: Any) -> list[dict]:
    """Pull a list of records from a variety of host response shapes."""
    body = _unwrap(res)
    for key in ("results", "items", "records", "data"):
        val = body.get(key)
        if isinstance(val, list):
            return val
    if isinstance(body, list):
        return body
    return []


def _sha256(data: bytes | None) -> str | None:
    if data is None:
        return None
    return hashlib.sha256(data).hexdigest()
