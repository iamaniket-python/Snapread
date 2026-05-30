import time
import logging
import functools
from collections import defaultdict

from rest_framework import status
from rest_framework.response import Response

from .models import Post, Comment, Profile

logger = logging.getLogger('medium_clone')


# ═══════════════════════════════════════════
# 1. LOGIN REQUIRED
# Use this on any APIView method that needs auth
# ═══════════════════════════════════════════

def login_required(view_func):
    """
    Blocks unauthenticated users with 401.
    Use instead of permission_classes on individual methods.

    Usage:
        @login_required
        def post(self, request, slug):
            ...
    """
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required. Please login to continue.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper


def post_owner_required(view_func):
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        slug = kwargs.get('slug')
        try:
            post = Post.objects.select_related('author').get(slug=slug)
        except Post.DoesNotExist:
            return Response(
                {'error': 'Post not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if post.author != request.user:
            return Response(
                {'error': 'You are not the author of this post.'},
                status=status.HTTP_403_FORBIDDEN
            )
        kwargs['post'] = post
        return view_func(self, request, *args, **kwargs)
    return wrapper


def comment_owner_required(view_func):

    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        pk = kwargs.get('pk')
        try:
            comment = Comment.objects.select_related('user').get(pk=pk)
        except Comment.DoesNotExist:
            return Response(
                {'error': 'Comment not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if comment.user != request.user:
            return Response(
                {'error': 'You are not the author of this comment.'},
                status=status.HTTP_403_FORBIDDEN
            )
        kwargs['comment'] = comment
        return view_func(self, request, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════
# 4. PROFILE OWNER REQUIRED
# Checks username kwarg → verifies request.user matches
# ═══════════════════════════════════════════

def profile_owner_required(view_func):
  
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        username = kwargs.get('username')
        if request.user.username != username:
            return Response(
                {'error': 'You can only edit your own profile.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════
# 5. PUBLISHED POST REQUIRED
# Ensures slug resolves to a published post
# Attaches `post` to kwargs
# ═══════════════════════════════════════════

def published_post_required(view_func):
    """
    Ensures the post exists AND is published.
    Injects `post` into kwargs so view doesn't re-query.

    Usage:
        @published_post_required
        def get(self, request, slug, post, **kwargs):
            return Response({'title': post.title})
    """
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        slug = kwargs.get('slug')
        try:
            post = Post.objects.select_related('author', 'category').get(
                slug=slug, status='published'
            )
        except Post.DoesNotExist:
            return Response(
                {'error': 'Post not found or not yet published.'},
                status=status.HTTP_404_NOT_FOUND
            )
        kwargs['post'] = post
        return view_func(self, request, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════
# 6. ACTIVE USER REQUIRED
# Blocks deactivated accounts even if they have a valid JWT
# ═══════════════════════════════════════════

def active_user_required(view_func):
    """
    Blocks deactivated users (is_active=False) even with a valid token.

    Usage:
        @login_required
        @active_user_required
        def post(self, request, ...):
            ...
    """
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        if not request.user.is_active:
            return Response(
                {'error': 'Your account has been deactivated. Contact support.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════
# 7. RATE LIMIT
# Per-user or per-IP sliding window limiter
# ═══════════════════════════════════════════

_rate_limit_store = defaultdict(list)


def rate_limit(max_calls: int, period: int):
    """
    Limits a view method to `max_calls` per `period` seconds.
    Keyed by user ID (authenticated) or IP (anonymous).

    Usage:
        @login_required
        @rate_limit(max_calls=5, period=60)   # 5 claps per minute
        def post(self, request, slug):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            if request.user.is_authenticated:
                key = f"rl:user:{request.user.id}:{view_func.__qualname__}"
            else:
                ip  = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                      or request.META.get('REMOTE_ADDR', 'unknown')
                key = f"rl:ip:{ip}:{view_func.__qualname__}"

            now = time.time()
            _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < period]

            if len(_rate_limit_store[key]) >= max_calls:
                retry_after = int(period - (now - _rate_limit_store[key][0]))
                return Response(
                    {
                        'error': f'Too many requests. Max {max_calls} per {period}s.',
                        'retry_after_seconds': retry_after,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            _rate_limit_store[key].append(now)
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator


# ═══════════════════════════════════════════
# 8. LOG ACTION
# Logs every decorated call with user, method, path
# ═══════════════════════════════════════════

def log_action(action_name: str):
    """
    Logs every call with user info, HTTP method, and path.

    Usage:
        @log_action('publish_post')
        def post(self, request, slug):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            user = request.user.username if request.user.is_authenticated else 'anonymous'
            logger.info(
                f"[{action_name}] user={user} | method={request.method} | path={request.path}"
            )
            response = view_func(self, request, *args, **kwargs)
            logger.info(
                f"[{action_name}] done | status={response.status_code}"
            )
            return response
        return wrapper
    return decorator


# ═══════════════════════════════════════════
# 9. SELF FOLLOW GUARD
# Blocks a user from following themselves
# ═══════════════════════════════════════════

def cannot_follow_self(view_func):
    """
    Prevents a user from following their own profile.
    Must be used on a view with `username` kwarg.

    Usage:
        @login_required
        @cannot_follow_self
        def post(self, request, username):
            ...
    """
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        username = kwargs.get('username')
        if request.user.is_authenticated and request.user.username == username:
            return Response(
                {'error': 'You cannot follow yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════
# 10. ALREADY FOLLOWING GUARD
# Blocks duplicate follow requests
# ═══════════════════════════════════════════

def not_already_following(view_func):
    """
    Returns 400 if the current user is already following the target.
    Must be used on a view with `username` kwarg.

    Usage:
        @login_required
        @cannot_follow_self
        @not_already_following
        def post(self, request, username):
            ...
    """
    @functools.wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        from django.contrib.auth.models import User
        username = kwargs.get('username')
        try:
            target_profile = Profile.objects.get(user__username=username)
            my_profile     = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist:
            return Response({'error': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target_profile.followers.filter(pk=my_profile.pk).exists():
            return Response(
                {'error': f'You are already following {username}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper

