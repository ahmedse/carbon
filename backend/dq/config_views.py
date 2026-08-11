"""Phase 1.7: DQ Profile Config API — read/update the singleton config."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import AdminOrSuperuserOnly
from dq.models import DQProfileConfig
from dq.serializers import DQProfileConfigSerializer


class DQProfileConfigView(APIView):
    """Singleton — GET returns the config, PUT updates it."""
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = 'platform:admin'

    def get(self, request):
        config, _ = DQProfileConfig.objects.get_or_create()
        serializer = DQProfileConfigSerializer(config)
        return Response(serializer.data)

    def put(self, request):
        config, _ = DQProfileConfig.objects.get_or_create()
        serializer = DQProfileConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
