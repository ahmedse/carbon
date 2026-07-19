# mdm/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ReferenceSetViewSet,
    ReferenceValueViewSet,
    OrgUnitViewSet,
    BindFieldView,
    FieldOptionsView,
)

router = DefaultRouter()
router.register(r'reference-sets', ReferenceSetViewSet, basename='referenceset')
router.register(r'reference-values', ReferenceValueViewSet, basename='referencevalue')
router.register(r'org-units', OrgUnitViewSet, basename='orgunit')

urlpatterns = [
    path('bind-field/', BindFieldView.as_view(), name='bind-field'),
    path('field-options/', FieldOptionsView.as_view(), name='field-options'),
]

urlpatterns += router.urls
