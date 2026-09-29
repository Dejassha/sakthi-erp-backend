# Generated for BreakdownMaintenanceLog

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0045_maintenanceschedule_remind_before_days'),
    ]

    operations = [
        migrations.CreateModel(
            name='BreakdownMaintenanceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('record_number', models.CharField(blank=True, max_length=50, null=True)),
                ('action', models.CharField(default='CREATED', max_length=50)),
                ('breakdown_type', models.CharField(blank=True, max_length=100, null=True)),
                ('affected_equipment', models.CharField(blank=True, max_length=120, null=True)),
                ('shift', models.CharField(blank=True, max_length=50, null=True)),
                ('breakdown_date', models.DateField(blank=True, null=True)),
                ('breakdown_time', models.TimeField(blank=True, null=True)),
                ('maintenance_start_time', models.TimeField(blank=True, null=True)),
                ('maintenance_complete_time', models.TimeField(blank=True, null=True)),
                ('restart_time', models.TimeField(blank=True, null=True)),
                ('breakdown_complete_date', models.DateField(blank=True, null=True)),
                ('total_downtime_hours', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('operator_name', models.CharField(blank=True, max_length=100, null=True)),
                ('supervisor', models.CharField(blank=True, max_length=100, null=True)),
                ('performed_by', models.CharField(blank=True, max_length=100, null=True)),
                ('status', models.CharField(default='OPEN', max_length=50)),
                ('action_details', models.TextField(blank=True, null=True)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('breakdown', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='logs', to='api.breakdownmaintenance')),
                ('machine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='breakdown_logs', to='api.machine')),
            ],
        ),
    ]
