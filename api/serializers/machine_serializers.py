from rest_framework import serializers
from api.models import *

class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    machine_name = serializers.ReadOnlyField(source="machine.machine_name")
    remaining_days = serializers.SerializerMethodField()
    remaining_days_display = serializers.SerializerMethodField()
    remaining_days_status = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceSchedule
        fields = "__all__"

    def _get_rem(self, obj):
        if not hasattr(obj, "_cached_rem_days"):
            obj._cached_rem_days = obj.remaining_days()
        return obj._cached_rem_days

    def get_remaining_days(self, obj):
        result = self._get_rem(obj)
        return result.get("value") if isinstance(result, dict) else result

    def get_remaining_days_display(self, obj):
        result = self._get_rem(obj)
        return result.get("display") if isinstance(result, dict) else str(result)

    def get_remaining_days_status(self, obj):
        result = self._get_rem(obj)
        return result.get("status") if isinstance(result, dict) else "none"


# Machine Details
class MachineSerializer(serializers.ModelSerializer):
    maintenance_schedules = MaintenanceScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = Machine
        fields = [
            "id",
            "machine_name",
            "does_need_gas",
            "created_by",
            "created_at",
            "maintenance_schedules",
        ]


class MachineMaintenanceLogSerializer(serializers.ModelSerializer):
    machine_name = serializers.ReadOnlyField(source="machine.machine_name")

    class Meta:
        model = MachineMaintenanceLog
        fields = [
            "id",
            "machine",
            "schedule",
            "machine_name",
            "maintenance_name",
            "action",
            "scheduled_date",
            "approved_date",
            "status",
            "approved_by",
            "performed_by",
            "supervised_by",
            "parts_used",
            "action_details",
            "remarks",
            "created_at",
        ]


class BreakdownMaintenanceSerializer(serializers.ModelSerializer):
    machine_name = serializers.ReadOnlyField(source="machine.machine_name", allow_null=True)
    machine_id = serializers.ReadOnlyField(source="machine.id", allow_null=True)
    mean_time = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = BreakdownMaintenance
        fields = [
            "id",
            "record_number",
            "breakdown_date",
            "shift",
            "machine",
            "machine_name",
            "machine_id",
            "affected_equipment",
            "operator_name",
            "supervisor",
            "breakdown_time",
            "breakdown_type",
            "maintenance_start_time",
            "maintenance_complete_time",
            "restart_time",
            "breakdown_complete_date",
            "total_downtime_hours",
            "mean_time",
            "status",
            "created_by",
            "remarks",
            "created_at",
        ]

    def get_status(self, obj):
        if obj.restart_time or obj.maintenance_complete_time:
            return "CLOSED"
        return "OPEN"

    def validate(self, attrs):
        bd_date = attrs.get("breakdown_date") or (self.instance.breakdown_date if self.instance else None)
        bd_comp_date = attrs.get("breakdown_complete_date") or (self.instance.breakdown_complete_date if self.instance else None)
        if bd_date and bd_comp_date and bd_comp_date < bd_date:
            raise serializers.ValidationError(
                {"breakdown_complete_date": "Breakdown completion date cannot be before breakdown date."}
            )
        return attrs

    def get_mean_time(self, obj):
        if not obj.affected_equipment:
            return "0"

        eq = obj.affected_equipment.strip().lower()
        if not eq:
            return "0"

        # Cache grouped breakdown entries across queryset serialization to prevent N+1 queries
        groups = self.context.get("breakdown_mean_time_cache") if isinstance(self.context, dict) else None
        if groups is None:
            root = getattr(self, "root", None)
            instances = getattr(root, "instance", None) if root else None
            if isinstance(instances, (list, tuple)) or hasattr(instances, "__iter__"):
                records_list = list(instances)
            else:
                records_list = None

            if records_list is not None and len(records_list) > 1:
                groups = {}
                import datetime
                for r in records_list:
                    r_eq = (r.affected_equipment or "").strip().lower()
                    if not r_eq:
                        continue
                    m_id = r.machine_id if hasattr(r, "machine_id") else (r.machine.id if r.machine else None)
                    k = (m_id, r_eq)
                    if k not in groups:
                        groups[k] = []
                    bd_d = r.breakdown_date
                    if bd_d:
                        bd_t = r.breakdown_time or datetime.time(0, 0)
                        groups[k].append({"id": r.id, "dt": datetime.datetime.combine(bd_d, bd_t)})
                for k in groups:
                    groups[k].sort(key=lambda e: e["dt"])
                if isinstance(self.context, dict):
                    self.context["breakdown_mean_time_cache"] = groups

        m_key_id = obj.machine_id if hasattr(obj, "machine_id") else (obj.machine.id if obj.machine else None)
        lookup_key = (m_key_id, eq)
        if groups and lookup_key in groups:
            entries = groups[lookup_key]
        else:
            if obj.machine:
                qs = BreakdownMaintenance.objects.filter(
                    machine=obj.machine,
                    affected_equipment__iexact=eq
                )
            else:
                qs = BreakdownMaintenance.objects.filter(
                    machine__isnull=True,
                    affected_equipment__iexact=eq
                )
            if qs.count() <= 1:
                return "0"
            import datetime
            entries = []
            for r in qs:
                if r.breakdown_date:
                    bd_t = r.breakdown_time or datetime.time(0, 0)
                    entries.append({"id": r.id, "dt": datetime.datetime.combine(r.breakdown_date, bd_t)})
            entries.sort(key=lambda e: e["dt"])

        if len(entries) <= 1:
            return "0"

        current_index = next((i for i, e in enumerate(entries) if e["id"] == obj.id), -1)
        if current_index <= 0:
            return "0"

        diff = entries[current_index]["dt"] - entries[current_index - 1]["dt"]
        diff_minutes = diff.total_seconds() / 60.0
        if diff_minutes <= 0:
            return "0"

        days = int(diff_minutes // 1440)
        hours = int((diff_minutes % 1440) // 60)
        minutes = int(round(diff_minutes % 60))

        days_label = "day" if days == 1 else "days"
        hours_label = "hour" if hours == 1 else "hours"
        minutes_label = "minute" if minutes == 1 else "minutes"

        return f"{days} {days_label}, {hours} {hours_label}, {minutes} {minutes_label}"


class GasDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GasDetails
        fields = "__all__"


class BreakdownMaintenanceLogSerializer(serializers.ModelSerializer):
    machine_name = serializers.ReadOnlyField(source="machine.machine_name", allow_null=True)

    class Meta:
        model = BreakdownMaintenanceLog
        fields = "__all__"


