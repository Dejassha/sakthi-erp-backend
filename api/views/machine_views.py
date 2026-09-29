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

def get_machine_interval(next_date, last_date):
    if not next_date or not last_date:
        return None
    if isinstance(next_date, str):
        try:
            next_date = datetime.datetime.strptime(next_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    if isinstance(last_date, str):
        try:
            last_date = datetime.datetime.strptime(last_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    if hasattr(next_date, "date") and callable(getattr(next_date, "date")):
        next_date = next_date.date()
    if hasattr(last_date, "date") and callable(getattr(last_date, "date")):
        last_date = last_date.date()
    delta = next_date - last_date
    return max(delta.days, 0)


# Machines Details
@api_view(["GET"])
def get_machines(request):
    machines = (
        Machine.objects.prefetch_related("maintenance_schedules__machine")
        .all()
        .order_by("-id")
    )
    serializer = MachineSerializer(machines, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_machine(request):
    machine_name = request.data.get("machine_name")
    is_gas = request.data.get("does_need_gas")
    created_by = request.data.get("created_by")

    if not machine_name:
        return Response({"message": "Machine name is required"}, status=400)

    machine_name = str(machine_name).strip()
    if not machine_name:
        return Response({"message": "Machine name is required"}, status=400)

    if Machine.objects.filter(machine_name__iexact=machine_name).exists():
        return Response({"message": "Machine name already exists in the table"}, status=400)

    does_need_gas = is_gas
    if isinstance(does_need_gas, str):
        does_need_gas = does_need_gas.lower() == "true"

    machine = Machine.objects.create(
        machine_name=machine_name,
        does_need_gas=does_need_gas,
        created_by=created_by,
    )

    return Response(
        {"message": "Machine added successfully", "id": machine.id}, status=201
    )


@api_view(["PUT"])
def update_machine(request, id):
    machine_name = request.data.get("machine_name")
    is_gas = request.data.get("does_need_gas")
    created_by = request.data.get("created_by")

    if not machine_name:
        return Response({"message": "Machine name is required"}, status=400)

    machine_name = str(machine_name).strip()
    if not machine_name:
        return Response({"message": "Machine name is required"}, status=400)

    try:
        machine_obj = Machine.objects.get(id=id)
    except Machine.DoesNotExist:
        return Response({"message": "Machine not found"}, status=404)

    current_name = str(machine_obj.machine_name or "").strip()
    if machine_name.lower() != current_name.lower():
        if Machine.objects.filter(machine_name__iexact=machine_name).exists():
            return Response({"message": "Machine name already exists in the table"}, status=400)

    machine_obj.machine_name = machine_name

    does_need_gas = is_gas
    if isinstance(does_need_gas, str):
        does_need_gas = does_need_gas.lower() == "true"
    machine_obj.does_need_gas = does_need_gas

    if created_by:
        machine_obj.created_by = created_by

    machine_obj.save()
    return Response({"message": "Machine updated successfully"}, status=200)


@api_view(["DELETE"])
def delete_machine(request, id):
    try:
        machine_obj = Machine.objects.get(id=id)
    except Machine.DoesNotExist:
        return Response({"message": "Machine not found"}, status=404)

    machine_obj.delete()

    return Response({"message": "Machine deleted successfully"}, status=200)


@api_view(["POST"])
def add_maintenance_schedule(request):
    machine_id = request.data.get("machine_id")
    maintenance_name = request.data.get("maintenance_name", "General Maintenance")
    maintenance_needs = request.data.get("maintenance_needs", "")
    interval_days = request.data.get("interval_days", 30)
    last_maintenance_date = request.data.get("last_maintenance_date")
    next_maintenance_date = request.data.get("next_maintenance_date")
    created_by = request.data.get("created_by") or getattr(request.user, "username", None) or getattr(request.user, "name", None) or "Admin"

    clean_needs = str(maintenance_needs).strip().upper() if maintenance_needs else ""
    if not machine_id or not next_maintenance_date or not interval_days or not clean_needs:
        return Response(
            {
                "message": "machine_id, interval_days, next_maintenance_date, and remarks/maintenance_needs are required"
            },
            status=400,
        )

    try:
        machine = Machine.objects.get(id=machine_id)
    except Machine.DoesNotExist:
        return Response({"message": "Machine not found"}, status=404)

    supervised_by = request.data.get("supervised_by")
    if supervised_by:
        supervised_by = str(supervised_by).strip()

    remind_before_days = request.data.get("remind_before_days", 3)
    try:
        remind_before_days = int(remind_before_days) if remind_before_days is not None else 3
    except (ValueError, TypeError):
        remind_before_days = 3

    schedule = MaintenanceSchedule.objects.create(
        machine=machine,
        maintenance_name=maintenance_name,
        maintenance_needs=clean_needs,
        interval_days=interval_days,
        last_maintenance_date=to_date(last_maintenance_date),
        next_maintenance_date=to_date(next_maintenance_date),
        supervised_by=supervised_by,
        remind_before_days=remind_before_days,
        status="active",
        created_by=created_by,
        updated_by=created_by,
    )

    # Record CREATED audit log
    init_details = {
        "action": "CREATED",
        "maintenance_name": schedule.maintenance_name,
        "supervised_by": schedule.supervised_by,
        "interval_days": schedule.interval_days,
        "remind_before_days": schedule.remind_before_days,
        "last_maintenance_date": str(schedule.last_maintenance_date) if schedule.last_maintenance_date else None,
        "next_maintenance_date": str(schedule.next_maintenance_date),
        "maintenance_needs": schedule.maintenance_needs or "-",
        "status": schedule.status,
    }
    MachineMaintenanceLog.objects.create(
        machine=machine,
        schedule=schedule,
        maintenance_name=schedule.maintenance_name,
        action="CREATED",
        scheduled_date=schedule.next_maintenance_date,
        approved_date=schedule.created_at.date() if hasattr(schedule.created_at, "date") else timezone.now().date(),
        status=schedule.status,
        approved_by=created_by,
        performed_by=created_by,
        supervised_by=schedule.supervised_by,
        action_details=json.dumps(init_details),
        remarks=schedule.maintenance_needs or clean_needs or "-",
        created_at=schedule.created_at,
    )

    return Response(
        {"message": "Schedule created successfully", "id": schedule.id}, status=201
    )


@api_view(["PUT"])
def update_maintenance_schedule(request, id):
    try:
        schedule = MaintenanceSchedule.objects.get(id=id)
    except MaintenanceSchedule.DoesNotExist:
        return Response({"message": "Schedule not found"}, status=404)

    updated_by = request.data.get("updated_by") or request.data.get("created_by") or getattr(request.user, "username", None) or getattr(request.user, "name", None) or "Admin"

    old_name = schedule.maintenance_name
    old_interval = schedule.interval_days
    old_next = schedule.next_maintenance_date

    schedule.maintenance_name = request.data.get(
        "maintenance_name", schedule.maintenance_name
    )

    if "maintenance_needs" in request.data:
        needs_input = request.data.get("maintenance_needs")
        if not needs_input or not str(needs_input).strip():
            return Response(
                {"message": "Remarks / maintenance notes cannot be empty."}, status=400
            )
        schedule.maintenance_needs = str(needs_input).strip().upper()

    if "supervised_by" in request.data:
        sup = request.data.get("supervised_by")
        schedule.supervised_by = str(sup).strip() if sup else None

    if "remind_before_days" in request.data:
        remind = request.data.get("remind_before_days")
        try:
            schedule.remind_before_days = int(remind) if remind is not None else 3
        except (ValueError, TypeError):
            schedule.remind_before_days = 3

    interval = request.data.get("interval_days")
    if interval is not None:
        schedule.interval_days = int(interval)

    last_date = request.data.get("last_maintenance_date")
    if last_date is not None:
        schedule.last_maintenance_date = to_date(last_date)

    next_date = request.data.get("next_maintenance_date")
    if next_date is not None:
        schedule.next_maintenance_date = to_date(next_date)

    schedule.status = request.data.get("status", schedule.status)
    schedule.updated_by = updated_by
    schedule.save()

    # Record EDITED audit log
    update_details = {
        "action": "EDITED",
        "maintenance_name": schedule.maintenance_name,
        "supervised_by": schedule.supervised_by,
        "interval_days": schedule.interval_days,
        "remind_before_days": schedule.remind_before_days,
        "last_maintenance_date": str(schedule.last_maintenance_date) if schedule.last_maintenance_date else None,
        "next_maintenance_date": str(schedule.next_maintenance_date),
        "maintenance_needs": schedule.maintenance_needs or "-",
        "status": schedule.status,
    }
    MachineMaintenanceLog.objects.create(
        machine=schedule.machine,
        schedule=schedule,
        maintenance_name=schedule.maintenance_name,
        action="EDITED",
        scheduled_date=schedule.next_maintenance_date,
        approved_date=timezone.now().date(),
        status=schedule.status,
        approved_by=updated_by,
        performed_by=updated_by,
        supervised_by=schedule.supervised_by,
        action_details=json.dumps(update_details),
        remarks=schedule.maintenance_needs or f"Schedule edited by {updated_by}",
        created_at=timezone.now(),
    )

    return Response({"message": "Schedule updated successfully"}, status=200)


@api_view(["DELETE"])
def delete_maintenance_schedule(request, id):
    try:
        schedule = MaintenanceSchedule.objects.get(id=id)
        remarks = (
            request.data.get("remarks") if isinstance(request.data, dict) else None
        )
        if not remarks or not str(remarks).strip():
            return Response(
                {"message": "Remarks / reason is required to delete a maintenance schedule."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        clean_remarks = str(remarks).strip().upper()

        deleted_by = (
            (request.data.get("deleted_by") if isinstance(request.data, dict) else None)
            or getattr(request.user, "username", None)
            or getattr(request.user, "name", None)
            or schedule.updated_by
            or schedule.created_by
            or "Admin"
        )
        delete_details = {
            "action": "DELETED",
            "maintenance_name": schedule.maintenance_name,
            "supervised_by": schedule.supervised_by,
            "interval_days": schedule.interval_days,
            "remind_before_days": schedule.remind_before_days,
            "last_maintenance_date": str(schedule.last_maintenance_date) if schedule.last_maintenance_date else None,
            "next_maintenance_date": str(schedule.next_maintenance_date) if schedule.next_maintenance_date else None,
            "maintenance_needs": schedule.maintenance_needs or "-",
            "status": "DELETED",
            "remarks": clean_remarks,
        }
        MachineMaintenanceLog.objects.create(
            machine=schedule.machine,
            schedule=None,
            maintenance_name=schedule.maintenance_name,
            action="DELETED",
            scheduled_date=schedule.next_maintenance_date,
            approved_date=timezone.now().date(),
            status="DELETED",
            approved_by=deleted_by,
            performed_by=deleted_by,
            supervised_by=schedule.supervised_by,
            action_details=json.dumps(delete_details),
            remarks=clean_remarks,
            created_at=timezone.now(),
        )

        schedule.delete()
        return Response({"message": "Schedule deleted successfully"}, status=200)
    except MaintenanceSchedule.DoesNotExist:
        return Response({"message": "Schedule not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["POST"])
def approve_maintenance(request):
    schedule_id = request.data.get("schedule_id")
    parts_used = request.data.get("parts_used") or []
    maintenance_date_str = request.data.get("maintenance_date") or request.data.get(
        "approved_date"
    )
    approved_by = (
        request.data.get("approved_by")
        or getattr(request.user, "username", None)
        or getattr(request.user, "name", None)
        or "Admin"
    )
    maintenance_name = request.data.get("maintenance_name")
    remarks_input = request.data.get("remarks")

    if not schedule_id:
        return Response({"message": "schedule_id is required"}, status=400)

    if not remarks_input or not str(remarks_input).strip():
        return Response(
            {"message": "Remarks are required to complete maintenance."}, status=400
        )

    clean_remarks = str(remarks_input).strip().upper()

    try:
        schedule = MaintenanceSchedule.objects.get(id=schedule_id)
        machine = schedule.machine
    except MaintenanceSchedule.DoesNotExist:
        return Response({"message": "Maintenance schedule not found"}, status=404)

    today = datetime.date.today()

    # Parse the maintenance performed date
    if maintenance_date_str:
        try:
            log_approved_date = datetime.datetime.strptime(
                str(maintenance_date_str).strip(), "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            log_approved_date = today
    else:
        log_approved_date = today

    # Calculate next maintenance date dynamically from performed date + interval_days
    next_maintenance_date = log_approved_date + datetime.timedelta(
        days=schedule.interval_days
    )

    if maintenance_name:
        schedule.maintenance_name = maintenance_name

    prev_scheduled_date = schedule.next_maintenance_date

    # Create history log entry (UPDATED / Completed Maintenance)
    complete_details = {
        "action": "UPDATED",
        "maintenance_name": schedule.maintenance_name,
        "completed_date": str(log_approved_date),
        "next_maintenance_date": str(next_maintenance_date),
        "parts_used": parts_used,
        "remarks": clean_remarks,
    }

    MachineMaintenanceLog.objects.create(
        machine=machine,
        schedule=schedule,
        maintenance_name=schedule.maintenance_name,
        action="UPDATED",
        scheduled_date=prev_scheduled_date,
        approved_date=log_approved_date,
        status="completed",
        approved_by=approved_by,
        performed_by=approved_by,
        supervised_by=schedule.supervised_by,
        parts_used=json.dumps(parts_used) if parts_used else None,
        action_details=json.dumps(complete_details),
        remarks=clean_remarks,
        created_at=timezone.now(),
    )

    # Update Schedule with the performed date and new next maintenance date
    schedule.last_maintenance_date = log_approved_date
    schedule.next_maintenance_date = next_maintenance_date
    schedule.updated_by = approved_by
    schedule.save()

    if parts_used:
        for item in parts_used:
            part_name = item.get("part_name")
            qty = item.get("quantity", 0)
            if not part_name:
                continue
            part = (
                InventoryPart.objects.filter(part_name__iexact=part_name)
                .order_by("-id")
                .first()
            )
            if not part:
                continue
            usage = InventoryUsage.objects.create(
                part=part,
                machine=machine,
                machine_name=machine.machine_name,
                used_quantity=qty,
                used_by=request.data.get("approved_by", "Admin"),
                used_hours=item.get("used_hours", "0"),
                used_date=today,
                maintenance_type=schedule.maintenance_name,
                remaining_stock=max(part.stock_quantity - part.used_quantity - qty, 0),
                remarks=item.get("remarks", "Used during maintenance"),
                created_by=request.data.get("approved_by", "Admin"),
            )
            part.used_quantity = part.used_quantity + qty
            part.available_quantity = max(part.stock_quantity - part.used_quantity, 0)
            part.sync_status()
            part.save()
            InventoryHistory.objects.create(
                part=part,
                part_name=part.part_name,
                action="Used",
                quantity=qty,
                machine_name=machine.machine_name,
                user=request.data.get("approved_by", "Admin"),
                remarks="Used during maintenance",
            )

    machine.save()
    return Response({"message": "Maintenance approved successfully"}, status=200)


@api_view(["GET"])
def get_maintenance_history(request):
    # Sort by newest history entry first so recently completed/approved records appear at the top
    logs = (
        MachineMaintenanceLog.objects.select_related("machine", "schedule")
        .all()
        .order_by("-id")
    )
    serializer = MachineMaintenanceLogSerializer(logs, many=True)
    return Response(serializer.data)


# GasDetails CRUD
@api_view(["GET"])
def get_gas_details(request):
    gas = GasDetails.objects.all().order_by("-created_at")
    serializer = GasDetailsSerializer(gas, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_gas_details(request):
    serializer = GasDetailsSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT"])
def update_gas_details(request, pk):
    gas = get_object_or_404(GasDetails, pk=pk)
    serializer = GasDetailsSerializer(gas, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
def delete_gas_details(request, pk):
    gas = get_object_or_404(GasDetails, pk=pk)
    gas.delete()
    return Response({"msg": "deleted successfully"}, status=status.HTTP_200_OK)


