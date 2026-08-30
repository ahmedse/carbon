# File: people/views.py
# People & Payroll API views (thin — orchestration lives in services).
#
# CBAC (NIR-1C): reads → ``people:view``, writes → ``people:manage``.
# Superusers and global admins bypass capability checks (full access).
# RULE_12: employee/payroll reads are org-scoped for non-admin users via
# ``accounts.rbac_utils.get_visible_org_units``.

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.rbac_utils import get_visible_org_units

from .models import ComplianceRule, Employee, PayrollRun, PayslipLine
from .permissions import PeopleAccess, is_global_admin
from .serializers import (
    ComplianceRuleSerializer,
    EmployeeSerializer,
    PayrollRunSerializer,
    PayslipLineSerializer,
)


def _visible_org_unit_ids(user):
    """Org unit ids the user may view (RULE_12 org scoping)."""
    return [ou.id for ou in get_visible_org_units(user)]


class ComplianceRuleListCreateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = ComplianceRule.objects.all()
        return Response({
            'count': qs.count(),
            'results': ComplianceRuleSerializer(qs, many=True).data,
        })

    def post(self, request):
        serializer = ComplianceRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ComplianceRuleDetailView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request, pk):
        rule = get_object_or_404(ComplianceRule, pk=pk)
        return Response(ComplianceRuleSerializer(rule).data)

    def patch(self, request, pk):
        rule = get_object_or_404(ComplianceRule, pk=pk)
        serializer = ComplianceRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        if is_global_admin(request.user):
            qs = Employee.objects.all()
        else:
            qs = Employee.objects.filter(
                org_unit_id__in=_visible_org_unit_ids(request.user),
            )
        return Response({
            'count': qs.count(),
            'results': EmployeeSerializer(qs, many=True).data,
        })

    def post(self, request):
        serializer = EmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def _get_queryset(self, user):
        if is_global_admin(user):
            return Employee.objects.all()
        return Employee.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(user),
        )

    def get(self, request, pk):
        employee = get_object_or_404(self._get_queryset(request.user), pk=pk)
        return Response(EmployeeSerializer(employee).data)

    def patch(self, request, pk):
        employee = get_object_or_404(self._get_queryset(request.user), pk=pk)
        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PayrollRunListCreateView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        if is_global_admin(request.user):
            qs = PayrollRun.objects.all()
        else:
            qs = PayrollRun.objects.filter(
                org_unit_id__in=_visible_org_unit_ids(request.user),
            )
        return Response({
            'count': qs.count(),
            'results': PayrollRunSerializer(qs, many=True).data,
        })

    def post(self, request):
        serializer = PayrollRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PayrollRunDetailView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def _get_queryset(self, user):
        if is_global_admin(user):
            return PayrollRun.objects.all()
        return PayrollRun.objects.filter(
            org_unit_id__in=_visible_org_unit_ids(user),
        )

    def get(self, request, pk):
        run = get_object_or_404(self._get_queryset(request.user), pk=pk)
        return Response(PayrollRunSerializer(run).data)

    def patch(self, request, pk):
        run = get_object_or_404(self._get_queryset(request.user), pk=pk)
        serializer = PayrollRunSerializer(run, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PayslipLineListView(APIView):
    permission_classes = [IsAuthenticated, PeopleAccess]

    def get(self, request):
        qs = PayslipLine.objects.all()
        run_id = request.query_params.get('payroll_run')
        if run_id:
            qs = qs.filter(payroll_run_id=run_id)
        return Response({
            'count': qs.count(),
            'results': PayslipLineSerializer(qs, many=True).data,
        })
