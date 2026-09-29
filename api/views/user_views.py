import logging
from django.utils.html import strip_tags
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from api.models import All_User, Role
from api.authentication import require_admin

logger = logging.getLogger("activity_audit")


# ==============================================================================
# Administrative User Management Views (Requires Admin / User Mgmt Privileges)
# ==============================================================================


@api_view(["POST"])
@require_admin
def create_user(request):
    """
    Admin endpoint to create a new user account and assign roles.
    """
    try:
        data = request.data
        username = strip_tags(str(data.get("username", "")).strip())
        email = strip_tags(str(data.get("email", "")).strip())
        password = data.get("password")
        isAdmin = bool(data.get("isAdmin", False))
        has_user_management = (
            bool(data.get("has_user_management", False)) if isAdmin else False
        )
        roles_data = data.get("roles", [])

        if not username:
            return Response(
                {"status": False, "message": "Username is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"status": False, "message": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not roles_data or len(roles_data) == 0:
            return Response(
                {"status": False, "message": "At least one role must be selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password)
        except ValidationError as e:
            return Response(
                {"status": False, "message": " ".join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if All_User.objects.filter(username=username).exists():
            return Response(
                {"status": False, "message": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_obj = All_User(
            username=username,
            email=email,
            isAdmin=isAdmin,
            has_user_management=has_user_management,
        )
        user_obj.set_password(password)
        user_obj.save()

        for role_name in roles_data:
            role, _ = Role.objects.get_or_create(name=role_name)
            user_obj.role.add(role)

        logger.info(f"User created: '{username}' by admin '{request.user.username}'")
        return Response(
            {
                "msg": "User created successfully",
                "username": username,
                "email": email,
                "isAdmin": isAdmin,
                "has_user_management": has_user_management,
                "roles": roles_data,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as e:
        logger.error(f"Error in create_user: {e}")
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
@require_admin
def get_all_users(request):
    """
    Admin endpoint to retrieve user list and roles.
    """
    try:
        all_users = All_User.objects.all()
        Response_data = {"total_users": all_users.count()}
        for user in all_users:
            Response_data[str(user.id)] = [
                {
                    "username": user.username,
                    "email": user.email,
                    "roles": list(user.role.values_list("name", flat=True)),
                    "isAdmin": user.isAdmin,
                    "has_user_management": user.has_user_management,
                }
            ]

        return Response(Response_data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in get_all_users: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["PUT"])
@require_admin
def update_user(request, id):
    """
    Admin endpoint to update existing user account information.
    """
    try:
        user = All_User.objects.get(id=id)

        username = strip_tags(str(request.data.get("username", "")).strip())
        email = strip_tags(str(request.data.get("email", "")).strip())
        password = request.data.get("password")
        isAdmin = bool(request.data.get("isAdmin", user.isAdmin))
        has_user_management = (
            bool(request.data.get("has_user_management", user.has_user_management))
            if isAdmin
            else False
        )
        roles_data = request.data.get("roles", [])

        if not username:
            return Response(
                {"status": False, "message": "Username is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not roles_data or len(roles_data) == 0:
            return Response(
                {"status": False, "message": "At least one role must be selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if All_User.objects.filter(username=username).exclude(id=id).exists():
            return Response(
                {"status": False, "message": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.username = username
        user.email = email
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                return Response(
                    {"status": False, "message": " ".join(e.messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.set_password(password)

        user.isAdmin = isAdmin
        user.has_user_management = has_user_management
        user.role.clear()

        for role_name in roles_data:
            role, _ = Role.objects.get_or_create(name=role_name)
            user.role.add(role)

        user.save()
        logger.info(f"User updated: ID {id} ('{username}') by admin '{request.user.username}'")

        return Response(
            {
                "status": True,
                "message": "User updated successfully",
                "username": user.username,
                "email": user.email,
                "isAdmin": user.isAdmin,
                "has_user_management": user.has_user_management,
                "roles": roles_data,
            },
            status=status.HTTP_200_OK,
        )

    except All_User.DoesNotExist:
        return Response(
            {"status": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in update_user: {e}")
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["DELETE"])
@require_admin
def delete_user(request, id):
    """
    Admin endpoint to delete a user account.
    """
    try:
        user = All_User.objects.get(id=id)

        # Industry standard: Prevent self-deletion
        if str(request.user.id) == str(user.id):
            logger.warning(f"Self-deletion attempt blocked for admin '{request.user.username}'")
            return Response(
                {"status": False, "message": "You cannot delete your own account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = user.username
        user.delete()
        logger.info(f"User deleted: ID {id} ('{username}') by admin '{request.user.username}'")

        return Response(
            {"status": True, "message": "User deleted successfully"},
            status=status.HTTP_200_OK,
        )

    except All_User.DoesNotExist:
        return Response(
            {"status": False, "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in delete_user: {e}")
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
@require_admin
def get_role_list(request):
    """
    Admin endpoint to retrieve default system roles list.
    """
    try:
        default_roles = [
            "inward",
            "programer",
            "qa",
            "accounts",
            "quotation",
            "inventory",
            "maintenance",
            "reports",
        ]
        for r_name in default_roles:
            Role.objects.get_or_create(name=r_name)

        Role.objects.exclude(name__in=default_roles).delete()
        roles = Role.objects.all()

        role_data = [{"id": role.id, "name": role.name} for role in roles]

        return Response(
            {
                "total_roles": roles.count(),
                "roles": role_data,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.error(f"Error in get_role_list: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
