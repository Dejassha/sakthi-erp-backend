from django.urls import path
from api import views

urlpatterns = [
    path('add_programer_Details/', views.add_programer_Details, name='add_programer_Details'),
    path('get_programer_Details/', views.get_programer_Details, name='get_programer_Details'),
    path('update_programer_details/', views.update_programer_details, name='update_programer_details'),
    path('create_pending_material/', views.create_pending_material, name='create_pending_material'),
    path('add_qa_details/', views.add_qa_details, name='add_qa_details'),
    path('get_qa_details/', views.get_qa_details, name='get_qa_details'),
    path('update_qa_details/', views.update_qa_details, name='update_qa_details'),
    path('add_acc_details/', views.add_acc_details, name='add_acc_details'),
    path('get_acc_details/', views.get_acc_details, name='get_acc_details'),
]
