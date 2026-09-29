from django.urls import path
from django.conf import settings
from api.views.utils import api_root
from .auth_urls import urlpatterns as auth_urls
from .company_operator_urls import urlpatterns as company_operator_urls
from .machine_urls import urlpatterns as machine_urls
from .inventory_urls import urlpatterns as inventory_urls
from .product_urls import urlpatterns as product_urls
from .programmer_qa_acc_urls import urlpatterns as programmer_qa_acc_urls
from .quotation_urls import urlpatterns as quotation_urls
from .kpi_urls import urlpatterns as kpi_urls
from .reports_urls import urlpatterns as reports_urls

# Register root API path ONLY when DEBUG is False
root_patterns = [] if settings.DEBUG else [path("", api_root, name="api_root")]

urlpatterns = root_patterns + (
    auth_urls
    + company_operator_urls
    + machine_urls
    + inventory_urls
    + product_urls
    + programmer_qa_acc_urls
    + quotation_urls
    + kpi_urls
    + reports_urls
)

