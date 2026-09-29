import os
import json
import io
import datetime
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Max, Q, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

import openpyxl
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from api.models import (
    product_details, product_material, company, programer_details,
    qa_details, qa_machine_details, acc_details, machine_operator,
    material_type, Machine, MaintenanceSchedule, All_User, Role, Quotation, QuotationItem,
    GasDetails, QuotationNote, MachineMaintenanceLog, InventoryPart,
    InventoryPartName, InventoryPurpose, InventoryUsage, PendingMaterial,
    InventoryHistory, InventoryRateHistory, BreakdownMaintenance,
    KPIRecord, KPITemplate
)

from api.serializers import (
    product_detailsSerializer, product_materialSerializer, programer_detailsSerializer,
    qa_detailsSerializer, QuotationSerializer, QuotationListSerializer,
    material_typeSerializer, acc_detailsSerializer, machine_operatorSerializer,
    MachineSerializer, GasDetailsSerializer, QuotationNoteSerializer,
    MachineMaintenanceLogSerializer, InventoryPartSerializer,
    InventoryPartNameSerializer, InventoryPurposeSerializer, InventoryUsageSerializer,
    PendingMaterialSerializer, InventoryHistorySerializer, BreakdownMaintenanceSerializer
)

from .utils import *

@api_view(["GET"])
def get_kpis(request):
    try:
        from api.models import KPITemplate, KPIRecord, programer_details, qa_machine_details
        from datetime import datetime
        import calendar


        # Get query params
        queries_str = request.query_params.get("queries")
        
        now = datetime.now()
        curr_week = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"
        curr_month = now.strftime("%Y-%m")
        curr_year = now.strftime("%Y")

        DEFAULT_KPIS = [
            {"s_no": 1, "kpi_category": "Production", "kpi_parameter": "Machine Utilization", "formula": "Planned Hours / Runtime (HH:MM) * 100", "target": "85-90%", "achieved": "", "frequency": "Monthly", "responsible": "Production", "remarks": "Achieved target utilization indicating effective machine capacity usage."},
            {"s_no": 2, "kpi_category": "Production", "kpi_parameter": "Production Achievement", "formula": "Total Used Weight / Processed Quantity * 100", "target": "90-95%", "achieved": "", "frequency": "Monthly", "responsible": "Planning + Production", "remarks": "Slightly below target; improvement required in planning and production coordination."},
            {"s_no": 3, "kpi_category": "Production", "kpi_parameter": "Overall Equipment Efficiency", "formula": "Productive Time / Total Time * 100", "target": ">=85%", "achieved": "", "frequency": "Monthly", "responsible": "Production", "remarks": "Close to tagret; improvement required by reducing downtime and improving performance."},
            {"s_no": 4, "kpi_category": "Laser", "kpi_parameter": "Cutting Speed Efficiency", "formula": "Actual Speed / Target Speed * 100", "target": ">=90%", "achieved": "", "frequency": "Monthly", "responsible": "Programming", "remarks": "Achieved target; cutting parameters and programming optimized."},
            {"s_no": 5, "kpi_category": "Laser", "kpi_parameter": "Nesting Efficiency", "formula": "Material Used / Sheet Area * 100", "target": ">= 85%", "achieved": "", "frequency": "Monthly", "responsible": "Programming", "remarks": "Below target; nesting optimization required to improve sheet utilization."},
            {"s_no": 6, "kpi_category": "Laser", "kpi_parameter": "Scrap Percentage", "formula": "Scrap Weight / Total Material * 100", "target": "<= 10%", "achieved": "", "frequency": "Monthly", "responsible": "Production", "remarks": "Significantly higher than tager; review nesting strategy and material handling."},
            {"s_no": 7, "kpi_category": "Folding", "kpi_parameter": "Bending Accuracy", "formula": "Correct Parts / Total Parts * 100", "target": ">=98%", "achieved": "", "frequency": "Monthly", "responsible": "Quality", "remarks": "Target achieved; bending process maintained dimensional accuracy."},
            {"s_no": 8, "kpi_category": "Quality", "kpi_parameter": "Rejection Rate", "formula": "Rejected Parts / Total Parts * 100", "target": "<=1%", "achieved": "", "frequency": "Monthly", "responsible": "Quality", "remarks": "Within acceptable limit but requires continuous monitoring to maintain quality."},
            {"s_no": 9, "kpi_category": "Quality", "kpi_parameter": "Rework Percentage", "formula": "Rework Parts / Total Parts * 100", "target": "<=2%", "achieved": "", "frequency": "Monthly", "responsible": "Production + Quality", "remarks": "Needs improvement; reduce rework by implementing proper quality checks and controls."},
            {"s_no": 10, "kpi_category": "Maintenance", "kpi_parameter": "Machine Downtime", "formula": "Actual Downtime / Planned Downtime * 100", "target": "<=8%", "achieved": "", "frequency": "Monthly", "responsible": "Maintenance", "remarks": "Improve maintenance planning and execution to reduce downtime and ensure on-time maintenance."},
            {"s_no": 11, "kpi_category": "Maintenance", "kpi_parameter": "Preventive Maintenance Compliance", "formula": "Actual Maintenance / Target Maintenance * 100", "target": "100%", "achieved": "", "frequency": "Monthly", "responsible": "Maintenance", "remarks": "Needs improvement; increase preventive maintenance frequency and compliance."},
            {"s_no": 12, "kpi_category": "Delivery", "kpi_parameter": "On-Time Delivery", "formula": "Jobs Delivered on Schedule / Total Jobs * 100", "target": "<= 95%", "achieved": "", "frequency": "Monthly", "responsible": "Planning", "remarks": "On track; maintain current performance levels to meet customer expectations."},
            {"s_no": 13, "kpi_category": "Cost Control", "kpi_parameter": "Consumable Cost Control", "formula": "Consumables Used vs Standard", "target": "Within Budget", "achieved": "", "frequency": "Monthly", "responsible": "Stores", "remarks": "Cost control measures in place; monitor usage to stay within budget."},
            {"s_no": 14, "kpi_category": "Safety", "kpi_parameter": "Safety Compliance", "formula": "No . of Incidents", "target": "Zero", "achieved": "", "frequency": "Monthly", "responsible": "All Staff", "remarks": "Zero incidents recorded; maintain safety standards through regular training and awareness programs."},
            {"s_no": 15, "kpi_category": "Production", "kpi_parameter": "Overall Equipment Effectiveness (OEE)", "formula": "Availability * Performance * Quality", "target": ">=57%", "achieved": "", "frequency": "Monthly", "responsible": "Production + Quality", "remarks": "Slightly below target, improvement required in availability, performance and quality. "}
        ]

        templates = KPITemplate.objects.all().order_by("group_id", "s_no")
        if not templates.exists():
            for item in DEFAULT_KPIS:
                KPITemplate.objects.create(
                    group_id="1",
                    name="Default KPI Configuration",
                    s_no=item["s_no"],
                    kpi_category=item["kpi_category"],
                    kpi_parameter=item["kpi_parameter"],
                    formula=item["formula"],
                    target=item["target"],
                    frequency=item["frequency"],
                    responsible=item["responsible"],
                    achieved=item.get("achieved", ""),
                    remarks=item.get("remarks", "")
                )
            templates = KPITemplate.objects.all().order_by("group_id", "s_no")

        query_map = {}
        if queries_str:
            for item in queries_str.split(","):
                parts = item.split("|")
                if len(parts) >= 4:
                    try:
                        g_id = parts[0].strip()
                        s_no_val = int(parts[1].strip())
                        freq = parts[2].strip()
                        period = parts[3].strip()
                        query_map[(g_id, s_no_val)] = (freq, period)
                    except ValueError:
                        pass
                elif len(parts) == 3:
                    try:
                        s_no_val = int(parts[0].strip())
                        freq = parts[1].strip()
                        period = parts[2].strip()
                        query_map[("1", s_no_val)] = (freq, period)
                    except ValueError:
                        pass

        def get_default_period(freq):
            if freq == "Weekly":
                return curr_week
            elif freq == "Yearly":
                return curr_year
            else:
                return curr_month

        # Helper to get date range for a specific row frequency based on selected period
        def get_row_date_range(p_str, row_freq):
            # Parse reference date
            if "-W" in p_str:
                try:
                    y, w = map(int, p_str.split("-W"))
                    ref = datetime.strptime(f"{y}-W{w:02d}-1", "%G-W%V-%u").date()
                except Exception:
                    ref = datetime.today().date()
            elif len(p_str) == 7 and "-" in p_str:
                try:
                    y, m = map(int, p_str.split("-"))
                    ref = datetime(y, m, 1).date()
                except Exception:
                    ref = datetime.today().date()
            elif len(p_str) == 4:
                try:
                    y = int(p_str)
                    ref = datetime(y, 1, 1).date()
                except Exception:
                    ref = datetime.today().date()
            else:
                ref = datetime.today().date()

            # Calculate bounds
            if row_freq == "Weekly":
                y, w, wd = ref.isocalendar()
                start = datetime.strptime(f"{y}-W{w:02d}-1", "%G-W%V-%u").date()
                end = datetime.strptime(f"{y}-W{w:02d}-7", "%G-W%V-%u").date()
                return start, end
            elif row_freq == "Yearly":
                return datetime(ref.year, 1, 1).date(), datetime(ref.year, 12, 31).date()
            else: # Monthly
                last_day = calendar.monthrange(ref.year, ref.month)[1]
                return datetime(ref.year, ref.month, 1).date(), datetime(ref.year, ref.month, last_day).date()

        kpi_data = []
        for t in templates:
            try:
                g_id = t.group_id or "1"
                if (g_id, t.s_no) in query_map:
                    freq, period = query_map[(g_id, t.s_no)]
                else:
                    freq = t.frequency
                    period = get_default_period(freq)

                start_date, end_date = get_row_date_range(period, freq)

                # Fetch or create KPIRecord by group_id, month and s_no
                kpi_rec, _ = KPIRecord.objects.get_or_create(
                    group_id=g_id,
                    month=period,
                    s_no=t.s_no,
                    defaults={
                        "kpi_category": t.kpi_category,
                        "kpi_parameter": t.kpi_parameter,
                        "formula": t.formula,
                        "target": t.target,
                        "frequency": freq,
                        "responsible": t.responsible,
                        "achieved": getattr(t, 'achieved', '') or '',
                        "remarks": getattr(t, 'remarks', '') or '',
                    }
                )

                # Use template achieved/remarks as the base, override with record if present
                template_achieved = getattr(t, 'achieved', '') or ''
                template_remarks = getattr(t, 'remarks', '') or ''
                
                final_remarks = template_remarks if template_remarks else (kpi_rec.remarks or '')
                
                # If user saved an achieved value on the record or template, use it; otherwise compute
                if kpi_rec.achieved is not None and kpi_rec.achieved != "":
                    achieved_str = kpi_rec.achieved
                elif template_achieved != "":
                    achieved_str = template_achieved
                else:
                    # Calculations
                    achieved_str = ""
                    if t.kpi_parameter == "Machine Utilization":
                        prog_logs = programer_details.objects.filter(program_date__range=[start_date, end_date])
                        qa_logs = qa_machine_details.objects.filter(date__range=[start_date, end_date])
                        total_planned_seconds = 0.0
                        for log in prog_logs:
                            if log.total_planned_hours is not None:
                                total_planned_seconds += log.total_planned_hours.total_seconds()

                        total_runtime_seconds = 0.0
                        for log in qa_logs:
                            if log.runtime is not None:
                                total_runtime_seconds += log.runtime.total_seconds()

                        if total_runtime_seconds > 0:
                            achieved_pct = (total_planned_seconds / total_runtime_seconds) * 100
                            if achieved_pct > 100.0:
                                achieved_pct = 100.0
                            achieved_str = f"{achieved_pct:.2f}%"
                        else:
                            achieved_str = "0.00%"
                    elif t.kpi_parameter == "Production Achievement":
                        prog_logs = programer_details.objects.filter(program_date__range=[start_date, end_date])
                        total_used_weight = 0.0
                        total_processed_qty = 0.0
                        for log in prog_logs:
                            if log.total_used_weight:
                                total_used_weight += float(log.total_used_weight)
                            if log.processed_quantity:
                                total_processed_qty += float(log.processed_quantity)

                        if total_processed_qty > 0:
                            achieved_pct = (total_used_weight / total_processed_qty) * 100
                            if achieved_pct > 100.0:
                                achieved_pct = 100.0
                            achieved_str = f"{achieved_pct:.2f}%"
                        else:
                            achieved_str = "0.00%"
                    elif t.kpi_parameter == "Consumable Cost Control":
                        achieved_str = "yes"
                    elif t.kpi_parameter == "Safety Compliance":
                        achieved_str = "0%"

                row_data = {
                    "id": kpi_rec.id,
                    "group_id": g_id,
                    "name": getattr(t, 'name', '') or '',
                    "created_by": getattr(t, 'created_by', '') or '',
                    "s_no": t.s_no,
                    "kpi_category": t.kpi_category,
                    "kpi_parameter": t.kpi_parameter,
                    "formula": t.formula,
                    "target": t.target,
                    "achieved": achieved_str,
                    "frequency": kpi_rec.frequency,
                    "responsible": t.responsible,
                    "remarks": final_remarks,
                    "period": period,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                if kpi_rec.extra_data and isinstance(kpi_rec.extra_data, dict):
                    row_data.update(kpi_rec.extra_data)
                kpi_data.append(row_data)
            except Exception as e:
                print(f"Error parsing template row {t.s_no}: {e}")

        return Response(kpi_data, status=200)

    except Exception as e:
        print(f"Error in get_kpis: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
def save_kpis(request):
    try:
        from api.models import KPITemplate, KPIRecord
        
        rows = request.data.get("rows", [])
        group_id = request.data.get("group_id")
        config_name = request.data.get("name", "")
        created_by = request.data.get("created_by", "")
        if not group_id:
            for r in rows:
                if r.get("group_id"):
                    group_id = r.get("group_id")
                    break
            if not group_id:
                import uuid
                group_id = str(uuid.uuid4())
        
        # If group already exists, delete old templates so the edit fully replaces them
        existing_templates = KPITemplate.objects.filter(group_id=group_id)
        if existing_templates.exists():
            existing_templates.delete()
        
        # Clean up any KPIRecords for this group_id where s_no is greater than current number of rows
        max_s_no = len(rows)
        KPIRecord.objects.filter(group_id=group_id, s_no__gt=max_s_no).delete()

        standard_fields = {
            "id", "s_no", "kpi_category", "kpi_parameter", "formula",
            "target", "achieved", "frequency", "responsible", "remarks", "period"
        }
        meta_fields = {"group_id", "name", "created_by", "created_at", "extra_data"}

        for row in rows:
            s_no = row.get("s_no")
            kpi_category = row.get("kpi_category", "")
            kpi_parameter = row.get("kpi_parameter", "")
            formula = row.get("formula", "")
            target = row.get("target", "")
            frequency = row.get("frequency", "Monthly")
            responsible = row.get("responsible", "")
            achieved = row.get("achieved", "")
            remarks = row.get("remarks", "")
            period = row.get("period", "")
            
            # Extract additional custom fields into extra_data
            extra_data = {}
            if isinstance(row.get("extra_data"), dict):
                extra_data.update(row.get("extra_data"))
            for k, v in row.items():
                if k not in standard_fields and k not in meta_fields:
                    extra_data[k] = v

            # Create KPITemplate
            KPITemplate.objects.create(
                group_id=group_id,
                name=config_name,
                created_by=created_by,
                s_no=s_no,
                kpi_category=kpi_category,
                kpi_parameter=kpi_parameter,
                formula=formula,
                target=target,
                frequency=frequency,
                responsible=responsible,
                achieved=achieved,
                remarks=remarks,
            )
            
            # Update existing KPIRecord entries for this group_id and s_no so remarks and other fields sync
            KPIRecord.objects.filter(group_id=group_id, s_no=s_no).update(
                kpi_category=kpi_category,
                kpi_parameter=kpi_parameter,
                formula=formula,
                target=target,
                frequency=frequency,
                responsible=responsible,
                achieved=achieved,
                remarks=remarks,
                extra_data=extra_data,
            )
            
            # Update or create KPIRecord for this specific period if provided
            if period:
                KPIRecord.objects.update_or_create(
                    group_id=group_id,
                    month=period,
                    s_no=s_no,
                    defaults={
                        "kpi_category": kpi_category,
                        "kpi_parameter": kpi_parameter,
                        "formula": formula,
                        "target": target,
                        "frequency": frequency,
                        "responsible": responsible,
                        "achieved": achieved,
                        "remarks": remarks,
                        "extra_data": extra_data,
                    }
                )
                
        return Response({"status": True, "message": "All KPIs saved successfully"}, status=200)
    except Exception as e:
        print(f"Error in save_kpis: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(["PUT"])
def update_kpi(request, pk):
    try:
        from api.models import KPIRecord, KPITemplate
        kpi_rec = KPIRecord.objects.get(pk=pk)

        target = request.data.get("target")
        frequency = request.data.get("frequency")
        responsible = request.data.get("responsible")
        remarks = request.data.get("remarks")
        kpi_category = request.data.get("kpi_category")
        kpi_parameter = request.data.get("kpi_parameter")
        formula = request.data.get("formula")
        achieved = request.data.get("achieved")

        if target is not None:
            kpi_rec.target = target
        if frequency is not None:
            kpi_rec.frequency = frequency
        if responsible is not None:
            kpi_rec.responsible = responsible
        if remarks is not None:
            kpi_rec.remarks = remarks
        if kpi_category is not None:
            kpi_rec.kpi_category = kpi_category
        if kpi_parameter is not None:
            kpi_rec.kpi_parameter = kpi_parameter
        if formula is not None:
            kpi_rec.formula = formula
        if achieved is not None:
            kpi_rec.achieved = achieved

        # Also support updating extra_data / custom columns if provided
        standard_fields = {
            "id", "s_no", "kpi_category", "kpi_parameter", "formula",
            "target", "achieved", "frequency", "responsible", "remarks", "period"
        }
        meta_fields = {"group_id", "name", "created_by", "created_at", "extra_data"}
        current_extra_data = dict(kpi_rec.extra_data or {})
        if isinstance(request.data.get("extra_data"), dict):
            current_extra_data.update(request.data.get("extra_data"))
        for k, v in request.data.items():
            if k not in standard_fields and k not in meta_fields:
                current_extra_data[k] = v
        kpi_rec.extra_data = current_extra_data

        kpi_rec.save()

        # Update templates to keep them synchronized
        KPITemplate.objects.filter(group_id=kpi_rec.group_id, s_no=kpi_rec.s_no).update(
            kpi_category=kpi_rec.kpi_category,
            kpi_parameter=kpi_rec.kpi_parameter,
            formula=kpi_rec.formula,
            target=kpi_rec.target,
            frequency=kpi_rec.frequency,
            responsible=kpi_rec.responsible,
            achieved=kpi_rec.achieved,
            remarks=kpi_rec.remarks,
        )
        return Response({"status": True, "message": "KPI updated successfully"}, status=200)

    except KPIRecord.DoesNotExist:
        return Response({"error": "KPI record not found"}, status=404)
    except Exception as e:
        print(f"Error in update_kpi: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(["DELETE"])
def delete_kpi_group(request, group_id):
    try:
        from api.models import KPITemplate, KPIRecord
        KPITemplate.objects.filter(group_id=group_id).delete()
        KPIRecord.objects.filter(group_id=group_id).delete()
        return Response({"status": True, "message": "KPI configuration group deleted successfully"}, status=200)
    except Exception as e:
        print(f"Error in delete_kpi_group: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
def get_kpi_defaults(request):
    """Returns the default KPI template rows for pre-filling the Add New KPI Configuration form."""
    try:
        from api.models import KPITemplate
        # Try to return from group_id="1" (default template) if it exists
        defaults = KPITemplate.objects.filter(group_id="1").order_by("s_no")
        if defaults.exists():
            data = [{
                "s_no": t.s_no,
                "kpi_category": t.kpi_category,
                "kpi_parameter": t.kpi_parameter,
                "formula": t.formula,
                "target": t.target,
                "achieved": t.achieved if t.achieved is not None else "",
                "frequency": t.frequency,
                "responsible": t.responsible,
                "remarks": t.remarks or "",
            } for t in defaults]
            return Response(data, status=200)

        # Fallback: return hardcoded defaults
        DEFAULT_KPIS = [
            {"s_no": 1, "kpi_category": "Production", "kpi_parameter": "Machine Utilization", "formula": "Planned Hours / Runtime (HH:MM) * 100", "target": "85-90%", "achieved": "", "frequency": "Monthly", "responsible": "Production", "remarks": "Achieved target utilization indicating effective machine capacity usage."},
            {"s_no": 2, "kpi_category": "Production", "kpi_parameter": "Production Achievement", "formula": "Total Used Weight / Processed Quantity * 100", "target": "90-95%", "achieved": "", "frequency": "Monthly", "responsible": "Planning + Production", "remarks": "Slightly below target; improvement required in planning and production coordination."},
            {"s_no": 3, "kpi_category": "Production", "kpi_parameter": "Overall Equipment Efficiency", "formula": "Productive Time / Total Time * 100", "target": ">=85%", "achieved": "", "frequency": "Monthly", "responsible": "Production", "remarks": "Close to tagret; improvement required by reducing downtime and improving performance."},
            {"s_no": 4, "kpi_category": "Laser", "kpi_parameter": "Cutting Speed Efficiency", "formula": "Actual Speed / Target Speed * 100", "target": ">=90%", "achieved": "", "frequency": "Monthly", "responsible": "Programming", "remarks": "Achieved target; cutting parameters and programming optimized."},
            {"s_no": 5, "kpi_category": "Laser", "kpi_parameter": "Nesting Efficiency", "formula": "Material Used / Sheet Area * 100", "target": ">= 85%", "achieved": "", "frequency": "Monthly", "responsible": "Programming", "remarks": "Below target; nesting optimization required to improve sheet utilization."},
            {"s_no": 6, "kpi_category": "Laser", "kpi_parameter": "Scrap Percentage", "formula": "Scrap Weight / Total Material * 100", "target": "<= 10%", "achieved": "", "frequency": "Monthly", "responsible": "Production", "remarks": "Significantly higher than tager; review nesting strategy and material handling."},
            {"s_no": 7, "kpi_category": "Folding", "kpi_parameter": "Bending Accuracy", "formula": "Correct Parts / Total Parts * 100", "target": ">=98%", "achieved": "", "frequency": "Monthly", "responsible": "Quality", "remarks": "Target achieved; bending process maintained dimensional accuracy."},
            {"s_no": 8, "kpi_category": "Quality", "kpi_parameter": "Rejection Rate", "formula": "Rejected Parts / Total Parts * 100", "target": "<=1%", "achieved": "", "frequency": "Monthly", "responsible": "Quality", "remarks": "Within acceptable limit but requires continuous monitoring to maintain quality."},
            {"s_no": 9, "kpi_category": "Quality", "kpi_parameter": "Rework Percentage", "formula": "Rework Parts / Total Parts * 100", "target": "<=2%", "achieved": "", "frequency": "Monthly", "responsible": "Production + Quality", "remarks": "Needs improvement; reduce rework by implementing proper quality checks and controls."},
            {"s_no": 10, "kpi_category": "Maintenance", "kpi_parameter": "Machine Downtime", "formula": "Actual Downtime / Planned Downtime * 100", "target": "<=8%", "achieved": "", "frequency": "Monthly", "responsible": "Maintenance", "remarks": "Improve maintenance planning and execution to reduce downtime and ensure on-time maintenance."},
            {"s_no": 11, "kpi_category": "Maintenance", "kpi_parameter": "Preventive Maintenance Compliance", "formula": "Actual Maintenance / Target Maintenance * 100", "target": "100%", "achieved": "", "frequency": "Monthly", "responsible": "Maintenance", "remarks": "Needs improvement; increase preventive maintenance frequency and compliance."},
            {"s_no": 12, "kpi_category": "Delivery", "kpi_parameter": "On-Time Delivery", "formula": "Jobs Delivered on Schedule / Total Jobs * 100", "target": "<= 95%", "achieved": "", "frequency": "Monthly", "responsible": "Planning", "remarks": "On track; maintain current performance levels to meet customer expectations."},
            {"s_no": 13, "kpi_category": "Cost Control", "kpi_parameter": "Consumable Cost Control", "formula": "Consumables Used vs Standard", "target": "Within Budget", "achieved": "", "frequency": "Monthly", "responsible": "Stores", "remarks": "Cost control measures in place; monitor usage to stay within budget."},
            {"s_no": 14, "kpi_category": "Safety", "kpi_parameter": "Safety Compliance", "formula": "No . of Incidents", "target": "Zero", "achieved": "", "frequency": "Monthly", "responsible": "All Staff", "remarks": "Zero incidents recorded; maintain safety standards through regular training and awareness programs."},
            {"s_no": 15, "kpi_category": "Production", "kpi_parameter": "Overall Equipment Effectiveness (OEE)", "formula": "Availability * Performance * Quality", "target": ">=57%", "achieved": "", "frequency": "Monthly", "responsible": "Production + Quality", "remarks": "Slightly below target, improvement required in availability, performance and quality. "}
        ]
        return Response(DEFAULT_KPIS, status=200)
    except Exception as e:
        print(f"Error in get_kpi_defaults: {e}")
        return Response({"error": str(e)}, status=500)


