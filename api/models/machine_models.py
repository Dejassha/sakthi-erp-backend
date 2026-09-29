from django.db import models
from django.utils import timezone
from datetime import date, timedelta

from .user_models import *
from .company_models import *
# Machine
class Machine(models.Model):
    machine_name = models.CharField(max_length=50)
    does_need_gas = models.BooleanField(default=False)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"{self.machine_name} -- {self.id}"


class MaintenanceSchedule(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="maintenance_schedules")
    maintenance_name = models.CharField(max_length=100)
    maintenance_needs = models.TextField(null=True, blank=True)
    interval_days = models.IntegerField(help_text="Maintenance cycle in days")
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_date = models.DateField()
    remind_before_days = models.IntegerField(default=3, help_text="Days before due date to start reminding")
    supervised_by = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default="active")
    created_by = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["next_maintenance_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["machine", "status"]),
        ]

    def __str__(self):
        return f"{self.machine.machine_name} - {self.maintenance_name}"

    def remaining_days(self):
        today = timezone.now().date()
        delta = (self.next_maintenance_date - today).days
        remind_days = self.remind_before_days if self.remind_before_days is not None else 3
        if delta < 0:
            abs_delta = abs(delta)
            return {
                "value": delta,
                "display": f"Overdue by {abs_delta} Day{'s' if abs_delta != 1 else ''}",
                "status": "overdue",
            }
        elif delta == 0:
            return {"value": 0, "display": "Due Today", "status": "due"}
        elif delta <= remind_days:
            return {
                "value": delta,
                "display": f"{delta} Day{'s' if delta != 1 else ''}",
                "status": "remind",
            }
        else:
            return {
                "value": delta,
                "display": f"{delta} Days",
                "status": "safe",
            }


class MachineMaintenanceLog(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="maintenance_logs")
    schedule = models.ForeignKey(MaintenanceSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    maintenance_name = models.CharField(max_length=100)
    action = models.CharField(max_length=50, default="COMPLETED")  # CREATED, UPDATED, COMPLETED
    scheduled_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(default=date.today)
    status = models.CharField(max_length=20, default="approved")
    approved_by = models.CharField(max_length=50, null=True, blank=True)
    performed_by = models.CharField(max_length=50, null=True, blank=True)
    supervised_by = models.CharField(max_length=100, null=True, blank=True)
    parts_used = models.TextField(blank=True, null=True)
    action_details = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["machine", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.machine.machine_name} - {self.maintenance_name} - {self.action} ({self.created_at})"


class BreakdownMaintenance(models.Model):
    record_number = models.CharField(max_length=50, blank=True, null=True)
    breakdown_date = models.DateField(blank=True, null=True)
    shift = models.CharField(max_length=50, blank=True, null=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="breakdown_records",
    )
    affected_equipment = models.CharField(max_length=120, blank=True, null=True)
    operator_name = models.CharField(max_length=100, blank=True, null=True)
    supervisor = models.CharField(max_length=100, blank=True, null=True)
    breakdown_time = models.TimeField(blank=True, null=True)
    breakdown_type = models.CharField(max_length=100, blank=True, null=True)
    maintenance_start_time = models.TimeField(blank=True, null=True)
    maintenance_complete_time = models.TimeField(blank=True, null=True)
    restart_time = models.TimeField(blank=True, null=True)
    breakdown_complete_date = models.DateField(blank=True, null=True)
    total_downtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_by = models.CharField(max_length=50, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["breakdown_date"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["machine", "-created_at"]),
        ]

    def __str__(self):
        machine_label = self.machine.machine_name if self.machine else "Unknown"
        return f"{self.record_number or self.id} - {machine_label}"


class BreakdownMaintenanceLog(models.Model):
    machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="breakdown_logs",
    )
    breakdown = models.ForeignKey(
        BreakdownMaintenance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    record_number = models.CharField(max_length=50, blank=True, null=True)
    action = models.CharField(max_length=50, default="CREATED")  # CREATED, UPDATED, EDITED, DELETED
    breakdown_type = models.CharField(max_length=100, blank=True, null=True)
    affected_equipment = models.CharField(max_length=120, blank=True, null=True)
    shift = models.CharField(max_length=50, blank=True, null=True)
    breakdown_date = models.DateField(null=True, blank=True)
    breakdown_time = models.TimeField(null=True, blank=True)
    maintenance_start_time = models.TimeField(null=True, blank=True)
    maintenance_complete_time = models.TimeField(null=True, blank=True)
    restart_time = models.TimeField(null=True, blank=True)
    breakdown_complete_date = models.DateField(null=True, blank=True)
    total_downtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    operator_name = models.CharField(max_length=100, null=True, blank=True)
    supervisor = models.CharField(max_length=100, null=True, blank=True)
    performed_by = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50, default="OPEN")
    action_details = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["machine", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.record_number} - {self.action} ({self.created_at})"


