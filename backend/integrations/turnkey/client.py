"""CarbonTurnKeyClient — HTTP bridge to TurnKey's ML serving API.

Based on the reference implementation ``gigacast/backend/aihub/turnkey_client.py``
(design contract: docs/DESIGN-PLATFORM.md §6.2/§6.4). Intentionally Django-free
so it can be unit-tested standalone and reused by management commands, services
and tests alike.

Auth: TurnKey resolves the project scope from the API key itself, so only the
``X-API-Key`` header is required.

All methods raise ``TurnKeyClientError`` on any non-2xx response — errors are
never swallowed silently.

Example:
    from integrations.turnkey.client import CarbonTurnKeyClient

    client = CarbonTurnKeyClient("https://turnkey.internal", "sk-...")
    model = client.register_or_get_model("healthy-returns", "lightgbm")
    version_id = client.push_version(
        model["id"],
        artifact_path="/tmp/returns_v2.bentomodel",
        metrics={"mape": 4.2},
        feature_names=["qty_lag_1", "qty_lag_2"],
    )
    client.promote_to_production(model["id"], version_id)
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

import requests


class TurnKeyClientError(Exception):
    """Raised for any non-2xx TurnKey API response (or transport failure)."""


def sha256_file(path: str) -> str:
    """Return the bare 64-char hex SHA-256 of a file (TurnKey schema-safe)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class CarbonTurnKeyClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers.update(
            {"X-API-Key": api_key, "Content-Type": "application/json"}
        )
        self._timeout = timeout

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "CarbonTurnKeyClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── HTTP plumbing ───────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._session.request(
            method, f"{self.base_url}{path}", timeout=self._timeout, **kwargs
        )
        if resp.status_code >= 400:
            raise TurnKeyClientError(
                f"{method} {path} -> {resp.status_code}: {resp.text}"
            )
        if not resp.content:
            return None
        return resp.json()

    # ── Registry API ────────────────────────────────────────

    def register_model(
        self,
        name: str,
        model_type: str = "custom",
        description: Optional[str] = None,
    ) -> dict:
        return self._request(
            "POST",
            "/api/v1/models/",
            json={"name": name, "model_type": model_type, "description": description},
        )

    def register_or_get_model(self, name: str, model_type: str = "custom") -> dict:
        """Return an existing registered model or register a new one.

        Idempotent by name: if TurnKey already has a model with this name it
        is returned as-is; otherwise a new model is registered.
        """
        models = self.list_models()
        items = models.get("items") if isinstance(models, dict) else models
        for item in items or []:
            if item.get("name") == name:
                return item
        return self.register_model(name, model_type=model_type)

    def list_models(self) -> dict:
        # Trailing slash required: TurnKey sets redirect_slashes=False and the
        # registry list route is registered at /api/v1/models/.
        return self._request("GET", "/api/v1/models/")

    def get_model(self, model_id: str) -> dict:
        return self._request("GET", f"/api/v1/models/{model_id}")

    def list_versions(self, model_id: str) -> dict:
        return self._request("GET", f"/api/v1/models/{model_id}/versions")

    def push_version(
        self,
        model_id: str,
        artifact_path: str,
        metrics: Optional[dict] = None,
        feature_names: Optional[list[str]] = None,
        config: Optional[dict] = None,
        framework: str = "bentoml",
        artifact_hash: Optional[str] = None,
        framework_version: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Push a trained artifact to TurnKey. Returns the version id.

        ``artifact_hash`` is required by TurnKey's schema (exactly 64 hex chars).
        When omitted it is computed from ``artifact_path`` via SHA-256, so the
        common case needs no extra bookkeeping.
        """
        if artifact_hash is None:
            artifact_hash = sha256_file(artifact_path)
        resp = self._request(
            "POST",
            f"/api/v1/models/{model_id}/versions",
            json={
                "artifact_path": artifact_path,
                "artifact_hash": artifact_hash,
                "feature_names": list(feature_names or []),
                "framework": framework,
                "framework_version": framework_version,
                "metrics": metrics or {},
                "config": config or {},
                "description": description,
            },
        )
        return resp["id"]

    def promote_version(
        self, model_id: str, version_id: str, target_status: str = "production"
    ) -> dict:
        return self._request(
            "POST",
            f"/api/v1/models/{model_id}/versions/{version_id}/promote",
            json={"target_status": target_status},
        )

    def promote_to_staging(self, model_id: str, version_id: str) -> dict:
        """Mark a version as staging — ready for review."""
        return self.promote_version(model_id, version_id, target_status="staging")

    def promote_to_production(self, model_id: str, version_id: str) -> dict:
        """Promote a version all the way to production.

        TurnKey's lifecycle is a strict state machine
        (``registered → staging → production``), so a single jump is rejected
        with 400. This chains the two required transitions.
        """
        first = self.promote_version(model_id, version_id, target_status="staging")
        second = self.promote_version(model_id, version_id, target_status="production")
        return {"staging": first, "production": second}

    # ── Monitoring API ──────────────────────────────────────

    def get_model_metrics(self, model_id: str) -> dict:
        """Fetch live accuracy metrics from TurnKey for display in Carbon."""
        return self._request("GET", f"/api/v1/monitor/models/{model_id}/metrics")
