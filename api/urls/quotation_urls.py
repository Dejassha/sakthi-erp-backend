from django.urls import path
from api import views

urlpatterns = [
    path('add_quotation/', views.add_quotation, name='add_quotation'),
    path('edit_quotation/<int:quotation_id>/', views.edit_quotation, name='edit_quotation'),
    path('delete_quotation/<int:quotation_id>/', views.delete_quotation, name='delete_quotation'),
    path('update_quotation/<int:pk>/', views.update_quotation, name='update_quotation'),
    path('duplicate_quotation/', views.duplicate_quotation, name='duplicate_quotation'),
    path('get_quotation_list/', views.get_quotation_list, name='get_quotation_list'),
    path('get_quotation_details/', views.get_quotation_details, name='get_quotation_details'),
    path('get_next_doc_number/', views.get_next_doc_number, name='get_next_doc_number'),
    path('get_quotation_note/', views.get_quotation_note, name='get_quotation_note'),
    path('add_quotation_note/', views.add_quotation_note, name='add_quotation_note'),
    path('update_quotation_note/<int:pk>/', views.update_quotation_note, name='update_quotation_note'),
    path('delete_quotation_note/<int:pk>/', views.delete_quotation_note, name='delete_quotation_note'),
]
