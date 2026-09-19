from django.urls import include, path

from gradevance import views
from gradevance.audit import RunAuditExportView
from gradevance.lti.ags_views import RunAgsPassbackView, RunAgsPreviewView
from gradevance.lti.deep_link_views import DeepLinkPreviewView
from gradevance.lti.nrps_views import NrpsRosterPreviewView
from gradevance.lti.oidc import LtiConfigView, LtiOidcLaunchView, LtiOidcLoginView
from gradevance.lti.tool_config import LtiToolConfigView
from gradevance.lti.tool_jwks import ToolJwksView
from gradevance.lti.views import LtiStatusView

urlpatterns = [
    path("me/", include("gradevance.me_urls")),
    path("summary/", views.SummaryView.as_view(), name="gradevance-summary"),
    path("profiles/", views.ProfileCatalogView.as_view(), name="gradevance-profiles"),
    path(
        "profiles/<str:pack_id>/",
        views.ProfileDetailView.as_view(),
        name="gradevance-profile-detail",
    ),
    path("knowledge-bases/", views.KnowledgeBaseListView.as_view(), name="gradevance-kbs"),
    path("examples/", views.DemoExamplesView.as_view(), name="gradevance-examples"),
    path("courses/", views.CourseListCreateView.as_view(), name="gradevance-courses"),
    path("courses/<uuid:course_id>/", views.CourseDetailView.as_view(), name="gradevance-course-detail"),
    path(
        "courses/<uuid:course_id>/enrollments/",
        views.CourseEnrollmentListCreateView.as_view(),
        name="gradevance-course-enrollments",
    ),
    path(
        "courses/<uuid:course_id>/enrollments/<uuid:enrollment_id>/",
        views.CourseEnrollmentDetailView.as_view(),
        name="gradevance-course-enrollment-detail",
    ),
    path("assignments/", views.AssignmentListCreateView.as_view(), name="gradevance-assignments"),
    path(
        "assignments/<uuid:assignment_id>/",
        views.AssignmentDetailView.as_view(),
        name="gradevance-assignment-detail",
    ),
    path(
        "assignments/<uuid:assignment_id>/batch-analyze/",
        views.AssignmentBatchAnalyzeView.as_view(),
        name="gradevance-assignment-batch-analyze",
    ),
    path("submissions/", views.SubmissionListCreateView.as_view(), name="gradevance-submissions"),
    path(
        "submissions/upload/",
        views.SubmissionUploadView.as_view(),
        name="gradevance-submission-upload",
    ),
    path(
        "submissions/<uuid:submission_id>/analyze/",
        views.SubmissionAnalyzeView.as_view(),
        name="gradevance-analyze",
    ),
    path("runs/", views.RunListView.as_view(), name="gradevance-runs"),
    path("runs/<uuid:run_id>/", views.RunDetailView.as_view(), name="gradevance-run-detail"),
    path("runs/<uuid:run_id>/edits/", views.ExpertEditCreateView.as_view(), name="gradevance-edits"),
    path("runs/<uuid:run_id>/release/", views.RunReleaseView.as_view(), name="gradevance-release"),
    path(
        "runs/<uuid:run_id>/audit-export/",
        RunAuditExportView.as_view(),
        name="gradevance-audit-export",
    ),
    path("review-queue/", views.ReviewQueueView.as_view(), name="gradevance-review-queue"),
    path("appeals/", views.AppealListView.as_view(), name="gradevance-appeals"),
    path(
        "appeals/<uuid:appeal_id>/resolve/",
        views.AppealResolveView.as_view(),
        name="gradevance-appeal-resolve",
    ),
    path("qa/summary/", views.QaSummaryView.as_view(), name="gradevance-qa-summary"),
    path("proposals/", views.ProposalListView.as_view(), name="gradevance-proposals"),
    path(
        "proposals/<uuid:proposal_id>/decide/",
        views.ProposalDecideView.as_view(),
        name="gradevance-proposal-decide",
    ),
    path(
        "proposals/<uuid:proposal_id>/bump/",
        views.ProposalBumpView.as_view(),
        name="gradevance-proposal-bump",
    ),
    path(
        "proposals/<uuid:proposal_id>/repin/",
        views.ProposalRepinView.as_view(),
        name="gradevance-proposal-repin",
    ),
    path("publish-gate/", views.PublishGatePreviewView.as_view(), name="gradevance-publish-gate"),
    path("calibration/", views.CalibrationPreviewView.as_view(), name="gradevance-calibration"),
    path(
        "calibration/segmentation-propose/",
        views.CalibrationSegmentationProposeView.as_view(),
        name="gradevance-calibration-seg-propose",
    ),
    path(
        "calibration/suggest-splits/",
        views.SuggestSplitsView.as_view(),
        name="gradevance-suggest-splits",
    ),
    path(
        "assignments/<uuid:assignment_id>/publish/",
        views.AssignmentPublishView.as_view(),
        name="gradevance-assignment-publish",
    ),
    path(
        "runs/<uuid:run_id>/ags-preview/",
        RunAgsPreviewView.as_view(),
        name="gradevance-ags-preview",
    ),
    path(
        "runs/<uuid:run_id>/ags-passback/",
        RunAgsPassbackView.as_view(),
        name="gradevance-ags-passback",
    ),
    path("lti/status/", LtiStatusView.as_view(), name="gradevance-lti-status"),
    path("lti/config/", LtiConfigView.as_view(), name="gradevance-lti-config"),
    path("lti/oidc/login/", LtiOidcLoginView.as_view(), name="gradevance-lti-oidc-login"),
    path("lti/oidc/launch/", LtiOidcLaunchView.as_view(), name="gradevance-lti-oidc-launch"),
    path("lti/deep-link/preview/", DeepLinkPreviewView.as_view(), name="gradevance-lti-deeplink"),
    path("lti/nrps/preview/", NrpsRosterPreviewView.as_view(), name="gradevance-lti-nrps"),
    path("lti/jwks/", ToolJwksView.as_view(), name="gradevance-lti-jwks"),
    path("lti/tool-config/", LtiToolConfigView.as_view(), name="gradevance-lti-tool-config"),
    path("accessibility/", views.AccessibilityChecklistView.as_view(), name="gradevance-a11y"),
]
