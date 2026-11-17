# Small-Warehouse WMS Admin UI Specification

## 1. Product and UI direction

This specification targets warehouse managers, administrators, and read-only owners/viewers. It also accounts for receiving and picking work where the manager configures or monitors it.

The existing application uses Flask/Jinja templates and a small custom stylesheet. Keep that server-rendered approach for the MVP: it suits a small team, keeps the deployment simple, and works with keyboard-wedge barcode scanners. Build reusable template macros and CSS components rather than introducing a separate SPA. If a consistent component library becomes necessary, Bootstrap 5 is a practical Jinja-compatible option; do not combine it with a second competing component system.

Use a desktop-first admin layout, but make receiving, scanning, and pick confirmation usable on handheld-sized screens. A manager should be able to scan or type an SKU from the item lookup without changing systems.

## 2. Navigation and shared layout

```text
Dashboard
Inbound
  Receipts
  Receive against PO
  Putaway work
Inventory
  Stock on hand
  Movement history
  Adjustments
  Cycle counts
Outbound
  Orders
  Pick tasks
  Packing and shipping
Master data
  Items / SKUs
  Locations / bins
  Suppliers
  Customers
Reports
Admin (Admin only)
  Users and roles
  Audit log
```

### Shared page shell

- **Sidebar:** Persistent primary navigation, active section, signed-in user and role, logout. Collapse to a menu on narrow screens.
- **Header:** Page title, breadcrumb where helpful, optional warehouse selector, and contextual primary action (for example, **New receipt**).
- **Global feedback:** A consistent toast/banner for saved, blocked, failed, and pending-approval actions. Errors remain visible until understood; never show success after a failed write.
- **Search/filter toolbar:** Search field, common filters, Apply and Reset, result count, and export action where relevant. Preserve filters when opening a record and returning to the list.
- **Main content:** Tables and detail panels use consistent spacing, row actions, pagination, empty states, and loading/error states.
- **Role-aware actions:** Hide unauthorized actions in the UI for clarity, but always enforce permissions on the server. Viewer/owner pages contain no write controls.

## 3. Screen list

| Screen | Purpose | Key components |
| --- | --- | --- |
| Dashboard | Show current warehouse health and work requiring attention | KPI cards, low-stock table, open receipt/order queues, recent adjustments, accuracy trends |
| Item/SKU list and detail | Search and maintain product master records | Search/filter toolbar, sortable table, create/edit form, inventory-by-bin panel, movement link |
| Location/bin list and detail | Maintain warehouse storage locations | Warehouse/zone filters, bin table, active/pickable flags, current stock and open work |
| Supplier/customer list and detail | Maintain counterparties used by receipts/orders | Searchable tables, detail form, active status, linked receipt/order history |
| Receipt list | Monitor inbound work and exceptions | PO/status/supplier/date filters, status badges, discrepancy indicator, **Receive** action |
| Receipt detail / receive against PO | Confirm deliveries against expected lines | PO header, expected/received quantities, focused scan input, discrepancy form, receive confirmation |
| Putaway work | Move received stock into storage | Suggested bin, source/item/quantity, scan destination, confirm and movement result |
| Stock on hand | Locate physical inventory by SKU, bin, and optional tracking dimensions | Search, bin-level stock table, on-hand/reserved/available values, movement shortcut |
| Movement history | Explain how a balance changed | Filters, signed ledger rows, actor, reason, source document, before/after context where available |
| Adjustments | Request and review controlled corrections | Adjustment list, request form, proposed balance, approval queue, rejection/reversal history |
| Cycle counts | Run and resolve physical counts | Count task list, bin scope, blind-count entry, variance review, recount/approval controls |
| Order list/detail | Track customer orders through fulfillment | Status/priority filters, order lines, allocation/shortage state, pick task and shipment references |
| Pick task | Guide scan-confirmed picking | Ordered bin/item/quantity, scanner field, progress, mismatch feedback, exception path |
| Pack and ship | Verify packed contents and record dispatch | Pack scan list, order comparison, packing-slip action, carrier/tracking fields, dispatch confirmation |
| Reports | Review inventory, movements, turnover, productivity, accuracy | Report selector, date/warehouse/SKU/bin filters, summary and table, CSV export |
| Users and roles | Manage accounts and access | User table, role/status editor, last-admin safeguard, permission summary |
| Audit log | Review attributable changes | Time/user/action/entity/reference filters, event detail with safe before/after values |

## 4. Dashboard specification

### KPI cards

| Card | Definition and presentation |
| --- | --- |
| Stock value | Sum of on-hand quantity × agreed inventory unit cost. Label the valuation basis and “as of” time. Do not use a sales/list price as accounting value. If no cost basis exists, show “Not configured.” |
| Low-stock alerts | Count of active SKUs at or below their reorder threshold; click through to the filtered list. |
| Open receipts | Count of receipts not closed/cancelled, with overdue or discrepancy counts called out separately. |
| Open orders | Count of orders not shipped/cancelled, with shortages visible. |
| Pick accuracy | Correct pick lines ÷ total confirmed pick lines over the selected period; show sample size and comparison period. |
| Inventory accuracy | Counted item/bin lines within agreed tolerance ÷ count lines completed; show sample size and latest count date. |

Do not imply statistical confidence from very small samples. If a KPI has no data or lacks required fields, show “No data” or “Not configured,” not zero accuracy.

### Dashboard panels

- **Attention required:** Low stock, unresolved receipt discrepancies, pending adjustment approvals, count variances, and orders short of stock.
- **Inbound queue:** Receipt/PO, supplier, expected date, status, received progress, discrepancy count.
- **Outbound queue:** Order reference, priority, line count, status, allocated/short lines, ship-by time if used.
- **Recent stock changes:** Latest ledger movements with item, signed quantity, bin, user, reason, and document link.
- **Trends:** Optional weekly pick and inventory accuracy trend; use a table/summary if a chart obscures exact counts.

## 5. Main table columns

All list screens should support stable sorting, pagination, a clear empty state, and filters that can be reset. Avoid placing every data field in the default view; allow detail pages or column settings for less-used fields.

| Screen | Recommended default columns |
| --- | --- |
| Items / SKUs | SKU, barcode, description, UOM, on-hand, reserved, available, min stock, status, actions |
| Locations / bins | Warehouse, bin code, zone, pickable, active, distinct SKUs, on-hand units, open work, actions |
| Suppliers | Supplier code, name, contact, open receipts, active, actions |
| Customers | Customer reference, name, contact, open orders, active, actions |
| Receipts | Receipt/PO, supplier, expected date, received lines, discrepancies, status, updated, actions |
| Receipt lines | SKU, description, expected qty, received qty, difference, suggested bin, actual bin, discrepancy, line status |
| Stock on hand | SKU, description, bin, lot, expiry, on-hand, reserved, available, last movement |
| Movement history | Timestamp, movement type, SKU, bin, signed qty, resulting balance, reason, reference document, user |
| Adjustments | Request ID, SKU, bin, proposed change, reason, requester, approver, status, created |
| Cycle counts | Count ID, warehouse/bin scope, lines, counted/remaining, variance lines, status, owner, due |
| Orders | Order/customer reference, priority, line count, allocated/short, pick progress, status, ship-by, actions |
| Pick tasks | Task/order, picker, next bin, lines remaining, exceptions, status, started |
| Shipments | Order, packed by, carrier, tracking number, shipped at, status |
| Users | Username, role, active, last login, created, actions |
| Audit log | Timestamp, actor, action, entity, reference, request ID; open a detail panel for safe before/after values |

### Status badges

Use a consistent badge component with both a text label and a visual treatment; color is never the only status cue.

| Label | Suggested meaning |
| --- | --- |
| Open | Work created and not yet started |
| Receiving | At least one receipt line is being processed |
| Putaway | Received stock is awaiting bin placement |
| Picking | Order pick work is active |
| Packed | Pack verification is complete; not yet dispatched |
| Shipped | Dispatch has been confirmed |
| Closed | Work is resolved and no further normal edits are allowed |

Show separate badges or flags for **Discrepancy**, **Pending approval**, **Short**, **Cancelled**, and **Overdue** rather than overloading the main workflow status. Reject invalid status transitions with an explanation.

## 6. Forms and validation rules

### Item / SKU form

Fields: SKU, barcode, description, UOM, category (if maintained), min-stock threshold, supplier links, active status, optional lot/serial tracking flags.

Validation:

- SKU is required, trimmed, and unique, case-insensitive if that is the system standard.
- Barcode is optional but unique when present; reject conflicting SKU/barcode matches.
- Description and UOM are required; UOM must be selected from approved values.
- Minimum stock is numeric and non-negative.
- Tracking flags cannot be disabled while active stock or open work uses those dimensions.
- Do not include an editable on-hand field. Initial stock and corrections use an explicit opening balance or adjustment workflow.

### Location/bin form

Fields: warehouse, bin code, zone, pickable, active, optional location type.

Validation:

- Warehouse and bin code are required; bin code is unique within warehouse.
- Deactivation is blocked while stock remains or open work references the bin; explain how to transfer/close those records first.
- Destination bin must be active and eligible for putaway. Pick source must be active and pickable.

### Supplier/customer forms

Fields: code, name, contact name, email, phone, address/reference fields as required, active status.

Validation:

- Name required; code unique when provided.
- Validate email format and phone length/allowed characters without rejecting legitimate international formats.
- Use deactivation instead of deletion when the record has historical references.

### Receipt and scan-receive form

Fields: PO/reference, supplier, expected date, item lines, expected quantity, scan field, received quantity, lot/expiry/serial (when configured), discrepancy type/note.

Validation:

- Receipt reference and supplier required when applicable; each line references an active SKU.
- Received quantity must be greater than zero; over/short/damaged quantities require explicit discrepancy selection and note.
- Scanned barcode and entered SKU must resolve to the same item. Unknown scans cannot be posted.
- For tracked items, required lot/expiry/serial values are collected and validated before confirmation.
- Over-receipt beyond configured tolerance requires manager approval.
- Disable duplicate submission while saving and use an idempotency key for retried scan confirmations.

### Putaway form

Fields: receipt/line, item, source staging bin, quantity, suggested destination, scanned destination.

Validation:

- Source must contain enough unreserved stock; quantity must be positive and no greater than the available amount.
- Scanned item and destination bin must match the expected item and active allowed location.
- Confirm shows the movement and resulting source/destination quantities. A successful putaway is recorded in history; no balance is directly edited.

### Stock adjustment form

Fields: SKU, bin, lot/serial if applicable, adjustment quantity or counted quantity, reason code, notes, before/after quantity, requester.

Validation:

- Reason code and non-empty explanation required.
- Quantity is positive when using direction plus amount, or non-zero when using a signed delta; never ambiguous.
- Preview resulting quantity and reject a negative balance by default.
- Require approval based on configured quantity/value threshold. Requester cannot approve own request.
- Approval posts a ledger movement; rejection leaves on-hand unchanged and remains visible.

### Cycle count form

Fields: count/task, bin scan, SKU scan, physical quantity, lot/serial, recount reason.

Validation:

- Count is open and line belongs to the task.
- Scanned bin/item match the assigned count line.
- Count is numeric and non-negative. Blind count hides expected quantity until submission if enabled.
- Variance is reviewed/approved before it changes stock; count and correction are both traceable.

### Order, pick, pack, and ship forms

Fields: customer/order reference, priority, order lines/SKU/quantity, allocation bins, pick scans, pack scans, carrier, tracking number, dispatch confirmation.

Validation:

- External order reference is unique in its source scope; each line has an active SKU and positive quantity.
- Allocation does not exceed available stock; shortages remain explicit and block full release unless partial fulfillment is configured.
- Picker scans expected bin and item; wrong bin/item produces a clear mismatch and does not advance the line.
- Packed item/quantity must match the order before completion.
- Shipping is allowed only after pack verification; duplicate dispatch requests are idempotent.
- Carrier/tracking fields are optional only if the workflow permits manual carrier processing.

## 7. Stock history, audit, and trust cues

- Every posted stock-changing action links to a detail view showing movement type, signed quantity, item, bin, actor, timestamp, reason, and reference document.
- Transfers show both source and destination ledger legs together.
- Adjustments show the original request, before/after, reason, requester, approver/rejecter, and resulting ledger entry.
- Receipt, putaway, pick, pack, and shipment timelines show who completed each step. A pack status alone does not imply a physical stock movement.
- Posted records are read-only. Corrections use reversal/adjustment actions with confirmation, not edit/delete controls.
- Distinguish **on-hand**, **reserved**, and **available** quantities on every screen where they appear.
- On transaction failure, preserve user input where safe and show whether the operation committed; provide an explicit retry path.

## 8. Page layout and component recommendations

### Desktop layout

- Fixed or collapsible left navigation (about 220–250 px); main content fills remaining width.
- Page header has title, breadcrumb, warehouse context, and one primary action.
- Place search and filters immediately above results; keep applied filters visible.
- Use compact but readable tables, sticky table headers for long lists, and a right-side detail drawer only for quick inspection. Use a full detail page for workflows or approvals.
- Put destructive or irreversible actions away from primary actions and require a confirmation that names the operation and affected stock.

### Component set

Implement a small, consistent set of template/CSS components:

- `PageHeader`, `FilterToolbar`, `DataTable`, `Pagination`
- `StatusBadge`, `MetricCard`, `EmptyState`, `LoadingState`
- `FormField`, `ValidationSummary`, `ConfirmDialog`
- `ScanInput`, `QuantityControl`, `DiscrepancyPanel`
- `AuditTimeline`, `ApprovalPanel`, `Toast/FlashMessage`

Prefer semantic HTML controls, server-side validation, and simple progressive enhancement. For barcode scanners that emulate a keyboard, keep a visible, labeled scan input with predictable focus and avoid intercepting ordinary typing. Do not require camera permissions for scanner support.

### Accessibility and responsive behavior

- All fields have labels; errors are associated with fields and summarized at the top.
- Keyboard navigation and visible focus are supported. Dialogs trap focus appropriately and return focus when closed.
- Text and icon labels accompany color; meet WCAG AA contrast for normal text.
- At tablet/phone widths, tables scroll horizontally or convert key rows into stacked cards without hiding critical actions.
- Receiving and picking pages prioritize the active scan field, large touch targets, short instructions, clear success/error feedback, and minimal typing.
- Test with actual scanner hardware and representative browsers before rollout.

## 9. Role-specific UI behavior

| Role | UI behavior |
| --- | --- |
| Warehouse manager | Dashboard, approvals, receipt/order queues, inventory reports, count/adjustment review, and master-data actions |
| Admin | All manager workflows plus user/role management, system settings, and audit-log access |
| Viewer/owner | Dashboard, stock, operational statuses, and permitted reports/audit views; no create/edit/approve/ship controls |

An unauthorized request must still be rejected by the backend even if a user manipulates a form or calls a route directly.

## 10. MVP build order

1. Establish shared layout, role-aware navigation, status badges, table/filter patterns, and common form/error components.
2. Deliver dashboard, item/bin lists, stock lookup, and movement detail with clear on-hand/reserved/available semantics.
3. Add receipt, discrepancy, and putaway workflows with scan confirmation and ledger-linked history.
4. Add adjustment approvals and cycle-count tasks.
5. Add order, pick, pack, and ship screens; validate on actual handheld/scanner hardware.
6. Add report filters/exports, audit search, and role administration. Test the read-only viewer role on every page.

Avoid adding dashboard charts, configurable widgets, or dense reporting before users can complete the basic warehouse tasks accurately.
