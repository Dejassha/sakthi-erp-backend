from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from api.models import (
    All_User,
    InventoryPartName,
    InventoryPurpose,
    InventoryPart,
    InventoryUsage,
)


class InventoryModuleTests(TestCase):
    """
    Tests for Inventory Parts, Usage Types, FIFO / Batch Consumption, and Stock History.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = All_User.objects.create(username="testadmin", isAdmin=True)
        self.client.force_authenticate(user=self.user)

    def test_inventory_masters_crud(self):
        """Part Names and Usage Types master CRUD."""
        # 1. Part Name Master
        res_pn = self.client.post(
            reverse("add_inventory_part_name"),
            {"part_name": "Focus Lens 20mm"},
            format="json",
        )
        self.assertEqual(res_pn.status_code, 201)
        pn = InventoryPartName.objects.get(part_name="Focus Lens 20mm")

        get_pn = self.client.get(reverse("get_inventory_part_names"))
        self.assertEqual(get_pn.status_code, 200)

        # 2. Usage Type Master
        res_ut = self.client.post(
            reverse("add_inventory_usage_type"),
            {"name": "Breakdown Replacement"},
            format="json",
        )
        self.assertEqual(res_ut.status_code, 201)
        ut = InventoryPurpose.objects.get(name="Breakdown Replacement")

        get_ut = self.client.get(reverse("get_inventory_usage_types"))
        self.assertEqual(get_ut.status_code, 200)

    def test_inventory_parts_and_fifo_consumption(self):
        """Adding batches of parts and consuming via FIFO vs newest batch."""
        # Add Batch 1 (Older, cheaper)
        part_old = InventoryPart.objects.create(
            part_name="Laser Nozzle D1.5mm",
            stock_quantity=10,
            available_quantity=10,
            purchase_price=500,
            purchase_date="2026-01-10",
        )

        # Add Batch 2 (Newer, revised cost)
        part_new = InventoryPart.objects.create(
            part_name="Laser Nozzle D1.5mm",
            stock_quantity=15,
            available_quantity=15,
            purchase_price=550,
            purchase_date="2026-08-10",
        )

        # 1. Consume from Old Batch first (FIFO default)
        res_use_old = self.client.post(
            reverse("add_inventory_usage"),
            {
                "part": part_old.id,
                "used_quantity": 4,
                "used_by": "MaintTechnician",
                "used_date": "2026-09-15",
                "use_new_quantity": False,
                "maintenance_type": "Periodic Preventive",
            },
            format="json",
        )
        self.assertEqual(res_use_old.status_code, 201)
        part_old.refresh_from_db()
        part_new.refresh_from_db()
        self.assertEqual(part_old.available_quantity, 6)
        self.assertEqual(part_new.available_quantity, 15)

        # 2. Consume from New Batch directly
        res_use_new = self.client.post(
            reverse("add_inventory_usage"),
            {
                "part": part_old.id,
                "used_quantity": 5,
                "used_by": "MaintTechnician",
                "used_date": "2026-09-15",
                "use_new_quantity": True,
                "maintenance_type": "Breakdown Fix",
            },
            format="json",
        )
        self.assertEqual(res_use_new.status_code, 201)
        part_old.refresh_from_db()
        part_new.refresh_from_db()
        self.assertEqual(part_old.available_quantity, 6)
        self.assertEqual(part_new.available_quantity, 10)

    def test_inventory_history_recording(self):
        """Recording inventory stock addition and checking history."""
        res_history = self.client.post(
            reverse("record_inventory_history"),
            {
                "part_name": "Laser Protective Window",
                "action": "Stock Added",
                "quantity": 20,
                "purchase_price": 850,
                "user": "Admin",
            },
            format="json",
        )
        self.assertEqual(res_history.status_code, 201)
