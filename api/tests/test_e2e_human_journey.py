import datetime
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.utils import timezone
from api.models import (
    All_User,
    Role,
    company,
    machine_operator,
    material_type,
    GasDetails,
    Machine,
    InventoryPart,
    product_details,
    product_material,
    programer_details,
    qa_details,
    acc_details,
    BreakdownMaintenance,
    MaintenanceSchedule,
    Quotation,
)


class EndToEndHumanERPJourneyTests(TestCase):
    """
    Simulates a real human business lifecycle from end-to-end:
    Login -> Master Data Setup -> Quotation -> Inward -> CNC Nesting ->
    Spare Part Inventory Usage & Breakdown Fix -> QA Inspection -> Accounts Billing ->
    Periodic Maintenance -> Reports & Excel Export.
    """

    def test_complete_factory_business_journey(self):
        client = APIClient()
        today = timezone.now().date()

        # =========================================================================
        # 1. USER AUTHENTICATION & LOGIN
        # =========================================================================
        role_admin = Role.objects.create(name="admin")
        admin = All_User.objects.create(
            username="sakthi_admin",
            email="admin@sakthilaser.com",
            isAdmin=True,
            has_user_management=True,
        )
        admin.set_password("AdminSecurePass!1")
        admin.save()
        admin.role.add(role_admin)

        login_res = client.post(
            reverse("login"),
            {"username": "sakthi_admin", "password": "AdminSecurePass!1"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        client.force_authenticate(user=admin)

        # =========================================================================
        # 2. MASTER DATA SETUP
        # =========================================================================
        # Add Customer Company
        comp_res = client.post(
            reverse("add_company"),
            {
                "company_name": "Larsen & Toubro Ltd",
                "customer_name": "L&T Heavy Engineering",
                "contact_no": "9443322110",
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertEqual(comp_res.status_code, 201)

        # Add Operator
        op_res = client.post(
            reverse("add_operator"),
            {"operator_name": "Murugan R", "created_by": "sakthi_admin"},
            format="json",
        )
        self.assertEqual(op_res.status_code, 201)

        # Add Material Type
        mat_res = client.post(
            reverse("add_material_type"),
            {
                "material_name": "SS 316L",
                "density_value": 8.00,
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertEqual(mat_res.status_code, 201)

        # Add Machine
        mach_res = client.post(
            reverse("add_machine"),
            {
                "machine_name": "Bystronic Fiber Laser 10kW",
                "does_need_gas": True,
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertEqual(mach_res.status_code, 201)
        machine = Machine.objects.get(machine_name="Bystronic Fiber Laser 10kW")

        # Add Inventory Spare Parts Stock
        spare_part = InventoryPart.objects.create(
            part_name="High-Pressure Nitrogen Nozzle 2.0mm",
            stock_quantity=10,
            available_quantity=10,
            purchase_price=750,
            purchase_date=str(today - datetime.timedelta(days=10)),
        )

        # =========================================================================
        # 3. QUOTATION & ESTIMATION
        # =========================================================================
        quot_res = client.post(
            reverse("add_quotation"),
            {
                "doc_no": "QUOT-LT-2026-001",
                "doc_date": str(today),
                "company_name": "Larsen & Toubro Ltd",
                "customer_name": "L&T Heavy Engineering",
                "contact": "9443322110",
                "email": "purchases@lnt.com",
                "customer_gst_no": "33AAACL1234F1Z1",
                "net_amount": 50000.0,
                "gst_percentage": 18.0,
                "gst_amount": 9000.0,
                "total_amount": 59000.0,
                "status": "approved",
                "payment_terms": "30 Days Credit",
                "created_by": "sakthi_admin",
                "items": [
                    {
                        "description": "Laser Cutting 4mm SS 316L Flange Plate",
                        "material": "SS 316L 4mm",
                        "quantity": 200,
                        "uom": "Nos",
                        "unit_rate": 250.0,
                        "total_amount": 50000.0,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(quot_res.status_code, 201)

        # =========================================================================
        # 4. INWARD MATERIAL RECEIPT
        # =========================================================================
        inward_res = client.post(
            reverse("add_inward_details"),
            {
                "inward_slip_number": "J-9991",
                "company_name": "Larsen & Toubro Ltd",
                "customer_name": "L&T Heavy Engineering",
                "contact_no": "9443322110",
                "job_type": "Job Work",
                "sheet_type": "Fresh",
                "worker_no": "Murugan R",
                "materials": [
                    {
                        "mat_type": "SS 316L",
                        "thick": "4.0",
                        "length": 3000,
                        "width": 1500,
                        "quantity": 8,
                        "density": 8.0,
                        "unit_weight": 144.0,
                        "total_weight": 1152.0,
                        "total_length": 24000,
                        "total_width": 12000,
                        "stock_due": "In Stock",
                        "remarks": "Nuclear piping flange plates",
                    }
                ],
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertIn(inward_res.status_code, [200, 201])

        product = product_details.objects.get(
            inward_slip_number="J-9991"
        )
        material_item = product_material.objects.filter(product=product).first()

        # =========================================================================
        # 5. CNC PROGRAMMER NESTING
        # =========================================================================
        prog_res = client.post(
            reverse("add_programer_Details"),
            {
                "material_id": material_item.id,
                "program_no": "PRG-LT-FLANGE-01",
                "program_date": str(today),
                "processed_quantity": 8,
                "balance_quantity": 0,
                "processed_width": 1500,
                "processed_length": 3000,
                "remaining_width": 0,
                "remaining_length": 0,
                "used_weight": 1152.0,
                "number_of_sheets": 8,
                "cut_length_per_sheet": 160.0,
                "pierce_per_sheet": 60,
                "processed_mins_per_sheet": 15.0,
                "total_planned_hours": "02:00:00",
                "total_meters": 1280.0,
                "total_piercing": 480,
                "total_used_weight": 1152.0,
                "total_no_of_sheets": 8,
                "remarks": "Nesting programmed with lead-in optimization.",
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertIn(prog_res.status_code, [200, 201])

        # =========================================================================
        # 6. BREAKDOWN & INVENTORY SPARE REPLACEMENT
        # =========================================================================
        # Machine encounters a clogged nozzle during laser piercing
        bd_res = client.post(
            reverse("add_breakdown_maintenance"),
            {
                "record_number": "BM-2026-888",
                "machine": machine.id,
                "breakdown_date": str(today),
                "shift": "Shift 1",
                "affected_equipment": "Laser Cutting Head Nozzle",
                "operator_name": "Murugan R",
                "supervisor": "sakthi_admin",
                "breakdown_type": "Nozzle Thermal Erosion & Clogging",
                "breakdown_time": "11:00:00",
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertEqual(bd_res.status_code, 201)
        bm = BreakdownMaintenance.objects.get(record_number="BM-2026-888")

        # Technician consumes 1 replacement nozzle from inventory
        usage_res = client.post(
            reverse("add_inventory_usage"),
            {
                "part": spare_part.id,
                "used_quantity": 1,
                "used_by": "Murugan R",
                "used_date": str(today),
                "use_new_quantity": False,
                "maintenance_type": "Breakdown Replacement",
            },
            format="json",
        )
        self.assertEqual(usage_res.status_code, 201)
        spare_part.refresh_from_db()
        self.assertEqual(spare_part.available_quantity, 9)

        # Complete breakdown repair
        client.put(
            reverse("update_breakdown_maintenance", kwargs={"pk": bm.id}),
            {
                "record_number": "BM-2026-888",
                "machine": machine.id,
                "breakdown_date": str(today),
                "shift": "Shift 1",
                "affected_equipment": "Laser Cutting Head Nozzle",
                "operator_name": "Murugan R",
                "supervisor": "sakthi_admin",
                "breakdown_type": "Nozzle Thermal Erosion & Clogging",
                "breakdown_time": "11:00:00",
                "maintenance_start_time": "11:10:00",
                "maintenance_complete_time": "11:35:00",
                "restart_time": "11:35:00",
                "breakdown_complete_date": str(today),
                "total_downtime_hours": 0.58,
                "parts_used": '[{"name": "High-Pressure Nitrogen Nozzle 2.0mm", "qty": 1}]',
            },
            format="json",
        )

        # =========================================================================
        # 7. QA INSPECTION
        # =========================================================================
        qa_res = client.post(
            reverse("add_qa_details"),
            {
                "material_id": material_item.id,
                "processed_date": str(today),
                "shift": "Shift 1",
                "created_by": "sakthi_admin",
                "machines_used": [
                    {
                        "machine_name": machine.machine_name,
                        "date": str(today),
                        "start_time": "11:35:00",
                        "end_time": "13:35:00",
                        "runtime": "02:00:00",
                        "operator_name": "Murugan R",
                        "gas_type": "Nitrogen",
                    }
                ],
            },
            format="json",
        )
        self.assertIn(qa_res.status_code, [200, 201])

        # =========================================================================
        # 8. ACCOUNTS BILLING & DISPATCH
        # =========================================================================
        acc_res = client.post(
            reverse("add_acc_details"),
            {
                "product_details": product.id,
                "material_details": [material_item.id],
                "invoice_no": "INV-LT-9901",
                "transporter_no": "TN-38-AB-1234",
                "payments_terms": "30 Days Credit",
                "status": "completed",
                "remarks": "Dispatched via dedicated vehicle",
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertIn(acc_res.status_code, [200, 201])

        # =========================================================================
        # 9. PERIODIC PREVENTIVE MAINTENANCE SCHEDULING
        # =========================================================================
        sched_res = client.post(
            reverse("add_maintenance_schedule"),
            {
                "machine_id": machine.id,
                "maintenance_name": "Laser Resonator Servicing",
                "maintenance_needs": "Check coolant conductivity and flush",
                "interval_days": 60,
                "last_maintenance_date": str(today - datetime.timedelta(days=60)),
                "next_maintenance_date": str(today),
                "created_by": "sakthi_admin",
            },
            format="json",
        )
        self.assertEqual(sched_res.status_code, 201)
        sched = MaintenanceSchedule.objects.get(
            maintenance_name="Laser Resonator Servicing"
        )

        # Approve Maintenance
        appr_res = client.post(
            reverse("approve_maintenance"),
            {
                "schedule_id": sched.id,
                "maintenance_name": "Laser Resonator Servicing",
                "approved_by": "sakthi_admin",
                "parts_used": [{"part_name": "Coolant Cartridge", "quantity": 1}],
                "remarks": "Flushed and refilled with deionized water.",
            },
            format="json",
        )
        self.assertEqual(appr_res.status_code, 200)
        sched.refresh_from_db()
        self.assertEqual(
            sched.next_maintenance_date, today + datetime.timedelta(days=60)
        )

        # =========================================================================
        # 10. AUDIT & REPORT GENERATION
        # =========================================================================
        # Periodic & Breakdown Maintenance Reports
        periodic_report = client.get(
            reverse("get_periodic_maintenance_reports"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(periodic_report.status_code, 200)
        self.assertGreaterEqual(len(periodic_report.data), 1)

        breakdown_report = client.get(
            reverse("get_breakdown_maintenance_reports"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(breakdown_report.status_code, 200)
        self.assertGreaterEqual(len(breakdown_report.data), 1)

        # Excel Exports (Periodic & Breakdown)
        excel_periodic = client.get(
            reverse("export_periodic_maintenance_excel"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(excel_periodic.status_code, 200)
        self.assertGreater(len(excel_periodic.content), 500)

        excel_breakdown = client.get(
            reverse("export_breakdown_maintenance_excel"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(excel_breakdown.status_code, 200)
        self.assertGreater(len(excel_breakdown.content), 500)
