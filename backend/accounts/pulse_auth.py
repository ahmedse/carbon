"""
Pulse AI Copilot Authentication Bridge
Provisions authenticated users to Pulse instance for Carbon platform
"""
import os
import jwt
import time
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


# Pulse configuration from environment
PULSE_HOST = os.getenv('PULSE_HOST', 'http://127.0.0.1:9100')
PULSE_INSTANCE_ID = os.getenv('PULSE_INSTANCE_ID', 'carbon')
PULSE_JWT_SECRET = os.getenv('PULSE_JWT_SECRET', 'changeme-in-production')
PULSE_JWT_ALGORITHM = os.getenv('PULSE_JWT_ALGORITHM', 'HS256')


def generate_pulse_token(user):
    """
    Generate JWT token for Pulse authentication
    Token includes user identity and instance context
    """
    now = int(time.time())
    payload = {
        'sub': user.username,  # User identifier
        'email': user.email,
        'name': user.get_full_name() or user.username,
        'iss': 'carbon-platform',  # Issuer
        'instance_id': PULSE_INSTANCE_ID,
        'iat': now,
        'exp': now + (24 * 60 * 60),  # 24 hour expiry
    }
    
    token = jwt.encode(payload, PULSE_JWT_SECRET, algorithm=PULSE_JWT_ALGORITHM)
    return token


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
    pulse_token = generate_pulse_token(user)
    
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
        'pulse_host': PULSE_HOST,
        'instance_id': PULSE_INSTANCE_ID,
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
    
    # Generate token
    pulse_token = generate_pulse_token(user)
    
    try:
        # Call Pulse provision endpoint
        provision_url = f"{PULSE_HOST}/api/v1/instances/{PULSE_INSTANCE_ID}/users"
        
        provision_data = {
            'user_id': user.username,
            'email': user.email,
            'name': user.get_full_name() or user.username,
            'roles': list(user.groups.values_list('name', flat=True)),
            'context': context,
        }
        
        response = requests.post(
            provision_url,
            json=provision_data,
            headers={
                'Authorization': f'Bearer {pulse_token}',
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        
        if response.status_code in [200, 201]:
            return Response({
                'status': 'provisioned',
                'pulse_user_id': response.json().get('user_id'),
            })
        else:
            return Response({
                'status': 'error',
                'message': f'Pulse provision failed: {response.text}',
            }, status=status.HTTP_502_BAD_GATEWAY)
            
    except requests.RequestException as e:
        return Response({
            'status': 'error',
            'message': f'Failed to connect to Pulse: {str(e)}',
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
