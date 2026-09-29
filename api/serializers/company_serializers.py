from rest_framework import serializers
from api.models import *

# Company
class companySerializer(serializers.ModelSerializer):
    class Meta:
        model = company
        fields = [
            "id",
            "company_name",
            "customer_name",
            "contact_no",
        ]


# Machine Operator
class machine_operatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = machine_operator
        fields = [
            "id",
            "operator_name",
        ]


# Material Type
class material_typeSerializer(serializers.ModelSerializer):
    class Meta:
        model = material_type
        fields = [
            "id",
            "material_name",
            "density_value",
        ]


