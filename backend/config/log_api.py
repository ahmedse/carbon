# File: config/log_api.py
# Phase 1 — DRF API endpoint for the centralized log viewer.
# Only superusers and members of the admins_group can access.

import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .log_viewer import read_logs, list_log_files
from accounts.permissions import AdminOrSuperuserOnly


class LogViewerAPIView(APIView):
    """GET /carbon-api/system/logs/ — Read-only access to platform logs.

    Query params:
        lines (int): Max raw lines to tail (default 200)
        level (str): Filter by level (INFO, WARNING, ERROR, CRITICAL, DEBUG)
        search (str): Case-insensitive substring search
        correlation_id (str): Filter by correlation ID
        log_file (str): Log file name (default 'carbon.log')
        page (int): Page number (default 1)
        page_size (int): Entries per page (default 50, max 500)
    """
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]
    required_capability = 'platform:view_audit'

    def get(self, request):
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'logs',
        )

        # List log files if requested
        if request.query_params.get('list') == '1':
            return Response({'files': list_log_files(log_dir)})

        # Resolve log file path
        log_name = request.query_params.get('log_file', 'carbon.log')
        # Prevent path traversal
        log_name = os.path.basename(log_name)
        log_path = os.path.join(log_dir, log_name)

        # Parse query params
        try:
            lines = int(request.query_params.get('lines', 200))
        except (TypeError, ValueError):
            lines = 200

        try:
            page = int(request.query_params.get('page', 1))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = int(request.query_params.get('page_size', 50))
        except (TypeError, ValueError):
            page_size = 50

        page_size = min(max(page_size, 1), 500)

        level = request.query_params.get('level', None)
        search = request.query_params.get('search', None)
        correlation_id = request.query_params.get('correlation_id', None)

        result = read_logs(
            log_file=log_path,
            lines=lines,
            level=level,
            search=search,
            correlation_id=correlation_id,
            page=page,
            page_size=page_size,
        )

        return Response(result)
