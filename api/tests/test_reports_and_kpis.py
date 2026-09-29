import datetime
from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.utils import timezone
from api.models import (
    All_User,
    Machine,
    MaintenanceSchedule,
    BreakdownMaintenance,
    MachineMaintenanceLog,
    InventoryPart,
    Quotation,
    KPIRecord,
)


class ReportsAndKPIModuleTests(TestCase):
    """
    Tests for KPI Analytics, Unified Maintenance Reports, Inventory History,
    Quotation Reports, and Excel Export endpoints.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = All_User.objects.create(username="testadmin", isAdmin=True)
        self.client.force_authenticate(user=self.user)
        self.today = timezone.now().date()

        self.machine = Machine.objects.create(
            machine_name="Trumpf TruLaser 3030", does_need_gas=True
        )

        self.schedule = MaintenanceSchedule.objects.create(
            machine=self.machine,
            maintenance_name="Optical Lens Cleaning",
            maintenance_needs="IPA Cleaning",
            interval_days=14,
            last_maintenance_date=self.today - datetime.timedelta(days=20),
            next_maintenance_date=self.today + datetime.timedelta(days=6),
            status="active",
            created_by="ADMIN",
        )

        self.breakdown = BreakdownMaintenance.objects.create(
            record_number="BM-1001",
            machine=self.machine,
            breakdown_date=self.today - datetime.timedelta(days=2),
            shift="Shift 1",
            affected_equipment="Laser Cutting Head",
            operator_name="Ramesh Kumar",
            supervisor="Admin",
            breakdown_type="Lens Thermal Breakdown",
            breakdown_time=datetime.time(9, 15),
            maintenance_start_time=datetime.time(9, 30),
            maintenance_complete_time=datetime.time(10, 15),
            restart_time=datetime.time(10, 15),
            breakdown_complete_date=self.today - datetime.timedelta(days=2),
            total_downtime_hours=1.0,
            created_by="ADMIN",
        )

    def test_maintenance_reports_and_filtering(self):
        """Dedicated endpoints for periodic and breakdown maintenance report history."""
        # Periodic report endpoint
        res_pm = self.client.get(
            reverse("get_periodic_maintenance_reports"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(res_pm.status_code, 200)
        self.assertGreaterEqual(len(res_pm.data), 1)
        self.assertTrue(all(r["type_key"] == "periodic" for r in res_pm.data))

        # Breakdown report endpoint
        res_bd = self.client.get(
            reverse("get_breakdown_maintenance_reports"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(res_bd.status_code, 200)
        self.assertGreaterEqual(len(res_bd.data), 1)
        self.assertTrue(all(r["type_key"] == "breakdown" for r in res_bd.data))

    def test_maintenance_excel_export(self):
        """Excel export generates valid .xlsx binary stream for periodic and breakdown."""
        # Dedicated periodic export
        res_periodic = self.client.get(
            reverse("export_periodic_maintenance_excel"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(res_periodic.status_code, 200)
        self.assertEqual(
            res_periodic.get("Content-Type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertGreater(len(res_periodic.content), 100)

        # Dedicated breakdown export
        res_breakdown = self.client.get(
            reverse("export_breakdown_maintenance_excel"), HTTP_HOST="127.0.0.1"
        )
        self.assertEqual(res_breakdown.status_code, 200)
        self.assertEqual(
            res_breakdown.get("Content-Type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertGreater(len(res_breakdown.content), 100)

    def test_kpi_endpoints(self):
        """KPI retrieval and default template configuration."""
        res_defaults = self.client.get(reverse("get_kpi_defaults"))
        self.assertEqual(res_defaults.status_code, 200)

        res_kpis = self.client.get(reverse("get_kpis"))
        self.assertEqual(res_kpis.status_code, 200)
