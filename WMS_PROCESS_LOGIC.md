# Small-Warehouse WMS Business Logic

## 1. Scope and invariants

This document defines the operational rules for receipts, putaway, orders, picking, packing, shipping, inventory, and cycle counts. It targets one small warehouse and simple receive → putaway and order → pick → pack → ship workflows.

Non-negotiable invariants:

1. The stock ledger is the authoritative record of physical quantity changes. Never edit or delete a posted movement; correct it with a linked reversal/adjustment.
2. The on-hand snapshot is updated in the same database transaction as its ledger movement(s).
3. A transfer is two equal-and-opposite ledger rows posted atomically.
4. Reservations reduce available-to-promise, not physical on-hand.
5. Unknown or mismatched scans do not post stock or advance work.
6. Every successful write records the actor, timestamp, reason/reference, and an idempotency key or equivalent source-document line reference.
7. Offline or uncertain submissions are not shown as committed until the server confirms the result.

## 2. Status transitions

### 2.1 Receipt

`DRAFT` means editable and not operationally released. `OPEN` is ready to receive. `RECEIVING` has at least one receipt action. `PUTAWAY` means receiving is complete or explicitly short-closed and accepted stock remains to put away. `CLOSED` means all accepted stock is put away or an authorized disposition is documented. `CANCELLED` is allowed only before posted movements, or after explicit reversal of already-posted movements.

```text
DRAFT -> OPEN -> RECEIVING -> PUTAWAY -> CLOSED
  |       |          |           |
  +-------+----------+----------> CANCELLED (subject to posting/reversal rules)
```

| Transition | Guard / side effect |
| --- | --- |
| DRAFT → OPEN | Source reference/type and supplier/transfer party validated; expected lines are valid. |
| OPEN → RECEIVING | First line begins receiving; no quantity is posted until the scan/quantity confirmation commits. |
| RECEIVING → RECEIVING | Additional partial receipt; preserve expected, received, and outstanding quantities separately. |
| RECEIVING → PUTAWAY | All lines are received/explicitly short-closed, and discrepancies are recorded; accepted quantities are available in receiving or quarantine locations. |
| PUTAWAY → CLOSED | All accepted quantities have a final bin/disposition; unresolved lines or approvals block closure. |
| DRAFT/OPEN → CANCELLED | No stock movement exists. If a posted receipt must be cancelled, reverse it through an authorized correction; do not erase the ledger. |
| RECEIVING/PUTAWAY → CANCELLED | Only manager-authorized with a documented disposition and compensating ledger movement for any stock already posted. |

**Schema alignment:** the current schema draft's receipt status check omits `PUTAWAY`. Add it (and any chosen exception status) before implementing this state machine. Track putaway progress at line/quantity level; a single header status is not enough for partial putaway.

### 2.2 Customer order

```text
DRAFT -> OPEN -> ALLOCATED -> PICKING -> PICKED -> PACKED -> SHIPPED
                    |             |         |
                    +----------> ON_HOLD <---+
                                      |
                                      +--> OPEN / ALLOCATED (after resolution)

DRAFT/OPEN/ALLOCATED -> CANCELLED
```

| Transition | Guard / side effect |
| --- | --- |
| DRAFT → OPEN | Required customer/source reference and valid item quantities; external import ID is deduplicated. |
| OPEN → ALLOCATED | Reserve enough available stock for all required lines, or apply an explicitly configured partial-allocation policy. |
| ALLOCATED → PICKING | At least one pick task is released; task lines reference eligible bins and reservation quantities. |
| PICKING → PICKED | All required lines are picked or an approved partial-fulfillment decision is recorded. |
| PICKED → PACKED | Pack station has verified every line and quantity; discrepancies are resolved. |
| PACKED → SHIPPED | Dispatch is confirmed; shipment, allocation consumption, audit event, and physical stock ledger movements commit atomically. |
| OPEN/ALLOCATED/PICKING → ON_HOLD | Shortage, scan exception, damaged stock, address/order issue, or approval-required condition blocks further normal work. |
| ON_HOLD → prior eligible state | Manager resolves and records the reason; reallocation may be required. |
| DRAFT/OPEN/ALLOCATED → CANCELLED | Release active reservations. If any physical movement was posted, reverse/return stock explicitly. |

`ON_HOLD` is a recommended addition to the current order status constraint (or use a separate hold/exception flag). Never label a partially dispatched order `SHIPPED` unless the product explicitly supports partial shipments and stores shipment-level records.

### 2.3 Pick task

Add `pick_tasks` and `pick_task_lines` to the schema before implementing pick workflows; they are referenced by the API plan but are not yet present in the schema draft.

```text
QUEUED -> RELEASED -> IN_PROGRESS -> COMPLETED
   |          |           |
   +----------+----------> BLOCKED -> RELEASED (after resolution)
QUEUED/RELEASED -> CANCELLED
```

| Transition | Guard / side effect |
| --- | --- |
| QUEUED → RELEASED | Order is allocated; task lines have a bin, item, and quantity. |
| RELEASED → IN_PROGRESS | Picker claims/starts task; assignment and start time are recorded. |
| IN_PROGRESS → IN_PROGRESS | Successful line scans update picked quantity exactly once. |
| IN_PROGRESS → BLOCKED | Shortage, wrong stock, damaged goods, count lock, or other unresolved exception. |
| BLOCKED → RELEASED | Authorized user records resolution; re-check allocation and stock before resuming. |
| IN_PROGRESS → COMPLETED | All lines meet the required pick quantity or approved partial-pick disposition. |
| QUEUED/RELEASED → CANCELLED | Release reservations or return them to the order; never remove existing ledger history. |

### 2.4 Cycle count

```text
OPEN -> COUNTING -> REVIEW -> CLOSED
           |          |
           +-> RECOUNT+

OPEN/COUNTING -> CANCELLED (no posted correction without reversal)
```

| Transition | Guard / side effect |
| --- | --- |
| OPEN → COUNTING | Count scope and baseline are captured; assigned counter starts work. |
| COUNTING → REVIEW | Required lines are counted; variances are visible to an authorized reviewer. |
| REVIEW → COUNTING (RECOUNT) | Reviewer requests a blind recount; retain both original and recount values. |
| REVIEW → CLOSED | Variances are approved/rejected and any approved adjustment ledger entries commit. |
| OPEN/COUNTING → CANCELLED | No unresolved posted correction; record cancellation reason and retain entered counts. |

Schedule high-value items weekly and other active items monthly. Define “high value” using the business's agreed unit-cost threshold or ABC class; do not infer it from selling price. Count frequency is a schedule, not a reason to skip a count after a material discrepancy.

## 3. Inbound: receive and put away

### 3.1 Receipt sources and receiving

1. Create a receipt linked to a PO, return authorization, or transfer order. Validate the source exists and is eligible for receipt; retain source type and reference.
2. Scan the PO/receipt label or search the reference, then scan each item. The scanned barcode must resolve to the same active SKU as the selected expected line.
3. Show expected, previously received, and outstanding quantity before entry. Capture actual received quantity and required lot/batch, expiry, or serial identifiers.
4. Record shortage, overage, damage, wrong item, or other discrepancy with a reason code and note.
5. Confirm the receipt line. Post an inbound ledger movement to a receiving/staging or quarantine bin and update the balance snapshot in the same transaction. Use an idempotency key per confirmed line/action.
6. Keep partial receipts open. A manager may close a PO receipt short only by recording the outstanding quantity as backordered/cancelled or otherwise dispositioned; never silently mark the full expected amount received.
7. Received stock is eligible for allocation only when in an active pickable bin and not held/quarantined.

### 3.2 Putaway suggestion rules

Use simple eligibility filters first, then rank eligible bins:

| Rule | Behavior |
| --- | --- |
| Active and compatible | Exclude inactive bins and bins disallowed for the item's hazard, temperature, size, or tracking requirements. |
| Capacity | If capacity data is maintained, exclude bins that would exceed configured capacity. If capacity is unknown, do not claim the bin is capacity-validated. |
| Fast movers | Prefer pickable bins closer to packing for high-throughput items, subject to the location plan. |
| Heavy items | Prefer low-level floor/low bins for heavy items; do not suggest high shelving. |
| Existing stock | Prefer the same item's current bin when consolidation is allowed and the bin remains eligible. |
| Zone and walk path | Rank by configured warehouse zone/aisle sequence to reduce travel. |
| Tie-break | Use a stable bin sequence and show the reason for the suggestion. |

The suggestion is guidance, not an inventory movement. The operator scans the destination bin and confirms item, source, quantity, and destination. Wrong/inactive/incompatible bins block confirmation. A manager may choose another allowed bin with a reason; an override cannot bypass safety, compatibility, or access restrictions.

### 3.3 Putaway posting

On confirmation, verify the source receiving bin has sufficient unreserved stock and the destination is allowed. Write paired ledger entries (source negative, destination positive) and update both balance rows atomically. A retry of the same confirmation must return the original result, not make another transfer.

## 4. Outbound: order to shipment

1. Import/create an order from API or CSV. Validate item identifiers and quantities, customer/external order identity, and duplicate source IDs. Invalid CSV rows are reported before release.
2. Allocate stock by item and eligible bin. Reservation is performed transactionally under row locks or conditional updates.
3. Generate pick tasks ordered by the configured bin sequence (zone/aisle/bay/level/bin), not lexical bin code alone.
4. Picker scans bin, then item; compare both with task expectation. Confirm quantity in the base UOM. A short pick or damage enters an exception path and does not silently reduce order quantity.
5. Pack station scans each item and verifies quantity against the order. The order cannot move to `PACKED` with missing/extra/unverified lines unless an authorized, documented partial-shipment policy applies.
6. Print packing slip/shipping label through the configured printer/carrier workflow. Printing failure does not mark the order shipped.
7. On dispatch confirmation, consume reservations, post negative shipment ledger movement(s), store carrier/tracking information, and mark shipped in a single transaction. Make the action idempotent.

## 5. Scan-to-confirm rules

| Operation | Required scan(s) | Server validation | Success effect |
| --- | --- | --- | --- |
| Receive | PO/receipt, item barcode/SKU | Source is open; line belongs to receipt; barcode maps to item; quantity and tracking data valid | Receipt line and inbound ledger movement commit once |
| Putaway | Item (or active receipt line), destination bin | Item/source/destination match task; source has enough quantity; destination active and compatible | Paired transfer ledger rows and two snapshots commit |
| Pick | Expected source bin, item barcode/SKU | Both match task; order active; quantity is remaining and reserved/available | Pick progress records once; ledger transfer only if stock physically moves to staging |
| Pack | Order, item barcode/SKU | Item belongs to order and packed quantity does not exceed remaining quantity | Pack verification recorded; not a physical movement unless location changes |
| Cycle count | Count bin, item barcode/SKU | Both are in active count scope; quantity valid; duplicate line not accidentally counted twice | Count result saved; variance awaits review |
| Lookup | Item barcode/SKU or bin barcode | Unique active match | Read-only stock result; no ledger change |

General scan rules:

- Normalize only harmless formatting supported by the barcode standard; do not silently rewrite an identifier into a different SKU.
- If barcode and typed SKU are both present, they must identify the same item.
- Unknown, ambiguous, inactive, or mismatched scans block the action and preserve context.
- Compare `expected` and `scanned/entered` quantity visibly before final confirmation.
- Debounce scanner suffixes and disable the primary button during submission. Use a stable idempotency key for retried writes.
- A repeated scan of an already accepted line is not another quantity by default. Require an explicit additional-quantity action or line reopen with authorization.
- Manager override requires manager authentication, a reason, actor/time, expected/scanned values, and audit event. It cannot authorize unknown SKU identity or make an inactive/unsafe bin eligible.

## 6. Discrepancies and manager overrides

### Discrepancy handling

| Discrepancy | Default behavior | Resolution |
| --- | --- | --- |
| Short receipt | Record actual received quantity and outstanding quantity; leave PO/receipt partially open | Supplier follow-up, backorder, or manager-authorized short close |
| Over receipt | Record actual quantity and discrepancy; apply configured tolerance | Within tolerance may receive; beyond tolerance holds excess in receiving/quarantine pending manager approval |
| Damaged receipt | Receive into non-pickable quarantine/damage bin with condition and evidence note | Manager disposition: return, scrap, or release after inspection; scrap posts an adjustment |
| Wrong item received | Do not receive against the expected SKU | Create an exception line/return disposition or manager-approved correction to the proper item; retain original scan and reason |
| Short pick | Record picked quantity and reason; block/hold affected line | Recount source bin, reallocate another bin, substitute only with order approval, or partial-fulfill under policy |
| Wrong item/bin scan | Reject scan; no stock/order progress changes | Rescan correct label; if label/master data is wrong, manager resolves through an auditable correction |
| Damaged stock found during picking/count | Do not ship; move to quarantine with transfer ledger entries | Approved scrap/write-off or inspected return-to-stock |
| Expired/near-expiry lot | Block expired lot by default; warn according to configured shelf-life rule | Manager cannot bypass legal/customer restrictions; permitted exception needs reason and audit |
| Duplicate receipt/pick/ship request | Replay original idempotent result | If payload differs for same idempotency key, return conflict; never apply twice |

### Manager override controls

- Require separate manager permission and preferably re-authentication on the device.
- Capture manager identity, operator identity, reason code, notes, original expected value, actual value, and reference document.
- Never allow self-approval for an adjustment or count variance except under an explicit documented single-person policy.
- Do not allow override to create negative stock, accept an unknown SKU, bypass lot/serial traceability requirements, violate safety restrictions, or mark unverified goods shipped.
- Where policy permits an exception (for example, alternate compatible bin or bounded PO overage), show the exact effect before approval.
- Every override either posts through the normal ledger service or leaves inventory unchanged; no privileged direct quantity editing.

## 7. Reserved quantity and available stock

For each stock dimension (item, bin, lot, and any required serial dimension):

```text
available_to_promise = qty_on_hand - qty_reserved
qty_reserved = sum(active order allocations for that inventory dimension)
```

Rules:

1. `qty_on_hand` changes only through ledger-backed physical movements.
2. Reservation creation locks/conditionally updates eligible inventory rows, verifies `available_to_promise >= requested_qty`, writes allocation records, and updates the reserved snapshot atomically.
3. A reservation is not a physical stock movement and does not create a stock-ledger row. It is an audited commitment.
4. Pick tasks consume only the order's active allocations. A transfer to a packing/staging location carries the reservation to the new dimension atomically.
5. Cancellation/reallocation releases unused reservation. Shipment consumes shipped reservation and decreases physical on-hand once.
6. Never allow `qty_reserved > qty_on_hand` for a dimension. Reconcile reservation totals to active allocation records.
7. Simultaneous allocations/picks use row locks or atomic conditional updates; a stale screen value is never authority to reserve stock.
8. Backorders remain unallocated. They must not be hidden as a successful full allocation.

## 8. Lot, expiry, and FEFO

- Apply lot/expiry rules only to items configured for tracking. Do not invent a lot number or expiry for untracked goods.
- Store expiry consistently with the lot and include lot in receipt, bin balance, ledger, count, reservation, pick, and shipment records.
- If FEFO is enabled, allocate and suggest the eligible lot with the earliest expiry first, then use bin sequence as a tie-breaker.
- Exclude expired stock from allocation by default. Configure a minimum remaining shelf-life threshold where customer requirements demand it.
- If the earliest lot lacks enough quantity, allocate from the next eligible lot(s) and show the lot split to the picker/packer.
- Do not mix lots in one scan confirmation unless the operator confirms each lot separately.
- For serial-tracked items, verify the specific serial on receipt, pick, pack, and ship. Each serialized unit movement has quantity `+1` or `-1`; serial identity cannot be duplicated or silently reassigned.
- FEFO is conditional: if the business does not track expiry or requires another rotation rule, use the configured rule and document it.

## 9. Edge-case rules

| Edge case | Required behavior |
| --- | --- |
| Partial receipt | Record received and outstanding quantities separately; post only actual accepted quantity; leave remainder open/backordered or explicitly short-close it. |
| Duplicate scan | Same request/key returns the original result. A repeated deliberate scan requires an explicit add-quantity action; it must not double count by accident. |
| Wrong item scan | Reject; do not update receipt, pick, pack, count, reservation, or ledger. Show expected versus scanned item. |
| Short pick | Record the short quantity and reason; block/hold affected work, release or revise allocation safely, then recount/reallocate/partial-fulfill by policy. |
| Negative stock attempt | Reject transaction and rollback ledger, snapshot, and document changes. No ordinary manager override. |
| Damaged goods | Quarantine in a non-pickable bin. If later scrapped, post a reason-coded negative adjustment; do not both deduct at quarantine and deduct again at scrap. |
| Network drops during confirmation | Keep command pending/unknown; retry with the same idempotency key and query status. Never issue a fresh key until result is known. |
| Cancellation after receipt | Reverse accepted stock to the correct return/staging disposition; retain original receipt/ledger rows. |
| Order cancellation after allocation | Release unpicked reservations. If already physically picked to staging, transfer back to a valid stock bin with ledger entries. |
| Shipment retry | A unique shipment/document-line key prevents a second deduction. Return the existing shipment result. |
| Item/bin deactivation during open work | Block deactivation or require work to be reassigned/resolved; preserve history. |
| Count concurrent with movement | Prefer a short count lock on the target bin. If movements must continue, capture count time and reconcile all intervening ledger movements before approving a variance. |
| Receipt of unplanned item | Put in an exception/quarantine state; do not silently create a SKU or add it to an unrelated PO line. |
| Return authorization receipt | Link to RMA; inspect and classify as restockable, quarantine, or scrap. Only restockable units become allocatable after putaway/inspection. |
| Transfer order in transit | Treat dispatch and receipt as distinct events with an in-transit location/status; do not show stock as available at destination before receipt. |

## 10. Cycle count policy and variance posting

1. Generate count tasks weekly for designated high-value/critical SKUs and monthly for remaining active SKUs.
2. Capture a baseline quantity and count scope. Prefer a short bin lock during the count for the MVP.
3. Operator scans bin/item and enters physical quantity. Blind counts hide expected quantity until submission where appropriate.
4. A mismatch enters `REVIEW`; optional recount is independent and retained alongside the first count.
5. Manager approves/rejects the variance with a reason. Approval posts one `CYCLE_COUNT` or `ADJUST` ledger movement for the difference and updates the snapshot atomically.
6. Reconciliation checks ledger sums against snapshots and reserved quantities against active allocations; discrepancies are corrected by approved movements, not direct updates.

## 11. Operational acceptance checks

- A repeated receipt, pick, putaway, or shipment submission never posts twice.
- Wrong item/bin scans leave stock and task progress unchanged.
- A transfer's source and destination ledger deltas net to zero.
- Available stock falls on reservation; on-hand does not.
- Shipment reduces on-hand and consumes reservation exactly once.
- Expired lots are not allocated when expiry blocking is enabled.
- Every adjustment, discrepancy resolution, and override has an attributable audit trail.
- Partial receipts, short picks, returns, and damaged goods remain visible until explicitly resolved.
