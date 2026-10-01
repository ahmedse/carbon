"""Host-layer Pulse bind: identity, pack jail, app jail, containment.

Not engine. Pack ids and app slugs live here and in the pack YAML.
No routing ``re.compile`` and no phrase table.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

from ai.instance_registry import (
    active_brand,
    known_brand,
    pack_id_for_brand,
    resolve_instance_id,
)
from ai.models.control_state import (
    CONTAINMENT_AUTONOMY_CLAMP,
    CONTAINMENT_FULL_STOP,
    CONTAINMENT_TOOL_FREEZE,
    get_or_create_control_state,
)

# Honest refuse copy. Host layer may name Pulse. Engine must not.
PULSE_OFF_NO_PACK = (
    "Pulse is off for this deployment. There is no pack bound to this process."
)
PULSE_OFF_STOPPED = (
    "Pulse is off. This deployment is not serving Pulse turns."
)
TOOL_FREEZE_HOST = "Host tools are frozen for this deployment."

_ENV_KEYS = frozenset(
    {
        "DJANGO_BRAND",
        "PULSE_INSTANCE_ID",
        "REDIS_URL",
        "PULSE_MEMORY_REDIS_URL",
    }
)
_REDIS_DB_RE = re.compile(r"/(\d+)/?$")

# Second pack on the same brand. Listed and toggleable, not a silent override.
_EXTRA_PACKS_BY_BRAND: dict[str, tuple[str, ...]] = {
    "aastmt": ("aast-med",),
}

# Surface apps that share a host pack. people off drops the host APIs.
_HOST_APP_FOR_PACK: dict[str, str] = {
    "nibras": "people",
}


def domain_packs_root() -> Path:
    return Path(settings.BASE_DIR).resolve().parent / "domain_packs"


def has_domain_pack(instance_id: str) -> bool:
    """True when ``domain_packs/<id>/pack.yaml`` exists."""
    name = (instance_id or "").strip()
    if not name or "/" in name or name.startswith("."):
        return False
    return (domain_packs_root() / name / "pack.yaml").is_file()


def read_pack_version(instance_id: str) -> str | None:
    if not has_domain_pack(instance_id):
        return None
    try:
        import yaml

        data = yaml.safe_load(
            (domain_packs_root() / instance_id / "pack.yaml").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("version")
    return str(version) if version is not None else None


def backend_env_path() -> Path:
    return Path(settings.BASE_DIR) / ".env"


def read_env_file_keys(path: Path | None = None) -> dict[str, str]:
    """Read only bind keys from a .env file. Never returns other values."""
    target = path or backend_env_path()
    out: dict[str, str] = {}
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in _ENV_KEYS:
            out[key] = value.strip().strip("'").strip('"')
    return out


def redis_db_from_url(url: str | None) -> int | None:
    if not url:
        return None
    parsed = urlparse(url)
    path = (parsed.path or "").strip()
    match = _REDIS_DB_RE.search(path)
    if match:
        return int(match.group(1))
    if path in ("", "/"):
        return 0
    try:
        return int(path.lstrip("/").split("/", 1)[0])
    except (TypeError, ValueError):
        return None


def process_brand() -> str:
    return active_brand()


def files_brand() -> str:
    raw = (read_env_file_keys().get("DJANGO_BRAND") or "").strip().lower()
    if known_brand(raw):
        return raw
    return process_brand()


def pack_apps_from_catalog(catalog: list) -> set[str]:
    apps: set[str] = set()
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        app = str(entry.get("app") or "").strip()
        if app:
            apps.add(app)
    return apps


def brand_preset_apps(brand: str | None = None) -> set[str]:
    presets = getattr(settings, "BRAND_APP_PRESETS", {}) or {}
    row = presets.get(brand or process_brand()) or {}
    return {str(k) for k, v in row.items() if v}


def extra_packs_for_brand(brand: str | None = None) -> tuple[str, ...]:
    return _EXTRA_PACKS_BY_BRAND.get(brand or process_brand(), ())


def _orm_call(fn, *args, **kwargs):
    """Sync ORM helper. Callers inside async must use ``sync_to_async``."""
    return fn(*args, **kwargs)


def deactivated_app_slugs() -> set[str]:
    """App slugs with an AppActivation row set off. No row means not deactivated."""
    """Active AppActivation slugs, or None when activation cannot vote.

    None = fail open (preset still applies). A non-empty set intersects.
    Zero rows means the table is unused, not that every app is off.
    """
    def _load() -> set[str]:
        try:
            from appregistry.models import AppActivation

            return set(
                AppActivation.objects.filter(is_active=False).values_list(
                    "app__slug", flat=True
                )
            )
        except Exception:  # noqa: BLE001 — jail must not crash a turn
            return set()

    return _orm_call(_load)


def pulse_enablement_map(instance_id: str) -> dict[str, bool]:
    """Explicit PulseAppEnablement rows. Missing slug defaults on."""
    def _load() -> dict[str, bool]:
        try:
            from ai.models.app_enablement import PulseAppEnablement

            rows = PulseAppEnablement.objects.filter(instance_id=instance_id)
            return {row.app_slug: bool(row.enabled) for row in rows}
        except Exception:  # noqa: BLE001
            return {}

    return _orm_call(_load)


def allowed_apps(
    instance_id: str,
    *,
    catalog: list | None = None,
    brand: str | None = None,
) -> set[str]:
    """preset ∩ activation ∩ Pulse enablement ∩ apps the pack owns.

    An extra pack on this brand (aast-med on aastmt) is jailed to *its*
    catalog. Those apps are not folded into the process pack's owned set.
    """
    brand_id = brand or process_brand()
    owned = pack_apps_from_catalog(catalog or [])
    extra = extra_packs_for_brand(brand_id)
    process_pack = resolve_instance_id()
    preset = brand_preset_apps(brand_id)
    on_process = instance_id == process_pack
    on_extra = instance_id in extra
    # Brand preset jails the live process pack. An extra pack on this cell
    # keeps pack-owned rows and never inherits the process pack's apps.
    # A foreign pack (tests / inspect) keeps pack-owned rows; turns on
    # another brand never load that pack as the process default.
    if on_extra:
        candidates = set(owned)
    elif on_process:
        candidates = owned & preset if owned else set(preset)
    else:
        candidates = set(owned) if owned else set()
    candidates -= deactivated_app_slugs()
    enablement = pulse_enablement_map(instance_id)
    out = {app for app in candidates if enablement.get(app, True)}
    host = _HOST_APP_FOR_PACK.get(instance_id)
    if host and host not in out:
        return set()
    return out


def filter_catalog_by_app(catalog: list, allowed: set[str]) -> list:
    """R7: a row without ``app`` is not shown and not executable."""
    kept: list = []
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        app = str(entry.get("app") or "").strip()
        if app and app in allowed:
            kept.append(entry)
    return kept


def catalog_names(catalog: list) -> set[str]:
    names: set[str] = set()
    for entry in catalog or []:
        if isinstance(entry, dict) and entry.get("name"):
            names.add(str(entry["name"]))
    return names


@dataclass(frozen=True)
class TurnGate:
    pulse_off: bool
    refuse_before_model: bool
    tool_freeze: bool
    autonomy_clamp: bool
    message: str
    containment_level: str
    pack_present: bool


def pulse_enabled_for(instance_id: str) -> bool:
    if not has_domain_pack(instance_id):
        return False
    state = _orm_call(get_or_create_control_state, instance_id)
    return state.containment_level != CONTAINMENT_FULL_STOP


def turn_gate(instance_id: str) -> TurnGate:
    pack_ok = has_domain_pack(instance_id)
    if not pack_ok:
        return TurnGate(
            pulse_off=True,
            refuse_before_model=True,
            tool_freeze=True,
            autonomy_clamp=True,
            message=PULSE_OFF_NO_PACK,
            containment_level=CONTAINMENT_FULL_STOP,
            pack_present=False,
        )
    state = _orm_call(get_or_create_control_state, instance_id)
    level = state.containment_level or "normal"
    if level == CONTAINMENT_FULL_STOP:
        return TurnGate(
            pulse_off=True,
            refuse_before_model=True,
            tool_freeze=True,
            autonomy_clamp=True,
            message=PULSE_OFF_STOPPED,
            containment_level=level,
            pack_present=True,
        )
    return TurnGate(
        pulse_off=False,
        refuse_before_model=False,
        tool_freeze=level == CONTAINMENT_TOOL_FREEZE,
        autonomy_clamp=level == CONTAINMENT_AUTONOMY_CLAMP,
        message="",
        containment_level=level,
        pack_present=True,
    )


def bind_health(*, instance_id: str | None = None) -> dict[str, Any]:
    """Process vs file brand, pack id, Redis db. Does not claim a silent switch."""
    process = process_brand()
    files = files_brand()
    files_keys = read_env_file_keys()
    pack = instance_id or resolve_instance_id()
    process_memory_url = os.environ.get("PULSE_MEMORY_REDIS_URL") or os.environ.get(
        "REDIS_URL", ""
    )
    files_memory_url = files_keys.get("PULSE_MEMORY_REDIS_URL") or files_keys.get(
        "REDIS_URL", ""
    )
    # Tokens stamp the process pack, not the brand slug (aastmt → carbon)
    # and not a class-body getenv captured before dotenv.
    jwt_instance = pack
    env_pulse = os.environ.get("PULSE_INSTANCE_ID") or ""
    files_pulse = files_keys.get("PULSE_INSTANCE_ID") or ""
    match = process == files
    pack_ok = has_domain_pack(pack)
    gate = turn_gate(pack)
    return {
        "process_brand": process,
        "files_brand": files,
        "files_match_process": match,
        "switched": match,
        "pack": pack,
        "pack_version": read_pack_version(pack),
        "pack_present": pack_ok,
        "pulse_available": pack_ok and not gate.pulse_off,
        "pulse_enabled": gate.pack_present and not gate.pulse_off,
        "containment_level": gate.containment_level,
        "jwt_instance": jwt_instance,
        "env_pulse_instance_id": env_pulse,
        "files_pulse_instance_id": files_pulse,
        "jwt_matches_pack": (env_pulse == pack) if env_pulse else True,
        "redis_memory_db": redis_db_from_url(process_memory_url),
        "files_redis_memory_db": redis_db_from_url(files_memory_url),
        "extra_packs": list(extra_packs_for_brand(process)),
    }


def bind_apps_payload(instance_id: str, catalog: list | None = None) -> list[dict]:
    """Apps this pack owns. Extra packs are a separate payload, not merged here."""
    owned = pack_apps_from_catalog(catalog or [])
    extra = extra_packs_for_brand()
    process_pack = resolve_instance_id()
    preset = brand_preset_apps()
    if instance_id in extra:
        slugs = sorted(owned)
    elif instance_id == process_pack:
        slugs = sorted(owned & preset) if owned else sorted(preset)
        if not slugs:
            slugs = sorted(owned)
    else:
        slugs = sorted(owned)
    deactivated = deactivated_app_slugs()
    enablement = pulse_enablement_map(instance_id)
    allowed = allowed_apps(instance_id, catalog=catalog)
    out = []
    for slug in slugs:
        act = slug not in deactivated
        pulse_on = enablement.get(slug, True)
        out.append(
            {
                "slug": slug,
                "in_pack": slug in owned,
                "in_preset": slug in preset,
                "activated": act,
                "pulse_enabled": pulse_on,
                "effective": slug in allowed,
            }
        )
    return out
