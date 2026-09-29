from django.db import models
from django.utils import timezone
from datetime import date, timedelta

class KPIRecord(models.Model):
    group_id = models.CharField(max_length=50, default="1")
    month = models.CharField(max_length=20) # Format: YYYY-MM or YYYY-Www or YYYY
    s_no = models.IntegerField(default=1)
    kpi_category = models.CharField(max_length=100, default="Production")
    kpi_parameter = models.CharField(max_length=100, default="Machine Utilization")
    formula = models.CharField(max_length=200, default="Planned Hours / Runtime (HH:MM) * 100")
    target = models.CharField(max_length=50, null=True, blank=True, default="85-90%")
    achieved = models.CharField(max_length=50, null=True, blank=True)
    frequency = models.CharField(max_length=50, default="Monthly")
    responsible = models.CharField(max_length=100, null=True, blank=True, default="Production")
    remarks = models.TextField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('group_id', 'month', 's_no')

    def __str__(self):
        return f"{self.group_id} - {self.month} - {self.s_no} - {self.kpi_parameter}"


class KPITemplate(models.Model):
    group_id = models.CharField(max_length=50, default="1")
    name = models.CharField(max_length=200, null=True, blank=True, default="")
    s_no = models.IntegerField(default=1)
    kpi_category = models.CharField(max_length=100, default="Production")
    kpi_parameter = models.CharField(max_length=100, default="Machine Utilization")
    formula = models.CharField(max_length=200, default="Planned Hours / Runtime (HH:MM) * 100")
    target = models.CharField(max_length=50, null=True, blank=True, default="85-90%")
    frequency = models.CharField(max_length=50, default="Monthly")
    responsible = models.CharField(max_length=100, null=True, blank=True, default="Production")
    achieved = models.CharField(max_length=50, null=True, blank=True, default="")
    remarks = models.TextField(null=True, blank=True, default="")
    created_by = models.CharField(max_length=100, null=True, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'kpi_template'
        unique_together = ('group_id', 's_no')
        ordering = ['group_id', 's_no']

    def __str__(self):
        return f"{self.group_id} - {self.s_no} - {self.kpi_parameter}"


