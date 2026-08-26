# File: dataschema/policy_views.py
"""
Column-level RBAC (EPH-4A): FieldAccessPolicy management endpoints.

These are admin-only (gated by `dataschema:manage` via AdminOrSuperuserOnly).
They manage the policies consumed by DataFieldSerializer.to_representation to
deny/mask sensitive columns (e.g. PII) for users lacking a capability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from accounts.permissions import AdminOrSuperuserOnly
from .models import DataField, FieldAccessPolicy


class FieldAccessPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldAccessPolicy
        fields = ['id', 'field', 'required_capability', 'action', 'created_by', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']


class FieldAccessPolicyView(APIView):
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = 'dataschema:manage'

    def get(self, request, field_id):
        field = get_object_or_404(DataField, pk=field_id)
        return Response(FieldAccessPolicySerializer(field.access_policies.all(), many=True).data)

    def post(self, request, field_id):
        field = get_object_or_404(DataField, pk=field_id)
        serializer = FieldAccessPolicySerializer(data={**request.data, 'field': field.id})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(created_by=request.user)
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "A FieldAccessPolicy for this field and required_capability "
                        "already exists."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FieldAccessPolicyDetailView(APIView):
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = 'dataschema:manage'

    def delete(self, request, field_id, pk):
        policy = get_object_or_404(FieldAccessPolicy, pk=pk, field_id=field_id)
        policy.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
