import json
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from api.models import BreakdownMaintenance, BreakdownMaintenanceLog
from api.serializers import BreakdownMaintenanceSerializer, BreakdownMaintenanceLogSerializer
from .utils import _calculate_downtime_hours


def _create_breakdown_log(record, action, user_name, remarks=None):
    status_val = "CLOSED" if (record.restart_time or record.maintenance_complete_time) else "OPEN"
    if action == "DELETED":
        status_val = "DELETED"

    clean_remarks = (remarks or record.remarks or "").strip().upper()
    if not clean_remarks:
        clean_remarks = f"{record.record_number or 'Breakdown'} - {action.capitalize()} by {user_name}".upper()

    details = {
        "action": action,
        "record_number": record.record_number,
        "breakdown_date": str(record.breakdown_date) if record.breakdown_date else None,
        "breakdown_time": str(record.breakdown_time) if record.breakdown_time else None,
        "shift": record.shift,
        "machine_id": record.machine_id if record.machine else None,
        "machine_name": record.machine.machine_name if record.machine else "-",
        "affected_equipment": record.affected_equipment,
        "operator_name": record.operator_name,
        "supervisor": record.supervisor,
        "breakdown_type": record.breakdown_type,
        "maintenance_start_time": str(record.maintenance_start_time) if record.maintenance_start_time else None,
        "maintenance_complete_time": str(record.maintenance_complete_time) if record.maintenance_complete_time else None,
        "restart_time": str(record.restart_time) if record.restart_time else None,
        "breakdown_complete_date": str(record.breakdown_complete_date) if record.breakdown_complete_date else None,
        "total_downtime_hours": float(record.total_downtime_hours or 0),
        "status": status_val,
        "performed_by": user_name,
        "remarks": clean_remarks,
    }

    return BreakdownMaintenanceLog.objects.create(
        machine=record.machine,
        breakdown=record if action != "DELETED" else None,
        record_number=record.record_number,
        action=action,
        breakdown_type=record.breakdown_type,
        affected_equipment=record.affected_equipment,
        shift=record.shift,
        breakdown_date=record.breakdown_date,
        breakdown_time=record.breakdown_time,
        maintenance_start_time=record.maintenance_start_time,
        maintenance_complete_time=record.maintenance_complete_time,
        restart_time=record.restart_time,
        breakdown_complete_date=record.breakdown_complete_date,
        total_downtime_hours=record.total_downtime_hours or 0,
        operator_name=record.operator_name,
        supervisor=record.supervisor,
        performed_by=user_name,
        status=status_val,
        action_details=json.dumps(details),
        remarks=clean_remarks,
        created_at=timezone.now(),
    )


@api_view(["GET"])
def get_breakdown_maintenance(request):
    records = BreakdownMaintenance.objects.select_related("machine").all().order_by("-id")
    serializer = BreakdownMaintenanceSerializer(records, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def get_breakdown_maintenance_logs(request):
    logs = BreakdownMaintenanceLog.objects.select_related("machine").all().order_by("-id")
    serializer = BreakdownMaintenanceLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def add_breakdown_maintenance(request):
    record_number = request.data.get("record_number")
    if record_number and isinstance(record_number, str) and record_number.strip():
        trimmed_rn = record_number.strip()
        if BreakdownMaintenance.objects.filter(record_number__iexact=trimmed_rn).exists():
            return Response(
                {"message": f"Breakdown record number '{trimmed_rn}' already exists. Please use a unique record number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    remarks = request.data.get("remarks")
    if not remarks or not str(remarks).strip():
        return Response(
            {"message": "Remarks are required to create a breakdown record."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = BreakdownMaintenanceSerializer(data=request.data)
    if serializer.is_valid():
        record = serializer.save()
        if not record.record_number:
            gen_number = f"BM-{record.id:04d}"
            counter = 1
            while BreakdownMaintenance.objects.filter(record_number=gen_number).exclude(id=record.id).exists():
                gen_number = f"BM-{record.id + counter:04d}"
                counter += 1
            record.record_number = gen_number
        record.total_downtime_hours = _calculate_downtime_hours(record)
        clean_remarks = str(remarks).strip().upper()
        record.remarks = clean_remarks
        record.save()

        user_name = (
            request.data.get("created_by")
            or getattr(request.user, "username", None)
            or getattr(request.user, "name", None)
            or record.operator_name
            or "Admin"
        )
        _create_breakdown_log(record, "CREATED", user_name, remarks=clean_remarks)

        return Response(BreakdownMaintenanceSerializer(record).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(["PUT"])
def update_breakdown_maintenance(request, pk):
    try:
        record = BreakdownMaintenance.objects.get(id=pk)
    except BreakdownMaintenance.DoesNotExist:
        return Response({"message": "Breakdown maintenance record not found"}, status=404)

    record_number = request.data.get("record_number")
    if record_number and isinstance(record_number, str) and record_number.strip():
        trimmed_rn = record_number.strip().upper()
        if BreakdownMaintenance.objects.filter(record_number__iexact=trimmed_rn).exclude(id=pk).exists():
            return Response(
                {"message": f"Breakdown record number '{trimmed_rn}' already exists. Please use a unique record number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    remarks = request.data.get("remarks")
    if not remarks or not str(remarks).strip():
        return Response(
            {"message": "Remarks are required to update a breakdown record."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = BreakdownMaintenanceSerializer(record, data=request.data, partial=True)
    if serializer.is_valid():
        updated = serializer.save()
        if not updated.record_number:
            updated.record_number = f"BM-{updated.id:04d}"
        updated.total_downtime_hours = _calculate_downtime_hours(updated)
        clean_remarks = str(remarks).strip().upper()
        updated.remarks = clean_remarks
        updated.save()

        user_name = (
            request.data.get("updated_by")
            or request.data.get("created_by")
            or getattr(request.user, "username", None)
            or getattr(request.user, "name", None)
            or updated.supervisor
            or updated.operator_name
            or "Admin"
        )
        action_type = request.data.get("action_type")
        if not action_type:
            if updated.restart_time or updated.maintenance_complete_time or updated.breakdown_complete_date:
                action_type = "UPDATED"
            else:
                action_type = "EDITED"
        _create_breakdown_log(updated, action_type, user_name, remarks=clean_remarks)

        return Response(BreakdownMaintenanceSerializer(updated).data)
    return Response(serializer.errors, status=400)


@api_view(["DELETE"])
def delete_breakdown_maintenance(request, pk):
    try:
        record = BreakdownMaintenance.objects.get(id=pk)
    except BreakdownMaintenance.DoesNotExist:
        return Response({"message": "Breakdown maintenance record not found"}, status=404)

    remarks = (
        request.data.get("remarks") if isinstance(request.data, dict) else None
    )
    if not remarks or not str(remarks).strip():
        return Response(
            {"message": "Remarks / reason is required to delete a breakdown record."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    clean_remarks = str(remarks).strip().upper()
    user_name = (
        (request.data.get("deleted_by") if isinstance(request.data, dict) else None)
        or getattr(request.user, "username", None)
        or getattr(request.user, "name", None)
        or record.created_by
        or "Admin"
    )
    _create_breakdown_log(record, "DELETED", user_name, remarks=clean_remarks)

    record.delete()
    return Response({"message": "Breakdown maintenance record deleted successfully"})
