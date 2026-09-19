"""GradeVance API — thin views; orchestration in services."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model

from gradevance.models import (
    AnalysisRun,
    Appeal,
    Assignment,
    Course,
    Enrollment,
    ExpertEdit,
    Proposal,
    ReviewItem,
    Submission,
)
from gradevance.permissions import (
    GradevanceManageAccess,
    GradevanceMarkAccess,
    GradevanceQaAccess,
    GradevanceReadOrSubmit,
    GradevanceViewAccess,
)
from gradevance.serializers import (
    AnalysisRunListSerializer,
    AnalysisRunSerializer,
    AppealSerializer,
    AssignmentSerializer,
    CourseSerializer,
    EnrollmentSerializer,
    ExpertEditSerializer,
    ReviewItemSerializer,
    SubmissionSerializer,
)
from gradevance.services import (
    FormativePipelineService,
    ReviewService,
    find_profile_file_for_id,
    list_profiles,
    load_profile,
)
from gradevance.services.pack_bump import PackBumpError, PackBumpService
from gradevance.services.publish import PublishGateError, assert_summative_publish_allowed, evaluate_publish_gate
from gradevance.services.repin import ProfileRepinService, RepinError


class SummaryView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        return Response(
            {
                "courses": Course.objects.count(),
                "assignments": Assignment.objects.count(),
                "submissions": Submission.objects.count(),
                "runs": AnalysisRun.objects.count(),
                "open_reviews": ReviewItem.objects.filter(status=ReviewItem.STATUS_OPEN).count(),
                "profiles_on_disk": len(list_profiles()),
            }
        )


class AccessibilityChecklistView(APIView):
    """WCAG checklist toward VPAT — not a conformance claim."""

    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        from gradevance.accessibility import accessibility_summary

        return Response(accessibility_summary())


class ProfileCatalogView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        return Response({"count": len(list_profiles()), "results": list_profiles()})


class ProfileDetailView(APIView):
    """Read-only pack drawer: anchors, band descriptors, brief, kb pin."""

    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request, pack_id):
        version = int(request.query_params.get("profile_version") or request.query_params.get("version") or 1)
        try:
            from gradevance.services.packs import profile_detail_payload

            return Response(profile_detail_payload(pack_id, version))
        except FileNotFoundError as exc:
            return Response({"detail": str(exc)}, status=404)


class KnowledgeBaseListView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        from gradevance.services.packs import list_knowledge_bases

        rows = list_knowledge_bases()
        return Response({"count": len(rows), "results": rows})


class DemoExamplesView(APIView):
    """Gold / held_out practice texts for Student desk example picker."""

    permission_classes = [IsAuthenticated, GradevanceReadOrSubmit]

    def get(self, request):
        from gradevance.services.demo_examples import list_demo_examples

        results = list_demo_examples()
        return Response({"count": len(results), "results": results})


class CourseListCreateView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        from gradevance.services.scope import teach_course_scope_ids

        qs = Course.objects.all()
        scope = teach_course_scope_ids(request.user)
        if scope is not None:
            qs = qs.filter(id__in=scope)
        rows = list(qs[:200])
        return Response({"count": qs.count(), "results": CourseSerializer(rows, many=True).data})

    def post(self, request):
        if not GradevanceManageAccess().has_permission(request, self):
            return Response({"detail": "gradevance:manage required"}, status=403)
        ser = CourseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(CourseSerializer(obj).data, status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request, course_id):
        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        asgs = Assignment.objects.filter(course=course)[:100]
        return Response(
            {
                "course": CourseSerializer(course).data,
                "assignments": AssignmentSerializer(asgs, many=True).data,
                "assignment_count": Assignment.objects.filter(course=course).count(),
            }
        )

    def patch(self, request, course_id):
        if not GradevanceManageAccess().has_permission(request, self):
            return Response({"detail": "gradevance:manage required"}, status=403)
        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        ser = CourseSerializer(course, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class CourseEnrollmentListCreateView(APIView):
    """Teach roster — list (mark/manage) + add/update (manage) enrollments."""

    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def _get_course(self, request, course_id):
        from gradevance.services.scope import teach_course_scope_ids

        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return None, Response({"detail": "Not found"}, status=404)
        scope = teach_course_scope_ids(request.user)
        if scope is not None and course.id not in scope:
            return None, Response({"detail": "Not found"}, status=404)
        return course, None

    def get(self, request, course_id):
        course, err = self._get_course(request, course_id)
        if err is not None:
            return err
        qs = Enrollment.objects.select_related("user").filter(course=course).order_by(
            "role", "user__username"
        )
        rows = list(qs[:500])
        return Response(
            {"count": qs.count(), "results": EnrollmentSerializer(rows, many=True).data}
        )

    def post(self, request, course_id):
        if not GradevanceManageAccess().has_permission(request, self):
            return Response({"detail": "gradevance:manage required"}, status=403)
        course, err = self._get_course(request, course_id)
        if err is not None:
            return err

        from gradevance.lti.roster_sync import ensure_enrollment

        role = (request.data.get("role") or "").strip()
        if role not in {
            Enrollment.ROLE_STUDENT,
            Enrollment.ROLE_TA,
            Enrollment.ROLE_INSTRUCTOR,
        }:
            return Response(
                {"detail": "role must be student, ta, or instructor"},
                status=400,
            )

        User = get_user_model()
        user = None
        user_id = request.data.get("user_id")
        username = (request.data.get("username") or "").strip()
        if user_id not in (None, ""):
            try:
                user = User.objects.get(pk=user_id)
            except (User.DoesNotExist, ValueError, TypeError):
                return Response({"detail": "user_id not found"}, status=400)
        elif username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({"detail": "username not found"}, status=400)
        else:
            return Response(
                {"detail": "username or user_id required"},
                status=400,
            )

        ens = ensure_enrollment(
            course, user, role, source=Enrollment.SOURCE_MANUAL
        )
        return Response(
            EnrollmentSerializer(ens).data,
            status=status.HTTP_201_CREATED,
        )


class CourseEnrollmentDetailView(APIView):
    """PATCH enrollment active/role — manage only, teach-scoped."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def patch(self, request, course_id, enrollment_id):
        from gradevance.services.scope import teach_course_scope_ids

        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        scope = teach_course_scope_ids(request.user)
        if scope is not None and course.id not in scope:
            return Response({"detail": "Not found"}, status=404)
        try:
            ens = Enrollment.objects.select_related("user").get(
                pk=enrollment_id, course=course
            )
        except Enrollment.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        data = {}
        if "active" in request.data:
            data["active"] = request.data.get("active")
        if "role" in request.data:
            role = (request.data.get("role") or "").strip()
            if role not in {
                Enrollment.ROLE_STUDENT,
                Enrollment.ROLE_TA,
                Enrollment.ROLE_INSTRUCTOR,
            }:
                return Response(
                    {"detail": "role must be student, ta, or instructor"},
                    status=400,
                )
            data["role"] = role
        if not data:
            return Response({"detail": "active and/or role required"}, status=400)

        ser = EnrollmentSerializer(ens, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(EnrollmentSerializer(ens).data)


class AssignmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        from gradevance.services.scope import teach_course_scope_ids

        qs = Assignment.objects.select_related("course").all()
        scope = teach_course_scope_ids(request.user)
        if scope is not None:
            qs = qs.filter(course_id__in=scope)
        course_id = request.query_params.get("course")
        if course_id:
            qs = qs.filter(course_id=course_id)
        status_f = request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        rows = list(qs[:200])
        return Response(
            {"count": qs.count(), "results": AssignmentSerializer(rows, many=True).data}
        )

    def post(self, request):
        if not GradevanceManageAccess().has_permission(request, self):
            return Response({"detail": "gradevance:manage required"}, status=403)
        data = dict(request.data or {})
        pack_id = data.get("profile_pack_id")
        version = int(data.get("profile_version") or 1)
        client_brief = data.get("brief") if isinstance(data.get("brief"), dict) else {}
        if pack_id and not data.get("pipeline_config_snapshot"):
            try:
                fname = find_profile_file_for_id(pack_id, version)
                loaded = load_profile(fname)
                data["pipeline_config_snapshot"] = loaded.profile.get("pipeline") or {}
                pack_brief = loaded.profile.get("brief") or {}
                data["brief"] = {**pack_brief, **(client_brief or {})}
                if not data.get("title"):
                    data["title"] = loaded.profile.get("name") or pack_id
            except FileNotFoundError as exc:
                return Response({"detail": str(exc)}, status=400)
        elif client_brief is not None:
            data["brief"] = client_brief
        ser = AssignmentSerializer(data=data)
        ser.is_valid(raise_exception=True)
        if (
            ser.validated_data.get("status") == Assignment.STATUS_PUBLISHED
            and ser.validated_data.get("mode") == Assignment.MODE_SUMMATIVE
        ):
            try:
                gate = assert_summative_publish_allowed(
                    ser.validated_data["profile_pack_id"],
                    int(ser.validated_data.get("profile_version") or 1),
                )
            except (PublishGateError, FileNotFoundError) as exc:
                return Response({"detail": str(exc)}, status=400)
        else:
            gate = None
        obj = ser.save(created_by=request.user)
        payload = AssignmentSerializer(obj).data
        if gate:
            payload["publish_gate"] = gate
        return Response(payload, status=status.HTTP_201_CREATED)


class AssignmentDetailView(APIView):
    """Professor assignment hub: stem/config + submissions + runs."""

    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request, assignment_id):
        try:
            asg = Assignment.objects.select_related("course").get(pk=assignment_id)
        except Assignment.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        subs = Submission.objects.filter(assignment=asg).select_related("student_user").order_by("-created_at")[:100]
        runs = (
            AnalysisRun.objects.filter(submission__assignment=asg)
            .select_related("submission")
            .order_by("-created_at")[:100]
        )
        asg_data = AssignmentSerializer(asg).data
        if asg.course_id:
            asg_data["course_detail"] = CourseSerializer(asg.course).data
        return Response(
            {
                "assignment": asg_data,
                "submissions": SubmissionSerializer(subs, many=True).data,
                "runs": AnalysisRunListSerializer(runs, many=True).data,
                "counts": {
                    "submissions": Submission.objects.filter(assignment=asg).count(),
                    "runs": AnalysisRun.objects.filter(submission__assignment=asg).count(),
                    "open_reviews": ReviewItem.objects.filter(
                        run__submission__assignment=asg,
                        status__in=[ReviewItem.STATUS_OPEN, ReviewItem.STATUS_IN_PROGRESS],
                    ).count(),
                },
            }
        )

    def patch(self, request, assignment_id):
        if not GradevanceManageAccess().has_permission(request, self):
            return Response({"detail": "gradevance:manage required"}, status=403)
        try:
            asg = Assignment.objects.get(pk=assignment_id)
        except Assignment.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        data = dict(request.data or {})
        if isinstance(data.get("brief"), dict):
            incoming = data["brief"]
            if asg.status != Assignment.STATUS_DRAFT:
                # Published: only KB pin / note may change (RULE_32 — no silent stem rewrite).
                allowed = {k: incoming[k] for k in ("kb", "kb_note") if k in incoming}
                disallowed = set(incoming.keys()) - {"kb", "kb_note"}
                if disallowed:
                    return Response(
                        {
                            "detail": (
                                "Stem/instructions are frozen on published assignments. "
                                "Save a draft to edit the stem, or pin KB only."
                            ),
                            "disallowed_brief_keys": sorted(disallowed),
                        },
                        status=400,
                    )
                data["brief"] = {**(asg.brief or {}), **allowed}
            else:
                data["brief"] = {**(asg.brief or {}), **incoming}
        next_status = data.get("status", asg.status)
        next_mode = data.get("mode", asg.mode)
        if next_status == Assignment.STATUS_PUBLISHED and next_mode == Assignment.MODE_SUMMATIVE:
            try:
                assert_summative_publish_allowed(
                    data.get("profile_pack_id") or asg.profile_pack_id,
                    int(data.get("profile_version") or asg.profile_version or 1),
                )
            except (PublishGateError, FileNotFoundError) as exc:
                return Response({"detail": str(exc)}, status=400)
        ser = AssignmentSerializer(asg, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


def _is_course_staff(request, view) -> bool:
    """Marker/manager (or admin) — may read cohort submissions. Students may not."""
    return GradevanceMarkAccess().has_permission(request, view)


class SubmissionListCreateView(APIView):
    permission_classes = [IsAuthenticated, GradevanceReadOrSubmit]

    def get(self, request):
        qs = Submission.objects.select_related("assignment").all()
        if not _is_course_staff(request, self):
            # P0 privacy scope (GRADEVANCE-PERSONA-APPS §2.2): submit-only callers
            # see only their own rows — never another student's reflective text.
            qs = qs.filter(student_user=request.user)
        assignment_id = request.query_params.get("assignment")
        if assignment_id:
            qs = qs.filter(assignment_id=assignment_id)
        rows = list(qs[:200])
        return Response(
            {"count": qs.count(), "results": SubmissionSerializer(rows, many=True).data}
        )

    def post(self, request):
        ser = SubmissionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        text = ser.validated_data.get("text") or ""
        words = len(text.split())
        obj = ser.save(student_user=request.user, word_count=words)
        auto = request.data.get("analyze") in (True, "true", "True", 1, "1")
        payload = {"submission": SubmissionSerializer(obj).data}
        if auto:
            run = FormativePipelineService().analyze_submission(obj)
            payload["run"] = AnalysisRunSerializer(run).data
        return Response(payload, status=status.HTTP_201_CREATED)


class SubmissionAnalyzeView(APIView):
    permission_classes = [IsAuthenticated, GradevanceReadOrSubmit]

    def post(self, request, submission_id):
        qs = Submission.objects.select_related("assignment")
        if not _is_course_staff(request, self):
            qs = qs.filter(student_user=request.user)
        try:
            sub = qs.get(pk=submission_id)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        run = FormativePipelineService().analyze_submission(sub)
        return Response(AnalysisRunSerializer(run).data, status=status.HTTP_201_CREATED)


class SubmissionUploadView(APIView):
    """Accept .txt/.md upload → Submission.text (no binary SoR yet)."""

    permission_classes = [IsAuthenticated, GradevanceReadOrSubmit]

    def post(self, request):
        assignment_id = request.data.get("assignment")
        if not assignment_id:
            return Response({"detail": "assignment required"}, status=400)
        try:
            asg = Assignment.objects.get(pk=assignment_id)
        except Assignment.DoesNotExist:
            return Response({"detail": "Assignment not found"}, status=404)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required (.txt or .md)"}, status=400)
        name = (upload.name or "upload.txt").lower()
        if not (name.endswith(".txt") or name.endswith(".md") or name.endswith(".text")):
            return Response(
                {"detail": "Only .txt / .md text uploads are supported in Phase C"},
                status=400,
            )
        raw = upload.read()
        if len(raw) > 2_000_000:
            return Response({"detail": "File too large (max 2MB)"}, status=400)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
        text = text.strip()
        if not text:
            return Response({"detail": "Uploaded file is empty"}, status=400)
        words = len(text.split())
        sub = Submission.objects.create(
            assignment=asg,
            student_user=request.user,
            text=text,
            word_count=words,
            external_student_key=(upload.name or "")[:120],
        )
        payload = {
            "submission": SubmissionSerializer(sub).data,
            "filename": upload.name,
        }
        auto = request.data.get("analyze") in (True, "true", "True", 1, "1")
        if auto:
            run = FormativePipelineService().analyze_submission(sub)
            payload["run"] = AnalysisRunSerializer(run).data
        return Response(payload, status=status.HTTP_201_CREATED)


class AssignmentBatchAnalyzeView(APIView):
    """Analyze all submissions for an assignment that lack a complete run (or force all)."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request, assignment_id):
        try:
            asg = Assignment.objects.get(pk=assignment_id)
        except Assignment.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        force = request.data.get("force") in (True, "true", "True", 1, "1")
        limit = min(int(request.data.get("limit") or 50), 100)
        subs = list(Submission.objects.filter(assignment=asg).order_by("created_at")[:limit])
        pipeline = FormativePipelineService()
        created = []
        skipped = []
        errors = []
        for sub in subs:
            has_run = AnalysisRun.objects.filter(submission=sub).exclude(
                status=AnalysisRun.STATUS_FAILED
            ).exists()
            if has_run and not force:
                skipped.append(str(sub.id))
                continue
            try:
                run = pipeline.analyze_submission(sub)
                created.append({"submission_id": str(sub.id), "run_id": str(run.id)})
            except Exception as exc:  # noqa: BLE001 — cohort batch continues
                errors.append({"submission_id": str(sub.id), "detail": str(exc)[:240]})
        return Response(
            {
                "assignment_id": str(asg.id),
                "analyzed": len(created),
                "skipped": len(skipped),
                "errors": errors,
                "runs": created,
            }
        )


class RunDetailView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request, run_id):
        try:
            run = (
                AnalysisRun.objects.select_related(
                    "wave", "submission", "submission__assignment", "submission__assignment__course"
                )
                .prefetch_related("segments__codes", "rubric_scores")
                .get(pk=run_id)
            )
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        payload = AnalysisRunSerializer(run).data
        asg = run.submission.assignment
        asg_data = AssignmentSerializer(asg).data
        if asg.course_id:
            asg_data["course_detail"] = CourseSerializer(asg.course).data
        payload["assignment"] = asg_data
        payload["submission_detail"] = SubmissionSerializer(run.submission).data
        return Response(payload)


class RunListView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request):
        from gradevance.services.scope import teach_course_scope_ids

        qs = AnalysisRun.objects.select_related("submission", "submission__assignment").all()
        scope = teach_course_scope_ids(request.user)
        if scope is not None:
            qs = qs.filter(submission__assignment__course_id__in=scope)
        assignment_id = request.query_params.get("assignment")
        submission_id = request.query_params.get("submission")
        if assignment_id:
            qs = qs.filter(submission__assignment_id=assignment_id)
        if submission_id:
            qs = qs.filter(submission_id=submission_id)
        rows = list(qs[:100])
        return Response(
            {"count": qs.count(), "results": AnalysisRunListSerializer(rows, many=True).data}
        )


class CalibrationPreviewView(APIView):
    """Professor calibration: held-out expert vs engine SG labels + κ for a profile."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def get(self, request):
        pack_id = request.query_params.get("profile_pack_id") or "naa_cycle1_exam_prep"
        version = int(request.query_params.get("profile_version") or 1)
        try:
            loaded = load_profile(find_profile_file_for_id(pack_id, version))
        except FileNotFoundError as exc:
            return Response({"detail": str(exc)}, status=404)
        # Calibration proves the instrument before stakes — always evaluate summative gate
        # even when the pack file defaults to formative (Instrument Trust smoke).
        gate = evaluate_publish_gate(loaded, as_mode="summative")
        device = (loaded.profile.get("lct_device") or {})
        device_rel = device.get("pack_path") or ""
        from gradevance.services.publish import (
            engine_sd_labels_for_held_out,
            engine_sg_labels_for_held_out,
            load_held_out_rows,
        )

        pairs = []
        if device_rel:
            expert, engine = engine_sg_labels_for_held_out(device_rel)
            expert_sd, engine_sd = engine_sd_labels_for_held_out(device_rel)
            rows = load_held_out_rows(device_rel)
            flat_i = 0
            sd_i = 0
            for row in rows:
                for seg in row.get("segments") or []:
                    eng_sd = None
                    if seg.get("sd_label"):
                        eng_sd = engine_sd[sd_i] if sd_i < len(engine_sd) else None
                        sd_i += 1
                    pairs.append(
                        {
                            "example_id": row.get("id"),
                            "segment_index": seg.get("segment_index"),
                            "text": (seg.get("text") or "")[:240],
                            "expert_sg": seg.get("sg_label")
                            or (expert[flat_i] if flat_i < len(expert) else None),
                            "engine_sg": engine[flat_i] if flat_i < len(engine) else None,
                            "expert_sd": seg.get("sd_label"),
                            "engine_sd": eng_sd,
                        }
                    )
                    flat_i += 1
        # Surface both dimensions on gate for Calibration / QA UI
        if isinstance(gate, dict) and gate.get("reliability") and isinstance(gate["reliability"], dict):
            gate = {
                **gate,
                "kappa": gate.get("kappa") or gate["reliability"].get("value"),
                "kappa_sd": gate.get("kappa_sd"),
            }
        return Response(
            {
                "profile_pack_id": pack_id,
                "profile_version": version,
                "profile_name": loaded.profile.get("name"),
                "lct_device": device,
                "rubric_pack": loaded.profile.get("rubric_pack"),
                "pipeline": loaded.profile.get("pipeline"),
                "publish_gate": gate,
                "segment_pairs": pairs,
                "pair_count": len(pairs),
            }
        )


class ReviewQueueView(APIView):
    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def get(self, request):
        from gradevance.services.scope import teach_course_scope_ids

        open_statuses = [ReviewItem.STATUS_OPEN, ReviewItem.STATUS_IN_PROGRESS]
        qs = ReviewItem.objects.select_related("run").filter(status__in=open_statuses)
        scope = teach_course_scope_ids(request.user)
        if scope is not None:
            qs = qs.filter(run__submission__assignment__course_id__in=scope)
        rows = list(qs.order_by("-priority", "created_at")[:100])
        return Response(
            {
                "count": qs.count(),
                "results": ReviewItemSerializer(rows, many=True).data,
            }
        )


class ExpertEditCreateView(APIView):
    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def post(self, request, run_id):
        try:
            run = AnalysisRun.objects.get(pk=run_id)
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        data = request.data or {}
        review_item = None
        rid = data.get("review_item")
        if rid:
            review_item = ReviewItem.objects.filter(pk=rid, run=run).first()
        edit = ReviewService().apply_edit(
            run=run,
            editor=request.user,
            edit_kind=data.get("edit_kind") or ExpertEdit.KIND_OTHER,
            before=data.get("before") or {},
            after=data.get("after") or {},
            rationale=data.get("rationale") or "",
            review_item=review_item,
            resolve=bool(data.get("resolve")),
        )
        return Response(ExpertEditSerializer(edit).data, status=status.HTTP_201_CREATED)


class RunReleaseView(APIView):
    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def post(self, request, run_id):
        try:
            run = AnalysisRun.objects.select_related("submission__assignment").get(pk=run_id)
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        run = ReviewService().release_summative(run, request.user)
        return Response(AnalysisRunListSerializer(run).data)


class ProposalListView(APIView):
    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def get(self, request):
        qs = Proposal.objects.all()[:100]
        results = [
            {
                "id": str(p.id),
                "kind": p.kind,
                "status": p.status,
                "payload": p.payload,
                "source_edit_ids": p.source_edit_ids,
                "created_at": p.created_at,
            }
            for p in qs
        ]
        return Response({"count": Proposal.objects.count(), "results": results})


class ProposalDecideView(APIView):
    """Accept/reject a proposal. Accept marks proposed→accepted; pack bump is gated."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request, proposal_id):
        try:
            prop = Proposal.objects.get(pk=proposal_id)
        except Proposal.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        decision = (request.data or {}).get("decision")
        from django.utils import timezone as dj_tz
        from gradevance.services.canary import evaluate_canary

        if decision == "accept":
            # Optional canary payload from client (held-out labels).
            data = request.data or {}
            expert = data.get("expert_labels") or []
            engine = data.get("engine_labels") or []
            held_out_n = int(data.get("held_out_n") or len(expert) or 0)
            minimum = float(data.get("minimum_kappa") or 0.6)
            if expert and engine:
                canary = evaluate_canary(
                    expert_labels=expert,
                    engine_labels=engine,
                    minimum_kappa=minimum,
                    held_out_n=held_out_n,
                )
                if not canary.allowed:
                    return Response(
                        {
                            "detail": "Canary gate failed",
                            "reason": canary.reason,
                            "reliability": canary.reliability,
                        },
                        status=400,
                    )
            prop.status = Proposal.STATUS_ACCEPTED
            prop.payload = {
                **(prop.payload or {}),
                "accepted_note": (
                    "Activate for new runs only — never silent cohort rewrite."
                ),
            }
        elif decision == "reject":
            prop.status = Proposal.STATUS_REJECTED
        elif decision == "propose":
            prop.status = Proposal.STATUS_PROPOSED
        else:
            return Response({"detail": "decision must be accept|reject|propose"}, status=400)
        prop.decided_at = dj_tz.now()
        prop.save(update_fields=["status", "decided_at", "payload"])
        return Response(
            {
                "id": str(prop.id),
                "status": prop.status,
                "note": "Accepted proposals do not silently regrade cohorts; activate via pack bump + canary.",
            }
        )


class ProposalBumpView(APIView):
    """Write a draft TranslationDevice bump from an accepted proposal."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request, proposal_id):
        try:
            prop = Proposal.objects.get(pk=proposal_id)
        except Proposal.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        data = request.data or {}
        try:
            result = PackBumpService().bump_device_from_proposal(
                prop,
                source_pack_rel=data.get("source_pack_rel")
                or "engines/lct_semantics/naa_reflective_v1",
                expert_labels=data.get("expert_labels"),
                engine_labels=data.get("engine_labels"),
                held_out_n=data.get("held_out_n"),
                minimum_kappa=float(data.get("minimum_kappa") or 0.6),
                require_canary=bool(data.get("require_canary", False)),
            )
        except PackBumpError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=status.HTTP_201_CREATED)


class ProposalRepinView(APIView):
    """Create a new AssignmentProfile pinning the bumped device (draft assignments only)."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request, proposal_id):
        try:
            prop = Proposal.objects.get(pk=proposal_id)
        except Proposal.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        data = request.data or {}
        try:
            result = ProfileRepinService().repin_from_proposal(
                prop,
                base_profile_id=data.get("base_profile_id") or "naa_cycle1_exam_prep",
                base_profile_version=int(data.get("base_profile_version") or 1),
                update_draft_assignments=data.get("update_draft_assignments", True) is not False,
            )
        except RepinError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=status.HTTP_201_CREATED)


class PublishGatePreviewView(APIView):
    """Preview held-out κ gate for a profile without publishing."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def get(self, request):
        pack_id = request.query_params.get("profile_pack_id")
        version = int(request.query_params.get("profile_version") or 1)
        as_mode = request.query_params.get("as_mode") or None
        if not pack_id:
            return Response({"detail": "profile_pack_id required"}, status=400)
        try:
            loaded = load_profile(find_profile_file_for_id(pack_id, version))
        except FileNotFoundError as exc:
            return Response({"detail": str(exc)}, status=404)
        return Response(evaluate_publish_gate(loaded, as_mode=as_mode))


class AssignmentPublishView(APIView):
    """Transition draft → published with summative κ gate when required."""

    permission_classes = [IsAuthenticated, GradevanceManageAccess]

    def post(self, request, assignment_id):
        try:
            asg = Assignment.objects.get(pk=assignment_id)
        except Assignment.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        gate = None
        data = request.data or {}
        qa_override = data.get("qa_override") in (True, "true", "True", 1, "1")
        if asg.mode == Assignment.MODE_SUMMATIVE:
            try:
                gate = assert_summative_publish_allowed(asg.profile_pack_id, asg.profile_version)
            except (PublishGateError, FileNotFoundError) as exc:
                if qa_override:
                    from gradevance.permissions import _can

                    if not _can(request.user, "gradevance:qa") and not _can(
                        request.user, "gradevance:manage"
                    ):
                        return Response(
                            {"detail": "qa_override requires gradevance:qa or manage"},
                            status=403,
                        )
                    gate = {
                        "required": True,
                        "passed": False,
                        "overridden": True,
                        "reason": str(exc),
                        "override_rationale": data.get("override_rationale") or "",
                    }
                else:
                    return Response({"detail": str(exc)}, status=400)
        asg.status = Assignment.STATUS_PUBLISHED
        # Freeze pipeline snapshot from pack if empty.
        if not asg.pipeline_config_snapshot:
            try:
                loaded = load_profile(
                    find_profile_file_for_id(asg.profile_pack_id, asg.profile_version)
                )
                asg.pipeline_config_snapshot = loaded.profile.get("pipeline") or {}
            except FileNotFoundError:
                pass
        if gate and gate.get("overridden"):
            snap = dict(asg.pipeline_config_snapshot or {})
            snap["publish_qa_override"] = {
                "reason": gate.get("reason"),
                "rationale": gate.get("override_rationale"),
            }
            asg.pipeline_config_snapshot = snap
        asg.save(update_fields=["status", "pipeline_config_snapshot", "updated_at"])
        payload = AssignmentSerializer(asg).data
        if gate:
            payload["publish_gate"] = gate
        return Response(payload)


class AppealListView(APIView):
    """Teach appeals inbox — scoped via teach_course_scope_ids."""

    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def get(self, request):
        from gradevance.services.scope import teach_course_scope_ids

        qs = Appeal.objects.select_related(
            "run",
            "run__submission",
            "run__submission__assignment",
            "run__submission__assignment__course",
            "student_user",
            "resolved_by",
        )
        scope = teach_course_scope_ids(request.user)
        if scope is not None:
            qs = qs.filter(run__submission__assignment__course_id__in=scope)
        status_f = request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        rows = list(qs.order_by("-created_at")[:200])
        return Response(
            {"count": qs.count(), "results": AppealSerializer(rows, many=True).data}
        )


class AppealResolveView(APIView):
    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def post(self, request, appeal_id):
        from gradevance.services.scope import teach_course_scope_ids

        try:
            appeal = Appeal.objects.select_related(
                "run__submission__assignment"
            ).get(pk=appeal_id)
        except Appeal.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        scope = teach_course_scope_ids(request.user)
        course_id = appeal.run.submission.assignment.course_id
        if scope is not None and (course_id is None or course_id not in scope):
            return Response({"detail": "Not found"}, status=404)

        if appeal.status != Appeal.STATUS_OPEN:
            return Response({"detail": "Appeal is not open"}, status=400)

        resolution = (request.data.get("resolution") or "").strip()
        new_status = (request.data.get("status") or "").strip()
        if new_status not in (Appeal.STATUS_ACCEPTED, Appeal.STATUS_REJECTED):
            return Response(
                {"detail": "status must be accepted or rejected"},
                status=400,
            )
        if not resolution:
            return Response({"detail": "resolution required"}, status=400)

        appeal.resolution = resolution
        appeal.status = new_status
        appeal.resolved_by = request.user
        appeal.save(update_fields=["resolution", "status", "resolved_by", "updated_at"])
        return Response(AppealSerializer(appeal).data)


class QaSummaryView(APIView):
    """QA console summary — open appeals/reviews + calibration hint + gold eval."""

    permission_classes = [IsAuthenticated, GradevanceQaAccess]

    def get(self, request):
        open_appeals = Appeal.objects.filter(status=Appeal.STATUS_OPEN).count()
        open_reviews = ReviewItem.objects.filter(
            status__in=[ReviewItem.STATUS_OPEN, ReviewItem.STATUS_IN_PROGRESS]
        ).count()
        profiles_on_disk = len(list_profiles())

        gold_eval = None
        try:
            import json
            from pathlib import Path

            # views.py lives at backend/gradevance/views.py → parents[2] = repo root
            latest = (
                Path(__file__).resolve().parents[2]
                / "docs"
                / "eduos"
                / "qa-evidence"
                / "GOLD-EVAL-LATEST.json"
            )
            if latest.is_file():
                payload = json.loads(latest.read_text(encoding="utf-8"))
                pre = (payload.get("presegmented_gate") or {}).get("sg") or {}
                gold_eval = {
                    "generated_at": payload.get("generated_at"),
                    "sg_kappa": pre.get("value"),
                    "sd_kappa": ((payload.get("presegmented_gate") or {}).get("sd") or {}).get(
                        "value"
                    ),
                    "essay_count": len(payload.get("essays") or []),
                    "artifact": "docs/eduos/qa-evidence/GOLD-EVAL-LATEST.json",
                }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            gold_eval = None

        kappa = None
        kappa_sd = None
        try:
            from gradevance.services.packs import find_profile_file_for_id, load_profile
            from gradevance.services.publish import evaluate_publish_gate

            loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
            gate = evaluate_publish_gate(loaded, as_mode="summative")
            rel = gate.get("reliability") or {}
            kappa = gate.get("kappa") or (rel.get("value") if isinstance(rel, dict) else None)
            kappa_sd = gate.get("kappa_sd")
        except Exception:  # noqa: BLE001 — QA summary is best-effort
            pass

        return Response(
            {
                "open_appeals": open_appeals,
                "open_reviews": open_reviews,
                "profiles_on_disk": profiles_on_disk,
                "profiles_hint": (
                    f"{profiles_on_disk} assignment profile(s) available — "
                    "open Calibration for held-out κ."
                ),
                "fairness_note": (
                    "Summative bands stay withheld until release; sample audit exports "
                    "from the run workbench before accreditation review."
                ),
                "calibration_path": "calibration/",
                "kappa": kappa,
                "kappa_sd": kappa_sd,
                "gold_eval": gold_eval,
                "default_pack_id": "naa_cycle1_exam_prep",
            }
        )
