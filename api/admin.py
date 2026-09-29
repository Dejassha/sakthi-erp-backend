from django.contrib import admin
from .models import (
    Role,
    All_User,
    Admin,
    company,
    Machine,
    MaintenanceSchedule,
    MachineMaintenanceLog,
    InventoryPartName,
    InventoryPurpose,
    InventoryPart,
    InventoryUsage,
    PendingMaterial,
    InventoryHistory,
    InventoryRateHistory,
    BreakdownMaintenance,
    machine_operator,
    material_type,
    product_details,
    product_material,
    programer_details,
    qa_details,
    qa_machine_details,
    acc_details,
    Quotation,
    QuotationItem,
    QuotationNote,
    GasDetails,
    KPIRecord,
    KPITemplate,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("id",)


@admin.register(All_User)
class AllUserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "isAdmin", "has_user_management")
    list_filter = ("isAdmin", "has_user_management")
    search_fields = ("username", "email")
    filter_horizontal = ("role",)
    ordering = ("-id",)
    list_per_page = 25


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ("id", "user")
    search_fields = ("user__username",)


@admin.register(company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company_name",
        "customer_name",
        "contact_no",
        "created_by",
        "created_at",
    )
    search_fields = ("company_name", "customer_name", "contact_no")
    list_filter = ("created_at",)
    ordering = ("-id",)
    list_per_page = 25


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("id", "machine_name", "does_need_gas", "created_by", "created_at")
    list_filter = ("does_need_gas", "created_at")
    search_fields = ("machine_name",)
    ordering = ("-id",)


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "machine",
        "maintenance_name",
        "interval_days",
        "last_maintenance_date",
        "next_maintenance_date",
        "status",
    )
    list_filter = ("status", "machine")
    search_fields = ("maintenance_name", "machine__machine_name")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(MachineMaintenanceLog)
class MachineMaintenanceLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "machine",
        "maintenance_name",
        "scheduled_date",
        "approved_date",
        "status",
        "approved_by",
    )
    list_filter = ("status", "machine", "approved_date")
    search_fields = ("maintenance_name", "machine__machine_name", "approved_by")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(InventoryPartName)
class InventoryPartNameAdmin(admin.ModelAdmin):
    list_display = ("id", "part_name", "created_by", "created_at")
    search_fields = ("part_name",)
    ordering = ("-id",)


@admin.register(InventoryPurpose)
class InventoryPurposeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    search_fields = ("name",)
    ordering = ("-id",)


@admin.register(InventoryPart)
class InventoryPartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "part_name",
        "spare_id",
        "item_code",
        "stock_quantity",
        "available_quantity",
        "status",
        "created_at",
    )
    list_filter = ("status", "machine")
    search_fields = ("part_name", "spare_id", "item_code", "batch_number")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(InventoryUsage)
class InventoryUsageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "part",
        "machine_name",
        "used_quantity",
        "used_by",
        "used_date",
        "created_at",
    )
    list_filter = ("used_date",)
    search_fields = ("part__part_name", "machine_name", "used_by")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(PendingMaterial)
class PendingMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "part_name",
        "requested_quantity",
        "priority",
        "status",
        "request_date",
    )
    list_filter = ("status", "priority", "request_date")
    search_fields = ("part_name", "requested_by")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "part_name", "action", "quantity", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("part_name", "user")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(InventoryRateHistory)
class InventoryRateHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "part", "rate", "created_at")
    search_fields = ("part__part_name",)
    ordering = ("-id",)


@admin.register(BreakdownMaintenance)
class BreakdownMaintenanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "record_number",
        "machine",
        "breakdown_date",
        "shift",
        "total_downtime_hours",
        "created_by",
    )
    list_filter = ("shift", "breakdown_date", "machine")
    search_fields = (
        "record_number",
        "machine__machine_name",
        "operator_name",
        "supervisor",
    )
    ordering = ("-id",)
    list_per_page = 25


@admin.register(machine_operator)
class MachineOperatorAdmin(admin.ModelAdmin):
    list_display = ("id", "operator_name", "created_by", "created_at")
    search_fields = ("operator_name",)
    ordering = ("-id",)


@admin.register(material_type)
class MaterialTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "material_name", "density_value", "created_by", "created_at")
    search_fields = ("material_name",)
    ordering = ("-id",)


@admin.register(product_details)
class ProductDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "inward_slip_number",
        "company_name",
        "customer_name",
        "job_type",
        "programer_status",
        "qa_status",
        "outward_status",
        "created_at",
    )
    list_filter = ("job_type", "programer_status", "qa_status", "outward_status")
    search_fields = ("inward_slip_number", "company_name", "customer_name")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(product_material)
class ProductMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "uid_no",
        "mat_type",
        "mat_grade",
        "programer_status",
        "qa_status",
        "acc_status",
    )
    list_filter = ("mat_type", "programer_status", "qa_status", "acc_status")
    search_fields = ("uid_no", "mat_type", "mat_grade")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(programer_details)
class ProgramerDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "program_no",
        "material",
        "program_date",
        "created_by",
        "created_at",
    )
    list_filter = ("program_date",)
    search_fields = ("program_no",)
    ordering = ("-id",)
    list_per_page = 25


@admin.register(qa_details)
class QaDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "material",
        "processed_date",
        "shift",
        "created_by",
        "created_at",
    )
    list_filter = ("shift", "processed_date")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(qa_machine_details)
class QaMachineDetailsAdmin(admin.ModelAdmin):
    list_display = ("id", "qa", "machine_name", "date", "operator", "gas_type")
    list_filter = ("gas_type", "date")
    search_fields = ("machine_name", "operator")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(acc_details)
class AccDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "material",
        "invoice_no",
        "transporter_no",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("invoice_no", "transporter_no")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "doc_no",
        "company_name",
        "customer_name",
        "total_amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("doc_no", "company_name", "customer_name")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(QuotationItem)
class QuotationItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "quotation",
        "description",
        "material",
        "quantity",
        "rate",
        "total",
    )
    search_fields = ("description", "material")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(QuotationNote)
class QuotationNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "note", "created_by", "created_at")
    ordering = ("-id",)


@admin.register(GasDetails)
class GasDetailsAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    ordering = ("-id",)


@admin.register(KPIRecord)
class KPIRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "group_id",
        "month",
        "s_no",
        "kpi_category",
        "kpi_parameter",
        "target",
        "achieved",
    )
    list_filter = ("kpi_category", "month")
    search_fields = ("kpi_parameter", "month")
    ordering = ("-id",)
    list_per_page = 25


@admin.register(KPITemplate)
class KPITemplateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "group_id",
        "name",
        "s_no",
        "kpi_category",
        "kpi_parameter",
        "target",
    )
    list_filter = ("kpi_category", "group_id")
    search_fields = ("name", "kpi_parameter")
    ordering = ("id",)
    list_per_page = 25
