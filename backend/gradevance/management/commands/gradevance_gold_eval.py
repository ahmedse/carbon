"""Full-pipeline gold eval — agreement report vs held_out (Instrument Trust T3).

Runs FormativePipeline on gold full text (re-segment) and compares to expert
held_out labels. Does NOT invent a parallel eval service — reuses pipeline +
reliability helpers. Emits frozen JSON under docs/eduos/qa-evidence/.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gradevance.models import AnalysisRun, Assignment, Submission
from gradevance.services.packs import eduos_pack_root, find_profile_file_for_id, load_profile
from gradevance.services.pipeline import FormativePipelineService, code_segment, _SegDraft
from gradevance.services.publish import (
    engine_sd_labels_for_held_out,
    engine_sg_labels_for_held_out,
    load_held_out_rows,
)
from gradevance.services.reliability import adjacent_band_agreement, cohen_kappa, passes_reliability_gate


def _repo_root() -> Path:
    # backend/gradevance/management/commands/this → repo root
    return Path(__file__).resolve().parents[4]


def _align_f1(expert_segs: list[dict], engine_segs: list) -> dict:
    """Greedy span-overlap alignment F1 (word ranges)."""
    if not expert_segs or not engine_segs:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "matched": 0}

    def span(s):
        if isinstance(s, dict):
            return int(s.get("word_start") or 0), int(s.get("word_end") or 0)
        return int(getattr(s, "start_word", 0) or 0), int(getattr(s, "end_word", 0) or 0)

    matched = 0
    used = set()
    for ex in expert_segs:
        a0, a1 = span(ex)
        best_j, best_ov = None, 0
        for j, eng in enumerate(engine_segs):
            if j in used:
                continue
            b0, b1 = span(eng)
            ov = max(0, min(a1, b1) - max(a0, b0))
            if ov > best_ov:
                best_ov, best_j = ov, j
        if best_j is not None and best_ov > 0:
            used.add(best_j)
            matched += 1
    prec = matched / len(engine_segs) if engine_segs else 0.0
    rec = matched / len(expert_segs) if expert_segs else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "matched": matched,
    }


class Command(BaseCommand):
    help = "Run gold held_out through FormativePipeline; write GOLD-EVAL report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            default="naa_cycle1_exam_prep",
            help="Profile pack_id",
        )
        parser.add_argument("--profile-version", type=int, default=1)
        parser.add_argument(
            "--device-rel",
            default="",
            help="Override device pack_path relative to eduos root",
        )

    def handle(self, *args, **options):
        pack_id = options["profile"]
        version = options["profile_version"]
        loaded = load_profile(find_profile_file_for_id(pack_id, version))
        device_rel = options["device_rel"] or (loaded.profile.get("lct_device") or {}).get("pack_path")
        if not device_rel:
            self.stderr.write("No lct_device.pack_path")
            return

        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username="gold_eval_bot",
            defaults={"email": "gold_eval@eduos.local"},
        )
        asg, _ = Assignment.objects.get_or_create(
            title=f"[gold-eval] {pack_id}",
            defaults={
                "mode": Assignment.MODE_CALIBRATION,
                "status": Assignment.STATUS_PUBLISHED,
                "profile_pack_id": pack_id,
                "profile_version": version,
                "brief": {"stem": "Gold eval harness — not a live assignment."},
            },
        )

        rows = load_held_out_rows(device_rel)
        expert_sg, engine_preseg_sg = engine_sg_labels_for_held_out(device_rel)
        expert_sd, engine_preseg_sd = engine_sd_labels_for_held_out(device_rel)
        preseg_sg = passes_reliability_gate(
            expert_sg, engine_preseg_sg, minimum=0.6, dimension="semantic_gravity"
        )
        preseg_sd = (
            passes_reliability_gate(
                expert_sd, engine_preseg_sd, minimum=0.4, dimension="semantic_density"
            )
            if len(expert_sd) >= 3
            else None
        )

        pipeline = FormativePipelineService()
        essay_reports = []
        for row in rows:
            text = row.get("text") or ""
            if not text.strip():
                continue
            sub = Submission.objects.create(
                assignment=asg,
                student_user=user,
                text=text,
                word_count=len(text.split()),
                status=Submission.STATUS_DRAFT,
            )
            run = pipeline.analyze_submission(sub)
            eng_segs = list(run.segments.order_by("ordinal"))
            align = _align_f1(row.get("segments") or [], eng_segs)

            # Rubric vs expert_rubric_bands if present
            expert_bands = row.get("expert_rubric_bands") or {}
            engine_bands = {}
            for ev in run.rubric_scores.all():
                engine_bands[ev.criterion_id] = ev.band
            rubric_report = None
            if expert_bands:
                keys = sorted(expert_bands.keys())
                rubric_report = adjacent_band_agreement(
                    [expert_bands[k] for k in keys],
                    [engine_bands.get(k) or "" for k in keys],
                    band_order=["F", "E", "D", "C", "B", "A"],
                )
                rubric_report["expert"] = expert_bands
                rubric_report["engine"] = {k: engine_bands.get(k) for k in keys}

            essay_reports.append(
                {
                    "id": row.get("id"),
                    "run_id": str(run.id),
                    "word_count": sub.word_count,
                    "engine_status": run.status,
                    "alignment": align,
                    "engine_segment_count": len(eng_segs),
                    "expert_segment_count": len(row.get("segments") or []),
                    "rubric": rubric_report,
                    "advisory_bands": run.advisory_bands,
                }
            )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_dir = _repo_root() / "docs" / "eduos" / "qa-evidence"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / f"GOLD-EVAL-{stamp}.json"
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile_pack_id": pack_id,
            "profile_version": version,
            "device_rel": device_rel,
            "presegmented_gate": {
                "sg": preseg_sg,
                "sd": preseg_sd,
                "held_out_n_sg": len(expert_sg),
                "held_out_n_sd": len(expert_sd),
            },
            "essays": essay_reports,
            "notes": [
                "presegmented_gate = publish/calibration path (expert spans, no re-segment)",
                "essays[].alignment = full-pipeline re-segment vs expert spans",
                "rubric agreement only when expert_rubric_bands present on held_out row",
            ],
        }
        out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

        md = out_dir / f"GOLD-EVAL-{stamp}.md"
        md.write_text(
            "\n".join(
                [
                    f"# Gold eval — {pack_id} ({stamp})",
                    "",
                    f"- Device: `{device_rel}`",
                    f"- Preseg SG κ: **{(preseg_sg or {}).get('value')}** (n={len(expert_sg)})",
                    f"- Preseg SD κ: **{(preseg_sd or {}).get('value')}** (n={len(expert_sd)})",
                    f"- Essays run: {len(essay_reports)}",
                    f"- Artifact: `{out_json.name}`",
                    "",
                    "## Per essay",
                    "",
                    *[
                        f"- `{e['id']}`: align F1={e['alignment']['f1']} · "
                        f"segs eng/expert={e['engine_segment_count']}/{e['expert_segment_count']}"
                        + (
                            f" · rubric exact={(e['rubric'] or {}).get('exact')}"
                            if e.get("rubric")
                            else ""
                        )
                        for e in essay_reports
                    ],
                    "",
                    "See docs/eduos/GOLD-PROVENANCE.md. Learn must not claim expert agreement beyond this report.",
                ]
            ),
            encoding="utf-8",
        )
        # Stable latest symlink-style copy for QA console
        latest = out_dir / "GOLD-EVAL-LATEST.json"
        latest.write_text(out_json.read_text(encoding="utf-8"), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {out_json} and {md}"))
