# mdm/views.py
from django.utils.text import slugify
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from dataschema.models import DataField
from .models import ReferenceSet, ReferenceValue, OrgUnit
from .serializers import ReferenceSetSerializer, ReferenceValueSerializer, OrgUnitSerializer
from .permissions import ReadAnyWriteAdmin


class ReferenceSetViewSet(viewsets.ModelViewSet):
    queryset = ReferenceSet.objects.all()
    serializer_class = ReferenceSetSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))

    @action(detail=True, methods=['get'])
    def values(self, request, pk=None):
        """GET /mdm/reference-sets/{id}/values/?active=1 -> values of this set."""
        qs = ReferenceValue.objects.filter(reference_set_id=pk)
        if request.query_params.get('active') in ('1', 'true', 'True'):
            qs = qs.filter(is_active=True)
        return Response(ReferenceValueSerializer(qs, many=True).data)


class ReferenceValueViewSet(viewsets.ModelViewSet):
    serializer_class = ReferenceValueSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        qs = ReferenceValue.objects.all()
        p = self.request.query_params
        if p.get('reference_set'):
            qs = qs.filter(reference_set_id=p['reference_set'])
        if p.get('active') in ('1', 'true', 'True'):
            qs = qs.filter(is_active=True)
        return qs


class BindFieldView(APIView):
    """POST /mdm/bind-field/ {"data_field": <id>, "reference_set": <id|null>}
    Binds (or unbinds) a dataschema DataField to a ReferenceSet. Admin only."""
    permission_classes = [ReadAnyWriteAdmin]

    def post(self, request):
        field_id = request.data.get('data_field')
        set_id = request.data.get('reference_set')
        if not field_id:
            return Response({'error': 'data_field is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            field = DataField.objects.get(pk=field_id)
        except DataField.DoesNotExist:
            return Response({'error': 'data_field not found'}, status=status.HTTP_404_NOT_FOUND)
        if set_id in (None, '', 'null'):
            field.reference_set = None
        else:
            try:
                field.reference_set = ReferenceSet.objects.get(pk=set_id)
            except ReferenceSet.DoesNotExist:
                return Response({'error': 'reference_set not found'}, status=status.HTTP_404_NOT_FOUND)
        field.save(update_fields=['reference_set'])
        return Response({'data_field': field.id, 'reference_set': field.reference_set_id})


class FieldOptionsView(APIView):
    """GET /mdm/field-options/?data_field=<id> -> ACTIVE values of the set bound
    to this field (empty list if the field is not bound). Read: any authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        field_id = request.query_params.get('data_field')
        if not field_id:
            return Response({'error': 'data_field is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            field = DataField.objects.get(pk=field_id)
        except DataField.DoesNotExist:
            return Response({'error': 'data_field not found'}, status=status.HTTP_404_NOT_FOUND)
        if not field.reference_set_id:
            return Response({'data_field': field.id, 'reference_set': None, 'values': []})
        qs = ReferenceValue.objects.filter(reference_set_id=field.reference_set_id, is_active=True)
        return Response({
            'data_field': field.id,
            'reference_set': field.reference_set_id,
            'values': ReferenceValueSerializer(qs, many=True).data,
        })


class OrgUnitViewSet(viewsets.ModelViewSet):
    """CRUD for organisational units. Supports tree hierarchy via parent FK."""
    serializer_class = OrgUnitSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        qs = OrgUnit.objects.all()
        p = self.request.query_params
        if p.get('parent'):
            qs = qs.filter(parent_id=p['parent'])
        if p.get('root'):
            qs = qs.filter(parent=None)
        if p.get('org_type'):
            qs = qs.filter(org_type=p['org_type'])
        return qs

    def perform_create(self, serializer):
        from django.utils.text import slugify
        name = serializer.validated_data.get('name', '')
        parent = serializer.validated_data.get('parent')
        base = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
        serializer.save(slug=base)
