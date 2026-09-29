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
from django.conf import settings
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

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

def to_date(val):
    if not val or val == "":
        return None
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        try:
            return datetime.datetime.strptime(val, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return None


# Helper for Production-Level Decimal Handling
def to_decimal(val):
    """Safely converts a value to Decimal for DB storage. Returns None for empty/invalid/NaN/Infinity."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "infinity", "-infinity", "+infinity", "inf", "-inf", "null", "undefined", "none"):
        return None
    s = s.replace(",", "")
    try:
        d = Decimal(s)
        if not d.is_finite():
            return None
        return d
    except (InvalidOperation, ValueError, TypeError):
        return None


def to_float(val):
    """Safely converts a value to float for DB storage. Returns None for empty/invalid/NaN/Infinity."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "infinity", "-infinity", "+infinity", "inf", "-inf", "null", "undefined", "none"):
        return None
    s = s.replace(",", "")
    try:
        import math
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def to_duration(val):
    """Safely converts a string (HH:MM or HH:MM:SS) to timedelta for DurationField."""
    from datetime import timedelta

    if not val or str(val).strip() == "":
        return None
    try:
        parts = str(val).strip().split(":")
        if len(parts) == 2:
            return timedelta(hours=int(parts[0]), minutes=int(parts[1]))
        elif len(parts) == 3:
            return timedelta(
                hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2])
            )
    except (ValueError, IndexError):
        pass
    return None


def apply_ag_grid_filter(queryset, field_name, filter_config):
    """
    Recursive helper to apply Ag-Grid filters (supports conditions list, condition1/condition2, & operators).
    """
    if not filter_config:
        return queryset

    # 1. Handle Combined Filter with conditions list (Modern Ag-Grid v30+)
    if "conditions" in filter_config and isinstance(filter_config["conditions"], list):
        operator = filter_config.get("operator", "AND").upper()
        q_combined = None
        for cond in filter_config["conditions"]:
            q_cond = get_q_for_single_condition(field_name, cond)
            if q_combined is None:
                q_combined = q_cond
            else:
                if operator == "OR":
                    q_combined = q_combined | q_cond
                else:
                    q_combined = q_combined & q_cond
        return queryset.filter(q_combined) if q_combined is not None else queryset

    # 2. Handle Combined Filter with condition1 / condition2 (Legacy Ag-Grid)
    if "condition1" in filter_config or "condition2" in filter_config or "operator" in filter_config:
        operator = filter_config.get("operator", "AND").upper()
        cond1 = filter_config.get("condition1")
        cond2 = filter_config.get("condition2")

        q1 = get_q_for_single_condition(field_name, cond1) if cond1 else Q()
        q2 = get_q_for_single_condition(field_name, cond2) if cond2 else Q()

        if cond1 and cond2:
            if operator == "OR":
                return queryset.filter(q1 | q2)
            else:
                return queryset.filter(q1 & q2)
        elif cond1:
            return queryset.filter(q1)
        elif cond2:
            return queryset.filter(q2)

    # 3. Handle Single Condition
    q = get_q_for_single_condition(field_name, filter_config)
    return queryset.filter(q)


def get_q_for_single_condition(field_name, config):
    """
    Returns a Django Q object for a single Ag-Grid condition.
    """
    if not config or not isinstance(config, dict):
        return Q()

    type_op = config.get("type")
    filter_value = config.get("filter")
    date_from = config.get("dateFrom")
    date_to = config.get("dateTo")
    filter_to = config.get("filterTo")

    # Normalize Dates: Ag-Grid sends "YYYY-MM-DD 00:00:00" for dates.
    # We strip the time to ensure correct DateField comparison in SQLite/Django.
    v_from = filter_value if filter_value is not None else date_from
    v_to = filter_to if filter_to is not None else date_to

    if config.get("filterType") == "date" or "date" in field_name.lower():
        if isinstance(v_from, str):
            v_from = v_from.split(" ")[0].split("T")[0]
        if isinstance(v_to, str):
            v_to = v_to.split(" ")[0].split("T")[0]

    # 1. Null / Empty checks
    if type_op == "blank":
        return Q(**{f"{field_name}__isnull": True}) | Q(**{field_name: ""})
    if type_op == "notBlank":
        return ~Q(**{f"{field_name}__isnull": True}) & ~Q(**{field_name: ""})

    # 2. Logic based on field type / operator
    if type_op == "inRange":
        if v_from is not None and v_to is not None:
            d_start = min(v_from, v_to)
            d_end = max(v_from, v_to)
            return Q(**{f"{field_name}__range": [d_start, d_end]})
        elif v_from is not None:
            return Q(**{f"{field_name}__gte": v_from})
        elif v_to is not None:
            return Q(**{f"{field_name}__lte": v_to})

    # 3. Set / Array Values
    if type_op == "set" or "values" in config:
        values = config.get("values", [])
        if values:
            return Q(**{f"{field_name}__in": values})

    # 4. Comparisons
    v_main = v_from
    if v_main is not None:
        if type_op in ("equals", "equal"):
            return Q(**{field_name: v_main})
        if type_op in ("notEqual", "notEquals"):
            return ~Q(**{field_name: v_main})
        if type_op == "greaterThan":
            return Q(**{f"{field_name}__gt": v_main})
        if type_op in ("greaterThanOrEqual", "greaterThanOrEqualTo"):
            return Q(**{f"{field_name}__gte": v_main})
        if type_op == "lessThan":
            return Q(**{f"{field_name}__lt": v_main})
        if type_op in ("lessThanOrEqual", "lessThanOrEqualTo"):
            return Q(**{f"{field_name}__lte": v_main})

    # 5. Text operations
    if filter_value is not None:
        if type_op == "contains":
            return Q(**{f"{field_name}__icontains": filter_value})
        if type_op == "notContains":
            return ~Q(**{f"{field_name}__icontains": filter_value})
        if type_op == "startsWith":
            return Q(**{f"{field_name}__istartswith": filter_value})
        if type_op == "endsWith":
            return Q(**{f"{field_name}__iendswith": filter_value})

    return Q()


def parse_time_to_minutes(value):
    if value is None:
        return 0
    # Handle timedelta (e.g. from DurationField)
    if isinstance(value, datetime.timedelta):
        return int(value.total_seconds() / 60)
    # Handle string H:M format
    if isinstance(value, str) and ":" in value:
        try:
            parts = value.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h * 60 + m
        except (ValueError, TypeError):
            return 0
    # Fallback for numeric strings/numbers
    try:
        return int(float(value))
    except (ValueError, TypeError, OverflowError):
        return 0


def format_duration_as_time(duration):
    if duration is None:
        return ""
    if isinstance(duration, str):
        return duration
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def _calculate_downtime_hours(record):
    breakdown_time = record.breakdown_time
    restart_time = record.restart_time
    if not breakdown_time or not restart_time:
        return Decimal("0")

    start_date = record.breakdown_date or timezone.now().date()
    end_date = record.breakdown_complete_date or record.breakdown_date or start_date

    start_dt = datetime.datetime.combine(start_date, breakdown_time)
    end_dt = datetime.datetime.combine(end_date, restart_time)
    if end_dt <= start_dt:
        end_dt += datetime.timedelta(days=1)

    diff_hours = (end_dt - start_dt).total_seconds() / 3600
    return Decimal(str(round(diff_hours, 2)))


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    return Response(
        {
            "success": True,
            "message": "Sakthi Laser ERP API is active.",
        }
    )


@api_view(["POST"])
def record_inventory_history(request):
    serializer = InventoryHistorySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


def resolve_part_batch(part_id, use_new_quantity, editing_usage_id=None):
    try:
        original_part = InventoryPart.objects.get(id=part_id)
    except InventoryPart.DoesNotExist:
        return part_id

    # Get all parts with the same name
    all_matched = InventoryPart.objects.filter(part_name__iexact=original_part.part_name)

    # Filter parts that have available_quantity > 0,
    # OR if we are editing, include the part that is currently used by this usage record.
    currently_used_part_id = None
    if editing_usage_id:
        try:
            currently_used_part_id = InventoryUsage.objects.get(id=editing_usage_id).part_id
        except InventoryUsage.DoesNotExist:
            pass

    matched_parts = []
    for p in all_matched:
        if p.available_quantity > 0 or p.id == currently_used_part_id or p.id == original_part.id:
            matched_parts.append(p)

    if not matched_parts:
        return original_part.id

    # Sort matched parts: purchase date ascending (nulls last), then id ascending
    def sort_key(p):
        has_no_date = 1 if p.purchase_date is None else 0
        date_str = str(p.purchase_date) if p.purchase_date is not None else ""
        return (has_no_date, date_str, p.id)

    matched_parts.sort(key=sort_key)

    if use_new_quantity:
        return matched_parts[-1].id
    else:
        return matched_parts[0].id


@api_view(["POST"])
def create_pending_material(request):
    try:
        with transaction.atomic():
            data = request.data
            product_id = data.get("product_id")
            material_id = data.get("material_id")
            remaining_width = data.get("remaining_width")
            remaining_length = data.get("remaining_length")
            balance_qty = data.get("balance_quantity")

            # STEP 1 Resolve material and product
            if not product_id:
                return Response(
                    {"error": "Missing 'product_id' ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not material_id:
                return Response(
                    {"error": "Missing 'material_id' ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                product = product_details.objects.get(id=product_id)
                old_material = product_material.objects.get(id=material_id)
            except product_details.DoesNotExist:
                return Response(
                    {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
                )
            except product_material.DoesNotExist:
                return Response(
                    {"error": "Material not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # STEP 5 Create new updated material
            bal_qty = to_decimal(balance_qty)
            rem_width = to_decimal(remaining_width)
            rem_length = to_decimal(remaining_length)

            thick_val = old_material.thick or Decimal("0")
            density_val = Decimal(str(old_material.density or 0.0))
            
            new_unit_weight = Decimal("0")
            new_total_weight = Decimal("0")
            if rem_width and rem_length:
                new_unit_weight = thick_val * rem_width * rem_length * density_val
                if bal_qty:
                    new_total_weight = bal_qty * new_unit_weight

            new_mat = product_material.objects.create(
                product=product,
                uid_no=old_material.uid_no,
                heat_no=old_material.heat_no,
                mat_type=old_material.mat_type,
                mat_grade=old_material.mat_grade,
                thick=old_material.thick,
                width=rem_width,
                length=rem_length,
                density=old_material.density,
                unit_weight=new_unit_weight,
                quantity=bal_qty,
                total_weight=new_total_weight,
                total_length=(
                    rem_length * bal_qty
                    if rem_length and bal_qty
                    else None
                ),
                total_width=(
                    rem_width * bal_qty
                    if rem_width and bal_qty
                    else None
                ),
                bay=old_material.bay,
                stock_due=old_material.stock_due,
                remarks=old_material.remarks,
                programer_status="pending",
                qa_status="pending",
                acc_status="pending",
            )

            return Response(
                {
                    "message": "Material copied and updated successfully",
                    "new_material_id": new_mat.id,
                    "width": remaining_width,
                    "length": remaining_length,
                    "quantity": balance_qty,
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        print("? Error:", str(e))
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


