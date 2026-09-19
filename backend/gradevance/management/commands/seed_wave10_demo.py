"""Create (or refresh) a 10-segment oscillating semantic-wave demo run."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gradevance.models import Assignment, Course, Enrollment, Submission
from gradevance.services.demo_examples import WAVE_10_EXAMPLE, wave_10_segment_spans
from gradevance.services.pipeline import FormativePipelineService, _apply_expert_segmentation


class Command(BaseCommand):
    help = "Seed a long 10-segment NAA reflective run for the rich wave chart demo."

    def handle(self, *args, **options):
        User = get_user_model()
        author = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not author:
            self.stderr.write("No user — create an admin first.")
            return

        course, _ = Course.objects.get_or_create(
            code="DEMO-WAVE",
            defaults={
                "name": "GradeVance wave demo",
                "discipline": "reflective_practice",
                "entry_code": "DEMO-WAVE",
            },
        )
        Enrollment.objects.get_or_create(
            course=course,
            user=author,
            defaults={"role": Enrollment.ROLE_INSTRUCTOR, "source": Enrollment.SOURCE_MANUAL},
        )

        asg, _ = Assignment.objects.get_or_create(
            course=course,
            title="10-segment semantic wave demo",
            defaults={
                "mode": Assignment.MODE_FORMATIVE,
                "status": Assignment.STATUS_PUBLISHED,
                "profile_pack_id": "naa_cycle1_exam_prep",
                "profile_version": 1,
                "created_by": author,
                "brief": {
                    "stem": (
                        "Write a reflective account that moves between concrete episodes "
                        "and transferable principles (semantic gravity wave)."
                    ),
                    "authored_by": "seed_wave10_demo",
                },
            },
        )
        if asg.status != Assignment.STATUS_PUBLISHED:
            asg.status = Assignment.STATUS_PUBLISHED
            asg.save(update_fields=["status", "updated_at"])

        text = WAVE_10_EXAMPLE["text"]
        sub, _ = Submission.objects.update_or_create(
            assignment=asg,
            external_student_key="demo-wave-10",
            defaults={
                "text": text,
                "student_user": author,
                "word_count": len(text.split()),
            },
        )

        run = FormativePipelineService().analyze_submission(sub)
        spans = wave_10_segment_spans()
        assert len(spans) == 10, len(spans)
        _apply_expert_segmentation(run, spans)
        run.refresh_from_db()
        n = run.segments.count()
        wave = getattr(run, "wave", None)
        pts = (wave.points if wave else []) or []
        levels = [p.get("profile_level") for p in pts]
        self.stdout.write(
            self.style.SUCCESS(
                f"Wave-10 demo ready · run={run.id} · segments={n} · levels={levels}\n"
                f"Open: /teach/runs/{run.id}"
            )
        )
