# Small-Warehouse WMS Implementation Roadmap

> **Scope baseline:** [WMS_PROJECT_PLAN.md](WMS_PROJECT_PLAN.md) is the updated source of truth for module priorities, phase boundaries, workflows, backlog, and KPIs. This roadmap remains the detailed pilot, training, change-management, and go-live checklist; align its dates and deliverables to the updated plan before scheduling.

## 1. Planning assumptions and governance

This roadmap uses the project's planning baseline: one warehouse, about 300 active SKUs, about 50 orders/day, and 3–6 staff. The phase durations are indicative; do not advance because a calendar date arrived if the phase exit criteria are not met.

| Role | Accountability |
| --- | --- |
| Executive sponsor / owner | Confirms system-of-record policy, budget, scope, risk tolerance, and go-live decision |
| Project lead | Owns scope, timeline, decisions, dependencies, communications, and readiness review |
| Warehouse manager | Process owner; approves bin layout, exceptions, roles, count results, and operational acceptance |
| Admin / technical lead | Configures app/data, imports, permissions, backups, integrations, monitoring, and recovery |
| Receiving champion | Tests and coaches PO/return receiving, discrepancies, and putaway |
| Picking/packing champion | Tests and coaches pick, pack, shipment, and return workflows |
| All operators | Validate real tasks, report friction/labels/network problems, follow scan and exception procedures |

In a small team, people may hold multiple roles, but approval and control checks should remain independent where practical. In particular, avoid self-approval of material stock adjustments.

## 2. Timeline and phase gates

| Phase / timing | Milestones | Deliverables | Accountable owner | Exit gate |
| --- | --- | --- | --- | --- |
| **0. Prepare / weeks 1–2** | Confirm process and system ownership; walk the warehouse; measure Wi-Fi; inventory data cleanup; select pilot area and hardware | Signed process map, data dictionary, SKU/bin labeling plan, baseline count, risk/issue list, test cases, backup/cutover/rollback plan | Project lead + Warehouse manager | Source of truth, scope, bin structure, device plan, and pilot baseline approved |
| **1. Inventory Digitization / months 1–2** | Label SKUs/bins; configure master data; validate opening balances; deploy scan receiving and putaway; enable stock lookup/low-stock report; train pilot; reconcile and expand | Clean item/bin master, opening ledger/balance reconciliation, labels, receiving/putaway flow, on-hand lookup, low-stock alerts, operator guides, support/runbook | Warehouse manager (process) + Admin/technical lead (system) | Pilot receipts and putaways reconcile; target book-to-physical accuracy agreed and achieved; backup restore proven; manager approves retire/limit Excel |
| **2. Process Standardization / months 3–5** | Stabilize phase 1; release guided picking and scan verification; launch count cadence; standardize returns; introduce basic productivity tracking; train all shifts | Pick task workflow, cycle count calendar/task process, returns disposition procedure, scan exception rules, productivity baseline, updated training cards | Warehouse manager + Picking/packing champion | Representative orders complete scan-to-ship; count variances are approved/traceable; no unresolved critical defects |
| **3. Data-Driven Optimization / months 6–11** | Establish data-quality baseline; analyze turnover and errors; run controlled slotting pilot; measure travel and accuracy before/after; approve improvements | Turnover/dead-stock report, error pareto, fast-mover recommendations, dynamic slotting suggestions, pilot evaluation and rollout decisions | Warehouse manager + Project lead; Admin supports analysis | Improvements demonstrate measured benefit without degraded accuracy, safety, or replenishment performance |

### Phase timing and sequencing

- Phase 1 is 1–2 months; Phase 2 is 2–3 months after its gate; Phase 3 is 3–6 months after its gate. Sequential delivery therefore spans roughly 6–11 months. Some preparation and measurement can overlap when it does not compromise phase gates.
- The ranges describe elapsed time, not a promise that all phases fit within six months. Data cleanup, hardware delivery, vendor integration, or Wi-Fi remediation may extend the plan.
- Keep integration scope CSV/manual during the pilot unless an existing integration is a hard launch dependency. Avoid coupling go-live to a broad ERP/carrier integration.

## 3. Phase plans

### Phase 0 — Prepare

**Milestones and deliverables**

1. Observe current receiving, putaway, lookup, picking, returns, and count processes on the floor.
2. Decide and document the system of record for item identifiers, physical on-hand, cost/financial valuation, customer orders, and suppliers.
3. Clean SKU data: unique SKU/barcode, description, base UOM, active state, reorder level, and tracking requirements.
4. Define warehouse code, zones, bin naming/sequence, receiving/staging/quarantine/packing locations, and pickable status.
5. Physically walk Wi-Fi and scanner coverage in receiving, aisles, packing, and dispatch.
6. Select a pilot area and representative SKUs, including fast/slow movers, bulky/heavy items, and any tracked lots/expiry.
7. Baseline a physical count, adjustment frequency, receiving time, and current order accuracy using known data; mark unavailable metrics as baseline-needed.

**Owners:** Project lead coordinates; manager validates process/layout; admin validates data and deployment; champions validate real work.

**Gate:** No production setup until identifiers, location labels, system-of-record ownership, and opening-count approach are agreed.

### Phase 1 — Inventory Digitization (1–2 months)

**Milestones**

1. **Master data ready:** De-duplicate and import active SKUs, barcode assignments, UOMs, reorder levels, and locations.
2. **Labels installed:** Print and test SKU/bin labels at real scan distances; replace damaged or ambiguous labels.
3. **Opening balances reconciled:** Count pilot stock by SKU/bin; load through explicit opening-balance entries; compare ledger totals and stock snapshot; record unresolved variances.
4. **Receive/putaway pilot:** Receive against an expected PO/reference, scan item and quantity, capture discrepancy, scan destination bin, confirm putaway.
5. **Lookup and alerts:** Search/scan item or bin; show stock by location and low-stock threshold. Clearly distinguish on-hand, reserved (if enabled), and available.
6. **Expand by zone:** Roll out to remaining locations only after pilot exit criteria pass.

**Deliverables**

- SKU/barcode register and bin map, including inactive/quarantine/staging bins.
- Receiving and putaway SOP, discrepancy reason codes, and support escalation.
- Opening count and reconciliation record.
- Low-stock threshold ownership and report.
- Backup schedule, restore test, access roles, and rollback/cutover plan.

**Phase 1 acceptance**

- Every active SKU and operational bin has one approved, scannable identifier.
- Pilot receipt and putaway movements reconcile exactly between ledger and balance projection.
- A physical sample count meets the agreed accuracy target (use **>98%** as the initial target from the analytics plan unless the business sets another tolerance); exceptions are assigned and resolved.
- Wi-Fi and scanning pass at all pilot work points; operators know how to handle uncertain submissions.
- Excel is retired as the live quantity authority only after the manager signs off. Keep a read-only/archive copy per retention policy; do not maintain two editable stock masters.

### Phase 2 — Process Standardization (2–3 months)

**Milestones**

1. **Pick workflow:** Generate tasks sorted by actual bin sequence; scan bin and item; record full/short pick and mismatch exceptions.
2. **Pack verification:** Rescan items against order; print a packing slip/label through the approved printer workflow; confirm ship separately from pack.
3. **Cycle counts:** Define weekly high-value/critical and monthly remaining-item counts; assign counters; review, recount, and approve variances through ledger adjustments.
4. **Returns:** Require source reference/return authorization where applicable; classify as restockable, quarantine, return-to-supplier, or scrap.
5. **Productivity baseline:** Capture pick lines, orders packed, active task times where reliable, and accuracy/exceptions. Review trends, not raw speed rankings.
6. **Role and training review:** Confirm operators can do assigned work and managers can approve/reconcile without bypassing audit controls.

**Deliverables**

- Pick/pack SOP, short-pick and wrong-scan playbooks.
- Cycle-count calendar, count task ownership, variance approval rules.
- Returns disposition matrix and quarantine process.
- Weekly operational scorecard with sample sizes and definitions.
- Updated quick reference cards and training sign-off.

**Phase 2 acceptance**

- Representative orders complete from allocation through shipment without spreadsheet quantity edits.
- Wrong bin/item, duplicate scan, insufficient stock, and printer/network failure scenarios are tested.
- Count corrections require a reason and approval as configured, and produce traceable ledger entries.
- Returns do not make damaged/uninspected stock available for picking.
- Pick accuracy baseline is captured; target **>99.5%** is pursued after enough valid picks are sampled.

### Phase 3 — Data-Driven Optimization (3–6 months)

**Milestones**

1. Validate minimum data quality: reliable movement types, source references, task timestamps, unit costs where value is used, and count/pick exceptions.
2. Analyze turnover and dead stock by SKU/category; verify demand seasonality and open purchase orders before recommending changes.
3. Identify fast movers from shipped/picked history and compare current bin travel, safety, replenishment work, and congestion.
4. Produce simple slotting suggestions using eligibility constraints (capacity/compatibility, weight at low level, fast movers near packing).
5. Pilot a limited set of relocations; record before/after travel time, replenishment effort, pick accuracy, and congestion.
6. Review error-rate Pareto (wrong item, wrong bin, short pick, receiving discrepancy, damaged) and address systemic root causes such as labels, master data, packaging, or process.
7. Roll out only recommendations with measured benefit and manager approval.

**Deliverables**

- Monthly turnover/dead-stock and accuracy reports.
- Error trend/root-cause review with owners and corrective actions.
- Slotting recommendations with reason, affected bins/SKUs, and expected benefit.
- Before/after pilot scorecard and decision to retain, adjust, or revert changes.

**Phase 3 acceptance**

- Recommendations are explainable and respect safety, lot/expiry, bin compatibility, and replenishment constraints.
- A slotting pilot improves agreed travel/productivity measure without reducing accuracy or safety.
- No automatic relocation is performed; a manager approves changes and transfers are recorded.

## 4. Pilot team and rollout strategy

### Pilot team

Keep the pilot small but representative:

- One warehouse manager as process owner and decision-maker.
- One receiving champion who tests PO/return receipt, discrepancy, and putaway.
- One picker/packer champion who tests guided picking, packing, and shipping.
- One admin/technical lead responsible for setup, imports, permissions, backups, and issue triage.
- One or two additional operators to test normal shift/role variation.
- Project lead/sponsor attends readiness and go/no-go reviews.

For a 3–6 person warehouse, champions should be active operators, not only managers. Assign a backup champion for leave/shift coverage.

### Pilot boundaries

- Start with one aisle/zone or representative subset of SKUs and bins.
- Include at least one receipt, partial receipt, discrepancy, putaway, stock lookup, pick/pack/ship, return, and cycle count.
- Run controlled reconciliation against a physical count. Temporary parallel observation is acceptable; avoid two live, editable inventory sources.
- Log issues with severity, owner, due date, workaround, and go-live impact.
- Expand only when ledger/snapshot reconciliation, scan success, and user confidence meet exit criteria.

## 5. Change management and training

### Training package

| Material | Audience | Required content |
| --- | --- | --- |
| Operator quick-start guide | All operators | Login, scan focus, receive, putaway, pick, pack, lookup, and how to tell pending from committed |
| Quick reference cards | Receiving, picking/packing, counting | Scan order, expected-vs-actual, common errors, retry, escalation; laminate or mount near stations |
| Manager guide | Manager/owner | Approvals, exceptions, cycle-count review, reconciliation, low-stock, reports, audit |
| Admin runbook | Admin/technical lead | User access, import/export, backups/restore, device setup, incident response, release/rollback |
| Train-the-champion session | Champions | Demonstrate workflow, coach a new operator, collect feedback, reproduce common failure cases |

### Training approach

1. Explain why the WMS becomes the physical stock source of truth and which system owns cost/orders.
2. Demonstrate one task at normal pace; operators then practice in a test/pilot area.
3. Train exceptions explicitly: wrong scan, short/over receipt, short pick, damaged stock, network loss, duplicate submission, printer failure.
4. Require a short task sign-off for each operational role before unsupervised work.
5. Hold 10-minute daily pilot huddles during the first week; review blockers, label/Wi-Fi problems, and user feedback.
6. Publish release/change notes and keep one champion available per shift during cutover.

### Communication and adoption

- Announce the reason, timeline, pilot scope, and support contact before rollout.
- Tell staff what is changing and what is not (for example, the WMS owns physical on-hand; ERP keeps financial valuation).
- Provide a no-blame process for reporting errors; use metrics to fix processes, not to punish operators for system/label defects.
- Share pilot wins and resolved issues; ask operators to verify every new workflow before expansion.

## 6. Critical pitfalls and mitigations

| Pitfall | Impact | Prevention / response |
| --- | --- | --- |
| Over-engineering | Delays basic accuracy; creates workflows staff cannot sustain | Limit Phase 1 to master data, labels, receiving, putaway, lookup, alerts, and ledger integrity. Defer automation/advanced slotting until measured need. |
| Unclear system of record | Conflicting quantities across WMS, ERP, and spreadsheets | Publish ownership by data type. Choose one physical inventory authority; make other systems read/import or reconcile, not edit in parallel. |
| Poor physical organization | Scans resolve but items/bins are unsafe, ambiguous, or hard to find | Walk the site, define zones and bin sequence, remove duplicate labels, establish receiving/quarantine/staging areas, and audit labels. |
| Weak Wi-Fi | Timed-out scans, duplicate submissions, workarounds | Survey at working height and during live operations; remediate dead zones; use explicit pending/error states and idempotent retry; document outage procedure. |
| Lack of training | Scan bypass, inaccurate stock, poor adoption | Train champions and backups; practice exceptions; keep job aids at stations; provide floor support during go-live. |
| Dirty SKU/UOM/barcode data | Wrong item matches and bad quantities | Normalize unique identifiers and base units; scan-test labels; quarantine ambiguous records before import. |
| Unreconciled opening balances | System is untrusted from day one | Count by SKU/bin, import opening movements, reconcile, document variance owners, and do not claim clean history that was not captured. |
| Weak backup/rollback | Data loss or unworkable failed cutover | Test database restore and reversal/cutover plan; define who can authorize fallback and how transactions are reconciled afterward. |
| Speed-only productivity targets | Operators skip scans or accuracy deteriorates | Pair speed with accuracy, exception rates, task mix, and sample size; improve system/layout before individual ranking. |
| Uncontrolled slotting changes | Misplaced stock and broken pick paths | Treat suggestions as advisory; manager approves; use transfer transactions and measure pilot results. |

## 7. Go-live readiness checklist

### Business and process

- [ ] System-of-record ownership is written and accepted by warehouse, finance/ERP owner, and management.
- [ ] Phase scope, support contacts, escalation path, operating hours, and go/no-go authority are named.
- [ ] Receipt, putaway, pick, pack, ship, return, count, damage, and adjustment procedures are documented.
- [ ] Exception and manager-override rules are understood; no one relies on silent quantity editing.
- [ ] Pilot results and open defects have been reviewed; no critical severity issue remains.

### Data and inventory

- [ ] Active SKU master has unique SKU/barcode, description, base UOM, and required reorder/tracking fields.
- [ ] Bin/location map is complete, labeled, active/pickable flags validated, and physical labels scan correctly.
- [ ] Opening physical count is complete for the cutover scope; variances are documented and approved.
- [ ] Opening ledger/balance totals reconcile by SKU/bin (and lot/serial where applicable).
- [ ] Suppliers/customers and source references needed for live work are available.
- [ ] Inactive/duplicate/unknown records are excluded or explicitly dispositioned.

### Technology, devices, and security

- [ ] Production app, database, secrets, TLS/session settings, role permissions, and audit attribution are configured.
- [ ] Backup completed and a restore test succeeded within agreed RPO/RTO.
- [ ] Wi-Fi coverage tested at receiving, all pilot bins, packing, and dispatch during a busy period.
- [ ] Each scanner pairs/connects, reads actual labels, and sends the expected suffix; browser focus and duplicate scan behavior are tested.
- [ ] Printer produces correct packing slips/labels on approved stock; reprint/failure behavior is documented.
- [ ] Device charging, cases, account logout, and shared-device access are set up.
- [ ] Health monitoring, error logs, support ownership, and incident contact are active.

### People and operations

- [ ] Every user can log in and has the least-privilege role required for assigned duties.
- [ ] Receiving, picking/packing, manager, and admin training is completed and recorded.
- [ ] Quick reference cards and support contacts are available at workstations.
- [ ] Pilot champions and backups are scheduled for launch and first-week coverage.
- [ ] Staff know how to handle offline/time-out states and do not repeat submissions with a new request ID.
- [ ] Daily reconciliation and issue-review cadence is assigned for the first two weeks.

### Cutover and rollback

- [ ] Cutover time, last spreadsheet update, count/freeze window, and opening balance process are scheduled.
- [ ] Existing spreadsheets are archived/read-only after acceptance; no second live quantity master remains.
- [ ] In-flight receipts/orders at cutover have an owner and an explicit migration or completion plan.
- [ ] Rollback trigger, decision-maker, safe fallback process, and transaction reconciliation steps are written.
- [ ] Go/no-go meeting reviews accuracy, scan/device tests, unresolved exceptions, backup restore, and operator readiness.
- [ ] First-shift floor support and end-of-day stock reconciliation are scheduled.

## 8. Go-live and stabilization

At go-live, roll out one zone or a controlled SKU set first, then expand by signed-off area. For the first two weeks:

- Review failed scans, timeouts, duplicate/idempotency events, discrepancies, and adjustments daily.
- Physically recount a rotating sample of high-risk and recently moved SKUs.
- Reconcile ledger totals with inventory snapshots and reservations with active allocations.
- Keep a visible issue log and prioritize fixes that risk stock integrity, safety, or order correctness.
- Do not add a new phase feature during stabilization unless it resolves a critical operational blocker.
- Retire parallel editable spreadsheets only after manager acceptance; preserve archived source files and cutover evidence.
