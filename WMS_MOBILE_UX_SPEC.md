# Handheld WMS Mobile UX Specification

## 1. Product decision

### Recommended approach: responsive PWA

Start with a mobile-first, installable PWA served by the existing Flask application. It avoids a separate mobile release pipeline, works with the current web stack, supports Android Chrome, and can accept input from most Bluetooth/USB scanners configured as keyboard wedges. Cache the app shell and static help/status content for fast launch, but keep stock-changing operations online-first.

Do **not** make a scan appear committed while the device is offline. In the MVP, preserve an unsent form locally in the active screen, show **Not synced — not recorded**, and retry only after a deliberate user action. A later offline outbox may queue immutable command drafts with idempotency keys, but each must remain visibly pending until the server revalidates stock, reservations, document state, and permissions. Do not execute dependent steps from pending commands.

Choose Flutter or React Native only if validated requirements demand reliable offline mutation queues, deeper device management/kiosk control, native printer/scanner SDKs, or camera scanning that cannot be met through Android browser/PWA support. A native client increases build, deployment, and support effort and does not remove server-side concurrency/conflict requirements.

### Device assumptions

- Android phone/tablet or rugged handheld, used mainly in portrait orientation.
- Scanner behaves as keyboard input, appends an optional Enter/Tab suffix, and can be tested on the actual device.
- Touch and scanner are both supported. Camera scanning is optional and must never be the only scan path.
- Wi-Fi is not assumed to be continuous. The UI distinguishes local form state from server-confirmed state.

## 2. Shared mobile interaction model

- **Top bar:** warehouse name, connection state, current user/role, and a back/cancel action that warns about unsaved work.
- **Connection indicator:** persistent `Online`, `Connecting`, or `Offline — changes are not recorded`. Show a last successful sync time only where cached information is displayed.
- **Primary scan panel:** one clearly labeled, visible scan field; automatically focus it on entry and after a successful step. Keep a manual search fallback.
- **Progress:** show the current step (for example, `Receipt 2 of 5`) and expected versus scanned quantity. Do not bury the main task in navigation.
- **Actions:** one high-contrast primary button and a smaller secondary action. Buttons are at least 48 dp high; primary actions should be large enough for gloved use.
- **Feedback:** short success/error text plus color/icon; use optional vibration or sound only when supported and enabled. Provide a visual cue even when sound/vibration is unavailable or disabled.
- **Confirmation:** show item, bin, quantity, and resulting action before a consequential submission. Prevent double taps and replay committed responses on idempotent retry.
- **Failure handling:** retain safe unsent inputs; identify whether the server committed the command. Do not assume failure or success if the connection drops during submission—retry with the same idempotency key and reconcile the response.

## 3. Navigation and role-based home

### Navigation

Use a simple bottom navigation or home tiles:

```text
Home | Receive | Pick | Lookup | More
```

`More` contains Putaway, Pack/Ship, Cycle Count, and Help according to the user's permissions. Keep the current active task visible when navigating away and provide a clear **Resume task** entry on Home.

### Login screen

**Fields and controls**

- Username
- Password (show/hide control)
- **Sign in**
- Optional warehouse selector after authentication if the user has access to multiple sites
- Clear connection/authentication status

**Validation**

- Require both username and password; do not reveal whether the username exists.
- On success, rotate the session, display the user's name and assigned role, and open the correct home screen.
- On invalid credentials show a generic retry message. On offline/unreachable service, state that sign-in could not be completed; do not accept cached credentials as a successful login.
- Use secure session cookies and CSRF protection for state-changing requests.

### Role-based home screen

| Role | Home content |
| --- | --- |
| Operator | Large **Receive**, **Putaway**, **Pick**, **Pack**, **Cycle Count**, and **Lookup** actions based on permissions; assigned/open tasks first |
| Manager | Operator actions plus exception queue, pending approvals, open receipt/order counts, and discrepancy links |
| Admin | Manager view plus user/configuration entry points; administrative tasks should not crowd out operational work |
| Viewer/owner | Read-only lookup, stock summaries, task/order status, and allowed reports; no write or scan-to-post actions |

Show offline/unsynced work prominently. Do not show a green completion state for a command that the server has not acknowledged.

## 4. Screen-by-screen flows

### 4.1 Receiving

**Flow**

1. Tap **Receive** or **Resume receipt**.
2. Scan PO/receipt barcode or search by PO/reference.
3. Confirm supplier and receipt status; choose an open line or scan the SKU.
4. Compare the matched item with expected SKU/description and expected quantity.
5. Enter/adjust received quantity; scan or enter lot/expiry/serial data when required.
6. If actual differs from expected, choose discrepancy type and enter a short note.
7. Review and tap **Confirm receipt**. The success state appears only after server confirmation.
8. Continue to the next line or **Go to putaway**.

**Key fields**

- PO/receipt reference, supplier, line status
- SKU/barcode, item description, expected quantity, received quantity
- Lot/batch and expiry date, serial number(s) where item configuration requires them
- Discrepancy type: short, over, damaged, wrong item, other; note

**Buttons**

- **Scan PO**
- **Scan item**
- **Add discrepancy**
- **Confirm receipt**
- **Save draft** (if supported; explicitly not a stock posting)
- **Cancel**

**Validation and errors**

- PO must exist and be open; closed/cancelled receipts cannot receive more stock without manager action.
- Scanned barcode and selected SKU must match. Unknown or ambiguous scans block posting.
- Quantity must be positive and use the item's base unit; fractional quantities only where allowed.
- Required lot/expiry/serial values must be valid; expiry must be a valid date and not silently inferred.
- Over-receipt beyond configured tolerance requires manager approval.
- Difference from expected requires a discrepancy type and note before confirmation.
- Duplicate submission returns the original receipt result using the idempotency key.

### 4.2 Putaway

**Flow**

1. Open a received line awaiting putaway.
2. Review item and quantity in the receiving/staging bin.
3. View the suggested destination bin and its zone/pickability.
4. Scan the destination bin barcode.
5. If it matches an allowed bin, review source, destination, SKU, and quantity.
6. Tap **Confirm putaway**. On success, show the new bin balance and next line.

**Key fields:** SKU, quantity to move, source bin, suggested bin, scanned bin, optional lot/serial.

**Buttons:** **Scan destination**, **Confirm putaway**, **Choose another bin** (when allowed), **Report issue**.

**Validation and errors**

- Source must have sufficient available stock; destination must be active and permitted for putaway.
- Wrong destination bin blocks confirmation. A manager override, if configured, requires fresh manager authorization, a reason, and audit attribution.
- Source and destination cannot be the same.
- A successful putaway posts balanced ledger movements for source and destination atomically.

### 4.3 Picking

**Flow**

1. Tap **Pick** and select an assigned/released order or task.
2. Show remaining lines ordered by warehouse bin sequence, not simple alphabetic text order. The sequence should follow the warehouse's configured aisle/zone/level/bin ordering.
3. Scan the expected bin.
4. Scan the item barcode.
5. Confirm the requested quantity using a large quantity control; scan each unit only if the operation requires unit-level verification.
6. Confirm pick and move to the next line. Show progress and exceptions.

**Key fields:** order reference, line progress, expected bin, item/SKU, requested quantity, picked quantity, lot/serial where required.

**Buttons:** **Scan bin**, **Scan item**, **Confirm pick**, **Short pick**, **Skip with reason**, **Pause task**.

**Validation and errors**

- Wrong bin or item blocks progress. Manager override requires manager authentication, reason, and an audit event; never silently accept mismatch.
- Pick quantity cannot exceed the remaining line quantity or allocated/available stock.
- A short pick requires a reason and returns the line/order to an explicit shortage/exception state.
- On success, update the task only once. If picking physically moves stock to staging, post paired ledger movements; reservations themselves are not physical stock movements.

### 4.4 Packing and shipping

**Flow**

1. Scan or select a picked order.
2. Verify order identity and show expected items/quantities.
3. Scan each item being packed; show accepted count versus expected count.
4. Resolve missing, extra, or wrong items before packing can complete.
5. Tap **Complete packing** after all lines match.
6. Print a packing slip or supported label. If no printer/carrier integration is configured, allow the approved manual workflow.
7. Enter/select carrier and tracking number if available; tap **Mark shipped** only when dispatch is confirmed.

**Key fields:** order reference, item/barcode, expected and scanned quantity, carrier, tracking number, packed by, shipped at.

**Buttons:** **Scan item**, **Complete packing**, **Print slip**, **Print label** (when configured), **Mark shipped**.

**Validation and errors**

- Wrong/extra item or excess quantity blocks pack completion and names the mismatch.
- A partially packed order remains `Picking` or `Packed` only according to the defined backend state transition; never show `Shipped` early.
- Shipment confirmation requires pack verification and is idempotent.
- Shipment ledger movement is posted once on dispatch confirmation. Packing alone is not a stock movement unless it changes physical location.
- Printer failure does not mark the order shipped; show **Print failed** and an explicit retry/manual-print path.

### 4.5 Cycle count

**Flow**

1. Tap **Cycle Count** and open an assigned count task.
2. Scan the bin.
3. Scan each item in that bin and enter the physical count.
4. For a blind count, do not show the expected stock until the count is submitted.
5. Show a variance summary after submission; request a recount or manager review where required.
6. Only approved corrections change the stock balance.

**Key fields:** count/task ID, expected bin, scanned SKU, lot/serial, counted quantity, variance and reason.

**Buttons:** **Scan bin**, **Scan item**, **Submit count**, **Recount**, **Flag exception**, **Finish bin**.

**Validation and errors**

- The scanned bin and item must belong to the count task.
- Count must be a non-negative valid quantity; required lot/serial details must be captured.
- A variance is recorded as a count result, not an immediate balance edit. Manager approval creates the adjustment ledger entry.
- Unexpected SKU in the bin is flagged as an exception; it cannot be silently added to the count.

### 4.6 Stock lookup

**Flow**

1. Tap **Lookup** and scan an SKU/barcode or bin barcode.
2. Show the matched item/bin and on-hand, reserved, and available stock.
3. If an item was scanned, list all bins holding it; if a bin was scanned, list its contents.
4. Tap a row for recent movement history and lot/expiry details if tracked.

**Key fields:** scan/search field, item identity, bin, on-hand, reserved, available, lot/expiry, last movement.

**Buttons:** **Scan SKU**, **Scan bin**, **Search**, **View movements**.

**Validation and errors**

- Show a clear unknown/ambiguous barcode result; never choose an arbitrary item.
- Distinguish cached/stale information from a current server response with sync time.
- Viewers can look up but cannot initiate adjustment, transfer, receipt, or pick actions.

## 5. Shared validation and feedback states

| State | UI response |
| --- | --- |
| Valid scan | High-contrast success banner, matched SKU/bin text, optional short vibration/sound, focus next scan input |
| Wrong item/bin | Stop the workflow, show expected versus scanned values, preserve task state, offer **Scan again**; show **Request manager override** only if permitted |
| Unknown barcode | Show **No match found**, keep input active, allow manual search; do not post |
| Invalid quantity | Inline message and focus quantity control; preserve entered value |
| Pending approval | Clearly label **Awaiting manager approval**; do not imply balance has changed |
| Server validation/conflict | Show actionable message (for example, insufficient stock or receipt closed); preserve safe form data |
| Offline before submit | Show **Offline — not recorded**; disable commit action or keep it disabled until reconnection |
| Connection drops during submit | Show **Checking submission status**; retry with the same idempotency key and do not create a new command |
| Printer unavailable | Keep packing/shipping status unchanged; offer retry or documented manual path |

Use optional vibration/sound feedback as enhancement, not as the only signal. Respect device silent mode and user preferences. Avoid loud or continuous alerts in shared warehouse environments.

## 6. Offline behavior and safe retry

### MVP

- Cache app shell and non-sensitive static assets for quick startup.
- Do not cache credentials or present private stock data as current while offline.
- Disable stock-changing submissions when offline. Preserve current form entries as an **unsent draft** where practical.
- Distinguish `Draft`, `Pending`, and `Committed` states. Only a server response marks a stock operation committed.
- Give each retryable submission a stable idempotency key; keep the same key until the server confirms the result.
- On reconnect, revalidate the session and refresh item/order/bin state before the operator submits.

### Optional later offline outbox

If real warehouse Wi-Fi surveys show a material dead zone, design a limited outbox as a separate phase:

- Queue command payloads locally as pending drafts, with user, task, client timestamp, and idempotency key.
- Display pending count and provide a review/cancel action. Do not allow dependent pick/pack/ship steps to assume pending stock changes succeeded.
- On reconnect, submit commands sequentially; server revalidates current authorization, task status, and available quantities.
- Return accepted, rejected, or conflict for every queued action; require operator/manager resolution for conflicts.
- Define device loss, shared-device logout, local-data protection, retention, and audit behavior before enabling the queue.

An offline queue is not merely a network retry. Stale inventory can create overselling and duplicate dispatches, so do not ship it as a hidden background feature.

## 7. PWA and scanner recommendations

- Use responsive HTML forms and a visible scan input that accepts keyboard-wedge scanner input, with tested Enter/Tab handling.
- Keep keyboard input available for accessibility and scanner fallback; avoid trapping keypresses globally.
- Test scanner suffix/configuration, focus behavior, rapid scans, duplicate scans, browser keyboard display, and screen sleep on the target Android devices.
- Use a camera-based barcode library only if tested hardware lacks a scanner; request camera permission only on the scan screen and provide a manual fallback.
- For printing, prefer server-generated PDF/label output for browser print or a proven printer workflow. Direct Bluetooth/USB printer control may require native APIs and can be a reason to consider a native client later.
- Ensure session cookies use HTTPS, `Secure`, `HttpOnly`, and appropriate `SameSite` policy in production. Protect state-changing requests against CSRF.

## 8. Suggested build and field-test sequence

1. Build shared scan panel, connection indicator, result banners, quantity control, and role-aware home.
2. Pilot stock lookup and receipt scan on the actual Android device/scanner.
3. Add putaway and picking; validate bin sequencing and mismatch recovery with operators.
4. Add pack, ship, cycle count, and manager override/approval flows.
5. Test weak Wi-Fi, access-point handoff, connection loss during submission, repeated scanner input, and printer failure.
6. Observe operators completing representative tasks; tune field focus, button placement, wording, and scan feedback before adding offline queueing.
