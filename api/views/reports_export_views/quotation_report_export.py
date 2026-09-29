import io
import datetime
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from rest_framework.decorators import api_view
from rest_framework.response import Response
import xlsxwriter

from api.models import Quotation


def _compute_quotation_reports_data():
    qs = Quotation.objects.all()

    total_quotes = qs.count()
    total_value = qs.aggregate(total=Sum("total_amount"))["total"] or 0

    new_clients_value = (
        qs.aggregate(
            total=Sum(
                "billed_value", filter=Q(status__iexact="won", quote_type__iexact="new")
            )
        )["total"]
        or 0
    )

    existing_clients_value = (
        qs.aggregate(
            total=Sum(
                "billed_value",
                filter=Q(status__iexact="won", quote_type__iexact="existing"),
            )
        )["total"]
        or 0
    )

    pending_quote_value = (
        qs.aggregate(total=Sum("total_amount", filter=Q(status__iexact="pending")))[
            "total"
        ]
        or 0
    )

    won_quote_value = (
        qs.aggregate(total=Sum("total_amount", filter=Q(status__iexact="won")))["total"]
        or 0
    )

    lost_quote_value = (
        qs.aggregate(total=Sum("total_amount", filter=Q(status__iexact="lost")))[
            "total"
        ]
        or 0
    )

    orders_won = qs.filter(status__iexact="won").count()
    orders_new_clients = qs.filter(
        status__iexact="won", quote_type__iexact="new"
    ).count()
    orders_existing_clients = qs.filter(
        status__iexact="won", quote_type__iexact="existing"
    ).count()
    pending_quotes = qs.filter(status__iexact="pending").count()
    lost_quotes = qs.filter(status__iexact="lost").count()

    top_companies = (
        qs.exclude(company_name__isnull=True)
        .exclude(company_name="")
        .values("company_name")
        .annotate(total_value=Sum("total_amount"))
        .order_by("-total_value")[:3]
    )

    top_company_names = [
        {
            "company_name": row["company_name"],
            "value": float(row["total_value"] or 0),
        }
        for row in top_companies
    ]

    cumulative = [
        {
            "label": "Quotations Sent",
            "count": total_quotes,
            "value": float(total_value),
        },
        {
            "label": "Orders from New Clients",
            "count": orders_new_clients,
            "value": float(new_clients_value),
        },
        {
            "label": "Repeat Orders from Existing Clients",
            "count": orders_existing_clients,
            "value": float(existing_clients_value),
        },
        {
            "label": "Quotations in Tracking",
            "count": pending_quotes,
            "value": float(pending_quote_value),
        },
        {
            "label": "Orders Won / Conversion Rate",
            "count": orders_won,
            "value": float(won_quote_value),
        },
        {
            "label": "Orders Lost / Conversion Rate",
            "count": lost_quotes,
            "value": float(lost_quote_value),
        },
        {
            "label": "Major Clients Approached",
            "count": len(top_company_names),
            "value": top_company_names,
        },
    ]

    month_data = (
        qs.annotate(month=TruncMonth("doc_date"))
        .values("month")
        .annotate(
            quotes_sent=Count("id"),
            orders_won=Count("id", filter=Q(status__iexact="won")),
            lost_quotes=Count("id", filter=Q(status__iexact="lost")),
            pending=Count("id", filter=Q(status__iexact="pending")),
            quote_value=Sum("total_amount"),
            billed_value=Sum("billed_value", filter=Q(status__iexact="won")),
        )
        .order_by("month")
    )

    monthly = []
    for row in month_data:
        conversion = (
            (row["orders_won"] / row["quotes_sent"]) * 100
            if row["quotes_sent"] > 0
            else 0
        )

        monthly.append(
            {
                "month": row["month"].strftime("%b-%y") if row["month"] else "-",
                "quotes_sent": row["quotes_sent"],
                "orders_received": row["orders_won"],
                "lost_quotations": row["lost_quotes"],
                "pending": row["pending"],
                "conversion": round(conversion, 2),
                "quote_value": float(row["quote_value"] or 0),
                "billed_value": float(row["billed_value"] or 0),
            }
        )

    return {"cumulative": cumulative, "monthly": monthly}


@api_view(["GET"])
def get_quotation_reports(request):
    data = _compute_quotation_reports_data()
    return Response(data)


@api_view(["GET", "POST"])
def export_quotation_reports_excel(request):
    data = _compute_quotation_reports_data()
    cumulative = data.get("cumulative", [])
    monthly = data.get("monthly", [])

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("Cumulative Quotation Report")

    # Ensure gridlines are visible
    worksheet.hide_gridlines(0)

    # -----------------------------
    # STYLES & DESIGN SYSTEM TOKENS
    # -----------------------------
    title_fmt = workbook.add_format({
        "bold": True,
        "font_size": 14,
        "font_color": "#FFFFFF",
        "bg_color": "#0F172A",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#0F172A",
    })

    subtitle_fmt = workbook.add_format({
        "font_size": 9,
        "italic": True,
        "font_color": "#94A3B8",
        "bg_color": "#0F172A",
        "align": "center",
        "valign": "vcenter",
    })

    section_header_fmt = workbook.add_format({
        "bold": True,
        "font_size": 11,
        "font_color": "#FFFFFF",
        "bg_color": "#1E3A8A",
        "align": "left",
        "valign": "vcenter",
        "left": 1,
        "right": 1,
        "top": 1,
        "bottom": 1,
        "border_color": "#1E3A8A",
    })

    col_header_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#1E293B",
        "bg_color": "#E2E8F0",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#CBD5E1",
    })

    col_header_left_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#1E293B",
        "bg_color": "#E2E8F0",
        "align": "left",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#CBD5E1",
    })

    cell_text_fmt = workbook.add_format({
        "font_size": 10,
        "font_color": "#1E293B",
        "align": "left",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E2E8F0",
    })

    cell_center_fmt = workbook.add_format({
        "font_size": 10,
        "font_color": "#1E293B",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E2E8F0",
    })

    cell_bold_center_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#0F172A",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E2E8F0",
    })

    cell_currency_fmt = workbook.add_format({
        "font_size": 10,
        "font_color": "#0F172A",
        "num_format": "[$₹-4009] #,##0.00",
        "align": "right",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E2E8F0",
    })

    cell_bold_currency_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#1E3A8A",
        "num_format": "[$₹-4009] #,##0.00",
        "align": "right",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E2E8F0",
    })

    cell_percent_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#047857",
        "num_format": "0.00%",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E2E8F0",
    })

    sub_item_fmt = workbook.add_format({
        "font_size": 9,
        "font_color": "#1E3A8A",
        "bg_color": "#EFF6FF",
        "align": "left",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#BFDBFE",
    })

    sub_item_currency_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#1E3A8A",
        "bg_color": "#EFF6FF",
        "num_format": "[$₹-4009] #,##0.00",
        "align": "right",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#BFDBFE",
    })

    total_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#0F172A",
        "bg_color": "#F8FAFC",
        "align": "center",
        "valign": "vcenter",
        "top": 2,
        "bottom": 6,
        "left": 1,
        "right": 1,
        "border_color": "#94A3B8",
    })

    total_currency_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#0F172A",
        "bg_color": "#F8FAFC",
        "num_format": "[$₹-4009] #,##0.00",
        "align": "right",
        "valign": "vcenter",
        "top": 2,
        "bottom": 6,
        "left": 1,
        "right": 1,
        "border_color": "#94A3B8",
    })

    # -----------------------------
    # BUILD TITLE BANNER
    # -----------------------------
    worksheet.merge_range("A1:G1", "SAKTHI LASER TECHNOLOGY - CUMULATIVE QUOTATION REPORT", title_fmt)
    worksheet.set_row(0, 24)
    worksheet.merge_range("A2:G2", f"Generated on {datetime.datetime.now().strftime('%d-%b-%Y %I:%M %p')}", subtitle_fmt)
    worksheet.set_row(1, 16)

    curr_row = 3

    # -----------------------------
    # 1. CUMULATIVE SUMMARY SECTION
    # -----------------------------
    worksheet.merge_range(curr_row, 0, curr_row, 6, "  CUMULATIVE SUMMARY", section_header_fmt)
    worksheet.set_row(curr_row, 22)
    curr_row += 1

    # Headers: A: S.No (0), B-D: Particulars (1..3 merged), E: Count (4), F-G: Value (5..6 merged)
    worksheet.write(curr_row, 0, "SL.NO", col_header_fmt)
    worksheet.merge_range(curr_row, 1, curr_row, 3, "PARTICULARS", col_header_left_fmt)
    worksheet.write(curr_row, 4, "COUNT", col_header_fmt)
    worksheet.merge_range(curr_row, 5, curr_row, 6, "VALUE (₹)", col_header_fmt)
    worksheet.set_row(curr_row, 20)
    curr_row += 1

    sno = 1
    for item in cumulative:
        val = item.get("value")
        label = item.get("label", "")
        count = item.get("count", 0)

        if isinstance(val, list):
            # Major clients approached
            worksheet.write(curr_row, 0, sno, cell_center_fmt)
            worksheet.merge_range(curr_row, 1, curr_row, 3, label, cell_text_fmt)
            worksheet.write(curr_row, 4, count, cell_bold_center_fmt)
            worksheet.merge_range(curr_row, 5, curr_row, 6, f"Top {len(val)} Clients", cell_center_fmt)
            worksheet.set_row(curr_row, 20)
            curr_row += 1

            # Sub-rows for each major client
            for client in val:
                worksheet.write(curr_row, 0, "", cell_center_fmt)
                worksheet.merge_range(curr_row, 1, curr_row, 3, f"  ↳  {client.get('company_name', '-')}", sub_item_fmt)
                worksheet.write(curr_row, 4, "-", cell_center_fmt)
                worksheet.merge_range(curr_row, 5, curr_row, 6, float(client.get("value", 0)), sub_item_currency_fmt)
                worksheet.set_row(curr_row, 18)
                curr_row += 1
        else:
            worksheet.write(curr_row, 0, sno, cell_center_fmt)
            worksheet.merge_range(curr_row, 1, curr_row, 3, label, cell_text_fmt)
            worksheet.write(curr_row, 4, count, cell_bold_center_fmt)
            worksheet.merge_range(curr_row, 5, curr_row, 6, float(val or 0), cell_bold_currency_fmt)
            worksheet.set_row(curr_row, 20)
            curr_row += 1

        sno += 1

    curr_row += 1  # Spacer row

    # -----------------------------
    # 2. MONTH-WISE STATISTICS SECTION
    # -----------------------------
    worksheet.merge_range(curr_row, 0, curr_row, 6, "  MONTH WISE STATISTICS", section_header_fmt)
    worksheet.set_row(curr_row, 22)
    curr_row += 1

    m_headers = [
        ("MONTH/YEAR", col_header_fmt),
        ("QUOTES SENT", col_header_fmt),
        ("ORDERS RECEIVED", col_header_fmt),
        ("LOST QUOTES", col_header_fmt),
        ("CONVERSION %", col_header_fmt),
        ("QUOTE VALUE (₹)", col_header_fmt),
        ("BILLED VALUE (₹)", col_header_fmt),
    ]

    for col_idx, (h_text, h_fmt) in enumerate(m_headers):
        worksheet.write(curr_row, col_idx, h_text, h_fmt)
    worksheet.set_row(curr_row, 20)
    curr_row += 1

    start_m_row = curr_row + 1  # 1-based index for Excel formulas

    for m_item in monthly:
        worksheet.write(curr_row, 0, m_item.get("month", "-"), cell_bold_center_fmt)
        worksheet.write(curr_row, 1, m_item.get("quotes_sent", 0), cell_center_fmt)
        worksheet.write(curr_row, 2, m_item.get("orders_received", 0), cell_center_fmt)
        worksheet.write(curr_row, 3, m_item.get("lost_quotations", 0), cell_center_fmt)
        worksheet.write(curr_row, 4, float(m_item.get("conversion", 0)) / 100.0, cell_percent_fmt)
        worksheet.write(curr_row, 5, float(m_item.get("quote_value", 0)), cell_currency_fmt)
        worksheet.write(curr_row, 6, float(m_item.get("billed_value", 0)), cell_bold_currency_fmt)
        worksheet.set_row(curr_row, 20)
        curr_row += 1

    end_m_row = curr_row  # 1-based index of last data row

    # Summary Row for Monthly Statistics
    if len(monthly) > 0:
        worksheet.write(curr_row, 0, "TOTAL", total_fmt)
        worksheet.write_formula(curr_row, 1, f"=SUM(B{start_m_row}:B{end_m_row})", total_fmt)
        worksheet.write_formula(curr_row, 2, f"=SUM(C{start_m_row}:C{end_m_row})", total_fmt)
        worksheet.write_formula(curr_row, 3, f"=SUM(D{start_m_row}:D{end_m_row})", total_fmt)
        worksheet.write_formula(curr_row, 4, f"=IF(B{curr_row+1}>0, C{curr_row+1}/B{curr_row+1}, 0)", cell_percent_fmt)
        worksheet.write_formula(curr_row, 5, f"=SUM(F{start_m_row}:F{end_m_row})", total_currency_fmt)
        worksheet.write_formula(curr_row, 6, f"=SUM(G{start_m_row}:G{end_m_row})", total_currency_fmt)
        worksheet.set_row(curr_row, 22)

    # Column Widths Setup
    worksheet.set_column(0, 0, 16)  # Month / S.No
    worksheet.set_column(1, 1, 18)  # Quotes Sent / Particulars
    worksheet.set_column(2, 2, 20)  # Orders Received
    worksheet.set_column(3, 3, 16)  # Lost Quotes
    worksheet.set_column(4, 4, 18)  # Conversion % / Count
    worksheet.set_column(5, 5, 24)  # Quote Value
    worksheet.set_column(6, 6, 24)  # Billed Value

    workbook.close()
    output.seek(0)

    filename = f"Cumulative_Quotation_Report_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
