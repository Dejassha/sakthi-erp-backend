from django.urls import path
from api import views

urlpatterns = [
    path('add_operator/', views.add_operator, name='add_operator'),
    path('get_operator/', views.get_operator, name='get_operator'),
    path('update_operator/<int:operator_id>/', views.update_operator, name='update-operator'),
    path('delete_operator/<int:operator_id>/', views.delete_operator, name='delete-operator'),
    path('get_companies/', views.get_companies, name='get_companies'),
    path('add_company/', views.add_company, name='add_company'),
    path('update_company/<int:pk>/', views.update_company, name='update_company'),
    path('delete_company/<int:pk>/', views.delete_company, name='delete_company'),
    path('get_material_type/', views.get_material_type, name='get_material_type'),
    path('add_material_type/', views.add_material_type, name='add_material_type'),
    path('update_material_type/<int:pk>/', views.update_material_type, name='update_material_type'),
    path('delete_material_type/<int:pk>/', views.delete_material_type, name='delete_material_type'),
]
