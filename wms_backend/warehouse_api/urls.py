from django.urls import include, path
from rest_framework.routers import DefaultRouter

from warehouse_api.views import (
    AdjustmentViewSet,
    AuditLogView,
    CustomerViewSet,
    CycleCountViewSet,
    ExpiryReportView,
    HealthView,
    InventoryListView,
    InventoryTransferView,
    ItemViewSet,
    LocationViewSet,
    LowStockView,
    MovementHistoryView,
    OrderViewSet,
    PickTaskViewSet,
    ReceiptViewSet,
    ReplenishmentView,
    SupplierViewSet,
    UserViewSet,
    WarehouseViewSet,
)


router = DefaultRouter()
router.register("items", ItemViewSet, basename="item")
router.register("locations", LocationViewSet, basename="location")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("customers", CustomerViewSet, basename="customer")
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("users", UserViewSet, basename="user")
router.register("receipts", ReceiptViewSet, basename="receipt")
router.register("orders", OrderViewSet, basename="order")
router.register("pick-tasks", PickTaskViewSet, basename="pick-task")
router.register("adjustments", AdjustmentViewSet, basename="adjustment")
router.register("cycle-counts", CycleCountViewSet, basename="cycle-count")
router.register("movement-history", MovementHistoryView, basename="movement-history")
router.register("audit-logs", AuditLogView, basename="audit-log")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("inventory/", InventoryListView.as_view(), name="inventory"),
    path("inventory/transfer/", InventoryTransferView.as_view(), name="inventory-transfer"),
    path("reports/low-stock/", LowStockView.as_view(), name="low-stock"),
    path("reports/expiry/", ExpiryReportView.as_view(), name="expiry"),
    path("reports/replenishment/", ReplenishmentView.as_view(), name="replenishment"),
    path("", include(router.urls)),
]
