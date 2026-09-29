from django.db import models
from django.utils import timezone
from datetime import date, timedelta

from .user_models import *
from .company_models import *
from .machine_models import *


class InventoryPartName(models.Model):
    part_name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.part_name


class InventoryPurpose(models.Model):
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.name


class InventoryPart(models.Model):
    spare_id = models.CharField(max_length=50, blank=True, null=True)
    item_code = models.CharField(max_length=50, blank=True, null=True)
    part_name = models.CharField(max_length=120)
    batch_number = models.CharField(max_length=80, blank=True, null=True, default="")
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_parts")
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=30, default="pcs")
    purchase_date = models.DateField(null=True, blank=True)
    bought_from = models.CharField(max_length=120, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=30, default="in_stock")
    created_by = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.part_name} ({self.batch_number})" if self.batch_number else self.part_name

    def sync_status(self):
        if self.available_quantity <= 0:
            self.status = "out_of_stock"
        elif self.min_stock_quantity is not None and self.min_stock_quantity > 0:
            if self.available_quantity <= self.min_stock_quantity:
                self.status = "low_stock"
            else:
                self.status = "in_stock"
        elif self.available_quantity <= (self.stock_quantity / 2):
            self.status = "low_stock"
        else:
            self.status = "in_stock"
        return self.status

    class Meta:
        indexes = [
            models.Index(fields=["part_name"]),
            models.Index(fields=["batch_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["machine"]),
            models.Index(fields=["-created_at"]),
        ]


class InventoryUsage(models.Model):
    part = models.ForeignKey(InventoryPart, on_delete=models.SET_NULL, null=True, blank=True, related_name="usage_history")
    batch_number = models.CharField(max_length=80, blank=True, null=True, default="")
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_usage")
    machine_name = models.CharField(max_length=120, blank=True)
    used_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_by = models.CharField(max_length=120, blank=True)
    used_hours = models.CharField(max_length=40, blank=True)
    used_date = models.DateField(default=timezone.localdate)
    remaining_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)
    use_new_quantity = models.BooleanField(default=False)
    created_by = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        part_label = self.part.part_name if self.part else (self.batch_number or "Inventory Part")
        return f"{part_label} used on {self.used_date}"

    class Meta:
        indexes = [
            models.Index(fields=["part"]),
            models.Index(fields=["batch_number"]),
            models.Index(fields=["machine"]),
            models.Index(fields=["-used_date"]),
        ]


class PendingMaterial(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ordered", "Ordered"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    part_name = models.CharField(max_length=120)
    requested_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    requested_by = models.CharField(max_length=120, blank=True)
    request_date = models.DateField(default=timezone.now)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.part_name} - {self.status}"

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["-request_date"]),
        ]


class InventoryHistory(models.Model):
    part = models.ForeignKey(InventoryPart, on_delete=models.SET_NULL, null=True, blank=True, related_name="history")
    part_name = models.CharField(max_length=120)
    batch_number = models.CharField(max_length=80, blank=True, null=True, default="")
    action = models.CharField(max_length=30)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    machine_name = models.CharField(max_length=120, blank=True)
    user = models.CharField(max_length=120, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.part_name} - {self.action}"

    class Meta:
        indexes = [
            models.Index(fields=["part_name"]),
            models.Index(fields=["action"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["part"]),
        ]


class InventoryRateHistory(models.Model):
    part = models.ForeignKey(InventoryPart, on_delete=models.CASCADE, related_name="rates")
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.part.part_name} - ₹{self.rate}"

    class Meta:
        indexes = [
            models.Index(fields=["part", "-created_at"]),
        ]


