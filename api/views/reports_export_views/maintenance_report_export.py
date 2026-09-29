import io
import json
import datetime
from decimal import Decimal
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import xlsxwriter

from api.models import Machine, MaintenanceSchedule, BreakdownMaintenance, MachineMaintenanceLog, BreakdownMaintenanceLog


import ast

def _format_parts_used(parts_raw):
    """
    Formats parts_used field into a clean human-readable string.
    Handles JSON strings, Python literal lists, lists of dicts/strings, or raw text.
    """
    if not parts_raw:
        return "-"
    if isinstance(parts_raw, list):
        items = []
        for p in parts_raw:
            if isinstance(p, dict):
                p_name = p.get("part_name") or p.get("name") or "Part"
                p_qty = p.get("quantity") or p.get("qty") or 1
                items.append(f"{p_name} x{p_qty}")
            else:
                items.append(str(p))
        return ", ".join(items) if items else "-"
    if isinstance(parts_raw, str):
        parts_str = parts_raw.strip()
        if not parts_str or parts_str in ["[]", "{}"]:
            return "-"
        try:
            parsed = json.loads(parts_str)
            return _format_parts_used(parsed)
        except Exception:
            try:
                parsed = ast.literal_eval(parts_str)
                if isinstance(parsed, (list, dict)):
                    return _format_parts_used(parsed)
            except Exception:
                pass
            return parts_str
    return str(parts_raw)


def _format_downtime(hours_val):
    """
    Converts decimal/float hours into HH:MM display format.
    Returns '-' if zero or None.
    """
    if hours_val is None:
        return "-"
    try:
        val = float(hours_val)
    except (ValueError, TypeError):
        return "-"
    if val <= 0:
        return "-"
    total_minutes = int(round(val * 60))
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def _calculate_remaining_days(next_maintenance_date, remind_before_days=3):
    """
    Calculates remaining days, human-readable display string, and status category.
    """
    if not next_maintenance_date:
        return None, "-", None
    today = timezone.now().date() if timezone.is_aware(timezone.now()) else datetime.date.today()
    if isinstance(next_maintenance_date, str):
        try:
            next_date = datetime.datetime.strptime(next_maintenance_date[:10], "%Y-%m-%d").date()
        except Exception:
            return None, "-", None
    elif isinstance(next_maintenance_date, datetime.datetime):
        next_date = next_maintenance_date.date()
    else:
        next_date = next_maintenance_date

    remind_days = remind_before_days if remind_before_days is not None else 3
    delta = (next_date - today).days
    if delta < 0:
        abs_delta = abs(delta)
        display = f"Overdue by {abs_delta} Day{'s' if abs_delta != 1 else ''}"
        status_cat = "overdue"
    elif delta == 0:
        display = "Due Today"
        status_cat = "due"
    elif delta <= remind_days:
        display = f"{delta} Day{'s' if delta != 1 else ''}"
        status_cat = "remind"
    else:
        display = f"{delta} Days"
        status_cat = "safe"
    return delta, display, status_cat


def _format_datetime_ampm(dt_val):
    """
    Formats a datetime object or ISO string to 'YYYY-MM-DD hh:mm AM/PM'.
    """
    if not dt_val or dt_val == "-":
        return "-"
    if isinstance(dt_val, datetime.datetime):
        if timezone.is_aware(dt_val):
            dt_val = timezone.localtime(dt_val)
        return dt_val.strftime("%Y-%m-%d %I:%M %p")
    if isinstance(dt_val, datetime.date):
        return dt_val.strftime("%Y-%m-%d")
    if isinstance(dt_val, str):
        val_s = dt_val.strip()
        try:
            dt_obj = datetime.datetime.fromisoformat(val_s)
            if timezone.is_aware(dt_obj):
                dt_obj = timezone.localtime(dt_obj)
            return dt_obj.strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            try:
                dt_obj = datetime.datetime.strptime(val_s[:16], "%Y-%m-%d %H:%M")
                return dt_obj.strftime("%Y-%m-%d %I:%M %p")
            except Exception:
                return val_s
    return str(dt_val)


def _format_time_ampm(t_val):
    """
    Formats a time object or string to 'hh:mm AM/PM'.
    """
    if not t_val or t_val == "-":
        return "-"
    if isinstance(t_val, datetime.time):
        return t_val.strftime("%I:%M %p")
    if isinstance(t_val, str):
        val_s = t_val.strip()
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p", "%I:%M %a", "%I:%M%a"):
            try:
                t_obj = datetime.datetime.strptime(val_s, fmt).time()
                return t_obj.strftime("%I:%M %p")
            except Exception:
                pass
        return val_s
    return str(t_val)


def _get_schedule_item(sched):
    rem_days, rem_display, rem_status = _calculate_remaining_days(
        sched.next_maintenance_date,
        getattr(sched, "remind_before_days", 3),
    )
    status_val = "OVERDUE" if (rem_days is not None and rem_days < 0) else "PENDING"
    if sched.status and sched.status.upper() in ["ACTIVE", "PENDING", "OVERDUE", "OPEN", "CLOSED", "COMPLETED"]:
        if sched.status.upper() == "ACTIVE":
            status_val = "OVERDUE" if (rem_days is not None and rem_days < 0) else "PENDING"
        else:
            status_val = sched.status.upper()

    m_date = sched.last_maintenance_date.strftime("%Y-%m-%d") if sched.last_maintenance_date else None
    next_m_date = sched.next_maintenance_date.strftime("%Y-%m-%d") if sched.next_maintenance_date else None
    
    created_at_dt = sched.created_at if hasattr(sched, "created_at") and sched.created_at else None
    created_at_str = _format_datetime_ampm(created_at_dt)
    updated_at_dt = sched.updated_at if hasattr(sched, "updated_at") and sched.updated_at else None
    updated_at_str = _format_datetime_ampm(updated_at_dt)

    user_val = sched.updated_by or sched.created_by or "ADMIN"
    event_timestamp = updated_at_str if (updated_at_str != "-" and updated_at_str != created_at_str) else created_at_str

    details_parts = []
    if sched.interval_days:
        details_parts.append(f"Interval: {sched.interval_days} Days")
    if sched.maintenance_needs and sched.maintenance_needs != "-":
        details_parts.append(f"Needs: {sched.maintenance_needs}")
    if next_m_date:
        details_parts.append(f"Next Due: {next_m_date}")
    details_str = " | ".join(details_parts) if details_parts else (sched.maintenance_needs or "-")

    sched_created_at_dt = sched.updated_at if (hasattr(sched, "updated_at") and sched.updated_at) else (sched.created_at if hasattr(sched, "created_at") and sched.created_at else None)
    iso_timestamp = sched_created_at_dt.isoformat() if hasattr(sched_created_at_dt, "isoformat") else str(sched_created_at_dt or "")

    return {
        "id": f"PM-{sched.id}",
        "raw_id": sched.id,
        "iso_timestamp": iso_timestamp,
        "maintenance_type": "Periodic Maintenance",
        "type_key": "periodic",
        "action": "CREATED",
        "timestamp": event_timestamp,
        "user": user_val,
        "performed_by": user_val,
        "created_by": sched.created_by or "ADMIN",
        "created_at": created_at_str,
        "updated_by": sched.updated_by or sched.created_by or "ADMIN",
        "updated_at": updated_at_str,
        "record_number": f"PM-{sched.id:04d}",
        "machine_id": sched.machine.id if sched.machine else None,
        "machine_name": sched.machine.machine_name if sched.machine else "-",
        "title": sched.maintenance_name or "Periodic Maintenance",
        "supervised_by": sched.supervised_by or "-",
        "maintenance_needs": sched.maintenance_needs or "-",
        "interval_days": sched.interval_days,
        "interval_display": f"{sched.interval_days} Days" if sched.interval_days else "-",
        "remind_before_days": sched.remind_before_days,
        "remind_before_display": f"{sched.remind_before_days} Days" if sched.remind_before_days is not None else "-",
        "maintenance_date": m_date,
        "next_maintenance_date": next_m_date,
        "remaining_days": rem_days,
        "remaining_days_display": rem_display,
        "remaining_days_status": rem_status,
        "downtime_hours": 0,
        "downtime_display": "-",
        "status": status_val,
        "operator_name": "-",
        "approved_by": None,
        "parts_used": "-",
        "remarks": sched.maintenance_needs or "-",
    }


def _get_breakdown_item(bm):
    downtime = float(bm.total_downtime_hours or 0)
    downtime_disp = _format_downtime(downtime)

    is_closed = bool(bm.breakdown_complete_date or bm.restart_time or bm.maintenance_complete_time)
    action_val = "UPDATED" if is_closed else "CREATED"
    status_val = "CLOSED" if is_closed else "OPEN"

    m_date = bm.breakdown_date.strftime("%Y-%m-%d") if bm.breakdown_date else (
        bm.created_at.strftime("%Y-%m-%d") if bm.created_at else None
    )

    c_date = bm.breakdown_complete_date.strftime("%Y-%m-%d") if bm.breakdown_complete_date else None

    rec_num = bm.record_number or f"BM-{bm.id:04d}"

    remarks_parts = []
    if bm.shift:
        shift_str = str(bm.shift).strip()
        if shift_str.lower().startswith("shift"):
            remarks_parts.append(shift_str)
        else:
            remarks_parts.append(f"Shift {shift_str}")
    if bm.breakdown_type:
        remarks_parts.append(bm.breakdown_type)
    remarks_str = " | ".join(remarks_parts) if remarks_parts else (bm.affected_equipment or "-")

    created_at_dt = bm.created_at if hasattr(bm, "created_at") and bm.created_at else None
    created_at_str = _format_datetime_ampm(created_at_dt)
    iso_timestamp = created_at_dt.isoformat() if hasattr(created_at_dt, "isoformat") else str(created_at_dt or "")
    user_val = bm.created_by or bm.operator_name or "ADMIN"

    bd_time = _format_time_ampm(bm.breakdown_time)
    m_start_time = _format_time_ampm(bm.maintenance_start_time)
    m_comp_time = _format_time_ampm(bm.maintenance_complete_time)
    r_time = _format_time_ampm(bm.restart_time)

    return {
        "id": f"BM-{bm.id}",
        "raw_id": bm.id,
        "iso_timestamp": iso_timestamp,
        "maintenance_type": "Breakdown Maintenance",
        "type_key": "breakdown",
        "action": action_val,
        "timestamp": created_at_str,
        "user": user_val,
        "performed_by": user_val,
        "created_by": user_val,
        "record_number": rec_num,
        "machine_id": bm.machine.id if bm.machine else None,
        "machine_name": bm.machine.machine_name if bm.machine else "-",
        "title": bm.breakdown_type or bm.affected_equipment or "Breakdown Maintenance",
        "breakdown_type": bm.breakdown_type or "-",
        "affected_equipment": bm.affected_equipment or "-",
        "shift": bm.shift or "-",
        "operator_name": bm.operator_name or "-",
        "supervisor": bm.supervisor or "-",
        "supervised_by": bm.supervisor or "-",
        "breakdown_date": m_date,
        "breakdown_time": bd_time,
        "maintenance_start_time": m_start_time,
        "maintenance_complete_time": m_comp_time,
        "restart_time": r_time,
        "breakdown_complete_date": c_date,
        "completion_date": c_date,
        "maintenance_date": m_date,
        "next_maintenance_date": c_date,
        "action_taken": getattr(bm, "action_taken", "-") or "-",
        "maintenance_needs": bm.affected_equipment or "-",
        "interval_days": None,
        "remaining_days": None,
        "remaining_days_display": "-",
        "remaining_days_status": None,
        "downtime_hours": downtime,
        "downtime_display": downtime_disp,
        "total_downtime_hours": downtime,
        "status": status_val,
        "approved_by": bm.supervisor or None,
        "parts_used": "-",
        "remarks": bm.remarks or remarks_str,
    }


def _get_breakdown_log_item(log):
    created_at_dt = log.created_at if hasattr(log, "created_at") and log.created_at else None
    created_at_str = _format_datetime_ampm(created_at_dt)
    iso_timestamp = created_at_dt.isoformat() if hasattr(created_at_dt, "isoformat") else str(created_at_dt or "")

    user_val = getattr(log, "performed_by", None) or getattr(log, "operator_name", None) or "ADMIN"

    parsed_d = {}
    raw_details = getattr(log, "action_details", None)
    if raw_details:
        try:
            parsed_d = json.loads(raw_details) if isinstance(raw_details, str) else raw_details
            if not isinstance(parsed_d, dict):
                parsed_d = {}
        except Exception:
            parsed_d = {}

    raw_action = str(getattr(log, "action", "") or "").upper()
    if raw_action in ["COMPLETED", "APPROVED", "UPDATED"]:
        action_val = "UPDATED"
    elif raw_action in ["EDITED", "MODIFIED"]:
        action_val = "EDITED"
    elif raw_action == "DELETED":
        action_val = "DELETED"
    elif raw_action == "CREATED":
        action_val = "CREATED"
    else:
        action_val = raw_action or "UPDATED"

    rec_num = log.record_number or parsed_d.get("record_number") or (f"BM-{log.breakdown_id:04d}" if log.breakdown_id else f"BL-{log.id:04d}")

    downtime = float(log.total_downtime_hours or parsed_d.get("total_downtime_hours") or 0)
    downtime_disp = _format_downtime(downtime)

    m_date = str(log.breakdown_date) if log.breakdown_date else parsed_d.get("breakdown_date")
    c_date = str(log.breakdown_complete_date) if log.breakdown_complete_date else parsed_d.get("breakdown_complete_date")

    remarks_val = parsed_d.get("remarks") or log.remarks or "-"

    record_status = (
        parsed_d.get("status")
        or log.status
        or ("DELETED" if action_val == "DELETED" else ("CLOSED" if (log.restart_time or log.maintenance_complete_time or parsed_d.get("restart_time") or parsed_d.get("maintenance_complete_time")) else "OPEN"))
    )

    bd_time = _format_time_ampm(log.breakdown_time or parsed_d.get("breakdown_time"))
    m_start_time = _format_time_ampm(log.maintenance_start_time or parsed_d.get("maintenance_start_time"))
    m_comp_time = _format_time_ampm(log.maintenance_complete_time or parsed_d.get("maintenance_complete_time"))
    r_time = _format_time_ampm(log.restart_time or parsed_d.get("restart_time"))

    return {
        "id": f"BL-{log.id}",
        "raw_id": log.id,
        "iso_timestamp": iso_timestamp,
        "maintenance_type": "Breakdown Maintenance",
        "type_key": "breakdown",
        "action": action_val,
        "timestamp": created_at_str,
        "user": user_val,
        "performed_by": user_val,
        "created_by": user_val,
        "record_number": rec_num,
        "machine_id": log.machine.id if log.machine else None,
        "machine_name": log.machine.machine_name if log.machine else parsed_d.get("machine_name", "-"),
        "title": log.breakdown_type or log.affected_equipment or "Breakdown Maintenance",
        "breakdown_type": log.breakdown_type or parsed_d.get("breakdown_type", "-"),
        "affected_equipment": log.affected_equipment or parsed_d.get("affected_equipment", "-"),
        "shift": log.shift or parsed_d.get("shift", "-"),
        "operator_name": log.operator_name or parsed_d.get("operator_name", "-"),
        "supervisor": log.supervisor or parsed_d.get("supervisor", "-"),
        "supervised_by": log.supervisor or parsed_d.get("supervisor", "-"),
        "breakdown_date": m_date,
        "breakdown_time": bd_time,
        "maintenance_start_time": m_start_time,
        "maintenance_complete_time": m_comp_time,
        "restart_time": r_time,
        "breakdown_complete_date": c_date,
        "completion_date": c_date,
        "maintenance_date": m_date,
        "next_maintenance_date": c_date,
        "action_taken": getattr(log, "action_taken", "-") or "-",
        "maintenance_needs": log.affected_equipment or "-",
        "interval_days": None,
        "remaining_days": None,
        "remaining_days_display": "-",
        "remaining_days_status": None,
        "downtime_hours": downtime,
        "downtime_display": downtime_disp,
        "total_downtime_hours": downtime,
        "status": record_status,
        "parts_used": "-",
        "remarks": remarks_val,
        "action_details": raw_details,
    }



def _get_log_item(log):
    created_at_dt = log.created_at if hasattr(log, "created_at") and log.created_at else (log.approved_date if log.approved_date else None)
    created_at_str = _format_datetime_ampm(created_at_dt)

    user_val = getattr(log, "performed_by", None) or log.approved_by or (log.schedule.created_by if log.schedule and log.schedule.created_by else "ADMIN")

    parsed_d = {}
    raw_details = getattr(log, "action_details", None)
    if raw_details:
        try:
            parsed_d = json.loads(raw_details) if isinstance(raw_details, str) else raw_details
            if not isinstance(parsed_d, dict):
                parsed_d = {}
        except Exception:
            parsed_d = {}

    raw_action = str(getattr(log, "action", "") or "").upper()
    if raw_action in ["COMPLETED", "APPROVED"] or parsed_d.get("action") in ["COMPLETED", "APPROVED"] or getattr(log, "status", "").lower() in ["completed", "approved"]:
        action_val = "UPDATED"
    elif raw_action in ["EDITED", "UPDATED", "MODIFIED"]:
        action_val = "EDITED"
    elif raw_action == "DELETED":
        action_val = "DELETED"
    elif raw_action == "CREATED":
        action_val = "CREATED"
    else:
        action_val = raw_action or "UPDATED"

    # Extract historical interval from snapshot
    hist_interval = parsed_d.get("interval_days") or (log.schedule.interval_days if log.schedule else None)
    interval_disp = f"{hist_interval} Days" if hist_interval else "-"

    # Extract historical dates from snapshot
    if action_val == "UPDATED":
        m_date = parsed_d.get("completed_date") or (log.approved_date.strftime("%Y-%m-%d") if log.approved_date else (log.scheduled_date.strftime("%Y-%m-%d") if log.scheduled_date else None))
        next_m_date = parsed_d.get("next_due_date") or parsed_d.get("next_maintenance_date") or (log.scheduled_date.strftime("%Y-%m-%d") if log.scheduled_date else (log.schedule.next_maintenance_date.strftime("%Y-%m-%d") if log.schedule else None))
    elif action_val in ["CREATED", "DELETED", "EDITED"]:
        m_date = parsed_d.get("last_maintenance_date") or (log.approved_date.strftime("%Y-%m-%d") if log.approved_date else None)
        next_m_date = parsed_d.get("next_maintenance_date") or (log.scheduled_date.strftime("%Y-%m-%d") if log.scheduled_date else None)
    else:
        m_date = log.approved_date.strftime("%Y-%m-%d") if log.approved_date else (log.scheduled_date.strftime("%Y-%m-%d") if log.scheduled_date else None)
        next_m_date = (log.schedule.next_maintenance_date.strftime("%Y-%m-%d") if log.schedule and log.schedule.next_maintenance_date else None)

    parts_str = _format_parts_used(log.parts_used or parsed_d.get("parts_used"))
    remind_days = parsed_d.get("remind_before_days") if parsed_d.get("remind_before_days") is not None else (log.schedule.remind_before_days if log.schedule and log.schedule.remind_before_days is not None else 3)

    status_val = action_val
    rem_days, rem_display, rem_status = _calculate_remaining_days(
        next_m_date,
        remind_days,
    )

    explicit_remarks = parsed_d.get("remarks") or log.remarks
    if explicit_remarks and str(explicit_remarks).strip() and str(explicit_remarks).strip() != "-":
        exp_str = str(explicit_remarks).strip()
        if exp_str.startswith("Schedule created by") or exp_str.startswith("Schedule updated by") or exp_str.startswith("Schedule deleted by"):
            fallback_needs = parsed_d.get("maintenance_needs") or (log.schedule.maintenance_needs if log.schedule else None)
            final_remarks = str(fallback_needs).strip().upper() if fallback_needs and str(fallback_needs).strip() != "-" else exp_str.upper()
        else:
            final_remarks = exp_str.upper()
    elif parsed_d.get("maintenance_needs") and str(parsed_d.get("maintenance_needs")).strip() != "-":
        final_remarks = str(parsed_d.get("maintenance_needs")).strip().upper()
    elif log.schedule and log.schedule.maintenance_needs and str(log.schedule.maintenance_needs).strip() != "-":
        final_remarks = str(log.schedule.maintenance_needs).strip().upper()
    else:
        final_remarks = "-"

    iso_timestamp = created_at_dt.isoformat() if hasattr(created_at_dt, "isoformat") else str(created_at_dt or "")

    return {
        "id": f"ML-{log.id}",
        "raw_id": log.id,
        "iso_timestamp": iso_timestamp,
        "maintenance_type": "Periodic Maintenance",
        "type_key": "periodic",
        "action": action_val,
        "timestamp": created_at_str,
        "user": user_val,
        "performed_by": user_val,
        "created_by": user_val,
        "record_number": f"ML-{log.id:04d}",
        "machine_id": log.machine.id if log.machine else None,
        "machine_name": log.machine.machine_name if log.machine else "-",
        "title": log.maintenance_name or (log.schedule.maintenance_name if log.schedule else "Periodic Maintenance"),
        "action_taken": "-",
        "completion_date": m_date,
        "supervised_by": log.supervised_by or parsed_d.get("supervised_by") or (log.schedule.supervised_by if log.schedule and log.schedule.supervised_by else "-"),
        "maintenance_needs": parsed_d.get("maintenance_needs") or (log.schedule.maintenance_needs if log.schedule and log.schedule.maintenance_needs else "-"),
        "interval_days": hist_interval,
        "interval_display": interval_disp,
        "remind_before_days": remind_days,
        "remind_before_display": f"{remind_days} Days" if remind_days is not None else "-",
        "maintenance_date": m_date,
        "next_maintenance_date": next_m_date,
        "remaining_days": rem_days,
        "remaining_days_display": rem_display,
        "remaining_days_status": rem_status,
        "downtime_hours": 0,
        "downtime_display": "-",
        "status": status_val,
        "operator_name": "-",
        "approved_by": log.approved_by or user_val,
        "parts_used": parts_str,
        "remarks": final_remarks,
    }


def _fetch_unified_maintenance_data(params):
    """
    Fetches and filters unified maintenance records from MaintenanceSchedule,
    BreakdownMaintenance, and MachineMaintenanceLog.
    """
    mtype = str(params.get("maintenance_type") or "all").strip().lower()
    machine_id = params.get("machine_id")
    machine_name = params.get("machine_name")
    status_filter = str(params.get("status") or "").strip().upper()
    start_date_str = params.get("start_date")
    end_date_str = params.get("end_date")
    search = str(params.get("search") or "").strip().lower()

    # Parse date boundaries if supplied
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.datetime.strptime(str(start_date_str)[:10], "%Y-%m-%d").date()
        except Exception:
            start_date = None
    if end_date_str:
        try:
            end_date = datetime.datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d").date()
        except Exception:
            end_date = None

    unified_records = []

    # 1. Periodic Maintenance Lifecycle Audit Logs (CREATED, UPDATED, COMPLETED)
    if mtype in ["all", "periodic", "completed", "logs", "history", "schedule", "schedules"]:
        log_qs = MachineMaintenanceLog.objects.select_related("machine", "schedule").all()
        if machine_id:
            log_qs = log_qs.filter(machine_id=machine_id)
        if machine_name:
            log_qs = log_qs.filter(machine__machine_name__icontains=machine_name)

        logged_schedule_ids = set()
        for log in log_qs:
            item = _get_log_item(log)
            unified_records.append(item)
            if log.schedule_id:
                logged_schedule_ids.add(log.schedule_id)

        # Include legacy schedules that do not have any MachineMaintenanceLog entries yet
        sched_qs = MaintenanceSchedule.objects.select_related("machine").all()
        if machine_id:
            sched_qs = sched_qs.filter(machine_id=machine_id)
        if machine_name:
            sched_qs = sched_qs.filter(machine__machine_name__icontains=machine_name)

        orphan_sched_qs = sched_qs.exclude(id__in=logged_schedule_ids)
        for sched in orphan_sched_qs:
            item = _get_schedule_item(sched)
            unified_records.append(item)

    # 2. Breakdown Maintenance Records & Lifecycle Audit Logs (CREATED, UPDATED, EDITED, DELETED)
    if mtype in ["all", "breakdown"]:
        bm_log_qs = BreakdownMaintenanceLog.objects.select_related("machine", "breakdown").all()
        if machine_id:
            bm_log_qs = bm_log_qs.filter(machine_id=machine_id)
        if machine_name:
            bm_log_qs = bm_log_qs.filter(machine__machine_name__icontains=machine_name)

        logged_bm_ids = set()
        for b_log in bm_log_qs:
            item = _get_breakdown_log_item(b_log)
            unified_records.append(item)
            if b_log.breakdown_id:
                logged_bm_ids.add(b_log.breakdown_id)

        # Include legacy breakdown records that do not have any BreakdownMaintenanceLog entries yet
        bm_qs = BreakdownMaintenance.objects.select_related("machine").all()
        if machine_id:
            bm_qs = bm_qs.filter(machine_id=machine_id)
        if machine_name:
            bm_qs = bm_qs.filter(machine__machine_name__icontains=machine_name)

        orphan_bm_qs = bm_qs.exclude(id__in=logged_bm_ids)
        for bm in orphan_bm_qs:
            item = _get_breakdown_item(bm)
            unified_records.append(item)

    # In-memory unified filtering
    filtered_records = []
    for r in unified_records:
        # Status Filter
        if status_filter and status_filter != "ALL":
            rec_status = (r.get("status") or "").upper()
            if "," in status_filter:
                statuses = [s.strip().upper() for s in status_filter.split(",")]
                if rec_status not in statuses:
                    continue
            elif rec_status != status_filter:
                continue

        # Date Range Filter (checks maintenance_date or next_maintenance_date)
        rec_date_str = r.get("maintenance_date") or r.get("next_maintenance_date")
        if start_date or end_date:
            if not rec_date_str:
                continue
            try:
                rec_date = datetime.datetime.strptime(str(rec_date_str)[:10], "%Y-%m-%d").date()
                if start_date and rec_date < start_date:
                    continue
                if end_date and rec_date > end_date:
                    continue
            except Exception:
                continue

        # Search Query Filter across key fields
        if search:
            searchable_text = " ".join([
                str(r.get("machine_name") or ""),
                str(r.get("title") or ""),
                str(r.get("action_taken") or ""),
                str(r.get("record_number") or ""),
                str(r.get("id") or ""),
                str(r.get("operator_name") or ""),
                str(r.get("created_by") or ""),
                str(r.get("approved_by") or ""),
                str(r.get("maintenance_needs") or ""),
                str(r.get("parts_used") or ""),
                str(r.get("remarks") or ""),
                str(r.get("status") or ""),
                str(r.get("maintenance_type") or ""),
            ]).lower()
            if search not in searchable_text:
                continue

        filtered_records.append(r)

    # Sort records: newest log / event first (iso_timestamp descending, then raw_id descending)
    def sort_key(item):
        t_str = str(item.get("iso_timestamp") or item.get("timestamp") or item.get("maintenance_date") or "1970-01-01")
        raw_id_val = item.get("raw_id") or 0
        return (t_str, raw_id_val)

    filtered_records.sort(key=sort_key, reverse=True)
    for idx, r in enumerate(filtered_records):
        r["sno"] = idx + 1
    return filtered_records


@api_view(["GET"])
def get_periodic_maintenance_reports(request):
    """
    Returns periodic maintenance records (schedules and completed periodic logs).
    """
    params = request.GET.dict() if hasattr(request.GET, "dict") else dict(request.GET)
    params["maintenance_type"] = "periodic"
    data = _fetch_unified_maintenance_data(params)
    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_breakdown_maintenance_reports(request):
    """
    Returns breakdown maintenance incident records.
    """
    params = request.GET.dict() if hasattr(request.GET, "dict") else dict(request.GET)
    params["maintenance_type"] = "breakdown"
    data = _fetch_unified_maintenance_data(params)
    return Response(data, status=status.HTTP_200_OK)


def _generate_maintenance_workbook(data_payload, report_type="all", get_params=None):
    """
    Core generator returning an HttpResponse with styled Excel content.
    report_type: 'periodic', 'breakdown', or 'all'
    """
    custom_headers = data_payload.get("headers", [])
    custom_rows = data_payload.get("rows", [])

    if report_type == "periodic":
        default_sheet = "Periodic Maintenance"
        default_file_prefix = "Periodic_Maintenance_Report"
        default_title = "SAKTHI LASER TECHNOLOGY - PERIODIC MAINTENANCE REPORT"
    elif report_type == "breakdown":
        default_sheet = "Breakdown Maintenance"
        default_file_prefix = "Breakdown_Maintenance_Report"
        default_title = "SAKTHI LASER TECHNOLOGY - BREAKDOWN MAINTENANCE REPORT"
    else:
        default_sheet = "Maintenance History"
        default_file_prefix = "Maintenance_Report_History"
        default_title = "SAKTHI LASER TECHNOLOGY - UNIFIED MAINTENANCE HISTORY REPORT"

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet(default_sheet)
    worksheet.hide_gridlines(0)

    # -----------------------------
    # STYLES & DESIGN SYSTEM TOKENS
    # -----------------------------
    title_fmt = workbook.add_format({
        "bold": True,
        "font_size": 13,
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

    col_header_right_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#1E293B",
        "bg_color": "#E2E8F0",
        "align": "right",
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

    # Status badge formats
    badge_completed_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#047857",
        "bg_color": "#ECFDF5",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#A7F3D0",
    })

    badge_overdue_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#B91C1C",
        "bg_color": "#FEF2F2",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FECACA",
    })

    badge_pending_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#B45309",
        "bg_color": "#FEF3C7",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FDE68A",
    })

    badge_open_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#1E40AF",
        "bg_color": "#EFF6FF",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#BFDBFE",
    })

    # Maintenance Type Badges
    type_periodic_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#4338CA",
        "bg_color": "#EEF2FF",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#C7D2FE",
    })

    type_breakdown_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#BE123C",
        "bg_color": "#FFF1F2",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FECDD3",
    })

    # Summary category formats
    summary_periodic_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#4338CA",
        "bg_color": "#EEF2FF",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#C7D2FE",
    })

    summary_breakdown_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#BE123C",
        "bg_color": "#FFF1F2",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FECDD3",
    })

    summary_completed_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#047857",
        "bg_color": "#ECFDF5",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#A7F3D0",
    })

    summary_pending_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#B45309",
        "bg_color": "#FEF3C7",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FDE68A",
    })

    summary_downtime_fmt = workbook.add_format({
        "bold": True,
        "font_size": 10,
        "font_color": "#7E22CE",
        "bg_color": "#FAF5FF",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#E9D5FF",
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

    # Action badge formats
    badge_action_created_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#047857",
        "bg_color": "#ECFDF5",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#A7F3D0",
    })

    badge_action_updated_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#854D0E",
        "bg_color": "#FEF9C3",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FDE047",
    })

    badge_action_edited_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#C2410C",
        "bg_color": "#FFEDD5",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FED7AA",
    })

    badge_action_deleted_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#BE123C",
        "bg_color": "#FFE4E6",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#FECDD3",
    })

    badge_action_completed_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#047857",
        "bg_color": "#ECFDF5",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#A7F3D0",
    })

    badge_action_scheduled_fmt = workbook.add_format({
        "bold": True,
        "font_size": 9,
        "font_color": "#4338CA",
        "bg_color": "#EEF2FF",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        "border_color": "#C7D2FE",
    })

    # Available Column Specs
    ALL_COLUMN_SPECS = {
        "sno": {"header": "SL.NO", "header_fmt": col_header_fmt, "width": 8, "align": "center"},
        "action": {"header": "EVENT / ACTION", "header_fmt": col_header_fmt, "width": 16, "align": "action_badge"},
        "timestamp": {"header": "DATE & TIME", "header_fmt": col_header_fmt, "width": 18, "align": "center"},
        "performed_by": {"header": "PERFORMED BY", "header_fmt": col_header_left_fmt, "width": 18, "align": "left"},
        "maintenance_type": {"header": "TYPE", "header_fmt": col_header_fmt, "width": 20, "align": "type_badge"},
        "record_number": {"header": "RECORD NO.", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "maintenance_date": {"header": "DATE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "machine_name": {"header": "MACHINE NAME", "header_fmt": col_header_left_fmt, "width": 24, "align": "left"},
        "title": {"header": "SCHEDULE NAME / TASK", "header_fmt": col_header_left_fmt, "width": 28, "align": "left"},
        "supervised_by": {"header": "SUPERVISED BY", "header_fmt": col_header_left_fmt, "width": 20, "align": "left"},
        "action_taken": {"header": "ACTION TAKEN", "header_fmt": col_header_left_fmt, "width": 28, "align": "left"},
        "completion_date": {"header": "COMPLETION DATE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "status": {"header": "STATUS", "header_fmt": col_header_fmt, "width": 16, "align": "status_badge"},
        "interval_display": {"header": "INTERVAL", "header_fmt": col_header_fmt, "width": 14, "align": "center"},
        "remind_before_display": {"header": "REMIND BEFORE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "remind_before_days": {"header": "REMIND BEFORE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "next_maintenance_date": {"header": "NEXT DUE DATE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "remaining_days_display": {"header": "REMAINING DAYS", "header_fmt": col_header_fmt, "width": 18, "align": "center"},
        "downtime_display": {"header": "DOWNTIME", "header_fmt": col_header_fmt, "width": 14, "align": "center"},
        "operator_name": {"header": "OPERATOR", "header_fmt": col_header_left_fmt, "width": 18, "align": "left"},
        "parts_used": {"header": "PARTS USED", "header_fmt": col_header_left_fmt, "width": 28, "align": "left"},
        "created_by": {"header": "CREATED BY", "header_fmt": col_header_left_fmt, "width": 16, "align": "left"},
        "approved_by": {"header": "APPROVED BY", "header_fmt": col_header_left_fmt, "width": 16, "align": "left"},
        "maintenance_needs": {"header": "MAINTENANCE NEEDS / EQUIPMENT", "header_fmt": col_header_left_fmt, "width": 30, "align": "left"},
        "shift": {"header": "SHIFT", "header_fmt": col_header_fmt, "width": 12, "align": "center"},
        "supervisor": {"header": "SUPERVISOR", "header_fmt": col_header_left_fmt, "width": 20, "align": "left"},
        "breakdown_type": {"header": "BREAKDOWN TYPE", "header_fmt": col_header_left_fmt, "width": 22, "align": "left"},
        "affected_equipment": {"header": "AFFECTED EQUIPMENT", "header_fmt": col_header_left_fmt, "width": 24, "align": "left"},
        "breakdown_date": {"header": "BREAKDOWN DATE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "breakdown_time": {"header": "BREAKDOWN TIME", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "maintenance_start_time": {"header": "MAINTENANCE START TIME", "header_fmt": col_header_fmt, "width": 22, "align": "center"},
        "maintenance_complete_time": {"header": "MAINTENANCE COMPLETE TIME", "header_fmt": col_header_fmt, "width": 24, "align": "center"},
        "restart_time": {"header": "RESTART TIME", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "breakdown_complete_date": {"header": "COMPLETION DATE", "header_fmt": col_header_fmt, "width": 16, "align": "center"},
        "details": {"header": "DETAILS & CHANGES", "header_fmt": col_header_left_fmt, "width": 36, "align": "left"},
        "remarks": {"header": "REMARKS", "header_fmt": col_header_left_fmt, "width": 30, "align": "left"},
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

    report_title_custom = data_payload.get("report_title")
    title_text = (
        f"SAKTHI LASER TECHNOLOGY - {str(report_title_custom).upper()}"
        if report_title_custom
        else default_title
    )
    worksheet.merge_range(f"A1:{last_col_letter}1", title_text, title_fmt)
    worksheet.set_row(0, 24)
    now_local = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else datetime.datetime.now()
    worksheet.merge_range(f"A2:{last_col_letter}2", f"Generated on {now_local.strftime('%d-%b-%Y %I:%M %p')}", subtitle_fmt)
    worksheet.set_row(1, 16)

    curr_row = 3

    # Write Headers
    for col_idx, (f_key, spec) in enumerate(active_columns):
        worksheet.write(curr_row, col_idx, spec["header"], spec["header_fmt"])
        worksheet.set_column(col_idx, col_idx, spec["width"])

    worksheet.set_row(curr_row, 20)
    curr_row += 1
    start_data_row = curr_row + 1

    # Prepare data rows
    data_rows = []
    if custom_rows and isinstance(custom_rows, list):
        for idx, r in enumerate(custom_rows):
            dt_h = 0.0
            if r.get("downtime_hours") is not None:
                try:
                    dt_h = float(r.get("downtime_hours"))
                except (ValueError, TypeError):
                    dt_h = 0.0
            elif r.get("total_downtime_hours") is not None:
                try:
                    dt_h = float(r.get("total_downtime_hours"))
                except (ValueError, TypeError):
                    dt_h = 0.0
            elif r.get("downtime_display") and ":" in str(r.get("downtime_display")):
                try:
                    parts = str(r.get("downtime_display")).split(":")
                    dt_h = int(parts[0]) + (int(parts[1]) / 60.0)
                except Exception:
                    dt_h = 0.0

            downtime_str = r.get("downtime_display") or _format_downtime(dt_h)
            parts_str = _format_parts_used(r.get("parts_used"))

            data_rows.append({
                "sno": idx + 1,
                "action": r.get("action") or ("SCHEDULED" if r.get("type_key") == "periodic" else "INCIDENT"),
                "timestamp": r.get("timestamp") or r.get("maintenance_date") or "-",
                "performed_by": r.get("performed_by") or r.get("user") or r.get("created_by") or "-",
                "maintenance_type": r.get("maintenance_type") or ("Periodic" if r.get("type_key") == "periodic" else "Breakdown"),
                "type_key": r.get("type_key") or "periodic",
                "record_number": r.get("record_number") or "-",
                "maintenance_date": r.get("maintenance_date") or r.get("breakdown_date") or "-",
                "machine_name": r.get("machine_name") or "-",
                "title": r.get("title") or "-",
                "supervised_by": r.get("supervised_by") or r.get("supervisor") or "-",
                "supervisor": r.get("supervisor") or r.get("supervised_by") or "-",
                "shift": r.get("shift") or "-",
                "breakdown_type": r.get("breakdown_type") or r.get("title") or "-",
                "affected_equipment": r.get("affected_equipment") or "-",
                "breakdown_date": r.get("breakdown_date") or r.get("maintenance_date") or "-",
                "breakdown_time": r.get("breakdown_time") or "-",
                "maintenance_start_time": r.get("maintenance_start_time") or "-",
                "maintenance_complete_time": r.get("maintenance_complete_time") or "-",
                "restart_time": r.get("restart_time") or "-",
                "breakdown_complete_date": r.get("breakdown_complete_date") or r.get("completion_date") or "-",
                "action_taken": r.get("action_taken") or "-",
                "completion_date": r.get("completion_date") or r.get("breakdown_complete_date") or "-",
                "status": (r.get("status") or "PENDING").upper(),
                "interval_display": r.get("interval_display") or "-",
                "remind_before_display": r.get("remind_before_display") or (f"{r.get('remind_before_days')} Days" if r.get("remind_before_days") is not None else "-"),
                "remind_before_days": r.get("remind_before_days"),
                "next_maintenance_date": r.get("next_maintenance_date") or "-",
                "remaining_days_display": r.get("remaining_days_display") or "-",
                "downtime_display": downtime_str,
                "downtime_hours": dt_h,
                "operator_name": r.get("operator_name") or "-",
                "parts_used": parts_str,
                "created_by": r.get("created_by") or "-",
                "approved_by": r.get("approved_by") or "-",
                "maintenance_needs": r.get("maintenance_needs") or "-",
                "details": r.get("details") or r.get("remarks") or "-",
                "remarks": r.get("remarks") or "-",
            })
    else:
        # Fetch from unified database
        params = dict(get_params or {})
        if report_type == "periodic":
            params["maintenance_type"] = "periodic"
        elif report_type == "breakdown":
            params["maintenance_type"] = "breakdown"
        raw_records = _fetch_unified_maintenance_data(params)
        for idx, r in enumerate(raw_records):
            remind_display = r.get("remind_before_display") or (f"{r.get('remind_before_days')} Days" if r.get("remind_before_days") is not None else "-")
            data_rows.append({
                "sno": idx + 1,
                "action": r.get("action") or ("SCHEDULED" if r.get("type_key") == "periodic" else "INCIDENT"),
                "timestamp": r.get("timestamp") or r.get("maintenance_date") or "-",
                "performed_by": r.get("performed_by") or r.get("user") or r.get("created_by") or "-",
                "maintenance_type": r.get("maintenance_type") or "Periodic",
                "type_key": r.get("type_key") or "periodic",
                "record_number": r.get("record_number") or "-",
                "maintenance_date": r.get("maintenance_date") or r.get("breakdown_date") or "-",
                "machine_name": r.get("machine_name") or "-",
                "title": r.get("title") or "-",
                "supervised_by": r.get("supervised_by") or r.get("supervisor") or "-",
                "supervisor": r.get("supervisor") or r.get("supervised_by") or "-",
                "shift": r.get("shift") or "-",
                "breakdown_type": r.get("breakdown_type") or r.get("title") or "-",
                "affected_equipment": r.get("affected_equipment") or "-",
                "breakdown_date": r.get("breakdown_date") or r.get("maintenance_date") or "-",
                "breakdown_time": r.get("breakdown_time") or "-",
                "maintenance_start_time": r.get("maintenance_start_time") or "-",
                "maintenance_complete_time": r.get("maintenance_complete_time") or "-",
                "restart_time": r.get("restart_time") or "-",
                "breakdown_complete_date": r.get("breakdown_complete_date") or r.get("completion_date") or "-",
                "action_taken": r.get("action_taken") or "-",
                "completion_date": r.get("completion_date") or r.get("breakdown_complete_date") or "-",
                "status": (r.get("status") or "PENDING").upper(),
                "interval_display": r.get("interval_display") or "-",
                "remind_before_display": remind_display,
                "remind_before_days": r.get("remind_before_days"),
                "next_maintenance_date": r.get("next_maintenance_date") or "-",
                "remaining_days_display": r.get("remaining_days_display") or "-",
                "downtime_display": r.get("downtime_display") or "-",
                "downtime_hours": r.get("downtime_hours") or 0,
                "operator_name": r.get("operator_name") or "-",
                "parts_used": r.get("parts_used") or "-",
                "created_by": r.get("created_by") or "-",
                "approved_by": r.get("approved_by") or "-",
                "maintenance_needs": r.get("maintenance_needs") or "-",
                "details": r.get("details") or r.get("remarks") or "-",
                "remarks": r.get("remarks") or "-",
            })

    # Render Data Rows
    for r in data_rows:
        row_fmt = cell_text_fmt
        for col_idx, (f_key, spec) in enumerate(active_columns):
            val = r.get(f_key, "-")
            align = spec.get("align", "left")

            if align == "center":
                worksheet.write(curr_row, col_idx, str(val) if val is not None else "-", cell_center_fmt)
            elif align == "action_badge":
                act = str(val).upper()
                if act in ["COMPLETED", "APPROVED", "UPDATED", "DONE"]:
                    worksheet.write(curr_row, col_idx, "UPDATED", badge_action_updated_fmt)
                elif act == "CREATED":
                    worksheet.write(curr_row, col_idx, "CREATED", badge_action_created_fmt)
                elif act in ["EDITED", "MODIFIED"]:
                    worksheet.write(curr_row, col_idx, "EDITED", badge_action_edited_fmt)
                elif act in ["DELETED", "CANCELLED"]:
                    worksheet.write(curr_row, col_idx, "DELETED", badge_action_deleted_fmt)
                else:
                    worksheet.write(curr_row, col_idx, act, badge_action_scheduled_fmt)
            elif align == "type_badge":
                is_periodic = r.get("type_key") == "periodic" or "periodic" in str(val).lower()
                b_fmt = type_periodic_fmt if is_periodic else type_breakdown_fmt
                worksheet.write(curr_row, col_idx, "PERIODIC" if is_periodic else "BREAKDOWN", b_fmt)
            elif align == "status_badge":
                st = str(val).upper()
                if st in ["COMPLETED", "CLOSED", "APPROVED"]:
                    worksheet.write(curr_row, col_idx, st, badge_completed_fmt)
                elif st in ["OVERDUE"]:
                    worksheet.write(curr_row, col_idx, st, badge_overdue_fmt)
                elif st in ["PENDING", "DUE"]:
                    worksheet.write(curr_row, col_idx, st, badge_pending_fmt)
                elif st in ["OPEN"]:
                    worksheet.write(curr_row, col_idx, st, badge_open_fmt)
                elif st == "CREATED":
                    worksheet.write(curr_row, col_idx, st, badge_action_created_fmt)
                elif st == "UPDATED":
                    worksheet.write(curr_row, col_idx, st, badge_action_updated_fmt)
                else:
                    worksheet.write(curr_row, col_idx, st, cell_center_fmt)
            else:
                worksheet.write(curr_row, col_idx, str(val) if val is not None else "-", row_fmt)

        worksheet.set_row(curr_row, 18)
        curr_row += 1

    # Add Summary Rows (only for unified reports)
    if data_rows and len(data_rows) > 0:
        if report_type in ["periodic", "breakdown"]:
            pass  # Stats/summary rows removed for periodic and breakdown maintenance exports as requested
        else:
            # Unified summary
            curr_row += 1
            periodic_count = sum(1 for r in data_rows if r.get("type_key") == "periodic" or "periodic" in str(r.get("maintenance_type", "")).lower())
            breakdown_count = sum(1 for r in data_rows if r.get("type_key") == "breakdown" or "breakdown" in str(r.get("maintenance_type", "")).lower())
            completed_count = sum(1 for r in data_rows if str(r.get("status", "")).upper() in ["COMPLETED", "CLOSED"])
            pending_count = sum(1 for r in data_rows if str(r.get("status", "")).upper() in ["PENDING", "OPEN", "OVERDUE", "DUE"])

            total_downtime_hours = sum(float(r.get("downtime_hours") or 0) for r in data_rows)
            total_dt_mins = int(round(total_downtime_hours * 60))
            dt_h = total_dt_mins // 60
            dt_m = total_dt_mins % 60
            total_dt_display = f"{dt_h:02d}:{dt_m:02d}" if total_dt_mins > 0 else "-"

            summary_categories = [
                ("TOTAL PERIODIC", f"{periodic_count} Schedule{'s' if periodic_count != 1 else ''}", "-", summary_periodic_fmt),
                ("TOTAL BREAKDOWN", f"{breakdown_count} Incident{'s' if breakdown_count != 1 else ''}", total_dt_display, summary_breakdown_fmt),
                ("TOTAL COMPLETED / CLOSED", f"{completed_count} Resolved", "-", summary_completed_fmt),
                ("TOTAL PENDING / OPEN", f"{pending_count} Attention Needed", "-", summary_pending_fmt),
                ("TOTAL DOWNTIME", f"{breakdown_count} Breakdown Incident{'s' if breakdown_count != 1 else ''}", total_dt_display, summary_downtime_fmt),
            ]
            for label, desc_val, dt_val, cat_fmt in summary_categories:
                for c_idx, (f_key, spec) in enumerate(active_columns):
                    if c_idx == 0:
                        worksheet.write(curr_row, c_idx, label, cat_fmt)
                    elif f_key in ["machine_name", "title"]:
                        if f_key == "machine_name" or (f_key == "title" and not any(k == "machine_name" for k, _ in active_columns)):
                            worksheet.write(curr_row, c_idx, desc_val, cat_fmt)
                        else:
                            worksheet.write(curr_row, c_idx, "", cat_fmt)
                    elif f_key in ["downtime_display", "downtime_hours"]:
                        worksheet.write(curr_row, c_idx, dt_val, cat_fmt)
                    else:
                        worksheet.write(curr_row, c_idx, "", cat_fmt)
                worksheet.set_row(curr_row, 20)
                curr_row += 1

    workbook.close()
    output.seek(0)

    filename = f"{default_file_prefix}_{now_local.strftime('%Y-%m-%d')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET", "POST"])
def export_periodic_maintenance_excel(request):
    """
    Dedicated endpoint for exporting Periodic Maintenance Excel reports.
    """
    data_payload = request.data if request.method == "POST" else {}
    return _generate_maintenance_workbook(data_payload, report_type="periodic", get_params=request.GET)


@api_view(["GET", "POST"])
def export_breakdown_maintenance_excel(request):
    """
    Dedicated endpoint for exporting Breakdown Maintenance Excel reports.
    """
    data_payload = request.data if request.method == "POST" else {}
    return _generate_maintenance_workbook(data_payload, report_type="breakdown", get_params=request.GET)

