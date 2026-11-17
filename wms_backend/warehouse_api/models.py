from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MANAGER = "MANAGER", "Manager"
        OPERATOR = "OPERATOR", "Operator"
        VIEWER = "VIEWER", "Viewer"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OPERATOR)


class Warehouse(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} — {self.name}"


class Supplier(models.Model):
    code = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Customer(models.Model):
    code = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Item(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=128, unique=True, null=True, blank=True)
    description = models.CharField(max_length=240)
    uom = models.CharField(max_length=24, default="each")
    min_stock = models.DecimalField(max_digits=18, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    track_lot = models.BooleanField(default=False)
    track_expiry = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sku} — {self.description}"


class Location(models.Model):
    class Kind(models.TextChoices):
        STORAGE = "STORAGE", "Storage"
        RECEIVING = "RECEIVING", "Receiving"
        PACKING = "PACKING", "Packing"
        QUARANTINE = "QUARANTINE", "Quarantine"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="locations")
    bin_code = models.CharField(max_length=64)
    zone = models.CharField(max_length=64, blank=True)
    sequence = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.STORAGE)
    is_pickable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    capacity = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("warehouse", "bin_code"), name="unique_bin_per_warehouse"),
            models.CheckConstraint(condition=Q(capacity__isnull=True) | Q(capacity__gte=0), name="location_capacity_nonnegative"),
        ]
        ordering = ("warehouse_id", "sequence", "bin_code")

    def __str__(self):
        return self.bin_code


class Receipt(models.Model):
    class SourceType(models.TextChoices):
        PO = "PO", "Purchase order"
        RETURN = "RETURN", "Return authorization"
        TRANSFER = "TRANSFER", "Transfer order"
        OTHER = "OTHER", "Other inbound"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        RECEIVING = "RECEIVING", "Receiving"
        INSPECTING = "INSPECTING", "Inspecting return"
        PUTAWAY = "PUTAWAY", "Putaway"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    source_type = models.CharField(max_length=12, choices=SourceType.choices, default=SourceType.PO)
    source_reference = models.CharField(max_length=100)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT)
    receiving_location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="receipts")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_receipts")
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("warehouse", "source_type", "source_reference"),
                name="unique_receipt_source_per_warehouse",
            )
        ]
        ordering = ("-created_at",)


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    expected_qty = models.DecimalField(max_digits=18, decimal_places=3, validators=[MinValueValidator(0)])
    received_qty = models.DecimalField(max_digits=18, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    putaway_qty = models.DecimalField(max_digits=18, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    discrepancy_type = models.CharField(max_length=32, blank=True)
    discrepancy_note = models.TextField(blank=True)
    actual_bin = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)


class ReturnDisposition(models.Model):
    class Type(models.TextChoices):
        RESTOCK = "RESTOCK", "Restock"
        QUARANTINE = "QUARANTINE", "Quarantine"
        SCRAP = "SCRAP", "Scrap"

    receipt_line = models.ForeignKey(ReceiptLine, on_delete=models.PROTECT, related_name="return_dispositions")
    disposition = models.CharField(max_length=12, choices=Type.choices)
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    destination = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    reason = models.TextField()
    inspected_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="return_disposition_quantity_positive"),
        ]


class Inventory(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="inventory")
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    qty_on_hand = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    qty_reserved = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("item", "location", "lot_number"),
                condition=Q(expiry_date__isnull=True),
                name="unique_inventory_without_expiry",
            ),
            models.UniqueConstraint(
                fields=("item", "location", "lot_number", "expiry_date"),
                condition=Q(expiry_date__isnull=False),
                name="unique_inventory_with_expiry",
            ),
            models.CheckConstraint(condition=Q(qty_on_hand__gte=0), name="inventory_on_hand_nonnegative"),
            models.CheckConstraint(condition=Q(qty_reserved__gte=0), name="inventory_reserved_nonnegative"),
            models.CheckConstraint(condition=Q(qty_reserved__lte=F("qty_on_hand")), name="inventory_reserved_lte_on_hand"),
            models.CheckConstraint(condition=Q(expiry_date__isnull=True) | ~Q(lot_number=""), name="expiry_requires_lot"),
        ]
        ordering = ("item__sku", "location__sequence", "location__bin_code")


class CustomerOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        ALLOCATED = "ALLOCATED", "Allocated"
        PICKING = "PICKING", "Picking"
        PICKED = "PICKED", "Picked"
        PACKED = "PACKED", "Packed"
        SHIPPED = "SHIPPED", "Shipped"
        ON_HOLD = "ON_HOLD", "On hold"
        CANCELLED = "CANCELLED", "Cancelled"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT)
    external_reference = models.CharField(max_length=120, unique=True, null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    priority = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    shipped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("priority", "created_at")
        constraints = [
            models.CheckConstraint(condition=Q(priority__gte=1) & Q(priority__lte=5), name="order_priority_1_5")
        ]


class OrderLine(models.Model):
    order = models.ForeignKey(CustomerOrder, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty_ordered = models.DecimalField(max_digits=18, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    qty_picked = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    qty_packed = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    qty_shipped = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(qty_picked__gte=0) & Q(qty_picked__lte=F("qty_ordered")), name="order_picked_in_range"),
            models.CheckConstraint(condition=Q(qty_packed__gte=0) & Q(qty_packed__lte=F("qty_picked")), name="order_packed_in_range"),
            models.CheckConstraint(condition=Q(qty_shipped__gte=0) & Q(qty_shipped__lte=F("qty_packed")), name="order_shipped_in_range"),
        ]


class Reservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        RELEASED = "RELEASED", "Released"
        CONSUMED = "CONSUMED", "Consumed"

    order_line = models.ForeignKey(OrderLine, on_delete=models.PROTECT, related_name="reservations")
    inventory = models.ForeignKey(Inventory, on_delete=models.PROTECT, related_name="reservations")
    qty_reserved = models.DecimalField(max_digits=18, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)


class PickTask(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RELEASED = "RELEASED", "Released"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        BLOCKED = "BLOCKED", "Blocked"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    order = models.ForeignKey(CustomerOrder, on_delete=models.PROTECT, related_name="pick_tasks")
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class PickTaskLine(models.Model):
    task = models.ForeignKey(PickTask, on_delete=models.PROTECT, related_name="lines")
    order_line = models.ForeignKey(OrderLine, on_delete=models.PROTECT)
    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT)
    qty_requested = models.DecimalField(max_digits=18, decimal_places=3)
    qty_picked = models.DecimalField(max_digits=18, decimal_places=3, default=0)


class Shipment(models.Model):
    order = models.OneToOneField(CustomerOrder, on_delete=models.PROTECT, related_name="shipment")
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=160, blank=True)
    shipped_by = models.ForeignKey(User, on_delete=models.PROTECT)
    shipped_at = models.DateTimeField(auto_now_add=True)


class StockAdjustment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        POSTED = "POSTED", "Posted"

    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    qty_change = models.DecimalField(max_digits=18, decimal_places=3)
    reason = models.CharField(max_length=64)
    notes = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="adjustments_requested")
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="adjustments_approved")
    created_at = models.DateTimeField(auto_now_add=True)
    posted_ledger_id = models.BigIntegerField(null=True, blank=True)


class CycleCount(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        COUNTING = "COUNTING", "Counting"
        REVIEW = "REVIEW", "Review"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CycleCountLine(models.Model):
    count = models.ForeignKey(CycleCount, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    expected_qty = models.DecimalField(max_digits=18, decimal_places=3)
    counted_qty = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    counted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    counted_at = models.DateTimeField(null=True, blank=True)


class StockLedger(models.Model):
    class Type(models.TextChoices):
        OPENING_BALANCE = "OPENING_BALANCE", "Opening balance"
        RECEIPT = "RECEIPT", "Receipt"
        PUTAWAY = "PUTAWAY", "Putaway"
        PICK = "PICK", "Pick"
        PACK = "PACK", "Pack"
        SHIP = "SHIP", "Ship"
        ADJUST = "ADJUST", "Adjustment"
        TRANSFER = "TRANSFER", "Transfer"
        CYCLE_COUNT = "CYCLE_COUNT", "Cycle count"

    occurred_at = models.DateTimeField(auto_now_add=True)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="ledger_entries")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="ledger_entries")
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=Type.choices)
    qty_change = models.DecimalField(max_digits=18, decimal_places=3)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="ledger_entries")
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(condition=~Q(qty_change=0), name="ledger_quantity_nonzero"),
        ]
        indexes = [
            models.Index(fields=("item", "-occurred_at"), name="ledger_item_time_idx"),
            models.Index(fields=("location", "-occurred_at"), name="ledger_location_time_idx"),
            models.Index(fields=("reference_type", "reference_id"), name="ledger_reference_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Stock ledger entries are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Stock ledger entries are immutable.")


class AuditLog(models.Model):
    occurred_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=100)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=80, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")


class IdempotencyRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "key"), name="unique_user_idempotency_key")
        ]
