import logging
import re

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        logger.info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
        )
        return response


class CsrfExemptAPIMiddleware(MiddlewareMixin):
    """Disable CSRF checks for API endpoints that use JWT authentication."""
    
    API_PATHS = [
        r'^/api/v1/',
    ]
    
    def process_request(self, request):
        for pattern in self.API_PATHS:
            if re.match(pattern, request.path):
                setattr(request, '_dont_enforce_csrf_checks', True)
                break
        return None