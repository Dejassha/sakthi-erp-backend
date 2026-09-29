from django.db import models
from django.utils import timezone
from datetime import date, timedelta

from .user_models import *
from .company_models import *
from .machine_models import *
# Product Details
class product_details(models.Model):
    company_name = models.CharField(max_length=30, null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    job_type = models.CharField(max_length=20, null=True, blank=True)
    inward_slip_number = models.CharField(max_length=50, null=True, blank=True)
    sheet_type = models.CharField(max_length=20, null=True, blank=True)
    worker_no = models.CharField(max_length=50, null=True, blank=True)
    customer_name = models.CharField(max_length=30, null=True, blank=True)
    customer_dc_no = models.CharField(max_length=30, null=True, blank=True)
    contact_no = models.CharField(max_length=30, null=True, blank=True)

    programer_status = models.CharField(max_length=30, default="pending")
    qa_status = models.CharField(max_length=30, default="pending")
    outward_status = models.CharField(max_length=30, default="pending")

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["inward_slip_number"]),
            models.Index(fields=["company_name"]),
            models.Index(fields=["customer_name"]),
            models.Index(fields=["programer_status"]),
            models.Index(fields=["qa_status"]),
            models.Index(fields=["outward_status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.inward_slip_number}"

    def refresh_statuses(self):
        """Re-evaluates all department statuses based on associated materials."""
        all_materials = self.product_material_set.all()
        if not all_materials.exists():
            return

        # Explicitly evaluate each department status
        new_prog = (
            "completed"
            if all(m.programer_status == "completed" for m in all_materials)
            else "pending"
        )
        new_qa = (
            "completed"
            if all(m.qa_status == "completed" for m in all_materials)
            else "pending"
        )
        if all(m.acc_status == "cancelled" for m in all_materials):
            new_outward = "cancelled"
        elif all(m.acc_status in ["completed", "cancelled"] for m in all_materials):
            new_outward = "completed"
        else:
            new_outward = "pending"

        updated = False
        if self.programer_status != new_prog:
            self.programer_status = new_prog
            updated = True
        if self.qa_status != new_qa:
            self.qa_status = new_qa
            updated = True
        if self.outward_status != new_outward:
            self.outward_status = new_outward
            updated = True

        if updated:
            self.save(update_fields=["programer_status", "qa_status", "outward_status"])


# Product Material Details
class product_material(models.Model):
    product = models.ForeignKey(
        product_details, on_delete=models.CASCADE, null=True, blank=True
    )

    uid_no = models.CharField(max_length=50, blank=True, null=True)
    heat_no = models.CharField(max_length=50, blank=True, null=True)

    bay = models.CharField(max_length=50, blank=True, null=True)
    mat_type = models.CharField(max_length=50, blank=True, null=True)
    mat_grade = models.CharField(max_length=50, blank=True, null=True)
    thick = models.DecimalField(max_digits=15, decimal_places=3, blank=True, null=True)
    width = models.DecimalField(max_digits=15, decimal_places=3, blank=True, null=True)
    length = models.DecimalField(max_digits=15, decimal_places=3, blank=True, null=True)
    density = models.FloatField(blank=True, null=True)
    unit_weight = models.DecimalField(
        max_digits=15, decimal_places=3, blank=True, null=True
    )
    quantity = models.DecimalField(
        max_digits=15, decimal_places=3, blank=True, null=True
    )
    total_weight = models.DecimalField(
        max_digits=15, decimal_places=3, blank=True, null=True
    )
    total_length = models.DecimalField(
        max_digits=15, decimal_places=3, blank=True, null=True
    )
    total_width = models.DecimalField(
        max_digits=15, decimal_places=3, blank=True, null=True
    )
    stock_due = models.CharField(max_length=50, blank=True, null=True)

    remarks = models.TextField(blank=True, null=True)

    programer_status = models.CharField(max_length=30, default="pending")
    qa_status = models.CharField(max_length=30, default="pending")
    acc_status = models.CharField(max_length=30, default="pending")

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["mat_type"]),
            models.Index(fields=["mat_grade"]),
            models.Index(fields=["uid_no"]),
            models.Index(fields=["heat_no"]),
            models.Index(fields=["programer_status"]),
            models.Index(fields=["qa_status"]),
            models.Index(fields=["acc_status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.product.id}"

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)
        if self.product:
            self.product.refresh_statuses()


# Programer Model
class programer_details(models.Model):
    material = models.ForeignKey(
        product_material, on_delete=models.CASCADE, null=True, blank=True
    )

    program_no = models.CharField(max_length=30, null=True, blank=True)
    program_date = models.DateField(auto_now_add=False)

    processed_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    balance_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )

    processed_width = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    processed_length = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )

    remaining_width = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    remaining_length = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )

    used_weight = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    number_of_sheets = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    cut_length_per_sheet = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    pierce_per_sheet = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    processed_mins_per_sheet = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )

    total_planned_hours = models.DurationField(null=True, blank=True)
    total_meters = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    total_piercing = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    total_used_weight = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )
    total_no_of_sheets = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True
    )

    remarks = models.CharField(max_length=150, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["material"]),
            models.Index(fields=["program_no"]),
            models.Index(fields=["program_date"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.program_no} - {self.id} - {self.material.product.inward_slip_number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.material:
            return

        fields_to_check = [
            self.processed_quantity,
            self.used_weight,
            self.number_of_sheets,
            self.cut_length_per_sheet,
            self.pierce_per_sheet,
            self.processed_mins_per_sheet,
            self.total_planned_hours,
        ]

        if all(f is not None for f in fields_to_check):
            self.material.programer_status = "completed"
        else:
            self.material.programer_status = "pending"

        self.material.save(update_fields=["programer_status"])

        if self.material.product:
            self.material.product.refresh_statuses()


# QA Model
class qa_details(models.Model):
    material = models.ForeignKey(
        product_material, on_delete=models.CASCADE, null=True, blank=True
    )

    processed_date = models.DateField(auto_now_add=False, null=True, blank=True)
    shift = models.CharField(max_length=30, null=True, blank=True)

    # no_of_sheets = models.DecimalField(
    #     max_digits=15, decimal_places=3, null=True, blank=True
    # )
    # cycletime_per_sheet = models.DecimalField(
    #     max_digits=15, decimal_places=3, null=True, blank=True
    # )
    # total_cycle_time = models.DurationField(null=True, blank=True)

    remarks = models.CharField(max_length=150, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["material"]),
            models.Index(fields=["processed_date"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.processed_date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Skip status update if no material linked
        if not self.material:
            return

        # Decide QA status (Check main fields + machine logs existence)
        fields_to_check = [
            self.processed_date,
            self.shift,
            # self.no_of_sheets,
            # self.cycletime_per_sheet,
            # self.total_cycle_time,
        ]

        is_complete = (
            all(f is not None for f in fields_to_check)
            and self.qa_machine_details.exists()
        )

        # Update the material QA status
        new_status = "completed" if is_complete else "pending"

        if self.material.qa_status != new_status:
            self.material.qa_status = new_status
            self.material.save(update_fields=["qa_status"])

            # ✅ Update parent product status using centralized logic
            if self.material.product:
                self.material.product.refresh_statuses()


# QA Machine Log Model (Relational replacement for machines_used JSON)
class qa_machine_details(models.Model):
    qa = models.ForeignKey(
        qa_details, on_delete=models.CASCADE, related_name="qa_machine_details"
    )

    machine_name = models.CharField(max_length=30, null=True, blank=True)
    date = models.DateField(auto_now_add=False, null=True, blank=True)
    start_time = models.DurationField(null=True, blank=True)  # e.g. "08:00"
    end_time = models.DurationField(null=True, blank=True)
    runtime = models.DurationField(null=True, blank=True)

    operator = models.CharField(max_length=30, null=True, blank=True)

    gas_type = models.CharField(
        max_length=30, null=True, blank=True
    )  # e.g. Air, Gas, O2

    class Meta:
        indexes = [
            models.Index(fields=["qa"]),
            models.Index(fields=["machine_name"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.qa:
            self.qa.save()


# Accounts Model
class acc_details(models.Model):
    material = models.ForeignKey(
        product_material, on_delete=models.CASCADE, null=True, blank=True
    )
    invoice_no = models.CharField(max_length=30, null=True, blank=True)
    transporter_no = models.CharField(max_length=50, null=True, blank=True)
    payments_terms = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=30)
    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["material"]),
            models.Index(fields=["invoice_no"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.invoice_no} "

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.material:
            # If status is cancelled, material status is cancelled
            if self.status.lower() == "cancelled":
                self.material.acc_status = "cancelled"
            # Relaxed check: Only require invoice_no and status for completion
            elif all([self.invoice_no, self.status]):
                self.material.acc_status = "completed"
            else:
                self.material.acc_status = "pending"
            self.material.save(update_fields=["acc_status"])

            # ✅ Update parent product status using centralized logic
            if self.material.product:
                self.material.product.refresh_statuses()


