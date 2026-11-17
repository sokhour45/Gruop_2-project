import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from warehouse_api.models import Item, Location, StockLedger, Supplier, Warehouse
from warehouse_api.services import post_movement


class Command(BaseCommand):
    help = "Create the first administrator and a small set of warehouse demo data."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default=os.environ.get("WMS_ADMIN_USERNAME", "admin"))
        parser.add_argument("--admin-password", default=os.environ.get("WMS_ADMIN_PASSWORD"))
        parser.add_argument("--skip-samples", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["admin_username"]
        password = options["admin_password"]
        if not password or len(password) < 12:
            raise CommandError("Set WMS_ADMIN_PASSWORD to a unique password of at least 12 characters.")
        user_model = get_user_model()
        admin_user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"role": user_model.Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        if created:
            admin_user.set_password(password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created administrator {username}."))
        elif not admin_user.check_password(password):
            raise CommandError(f"User {username!r} already exists with a different password; no changes made.")
        if options["skip_samples"]:
            return

        warehouse, _ = Warehouse.objects.get_or_create(code="MAIN", defaults={"name": "Main Warehouse"})
        receiving, _ = Location.objects.get_or_create(
            warehouse=warehouse,
            bin_code="RCV-01",
            defaults={"kind": Location.Kind.RECEIVING, "is_pickable": False, "zone": "Receiving"},
        )
        packing, _ = Location.objects.get_or_create(
            warehouse=warehouse,
            bin_code="PACK-01",
            defaults={"kind": Location.Kind.PACKING, "is_pickable": False, "zone": "Packing"},
        )
        storage, _ = Location.objects.get_or_create(
            warehouse=warehouse,
            bin_code="A-01",
            defaults={"kind": Location.Kind.STORAGE, "is_pickable": True, "zone": "A", "sequence": 1},
        )
        supplier, _ = Supplier.objects.get_or_create(
            code="SUP-001",
            defaults={"name": "Demo Supplier", "email": "warehouse@example.invalid"},
        )
        samples = (
            ("SKU-100", "BC-100", "Demo item 100", Decimal("20"), Decimal("5")),
            ("SKU-200", "BC-200", "Demo item 200", Decimal("8"), Decimal("2")),
        )
        for sku, barcode, description, qty, min_stock in samples:
            item, _ = Item.objects.get_or_create(
                sku=sku,
                defaults={
                    "barcode": barcode,
                    "description": description,
                    "uom": "each",
                    "min_stock": min_stock,
                },
            )
            if not StockLedger.objects.filter(
                item=item,
                location=storage,
                transaction_type=StockLedger.Type.OPENING_BALANCE,
            ).exists():
                post_movement(
                    item=item,
                    location=storage,
                    qty_change=qty,
                    transaction_type=StockLedger.Type.OPENING_BALANCE,
                    user=admin_user,
                    reference_type="SEED",
                    reference_id=f"DEMO-{sku}",
                    notes="Demo opening stock",
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo warehouse ready: {warehouse.code}; bins {receiving.bin_code}, "
                f"{storage.bin_code}, {packing.bin_code}; supplier {supplier.code}."
            )
        )
