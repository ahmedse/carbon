# mdm/urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    ReferenceSetViewSet, ReferenceValueViewSet, BindFieldView, FieldOptionsView,
    OrgUnitViewSet,
)

router = DefaultRouter()
router.register(r'reference-sets', ReferenceSetViewSet, basename='referenceset')
router.register(r'reference-values', ReferenceValueViewSet, basename='referencevalue')
router.register(r'org-units', OrgUnitViewSet, basename='orgunit')

urlpatterns = [
    path('bind-field/', BindFieldView.as_view(), name='mdm-bind-field'),
    path('field-options/', FieldOptionsView.as_view(), name='mdm-field-options'),
]
urlpatterns += router.urls
