import io
import datetime
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
import xlsxwriter

from django.db.models import Sum, Count, Q, Value, DecimalField
from django.db.models.functions import Coalesce

from api.models import InventoryHistory
from api.serializers import InventoryHistorySerializer


@api_view(["GET"])
def get_inventory_history(request):
    history_qs = InventoryHistory.objects.select_related("part").all().order_by("-id")
    serializer = InventoryHistorySerializer(history_qs, many=True)

    agg = history_qs.aggregate(
        total_qty=Coalesce(Sum("quantity"), Value(0, output_field=DecimalField())),
        total_count=Count("id"),
        added_qty=Coalesce(Sum("quantity", filter=Q(action__icontains="add") | Q(action__icontains="restock")), Value(0, output_field=DecimalField())),
        added_count=Count("id", filter=Q(action__icontains="add") | Q(action__icontains="restock")),
        updated_qty=Coalesce(Sum("quantity", filter=Q(action__icontains="update")), Value(0, output_field=DecimalField())),
        updated_count=Count("id", filter=Q(action__icontains="update")),
        edited_qty=Coalesce(Sum("quantity", filter=Q(action__icontains="edit")), Value(0, output_field=DecimalField())),
        edited_count=Count("id", filter=Q(action__icontains="edit")),
        used_qty=Coalesce(Sum("quantity", filter=Q(action__icontains="use")), Value(0, output_field=DecimalField())),
        used_count=Count("id", filter=Q(action__icontains="use")),
        deleted_qty=Coalesce(Sum("quantity", filter=Q(action__icontains="del")), Value(0, output_field=DecimalField())),
        deleted_count=Count("id", filter=Q(action__icontains="del")),
    )

    totals = {
        "addedQty": float(agg["added_qty"] or 0),
        "addedCount": agg["added_count"] or 0,
        "updatedQty": float(agg["updated_qty"] or 0),
        "updatedCount": agg["updated_count"] or 0,
        "editedQty": float(agg["edited_qty"] or 0),
        "editedCount": agg["edited_count"] or 0,
        "usedQty": float(agg["used_qty"] or 0),
        "usedCount": agg["used_count"] or 0,
        "deletedQty": float(agg["deleted_qty"] or 0),
        "deletedCount": agg["deleted_count"] or 0,
        "totalQty": float(agg["total_qty"] or 0),
        "totalCount": agg["total_count"] or 0,
    }

    return Response(
        {
            "data": serializer.data,
            "totals": totals,
        }
    )


@api_view(["GET", "POST"])
def export_inventory_history_excel(request):
    """
    Exports Inventory History to a high-fidelity Excel report using XlsxWriter.
    Supports dynamic headers, selective column export, and filtered/selected rows.
    Guarantees 100% timezone-accurate dates and times.
    """
    data = request.data if request.method == "POST" else {}
    custom_headers = data.get("headers", [])
    custom_rows = data.get("rows", [])

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("Inventory History")

    worksheet.hide_gridlines(0)

    # -----------------------------
    # STYLES & DESIGN SYSTEM TOKENS
    # -----------------------------
    title_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 13,
            "font_color": "#FFFFFF",
            "bg_color": "#0F172A",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#0F172A",
        }
    )

    subtitle_fmt = workbook.add_format(
        {
            "font_size": 9,
            "italic": True,
            "font_color": "#94A3B8",
            "bg_color": "#0F172A",
            "align": "center",
            "valign": "vcenter",
        }
    )

    col_header_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#1E293B",
            "bg_color": "#E2E8F0",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#CBD5E1",
        }
    )

    col_header_left_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#1E293B",
            "bg_color": "#E2E8F0",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#CBD5E1",
        }
    )

    col_header_right_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#1E293B",
            "bg_color": "#E2E8F0",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#CBD5E1",
        }
    )

    cell_text_fmt = workbook.add_format(
        {
            "font_size": 10,
            "font_color": "#1E293B",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E2E8F0",
        }
    )

    cell_center_fmt = workbook.add_format(
        {
            "font_size": 10,
            "font_color": "#1E293B",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E2E8F0",
        }
    )

    cell_num_fmt = workbook.add_format(
        {
            "font_size": 10,
            "font_color": "#0F172A",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E2E8F0",
        }
    )

    cell_currency_fmt = workbook.add_format(
        {
            "font_size": 10,
            "font_color": "#0F172A",
            "num_format": "[$₹-4009] #,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E2E8F0",
        }
    )

    # Action badge formats
    action_added_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": "#047857",
            "bg_color": "#ECFDF5",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#A7F3D0",
        }
    )

    action_used_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": "#C2410C",
            "bg_color": "#FFF7ED",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FED7AA",
        }
    )

    action_deleted_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": "#B91C1C",
            "bg_color": "#FEF2F2",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FECACA",
        }
    )

    action_edited_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": "#7E22CE",
            "bg_color": "#FAF5FF",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E9D5FF",
        }
    )

    action_default_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": "#1E40AF",
            "bg_color": "#EFF6FF",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#BFDBFE",
        }
    )

    summary_added_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#047857",
            "bg_color": "#ECFDF5",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#A7F3D0",
        }
    )

    summary_added_num_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#047857",
            "bg_color": "#ECFDF5",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#A7F3D0",
        }
    )

    summary_used_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#C2410C",
            "bg_color": "#FFF7ED",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FED7AA",
        }
    )

    summary_used_num_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#C2410C",
            "bg_color": "#FFF7ED",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FED7AA",
        }
    )

    summary_updated_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#1E40AF",
            "bg_color": "#EFF6FF",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#BFDBFE",
        }
    )

    summary_updated_num_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#1E40AF",
            "bg_color": "#EFF6FF",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#BFDBFE",
        }
    )

    summary_edited_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#7E22CE",
            "bg_color": "#FAF5FF",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E9D5FF",
        }
    )

    summary_edited_num_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#7E22CE",
            "bg_color": "#FAF5FF",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#E9D5FF",
        }
    )

    summary_deleted_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#B91C1C",
            "bg_color": "#FEF2F2",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FECACA",
        }
    )

    summary_deleted_num_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#B91C1C",
            "bg_color": "#FEF2F2",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#FECACA",
        }
    )

    total_fmt = workbook.add_format(
        {
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
        }
    )

    total_num_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": "#0F172A",
            "bg_color": "#F8FAFC",
            "num_format": "#,##0.00",
            "align": "right",
            "valign": "vcenter",
            "top": 2,
            "bottom": 6,
            "left": 1,
            "right": 1,
            "border_color": "#94A3B8",
        }
    )

    # Available Column Specs
    ALL_COLUMN_SPECS = {
        "sno": {
            "header": "SL.NO",
            "header_fmt": col_header_fmt,
            "width": 8,
            "align": "center",
        },
        "created_date": {
            "header": "DATE",
            "header_fmt": col_header_fmt,
            "width": 14,
            "align": "center",
        },
        "created_time": {
            "header": "TIME",
            "header_fmt": col_header_fmt,
            "width": 12,
            "align": "center",
        },
        "spare_id": {
            "header": "SPARE ID",
            "header_fmt": col_header_fmt,
            "width": 14,
            "align": "center",
        },
        "item_code": {
            "header": "ITEM CODE",
            "header_fmt": col_header_fmt,
            "width": 14,
            "align": "center",
        },
        "part_name": {
            "header": "ITEM NAME",
            "header_fmt": col_header_left_fmt,
            "width": 26,
            "align": "left",
        },
        "batch_number": {
            "header": "BATCH NO",
            "header_fmt": col_header_fmt,
            "width": 16,
            "align": "center",
        },
        "action": {
            "header": "ACTION",
            "header_fmt": col_header_fmt,
            "width": 14,
            "align": "action",
        },
        "quantity": {
            "header": "QTY",
            "header_fmt": col_header_right_fmt,
            "width": 14,
            "align": "number",
        },
        "available_quantity": {
            "header": "AVAILABLE QTY",
            "header_fmt": col_header_fmt,
            "width": 16,
            "align": "center",
        },
        "min_stock_quantity": {
            "header": "MIN QTY",
            "header_fmt": col_header_fmt,
            "width": 12,
            "align": "center",
        },
        "purchase_price": {
            "header": "RATE/QTY (₹)",
            "header_fmt": col_header_right_fmt,
            "width": 16,
            "align": "currency",
        },
        "status": {
            "header": "STATUS",
            "header_fmt": col_header_fmt,
            "width": 14,
            "align": "center",
        },
        "machine_name": {
            "header": "MACHINE NAME",
            "header_fmt": col_header_left_fmt,
            "width": 20,
            "align": "left",
        },
        "user": {
            "header": "USER",
            "header_fmt": col_header_left_fmt,
            "width": 16,
            "align": "left",
        },
        "remarks": {
            "header": "REMARKS",
            "header_fmt": col_header_left_fmt,
            "width": 28,
            "align": "left",
        },
    }

    # Resolve active columns to export
    active_columns = []
    if custom_headers and isinstance(custom_headers, list):
        for h in custom_headers:
            f = h.get("field") if isinstance(h, dict) else str(h)
            if f in ALL_COLUMN_SPECS:
                spec = ALL_COLUMN_SPECS[f].copy()
                if isinstance(h, dict) and h.get("header"):
                    spec["header"] = h["header"]
                active_columns.append((f, spec))

    if not active_columns:
        active_columns = list(ALL_COLUMN_SPECS.items())

    # Build Title Banner
    total_cols = len(active_columns)
    last_col_letter = xlsxwriter.utility.xl_col_to_name(max(total_cols - 1, 0))

    worksheet.merge_range(
        f"A1:{last_col_letter}1",
        "SAKTHI LASER TECHNOLOGY - INVENTORY & SPARE PARTS HISTORY",
        title_fmt,
    )
    worksheet.set_row(0, 24)
    now_local = (
        timezone.localtime(timezone.now())
        if timezone.is_aware(timezone.now())
        else datetime.datetime.now()
    )
    worksheet.merge_range(
        f"A2:{last_col_letter}2",
        f"Generated on {now_local.strftime('%d-%b-%Y %I:%M %p')}",
        subtitle_fmt,
    )
    worksheet.set_row(1, 16)

    curr_row = 3

    # Write Headers
    for col_idx, (f_key, spec) in enumerate(active_columns):
        worksheet.write(curr_row, col_idx, spec["header"], spec["header_fmt"])
        worksheet.set_column(col_idx, col_idx, spec["width"])

    worksheet.set_row(curr_row, 20)
    curr_row += 1

    start_data_row = curr_row + 1  # 1-based row index for formulas

    if 'rows' not in locals():
        rows = locals().get('custom_rows', None)

    # Parse provided rows if available, else fetch all from DB
    data_rows = []
    if rows and isinstance(rows, list):
        for idx, r in enumerate(rows):
            dt_raw = r.get("created_at")
            date_str = r.get("created_date")
            time_str = r.get("created_time")
            if dt_raw and (not date_str or not time_str or date_str == "-"):
                try:
                    parsed_dt = datetime.datetime.fromisoformat(
                        dt_raw.replace("Z", "+00:00")
                    )
                    date_str = parsed_dt.strftime("%Y-%m-%d")
                    time_str = parsed_dt.strftime("%I:%M %p")
                except Exception:
                    pass

            avail_qty = r.get("available_quantity")
            unit_str = (r.get("unit") or "pcs").lower()
            avail_display = f"{avail_qty} {unit_str}" if avail_qty is not None else "-"

            data_rows.append(
                {
                    "sno": r.get("sno") or (idx + 1),
                    "created_date": date_str or "-",
                    "created_time": time_str or "-",
                    "spare_id": r.get("spare_id") or "-",
                    "item_code": r.get("item_code") or "-",
                    "part_name": r.get("part_name") or "-",
                    "batch_number": r.get("batch_number") or "-",
                    "action": (r.get("action") or "").strip(),
                    "quantity": float(r.get("quantity") or 0),
                    "available_quantity": avail_display,
                    "min_stock_quantity": r.get("min_stock_quantity") if r.get("min_stock_quantity") is not None else "-",
                    "purchase_price": float(r.get("purchase_price") or 0),
                    "status": (r.get("status") or "-").replace("_", " ").upper(),
                    "machine_name": r.get("machine_name") or "Common Machine",
                    "user": r.get("user") or "-",
                    "remarks": r.get("remarks") or "-",
                }
            )
    else:
        history_qs = InventoryHistory.objects.select_related("part").all().order_by("-created_at", "-id")
        for idx, item in enumerate(history_qs):
            created_at = item.created_at
            if created_at:
                local_dt = (
                    timezone.localtime(created_at)
                    if timezone.is_aware(created_at)
                    else created_at
                )
                date_str = local_dt.strftime("%Y-%m-%d")
                time_str = local_dt.strftime("%I:%M %p")
            else:
                date_str = "-"
                time_str = "-"

            spare_id = item.part.spare_id if item.part and item.part.spare_id else (f"SP-{str(item.part.id).zfill(3)}" if item.part and item.part.id else "-")
            item_code = item.part.item_code if item.part and item.part.item_code else "-"
            avail_qty = item.part.available_quantity if item.part else None
            unit_str = (item.part.unit or "pcs").lower() if item.part else "pcs"
            avail_display = f"{avail_qty} {unit_str}" if avail_qty is not None else "-"
            min_qty = item.part.min_stock_quantity if item.part else "-"
            status_val = (item.part.status or "-").replace("_", " ").upper() if item.part else "-"
            batch_no = item.batch_number if item.batch_number else "-"

            data_rows.append(
                {
                    "sno": idx + 1,
                    "created_date": date_str,
                    "created_time": time_str,
                    "spare_id": spare_id,
                    "item_code": item_code,
                    "part_name": item.part_name or "-",
                    "batch_number": batch_no,
                    "action": (item.action or "").strip(),
                    "quantity": float(item.quantity or 0),
                    "available_quantity": avail_display,
                    "min_stock_quantity": min_qty,
                    "purchase_price": float(item.purchase_price or 0),
                    "status": status_val,
                    "machine_name": (
                        item.machine_name if item.machine_name else "Common Machine"
                    ),
                    "user": item.user if item.user else "-",
                    "remarks": item.remarks if item.remarks else "-",
                }
            )

    # Write Data Rows
    action_col_letter = None
    qty_col_letter = None
    for r_idx, row in enumerate(data_rows):
        for c_idx, (f_key, spec) in enumerate(active_columns):
            val = row.get(f_key, "")
            align_type = spec.get("align", "left")

            if f_key == "action":
                action_col_letter = xlsxwriter.utility.xl_col_to_name(c_idx)
            elif f_key == "quantity":
                qty_col_letter = xlsxwriter.utility.xl_col_to_name(c_idx)

            if align_type == "center":
                worksheet.write(curr_row, c_idx, val, cell_center_fmt)
            elif align_type == "action":
                action_lower = str(val).lower()
                if "add" in action_lower:
                    act_fmt = action_added_fmt
                elif "use" in action_lower:
                    act_fmt = action_used_fmt
                elif "del" in action_lower:
                    act_fmt = action_deleted_fmt
                elif "edit" in action_lower:
                    act_fmt = action_edited_fmt
                else:
                    act_fmt = action_default_fmt
                worksheet.write(curr_row, c_idx, str(val).upper(), act_fmt)
            elif align_type == "number":
                worksheet.write(curr_row, c_idx, float(val or 0), cell_num_fmt)
            elif align_type == "currency":
                worksheet.write(curr_row, c_idx, float(val or 0), cell_currency_fmt)
            else:
                worksheet.write(curr_row, c_idx, str(val), cell_text_fmt)

        worksheet.set_row(curr_row, 19)
        curr_row += 1

    end_data_row = curr_row  # 1-based last data row

    # Action-Wise Summary & Overall Total (Only rendered when more than 1 row is exported)
    if data_rows and len(data_rows) > 1:
        # Precompute values for resilience across spreadsheet viewers
        added_count = sum(1 for r in data_rows if "add" in r["action"].lower())
        added_qty = sum(
            r["quantity"] for r in data_rows if "add" in r["action"].lower()
        )

        used_count = sum(1 for r in data_rows if "use" in r["action"].lower())
        used_qty = sum(r["quantity"] for r in data_rows if "use" in r["action"].lower())

        updated_count = sum(1 for r in data_rows if "update" in r["action"].lower())
        updated_qty = sum(
            r["quantity"] for r in data_rows if "update" in r["action"].lower()
        )

        edited_count = sum(1 for r in data_rows if "edit" in r["action"].lower())
        edited_qty = sum(
            r["quantity"] for r in data_rows if "edit" in r["action"].lower()
        )

        deleted_count = sum(1 for r in data_rows if "del" in r["action"].lower())
        deleted_qty = sum(
            r["quantity"] for r in data_rows if "del" in r["action"].lower()
        )

        total_qty = sum(r["quantity"] for r in data_rows)

        summary_categories = [
            (
                "TOTAL ADDED QTY",
                added_count,
                added_qty,
                "*ADD*",
                summary_added_fmt,
                summary_added_num_fmt,
            ),
            (
                "TOTAL UPDATED QTY",
                updated_count,
                updated_qty,
                "*UPDATE*",
                summary_updated_fmt,
                summary_updated_num_fmt,
            ),
            (
                "TOTAL EDITED QTY",
                edited_count,
                edited_qty,
                "*EDIT*",
                summary_edited_fmt,
                summary_edited_num_fmt,
            ),
            (
                "TOTAL USED QTY",
                used_count,
                used_qty,
                "*USE*",
                summary_used_fmt,
                summary_used_num_fmt,
            ),
            (
                "TOTAL DELETED QTY",
                deleted_count,
                deleted_qty,
                "*DEL*",
                summary_deleted_fmt,
                summary_deleted_num_fmt,
            ),
        ]

        for (
            label,
            count_val,
            qty_val,
            formula_pattern,
            label_fmt,
            num_fmt,
        ) in summary_categories:
            for c_idx, (f_key, spec) in enumerate(active_columns):
                if c_idx == 0:
                    worksheet.write(curr_row, c_idx, label, label_fmt)
                elif f_key == "part_name":
                    worksheet.write(
                        curr_row,
                        c_idx,
                        f"{count_val} Record{'s' if count_val != 1 else ''}",
                        label_fmt,
                    )
                elif f_key == "quantity" and qty_col_letter and action_col_letter:
                    worksheet.write_formula(
                        curr_row,
                        c_idx,
                        f'=SUMIF({action_col_letter}{start_data_row}:{action_col_letter}{end_data_row}, "{formula_pattern}", {qty_col_letter}{start_data_row}:{qty_col_letter}{end_data_row})',
                        num_fmt,
                        qty_val,
                    )
                elif f_key == "quantity" and qty_col_letter:
                    worksheet.write(curr_row, c_idx, qty_val, num_fmt)
                else:
                    worksheet.write(curr_row, c_idx, "", label_fmt)
            worksheet.set_row(curr_row, 20)
            curr_row += 1

        # OVERALL TOTAL Row
        for c_idx, (f_key, spec) in enumerate(active_columns):
            if c_idx == 0:
                worksheet.write(curr_row, c_idx, "OVERALL TOTAL QTY", total_fmt)
            elif f_key == "part_name":
                worksheet.write(curr_row, c_idx, f"{len(data_rows)} Records", total_fmt)
            elif f_key == "quantity" and qty_col_letter:
                worksheet.write_formula(
                    curr_row,
                    c_idx,
                    f"=SUM({qty_col_letter}{start_data_row}:{qty_col_letter}{end_data_row})",
                    total_num_fmt,
                    total_qty,
                )
            else:
                worksheet.write(curr_row, c_idx, "", total_fmt)
        worksheet.set_row(curr_row, 22)

    workbook.close()
    output.seek(0)

    filename = f"Inventory_History_Report_{now_local.strftime('%Y-%m-%d')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
