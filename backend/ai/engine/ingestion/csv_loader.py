"""
Host-agnostic CSV loader for timeseries datasets.

This module is **pure** (no DB, no network, no host-specific knowledge) so it can
be unit-tested in isolation and reused across any host system. Everything that is
host-specific — the canonical field names, their types and valid ranges, which
columns come from the file vs. an external provider — is passed in as a
``FieldSchema`` that callers fetch live from the host (e.g. Gigacast's
``GET /datasets/{id}/`` ``fields_schema``).

Responsibilities (mirrors the proven host-side loader, generalised):
  * auto-detect the timestamp column (``DateTime``/``Date/Time``/``timestamp``/``time``)
  * parse common timestamp formats and store timezone-aware
  * map/alias feature headers to the canonical schema (fuzzy/substring matching)
  * strip units (`` MW``, ``%``) and clean non-numeric cells
  * validate each value against the schema (type / min / max)
  * skip and *report* bad rows rather than failing the whole file
  * keep external-source columns (e.g. weather) OUT of the file-derived values

The output is a :class:`LoadResult` — a typed, idempotent-ready record set
(``[{"timestamp": iso, "values": {field: float}}]``) plus a full provenance and
skipped-rows report. Writing the records (idempotent upsert on
``(dataset, timestamp)``) is the host's job, performed via its bulk API.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Any, Iterable, Mapping, Sequence

try:  # Python 3.9+ stdlib; present on 3.12 target
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - defensive
    ZoneInfo = None  # type: ignore[assignment]

logger = logging.getLogger("pulse.ingestion.csv_loader")

# Headers that denote the timestamp column (lower-cased, stripped).
_TIMESTAMP_HEADER_ALIASES = ("datetime", "date/time", "timestamp", "time", "date")

# Common explicit timestamp formats, tried in order before ISO parsing.
_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)

# Strip everything that is not part of a number (keeps digits, sign, dot, exponent).
_NUMERIC_CLEAN_RE = re.compile(r"[^\d.\-+eE]")


@dataclass(frozen=True)
class FieldSpec:
    """One canonical field in the target dataset's schema."""

    name: str
    type: str = "float"          # float | int | string
    min: float | None = None
    max: float | None = None
    # Optional explicit header aliases / substrings that map to this field.
    aliases: tuple[str, ...] = ()


@dataclass
class FieldSchema:
    """The target dataset's field schema plus column provenance.

    ``fields`` are the canonical columns. ``external_fields`` is the subset that
    must NOT be read from the uploaded CSV — they are fetched from an external
    provider (e.g. weather). Any header that maps to an external field is ignored
    so external data is never silently overridden by the file.
    """

    fields: tuple[FieldSpec, ...]
    external_fields: frozenset[str] = frozenset()

    @classmethod
    def from_host_schema(
        cls,
        fields_schema: Mapping[str, Mapping[str, Any]],
        external_fields: Iterable[str] = (),
    ) -> "FieldSchema":
        """Build from a host ``fields_schema`` dict (``{name: {type, min, max}}``)."""
        specs = tuple(
            FieldSpec(
                name=name,
                type=str(spec.get("type", "float")),
                min=spec.get("min"),
                max=spec.get("max"),
                aliases=tuple(spec.get("aliases", ()) or ()),
            )
            for name, spec in fields_schema.items()
        )
        return cls(fields=specs, external_fields=frozenset(external_fields))

    @property
    def file_fields(self) -> tuple[FieldSpec, ...]:
        """Canonical fields that are expected to come from the uploaded file."""
        return tuple(f for f in self.fields if f.name not in self.external_fields)

    def get(self, name: str) -> FieldSpec | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None


@dataclass
class SkippedRow:
    """A row (or cell) that was dropped during loading, with a reason."""

    line: int
    reason: str
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class LoadResult:
    """The validated, provenance-rich output of :func:`load_csv`."""

    records: list[dict[str, Any]]                       # [{"timestamp": iso, "values": {field: num}}]
    column_map: dict[str, str]                          # raw_header -> canonical field
    timestamp_header: str | None
    file_columns: list[str]                             # canonical fields taken from the file
    external_columns: list[str]                         # canonical fields deliberately NOT taken from file
    unmapped_headers: list[str]                         # headers we could not map (ignored)
    skipped: list[SkippedRow]
    total_rows: int
    date_start: str | None = None
    date_end: str | None = None

    @property
    def ingested_rows(self) -> int:
        return len(self.records)

    @property
    def skipped_rows(self) -> int:
        return len(self.skipped)

    def summary(self) -> dict[str, Any]:
        """A compact, serialisable provenance summary."""
        return {
            "total_rows": self.total_rows,
            "ingested_rows": self.ingested_rows,
            "skipped_rows": self.skipped_rows,
            "timestamp_header": self.timestamp_header,
            "column_map": self.column_map,
            "file_columns": self.file_columns,
            "external_columns": self.external_columns,
            "unmapped_headers": self.unmapped_headers,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "skipped_sample": [
                {"line": s.line, "reason": s.reason} for s in self.skipped[:10]
            ],
        }


# ── timestamp detection & parsing ────────────────────────────────────────────

def detect_timestamp_header(headers: Sequence[str]) -> str | None:
    """Return the raw header that carries the timestamp, or ``None``.

    Matches a known alias exactly first, then falls back to any header that
    *contains* a date/time token.
    """
    norm = [(h, (h or "").strip().lower()) for h in headers]
    for raw, key in norm:
        if key in _TIMESTAMP_HEADER_ALIASES:
            return raw
    for raw, key in norm:
        if any(tok in key for tok in ("datetime", "date", "time", "timestamp")):
            return raw
    return None


def _resolve_tz(tz: str | tzinfo | None) -> tzinfo:
    if tz is None:
        return timezone.utc
    if isinstance(tz, tzinfo):
        return tz
    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz)
        except Exception:
            logger.warning("Unknown timezone %r; falling back to UTC", tz)
    return timezone.utc


def parse_timestamp(raw: str, tz: str | tzinfo | None = None) -> datetime | None:
    """Parse a timestamp string into a timezone-aware :class:`datetime`.

    Naive inputs are localised to ``tz`` (default UTC). Timezone-aware inputs
    (ISO strings with an offset, or trailing ``Z``) keep their own zone. Returns
    ``None`` when the value cannot be parsed.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    zone = _resolve_tz(tz)
    dt: datetime | None = None

    # ISO 8601 (handles offsets and 'Z')
    iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        dt = None

    if dt is None:
        for fmt in _TIMESTAMP_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        return None

    # Localise naive datetimes; preserve aware ones.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)
    return dt


# ── header mapping ───────────────────────────────────────────────────────────

def _build_substring_rules(schema: FieldSchema) -> list[tuple[str, str]]:
    """Build ``(needle, canonical)`` substring rules from the schema.

    Each field's own name (lower-cased, separators stripped) and any explicit
    aliases become substring needles. Longer needles are tried first so specific
    matches win over generic ones.
    """
    rules: list[tuple[str, str]] = []
    for spec in schema.fields:
        needles = {spec.name.lower()}
        # name without unit-ish suffixes and separators, e.g. Generation_MW -> generation
        base = re.split(r"[_\s\-]", spec.name.lower())[0]
        if base:
            needles.add(base)
        for a in spec.aliases:
            if a:
                needles.add(a.strip().lower())
        for n in needles:
            if n:
                rules.append((n, spec.name))
    # Specific (longer) needles first.
    rules.sort(key=lambda r: len(r[0]), reverse=True)
    return rules


def build_header_map(
    headers: Sequence[str],
    schema: FieldSchema,
    timestamp_header: str | None = None,
) -> dict[str, str]:
    """Map raw feature headers to canonical schema field names.

    Resolution order per header: exact name → explicit alias → substring rule.
    Headers that resolve to an external-source field are intentionally dropped so
    external data is never taken from the file. The timestamp header is excluded.
    """
    rules = _build_substring_rules(schema)
    file_field_names = {f.name for f in schema.file_fields}
    external = set(schema.external_fields)

    mapping: dict[str, str] = {}
    used: set[str] = set()

    for h in headers:
        if h == timestamp_header:
            continue
        key = (h or "").strip().lower()
        if not key:
            continue

        canonical: str | None = None

        # exact canonical name
        for spec in schema.fields:
            if key == spec.name.lower() and spec.name not in used:
                canonical = spec.name
                break

        # explicit aliases
        if canonical is None:
            for spec in schema.fields:
                if spec.name in used:
                    continue
                if key in {a.strip().lower() for a in spec.aliases if a}:
                    canonical = spec.name
                    break

        # substring rules (ministry-style multi-word headers); pad to allow
        # word-boundary-ish matching of short tokens like ' temp '.
        if canonical is None:
            padded = f" {key} "
            for needle, target in rules:
                if target in used:
                    continue
                if needle in key or f" {needle} " in padded:
                    canonical = target
                    break

        if canonical is None:
            continue
        # Drop external-source fields — never take them from the file.
        if canonical in external:
            used.add(canonical)
            continue
        if canonical in file_field_names and canonical not in used:
            mapping[h] = canonical
            used.add(canonical)

    return mapping


# ── value cleaning & validation ──────────────────────────────────────────────

def strip_units(raw: Any) -> str:
    """Strip trailing/embedded units (`` MW``, ``%``, ``C``) from a numeric cell."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    return _NUMERIC_CLEAN_RE.sub("", s)


def _coerce_and_validate(
    spec: FieldSpec, raw: Any
) -> tuple[bool, float | int | str | None, str | None]:
    """Coerce a raw cell to the schema type and range-check it.

    Returns ``(ok, value, reason)``. ``ok`` False means the cell is dropped
    (value set to ``None``); ``reason`` explains why, for the skipped report.
    """
    if spec.type == "string":
        s = "" if raw is None else str(raw).strip()
        return (True, s or None, None)

    cleaned = strip_units(raw)
    if cleaned in ("", "-", "+", ".", "-.", "+."):
        return (True, None, None)  # genuinely empty → null, not an error

    try:
        num: float | int = float(cleaned)
    except ValueError:
        return (False, None, f"non-numeric value {raw!r}")

    if spec.type == "int":
        num = int(num)

    if spec.min is not None and num < spec.min:
        return (False, None, f"{spec.name}={num} below min {spec.min}")
    if spec.max is not None and num > spec.max:
        return (False, None, f"{spec.name}={num} above max {spec.max}")

    return (True, num, None)


# ── main entrypoint ──────────────────────────────────────────────────────────

def load_csv(
    source: str | io.TextIOBase | bytes,
    schema: FieldSchema,
    *,
    tz: str | tzinfo | None = None,
    skip_out_of_range: bool = True,
) -> LoadResult:
    """Parse and validate a timeseries CSV into upsert-ready records.

    Parameters
    ----------
    source:
        A filesystem path, raw bytes, raw CSV text, or an open text stream.
    schema:
        The target dataset's :class:`FieldSchema` (fetched live from the host).
    tz:
        Timezone for naive timestamps (IANA name or ``tzinfo``). Aware
        timestamps keep their own zone. Defaults to UTC.
    skip_out_of_range:
        When True (default) a value outside ``[min, max]`` drops that *cell*
        (set to null) and is logged in the skipped report; the row is kept if it
        still has a valid timestamp. When False, out-of-range values are kept.
    """
    text = _read_text(source)
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])

    ts_header = detect_timestamp_header(headers)
    column_map = build_header_map(headers, schema, ts_header)
    file_columns = sorted(set(column_map.values()))
    external_columns = sorted(schema.external_fields)
    mapped = set(column_map.keys()) | ({ts_header} if ts_header else set())
    unmapped = [h for h in headers if h not in mapped]

    records: list[dict[str, Any]] = []
    skipped: list[SkippedRow] = []
    total = 0
    min_ts: datetime | None = None
    max_ts: datetime | None = None

    # line 1 is the header; data starts at line 2
    for idx, row in enumerate(reader, start=2):
        total += 1

        if not ts_header:
            skipped.append(SkippedRow(idx, "no timestamp column detected", dict(row)))
            continue

        ts = parse_timestamp(row.get(ts_header, ""), tz)
        if ts is None:
            skipped.append(
                SkippedRow(idx, f"unparseable timestamp {row.get(ts_header)!r}", dict(row))
            )
            continue

        values: dict[str, Any] = {}
        for raw_header, canonical in column_map.items():
            spec = schema.get(canonical)
            if spec is None:
                continue
            ok, val, reason = _coerce_and_validate(spec, row.get(raw_header))
            if not ok:
                if skip_out_of_range:
                    skipped.append(SkippedRow(idx, reason or "invalid value", dict(row)))
                    values[canonical] = None
                    continue
            values[canonical] = val

        records.append({"timestamp": ts.isoformat(), "values": values})
        if min_ts is None or ts < min_ts:
            min_ts = ts
        if max_ts is None or ts > max_ts:
            max_ts = ts

    return LoadResult(
        records=records,
        column_map=column_map,
        timestamp_header=ts_header,
        file_columns=file_columns,
        external_columns=external_columns,
        unmapped_headers=unmapped,
        skipped=skipped,
        total_rows=total,
        date_start=min_ts.isoformat() if min_ts else None,
        date_end=max_ts.isoformat() if max_ts else None,
    )


def _read_text(source: str | io.TextIOBase | bytes) -> str:
    """Resolve ``source`` (path / bytes / text / stream) to CSV text (BOM-safe)."""
    if isinstance(source, bytes):
        return source.decode("utf-8-sig")
    if hasattr(source, "read"):
        return source.read()  # type: ignore[union-attr]
    s = str(source)
    # Heuristic: treat as a path if it has no newline and points at a file.
    if "\n" not in s and "," not in s:
        import os

        if os.path.exists(s):
            with open(s, "r", encoding="utf-8-sig", newline="") as f:
                return f.read()
    return s
