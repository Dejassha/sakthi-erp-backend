from django.urls import path
from api import views

urlpatterns = [
    # Quotation Reports & Export
    path('get_quotation_reports/', views.get_quotation_reports, name='get_quotation_reports'),
    path('export_quotation_reports_excel/', views.export_quotation_reports_excel, name='export_quotation_reports_excel'),
    # Inventory History
    path('get_inventory_history/', views.get_inventory_history, name='get_inventory_history'),
    path('export_inventory_history_excel/', views.export_inventory_history_excel, name='export_inventory_history_excel'),
    # Maintenance Reports & Export
    path('get_periodic_maintenance_reports/', views.get_periodic_maintenance_reports, name='get_periodic_maintenance_reports'),
    path('get_breakdown_maintenance_reports/', views.get_breakdown_maintenance_reports, name='get_breakdown_maintenance_reports'),
    path('export_periodic_maintenance_excel/', views.export_periodic_maintenance_excel, name='export_periodic_maintenance_excel'),
    path('export_breakdown_maintenance_excel/', views.export_breakdown_maintenance_excel, name='export_breakdown_maintenance_excel'),
]


