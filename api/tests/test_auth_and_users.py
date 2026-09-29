from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from api.models import All_User, Role
from api.views.auth_views import generate_access_token


class AuthAndUserModuleTests(TestCase):
    """
    Comprehensive tests for Authentication, Authorization, Roles, and User Management.
    """

    def setUp(self):
        self.client = APIClient()
        # Seed core roles
        self.role_admin = Role.objects.create(name="admin")
        self.role_inward = Role.objects.create(name="inward")
        self.role_qa = Role.objects.create(name="qa")
        self.role_accounts = Role.objects.create(name="accounts")

        # Create admin user
        self.admin_user = All_User.objects.create(
            username="adminuser",
            email="admin@sakthilaser.com",
            isAdmin=True,
            has_user_management=True,
        )
        self.admin_user.set_password("Admin@1234")
        self.admin_user.save()
        self.admin_user.role.add(self.role_admin)

        # Create standard operator user
        self.standard_user = All_User.objects.create(
            username="qa_user",
            email="qa@sakthilaser.com",
            isAdmin=False,
            has_user_management=False,
        )
        self.standard_user.set_password("QaUser@1234")
        self.standard_user.save()
        self.standard_user.role.add(self.role_qa)

        # Generate Bearer token for admin API operations
        self.token = generate_access_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_login_success(self):
        """User can login with valid credentials and receive token."""
        client_anon = APIClient()
        response = client_anon.post(
            reverse("login"),
            {"username": "adminuser", "password": "Admin@1234"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))
        self.assertIn("accesstoken", response.data)
        self.assertEqual(response.data["username"], "adminuser")

    def test_login_invalid_password(self):
        """Login fails with invalid password."""
        client_anon = APIClient()
        response = client_anon.post(
            reverse("login"),
            {"username": "adminuser", "password": "WrongPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_get_current_user_me(self):
        """Authenticated user can fetch profile details."""
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "adminuser")
        self.assertEqual(response.data["email"], "admin@sakthilaser.com")

    def test_get_role_list(self):
        """Fetch all available roles."""
        response = self.client.get(reverse("get_role_list"))
        self.assertEqual(response.status_code, 200)
        role_names = [r["name"] for r in response.data.get("roles", [])]
        self.assertIn("inward", role_names)
        self.assertIn("qa", role_names)
        self.assertIn("accounts", role_names)

    def test_create_user_flow(self):
        """Admin creates a new ERP user with assigned roles."""
        payload = {
            "username": "inward_clerk",
            "email": "inward@sakthilaser.com",
            "password": "Password@123",
            "roles": ["inward"],
            "isAdmin": False,
            "has_user_management": False,
        }
        response = self.client.post(reverse("create_user"), payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(All_User.objects.filter(username="inward_clerk").exists())
        created = All_User.objects.get(username="inward_clerk")
        self.assertTrue(created.check_password("Password@123"))

    def test_create_duplicate_user_rejected(self):
        """Creating duplicate username is rejected."""
        payload = {
            "username": "adminuser",
            "email": "duplicate@sakthilaser.com",
            "password": "Password@123",
            "roles": ["admin"],
        }
        response = self.client.post(reverse("create_user"), payload, format="json")
        self.assertIn(response.status_code, [400, 409])

    def test_get_all_users(self):
        """Listing all registered users."""
        response = self.client.get(reverse("get_all_users"))
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("total_users", 0), 2)
        users_info = []
        for k, v in response.data.items():
            if k != "total_users" and isinstance(v, list) and len(v) > 0:
                users_info.append(v[0].get("username"))
        self.assertIn("adminuser", users_info)
        self.assertIn("qa_user", users_info)

    def test_update_user_details(self):
        """Updating user email and permissions."""
        payload = {
            "username": "qa_user",
            "email": "qa_updated@sakthilaser.com",
            "roles": ["qa", "accounts"],
            "isAdmin": True,
            "has_user_management": True,
        }
        response = self.client.put(
            reverse("update_user", kwargs={"id": self.standard_user.id}),
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.standard_user.refresh_from_db()
        self.assertEqual(self.standard_user.email, "qa_updated@sakthilaser.com")
        self.assertTrue(self.standard_user.isAdmin)
        self.assertTrue(self.standard_user.has_user_management)

    def test_user_requires_at_least_one_role(self):
        """Creating or updating user without roles is rejected."""
        payload = {
            "username": "no_role_user",
            "email": "norole@sakthilaser.com",
            "password": "Password@123",
            "roles": [],
        }
        response = self.client.post(reverse("create_user"), payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("message"), "At least one role must be selected.")

    def test_user_management_requires_admin(self):
        """User management access cannot be given if isAdmin is False."""
        payload = {
            "username": "qa_user",
            "email": "qa_user@sakthilaser.com",
            "roles": ["qa"],
            "isAdmin": False,
            "has_user_management": True,
        }
        response = self.client.put(
            reverse("update_user", kwargs={"id": self.standard_user.id}),
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.standard_user.refresh_from_db()
        self.assertFalse(self.standard_user.has_user_management)

    def test_delete_user(self):
        """Deleting a user removes them from the database."""
        user_to_delete = All_User.objects.create(
            username="temp_user",
            email="temp@sakthilaser.com",
        )
        user_id = user_to_delete.id
        response = self.client.delete(reverse("delete_user", kwargs={"id": user_id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(All_User.objects.filter(id=user_id).exists())

