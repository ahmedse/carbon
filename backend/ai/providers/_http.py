"""
Thin HTTP helpers shared across AI providers.

Extracted so PulseProvider (and future AzureProvider, ClaudeProvider, etc.)
share a single envelope format and error-handling strategy.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import requests

logger = logging.getLogger("carbon.ai.http")

# ── Public helpers ────────────────────────────────────────────────────────


def post_task(
    base_url: str,
    api_key: str,
    task_type: str,
    payload: dict[str, Any],
    timeout: int = 30,
    instance_id: str = "carbon",
) -> dict[str, Any]:
    """POST a task envelope to ``{base_url}/tasks``.

    Returns the parsed JSON body, or a ``pulse_unavailable``-shaped dict
    on any error (timeout, connection refused, HTTP 5xx, etc.).
    """
    task_id = str(uuid.uuid4())
    envelope: dict[str, Any] = {
        "auth": {
            "instance_id": instance_id,
            "api_key": api_key,
        },
        "task": {
            "id": task_id,
            "type": task_type,
            "payload": payload,
        },
    }

    try:
        resp = requests.post(
            f"{base_url}/tasks",
            json=envelope,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    except requests.Timeout:
        logger.warning(
            "Pulse timeout after %ds for task %s (%s)",
            timeout, task_id, task_type,
        )
        return _error("timeout", f"Request timed out after {timeout}s")

    except requests.ConnectionError as exc:
        logger.warning("Pulse unreachable at %s: %s", base_url, exc)
        return _error("unreachable", f"Pulse at {base_url} is unreachable")

    except requests.RequestException as exc:
        logger.error(
            "Pulse request failed for task %s (%s): %s",
            task_id, task_type, exc,
        )
        return _error("request_failed", str(exc))

    except Exception as exc:
        logger.exception(
            "Unexpected Pulse error for task %s (%s)", task_id, task_type,
        )
        return _error("unexpected", str(exc))


def get_modules(
    base_url: str,
    instance_id: str = "carbon",
    timeout: int = 10,
) -> dict[str, Any]:
    """GET ``{base_url}/tasks/modules`` — used by ``health_check()``.

    Returns the raw parsed JSON or an error dict.
    """
    modules_url = f"{base_url}/tasks/modules"
    try:
        resp = requests.get(
            modules_url,
            timeout=timeout,
            params={"instance_id": instance_id},
        )
        if resp.ok:
            return resp.json()
        return {
            "modules": [],
            "error": {"code": "http_error", "message": f"HTTP {resp.status_code}"},
        }
    except requests.Timeout:
        return {"modules": [], "error": {"code": "timeout", "message": "Health-check timed out"}}
    except requests.ConnectionError as exc:
        return {"modules": [], "error": {"code": "unreachable", "message": str(exc)}}
    except Exception as exc:
        return {"modules": [], "error": {"code": "unexpected", "message": str(exc)}}


def get_task(
    base_url: str,
    task_id: str,
    timeout: int = 10,
) -> dict[str, Any]:
    """GET ``{base_url}/tasks/{task_id}`` — single poll, no retry loop.

    Used by ``CarbonIntelligence.get_task_status()`` for DQ job polling.
    Returns parsed JSON or an error dict on any failure.
    """
    try:
        resp = requests.get(
            f"{base_url}/tasks/{task_id}",
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout:
        return _error("timeout", f"Task status request timed out after {timeout}s")
    except requests.ConnectionError as exc:
        return _error("unreachable", f"Pulse at {base_url} is unreachable")
    except requests.RequestException as exc:
        return _error("request_failed", str(exc))
    except Exception as exc:
        return _error("unexpected", str(exc))


def poll_task(
    base_url: str,
    api_key: str,
    task_id: str,
    poll_interval: float = 2.0,
    max_wait: float = 120.0,
    instance_id: str = "carbon",
) -> dict[str, Any]:
    """Poll ``{base_url}/tasks/{task_id}`` until completed or timeout.

    Returns the final parsed JSON body or an error dict.
    """
    import time

    url = f"{base_url}/tasks/{task_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Pulse-Instance": instance_id,
        "Authorization": f"Bearer {api_key}",
    }
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            if resp.ok:
                data = resp.json()
                if data.get("status") in ("completed", "failed"):
                    return data
            else:
                logger.warning("Poll %s returned HTTP %d", task_id, resp.status_code)
        except requests.Timeout:
            logger.warning("Poll %s timed out (will retry)", task_id)
        except requests.ConnectionError:
            logger.warning("Poll %s connection error (will retry)", task_id)
        except Exception as exc:
            logger.warning("Poll %s unexpected: %s", task_id, exc)

        time.sleep(poll_interval)

    return _error("timeout", f"Task {task_id} did not complete within {max_wait}s")


# ── Internal ──────────────────────────────────────────────────────────────


def _error(code: str, message: str) -> dict[str, Any]:
    """Build a ``pulse_unavailable`` error envelope."""
    return {
        "status": "pulse_unavailable",
        "error": {"code": code, "message": message},
    }
