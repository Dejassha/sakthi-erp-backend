from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from api.models import (
    All_User,
    company,
    Quotation,
    QuotationItem,
    QuotationNote,
)


class QuotationModuleTests(TestCase):
    """
    Tests for Quotation Estimation, Line Items, Pricing, Terms & Notes, and Duplication.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = All_User.objects.create(username="testadmin", isAdmin=True)
        self.client.force_authenticate(user=self.user)

        self.comp = company.objects.create(
            company_name="Dynamic Fabricators Pvt Ltd",
            customer_name="Dynamic Customer",
            contact_no="9876500000",
            created_by="testadmin",
        )

    def test_quotation_notes_crud(self):
        """Quotation notes / terms & conditions master CRUD."""
        # 1. Add note
        res_note = self.client.post(
            reverse("add_quotation_note"),
            {
                "note": "50% Advance with Purchase Order, balance against delivery.",
                "created_by": "testadmin",
            },
            format="json",
        )
        self.assertEqual(res_note.status_code, 201)
        note = QuotationNote.objects.get(note__startswith="50% Advance")

        # 2. Get notes
        get_res = self.client.get(reverse("get_quotation_note"))
        self.assertEqual(get_res.status_code, 200)

        # 3. Update note
        update_res = self.client.put(
            reverse("update_quotation_note", kwargs={"pk": note.id}),
            {
                "note": "100% Payment against Delivery.",
                "created_by": "testadmin",
            },
            format="json",
        )
        self.assertEqual(update_res.status_code, 200)

        # 4. Delete note
        del_res = self.client.delete(
            reverse("delete_quotation_note", kwargs={"pk": note.id})
        )
        self.assertEqual(del_res.status_code, 200)

    def test_next_doc_number_generation(self):
        """Fetching next sequential quotation document number."""
        res = self.client.get(reverse("get_next_doc_number"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("doc_number", res.data)

    def test_quotation_full_flow(self):
        """Create quotation with line items, retrieve, edit, duplicate, and delete."""
        payload = {
            "doc_no": "QUOT-2026-0001",
            "doc_date": "2026-09-18",
            "company_name": self.comp.company_name,
            "customer_name": self.comp.customer_name,
            "contact": self.comp.contact_no,
            "email": "customer@dynamicfab.com",
            "customer_gst_no": "33ABCDE1234F1Z5",
            "net_amount": 10000.0,
            "gst_percentage": 18.0,
            "gst_amount": 1800.0,
            "total_amount": 11800.0,
            "status": "pending",
            "payment_terms": "30 Days Credit",
            "created_by": "testadmin",
            "items": [
                {
                    "description": "Laser Cutting 5mm MS Flange",
                    "material": "MS 5mm",
                    "quantity": 50,
                    "uom": "Nos",
                    "unit_rate": 200.0,
                    "total_amount": 10000.0,
                }
            ],
        }

        # 1. Create Quotation
        res_create = self.client.post(
            reverse("add_quotation"), payload, format="json"
        )
        self.assertEqual(res_create.status_code, 201)
        quotation = Quotation.objects.get(doc_no="QUOT-2026-0001")
        self.assertEqual(float(quotation.total_amount), 11800.0)

        # 2. Get Quotation List & Details
        res_list = self.client.get(reverse("get_quotation_list"))
        self.assertEqual(res_list.status_code, 200)

        res_details = self.client.get(
            reverse("get_quotation_details"), {"id": quotation.id}
        )
        self.assertEqual(res_details.status_code, 200)

        # 3. Duplicate Quotation
        res_dup = self.client.post(
            reverse("duplicate_quotation"),
            {"quotation_id": quotation.id, "doc_no": "QUOT-2026-0002"},
            format="json",
        )
        self.assertEqual(res_dup.status_code, 201)
        self.assertTrue(Quotation.objects.filter(doc_no="QUOT-2026-0002").exists())

        # 4. Delete Quotation
        res_del = self.client.delete(
            reverse("delete_quotation", kwargs={"quotation_id": quotation.id})
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertFalse(Quotation.objects.filter(id=quotation.id).exists())
