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

# Programmer API's
@api_view(["POST"])
def add_programer_Details(request):
    try:
        with transaction.atomic():
            data = request.data

            material_id = data.get("material_id")
            program_no = data.get("program_no")
            program_date = data.get("program_date")

            processed_quantity = data.get("processed_quantity")
            balance_quantity = data.get("balance_quantity")

            processed_width = data.get("processed_width")
            processed_length = data.get("processed_length")

            remaining_width = data.get("remaining_width")
            remaining_length = data.get("remaining_length")

            used_weight = data.get("used_weight")
            number_of_sheets = data.get("number_of_sheets")
            cut_length_per_sheet = data.get("cut_length_per_sheet")
            pierce_per_sheet = data.get("pierce_per_sheet")
            processed_mins_per_sheet = data.get("processed_mins_per_sheet")

            total_planned_hours = data.get("total_planned_hours")
            total_meters = data.get("total_meters")
            total_piercing = data.get("total_piercing")
            total_used_weight = data.get("total_used_weight")
            total_no_of_sheets = data.get("total_no_of_sheets")

            remarks = data.get("remarks")

            # Resolve created_by user from request.user / request.user_obj, fallback to payload or Admin
            creator_username = None
            if hasattr(request, "user") and request.user and request.user.is_authenticated:
                creator_username = getattr(request.user, "username", None) or str(request.user)
            elif hasattr(request, "user_obj") and request.user_obj:
                creator_username = getattr(request.user_obj, "username", None) or str(request.user_obj)

            created_by = creator_username or data.get("created_by") or "Admin"

            # ? Step 2: Validate material and resolve product
            if not material_id:
                return Response(
                    {"error": "Missing 'material' ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:

                material_instance = product_material.objects.get(id=material_id)
                prod = material_instance.product
            except product_material.DoesNotExist:
                return Response(
                    {"error": "Material details not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

                # Guard: Each material can only have one programmer record
                if programer_details.objects.filter(
                    material=material_instance
                ).exists():
                    return Response(
                        {
                            "error": "Programmer details already exist for this material."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            programmer_obj = programer_details.objects.create(
                material=material_instance,
                program_no=program_no,
                program_date=program_date,
                processed_quantity=to_decimal(processed_quantity),
                balance_quantity=to_decimal(balance_quantity),
                processed_width=to_decimal(processed_width),
                processed_length=to_decimal(processed_length),
                used_weight=to_decimal(used_weight),
                number_of_sheets=to_decimal(number_of_sheets),
                cut_length_per_sheet=to_decimal(cut_length_per_sheet),
                pierce_per_sheet=to_decimal(pierce_per_sheet),
                processed_mins_per_sheet=to_decimal(processed_mins_per_sheet),
                total_planned_hours=to_duration(total_planned_hours),
                total_meters=to_decimal(total_meters),
                total_piercing=to_decimal(total_piercing),
                total_used_weight=to_decimal(total_used_weight),
                total_no_of_sheets=to_decimal(total_no_of_sheets),
                remaining_width=to_decimal(remaining_width),
                remaining_length=to_decimal(remaining_length),
                remarks=remarks,
                created_by=created_by,
            )

            # ? Step 3: Handle Pending Material Creation (Atomically)
            new_material_id = None
            bal_qty = to_decimal(balance_quantity)
            if bal_qty and bal_qty > 0:
                rem_width = to_decimal(remaining_width)
                rem_length = to_decimal(remaining_length)

                orig_width = material_instance.width or Decimal("0")
                orig_length = material_instance.length or Decimal("0")

                proc_width = to_decimal(processed_width) or Decimal("0")
                proc_length = to_decimal(processed_length) or Decimal("0")

                new_width = orig_width - proc_width if (proc_width > 0 and proc_width < orig_width) else orig_width
                new_length = orig_length - proc_length if (proc_length > 0 and proc_length < orig_length) else orig_length

                thick_val = material_instance.thick or Decimal("0")
                density_val = Decimal(str(material_instance.density or 0.0))
                new_unit_weight = thick_val * new_width * new_length * density_val
                new_total_weight = bal_qty * new_unit_weight

                new_mat = product_material.objects.create(
                    product=prod,
                    uid_no=material_instance.uid_no,
                    heat_no=material_instance.heat_no,
                    mat_type=material_instance.mat_type,
                    mat_grade=material_instance.mat_grade,
                    thick=material_instance.thick,
                    width=new_width,
                    length=new_length,
                    density=material_instance.density,
                    unit_weight=new_unit_weight,
                    quantity=bal_qty,
                    total_weight=new_total_weight,
                    total_length=new_length * bal_qty,
                    total_width=new_width * bal_qty,
                    bay=material_instance.bay,
                    stock_due=material_instance.stock_due,
                    remarks=material_instance.remarks,
                    created_by=created_by,
                    programer_status="pending",
                    qa_status="pending",
                    acc_status="pending",
                )
                new_material_id = new_mat.id

            # Note: Material and Product status updates are handled by programer_details.save()
            prod.refresh_from_db()

            return Response(
                {
                    "msg": "programmer created successfully",
                    "programmer_id": programmer_obj.id,
                    "product_id": prod.id,
                    "material_id": material_instance.id,
                    "new_material_id": new_material_id,
                    "program_no": program_no,
                    "program_date": program_date,
                    "processed_quantity": processed_quantity,
                    "balance_quantity": balance_quantity,
                    "processed_width": processed_width,
                    "processed_length": processed_length,
                    "used_weight": used_weight,
                    "number_of_sheets": number_of_sheets,
                    "cut_length_per_sheet": cut_length_per_sheet,
                    "pierce_per_sheet": pierce_per_sheet,
                    "processed_mins_per_sheet": processed_mins_per_sheet,
                    "total_planned_hours": str(total_planned_hours),
                    "total_meters": total_meters,
                    "total_piercing": total_piercing,
                    "total_used_weight": total_used_weight,
                    "total_no_of_sheets": total_no_of_sheets,
                    "remaining_width": remaining_width,
                    "remaining_length": remaining_length,
                    "remarks": remarks,
                    "created_by": created_by,
                    "programer_status": prod.programer_status,
                },
                status=status.HTTP_201_CREATED,
            )
    except Exception as e:
        print("? Error in add_account_new:", str(e))
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
def get_programer_Details(request):
    """
    ? Fetch all programer_details, or filter by product_id / material_id
    Examples:
        GET /api/get_programer_Details/                          ? all records
        GET /api/get_programer_Details/?product_id=5             ? records for a specific product
        GET /api/get_programer_Details/?material_id=12           ? records for a specific material
        GET /api/get_programer_Details/?product_id=5&material_id=12 ? combined filter
    """
    try:
        product_id = request.query_params.get("product_id")
        material_id = request.query_params.get("material_id")

        # ? Base QuerySet
        details = programer_details.objects.all().select_related(
            "material", "material__product"
        )

        # ? Apply filters dynamically
        if product_id:
            details = details.filter(material__product__id=product_id)
        if material_id:
            details = details.filter(material__id=material_id)

        if not details.exists():
            return Response([], status=status.HTTP_200_OK)

        # ? Serialize and respond
        serializer = programer_detailsSerializer(details, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        print("? Error in get_programer_Details:", str(e))
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


# Update Programmer Product
@api_view(["PUT"])
def update_programer_details(request):
    """
    Update programmer details for a specific material.

    Requires:
    - material_id (sent in request body)
    """
    try:
        # ---------------------------
        # Validate required material ID
        # ---------------------------
        material_id = request.data.get("material_id")

        if not material_id:
            return Response({"msg": "material_id is required"}, status=400)

        # ---------------------------
        # Fetch or Create programmer entry for given material
        # ---------------------------
        # Fetch programmer entry for given material
        try:
            material = product_material.objects.get(id=material_id)
            prog, _ = programer_details.objects.get_or_create(material=material)
        except product_material.DoesNotExist:
            return Response(
                {"msg": "Material not found"},
                status=404,
            )
        except programer_details.MultipleObjectsReturned:
            return Response(
                {"msg": "Multiple programmer entries found. Provide programmer ID."},
                status=400,
            )

        # ---------------------------
        # Update normal fields
        # ---------------------------
        fields_to_update = [
            "program_no",
            "program_date",
            "processed_quantity",
            "balance_quantity",
            "processed_width",
            "processed_length",
            "remaining_width",
            "remaining_length",
            "used_weight",
            "number_of_sheets",
            "cut_length_per_sheet",
            "pierce_per_sheet",
            "processed_mins_per_sheet",
            "total_planned_hours",
            "total_meters",
            "total_piercing",
            "total_used_weight",
            "total_no_of_sheets",
            "date",
            "time",
            "remarks",
        ]

        for field in fields_to_update:
            if field in request.data:
                val = request.data.get(field)
                if field == "total_planned_hours":
                    val = to_duration(val)
                setattr(prog, field, val)

        # ---------------------------
        # Update created_by (ForeignKey)
        # ---------------------------
        created_by_username = request.data.get("created_by")
        if created_by_username:
            try:
                user = All_User.objects.get(username=created_by_username)
                prog.created_by = user.username
            except All_User.DoesNotExist:
                return Response({"msg": "Invalid created_by username"}, status=400)

        # Save updated entry
        prog.save()

        return Response({"msg": "Programmer details updated successfully"}, status=200)

    except Exception as e:
        return Response({"msg": f"Error updating programmer: {str(e)}"}, status=500)


# QA API's
@api_view(["POST"])
def add_qa_details(request):
    try:
        data = request.data
        material_id = data.get("material_id")
        processed_date = data.get("processed_date")
        shift = data.get("shift")
        # no_of_sheets = data.get("no_of_sheets")
        # cycletime_per_sheet = data.get("cycletime_per_sheet")
        # total_cycle_time = data.get("total_cycle_time")
        # total_cycle_time_formatted = data.get("total_cycle_time_formatted")
        # machines_used is now a list of objects from the frontend
        machines_used = data.get("machines_used", [])
        creator_username = None
        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            creator_username = getattr(request.user, "username", None) or str(request.user)
        elif hasattr(request, "user_obj") and request.user_obj:
            creator_username = getattr(request.user_obj, "username", None) or str(request.user_obj)

        created_by = creator_username or data.get("created_by") or "Admin"

        # ? Resolve material and product
        if not material_id:
            return Response(
                {"status": False, "message": "Missing 'material_id' ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            material_instance = product_material.objects.get(id=material_id)
        except product_material.DoesNotExist:
            return Response(
                {"status": False, "message": "Material details not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if QA already exists for this material
        if qa_details.objects.filter(material=material_instance).exists():
            return Response(
                {
                    "status": False,
                    "message": "QA details already exist for this material.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ? Create the QA details record and logs in one transaction
        with transaction.atomic():
            # Create main QA header
            qa_obj = qa_details.objects.create(
                material=material_instance,
                processed_date=processed_date,
                shift=shift,
                # no_of_sheets=to_decimal(no_of_sheets),
                # cycletime_per_sheet=to_decimal(cycletime_per_sheet),
                # total_cycle_time=to_duration(total_cycle_time_formatted),
                created_by=created_by,
            )

            # Create relational machine logs
            for log_data in machines_used:
                qa_machine_details.objects.create(
                    qa=qa_obj,
                    machine_name=log_data.get("machine_name"),
                    date=log_data.get("date"),
                    start_time=to_duration(
                        log_data.get("start_time") or log_data.get("start")
                    ),
                    end_time=to_duration(
                        log_data.get("end_time") or log_data.get("end")
                    ),
                    runtime=to_duration(log_data.get("runtime")),
                    operator=log_data.get("operator_name") or log_data.get("operator"),
                    gas_type=log_data.get("gas_type")
                    or log_data.get("air_gas")
                    or log_data.get("air"),
                )

            # ✅ Trigger save again to update status now that machine logs exist
            qa_obj.save()

        # ? Response
        return Response(
            {
                "msg": "QA details created successfully",
                "qa_id": qa_obj.id,
                "material_id": material_id,
                "status": "completed",
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        print(f"Error in add_qa_details: {str(e)}")
        return Response(
            {"status": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET"])
def get_qa_details(request):
    try:
        product_id = request.GET.get("product_id")
        material_id = request.GET.get("material_id")

        # ? Build queryset with prefetched machine logs
        qa_qs = (
            qa_details.objects.select_related("material", "material__product")
            .prefetch_related("qa_machine_details")
            .all()
        )

        # ? Apply filters
        if product_id:
            qa_qs = qa_qs.filter(material__product__id=product_id)
        if material_id:
            qa_qs = qa_qs.filter(material__id=material_id)

        # ? Serialize queryset
        serializer = qa_detailsSerializer(qa_qs, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error in get_qa_details: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Update Qa Product
@api_view(["PUT"])
def update_qa_details(request):
    try:
        data = request.data
        material_id = data.get("material_id")

        if not material_id:
            return Response({"msg": "material_id is required"}, status=400)

        # Fetch QA for given material (belonging to this material)
        try:
            material = product_material.objects.get(id=material_id)
            qa, _ = qa_details.objects.get_or_create(material=material)
        except product_material.DoesNotExist:
            return Response({"msg": "Material not found"}, status=404)

        # Transactional update for main fields and machine logs
        with transaction.atomic():
            # Update main fields
            common_fields = ["processed_date", "shift", "remarks"]
            for field in common_fields:
                if field in data:
                    setattr(qa, field, data.get(field))

            sync_machines = data.get("machines_used")
            if sync_machines is not None:
                # Clear existing logs
                qa.qa_machine_details.all().delete()

                # Re-create logs
                for log_data in sync_machines:
                    qa_machine_details.objects.create(
                        qa=qa,
                        machine_name=log_data.get("machine_name"),
                        date=log_data.get("date"),
                        start_time=to_duration(log_data.get("start_time")),
                        end_time=to_duration(log_data.get("end_time")),
                        runtime=to_duration(log_data.get("runtime")),
                        operator=log_data.get("operator_name")
                        or log_data.get("operator"),
                        gas_type=log_data.get("gas_type") or log_data.get("air_gas"),
                    )

            # Save AT THE END after machines are created, so status is updated correctly
            qa.save()

        return Response({"msg": "QA updated successfully"}, status=200)

    except Exception as e:
        return Response({"msg": f"Error updating QA: {str(e)}"}, status=500)


# Accounts API's
@api_view(["POST"])
def add_acc_details(request):
    try:
        data = request.data
        invoice_no = data.get("invoice_no")
        transporter_no = data.get("transporter_no")
        payments_terms = data.get("payments_terms")
        status_acc = data.get("status")
        remarks = data.get("remarks")
        product_id = data.get("product_details")
        material_ids = data.get("material_details", [])  # <-- LIST
        creator_username = None
        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            creator_username = getattr(request.user, "username", None) or str(request.user)
        elif hasattr(request, "user_obj") and request.user_obj:
            creator_username = getattr(request.user_obj, "username", None) or str(request.user_obj)

        created_by = creator_username or data.get("created_by") or "Admin"

        # Validate product
        try:
            prod = product_details.objects.get(id=product_id)
        except product_details.DoesNotExist:
            return Response(
                {"status": False, "message": "Product not found"}, status=404
            )

        created_records = []

        # LOOP THROUGH ALL MATERIALS
        with transaction.atomic():
            for material_id in material_ids:
                try:
                    material_instance = product_material.objects.get(
                        id=material_id, product=prod
                    )
                except product_material.DoesNotExist:
                    return Response(
                        {
                            "status": False,
                            "message": f"Material {material_id} not found or not linked to product",
                        },
                        status=400,
                    )

                # Guard: One record per material
                if acc_details.objects.filter(material=material_instance).exists():
                    continue  # Skip or handle duplicate as needed

                acc_obj = acc_details.objects.create(
                    material=material_instance,
                    invoice_no=invoice_no,
                    transporter_no=transporter_no,
                    payments_terms=payments_terms,
                    status=status_acc,
                    remarks=remarks,
                    created_by=created_by,
                )
                created_records.append(acc_obj.id)

        # Note: Material and Product status updates are handled by acc_details.save() trigger
        return Response(
            {
                "status": True,
                "msg": "Account details created successfully",
                "created_records": created_records,
            },
            status=201,
        )

    except Exception as e:
        print(f"Error in add_acc_details: {str(e)}")
        return Response({"status": False, "error": str(e)}, status=400)


@api_view(["GET"])
def get_acc_details(request):
    try:
        product_id = request.GET.get("product_id")
        creator_by = request.GET.get("created_by")

        # ? Select material and product correctly
        acc_qs = acc_details.objects.select_related(
            "material", "material__product"
        ).all()

        # Filter by product id
        if product_id:
            acc_qs = acc_qs.filter(material__product__id=product_id)

        # Filter by created_by (username)
        if creator_by:
            acc_qs = acc_qs.filter(created_by=creator_by)

        serializer = acc_detailsSerializer(acc_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error in get_acc_details: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


