from rest_framework import serializers
from api.models import *

class InventoryPartNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryPartName
        fields = "__all__"


class InventoryPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryPurpose
        fields = "__all__"


class InventoryPartSerializer(serializers.ModelSerializer):
    machine_name = serializers.ReadOnlyField(source="machine.machine_name", allow_null=True)
    item_name = serializers.ReadOnlyField(source="part_name")
    rate_history = serializers.SerializerMethodField()

    class Meta:
        model = InventoryPart
        fields = [
            "id",
            "spare_id",
            "item_code",
            "part_name",
            "item_name",
            "batch_number",
            "machine",
            "machine_name",
            "stock_quantity",
            "available_quantity",
            "used_quantity",
            "min_stock_quantity",
            "unit",
            "purchase_date",
            "bought_from",
            "purchase_price",
            "remarks",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "rate_history",
        ]

    def get_rate_history(self, obj):
        rates_qs = obj.rates.order_by('-created_at').values_list('rate', flat=True)
        seen = set()
        result = []
        for r in rates_qs:
            val = float(r)
            if val not in seen:
                seen.add(val)
                result.append(val)
        return result


class InventoryUsageSerializer(serializers.ModelSerializer):
    part_name = serializers.ReadOnlyField(source="part.part_name")
    machine_name = serializers.ReadOnlyField(source="machine.machine_name", allow_null=True)

    class Meta:
        model = InventoryUsage
        fields = [
            "id",
            "part",
            "part_name",
            "batch_number",
            "machine",
            "machine_name",
            "used_quantity",
            "used_by",
            "used_hours",
            "used_date",
            "remaining_stock",
            "remarks",
            "use_new_quantity",
            "created_by",
            "created_at",
        ]


class PendingMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingMaterial
        fields = [
            "id",
            "part_name",
            "requested_quantity",
            "available_quantity",
            "requested_by",
            "request_date",
            "priority",
            "status",
            "remarks",
            "created_at",
            "updated_at",
        ]


class InventoryHistorySerializer(serializers.ModelSerializer):
    spare_id = serializers.SerializerMethodField()
    item_code = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()
    min_stock_quantity = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()

    class Meta:
        model = InventoryHistory
        fields = [
            "id",
            "part",
            "part_name",
            "batch_number",
            "spare_id",
            "item_code",
            "action",
            "quantity",
            "available_quantity",
            "min_stock_quantity",
            "unit",
            "purchase_price",
            "status",
            "machine_name",
            "user",
            "remarks",
            "created_at",
        ]

    def get_spare_id(self, obj):
        if obj.part and obj.part.spare_id:
            return obj.part.spare_id
        if obj.part_id:
            return f"SP-{str(obj.part_id).zfill(3)}"
        return "-"

    def get_item_code(self, obj):
        if obj.part and obj.part.item_code:
            return obj.part.item_code
        return "-"

    def get_available_quantity(self, obj):
        if obj.part and obj.part.available_quantity is not None:
            return float(obj.part.available_quantity)
        return None

    def get_min_stock_quantity(self, obj):
        if obj.part and obj.part.min_stock_quantity is not None:
            return float(obj.part.min_stock_quantity)
        return None

    def get_status(self, obj):
        if obj.part and obj.part.status:
            return obj.part.status
        return "-"

    def get_unit(self, obj):
        if obj.part and obj.part.unit:
            return obj.part.unit
        return "pcs"


