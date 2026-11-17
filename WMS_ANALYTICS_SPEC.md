# Small-Warehouse WMS Analytics and KPI Specification

## 1. Reporting principles

- Reports are read-only views over operational documents, the append-only stock ledger, count records, and task events. A report never edits inventory.
- Always show the selected warehouse, time zone, filters, and “as of”/generation time. Use one agreed business time zone for display and UTC for stored timestamps.
- Distinguish **on-hand**, **reserved**, **available**, and **inbound expected** quantities.
- Use a stable report definition and denominator. Do not compare results across periods if the definition changed without labeling the change.
- A KPI with missing or insufficient source data is **Not available** or **Insufficient sample**, not zero or an inferred value.
- Targets below are starting operational targets. Agree on counting tolerance, exclusions, and review cadence with the warehouse owner.

## 2. Required reports

| Report | Purpose | Filters | Recommended columns | Frequency | Primary role |
| --- | --- | --- | --- | --- | --- |
| Stock on hand | Locate and reconcile inventory at item/bin/lot level and total | Warehouse, SKU/barcode, description, bin/zone, lot, expiry, active/zero-stock toggle, as-of time | SKU, description, UOM, bin, lot, expiry, on-hand, reserved, available, total by SKU, last movement, reorder point | Live lookup; daily review/export | Manager; Operator for lookup; Viewer/Owner read-only |
| Stock movement history | Explain each change from the immutable ledger | Warehouse, date/time range, SKU, bin, lot/serial, movement type, reference document, actor, request ID | Ledger ID, timestamp, type, SKU, bin, lot/serial, signed quantity, reference type/ID, user, reason, reversal link | Live; daily exception review; on demand | Manager, Admin; Operator limited operational scope; Viewer if permitted |
| Low-stock and reorder alerts | Identify items needing replenishment | Warehouse, supplier, category, alert status, SKU, min stock, available threshold, include inactive toggle | SKU, description, supplier, on-hand, reserved, available, min stock, open PO qty/date, suggested action, days below threshold | Daily; optionally refreshed after movement | Manager; Admin |
| Open receipts | Track inbound work and supplier discrepancies | Warehouse, status, supplier, PO/return/transfer ref, expected/received date, overdue, discrepancy | Receipt, source reference/type, supplier, status, lines expected/received, outstanding qty, discrepancy count, receiving age, putaway progress, owner | Live queue; daily review | Receiving Operator, Manager |
| Open orders | Track allocation and fulfillment risk | Warehouse, status, priority, customer/source, age, ship-by, shortage, picker | Order/source ref, customer, created/release time, line count, ordered/allocated/picked/packed qty, shortage, status, assigned picker, ship-by | Live queue; start/mid/end of shift | Picker/Operator; Manager |
| Cycle count variance | Resolve discrepancies and monitor inventory accuracy | Warehouse, count date, SKU, bin, lot, counter, status, variance reason, approval status | Count/task ID, item/bin/lot, expected qty, counted qty, absolute and percentage variance, unit cost/value variance, counter, recount, approver, ledger adjustment ref | After each count; weekly review | Manager; Admin |
| Picker productivity | Understand throughput and workload balance | Date/time range, warehouse, picker, shift, order priority/type | Picker, active pick hours, lines completed, lines/hour, orders packed, pack hours, orders/hour, short/mismatch count, pick accuracy, sample size | Daily/weekly; review with context | Manager; Operator for own/assigned stats |
| Inventory turnover and dead stock | Identify slow-moving or excess inventory | Period, warehouse, SKU/category/supplier, cost basis, last movement, stock status | SKU, average inventory value/qty, shipped qty/value, turnover, days on hand, last demand/movement date, current qty/value, dead-stock age | Monthly; purchasing review | Manager; Viewer/Owner read-only |
| Pick accuracy | Find wrong-item/quantity/bin errors and process trends | Date range, warehouse, picker, SKU, order, error type, resolution | Total pick lines, correct lines, wrong-item/bin/qty exceptions, corrected lines, line accuracy %, order-perfect rate, picker, order | Daily/weekly | Manager; Operator own/assigned details |
| Receiving accuracy | Monitor supplier and receiving quality | Date range, warehouse, supplier, PO, SKU, discrepancy type, receiver | Receipt lines/units expected, accepted, short, over, damaged, wrong item, exact-match rate, receiver, discrepancy value | Per receipt; weekly supplier review | Manager; Receiving Operator for own work |

### Report behavior details

- **Stock totals:** group item/bin/lot and show a distinct SKU total. Do not sum `qty_reserved` into physical on-hand. Exclude inactive items/bins by default but allow an authorized historical/inactive filter.
- **Movement history:** use the ledger as its source; show positive and negative legs of a transfer together. Never recalculate or rewrite historic ledger rows to “correct” the report.
- **Reorder alerts:** default trigger is `available <= min_stock`; display open purchase order quantities separately. Do not silently include future/inbound stock in the available balance.
- **Open work:** cancelled/closed/shipped records are excluded by default. Make blocked, overdue, short, and pending-approval work prominent.
- **Count variance:** retain original count and recount. Show both unit and cost valuation only when an approved unit-cost basis exists.
- **Productivity:** show accuracy and exceptions alongside speed; exclude breaks and paused time only if the task event model reliably records them. Never rank users on raw speed alone.

## 3. KPI definitions

Use the warehouse's configured UOM and a documented tolerance. For line-based accuracy, count a line as correct only when the verified item and quantity match the expected value within the agreed tolerance. Also report absolute unit variance so aggregation cannot hide large errors.

| KPI | Formula | Target / cadence | Notes and required data |
| --- | --- | --- | --- |
| Inventory accuracy | `count lines within tolerance ÷ count lines completed × 100` | **>98%**; review weekly and monthly | Show line sample size and unit variance. For financial/high-risk SKUs, also report exact-match accuracy. Requires expected snapshot and approved physical count result. |
| Dock-to-stock time | `stock-available timestamp − dock-arrival timestamp` | Establish baseline; reduce median and 90th percentile | Define dock arrival as first recorded receipt arrival; stock-available is accepted stock put away in an eligible pickable bin. Report median/P90, not only average. |
| Pick accuracy | `correct verified pick lines ÷ total verified pick lines × 100` | **>99.5%**; review daily/weekly | A correct line has correct item, source bin where required, and quantity. Report order-perfect rate separately. Requires expected task and scan/exception events. |
| Order cycle time | `shipment-confirmed timestamp − order-accepted/released timestamp` | Establish baseline; compare median/P90 by service class | Use the same start event and shipping cutoff policy in each period; separate held/awaiting-customer time where reliably captured. |
| Inventory turnover by SKU | `period COGS for SKU ÷ average inventory value for SKU` | Set by category/business; monthly | Requires a consistent unit cost/COGS basis. Annualize only when clearly labeled: `period turnover × (365 ÷ days in period)`. Do not substitute sales price. |
| Days on hand (supporting) | `average inventory value ÷ period COGS × days in period` | Category-specific; monthly | Undefined when COGS is zero; show `No demand/COGS` rather than infinity. Quantity-based version must use a consistent demand UOM. |
| Dead stock | On-hand stock with no qualifying demand movement for configured age (default candidate: 90 or 180 days) | Review monthly | Define qualifying movement as customer shipment/consumption, not internal transfer or count adjustment. Exclude seasonal/strategic/quality-held stock by an explicit reason. |
| Stock adjustment frequency | `posted adjustment count ÷ period` and optionally `adjustment lines ÷ total movement lines × 100` | Track from day one; investigate trend | Separate cycle-count corrections, damage/write-off, and other adjustments. Pending/rejected requests are not posted adjustments. |
| Stock adjustment value | `sum(abs(qty_change × approved unit cost))` | Track from day one; review monthly | Use a documented valuation date/basis. Absolute value measures gross correction magnitude; also show signed net value to indicate direction. |
| Receiving accuracy | `receipt lines matching accepted expected quantity/item within tolerance ÷ eligible receipt lines × 100` | Establish baseline; supplier review weekly/monthly | Exclude cancelled lines and explicitly designated no-PO receipts from the PO accuracy denominator; report them separately. Include wrong item, damage, short, and over counts. |
| Lines picked per hour | `verified pick lines ÷ active pick labor hours` | Baseline by workflow; review weekly | Define active time from task start/pause/complete events. Pair with pick accuracy, task complexity, and short-pick rate. |
| Orders packed per hour | `orders with pack verification completed ÷ active pack labor hours` | Baseline by workflow; review weekly | Report order/line mix and accuracy; partial packs do not count as completed orders. |

### Measurement rules

1. Define the inventory count tolerance before go-live (for example, exact for each/serial goods and agreed decimal tolerance for bulk goods).
2. Freeze KPI definitions and timestamp events before comparing periods. If a definition changes, annotate the report.
3. Capture denominator, sample size, exclusions, and period on every accuracy KPI.
4. Do not calculate turnover, adjustment value, or stock value from a sales/list price. If cost data are not available, show quantity turnover or mark value metrics unavailable.
5. Use UTC for storage and the site's time zone for shift/day reporting; define how daylight-saving transitions are handled.

## 4. Manager dashboard recommendations

### Desktop layout

```text
┌───────────────────────────────────────────────────────────────┐
│ Warehouse / date range / data refreshed                       │
├──────────────┬──────────────┬─────────────┬───────────────────┤
│ Stock value  │ Low stock    │ Open receipts│ Open orders      │
├──────────────┴──────────────┴─────────────┴───────────────────┤
│ Inventory accuracy        │ Pick accuracy                    │
│ >98% + sample + trend     │ >99.5% + sample + trend           │
├───────────────────────────┬───────────────────────────────────┤
│ Needs attention           │ Inbound / outbound queue          │
│ approvals, variances,     │ due work, shortages, discrepancies │
│ damaged/expired stock     │                                   │
├───────────────────────────┴───────────────────────────────────┤
│ Dock-to-stock, cycle time, adjustments, productivity trends   │
└───────────────────────────────────────────────────────────────┘
```

### Widget behavior

- KPI cards link to the filtered report behind the number.
- Show target, actual, trend arrow, sample size, and latest refresh time. Avoid red/green-only encoding.
- “Needs attention” prioritizes pending approvals, receipt discrepancies, blocked picks, expired/near-expiry stock, and count variances.
- Open receipts/orders show the oldest and most urgent work first, with status, age, assigned person, and next action.
- Accuracy cards show the latest completed count/pick window and a trend; do not imply real-time accuracy if no recent validation event exists.
- Use charts only where trend is meaningful; keep exact values and definitions available in a table or accessible text.

## 5. Using analytics to improve operations

### Slotting

- Combine pick frequency, lines picked, travel sequence, and item dimensions/weight to identify fast movers that should be closer to packing.
- Use heavy-item/low-shelf safety rules as hard constraints before ranking by travel reduction.
- Compare pick time and wrong-bin rate before/after a slot change; do not move items solely because of raw order count if quantities, size, or replenishment burden differ.
- Track replenishment travel and congestion where possible so a “faster pick” location does not create receiving/replenishment bottlenecks.

### Purchasing and replenishment

- Review available stock, reorder point, recent demand/shipments, lead time, open PO quantities, and supplier accuracy together.
- Use low-stock alerts as review prompts, not automatic purchase orders, until lead-time and demand data are trustworthy.
- Identify dead/slow stock and supplier overage/damage patterns before buying more.
- Keep accounting valuation/cost ownership in the ERP when applicable; reconcile WMS physical quantities with the purchasing system rather than making the WMS a financial ledger.

### Error reduction

- Group wrong-item/bin scans and short picks by location, SKU, shift, task type, and label age to find root causes.
- Use receiving discrepancy reports to identify supplier packing/label issues and improve PO/unit-of-measure setup.
- Review cycle-count variances alongside recent ledger movements to distinguish process errors, missed scans, and data/master errors.
- Pair productivity with accuracy and exception rate; coach on workflow or slotting problems rather than incentivizing speed that encourages scan bypass.
- Use adjustment reasons consistently and review adjustment frequency/value trends before adding more approval bureaucracy.

## 6. Data prerequisites and day-one checklist

| Data needed | Why it matters | Minimum collection |
| --- | --- | --- |
| Ledger timestamp, actor, item, bin, signed quantity, movement type, reference | Stock and movement reports, adjustments | Required for every physical movement |
| Receipt arrival, first scan, accepted, putaway-complete timestamps | Dock-to-stock | Capture with clear event definitions |
| Expected line and barcode/item/bin scan results | Pick and receiving accuracy | Store accepted and rejected scan/exception events |
| Order accepted/released, pick, pack, shipment timestamps | Order cycle time and productivity | Store lifecycle event times and task assignments |
| Count baseline, actual count, counter, approval, adjustment link | Inventory accuracy and variance reports | Retain original and recount values |
| Active reservation/allocation records | Available stock and overselling prevention | Reconcile against reserved snapshot |
| Unit cost/valuation source and effective date | Stock value, turnover, adjustment value | Import from the agreed ERP source or mark value reports unavailable |
| Item reorder threshold and supplier/lead time where known | Reorder alerts | Configure threshold; avoid fabricated lead-time assumptions |

Start capturing these events from day one, even if early reports show insufficient sample. Accurate baselines are more valuable than polished dashboards built from incomplete timestamps.
