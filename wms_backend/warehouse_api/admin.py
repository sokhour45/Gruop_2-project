from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from warehouse_api.models import (
    AuditLog,
    Customer,
    CustomerOrder,
    CycleCount,
    CycleCountLine,
    Inventory,
    Item,
    Location,
    OrderLine,
    PickTask,
    PickTaskLine,
    Receipt,
    ReceiptLine,
    Reservation,
    ReturnDisposition,
    Shipment,
    StockAdjustment,
    StockLedger,
    Supplier,
    User,
    Warehouse,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Warehouse role", {"fields": ("role",)}),)
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = ("id", "occurred_at", "item", "location", "transaction_type", "qty_change", "user")
    list_filter = ("transaction_type", "location")
    search_fields = ("item__sku", "reference_id", "user__username")
    readonly_fields = [field.name for field in StockLedger._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("item", "location", "lot_number", "qty_on_hand", "qty_reserved", "updated_at")
    readonly_fields = ("item", "location", "lot_number", "expiry_date", "qty_on_hand", "qty_reserved", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReturnDisposition)
class ReturnDispositionAdmin(admin.ModelAdmin):
    list_display = ("id", "receipt_line", "disposition", "quantity", "destination", "inspected_by", "created_at")
    readonly_fields = [field.name for field in ReturnDisposition._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (
    Warehouse,
    Supplier,
    Customer,
    Item,
    Location,
    Receipt,
    ReceiptLine,
    CustomerOrder,
    OrderLine,
    Reservation,
    PickTask,
    PickTaskLine,
    Shipment,
    StockAdjustment,
    CycleCount,
    CycleCountLine,
    AuditLog,
):
    admin.site.register(model)
