import csv
import io
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.decorators import method_decorator
from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

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
from warehouse_api.permissions import (
    AdminOnly,
    ManagerOrAdmin,
    OperatorOrAbove,
    ReadOnlyOrAdminManager,
    ViewerReadOnly,
)
from warehouse_api.serializers import (
    AdjustmentSerializer,
    AuditLogSerializer,
    CustomerSerializer,
    CycleCountSerializer,
    InventorySerializer,
    ItemSerializer,
    LocationSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    PickTaskSerializer,
    ReceiptCreateSerializer,
    ReceiptSerializer,
    ReturnDispositionSerializer,
    ShipmentSerializer,
    StockLedgerSerializer,
    SupplierSerializer,
    UserCreateSerializer,
    UserSerializer,
    WarehouseSerializer,
)
from warehouse_api.services import (
    Conflict,
    allocate_order,
    audit,
    confirm_pick,
    confirm_putaway,
    dispose_return_line,
    post_movement,
    receive_line,
    run_idempotent,
    ship_order,
    suggest_putaway,
    transfer_stock,
    verify_pack,
)


class WarehouseTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.pk,
            "username": self.user.username,
            "role": self.user.role,
        }
        return data


class WarehouseTokenView(TokenObtainPairView):
    serializer_class = WarehouseTokenSerializer
    permission_classes = (AllowAny,)


def app_shell(request):
    return render(request, "warehouse_api/app.html")


def service_worker(request):
    from pathlib import Path

    worker = Path(__file__).resolve().parent / "static" / "warehouse_api" / "service-worker.js"
    response = HttpResponse(worker.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


class MasterDataViewSet(viewsets.ModelViewSet):
    permission_classes = (ReadOnlyOrAdminManager,)
    audit_name = "MasterData"

    @method_decorator(transaction.atomic)
    def perform_create(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "MASTER_CREATED", self.audit_name, instance.pk)

    @method_decorator(transaction.atomic)
    def perform_update(self, serializer):
        instance = serializer.instance
        if serializer.validated_data.get("is_active") is False:
            if isinstance(instance, Item) and Inventory.objects.filter(item=instance, qty_on_hand__gt=0).exists():
                raise ValidationError({"is_active": "Move all stock before deactivating this item."})
            if isinstance(instance, Location) and Inventory.objects.filter(location=instance, qty_on_hand__gt=0).exists():
                raise ValidationError({"is_active": "Move all stock before deactivating this bin."})
        instance = serializer.save()
        audit(self.request.user, "MASTER_UPDATED", self.audit_name, instance.pk)

    @method_decorator(transaction.atomic)
    def perform_destroy(self, instance):
        if not hasattr(instance, "is_active"):
            raise ValidationError("This record cannot be deleted.")
        if isinstance(instance, Item) and Inventory.objects.filter(item=instance, qty_on_hand__gt=0).exists():
            raise ValidationError("Move all stock before deactivating this item.")
        if isinstance(instance, Location) and Inventory.objects.filter(location=instance, qty_on_hand__gt=0).exists():
            raise ValidationError("Move all stock before deactivating this bin.")
        instance.is_active = False
        instance.save(update_fields=("is_active",))
        audit(self.request.user, "MASTER_DEACTIVATED", self.audit_name, instance.pk)


class ItemViewSet(MasterDataViewSet):
    serializer_class = ItemSerializer
    queryset = Item.objects.all().order_by("sku")
    audit_name = "Item"

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get("query", "").strip()
        active = self.request.query_params.get("active")
        if query:
            queryset = queryset.filter(
                Q(sku__icontains=query)
                | Q(barcode__icontains=query)
                | Q(description__icontains=query)
            )
        if active in {"true", "false"}:
            queryset = queryset.filter(is_active=active == "true")
        return queryset


class LocationViewSet(MasterDataViewSet):
    serializer_class = LocationSerializer
    queryset = Location.objects.select_related("warehouse").all()
    audit_name = "Location"

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get("query", "").strip()
        warehouse = self.request.query_params.get("warehouse")
        if query:
            queryset = queryset.filter(Q(bin_code__icontains=query) | Q(zone__icontains=query))
        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)
        return queryset


class SupplierViewSet(MasterDataViewSet):
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.all().order_by("name")
    audit_name = "Supplier"


class CustomerViewSet(MasterDataViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all().order_by("name")
    audit_name = "Customer"


class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WarehouseSerializer
    queryset = Warehouse.objects.filter(is_active=True).order_by("code")


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.all().order_by("username")
    permission_classes = (AdminOnly,)

    def get_serializer_class(self):
        return UserCreateSerializer if self.action == "create" else UserSerializer

    @method_decorator(transaction.atomic)
    def perform_update(self, serializer):
        user = serializer.save()
        if user.role != User.Role.ADMIN:
            if user.is_superuser:
                user.is_superuser = False
                user.save(update_fields=("is_superuser",))
            user.is_staff = False
        else:
            user.is_staff = True
        if (
            user.role != User.Role.ADMIN or not user.is_active
        ) and not User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=user.pk).exists():
            raise ValidationError("At least one active administrator account is required.")
        user.save(update_fields=("is_staff",))
        audit(self.request.user, "USER_UPDATED", "User", user.pk, details={"role": user.role, "active": user.is_active})

    @method_decorator(transaction.atomic)
    def perform_create(self, serializer):
        user = serializer.save()
        if user.role == User.Role.ADMIN:
            user.is_staff = True
            user.save(update_fields=("is_staff",))
        audit(self.request.user, "USER_CREATED", "User", user.pk, details={"role": user.role})

    @method_decorator(transaction.atomic)
    def perform_destroy(self, instance):
        if instance.role == User.Role.ADMIN and User.objects.filter(role=User.Role.ADMIN, is_active=True).count() <= 1:
            raise ValidationError("At least one active administrator account is required.")
        instance.is_active = False
        instance.save(update_fields=("is_active",))
        audit(self.request.user, "USER_DEACTIVATED", "User", instance.pk)


class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Receipt.objects.select_related("warehouse", "supplier", "receiving_location").prefetch_related(
        "lines__item",
        "lines__return_dispositions__destination",
        "lines__return_dispositions__inspected_by",
    )
    permission_classes = (ViewerReadOnly,)

    def get_serializer_class(self):
        return ReceiptCreateSerializer if self.action == "create" else ReceiptSerializer

    @method_decorator(transaction.atomic)
    def create(self, request, *args, **kwargs):
        serializer = ReceiptCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        receipt = serializer.save()
        audit(request.user, "RECEIPT_CREATED", "Receipt", receipt.pk, reference_type=receipt.source_type, reference_id=receipt.source_reference)
        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), permission_classes=(OperatorOrAbove,))
    def receive(self, request, pk=None):
        receipt = self.get_object()
        payload = ReceiveRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        line = get_object_or_404(ReceiptLine, pk=values["line_id"], receipt=receipt)
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            ledger, updated_line = receive_line(
                receipt=receipt,
                line=line,
                barcode=values["barcode"],
                quantity=values["quantity"],
                user=request.user,
                lot_number=values.get("lot_number", ""),
                expiry_date=values.get("expiry_date"),
                discrepancy_type=values.get("discrepancy_type", ""),
                discrepancy_note=values.get("discrepancy_note", ""),
                idempotency_key=key,
            )
            return status.HTTP_200_OK, {
                "receipt_id": receipt.pk,
                "line_id": updated_line.pk,
                "received_qty": str(updated_line.received_qty),
                "expected_qty": str(updated_line.expected_qty),
                "ledger_id": ledger.pk,
                "status": receipt.status,
            }

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)

    @action(detail=True, methods=("get",), url_path="putaway-suggestion", permission_classes=(OperatorOrAbove,))
    def putaway_suggestion(self, request, pk=None):
        receipt = self.get_object()
        line = get_object_or_404(ReceiptLine, pk=request.query_params.get("line_id"), receipt=receipt)
        quantity = request.query_params.get("quantity", str(line.received_qty - line.putaway_qty))
        destination = suggest_putaway(receipt, line, quantity)
        if destination is None:
            return Response({"detail": "No eligible putaway bin found."}, status=status.HTTP_409_CONFLICT)
        return Response({"bin_code": destination.bin_code, "location_id": destination.pk, "zone": destination.zone})

    @action(detail=True, methods=("post",), url_path="inspect-return", permission_classes=(OperatorOrAbove,))
    def inspect_return(self, request, pk=None):
        receipt = self.get_object()
        payload = ReturnDispositionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        line = get_object_or_404(ReceiptLine, pk=values["line_id"], receipt=receipt)
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            record = dispose_return_line(
                receipt=receipt,
                line=line,
                barcode=values["barcode"],
                quantity=values["quantity"],
                disposition=values["disposition"],
                destination_bin=values.get("destination_bin", ""),
                lot_number=values.get("lot_number", ""),
                expiry_date=values.get("expiry_date"),
                reason=values["reason"],
                user=request.user,
                idempotency_key=key,
            )
            return status.HTTP_200_OK, ReturnDispositionSerializer(record).data

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)

    @action(detail=True, methods=("post",), permission_classes=(OperatorOrAbove,))
    def putaway(self, request, pk=None):
        receipt = self.get_object()
        payload = PutawayRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        line = get_object_or_404(ReceiptLine, pk=values["line_id"], receipt=receipt)
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            updated_line = confirm_putaway(
                receipt=receipt,
                line=line,
                barcode=values["barcode"],
                bin_code=values["bin_code"],
                quantity=values["quantity"],
                user=request.user,
                idempotency_key=key,
            )
            return status.HTTP_200_OK, {
                "receipt_id": receipt.pk,
                "line_id": updated_line.pk,
                "putaway_qty": str(updated_line.putaway_qty),
                "actual_bin": updated_line.actual_bin.bin_code,
                "status": receipt.status,
            }

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)

    @method_decorator(transaction.atomic)
    @action(detail=True, methods=("post",), permission_classes=(ManagerOrAdmin,))
    def close(self, request, pk=None):
        receipt = self.get_object()
        if receipt.source_type == Receipt.SourceType.RETURN:
            for line in receipt.lines.prefetch_related("return_dispositions"):
                dispositioned = sum(
                    (entry.quantity for entry in line.return_dispositions.all()),
                    Decimal("0"),
                )
                if dispositioned < line.received_qty:
                    raise Conflict("All received return quantities must be inspected and dispositioned before closing.")
        elif receipt.lines.filter(putaway_qty__lt=F("received_qty")).exists():
            raise Conflict("All received quantities must be put away before closing.")
        if receipt.lines.filter(received_qty__lt=F("expected_qty")).exists() and not request.data.get("short_close_reason"):
            raise ValidationError({"short_close_reason": "A reason is required to close a partial receipt."})
        receipt.status = Receipt.Status.CLOSED
        receipt.closed_at = timezone.now()
        receipt.save(update_fields=("status", "closed_at"))
        audit(request.user, "RECEIPT_CLOSED", "Receipt", receipt.pk, details={"reason": request.data.get("short_close_reason", "")})
        return Response(ReceiptSerializer(receipt).data)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomerOrder.objects.select_related("warehouse", "customer").prefetch_related("lines__item")
    permission_classes = (ViewerReadOnly,)

    def get_serializer_class(self):
        return OrderCreateSerializer if self.action == "create" else OrderSerializer

    def create(self, request, *args, **kwargs):
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            external_reference = request.data.get("external_reference")
            existing = CustomerOrder.objects.filter(external_reference=external_reference).first() if external_reference else None
            if existing:
                incoming = sorted(
                    (line.get("sku"), str(line.get("qty_ordered")))
                    for line in request.data.get("lines", [])
                )
                persisted = sorted(
                    (line.item.sku, str(line.qty_ordered))
                    for line in existing.lines.select_related("item")
                )
                if incoming != persisted:
                    raise Conflict(f"External order {external_reference} already exists with different lines.")
                return status.HTTP_200_OK, OrderSerializer(existing).data
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            order = serializer.save()
            audit(request.user, "ORDER_CREATED", "CustomerOrder", order.pk, reference_type="ORDER", reference_id=order.external_reference or order.pk)
            return status.HTTP_201_CREATED, OrderSerializer(order).data

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)

    def perform_create(self, serializer):
        order = serializer.save()
        audit(self.request.user, "ORDER_CREATED", "CustomerOrder", order.pk, reference_type="ORDER", reference_id=order.external_reference or order.pk)

    @action(
        detail=False,
        methods=("post",),
        url_path="import-orders",
        permission_classes=(OperatorOrAbove,),
        parser_classes=(JSONParser, MultiPartParser),
    )
    def import_orders(self, request):
        if request.FILES.get("file"):
            uploaded = request.FILES["file"]
            if uploaded.size > 2_000_000:
                raise ValidationError({"file": "CSV must be smaller than 2 MB."})
            try:
                text = uploaded.read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(text))
                required = {"external_reference", "warehouse", "sku", "quantity"}
                if (
                    not reader.fieldnames
                    or any(not isinstance(name, str) or not name.strip() for name in reader.fieldnames)
                    or len({name.strip().lower() for name in reader.fieldnames}) != len(reader.fieldnames)
                    or not required.issubset({name.strip().lower() for name in reader.fieldnames})
                ):
                    raise ValidationError({"file": "CSV headers must include external_reference, warehouse, sku, quantity."})
                header_map = {name.strip().lower(): name for name in reader.fieldnames}
                grouped = {}
                for row_number, row in enumerate(reader, start=2):
                    if None in row:
                        raise ValidationError({"file": f"CSV row {row_number} has more values than headers."})
                    normalized = {key: (row.get(source) or "").strip() for key, source in header_map.items()}
                    if any(not normalized.get(key) for key in required):
                        raise ValidationError({"file": f"CSV row {row_number} has a missing required value."})
                    warehouse = Warehouse.objects.filter(code=normalized["warehouse"], is_active=True).first()
                    if warehouse is None:
                        raise ValidationError({"file": f"CSV row {row_number} has an unknown warehouse."})
                    order = grouped.setdefault(
                        normalized["external_reference"],
                        {"warehouse": warehouse.pk, "external_reference": normalized["external_reference"], "lines": []},
                    )
                    if order["warehouse"] != warehouse.pk:
                        raise ValidationError({"file": f"CSV row {row_number} changes warehouse for the same order."})
                    order["lines"].append({"sku": normalized["sku"], "qty_ordered": normalized["quantity"]})
                orders_data = list(grouped.values())
            except UnicodeDecodeError as error:
                raise ValidationError({"file": "CSV must be UTF-8 encoded."}) from error
            except csv.Error as error:
                raise ValidationError({"file": "CSV could not be parsed."}) from error
        else:
            orders_data = request.data.get("orders")
        if not isinstance(orders_data, list) or not orders_data:
            raise ValidationError({"orders": "Provide a non-empty list of orders or a CSV file."})
        if any(not isinstance(record, dict) for record in orders_data):
            raise ValidationError({"orders": "Each imported order must be an object."})
        for record in orders_data:
            lines = record.get("lines")
            if not isinstance(lines, list) or not lines:
                raise ValidationError({"orders": "Each imported order must have at least one line."})
            for line in lines:
                if not isinstance(line, dict) or not line.get("sku") or line.get("qty_ordered") is None:
                    raise ValidationError({"orders": "Each order line requires a SKU and quantity."})
                try:
                    quantity = Decimal(str(line["qty_ordered"]))
                except (InvalidOperation, TypeError, ValueError) as error:
                    raise ValidationError({"orders": "Order quantities must be valid decimals."}) from error
                if not quantity.is_finite() or quantity <= 0:
                    raise ValidationError({"orders": "Order quantities must be greater than zero."})
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            results = []
            for record in orders_data:
                external_reference = record.get("external_reference")
                existing = CustomerOrder.objects.filter(external_reference=external_reference).first() if external_reference else None
                if existing:
                    incoming = sorted((line.get("sku"), Decimal(str(line.get("qty_ordered")))) for line in record["lines"])
                    persisted = sorted((line.item.sku, line.qty_ordered) for line in existing.lines.select_related("item"))
                    if incoming != persisted or str(existing.warehouse_id) != str(record.get("warehouse")):
                        raise Conflict(f"External order {external_reference} already exists with different lines.")
                    results.append(OrderSerializer(existing).data)
                    continue
                serializer = OrderCreateSerializer(data=record, context={"request": request})
                serializer.is_valid(raise_exception=True)
                order = serializer.save()
                audit(request.user, "ORDER_IMPORTED", "CustomerOrder", order.pk, reference_type="ORDER", reference_id=external_reference or order.pk)
                results.append(OrderSerializer(order).data)
            return status.HTTP_201_CREATED, {"orders": results}

        code, body = run_idempotent(request.user, key, orders_data, operation)
        return Response(body, status=code)

    @action(detail=True, methods=("post",), permission_classes=(OperatorOrAbove,))
    def allocate(self, request, pk=None):
        order = self.get_object()
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            task = allocate_order(order, request.user)
            return status.HTTP_201_CREATED, PickTaskSerializer(task).data

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)

    @action(detail=True, methods=("post",), url_path="pack-verify", permission_classes=(OperatorOrAbove,))
    def pack_verify(self, request, pk=None):
        order = self.get_object()
        payload = PackRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            line = verify_pack(
                order=order,
                barcode=values["barcode"],
                quantity=values["quantity"],
                user=request.user,
            )
            return status.HTTP_200_OK, {
                "order_id": order.pk,
                "line_id": line.pk,
                "sku": line.item.sku,
                "qty_packed": str(line.qty_packed),
                "status": order.status,
            }

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)

    @action(detail=True, methods=("post",), permission_classes=(OperatorOrAbove,))
    def ship(self, request, pk=None):
        order = self.get_object()
        payload = ShipRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            shipment = ship_order(
                order=order,
                carrier=values.get("carrier", ""),
                tracking_number=values.get("tracking_number", ""),
                user=request.user,
                idempotency_key=key,
            )
            return status.HTTP_201_CREATED, ShipmentSerializer(shipment).data

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)


class PickTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickTask.objects.select_related("order", "assigned_to").prefetch_related("lines__order_line__item", "lines__reservation__inventory__location")
    serializer_class = PickTaskSerializer
    permission_classes = (ViewerReadOnly,)

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if self.request.user.role == User.Role.OPERATOR:
            queryset = queryset.filter(assigned_to=self.request.user)
        return queryset

    @action(detail=True, methods=("post",), permission_classes=(OperatorOrAbove,))
    def confirm(self, request, pk=None):
        task = self.get_object()
        payload = PickRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        line = get_object_or_404(PickTaskLine, pk=values["line_id"], task=task)
        key = request.headers.get("Idempotency-Key", "")

        def operation():
            updated_line = confirm_pick(
                task_line=line,
                bin_code=values["bin_code"],
                barcode=values["barcode"],
                quantity=values["quantity"],
                user=request.user,
                idempotency_key=key,
            )
            return status.HTTP_200_OK, {
                "task_id": task.pk,
                "line_id": updated_line.pk,
                "qty_picked": str(updated_line.qty_picked),
                "status": task.status,
            }

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)


class InventoryListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        queryset = Inventory.objects.select_related("item", "location")
        sku = request.query_params.get("sku")
        barcode = request.query_params.get("barcode")
        query = request.query_params.get("query")
        bin_code = request.query_params.get("bin_code")
        if sku:
            queryset = queryset.filter(item__sku__iexact=sku)
        if barcode:
            queryset = queryset.filter(item__barcode=barcode)
        if query:
            queryset = queryset.filter(Q(item__sku__iexact=query) | Q(item__barcode__iexact=query))
        if bin_code:
            queryset = queryset.filter(Q(location__bin_code__iexact=bin_code) | Q(item__sku__iexact=bin_code) | Q(item__barcode__iexact=bin_code))
        serializer = InventorySerializer(queryset, many=True)
        return Response(serializer.data)


class InventoryTransferView(APIView):
    permission_classes = (OperatorOrAbove,)

    def post(self, request):
        payload = InventoryTransferRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        matching_items = Item.objects.filter(is_active=True).filter(
            Q(sku__iexact=values["barcode"]) | Q(barcode__iexact=values["barcode"])
        )
        if matching_items.count() != 1:
            raise ValidationError({"barcode": "Scan one active SKU or barcode."})
        item = matching_items.get()
        warehouse = values["warehouse"]
        source = Location.objects.filter(
            warehouse=warehouse,
            bin_code__iexact=values["source_bin"],
            kind=Location.Kind.STORAGE,
            is_active=True,
        ).first()
        destination = Location.objects.filter(
            warehouse=warehouse,
            bin_code__iexact=values["destination_bin"],
            kind=Location.Kind.STORAGE,
            is_active=True,
        ).first()
        if source is None or destination is None:
            raise ValidationError({"bin_code": "Both bins must be active storage bins in the selected warehouse."})
        key = request.headers.get("Idempotency-Key", "")
        if len(key) > 80:
            raise ValidationError({"Idempotency-Key": "The key must be at most 80 characters."})

        def operation():
            locked_locations = list(
                Location.objects.select_for_update()
                .filter(pk__in=(source.pk, destination.pk), warehouse=warehouse, is_active=True)
                .order_by("pk")
            )
            locations_by_id = {location.pk: location for location in locked_locations}
            locked_source = locations_by_id.get(source.pk)
            locked_destination = locations_by_id.get(destination.pk)
            if (
                locked_source is None
                or locked_destination is None
                or locked_source.kind != Location.Kind.STORAGE
                or locked_destination.kind != Location.Kind.STORAGE
            ):
                raise ValidationError({"bin_code": "Both bins must remain active storage bins."})
            locked_item = Item.objects.select_for_update().get(pk=item.pk)
            if not locked_item.is_active or values["barcode"] not in {locked_item.sku, locked_item.barcode}:
                raise ValidationError({"barcode": "Scanned SKU or barcode is no longer active."})
            outbound, inbound = transfer_stock(
                item=locked_item,
                source=locked_source,
                destination=locked_destination,
                quantity=values["quantity"],
                transaction_type=StockLedger.Type.TRANSFER,
                user=request.user,
                reference_type="BIN_TRANSFER",
                reference_id=key,
                lot_number=values.get("lot_number", ""),
                expiry_date=values.get("expiry_date"),
                notes=values.get("notes", ""),
                idempotency_key=key,
            )
            return status.HTTP_200_OK, {
                "sku": locked_item.sku,
                "source_bin": locked_source.bin_code,
                "destination_bin": locked_destination.bin_code,
                "quantity": str(values["quantity"]),
                "ledger_ids": [outbound.pk, inbound.pk],
            }

        code, body = run_idempotent(request.user, key, request.data, operation)
        return Response(body, status=code)


class LowStockView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        today = timezone.localdate()
        pickable_stock = Q(
            inventory__location__is_active=True,
            inventory__location__is_pickable=True,
            inventory__location__kind=Location.Kind.STORAGE,
        )
        usable_stock = pickable_stock & (
            Q(inventory__expiry_date__gte=today)
            | Q(inventory__expiry_date__isnull=True, inventory__item__track_expiry=False)
        )
        expired_stock = pickable_stock & Q(inventory__expiry_date__lt=today)
        missing_expiry_stock = pickable_stock & Q(
            inventory__expiry_date__isnull=True,
            inventory__item__track_expiry=True,
        )
        items = Item.objects.filter(is_active=True).annotate(
            on_hand=Coalesce(Sum("inventory__qty_on_hand", filter=usable_stock), Value(Decimal("0"))),
            reserved=Coalesce(Sum("inventory__qty_reserved", filter=usable_stock), Value(Decimal("0"))),
            expired=Coalesce(Sum("inventory__qty_on_hand", filter=expired_stock), Value(Decimal("0"))),
            missing_expiry=Coalesce(
                Sum("inventory__qty_on_hand", filter=missing_expiry_stock),
                Value(Decimal("0")),
            ),
        ).annotate(available=F("on_hand") - F("reserved")).filter(available__lte=F("min_stock")).order_by("sku")
        return Response([
            {
                "item_id": item.pk,
                "sku": item.sku,
                "description": item.description,
                "on_hand": str(item.on_hand),
                "reserved": str(item.reserved),
                "available": str(item.available),
                "expired_qty": str(item.expired),
                "missing_expiry_qty": str(item.missing_expiry),
                "min_stock": str(item.min_stock),
            }
            for item in items
        ])


class ExpiryReportView(APIView):
    permission_classes = (ManagerOrAdmin,)

    def get(self, request):
        try:
            days = int(request.query_params.get("days", "30"))
        except (TypeError, ValueError):
            raise ValidationError({"days": "Use a whole number between 1 and 365."})
        if not 1 <= days <= 365:
            raise ValidationError({"days": "Use a whole number between 1 and 365."})
        today = timezone.localdate()
        inventory = Inventory.objects.select_related("item", "location").filter(
            item__is_active=True,
            item__track_expiry=True,
            location__is_active=True,
            qty_on_hand__gt=0,
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__lte=today + timedelta(days=days))
        ).order_by("expiry_date", "item__sku", "location__sequence", "location__bin_code")
        rows = []
        for balance in inventory:
            if balance.expiry_date is None:
                status_code = "MISSING_EXPIRY"
                days_to_expiry = None
            else:
                days_to_expiry = (balance.expiry_date - today).days
                status_code = "EXPIRED" if days_to_expiry < 0 else "EXPIRING_SOON"
            rows.append({
                "item_id": balance.item_id,
                "sku": balance.item.sku,
                "description": balance.item.description,
                "bin_code": balance.location.bin_code,
                "lot_number": balance.lot_number,
                "expiry_date": balance.expiry_date.isoformat() if balance.expiry_date else None,
                "qty_on_hand": str(balance.qty_on_hand),
                "qty_reserved": str(balance.qty_reserved),
                "available": str(balance.qty_on_hand - balance.qty_reserved),
                "days_to_expiry": days_to_expiry,
                "status": status_code,
            })
        return Response({"days": days, "results": rows})


class ReplenishmentView(APIView):
    permission_classes = (ManagerOrAdmin,)

    def get(self, request):
        today = timezone.localdate()
        pickable_stock = Q(
            inventory__location__is_active=True,
            inventory__location__is_pickable=True,
            inventory__location__kind=Location.Kind.STORAGE,
        )
        usable_stock = pickable_stock & (
            Q(inventory__expiry_date__gte=today)
            | Q(inventory__expiry_date__isnull=True, inventory__item__track_expiry=False)
        )
        expired_stock = pickable_stock & Q(inventory__expiry_date__lt=today)
        missing_expiry_stock = pickable_stock & Q(
            inventory__expiry_date__isnull=True,
            inventory__item__track_expiry=True,
        )
        items = Item.objects.filter(is_active=True, min_stock__gt=0).annotate(
            on_hand=Coalesce(
                Sum("inventory__qty_on_hand", filter=usable_stock),
                Value(Decimal("0")),
            ),
            reserved=Coalesce(
                Sum("inventory__qty_reserved", filter=usable_stock),
                Value(Decimal("0")),
            ),
            expired=Coalesce(
                Sum("inventory__qty_on_hand", filter=expired_stock),
                Value(Decimal("0")),
            ),
            missing_expiry=Coalesce(
                Sum("inventory__qty_on_hand", filter=missing_expiry_stock),
                Value(Decimal("0")),
            ),
        ).order_by("sku")
        inbound_by_item = {
            entry["item_id"]: entry
            for entry in ReceiptLine.objects.filter(
                item__is_active=True,
                receipt__source_type=Receipt.SourceType.PO,
                receipt__status__in=(
                    Receipt.Status.OPEN,
                    Receipt.Status.RECEIVING,
                    Receipt.Status.PUTAWAY,
                ),
            ).values("item_id").annotate(
                open_po_qty=Coalesce(
                    Sum(
                        F("expected_qty") - F("received_qty"),
                        filter=(
                            Q(expected_qty__gt=F("received_qty"))
                            & (Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
                        ),
                    ),
                    Value(Decimal("0")),
                ),
                pending_putaway_qty=Coalesce(
                    Sum(
                        F("received_qty") - F("putaway_qty"),
                        filter=(
                            Q(received_qty__gt=F("putaway_qty"))
                            & (
                                Q(expiry_date__gte=today)
                                | Q(expiry_date__isnull=True, item__track_expiry=False)
                            )
                        ),
                    ),
                    Value(Decimal("0")),
                ),
            )
        }

        suggestions = []
        for item in items:
            inbound = inbound_by_item.get(item.pk, {})
            available = item.on_hand - item.reserved
            open_po_qty = inbound.get("open_po_qty", Decimal("0"))
            pending_putaway_qty = inbound.get("pending_putaway_qty", Decimal("0"))
            projected_available = available + open_po_qty + pending_putaway_qty
            suggested_order_qty = max(item.min_stock - projected_available, Decimal("0"))
            if suggested_order_qty:
                status_code = "REORDER"
            elif available < item.min_stock:
                status_code = "INBOUND_COVERS"
            else:
                status_code = "HEALTHY"
            suggestions.append({
                "item_id": item.pk,
                "sku": item.sku,
                "description": item.description,
                "uom": item.uom,
                "on_hand": str(item.on_hand),
                "reserved": str(item.reserved),
                "available": str(available),
                "expired_qty": str(item.expired),
                "missing_expiry_qty": str(item.missing_expiry),
                "open_po_qty": str(open_po_qty),
                "pending_putaway_qty": str(pending_putaway_qty),
                "projected_available": str(projected_available),
                "min_stock": str(item.min_stock),
                "suggested_order_qty": str(suggested_order_qty),
                "status": status_code,
            })
        suggestions.sort(
            key=lambda row: (
                row["status"] != "REORDER",
                -Decimal(row["suggested_order_qty"]),
                row["sku"],
            )
        )
        return Response(suggestions)


class MovementHistoryView(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockLedgerSerializer
    permission_classes = (IsAuthenticated,)
    queryset = StockLedger.objects.select_related("item", "location", "user").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        sku = self.request.query_params.get("sku")
        bin_code = self.request.query_params.get("bin_code")
        transaction_type = self.request.query_params.get("transaction_type")
        if sku:
            queryset = queryset.filter(item__sku__iexact=sku)
        if bin_code:
            queryset = queryset.filter(location__bin_code__iexact=bin_code)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        return queryset


class AdjustmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdjustmentSerializer
    queryset = StockAdjustment.objects.select_related("item", "location", "requested_by", "approved_by")
    permission_classes = (ViewerReadOnly,)

    @method_decorator(transaction.atomic)
    def create(self, request):
        if request.user.role == User.Role.VIEWER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        payload = AdjustmentCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        adjustment = StockAdjustment.objects.create(
            **values,
            requested_by=request.user,
            status=StockAdjustment.Status.PENDING,
        )
        audit(request.user, "ADJUSTMENT_REQUESTED", "StockAdjustment", adjustment.pk, details={"reason": adjustment.reason, "qty_change": str(adjustment.qty_change)})
        return Response(AdjustmentSerializer(adjustment).data, status=status.HTTP_201_CREATED)

    @method_decorator(transaction.atomic)
    @action(detail=True, methods=("post",), permission_classes=(ManagerOrAdmin,))
    def approve(self, request, pk=None):
        adjustment = self.get_object()
        if adjustment.requested_by_id == request.user.pk:
            raise ValidationError("A requester cannot approve their own adjustment.")
        if adjustment.status != StockAdjustment.Status.PENDING:
            raise Conflict("Only pending adjustments can be approved.")
        adjustment.approved_by = request.user
        adjustment.status = StockAdjustment.Status.APPROVED
        try:
            ledger, _ = post_movement(
                item=adjustment.item,
                location=adjustment.location,
                qty_change=adjustment.qty_change,
                transaction_type=StockLedger.Type.ADJUST,
                user=request.user,
                reference_type="ADJUSTMENT",
                reference_id=adjustment.pk,
                lot_number=adjustment.lot_number,
                expiry_date=adjustment.expiry_date,
                notes=f"{adjustment.reason}: {adjustment.notes}",
            )
        except Conflict:
            adjustment.approved_by = None
            adjustment.status = StockAdjustment.Status.PENDING
            raise
        adjustment.status = StockAdjustment.Status.POSTED
        adjustment.posted_ledger_id = ledger.pk
        adjustment.save(update_fields=("approved_by", "status", "posted_ledger_id"))
        audit(request.user, "ADJUSTMENT_POSTED", "StockAdjustment", adjustment.pk, reference_type="LEDGER", reference_id=ledger.pk)
        return Response(AdjustmentSerializer(adjustment).data)


class CycleCountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CycleCount.objects.select_related("warehouse", "created_by").prefetch_related("lines__item", "lines__location")
    serializer_class = CycleCountSerializer
    permission_classes = (ViewerReadOnly,)

    @method_decorator(transaction.atomic)
    def create(self, request):
        if request.user.role not in {User.Role.ADMIN, User.Role.MANAGER}:
            return Response(status=status.HTTP_403_FORBIDDEN)
        payload = CycleCountCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        locations = Location.objects.filter(
            warehouse=values["warehouse"],
            id__in=values["location_ids"],
            is_active=True,
        )
        if locations.count() != len(set(values["location_ids"])):
            raise ValidationError({"location_ids": "All bins must be active and belong to the selected warehouse."})
        count = CycleCount.objects.create(warehouse=values["warehouse"], created_by=request.user)
        for inventory in Inventory.objects.filter(location__in=locations).select_related("item", "location"):
            CycleCountLine.objects.create(
                count=count,
                item=inventory.item,
                location=inventory.location,
                lot_number=inventory.lot_number,
                expiry_date=inventory.expiry_date,
                expected_qty=inventory.qty_on_hand,
            )
        audit(request.user, "CYCLE_COUNT_CREATED", "CycleCount", count.pk)
        return Response(CycleCountSerializer(count).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="count-line", permission_classes=(OperatorOrAbove,))
    @method_decorator(transaction.atomic)
    def count_line(self, request, pk=None):
        count = self.get_object()
        if count.status not in {CycleCount.Status.OPEN, CycleCount.Status.COUNTING}:
            raise Conflict("This cycle count is not open.")
        payload = CountLineRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        line = get_object_or_404(CycleCountLine, pk=values["line_id"], count=count)
        barcode = values["barcode"]
        if barcode not in {line.item.sku, line.item.barcode} or values["bin_code"] != line.location.bin_code:
            raise ValidationError("Scanned bin/item does not match the count line.")
        if (line.item.track_lot or line.lot_number) and values.get("lot_number", "") != line.lot_number:
            raise ValidationError({"lot_number": "Scanned lot does not match the count line."})
        if line.item.track_expiry and values.get("expiry_date") != line.expiry_date:
            raise ValidationError({"expiry_date": "Scanned expiry date does not match the count line."})
        Item.objects.select_for_update().get(pk=line.item_id)
        inventory = Inventory.objects.select_for_update().filter(
            item=line.item,
            location=line.location,
            lot_number=line.lot_number,
            expiry_date=line.expiry_date,
        ).first()
        line.expected_qty = inventory.qty_on_hand if inventory else Decimal("0")
        line.counted_qty = values["counted_qty"]
        line.counted_by = request.user
        line.counted_at = timezone.now()
        line.save(update_fields=("expected_qty", "counted_qty", "counted_by", "counted_at"))
        count.status = CycleCount.Status.COUNTING
        count.save(update_fields=("status",))
        audit(request.user, "CYCLE_COUNT_LINE_RECORDED", "CycleCountLine", line.pk, reference_type="CYCLE_COUNT", reference_id=count.pk)
        return Response(CycleCountSerializer(count).data)

    @method_decorator(transaction.atomic)
    @action(detail=True, methods=("post",), permission_classes=(ManagerOrAdmin,))
    def approve(self, request, pk=None):
        count = self.get_object()
        if count.status not in {CycleCount.Status.OPEN, CycleCount.Status.COUNTING}:
            raise Conflict("Only an active cycle count can be approved.")
        if CycleCountLine.objects.filter(count=count, counted_qty__isnull=True).exists():
            raise Conflict("All count lines must be counted before approval.")
        lines = CycleCountLine.objects.select_for_update().filter(count=count).select_related("item", "location")
        for line in lines:
            delta = line.counted_qty - line.expected_qty
            if delta:
                post_movement(
                    item=line.item,
                    location=line.location,
                    qty_change=delta,
                    transaction_type=StockLedger.Type.CYCLE_COUNT,
                    user=request.user,
                    reference_type="CYCLE_COUNT",
                    reference_id=count.pk,
                    lot_number=line.lot_number,
                    expiry_date=line.expiry_date,
                    notes=f"Count line {line.pk}",
                )
        count.status = CycleCount.Status.CLOSED
        count.save(update_fields=("status",))
        audit(request.user, "CYCLE_COUNT_APPROVED", "CycleCount", count.pk)
        return Response(CycleCountSerializer(count).data)


class AuditLogView(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("user").all()
    permission_classes = (ManagerOrAdmin,)

    def get_queryset(self):
        queryset = super().get_queryset()
        entity_type = self.request.query_params.get("entity_type")
        entity_id = self.request.query_params.get("entity_id")
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        if entity_id:
            queryset = queryset.filter(entity_id=entity_id)
        return queryset


class HealthView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({"status": "ok"})


class ReceiveRequestSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    barcode = serializers.CharField(max_length=128)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))
    lot_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    discrepancy_type = serializers.CharField(max_length=32, required=False, allow_blank=True)
    discrepancy_note = serializers.CharField(required=False, allow_blank=True)


class ReturnDispositionRequestSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    barcode = serializers.CharField(max_length=128)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))
    disposition = serializers.ChoiceField(choices=ReturnDisposition.Type.choices)
    destination_bin = serializers.CharField(max_length=64, required=False, allow_blank=True)
    lot_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=500)


class PutawayRequestSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    barcode = serializers.CharField(max_length=128)
    bin_code = serializers.CharField(max_length=64)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))


class PickRequestSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    bin_code = serializers.CharField(max_length=64)
    barcode = serializers.CharField(max_length=128)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))


class PackRequestSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=128)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))


class ShipRequestSerializer(serializers.Serializer):
    carrier = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tracking_number = serializers.CharField(max_length=160, required=False, allow_blank=True)


class AdjustmentCreateSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.filter(is_active=True))
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.filter(is_active=True))
    lot_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    qty_change = serializers.DecimalField(max_digits=18, decimal_places=3)
    reason = serializers.CharField(max_length=64)
    notes = serializers.CharField()

    def validate_qty_change(self, value):
        if value == 0:
            raise serializers.ValidationError("Adjustment must change stock.")
        return value


class CycleCountCreateSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True))
    location_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)


class CountLineRequestSerializer(serializers.Serializer):
    line_id = serializers.IntegerField(min_value=1)
    bin_code = serializers.CharField(max_length=64)
    barcode = serializers.CharField(max_length=128)
    counted_qty = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0"))
    lot_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)


class InventoryTransferRequestSerializer(serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True))
    barcode = serializers.CharField(max_length=128)
    source_bin = serializers.CharField(max_length=64)
    destination_bin = serializers.CharField(max_length=64)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal("0.001"))
    lot_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
