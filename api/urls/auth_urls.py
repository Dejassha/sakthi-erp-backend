from django.urls import path
from api import views

urlpatterns = [
    path("login/", views.login, name="login"),
    path("refresh_token/", views.refresh_token, name="refresh_token"),
    path("me/", views.me, name="me"),
    path("logout/", views.logout_view, name="logout"),
    path("create_user/", views.create_user, name="create_user"),
    path("get_all_users/", views.get_all_users, name="get_all_users"),
    path("update_user/<int:id>/", views.update_user, name="update_user"),
    path("delete_user/<int:id>/", views.delete_user, name="delete_user"),
    path("get_role_list/", views.get_role_list, name="get_role_list"),
]
