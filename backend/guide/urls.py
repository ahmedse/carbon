from django.urls import path

from guide.views import GuideDetailAPIView, GuideListAPIView, GuideProgressAPIView

app_name = "guide"

urlpatterns = [
    path("<str:app_id>/", GuideListAPIView.as_view(), name="list"),
    path("<str:app_id>/lessons/<str:lesson_id>/", GuideDetailAPIView.as_view(), name="detail"),
    path("<str:app_id>/lessons/<str:lesson_id>/progress/", GuideProgressAPIView.as_view(), name="progress"),
]
