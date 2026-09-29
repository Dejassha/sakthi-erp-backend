from django.db import models
from django.utils import timezone
from datetime import date, timedelta

# Company
class company(models.Model):
    company_name = models.CharField(max_length=30, null=True, blank=True)
    customer_name = models.CharField(max_length=30, null=True, blank=True)
    contact_no = models.CharField(max_length=15, null=True, blank=True)

    created_by = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.company_name} -{self.contact_no}--{self.id}"


# Machine Operator
class machine_operator(models.Model):
    operator_name = models.CharField(max_length=30, null=True, blank=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.operator_name} -- {self.id} "


# Material Type
class material_type(models.Model):
    material_name = models.CharField(max_length=10, unique=True)
    density_value = models.FloatField(null=True, blank=True)

    created_by = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.material_name} - {self.density_value}"


