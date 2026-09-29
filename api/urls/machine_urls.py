from django.urls import path
from api import views

urlpatterns = [
    path('get_machines/', views.get_machines, name='get_machines'),
    path('add_machine/', views.add_machine, name='add_machine'),
    path('update_machine/<int:id>/', views.update_machine, name='update_machine'),
    path('delete_machine/<int:id>/', views.delete_machine, name='delete_machine'),
    path('add_maintenance_schedule/', views.add_maintenance_schedule, name='add_maintenance_schedule'),
    path('update_maintenance_schedule/<int:id>/', views.update_maintenance_schedule, name='update_maintenance_schedule'),
    path('delete_maintenance_schedule/<int:id>/', views.delete_maintenance_schedule, name='delete_maintenance_schedule'),
    path('approve_maintenance/', views.approve_maintenance, name='approve_maintenance'),
    path('get_maintenance_history/', views.get_maintenance_history, name='get_maintenance_history'),
    path('get_breakdown_maintenance/', views.get_breakdown_maintenance, name='get_breakdown_maintenance'),
    path('get_breakdown_maintenance_logs/', views.get_breakdown_maintenance_logs, name='get_breakdown_maintenance_logs'),
    path('add_breakdown_maintenance/', views.add_breakdown_maintenance, name='add_breakdown_maintenance'),
    path('update_breakdown_maintenance/<int:pk>/', views.update_breakdown_maintenance, name='update_breakdown_maintenance'),
    path('delete_breakdown_maintenance/<int:pk>/', views.delete_breakdown_maintenance, name='delete_breakdown_maintenance'),
    path('get_gas_details/', views.get_gas_details, name='get_gas_details'),
    path('add_gas_details/', views.add_gas_details, name='add_gas_details'),
    path('update_gas_details/<int:pk>/', views.update_gas_details, name='update_gas_details'),
    path('delete_gas_details/<int:pk>/', views.delete_gas_details, name='delete_gas_details'),
]
