from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def data_trust_exception_handler(exc, context):
    # AppFeedback carries structured feedback — pass through as-is
    from core.feedback import AppFeedback
    if isinstance(exc, AppFeedback):
        response = Response(exc.feedback, status=exc.status_code)
        request = context.get('request')
        correlation_id = getattr(request, 'correlation_id', None) if request else None
        if correlation_id:
            response.data['correlation_id'] = correlation_id
        return response

    response = exception_handler(exc, context)
    request = context.get('request')
    correlation_id = getattr(request, 'correlation_id', None) if request else None

    if response is None:
        if isinstance(exc, APIException):
            payload = {
                'error': exc.__class__.__name__,
                'message': str(exc),
                'timestamp': timezone.now().isoformat(),
                'path': request.path if request else None,
            }
            if correlation_id:
                payload['correlation_id'] = correlation_id
            response = Response(payload, status=exc.status_code)
        else:
            payload = {
                'error': exc.__class__.__name__,
                'message': 'An unexpected server error occurred.',
                'timestamp': timezone.now().isoformat(),
                'path': request.path if request else None,
            }
            if correlation_id:
                payload['correlation_id'] = correlation_id
            response = Response(payload, status=500)
        return response

    payload = {
        'error': exc.__class__.__name__,
        'message': str(exc),
        'timestamp': timezone.now().isoformat(),
        'path': request.path if request else None,
    }

    if correlation_id:
        payload['correlation_id'] = correlation_id

    if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
        payload['details'] = exc.detail
    elif hasattr(exc, 'detail') and isinstance(exc.detail, list):
        payload['details'] = exc.detail

    # Add actionable guidance for common error types
    suggested_action = _get_suggested_action(exc, payload.get('details'))
    if suggested_action:
        payload['suggested_action'] = suggested_action

    response.data = payload
    return response


def _get_suggested_action(exc, details):
    """
    Provide actionable guidance based on exception type and context.
    """
    # For validation errors with field-level details
    if isinstance(exc, ValidationError) and details and isinstance(details, dict):
        field_names = ', '.join(details.keys())
        return f"Check the following fields: {field_names}"
    
    # Generic validation error
    if isinstance(exc, ValidationError):
        return "Review the request payload and ensure all required fields are valid"
    
    # Add more contextual suggestions as needed
    return None
