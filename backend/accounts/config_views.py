"""Platform config APIs — read/update singletons: Email, Backup, Logging, API."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import AdminOrSuperuserOnly
from accounts.models import EmailConfig, BackupConfig, LogConfig, APIConfig
from accounts.serializers import (
    EmailConfigSerializer, BackupConfigSerializer,
    LogConfigSerializer, APIConfigSerializer,
)


class _ConfigMixin:
    """Shared GET/PUT for singleton config models."""
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]

    def get(self, request):
        obj, _ = self.model.objects.get_or_create()
        return Response(self.serializer_class(obj).data)

    def put(self, request):
        obj, _ = self.model.objects.get_or_create()
        ser = self.serializer_class(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailConfigView(_ConfigMixin, APIView):
    model = EmailConfig
    serializer_class = EmailConfigSerializer


class BackupConfigView(_ConfigMixin, APIView):
    model = BackupConfig
    serializer_class = BackupConfigSerializer


class LogConfigView(_ConfigMixin, APIView):
    model = LogConfig
    serializer_class = LogConfigSerializer


class APIConfigView(_ConfigMixin, APIView):
    model = APIConfig
    serializer_class = APIConfigSerializer
