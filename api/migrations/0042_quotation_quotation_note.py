from django.db import migrations, models
from django.db.models import Q


def populate_existing_quotation_notes(apps, schema_editor):
    Quotation = apps.get_model('api', 'Quotation')
    QuotationNote = apps.get_model('api', 'QuotationNote')

    latest_note = QuotationNote.objects.order_by('-created_at').first()
    if latest_note and latest_note.note:
        default_note_text = latest_note.note
        Quotation.objects.filter(
            Q(quotation_note__isnull=True) | Q(quotation_note='')
        ).update(quotation_note=default_note_text)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0041_acc_details_api_acc_det_materia_06683f_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='quotation_note',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(
            populate_existing_quotation_notes,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
