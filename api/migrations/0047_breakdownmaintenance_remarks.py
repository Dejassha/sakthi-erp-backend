# Generated for BreakdownMaintenance remarks field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0046_breakdownmaintenancelog'),
    ]

    operations = [
        migrations.AddField(
            model_name='breakdownmaintenance',
            name='remarks',
            field=models.TextField(blank=True, null=True),
        ),
    ]
