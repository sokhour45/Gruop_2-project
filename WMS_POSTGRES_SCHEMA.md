# PostgreSQL Schema for a Small-Warehouse WMS

This schema is a starting point for the project’s planned PostgreSQL-backed WMS. It covers master data, receipts, orders, stock snapshots, an append-only ledger, optional lot/serial tracking, roles, counts, adjustments, and audit events. It assumes PostgreSQL 15+ for `UNIQUE NULLS NOT DISTINCT`.

The current project uses SQLite and does not yet have these tables. Treat this as a target schema, not a drop-in migration. Test any migration against a backup and reconcile opening balances before switching production reads.

## DDL

```sql
CREATE TABLE warehouses (
    warehouse_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roles (
    role_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name     TEXT NOT NULL UNIQUE,
    description   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE role_permissions (
    role_id       BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,
    permission_key TEXT NOT NULL,
    PRIMARY KEY (role_id, permission_key)
);

CREATE TABLE users (
    user_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id       BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE suppliers (
    supplier_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_code TEXT UNIQUE,
    name          TEXT NOT NULL,
    email         TEXT,
    phone         TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customers (
    customer_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_code TEXT UNIQUE,
    name          TEXT NOT NULL,
    email         TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE items (
    item_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku           TEXT NOT NULL UNIQUE,
    description   TEXT NOT NULL,
    uom           TEXT NOT NULL,
    barcode       TEXT UNIQUE,
    min_stock     NUMERIC(18, 6) NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    track_lot     BOOLEAN NOT NULL DEFAULT FALSE,
    track_serial  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(sku)) > 0),
    CHECK (length(trim(uom)) > 0)
);

CREATE TABLE locations (
    location_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id  BIGINT NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    bin_code      TEXT NOT NULL,
    zone          TEXT,
    is_pickable   BOOLEAN NOT NULL DEFAULT TRUE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (warehouse_id, bin_code),
    UNIQUE (location_id, warehouse_id),
    CHECK (length(trim(bin_code)) > 0)
);

CREATE TABLE receipts (
    receipt_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id  BIGINT NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    supplier_id   BIGINT REFERENCES suppliers(supplier_id) ON DELETE RESTRICT,
    po_number     TEXT,
    status        TEXT NOT NULL DEFAULT 'DRAFT'
                  CHECK (status IN ('DRAFT', 'OPEN', 'RECEIVING', 'RECEIVED',
                                    'CLOSED', 'CANCELLED')),
    received_by   BIGINT REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_at   TIMESTAMPTZ,
    notes         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE receipt_lines (
    receipt_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    receipt_id      BIGINT NOT NULL REFERENCES receipts(receipt_id) ON DELETE RESTRICT,
    item_id         BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    expected_qty    NUMERIC(18, 6) NOT NULL CHECK (expected_qty >= 0),
    received_qty    NUMERIC(18, 6) NOT NULL DEFAULT 0 CHECK (received_qty >= 0),
    suggested_bin   BIGINT REFERENCES locations(location_id) ON DELETE RESTRICT,
    actual_bin      BIGINT REFERENCES locations(location_id) ON DELETE RESTRICT,
    discrepancy_note TEXT NOT NULL DEFAULT '',
    CHECK (actual_bin IS NULL OR received_qty > 0)
);

CREATE TABLE customer_orders (
    order_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id   BIGINT NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    customer_id    BIGINT REFERENCES customers(customer_id) ON DELETE RESTRICT,
    customer_ref   TEXT,
    status         TEXT NOT NULL DEFAULT 'DRAFT'
                   CHECK (status IN ('DRAFT', 'OPEN', 'ALLOCATED', 'PICKING',
                                     'PICKED', 'PACKED', 'SHIPPED', 'CANCELLED')),
    priority       SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    shipped_at     TIMESTAMPTZ,
    created_by     BIGINT REFERENCES users(user_id) ON DELETE RESTRICT,
    UNIQUE (warehouse_id, customer_ref)
);

CREATE TABLE order_lines (
    order_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES customer_orders(order_id) ON DELETE RESTRICT,
    item_id       BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    qty_ordered   NUMERIC(18, 6) NOT NULL CHECK (qty_ordered > 0),
    qty_picked    NUMERIC(18, 6) NOT NULL DEFAULT 0 CHECK (qty_picked >= 0),
    bin_id        BIGINT REFERENCES locations(location_id) ON DELETE RESTRICT,
    CHECK (qty_picked <= qty_ordered)
);

CREATE TABLE inventory (
    inventory_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id       BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    location_id   BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE RESTRICT,
    lot_number    TEXT,
    expiry_date   DATE,
    qty_on_hand   NUMERIC(18, 6) NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
    qty_reserved  NUMERIC(18, 6) NOT NULL DEFAULT 0 CHECK (qty_reserved >= 0),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expiry_date IS NULL OR lot_number IS NOT NULL),
    CHECK (qty_reserved <= qty_on_hand),
    UNIQUE NULLS NOT DISTINCT (item_id, location_id, lot_number, expiry_date)
);

CREATE TABLE serial_numbers (
    serial_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id         BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    serial_number   TEXT NOT NULL,
    lot_number      TEXT,
    expiry_date     DATE,
    current_location_id BIGINT REFERENCES locations(location_id) ON DELETE RESTRICT,
    status          TEXT NOT NULL DEFAULT 'AVAILABLE'
                    CHECK (status IN ('AVAILABLE', 'RESERVED', 'IN_TRANSIT',
                                      'SHIPPED', 'DAMAGED', 'UNKNOWN')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (item_id, serial_number),
    UNIQUE (item_id, serial_id),
    CHECK (expiry_date IS NULL OR lot_number IS NOT NULL)
);

CREATE TABLE stock_ledger (
    ledger_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    item_id         BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    location_id     BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE RESTRICT,
    lot_number      TEXT,
    expiry_date     DATE,
    serial_id       BIGINT,
    transaction_type TEXT NOT NULL
                    CHECK (transaction_type IN (
                        'OPENING_BALANCE', 'RECEIPT', 'PUTAWAY', 'PICK',
                        'PACK', 'SHIP', 'ADJUST', 'TRANSFER', 'CYCLE_COUNT'
                    )),
    qty_change      NUMERIC(18, 6) NOT NULL CHECK (qty_change <> 0),
    reference_doc_type TEXT,
    reference_doc_id BIGINT,
    user_id         BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    notes           TEXT NOT NULL DEFAULT '',
    CHECK (expiry_date IS NULL OR lot_number IS NOT NULL),
    CHECK ((reference_doc_type IS NULL) = (reference_doc_id IS NULL)),
    FOREIGN KEY (item_id, serial_id)
        REFERENCES serial_numbers(item_id, serial_id) ON DELETE RESTRICT
);

CREATE TABLE order_allocations (
    allocation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_line_id BIGINT NOT NULL REFERENCES order_lines(order_line_id) ON DELETE RESTRICT,
    inventory_id  BIGINT NOT NULL REFERENCES inventory(inventory_id) ON DELETE RESTRICT,
    qty_reserved  NUMERIC(18, 6) NOT NULL CHECK (qty_reserved > 0),
    status        TEXT NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE', 'RELEASED', 'CONSUMED')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (order_line_id, inventory_id)
);

CREATE TABLE stock_adjustments (
    adjustment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'POSTED')),
    reason        TEXT NOT NULL,
    requested_by  BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    approved_by   BIGINT REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at    TIMESTAMPTZ,
    posted_at     TIMESTAMPTZ,
    CHECK (approved_by IS NULL OR approved_by <> requested_by)
);

CREATE TABLE stock_adjustment_lines (
    adjustment_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    adjustment_id BIGINT NOT NULL REFERENCES stock_adjustments(adjustment_id) ON DELETE RESTRICT,
    item_id       BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    location_id   BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE RESTRICT,
    lot_number    TEXT,
    expiry_date   DATE,
    qty_change    NUMERIC(18, 6) NOT NULL CHECK (qty_change <> 0),
    notes         TEXT NOT NULL DEFAULT '',
    CHECK (expiry_date IS NULL OR lot_number IS NOT NULL)
);

CREATE TABLE cycle_counts (
    cycle_count_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id  BIGINT NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE RESTRICT,
    status        TEXT NOT NULL DEFAULT 'OPEN'
                  CHECK (status IN ('OPEN', 'COUNTING', 'REVIEW', 'CLOSED', 'CANCELLED')),
    blind_count   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by    BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at     TIMESTAMPTZ
);

CREATE TABLE cycle_count_lines (
    cycle_count_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cycle_count_id BIGINT NOT NULL REFERENCES cycle_counts(cycle_count_id) ON DELETE RESTRICT,
    item_id       BIGINT NOT NULL REFERENCES items(item_id) ON DELETE RESTRICT,
    location_id   BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE RESTRICT,
    lot_number    TEXT,
    expiry_date   DATE,
    expected_qty  NUMERIC(18, 6) NOT NULL CHECK (expected_qty >= 0),
    counted_qty   NUMERIC(18, 6) CHECK (counted_qty >= 0),
    counted_by    BIGINT REFERENCES users(user_id) ON DELETE RESTRICT,
    counted_at    TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'OPEN'
                  CHECK (status IN ('OPEN', 'COUNTED', 'RECOUNT', 'APPROVED', 'POSTED')),
    UNIQUE NULLS NOT DISTINCT
        (cycle_count_id, item_id, location_id, lot_number, expiry_date),
    CHECK (expiry_date IS NULL OR lot_number IS NOT NULL)
);

CREATE TABLE audit_logs (
    audit_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id       BIGINT REFERENCES users(user_id) ON DELETE RESTRICT,
    action        TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    before_data   JSONB,
    after_data    JSONB,
    request_id    TEXT,
    notes         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX locations_warehouse_zone_idx
    ON locations (warehouse_id, zone) WHERE is_active;
CREATE INDEX items_active_sku_idx ON items (sku) WHERE is_active;
CREATE INDEX inventory_item_location_idx ON inventory (item_id, location_id);
CREATE INDEX inventory_location_item_idx ON inventory (location_id, item_id);
CREATE INDEX inventory_lot_expiry_idx ON inventory (expiry_date)
    WHERE expiry_date IS NOT NULL;
CREATE INDEX serials_location_status_idx
    ON serial_numbers (current_location_id, status);
CREATE INDEX receipts_open_idx ON receipts (warehouse_id, created_at)
    WHERE status IN ('OPEN', 'RECEIVING');
CREATE INDEX receipt_lines_receipt_idx ON receipt_lines (receipt_id);
CREATE INDEX orders_open_idx ON customer_orders (warehouse_id, priority, created_at)
    WHERE status IN ('OPEN', 'ALLOCATED', 'PICKING', 'PICKED', 'PACKED');
CREATE INDEX order_lines_order_idx ON order_lines (order_id);
CREATE INDEX ledger_item_time_idx ON stock_ledger (item_id, occurred_at DESC, ledger_id DESC);
CREATE INDEX ledger_location_time_idx ON stock_ledger (location_id, occurred_at DESC, ledger_id DESC);
CREATE INDEX ledger_reference_idx
    ON stock_ledger (reference_doc_type, reference_doc_id)
    WHERE reference_doc_id IS NOT NULL;
CREATE INDEX ledger_serial_idx ON stock_ledger (serial_id)
    WHERE serial_id IS NOT NULL;
CREATE INDEX allocations_active_inventory_idx ON order_allocations (inventory_id)
    WHERE status = 'ACTIVE';
CREATE INDEX adjustments_pending_idx ON stock_adjustments (created_at)
    WHERE status = 'PENDING';
CREATE INDEX cycle_counts_open_idx ON cycle_counts (warehouse_id, created_at)
    WHERE status IN ('OPEN', 'COUNTING', 'REVIEW');
CREATE INDEX audit_entity_time_idx ON audit_logs (entity_type, entity_id, occurred_at DESC);
```

### Prevent ledger mutation

```sql
CREATE FUNCTION reject_stock_ledger_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'stock_ledger is append-only; post a reversal or correction';
END;
$$;

CREATE TRIGGER stock_ledger_no_update
BEFORE UPDATE OR DELETE ON stock_ledger
FOR EACH ROW EXECUTE FUNCTION reject_stock_ledger_mutation();

CREATE TRIGGER audit_logs_no_update
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION reject_stock_ledger_mutation();
```

The trigger is defense in depth, not a complete security boundary. The runtime application role must not own these tables and must not have direct `INSERT`, `UPDATE`, or `DELETE` access to `stock_ledger` or direct `UPDATE` access to `inventory`. Grant it `EXECUTE` only on reviewed posting/reservation routines. Keep a separate, restricted migration/owner role.

## Design notes

### Source of truth and reconciliation

- **`stock_ledger` is the authoritative history of physical stock changes.** Rows are append-only. A mistake is corrected by a compensating movement with a reason and a reference to the original document/movement; never update or delete a posted row.
- **`inventory` is a performance snapshot**, not an independent editable source. Its unique key identifies item, bin, lot, and expiry dimensions. Update it only in the same database transaction that inserts the corresponding ledger entry.
- `stock_ledger.reference_doc_type` and `reference_doc_id` form a polymorphic reference (for example, `RECEIPT` + `receipt_id`). A normal foreign key cannot target several document tables. Validate these references in the posting service or introduce a shared document table if database-enforced document references are required.
- Reconcile by grouping ledger deltas on `item_id`, `location_id`, `lot_number`, and `expiry_date`, then comparing those sums with `inventory.qty_on_hand`. For serial-tracked items, also compare the ledger's current state with `serial_numbers`. Investigate and correct discrepancies with an approved adjustment; do not overwrite the snapshot to make the report match.
- Seed migrated stock as explicit `OPENING_BALANCE` ledger entries tied to an opening-balance reference. Preserve legacy history as legacy/imported data rather than implying it had guarantees that it did not.

### Posting every movement

DDL cannot by itself guarantee that every application code path updates both tables. Use one database posting routine for each stock-changing operation and do not let routes or users write the snapshot directly. In one transaction, the routine must:

1. Validate the item, bin, tracking requirements, transaction type, and authorized actor.
2. Lock or atomically upsert the relevant `inventory` dimension; reject insufficient quantity or a negative resulting balance.
3. Apply serial-registry and reservation changes where applicable.
4. Insert the matching `stock_ledger` row (or rows for a transfer).
5. Commit both ledger and snapshot changes together; any failure rolls back the entire operation.

For transfers, write two ledger rows in that transaction: a negative delta at the source and equal positive delta at the destination, with a shared transfer reference. A move into or out of a staging/packing bin is also a transfer. `PACK` is a workflow event unless it physically changes location; `SHIP` is the physical stock decrement. `PICK` only posts stock movements if picking moves goods from a pick bin to a staging/packing bin. Use idempotency keys or unique document-line posting references so a retried receipt, pick, or shipment cannot post twice.

### Optional lot and serial tracking

- For untracked items, `lot_number`, `expiry_date`, and `serial_id` remain null.
- For `track_lot` items, the posting routine requires a lot number and preserves its expiry consistently across receipt, putaway, count, adjustment, and shipment. The denormalized lot/expiry columns make the balance key straightforward; validate that a given item's lot has one consistent expiry at posting time.
- For `track_serial` items, record one serial per ledger unit movement (`qty_change` is `+1` or `-1`) and use `serial_numbers` to enforce item/serial uniqueness and show current status/location. The registry is a projection maintained atomically with the ledger. Transfers must update the serial location and write both ledger legs in the same transaction.
- If an item requires both lot and serial tracking, require both on each applicable posting. Use application/database routines to enforce cross-table tracking rules; simple row-level `CHECK` constraints cannot inspect `items.track_lot` or `items.track_serial`.

### Concurrency and reserved quantity

- A read-then-write sequence without locking can oversell stock. Reserve stock in a transaction that locks the relevant inventory rows (`SELECT ... FOR UPDATE`) or uses a conditional atomic update, checks `qty_on_hand - qty_reserved`, and creates the `order_allocations` row in the same transaction.
- `qty_reserved` is a projection of active allocations, not physical stock and not a stock-ledger movement. Maintain it atomically with allocation/release/consume operations and periodically reconcile it to `order_allocations`.
- Picking should consume/release the reservation according to the agreed workflow. Shipping decreases physical on-hand and consumes the order allocation; reservation alone must never decrease physical on-hand.
- Use a consistent lock order across allocation, transfer, receipt, and shipment routines to reduce deadlocks. On a serialization/deadlock retry, retry the whole idempotent transaction, not only its final SQL statement.
- `READ COMMITTED` plus explicit row locks/conditional updates is usually sufficient for this small operation. Test concurrent picks, receipts, and adjustments against the expected peak activity before launch.

### Other implementation decisions

- `qty_change` is signed: positive adds to a location; negative removes from it. All quantities use the item's base unit. Use decimal quantities because some units may be fractional; use integer-only validation for indivisible items.
- Roles and permission keys are stored separately. Seed the supported permission keys and role grants as controlled configuration; enforce them on every application/API request and deny by default.
- Audit events describe user and administrative actions; stock ledger rows describe physical quantity changes. Both should be append-only and attributed to a user or explicit service account.
- The polymorphic `reference_doc_id` is intentionally not a foreign key. If stronger referential integrity is required, create a shared `documents` table referenced by receipts, orders, adjustments, and counts.
- Do not delete referenced items, locations, users, or documents. Deactivate them and preserve the historical links.
