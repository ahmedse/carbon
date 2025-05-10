from rest_framework import viewsets
from .models import Role, Context, RoleAssignment
from .serializers import RoleSerializer, ContextSerializer, RoleAssignmentSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

class ContextViewSet(viewsets.ModelViewSet):
    queryset = Context.objects.all()
    serializer_class = ContextSerializer

class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RoleAssignment.objects.all()
    serializer_class = RoleAssignmentSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        # Optionally add role assignments or permissions summary
        # token['roles'] = list(user.role_assignments.values_list('role__name', flat=True))
        return token

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    
# accounts/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_roles(request):
    user = request.user
    assignments = user.role_assignments.select_related('role', 'context')
    roles = [
        {
            "role": a.role.name,
            "context_type": a.context.type,
            "project": getattr(a.context.project, 'name', None),
            "cycle": getattr(a.context.cycle, 'name', None),
            "module": getattr(a.context.module, 'name', None),
            "permissions": a.role.permissions,
        }
        for a in assignments
    ]
    return Response({"roles": roles})