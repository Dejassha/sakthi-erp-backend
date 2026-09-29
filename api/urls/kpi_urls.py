from django.urls import path
from api import views

urlpatterns = [
    path('get_kpis/', views.get_kpis, name='get_kpis'),
    path('update_kpi/<int:pk>/', views.update_kpi, name='update_kpi'),
    path('save_kpis/', views.save_kpis, name='save_kpis'),
    path('delete_kpi_group/<str:group_id>/', views.delete_kpi_group, name='delete_kpi_group'),
    path('get_kpi_defaults/', views.get_kpi_defaults, name='get_kpi_defaults'),
]
