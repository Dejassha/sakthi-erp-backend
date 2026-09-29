from rest_framework import serializers
from api.models import *

# QA Machine Details Serial
class qa_machine_detailsSerializer(serializers.ModelSerializer):
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    runtime = serializers.SerializerMethodField()

    class Meta:
        model = qa_machine_details
        fields = [
            "id",
            "machine_name",
            "date",
            "start_time",
            "end_time",
            "runtime",
            "operator",
            "gas_type",
        ]

    def get_start_time(self, obj):
        if obj.start_time is not None:
            total_seconds = int(obj.start_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return None

    def get_end_time(self, obj):
        if obj.end_time is not None:
            total_seconds = int(obj.end_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return None

    def get_runtime(self, obj):
        if obj.runtime is not None:
            total_seconds = int(obj.runtime.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return None


# Qa Serial
class qa_detailsSerializer(serializers.ModelSerializer):
    # Relational logs from foreign key (related_name="qa_machine_details")
    machine_logs = qa_machine_detailsSerializer(
        many=True, read_only=True, source="qa_machine_details"
    )

    material_id = serializers.IntegerField(source="material.id", read_only=True)

    class Meta:
        model = qa_details
        fields = "__all__"

    def get_material_id(self, obj):
        return obj.material.id if obj.material else None


# Accounts Serial
class acc_detailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = acc_details
        fields = "__all__"


# Programer Serial
class programer_detailsSerializer(serializers.ModelSerializer):
    total_planned_hours = serializers.SerializerMethodField()
    material_id = serializers.IntegerField(source="material.id", read_only=True)
    product_id = serializers.IntegerField(source="material.product.id", read_only=True)
    inward_slip_number = serializers.CharField(source="material.product.inward_slip_number", read_only=True)
    job_type = serializers.CharField(source="material.product.job_type", read_only=True)
    company_name = serializers.CharField(source="material.product.company_name", read_only=True)
    customer_name = serializers.CharField(source="material.product.customer_name", read_only=True)
    mat_type = serializers.CharField(source="material.mat_type", read_only=True)
    mat_grade = serializers.CharField(source="material.mat_grade", read_only=True)
    uid_no = serializers.CharField(source="material.uid_no", read_only=True)
    heat_no = serializers.CharField(source="material.heat_no", read_only=True)
    thick = serializers.DecimalField(source="material.thick", max_digits=15, decimal_places=3, read_only=True)
    width = serializers.DecimalField(source="material.width", max_digits=15, decimal_places=3, read_only=True)
    length = serializers.DecimalField(source="material.length", max_digits=15, decimal_places=3, read_only=True)
    quantity = serializers.DecimalField(source="material.quantity", max_digits=15, decimal_places=3, read_only=True)
    total_weight = serializers.DecimalField(source="material.total_weight", max_digits=15, decimal_places=3, read_only=True)

    class Meta:
        model = programer_details
        fields = "__all__"

    def get_total_planned_hours(self, obj):
        if obj.total_planned_hours is not None:
            total_seconds = int(obj.total_planned_hours.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return None


# Material
class product_materialSerializer(serializers.ModelSerializer):

    class Meta:
        model = product_material
        fields = "__all__"


# Inward Details Serializer
class product_detailsSerializer(serializers.ModelSerializer):
    materials = product_materialSerializer(
        many=True, read_only=True, source="product_material_set"
    )

    class Meta:
        model = product_details
        fields = "__all__"


