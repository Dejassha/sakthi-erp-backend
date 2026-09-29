from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from api.models import (
    All_User,
    company,
    machine_operator,
    material_type,
    GasDetails,
)


class MasterDataModuleTests(TestCase):
    """
    Tests for Master Data: Companies, Operators, Material Types, and Gas Details.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = All_User.objects.create(username="adminuser", isAdmin=True)
        self.client.force_authenticate(user=self.user)

    # ------------------ Company Tests ------------------
    def test_company_crud_lifecycle(self):
        """Create, read, update, and delete customer company."""
        # 1. Create
        create_res = self.client.post(
            reverse("add_company"),
            {
                "company_name": "Apex Engineering Ltd",
                "customer_name": "Apex Customer",
                "contact_no": "9876543210",
                "created_by": "adminuser",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        comp = company.objects.get(company_name="Apex Engineering Ltd")

        # 2. Read
        get_res = self.client.get(reverse("get_companies"))
        self.assertEqual(get_res.status_code, 200)
        self.assertTrue(
            any(c["company_name"] == "Apex Engineering Ltd" for c in get_res.data)
        )

        # 3. Update
        update_res = self.client.put(
            reverse("update_company", kwargs={"pk": comp.id}),
            {
                "company_name": "Apex Precision Ltd",
                "customer_name": "Apex Updated",
                "contact_no": "9876543211",
                "created_by": "adminuser",
            },
            format="json",
        )
        self.assertEqual(update_res.status_code, 200)
        comp.refresh_from_db()
        self.assertEqual(comp.company_name, "Apex Precision Ltd")

        # 4. Delete
        del_res = self.client.delete(
            reverse("delete_company", kwargs={"pk": comp.id})
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(company.objects.filter(id=comp.id).exists())

    # ------------------ Operator Tests ------------------
    def test_operator_crud_lifecycle(self):
        """Create, read, update, and delete machine operator."""
        # 1. Create
        create_res = self.client.post(
            reverse("add_operator"),
            {"operator_name": "Karthik Raj", "created_by": "adminuser"},
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        operator = machine_operator.objects.get(operator_name="Karthik Raj")

        # 2. Read
        get_res = self.client.get(reverse("get_operator"))
        self.assertEqual(get_res.status_code, 200)
        self.assertTrue(
            any(op["operator_name"] == "Karthik Raj" for op in get_res.data)
        )

        # 3. Update
        update_res = self.client.put(
            reverse("update-operator", kwargs={"operator_id": operator.id}),
            {"operator_name": "Karthik Raja", "created_by": "adminuser"},
            format="json",
        )
        self.assertEqual(update_res.status_code, 200)
        operator.refresh_from_db()
        self.assertEqual(operator.operator_name, "Karthik Raja")

        # 4. Delete
        del_res = self.client.delete(
            reverse("delete-operator", kwargs={"operator_id": operator.id})
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(machine_operator.objects.filter(id=operator.id).exists())

    # ------------------ Material Type Tests ------------------
    def test_material_type_crud_lifecycle(self):
        """Create, read, update, and delete material type."""
        # 1. Create
        create_res = self.client.post(
            reverse("add_material_type"),
            {
                "material_name": "SS 304",
                "density_value": 7.93,
                "created_by": "adminuser",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        material = material_type.objects.get(material_name="SS 304")

        # 2. Read
        get_res = self.client.get(reverse("get_material_type"))
        self.assertEqual(get_res.status_code, 200)
        self.assertTrue(
            any(m["material_name"] == "SS 304" for m in get_res.data)
        )

        # 3. Update
        update_res = self.client.put(
            reverse("update_material_type", kwargs={"pk": material.id}),
            {
                "material_name": "SS 316",
                "density_value": 8.0,
                "created_by": "adminuser",
            },
            format="json",
        )
        self.assertEqual(update_res.status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.material_name, "SS 316")

        # 4. Delete
        del_res = self.client.delete(
            reverse("delete_material_type", kwargs={"pk": material.id})
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(material_type.objects.filter(id=material.id).exists())

    # ------------------ Gas Details Tests ------------------
    def test_gas_details_crud_lifecycle(self):
        """Create, read, update, and delete gas records."""
        # 1. Create
        create_res = self.client.post(
            reverse("add_gas_details"),
            {
                "name": "High Purity Nitrogen N2",
                "created_by": "adminuser",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        gas = GasDetails.objects.get(name="High Purity Nitrogen N2")

        # 2. Read
        get_res = self.client.get(reverse("get_gas_details"))
        self.assertEqual(get_res.status_code, 200)

        # 3. Update
        update_res = self.client.put(
            reverse("update_gas_details", kwargs={"pk": gas.id}),
            {
                "name": "High Purity Nitrogen (Grade 5.0)",
                "created_by": "adminuser",
            },
            format="json",
        )
        self.assertEqual(update_res.status_code, 200)
        gas.refresh_from_db()
        self.assertEqual(gas.name, "High Purity Nitrogen (Grade 5.0)")

        # 4. Delete
        del_res = self.client.delete(
            reverse("delete_gas_details", kwargs={"pk": gas.id})
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(GasDetails.objects.filter(id=gas.id).exists())
