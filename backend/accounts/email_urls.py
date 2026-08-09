# File: accounts/email_urls.py
# Phase 1.1 — Email test endpoint

from django.urls import path
from .views import email_test


urlpatterns = [
    path('', email_test, name='email-test'),
]
