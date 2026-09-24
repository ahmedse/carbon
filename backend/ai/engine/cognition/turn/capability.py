"""One capability surface per turn (ADR-0049 §9).

The understand prompt lists these entries, ``validate_decision`` accepts
exactly these names and argument shapes, and the executor binds calls from
the same entries. A tool the model is shown is a tool the executor runs;
a tool the executor cannot run is never shown.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _is_write(entry: dict) -> bool:
    kind = str(entry.get("kind") or "")
    method = str(entry.get("method") or "GET").strip().upper()
    return kind == "write" or method != "GET"


def _path_keys(path: str) -> set[str]:
    keys: set[str] = set()
    rest = path or ""
    while "{" in rest:
        _, _, tail = rest.partition("{")
        key, closed, rest = tail.partition("}")
        if not closed:
            break
        if key.strip():
            keys.add(key.strip())
    return keys


@dataclass(frozen=True)
class CapabilitySurface:
    """Audience-scoped entries the model may name this turn."""

    entries: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def names(self) -> set[str]:
        return {str(e.get("name") or "") for e in self.entries if e.get("name")}

    @property
    def writes(self) -> set[str]:
        return {str(e.get("name") or "") for e in self.entries if _is_write(e)}

    def entry(self, name: str) -> dict | None:
        wanted = str(name or "").strip()
        for item in self.entries:
            if str(item.get("name") or "") == wanted:
                return item
        return None

    def schema(self, name: str) -> dict | None:
        params = (self.entry(name) or {}).get("parameters")
        return params if isinstance(params, dict) and params else None

    def label(self, name: str) -> str:
        """Human label for an entry name. Never the raw identifier."""
        entry = self.entry(name) or {}
        for key in ("label", "title"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(name or "").replace("_", " ").strip()

    def arg_violations(self, name: str, args: dict | None) -> list[str]:
        """Schema misses for ``args`` against this entry. Empty when valid."""
        schema = self.schema(name)
        if schema is None:
            return []
        from ai.engine.cognition.plan.planner import _schema_violations

        return _schema_violations(schema, flat_args(args))

    def path_keys(self, name: str) -> set[str]:
        return _path_keys(str((self.entry(name) or {}).get("path") or ""))

    def missing_path_keys(self, name: str, args: dict | None) -> list[str]:
        """Path placeholders ``args`` does not fill."""
        raw = args if isinstance(args, dict) else {}
        given = raw.get("path_params") if isinstance(raw.get("path_params"), dict) else {}
        return sorted(
            k for k in self.path_keys(name)
            if given.get(k) is None or not str(given.get(k)).strip()
        )

    def host_args(self, name: str, args: dict | None) -> dict:
        """The one ``call_host_api`` argument shape for ``name``.

        Path placeholders go to ``path_params``; everything else goes to
        ``query_params`` for a read and ``body`` for a write. The executor
        sends nothing else, so validation and repair read this shape too.
        Keys the entry's schema forbids are dropped: the host rejects them.
        """
        entry = self.entry(name) or {}
        raw = args if isinstance(args, dict) else {}
        flat = flat_args(raw)
        # The executor derives the transport from the entry; a caller never sets it.
        for key in ("method", "path", "endpoint", "url"):
            flat.pop(key, None)
        schema = self.schema(name) or {}
        props = schema.get("properties") or {}
        path_keys = self.path_keys(name)
        if schema.get("additionalProperties") is False:
            flat = {k: v for k, v in flat.items() if k in props or k in path_keys}
        path_params = {k: v for k, v in flat.items() if k in path_keys}
        rest = {k: v for k, v in flat.items() if k not in path_keys}
        out: dict[str, Any] = {"api_name": str(name or "")}
        if isinstance(raw.get("explanation"), str) and raw["explanation"].strip():
            out["explanation"] = raw["explanation"]
        if isinstance(raw.get("bind"), dict) and raw["bind"]:
            out["bind"] = dict(raw["bind"])
        if path_params:
            out["path_params"] = path_params
        if rest:
            out["body" if _is_write(entry) else "query_params"] = rest
        return out

    def host_call(self, name: str, args: dict | None, *, call_id: str) -> dict:
        """The ``call_host_api`` tool call that executes ``name`` with ``args``."""
        payload = {
            "explanation": f"Decided read: {name}",
            **self.host_args(name, args),
        }
        payload.pop("bind", None)
        return {
            "id": call_id,
            "function": {
                "name": "call_host_api",
                "arguments": json.dumps(payload, ensure_ascii=False, default=str),
            },
        }


def flat_args(args: dict | None) -> dict:
    """One flat mapping. The model may nest values under the host-call keys.

    A nested value wins over a stray top-level one: nested is what the
    executor sends.
    """
    raw = args if isinstance(args, dict) else {}
    out: dict = {}
    for key, value in raw.items():
        if key in ("path_params", "query_params", "body", "api_name", "explanation", "bind"):
            continue
        out[key] = value
    for nest in ("path_params", "query_params", "body"):
        inner = raw.get(nest)
        if isinstance(inner, dict):
            out.update(inner)
    return out


def host_surface(instance_config: dict | None) -> CapabilitySurface:
    """Every host entry ``call_host_api`` can execute, unscoped.

    The shape of a call does not depend on who asks; access is the host's
    and the audience filter's job.
    """
    cfg = instance_config or {}
    catalog = [e for e in (cfg.get("api_catalog") or []) if isinstance(e, dict)]
    known = {str(e.get("name") or "") for e in catalog}
    try:
        from ai.engine.agent.tools import host_api_capabilities

        registry = [e for e in host_api_capabilities(cfg) if e.get("name") not in known]
    except Exception:  # noqa: BLE001 — the host catalog alone is still a surface
        registry = []
    return CapabilitySurface(entries=tuple(catalog + registry))


def internal_name_labels(instance_config: dict | None) -> dict[str, str]:
    """Every tool / catalog identifier the engine knows, mapped to a human label.

    Built from the registry and the catalog, so a new tool is covered the
    moment it exists. Only identifiers with ``_`` are listed: a one-word
    name is indistinguishable from an ordinary word.
    """
    cfg = instance_config or {}
    entries = [e for e in (cfg.get("api_catalog") or []) if isinstance(e, dict)]
    names: set[str] = set()
    try:
        from ai.engine.agent.tools import get_tool_definitions, host_api_capabilities

        entries += host_api_capabilities(cfg)
        for tool in get_tool_definitions(cfg):
            name = str(((tool or {}).get("function") or {}).get("name") or "")
            if name:
                names.add(name)
    except Exception:  # noqa: BLE001 — the catalog alone still labels
        pass
    surface = CapabilitySurface(entries=tuple(entries))
    names |= surface.names
    return {n: surface.label(n) for n in names if "_" in n}


def scrub_internal_names(text: str, labels: dict[str, str]) -> tuple[str, list[str]]:
    """Replace exact identifier tokens with their labels. Returns (text, hits)."""
    if not text or not labels:
        return text, []
    out: list[str] = []
    hits: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if not (ch.isalnum() or ch == "_"):
            out.append(ch)
            i += 1
            continue
        j = i
        while j < n and (text[j].isalnum() or text[j] == "_"):
            j += 1
        token = text[i:j]
        label = labels.get(token)
        if label is not None:
            out.append(label)
            hits.append(token)
        else:
            out.append(token)
        i = j
    return "".join(out), hits


def capability_surface(
    instance_config: dict | None,
    user_info: dict | None,
) -> CapabilitySurface:
    """Host catalog plus registry capabilities, filtered by the caller's audience."""
    from ai.engine.agent.tools import host_api_capabilities
    from ai.engine.cognition.context_pack import filter_catalog_by_audience
    from ai.engine.cognition.turn.runner_helpers import _audience_from_user_info

    cfg = instance_config or {}
    catalog = [e for e in (cfg.get("api_catalog") or []) if isinstance(e, dict)]
    known = {str(e.get("name") or "") for e in catalog}
    try:
        registry = [e for e in host_api_capabilities(cfg) if e.get("name") not in known]
    except Exception:  # noqa: BLE001 — the host catalog alone is still a surface
        registry = []
    scoped = filter_catalog_by_audience(catalog + registry, _audience_from_user_info(user_info))
    return CapabilitySurface(entries=tuple(scoped))
