from django.urls import path
from api import views

urlpatterns = [
    path('add_inward_details/', views.add_inward_details, name='add_inward_details'),
    path('get_inward_details/', views.get_inward_details, name='get_inward_details'),
    path('get_dashboard_list/', views.get_dashboard_list, name='get_dashboard_list'),
    path('get_dashboard_details/', views.get_dashboard_details, name='get_dashboard_details'),
    path('check_slip_number/', views.check_slip_number, name='check_slip_number'),
    path('get_latest_slip_number/', views.get_latest_slip_number, name='get_latest_slip_number'),
    path('get_materials_by_product/', views.get_materials_by_product, name='get_materials_by_product'),
    path('get_overall_details/', views.get_overall_details, name='get_overall_details'),
    path('export_selected_rows/', views.export_selected_rows, name='export_selected_rows'),
    path('export_all_flow_details/', views.export_all_flow_details, name='export_all_flow_details'),
    path('import_all_flow_details/', views.import_all_flow_details, name='import_all_flow_details'),
    path('update_product_details/<int:product_id>/', views.update_product_details, name='update_product_details'),
    path('add_product_material/', views.add_product_material, name='add_product_material'),
    path('delete_product_material/<int:product_id>/', views.delete_product_material, name='delete_product_material'),
]
