# Updated Small-Warehouse WMS Project Plan

## 1. Executive summary and MVP boundary

This plan is the current scope baseline for a small warehouse. It prioritizes dependable receipt, putaway, storage, picking, packing, shipping, counting, adjustment, and barcode workflows. It explicitly excludes distribution-center automation and complex fulfillment optimization.

### Planning assumptions

The business details in the request are blank. Use these as planning assumptions until the warehouse confirms them:

| Detail | Assumption / current project information |
| --- | --- |
| Warehouse footprint | One warehouse in Phase 1 |
| SKU / order volume / staff | Planning estimate from earlier project docs: about 300 SKUs, 50 orders/day, 3–6 staff; not confirmed |
| Budget, launch date, integrations | Not provided; use CSV/manual operations for the pilot and confirm before committing dates |
| Application | Django REST Framework backend with a responsive PWA; the existing Flask application remains available during the staged transition |
| Data | PostgreSQL is the target for shared operation; SQLite is a local development fallback |
| Authentication | JWT with Admin, Manager, Operator, and Viewer roles |
| Inventory authority | WMS owns physical on-hand once opening stock is counted and accepted; ERP/accounting remains the financial authority |
| Tracking | Decide lot/batch and expiry needs in Phase 0; serial tracking is not part of the baseline |

### MVP boundary

**Phase 1 must make ordinary warehouse work reliable:** maintain item/bin masters, receive stock, confirm putaway, look up stock, import/create sales orders, reserve and pick, verify packing, ship, record every physical stock movement in the immutable ledger, and produce a basic stock report. Use CSV/manual carrier steps where an API is not already available.

Keep the first release to one warehouse, simple bin sequence, one-step internal bin moves, and straightforward exception handling. Do not make a carrier integration, multi-warehouse routing, advanced slotting, wave picking, robotics, offline stock mutation, or full ERP integration a launch dependency.

### Current implementation baseline

The project already contains a Django/PWA implementation of item and location masters, receipt and putaway, return inspection/disposition, stock lookup, CSV order import, allocation/reservation, FEFO picking for expiry-tracked items, pack verification, shipment posting, immutable stock ledger, adjustment approval, low-stock and replenishment reporting, cycle counts, expiry monitoring, role checks, and simple bin-to-bin transfer.

The following requirements remain **partial or planned**, not implied to be complete by the current UI: explicit `Locked` stock quantity, cycle-count movement locks and second counts, reconciliation reporting, distinct final `Closed` order status, full-cycle operational KPIs, carrier label printing, and carrier/ERP API integrations. Phase gates below cover these gaps. Preserve the existing Flask app until a cutover is approved.

## 2. Module scope and priorities

| Module / function | Priority | Phase target | Scope and boundary |
| --- | --- | --- | --- |
| SKU/item master, barcode, base UOM | Highest | Phase 1 | Unique SKU/barcode, description, UOM, active state, minimum/safety stock; one base UOM per SKU initially |
| Location master and labels | Highest | Phase 1 | Warehouse/zone/bin code such as `A-01-03`, sequence, active/pickable/type; one warehouse |
| Immutable inventory ledger and stock lookup | Highest | Phase 1 | Transactional snapshot plus append-only ledger; lookup by SKU/barcode/bin and stock summary |
| Inbound receipt and putaway | Highest | Phase 1 | Purchase, return, or other inbound reference; scan item/quantity, discrepancy, confirm destination |
| Outbound order, allocation, pick, pack, ship | Highest | Phase 1 | Manual/CSV sales orders; reserve available stock, scan-verify pick/pack, record shipment; deduct physical stock at shipment |
| Basic roles and audit attribution | Highest | Phase 1 baseline | Admin, Manager, Operator, Viewer; server-side permissions and actor/timestamp for writes |
| Internal bin transfer | High | Phase 1 | Simple scan-confirmed move between storage bins; paired ledger entries; no warehouse-to-warehouse routing |
| Cycle count and adjustment approval | High | Phase 2 | Planned counts, count-time baseline, variance review, approval, adjustment posting, count lock and second-count thresholds |
| Returns inspection and disposition | High | Phase 2 | Inspect returned items; decide restock, quarantine, return-to-supplier, or scrap before stock is pickable |
| Safety-stock alerts and movement/reconciliation reports | High | Phase 2 | Available stock alerts, inbound/outbound detail, movement history, snapshot-to-ledger reconciliation |
| Explicit locked stock and optional in-transit | Medium | Phase 2/3 decision | Add locked quantity/hold reason only with clear rules; in-transit only for a real transfer process |
| Batch/expiry | Medium | Configure only for applicable SKUs | Lot capture, FEFO allocation, expired-stock exclusion, expiry watch, and missing-expiry alerts when `track_expiry` is enabled |
| KPI dashboard and productivity | Medium | Phase 3 | Operationally trustworthy measures after timestamps and exception data are complete; avoid speed-only rankings |
| Carrier, ERP, e-commerce APIs | Low | Phase 3 | Add only after CSV formats and business ownership are proven |
| Multi-warehouse transfer/routing | Low | Phase 3 or later | Requires inter-warehouse transit, ownership, reconciliation, and routing policy |
| Advanced wave planning, task interleaving, dynamic slotting, robotics | Deferred | Out of scope | Do not build for this operation without measured volume and a separate business case |

## 3. End-to-end process flows

### 3.1 Inbound: purchase, return, or other receipt

**Status flow:** `Draft → Confirmed → Receiving → Received → Putaway in progress → Putaway completed → Closed`

1. Create a receipt with source type (`Purchase`, `Return`, or `Other`), source reference, warehouse, receiving bin, and expected lines. An ASN is optional; do not make it a dependency.
2. On arrival, scan the receipt/reference and item barcode. Show expected, received, and outstanding quantity before confirming.
3. Enter actual quantity and required lot/expiry details. Record short, over, damaged, wrong item, or other discrepancies with a reason and note.
4. Confirm receipt. Record physical stock in a non-pickable receiving/staging location in the same transaction as the `RECEIPT` ledger entry. Receiving stock is on-hand but is not available for allocation.
5. If QC is required, hold stock in quarantine until disposition. Otherwise suggest an eligible storage bin using simple active/type/capacity/sequence rules.
6. Scan item and destination bin; confirm putaway. Post balanced source/destination ledger entries. Stock becomes pickable only when it is in an active pickable storage location and not reserved/locked.
7. Close when all accepted quantities are put away or all remaining quantities have an authorized, documented disposition.

**Exceptions**

| Case | Default response |
| --- | --- |
| Short receipt | Record actual received and outstanding amounts; leave open or manager-close with a reason/backorder disposition |
| Over receipt | Record discrepancy; hold excess pending manager approval; do not silently increase expected quantity |
| Damaged goods | Receive to quarantine/non-pickable status; inspect before restock; scrap requires an approved adjustment |
| Wrong item | Do not post against the expected SKU; record an exception and resolve against the correct item/source |
| Full/ineligible bin | Do not confirm putaway; suggest another eligible bin or require a manager-approved location change |
| Duplicate scan/retry | Reuse the same idempotency key; replay the original response instead of posting twice |

### 3.2 Outbound: sales order to shipment

**Status flow:** `Created → Allocated → Picking → Picked → Packed → Shipped → Closed`

1. Create an order manually or import CSV. Validate customer/reference, active SKU, UOM quantity, duplicates, and warehouse.
2. Validate available stock and reserve the full order by default. If stock is insufficient, leave the order unallocated or on hold with the shortage identified; do not create a misleading partial allocation.
3. Generate a simple pick task ordered by configured bin sequence. Scan bin, then item; verify the remaining quantity.
4. Record short pick, damage, or missing stock as an exception. Recheck/reallocate or manager-authorize a documented partial fulfillment; never lower ordered quantity silently.
5. At packing, scan each item and confirm packed quantities against picked/order quantities. Resolve missing or extra items before shipment.
6. Confirm shipment and tracking details. Deduct stock from the packing/staging location only at shipment confirmation; write shipment ledger movements and mark the order `Shipped` atomically.
7. Close the order after shipment confirmation and required paperwork/reconciliation. If no separate close action is needed operationally, treat `Shipped` as terminal and omit `Closed` rather than adding a meaningless step.

**Exceptions**

| Case | Default response |
| --- | --- |
| Insufficient stock | Do not allocate; show missing SKU quantity and leave order open/on hold |
| Wrong bin/item | Reject without changing pick progress; prompt for expected scan |
| Short pick/damage | Block line completion; recount or reallocate, then record reason/manager disposition |
| Pack mismatch | Block packed/shipped status until verified or explicitly approved partial shipment |
| Duplicate order/import/ship submission | Enforce unique external reference and idempotent writes |

### 3.3 Inventory, availability, and transfers

Use these terms consistently:

| Quantity | Definition |
| --- | --- |
| On-hand | Physical quantity in all locations, including receiving, packing, quarantine, and storage |
| Reserved | On-hand committed to an active order; reservation is not a physical ledger movement |
| Locked | On-hand intentionally unavailable because of QC, damage, expiry, an active count, or another hold |
| Available | `On-hand − Reserved − Locked`, limited to eligible pickable locations for order allocation |
| In-transit | Optional quantity dispatched from one warehouse but not yet received at another; do not include in destination on-hand |

The first release can use non-pickable receiving/quarantine bins and active reservations while explicit `Locked` quantity is pending. Before adding it, define whether locks overlap reservation quantities; the target rule is disjoint buckets so the formula does not double-subtract.

Every physical movement (receipt, putaway, pick-to-pack, ship, transfer, adjustment, count correction, scrap) posts ledger rows and updates the on-hand projection atomically. Reservations affect availability but do not create physical stock ledger rows. Reject negative available stock by default. Reconciliation compares ledger-summed quantity to the snapshot for every SKU/location/lot dimension.

**Simple internal transfer:** `Created → Source confirmed/picked → In transit (optional) → Destination received → Closed`. In one very small warehouse, Phase 1 may use a single atomic `Move stock` action: scan SKU, source bin, destination bin, and quantity; validate available stock/capacity; post equal-and-opposite `TRANSFER` entries. Use a staged in-transit document only when movement is asynchronous or spans warehouses.

### 3.4 Counting and adjustment

**Count status flow:** `Planned → Counting → Counted → Variance review → Approved → Adjusted → Closed`

1. Manager creates a count plan for bins/SKUs and assigns a counter. Lock the scoped stock from conflicting movement, or use a clearly documented short freeze during count.
2. Capture the count-time system baseline; support blind counts when practical. Scan bin, item, and lot/expiry when configured; record physical quantity without changing inventory.
3. Compare counted quantity with baseline. A variance over the configured absolute/percentage threshold requires a second count by a different user where staffing permits.
4. Reviewer approves/rejects the variance and records reason. An approved difference posts a `CYCLE_COUNT` gain/loss ledger adjustment; only then does the snapshot change.
5. Close and release the count lock after all approved adjustments post. Cancellation retains count history and releases locks safely.

**Adjustment status:** `Requested → Pending approval → Approved → Posted` or `Rejected`. Every adjustment requires a reason code, notes, requester, and approver. Do not permit self-approval of material adjustments. A count is evidence; the adjustment is the posting.

### 3.5 Returns

**Status flow:** `Requested → Received → Inspecting → Dispositioned → Posted → Closed`

1. Link the return to a customer/supplier return reference and scan the SKU/quantity.
2. Receive into quarantine/non-pickable stock. Record condition, packaging, lot/expiry if applicable, and inspection notes.
3. Choose disposition: restock, quarantine/hold, return-to-supplier, or scrap.
4. Restock transfers to an eligible bin; quarantine remains locked/non-pickable; scrap posts an approved loss adjustment; supplier return becomes an outbound issue.
5. Close only after each line has a disposition and ledger effect where appropriate.

### 3.6 Phase-1 internal bin transfer

1. Operator chooses warehouse and scans SKU/barcode.
2. Scan source and destination storage bins, enter quantity, and capture lot/expiry when tracked.
3. Server validates active storage bins, available source stock, lot dimension, and destination capacity.
4. In one transaction, post balanced `TRANSFER` ledger rows and update both snapshots. Failed/duplicate requests do not double-move stock.

## 4. Documents, statuses, and posting points

| Document / record | Minimum status flow | Physical posting point | Phase |
| --- | --- | --- | --- |
| Inbound receipt | Draft → Confirmed → Receiving → Received → Putaway in progress → Putaway completed → Closed / Cancelled | Receipt confirmation posts to receiving/staging; putaway posts a paired transfer; allocation eligibility begins only in pickable storage | 1 |
| Putaway task | Planned → In progress → Completed / Cancelled | Destination-bin confirmation posts paired ledger rows | 1 |
| Outbound order | Created → Allocated → Picking → Picked → Packed → Shipped → Closed / Cancelled | Shipment confirmation deducts staged/packing stock; picking may move stock to packing but cannot erase history | 1 |
| Pick task | Queued → Released → In progress → Completed / Blocked / Cancelled | Scan-confirmed source-to-packing movement posts paired rows if physical location changes | 1 |
| Shipment | Draft/Ready → Confirmed → Shipped → Closed / Cancelled | Shipment confirmation consumes reservation and posts negative `SHIP` movement(s) | 1 |
| Inventory adjustment | Requested → Pending approval → Approved → Posted / Rejected | Approval/posting creates signed `ADJUST` ledger movement | 1 baseline; formal thresholds 2 |
| Count plan/record | Planned → Counting → Counted → Variance review → Approved → Adjusted → Closed / Cancelled | Count entry does not change stock; approved variance creates `CYCLE_COUNT` movement | 2 |
| Return order | Requested → Received → Inspecting → Dispositioned → Posted → Closed | Post only the disposition: restock transfer, quarantine hold, supplier issue, or approved scrap adjustment | 2 |
| Bin transfer | Created → Confirmed → Completed / Cancelled | Confirmation posts equal-and-opposite `TRANSFER` rows in one transaction | 1 simple; 3 staged/inter-warehouse |

Never edit a posted ledger row or set on-hand directly from a form. Corrections use a new, referenced movement. Reservation and count-lock changes are audited; they are not physical quantity postings.

## 5. Phased build plan and gates

| Phase | Deliverables | Exit criteria |
| --- | --- | --- |
| **0 — Process and data preparation** | Confirm process owners/system of record; map zones and location codes; clean SKU/barcode/UOM data; decide lot/expiry; define discrepancy and adjustment reason codes; set approval and count thresholds; baseline count and Wi-Fi/scanner survey; select pilot and data migration approach | Manager signs off location map, clean import file, reason codes, approval policy, opening-count plan, and scope |
| **1 — MVP operations** | Master data; basic RBAC; receipt against purchase/return/other reference; scan receipt and putaway confirmation; storage lookup and low-stock threshold; order entry/CSV import; all-or-nothing reservation; guided pick; pack verification; shipment confirmation; immutable ledger and basic stock report; simple internal bin transfer; seed/setup documentation | Pilot completes receipt-to-putaway and order-to-ship; every stock change has corresponding ledger rows; ledger/snapshot reconciles by SKU/bin; no critical scan/permission defects; staff complete training |
| **2 — Control and exceptions** | Count plans with stock locks, variance approval, second-count threshold and reason codes; formal adjustment approvals; return inspection/disposition; explicit locked-stock model; safety-stock alerts; inbound/outbound detail, movement and reconciliation reports; granular role permission review; daily/weekly count cadence | Approved counts and adjustments are auditable; damaged/held stock cannot be picked; returns only become available after disposition; reconciliation exceptions have owners |
| **3 — Integration and optimization** | Optional lot/expiry/FEFO if validated in Phase 0; staged/multi-warehouse transfers only if needed; carrier label/API integration; ERP/e-commerce API integration; KPI dashboard and productivity trends; simple slotting recommendations only after reliable history exists | Integration retries are idempotent; pilot shows business benefit; stock remains reconcilable; manager approves each production expansion |

**Do not advance on dates alone.** For a 3–6 person team, use short pilot cycles and one champion per shift. The budget and target date are unknown; estimate them after Phase 0 data cleanup, hardware, and deployment decisions.

## 6. Backlog grouped by epic

Prioritize the following backlog in order. Existing code may satisfy some stories; verify each acceptance criterion before marking it complete.

### Epic A — Process and master data (Phase 0/1)

| Story | Acceptance criteria |
| --- | --- |
| As an admin, I can maintain item SKU, barcode, description, base UOM, active state, and minimum stock. | SKU is unique; duplicate barcode is rejected; inactive items cannot be received/picked; no form silently changes quantity. |
| As a manager, I can define warehouse, zone, bin code, sequence, type, and pickability. | Bin code is unique within warehouse; receiving/quarantine/packing/storage are distinguishable; scanned inactive bins are rejected. |
| As an admin, I can load supplier/customer references and clean master data. | Import validates required fields and duplicates; failures are reported by row; no partial hidden import occurs. |
| As a project lead, I can approve a location map and opening-count file. | Each active SKU/bin count has an owner; cutover totals reconcile; ambiguous identifiers are resolved before live use. |

### Epic B — Inbound and putaway (Phase 1)

| Story | Acceptance criteria |
| --- | --- |
| As a receiver, I can create a purchase, return, or other inbound receipt. | Receipt has source type/reference, warehouse, receiving location, expected SKU quantities, and actor; duplicate source documents are rejected or safely recognized. |
| As a receiver, I can scan and confirm received quantity. | Wrong SKU/barcode has no stock effect; quantity and discrepancies are recorded; retry with same key posts once. |
| As a receiver, I can put away accepted quantity. | Destination must be eligible; wrong item/bin and insufficient receiving stock are rejected; successful putaway posts balanced ledger rows. |
| As a manager, I can close a short or discrepant receipt. | Unresolved quantity requires reason/disposition; closed receipt history remains readable. |

### Epic C — Inventory ledger, availability, and transfers (Phase 1/2)

| Story | Acceptance criteria |
| --- | --- |
| As an operator, I can look up stock by SKU, barcode, or bin. | Results show on-hand, reserved, and available by location; quarantine/receiving is not presented as pickable stock. |
| As an operator, I can move stock between storage bins. | Correct SKU and both bins are validated; reserved/insufficient quantity and capacity violations are rejected; two balanced transfer rows and snapshot updates commit atomically. |
| As a manager, I can reconcile stock snapshot to the ledger. | Report groups by item/location/tracking dimension, displays differences and last movement, and does not auto-correct balances. |
| As a manager, I can hold stock from allocation. | Phase 2 lock has a reason, actor, scope, and release condition; available quantity subtracts locked and reserved without double-counting. |

### Epic D — Outbound order fulfillment (Phase 1)

| Story | Acceptance criteria |
| --- | --- |
| As an operator, I can create/import sales orders. | CSV rows validate warehouse, reference, SKU, UOM quantity, and duplicate identity; import is idempotent and reports failures clearly. |
| As the system, I reserve available stock before creating a pick task. | No negative availability; insufficient orders remain visibly unallocated/on hold; concurrent allocations cannot reserve the same units twice. |
| As a picker, I can follow a bin-sequenced task and confirm scans. | Wrong bin/item does not advance quantity; successful pick records actor/time and any physical staging movement in the ledger. |
| As a packer, I can scan-check order contents. | Missing/extra quantities block pack completion; pack verification is audited; physical on-hand is not deducted twice. |
| As a shipper, I can confirm dispatch and tracking. | Shipment confirmation is idempotent; only packed orders ship; reserved stock is consumed and `SHIP` ledger rows post atomically. |

### Epic E — Counts, adjustments, and returns (Phase 2)

| Story | Acceptance criteria |
| --- | --- |
| As a manager, I can plan a cycle/full count and lock its scope. | Count scope and baseline are captured; movement that would invalidate the count is blocked or routed through a safe, audited exception. |
| As a counter, I can submit physical counts without changing stock. | Count records bin/item and tracking dimensions; wrong scan is rejected; variance is visible only to authorized review where blind counting is enabled. |
| As a manager, I can review variance and require a second count. | Threshold is configurable; second count has a distinct actor/value; approval/rejection and reason are audited. |
| As a manager, I can approve a reason-coded adjustment. | Requester cannot self-approve; approval posts one ledger movement; negative available is rejected by default. |
| As a receiver, I can inspect a return and select disposition. | Restock, quarantine, supplier return, and scrap each have explicit status/effect; held/damaged goods cannot be allocated. |

### Epic F — Reports, security, and go-live (Phase 1/2/3)

| Story | Acceptance criteria |
| --- | --- |
| As a manager, I can view inbound/outbound detail, stock summary, and movement history. | Reports filter by period, SKU, bin, reference, and status where relevant; totals reconcile to ledger. |
| As a manager, I can see minimum operational KPIs. | Definitions, data source, time window, target, sample size, and missing-data caveats are shown. |
| As an admin, I can assign least-privilege roles and review audit history. | Server rejects unauthorized writes regardless of hidden UI controls; every write identifies actor/time/reference. |
| As a project lead, I can safely launch and recover. | Backup restore is tested; scanner/Wi-Fi/browser validated; training and rollback checklist signed; one inventory system of record remains. |

## 7. Minimum KPIs

Set numeric targets after the Phase 0 baseline. Targets below are placeholders, not guarantees; define the sample size and exclusions before reporting.

| KPI | Definition | Initial target placeholder |
| --- | --- | --- |
| Receiving accuracy | Receipt lines with correct SKU and received quantity ÷ receipt lines audited | ≥ 99%; baseline in pilot |
| Putaway accuracy | Putaway confirmations to correct scanned/eligible bin ÷ putaways audited | ≥ 99% |
| Pick accuracy | Correct SKU, bin, and quantity ÷ order lines picked | ≥ 99.5% after sufficient samples |
| On-time shipment rate | Orders shipped by promised ship time ÷ orders due in period | ≥ 95%; establish promise-time data first |
| Inventory accuracy | Counted SKU/bin dimensions within agreed tolerance ÷ dimensions counted | ≥ 98% |
| Stock variance rate | Counted dimensions with non-zero variance ÷ dimensions counted; also report absolute unit/value variance if costing is trusted | Trend down from Phase 0 baseline; target TBD |
| Order fulfillment cycle time | Time from order release/creation (choose one consistently) to shipment confirmation; report median and 90th percentile | Baseline first; set target after 2–4 weeks |

Do not treat reservations as physical movement. Exclude cancelled/invalid orders only by a published rule. Report count sample size, partial shipments, and missing timestamps; do not rank individuals by speed without task-mix and accuracy context.

## 8. Risks, assumptions, and open questions

### Risks and controls

| Risk | Control |
| --- | --- |
| Project size or launch date is unknown | Confirm sponsor, budget, operator availability, and a Phase 0 target date before committing schedule. |
| Two editable inventory masters persist | Declare WMS physical stock authority; archive spreadsheets after reconciled cutover; ERP remains financial authority. |
| Dirty SKU/barcode/UOM or bin labels | Clean and scan-test all identifiers; use one base UOM; resolve duplicates before import. |
| Count scope moves during count | Implement bin/item locks or a controlled freeze; release only after approval/adjustment. |
| Returns/damage enter pickable stock | Receive to quarantine and require disposition before restock. |
| Wi-Fi, scanner, or retry failure | Survey work areas; test scanner suffix/browser focus; use idempotency; never assume a timeout means a failed or successful commit. |
| Overbuilding integrations and analytics early | CSV/manual carrier portal in Phase 1; add APIs/KPIs only after operational data is reliable. |
| PostgreSQL deployment and backup not proven | Validate production migrations, role permissions, backups, restore, monitoring, and concurrency before go-live; local SQLite success is not a production proof. |
| Untrained operators or speed-only targets | Pilot with operator champions, train exception paths, pair speed with accuracy and safety. |

### Open questions for Phase 0

1. Confirm actual warehouse type, SKU count, daily order volume, team/shift size, budget, and desired go-live date.
2. Which system owns SKU/customer/supplier data, customer orders, and physical stock after cutover? Which ERP/accounting system retains cost and financial valuation?
3. Are purchase orders, supplier returns, customer returns, and transfer orders imported or entered manually? What CSV columns are available?
4. Are lot/batch, expiry, serial, QC, or regulatory traceability required for any SKU? If yes, which SKUs and what scan label contains the identifiers?
5. What constitutes a material adjustment/variance, who may approve it, and when is a second count mandatory?
6. Should count locks be per bin, SKU/bin, or lot/bin? What is the approved emergency override?
7. What is the on-time shipment promise, and are carrier labels printed in the carrier portal or must the WMS generate them?
8. What Wi-Fi/scanner/printer hardware is already available, and what is the tested backup/restore RPO/RTO?

### Explicitly deferred

Wave picking, task interleaving, automated replenishment, advanced slotting, multi-warehouse routing, robotics/conveyors, carrier purchasing APIs, offline mutation queues, serial-number traceability, and predictive forecasting are deferred unless a confirmed business constraint requires them.
