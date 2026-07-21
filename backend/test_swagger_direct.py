#!/usr/bin/env python3
"""Direct Swagger schema generation test to capture full error details."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.conf import settings

User = get_user_model()

# Create test user
user = User.objects.create_user(username='swagger-direct-test', password='pass123')

# Create API client
client = APIClient()
client.force_authenticate(user=user)

api_prefix = settings.API_PREFIX.strip('/')

print(f"Testing Swagger endpoint: /{api_prefix}/swagger/?format=openapi")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print()

try:
    response = client.get(f'/{api_prefix}/swagger/?format=openapi')
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        print("SUCCESS: Swagger schema generated successfully!")
        schema = response.json()
        paths = schema.get('paths', {})
        print(f"Number of API paths documented: {len(paths)}")
    else:
        print(f"FAILED with status {response.status_code}")
        print("\nResponse content (first 2000 chars):")
        print(response.content.decode('utf-8')[:2000])
        
except Exception as e:
    print(f"Exception occurred: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    user.delete()
