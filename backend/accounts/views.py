# File: accounts/views.py
# Purpose: API views for RBAC operations (roles, contexts, assignments, tokens, user roles).

from rest_framework import viewsets
from .models import Role, Context, RoleAssignment
from .serializers import RoleSerializer, ContextSerializer, RoleAssignmentSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class RoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for listing, creating, retrieving, updating and deleting roles.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

class ContextViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing contexts.
    """
    queryset = Context.objects.all()
    serializer_class = ContextSerializer

class RoleAssignmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing role assignments.
    """
    queryset = RoleAssignment.objects.all()
    serializer_class = RoleAssignmentSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT token to include extra user information.
    """
    @classmethod
    def get_token(cls, user):
        """
        Generate a token for the user, including the username.
        """
        token = super().get_token(user)
        token['username'] = user.username
        # Optionally add role assignments or permissions summary
        # token['roles'] = list(user.role_assignments.values_list('role__name', flat=True))
        return token

class MyTokenObtainPairView(TokenObtainPairView):
    """
    API endpoint for obtaining JWT tokens with custom claims.
    """
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        """
        Logs token request data and returns token response.
        """
        import logging
        logger = logging.getLogger('django')
        logger.debug(f"Token request data: {request.data}")
        return super().post(request, *args, **kwargs)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_roles(request):
    """
    Returns all roles assigned to the authenticated user, including context information.
    """
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