"""Seed EduOS GradeVance demo: gold/raw LCT examples → assignments → analyzed runs."""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.constants import GRADEVANCE_STUDENTS_GROUP
from accounts.models import ScopedRole
from gradevance.lti.roster_sync import ensure_enrollment
from gradevance.models import Assignment, Course, Enrollment, Submission
from gradevance.services.demo_examples import DEMO_SPECS, collect_demo_texts
from gradevance.services.packs import find_profile_file_for_id, load_profile
from gradevance.services.pipeline import FormativePipelineService


class Command(BaseCommand):
    help = "Seed GradeVance demo assignments + LCT analyses from gold/held_out packs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-analyze",
            action="store_true",
            help="Only create assignments/submissions without analyzing.",
        )

    def handle(self, *args, **options):
        analyze = not options.get("no_analyze")
        User = get_user_model()
        author = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not author:
            self.stderr.write("No user — run ensure_eduos_admins first.")
            return

        course, _ = Course.objects.get_or_create(
            code="DEMO-LCT",
            defaults={
                "name": "GradeVance LCT demo course",
                "discipline": "multi_domain",
                "entry_code": "DEMO-LCT",
            },
        )
        if not (course.entry_code or "").strip():
            course.entry_code = "DEMO-LCT"
            course.save(update_fields=["entry_code", "updated_at"])

        ensure_enrollment(
            course, author, Enrollment.ROLE_INSTRUCTOR, source=Enrollment.SOURCE_MANUAL
        )

        password = os.environ.get("CARBON_ADMIN_PASSWORD") or "AdminPa_132"
        student, created = User.objects.get_or_create(
            username="gv_student",
            defaults={"email": "gv_student@eduos.local"},
        )
        if created or not student.has_usable_password():
            student.set_password(password)
            student.is_active = True
            student.save()
        else:
            # Keep password in sync with env when re-seeding demos.
            student.set_password(password)
            student.is_active = True
            student.save(update_fields=["password", "is_active"])

        students_group, _ = Group.objects.get_or_create(name=GRADEVANCE_STUDENTS_GROUP)
        ScopedRole.objects.get_or_create(
            user=student,
            group=students_group,
            org_unit=None,
            module=None,
            defaults={"is_active": True},
        )
        ensure_enrollment(
            course, student, Enrollment.ROLE_STUDENT, source=Enrollment.SOURCE_MANUAL
        )

        pipeline = FormativePipelineService()
        created_asg = 0
        created_sub = 0
        created_run = 0

        for spec in DEMO_SPECS:
            pack_id = spec["profile_pack_id"]
            version = spec["profile_version"]
            try:
                loaded = load_profile(find_profile_file_for_id(pack_id, version))
            except FileNotFoundError as exc:
                self.stdout.write(self.style.WARNING(f"  skip {pack_id}: {exc}"))
                continue

            pipeline_snap = loaded.profile.get("pipeline") or {}
            brief = dict(loaded.profile.get("brief") or {})
            if not (brief.get("stem") or "").strip():
                brief["stem"] = (
                    f"Demo stem for {spec['title']}: write a reflective response "
                    f"that moves between concrete experience and abstract insight "
                    f"(profile {pack_id})."
                )
            brief.setdefault("authored_by", "seed_gradevance_demo")

            asg, asg_created = Assignment.objects.update_or_create(
                title=spec["title"],
                profile_pack_id=pack_id,
                profile_version=version,
                defaults={
                    "course": course,
                    "mode": Assignment.MODE_FORMATIVE,
                    "status": Assignment.STATUS_PUBLISHED,
                    "pipeline_config_snapshot": pipeline_snap,
                    "brief": brief,
                    "created_by": author,
                },
            )
            if asg_created:
                created_asg += 1

            texts = collect_demo_texts(spec)
            if not texts:
                self.stdout.write(self.style.WARNING(f"  no texts for {pack_id}"))
                continue

            for ex in texts:
                existing = Submission.objects.filter(assignment=asg, text=ex["text"]).first()
                if existing:
                    sub = existing
                else:
                    sub = Submission.objects.create(
                        assignment=asg,
                        student_user=author,
                        text=ex["text"],
                        word_count=len(ex["text"].split()),
                    )
                    created_sub += 1

                if analyze and not sub.runs.exists():
                    run = pipeline.analyze_submission(sub)
                    created_run += 1
                    segs = run.segments.count()
                    codes = sum(s.codes.count() for s in run.segments.all())
                    wave = getattr(run, "wave", None)
                    metrics = (wave.metrics if wave else {}) or {}
                    self.stdout.write(
                        f"  ✓ {pack_id} · {ex['id']}: run={run.id} "
                        f"segs={segs} codes={codes} "
                        f"sg_range={metrics.get('sg_range')} "
                        f"transitions={metrics.get('transitions')}"
                    )
                elif analyze:
                    run = sub.runs.order_by("-created_at").first()
                    self.stdout.write(
                        f"  · {pack_id} · {ex['id']}: already analyzed "
                        f"run={run.id if run else '?'}"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Demo seed complete — assignments={created_asg} "
                f"submissions={created_sub} new_runs={created_run} "
                f"(course={course.code}, entry_code={course.entry_code})"
            )
        )
        self.stdout.write(
            f"  Student login: gv_student / "
            f"{'(CARBON_ADMIN_PASSWORD)' if os.environ.get('CARBON_ADMIN_PASSWORD') else 'AdminPa_132'} "
            f"— join code DEMO-LCT (already enrolled)"
        )
