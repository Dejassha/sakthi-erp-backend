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

# Operators API'S
@api_view(["POST"])
def add_operator(request):
    try:
        data = request.data
        operator_name = data.get("operator_name")
        created_by = data.get("created_by")

        # Validation
        if not operator_name:
            return Response(
                {"status": False, "message": "Operator name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not created_by:
            return Response(
                {"status": False, "error": "Login required: 'created_by' is missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        operator_obj = machine_operator.objects.create(
            operator_name=operator_name,
            created_by=created_by,
        )
        return Response(
            {
                "msg": "Operator created successfully",
                "operator_name": operator_name,
                "Created_by": created_by,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as e:
        print("? Error in add_operator:", str(e))
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
def get_operator(request):
    try:
        operators = machine_operator.objects.all()
        serializer = machine_operatorSerializer(operators, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"msg": f"Error fetching operators: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
def update_operator(request, operator_id):
    try:
        operator = machine_operator.objects.get(id=operator_id)

        operator_name = request.data.get("operator_name")
        created_by = request.data.get("created_by")

        if not operator_name:
            return Response(
                {"status": False, "message": "Operator name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not created_by:
            return Response(
                {"status": False, "error": "Login required: 'created_by' is missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        operator.operator_name = operator_name
        operator.created_by = created_by
        operator.save()

        return Response(
            {
                "status": True,
                "message": "Operator updated successfully",
                "operator_name": operator.operator_name,
                "Created_by": created_by,
            },
            status=status.HTTP_200_OK,
        )

    except machine_operator.DoesNotExist:
        return Response(
            {"status": False, "message": "Operator not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["DELETE"])
def delete_operator(request, operator_id):
    try:
        operator = machine_operator.objects.get(id=operator_id)
        operator.delete()

        return Response(
            {"status": True, "message": "Operator deleted successfully"},
            status=status.HTTP_200_OK,
        )

    except machine_operator.DoesNotExist:
        return Response(
            {"status": False, "message": "Operator not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


# Companies API'S
@api_view(["GET"])
def get_companies(request):
    company_data = company.objects.all()
    get = []
    for comp in company_data:
        get.append(
            {
                "id": comp.id,
                "company_name": comp.company_name,
                "customer_name": comp.customer_name,
                "contact_no": comp.contact_no,
            }
        )
    return Response(get)


@api_view(["POST"])
def add_company(request):
    try:
        data = request.data
        company_name = data.get("company_name")
        customer_name = data.get("customer_name")
        contact_no = data.get("contact_no")

        # ? Validation
        if not company_name:
            return Response(
                {"status": False, "message": "Company name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ? Create the company record
        new_company = company.objects.create(
            company_name=company_name,
            customer_name=customer_name,
            contact_no=contact_no,
            created_by=data.get("created_by"),
        )

        return Response(
            {
                "status": True,
                "msg": f"Company added successfully by {new_company.created_by}",
                "data": {
                    "id": new_company.id,
                    "company_name": new_company.company_name,
                    "customer_name": new_company.customer_name,
                    "contact_no": new_company.contact_no,
                    "created_by": new_company.created_by,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["PUT"])
def update_company(request, pk):
    try:
        comp = company.objects.get(id=pk)
    except company.DoesNotExist:
        return Response(
            {"status": False, "message": "Company not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    data = request.data
    company_name = data.get("company_name")

    if not company_name:
        return Response(
            {
                "status": False,
                "message": "company_name are required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        comp.company_name = company_name
        comp.customer_name = data.get("customer_name", comp.customer_name)
        comp.contact_no = data.get("contact_no", comp.contact_no)
        comp.created_by = data.get("created_by", comp.created_by)
        comp.save()

        return Response(
            {
                "message": f"Company updated successfully by {comp.created_by}",
                "company": {
                    "id": comp.id,
                    "company_name": comp.company_name,
                    "customer_name": comp.customer_name,
                    "contact_no": comp.contact_no,
                    "created_by": comp.created_by,
                },
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["DELETE"])
def delete_company(request, pk):
    try:
        comp = company.objects.get(id=pk)
    except company.DoesNotExist:
        return Response(
            {"status": False, "message": "Company not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        comp.delete()
        return Response(
            {"status": True, "message": "Company deleted successfully"},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


# Material Type
@api_view(["GET"])
def get_material_type(request):
    types = material_type.objects.all().order_by("material_name")
    serializer = material_typeSerializer(types, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
def add_material_type(request):
    try:
        created_by_username = request.data.get("created_by")
        if not created_by_username:
            return Response(
                {"error": "Login required: 'created_by' is missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            created_user = All_User.objects.get(username=created_by_username)
        except All_User.DoesNotExist:
            return Response(
                {"error": f"User '{created_by_username}' not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        material_name = request.data.get("material_name")
        density_value = request.data.get("density_value")

        if not material_name or density_value is None:
            return Response(
                {"error": "material_name and density_value are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = material_type.objects.create(
            material_name=material_name,
            density_value=float(density_value),
            created_by=created_by_username,
        )

        serializer = material_typeSerializer(instance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT"])
def update_material_type(request, pk):
    try:
        instance = material_type.objects.get(id=pk)
    except material_type.DoesNotExist:
        return Response(
            {"error": "Material type not found"}, status=status.HTTP_404_NOT_FOUND
        )

    created_by_username = request.data.get("created_by")
    if not created_by_username:
        return Response(
            {"error": "Login required: 'created_by' is missing."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        All_User.objects.get(username=created_by_username)
        instance.created_by = created_by_username
    except All_User.DoesNotExist:
        return Response(
            {"error": f"User '{created_by_username}' not found"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = material_typeSerializer(instance, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
def delete_material_type(request, pk):
    try:
        instance = material_type.objects.get(id=pk)
    except material_type.DoesNotExist:
        return Response(
            {"error": "Material type not found"}, status=status.HTTP_404_NOT_FOUND
        )

    instance.delete()
    return Response(
        {"message": "Material deleted successfully"}, status=status.HTTP_200_OK
    )


