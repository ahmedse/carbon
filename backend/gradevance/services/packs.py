"""Load GradeVance engine packs from ``domain_packs/eduos/`` (filesystem SoT)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings


def eduos_pack_root() -> Path:
    """Resolve domain_packs/eduos relative to the monorepo root."""
    # backend/gradevance/services/packs.py → parents[3] = repo root
    here = Path(__file__).resolve()
    repo = here.parents[3]
    candidate = repo / "domain_packs" / "eduos"
    if candidate.is_dir():
        return candidate
    # Fallback: settings.BASE_DIR is backend/
    alt = Path(settings.BASE_DIR).resolve().parent / "domain_packs" / "eduos"
    return alt


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


@dataclass(frozen=True)
class LoadedDevice:
    device: dict[str, Any]
    anchors: list[dict[str, Any]]
    boundary_pairs: list[dict[str, Any]]
    segmentation: dict[str, Any]
    pack_dir: Path
    content_hash: str


@dataclass(frozen=True)
class LoadedRubric:
    rubric: dict[str, Any]
    action_templates: list[dict[str, Any]]
    band_descriptors: dict[str, Any]
    pack_dir: Path
    content_hash: str


@dataclass(frozen=True)
class LoadedProfile:
    profile: dict[str, Any]
    device: LoadedDevice | None
    rubric: LoadedRubric | None
    source_path: Path
    content_hash: str


def _hash_files(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: str(x)):
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


@lru_cache(maxsize=32)
def load_device(pack_rel: str) -> LoadedDevice:
    root = eduos_pack_root()
    pack_dir = (root / pack_rel).resolve()
    if not pack_dir.is_dir():
        raise FileNotFoundError(f"LCT device pack not found: {pack_dir}")
    device = _read_yaml(pack_dir / "device.yaml")
    anchors_file = pack_dir / device.get("anchors_file", "anchors.yaml")
    boundary_file = pack_dir / device.get("boundary_pairs_file", "boundary_pairs.yaml")
    seg_file = pack_dir / device.get("segmentation_file", "segmentation.yaml")
    anchors_doc = _read_yaml(anchors_file) if anchors_file.is_file() else {}
    boundary_doc = _read_yaml(boundary_file) if boundary_file.is_file() else {}
    seg = _read_yaml(seg_file) if seg_file.is_file() else {}
    anchors = anchors_doc.get("anchors") or []
    pairs = boundary_doc.get("pairs") or boundary_doc.get("boundary_pairs") or []
    return LoadedDevice(
        device=device,
        anchors=list(anchors),
        boundary_pairs=list(pairs),
        segmentation=seg,
        pack_dir=pack_dir,
        content_hash=_hash_files(pack_dir / "device.yaml", anchors_file, boundary_file, seg_file),
    )


@lru_cache(maxsize=32)
def load_rubric(pack_rel: str) -> LoadedRubric:
    root = eduos_pack_root()
    pack_dir = (root / pack_rel).resolve()
    if not pack_dir.is_dir():
        raise FileNotFoundError(f"Rubric pack not found: {pack_dir}")
    rubric = _read_yaml(pack_dir / "rubric.yaml")
    actions_file = pack_dir / rubric.get("action_templates_file", "action_templates.yaml")
    bands_file = pack_dir / rubric.get("band_descriptors_file", "band_descriptors.yaml")
    actions_doc = _read_yaml(actions_file) if actions_file.is_file() else {}
    bands = _read_yaml(bands_file) if bands_file.is_file() else {}
    templates = actions_doc.get("templates") or []
    return LoadedRubric(
        rubric=rubric,
        action_templates=list(templates),
        band_descriptors=bands,
        pack_dir=pack_dir,
        content_hash=_hash_files(pack_dir / "rubric.yaml", actions_file, bands_file),
    )


@lru_cache(maxsize=32)
def load_profile(profile_filename: str) -> LoadedProfile:
    """Load ``profiles/<filename>.yaml`` (with or without .yaml suffix)."""
    root = eduos_pack_root()
    name = profile_filename if profile_filename.endswith(".yaml") else f"{profile_filename}.yaml"
    path = root / "profiles" / name
    if not path.is_file():
        # Also allow lookup by pack id prefix
        matches = sorted((root / "profiles").glob(f"{profile_filename}*.yaml"))
        if not matches:
            raise FileNotFoundError(f"Profile not found: {path}")
        path = matches[0]
    profile = _read_yaml(path)
    device = None
    rubric = None
    pipeline = profile.get("pipeline") or {}
    lct_ref = profile.get("lct_device") or {}
    rubric_ref = profile.get("rubric_pack") or {}
    if pipeline.get("lct_enabled") and lct_ref.get("pack_path"):
        device = load_device(lct_ref["pack_path"])
    if rubric_ref.get("pack_path"):
        rubric = load_rubric(rubric_ref["pack_path"])
    return LoadedProfile(
        profile=profile,
        device=device,
        rubric=rubric,
        source_path=path,
        content_hash=_hash_files(path),
    )


def list_profiles() -> list[dict[str, Any]]:
    root = eduos_pack_root() / "profiles"
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.yaml")):
        doc = _read_yaml(path)
        out.append(
            {
                "pack_id": doc.get("id"),
                "version": doc.get("version"),
                "name": doc.get("name"),
                "status": doc.get("status"),
                "discipline": doc.get("discipline"),
                "genre": doc.get("genre"),
                "mode": doc.get("mode"),
                "file": path.name,
                "lct_enabled": bool((doc.get("pipeline") or {}).get("lct_enabled")),
            }
        )
    return out


def find_profile_file_for_id(pack_id: str, version: int | None = None) -> str:
    """Return profile filename for a pack_id (+ optional version)."""
    for meta in list_profiles():
        if meta.get("pack_id") != pack_id:
            continue
        if version is not None and meta.get("version") != version:
            continue
        return meta["file"]
    raise FileNotFoundError(f"No profile for id={pack_id!r} version={version!r}")


def list_knowledge_bases() -> list[dict[str, Any]]:
    """Filesystem KB catalog under ``domain_packs/eduos/knowledge_bases/`` (pin SoT)."""
    root = eduos_pack_root() / "knowledge_bases"
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*/kb.yaml")):
        doc = _read_yaml(path)
        out.append(
            {
                "pack_id": doc.get("id") or path.parent.name,
                "version": doc.get("version") or 1,
                "name": doc.get("name") or path.parent.name,
                "discipline": doc.get("discipline") or "",
                "genre": doc.get("genre") or "",
                "status": doc.get("status") or "draft",
                "description": (doc.get("description") or "")[:240],
                "chunk_count": int(doc.get("chunk_count") or 0),
            }
        )
    return out


def profile_detail_payload(pack_id: str, version: int = 1) -> dict[str, Any]:
    """Read-only pack drawer payload: brief, anchors sample, rubric bands, kb pin."""
    loaded = load_profile(find_profile_file_for_id(pack_id, version))
    doc = loaded.profile
    anchors = []
    if loaded.device:
        for a in (loaded.device.anchors or [])[:40]:
            anchors.append(
                {
                    "id": a.get("id"),
                    "dimension": a.get("dimension"),
                    "value": a.get("value"),
                    "numeric": a.get("numeric"),
                    "span_text": (a.get("span_text") or "")[:160],
                    "rationale": (a.get("rationale") or "")[:160],
                }
            )
    bands: dict[str, Any] = {}
    criteria: list[str] = []
    if loaded.rubric:
        band_doc = loaded.rubric.band_descriptors or {}
        criterion_bands = band_doc.get("criterion_bands") or band_doc
        if isinstance(criterion_bands, dict):
            for crit, levels in list(criterion_bands.items())[:12]:
                if crit in ("id", "version", "name", "description"):
                    continue
                criteria.append(str(crit))
                if isinstance(levels, dict):
                    bands[str(crit)] = {
                        k: (v[:120] if isinstance(v, str) else v)
                        for k, v in list(levels.items())[:8]
                    }
    lct = doc.get("lct_device") or {}
    rubric = doc.get("rubric_pack") or {}
    return {
        "pack_id": doc.get("id") or pack_id,
        "version": doc.get("version") or version,
        "name": doc.get("name"),
        "status": doc.get("status"),
        "discipline": doc.get("discipline"),
        "genre": doc.get("genre"),
        "mode": doc.get("mode"),
        "brief": doc.get("brief") or {},
        "pipeline": doc.get("pipeline") or {},
        "lct_device": {
            "pack_path": lct.get("pack_path"),
            "version": lct.get("version"),
            "anchor_count": len(anchors),
        },
        "rubric_pack": {
            "pack_path": rubric.get("pack_path"),
            "version": rubric.get("version"),
            "criteria": criteria,
        },
        "kb": doc.get("kb"),
        "anchors": anchors,
        "band_descriptors": bands,
    }


def clear_pack_caches() -> None:
    load_device.cache_clear()
    load_rubric.cache_clear()
    load_profile.cache_clear()
