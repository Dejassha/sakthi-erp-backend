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
)


class MachineAndMaintenanceModuleTests(TestCase):
    """
    Tests for Machines, Periodic Maintenance schedules & approvals, Breakdown records, and History.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = All_User.objects.create(username="testadmin", isAdmin=True)
        self.client.force_authenticate(user=self.user)
        self.today = timezone.now().date()

        self.machine = Machine.objects.create(
            machine_name="Fiber Laser 6kW", does_need_gas=True, created_by="Admin"
        )

    def test_machine_crud_and_duplicate_handling(self):
        """Creating machines, checking unique constraints via API, updating and deleting."""
        # 1. Create duplicate name via API returns 400
        res_dup = self.client.post(
            reverse("add_machine"),
            {
                "machine_name": "Fiber Laser 6kW",
                "does_need_gas": True,
                "created_by": "Admin",
            },
            format="json",
        )
        self.assertEqual(res_dup.status_code, 400)

        # 2. Create new unique machine
        res_create = self.client.post(
            reverse("add_machine"),
            {
                "machine_name": "CNC Press Brake 150T",
                "does_need_gas": False,
                "created_by": "Admin",
            },
            format="json",
        )
        self.assertEqual(res_create.status_code, 201)
        pb = Machine.objects.get(machine_name="CNC Press Brake 150T")

        # 3. Read machines
        res_get = self.client.get(reverse("get_machines"))
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(
            any(m["machine_name"] == "CNC Press Brake 150T" for m in res_get.data)
        )

        # 4. Update machine
        res_update = self.client.put(
            reverse("update_machine", kwargs={"id": pb.id}),
            {
                "machine_name": "CNC Press Brake 150T (Amada)",
                "does_need_gas": False,
            },
            format="json",
        )
        self.assertEqual(res_update.status_code, 200)
        pb.refresh_from_db()
        self.assertEqual(pb.machine_name, "CNC Press Brake 150T (Amada)")

        # 5. Delete machine
        res_del = self.client.delete(
            reverse("delete_machine", kwargs={"id": pb.id})
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertFalse(Machine.objects.filter(id=pb.id).exists())

    def test_periodic_maintenance_lifecycle(self):
        """Create schedule, approve maintenance, roll next date, check history log."""
        # 1. Add periodic schedule
        res_add = self.client.post(
            reverse("add_maintenance_schedule"),
            {
                "machine_id": self.machine.id,
                "maintenance_name": "Laser Chiller Water Filter Replacement",
                "maintenance_needs": "Replace 5-micron deionized filter",
                "interval_days": 30,
                "last_maintenance_date": str(self.today - datetime.timedelta(days=30)),
                "next_maintenance_date": str(self.today),
                "created_by": "MaintLead",
            },
            format="json",
        )
        self.assertEqual(res_add.status_code, 201)
        schedule = MaintenanceSchedule.objects.get(
            maintenance_name="Laser Chiller Water Filter Replacement"
        )

        # 2. Approve / Complete Maintenance
        res_approve = self.client.post(
            reverse("approve_maintenance"),
            {
                "schedule_id": schedule.id,
                "maintenance_name": "Laser Chiller Water Filter Replacement",
                "approved_by": "testadmin",
                "parts_used": [{"part_name": "Deionizing Filter Cartridge", "quantity": 1}],
                "remarks": "Completed successfully with genuine replacement parts.",
            },
            format="json",
        )
        self.assertEqual(res_approve.status_code, 200)

        # Verify next maintenance date moved forward by interval_days (30 days)
        schedule.refresh_from_db()
        self.assertEqual(
            schedule.next_maintenance_date, self.today + datetime.timedelta(days=30)
        )

        # Verify MachineMaintenanceLog was created
        log = MachineMaintenanceLog.objects.filter(schedule=schedule, action="COMPLETED").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.approved_by, "testadmin")

    def test_breakdown_maintenance_lifecycle(self):
        """Log breakdown, update downtime and parts, complete breakdown."""
        # 1. Add breakdown
        res_add = self.client.post(
            reverse("add_breakdown_maintenance"),
            {
                "record_number": "BM-9001",
                "machine": self.machine.id,
                "breakdown_date": str(self.today),
                "shift": "Shift 1",
                "affected_equipment": "Laser Protective Window",
                "operator_name": "Ramesh K",
                "supervisor": "Suresh P",
                "breakdown_type": "Optical Lens Contamination",
                "breakdown_time": "09:30:00",
                "created_by": "Operator",
            },
            format="json",
        )
        self.assertEqual(res_add.status_code, 201)
        bm = BreakdownMaintenance.objects.get(record_number="BM-9001")
        self.assertEqual(bm.machine.id, self.machine.id)

        # 2. Update with maintenance completion and downtime
        res_update = self.client.put(
            reverse("update_breakdown_maintenance", kwargs={"pk": bm.id}),
            {
                "record_number": "BM-9001",
                "machine": self.machine.id,
                "breakdown_date": str(self.today),
                "shift": "Shift 1",
                "affected_equipment": "Laser Protective Window",
                "operator_name": "Ramesh K",
                "supervisor": "Suresh P",
                "breakdown_type": "Optical Lens Contamination",
                "breakdown_time": "09:30:00",
                "maintenance_start_time": "09:45:00",
                "maintenance_complete_time": "10:45:00",
                "restart_time": "10:45:00",
                "breakdown_complete_date": str(self.today),
                "total_downtime_hours": 1.25,
                "parts_used": '[{"name": "Cover Slide Glass", "qty": 1}]',
            },
            format="json",
        )
        self.assertEqual(res_update.status_code, 200)
        bm.refresh_from_db()
        self.assertEqual(bm.total_downtime_hours, 1.25)
        self.assertIsNotNone(bm.breakdown_complete_date)

        # 3. Fetch breakdown history
        res_history = self.client.get(reverse("get_breakdown_maintenance"))
        self.assertEqual(res_history.status_code, 200)
        self.assertTrue(
            any(b["record_number"] == "BM-9001" for b in res_history.data)
        )
