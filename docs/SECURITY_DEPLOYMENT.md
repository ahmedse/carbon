# Security & Deployment Specifications

This document provides comprehensive security hardening and production deployment specifications for the Carbon platform.

---

## PART 1: SECURITY HARDENING

### Current Security Posture: ⚠️ 6/10

**Strengths:**
- ✅ JWT authentication
- ✅ PBKDF2 password hashing
- ✅ HTTPS in production
- ✅ Tenant-level data isolation

**Critical Gaps:**
- ❌ No CSRF protection
- ❌ No rate limiting
- ❌ No token blacklist
- ❌ Missing security headers
- ❌ No MFA

---

## 1. AUTHENTICATION & SESSION SECURITY

### 1.1 JWT Token Security

**Current Implementation:**
```python
# backend/config/settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,  # ❌ Should be True
    'BLACKLIST_AFTER_ROTATION': False,  # ❌ Should be True
}
```

**Hardened Configuration:**

```python
# backend/config/settings.py

INSTALLED_APPS = [
    # ...
    'rest_framework_simplejwt.token_blacklist',  # Add this
]

SIMPLE_JWT = {
    # Token Lifetimes
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Short-lived
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Longer for UX
    
    # Rotation & Blacklisting
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    
    # Algorithm & Signing
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    
    # Claims
    'AUDIENCE': None,
    'ISSUER': 'carbon-platform',
    
    # Headers
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    # Sliding Token Settings (if using sliding tokens)
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}
```

**Migration for Token Blacklist:**

```bash
cd backend
python manage.py migrate token_blacklist
```

**Logout Implementation:**

```python
# backend/accounts/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated

class LogoutView(APIView):
    """
    Logout endpoint that blacklists refresh token.
    
    POST /carbon-api/accounts/logout/
    Body: {"refresh": "refresh_token_here"}
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'refresh token required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'message': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
```

**Add to URLs:**

```python
# backend/accounts/urls.py
from .views import LogoutView

urlpatterns = [
    # ...
    path('logout/', LogoutView.as_view(), name='logout'),
]
```

### 1.2 Password Security

**Current:** Basic Django password validation

**Enhanced Configuration:**

```python
# backend/config/settings.py

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,  # Increased from default 8
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'accounts.validators.CustomPasswordValidator',  # Custom validator
    },
]
```

**Custom Password Validator:**

```python
# backend/accounts/validators.py

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import re

class CustomPasswordValidator:
    """
    Enforce password complexity:
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    """
    
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
        
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter."),
                code='password_no_lower',
            )
        
        if not re.search(r'\d', password):
            raise ValidationError(
                _("Password must contain at least one digit."),
                code='password_no_digit',
            )
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                _("Password must contain at least one special character."),
                code='password_no_special',
            )
    
    def get_help_text(self):
        return _(
            "Your password must contain at least 12 characters, including "
            "uppercase, lowercase, digits, and special characters."
        )
```

### 1.3 Multi-Factor Authentication (MFA)

**Install Package:**

```bash
pip install django-otp qrcode
```

**Configuration:**

```python
# backend/config/settings.py

INSTALLED_APPS = [
    # ...
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
]

MIDDLEWARE = [
    # ...
    'django_otp.middleware.OTPMiddleware',  # Add after AuthenticationMiddleware
]
```

**Implementation:**

```python
# backend/accounts/views.py

from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import user_has_device
from django.contrib.auth import authenticate
import pyotp

class MFASetupView(APIView):
    """Generate QR code for TOTP setup."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        # Check if user already has device
        if user_has_device(user):
            return Response(
                {'error': 'MFA already enabled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create TOTP device
        device = TOTPDevice.objects.create(
            user=user,
            name='default',
            confirmed=False
        )
        
        # Generate provisioning URI
        uri = device.config_url
        
        return Response({
            'secret': device.key,
            'qr_uri': uri,
            'message': 'Scan QR code with authenticator app'
        })

class MFAVerifyView(APIView):
    """Verify TOTP token and confirm device."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        token = request.data.get('token')
        
        if not token:
            return Response(
                {'error': 'token required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get unconfirmed device
        device = TOTPDevice.objects.filter(
            user=user,
            confirmed=False
        ).first()
        
        if not device:
            return Response(
                {'error': 'No pending MFA setup'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify token
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            return Response({'message': 'MFA enabled successfully'})
        else:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
```

---

## 2. CSRF & CORS PROTECTION

### 2.1 CSRF Protection

**Enable CSRF for State-Changing Operations:**

```python
# backend/config/settings.py

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CSRF Settings
CSRF_COOKIE_SECURE = True  # HTTPS only
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_TRUSTED_ORIGINS = [
    'https://carbon.yourdomain.com',
]
```

**Double-Submit Cookie Pattern:**

```python
# backend/accounts/views.py

from django.middleware.csrf import get_token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_token_view(request):
    """Provide CSRF token for client-side forms."""
    return Response({
        'csrfToken': get_token(request)
    })
```

### 2.2 CORS Configuration

```python
# backend/config/settings.py

INSTALLED_APPS = [
    # ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    # ...
]

# CORS Settings (Production)
CORS_ALLOWED_ORIGINS = [
    'https://carbon.yourdomain.com',
    'https://app.yourdomain.com',
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Development Only
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
```

---

## 3. RATE LIMITING & THROTTLING

### 3.1 DRF Throttling

```python
# backend/config/settings.py

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',      # Anonymous users
        'user': '1000/hour',     # Authenticated users
        'login': '5/minute',     # Login attempts
        'sensitive': '10/hour',  # Sensitive operations
    }
}
```

### 3.2 Django-Ratelimit (Additional Layer)

```bash
pip install django-ratelimit
```

**Implementation:**

```python
# backend/accounts/decorators.py

from django_ratelimit.decorators import ratelimit
from rest_framework.decorators import api_view

@api_view(['POST'])
@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    """Login with IP-based rate limiting."""
    # ... login logic
```

### 3.3 Nginx Rate Limiting (Production)

```nginx
# /etc/nginx/sites-available/carbon

http {
    # Limit requests per IP
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    
    server {
        location / {
            limit_req zone=general burst=20 nodelay;
        }
        
        location /carbon-api/token/ {
            limit_req zone=login burst=3;
        }
    }
}
```

---

## 4. SECURITY HEADERS

### 4.1 Django Security Middleware

```python
# backend/config/settings.py

# Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = True  # Production only
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # Avoid unsafe-inline in production
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)
```

### 4.2 Custom Security Headers Middleware

```python
# backend/accounts/middleware.py

class SecurityHeadersMiddleware:
    """Add additional security headers to all responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Permissions Policy (formerly Feature-Policy)
        response['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=(), '
            'payment=(), '
            'usb=()'
        )
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Additional CSP directives
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:;"
        )
        
        return response
```

**Add to Middleware:**

```python
MIDDLEWARE = [
    # ...
    'accounts.middleware.SecurityHeadersMiddleware',
]
```

---

## 5. INPUT VALIDATION & SANITIZATION

### 5.1 SQL Injection Prevention

**Rule:** Always use Django ORM, never raw SQL.

**If raw SQL is necessary:**

```python
from django.db import connection

# ❌ BAD: SQL Injection vulnerable
def bad_query(user_input):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM projects WHERE name = '{user_input}'")

# ✅ GOOD: Parameterized query
def good_query(user_input):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM projects WHERE name = %s", [user_input])
```

### 5.2 XSS Prevention

**Backend:**
- Django templates auto-escape by default ✅
- DRF serializers escape output ✅

**Frontend:**
- React escapes by default ✅
- **Never use `dangerouslySetInnerHTML` without sanitization**

**If HTML rendering is needed:**

```bash
npm install dompurify
```

```jsx
import DOMPurify from 'dompurify';

function RenderHTML({ htmlContent }) {
  const cleanHTML = DOMPurify.sanitize(htmlContent);
  return <div dangerouslySetInnerHTML={{ __html: cleanHTML }} />;
}
```

### 5.3 JSON Field Validation

**For DataRow.values (JSONB field):**

```python
# backend/dataschema/models.py

import jsonschema
from django.core.exceptions import ValidationError

class DataRow(models.Model):
    # ... existing fields ...
    
    def clean(self):
        """Validate values against table's field definitions."""
        super().clean()
        
        # Get field definitions
        fields = {f.name: f for f in self.table.fields.all()}
        
        # Validate each value
        for field_name, value in self.values.items():
            if field_name not in fields:
                raise ValidationError(f"Unknown field: {field_name}")
            
            field = fields[field_name]
            
            # Type validation
            if field.field_type == 'number':
                if not isinstance(value, (int, float)):
                    raise ValidationError(f"{field_name} must be a number")
            
            elif field.field_type == 'boolean':
                if not isinstance(value, bool):
                    raise ValidationError(f"{field_name} must be boolean")
            
            elif field.field_type == 'date':
                # Validate date format
                from datetime import datetime
                try:
                    datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    raise ValidationError(f"{field_name} must be YYYY-MM-DD format")
            
            # Required field validation
            if field.is_required and not value:
                raise ValidationError(f"{field_name} is required")
            
            # Custom validation rules
            if field.validation:
                self._validate_field_rules(field, value)
    
    def _validate_field_rules(self, field, value):
        """Apply custom validation rules from field.validation JSON."""
        rules = field.validation or {}
        
        if 'min' in rules and value < rules['min']:
            raise ValidationError(f"{field.name} must be >= {rules['min']}")
        
        if 'max' in rules and value > rules['max']:
            raise ValidationError(f"{field.name} must be <= {rules['max']}")
        
        if 'regex' in rules:
            import re
            if not re.match(rules['regex'], str(value)):
                raise ValidationError(f"{field.name} format invalid")
```

---

## 6. LOGGING & MONITORING

### 6.1 Comprehensive Logging

```python
# backend/config/settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/carbon/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'json',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/carbon/security.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'json',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
        'dataschema': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
    },
}
```

### 6.2 Audit Logging Middleware

```python
# backend/accounts/middleware.py

import logging
import json
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('django.security')

class AuditLogMiddleware(MiddlewareMixin):
    """Log all API requests for audit trail."""
    
    SENSITIVE_FIELDS = ['password', 'token', 'secret']
    
    def process_request(self, request):
        # Skip static files and health checks
        if request.path.startswith('/static/') or request.path == '/health/':
            return None
        
        # Sanitize request body
        try:
            body = json.loads(request.body) if request.body else {}
            sanitized_body = self._sanitize_data(body)
        except:
            sanitized_body = {}
        
        logger.info('API_REQUEST', extra={
            'user': str(request.user) if request.user.is_authenticated else 'Anonymous',
            'method': request.method,
            'path': request.path,
            'ip': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'body': sanitized_body,
        })
    
    def process_response(self, request, response):
        if request.path.startswith('/static/') or request.path == '/health/':
            return response
        
        if response.status_code >= 400:
            logger.warning('API_ERROR', extra={
                'user': str(request.user) if request.user.is_authenticated else 'Anonymous',
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
            })
        
        return response
    
    def _sanitize_data(self, data):
        """Remove sensitive fields from logs."""
        if isinstance(data, dict):
            return {
                k: '***REDACTED***' if k in self.SENSITIVE_FIELDS else v
                for k, v in data.items()
            }
        return data
    
    def _get_client_ip(self, request):
        """Get real client IP (accounting for proxies)."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
```

---

## PART 2: PRODUCTION DEPLOYMENT

## 1. INFRASTRUCTURE ARCHITECTURE

### Production Stack

```
                    ┌─────────────┐
                    │   Cloudflare │ (CDN, DDoS protection, SSL)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Nginx      │ (Reverse Proxy, Load Balancer)
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼────┐     ┌─────▼────┐
    │ Django  │      │ Django   │     │ Django   │ (App Servers)
    │ (8001)  │      │ (8002)   │     │ (8003)   │
    └────┬────┘      └─────┬────┘     └─────┬────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼───────┐
                    │  pgBouncer   │ (Connection Pooling)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  PostgreSQL  │ (Primary DB)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  PostgreSQL  │ (Read Replica)
                    └──────────────┘
```

---

## 2. DOCKER PRODUCTION SETUP

### 2.1 Dockerfile (Backend - Production)

```dockerfile
# backend/Dockerfile.prod

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy project
COPY . .

# Create non-root user
RUN useradd -m -u 1000 carbon && chown -R carbon:carbon /app
USER carbon

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "config.wsgi:application"]
```

### 2.2 Dockerfile (Frontend - Production)

```dockerfile
# carbon-frontend/Dockerfile.prod

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Nginx Config for Frontend:**

```nginx
# carbon-frontend/nginx.conf

server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 2.3 Docker Compose (Production)

```yaml
# docker-compose.prod.yml

version: '3.8'

services:
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
  
  redis:
    image: redis:7-alpine
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
  
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    env_file:
      - ./backend/.env.production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: always
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      replicas: 3  # Run 3 instances for load balancing
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
  
  frontend:
    build:
      context: ./carbon-frontend
      dockerfile: Dockerfile.prod
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - static_volume:/static:ro
      - media_volume:/media:ro
    depends_on:
      - backend
      - frontend
    restart: always

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

---

## 3. NGINX REVERSE PROXY (Production)

```nginx
# /etc/nginx/nginx.conf

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    
    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 20M;
    
    # Compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/atom+xml image/svg+xml;
    
    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    
    # Backend upstream
    upstream backend {
        least_conn;
        server backend:8000 max_fails=3 fail_timeout=30s;
        # Add more backend servers if using multiple replicas
    }
    
    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name carbon.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }
    
    # HTTPS Server
    server {
        listen 443 ssl http2;
        server_name carbon.yourdomain.com;
        
        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;
        
        # Security Headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
        
        # API Backend
        location /carbon-api/ {
            limit_req zone=api burst=50 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            
            # Disable buffering for SSE/WebSocket if needed
            proxy_buffering off;
        }
        
        # Login endpoint (stricter rate limit)
        location /carbon-api/token/ {
            limit_req zone=login burst=3;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Static files
        location /static/ {
            alias /static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        # Media files
        location /media/ {
            alias /media/;
            expires 7d;
            add_header Cache-Control "public";
        }
        
        # Frontend (SPA)
        location / {
            limit_req zone=general burst=20 nodelay;
            
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## 4. DATABASE CONFIGURATION

### 4.1 PostgreSQL Production Settings

```sql
-- /var/lib/postgresql/data/postgresql.conf

# Connection Settings
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB

# Logging
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 1000  # Log slow queries (> 1 second)

# Replication (if using read replicas)
wal_level = replica
max_wal_senders = 3
wal_keep_size = 1GB
```

### 4.2 Connection Pooling (pgBouncer)

**Install:**
```bash
sudo apt-get install pgbouncer
```

**Configuration:** `/etc/pgbouncer/pgbouncer.ini`

```ini
[databases]
carbon_prod = host=localhost port=5432 dbname=carbon_prod user=carbon_user password=YOUR_PASSWORD

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 100
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
```

**Django Settings:**
```python
# Use pgBouncer instead of direct connection
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'localhost',
        'PORT': '6432',  # pgBouncer port
        'NAME': 'carbon_prod',
        'USER': 'carbon_user',
        'PASSWORD': os.getenv('DB_PASSWORD'),
    }
}
```

---

## 5. DEPLOYMENT CHECKLIST

### Pre-Deployment

- [ ] All tests passing (backend, frontend, E2E)
- [ ] Security audit completed
- [ ] Database migrations reviewed
- [ ] Environment variables set in `.env.production`
- [ ] SSL certificates obtained (Let's Encrypt/Cloudflare)
- [ ] Backup strategy implemented
- [ ] Monitoring configured (Sentry, Prometheus, etc.)
- [ ] Log rotation configured
- [ ] Rate limiting tested
- [ ] Load testing completed

### Deployment Steps

1. **Backup Production Database**
   ```bash
   pg_dump -U carbon_user carbon_prod > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Build Docker Images**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

3. **Run Database Migrations**
   ```bash
   docker-compose -f docker-compose.prod.yml run backend python manage.py migrate --noinput
   ```

4. **Collect Static Files**
   ```bash
   docker-compose -f docker-compose.prod.yml run backend python manage.py collectstatic --noinput
   ```

5. **Deploy Containers**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

6. **Verify Health Checks**
   ```bash
   curl -f https://carbon.yourdomain.com/health/ || exit 1
   ```

7. **Monitor Logs**
   ```bash
   docker-compose -f docker-compose.prod.yml logs -f --tail=100
   ```

### Post-Deployment

- [ ] Smoke tests passed
- [ ] Health checks passing
- [ ] Error rates within threshold (< 0.1%)
- [ ] Response times acceptable (p95 < 500ms)
- [ ] SSL certificate valid
- [ ] CDN caching working
- [ ] Backups scheduled

---

## 6. MONITORING & ALERTING

### 6.1 Health Check Endpoint

```python
# backend/core/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for load balancers.
    
    GET /health/
    
    Returns 200 if healthy, 503 if unhealthy.
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return Response({
            'status': 'healthy',
            'database': 'ok',
        })
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
        }, status=503)
```

### 6.2 Error Tracking (Sentry)

```bash
pip install sentry-sdk
```

```python
# backend/config/settings.py

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

if not DEBUG:
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,  # Don't send personal data
        environment='production',
        release=os.getenv('GIT_COMMIT_SHA', 'unknown'),
    )
```

---

**Document Status:** ✅ Complete  
**Last Updated:** 2026-01-11  
**Next Review:** After security audit
