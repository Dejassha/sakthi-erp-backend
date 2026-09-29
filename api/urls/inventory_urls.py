from django.urls import path
from api import views

urlpatterns = [
    path('get_inventory_part_names/', views.get_inventory_part_names, name='get_inventory_part_names'),
    path('add_inventory_part_name/', views.add_inventory_part_name, name='add_inventory_part_name'),
    path('delete_inventory_part_name/<int:pk>/', views.delete_inventory_part_name, name='delete_inventory_part_name'),
    path('get_inventory_usage_types/', views.get_inventory_usage_types, name='get_inventory_usage_types'),
    path('add_inventory_usage_type/', views.add_inventory_usage_type, name='add_inventory_usage_type'),
    path('delete_inventory_usage_type/<int:pk>/', views.delete_inventory_usage_type, name='delete_inventory_usage_type'),
    path('get_inventory_parts/', views.get_inventory_parts, name='get_inventory_parts'),
    path('add_inventory_part/', views.add_inventory_part, name='add_inventory_part'),
    path('update_inventory_part/<int:pk>/', views.update_inventory_part, name='update_inventory_part'),
    path('delete_inventory_part/<int:pk>/', views.delete_inventory_part, name='delete_inventory_part'),
    path('get_inventory_usage/', views.get_inventory_usage, name='get_inventory_usage'),
    path('add_inventory_usage/', views.add_inventory_usage, name='add_inventory_usage'),
    path('update_inventory_usage/<int:pk>/', views.update_inventory_usage, name='update_inventory_usage'),
    path('delete_inventory_usage/<int:pk>/', views.delete_inventory_usage, name='delete_inventory_usage'),
    path('get_pending_materials/', views.get_pending_materials, name='get_pending_materials'),
    path('update_pending_material/<int:pk>/', views.update_pending_material, name='update_pending_material'),
    path('record_inventory_history/', views.record_inventory_history, name='record_inventory_history'),
]

