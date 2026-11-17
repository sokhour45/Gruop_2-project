from decimal import Decimal
from datetime import date, timedelta

from django.db import DatabaseError
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from warehouse_api.models import (
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
    StockLedger,
    User,
    Warehouse,
)
from warehouse_api.services import (
    Conflict,
    allocate_order,
    confirm_pick,
    post_movement,
    receive_line,
    transfer_stock,
)


class StockMovementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="operator",
            password="test-password",
            role=User.Role.OPERATOR,
        )
        self.warehouse = Warehouse.objects.create(code="WH1", name="Main")
        self.receiving = Location.objects.create(
            warehouse=self.warehouse,
            bin_code="RECEIVING",
            kind=Location.Kind.RECEIVING,
            is_pickable=False,
        )
        self.storage = Location.objects.create(
            warehouse=self.warehouse,
            bin_code="A-01",
            kind=Location.Kind.STORAGE,
        )
        self.second_storage = Location.objects.create(
            warehouse=self.warehouse,
            bin_code="B-01",
            kind=Location.Kind.STORAGE,
        )
        self.quarantine = Location.objects.create(
            warehouse=self.warehouse,
            bin_code="Q-01",
            kind=Location.Kind.QUARANTINE,
            is_pickable=False,
        )
        self.item = Item.objects.create(
            sku="SKU-1",
            barcode="0123456789",
            description="Test item",
        )
        self.receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_type=Receipt.SourceType.PO,
            source_reference="PO-1",
            receiving_location=self.receiving,
            created_by=self.user,
        )
        self.line = ReceiptLine.objects.create(
            receipt=self.receipt,
            item=self.item,
            expected_qty=Decimal("5"),
        )

    def test_receive_rejects_wrong_barcode_without_stock_or_ledger_write(self):
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(
            f"/api/v1/receipts/{self.receipt.pk}/receive/",
            {"line_id": self.line.pk, "barcode": "WRONG", "quantity": "1"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="receive-wrong-barcode",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Inventory.objects.exists())
        self.assertFalse(StockLedger.objects.exists())

    def test_receive_is_idempotent_and_creates_matching_inventory_and_ledger(self):
        client = APIClient()
        client.force_authenticate(self.user)
        request = {
            "line_id": self.line.pk,
            "barcode": self.item.barcode,
            "quantity": "5",
        }

        first = client.post(
            f"/api/v1/receipts/{self.receipt.pk}/receive/",
            request,
            format="json",
            HTTP_IDEMPOTENCY_KEY="receive-once",
        )
        duplicate = client.post(
            f"/api/v1/receipts/{self.receipt.pk}/receive/",
            request,
            format="json",
            HTTP_IDEMPOTENCY_KEY="receive-once",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(first.data, duplicate.data)
        self.assertEqual(StockLedger.objects.count(), 1)
        inventory = Inventory.objects.get(item=self.item, location=self.receiving)
        self.assertEqual(inventory.qty_on_hand, Decimal("5"))
        self.assertEqual(StockLedger.objects.get().qty_change, inventory.qty_on_hand)

    def test_transfer_conserves_stock_and_writes_two_balanced_ledger_rows(self):
        receive_line(
            receipt=self.receipt,
            line=self.line,
            barcode=self.item.barcode,
            quantity=Decimal("5"),
            user=self.user,
        )

        transfer_stock(
            item=self.item,
            source=self.receiving,
            destination=self.storage,
            quantity=Decimal("3"),
            transaction_type=StockLedger.Type.PUTAWAY,
            user=self.user,
            reference_type="RECEIPT",
            reference_id=self.receipt.pk,
        )

        self.assertEqual(StockLedger.objects.count(), 3)
        self.assertEqual(
            sum(StockLedger.objects.values_list("qty_change", flat=True)),
            Decimal("5"),
        )
        self.assertEqual(
            sum(Inventory.objects.filter(item=self.item).values_list("qty_on_hand", flat=True)),
            Decimal("5"),
        )
        self.assertEqual(Inventory.objects.get(location=self.receiving).qty_on_hand, Decimal("2"))
        self.assertEqual(Inventory.objects.get(location=self.storage).qty_on_hand, Decimal("3"))

    def test_operator_bin_transfer_posts_balanced_ledger_rows_and_is_idempotent(self):
        post_movement(
            item=self.item,
            location=self.storage,
            qty_change=Decimal("5"),
            transaction_type=StockLedger.Type.OPENING_BALANCE,
            user=self.user,
        )
        client = APIClient()
        client.force_authenticate(self.user)
        payload = {
            "warehouse": self.warehouse.pk,
            "barcode": self.item.barcode,
            "source_bin": self.storage.bin_code,
            "destination_bin": self.second_storage.bin_code,
            "quantity": "2",
        }
        invalid_barcode = client.post(
            "/api/v1/inventory/transfer/",
            {**payload, "barcode": "WRONG"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="bin-transfer-wrong-barcode",
        )
        insufficient_stock = client.post(
            "/api/v1/inventory/transfer/",
            {**payload, "quantity": "6"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="bin-transfer-insufficient",
        )

        first = client.post(
            "/api/v1/inventory/transfer/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="bin-transfer-1",
        )
        retry = client.post(
            "/api/v1/inventory/transfer/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="bin-transfer-1",
        )

        self.assertEqual(invalid_barcode.status_code, 400)
        self.assertEqual(insufficient_stock.status_code, 409)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.data, retry.data)
        transfer_rows = StockLedger.objects.filter(transaction_type=StockLedger.Type.TRANSFER)
        self.assertEqual(transfer_rows.count(), 2)
        self.assertEqual(sum(transfer_rows.values_list("qty_change", flat=True)), Decimal("0"))
        self.assertEqual(Inventory.objects.get(location=self.storage).qty_on_hand, Decimal("3"))
        self.assertEqual(Inventory.objects.get(location=self.second_storage).qty_on_hand, Decimal("2"))

    def test_negative_stock_is_rejected_without_ledger_write(self):
        with self.assertRaises(Conflict):
            post_movement(
                item=self.item,
                location=self.storage,
                qty_change=Decimal("-1"),
                transaction_type=StockLedger.Type.ADJUST,
                user=self.user,
            )

        self.assertFalse(StockLedger.objects.exists())

    def test_ledger_rows_cannot_be_updated_or_deleted(self):
        row = StockLedger.objects.create(
            item=self.item,
            location=self.receiving,
            transaction_type=StockLedger.Type.RECEIPT,
            qty_change=Decimal("1"),
            user=self.user,
        )

        row.qty_change = Decimal("2")
        with self.assertRaises(ValueError):
            row.save()
        with self.assertRaises(ValueError):
            row.delete()
        with self.assertRaises(DatabaseError):
            StockLedger.objects.filter(pk=row.pk).update(qty_change=Decimal("3"))

    def test_csv_order_import_supports_quoted_fields_and_idempotent_retries(self):
        client = APIClient()
        client.force_authenticate(self.user)
        csv_bytes = (
            b"external_reference,warehouse,sku,quantity\n"
            b'"ORDER, 1",WH1,SKU-1,2\n'
        )

        def upload():
            return client.post(
                "/api/v1/orders/import-orders/",
                {"file": SimpleUploadedFile("orders.csv", csv_bytes, content_type="text/csv")},
                format="multipart",
                HTTP_IDEMPOTENCY_KEY="csv-order-import",
            )

        first = upload()
        retry = upload()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(first.data, retry.data)
        self.assertEqual(CustomerOrder.objects.count(), 1)
        self.assertEqual(CustomerOrder.objects.get().external_reference, "ORDER, 1")

    def test_cycle_count_adjusts_the_matching_lot_and_records_ledger_entry(self):
        manager = User.objects.create_user(
            username="manager",
            password="test-password",
            role=User.Role.MANAGER,
        )
        lot_item = Item.objects.create(
            sku="LOT-SKU",
            barcode="LOT-BC",
            description="Lot-tracked item",
            track_lot=True,
            track_expiry=True,
        )
        expiry = date(2027, 1, 31)
        inventory = Inventory.objects.create(
            item=lot_item,
            location=self.storage,
            lot_number="LOT-A",
            expiry_date=expiry,
            qty_on_hand=Decimal("5"),
        )
        StockLedger.objects.create(
            item=lot_item,
            location=self.storage,
            lot_number="LOT-A",
            expiry_date=expiry,
            transaction_type=StockLedger.Type.OPENING_BALANCE,
            qty_change=Decimal("5"),
            user=self.user,
        )
        count = CycleCount.objects.create(warehouse=self.warehouse, created_by=manager)
        line = CycleCountLine.objects.create(
            count=count,
            item=lot_item,
            location=self.storage,
            lot_number="LOT-A",
            expiry_date=expiry,
            expected_qty=Decimal("5"),
        )
        client = APIClient()
        client.force_authenticate(self.user)

        counted = client.post(
            f"/api/v1/cycle-counts/{count.pk}/count-line/",
            {
                "line_id": line.pk,
                "bin_code": self.storage.bin_code,
                "barcode": lot_item.barcode,
                "lot_number": "LOT-A",
                "expiry_date": expiry.isoformat(),
                "counted_qty": "3",
            },
            format="json",
        )
        self.assertEqual(counted.status_code, 200)

        client.force_authenticate(manager)
        approved = client.post(f"/api/v1/cycle-counts/{count.pk}/approve/", {}, format="json")

        self.assertEqual(approved.status_code, 200)
        inventory.refresh_from_db()
        self.assertEqual(inventory.qty_on_hand, Decimal("3"))
        adjustment = StockLedger.objects.get(transaction_type=StockLedger.Type.CYCLE_COUNT)
        self.assertEqual(adjustment.qty_change, Decimal("-2"))
        self.assertEqual(adjustment.lot_number, "LOT-A")
        self.assertEqual(adjustment.expiry_date, expiry)

    def test_return_inspection_routes_restock_quarantine_and_manager_approved_scrap(self):
        manager = User.objects.create_user(
            username="return-manager",
            password="test-password",
            role=User.Role.MANAGER,
        )
        receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_type=Receipt.SourceType.RETURN,
            source_reference="RMA-1",
            receiving_location=self.receiving,
            created_by=self.user,
        )
        line = ReceiptLine.objects.create(
            receipt=receipt,
            item=self.item,
            expected_qty=Decimal("5"),
        )
        receive_line(
            receipt=receipt,
            line=line,
            barcode=self.item.barcode,
            quantity=Decimal("5"),
            user=self.user,
        )
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, Receipt.Status.INSPECTING)

        client = APIClient()
        client.force_authenticate(self.user)
        endpoint = f"/api/v1/receipts/{receipt.pk}/inspect-return/"

        def disposition(kind, amount, destination, key, reason):
            return client.post(
                endpoint,
                {
                    "line_id": line.pk,
                    "barcode": self.item.barcode,
                    "quantity": str(amount),
                    "disposition": kind,
                    "destination_bin": destination,
                    "reason": reason,
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=key,
            )

        wrong_barcode = client.post(
            endpoint,
            {
                "line_id": line.pk,
                "barcode": "WRONG",
                "quantity": "1",
                "disposition": "RESTOCK",
                "destination_bin": self.storage.bin_code,
                "reason": "Packaging intact",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="return-wrong-barcode",
        )
        over_disposed = disposition("RESTOCK", 6, self.storage.bin_code, "return-over-disposed", "Packaging intact")
        restocked = disposition("RESTOCK", 2, self.storage.bin_code, "return-restock", "Packaging intact")
        restocked_retry = disposition("RESTOCK", 2, self.storage.bin_code, "return-restock", "Packaging intact")
        quarantined = disposition("QUARANTINE", 2, self.quarantine.bin_code, "return-quarantine", "Needs inspection")
        unauthorized_scrap = disposition("SCRAP", 1, "", "return-scrap-denied", "Damaged")

        self.assertEqual(wrong_barcode.status_code, 400)
        self.assertEqual(over_disposed.status_code, 400)
        self.assertEqual(restocked.status_code, 200)
        self.assertEqual(restocked_retry.status_code, 200)
        self.assertEqual(restocked.data, restocked_retry.data)
        self.assertEqual(quarantined.status_code, 200)
        self.assertEqual(unauthorized_scrap.status_code, 403)
        self.assertEqual(ReturnDisposition.objects.count(), 2)

        client.force_authenticate(manager)
        incomplete_close = client.post(
            f"/api/v1/receipts/{receipt.pk}/close/",
            {},
            format="json",
        )
        scrapped = disposition("SCRAP", 1, "", "return-scrap-approved", "Damaged beyond repair")
        closed = client.post(
            f"/api/v1/receipts/{receipt.pk}/close/",
            {},
            format="json",
        )

        self.assertEqual(incomplete_close.status_code, 409)
        self.assertEqual(scrapped.status_code, 200)
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.data["status"], Receipt.Status.CLOSED)
        self.assertEqual(Inventory.objects.get(item=self.item, location=self.receiving).qty_on_hand, Decimal("0"))
        self.assertEqual(Inventory.objects.get(item=self.item, location=self.storage).qty_on_hand, Decimal("2"))
        self.assertEqual(Inventory.objects.get(item=self.item, location=self.quarantine).qty_on_hand, Decimal("2"))
        self.assertEqual(StockLedger.objects.filter(transaction_type=StockLedger.Type.ADJUST).count(), 1)

    def test_replenishment_advisor_accounts_for_reservations_and_inbound_stock(self):
        manager = User.objects.create_user(
            username="replenishment-manager",
            password="test-password",
            role=User.Role.MANAGER,
        )
        self.receipt.status = Receipt.Status.CANCELLED
        self.receipt.save(update_fields=("status",))
        self.item.min_stock = Decimal("10")
        self.item.save(update_fields=("min_stock",))
        Inventory.objects.create(
            item=self.item,
            location=self.storage,
            qty_on_hand=Decimal("2"),
            qty_reserved=Decimal("1"),
        )
        open_receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_type=Receipt.SourceType.PO,
            source_reference="PO-REORDER",
            receiving_location=self.receiving,
            created_by=self.user,
        )
        ReceiptLine.objects.create(
            receipt=open_receipt,
            item=self.item,
            expected_qty=Decimal("5"),
            received_qty=Decimal("2"),
            putaway_qty=Decimal("1"),
        )
        ReceiptLine.objects.create(
            receipt=open_receipt,
            item=self.item,
            expected_qty=Decimal("1"),
            received_qty=Decimal("3"),
            putaway_qty=Decimal("3"),
        )

        covered_item = Item.objects.create(
            sku="SKU-COVERED",
            barcode="COVERED-BC",
            description="Covered by inbound",
            min_stock=Decimal("10"),
        )
        Inventory.objects.create(
            item=covered_item,
            location=self.storage,
            qty_on_hand=Decimal("4"),
            qty_reserved=Decimal("1"),
        )
        covered_receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_type=Receipt.SourceType.PO,
            source_reference="PO-COVERED",
            receiving_location=self.receiving,
            created_by=self.user,
        )
        ReceiptLine.objects.create(
            receipt=covered_receipt,
            item=covered_item,
            expected_qty=Decimal("10"),
            received_qty=Decimal("4"),
            putaway_qty=Decimal("2"),
        )

        client = APIClient()
        client.force_authenticate(self.user)
        forbidden = client.get("/api/v1/reports/replenishment/")
        client.force_authenticate(manager)
        response = client.get("/api/v1/reports/replenishment/")

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(response.status_code, 200)
        rows = {row["sku"]: row for row in response.data}
        self.assertEqual(Decimal(rows["SKU-1"]["available"]), Decimal("1"))
        self.assertEqual(Decimal(rows["SKU-1"]["open_po_qty"]), Decimal("3"))
        self.assertEqual(Decimal(rows["SKU-1"]["pending_putaway_qty"]), Decimal("1"))
        self.assertEqual(Decimal(rows["SKU-1"]["suggested_order_qty"]), Decimal("5"))
        self.assertEqual(rows["SKU-1"]["status"], "REORDER")
        self.assertEqual(Decimal(rows["SKU-COVERED"]["projected_available"]), Decimal("11"))
        self.assertEqual(Decimal(rows["SKU-COVERED"]["suggested_order_qty"]), Decimal("0"))
        self.assertEqual(rows["SKU-COVERED"]["status"], "INBOUND_COVERS")

    def test_expiry_report_and_low_stock_exclude_expired_tracked_stock(self):
        manager = User.objects.create_user(
            username="expiry-manager",
            password="test-password",
            role=User.Role.MANAGER,
        )
        item = Item.objects.create(
            sku="EXPIRY-SKU",
            barcode="EXPIRY-BC",
            description="Expiry tracked item",
            min_stock=Decimal("10"),
            track_lot=True,
            track_expiry=True,
        )
        today = timezone.localdate()
        post_movement(
            item=item,
            location=self.storage,
            qty_change=Decimal("5"),
            transaction_type=StockLedger.Type.OPENING_BALANCE,
            user=self.user,
            lot_number="EXPIRED",
            expiry_date=today - timedelta(days=1),
        )
        post_movement(
            item=item,
            location=self.storage,
            qty_change=Decimal("2"),
            transaction_type=StockLedger.Type.OPENING_BALANCE,
            user=self.user,
            lot_number="SOON",
            expiry_date=today + timedelta(days=10),
        )
        post_movement(
            item=item,
            location=self.storage,
            qty_change=Decimal("3"),
            transaction_type=StockLedger.Type.OPENING_BALANCE,
            user=self.user,
            lot_number="LATER",
            expiry_date=today + timedelta(days=45),
        )

        client = APIClient()
        client.force_authenticate(self.user)
        forbidden = client.get("/api/v1/reports/expiry/?days=30")
        low_stock = client.get("/api/v1/reports/low-stock/")
        client.force_authenticate(manager)
        expiry_report = client.get("/api/v1/reports/expiry/?days=30")
        invalid_window = client.get("/api/v1/reports/expiry/?days=0")

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(low_stock.status_code, 200)
        low_row = next(row for row in low_stock.data if row["sku"] == item.sku)
        self.assertEqual(Decimal(low_row["on_hand"]), Decimal("5"))
        self.assertEqual(Decimal(low_row["expired_qty"]), Decimal("5"))
        self.assertEqual(expiry_report.status_code, 200)
        self.assertEqual(
            [(row["lot_number"], row["status"]) for row in expiry_report.data["results"]],
            [("EXPIRED", "EXPIRED"), ("SOON", "EXPIRING_SOON")],
        )
        self.assertEqual(invalid_window.status_code, 400)

    def test_order_allocation_uses_fefo_and_skips_expired_lots(self):
        item = Item.objects.create(
            sku="FEFO-SKU",
            barcode="FEFO-BC",
            description="FEFO item",
            track_lot=True,
            track_expiry=True,
        )
        today = timezone.localdate()
        for lot, expiry, quantity in (
            ("EXPIRED", today - timedelta(days=1), Decimal("5")),
            ("FIRST-EXPIRY", today + timedelta(days=5), Decimal("2")),
            ("SECOND-EXPIRY", today + timedelta(days=20), Decimal("5")),
        ):
            post_movement(
                item=item,
                location=self.storage,
                qty_change=quantity,
                transaction_type=StockLedger.Type.OPENING_BALANCE,
                user=self.user,
                lot_number=lot,
                expiry_date=expiry,
            )
        order = CustomerOrder.objects.create(
            warehouse=self.warehouse,
            external_reference="FEFO-ORDER",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, item=item, qty_ordered=Decimal("4"))

        task = allocate_order(order, self.user)
        picked_lots = list(
            task.lines.select_related("reservation__inventory").order_by(
                "reservation__inventory__expiry_date"
            )
        )

        self.assertEqual(
            [line.reservation.inventory.lot_number for line in picked_lots],
            ["FIRST-EXPIRY", "SECOND-EXPIRY"],
        )
        self.assertEqual(
            [line.qty_requested for line in picked_lots],
            [Decimal("2"), Decimal("2")],
        )
        self.assertEqual(
            Inventory.objects.get(item=item, lot_number="EXPIRED").qty_reserved,
            Decimal("0"),
        )

    def test_pick_confirmation_rejects_lot_that_expired_after_reservation(self):
        item = Item.objects.create(
            sku="EXPIRED-PICK-SKU",
            barcode="EXPIRED-PICK-BC",
            description="Expired reserved item",
            track_lot=True,
            track_expiry=True,
        )
        expired_date = timezone.localdate() - timedelta(days=1)
        _, inventory = post_movement(
            item=item,
            location=self.storage,
            qty_change=Decimal("2"),
            transaction_type=StockLedger.Type.OPENING_BALANCE,
            user=self.user,
            lot_number="EXPIRED",
            expiry_date=expired_date,
        )
        inventory.qty_reserved = Decimal("1")
        inventory.save(update_fields=("qty_reserved",))
        order = CustomerOrder.objects.create(
            warehouse=self.warehouse,
            external_reference="EXPIRED-PICK-ORDER",
            created_by=self.user,
        )
        order_line = OrderLine.objects.create(order=order, item=item, qty_ordered=Decimal("1"))
        task = PickTask.objects.create(order=order, assigned_to=self.user, status=PickTask.Status.RELEASED)
        reservation = Reservation.objects.create(
            order_line=order_line,
            inventory=inventory,
            qty_reserved=Decimal("1"),
        )
        task_line = PickTaskLine.objects.create(
            task=task,
            order_line=order_line,
            reservation=reservation,
            qty_requested=Decimal("1"),
        )

        with self.assertRaises(Conflict):
            confirm_pick(
                task_line=task_line,
                bin_code=self.storage.bin_code,
                barcode=item.barcode,
                quantity=Decimal("1"),
                user=self.user,
            )

        self.assertEqual(StockLedger.objects.count(), 1)
        inventory.refresh_from_db()
        self.assertEqual(inventory.qty_on_hand, Decimal("2"))
        self.assertEqual(inventory.qty_reserved, Decimal("1"))

    def test_expired_return_cannot_be_restocked_but_can_be_quarantined(self):
        item = Item.objects.create(
            sku="EXPIRED-RETURN-SKU",
            barcode="EXPIRED-RETURN-BC",
            description="Expired returned item",
            track_lot=True,
            track_expiry=True,
        )
        expired_date = timezone.localdate() - timedelta(days=1)
        receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_type=Receipt.SourceType.RETURN,
            source_reference="RMA-EXPIRED",
            receiving_location=self.receiving,
            status=Receipt.Status.INSPECTING,
            created_by=self.user,
        )
        line = ReceiptLine.objects.create(
            receipt=receipt,
            item=item,
            expected_qty=Decimal("1"),
            received_qty=Decimal("1"),
            lot_number="EXPIRED-LOT",
            expiry_date=expired_date,
        )
        post_movement(
            item=item,
            location=self.receiving,
            qty_change=Decimal("1"),
            transaction_type=StockLedger.Type.RECEIPT,
            user=self.user,
            reference_type="RECEIPT",
            reference_id=receipt.pk,
            lot_number=line.lot_number,
            expiry_date=expired_date,
        )
        client = APIClient()
        client.force_authenticate(self.user)
        endpoint = f"/api/v1/receipts/{receipt.pk}/inspect-return/"
        base_payload = {
            "line_id": line.pk,
            "barcode": item.barcode,
            "quantity": "1",
            "lot_number": line.lot_number,
            "expiry_date": expired_date.isoformat(),
            "destination_bin": self.storage.bin_code,
            "reason": "Expired product",
        }

        rejected = client.post(
            endpoint,
            {**base_payload, "disposition": "RESTOCK"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="expired-return-restock",
        )
        quarantined = client.post(
            endpoint,
            {**base_payload, "disposition": "QUARANTINE", "destination_bin": self.quarantine.bin_code},
            format="json",
            HTTP_IDEMPOTENCY_KEY="expired-return-quarantine",
        )

        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(quarantined.status_code, 200)
        self.assertEqual(
            Inventory.objects.get(item=item, location=self.quarantine).qty_on_hand,
            Decimal("1"),
        )
