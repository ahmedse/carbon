"""P6.3 — Instance export/import as portable .pulse.zip bundles.

Export produces a zip containing:
- instance.yaml            # the instance config
- pulse.db                 # SQLite database
- chroma/                  # ChromaDB vector store
- manifest.json            # metadata (version, archetype, timestamps, pulse_version)

Import extracts, validates, and registers the instance.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pulse.instance_export")

_MANIFEST_VERSION = 1


# ── Public API ──────────────────────────────────────────────────────────────


def export_instance(instance_name: str, output_path: str | None = None) -> Path:
    """Export an instance to a .pulse.zip bundle.

    Args:
        instance_name: Name of the instance directory (e.g. "twin-mind-demo").
        output_path:   Destination path for the .zip file.
                        Defaults to "<instance_name>.pulse.zip" in cwd.

    Returns:
        Path to the created zip file.

    Raises:
        FileNotFoundError: if the instance doesn't exist.
        ValueError: if the instance is missing required files.
    """
    from ai.engine.core.config import resolve_instance_paths

    instances_root = Path(__file__).resolve().parent.parent / "instances"
    instance_dir = instances_root / instance_name

    if not instance_dir.is_dir():
        raise FileNotFoundError(f"Instance '{instance_name}' not found at {instance_dir}")

    instance_yaml = instance_dir / "instance.yaml"
    if not instance_yaml.exists():
        raise ValueError(f"Instance '{instance_name}' has no instance.yaml")

    paths = resolve_instance_paths(instance_name)
    db_path = Path(paths["db_path"])
    chroma_dir = Path(paths["chroma_dir"])

    # Read instance.yaml to get archetype
    import yaml

    with open(instance_yaml, "r") as f:
        config = yaml.safe_load(f) or {}

    # Build manifest
    manifest = {
        "version": _MANIFEST_VERSION,
        "instance_name": instance_name,
        "archetype": config.get("archetype", "unknown"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pulse_version": "0.3.0",
    }

    if output_path is None:
        output_path = f"{instance_name}.pulse.zip"

    output = Path(output_path)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Write instance.yaml
        zf.write(instance_yaml, "instance.yaml")

        # Write pulse.db if it exists
        if db_path.exists():
            zf.write(db_path, "pulse.db")
        else:
            logger.warning("No pulse.db found for instance '%s'", instance_name)

        # Write chroma/ directory if it exists
        if chroma_dir.exists():
            for root, _dirs, files in os.walk(chroma_dir):
                for fname in files:
                    full_path = Path(root) / fname
                    arcname = "chroma/" + str(full_path.relative_to(chroma_dir))
                    zf.write(full_path, arcname)

    logger.info("Exported '%s' → %s (%d bytes)", instance_name, output, output.stat().st_size)
    return output


def import_instance(
    bundle_path: str,
    target_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Import a .pulse.zip bundle as a new instance.

    Args:
        bundle_path: Path to the .pulse.zip file.
        target_name: Override the instance name (default: use manifest name).
        force:       Overwrite existing instance if it exists.

    Returns:
        Dict with keys: instance_name, archetype, data_dir.

    Raises:
        FileNotFoundError: if bundle doesn't exist.
        ValueError: if manifest is missing or invalid.
        FileExistsError: if target instance already exists and force=False.
    """
    instances_root = Path(__file__).resolve().parent.parent / "instances"
    bundle = Path(bundle_path)

    if not bundle.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    with zipfile.ZipFile(bundle, "r") as zf:
        # Validate manifest
        if "manifest.json" not in zf.namelist():
            raise ValueError("Bundle is missing manifest.json")

        manifest_raw = zf.read("manifest.json").decode("utf-8")
        manifest = json.loads(manifest_raw)

        if manifest.get("version", 0) != _MANIFEST_VERSION:
            raise ValueError(
                f"Unsupported manifest version: {manifest.get('version')}. "
                f"Expected {_MANIFEST_VERSION}."
            )

        instance_name = target_name or manifest.get("instance_name", "imported")
        archetype = manifest.get("archetype", "unknown")

        # Check for existing instance
        target_dir = instances_root / instance_name
        if target_dir.exists() and not force:
            raise FileExistsError(
                f"Instance '{instance_name}' already exists at {target_dir}. "
                f"Use --force to overwrite."
            )

        # Clean up if force
        if target_dir.exists() and force:
            shutil.rmtree(target_dir)

        # Create instance dir
        target_dir.mkdir(parents=True, exist_ok=True)
        data_dir = target_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        chroma_dir = data_dir / "chroma"
        chroma_dir.mkdir(parents=True, exist_ok=True)

        # Extract instance.yaml
        if "instance.yaml" in zf.namelist():
            zf.extract("instance.yaml", target_dir)
        else:
            logger.warning("No instance.yaml in bundle")

        # Extract pulse.db
        if "pulse.db" in zf.namelist():
            zf.extract("pulse.db", data_dir)
        else:
            logger.warning("No pulse.db in bundle")

        # Extract chroma/
        for name in zf.namelist():
            if name.startswith("chroma/") and not name.endswith("/"):
                zf.extract(name, data_dir)

    logger.info(
        "Imported '%s' (archetype=%s) → %s", instance_name, archetype, target_dir
    )
    return {
        "instance_name": instance_name,
        "archetype": archetype,
        "data_dir": str(data_dir),
    }
