from django.db import models
from django.utils import timezone
from datetime import date, timedelta

# Quotation Model
class Quotation(models.Model):
    doc_no = models.CharField(max_length=50, unique=True)
    doc_date = models.DateField(auto_now_add=False, null=True, blank=True)

    company_name = models.CharField(max_length=200, blank=True, null=True)
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    contact = models.CharField(max_length=10, blank=True, null=True)
    customer_gst_no = models.CharField(max_length=50, blank=True, null=True)

    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gst_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=55, decimal_places=2, default=0)

    extra_note = models.CharField(max_length=1000, blank=True, null=True)
    quotation_note = models.TextField(blank=True, null=True)

    # Add these new fields for terms and conditions
    payment_terms = models.CharField(max_length=200, blank=True, null=True)
    material_terms = models.CharField(max_length=200, blank=True, null=True)
    transport_terms = models.CharField(max_length=200, blank=True, null=True)
    validity_terms = models.CharField(max_length=200, blank=True, null=True)

    quote_given_by = models.CharField(max_length=200, blank=True, null=True)

    approver_name = models.CharField(max_length=200, blank=True, null=True)
    approver_designation = models.CharField(max_length=200, blank=True, null=True)
    approver_contact = models.CharField(max_length=10, blank=True, null=True)

    mode_of_submission = models.CharField(max_length=200, blank=True, null=True)
    quote_type = models.CharField(max_length=200, blank=True, null=True)
    client_remarks = models.CharField(max_length=500, blank=True, null=True)

    billed_value = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    status = models.CharField(max_length=200, default="pending")
    remarks = models.CharField(max_length=200, blank=True, null=True)

    bank_name = models.CharField(max_length=200, blank=True, null=True)
    bank_account_number = models.CharField(max_length=200, blank=True, null=True)
    bank_ifsc_code = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Quotation {self.doc_no}"


# Quotation Material Model
class QuotationItem(models.Model):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="items"
    )

    description = models.CharField(max_length=200, blank=True, null=True)
    material = models.CharField(max_length=100, blank=True, null=True)
    uom = models.CharField(max_length=20, blank=True, null=True)

    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    remarks = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Item {self.id} - {self.description}"


class QuotationNote(models.Model):
    note = models.CharField(max_length=200)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Note {self.id} - {self.note}"


class GasDetails(models.Model):
    name = models.CharField(max_length=100)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Gas {self.id} - {self.name}"


