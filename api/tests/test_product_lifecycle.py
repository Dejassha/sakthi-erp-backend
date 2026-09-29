import datetime
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from api.models import (
    All_User,
    company,
    machine_operator,
    material_type,
    Machine,
    product_details,
    product_material,
    programer_details,
    qa_details,
    acc_details,
)


class ProductLifecycleModuleTests(TestCase):
    """
    Tests for Full Manufacturing Execution Lifecycle:
    Inward -> CNC Programmer -> QA Inspection -> Accounts Billing -> Dashboard Tracking.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = All_User.objects.create(username="testadmin", isAdmin=True)
        self.client.force_authenticate(user=self.user)

        self.comp = company.objects.create(
            company_name="Titan Engineering Corp",
            customer_name="Titan Customer",
            contact_no="9876543210",
            created_by="testadmin",
        )
        self.op = machine_operator.objects.create(
            operator_name="Operator Suresh", created_by="testadmin"
        )
        self.mat = material_type.objects.create(
            material_name="MS Sheet", density_value=7.85, created_by="testadmin"
        )
        self.machine = Machine.objects.create(
            machine_name="Trumpf Laser 4kW", does_need_gas=True, created_by="testadmin"
        )

    def test_complete_manufacturing_lifecycle_flow(self):
        """
        Simulate the complete lifecycle of a job:
        1. Inward: Record slip, drawing, company, materials.
        2. Programmer: Assign program name, cut time, nesting sheet details.
        3. QA: Inspect cut parts, record machine runtime and inspection logs.
        4. Accounts: Invoicing and billing status.
        5. Dashboard: Verify complete synchronized status.
        """
        # ==========================================
        # STEP 1: INWARD CREATION
        # ==========================================
        inward_payload = {
            "inward_slip_number": "J-0001",
            "company_name": self.comp.company_name,
            "customer_name": self.comp.customer_name,
            "contact_no": self.comp.contact_no,
            "job_type": "Job Work",
            "sheet_type": "Fresh",
            "worker_no": "EMP-101",
            "materials": [
                {
                    "mat_type": self.mat.material_name,
                    "thick": "3.0",
                    "length": 2500,
                    "width": 1250,
                    "quantity": 10,
                    "density": 7.85,
                    "unit_weight": 73.59,
                    "total_weight": 735.9,
                    "total_length": 25000,
                    "total_width": 12500,
                    "stock_due": "In Stock",
                    "remarks": "Bracket Frame A1",
                }
            ],
            "created_by": "testadmin",
        }

        res_inward = self.client.post(
            reverse("add_inward_details"), inward_payload, format="json"
        )
        self.assertIn(res_inward.status_code, [200, 201])

        product = product_details.objects.filter(
            inward_slip_number="J-0001"
        ).first()
        self.assertIsNotNone(product)
        self.assertEqual(product.company_name, self.comp.company_name)

        # Verify materials were created
        materials = product_material.objects.filter(product=product)
        self.assertEqual(materials.count(), 1)
        material_item = materials.first()

        # ==========================================
        # STEP 2: PROGRAMMER CNC NESTING
        # ==========================================
        prog_payload = {
            "material_id": material_item.id,
            "program_no": "PRG-NC-9021",
            "program_date": "2026-09-18",
            "processed_quantity": 10,
            "balance_quantity": 0,
            "processed_width": 1250,
            "processed_length": 2500,
            "remaining_width": 0,
            "remaining_length": 0,
            "used_weight": 735.9,
            "number_of_sheets": 10,
            "cut_length_per_sheet": 120.5,
            "pierce_per_sheet": 40,
            "processed_mins_per_sheet": 12.0,
            "total_planned_hours": "02:00:00",
            "total_meters": 1205.0,
            "total_piercing": 400,
            "total_used_weight": 735.9,
            "total_no_of_sheets": 10,
            "remarks": "Nesting completed with optimal sheet layout.",
            "created_by": "testadmin",
        }

        res_prog = self.client.post(
            reverse("add_programer_Details"), prog_payload, format="json"
        )
        self.assertIn(res_prog.status_code, [200, 201])

        # ==========================================
        # STEP 3: QA QUALITY INSPECTION
        # ==========================================
        qa_payload = {
            "material_id": material_item.id,
            "processed_date": "2026-09-18",
            "shift": "Shift 1",
            "created_by": "testadmin",
            "machines_used": [
                {
                    "machine_name": self.machine.machine_name,
                    "date": "2026-09-18",
                    "start_time": "09:00:00",
                    "end_time": "11:00:00",
                    "runtime": "02:00:00",
                    "operator_name": self.op.operator_name,
                    "gas_type": "Nitrogen",
                }
            ],
        }

        res_qa = self.client.post(
            reverse("add_qa_details"), qa_payload, format="json"
        )
        self.assertIn(res_qa.status_code, [200, 201])

        # ==========================================
        # STEP 4: ACCOUNTS BILLING
        # ==========================================
        acc_payload = {
            "product_details": product.id,
            "material_details": [material_item.id],
            "invoice_no": "INV-2026-8801",
            "transporter_no": "TN-38-AB-1234",
            "payments_terms": "30 Days Credit",
            "status": "completed",
            "remarks": "Ready for dispatch",
            "created_by": "testadmin",
        }

        res_acc = self.client.post(
            reverse("add_acc_details"), acc_payload, format="json"
        )
        self.assertIn(res_acc.status_code, [200, 201])

        # ==========================================
        # STEP 5: DASHBOARD & OVERALL RETRIEVAL
        # ==========================================
        res_dash = self.client.get(reverse("get_dashboard_list"))
        self.assertEqual(res_dash.status_code, 200)

        res_materials = self.client.get(
            reverse("get_materials_by_product"), {"product_id": product.id}
        )
        self.assertEqual(res_materials.status_code, 200)
