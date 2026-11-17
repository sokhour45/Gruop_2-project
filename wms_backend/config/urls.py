from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from warehouse_api.views import WarehouseTokenView, app_shell, service_worker


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/token/", WarehouseTokenView.as_view(), name="token_obtain_pair"),
    path("api/v1/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include("warehouse_api.urls")),
    path("service-worker.js", service_worker, name="service-worker"),
    path("", app_shell, name="app"),
]
