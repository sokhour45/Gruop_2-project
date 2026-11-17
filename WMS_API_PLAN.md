# Small-Warehouse WMS REST API Plan

## 1. Decisions and scope

The prompt leaves the framework and authentication fields open. This plan recommends:

| Concern | Recommendation |
| --- | --- |
| Backend | Extend the existing Python/Flask application with versioned Flask API blueprints |
| Database | PostgreSQL for the target multi-user WMS; the current application still uses SQLite |
| PostgreSQL access | Use a parameterized driver and a transaction/service boundary; `psycopg` 3 is a reasonable direct-SQL fit for the current code |
| Auth | Secure server-side session cookie for the same-origin browser/handheld UI, with CSRF protection; add OAuth/JWT only if separate mobile/native clients or external API consumers require it |
| API style | JSON REST under `/api/v1`; existing HTML routes can remain during migration |
| Stock source | Append-only `stock_ledger` for physical quantity changes; `inventory` is a transactionally maintained snapshot |

These are recommendations, not assumptions about future integrations. The project already has Flask routes, session-based login, and a SQLite data layer, but does not yet implement this API or use the PostgreSQL schema. See [PostgreSQL Schema](WMS_POSTGRES_SCHEMA.md) for target tables and ledger principles.

## 2. Roles and access policy

Enforce permissions on the server for every endpoint; hiding a button is not authorization. Resolve the authenticated user and role once per request. Deny by default.

| Capability | Admin | Manager | Operator | Viewer |
| --- | --- | --- | --- | --- |
| View inventory, items, locations, receipts, and orders | Yes | Yes | Yes | Yes |
| Maintain items, locations, suppliers, customers | Yes | Yes | No | No |
| Receive and put away | Yes | Yes | Yes | No |
| Create orders and allocate stock | Yes | Yes | Yes | No |
| Pick, pack, and ship | Yes | Yes | Yes | No |
| Request stock adjustment or count correction | Yes | Yes | Yes | No |
| Approve adjustments/count variances | Yes, not own request | Yes, not own request | No | No |
| Manage users, roles, and system settings | Yes | No | No | No |
| View audit and productivity reports | Yes | Yes | Own/assigned activity only | No |

Define separate permission keys (for example `inventory.adjust.request` and `inventory.adjust.approve`) so a user's role cannot accidentally grant self-approval. A one-person operation may need an explicit documented exception.

## 3. Endpoint outline

`{id}` denotes a database identifier. All paths below are under `/api/v1`. JSON response shapes are abbreviated in the table; examples follow. Endpoints listed as write operations require an authenticated role, schema validation, and an audit event.

### Auth and users

| Method | Path | Purpose | Role required |
| --- | --- | --- | --- |
| `POST` | `/auth/login` | Authenticate and create a session | Public |
| `POST` | `/auth/logout` | Revoke the current session | Authenticated |
| `GET` | `/auth/me` | Return current user and permissions | Authenticated |
| `GET` | `/users` | List users | Admin |
| `POST` | `/users` | Create an account and assign a role | Admin |
| `PATCH` | `/users/{id}` | Change role or active status | Admin |

### Master data

| Method | Path | Purpose | Role required |
| --- | --- | --- | --- |
| `GET` | `/items?query=&active=` | Search by SKU, barcode, or description | Authenticated |
| `POST` | `/items` | Create SKU/item | Admin, Manager |
| `GET` | `/items/{id}` | Read item | Authenticated |
| `PATCH` | `/items/{id}` | Update descriptive/reorder fields; do not set quantity | Admin, Manager |
| `DELETE` | `/items/{id}` | Soft-deactivate only if no open work; never delete history | Admin, Manager |
| `GET` | `/locations?warehouse_id=&query=` | Search bins | Authenticated |
| `POST` | `/locations` | Create a bin | Admin, Manager |
| `GET` | `/locations/{id}` | Read a bin | Authenticated |
| `PATCH` | `/locations/{id}` | Update zone, pickability, or active status | Admin, Manager |
| `DELETE` | `/locations/{id}` | Soft-deactivate only when empty and unused by open work | Admin, Manager |
| `GET` | `/suppliers?query=` | Search suppliers | Authenticated |
| `POST` | `/suppliers` | Create supplier | Admin, Manager |
| `GET` | `/suppliers/{id}` | Read supplier | Authenticated |
| `PATCH` | `/suppliers/{id}` | Update or deactivate supplier | Admin, Manager |
| `GET` | `/customers?query=` | Search customers | Authenticated |
| `POST` | `/customers` | Create customer | Admin, Manager |
| `GET` | `/customers/{id}` | Read customer | Authenticated |
| `PATCH` | `/customers/{id}` | Update or deactivate customer | Admin, Manager |

### Inbound and putaway

| Method | Path | Purpose | Role required |
| --- | --- | --- | --- |
| `POST` | `/receipts` | Create receipt from PO/reference and expected lines | Admin, Manager, Operator |
| `GET` | `/receipts?status=&po_number=` | Search receipts | Authenticated |
| `GET` | `/receipts/{id}` | Read receipt and lines | Authenticated |
| `POST` | `/receipts/{id}/lines/{line_id}/receive` | Confirm scanned item and received quantity; record discrepancy | Admin, Manager, Operator |
| `GET` | `/receipts/{id}/putaway-suggestions?line_id=` | Suggest an active destination bin | Admin, Manager, Operator |
| `POST` | `/receipts/{id}/putaways` | Confirm scan and move quantity from receiving/staging to destination | Admin, Manager, Operator |
| `POST` | `/receipts/{id}/close` | Close a resolved receipt | Admin, Manager, Operator |

### Inventory and counts

| Method | Path | Purpose | Role required |
| --- | --- | --- | --- |
| `GET` | `/inventory?sku=&barcode=&bin_code=` | Read on-hand and reserved quantities by bin | Authenticated |
| `GET` | `/inventory/movements?sku=&bin_code=&from=&to=&limit=` | Search stock ledger | Authenticated |
| `POST` | `/inventory/transfer/` | Move available stock between scanned storage bins; post paired ledger entries | Admin, Manager, Operator |
| `POST` | `/inventory/adjustments` | Request a reason-coded adjustment | Admin, Manager, Operator |
| `POST` | `/inventory/adjustments/{id}/approve` | Approve/reject; approval may post the adjustment | Admin or Manager, not requester |
| `POST` | `/orders/{id}/reservations` | Reserve available quantity for order lines | Admin, Manager, Operator |
| `DELETE` | `/orders/{id}/reservations/{allocation_id}` | Release an allocation | Admin, Manager, Operator |
| `POST` | `/cycle-counts` | Create a count task for bins/items | Admin, Manager |
| `GET` | `/cycle-counts?status=` | List count tasks | Authenticated |
| `GET` | `/cycle-counts/{id}` | Read count task and lines | Authenticated |
| `POST` | `/cycle-counts/{id}/lines/{line_id}/count` | Submit a scanned physical count | Admin, Manager, Operator |
| `POST` | `/cycle-counts/{id}/lines/{line_id}/recount` | Request a recount | Admin, Manager |
| `POST` | `/cycle-counts/{id}/lines/{line_id}/approve` | Approve variance and post correction | Admin or Manager, not counter/requester |

Reservations change available-to-promise, not physical on-hand. They must be recorded in allocation/reservation data and audited transactionally, but do not create a physical stock-ledger movement. If a business requires reservations represented in a separate commitment ledger, model that separately from `stock_ledger`.

### Outbound

| Method | Path | Purpose | Role required |
| --- | --- | --- | --- |
| `POST` | `/orders` | Create a customer order with lines | Admin, Manager, Operator |
| `POST` | `/orders/import` | Validate and stage CSV/API order data; deduplicate external IDs | Admin, Manager, Operator |
| `GET` | `/orders?status=&priority=` | Search orders | Authenticated |
| `GET` | `/orders/{id}` | Read order and current work status | Authenticated |
| `POST` | `/orders/{id}/pick-tasks` | Allocate stock and generate a simple pick task | Admin, Manager, Operator |
| `POST` | `/pick-tasks/{id}/lines/{line_id}/confirm` | Confirm scanned bin, item, and quantity | Admin, Manager, Operator |
| `POST` | `/orders/{id}/pack/verify` | Verify scanned packed item/quantity | Admin, Manager, Operator |
| `POST` | `/orders/{id}/ship` | Record dispatch/tracking and post shipment movement | Admin, Manager, Operator |

### Reports and audit

| Method | Path | Purpose | Role required |
| --- | --- | --- | --- |
| `GET` | `/reports/stock-on-hand?warehouse_id=&sku=&bin_code=` | Stock totals and bin-level balances | Admin, Manager, Operator, Viewer |
| `GET` | `/reports/movements?from=&to=&sku=&user_id=` | Filtered stock movement history | Admin, Manager; Operator limited to authorized scope |
| `GET` | `/reports/low-stock` | Active items at/below minimum stock | Admin, Manager, Operator, Viewer |
| `GET` | `/reports/expiry?days=30` | Expired, expiring-soon, and missing-expiry lots for tracked SKUs | Admin, Manager |
| `GET` | `/reports/replenishment` | Suggested order quantities after reservations and inbound purchase receipts | Admin, Manager |
| `GET` | `/reports/productivity?from=&to=&user_id=` | Completed picks/lines per user and time range | Admin, Manager; Operator own/assigned scope |
| `GET` | `/audit-logs?entity_type=&entity_id=&from=&to=` | Search audit events | Admin, Manager |

Use pagination (`limit`, `cursor` or `page`) for collection/report endpoints; enforce a conservative maximum limit such as 100. Return stable sort order, preferably timestamp plus primary key.

## 4. Request and response examples

### 4.1 Login (session-based)

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "receiver1",
  "password": "example-password"
}
```

```http
HTTP/1.1 200 OK
Set-Cookie: session=...; Secure; HttpOnly; SameSite=Lax
Content-Type: application/json

{
  "data": {
    "user": { "id": 18, "username": "receiver1", "role": "Operator" },
    "permissions": ["receipt.receive", "inventory.lookup", "putaway.confirm"]
  }
}
```

For browser sessions, protect state-changing requests with CSRF tokens and rotate the session on login. Do not return or log password hashes. For a separate native/mobile client, select a token flow deliberately rather than simply placing a long-lived JWT in local storage.

### 4.2 Scan and receive a PO line

```http
POST /api/v1/receipts/320/lines/991/receive
Idempotency-Key: 6ea5f08b-d14c-4c94-9726-f13f299a8d87
Content-Type: application/json

{
  "barcode": "0123456789012",
  "sku": "PART-100",
  "quantity": 12,
  "lot_number": "LOT-24A",
  "expiry_date": "2027-12-31",
  "discrepancy": {
    "type": "OVER",
    "note": "Two extra units in sealed carton"
  }
}
```

```json
{
  "data": {
    "receipt_id": 320,
    "receipt_line_id": 991,
    "received_quantity": 12,
    "expected_quantity": 10,
    "status": "RECEIVED",
    "ledger_entry_ids": [74001],
    "suggested_bin": { "id": 7, "bin_code": "A1-03" }
  },
  "meta": { "request_id": "req_..." }
}
```

The server verifies that the line belongs to the receipt, the scanned barcode and SKU identify the same active item, and the overage policy permits receipt or routes it to approval. The ledger, receipt-line update, audit event, and idempotency result commit together.

### 4.3 Inventory lookup

```http
GET /api/v1/inventory?sku=PART-100
```

```json
{
  "data": {
    "item": { "id": 44, "sku": "PART-100", "description": "Replacement part", "uom": "each" },
    "on_hand": 20,
    "reserved": 3,
    "available": 17,
    "locations": [
      { "bin_code": "A1-03", "on_hand": 12, "reserved": 1, "available": 11 },
      { "bin_code": "PICK-01", "on_hand": 8, "reserved": 2, "available": 6 }
    ]
  }
}
```

On-hand is physical quantity. Available is calculated as on-hand less active allocations; label both values to avoid treating reserved stock as free stock.

### 4.4 Adjustment request and approval

```http
POST /api/v1/inventory/adjustments
Idempotency-Key: 96c2d58a-6177-4e31-b657-5a303de1b221
Content-Type: application/json

{
  "item_id": 44,
  "bin_code": "A1-03",
  "quantity_change": -1,
  "reason_code": "DAMAGED",
  "notes": "Crushed during handling"
}
```

```json
{
  "data": {
    "adjustment_id": 205,
    "status": "PENDING_APPROVAL",
    "requested_by": 18,
    "approval_required": true
  }
}
```

Approval posts a ledger movement only after manager validation. On successful posting, return the new `ledger_entry_id` and resulting on-hand quantity. The requester cannot approve their own adjustment.

### 4.5 Pick confirmation and mismatch response

```http
POST /api/v1/pick-tasks/83/lines/442/confirm
Idempotency-Key: 1dc43519-2dfb-4fea-925f-b2f6d63c8262
Content-Type: application/json

{
  "scanned_bin": "A1-03",
  "scanned_barcode": "0123456789012",
  "sku": "PART-100",
  "quantity": 2
}
```

If the item is wrong, do not update picked quantity or stock:

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "error": {
    "code": "SCAN_ITEM_MISMATCH",
    "message": "Scanned item does not match this pick line.",
    "details": { "expected_sku": "PART-100" }
  },
  "meta": { "request_id": "req_..." }
}
```

### 4.6 Shipment confirmation

```http
POST /api/v1/orders/560/ship
Idempotency-Key: 74669d62-52f6-4211-8c4e-b2cdef0e23a6
Content-Type: application/json

{
  "carrier": "Example Carrier",
  "tracking_number": "TRACK-12345"
}
```

Return the shipped status, timestamp, tracking reference, and ledger IDs. The transaction must fail if the order is not pack-verified, a shipment was already posted, or allocated stock cannot be consumed.

## 5. Validation, transactions, and errors

### Validation rules

- **Identity:** SKU is unique; barcode is unique when present. If both barcode and SKU are supplied, they must resolve to the same active item.
- **Locations:** Bin code is unique within its warehouse. Bin is active and eligible for the operation; source and destination must differ for a transfer.
- **Receipt:** Receipt line belongs to the receipt; quantity is positive; received quantity and discrepancy are recorded; lot/expiry/serial data meet the item's tracking configuration.
- **Order/pick:** Order and line are in a valid state; requested quantity does not exceed remaining quantity; scanned bin and item match the active task; reservation and availability are sufficient. Expired stock cannot be allocated or picked; expiry-tracked SKUs allocate unexpired lots FEFO.
- **Inventory:** Physical result cannot be negative unless a specific manager-controlled configuration allows it. Default is deny. Do not allow arbitrary quantity writes through item CRUD.
- **Adjustments:** Require a reason code and explanatory note; apply configurable approval thresholds; prevent self-approval.
- **Cycle counts:** Count line belongs to the active task and scanned bin/item; variance is reviewed and approved before posting.
- **Idempotency:** Accept an `Idempotency-Key` on retryable writes. Scope the key to user/client and operation; store request hash and response with a unique constraint. Same key/same payload replays the original response; same key/different payload returns conflict.
- **Audit:** Each successful write records actor, UTC timestamp, action, entity/reference document, and request ID in the same transaction. Denied authorization attempts should be logged as security events, not successful writes.

### Error contract

Use a consistent shape:

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Not enough available stock in bin A1-03.",
    "details": { "available": 1, "requested": 2 }
  },
  "meta": { "request_id": "req_..." }
}
```

| HTTP | Example error code | Meaning |
| --- | --- | --- |
| `400` | `VALIDATION_ERROR`, `INVALID_QUANTITY` | Malformed request or invalid field |
| `401` | `UNAUTHENTICATED` | Missing/expired authentication |
| `403` | `FORBIDDEN` | Authenticated user lacks permission |
| `404` | `ITEM_NOT_FOUND`, `BIN_NOT_FOUND`, `ORDER_NOT_FOUND` | Resource is not visible or does not exist |
| `409` | `SKU_CONFLICT`, `SCAN_ITEM_MISMATCH`, `INSUFFICIENT_STOCK`, `INVALID_STATE`, `IDEMPOTENCY_CONFLICT` | Business rule, duplicate, or concurrency conflict |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | Request is not JSON where required |
| `429` | `RATE_LIMITED` | Request throttled |
| `500` | `INTERNAL_ERROR` | Unexpected failure; return request ID, not SQL or stack trace |
| `503` | `DATABASE_UNAVAILABLE` | Temporary dependency outage; safe retry only with idempotency key |

Do not return success-shaped fallbacks. Validation and conflict responses should identify the field or scan mismatch without exposing secrets or unrelated customer data.

## 6. Transaction and ledger requirements

Every physical stock change must be posted by a shared inventory service (or database routine) that:

1. Authenticates/authorizes the actor and validates item, bin, document state, scan identity, and tracking data.
2. Begins a PostgreSQL transaction and obtains row locks or performs conditional atomic updates for affected inventory dimensions.
3. Checks available quantity and prevents negative stock by default.
4. Writes receipt/order/count/adjustment state changes and `audit_logs`.
5. Inserts the matching append-only `stock_ledger` movement(s) and updates `inventory` snapshots atomically.
6. Stores the idempotency result before commit.

Receiving and shipment are positive/negative stock movements respectively. A transfer writes equal-and-opposite source/destination ledger rows. Putaway and a pick into staging are transfers. Packing itself is not a physical movement unless location changes. Reservation changes commitments, not physical stock; it updates allocation data and `qty_reserved` atomically, and is audited without a physical stock ledger row.

Do not hold database locks while waiting for a user scan or carrier response. Confirm each small operation in its own short transaction. On deadlock or serialization conflict, retry the complete idempotent operation.

## 7. Suggested project structure

Fit the existing Flask project incrementally; preserve the current `warehouse/web_app.py` and `warehouse/db.py` behavior while introducing API/service boundaries.

```text
warehouse/
  api/
    __init__.py
    auth.py
    errors.py
    permissions.py
    v1/
      __init__.py
      auth.py
      items.py
      locations.py
      suppliers.py
      customers.py
      receipts.py
      inventory.py
      cycle_counts.py
      orders.py
      reports.py
      audit.py
      schemas.py
  services/
    auth_service.py
    master_data_service.py
    receiving_service.py
    inventory_service.py
    reservation_service.py
    cycle_count_service.py
    fulfillment_service.py
    reporting_service.py
    audit_service.py
  repositories/
    items.py
    locations.py
    inventory.py
    receipts.py
    orders.py
    users.py
  db/
    connection.py
    migrations/
  models/
    ...
  tests/
    api/
    services/
    integration/
```

Blueprint handlers should stay thin: parse/validate request, call a service, map typed business errors to HTTP, return JSON. Services own transaction boundaries and authorization-sensitive business rules. Repositories own parameterized SQL only. Never duplicate stock-posting logic across routes.

## 8. Implementation plan

| Phase | Work | Exit criteria |
| --- | --- | --- |
| 1. API foundation | PostgreSQL connection/configuration, migrations, `/api/v1`, session auth, permission decorator/service, common error/JSON response contract, request ID | Auth and role tests pass; secrets are deployment-configured; API health and DB readiness are observable |
| 2. Master data and inventory reads | Item/location/supplier/customer CRUD, soft deactivation, stock lookup/report, pagination | Barcode/SKU uniqueness and role denial tested; no endpoint can edit on-hand directly |
| 3. Ledger-backed inbound and inventory | Shared posting service, idempotency table/middleware, receive, putaway, transfer, adjustment request/approval, cycle count | Each committed physical change has ledger + snapshot + audit; transaction rollback and retries tested |
| 4. Outbound | Order create/import, reservation, pick tasks, scan confirmation, pack verification, ship | Concurrency tests prevent over-allocation/negative stock; idempotent duplicate scans do not double-post |
| 5. Reports and pilot hardening | Movement, low-stock, audit, productivity reports; device tests, monitoring, restore test, operator training | Target handheld/scanner workflows verified; restore and reconciliation runbooks accepted |

## 9. Minimum test plan

- Unit tests for permission mapping, quantity/state validation, and barcode/SKU matching.
- API tests for each role's allowed and denied operations, including direct route calls.
- PostgreSQL integration tests for receipt, transfer, adjustment, and shipment transaction rollback.
- Concurrency tests for two simultaneous allocations/picks competing for the last units.
- Idempotency tests for repeated scan/ship request, plus same-key/different-payload conflict.
- Audit/ledger tests proving every successful physical posting has matching reference and actor; mutation/deletion of posted ledger rows is rejected.
- Mobile-sized browser/manual device tests for scan focus, mismatch feedback, Wi-Fi loss, and safe retry.
