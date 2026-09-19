"""Learn persona routes — mounted at ``gradevance/me/``."""
from django.urls import path

from gradevance import me_views

urlpatterns = [
    path("courses/", me_views.MeCourseListView.as_view(), name="gradevance-me-courses"),
    path("join/", me_views.MeJoinCourseView.as_view(), name="gradevance-me-join"),
    path("assignments/", me_views.MeAssignmentListView.as_view(), name="gradevance-me-assignments"),
    path(
        "assignments/<uuid:assignment_id>/",
        me_views.MeAssignmentDetailView.as_view(),
        name="gradevance-me-assignment-detail",
    ),
    path(
        "submissions/",
        me_views.MeSubmissionListCreateView.as_view(),
        name="gradevance-me-submissions",
    ),
    path(
        "submissions/<uuid:submission_id>/",
        me_views.MeSubmissionDetailView.as_view(),
        name="gradevance-me-submission-detail",
    ),
    path("runs/<uuid:run_id>/", me_views.MeRunDetailView.as_view(), name="gradevance-me-run-detail"),
    path("progress/", me_views.MeProgressView.as_view(), name="gradevance-me-progress"),
    path("appeals/", me_views.MeAppealListCreateView.as_view(), name="gradevance-me-appeals"),
    path(
        "appeals/<uuid:appeal_id>/withdraw/",
        me_views.MeAppealWithdrawView.as_view(),
        name="gradevance-me-appeal-withdraw",
    ),
]
