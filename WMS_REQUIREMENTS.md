# Small-Warehouse WMS Requirements

## 1. Purpose and planning context

This document defines an implementable first release and follow-on phases for the warehouse application. It is intentionally limited to the needs of a small operation; it is not a distribution-center specification.

The source prompt leaves the business-context fields blank. Until those details are confirmed, use the planning baseline from the project design:

| Context | Working assumption | Confirmation needed |
| --- | --- | --- |
| Warehouse type | Small general-goods or e-commerce stockroom | Product and compliance requirements |
| SKU count | About 300 active SKUs | Peak and expected growth |
| Daily orders | About 50 | Peak-day volume and order lines/order |
| Staff size | 3–6 users | Shift pattern and role overlap |
| Current process | Spreadsheet/paper and the current project app; exact source of truth is unknown | Current receiving, count, picking, and dispatch process |
| Must-have integrations | None specified; CSV is the initial exchange method | ERP/order source, accounting, and shipping carrier |

These are planning assumptions, not commitments. Confirm them before setting delivery dates, selecting hardware, or enabling lot/serial traceability. The project currently has a Flask web app, SQLite database, product records, simple stock-in/stock-out, transaction history, CSV export, login, and basic roles. Purchase orders, multi-bin stock, barcode-confirmed workflows, order fulfillment, immutable ledger enforcement, and shipping are future capabilities, not current behavior.

## 2. Personas

| Persona | Goals | Typical tasks | Needs and constraints |
| --- | --- | --- | --- |
| **Warehouse operator** | Move stock accurately and find items quickly | Look up stock, transfer stock between bins, report damage, help with counts | Few screens, scan-first operation, clear confirmation, minimal typing; may cover receiving or picking |
| **Receiving clerk** | Receive supplier deliveries and make stock available in the correct bin | Open PO/receipt, scan items and quantities, record discrepancies, put away stock | Fast scan feedback, expected-vs-received visibility, exception notes, no silent over-receipt |
| **Picker/packer** | Complete the right orders with minimal errors | Work a pick list, scan bin and SKU, verify packed items, confirm dispatch | Short guided steps, unmistakable mismatch warnings, no picking from unavailable stock |
| **Warehouse manager** | Maintain accurate inventory and daily throughput | Review exceptions, approve adjustments, assign work, run counts, inspect reports | Reliable audit history, actionable alerts, simple productivity and accuracy measures |
| **Administrator** | Configure and protect the system | Manage users/roles, SKU/bin configuration, imports, backups and settings | Least-privilege controls, safe deactivation, traceable configuration changes |

One employee may perform multiple jobs in a small team. Permissions attach to a user's assigned role, not the persona name; an administrator can also have an operational role where the business permits it.

## 3. Feature priority

| Feature | MVP / Phase 1 | Phase 2 | Phase 3 / nice-to-have |
| --- | --- | --- | --- |
| SKU and bin master data | Required: SKU/barcode, unit, active state, named bins | Supplier-specific item aliases and simple bin compatibility | Bulk optimization or sophisticated slotting |
| Purchase order receiving and putaway | Required: create/import expected receipt, scan, discrepancies, confirm destination bin | ERP/API PO sync and configurable putaway suggestions | Automated replenishment/slotting optimization |
| Real-time inventory lookup | Required: quantity by SKU and bin, movement history | Lot/expiry/serial filters where required | Cross-warehouse availability |
| Adjustments and audit | Required: reason, actor, timestamp, append-only ledger, manager approval for configured exceptions | More approval rules and scheduled reconciliation | Advanced fraud/risk analytics |
| Cycle counting | Required: create count, record physical quantity, review variance, post approved correction | ABC-based count scheduling and recount routing | Predictive count planning |
| Picking | Required: order entry/CSV, simple pick list, scan bin and item | Order-source API, work assignment enhancements | Batch/wave picking only if volume proves it necessary |
| Packing and shipping | Required: item verification, mark dispatched, record carrier/tracking reference; initially use carrier portal | Carrier API, label purchase/printing integration | Rate shopping and multi-carrier optimization |
| Low-stock alerts | Required: per-SKU reorder threshold and dashboard/report | Supplier lead-time-aware notifications | Forecasting and automated purchase recommendations |
| RBAC | Required: server-enforced roles and protected write actions | Permission configuration and SSO if justified | Enterprise identity lifecycle/advanced policy engine |
| Operational readiness | Required: backup/restore procedure, CSV validation, responsive UI | Monitoring and approved external integrations | Multi-site high availability |

Phase definitions are delivery priorities rather than promises of calendar dates. Phase 1 is complete only when core inventory actions are traceable and the team can run receiving through dispatch without maintaining a parallel quantity spreadsheet.

## 4. User stories and acceptance criteria

### 4.1 SKU and bin master data

**User story:** As an administrator or warehouse manager, I want to maintain uniquely identifiable SKUs and storage bins so that every receipt, lookup, count, and pick refers to the same item and location.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| MD-1 | Given an authorized manager, when they create an item with a unique SKU, required name, base unit, and optional barcode, then the item is saved and available for operational workflows. |
| MD-2 | Given a SKU or barcode already assigned to an active item, when a user attempts to assign the same identifier to another item, then the save is rejected with a clear error and neither item is changed. |
| MD-3 | Given an authorized user, when they create a bin with a unique code within the warehouse, then that bin appears in location search and can be used by stock movements. |
| MD-4 | Given a bin contains stock or is referenced by open work, when a user tries to delete or deactivate it, then the system prevents unsafe removal and explains the required transfer/closure; historical references remain intact. |
| MD-5 | Given a user without master-data permission, when they attempt to create, edit, or deactivate an item or bin, then the server denies the request and records the denied action where security logging is supported. |
| MD-6 | Given an item's identifier or description, when an operator searches or scans it, then the system returns a single clear match or an explicit no-match/ambiguous result; it never silently chooses among duplicates. |

### 4.2 Purchase order receiving and putaway

**User story:** As a receiving clerk, I want to receive against expected purchase-order lines, record differences, and put items into confirmed bins so that inventory is available and discrepancies are visible.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| IN-1 | Given an authorized user, when they create a receipt manually or import a supported CSV, then the receipt has a unique reference, expected item/quantities, status, and source reference where available. Invalid rows are reported before posting. |
| IN-2 | Given an open receipt line, when the clerk scans its barcode, then the matched SKU and expected quantity are shown before accepting a received quantity. Unknown identifiers do not post stock. |
| IN-3 | Given a received quantity differs from expected, when the clerk records it, then the receipt records the actual quantity and discrepancy type/note; configured over-receipt limits require manager approval. |
| IN-4 | Given a receipt line is confirmed, when the transaction commits, then a receipt movement with item, quantity, receiving location, actor, timestamp, and receipt reference is recorded and on-hand is updated atomically. Retrying the same confirmation cannot post it twice. |
| IN-5 | Given stock in a receiving/staging bin, when the clerk scans the item and a valid destination bin and confirms quantity, then the system records a balanced transfer and displays the resulting bin quantity. A mismatch or insufficient staging quantity is rejected without partial posting. |
| IN-6 | Given a receipt has unresolved lines or discrepancies, when the clerk attempts to close it, then the system prevents closure or requires an explicit authorized exception resolution. |

### 4.3 Real-time inventory lookup

**User story:** As a warehouse operator, I want to scan or search an SKU and see its current quantity by bin so that I can locate stock without checking spreadsheets or walking the warehouse.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| IV-1 | Given an active item, when a user scans its barcode or searches by SKU/name, then the response shows the item identity and on-hand quantity for each active bin, plus total on-hand. |
| IV-2 | Given posted stock movements, when a lookup is performed after a successful commit, then displayed on-hand reflects those movements and is derived from the ledger-backed balance projection. |
| IV-3 | Given reservations exist for open orders, when the user views availability, then on-hand and available-to-promise are labeled separately; the system does not describe reserved stock as freely available. |
| IV-4 | Given no matching item or an inactive item, when it is scanned/searched, then the UI reports no active match and provides a controlled lookup path instead of showing an unrelated item. |
| IV-5 | Given a lookup request fails or data is stale, when the result cannot be confirmed, then the UI displays an explicit error or last-updated time and does not present a stale quantity as current. |

### 4.4 Stock adjustments with audit trail

**User story:** As a warehouse manager, I want corrections to require a reason and be traceable so that inventory can be corrected without erasing what happened.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| AD-1 | Given a user with adjustment permission, when they request an adjustment, then they provide item, bin, quantity/direction or counted quantity, and a reason code; the UI shows the proposed before/after balance. |
| AD-2 | Given an adjustment exceeds the configured threshold, when it is submitted, then it remains pending and does not change stock until a different authorized manager approves it. |
| AD-3 | Given an adjustment is approved and posted, when stock changes, then an immutable ledger entry records the delta, reason, actor, approver if applicable, timestamp, and reference. The balance projection updates in the same transaction. |
| AD-4 | Given an adjustment is rejected, when the requester views it, then the request remains visible with rejection actor/time/reason and on-hand is unchanged. |
| AD-5 | Given a posted movement is incorrect, when an authorized user corrects it, then the system posts a linked reversal and any correcting movement; posted history cannot be edited or deleted through application flows. |
| AD-6 | Given concurrent requests or insufficient stock, when posting would make a bin balance negative or conflict with another posting, then the entire operation fails cleanly and no partial ledger/balance change occurs. |

### 4.5 Cycle counting

**User story:** As a warehouse manager, I want to count selected bins/items and resolve variances so that I can find stock errors before they disrupt fulfillment.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| CC-1 | Given an authorized manager, when they create a count for selected bins or items, then each count line has a defined item/location, status, and count session reference. |
| CC-2 | Given an active count line, when an operator scans the bin and item and enters the physical quantity, then the system validates that the scanned item belongs to the count and records the counter and time. |
| CC-3 | Given blind count is enabled, when the operator enters a count, then the expected quantity is not shown to that counter until submission. |
| CC-4 | Given the count differs from the system balance, when the count is submitted, then the variance is visible for review and does not silently change stock. |
| CC-5 | Given a variance has required approval, when an authorized manager approves it, then the system posts a reason-coded adjustment linked to the count and preserves the original count and expected quantity for audit. |
| CC-6 | Given a count has unresolved lines, when a user attempts to close it, then the system blocks closure or requires a documented, authorized exception. |

### 4.6 Order picking with barcode verification

**User story:** As a picker, I want a short pick list that tells me the bin and verifies the SKU when I scan it so that I fulfill the correct order from the correct location.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| PK-1 | Given an order with valid item lines, when an authorized user releases it for picking, then the system checks availability and creates pick work only for allocatable quantities; shortages are explicit. |
| PK-2 | Given a pick task, when the picker opens it, then the UI presents the order, next bin, item identity, and requested quantity in a mobile-friendly sequence. |
| PK-3 | Given a pick line, when the picker scans the expected bin and item, then the system accepts the correct item and quantity; a wrong bin/item produces a clear rejection and does not increment picked quantity. |
| PK-4 | Given the scanned item is correct but the picked quantity exceeds the remaining task quantity or available stock, when the picker submits it, then the system rejects the excess or routes it to an explicit exception path. |
| PK-5 | Given a network or server error while confirming a pick, when the user retries, then the system reports whether the prior confirmation committed and does not duplicate the pick or ledger posting. |
| PK-6 | Given a pick task is completed, when it is reviewed, then each confirmation is attributable to a picker and timestamp and can be reconciled to the order line. |

### 4.7 Packing and shipping

**User story:** As a packer, I want to verify packed items against the order and record dispatch details so that the right goods leave the warehouse with traceable shipment information.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| SH-1 | Given a picked order ready to pack, when the packer opens it, then the system shows expected items and quantities and supports scanning each item at pack. |
| SH-2 | Given a packed scan does not match the order or exceeds its remaining quantity, when submitted, then the system blocks pack completion and identifies the mismatch. |
| SH-3 | Given all required lines are verified, when the packer completes packing, then the order moves to packed and a packing slip can be printed or exported. |
| SH-4 | Given a packed order, when an authorized user confirms dispatch, then the system records shipment time, user, carrier/tracking reference if known, and shipment movement(s) exactly once. |
| SH-5 | Given dispatch has not been confirmed, when the order is viewed, then it is not shown as shipped and its shipment stock movement is not posted. |
| SH-6 | Given a carrier integration is not configured, when a shipment is processed, then the user can record a carrier/tracking reference manually; the MVP does not require carrier API label purchase. |

### 4.8 Low-stock alerts

**User story:** As a warehouse manager, I want to see items at or below their reorder threshold so that replenishment can be arranged before orders are affected.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| LS-1 | Given an active SKU with a reorder level, when its on-hand quantity is at or below that level, then it appears in the low-stock dashboard/report with SKU, description, on-hand, and threshold. |
| LS-2 | Given a stock movement changes quantity, when the movement commits, then the next dashboard/report request reflects the updated alert state. |
| LS-3 | Given a SKU has no configured threshold or is inactive, when alerts are calculated, then it is excluded or clearly labeled according to the agreed configuration; the system does not invent a threshold. |
| LS-4 | Given the manager exports the report, when CSV is downloaded, then the export uses stable column names and the same filter scope as the displayed report. |

### 4.9 Role-based access control

**User story:** As an administrator, I want each user to access only the operations allowed by their role so that sensitive configuration and stock changes are protected.

**Acceptance criteria**

| ID | Given / When / Then |
| --- | --- |
| RB-1 | Given an unauthenticated user, when they request a protected page or write action, then the system requires authentication and does not perform the action. |
| RB-2 | Given a signed-in user without the required permission, when they call a protected route directly (not just through the UI), then the server denies the action and leaves data unchanged. |
| RB-3 | Given an employee, manager, or administrator role, when they access functions, then the permissions match the role matrix below and are consistently enforced on HTML and API routes. |
| RB-4 | Given a user role is changed or an account is deactivated, when the change is saved, then subsequent requests enforce the updated access and retain an administrative audit event. |
| RB-5 | Given the last active administrator, when another user attempts to remove that user's admin access or deactivate the account, then the system prevents leaving the system without an active administrator. |
| RB-6 | Given manager approval is required, when the requester attempts to approve their own request, then the system rejects self-approval unless the business explicitly chooses and documents a single-person exception policy. |

**Initial role matrix**

| Capability | Warehouse operator / employee | Receiving clerk | Picker/packer | Warehouse manager | Administrator |
| --- | --- | --- | --- | --- | --- |
| View item, bin, and stock | Yes | Yes | Yes | Yes | Yes |
| Perform assigned receipt/putaway | As assigned | Yes | No | Yes | Optional |
| Pick, pack, and dispatch | As assigned | No | Yes | Yes | Optional |
| Request stock adjustment/count variance | Yes | Yes | Yes | Yes | Optional |
| Approve configured adjustments | No | No | No | Yes, not own request | Optional by policy |
| Manage SKU/bin master | No | No | No | Yes | Yes |
| Manage users/roles/security settings | No | No | No | No | Yes |
| View operational reports/audit | Limited operational view | Assigned work | Assigned work | Yes | Yes |

The administrator role is for system configuration, not a bypass for recording operational stock movements. Final permissions should be confirmed with the warehouse owner.

## 5. Non-functional requirements

The values below are proposed MVP targets. Validate them on the selected hardware and network before release.

| ID | Area | Requirement and acceptance measure |
| --- | --- | --- |
| NFR-1 | Usability | Core receive, putaway, lookup, pick, and pack tasks are usable on a phone/handheld-sized browser with large touch controls, clear focus, and no hover-only action. A new operator can complete a representative task after brief guided training; usability test findings are recorded and critical blockers fixed. |
| NFR-2 | Scan speed | On the warehouse LAN with a supported scanner, a valid scan produces a clear match/accept/reject response within 1 second at the 95th percentile, excluding deliberate user confirmation or label-print time. |
| NFR-3 | Data integrity | Every committed stock change has a corresponding append-only ledger movement. Ledger insertion and balance projection update are atomic. Retried requests are idempotent; no silent direct quantity edit is allowed. |
| NFR-4 | Auditability | Every posted movement captures item, signed quantity, location, operation/reference, actor, and timestamp. Adjustments and approvals retain reason, requester, approver, decision, and reversal links. Posted ledger records cannot be edited/deleted through normal application access. |
| NFR-5 | Backup and recovery | Automated daily backup at minimum, stored separately from the live database and access-controlled. Proposed recovery point objective (RPO) is 24 hours and recovery time objective (RTO) is 4 hours for MVP; perform and document a restore test before go-live and at least quarterly. |
| NFR-6 | Wi-Fi reliability | Receiving, storage, packing, and dispatch areas are surveyed and tested during normal operation. While connected, core scan commands meet NFR-2. When disconnected, the UI clearly reports failure and whether a command committed; it never queues an unconfirmed stock mutation as successful. Offline write support is not an MVP requirement. |
| NFR-7 | Availability | Proposed target: 99.5% availability during agreed operating hours, excluding planned maintenance. The actual deployment must have an owner, health check, and documented restart/recovery steps. |
| NFR-8 | Basic security | Use HTTPS outside local development, a deployment-managed secret, secure session-cookie settings, CSRF protection for state-changing browser forms, password hashing, least-privilege roles, input validation, and no secrets in logs or source control. |
| NFR-9 | Concurrency | Concurrent receipt, adjustment, and shipment attempts cannot produce negative balances, duplicate postings, or partial transactions. Conflicts return a clear retry/review message. |
| NFR-10 | Portability and export | Items, stock balances, movements, and orders can be exported in documented CSV formats. Imports validate headers, identifiers, quantities, duplicates, and row errors before posting. |
| NFR-11 | Accessibility and feedback | Do not communicate status by color alone; provide text and visual feedback for scan success, mismatch, validation errors, and network failures. Support keyboard navigation and readable contrast. |
| NFR-12 | Maintainability | Keep stock posting in a shared application service used by web and API entry points. Database migrations are versioned, backed up, and tested against a copy of production data before deployment. |

## 6. Out of scope

Explicitly exclude from the initial product unless business evidence changes the scope:

- Wave planning, task interleaving, labor optimization, and complex multi-zone routing.
- Conveyor, sortation, robotics, autonomous vehicles, or warehouse automation control.
- Multi-warehouse and multi-company orchestration.
- Complex directed putaway optimization, dynamic slotting, or capacity simulation.
- Demand forecasting, automated purchasing, supplier bidding, or advanced replenishment optimization.
- Full financial accounting, costing, invoicing, or replacing the ERP/accounting system.
- Mandatory carrier rate shopping or carrier label API integration in Phase 1.
- Offline-first stock mutation with synchronization/conflict resolution.
- Lot, serial, expiry, FEFO, recall, or regulated traceability unless required by the actual product mix or law.
- Complex returns, kitting, manufacturing, cross-docking, and value-added services.
- Custom analytics/data warehouse and predictive productivity scoring.

## 7. Definition of MVP acceptance

The MVP is ready for a controlled pilot when:

1. Item and bin data are validated and opening stock reconciles to a physical count.
2. Receiving, putaway, transfer, adjustment, cycle-count correction, and shipment all post traceable ledger entries.
3. Users can look up stock by SKU and bin and understand the difference between on-hand and available stock.
4. Pick and pack verification catch wrong-item scans without changing stock.
5. Role checks are enforced server-side, including direct route/API requests.
6. Low-stock reports, CSV import/export, backups, and a successful restore test are available.
7. The target scanner, printer, handheld browser, and warehouse Wi-Fi pass representative end-to-end tests.
8. Operators have a documented process for discrepancies, network interruptions, corrections, and escalation.
