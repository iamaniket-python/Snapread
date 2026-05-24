import time
import logging
import json

logger = logging.getLogger('medium_clone')


# ═══════════════════════════════════════════
# 1. REQUEST LOGGING MIDDLEWARE
# ═══════════════════════════════════════════

class RequestLoggingMiddleware:
    """
    Logs every incoming request with method, path, status code, and response time.
    Add to MIDDLEWARE in settings.py:
        'yourapp.middleware.RequestLoggingMiddleware'
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start    = time.time()
        response = self.get_response(request)
        duration = round((time.time() - start) * 1000, 2)  # ms

        user = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'

        logger.info(
            f"[REQUEST] {request.method} {request.path} "
            f"| status={response.status_code} "
            f"| user={user} "
            f"| {duration}ms"
        )
        return response


# ═══════════════════════════════════════════
# 2. BLACKLISTED TOKEN MIDDLEWARE
# ═══════════════════════════════════════════

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.http import JsonResponse


class BlockBlacklistedTokenMiddleware:
    """
    Rejects requests that carry a blacklisted JWT access token.
    Runs before DRF authentication so blacklisted tokens never reach views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1]
            try:
                token = AccessToken(token_str)
                # If simplejwt blacklist app is enabled, this raises TokenError
                token.verify()
            except TokenError:
                return JsonResponse({'error': 'Token is blacklisted or invalid.'}, status=401)

        return self.get_response(request)


# ═══════════════════════════════════════════
# 3. MAINTENANCE MODE MIDDLEWARE
# ═══════════════════════════════════════════

from django.conf import settings


class MaintenanceModeMiddleware:
    """
    Returns 503 for all requests when settings.MAINTENANCE_MODE = True.
    Superusers are still allowed through.

    Add to settings.py:
        MAINTENANCE_MODE = False   # flip to True to enable
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'MAINTENANCE_MODE', False):
            # Allow superusers to bypass
            if hasattr(request, 'user') and request.user.is_superuser:
                return self.get_response(request)
            return JsonResponse(
                {'error': 'We are under maintenance. Please check back soon.'},
                status=503
            )
        return self.get_response(request)


# ═══════════════════════════════════════════
# 4. CORS MIDDLEWARE (manual fallback)
# ═══════════════════════════════════════════

class CORSMiddleware:
    """
    Simple CORS middleware for dev.
    In production, use django-cors-headers instead.
    """

    ALLOWED_ORIGINS = getattr(settings, 'CORS_ALLOWED_ORIGINS', ['http://localhost:3000'])

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin   = request.META.get('HTTP_ORIGIN', '')
        response = self.get_response(request)

        if origin in self.ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin']      = origin
            response['Access-Control-Allow-Methods']     = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers']     = 'Content-Type, Authorization'
            response['Access-Control-Allow-Credentials'] = 'true'

        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Handle preflight OPTIONS request
        if request.method == 'OPTIONS':
            response = JsonResponse({})
            response['Access-Control-Allow-Origin']  = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.status_code = 200
            return response
        return None


# ═══════════════════════════════════════════
# 5. RATE LIMIT MIDDLEWARE (IP-based global)
# ═══════════════════════════════════════════

from collections import defaultdict

_global_rate_store = defaultdict(list)

RATE_LIMIT_CALLS  = getattr(settings, 'GLOBAL_RATE_LIMIT_CALLS', 200)   # requests
RATE_LIMIT_PERIOD = getattr(settings, 'GLOBAL_RATE_LIMIT_PERIOD', 60)   # seconds


class GlobalRateLimitMiddleware:
    """
    Global IP-based rate limiter.
    Default: 200 requests per 60 seconds per IP.
    Override via settings.py:
        GLOBAL_RATE_LIMIT_CALLS  = 200
        GLOBAL_RATE_LIMIT_PERIOD = 60
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip  = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown'))
        now = time.time()

        # Slide the window
        _global_rate_store[ip] = [
            t for t in _global_rate_store[ip] if now - t < RATE_LIMIT_PERIOD
        ]

        if len(_global_rate_store[ip]) >= RATE_LIMIT_CALLS:
            return JsonResponse(
                {'error': f'Too many requests. Limit: {RATE_LIMIT_CALLS} per {RATE_LIMIT_PERIOD}s.'},
                status=429
            )

        _global_rate_store[ip].append(now)
        return self.get_response(request)


# ═══════════════════════════════════════════
# 6. ATTACH PROFILE MIDDLEWARE
# ═══════════════════════════════════════════

from django.contrib.auth.models import AnonymousUser


class AttachProfileMiddleware:
    """
    Attaches request.profile to every authenticated request
    so views don't have to query Profile repeatedly.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.profile = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                from .models import Profile
                request.profile = Profile.objects.get(user=request.user)
            except Exception:
                pass
        return self.get_response(request)