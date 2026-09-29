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
    product_details,
    product_material,
    company,
    programer_details,
    qa_details,
    qa_machine_details,
    acc_details,
    machine_operator,
    material_type,
    Machine,
    MaintenanceSchedule,
    All_User,
    Role,
    Quotation,
    QuotationItem,
    GasDetails,
    QuotationNote,
    MachineMaintenanceLog,
    InventoryPart,
    InventoryPartName,
    InventoryPurpose,
    InventoryUsage,
    PendingMaterial,
    InventoryHistory,
    InventoryRateHistory,
    BreakdownMaintenance,
    KPIRecord,
    KPITemplate,
)

from api.serializers import (
    product_detailsSerializer,
    product_materialSerializer,
    programer_detailsSerializer,
    qa_detailsSerializer,
    QuotationSerializer,
    QuotationListSerializer,
    material_typeSerializer,
    acc_detailsSerializer,
    machine_operatorSerializer,
    MachineSerializer,
    GasDetailsSerializer,
    QuotationNoteSerializer,
    MachineMaintenanceLogSerializer,
    InventoryPartSerializer,
    InventoryPartNameSerializer,
    InventoryPurposeSerializer,
    InventoryUsageSerializer,
    PendingMaterialSerializer,
    InventoryHistorySerializer,
    BreakdownMaintenanceSerializer,
)

from .utils import *
from api.authentication import get_authenticated_username


@api_view(["GET"])
def get_inventory_part_names(request):
    part_names = InventoryPartName.objects.all().order_by("part_name")
    serializer = InventoryPartNameSerializer(part_names, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_inventory_part_name(request):
    serializer = InventoryPartNameSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(["DELETE"])
def delete_inventory_part_name(request, pk):
    try:
        item = InventoryPartName.objects.get(id=pk)
        item.delete()
        return Response({"message": "Part name deleted"})
    except InventoryPartName.DoesNotExist:
        return Response({"message": "Part name not found"}, status=404)


@api_view(["GET"])
def get_inventory_usage_types(request):
    usage_types = InventoryPurpose.objects.all().order_by("name")
    serializer = InventoryPurposeSerializer(usage_types, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_inventory_usage_type(request):
    serializer = InventoryPurposeSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(["DELETE"])
def delete_inventory_usage_type(request, pk):
    try:
        item = InventoryPurpose.objects.get(id=pk)
        item.delete()
        return Response({"message": "Usage type deleted"})
    except InventoryPurpose.DoesNotExist:
        return Response({"message": "Usage type not found"}, status=404)


@api_view(["GET"])
def get_inventory_parts(request):
    parts = (
        InventoryPart.objects.select_related("machine")
        .prefetch_related("rates")
        .all()
        .order_by("-id")
    )
    serializer = InventoryPartSerializer(parts, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_inventory_part(request):
    data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    if "item_name" in data and not data.get("part_name"):
        data["part_name"] = data["item_name"]
    if "purchase_date" in data and not data.get("purchase_date"):
        data["purchase_date"] = None
    if "machine" in data and (data.get("machine") in ["common", "others", "Others", ""]):
        data["machine"] = None

    if not data.get("spare_id"):
        data["spare_id"] = ""
    if not data.get("item_code"):
        data["item_code"] = data.get("spare_id") or (data.get("part_name") or "")[:50]

    required_check_map = {
        "part_name": "Item Name is required.",
        "stock_quantity": "Quantity is required.",
        "min_stock_quantity": "Min Stock Quantity is required.",
        "unit": "Unit is required.",
        "purchase_price": "Rate Per Quantity is required.",
    }

    errors = {}
    for field_key, err_msg in required_check_map.items():
        val = data.get(field_key)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors[field_key] = [err_msg]

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    serializer = InventoryPartSerializer(data=data)
    if serializer.is_valid():
        part = serializer.save()
        part.available_quantity = part.stock_quantity
        part.used_quantity = 0
        if not part.spare_id:
            part.spare_id = f"SP-{part.id:03d}"
        if not part.item_code:
            part.item_code = part.spare_id
        if not part.batch_number:
            existing_count = InventoryPart.objects.filter(part_name__iexact=part.part_name).count()
            part.batch_number = f"BAT-{existing_count:02d}" if existing_count > 1 else "BAT-01"
        part.sync_status()
        part.save()

        # Save initial rate to history
        if part.purchase_price is not None:
            InventoryRateHistory.objects.create(part=part, rate=part.purchase_price)

        user_name = get_authenticated_username(
            request, default=request.data.get("created_by", "Admin")
        )

        if part.part_name:
            InventoryPartName.objects.get_or_create(
                part_name=part.part_name,
                defaults={"created_by": user_name},
            )

        action_type = data.get("action") or "Added"

        InventoryHistory.objects.create(
            part=part,
            part_name=part.part_name,
            batch_number=part.batch_number or "",
            action=action_type,
            quantity=part.stock_quantity,
            purchase_price=part.purchase_price,
            machine_name=part.machine.machine_name if part.machine else "",
            user=user_name,
            remarks=data.get("remarks") or f"Inventory item {action_type.lower()}",
        )
        return Response(InventoryPartSerializer(part).data, status=201)
    
    error_msgs = []
    for field, errs in serializer.errors.items():
        if isinstance(errs, list):
            error_msgs.append(f"{field}: {errs[0]}")
        else:
            error_msgs.append(f"{field}: {errs}")
    return Response({"message": "; ".join(error_msgs), "errors": serializer.errors}, status=400)


@api_view(["PUT"])
def update_inventory_part(request, pk):
    try:
        part = InventoryPart.objects.get(id=pk)
    except InventoryPart.DoesNotExist:
        return Response({"message": "Inventory part not found"}, status=404)

    data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    if "item_name" in data and not data.get("part_name"):
        data["part_name"] = data["item_name"]
    if "purchase_date" in data and not data.get("purchase_date"):
        data["purchase_date"] = None
    if "machine" in data and (data.get("machine") == "common" or data.get("machine") == ""):
        data["machine"] = None

    old_stock = part.stock_quantity
    serializer = InventoryPartSerializer(part, data=data, partial=True)
    if serializer.is_valid():
        updated = serializer.save()
        updated.available_quantity = max(
            updated.stock_quantity - updated.used_quantity, 0
        )
        updated.sync_status()
        updated.save()

        # Save rate to history if purchase_price is provided/updated
        if "purchase_price" in data and data.get("purchase_price") is not None:
            try:
                price_val = Decimal(str(data.get("purchase_price")))
                if not InventoryRateHistory.objects.filter(
                    part=updated, rate=price_val
                ).exists():
                    InventoryRateHistory.objects.create(part=updated, rate=price_val)
            except (InvalidOperation, ValueError, TypeError):
                pass

        user_name = get_authenticated_username(
            request, default=request.data.get("created_by", "Admin")
        )

        if updated.part_name:
            InventoryPartName.objects.get_or_create(
                part_name=updated.part_name,
                defaults={"created_by": user_name},
            )

        action_type = data.get("action") or "Edited"
        added_qty = updated.stock_quantity - old_stock
        log_qty = added_qty if (action_type == "Updated" and added_qty != 0) else updated.available_quantity

        InventoryHistory.objects.create(
            part=updated,
            part_name=updated.part_name,
            batch_number=updated.batch_number or "",
            action=action_type,
            quantity=log_qty,
            purchase_price=updated.purchase_price,
            machine_name=updated.machine.machine_name if updated.machine else "",
            user=user_name,
            remarks=data.get("remarks", f"Inventory item {action_type.lower()}"),
        )
        return Response(InventoryPartSerializer(updated).data)

    error_msgs = []
    for field, errs in serializer.errors.items():
        if isinstance(errs, list):
            error_msgs.append(f"{field}: {errs[0]}")
        else:
            error_msgs.append(f"{field}: {errs}")
    return Response({"message": "; ".join(error_msgs), "errors": serializer.errors}, status=400)


@api_view(["DELETE", "POST"])
def delete_inventory_part(request, pk):
    try:
        part = InventoryPart.objects.get(id=pk)
    except InventoryPart.DoesNotExist:
        return Response({"message": "Inventory part not found"}, status=404)

    remarks = request.data.get("remarks") if isinstance(request.data, dict) else None
    if not remarks:
        remarks = request.GET.get("remarks")

    if not remarks or not str(remarks).strip():
        batch_label = f"batch {part.batch_number}" if part.batch_number else "part"
        remarks = f"Deleted {batch_label} ({part.part_name}) from inventory"

    user_name = get_authenticated_username(
        request,
        default=(
            (request.data.get("user") if isinstance(request.data, dict) else None)
            or (
                request.data.get("created_by")
                if isinstance(request.data, dict)
                else None
            )
            or request.GET.get("user")
            or "Admin"
        ),
    )

    InventoryHistory.objects.create(
        part=None,
        part_name=part.part_name,
        batch_number=part.batch_number or "",
        action="Deleted",
        quantity=part.available_quantity,
        machine_name=part.machine.machine_name if part.machine else "Common Machine",
        user=user_name,
        remarks=str(remarks).strip(),
    )

    part.delete()
    return Response({"message": "Inventory part deleted successfully"})


@api_view(["GET"])
def get_inventory_usage(request):
    usages = (
        InventoryUsage.objects.select_related("part", "machine")
        .all()
        .order_by("-id")
    )
    serializer = InventoryUsageSerializer(usages, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_inventory_usage(request):
    import decimal

    data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    part_id = data.get("part")
    if not part_id:
        return Response({"part": ["This field is required."]}, status=400)

    try:
        target_part = InventoryPart.objects.get(id=part_id)
    except InventoryPart.DoesNotExist:
        return Response({"message": "Part not found"}, status=404)

    # Get all active batches of the same part family
    all_matched = InventoryPart.objects.filter(part_name__iexact=target_part.part_name)

    # Sort by FIFO: purchase date asc, then id asc
    def sort_key(p):
        has_no_date = 1 if p.purchase_date is None else 0
        date_str = str(p.purchase_date) if p.purchase_date is not None else ""
        return (has_no_date, date_str, p.id)

    use_new_qty_val = data.get("use_new_quantity")
    use_new_qty = False
    if isinstance(use_new_qty_val, str):
        use_new_qty = use_new_qty_val.lower() == "true"
    elif use_new_qty_val is not None:
        use_new_qty = bool(use_new_qty_val)

    is_exact_batch_val = data.get("is_exact_batch", False)
    is_exact_batch = False
    if isinstance(is_exact_batch_val, str):
        is_exact_batch = is_exact_batch_val.lower() == "true"
    elif is_exact_batch_val is not None:
        is_exact_batch = bool(is_exact_batch_val)

    # If selected_batch_id is explicitly passed, handle as exact batch
    selected_batch_id = data.get("selected_batch_id") or data.get("batch_id")
    if selected_batch_id:
        is_exact_batch = True

    requested_qty = decimal.Decimal(data.get("used_quantity", 0))
    if requested_qty <= 0:
        return Response(
            {"used_quantity": ["Ensure this value is greater than 0."]}, status=400
        )

    if is_exact_batch:
        if selected_batch_id:
            resolved_part_id = selected_batch_id
        else:
            resolved_part_id = resolve_part_batch(part_id, use_new_qty)

        try:
            batch_part = InventoryPart.objects.get(id=resolved_part_id)
        except InventoryPart.DoesNotExist:
            return Response({"message": "Part batch not found"}, status=404)

        if requested_qty > batch_part.available_quantity:
            batch_label = f"Batch {batch_part.batch_number}" if batch_part.batch_number else "Selected batch"
            return Response(
                {
                    "used_quantity": [
                        f"Insufficient stock in {batch_label}. Available is {batch_part.available_quantity}."
                    ]
                },
                status=400,
            )

        usage_data = data.copy()
        usage_data["part"] = batch_part.id
        usage_data["batch_number"] = batch_part.batch_number or ""
        usage_data["used_quantity"] = float(requested_qty)
        usage_data["use_new_quantity"] = use_new_qty

        serializer = InventoryUsageSerializer(data=usage_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        usage = serializer.save()

        batch_part.used_quantity = batch_part.used_quantity + requested_qty
        batch_part.available_quantity = max(
            batch_part.stock_quantity - batch_part.used_quantity, 0
        )
        batch_part.sync_status()
        batch_part.save()

        InventoryHistory.objects.create(
            part=batch_part,
            part_name=batch_part.part_name,
            batch_number=batch_part.batch_number or "",
            action="Used",
            quantity=requested_qty,
            machine_name=usage.machine_name
            or (usage.machine.machine_name if usage.machine else ""),
            user=usage.used_by or usage.created_by or "Admin",
            remarks=usage.remarks or "Part used during maintenance",
        )
        return Response(serializer.data, status=201)

    matched_parts = list(all_matched)
    if use_new_qty:
        with_date = [p for p in matched_parts if p.purchase_date is not None]
        no_date = [p for p in matched_parts if p.purchase_date is None]
        with_date.sort(key=lambda p: (p.purchase_date, p.id), reverse=True)
        no_date.sort(key=lambda p: p.id, reverse=True)
        matched_parts = with_date + no_date
    else:
        matched_parts.sort(key=sort_key)

    requested_qty = decimal.Decimal(data.get("used_quantity", 0))
    if requested_qty <= 0:
        return Response(
            {"used_quantity": ["Ensure this value is greater than 0."]}, status=400
        )

    total_available = sum(p.available_quantity for p in matched_parts)
    if requested_qty > total_available:
        return Response(
            {
                "used_quantity": [
                    f"Insufficient stock. Total available is {total_available}."
                ]
            },
            status=400,
        )

    remaining_qty = requested_qty
    usages_to_create = []

    for p in matched_parts:
        if remaining_qty <= 0:
            break
        if p.available_quantity <= 0:
            continue

        qty_to_consume = min(p.available_quantity, remaining_qty)
        remaining_qty -= qty_to_consume

        usage_data = data.copy()
        usage_data["part"] = p.id
        usage_data["batch_number"] = p.batch_number or ""
        usage_data["used_quantity"] = float(qty_to_consume)

        usages_to_create.append((p, qty_to_consume, usage_data))

    if not usages_to_create:
        return Response({"message": "No available stock to consume."}, status=400)

    # Validate all serializers first
    serializers = []
    for p, qty, usage_data in usages_to_create:
        serializer = InventoryUsageSerializer(data=usage_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializers.append((serializer, p, qty))

    # Save all
    created_usages = []
    for serializer, p, qty in serializers:
        usage = serializer.save()

        # Update part stock
        p.used_quantity = p.used_quantity + qty
        p.available_quantity = max(p.stock_quantity - p.used_quantity, 0)
        p.sync_status()
        p.save()

        # Create history record
        InventoryHistory.objects.create(
            part=p,
            part_name=p.part_name,
            batch_number=p.batch_number or "",
            action="Used",
            quantity=qty,
            machine_name=usage.machine_name
            or (usage.machine.machine_name if usage.machine else ""),
            user=usage.used_by or usage.created_by or "Admin",
            remarks=usage.remarks or "Part used during maintenance",
        )
        created_usages.append(serializer.data)

    return Response(created_usages[0], status=201)


@api_view(["PUT", "PATCH"])
def update_inventory_usage(request, pk):
    try:
        usage = InventoryUsage.objects.get(pk=pk)
    except InventoryUsage.DoesNotExist:
        return Response({"message": "Usage record not found"}, status=404)

    old_quantity = usage.used_quantity
    old_part = usage.part

    data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    part_id = data.get("part")
    if not part_id and usage.part:
        part_id = usage.part.id

    use_new_quantity = data.get("use_new_quantity", usage.use_new_quantity)
    is_exact_batch = data.get("is_exact_batch", False)
    if part_id and not is_exact_batch:
        resolved_part_id = resolve_part_batch(
            part_id, use_new_quantity, editing_usage_id=usage.id
        )
        data["part"] = resolved_part_id

    serializer = InventoryUsageSerializer(usage, data=data, partial=True)
    if serializer.is_valid():
        updated_usage = serializer.save()

        # Update stock for part(s)
        new_part = updated_usage.part
        new_quantity = updated_usage.used_quantity

        if old_part and old_part == new_part:
            # Same part, adjust quantity diff
            diff = new_quantity - old_quantity
            old_part.used_quantity = max(old_part.used_quantity + diff, 0)
            old_part.available_quantity = max(
                old_part.stock_quantity - old_part.used_quantity, 0
            )
            old_part.sync_status()
            old_part.save()
        else:
            # Part changed: revert old part, apply to new part
            if old_part:
                old_part.used_quantity = max(old_part.used_quantity - old_quantity, 0)
                old_part.available_quantity = max(
                    old_part.stock_quantity - old_part.used_quantity, 0
                )
                old_part.sync_status()
                old_part.save()
            if new_part:
                new_part.used_quantity = max(new_part.used_quantity + new_quantity, 0)
                new_part.available_quantity = max(
                    new_part.stock_quantity - new_part.used_quantity, 0
                )
                new_part.sync_status()
                new_part.save()

        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(["DELETE"])
def delete_inventory_usage(request, pk):
    try:
        usage = InventoryUsage.objects.get(pk=pk)
    except InventoryUsage.DoesNotExist:
        return Response({"message": "Usage record not found"}, status=404)

    part = usage.part
    used_qty = usage.used_quantity
    usage.delete()

    if part:
        part.used_quantity = max(part.used_quantity - used_qty, 0)
        part.available_quantity = max(part.stock_quantity - part.used_quantity, 0)
        part.sync_status()
        part.save()

    return Response({"message": "Part usage record deleted successfully"})


@api_view(["GET"])
def get_pending_materials(request):
    pending = PendingMaterial.objects.all().order_by("-id")
    serializer = PendingMaterialSerializer(pending, many=True)
    return Response(serializer.data)


@api_view(["PUT"])
def update_pending_material(request, pk):
    try:
        pending = PendingMaterial.objects.get(id=pk)
    except PendingMaterial.DoesNotExist:
        return Response({"message": "Pending material not found"}, status=404)
    serializer = PendingMaterialSerializer(pending, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)

