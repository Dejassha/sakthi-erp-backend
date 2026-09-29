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

# Utility for checking duplicate slip number
@api_view(["GET"])
def check_slip_number(request):
    slip_number = request.GET.get("slip_number", None)
    if not slip_number:
        return Response({"error": "Slip number is required."}, status=400)

    exists = product_details.objects.filter(
        inward_slip_number__iexact=slip_number.strip()
    ).exists()

    return Response({"exists": exists})


# Utility for getting latest slip number
@api_view(["GET"])
def get_latest_slip_number(request):
    try:
        # Get all slip numbers
        all_products = product_details.objects.exclude(
            inward_slip_number__isnull=True
        ).exclude(inward_slip_number__exact="")

        max_j = 0
        max_q = 0

        for prod in all_products:
            slip = prod.inward_slip_number.upper()
            try:
                if slip.startswith("J-"):
                    num = int(slip.split("-")[1])
                    if num > max_j:
                        max_j = num
                elif slip.startswith("Q-"):
                    num = int(slip.split("-")[1])
                    if num > max_q:
                        max_q = num
            except (IndexError, ValueError):
                pass  # safely ignore manually mistyped slips that slipped past validation

        return Response(
            {
                "latest_jobcard": f"J-{max_j:04d}",
                "latest_quotation": f"Q-{max_q:04d}",
                "next_jobcard_number": f"{max_j + 1:04d}",
                "next_quotation_number": f"{max_q + 1:04d}",
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Utility for getting materials by product
@api_view(["GET"])
def get_materials_by_product(request):
    try:
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response({"error": "product_id is required"}, status=400)

        product = get_object_or_404(product_details, id=product_id)
        # Fetch all materials for this product and let the frontend decide filtering
        materials = product_material.objects.filter(product=product)

        mat_list = []
        for mat in materials:
            mat_list.append(
                {
                    "id": mat.id,
                    "product_id": mat.product.id if mat.product else None,
                    "mat_type": mat.mat_type,
                    "mat_grade": mat.mat_grade if mat.mat_grade else "",
                    "thick": float(mat.thick) if mat.thick is not None else 0.0,
                    "width": float(mat.width) if mat.width is not None else 0.0,
                    "length": float(mat.length) if mat.length is not None else 0.0,
                    "density": float(mat.density) if mat.density is not None else 0.0,
                    "unit_weight": (
                        float(mat.unit_weight) if mat.unit_weight is not None else 0.0
                    ),
                    "quantity": (
                        float(mat.quantity) if mat.quantity is not None else 0.0
                    ),
                    "total_weight": (
                        float(mat.total_weight) if mat.total_weight is not None else 0.0
                    ),
                    "total_length": (
                        float(mat.total_length) if mat.total_length is not None else 0.0
                    ),
                    "total_width": (
                        float(mat.total_width) if mat.total_width is not None else 0.0
                    ),
                    "programer_status": mat.programer_status,
                    "qa_status": mat.qa_status,
                    "acc_status": mat.acc_status,
                }
            )

        return Response(mat_list, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# All Dashboard List and Details
@api_view(["GET"])
def get_dashboard_list(request):
    try:
        page_number = request.GET.get("page", 1)
        page_size = request.GET.get("page_size", 15)
        filters_json = request.GET.get("filters")
        sort_json = request.GET.get("sort")

        # Build queryset
        products_qs = product_details.objects.all()

        # Apply Server-Side Filtering (Ag-Grid Style)
        if filters_json:
            try:
                filter_model = json.loads(filters_json)
                for field, config in filter_model.items():
                    # Map front-end field if necessary
                    db_field = field
                    if field == "created_by":
                        db_field = "created_by"
                    elif field == "programmer_no":
                        db_field = "product_material__programer_details__program_no"

                    # Recursively apply conditions
                    products_qs = apply_ag_grid_filter(products_qs, db_field, config)

                # Apply distinct to prevent duplicate products due to joins
                products_qs = products_qs.distinct()
            except Exception as e:
                print(f"Global filter error in get_dashboard_list: {e}")

        # Apply Server-Side Sorting
        if sort_json:
            try:
                sort_model = json.loads(sort_json)
                ordering = []
                for item in sort_model:
                    col_id = item.get("colId")
                    sort_dir = item.get("sort")

                    if col_id == "created_by":
                        col_id = "created_by"

                    prefix = "-" if sort_dir == "desc" else ""
                    ordering.append(f"{prefix}{col_id}")

                if ordering:
                    products_qs = products_qs.order_by(*ordering)
                else:
                    products_qs = products_qs.order_by("-id")
            except Exception as e:
                print(f"Sort error: {e}")
                products_qs = products_qs.order_by("-id")
        else:
            products_qs = products_qs.order_by("-id")

        # Paginate
        paginator = Paginator(products_qs, page_size)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        result = []
        for prod in page_obj:
            result.append(
                {
                    "id": prod.id,
                    "sheet_type": prod.sheet_type,
                    "job_type": prod.job_type,
                    "inward_slip_number": prod.inward_slip_number,
                    "date": prod.date,
                    "company_name": prod.company_name,
                    "customer_name": prod.customer_name,
                    "contact_no": prod.contact_no,
                    "programer_status": prod.programer_status,
                    "qa_status": prod.qa_status,
                    "outward_status": prod.outward_status,
                    "created_by": prod.created_by,
                }
            )

        return Response(
            {
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "results": result,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"msg": f"Error fetching dashboard list: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def get_dashboard_details(request):
    """
    Unified Professional API for Dashboard Details.
    Fetches Product -> Materials -> (Programmer, QA, Account Details)
    Query Params:
        product_id (required): ID of the product
        type (optional): 'programmer', 'qa', 'accounts' (defaults to 'accounts' for full data)
    """
    try:
        product_id = request.query_params.get("product_id")
        view_type = request.query_params.get("type", "accounts")

        if not product_id:
            return Response({"error": "product_id is required"}, status=400)

        # 1. Fetch Product with optimized creator fetch
        product = get_object_or_404(product_details, id=product_id)

        # 2. Fetch Materials linked to this product
        materials_qs = product_material.objects.filter(product=product)

        # 3. Optimize related detail fetches
        # We prefetch all related details to avoid N+1 problems
        materials_qs = materials_qs.prefetch_related(
            "programer_details_set",
            "qa_details_set",
            "acc_details_set",
        )

        material_list = []
        for mat in materials_qs:
            mat_data = {
                "id": mat.id,
                "uid_no": mat.uid_no,
                "heat_no": mat.heat_no,
                "bay": mat.bay,
                "mat_type": mat.mat_type,
                "mat_grade": mat.mat_grade,
                "thick": mat.thick,
                "width": mat.width,
                "length": mat.length,
                "density": mat.density,
                "unit_weight": mat.unit_weight,
                "quantity": mat.quantity,
                "total_weight": mat.total_weight,
                "stock_due": mat.stock_due,
                "remarks": mat.remarks,
                "programer_status": mat.programer_status,
                "qa_status": mat.qa_status,
                "acc_status": mat.acc_status,
                "created_by": mat.created_by,
                "programer_details": [],
                "qa_details": [],
                "account_details": [],
            }

            # Only include relevant details based on view_type
            # Programmer details are usually needed by all subsequent stages
            mat_data["programer_details"] = [
                {
                    "id": p.id,
                    "program_no": p.program_no,
                    "program_date": (
                        p.program_date.isoformat() if p.program_date else None
                    ),
                    "processed_quantity": p.processed_quantity,
                    "balance_quantity": p.balance_quantity,
                    "processed_width": p.processed_width,
                    "processed_length": p.processed_length,
                    "remaining_width": p.remaining_width,
                    "remaining_length": p.remaining_length,
                    "used_weight": p.used_weight,
                    "number_of_sheets": p.number_of_sheets,
                    "cut_length_per_sheet": p.cut_length_per_sheet,
                    "pierce_per_sheet": p.pierce_per_sheet,
                    "processed_mins_per_sheet": p.processed_mins_per_sheet,
                    "total_planned_hours": (
                        f"{int(p.total_planned_hours.total_seconds() // 3600):02d}:{int((p.total_planned_hours.total_seconds() % 3600) // 60):02d}"
                        if p.total_planned_hours
                        else None
                    ),
                    "total_meters": p.total_meters,
                    "total_piercing": p.total_piercing,
                    "total_used_weight": p.total_used_weight,
                    "total_no_of_sheets": p.total_no_of_sheets,
                    "remarks": p.remarks,
                    "created_by": p.created_by,
                }
                for p in mat.programer_details_set.all()
            ]

            if view_type in ["qa", "accounts", "admin"]:
                mat_data["qa_details"] = [
                    {
                        "id": q.id,
                        "processed_date": (
                            q.processed_date.isoformat() if q.processed_date else None
                        ),
                        "shift": q.shift,
                        "machine_logs": [
                            {
                                "id": m.id,
                                "machine_name": m.machine_name,
                                "date": m.date,
                                "start_time": (
                                    f"{int(m.start_time.total_seconds() // 3600):02d}:{int((m.start_time.total_seconds() % 3600) // 60):02d}"
                                    if m.start_time is not None
                                    else None
                                ),
                                "end_time": (
                                    f"{int(m.end_time.total_seconds() // 3600):02d}:{int((m.end_time.total_seconds() % 3600) // 60):02d}"
                                    if m.end_time is not None
                                    else None
                                ),
                                "runtime": (
                                    f"{int(m.runtime.total_seconds() // 3600):02d}:{int((m.runtime.total_seconds() % 3600) // 60):02d}"
                                    if m.runtime is not None
                                    else None
                                ),
                                "operator_name": m.operator,
                                "gas_type": m.gas_type,
                            }
                            for m in q.qa_machine_details.all()
                        ],
                        "created_by": q.created_by,
                    }
                    for q in mat.qa_details_set.all()
                ]

            if view_type in ["accounts", "admin"]:
                mat_data["account_details"] = [
                    {
                        "id": a.id,
                        "invoice_no": a.invoice_no,
                        "transporter_no": a.transporter_no,
                        "payments_terms": a.payments_terms,
                        "status": a.status,
                        "remarks": a.remarks,
                        "created_by": a.created_by,
                    }
                    for a in mat.acc_details_set.all()
                ]

            material_list.append(mat_data)

        # 4. Construct Final Response
        response_data = {
            "product": {
                "id": product.id,
                "company_name": product.company_name,
                "date": product.date,
                "job_type": product.job_type,
                "inward_slip_number": product.inward_slip_number,
                "sheet_type": product.sheet_type,
                "worker_no": product.worker_no,
                "customer_name": product.customer_name,
                "customer_dc_no": product.customer_dc_no,
                "contact_no": product.contact_no,
                "programer_status": product.programer_status,
                "qa_status": product.qa_status,
                "outward_status": product.outward_status,
                "created_by": product.created_by,
            },
            "materials": material_list,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        print("? Error in get_dashboard_details:", str(e))
        return Response(
            {"status": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Product API's
@api_view(["POST"])
def add_inward_details(request):
    print("DEBUG: Received Payload:", request.data)  # Log to server console
    try:
        with transaction.atomic():
            # Resolve created_by user from request.user / request.user_obj
            creator_username = None
            if hasattr(request, "user") and request.user and request.user.is_authenticated:
                creator_username = getattr(request.user, "username", None) or str(request.user)
            elif hasattr(request, "user_obj") and request.user_obj:
                creator_username = getattr(request.user_obj, "username", None) or str(request.user_obj)

            created_by_val = creator_username or request.data.get("created_by") or "System"

            # --- Product creation ---
            product = product_details.objects.create(
                sheet_type=request.data.get("sheet_type"),
                job_type=request.data.get("job_type"),
                inward_slip_number=request.data.get("inward_slip_number"),
                worker_no=request.data.get("worker_no") or "-",
                company_name=request.data.get("company_name"),
                customer_name=request.data.get("customer_name"),
                customer_dc_no=request.data.get("customer_dc_no"),
                contact_no=request.data.get("contact_no"),
                created_by=created_by_val,
            )

            materials_data = request.data.get("materials", [])
            created_materials = []

            for mat in materials_data:

                material = product_material.objects.create(
                    product=product,
                    uid_no=mat.get("uid_no", ""),
                    heat_no=mat.get("heat_no", ""),
                    mat_type=mat.get("mat_type", ""),
                    mat_grade=mat.get("mat_grade", ""),
                    thick=to_decimal(mat.get("thick")),
                    width=to_decimal(mat.get("width")),
                    length=to_decimal(mat.get("length")),
                    density=to_float(mat.get("density")),
                    unit_weight=to_decimal(mat.get("unit_weight")),
                    quantity=to_decimal(mat.get("quantity")),
                    total_weight=to_decimal(mat.get("total_weight")),
                    total_length=to_decimal(mat.get("total_length")),
                    total_width=to_decimal(mat.get("total_width")),
                    bay=mat.get("bay", ""),
                    stock_due=mat.get("stock_due", ""),
                    remarks=mat.get("remarks") or "-",
                    created_by=mat.get("created_by") or created_by_val,
                )

                # --- AUTO-FILL PROGRAMMER FOR ONLY_FOLDING ---
                if product.job_type == "Only Folding":
                    from datetime import timedelta

                    programer_details.objects.create(
                        material=material,
                        program_no="AUTO-FOLD",
                        program_date=timezone.now().date(),
                        processed_quantity=0,
                        balance_quantity=0,
                        processed_width=0,
                        processed_length=0,
                        remaining_width=0,
                        remaining_length=0,
                        used_weight=0,
                        number_of_sheets=0,
                        cut_length_per_sheet=0,
                        pierce_per_sheet=0,
                        processed_mins_per_sheet=0,
                        total_planned_hours=timedelta(0),
                        total_meters=0,
                        total_piercing=0,
                        total_used_weight=0,
                        total_no_of_sheets=0,
                        remarks="No Data Needed for Only Folding",
                        created_by="system",
                    )

                created_materials.append(material)

        # --- Serialize response ---
        response_data = {
            "msg": "Product and materials added successfully",
            "received_data": request.data,  # ECHO BACK the data received
            "product": product_detailsSerializer(product).data,
            "materials": product_materialSerializer(created_materials, many=True).data,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    except ValueError as ve:
        return Response({"msg": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"msg": f"Error adding product: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def get_inward_details(request):
    """
    Fetch all products with their related materials and nested logs.
    """
    try:
        product_id = request.query_params.get("product_id")
        if product_id:
            products = product_details.objects.filter(id=product_id)
        else:
            products = product_details.objects.all().order_by("-id")

        if not products.exists():
            return Response([], status=status.HTTP_200_OK)

        serializer = product_detailsSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"msg": f"Error fetching products: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as e:
        return Response(
            {"msg": f"Error fetching products: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Admin Reports
@api_view(["GET"])
def get_overall_details(request):

    try:
        FIELD_MAP = {
            # Product
            "sheet_type": "product__sheet_type",
            "job_type": "product__job_type",
            "inward_slip_number": "product__inward_slip_number",
            "date": "product__date",
            "company_name": "product__company_name",
            "company": "product__company_name",
            "customer_name": "product__customer_name",
            "customer": "product__customer_name",
            "contact_no": "product__contact_no",
            "customer_dc_no": "product__customer_dc_no",
            "worker_no": "product__worker_no",
            "inward_created_by": "product__created_by",
            # Material
            "mat_type": "mat_type",
            "mat_grade": "mat_grade",
            "uid_no": "uid_no",
            "heat_no": "heat_no",
            "bay": "bay",
            "thick": "thick",
            "width": "width",
            "length": "length",
            "quantity": "quantity",
            "density": "density",
            "unit_weight": "unit_weight",
            "total_weight": "total_weight",
            "stock_due": "stock_due",
            "programer_status": "programer_status",
            "qa_status": "qa_status",
            "acc_status": "acc_status",
            "material_created_by": "created_by",
            # Programmer
            "program_no": "programer_details__program_no",
            "program_date": "programer_details__program_date",
            "processed_quantity": "programer_details__processed_quantity",
            "balance_quantity": "programer_details__balance_quantity",
            "processed_width": "programer_details__processed_width",
            "processed_length": "programer_details__processed_length",
            "used_weight": "programer_details__used_weight",
            "number_of_sheets": "programer_details__number_of_sheets",
            "cut_length_per_sheet": "programer_details__cut_length_per_sheet",
            "pierce_per_sheet": "programer_details__pierce_per_sheet",
            "processed_mins_per_sheet": "programer_details__processed_mins_per_sheet",
            "total_planned_hours": "programer_details__total_planned_hours",
            "total_meters": "programer_details__total_meters",
            "total_piercing": "programer_details__total_piercing",
            "total_used_weight": "programer_details__total_used_weight",
            "total_no_of_sheets": "programer_details__total_no_of_sheets",
            "programer_created_by": "programer_details__created_by",
            # QA
            "qa_processed_date": "qa_details__processed_date",
            "shift": "qa_details__shift",
            "qa_created_by": "qa_details__created_by",
            # Machine Logs
            "machine_name": "qa_details__qa_machine_details__machine_name",
            "machine_date": "qa_details__qa_machine_details__date",
            "start_time": "qa_details__qa_machine_details__start_time",
            "end_time": "qa_details__qa_machine_details__end_time",
            "machine_start": "qa_details__qa_machine_details__start_time",
            "machine_end": "qa_details__qa_machine_details__end_time",
            "machine_runtime": "qa_details__qa_machine_details__runtime",
            "machine_operator": "qa_details__qa_machine_details__operator",
            "machine_air": "qa_details__qa_machine_details__gas_type",
            "machine_gas_type": "qa_details__qa_machine_details__gas_type",
            # Accounts
            "invoice_no": "acc_details__invoice_no",
            "transporter_no": "acc_details__transporter_no",
            "payments_terms": "acc_details__payments_terms",
            "status": "acc_details__status",
            "acc_remarks": "acc_details__remarks",
            "acc_created_by": "acc_details__created_by",
        }

        # 2. FILTERS & PARAMS
        filters_json = request.query_params.get("filters")
        sort_json = request.query_params.get("sort")

        # Legacy/Sidebar filters
        search_query = request.query_params.get("search", "").strip()
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 100))
        except:
            page, page_size = 1, 100

        # Base Queryset: Start from product_material
        from api.models import product_material as _PM

        # Use .distinct() if filtering on one-to-many rels (like machine logs) to avoid dups
        material_qs = _PM.objects.select_related("product").distinct()

        # ── AG Grid Filter Model ──
        if filters_json:
            try:
                filter_model = json.loads(filters_json)
                for field, config in filter_model.items():
                    db_field = FIELD_MAP.get(field, field)
                    material_qs = apply_ag_grid_filter(material_qs, db_field, config)
            except Exception as e:
                print(f"Report Filter Error: {e}")

        # ── Legacy Filters ──
        if search_query:
            material_qs = material_qs.filter(
                Q(product__inward_slip_number__icontains=search_query)
                | Q(product__company_name__icontains=search_query)
                | Q(product__customer_name__icontains=search_query)
                | Q(mat_type__icontains=search_query)
                | Q(uid_no__icontains=search_query)
                | Q(heat_no__icontains=search_query)
            )
        if start_date:
            material_qs = material_qs.filter(product__date__gte=start_date)
        if end_date:
            material_qs = material_qs.filter(product__date__lte=end_date)

        # ── AG Grid Sort Model ──
        if sort_json:
            try:
                sort_model = json.loads(sort_json)
                ordering = []
                for item in sort_model:
                    f = FIELD_MAP.get(item["colId"], item["colId"])
                    prefix = "-" if item["sort"] == "desc" else ""
                    ordering.append(f"{prefix}{f}")
                if ordering:
                    material_qs = material_qs.order_by(*ordering)
            except:
                material_qs = material_qs.order_by("-id")
        else:
            material_qs = material_qs.order_by("-id")

        # 3. EFFICIENT TOTALS FOR FULL FILTERED QS (UNPAGED)
        sum_columns = [
            "thick",
            "width",
            "length",
            "unit_weight",
            "quantity",
            "total_weight",
            "processed_quantity",
            "balance_quantity",
            "processed_width",
            "processed_length",
            "used_weight",
            "number_of_sheets",
            "cut_length_per_sheet",
            "pierce_per_sheet",
            "total_meters",
            "total_piercing",
            "total_used_weight",
            "total_no_of_sheets",
            "processed_mins_per_sheet",
            "total_planned_hours",
            # "qa_sheets", "qa_cycletime", "qa_total_cycle_time",
            "machine_runtime",
        ]
        totals = {col: 0 for col in sum_columns}

        # Use the filtered material_qs (before pagination)
        m_aggregates = material_qs.aggregate(
            sum_thick=Sum("thick"),
            sum_width=Sum("width"),
            sum_length=Sum("length"),
            sum_unit=Sum("unit_weight"),
            sum_qty=Sum("quantity"),
            sum_tot_w=Sum("total_weight"),
        )
        totals.update(
            {
                "thick": float(m_aggregates["sum_thick"] or 0),
                "width": float(m_aggregates["sum_width"] or 0),
                "length": float(m_aggregates["sum_length"] or 0),
                "unit_weight": float(m_aggregates["sum_unit"] or 0),
                "quantity": float(m_aggregates["sum_qty"] or 0),
                "total_weight": float(m_aggregates["sum_tot_w"] or 0),
            }
        )

        prog_qs = programer_details.objects.filter(material__in=material_qs)
        prog_aggregates = prog_qs.aggregate(
            sum_processed=Sum("processed_quantity"),
            sum_balance=Sum("balance_quantity"),
            sum_pw=Sum("processed_width"),
            sum_pl=Sum("processed_length"),
            sum_uw=Sum("used_weight"),
            sum_nos=Sum("number_of_sheets"),
            sum_cl=Sum("cut_length_per_sheet"),
            sum_pierce=Sum("pierce_per_sheet"),
            sum_meters=Sum("total_meters"),
            sum_tot_pierce=Sum("total_piercing"),
            sum_tuw=Sum("total_used_weight"),
            sum_tns=Sum("total_no_of_sheets"),
            sum_mins=Sum("processed_mins_per_sheet"),
            sum_tph=Sum("total_planned_hours"),
        )
        totals.update(
            {
                "processed_quantity": float(prog_aggregates["sum_processed"] or 0),
                "balance_quantity": float(prog_aggregates["sum_balance"] or 0),
                "processed_width": float(prog_aggregates["sum_pw"] or 0),
                "processed_length": float(prog_aggregates["sum_pl"] or 0),
                "used_weight": float(prog_aggregates["sum_uw"] or 0),
                "number_of_sheets": float(prog_aggregates["sum_nos"] or 0),
                "cut_length_per_sheet": float(prog_aggregates["sum_cl"] or 0),
                "pierce_per_sheet": float(prog_aggregates["sum_pierce"] or 0),
                "total_meters": float(prog_aggregates["sum_meters"] or 0),
                "total_piercing": float(prog_aggregates["sum_tot_pierce"] or 0),
                "total_used_weight": float(prog_aggregates["sum_tuw"] or 0),
                "total_no_of_sheets": float(prog_aggregates["sum_tns"] or 0),
                "processed_mins_per_sheet": float(prog_aggregates["sum_mins"] or 0),
                "total_planned_hours": parse_time_to_minutes(prog_aggregates["sum_tph"]),
            }
        )

        qa_mach_agg = qa_machine_details.objects.filter(
            qa__material__in=material_qs
        ).aggregate(sum_runtime=Sum("runtime"))
        totals["machine_runtime"] = parse_time_to_minutes(qa_mach_agg["sum_runtime"])

        # 4. PAGINATION & FLATTENING
        from django.db.models import F

        expanded_qs = material_qs.annotate(
            machine_log_id=F("qa_details__qa_machine_details__id")
        )

        total_count = expanded_qs.count()

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_materials = expanded_qs.prefetch_related(
            "programer_details_set",
            "qa_details_set",
            "qa_details_set__qa_machine_details",
            "acc_details_set",
        )[start_idx:end_idx]

        flat_rows = []
        for mat in paged_materials:
            prod = mat.product
            # Related items from prefetched caches (no extra DB queries)
            prog_list = list(mat.programer_details_set.all())
            prog = prog_list[0] if prog_list else None

            qa_list = list(mat.qa_details_set.all())
            qa = qa_list[0] if qa_list else None

            acc_list = list(mat.acc_details_set.all())
            acc = acc_list[0] if acc_list else None

            base_data = {
                "product_id": prod.id,
                "company_name": prod.company_name,
                "date": prod.date.isoformat() if prod.date else None,
                "inward_slip_number": prod.inward_slip_number,
                "sheet_type": prod.sheet_type,
                "job_type": prod.job_type,
                "worker_no": prod.worker_no,
                "customer_name": prod.customer_name,
                "customer_dc_no": prod.customer_dc_no,
                "contact_no": prod.contact_no,
                "inward_created_by": prod.created_by,
                "material_id": mat.id,
                "uid_no": mat.uid_no,
                "heat_no": mat.heat_no,
                "bay": mat.bay,
                "mat_type": mat.mat_type,
                "mat_grade": mat.mat_grade,
                "thick": float(mat.thick) if mat.thick else 0,
                "width": float(mat.width) if mat.width else 0,
                "length": float(mat.length) if mat.length else 0,
                "density": float(mat.density) if mat.density else 0,
                "unit_weight": float(mat.unit_weight) if mat.unit_weight else 0,
                "quantity": float(mat.quantity) if mat.quantity else 0,
                "total_weight": float(mat.total_weight) if mat.total_weight else 0,
                "stock_due": mat.stock_due,
                "material_created_by": mat.created_by,
                "programer_status": mat.programer_status,
                "qa_status": mat.qa_status,
                "acc_status": mat.acc_status,
                # Program details
                "program_no": prog.program_no if prog else "",
                "program_date": (
                    prog.program_date.isoformat() if prog and prog.program_date else ""
                ),
                "processed_quantity": (
                    float(prog.processed_quantity)
                    if prog and prog.processed_quantity
                    else 0
                ),
                "balance_quantity": (
                    float(prog.balance_quantity)
                    if prog and prog.balance_quantity
                    else 0
                ),
                "processed_width": (
                    float(prog.processed_width) if prog and prog.processed_width else 0
                ),
                "processed_length": (
                    float(prog.processed_length)
                    if prog and prog.processed_length
                    else 0
                ),
                "used_weight": (
                    float(prog.used_weight) if prog and prog.used_weight else 0
                ),
                "number_of_sheets": (
                    float(prog.number_of_sheets)
                    if prog and prog.number_of_sheets
                    else 0
                ),
                "cut_length_per_sheet": (
                    float(prog.cut_length_per_sheet)
                    if prog and prog.cut_length_per_sheet
                    else 0
                ),
                "pierce_per_sheet": (
                    float(prog.pierce_per_sheet)
                    if prog and prog.pierce_per_sheet
                    else 0
                ),
                "processed_mins_per_sheet": (
                    float(prog.processed_mins_per_sheet)
                    if prog and prog.processed_mins_per_sheet
                    else 0
                ),
                "total_planned_hours": (
                    format_duration_as_time(prog.total_planned_hours)
                    if prog and prog.total_planned_hours
                    else ""
                ),
                "total_meters": (
                    float(prog.total_meters) if prog and prog.total_meters else 0
                ),
                "total_piercing": (
                    float(prog.total_piercing) if prog and prog.total_piercing else 0
                ),
                "total_used_weight": (
                    float(prog.total_used_weight)
                    if prog and prog.total_used_weight
                    else 0
                ),
                "total_no_of_sheets": (
                    float(prog.total_no_of_sheets)
                    if prog and prog.total_no_of_sheets
                    else 0
                ),
                "programer_created_by": prog.created_by if prog else "",
                # QA details
                "qa_processed_date": (
                    qa.processed_date.isoformat() if qa and qa.processed_date else ""
                ),
                "shift": qa.shift if qa else "",
                "qa_created_by": qa.created_by if qa else "",
                # Accounts details
                "invoice_no": acc.invoice_no if acc else "",
                "transporter_no": acc.transporter_no if acc else "",
                "payments_terms": acc.payments_terms if acc else "",
                "status": acc.status if acc else "",
                "acc_remarks": acc.remarks if acc else "",
                "acc_created_by": acc.created_by if acc else "",
            }

            # Machine logs logic
            machine_log_id = getattr(mat, "machine_log_id", None)
            logs = qa.qa_machine_details.all() if qa else []
            row = base_data.copy()
            row["machine_log_id"] = machine_log_id or ""

            if machine_log_id and logs:
                log = next((l for l in logs if l.id == machine_log_id), None)
                if log:
                    row.update(
                        {
                            "machine_name": log.machine_name or "",
                            "machine_date": log.date.isoformat() if log.date else "",
                            "machine_start": format_duration_as_time(log.start_time),
                            "machine_end": format_duration_as_time(log.end_time),
                            "machine_runtime": format_duration_as_time(log.runtime)
                            or "00:00",
                            "machine_gas_type": log.gas_type or "",
                            "machine_operator": log.operator or "",
                        }
                    )
                else:
                    row.update(
                        {
                            "machine_name": "",
                            "machine_date": "",
                            "machine_start": "",
                            "machine_end": "",
                            "machine_runtime": "",
                            "machine_operator": "",
                            "machine_gas_type": "",
                        }
                    )
            else:
                row.update(
                    {
                        "machine_name": "",
                        "machine_date": "",
                        "machine_start": "",
                        "machine_end": "",
                        "machine_runtime": "",
                        "machine_operator": "",
                        "machine_gas_type": "",
                    }
                )

            flat_rows.append(row)

        return Response(
            {
                "rows": flat_rows,
                "totals": totals,
                "count": total_count,
                "page": page,
                "page_size": page_size,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"ERROR in get_overall_details: {e}")
        return Response(
            {"status": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )



# Update Inward Product
@api_view(["PUT"])
def update_product_details(request, product_id):
    try:
        with transaction.atomic():
            # 1. FETCH PRODUCT
            try:
                prod = product_details.objects.get(id=product_id)
            except product_details.DoesNotExist:
                return Response({"msg": "Product not found"}, status=404)

            # ---------------------------
            # 2. UPDATE PRODUCT HEADER FIELDS
            # ---------------------------
            header_fields = [
                "sheet_type",
                "job_type",
                "inward_slip_number",
                "date",
                "worker_no",
                "company_name",
                "customer_name",
                "customer_dc_no",
                "contact_no",
                "programer_status",
                "qa_status",
                "outward_status",
                "created_at",
                "created_by",
            ]

            for field in header_fields:
                if field in request.data:
                    setattr(prod, field, request.data.get(field))
            prod.save()

            # ---------------------------
            # 3. SYNC MATERIALS (Update, Create, Delete) - Only if provided
            # ---------------------------
            if "materials" in request.data:
                materials_data = request.data.get("materials", [])
                processed_material_ids = []

                for mat_data in materials_data:
                    mat_id = mat_data.get("id")

                    if mat_id:
                        # UPDATE EXISTING MATERIAL
                        try:
                            # Convert to int to ensure consistent ID comparison
                            clean_id = int(mat_id)
                            mat = product_material.objects.get(
                                id=clean_id, product=prod
                            )
                            processed_material_ids.append(mat.id)
                        except (product_material.DoesNotExist, ValueError):
                            continue  # Skip if ID is invalid or doesn't belong to this product
                    else:
                        # CREATE NEW MATERIAL
                        mat = product_material(product=prod)

                    # Update Material Fields
                    mat.uid_no = mat_data.get("uid_no", mat.uid_no)
                    mat.heat_no = mat_data.get("heat_no", mat.heat_no)
                    mat.bay = mat_data.get("bay", mat.bay)
                    mat.mat_type = mat_data.get("mat_type", mat.mat_type)
                    mat.mat_grade = mat_data.get("mat_grade", mat.mat_grade)
                    mat.thick = (
                        to_decimal(mat_data.get("thick"))
                        if "thick" in mat_data
                        else mat.thick
                    )
                    mat.width = (
                        to_decimal(mat_data.get("width"))
                        if "width" in mat_data
                        else mat.width
                    )
                    mat.length = (
                        to_decimal(mat_data.get("length"))
                        if "length" in mat_data
                        else mat.length
                    )
                    mat.density = (
                        to_decimal(mat_data.get("density"))
                        if "density" in mat_data
                        else mat.density
                    )
                    mat.unit_weight = (
                        to_decimal(mat_data.get("unit_weight"))
                        if "unit_weight" in mat_data
                        else mat.unit_weight
                    )
                    mat.quantity = (
                        to_decimal(mat_data.get("quantity"))
                        if "quantity" in mat_data
                        else mat.quantity
                    )
                    mat.total_weight = (
                        to_decimal(mat_data.get("total_weight"))
                        if "total_weight" in mat_data
                        else mat.total_weight
                    )

                    # Dimensional data
                    mat.total_length = (
                        to_decimal(mat_data.get("total_length"))
                        if "total_length" in mat_data
                        else mat.total_length
                    )
                    mat.total_width = (
                        to_decimal(mat_data.get("total_width"))
                        if "total_width" in mat_data
                        else mat.total_width
                    )

                    mat.stock_due = mat_data.get("stock_due", mat.stock_due)
                    mat.remarks = mat_data.get("remarks", mat.remarks)
                    mat.programer_status = mat_data.get(
                        "programer_status", mat.programer_status
                    )
                    mat.qa_status = mat_data.get("qa_status", mat.qa_status)
                    mat.acc_status = mat_data.get("acc_status", mat.acc_status)

                    mat.save()

                    # Important: For new materials, capture their generated ID
                    if not mat_id:
                        processed_material_ids.append(mat.id)

                # 4. DELETE REMOVED MATERIALS
                # Safety: Only delete if were given a list of IDs to keep and it's not suspiciously empty
                if processed_material_ids:
                    product_material.objects.filter(product=prod).exclude(
                        id__in=processed_material_ids
                    ).delete()

            # --- AUTO-FILL PROGRAMMER FOR ONLY_FOLDING ---
            if prod.job_type == "Only Folding":
                from datetime import timedelta

                existing_mats = product_material.objects.filter(product=prod)
                for m in existing_mats:
                    if not programer_details.objects.filter(material=m).exists():
                        programer_details.objects.create(
                            material=m,
                            program_no="AUTO-FOLD",
                            program_date=timezone.now().date(),
                            processed_quantity=0,
                            balance_quantity=0,
                            processed_width=0,
                            processed_length=0,
                            remaining_width=0,
                            remaining_length=0,
                            used_weight=0,
                            number_of_sheets=0,
                            cut_length_per_sheet=0,
                            pierce_per_sheet=0,
                            processed_mins_per_sheet=0,
                            total_planned_hours=timedelta(0),
                            total_meters=0,
                            total_piercing=0,
                            total_used_weight=0,
                            total_no_of_sheets=0,
                            remarks="No Data Needed for Only Folding",
                            created_by="system",
                        )

            # 5. RE-SYNC STATUSES
            prod.refresh_statuses()

        return Response(
            {"msg": "Product and materials synchronized successfully"},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"msg": f"Error synchronizing product: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Add Product Material
@api_view(["POST"])
def add_product_material(request):
    product_detail = request.data.get("product_detail")
    mat_type = request.data.get("mat_type")
    mat_grade = request.data.get("mat_grade")
    uid_no = request.data.get("uid_no")
    heat_no = request.data.get("heat_no")
    thick = request.data.get("thick")
    width = request.data.get("width")
    length = request.data.get("length")
    total_length = request.data.get("total_length")
    total_width = request.data.get("total_width")
    density = request.data.get("density")
    unit_weight = request.data.get("unit_weight")
    quantity = request.data.get("quantity")
    total_weight = request.data.get("total_weight")
    bay = request.data.get("bay")
    stock_due = request.data.get("stock_due")
    remarks = request.data.get("remarks")
    print(product_detail)

    try:
        with transaction.atomic():
            product_obj = product_details.objects.get(id=product_detail)
            material = product_material.objects.create(
                product=product_obj,
                mat_type=mat_type,
                mat_grade=mat_grade,
                uid_no=uid_no,
                heat_no=heat_no,
                thick=to_decimal(thick),
                width=to_decimal(width),
                length=to_decimal(length),
                density=to_decimal(density),
                unit_weight=to_decimal(unit_weight),
                quantity=to_decimal(quantity),
                total_weight=to_decimal(total_weight),
                total_length=to_decimal(total_length),
                total_width=to_decimal(total_width),
                stock_due=stock_due,
                remarks=remarks,
                bay=bay,
            )

            # --- AUTO-FILL PROGRAMMER FOR ONLY_FOLDING ---
            if product_obj.job_type == "Only Folding":
                from datetime import timedelta

                programer_details.objects.create(
                    material=material,
                    program_no="AUTO-FOLD",
                    program_date=timezone.now().date(),
                    processed_quantity=0,
                    balance_quantity=0,
                    processed_width=0,
                    processed_length=0,
                    remaining_width=0,
                    remaining_length=0,
                    used_weight=0,
                    number_of_sheets=0,
                    cut_length_per_sheet=0,
                    pierce_per_sheet=0,
                    processed_mins_per_sheet=0,
                    total_planned_hours=timedelta(0),
                    total_meters=0,
                    total_piercing=0,
                    total_used_weight=0,
                    total_no_of_sheets=0,
                    remarks="No Data Needed for Only Folding",
                    created_by="system",
                )

        return Response({"msg": "successfully created"}, status=200)
    except product_details.DoesNotExist:
        return Response({"error": "product not found"}, status=404)
    except Exception as e:
        return Response({"error": f"Internal server error {e}"}, status=500)


# Delete Product Material
@api_view(["DELETE"])
def delete_product_material(request, product_id):
    print(product_id)
    try:
        product_mat = product_material.objects.get(id=product_id)
        product_mat.delete()
        print(product_mat)
        return Response({"message": "porduct material delete "}, status=200)
    except product_material.DoesNotExist:
        return Response({"error": "product not found"}, status=404)
    except Exception as e:
        return Response({"error": f"{e}"}, status=500)


@api_view(["GET"])
def export_all_flow_details(request):
    """
    Exports ALL fields from product_details, product_material, programer_details,
    qa_details, qa_machine_details, and acc_details.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    import io
    import gc

    # 1. Fetch All Data
    materials_qs = (
        product_material.objects.select_related("product")
        .prefetch_related(
            "programer_details_set",
            "qa_details_set",
            "qa_details_set__qa_machine_details",
            "acc_details_set",
        )
        .all()
        .order_by("product__date", "product__inward_slip_number", "id")
    )

    quotations_qs = (
        Quotation.objects.prefetch_related("items").all().order_by("doc_date", "id")
    )

    # 2. Define Headers
    header_map = [
        ("P_Slip_No", "inward_slip_number"),
        ("P_Date", "date"),
        ("P_Job_Type", "job_type"),
        ("P_Company", "company_name"),
        ("P_Customer", "customer_name"),
        ("P_Sheet_Type", "sheet_type"),
        ("P_Worker_No", "worker_no"),
        ("P_DC_No", "customer_dc_no"),
        ("P_Contact", "contact_no"),
        ("P_Job_Type", "job_type"),
        ("P_Prog_Status", "programer_status"),
        ("P_QA_Status", "qa_status"),
        ("P_Outward_Status", "outward_status"),
        ("P_Created_At", "created_at"),
        ("P_Created_By", "created_by"),
        ("M_ID", "id"),
        ("M_Bay", "bay"),
        ("M_Type", "mat_type"),
        ("M_Grade", "mat_grade"),
        ("M_UID", "uid_no"),
        ("M_Heat", "heat_no"),
        ("M_Thick", "thick"),
        ("M_Width", "width"),
        ("M_Length", "length"),
        ("M_Density", "density"),
        ("M_Unit_Weight", "unit_weight"),
        ("M_Qty", "quantity"),
        ("M_Total_Weight", "total_weight"),
        ("M_Total_Length", "total_length"),
        ("M_Total_Width", "total_width"),
        ("M_Stock_Due", "stock_due"),
        ("M_Remarks", "remarks"),
        ("M_Prog_Status", "programer_status"),
        ("M_QA_Status", "qa_status"),
        ("M_Acc_Status", "acc_status"),
        ("M_Created_At", "created_at"),
        ("M_Created_By", "created_by"),
        ("Prog_No", "program_no"),
        ("Prog_Date", "program_date"),
        ("Prog_Proc_Qty", "processed_quantity"),
        ("Prog_Bal_Qty", "balance_quantity"),
        ("Prog_Proc_Width", "processed_width"),
        ("Prog_Proc_Length", "processed_length"),
        ("Prog_Rem_Width", "remaining_width"),
        ("Prog_Rem_Length", "remaining_length"),
        ("Prog_Used_Weight", "used_weight"),
        ("Prog_No_Sheets", "number_of_sheets"),
        ("Prog_Cut_Len", "cut_length_per_sheet"),
        ("Prog_Pierce", "pierce_per_sheet"),
        ("Prog_Proc_Mins", "processed_mins_per_sheet"),
        ("Prog_Total_Plan_Hrs", "total_planned_hours"),
        ("Prog_Total_Meters", "total_meters"),
        ("Prog_Total_Piercing", "total_piercing"),
        ("Prog_Total_Used_Wt", "total_used_weight"),
        ("Prog_Total_No_Sheets", "total_no_of_sheets"),
        ("Prog_Remarks", "remarks"),
        ("Prog_Created_At", "created_at"),
        ("Prog_Created_By", "created_by"),
        ("QA_Date", "processed_date"),
        ("QA_Shift", "shift"),
        ("QA_Remarks", "remarks"),
        ("QA_Created_At", "created_at"),
        ("QA_Created_By", "created_by"),
        ("ML_Machine", "machine_name"),
        ("ML_Date", "date"),
        ("ML_Start", "start_time"),
        ("ML_End", "end_time"),
        ("ML_Runtime", "runtime"),
        ("ML_Operator", "operator"),
        ("ML_Gas", "gas_type"),
        ("Acc_Inv_No", "invoice_no"),
        ("Acc_Transporter", "transporter_no"),
        ("Acc_Pay_Terms", "payments_terms"),
        ("Acc_Status", "status"),
        ("Acc_Remarks", "remarks"),
        ("Acc_Created_At", "created_at"),
        ("Acc_Created_By", "created_by"),
    ]

    headers = [h[0] for h in header_map]
    wb = Workbook()
    ws = wb.active
    ws.title = "ERP_Full_Backup"

    style_header = {
        "font": Font(bold=True, color="FFFFFF"),
        "fill": PatternFill("solid", fgColor="1E40AF"),
        "alignment": Alignment(horizontal="center"),
    }
    ws.append(headers)
    for i, cell in enumerate(ws[1]):
        cell.font, cell.fill, cell.alignment = (
            style_header["font"],
            style_header["fill"],
            style_header["alignment"],
        )

    # 3. Filling Data (SAFETY: Convert to list early)
    all_materials = list(materials_qs)
    for mat in all_materials:
        prod = mat.product
        prog = (
            list(mat.programer_details_set.all())[0]
            if len(mat.programer_details_set.all()) > 0
            else None
        )
        qa = (
            list(mat.qa_details_set.all())[0]
            if len(mat.qa_details_set.all()) > 0
            else None
        )
        acc = (
            list(mat.acc_details_set.all())[0]
            if len(mat.acc_details_set.all()) > 0
            else None
        )

        machine_logs = list(qa.qa_machine_details.all()) if qa else []
        log_count = max(1, len(machine_logs))

        for idx in range(log_count):
            log = machine_logs[idx] if idx < len(machine_logs) else None
            row = []
            # Product + Material (Standardized)
            row += [
                prod.inward_slip_number,
                prod.date.isoformat() if prod.date else "",
                prod.job_type,
                prod.company_name,
                prod.customer_name,
                prod.sheet_type,
                prod.worker_no,
                prod.customer_dc_no,
                prod.contact_no,
                prod.programer_status,
                prod.qa_status,
                prod.outward_status,
                prod.created_at.isoformat() if prod.created_at else "",
                prod.created_by,
            ]
            row += [
                mat.id,
                mat.bay,
                mat.mat_type,
                mat.mat_grade,
                mat.uid_no,
                mat.heat_no,
                float(mat.thick or 0),
                float(mat.width or 0),
                float(mat.length or 0),
                float(mat.density or 0),
                float(mat.unit_weight or 0),
                float(mat.quantity or 0),
                float(mat.total_weight or 0),
                float(mat.total_length or 0),
                float(mat.total_width or 0),
                mat.stock_due,
                mat.remarks,
                mat.programer_status,
                mat.qa_status,
                mat.acc_status,
                mat.created_at.isoformat() if mat.created_at else "",
                mat.created_by,
            ]

            # Programmer
            if prog:
                row += [
                    prog.program_no,
                    prog.program_date.isoformat() if prog.program_date else "",
                    float(prog.processed_quantity or 0),
                    float(prog.balance_quantity or 0),
                    float(prog.processed_width or 0),
                    float(prog.processed_length or 0),
                    float(prog.remaining_width or 0),
                    float(prog.remaining_length or 0),
                    float(prog.used_weight or 0),
                    float(prog.number_of_sheets or 0),
                    float(prog.cut_length_per_sheet or 0),
                    float(prog.pierce_per_sheet or 0),
                    float(prog.processed_mins_per_sheet or 0),
                    format_duration_as_time(prog.total_planned_hours),
                    float(prog.total_meters or 0),
                    float(prog.total_piercing or 0),
                    float(prog.total_used_weight or 0),
                    float(prog.total_no_of_sheets or 0),
                    prog.remarks,
                    prog.created_at.isoformat() if prog.created_at else "",
                    prog.created_by,
                ]
            else:
                row += [""] * 21

            # QA
            if qa:
                row += [
                    qa.processed_date.isoformat() if qa.processed_date else "",
                    qa.shift,
                    qa.remarks,
                    qa.created_at.isoformat() if qa.created_at else "",
                    qa.created_by,
                ]
            else:
                row += [""] * 5

            # Machine Logs
            if log:
                row += [
                    log.machine_name,
                    log.date.isoformat() if log.date else "",
                    format_duration_as_time(log.start_time),
                    format_duration_as_time(log.end_time),
                    format_duration_as_time(log.runtime),
                    log.operator,
                    log.gas_type,
                ]
            else:
                row += [""] * 7

            # Accounts
            if acc:
                row += [
                    acc.invoice_no,
                    acc.transporter_no,
                    acc.payments_terms,
                    acc.status,
                    acc.remarks,
                    acc.created_at.isoformat() if acc.created_at else "",
                    acc.created_by,
                ]
            else:
                row += [""] * 7
            ws.append(row)

    # Quotations Sheet
    ws2 = wb.create_sheet("Quotations_Backup")
    q_header_map = [
        ("Q_Doc_No", "doc_no"),
        ("Q_Date", "doc_date"),
        ("Q_Company", "company_name"),
        ("Q_Customer", "customer_name"),
        ("Q_Email", "email"),
        ("Q_Contact", "contact"),
        ("Q_GST_No", "customer_gst_no"),
        ("Q_Net_Amt", "net_amount"),
        ("Q_GST_Amt", "gst_amount"),
        ("Q_GST_Pct", "gst_percentage"),
        ("Q_Total_Amt", "total_amount"),
        ("Q_Extra_Note", "extra_note"),
        ("Q_Pay_Terms", "payment_terms"),
        ("Q_Mat_Terms", "material_terms"),
        ("Q_Trans_Terms", "transport_terms"),
        ("Q_Val_Terms", "validity_terms"),
        ("Q_Given_By", "quote_given_by"),
        ("Q_App_Name", "approver_name"),
        ("Q_App_Desig", "approver_designation"),
        ("Q_App_Contact", "approver_contact"),
        ("Q_Submission", "mode_of_submission"),
        ("Q_Type", "quote_type"),
        ("Q_Client_Remarks", "client_remarks"),
        ("Q_Billed_Val", "billed_value"),
        ("Q_Status", "status"),
        ("Q_Remarks", "remarks"),
        ("Q_Created_At", "created_at"),
        ("Q_Created_By", "created_by"),
        ("QI_Desc", "description"),
        ("QI_Mat", "material"),
        ("QI_UOM", "uom"),
        ("QI_Qty", "quantity"),
        ("QI_Rate", "rate"),
        ("QI_Total", "total"),
        ("QI_Remarks", "remarks"),
        ("QI_Created_At", "created_at"),
        ("QI_Created_By", "created_by"),
    ]
    ws2.append([h[0] for h in q_header_map])
    for cell in ws2[1]:
        cell.font, cell.fill, cell.alignment = (
            style_header["font"],
            style_header["fill"],
            style_header["alignment"],
        )

    all_quotations = list(quotations_qs)
    for quote in all_quotations:
        items = list(quote.items.all())
        count = max(1, len(items))
        for idx in range(count):
            it = items[idx] if idx < len(items) else None
            row = [
                quote.doc_no,
                quote.doc_date.isoformat() if quote.doc_date else "",
                quote.company_name,
                quote.customer_name,
                quote.email,
                quote.contact,
                quote.customer_gst_no,
                float(quote.net_amount or 0),
                float(quote.gst_amount or 0),
                float(quote.gst_percentage or 0),
                float(quote.total_amount or 0),
                quote.extra_note,
                quote.payment_terms,
                quote.material_terms,
                quote.transport_terms,
                quote.validity_terms,
                quote.quote_given_by,
                quote.approver_name,
                quote.approver_designation,
                quote.approver_contact,
                quote.mode_of_submission,
                quote.quote_type,
                quote.client_remarks,
                float(quote.billed_value or 0),
                quote.status,
                quote.remarks,
                quote.created_at.isoformat() if quote.created_at else "",
                quote.created_by,
            ]
            if it:
                row += [
                    it.description,
                    it.material,
                    it.uom,
                    float(it.quantity or 0),
                    float(it.rate or 0),
                    float(it.total or 0),
                    it.remarks,
                    it.created_at.isoformat() if it.created_at else "",
                    it.created_by,
                ]
            else:
                row += [""] * 9
            ws2.append(row)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    response = HttpResponse(
        stream.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="Flow_Full_Backup_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    )

    # Cleanup memory for VPS
    del all_materials, all_quotations, wb
    gc.collect()
    return response


@api_view(["POST"])
def import_all_flow_details(request):
    """
    Full Restore Logic: Updates every field matched from Excel.
    """
    from openpyxl import load_workbook
    from datetime import datetime

    file = request.FILES.get("file")
    if not file:
        return Response({"error": "No file"}, status=400)

    try:
        wb = load_workbook(file, data_only=True)
        ws = wb.active
        rows = list(ws.rows)
        if len(rows) < 2:
            return Response({"error": "Empty file"}, status=400)

        header_map = {cell.value: i for i, cell in enumerate(rows[0]) if cell.value}

        def get_v(row, key, df=None):
            idx = header_map.get(key)
            if idx is None:
                return df
            v = row[idx].value
            if v == "" or v is None:
                return df
            return v

        stats = {
            "products": 0,
            "materials": 0,
            "updates": 0,
            "quotations": 0,
            "q_updates": 0,
        }
        # Session cache to avoid duplicating materials when multiple rows exist (due to multiple machine logs)
        session_materials = {}
        session_quotations = {}

        with transaction.atomic():
            # ----------------------------------------------------
            # 1. PROCESS MAIN ERP DATA (Sheet 1)
            # ----------------------------------------------------
            for row in rows[1:]:
                slip_no = get_v(row, "P_Slip_No")
                if not slip_no:
                    continue

                # 1. Product Details
                prod, p_created = product_details.objects.get_or_create(
                    inward_slip_number=slip_no
                )
                prod.date = get_v(row, "P_Date", prod.date)
                prod.job_type = get_v(row, "P_Job_Type", prod.job_type)
                prod.company_name = get_v(row, "P_Company", prod.company_name)
                prod.customer_name = get_v(row, "P_Customer", prod.customer_name)
                prod.sheet_type = get_v(row, "P_Sheet_Type", prod.sheet_type)
                prod.worker_no = get_v(row, "P_Worker_No", prod.worker_no)
                prod.customer_dc_no = get_v(row, "P_DC_No", prod.customer_dc_no)
                prod.contact_no = get_v(row, "P_Contact", prod.contact_no)
                prod.job_type = get_v(row, "P_Job_Type", prod.job_type)
                prod.programer_status = get_v(
                    row, "P_Prog_Status", prod.programer_status
                )
                prod.qa_status = get_v(row, "P_QA_Status", prod.qa_status)
                prod.outward_status = get_v(
                    row, "P_Outward_Status", prod.outward_status
                )
                prod.created_by = get_v(row, "P_Created_By", prod.created_by)
                p_at = get_v(row, "P_Created_At")
                if p_at:
                    prod.created_at = p_at
                prod.save()
                if p_created:
                    stats["products"] += 1

                # 2. Material
                mat_id = get_v(row, "M_ID")
                mat = None

                # Check session cache first
                if mat_id in session_materials:
                    mat = session_materials[mat_id]
                else:
                    # Match by existing ID in DB
                    # if mat_id: mat = product_material.objects.filter(id=mat_id, product=prod).first()

                    # if not mat:
                    #     mat = product_material.objects.create(product=prod)

                    mat = None

                    # 1. Try by DB ID (fast path)
                    if mat_id:
                        mat = product_material.objects.filter(
                            id=mat_id, product=prod
                        ).first()

                    # 2. Fallback: match by UNIQUE COMBINATION
                    if not mat:
                        mat = product_material.objects.filter(
                            product=prod,
                            bay=get_v(row, "M_Bay"),
                            mat_type=get_v(row, "M_Type"),
                            mat_grade=get_v(row, "M_Grade"),
                            thick=to_decimal(get_v(row, "M_Thick")),
                            width=to_decimal(get_v(row, "M_Width")),
                            length=to_decimal(get_v(row, "M_Length")),
                        ).first()

                    # 3. Create only if NOT found
                    if not mat:
                        mat = product_material.objects.create(product=prod)
                        stats["materials"] += 1

                        # stats["materials"] += 1

                    # Store in session cache
                    if mat_id:
                        session_materials[mat_id] = mat

                mat.bay = get_v(row, "M_Bay", mat.bay)
                mat.uid_no = get_v(row, "M_UID", mat.uid_no)
                mat.heat_no = get_v(row, "M_Heat", mat.heat_no)
                mat.mat_type = get_v(row, "M_Type", mat.mat_type)
                mat.mat_grade = get_v(row, "M_Grade", mat.mat_grade)
                mat.thick = to_decimal(get_v(row, "M_Thick"))
                mat.width = to_decimal(get_v(row, "M_Width"))
                mat.length = to_decimal(get_v(row, "M_Length"))
                mat.density = get_v(row, "M_Density")
                mat.unit_weight = to_decimal(get_v(row, "M_Unit_Weight"))
                mat.quantity = to_decimal(get_v(row, "M_Qty"))
                mat.total_weight = to_decimal(get_v(row, "M_Total_Weight"))
                mat.total_length = to_decimal(get_v(row, "M_Total_Length"))
                mat.total_width = to_decimal(get_v(row, "M_Total_Width"))
                mat.stock_due = get_v(row, "M_Stock_Due", mat.stock_due)
                mat.remarks = get_v(row, "M_Remarks", mat.remarks)
                mat.programer_status = get_v(row, "M_Prog_Status", mat.programer_status)
                mat.qa_status = get_v(row, "M_QA_Status", mat.qa_status)
                mat.acc_status = get_v(row, "M_Acc_Status", mat.acc_status)
                mat.created_by = get_v(row, "M_Created_By", mat.created_by)
                m_at = get_v(row, "M_Created_At")
                if m_at:
                    mat.created_at = m_at
                mat.save()
                stats["updates"] += 1

                # 3. Programmer
                prog_no = get_v(row, "Prog_No")
                if prog_no:
                    # Provide default program_date for newly created records to avoid NOT NULL constraint error
                    prog, created = programer_details.objects.get_or_create(
                        material=mat,
                        program_no=prog_no,
                        defaults={"program_date": timezone.now().date()},  # fallback
                    )
                    prog.program_no = prog_no

                    p_date = get_v(row, "Prog_Date")
                    if p_date:
                        if isinstance(p_date, str):
                            try:
                                prog.program_date = datetime.fromisoformat(
                                    p_date
                                ).date()
                            except:
                                pass
                        elif isinstance(p_date, (datetime, d_date)):
                            prog.program_date = p_date
                    elif created:
                        # ensure NOT NULL safety
                        prog.program_date = timezone.now().date()

                    prog.processed_quantity = to_decimal(get_v(row, "Prog_Proc_Qty"))
                    prog.balance_quantity = to_decimal(get_v(row, "Prog_Bal_Qty"))
                    prog.processed_width = to_decimal(get_v(row, "Prog_Proc_Width"))
                    prog.processed_length = to_decimal(get_v(row, "Prog_Proc_Length"))
                    prog.remaining_width = to_decimal(get_v(row, "Prog_Rem_Width"))
                    prog.remaining_length = to_decimal(get_v(row, "Prog_Rem_Length"))
                    prog.used_weight = to_decimal(get_v(row, "Prog_Used_Weight"))
                    prog.number_of_sheets = to_decimal(get_v(row, "Prog_No_Sheets"))
                    prog.cut_length_per_sheet = to_decimal(get_v(row, "Prog_Cut_Len"))
                    prog.pierce_per_sheet = to_decimal(get_v(row, "Prog_Pierce"))
                    prog.processed_mins_per_sheet = to_decimal(
                        get_v(row, "Prog_Proc_Mins")
                    )
                    prog.total_planned_hours = to_duration(
                        get_v(row, "Prog_Total_Plan_Hrs")
                    )
                    prog.total_meters = to_decimal(get_v(row, "Prog_Total_Meters"))
                    prog.total_piercing = to_decimal(get_v(row, "Prog_Total_Piercing"))
                    prog.total_used_weight = to_decimal(
                        get_v(row, "Prog_Total_Used_Wt")
                    )
                    prog.total_no_of_sheets = to_decimal(
                        get_v(row, "Prog_Total_No_Sheets")
                    )
                    prog.remarks = get_v(row, "Prog_Remarks", prog.remarks)
                    prog.created_by = get_v(row, "Prog_Created_By", prog.created_by)
                    pr_at = get_v(row, "Prog_Created_At")
                    if pr_at:
                        prog.created_at = pr_at
                    prog.save()

                # 4. QA & Machine Logs
                qa_date = get_v(row, "QA_Date")
                if qa_date:
                    qa, _ = qa_details.objects.get_or_create(material=mat)
                    qa.processed_date = qa_date
                    qa.shift = get_v(row, "QA_Shift", qa.shift)
                    qa.remarks = get_v(row, "QA_Remarks", qa.remarks)
                    qa.created_by = get_v(row, "QA_Created_By", qa.created_by)
                    q_at = get_v(row, "QA_Created_At")
                    if q_at:
                        qa.created_at = q_at
                    qa.save()

                    mach = get_v(row, "ML_Machine")
                    if mach:
                        # Machine logs are tricky if multiple, we update existing or create
                        # For simplicity in 100% backup, we match by machine and start_time
                        ml_start = to_duration(get_v(row, "ML_Start"))
                        ml_date = get_v(row, "ML_Date")
                        ml, _ = qa_machine_details.objects.get_or_create(
                            qa=qa, machine_name=mach, start_time=ml_start, date=ml_date
                        )
                        ml.date = ml_date or ml.date
                        ml.end_time = to_duration(get_v(row, "ML_End"))
                        ml.runtime = to_duration(get_v(row, "ML_Runtime"))
                        ml.operator = get_v(row, "ML_Operator", ml.operator)
                        ml.gas_type = get_v(row, "ML_Gas", ml.gas_type)
                        ml.save()

                # 5. Accounts
                inv_no = get_v(row, "Acc_Inv_No")
                if inv_no:
                    acc, _ = acc_details.objects.get_or_create(
                        material=mat, invoice_no=inv_no
                    )
                    acc.invoice_no = inv_no
                    acc.transporter_no = get_v(
                        row, "Acc_Transporter", acc.transporter_no
                    )
                    acc.payments_terms = get_v(row, "Acc_Pay_Terms", acc.payments_terms)
                    acc.status = get_v(row, "Acc_Status", acc.status)
                    acc.remarks = get_v(row, "Acc_Remarks", acc.remarks)
                    acc.created_by = get_v(row, "Acc_Created_By", acc.created_by)
                    a_at = get_v(row, "Acc_Created_At")
                    if a_at:
                        acc.created_at = a_at
                    acc.save()

            # ----------------------------------------------------
            # 2. PROCESS QUOTATIONS (Sheet 2)
            # ----------------------------------------------------
            if "Quotations_Backup" in wb.sheetnames:
                ws_q = wb["Quotations_Backup"]
                q_rows = list(ws_q.rows)
                if len(q_rows) >= 2:
                    q_header_map = {
                        cell.value: i for i, cell in enumerate(q_rows[0]) if cell.value
                    }

                    def get_qv(row, key, df=None):
                        idx = q_header_map.get(key)
                        if idx is None:
                            return df
                        v = row[idx].value
                        if v == "" or v is None:
                            return df
                        return v

                    for q_row in q_rows[1:]:
                        doc_no = get_qv(q_row, "Q_Doc_No")
                        if not doc_no:
                            continue

                        quote = session_quotations.get(doc_no)
                        q_created = False
                        if not quote:
                            quote = Quotation.objects.filter(doc_no=doc_no).first()
                            if not quote:
                                quote = Quotation(doc_no=doc_no)
                                q_created = True
                                stats["quotations"] += 1

                            session_quotations[doc_no] = quote

                        if q_created or doc_no in session_quotations:
                            # Update fields
                            q_d = get_qv(q_row, "Q_Date")
                            if q_d:
                                if isinstance(q_d, str):
                                    try:
                                        quote.doc_date = datetime.fromisoformat(
                                            q_d
                                        ).date()
                                    except:
                                        pass
                                elif isinstance(q_d, (datetime, d_date)):
                                    quote.doc_date = q_d

                            quote.company_name = get_qv(
                                q_row, "Q_Company", quote.company_name
                            )
                            quote.customer_name = get_qv(
                                q_row, "Q_Customer", quote.customer_name
                            )
                            quote.email = get_qv(q_row, "Q_Email", quote.email)
                            quote.contact = get_qv(q_row, "Q_Contact", quote.contact)
                            quote.customer_gst_no = get_qv(
                                q_row, "Q_GST_No", quote.customer_gst_no
                            )

                            quote.net_amount = (
                                to_decimal(get_qv(q_row, "Q_Net_Amt"))
                                or quote.net_amount
                            )
                            quote.gst_amount = (
                                to_decimal(get_qv(q_row, "Q_GST_Amt"))
                                or quote.gst_amount
                            )
                            quote.gst_percentage = (
                                to_decimal(get_qv(q_row, "Q_GST_Pct"))
                                or quote.gst_percentage
                            )
                            quote.total_amount = (
                                to_decimal(get_qv(q_row, "Q_Total_Amt"))
                                or quote.total_amount
                            )

                            quote.extra_note = get_qv(
                                q_row, "Q_Extra_Note", quote.extra_note
                            )
                            quote.payment_terms = get_qv(
                                q_row, "Q_Pay_Terms", quote.payment_terms
                            )
                            quote.material_terms = get_qv(
                                q_row, "Q_Mat_Terms", quote.material_terms
                            )
                            quote.transport_terms = get_qv(
                                q_row, "Q_Trans_Terms", quote.transport_terms
                            )
                            quote.validity_terms = get_qv(
                                q_row, "Q_Val_Terms", quote.validity_terms
                            )

                            quote.quote_given_by = get_qv(
                                q_row, "Q_Given_By", quote.quote_given_by
                            )
                            quote.approver_name = get_qv(
                                q_row, "Q_App_Name", quote.approver_name
                            )
                            quote.approver_designation = get_qv(
                                q_row, "Q_App_Desig", quote.approver_designation
                            )
                            quote.approver_contact = get_qv(
                                q_row, "Q_App_Contact", quote.approver_contact
                            )
                            quote.mode_of_submission = get_qv(
                                q_row, "Q_Submission", quote.mode_of_submission
                            )
                            quote.quote_type = get_qv(q_row, "Q_Type", quote.quote_type)
                            quote.client_remarks = get_qv(
                                q_row, "Q_Client_Remarks", quote.client_remarks
                            )
                            quote.billed_value = (
                                to_decimal(get_qv(q_row, "Q_Billed_Val"))
                                or quote.billed_value
                            )
                            quote.status = get_qv(q_row, "Q_Status", quote.status)
                            quote.remarks = get_qv(q_row, "Q_Remarks", quote.remarks)
                            quote.created_by = get_qv(
                                q_row, "Q_Created_By", quote.created_by
                            )

                            q_at = get_qv(q_row, "Q_Created_At")
                            if q_at:
                                quote.created_at = q_at

                            quote.save()
                            stats["q_updates"] += 1

                        # Process Items
                        qi_desc = get_qv(q_row, "QI_Desc")
                        qi_mat = get_qv(q_row, "QI_Mat")

                        if qi_desc or qi_mat:
                            # To handle updates to existing items, we'd need some identifier.
                            # Without distinct ID exported for items, we can match by description & material
                            # or just recreate if missing.
                            # If we just recreate, they get duplicated on repeated imports.
                            # So let's match by quote + desc + material:
                            q_item, _ = QuotationItem.objects.get_or_create(
                                quotation=quote, description=qi_desc, material=qi_mat
                            )
                            q_item.uom = get_qv(q_row, "QI_UOM", q_item.uom)
                            q_item.quantity = (
                                to_decimal(get_qv(q_row, "QI_Qty")) or q_item.quantity
                            )
                            q_item.rate = (
                                to_decimal(get_qv(q_row, "QI_Rate")) or q_item.rate
                            )
                            q_item.total = (
                                to_decimal(get_qv(q_row, "QI_Total")) or q_item.total
                            )
                            q_item.remarks = get_qv(q_row, "QI_Remarks", q_item.remarks)
                            q_item.created_by = get_qv(
                                q_row, "QI_Created_By", q_item.created_by
                            )

                            qi_at = get_qv(q_row, "QI_Created_At")
                            if qi_at:
                                q_item.created_at = qi_at
                            q_item.save()

        return Response({"status": True, "message": "Import completed", "stats": stats})
    except Exception as e:

        import logging

        logger = logging.getLogger(__name__)
        logger.error("Import failed", exc_info=True)
        return Response({"error": str(e)}, status=500)


