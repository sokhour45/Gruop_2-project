# Small-Warehouse WMS QA Test Cases

These are acceptance and integration test cases for the planned WMS workflows. The current Flask/SQLite application does not implement all of these capabilities; use this matrix when those features are introduced.

## Test conventions and fixture

- Run database-mutating cases against an isolated test database with a known ledger/balance baseline.
- Unless stated otherwise, use active SKU `SKU-100` / barcode `BC-100`, active pickable bin `A-01`, receiving bin `RCV-01`, staging bin `PACK-01`, manager `manager1`, and operator `operator1`.
- Use `Idempotency-Key` on retryable scan/order/ship requests. A repeated request with the same key and payload must return the original result, not apply the operation again.
- **Physical stock movement** means on-hand quantity changed; it must write stock ledger row(s) and update the balance snapshot in the same transaction. Reservation-only changes affect availability, not physical on-hand, and must update allocation/audit data without a physical stock ledger row.
- Verify persisted database state as well as the UI/API response. For every rejected operation, confirm that no partial stock, document, or task update was committed.
- Priorities: **P0** = stock integrity/security/go-live blocker; **P1** = required core workflow; **P2** = conditional/optional capability.

## Test cases

| ID | Scenario | Steps | Expected result | Priority |
| --- | --- | --- | --- | --- |
| BAR-01 | Correct SKU barcode scan | Open an active receipt/pick line for `SKU-100`; scan `BC-100`; submit valid quantity | Scan resolves to `SKU-100`; expected item is shown; operation proceeds only after matching bin/item/quantity checks; any physical movement writes its ledger entry once | P0 |
| BAR-02 | Barcode resolves to wrong SKU | Set task to expect `SKU-100`; scan barcode belonging to `SKU-200` | Clear mismatch shows expected and scanned items; action is blocked; task quantity, inventory, and ledger remain unchanged | P0 |
| BAR-03 | Duplicate scan event | Scan correct item and confirm; resend same request with same idempotency key and payload | Original successful result is returned; picked/received quantity and ledger row count do not increase a second time | P0 |
| BAR-04 | Duplicate physical scan with new key | Complete a line, then scan the same barcode again using a new request/key without selecting an explicit add-quantity action | UI does not silently add quantity; requires explicit additional-quantity workflow or reports line already complete; no unintended ledger posting | P1 |
| BAR-05 | Unknown barcode | Scan a barcode not assigned to an active item | Show “no match”; allow manual search if permitted; do not select a similar SKU or create stock/task changes | P0 |
| BAR-06 | Inactive SKU barcode | Scan barcode for an inactive item on a new receipt/pick | New operational action is rejected with inactive-item message; historical lookup remains available only per permission | P1 |
| REC-01 | Partial receipt | PO expects 10 units; receive 6 and confirm | Receipt records expected 10, received 6, outstanding 4; posts +6 to receiving/staging bin and one receipt ledger movement; receipt remains open/partial, not fully received | P0 |
| REC-02 | Complete remaining partial receipt | Continue REC-01; receive remaining 4 with a new line action | Total accepted becomes 10; ledger total across both receipt actions is +10; receipt moves to putaway/next valid state only when line/discrepancy rules are satisfied | P1 |
| REC-03 | Over-receipt within allowed tolerance | PO expects 10; configured tolerance allows +1; receive 11 and confirm | Actual 11 and overage discrepancy are recorded; posting follows configured tolerance; ledger and snapshot increase by 11 exactly once | P1 |
| REC-04 | Over-receipt beyond tolerance | PO expects 10; tolerance is +1; receive 12 | Excess is blocked or held pending manager approval per configuration; no unauthorized quantity becomes pickable; response explains limit | P0 |
| REC-05 | Discrepancy details required | Receive quantity different from expected and omit discrepancy type/reason | Confirmation is blocked; no ledger or quantity update; form identifies missing discrepancy fields | P1 |
| REC-06 | Discrepancy captured and audited | Receive short/damaged quantity with reason and note; confirm | Actual quantity and discrepancy are linked to receipt line; actor/time/reason are auditable; damaged units go to quarantine if configured; only accepted quantity posts | P0 |
| REC-07 | Lot and expiry capture | Receive lot-tracked item with lot number and valid expiry | Ledger and inventory dimension retain lot/expiry; lookup shows same values; duplicate receipt retry does not duplicate quantity | P1 |
| REC-08 | Invalid/missing tracked lot data | Receive lot-tracked item without lot number, or expiry earlier than configured policy permits | Confirmation is blocked or routed to explicit exception; no stock is posted to an untracked/invalid lot | P0 |
| PUT-01 | Suggested putaway bin is eligible | Receive stock into `RCV-01`; request suggestion for item with configured zone/weight/velocity rules | System suggests an active compatible bin and explains/uses configured ranking; suggestion alone does not move stock | P1 |
| PUT-02 | Confirm suggested bin by scan | Scan the suggested active destination bin and confirm item/quantity | Transfer posts equal-and-opposite ledger rows for source and destination; snapshot totals remain conserved; receipt putaway progress updates atomically | P0 |
| PUT-03 | Wrong bin scan | Task suggests `A-01`; scan another bin not on task | Confirmation is blocked; expected/scanned bin displayed; no ledger, balance, or putaway progress changes | P0 |
| PUT-04 | Manager override to alternate bin | Scan a valid alternate compatible bin and request override; manager authenticates and enters reason | If override policy permits, manager/actor/reason are recorded and transfer posts to alternate bin; otherwise action remains blocked; no silent bypass | P1 |
| PUT-05 | Destination bin over capacity | Enable bin capacity; set destination to capacity; attempt putaway that exceeds capacity | System rejects or suggests another eligible bin; no partial ledger/balance change | P2 |
| PUT-06 | Capacity feature disabled | Run PUT-01 with capacity configuration unavailable/disabled | System does not claim capacity validation; normal compatibility rules still apply | P2 |
| PICK-01 | Correct bin and item scan | Allocate 3 units from `A-01`; scan correct bin and `BC-100`; confirm 2 | Pick line records 2 once; reservation/remaining quantity updates correctly; if goods move to staging, paired ledger transfer is written; otherwise on-hand is not deducted before shipment | P0 |
| PICK-02 | Wrong item scan | Task expects `SKU-100`; scan `SKU-200` | Mismatch blocks confirmation; picked quantity, reservation, inventory, and ledger stay unchanged | P0 |
| PICK-03 | Wrong bin scan | Task expects `A-01`; scan another bin | Confirmation is blocked; correct expected bin is shown; no pick progress or stock change | P0 |
| PICK-04 | Short pick | Task requests 5; operator finds 3 and submits short-pick reason | Actual picked quantity is 3; remaining 2 are flagged/held for recount or reallocation; reservation for unpicked quantity is safely adjusted; no false full-pick status | P0 |
| PICK-05 | Pick quantity exceeds remaining/allocation | Remaining allocated quantity is 2; submit quantity 3 | Request is rejected; no stock or task changes; current allocatable quantity is returned to the user | P0 |
| PICK-06 | Manager override for pick exception | Operator scans an allowed alternate bin/item exception; manager authenticates and enters reason | Only configured exception is allowed; override actor/reason/expected/scanned values are audited; ledger posting follows normal transfer rules | P1 |
| PICK-07 | Manager override cannot bypass item identity | Scan unknown or wrong SKU and attempt override | Override is rejected; unknown identity cannot be accepted as expected item; no stock/task change | P0 |
| PACK-01 | Final pack verification success | Scan each expected order item and exact quantity | All lines show verified; order can transition to `PACKED`; no shipment deduction occurs until dispatch confirmation | P0 |
| PACK-02 | Wrong item at pack station | Order expects `SKU-100`; scan `SKU-200` | Pack line is rejected with expected/scanned details; order remains un-packed; no shipment ledger movement | P0 |
| PACK-03 | Missing item at pack completion | Verify all but one order line; tap complete packing | Completion is blocked; missing SKU/quantity is listed; order remains in pick/exception state | P0 |
| PACK-04 | Overpacked quantity | Expected quantity is 2; scan/enter 3 | Excess is rejected; packed quantity cannot exceed ordered quantity; no shipment status or movement | P0 |
| PACK-05 | Label/packing-slip printing success | Complete pack verification and request print | Correct order/reference and item summary print; print event/status is recorded as configured; order is not marked shipped until dispatch | P1 |
| PACK-06 | Label printer unavailable | Simulate printer offline/error during print | Clear print failure and retry/manual path shown; pack/shipment data remain intact; no false “label printed” or “shipped” status | P1 |
| INV-01 | Adjustment with reason | Authorized operator requests +2 or -1 with reason code and note; manager approval required by threshold | Request is pending and does not change on-hand until approved; approval posts signed adjustment ledger row and snapshot atomically; request, approver, reason, and time are auditable | P0 |
| INV-02 | Adjustment missing reason | Submit adjustment without reason code or required note | Validation error; no adjustment posting, balance change, or success response | P0 |
| INV-03 | Prevent negative stock | Bin has 1 unit; request adjustment or shipment movement of -2 | Transaction fails with insufficient-stock error; no ledger row or snapshot/document partial update; balance remains 1 | P0 |
| INV-04 | Reservation reduces available only | On-hand 10, reserved 0; allocate 4 to open order | On-hand remains 10; reserved becomes 4; available becomes 6; allocation and audit event are created; no physical stock ledger row is created | P0 |
| INV-05 | Reservation cannot oversell | On-hand 5, reserved 3; request reservation of 3 | Request is rejected (only 2 available); reserved remains 3; no allocation is created | P0 |
| INV-06 | Release reservation | Release an active allocation of 2 | Reserved decreases by 2 and available increases by 2; on-hand and physical ledger remain unchanged; release is auditable | P1 |
| CNT-01 | Cycle count variance capture | Count line expected 10; operator submits 8 | Count result records expected 10/counted 8 and variance -2; inventory remains 10 pending review; counter/time preserved | P0 |
| CNT-02 | Approve count variance | Manager approves CNT-01 variance with reason | One -2 cycle-count/adjustment ledger movement posts; on-hand becomes 8 atomically; approval and count references are linked | P0 |
| CNT-03 | Reject or recount variance | Manager rejects variance or requests recount | No ledger posting; count remains visible with rejection/recount status and reason; existing stock remains unchanged | P1 |
| CNT-04 | Count posting retried | Resubmit approval with same idempotency key | Existing result returned; only one ledger row and one balance change exist | P0 |
| RBAC-01 | Operator cannot edit item master | Sign in as Operator; call item create/update/deactivate endpoint directly | Server returns forbidden; item data is unchanged; denied action is logged if security-event logging is enabled | P0 |
| RBAC-02 | Operator cannot edit bin master | Sign in as Operator; call location update/deactivate endpoint | Server returns forbidden; location and inventory remain unchanged | P0 |
| RBAC-03 | Operator cannot approve adjustment | Sign in as Operator; call approval endpoint for pending adjustment | Server returns forbidden; adjustment remains pending; no ledger row is posted | P0 |
| RBAC-04 | Requester cannot self-approve | Manager requests adjustment, then attempts to approve own request | Approval is rejected unless a documented single-person exception policy is configured; no posting occurs by default | P0 |
| LED-01 | Every physical receipt creates ledger row | Confirm a receipt of 5 units | Exactly one positive receipt ledger entry is linked to receipt line; balance snapshot increases by 5 in same committed transaction | P0 |
| LED-02 | Transfer ledger is balanced | Transfer 4 units from `A-01` to `B-01` | Two entries share transfer reference: -4 at source and +4 at destination; total on-hand across bins is unchanged | P0 |
| LED-03 | Ledger is immutable | Attempt application-level update/delete of posted ledger row | Database/application rejects mutation; correction is made only through linked compensating movement | P0 |
| LED-04 | Ledger and snapshot reconcile | Run reconciliation for item/bin/lot dimensions after receipt, transfer, pick-to-stage, adjustment, and shipment | Grouped ledger deltas equal `qty_on_hand`; any mismatch is reported, not silently corrected | P0 |
| LED-05 | Failed transaction rolls back both stores | Force ledger insert failure after snapshot update within posting transaction | Entire operation rolls back; neither snapshot nor document state changes; no success response | P0 |
| CON-01 | Two pickers compete for same stock | Bin has 5 available; two users simultaneously attempt to reserve/pick 4 each | At most 5 units are allocated/confirmed; one request succeeds fully and the other conflicts/shorts; no negative balance or duplicate movement | P0 |
| CON-02 | Concurrent reservations serialize correctly | Two users simultaneously reserve the last 2 units for different orders | Only one 2-unit reservation succeeds; other receives insufficient-availability conflict; on-hand unchanged and reserved never exceeds on-hand | P0 |
| CON-03 | Duplicate order submission | Submit same external order twice with same source ID/idempotency key | One order and one set of lines/reservations exist; second submission returns existing order result | P0 |
| CON-04 | Duplicate order ID with changed payload | Submit same external order ID with a different item/quantity payload | Request returns conflict or enters explicit update workflow; it does not silently overwrite an allocated/in-progress order | P0 |
| CON-05 | Shipment request races with duplicate retry | Submit shipment twice concurrently with same idempotency key | One shipment and one set of negative ledger movements exist; both callers receive consistent final result | P0 |

## Recommended execution order

1. Run all P0 cases against PostgreSQL integration tests before pilot/go-live.
2. Run P1 cases before enabling the related workflow in production.
3. Run P2 cases only when optional capacity configuration is implemented.
4. Repeat scan, network-timeout, retry, and concurrency cases on the actual Android/scanner setup and expected database isolation/locking configuration.
5. After any failed stock-integrity test, verify ledger, inventory snapshot, reservations, document state, and audit records—not only the HTTP/UI response.
