"""Self-scoped learn API — ``gradevance/me/*`` (ADR-0042 / persona apps P1)."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.models import AnalysisRun, Appeal, Assignment, Course, Enrollment, Submission
from gradevance.permissions import GradevanceLearnAccess
from gradevance.serializers import (
    AnalysisRunSerializer,
    AppealSerializer,
    AssignmentSerializer,
    CourseSerializer,
    SubmissionSerializer,
)
from gradevance.services import FormativePipelineService
from gradevance.services.scope import (
    compute_my_status,
    courses_for_student,
    redact_run_payload_for_student,
    student_can_access_assignment,
)
from gradevance.services.submissions import ensure_summative_submit_review, resolve_create_status


def _enrich_me_assignment(user, asg: Assignment) -> dict:
    data = AssignmentSerializer(asg).data
    data["my_status"] = compute_my_status(user, asg)
    data["course_title"] = asg.course.name if asg.course_id else ""
    data["due_at"] = asg.due_at.isoformat() if asg.due_at else None
    try:
        from gradevance.services.packs import profile_detail_payload

        detail = profile_detail_payload(asg.profile_pack_id, asg.profile_version)
        bands = detail.get("band_descriptors") or {}
        if bands:
            data["band_expectations"] = bands
    except (FileNotFoundError, OSError, ValueError, TypeError):
        pass
    return data


class MeCourseListView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request):
        qs = courses_for_student(request.user).order_by("code")
        rows = list(qs[:200])
        return Response({"count": qs.count(), "results": CourseSerializer(rows, many=True).data})


class MeJoinCourseView(APIView):
    """Student join-by-code — enroll as student via Course.entry_code."""

    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def post(self, request):
        from gradevance.lti.roster_sync import ensure_enrollment

        code = (request.data.get("entry_code") or "").strip()
        if not code:
            return Response({"detail": "entry_code required"}, status=400)
        course = Course.objects.filter(entry_code=code).exclude(entry_code="").first()
        if course is None:
            return Response({"detail": "Invalid entry code"}, status=404)
        ensure_enrollment(
            course,
            request.user,
            Enrollment.ROLE_STUDENT,
            source=Enrollment.SOURCE_CODE,
        )
        return Response(CourseSerializer(course).data, status=status.HTTP_200_OK)


class MeAssignmentListView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request):
        course_ids = list(courses_for_student(request.user).values_list("id", flat=True))
        qs = Assignment.objects.select_related("course").filter(
            status=Assignment.STATUS_PUBLISHED,
            course_id__in=course_ids,
        )
        course_f = request.query_params.get("course")
        if course_f:
            if course_f not in {str(c) for c in course_ids}:
                return Response({"count": 0, "results": []})
            qs = qs.filter(course_id=course_f)
        rows = list(qs.order_by("-created_at")[:200])
        results = [_enrich_me_assignment(request.user, asg) for asg in rows]
        return Response({"count": qs.count(), "results": results})


class MeAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request, assignment_id):
        try:
            asg = Assignment.objects.select_related("course").get(pk=assignment_id)
        except Assignment.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        if not student_can_access_assignment(request.user, asg):
            return Response({"detail": "Not found"}, status=404)
        data = _enrich_me_assignment(request.user, asg)
        if asg.course_id:
            data["course_detail"] = CourseSerializer(asg.course).data
        return Response(data)


class MeSubmissionListCreateView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request):
        qs = Submission.objects.select_related("assignment").filter(student_user=request.user)
        assignment_id = request.query_params.get("assignment")
        if assignment_id:
            qs = qs.filter(assignment_id=assignment_id)
        rows = list(qs.order_by("-created_at")[:200])
        # Prefetch latest run per submission for Learn home coaching (ADR Learn Trust L1).
        sub_ids = [s.id for s in rows]
        latest_by_sub: dict = {}
        if sub_ids:
            for run in (
                AnalysisRun.objects.filter(submission_id__in=sub_ids)
                .order_by("submission_id", "-created_at")
            ):
                sid = run.submission_id
                if sid not in latest_by_sub:
                    latest_by_sub[sid] = run
        results = []
        for sub in rows:
            data = SubmissionSerializer(sub).data
            data["assignment_title"] = sub.assignment.title if sub.assignment_id else ""
            run = latest_by_sub.get(sub.id)
            if run is not None:
                data["latest_run"] = {
                    "id": str(run.id),
                    "coaching": run.coaching or {},
                }
            else:
                data["latest_run"] = None
            results.append(data)
        return Response({"count": qs.count(), "results": results})

    def post(self, request):
        data = dict(request.data or {})
        analyze = data.get("analyze") in (True, "true", "True", 1, "1")
        requested = data.get("status")
        status_value = resolve_create_status(requested=requested, analyze=analyze)
        data["status"] = status_value

        ser = SubmissionSerializer(data=data)
        ser.is_valid(raise_exception=True)
        assignment = ser.validated_data["assignment"]
        if not student_can_access_assignment(request.user, assignment):
            return Response({"detail": "Not enrolled for this assignment"}, status=403)
        text = ser.validated_data.get("text") or ""
        words = len(text.split())
        obj = ser.save(
            student_user=request.user,
            word_count=words,
            status=status_value,
        )
        payload = {"submission": SubmissionSerializer(obj).data}
        if analyze:
            run = FormativePipelineService().analyze_submission(obj)
            # Preserve intentional draft/submitted after coaching.
            if obj.status != status_value:
                obj.status = status_value
                obj.save(update_fields=["status", "updated_at"])
            run_data = redact_run_payload_for_student(run, AnalysisRunSerializer(run).data)
            payload["run"] = run_data
            payload["submission"] = SubmissionSerializer(obj).data

        if status_value == Submission.STATUS_SUBMITTED:
            ensure_summative_submit_review(obj)
            obj.refresh_from_db()
            payload["submission"] = SubmissionSerializer(obj).data

        return Response(payload, status=status.HTTP_201_CREATED)


class MeSubmissionDetailView(APIView):
    """PATCH own submission — draft autosave / submit for marking."""

    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def patch(self, request, submission_id):
        try:
            obj = Submission.objects.select_related("assignment").get(
                pk=submission_id, student_user=request.user
            )
        except Submission.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        if not student_can_access_assignment(request.user, obj.assignment):
            return Response({"detail": "Not found"}, status=404)

        new_status = request.data.get("status")
        if new_status is not None:
            if (
                obj.status
                in (Submission.STATUS_SUBMITTED, Submission.STATUS_ANALYZED)
                and new_status == Submission.STATUS_DRAFT
            ):
                return Response(
                    {"detail": "Cannot revert submitted submission to draft"},
                    status=400,
                )
            if new_status not in (Submission.STATUS_DRAFT, Submission.STATUS_SUBMITTED):
                return Response(
                    {"detail": "status must be draft or submitted"},
                    status=400,
                )

        ser = SubmissionSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        update_fields = []
        if "text" in ser.validated_data:
            obj.text = ser.validated_data["text"]
            obj.word_count = len((obj.text or "").split())
            update_fields.extend(["text", "word_count"])
        transitioning_to_submitted = False
        if "status" in ser.validated_data:
            next_status = ser.validated_data["status"]
            transitioning_to_submitted = (
                next_status == Submission.STATUS_SUBMITTED
                and obj.status == Submission.STATUS_DRAFT
            )
            obj.status = next_status
            update_fields.append("status")
        if update_fields:
            update_fields.append("updated_at")
            obj.save(update_fields=list(dict.fromkeys(update_fields)))

        if transitioning_to_submitted or (
            obj.status == Submission.STATUS_SUBMITTED
            and obj.assignment.mode == Assignment.MODE_SUMMATIVE
            and new_status == Submission.STATUS_SUBMITTED
        ):
            ensure_summative_submit_review(obj)
            obj.refresh_from_db()

        return Response(SubmissionSerializer(obj).data)


class MeRunDetailView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request, run_id):
        try:
            run = (
                AnalysisRun.objects.select_related(
                    "wave",
                    "submission",
                    "submission__assignment",
                    "submission__assignment__course",
                )
                .prefetch_related("segments__codes", "rubric_scores")
                .get(pk=run_id, submission__student_user=request.user)
            )
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        payload = redact_run_payload_for_student(run, AnalysisRunSerializer(run).data)
        asg = run.submission.assignment
        payload["assignment"] = AssignmentSerializer(asg).data
        return Response(payload)


class MeProgressView(APIView):
    """Own submissions with latest run summary for progress / home."""

    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request):
        subs = (
            Submission.objects.select_related("assignment")
            .filter(student_user=request.user)
            .order_by("-created_at")[:50]
        )
        results = []
        for sub in subs:
            run = (
                AnalysisRun.objects.select_related("wave")
                .filter(submission=sub)
                .order_by("-created_at")
                .first()
            )
            bands = None
            wave_points = []
            run_id = None
            released = False
            run_status = None
            if run is not None:
                run_id = str(run.id)
                released = bool(run.released)
                run_status = run.status
                redacted = redact_run_payload_for_student(
                    run, {"advisory_bands": run.advisory_bands or {}}
                )
                bands = redacted.get("advisory_bands")
                from django.core.exceptions import ObjectDoesNotExist

                try:
                    wave_points = list(run.wave.points or [])
                except ObjectDoesNotExist:
                    wave_points = []
            results.append(
                {
                    "assignment_id": str(sub.assignment_id),
                    "title": sub.assignment.title,
                    "submission_id": str(sub.id),
                    "run_id": run_id,
                    "status": sub.status,
                    "released": released,
                    "run_status": run_status,
                    "advisory_bands": bands,
                    "wave_points": wave_points or [],
                    "created_at": sub.created_at.isoformat() if sub.created_at else None,
                }
            )
        return Response({"count": len(results), "results": results})


class MeAppealListCreateView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def get(self, request):
        qs = Appeal.objects.select_related(
            "run",
            "run__submission",
            "run__submission__assignment",
            "student_user",
        ).filter(student_user=request.user)
        assignment_id = request.query_params.get("assignment")
        if assignment_id:
            qs = qs.filter(run__submission__assignment_id=assignment_id)
        rows = list(qs.order_by("-created_at")[:200])
        return Response(
            {"count": qs.count(), "results": AppealSerializer(rows, many=True).data}
        )

    def post(self, request):
        run_id = request.data.get("run")
        reason = (request.data.get("reason") or "").strip()
        if not run_id:
            return Response({"detail": "run required"}, status=400)
        if not reason:
            return Response({"detail": "reason required"}, status=400)
        try:
            run = AnalysisRun.objects.select_related(
                "submission", "submission__assignment"
            ).get(pk=run_id, submission__student_user=request.user)
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        asg = run.submission.assignment
        if asg.mode == Assignment.MODE_SUMMATIVE and not run.released:
            return Response(
                {"detail": "Summative appeals require a released run"},
                status=400,
            )
        # Formative: any finished analysis (complete or needs_review) may be appealed.
        finished = {
            AnalysisRun.STATUS_COMPLETE,
            AnalysisRun.STATUS_NEEDS_REVIEW,
        }
        if asg.mode == Assignment.MODE_FORMATIVE and run.status not in finished:
            return Response(
                {"detail": "Formative appeals require a finished analysis run"},
                status=400,
            )
        if asg.mode == Assignment.MODE_CALIBRATION:
            return Response({"detail": "Appeals not available for calibration"}, status=400)

        if Appeal.objects.filter(run=run, status=Appeal.STATUS_OPEN).exists():
            return Response({"detail": "An open appeal already exists for this run"}, status=400)

        appeal = Appeal.objects.create(
            run=run,
            student_user=request.user,
            reason=reason,
            status=Appeal.STATUS_OPEN,
        )
        return Response(AppealSerializer(appeal).data, status=status.HTTP_201_CREATED)


class MeAppealWithdrawView(APIView):
    permission_classes = [IsAuthenticated, GradevanceLearnAccess]

    def post(self, request, appeal_id):
        try:
            appeal = Appeal.objects.get(pk=appeal_id, student_user=request.user)
        except Appeal.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        if appeal.status != Appeal.STATUS_OPEN:
            return Response({"detail": "Only open appeals can be withdrawn"}, status=400)
        appeal.status = Appeal.STATUS_WITHDRAWN
        appeal.save(update_fields=["status", "updated_at"])
        return Response(AppealSerializer(appeal).data)
