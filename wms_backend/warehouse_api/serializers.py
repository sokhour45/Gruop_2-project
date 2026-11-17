from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

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
    ReturnDisposition,
    Shipment,
    StockAdjustment,
    StockLedger,
    Supplier,
    User,
    Warehouse,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "is_active")


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.is_staff = user.role == User.Role.ADMIN
        user.save()
        return user


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ("id", "code", "name", "is_active")


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = (
            "id", "sku", "barcode", "description", "uom", "min_stock",
            "track_lot", "track_expiry", "is_active", "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        track_expiry = attrs.get("track_expiry", getattr(self.instance, "track_expiry", False))
        track_lot = attrs.get("track_lot", getattr(self.instance, "track_lot", False))
        if track_expiry and not track_lot:
            raise serializers.ValidationError({"track_expiry": "Expiry tracking requires lot tracking."})
        return attrs


class LocationSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = Location
        fields = (
            "id", "warehouse", "warehouse_code", "bin_code", "zone", "sequence",
            "kind", "is_pickable", "is_active", "capacity",
        )


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ("id", "code", "name", "email", "phone", "is_active")


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("id", "code", "name", "email", "is_active")


class ReceiptLineInputSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64)
    expected_qty = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0"))


class ReceiptCreateSerializer(serializers.ModelSerializer):
    lines = ReceiptLineInputSerializer(many=True, write_only=True)

    class Meta:
        model = Receipt
        fields = ("id", "warehouse", "source_type", "source_reference", "supplier", "receiving_location", "status", "lines")
        read_only_fields = ("id", "status")

    def validate(self, attrs):
        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "At least one receipt line is required."})
        if attrs["receiving_location"].warehouse_id != attrs["warehouse"].id:
            raise serializers.ValidationError({"receiving_location": "Receiving bin must belong to the selected warehouse."})
        if attrs["receiving_location"].kind != Location.Kind.RECEIVING:
            raise serializers.ValidationError({"receiving_location": "Choose a receiving location."})
        skus = [line["sku"] for line in lines]
        items = {item.sku: item for item in Item.objects.filter(sku__in=skus, is_active=True)}
        unknown = sorted(set(skus) - set(items))
        if unknown:
            raise serializers.ValidationError({"lines": f"Unknown or inactive SKU(s): {', '.join(unknown)}"})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        request = self.context["request"]
        receipt = Receipt.objects.create(
            **validated_data,
            created_by=request.user,
            status=Receipt.Status.OPEN,
        )
        item_by_sku = {item.sku: item for item in Item.objects.filter(sku__in=[line["sku"] for line in lines])}
        ReceiptLine.objects.bulk_create(
            [
                ReceiptLine(receipt=receipt, item=item_by_sku[line["sku"]], expected_qty=line["expected_qty"])
                for line in lines
            ]
        )
        return receipt


class ReceiptLineSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    description = serializers.CharField(source="item.description", read_only=True)
    return_dispositions = serializers.SerializerMethodField()

    def get_return_dispositions(self, instance):
        return ReturnDispositionSerializer(
            instance.return_dispositions.select_related("destination", "inspected_by"),
            many=True,
        ).data

    class Meta:
        model = ReceiptLine
        fields = (
            "id", "item", "sku", "description", "expected_qty", "received_qty",
            "putaway_qty", "lot_number", "expiry_date", "discrepancy_type",
            "discrepancy_note", "actual_bin", "return_dispositions",
        )


class ReturnDispositionSerializer(serializers.ModelSerializer):
    destination_bin = serializers.CharField(source="destination.bin_code", read_only=True, allow_null=True)
    inspector = serializers.CharField(source="inspected_by.username", read_only=True)

    class Meta:
        model = ReturnDisposition
        fields = (
            "id", "disposition", "quantity", "destination", "destination_bin",
            "reason", "inspected_by", "inspector", "created_at",
        )


class ReceiptSerializer(serializers.ModelSerializer):
    lines = ReceiptLineSerializer(many=True, read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    receiving_bin = serializers.CharField(source="receiving_location.bin_code", read_only=True)

    class Meta:
        model = Receipt
        fields = (
            "id", "warehouse", "warehouse_code", "source_type", "source_reference",
            "supplier", "receiving_location", "receiving_bin", "status", "created_at", "lines",
        )


class InventorySerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    description = serializers.CharField(source="item.description", read_only=True)
    bin_code = serializers.CharField(source="location.bin_code", read_only=True)
    available = serializers.SerializerMethodField()

    def get_available(self, instance):
        return str(instance.qty_on_hand - instance.qty_reserved)

    class Meta:
        model = Inventory
        fields = (
            "id", "item", "sku", "description", "location", "bin_code", "lot_number",
            "expiry_date", "qty_on_hand", "qty_reserved", "available", "updated_at",
        )

class OrderLineInputSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64)
    qty_ordered = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))


class OrderCreateSerializer(serializers.ModelSerializer):
    lines = OrderLineInputSerializer(many=True, write_only=True)

    class Meta:
        model = CustomerOrder
        fields = ("id", "warehouse", "customer", "external_reference", "priority", "status", "lines")
        read_only_fields = ("id", "status")

    def validate(self, attrs):
        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "At least one order line is required."})
        skus = [line["sku"] for line in lines]
        known = set(Item.objects.filter(sku__in=skus, is_active=True).values_list("sku", flat=True))
        unknown = sorted(set(skus) - known)
        if unknown:
            raise serializers.ValidationError({"lines": f"Unknown or inactive SKU(s): {', '.join(unknown)}"})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        order = CustomerOrder.objects.create(
            **validated_data,
            created_by=self.context["request"].user,
            status=CustomerOrder.Status.OPEN,
        )
        item_by_sku = {item.sku: item for item in Item.objects.filter(sku__in=[line["sku"] for line in lines])}
        OrderLine.objects.bulk_create(
            [
                OrderLine(order=order, item=item_by_sku[line["sku"]], qty_ordered=line["qty_ordered"])
                for line in lines
            ]
        )
        return order


class OrderLineSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    description = serializers.CharField(source="item.description", read_only=True)

    class Meta:
        model = OrderLine
        fields = ("id", "item", "sku", "description", "qty_ordered", "qty_picked", "qty_packed", "qty_shipped")


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, allow_null=True)

    class Meta:
        model = CustomerOrder
        fields = (
            "id", "warehouse", "customer", "customer_name", "external_reference",
            "status", "priority", "created_at", "shipped_at", "lines",
        )


class PickTaskLineSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="order_line.item.sku", read_only=True)
    bin_code = serializers.CharField(source="reservation.inventory.location.bin_code", read_only=True)

    class Meta:
        model = PickTaskLine
        fields = ("id", "order_line", "reservation", "sku", "bin_code", "qty_requested", "qty_picked")


class PickTaskSerializer(serializers.ModelSerializer):
    order_reference = serializers.CharField(source="order.external_reference", read_only=True, allow_null=True)
    lines = PickTaskLineSerializer(many=True, read_only=True)

    class Meta:
        model = PickTask
        fields = ("id", "order", "order_reference", "assigned_to", "status", "created_at", "lines")


class StockLedgerSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    bin_code = serializers.CharField(source="location.bin_code", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = StockLedger
        fields = (
            "id", "occurred_at", "item", "sku", "location", "bin_code",
            "lot_number", "expiry_date", "transaction_type", "qty_change",
            "reference_type", "reference_id", "user", "username", "notes",
        )


class AdjustmentSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    bin_code = serializers.CharField(source="location.bin_code", read_only=True)

    class Meta:
        model = StockAdjustment
        fields = (
            "id", "item", "sku", "location", "bin_code", "lot_number", "expiry_date",
            "qty_change", "reason", "notes", "status", "requested_by", "approved_by",
            "created_at", "posted_ledger_id",
        )
        read_only_fields = ("id", "status", "requested_by", "approved_by", "created_at", "posted_ledger_id")


class CycleCountLineSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    bin_code = serializers.CharField(source="location.bin_code", read_only=True)

    class Meta:
        model = CycleCountLine
        fields = (
            "id", "item", "sku", "location", "bin_code", "lot_number", "expiry_date",
            "expected_qty", "counted_qty", "counted_by", "counted_at",
        )
        read_only_fields = ("expected_qty", "counted_by", "counted_at")


class CycleCountSerializer(serializers.ModelSerializer):
    lines = CycleCountLineSerializer(many=True, read_only=True)

    class Meta:
        model = CycleCount
        fields = ("id", "warehouse", "status", "created_by", "created_at", "lines")
        read_only_fields = ("status", "created_by", "created_at")


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ("id", "order", "carrier", "tracking_number", "shipped_by", "shipped_at")
        read_only_fields = ("id", "order", "shipped_by", "shipped_at")


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = ("id", "occurred_at", "user", "username", "action", "entity_type", "entity_id", "reference_type", "reference_id", "details")
