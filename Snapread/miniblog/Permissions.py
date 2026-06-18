from rest_framework.permissions import BasePermission, SAFE_METHODS


# ═══════════════════════════════════════════
# 1. IS AUTHOR OR READ ONLY
# ═══════════════════════════════════════════

class IsAuthorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # Support both `author` and `user` field naming conventions
        owner = getattr(obj, 'author', None) or getattr(obj, 'user', None)
        return owner == request.user


# ═══════════════════════════════════════════
# 2. IS PROFILE OWNER
# ═══════════════════════════════════════════

class IsProfileOwner(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user == request.user


# ═══════════════════════════════════════════
# 3. IS VERIFIED (email-verified users only)
# ═══════════════════════════════════════════

class IsVerifiedUser(BasePermission):

    message = 'Your account is not verified. Please verify your email to continue.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return request.user.profile.is_verified
        except Exception:
            return False


# ═══════════════════════════════════════════
# 4. IS ADMIN OR READ ONLY
# ═══════════════════════════════════════════

class IsAdminOrReadOnly(BasePermission):

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


# ═══════════════════════════════════════════
# 5. IS OWNER (generic)
# ═══════════════════════════════════════════

class IsOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


# ═══════════════════════════════════════════
# 6. IS AUTHENTICATED AND VERIFIED
# ═══════════════════════════════════════════

class IsAuthenticatedAndVerified(BasePermission):
    
    message = 'Authentication and email verification required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return request.user.profile.is_verified
        except Exception:
            return False