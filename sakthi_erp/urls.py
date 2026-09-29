import os
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

# Configure Enterprise Admin Dashboard Branding
admin.site.site_header = "Sakthi Laser ERP Administration"
admin.site.site_title = "Sakthi Laser ERP Portal"
admin.site.index_title = "System Management & Administration"

# Dynamic Admin URL path loaded strictly from environment configuration
admin_path = (os.getenv("ADMIN_URL") or "admin").strip("/") + "/"

urlpatterns = [
    path(admin_path, admin.site.urls),
    path("api/", include("api.urls")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
