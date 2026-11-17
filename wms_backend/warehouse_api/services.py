import hashlib
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from warehouse_api.models import (
    AuditLog,
    CustomerOrder,
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
    IdempotencyRecord,
)


class Conflict(APIException):
    status_code = 409
    default_code = "conflict"
    default_detail = "The requested operation conflicts with current warehouse state."


def audit(user, action, entity_type, entity_id, *, reference_type="", reference_id="", details=None):
    return AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id is not None else "",
        details=details or {},
    )


def _inventory_for_update(item, location, lot_number="", expiry_date=None, create=False):
    query = Inventory.objects.select_for_update().filter(
        item=item,
        location=location,
        lot_number=lot_number or "",
        expiry_date=expiry_date,
    )
    inventory = query.first()
    if inventory or not create:
        return inventory
    try:
        inventory, _ = Inventory.objects.get_or_create(
            item=item,
            location=location,
            lot_number=lot_number or "",
            expiry_date=expiry_date,
            defaults={"qty_on_hand": Decimal("0"), "qty_reserved": Decimal("0")},
        )
    except IntegrityError:
        pass
    return Inventory.objects.select_for_update().get(
        item=item,
        location=location,
        lot_number=lot_number or "",
        expiry_date=expiry_date,
    )


def _validate_tracking(item, lot_number, expiry_date):
    if item.track_lot and not lot_number:
        raise ValidationError({"lot_number": "A lot number is required for this item."})
    if item.track_expiry and not expiry_date:
        raise ValidationError({"expiry_date": "An expiry date is required for this item."})
    if expiry_date and not lot_number:
        raise ValidationError({"lot_number": "A lot number is required when expiry is provided."})


@transaction.atomic
def post_movement(
    *,
    item,
    location,
    qty_change,
    transaction_type,
    user,
    reference_type="",
    reference_id="",
    lot_number="",
    expiry_date=None,
    notes="",
    reserved_change=Decimal("0"),
    idempotency_key="",
):
    qty_change = Decimal(qty_change)
    reserved_change = Decimal(reserved_change)
    if qty_change == 0:
        raise ValidationError({"qty_change": "Stock movement quantity cannot be zero."})
    if location.warehouse_id is None or not location.is_active:
        raise ValidationError({"location": "Choose an active warehouse location."})
    item = Item.objects.select_for_update().get(pk=item.pk)
    _validate_tracking(item, lot_number, expiry_date)
    inventory = _inventory_for_update(item, location, lot_number, expiry_date, create=qty_change > 0)
    if inventory is None:
        raise Conflict("No inventory balance exists for this stock dimension.")
    new_on_hand = inventory.qty_on_hand + qty_change
    new_reserved = inventory.qty_reserved + reserved_change
    if new_on_hand < 0:
        raise Conflict(f"Insufficient stock in {location.bin_code}.")
    if new_reserved < 0 or new_reserved > new_on_hand:
        raise Conflict("The movement would make reserved quantity invalid.")
    inventory.qty_on_hand = new_on_hand
    inventory.qty_reserved = new_reserved
    inventory.save(update_fields=("qty_on_hand", "qty_reserved", "updated_at"))
    ledger = StockLedger.objects.create(
        item=item,
        location=location,
        lot_number=lot_number or "",
        expiry_date=expiry_date,
        transaction_type=transaction_type,
        qty_change=qty_change,
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id else "",
        user=user,
        notes=notes,
        idempotency_key=idempotency_key,
    )
    return ledger, inventory


@transaction.atomic
def transfer_stock(
    *,
    item,
    source,
    destination,
    quantity,
    transaction_type,
    user,
    reference_type,
    reference_id,
    lot_number="",
    expiry_date=None,
    notes="",
    reserved=False,
    idempotency_key="",
):
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})
    if source.pk == destination.pk:
        raise ValidationError({"destination": "Source and destination bins must differ."})
    if not source.is_active or not destination.is_active:
        raise ValidationError({"location": "Source and destination bins must be active."})
    _validate_tracking(item, lot_number, expiry_date)
    item = Item.objects.select_for_update().get(pk=item.pk)
    source_inventory = _inventory_for_update(item, source, lot_number, expiry_date)
    if source_inventory is None:
        raise Conflict(f"No stock is available in {source.bin_code}.")
    destination_inventory = _inventory_for_update(
        item, destination, lot_number, expiry_date, create=True
    )
    if reserved:
        if source_inventory.qty_reserved < quantity:
            raise Conflict("The picked quantity exceeds the reserved quantity.")
        reserved_delta = quantity
    else:
        if source_inventory.qty_on_hand - source_inventory.qty_reserved < quantity:
            raise Conflict(f"Insufficient available stock in {source.bin_code}.")
        reserved_delta = Decimal("0")
    if destination.capacity is not None:
        destination_total = Inventory.objects.filter(location=destination).aggregate(
            total=Coalesce(Sum("qty_on_hand"), Decimal("0"))
        )["total"]
        if destination_total + quantity > destination.capacity:
            raise Conflict(f"Destination bin {destination.bin_code} exceeds configured capacity.")

    source_inventory.qty_on_hand -= quantity
    source_inventory.qty_reserved -= reserved_delta
    destination_inventory.qty_on_hand += quantity
    destination_inventory.qty_reserved += reserved_delta
    source_inventory.save(update_fields=("qty_on_hand", "qty_reserved", "updated_at"))
    destination_inventory.save(update_fields=("qty_on_hand", "qty_reserved", "updated_at"))
    common = {
        "item": item,
        "transaction_type": transaction_type,
        "reference_type": reference_type,
        "reference_id": str(reference_id),
        "user": user,
        "lot_number": lot_number or "",
        "expiry_date": expiry_date,
        "notes": notes,
        "idempotency_key": idempotency_key,
    }
    outbound = StockLedger.objects.create(location=source, qty_change=-quantity, **common)
    inbound = StockLedger.objects.create(location=destination, qty_change=quantity, **common)
    audit(
        user,
        "STOCK_TRANSFER",
        "InventoryTransfer",
        reference_id,
        reference_type=reference_type,
        reference_id=reference_id,
        details={
            "item_id": item.pk,
            "source": source.bin_code,
            "destination": destination.bin_code,
            "quantity": str(quantity),
            "ledger_ids": [outbound.pk, inbound.pk],
        },
    )
    return outbound, inbound


def run_idempotent(user, key, payload, callback):
    if not key:
        raise ValidationError({"Idempotency-Key": "This operation requires an Idempotency-Key header."})
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    with transaction.atomic():
        try:
            record, created = IdempotencyRecord.objects.get_or_create(
                user=user,
                key=key,
                defaults={"request_hash": payload_hash},
            )
        except IntegrityError:
            record = IdempotencyRecord.objects.select_for_update().get(user=user, key=key)
            created = False
        if not created:
            record = IdempotencyRecord.objects.select_for_update().get(pk=record.pk)
            if record.request_hash != payload_hash:
                raise Conflict("Idempotency key was already used with a different request.")
            if record.response_body is None:
                raise Conflict("A request with this idempotency key is still being processed.")
            return record.response_status, record.response_body
        status_code, response_body = callback()
        record.response_status = status_code
        record.response_body = response_body
        record.save(update_fields=("response_status", "response_body"))
        return status_code, response_body


@transaction.atomic
def receive_line(*, receipt, line, barcode, quantity, user, lot_number="", expiry_date=None,
                 discrepancy_type="", discrepancy_note="", idempotency_key=""):
    receipt = Receipt.objects.select_for_update().get(pk=receipt.pk)
    line = ReceiptLine.objects.select_for_update().select_related("item").get(
        pk=line.pk, receipt=receipt
    )
    if receipt.status not in {Receipt.Status.OPEN, Receipt.Status.RECEIVING}:
        raise Conflict("This receipt is not open for receiving.")
    item = line.item
    if not item.is_active or not barcode or barcode not in {item.sku, item.barcode}:
        raise ValidationError({"barcode": "Scanned barcode does not match the receipt line SKU."})
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValidationError({"quantity": "Received quantity must be greater than zero."})
    _validate_tracking(item, lot_number, expiry_date)
    if line.lot_number and (line.lot_number != lot_number or line.expiry_date != expiry_date):
        raise ValidationError({"lot_number": "Receive different lots on separate receipt lines."})
    if line.received_qty + quantity > line.expected_qty and user.role not in {
        user.Role.ADMIN,
        user.Role.MANAGER,
    }:
        raise Conflict("Over-receipt requires manager approval.")
    if line.expected_qty != line.received_qty + quantity and not discrepancy_type:
        raise ValidationError({"discrepancy_type": "Record a discrepancy when received quantity differs from expected."})
    ledger, _ = post_movement(
        item=item,
        location=receipt.receiving_location,
        qty_change=quantity,
        transaction_type=StockLedger.Type.RECEIPT,
        user=user,
        reference_type="RECEIPT",
        reference_id=receipt.pk,
        lot_number=lot_number,
        expiry_date=expiry_date,
        notes=discrepancy_note,
        idempotency_key=idempotency_key,
    )
    line.received_qty += quantity
    line.lot_number = lot_number or line.lot_number
    line.expiry_date = expiry_date or line.expiry_date
    if discrepancy_type:
        line.discrepancy_type = discrepancy_type
        line.discrepancy_note = discrepancy_note
    line.save()
    receipt.status = (
        Receipt.Status.INSPECTING
        if receipt.source_type == Receipt.SourceType.RETURN
        else Receipt.Status.RECEIVING
    )
    receipt.save(update_fields=("status",))
    audit(
        user,
        "RECEIPT_LINE_RECEIVED",
        "ReceiptLine",
        line.pk,
        reference_type="RECEIPT",
        reference_id=receipt.pk,
        details={"sku": item.sku, "quantity": str(quantity), "ledger_id": ledger.pk},
    )
    return ledger, line


@transaction.atomic
def suggest_putaway(receipt, line, quantity):
    if receipt.source_type == Receipt.SourceType.RETURN:
        raise Conflict("Returned stock must be inspected and dispositioned before putaway.")
    line = ReceiptLine.objects.select_related("item").get(pk=line.pk, receipt=receipt)
    remaining = line.received_qty - line.putaway_qty
    quantity = Decimal(quantity)
    if quantity <= 0 or quantity > remaining:
        raise ValidationError({"quantity": f"Quantity must be between 0 and {remaining}."})
    candidates = Location.objects.filter(
        warehouse=receipt.warehouse,
        kind=Location.Kind.STORAGE,
        is_active=True,
    ).order_by("zone", "sequence", "bin_code")
    for location in candidates:
        current = Inventory.objects.filter(location=location).aggregate(
            total=Coalesce(Sum("qty_on_hand"), Decimal("0"))
        )["total"]
        if location.capacity is None or current + quantity <= location.capacity:
            return location
    return None


@transaction.atomic
def confirm_putaway(*, receipt, line, barcode, bin_code, quantity, user, idempotency_key=""):
    receipt = Receipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.source_type == Receipt.SourceType.RETURN:
        raise Conflict("Returned stock must be inspected and dispositioned before putaway.")
    line = ReceiptLine.objects.select_for_update().select_related("item").get(
        pk=line.pk, receipt=receipt
    )
    if barcode not in {line.item.sku, line.item.barcode}:
        raise ValidationError({"barcode": "Scanned item does not match this receipt line."})
    destination = Location.objects.select_for_update().filter(
        warehouse=receipt.warehouse, bin_code=bin_code, is_active=True
    ).first()
    if destination is None or destination.kind != Location.Kind.STORAGE:
        raise ValidationError({"bin_code": "Scan a valid active storage bin."})
    quantity = Decimal(quantity)
    remaining = line.received_qty - line.putaway_qty
    if quantity <= 0 or quantity > remaining:
        raise ValidationError({"quantity": f"Quantity must be between 0 and {remaining}."})
    transfer_stock(
        item=line.item,
        source=receipt.receiving_location,
        destination=destination,
        quantity=quantity,
        transaction_type=StockLedger.Type.PUTAWAY,
        user=user,
        reference_type="RECEIPT",
        reference_id=receipt.pk,
        lot_number=line.lot_number,
        expiry_date=line.expiry_date,
        notes=f"Receipt line {line.pk}",
        idempotency_key=idempotency_key,
    )
    line.putaway_qty += quantity
    line.actual_bin = destination
    line.save(update_fields=("putaway_qty", "actual_bin"))
    if receipt.lines.filter(putaway_qty__lt=F("received_qty")).exists():
        receipt.status = Receipt.Status.PUTAWAY
    elif receipt.lines.filter(received_qty__lt=F("expected_qty")).exists():
        receipt.status = Receipt.Status.RECEIVING
    else:
        receipt.status = Receipt.Status.CLOSED
        receipt.closed_at = timezone.now()
    receipt.save(update_fields=("status", "closed_at"))
    audit(
        user,
        "PUTAWAY_CONFIRMED",
        "ReceiptLine",
        line.pk,
        reference_type="RECEIPT",
        reference_id=receipt.pk,
        details={"sku": line.item.sku, "bin": destination.bin_code, "quantity": str(quantity)},
    )
    return line


@transaction.atomic
def dispose_return_line(
    *,
    receipt,
    line,
    barcode,
    quantity,
    disposition,
    destination_bin,
    lot_number,
    expiry_date,
    reason,
    user,
    idempotency_key="",
):
    receipt = Receipt.objects.select_for_update().get(pk=receipt.pk)
    line = ReceiptLine.objects.select_for_update().select_related("item").get(
        pk=line.pk,
        receipt=receipt,
    )
    if receipt.source_type != Receipt.SourceType.RETURN:
        raise ValidationError({"receipt": "Inspection disposition is only valid for return receipts."})
    if receipt.status not in {Receipt.Status.INSPECTING, Receipt.Status.RECEIVING}:
        raise Conflict("This return is not open for inspection.")
    if not barcode or barcode not in {line.item.sku, line.item.barcode}:
        raise ValidationError({"barcode": "Scanned item does not match the return line."})
    if (line.item.track_lot or line.lot_number) and lot_number != line.lot_number:
        raise ValidationError({"lot_number": "Scanned lot does not match the returned stock."})
    if line.item.track_expiry and expiry_date != line.expiry_date:
        raise ValidationError({"expiry_date": "Scanned expiry date does not match the returned stock."})
    _validate_tracking(line.item, line.lot_number, line.expiry_date)
    quantity = Decimal(quantity)
    already_dispositioned = line.return_dispositions.aggregate(
        total=Coalesce(Sum("quantity"), Decimal("0"))
    )["total"]
    remaining = line.received_qty - already_dispositioned
    if quantity <= 0 or quantity > remaining:
        raise ValidationError({"quantity": f"Quantity must be between 0 and {remaining}."})
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": "A reason is required for every return disposition."})
    if disposition == ReturnDisposition.Type.SCRAP and user.role not in {
        user.Role.ADMIN,
        user.Role.MANAGER,
    }:
        raise PermissionDenied("Only a manager can approve scrap disposition.")

    destination = None
    if disposition in {ReturnDisposition.Type.RESTOCK, ReturnDisposition.Type.QUARANTINE}:
        if not destination_bin:
            raise ValidationError({"destination_bin": "A destination bin is required."})
        destination = Location.objects.select_for_update().filter(
            warehouse=receipt.warehouse,
            bin_code__iexact=destination_bin,
            is_active=True,
        ).first()
        if destination is None:
            raise ValidationError({"destination_bin": "Choose an active bin in this warehouse."})
        if disposition == ReturnDisposition.Type.RESTOCK and (
            destination.kind != Location.Kind.STORAGE or not destination.is_pickable
        ):
            raise ValidationError({"destination_bin": "Restock requires an active pickable storage bin."})
        if (
            disposition == ReturnDisposition.Type.RESTOCK
            and line.expiry_date
            and line.expiry_date < timezone.localdate()
        ):
            raise Conflict("Expired returns must be quarantined or scrapped, not restocked.")
        if disposition == ReturnDisposition.Type.QUARANTINE and (
            destination.kind != Location.Kind.QUARANTINE or destination.is_pickable
        ):
            raise ValidationError({"destination_bin": "Quarantine requires a non-pickable quarantine bin."})
    elif disposition != ReturnDisposition.Type.SCRAP:
        raise ValidationError({"disposition": "Choose restock, quarantine, or scrap."})

    record = ReturnDisposition.objects.create(
        receipt_line=line,
        disposition=disposition,
        quantity=quantity,
        destination=destination,
        reason=reason,
        inspected_by=user,
    )
    if disposition in {ReturnDisposition.Type.RESTOCK, ReturnDisposition.Type.QUARANTINE}:
        transfer_stock(
            item=line.item,
            source=receipt.receiving_location,
            destination=destination,
            quantity=quantity,
            transaction_type=StockLedger.Type.TRANSFER,
            user=user,
            reference_type="RETURN_DISPOSITION",
            reference_id=record.pk,
            lot_number=line.lot_number,
            expiry_date=line.expiry_date,
            notes=f"{disposition}: {reason}",
            idempotency_key=idempotency_key,
        )
    else:
        post_movement(
            item=line.item,
            location=receipt.receiving_location,
            qty_change=-quantity,
            transaction_type=StockLedger.Type.ADJUST,
            user=user,
            reference_type="RETURN_DISPOSITION",
            reference_id=record.pk,
            lot_number=line.lot_number,
            expiry_date=line.expiry_date,
            notes=f"Approved scrap: {reason}",
            idempotency_key=idempotency_key,
        )
    audit(
        user,
        "RETURN_DISPOSITION_POSTED",
        "ReturnDisposition",
        record.pk,
        reference_type="RECEIPT",
        reference_id=receipt.pk,
        details={
            "sku": line.item.sku,
            "disposition": disposition,
            "quantity": str(quantity),
            "destination": destination.bin_code if destination else "",
            "reason": reason,
        },
    )
    return record


@transaction.atomic
def allocate_order(order, user):
    order = CustomerOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != CustomerOrder.Status.OPEN:
        raise Conflict("Only open orders can be allocated.")
    if order.pick_tasks.exists():
        raise Conflict("A pick task already exists for this order.")
    task = PickTask.objects.create(order=order, assigned_to=user, status=PickTask.Status.RELEASED)
    for line in order.lines.select_related("item").order_by("id"):
        remaining = line.qty_ordered - line.qty_picked
        candidates = Inventory.objects.select_for_update().filter(
            item=line.item,
            location__warehouse=order.warehouse,
            location__is_active=True,
            location__is_pickable=True,
            location__kind=Location.Kind.STORAGE,
        ).filter(qty_on_hand__gt=F("qty_reserved")).select_related("location")
        if line.item.track_expiry:
            candidates = candidates.filter(expiry_date__gte=timezone.localdate())
            from django.db.models import F as ModelF

            candidates = candidates.order_by(ModelF("expiry_date").asc(nulls_last=True), "location__sequence")
        else:
            candidates = candidates.filter(
                Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate())
            )
            candidates = candidates.order_by("location__sequence", "location__bin_code")
        for inventory in candidates:
            available = inventory.qty_on_hand - inventory.qty_reserved
            amount = min(available, remaining)
            if amount <= 0:
                continue
            inventory.qty_reserved += amount
            inventory.save(update_fields=("qty_reserved", "updated_at"))
            reservation = Reservation.objects.create(
                order_line=line,
                inventory=inventory,
                qty_reserved=amount,
            )
            PickTaskLine.objects.create(
                task=task,
                order_line=line,
                reservation=reservation,
                qty_requested=amount,
            )
            remaining -= amount
            if remaining == 0:
                break
        if remaining > 0:
            raise Conflict(f"Insufficient stock to fully allocate SKU {line.item.sku}.")
    order.status = CustomerOrder.Status.ALLOCATED
    order.save(update_fields=("status",))
    audit(user, "ORDER_ALLOCATED", "CustomerOrder", order.pk, reference_type="ORDER", reference_id=order.pk)
    return task


@transaction.atomic
def confirm_pick(*, task_line, bin_code, barcode, quantity, user, idempotency_key=""):
    line = PickTaskLine.objects.select_for_update().select_related(
        "task__order", "order_line__item", "reservation__inventory__location"
    ).get(pk=task_line.pk)
    task = PickTask.objects.select_for_update().get(pk=line.task_id)
    reservation = Reservation.objects.select_for_update().get(pk=line.reservation_id)
    source_inventory = Inventory.objects.select_for_update().select_related(
        "item", "location"
    ).get(pk=reservation.inventory_id)
    if task.status not in {PickTask.Status.RELEASED, PickTask.Status.IN_PROGRESS}:
        raise Conflict("This pick task is not active.")
    if source_inventory.expiry_date and source_inventory.expiry_date < timezone.localdate():
        raise Conflict("Expired stock cannot be picked; have a manager review the reservation.")
    if source_inventory.item.track_expiry and not source_inventory.expiry_date:
        raise Conflict("Tracked stock without an expiry date cannot be picked.")
    if source_inventory.location.bin_code != bin_code:
        raise ValidationError({"bin_code": f"Scan expected bin {source_inventory.location.bin_code}."})
    expected_item = line.order_line.item
    if barcode not in {expected_item.sku, expected_item.barcode}:
        raise ValidationError({"barcode": f"Scan expected item {expected_item.sku}."})
    quantity = Decimal(quantity)
    remaining_line = line.qty_requested - line.qty_picked
    if quantity <= 0 or quantity > remaining_line or quantity > reservation.qty_reserved:
        raise ValidationError({"quantity": "Quantity exceeds the remaining pick allocation."})
    pack_location = Location.objects.filter(
        warehouse=task.order.warehouse,
        kind=Location.Kind.PACKING,
        is_active=True,
    ).order_by("sequence", "bin_code").first()
    if pack_location is None:
        raise Conflict("Configure an active packing location before picking.")
    transfer_stock(
        item=expected_item,
        source=source_inventory.location,
        destination=pack_location,
        quantity=quantity,
        transaction_type=StockLedger.Type.PICK,
        user=user,
        reference_type="PICK_TASK",
        reference_id=task.pk,
        lot_number=source_inventory.lot_number,
        expiry_date=source_inventory.expiry_date,
        notes=f"Pick task line {line.pk}",
        reserved=True,
        idempotency_key=idempotency_key,
    )
    reservation.qty_reserved -= quantity
    if reservation.qty_reserved == 0:
        reservation.status = Reservation.Status.RELEASED
    reservation.save(update_fields=("qty_reserved", "status"))
    staged_inventory = Inventory.objects.get(
        item=expected_item,
        location=pack_location,
        lot_number=source_inventory.lot_number,
        expiry_date=source_inventory.expiry_date,
    )
    Reservation.objects.create(
        order_line=line.order_line,
        inventory=staged_inventory,
        qty_reserved=quantity,
    )
    line.qty_picked += quantity
    line.save(update_fields=("qty_picked",))
    order_line = OrderLine.objects.select_for_update().get(pk=line.order_line_id)
    order_line.qty_picked += quantity
    order_line.save(update_fields=("qty_picked",))
    order = task.order
    if not task.lines.filter(qty_picked__lt=F("qty_requested")).exists():
        task.status = PickTask.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=("status", "completed_at"))
        order.status = CustomerOrder.Status.PICKED
    else:
        task.status = PickTask.Status.IN_PROGRESS
        task.save(update_fields=("status",))
        order.status = CustomerOrder.Status.PICKING
    order.save(update_fields=("status",))
    audit(
        user, "PICK_CONFIRMED", "PickTaskLine", line.pk,
        reference_type="ORDER", reference_id=order.pk,
        details={"sku": expected_item.sku, "quantity": str(quantity), "source_bin": bin_code},
    )
    return line


@transaction.atomic
def verify_pack(*, order, barcode, quantity, user):
    order = CustomerOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != CustomerOrder.Status.PICKED:
        raise Conflict("Order is not ready for pack verification.")
    item = Item.objects.filter(is_active=True).filter(
        Q(barcode=barcode) | Q(sku=barcode)
    ).first()
    if item is None:
        raise ValidationError({"barcode": "Unknown item barcode or SKU."})
    line = OrderLine.objects.select_for_update().filter(order=order, item=item).first()
    if line is None:
        raise ValidationError({"barcode": "Scanned item is not on this order."})
    quantity = Decimal(quantity)
    if quantity <= 0 or quantity > line.qty_picked - line.qty_packed:
        raise ValidationError({"quantity": "Packed quantity exceeds the picked quantity."})
    line.qty_packed += quantity
    line.save(update_fields=("qty_packed",))
    if not order.lines.filter(qty_packed__lt=F("qty_ordered")).exists():
        order.status = CustomerOrder.Status.PACKED
        order.save(update_fields=("status",))
    audit(user, "PACK_VERIFIED", "OrderLine", line.pk, reference_type="ORDER", reference_id=order.pk,
          details={"sku": item.sku, "quantity": str(quantity)})
    return line


@transaction.atomic
def ship_order(*, order, carrier, tracking_number, user, idempotency_key=""):
    order = CustomerOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != CustomerOrder.Status.PACKED:
        raise Conflict("Order must be pack-verified before shipment.")
    if Shipment.objects.filter(order=order).exists():
        raise Conflict("This order has already shipped.")
    if order.lines.filter(qty_packed__lt=F("qty_ordered")).exists():
        raise Conflict("All order lines must be pack verified before shipment.")
    reservations = Reservation.objects.select_for_update().filter(
        order_line__order=order,
        status=Reservation.Status.ACTIVE,
        inventory__location__kind=Location.Kind.PACKING,
    ).select_related("inventory", "order_line__item")
    shipment = Shipment.objects.create(
        order=order,
        carrier=carrier,
        tracking_number=tracking_number,
        shipped_by=user,
    )
    for reservation in reservations:
        inventory = Inventory.objects.select_for_update().get(pk=reservation.inventory_id)
        quantity = reservation.qty_reserved
        if inventory.qty_on_hand < quantity or inventory.qty_reserved < quantity:
            raise Conflict("Packing stock is no longer available for shipment.")
        inventory.qty_on_hand -= quantity
        inventory.qty_reserved -= quantity
        inventory.save(update_fields=("qty_on_hand", "qty_reserved", "updated_at"))
        StockLedger.objects.create(
            item=reservation.order_line.item,
            location=inventory.location,
            lot_number=inventory.lot_number,
            expiry_date=inventory.expiry_date,
            transaction_type=StockLedger.Type.SHIP,
            qty_change=-quantity,
            reference_type="SHIPMENT",
            reference_id=str(shipment.pk),
            user=user,
            idempotency_key=idempotency_key,
        )
        reservation.status = Reservation.Status.CONSUMED
        reservation.save(update_fields=("status",))
        order_line = OrderLine.objects.select_for_update().get(pk=reservation.order_line_id)
        order_line.qty_shipped += quantity
        order_line.save(update_fields=("qty_shipped",))
    order.status = CustomerOrder.Status.SHIPPED
    order.shipped_at = timezone.now()
    order.save(update_fields=("status", "shipped_at"))
    audit(user, "ORDER_SHIPPED", "CustomerOrder", order.pk, reference_type="SHIPMENT",
          reference_id=shipment.pk, details={"carrier": carrier, "tracking_number": tracking_number})
    return shipment
