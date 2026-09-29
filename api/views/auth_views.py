import os
import logging
import datetime
from datetime import timedelta

from django.conf import settings
from django.utils.html import strip_tags
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

import jwt  # type: ignore
from api.models import All_User, Role
from api.authentication import (
    validate_token,
    require_admin,
    get_access_token_secret,
    get_refresh_token_secret,
)

logger = logging.getLogger("activity_audit")


class LoginRateThrottle(ScopedRateThrottle):
    scope = "login"


ACCESS_TOKEN_SECRET = get_access_token_secret()
REFRESH_TOKEN_SECRET = get_refresh_token_secret()


def parse_timedelta(val_str, default_td):
    if not val_str:
        return default_td
    val_str = str(val_str).strip().lower()
    try:
        if val_str.endswith("m"):
            return datetime.timedelta(minutes=int(val_str[:-1]))
        elif val_str.endswith("h"):
            return datetime.timedelta(hours=int(val_str[:-1]))
        elif val_str.endswith("d"):
            return datetime.timedelta(days=int(val_str[:-1]))
        elif val_str.endswith("s"):
            return datetime.timedelta(seconds=int(val_str[:-1]))
    except ValueError:
        pass
    return default_td


def generate_access_token(user):
    """Generates a signed JWT access token for the given user."""
    access_expiry_str = os.getenv("ACCESS_TOKEN_EXPIRY", "15m")
    access_td = parse_timedelta(access_expiry_str, datetime.timedelta(minutes=15))
    payload = {
        "username": user.username,
        "type": "access",
        "exp": datetime.datetime.now(datetime.timezone.utc) + access_td,
        "iat": datetime.datetime.now(datetime.timezone.utc),
    }
    return jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm="HS256")


def generate_refresh_token(user):
    """Generates a signed JWT refresh token for the given user."""
    refresh_expiry_str = os.getenv("REFRESH_TOKEN_EXPIRY", "7d")
    refresh_td = parse_timedelta(refresh_expiry_str, datetime.timedelta(days=7))
    payload = {
        "username": user.username,
        "type": "refresh",
        "exp": datetime.datetime.now(datetime.timezone.utc) + refresh_td,
        "iat": datetime.datetime.now(datetime.timezone.utc),
    }
    return jwt.encode(payload, REFRESH_TOKEN_SECRET, algorithm="HS256")


# ==============================================================================
# Authentication Views (Login, Refresh, Me, Logout)
# ==============================================================================


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    """
    Authenticates user credentials and issues JWT Access & Refresh tokens.
    """
    try:
        raw_username = request.data.get("username")
        password = request.data.get("password")

        if not raw_username or not password:
            return Response(
                {
                    "success": False,
                    "error": "Username and password are required.",
                    "message": "Username and password are required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Input sanitization
        username = strip_tags(str(raw_username).strip())

        try:
            user = All_User.objects.get(username=username)
            if not user.check_password(password):
                logger.warning(f"Failed login attempt for username: '{username}' (invalid password)")
                return Response(
                    {
                        "success": False,
                        "error": "Invalid username or password.",
                        "message": "Invalid username or password.",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except All_User.DoesNotExist:
            logger.warning(f"Failed login attempt for unknown user: '{username}'")
            return Response(
                {
                    "success": False,
                    "error": "Invalid username or password.",
                    "message": "Invalid username or password.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not getattr(user, "is_active", True):
            return Response(
                {
                    "success": False,
                    "error": "User account has been deactivated.",
                    "message": "Account deactivated.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        roles = list(user.role.values_list("name", flat=True))
        user_data = {
            "username": user.username,
            "email": user.email,
            "isAdmin": user.isAdmin,
            "has_user_management": user.has_user_management,
            "roles": roles,
        }

        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user)

        response = Response(
            {
                "success": True,
                "message": "Login successful",
                "user": user_data,
                "username": user.username,
                "email": user.email,
                "isAdmin": user.isAdmin,
                "has_user_management": user.has_user_management,
                "roles": roles,
                "accesstoken": access_token,
            }
        )

        is_secure = not getattr(settings, "DEBUG", True)
        cookie_kwargs = {
            "httponly": True,
            "samesite": "Lax",
            "secure": is_secure,
            "max_age": 7 * 24 * 60 * 60,
            "path": "/",
        }

        response.set_cookie(key="refreshToken", value=refresh_token, **cookie_kwargs)
        return response
    except Exception as e:
        logger.error(f"Internal error during login execution: {e}")
        return Response(
            {
                "success": False,
                "error": "Server error during authentication. Please contact administrator.",
                "message": "Server error during authentication.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token(request):
    """
    Exchanges a valid Refresh Token cookie or payload for a new Access Token.
    """
    token = request.COOKIES.get("refreshToken") or request.data.get("refreshToken")
    if not token:
        return Response(
            {"success": False, "error": "Refresh token missing", "message": "Please Login now!"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        payload = jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            return Response(
                {"success": False, "error": "Invalid token type"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = All_User.objects.get(username=payload.get("username"))
        if not getattr(user, "is_active", True):
            return Response(
                {"success": False, "error": "Account deactivated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        new_access_token = generate_access_token(user)
        return Response({"success": True, "accesstoken": new_access_token})
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, All_User.DoesNotExist):
        return Response(
            {"success": False, "error": "Invalid or expired refresh token"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["GET"])
@validate_token
def me(request):
    """
    Validates current user session and returns user profile metadata.
    """
    user = getattr(request, "user", None) or getattr(request, "user_obj", None)
    if not user or not getattr(user, "is_authenticated", False):
        return Response(
            {"success": False, "error": "Invalid or expired access token"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    roles = list(user.role.values_list("name", flat=True))
    user_data = {
        "username": user.username,
        "email": user.email,
        "isAdmin": user.isAdmin,
        "has_user_management": user.has_user_management,
        "roles": roles,
    }
    return Response({"success": True, "message": "Session valid", "user": user_data, **user_data})


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    """
    Clears refresh token cookie.
    """
    response = Response({"success": True, "message": "Logged out successfully"})
    is_secure = not getattr(settings, "DEBUG", True)
    response.delete_cookie("refreshToken", path="/", samesite="Lax")
    response.set_cookie(
        key="refreshToken",
        value="",
        httponly=True,
        samesite="Lax",
        secure=is_secure,
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        path="/",
    )
    return response

