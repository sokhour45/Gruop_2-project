# Lightweight Warehouse Management System (WMS) Design

## 1. Purpose and operating assumptions

This design extends the project's existing small-warehouse inventory application without turning it into a large distribution-center system. It prioritizes reliable stock records, barcode-first work, short training time, and straightforward CSV/API integration.

The prompt leaves the business-context fields open. For a useful baseline, this document assumes:

| Context | Planning assumption |
| --- | --- |
| Warehouse type | Small general-goods or e-commerce stockroom |
| Assortment | About 300 active SKUs |
| Throughput | About 50 orders per day |
| Staff | 3–6 users across receiving, picking, and management |
| Existing systems | No integration is assumed; import/export CSV first |
| Constraints | Low-cost hardware, small implementation team, reliable local Wi-Fi not guaranteed |

These are sizing assumptions, not requirements. Confirm the actual product types, order source, traceability obligations, internet conditions, and shipping-carrier needs before committing to lot/serial tracking or integrations.

### Fit with the current project

The current application provides a Flask web UI, SQLite persistence, product master data, simple stock-in/stock-out, transaction history, CSV exports, login, and admin/manager/employee roles. Its current quantity is stored on the product record; stock changes are recorded in a `transactions` table. It does not yet provide purchase orders, sales orders, multiple-bin stock, barcode scanning flows, immutable-ledger enforcement, audit logs, approvals, or shipping.

Treat this design as the next product direction, not a claim that those capabilities already exist. Preserve the current straightforward workflows while migrating toward a ledger-backed, bin-aware model.

## 2. Scope: MVP and later phases

### MVP

1. **Master data:** SKUs, units, reorder levels, suppliers/customers, active warehouse bins, users, and roles.
2. **Inbound:** Simple expected-receipt entry (manual or CSV), barcode-assisted receipt, discrepancy notes, and directed putaway to a bin.
3. **Inventory:** Current quantity by SKU and bin derived from an append-only stock ledger; receiving, picking, transfers, adjustments, and cycle counts all create ledger entries.
4. **Outbound:** CSV/manual order intake, allocation checks, a short pick list, scan-to-confirm at pick and pack, and a shipped status. Initially print a packing slip or carrier label supplied by an existing carrier portal.
5. **Reports:** Stock on hand by bin, low-stock list, searchable movement history, open work, and basic units-per-hour productivity.
6. **Access and accountability:** Role checks on the server, actor and timestamp on all operational events, audit trail for master-data changes, and manager approval for configured adjustments.
7. **Operations:** CSV import/export, database backup/restore procedure, responsive screens, and usable error messages.

### Later phases

- Direct order-source and carrier APIs after CSV formats and business rules are proven.
- Lot/batch, expiry/FEFO, serial-number, or recall workflows only where products require them.
- Supplier purchase-order lifecycle, customer returns, replenishment suggestions, and configurable approval thresholds.
- Offline-capable handheld workflow only if a site survey proves Wi-Fi gaps materially disrupt work. Queueing offline stock mutations safely is non-trivial; do not imply that a normal web form is offline-safe.
- Multiple warehouses, advanced forecasting, wave planning, task interleaving, conveyor control, and robotics are out of scope unless the business grows enough to justify a separate design.

## 3. Module breakdown

| Module | MVP capabilities | Primary users |
| --- | --- | --- |
| Item and partner master | SKU/barcode, description, unit, active flag, reorder level, supplier/customer contacts | Admin, manager |
| Warehouse layout | Warehouse and uniquely labeled bins; bin type and active status | Admin, manager |
| Receiving | Expected receipt, scan SKU, enter quantity, record over/short/damage, assign putaway bin | Receiver |
| Putaway | Show suggested destination, scan/confirm source and destination, post movement | Receiver |
| Inventory | Search stock by SKU/bin, stock transfers, controlled adjustments, cycle-count tasks | Employee, manager |
| Order fulfillment | Import/create order, reserve available stock, guided pick, pack verification, ship/close | Picker, packer |
| Reports | Stock, low-stock, movement, open receipts/orders, count variances, productivity | Manager |
| Administration | Users/roles, audit search, integration settings, approval queue, backups | Admin, manager |

Keep the first release focused on one warehouse and a simple receive → putaway and order → pick → pack → ship flow.

## 4. Recommended architecture

### Layers

1. **Presentation:** Existing Flask-rendered web pages, made responsive for phones and handheld browsers. Use large touch targets, high contrast, a persistent scan/entry field, and keyboard-wedge scanner support. A small JavaScript enhancement can focus fields and show scan feedback; the workflow must still work without it.
2. **Application:** Explicit services for receiving, inventory posting, order fulfillment, authorization, approvals, and reporting. Validate each command once in the service layer. Web routes and future API handlers call the same services rather than writing stock directly.
3. **Data:** Relational tables with foreign keys and transactions. SQLite can support an initial, single-site, low-concurrency deployment, but move to PostgreSQL before multiple simultaneous handhelds or remote deployments become operationally critical. Keep ledger posting and on-hand projection updates in one database transaction.
4. **Integration boundary:** CSV import/export first, with validated staging and an import summary. Add small, retry-safe API adapters later. Persist external IDs and import status so retrying does not duplicate orders or receipts.

### Deployment recommendation

- Start with the existing Flask application and a supported production WSGI server; do not use Flask's development server in production.
- For a single local operator or pilot, use SQLite on reliable local storage with scheduled, tested backups. Do not put a SQLite database on a shared network drive.
- For simultaneous scanning by a team, host the web app and PostgreSQL on a small managed or on-premise server with HTTPS, role-restricted backups, and monitoring.
- Keep operational inventory in the WMS as the physical stock source of truth when agreed with the business. Keep accounting, costing, and financial valuation in the ERP/accounting system; define which system owns item identifiers, orders, and supplier records before integration.

### Project-specific security prerequisites

Before exposing this app beyond a trusted local pilot, replace the hard-coded Flask secret with a deployment secret, enable CSRF protection for state-changing forms, require HTTPS and secure session-cookie settings in production, apply least-privilege role checks to every write route, and document backup access. Do not log passwords, session secrets, or unnecessary personal data.

## 5. Relational schema outline

Use integer primary keys, foreign keys, `created_at` timestamps, and indexes for frequently scanned identifiers and status queries. Store timestamps consistently in UTC. Keep quantities in each item's base unit; conversions belong to explicit unit rules, not free-form arithmetic.

### Master and configuration tables

| Table | Important fields |
| --- | --- |
| `users` | `id`, `username`, `password_hash`, `role_id`, `active`, `created_at` |
| `roles` / `role_permissions` | Role name; permission key such as `inventory.adjust` or `order.ship` |
| `items` | `id`, `sku`, `barcode`, `name`, `category`, `base_unit`, `reorder_level`, `active`, optional `tracking_mode` |
| `suppliers` | `id`, `code`, `name`, contact fields, `active` |
| `customers` | `id`, `code`, `name`, external reference, `active` |
| `warehouses` | `id`, `code`, `name`, `active` (one warehouse is sufficient for MVP) |
| `locations` | `id`, `warehouse_id`, `code`, `location_type`, `active`; unique `(warehouse_id, code)` |
| `item_suppliers` | `item_id`, `supplier_id`, optional supplier SKU and lead time |
| `lots` (conditional) | `id`, `item_id`, `lot_code`, optional expiry/manufacture dates |
| `serial_numbers` (conditional) | `id`, `item_id`, `serial_code`, current status |

### Operational documents

| Table | Important fields |
| --- | --- |
| `receipts` | `id`, `supplier_id`, `reference`, `status`, `expected_at`, `received_by`, `created_at` |
| `receipt_lines` | `id`, `receipt_id`, `item_id`, `expected_qty`, `received_qty`, `discrepancy_note` |
| `orders` | `id`, `customer_id`, `external_order_id`, `status`, `ship_to` or protected reference, `created_at` |
| `order_lines` | `id`, `order_id`, `item_id`, `ordered_qty`, `allocated_qty`, `picked_qty`, `packed_qty` |
| `pick_tasks` | `id`, `order_id`, `assigned_to`, `status`, timestamps |
| `pick_task_lines` | `id`, `pick_task_id`, `order_line_id`, `location_id`, `requested_qty`, `picked_qty` |
| `approvals` | `id`, `action_type`, `reference_id`, `requested_by`, `approved_by`, `status`, reason and timestamps |
| `import_batches` | `id`, `source`, `file_name`, `status`, row counts, errors summary, timestamps |

### Inventory ledger and balance

| Table | Important fields |
| --- | --- |
| `stock_movements` | `id`, `item_id`, `location_id`, optional `lot_id`/serial reference, signed `quantity_delta`, `movement_type`, `reference_type`, `reference_id`, `actor_id`, `occurred_at`, `reason`, optional `reversal_of_id` |
| `stock_balances` | `item_id`, `location_id`, optional `lot_id`, `quantity_on_hand`, `updated_at`; projection/cache only, keyed uniquely by stock dimensions |

`stock_movements` is the immutable source of truth. Do not edit or delete posted movement rows in application flows. Corrections create compensating movements linked by `reversal_of_id`, then post the corrected movement. For every posting, insert ledger rows and update the balance projection atomically. Reject operations that would create a negative on-hand quantity unless an explicitly approved exception policy is introduced.

Protect immutability with restricted application write paths and, where supported, database triggers/permissions that reject update/delete on posted ledger rows. Balance projection changes must only occur through the posting service. Reconciliation should compare each balance to the sum of ledger deltas on a schedule.

### Audit and status

Add an append-only `audit_events` table for user/role/master-data changes and approval decisions: `id`, `actor_id`, `action`, `entity_type`, `entity_id`, `before_json`, `after_json`, `occurred_at`, and request/correlation ID. Avoid storing secrets in snapshots. A stock movement ledger is not a substitute for an audit log: the ledger records quantity effects; audit events record administrative changes and workflow decisions.

Use constrained status values, such as `draft`, `open`, `in_progress`, `completed`, and `cancelled`; never silently erase a completed receipt/order. Cancel or correct it through a traceable reversal.

### Migration from the current database

The current `products.quantity` is the authoritative quantity and existing `transactions` records are not a full immutable ledger. Plan a one-time, backed-up migration that creates a designated opening balance per SKU/location and records it as `OPENING_BALANCE`; map each product's current location to a real location record. Preserve historical transactions as imported history with their original timestamps where trustworthy, mark unknown actors clearly as legacy imports, and reconcile totals before switching reads to the new balance projection. Do not fabricate historical bin allocation or claim old rows have ledger guarantees they never had.

## 6. Core workflows

### Inbound: receive and put away

1. Create a receipt manually or import expected lines from CSV. A receipt can also be started without a PO for small operations.
2. Open the receipt on a phone/handheld. Scan the item barcode; show the matched SKU and description prominently for visual confirmation.
3. Enter or scan quantity. Record short, over, damaged, or unknown item discrepancies as explicit notes; require a manager decision for over-receipt beyond the configured tolerance.
4. Confirm receipt. In one transaction, post a positive `RECEIPT` ledger movement to a receiving/staging location and update the balance projection.
5. Show a suggested active putaway bin (simple empty/compatible bin rule; no complex slotting engine). Scan item and destination bin, confirm quantity, and post paired movements: negative from staging, positive to destination.
6. Close the receipt only when lines are resolved or explicitly left with a recorded exception.

### Outbound: order to shipment

1. Import a CSV or create an order manually. Validate external order IDs, item SKUs, and quantities; report invalid rows rather than partially hiding failures.
2. Check available stock and reserve the required quantities in the order workflow. Prevent double allocation through a transaction and a clear shortage status.
3. Generate a short pick list ordered by bin. The picker scans the bin, scans the item, and confirms quantity. A mismatch blocks completion and provides a clear correction path.
4. At pack, scan the order and each item again; verify packed quantities against the order. The MVP may use a printed packing slip.
5. On ship confirmation, post negative `SHIPMENT` ledger movements for picked quantities and mark the order shipped. Carrier label purchase/printing can initially remain in the carrier portal; store the tracking number and carrier reference when available.
6. For cancellation or mis-pick, release reservations or post compensating movements with a reason; never silently overwrite stock.

### Inventory: adjustments, transfers, and cycle counts

- **Transfer:** Scan source bin, item, quantity, and destination bin; post a balanced pair of movements in one transaction.
- **Adjustment:** Select a reason code, enter counted quantity or delta, show before/after, and require manager approval above a configurable quantity/value threshold. Post a ledger movement only after approval.
- **Cycle count:** Create a small bin/item count list, capture the physical count without revealing expected quantity where blind counts are desired, compare results, and send variances through the adjustment approval path.
- **Reconciliation:** A report flags any difference between `stock_balances` and ledger sums. Correct via traceable movements; do not edit the balance directly as a routine fix.

## 7. API surface

The existing app is primarily server-rendered HTML. Add a versioned JSON API only when handheld clients or integrations need it; reuse the same application services as HTML routes. Suggested resource shape:

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/items?query=` | Search items by SKU, barcode, or name |
| `GET /api/v1/stock?sku=&location=` | Read on-hand by item and bin |
| `POST /api/v1/receipts` | Create/import a receipt |
| `POST /api/v1/receipts/{id}/lines/{line_id}/receive` | Record a receipt line and discrepancy |
| `POST /api/v1/inventory/movements` | Post an authorized transfer or adjustment command |
| `POST /api/v1/orders/import` | Validate and stage orders from a source |
| `GET /api/v1/orders?status=` | List orders/work |
| `POST /api/v1/orders/{id}/allocate` | Reserve available stock |
| `POST /api/v1/picks/{id}/confirm` | Confirm a scanned pick |
| `POST /api/v1/orders/{id}/pack` | Validate packed contents |
| `POST /api/v1/orders/{id}/ship` | Confirm dispatch and post shipment movements |
| `GET /api/v1/reports/movements?from=&to=&sku=` | Search movement history |

Require authentication and permission checks on every write. Validate input and return clear `400` validation, `401` unauthenticated, `403` forbidden, `404` missing reference, and `409` conflict/insufficient-stock responses. Use idempotency keys for order imports and externally retried write requests. Never expose a generic endpoint that directly sets an item's quantity.

## 8. Web admin and handheld UI requirements

### Web administration

- Searchable item, supplier, customer, bin, and user lists with clear active/inactive states.
- Simple forms with validation close to fields; no routine editing of on-hand quantities from the item form.
- Approval inbox showing who requested an action, the proposed effect, reason, and approve/reject actions.
- Reports with date/SKU/bin filters and CSV export.
- Import preview with row-level errors, duplicate detection, and a final confirmation before posting.
- Audit and movement history searchable by item, actor, reference, and time.

### Mobile/handheld operation

- Responsive single-column screens, large buttons and quantity controls, readable under warehouse lighting, and limited typing.
- A persistent focused scan field that accepts keyboard-wedge scanners; camera scanning is optional and should not block keyboard/manual entry.
- Every scan shows the matched SKU/name/bin and a success/error state. Require a second scan or confirmation where item identity is ambiguous.
- Support gloves and common handheld screen sizes; do not rely on hover, tiny icons, or color alone.
- Provide clear retry behavior for network loss. A failed request must not appear successful; show whether the command was committed before allowing a retry.
- Test browser, scanner, label printer, and Wi-Fi behavior on the actual devices before rollout.

## 9. Hardware and barcode setup

- Use durable barcode labels with a unique, human-readable SKU alongside the barcode. Code 128 is a practical default for internal alphanumeric SKUs; use GS1 identifiers when required by suppliers, retail partners, or regulated products.
- Barcode standards do not replace item validation. Reject unknown or ambiguous scans and make manual SKU lookup an explicit fallback.
- Start with USB/Bluetooth keyboard-wedge scanners or Android handheld scanners that work as keyboard input. Evaluate camera scanning only if it is sufficiently fast under real lighting and packaging conditions.
- Label receiving/staging and storage bins clearly; test label size, print contrast, curvature, and distance.
- A standard office/thermal label printer and ordinary workstation are sufficient for MVP. Confirm carrier label dimensions and printer compatibility before selecting a thermal model.
- Survey Wi-Fi at receiving, storage, packing, and dispatch areas. Add access points where needed; choose online-first workflows until offline behavior is deliberately designed and tested.

## 10. Technology options

| Option | Suitable when | Trade-offs |
| --- | --- | --- |
| SaaS WMS | The team needs fast adoption, supported integrations, and predictable vendor support | Subscription and per-user/device costs; verify exports, offline behavior, and data ownership |
| Open-source WMS | Requirements fit an established product and the team can operate/customize it | Faster than bespoke for broad workflows, but configuration and upgrades still need ownership |
| Extend this custom app | Workflow is simple, budget is tight, and a developer can maintain Python/Flask | Maximum fit and low license cost; the team owns security, backups, migrations, integrations, and support |

For this project, the pragmatic next step is to extend the existing Flask application only if the actual needs remain close to the stated small-warehouse scope. Keep Flask and SQLAlchemy-independent existing persistence patterns initially if they remain maintainable, but introduce an application-service boundary before adding more workflow modules. Use PostgreSQL when concurrency or deployment needs exceed SQLite's safe operational envelope. Reassess buy-versus-build before implementing carrier, accounting, or ERP integrations.

## 11. Phased implementation roadmap

| Phase | Deliverable | Exit criteria |
| --- | --- | --- |
| 0. Confirm process | Observe receiving, storage, picking, packing; finalize SKU/bin labels, order source, roles, and exceptions | Sample data and real workflows agreed; devices and Wi-Fi tested |
| 1. Inventory foundation | Item/bin masters, opening-balance migration, append-only movement posting, balance reconciliation, role checks and audit trail | Migrated quantity reconciles; all stock changes trace to actor and reason |
| 2. Receive and count | Receipt entry/import, scan-to-receive, discrepancies, putaway, transfer, cycle counts, approvals | Pilot can receive and locate stock without spreadsheet updates |
| 3. Pick and ship | Order CSV intake, allocation, guided pick, pack verification, ship confirmation, packing slip | Representative daily orders complete with scan verification and shipment history |
| 4. Stabilize and integrate | Backup restore drill, monitoring, training, CSV hardening; then one high-value API integration | Agreed reliability and accuracy KPIs met; retries do not duplicate work |

Roll out in a pilot area or subset of SKUs first. Keep a documented rollback and reconciliation procedure through the first physical counts. Avoid a big-bang conversion before opening balances, labels, user permissions, and exception handling are tested.

## 12. Risks and best practices

| Risk | Mitigation |
| --- | --- |
| Incorrect opening inventory or bin mapping | Freeze or tightly control stock during migration; count and reconcile by SKU/bin before go-live |
| Duplicate imports or network retries | External IDs, idempotency keys, import staging, and visible duplicate/conflict reporting |
| Users bypass scans under time pressure | Make scan flows faster than typing, train staff, report exceptions, and keep a controlled fallback |
| Unauthorized or untraceable stock changes | Central posting service, server-side RBAC, append-only ledger, approvals, and periodic audit |
| SQLite contention or fragile shared-file hosting | Keep SQLite on local server storage for a small pilot; move to PostgreSQL before multi-user operational load requires it |
| Unusable scanning or poor Wi-Fi | Test on actual packaging and handhelds; survey coverage; define an explicit network-failure process |
| Overbuilding integrations or traceability | Start with CSV and only implement lot/serial/expiry when product and compliance rules require them |
| Sensitive operational data exposure | HTTPS, secret management, least privilege, minimal PII, access-controlled backups, and retention policy |

Operational best practices: never delete posted stock history; use reversals, reason codes, and audit attribution; back up automatically and test restores; reconcile ledger and balance projection; version CSV templates; define one owner per master-data field; and train users with exception scenarios, not only the happy path.

## 13. KPIs

Capture a baseline before rollout and review weekly during the pilot. Targets should be agreed with operators rather than assumed.

| KPI | Definition |
| --- | --- |
| Inventory accuracy | Counted units matching system quantity within agreed tolerance ÷ units counted |
| Receiving turnaround | Time from receipt arrival to stock available in its pickable bin |
| Order-pick accuracy | Correct order lines/quantities picked ÷ total lines/quantities picked |
| On-time shipment rate | Orders shipped by promised cutoff ÷ orders due |
| Pick productivity | Correct order lines picked per labor hour, interpreted alongside accuracy |
| Low-stock response | Time from threshold alert to replenishment decision |
| Exception rate | Receipts, picks, and counts requiring manual correction ÷ total operations |
| Ledger/projection reconciliation | Number and value of item/bin balances that differ from movement-ledger sums; target zero |

## 14. Immediate implementation priorities

1. Confirm real warehouse type, SKU/order volume, staff, existing systems, and traceability requirements.
2. Replace product-form quantity editing with explicit, reason-coded adjustment commands.
3. Establish bin master data and barcode labels before attempting directed putaway or guided picking.
4. Design and test the ledger/balance migration on a copy of `warehouse.db`; back up and reconcile before production cutover.
5. Add receiving and cycle-count workflows before integrating external order or carrier APIs.
6. Harden production security and operational backups before exposing the app to a shared network.
