import os
import logging
import jwt  # type: ignore
from functools import wraps
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework import status
from api.models import All_User

logger = logging.getLogger("activity_audit")


def get_access_token_secret():
    """
    Resolves the JWT access token secret key securely.
    Falls back to settings.SECRET_KEY if ACCESS_TOKEN_SECRET environment variable is not explicitly defined.
    """
    secret = os.getenv("ACCESS_TOKEN_SECRET")
    if not secret:
        secret = getattr(settings, "SECRET_KEY", None)
    if not secret:
        raise ValueError(
            "SECURITY RISK: ACCESS_TOKEN_SECRET or settings.SECRET_KEY must be defined."
        )
    return secret


def get_refresh_token_secret():
    """
    Resolves the JWT refresh token secret key securely.
    Falls back to settings.SECRET_KEY + '_ref' if REFRESH_TOKEN_SECRET environment variable is not explicitly defined.
    """
    secret = os.getenv("REFRESH_TOKEN_SECRET")
    if not secret:
        base = getattr(settings, "SECRET_KEY", None)
        if base:
            secret = f"{base}_ref"
    if not secret:
        raise ValueError(
            "SECURITY RISK: REFRESH_TOKEN_SECRET or settings.SECRET_KEY must be defined."
        )
    return secret


ACCESS_TOKEN_SECRET = get_access_token_secret()
REFRESH_TOKEN_SECRET = get_refresh_token_secret()


def extract_bearer_token(request):
    """
    Extracts Bearer token cleanly from HTTP Authorization header.
    Handles extra whitespace, case-insensitivity, and missing headers safely.
    """
    auth_header = request.headers.get("Authorization") or request.META.get(
        "HTTP_AUTHORIZATION"
    )
    if not auth_header:
        return None

    parts = str(auth_header).strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def decode_jwt_token(token):
    """
    Decodes and validates a JWT access token.
    Enforces HS256 algorithm and token type verification.
    """
    if not token or not isinstance(token, str):
        return None

    secret = get_access_token_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "require": ["username", "type", "exp"],
            },
        )
        if payload.get("type") != "access":
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, jwt.DecodeError):
        return None
    except Exception as e:
        logger.error(f"Unexpected error during JWT token decoding: {e}")
        return None


class JWTAuthentication(BaseAuthentication):
    """
    Industry-standard DRF Authentication class that validates JWT Bearer tokens
    for API endpoints and attaches the authenticated user instance from the backend DB.
    """

    def authenticate(self, request):
        if "refresh_token" in request.path:
            return None

        token = extract_bearer_token(request)
        if not token:
            return None

        payload = decode_jwt_token(token)
        if not payload:
            raise AuthenticationFailed("Invalid or expired access token.")

        username = payload.get("username")
        if not username:
            raise AuthenticationFailed("Token contains invalid user payload.")

        try:
            # User is ALWAYS fetched from backend DB using verified JWT claim
            user = All_User.objects.get(username=username)
        except All_User.DoesNotExist:
            raise AuthenticationFailed(
                "User account associated with this token does not exist."
            )

        # Active account check
        if not getattr(user, "is_active", True):
            raise AuthenticationFailed("User account has been deactivated.")

        # Synchronize backend request user context
        request.user = user
        request.user_obj = user
        return (user, token)

    def authenticate_header(self, request):
        """
        Return WWW-Authenticate header to instruct client to use Bearer scheme.
        Ensures DRF correctly returns 401 Unauthorized instead of 403 Forbidden on missing auth.
        """
        return 'Bearer realm="api"'


def get_authenticated_user(request):
    """
    Safely retrieves the authenticated All_User instance from backend context or JWT token.
    NEVER trusts user identity, IDs, or roles sent in request payloads/query params from the frontend.
    """
    user = getattr(request, "user", None) or getattr(request, "user_obj", None)
    if user and getattr(user, "is_authenticated", False):
        return user

    token = extract_bearer_token(request)
    if token:
        payload = decode_jwt_token(token)
        if payload and payload.get("username"):
            try:
                user = All_User.objects.get(username=payload.get("username"))
                if getattr(user, "is_active", True):
                    request.user = user
                    request.user_obj = user
                    return user
            except All_User.DoesNotExist:
                pass
    return None


def get_authenticated_username(request, default="System"):
    """
    Returns the verified username of the authenticated backend user.
    Prevents parameter tampering where frontend sends custom user/created_by values.
    """
    user = get_authenticated_user(request)
    if user and hasattr(user, "username") and user.username:
        return user.username
    return default


# ==============================================================================
# DRF Authorization Permission Classes (RBAC)
# ==============================================================================


class IsAuthenticatedUser(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None) or getattr(request, "user_obj", None)
        return bool(user and user.is_authenticated)


class IsAdmin(BasePermission):
    """
    Allows access only to system admins (isAdmin=True or has_user_management=True).
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None) or getattr(request, "user_obj", None)
        if not (user and user.is_authenticated):
            return False
        return bool(
            getattr(user, "isAdmin", False)
            or getattr(user, "has_user_management", False)
        )


class HasUserManagement(BasePermission):
    """
    Allows access to users with user management privileges or admin rights.
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None) or getattr(request, "user_obj", None)
        if not (user and user.is_authenticated):
            return False
        return bool(
            getattr(user, "has_user_management", False)
            or getattr(user, "isAdmin", False)
        )


class RolePermission(BasePermission):
    """
    Dynamic DRF Permission class for role-based access control (RBAC).
    Usage:
        permission_classes = [RolePermission.for_roles("inward", "inventory")]
    """

    allowed_roles = ()

    def __init__(self, allowed_roles=None):
        if allowed_roles is not None:
            self.allowed_roles = tuple(allowed_roles)

    @classmethod
    def for_roles(cls, *roles):
        class DynamicRolePermission(cls):
            allowed_roles = roles

        return DynamicRolePermission

    def has_permission(self, request, view):
        user = getattr(request, "user", None) or getattr(request, "user_obj", None)
        if not (user and user.is_authenticated):
            return False

        # System admins bypass role restriction
        if getattr(user, "isAdmin", False):
            return True

        if not self.allowed_roles:
            return True

        user_roles = (
            set(user.role.values_list("name", flat=True))
            if hasattr(user, "role")
            else set()
        )
        return bool(user_roles.intersection(self.allowed_roles))


# ==============================================================================
# Function-Based View (FBV) Authorization Decorators
# ==============================================================================


def validate_token(view_func):
    """
    Decorator to validate JWT Bearer token on any specific API view route.
    Attaches user instance to request.user, request.user_obj, and token to request.auth.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        token = extract_bearer_token(request)
        if not token:
            return Response(
                {
                    "success": False,
                    "error": "Authorization token missing or invalid format",
                    "message": "Unauthorized access",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        payload = decode_jwt_token(token)
        if not payload:
            return Response(
                {
                    "success": False,
                    "error": "Invalid or expired token",
                    "message": "Session expired, please login again",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        username = payload.get("username")
        try:
            user = All_User.objects.get(username=username)
        except All_User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "User account associated with this token does not exist",
                    "message": "Unauthorized access",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not getattr(user, "is_active", True):
            return Response(
                {
                    "success": False,
                    "error": "User account has been deactivated",
                    "message": "Unauthorized access",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.user = user
        request.user_obj = user
        request.auth = token
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_roles(*allowed_roles):
    """
    Decorator to enforce role-based access control (RBAC) on function-based API views.
    Combines token authentication and role authorization checks.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            token = extract_bearer_token(request)
            if not token:
                return Response(
                    {
                        "success": False,
                        "error": "Authorization token missing or invalid format",
                        "message": "Unauthorized access",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            payload = decode_jwt_token(token)
            if not payload:
                return Response(
                    {
                        "success": False,
                        "error": "Invalid or expired token",
                        "message": "Session expired, please login again",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            username = payload.get("username")
            try:
                user = All_User.objects.get(username=username)
            except All_User.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "error": "User account associated with this token does not exist",
                        "message": "Unauthorized access",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not getattr(user, "is_active", True):
                return Response(
                    {
                        "success": False,
                        "error": "User account has been deactivated",
                        "message": "Unauthorized access",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            request.user = user
            request.user_obj = user
            request.auth = token

            # Admin bypass
            if getattr(user, "isAdmin", False):
                return view_func(request, *args, **kwargs)

            if allowed_roles:
                user_roles = (
                    set(user.role.values_list("name", flat=True))
                    if hasattr(user, "role")
                    else set()
                )
                if not user_roles.intersection(allowed_roles):
                    return Response(
                        {
                            "success": False,
                            "error": "Insufficient permissions",
                            "message": "You do not have permission to perform this action.",
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def require_admin(view_func):
    """
    Decorator requiring admin or user management rights for function-based API views.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        token = extract_bearer_token(request)
        if not token:
            return Response(
                {
                    "success": False,
                    "error": "Authorization token missing or invalid format",
                    "message": "Unauthorized access",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        payload = decode_jwt_token(token)
        if not payload:
            return Response(
                {
                    "success": False,
                    "error": "Invalid or expired token",
                    "message": "Session expired, please login again",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = All_User.objects.get(username=payload.get("username"))
        except All_User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "User account associated with this token does not exist",
                    "message": "Unauthorized access",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not getattr(user, "is_active", True):
            return Response(
                {
                    "success": False,
                    "error": "User account has been deactivated",
                    "message": "Unauthorized access",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.user = user
        request.user_obj = user
        request.auth = token

        if not (
            getattr(user, "isAdmin", False)
            or getattr(user, "has_user_management", False)
        ):
            return Response(
                {
                    "success": False,
                    "error": "Access denied",
                    "message": "Admin privileges are required to access this resource.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view
