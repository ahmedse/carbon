"""
Pulse AI Copilot Authentication Bridge
Provisions authenticated users to Pulse instance for Carbon platform
View layer — business logic lives in accounts.services.PulseService.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import PulseService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pulse_auth_view(request):
    """
    Endpoint: GET /api/accounts/pulse-auth/

    Returns authentication token and user context for Pulse widget
    Frontend uses this to authenticate the widget on behalf of current user

    Response:
    {
        "pulse_token": "jwt-token-string",
        "pulse_user": {
            "username": "user123",
            "email": "user@example.com",
            "name": "User Name",
            "roles": ["admin", "org_steward"]
        },
        "pulse_host": "http://127.0.0.1:9100",
        "instance_id": "carbon"
    }
    """
    user = request.user

    # Generate Pulse JWT token
    pulse_token = PulseService.generate_token(user)

    # Build user context
    pulse_user = {
        'username': user.username,
        'email': user.email,
        'name': user.get_full_name() or user.username,
        'roles': list(user.groups.values_list('name', flat=True)),
    }

    return Response({
        'pulse_token': pulse_token,
        'pulse_user': pulse_user,
        'pulse_host': PulseService.PULSE_HOST,
        'instance_id': PulseService.PULSE_INSTANCE_ID,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pulse_provision_view(request):
    """
    Endpoint: POST /api/accounts/pulse-provision/

    Optional: Explicitly provision user to Pulse instance
    (Usually Pulse handles this automatically on first widget mount)

    Payload: (optional)
    {
        "context": {
            "org_unit": "org123",
            "role": "facilities_officer"
        }
    }
    """
    user = request.user
    context = request.data.get('context', {})

    status_code, payload = PulseService.provision(user, context)
    return Response(payload, status=status_code)
