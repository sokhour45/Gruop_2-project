(() => {
  "use strict";

  const API = "/api/v1";
  const tokenKey = "wms_access";
  const refreshKey = "wms_refresh";
  const userKey = "wms_user";
  const iconPaths = {
    dashboard: '<rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="5" rx="1"/><rect x="13" y="10" width="8" height="11" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/>',
    package: '<path d="m12 3 8.2 4.5v9L12 21l-8.2-4.5v-9L12 3Z"/><path d="m3.8 7.5 8.2 4.6 8.2-4.6M12 12.1V21"/>',
    location: '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    truck: '<path d="M3 6h11v11H3z"/><path d="M14 10h4l3 3v4h-7z"/><circle cx="7.5" cy="18" r="1.5"/><circle cx="17.5" cy="18" r="1.5"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    receipt: '<path d="M4 3h16v18l-3-2-3 2-2-2-3 2-2-2-3 2V3Z"/><path d="M8 8h8M8 12h8M8 16h4"/>',
    scan: '<path d="M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2"/><path d="M4 12h16"/>',
    return: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-2"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    transfer: '<path d="M7 7h14m0 0-4-4m4 4-4 4"/><path d="M17 17H3m0 0 4 4m-4-4 4-4"/>',
    cart: '<path d="M3 3h2l2.4 12.2a2 2 0 0 0 2 1.6h8.8a2 2 0 0 0 2-1.6L22 8H6"/><circle cx="10" cy="21" r="1"/><circle cx="18" cy="21" r="1"/>',
    pick: '<path d="m9 12 2 2 4-4"/><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/>',
    shipping: '<path d="M3 7h11v11H3z"/><path d="M14 10h4l3 3v5h-7z"/><circle cx="7.5" cy="19" r="1.5"/><circle cx="17.5" cy="19" r="1.5"/><path d="M6 10h5"/>',
    adjust: '<path d="M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3"/><path d="M2 14h4m4-6h4m4 8h4"/>',
    count: '<path d="M9 4h6"/><path d="M9 2h6v4H9z"/><rect x="5" y="4" width="14" height="18" rx="2"/><path d="m8 12 2 2 5-5m-7 9h8"/>',
    chart: '<path d="M3 3v18h18"/><path d="m7 14 4-4 4 3 6-7"/>',
    expiry: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/><path d="M9 2h6"/>',
    replenish: '<path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M5.6 9a7 7 0 0 1 11.6-2L20 12M4 12l2.8 5a7 7 0 0 0 11.6-2"/>',
    audit: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8m-8 4h8"/>',
    logout: '<path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/>',
    login: '<path d="M14 17l5-5-5-5"/><path d="M19 12H9"/><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7"/>',
    plus: '<path d="M12 5v14m-7-7h14"/>',
    save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
    delete: '<path d="M3 6h18m-2 0-.9 14H5.9L5 6m4 0V4h6v2m-5 4v6m4-6v6"/>',
    close: '<path d="m18 6-12 12M6 6l12 12"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5m-5 5V3"/>',
    alert: '<path d="m10.3 3.9-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3l-8-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/>'
  };
  const pageIcons = {
    dashboard: "dashboard", items: "package", locations: "location",
    suppliers: "truck", customers: "users", receipts: "receipt", receive: "scan",
    returns: "return", inventory: "search", transfer: "transfer", orders: "cart",
    picks: "pick", pack: "shipping", adjustments: "adjust", counts: "count",
    reports: "chart", expiry: "expiry", replenishment: "replenish", users: "users", audit: "audit"
  };
  const actionIcons = {
    "master-edit": "edit", "master-deactivate": "delete", "master-cancel": "close",
    "open-receipt": "receipt", "suggest-bin": "location", "allocate-order": "pick",
    "approve-adjustment": "pick", "approve-count": "pick", "export-replenishment": "download"
  };
  const loginScreen = document.getElementById("login-screen");
  const appShell = document.getElementById("app-shell");
  const content = document.getElementById("page-content");
  const message = document.getElementById("global-message");
  const pageTitles = {
    dashboard: "Dashboard", items: "Items / SKUs", locations: "Bins / locations",
    suppliers: "Suppliers", customers: "Customers", receipts: "Receipts",
    receive: "Receive / putaway", returns: "Returns / inspection",
    inventory: "Stock lookup", transfer: "Bin transfer", orders: "Orders",
    picks: "Pick tasks", pack: "Packing / shipping", adjustments: "Adjustments",
    counts: "Cycle counts", reports: "Reports", expiry: "Expiry watch",
    replenishment: "Replenishment advisor",
    users: "Users", audit: "Audit log"
  };
  const masterConfig = {
    items: {
      endpoint: "items", title: "Items / SKUs",
      columns: [["sku", "SKU"], ["barcode", "Barcode"], ["description", "Description"], ["uom", "UOM"], ["min_stock", "Min stock"], ["is_active", "Active"]],
      fields: [
        ["sku", "SKU", "text"], ["barcode", "Barcode", "text"],
        ["description", "Description", "text"], ["uom", "Unit of measure", "text"],
        ["min_stock", "Minimum stock", "number"], ["track_lot", "Track lot", "checkbox"],
        ["track_expiry", "Track expiry", "checkbox"], ["is_active", "Active", "checkbox"]
      ]
    },
    locations: {
      endpoint: "locations", title: "Bins / locations",
      columns: [["warehouse_code", "Warehouse"], ["bin_code", "Bin"], ["zone", "Zone"], ["sequence", "Sequence"], ["kind", "Type"], ["is_pickable", "Pickable"], ["capacity", "Capacity"], ["is_active", "Active"]],
      fields: [
        ["warehouse", "Warehouse", "warehouse"], ["bin_code", "Bin code", "text"],
        ["zone", "Zone", "text"], ["sequence", "Sequence", "number"],
        ["kind", "Type", "location_kind"], ["is_pickable", "Pickable", "checkbox"],
        ["capacity", "Capacity (optional)", "number"], ["is_active", "Active", "checkbox"]
      ]
    },
    suppliers: {
      endpoint: "suppliers", title: "Suppliers",
      columns: [["code", "Code"], ["name", "Name"], ["email", "Email"], ["phone", "Phone"], ["is_active", "Active"]],
      fields: [["code", "Code", "text"], ["name", "Name", "text"], ["email", "Email", "email"], ["phone", "Phone", "text"], ["is_active", "Active", "checkbox"]]
    },
    customers: {
      endpoint: "customers", title: "Customers",
      columns: [["code", "Code"], ["name", "Name"], ["email", "Email"], ["is_active", "Active"]],
      fields: [["code", "Code", "text"], ["name", "Name", "text"], ["email", "Email", "email"], ["is_active", "Active", "checkbox"]]
    }
  };
  let currentPage = "dashboard";
  let user = readStoredUser();
  let masterEditing = null;
  let receiptCache = [];
  let orderCache = [];
  let locationCache = [];
  let itemCache = [];
  const pendingSubmissionKeys = new WeakMap();

  function readStoredUser() {
    try { return JSON.parse(sessionStorage.getItem(userKey) || "null"); } catch { return null; }
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  function icon(name, className = "ui-icon") {
    const paths = iconPaths[name];
    if (!paths) return "";
    return `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths}</svg>`;
  }

  function iconForText(text) {
    const value = text.toLowerCase();
    if (/expiry|expired|expir/.test(value)) return "expiry";
    if (/supplier|inbound|receiv|putaway/.test(value)) return "receipt";
    if (/customer|user|account|role/.test(value)) return "users";
    if (/bin|location|destination/.test(value)) return "location";
    if (/return/.test(value)) return "return";
    if (/pick|approve|verify|count/.test(value)) return "pick";
    if (/pack|ship|dispatch|carrier/.test(value)) return "shipping";
    if (/order|cart/.test(value)) return "cart";
    if (/adjust|setting|filter/.test(value)) return "adjust";
    if (/transfer|move/.test(value)) return "transfer";
    if (/receipt|purchase/.test(value)) return "receipt";
    if (/stock|inventory|sku|item|product|lot/.test(value)) return "package";
    if (/audit|history|movement|transaction/.test(value)) return "audit";
    if (/report|metric|accuracy|productivity|attention|dashboard/.test(value)) return "chart";
    if (/scan|barcode/.test(value)) return "scan";
    if (/search|lookup/.test(value)) return "search";
    if (/export|download/.test(value)) return "download";
    return "";
  }

  function buttonIconName(button) {
    if (button.dataset.icon) return button.dataset.icon;
    if (button.dataset.action && actionIcons[button.dataset.action]) return actionIcons[button.dataset.action];
    const text = button.textContent.trim().toLowerCase();
    if (/^(sign in|log in)$/.test(text)) return "login";
    if (/log out|sign out/.test(text)) return "logout";
    if (/export|download/.test(text)) return "download";
    if (/delete|deactivate|remove|scrap/.test(text)) return "delete";
    if (/edit/.test(text)) return "edit";
    if (/^(add|create|new)\b/.test(text)) return "plus";
    const contextual = iconForText(text);
    if (contextual && /confirm|receive|put away|transfer|ship|pick|count|scan|search|lookup|inspect|allocate|suggest|approve|verify/.test(text)) return contextual;
    if (/save|submit|apply|post/.test(text)) return "save";
    if (/close|cancel|back/.test(text)) return "close";
    return contextual;
  }

  function decorateIcons() {
    document.querySelectorAll("button").forEach((button) => {
      if (button.dataset.iconDecorated) return;
      const name = buttonIconName(button);
      if (!name) return;
      const markup = icon(name, "ui-icon");
      if (!markup) return;
      button.insertAdjacentHTML("afterbegin", markup);
      button.dataset.iconDecorated = "true";
    });
    document.querySelectorAll(".page-heading h1").forEach((heading) => {
      if (heading.querySelector("svg")) return;
      const markup = icon(pageIcons[currentPage], "heading-icon");
      if (markup) heading.insertAdjacentHTML("afterbegin", markup);
    });
    document.querySelectorAll(".panel > h2, .panel > h3").forEach((heading) => {
      if (heading.querySelector("svg")) return;
      const markup = icon(iconForText(heading.textContent), "section-icon");
      if (markup) heading.insertAdjacentHTML("afterbegin", markup);
    });
    document.querySelectorAll(".metric-label").forEach((label) => {
      if (label.querySelector("svg")) return;
      const name = iconForText(label.textContent) || "chart";
      label.insertAdjacentHTML("afterbegin", icon(name, "metric-icon"));
    });
    document.querySelectorAll(".scan-step").forEach((step) => {
      if (!step.querySelector(".ui-icon")) step.insertAdjacentHTML("afterbegin", icon("scan"));
    });
    document.querySelectorAll("#login-form button[type='submit']").forEach((button) => {
      if (!button.dataset.iconDecorated) {
        button.insertAdjacentHTML("afterbegin", icon("login"));
        button.dataset.iconDecorated = "true";
      }
    });
  }

  function getRows(data) {
    if (Array.isArray(data)) return data;
    return data && Array.isArray(data.results) ? data.results : [];
  }

  function setMessage(text, kind = "") {
    message.textContent = text || "";
    message.className = `notice ${kind}`;
    if (text) window.setTimeout(() => {
      if (message.textContent === text) {
        message.textContent = "";
        message.className = "notice";
      }
    }, 7000);
  }

  function loginMessage(text, kind = "error") {
    const node = document.getElementById("login-message");
    node.textContent = text || "";
    node.className = `notice ${kind}`;
  }

  function idempotencyKey() {
    return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function submissionKey(form) {
    if (!pendingSubmissionKeys.has(form)) pendingSubmissionKeys.set(form, idempotencyKey());
    return pendingSubmissionKeys.get(form);
  }

  function clearSubmissionKey(form) {
    pendingSubmissionKeys.delete(form);
  }

  async function refreshAccess() {
    const refresh = sessionStorage.getItem(refreshKey);
    if (!refresh) throw new Error("Session expired. Sign in again.");
    const response = await fetch(`${API}/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Session expired. Sign in again.");
    sessionStorage.setItem(tokenKey, data.access);
    if (data.refresh) sessionStorage.setItem(refreshKey, data.refresh);
  }

  async function api(path, options = {}, retried = false) {
    const headers = new Headers(options.headers || {});
    const token = sessionStorage.getItem(tokenKey);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const response = await fetch(`${API}${path}`, { ...options, headers });
    if (response.status === 401 && !retried && sessionStorage.getItem(refreshKey)) {
      await refreshAccess();
      return api(path, options, true);
    }
    const text = await response.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = { detail: text }; }
    }
    if (!response.ok) {
      const error = data?.error?.message || data?.detail || flattenErrors(data);
      throw new Error(error || `Request failed (${response.status}).`);
    }
    return data;
  }

  function flattenErrors(data) {
    if (!data || typeof data !== "object") return "";
    return Object.entries(data).map(([field, value]) => {
      const text = Array.isArray(value) ? value.join(", ") : typeof value === "object" ? JSON.stringify(value) : value;
      return `${field}: ${text}`;
    }).join(" · ");
  }

  function setConnection() {
    const node = document.getElementById("connection-state");
    const online = navigator.onLine;
    node.textContent = online ? "Online" : "Offline — changes are not recorded";
    node.className = `connection ${online ? "online" : "offline"}`;
  }

  function mayWriteMaster() {
    return user && ["ADMIN", "MANAGER"].includes(user.role);
  }

  function isOperator() {
    return user && user.role !== "VIEWER";
  }

  function isManager() {
    return user && ["ADMIN", "MANAGER"].includes(user.role);
  }

  function renderTable(columns, rows, actions = null) {
    if (!rows.length) return '<div class="empty">No records found.</div>';
    return `<div class="table-wrap"><table><thead><tr>${columns.map(([, title]) => `<th>${esc(title)}</th>`).join("")}${actions ? "<th>Actions</th>" : ""}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map(([key]) => `<td>${esc(row[key] === true ? "Yes" : row[key] === false ? "No" : row[key])}</td>`).join("")}${actions ? `<td>${actions(row)}</td>` : ""}</tr>`).join("")}</tbody></table></div>`;
  }

  function card(label, value, note = "") {
    return `<div class="card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div><div class="subtle">${esc(note)}</div></div>`;
  }

  function showShell() {
    loginScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    document.getElementById("user-summary").textContent = `${user.username} · ${user.role}`;
    document.getElementById("top-user").textContent = `${user.username} (${user.role})`;
    document.querySelectorAll("[data-admin]").forEach((node) => node.classList.toggle("hidden", user.role !== "ADMIN"));
    document.querySelectorAll("[data-manager]").forEach((node) => node.classList.toggle("hidden", !isManager()));
    document.querySelectorAll("[data-operator]").forEach((node) => node.classList.toggle("hidden", !isOperator()));
    document.querySelectorAll("[data-write='master']").forEach((node) => node.classList.toggle("hidden", !mayWriteMaster()));
    setConnection();
    navigate("dashboard");
  }

  async function navigate(page) {
    currentPage = page;
    masterEditing = null;
    document.getElementById("page-title").textContent = pageTitles[page] || "Warehouse";
    document.querySelectorAll("#navigation [data-page]").forEach((node) => node.classList.toggle("active", node.dataset.page === page));
    content.innerHTML = '<div class="card">Loading…</div>';
    try {
      await renderPage(page);
      decorateIcons();
    } catch (error) {
      content.innerHTML = `<div class="notice error">${esc(error.message)}</div>`;
    }
    content.focus({ preventScroll: true });
  }

  async function renderPage(page) {
    if (masterConfig[page]) return renderMaster(page);
    const routes = {
      dashboard: renderDashboard,
      receipts: renderReceipts,
      receive: renderReceive,
      returns: renderReturns,
      inventory: renderInventory,
      transfer: renderTransfer,
      orders: renderOrders,
      picks: renderPicks,
      pack: renderPack,
      adjustments: renderAdjustments,
      counts: renderCounts,
      reports: renderReports,
      expiry: renderExpiry,
      replenishment: renderReplenishment,
      users: renderUsers,
      audit: renderAudit
    };
    if (routes[page]) return routes[page]();
    content.innerHTML = '<div class="empty">Screen not found.</div>';
  }

  async function renderDashboard() {
    const [low, receipts, orders, adjustments] = await Promise.all([
      api("/reports/low-stock/"),
      api("/receipts/"),
      api("/orders/"),
      api("/adjustments/")
    ]);
    const lowRows = getRows(low);
    const receiptRows = getRows(receipts).filter((row) => !["CLOSED", "CANCELLED"].includes(row.status));
    const orderRows = getRows(orders).filter((row) => !["SHIPPED", "CANCELLED"].includes(row.status));
    const pending = getRows(adjustments).filter((row) => row.status === "PENDING");
    content.innerHTML = `
      <div class="page-heading"><h1>Warehouse overview</h1><span class="badge ok">Ledger-backed stock</span></div>
      <div class="card-grid">
        ${card("Low-stock items", lowRows.length, "Available quantity at or below minimum")}
        ${card("Open receipts", receiptRows.length, "Receiving or putaway work")}
        ${card("Open orders", orderRows.length, "Not yet shipped")}
        ${card("Pending adjustments", pending.length, "Manager review required")}
      </div>
      <div class="panel"><h2>Needs attention · Low stock</h2>${renderTable([["sku","SKU"],["description","Item"],["on_hand","Usable on hand"],["reserved","Reserved"],["available","Available"],["expired_qty","Expired"],["missing_expiry_qty","Missing expiry"],["min_stock","Minimum"]], lowRows.slice(0, 10))}</div>
      <div class="card-grid">
        <div class="panel"><h2>Open receipts</h2>${renderTable([["id","Receipt"],["source_reference","PO / reference"],["status","Status"]], receiptRows.slice(0, 8))}</div>
        <div class="panel"><h2>Open orders</h2>${renderTable([["id","Order"],["external_reference","Reference"],["status","Status"]], orderRows.slice(0, 8))}</div>
      </div>`;
  }

  function fieldHtml(field, current, page) {
    const [key, label, type] = field;
    const value = current?.[key] ?? "";
    if (type === "checkbox") return `<label class="field"><span>${esc(label)}</span><input name="${esc(key)}" type="checkbox" ${value ? "checked" : ""}></label>`;
    if (type === "warehouse" || type === "location_kind") {
      const options = type === "warehouse"
        ? window.wmsWarehouses || []
        : ["STORAGE", "RECEIVING", "PACKING", "QUARANTINE"].map((kind) => ({ id: kind, name: kind }));
      const selected = type === "warehouse" ? current?.warehouse : value;
      return `<label class="field">${esc(label)}<select name="${esc(key)}" required>${options.map((option) => `<option value="${esc(type === "warehouse" ? option.id : option.id)}" ${String(selected) === String(option.id) ? "selected" : ""}>${esc(type === "warehouse" ? option.code : option.name)}</option>`).join("")}</select></label>`;
    }
    return `<label class="field">${esc(label)}<input name="${esc(key)}" type="${type === "number" ? "number" : type}" ${type === "number" ? 'step="0.001" min="0"' : ""} value="${esc(value)}" ${["sku","description","name","bin_code"].includes(key) ? "required" : ""}></label>`;
  }

  async function renderMaster(page) {
    const config = masterConfig[page];
    if (page === "locations") window.wmsWarehouses = getRows(await api("/warehouses/"));
    const records = getRows(await api(`/${config.endpoint}/`));
    const edit = masterEditing ? records.find((record) => record.id === masterEditing) : null;
    const form = mayWriteMaster() ? `
      <div class="panel">
        <h2>${edit ? "Edit" : "Add"} ${esc(config.title.slice(0, -1))}</h2>
        <form id="master-form" data-page="${page}" data-id="${edit?.id || ""}">
          <div class="form-grid">${config.fields.map((field) => fieldHtml(field, edit, page)).join("")}</div>
          <div class="actions"><button class="primary" type="submit">Save</button><button class="secondary" type="button" data-action="master-cancel">Cancel</button></div>
        </form>
      </div>` : "";
    content.innerHTML = `
      <div class="page-heading"><h1>${esc(config.title)}</h1><input id="master-search" placeholder="Search ${esc(config.title.toLowerCase())}" aria-label="Search"></div>
      ${form}
      <div id="master-table">${renderTable(config.columns, records, mayWriteMaster() ? (row) => `<div class="row-actions"><button class="secondary small" data-action="master-edit" data-id="${row.id}">Edit</button><button class="danger small" data-action="master-deactivate" data-id="${row.id}">Deactivate</button></div>` : null)}</div>`;
    const search = document.getElementById("master-search");
    search.addEventListener("input", () => {
      const term = search.value.toLowerCase();
      const filtered = records.filter((row) => Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(term)));
      document.getElementById("master-table").innerHTML = renderTable(config.columns, filtered, mayWriteMaster() ? (row) => `<div class="row-actions"><button class="secondary small" data-action="master-edit" data-id="${row.id}">Edit</button><button class="danger small" data-action="master-deactivate" data-id="${row.id}">Deactivate</button></div>` : null);
    });
  }

  async function renderReceipts() {
    const [receiptData, warehouses, locations, suppliers, items] = await Promise.all([
      api("/receipts/"), api("/warehouses/"), api("/locations/"), api("/suppliers/"), api("/items/")
    ]);
    receiptCache = getRows(receiptData);
    const receivingLocations = getRows(locations).filter((row) => row.kind === "RECEIVING" && row.is_active);
    const lines = `
      <div class="form-grid">
        <label class="field">SKU<input name="sku" required></label>
        <label class="field">Expected quantity<input name="expected_qty" type="number" step="0.001" min="0" required></label>
      </div>`;
    content.innerHTML = `
      <div class="page-heading"><h1>Receipts</h1></div>
      ${isOperator() ? `<div class="panel"><h2>Create receipt against PO / source reference</h2>
        <form id="receipt-create-form">
          <div class="form-grid">
            <label class="field">Warehouse<select name="warehouse" required>${getRows(warehouses).map((w) => `<option value="${w.id}">${esc(w.code)} — ${esc(w.name)}</option>`).join("")}</select></label>
            <label class="field">Source type<select name="source_type"><option value="PO">Purchase</option><option value="RETURN">Return</option><option value="TRANSFER">Transfer inbound</option><option value="OTHER">Other inbound</option></select></label>
            <label class="field">PO / source reference<input name="source_reference" required></label>
            <label class="field">Supplier<select name="supplier"><option value="">None</option>${getRows(suppliers).map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join("")}</select></label>
            <label class="field">Receiving bin<select name="receiving_location" required>${receivingLocations.map((l) => `<option value="${l.id}">${esc(l.bin_code)}</option>`).join("")}</select></label>
          </div><h3>First line</h3>${lines}
          <div class="actions"><button class="primary" type="submit">Create receipt</button></div>
        </form></div>` : ""}
      <div class="panel"><h2>Receipt queue</h2>${renderTable([["id","ID"],["source_type","Type"],["source_reference","PO / reference"],["status","Status"],["created_at","Created"]], receiptCache, isOperator() ? (row) => `<button class="primary small" data-action="open-receipt" data-id="${row.id}">${row.source_type === "RETURN" && row.status === "INSPECTING" ? "Inspect return" : "Receive / putaway"}</button>` : null)}</div>`;
  }

  async function renderReturns() {
    const receipts = getRows(await api("/receipts/")).filter((receipt) =>
      receipt.source_type === "RETURN" && !["CLOSED", "CANCELLED"].includes(receipt.status)
    );
    const returnCards = receipts.map((receipt) => {
      const allDispositioned = receipt.lines.every((line) => {
        const total = (line.return_dispositions || []).reduce((sum, entry) => sum + Number(entry.quantity), 0);
        return total >= Number(line.received_qty);
      });
      const lines = receipt.lines.map((line) => {
        const dispositioned = (line.return_dispositions || []).reduce((sum, entry) => sum + Number(entry.quantity), 0);
        const remaining = Math.max(0, Number(line.received_qty) - dispositioned);
        const form = remaining > 0 ? `<form class="return-disposition-form" data-receipt="${receipt.id}">
          <input type="hidden" name="line_id" value="${line.id}">
          <div class="scan-step">Inspect ${esc(line.sku)}${line.lot_number ? ` · Lot ${esc(line.lot_number)}` : ""}${line.expiry_date ? ` · Exp ${esc(line.expiry_date)}` : ""}. Remaining ${remaining}.</div>
          <div class="form-grid">
            <label class="field">Scan item barcode<input name="barcode" class="scan-input" required></label>
            <label class="field">Quantity<input name="quantity" type="number" min="0.001" max="${remaining}" step="0.001" value="${remaining}" required></label>
            <label class="field">Disposition<select name="disposition" required><option value="RESTOCK">Restock</option><option value="QUARANTINE">Quarantine</option>${isManager() ? '<option value="SCRAP">Scrap (manager approval)</option>' : ""}</select></label>
            <label class="field">Destination bin (restock/quarantine)<input name="destination_bin"></label>
            <label class="field">Lot (verify if shown)<input name="lot_number" value="${esc(line.lot_number || "")}"></label>
            <label class="field">Expiry (verify if shown)<input name="expiry_date" type="date" value="${esc(line.expiry_date || "")}"></label>
          </div>
          <label class="field">Inspection reason / condition<textarea name="reason" required></textarea></label>
          <button class="primary" type="submit">Post disposition</button>
        </form>` : "";
        return `<div class="panel"><h3>${esc(line.sku)} · ${esc(line.description)}</h3>
          <p>Expected ${esc(line.expected_qty)} · Received ${esc(line.received_qty)} · Dispositioned ${dispositioned} · Remaining ${remaining}</p>
          ${renderTable([["disposition","Disposition"],["quantity","Quantity"],["destination_bin","Destination"],["reason","Reason"]], line.return_dispositions || [])}
          ${form}</div>`;
      }).join("");
      const closeForm = isManager() && allDispositioned ? `<form class="return-close-form" data-receipt="${receipt.id}">
        <label class="field">Short-receipt reason (required when received quantity is below expected)<input name="short_close_reason"></label>
        <button class="secondary" type="submit">Close return</button>
      </form>` : "";
      return `<section class="panel"><h2>Return ${esc(receipt.source_reference)} · ${esc(receipt.status)}</h2>
        ${receipt.status === "OPEN" ? `<button class="primary" data-action="open-receipt" data-id="${receipt.id}">Receive returned items</button>` : ""}
        ${lines}${closeForm}</section>`;
    }).join("");
    content.innerHTML = `<div class="page-heading"><h1>Returns / inspection</h1></div>
      <p class="subtle">Returned stock remains unavailable until an inspector records a disposition. Scrap requires a manager.</p>
      ${returnCards || '<div class="empty">No open returns. Create a receipt with source type Return to begin.</div>'}`;
    content.querySelectorAll(".return-disposition-form").forEach((form) => {
      const disposition = form.elements.disposition;
      const destination = form.elements.destination_bin;
      const updateDestination = () => {
        const required = disposition.value !== "SCRAP";
        destination.required = required;
        destination.disabled = !required;
      };
      disposition.addEventListener("change", updateDestination);
      updateDestination();
    });
  }

  function receiptOptions() {
    return receiptCache.filter((r) => !["CLOSED", "CANCELLED"].includes(r.status))
      .map((r) => `<option value="${r.id}">${esc(r.source_reference)} · ${esc(r.status)}</option>`).join("");
  }

  function receiptLineOptions(receiptId) {
    const receipt = receiptCache.find((r) => String(r.id) === String(receiptId));
    return (receipt?.lines || []).map((line) => `<option value="${line.id}" data-sku="${esc(line.sku)}" data-remaining="${esc(Number(line.expected_qty) - Number(line.received_qty))}">${esc(line.sku)} · expected ${esc(line.expected_qty)} / received ${esc(line.received_qty)} / putaway ${esc(line.putaway_qty)}</option>`).join("");
  }

  async function ensureReceipts() {
    receiptCache = getRows(await api("/receipts/"));
  }

  async function renderReceive() {
    await ensureReceipts();
    const receiptId = new URLSearchParams(location.hash.split("?")[1] || "").get("receipt") || "";
    if (receiptId && !receiptCache.some((r) => String(r.id) === receiptId)) receiptCache = getRows(await api("/receipts/"));
    const selected = receiptId || receiptCache.find((r) => !["CLOSED", "CANCELLED"].includes(r.status))?.id || "";
    const lines = receiptLineOptions(selected);
    content.innerHTML = `
      <div class="page-heading"><h1>Receive and put away</h1></div>
      <div class="panel"><h2>Receive against source</h2>
        <form id="receive-form">
          <label class="field">Open receipt<select name="receipt_id" id="receive-receipt" required>${receiptOptions()}</select></label>
          <label class="field">Receipt line<select name="line_id" id="receive-line" required>${lines}</select></label>
          <div class="scan-step">Scan the item barcode and compare it with the SKU and expected quantity.</div>
          <label class="field">Scan SKU / barcode<input name="barcode" class="scan-input" autocomplete="off" required autofocus></label>
          <div class="form-grid">
            <label class="field">Received quantity<input name="quantity" type="number" min="0.001" step="0.001" required></label>
            <label class="field">Lot (if required)<input name="lot_number"></label>
            <label class="field">Expiry (if required)<input name="expiry_date" type="date"></label>
            <label class="field">Discrepancy<select name="discrepancy_type"><option value="">None</option><option value="SHORT">Short</option><option value="OVER">Over</option><option value="DAMAGED">Damaged</option><option value="WRONG_ITEM">Wrong item</option></select></label>
          </div>
          <label class="field">Discrepancy note<textarea name="discrepancy_note"></textarea></label>
          <div class="actions"><button class="primary" type="submit">Confirm receipt</button></div>
        </form>
      </div>
      <div class="panel"><h2>Putaway confirmation</h2>
        <form id="putaway-form">
          <label class="field">Receipt<select name="receipt_id" id="putaway-receipt" required>${receiptOptions()}</select></label>
          <label class="field">Receipt line<select name="line_id" id="putaway-line" required>${lines}</select></label>
          <div class="scan-step">Scan the item, then scan the suggested destination bin.</div>
          <div class="form-grid"><label class="field">Item barcode<input name="barcode" class="scan-input" required></label><label class="field">Destination bin<input name="bin_code" class="scan-input" required></label><label class="field">Quantity<input name="quantity" type="number" min="0.001" step="0.001" required></label></div>
          <div class="actions"><button class="secondary" type="button" data-action="suggest-bin">Suggest bin</button><button class="primary" type="submit">Confirm putaway</button></div>
        </form><div id="suggestion" class="status-line"></div>
      </div>`;
    document.getElementById("receive-receipt").value = selected;
    document.getElementById("putaway-receipt").value = selected;
    ["receive-receipt", "putaway-receipt"].forEach((id) => {
      document.getElementById(id).addEventListener("change", (event) => {
        const lineSelect = document.getElementById(id === "receive-receipt" ? "receive-line" : "putaway-line");
        lineSelect.innerHTML = receiptLineOptions(event.target.value);
      });
    });
  }

  async function renderInventory() {
    content.innerHTML = `
      <div class="page-heading"><h1>Stock lookup</h1></div>
      <div class="panel"><form id="inventory-search-form">
        <div class="form-grid"><label class="field">Scan or enter SKU/barcode/bin<input name="query" class="scan-input" autocomplete="off" autofocus></label><label class="field">Exact bin (optional)<input name="bin_code"></label></div>
        <div class="actions"><button class="primary" type="submit">Search stock</button></div>
      </form></div><div id="inventory-results" class="panel"><div class="empty">Scan an item or bin to see on-hand, reserved, and available stock.</div></div>`;
  }

  async function renderTransfer() {
    const [warehouses, locations] = await Promise.all([api("/warehouses/"), api("/locations/")]);
    const bins = getRows(locations).filter((location) =>
      location.kind === "STORAGE" && location.is_active
    );
    content.innerHTML = `<div class="page-heading"><h1>Bin transfer</h1></div>
      <div class="panel"><h2>Move stock between storage bins</h2>
        <form id="transfer-form">
          <label class="field">Warehouse<select name="warehouse" required>${getRows(warehouses).map((warehouse) => `<option value="${warehouse.id}">${esc(warehouse.code)} · ${esc(warehouse.name)}</option>`).join("")}</select></label>
          <div class="scan-step">Scan the item, source bin, and destination bin. Reserved stock cannot be transferred.</div>
          <div class="form-grid">
            <label class="field">Scan item SKU / barcode<input name="barcode" class="scan-input" autocomplete="off" required></label>
            <label class="field">Scan source bin<input name="source_bin" class="scan-input" required></label>
            <label class="field">Scan destination bin<input name="destination_bin" class="scan-input" required></label>
            <label class="field">Quantity<input name="quantity" type="number" min="0.001" step="0.001" required></label>
            <label class="field">Lot (if applicable)<input name="lot_number"></label>
            <label class="field">Expiry (if applicable)<input name="expiry_date" type="date"></label>
          </div>
          <label class="field">Reason / note<input name="notes" maxlength="500"></label>
          <button class="primary" type="submit">Confirm transfer</button>
        </form>
      </div>
      <div class="panel"><h2>Eligible storage bins</h2>${renderTable([["warehouse_code","Warehouse"],["bin_code","Bin"],["zone","Zone"],["is_pickable","Pickable"],["capacity","Capacity"]], bins)}</div>`;
  }

  async function renderOrders() {
    const [data, warehouses, customers] = await Promise.all([api("/orders/"), api("/warehouses/"), api("/customers/")]);
    orderCache = getRows(data);
    const canOperate = isOperator();
    content.innerHTML = `
      <div class="page-heading"><h1>Orders</h1></div>
      ${canOperate ? `<div class="panel"><h2>Create order</h2><form id="order-create-form">
        <div class="form-grid"><label class="field">Warehouse<select name="warehouse">${getRows(warehouses).map((w) => `<option value="${w.id}">${esc(w.code)}</option>`).join("")}</select></label>
        <label class="field">Customer<select name="customer"><option value="">None</option>${getRows(customers).map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></label>
        <label class="field">External order reference<input name="external_reference"></label>
        <label class="field">Priority 1–5<input name="priority" type="number" min="1" max="5" value="3"></label></div>
        <label class="field">Order lines (one SKU,quantity per line)<textarea name="lines" placeholder="SKU-100,2"></textarea></label>
        <div class="actions"><button class="primary" type="submit">Create order</button></div></form></div>
        <div class="panel"><h2>Import CSV</h2><p class="subtle">CSV columns: external_reference, warehouse (code), sku, quantity. One row per order line.</p>
        <form id="order-import-form"><label class="field">CSV file<input name="file" type="file" accept=".csv,text/csv" required></label><button class="secondary" type="submit">Import orders</button></form></div>` : ""}
      <div class="panel"><h2>Order queue</h2>${renderTable([["id","ID"],["external_reference","Reference"],["status","Status"],["priority","Priority"],["created_at","Created"]], orderCache, canOperate ? (row) => row.status === "OPEN" ? `<button class="primary small" data-action="allocate-order" data-id="${row.id}">Allocate / pick</button>` : `<span class="badge">${esc(row.status)}</span>` : null)}</div>`;
  }

  async function renderPicks() {
    const tasks = getRows(await api("/pick-tasks/"));
    content.innerHTML = `<div class="page-heading"><h1>Guided pick tasks</h1></div>
      ${tasks.map((task) => `<div class="panel"><h2>Task ${task.id} · Order ${esc(task.order_reference || task.order)} <span class="badge">${esc(task.status)}</span></h2>
        ${task.lines.map((line) => `<form class="pick-form" data-task="${task.id}" data-line="${line.id}">
          <div class="scan-step">Pick ${esc(line.qty_requested)} of <strong>${esc(line.sku)}</strong> from bin <strong>${esc(line.bin_code)}</strong> · done ${esc(line.qty_picked)}</div>
          <div class="form-grid"><label class="field">Scan bin<input name="bin_code" class="scan-input" required></label><label class="field">Scan item barcode<input name="barcode" class="scan-input" required></label><label class="field">Quantity<input name="quantity" type="number" min="0.001" step="0.001" value="${esc(Number(line.qty_requested) - Number(line.qty_picked))}" required></label></div>
          <button class="primary" type="submit">Confirm pick</button>
        </form>`).join("")}</div>`).join("") || '<div class="empty">No pick tasks.</div>'}`;
  }

  async function renderPack() {
    orderCache = getRows(await api("/orders/"));
    const eligible = orderCache.filter((order) => ["PICKED", "PACKED"].includes(order.status));
    content.innerHTML = `<div class="page-heading"><h1>Packing and shipping</h1></div>
      <div class="panel"><form id="pack-form"><label class="field">Order<select name="order_id" required>${eligible.map((order) => `<option value="${order.id}">${esc(order.external_reference || order.id)} · ${esc(order.status)}</option>`).join("")}</select></label>
        <div class="scan-step">Scan each packed item. Expected quantities are verified against the order.</div>
        <div class="form-grid"><label class="field">Item barcode<input name="barcode" class="scan-input" required></label><label class="field">Quantity<input name="quantity" type="number" min="0.001" step="0.001" value="1" required></label></div>
        <button class="primary" type="submit">Verify packed item</button></form></div>
      <div class="panel"><h2>Mark shipped</h2><form id="ship-form"><div class="form-grid"><label class="field">Order ID<input name="order_id" type="number" required></label><label class="field">Carrier<input name="carrier"></label><label class="field">Tracking number<input name="tracking_number"></label></div><button class="primary" type="submit">Confirm dispatch</button></form><p class="subtle">Shipping posts the inventory deduction. Printing must be completed at the pack station before dispatch.</p></div>`;
  }

  async function renderAdjustments() {
    const [adjustments, items, locations] = await Promise.all([api("/adjustments/"), api("/items/"), api("/locations/")]);
    const rows = getRows(adjustments);
    content.innerHTML = `<div class="page-heading"><h1>Stock adjustments</h1></div>
      ${isOperator() ? `<div class="panel"><h2>Request adjustment</h2><form id="adjustment-form">
        <div class="form-grid"><label class="field">Item<select name="item">${getRows(items).map((i) => `<option value="${i.id}">${esc(i.sku)} · ${esc(i.description)}</option>`).join("")}</select></label>
        <label class="field">Bin<select name="location">${getRows(locations).map((l) => `<option value="${l.id}">${esc(l.bin_code)}</option>`).join("")}</select></label>
        <label class="field">Quantity change (+/-)<input name="qty_change" type="number" step="0.001" required></label>
        <label class="field">Reason code<input name="reason" required></label></div>
        <label class="field">Notes<textarea name="notes" required></textarea></label><button class="primary" type="submit">Request adjustment</button></form></div>` : ""}
      <div class="panel"><h2>Requests</h2>${renderTable([["id","ID"],["sku","SKU"],["bin_code","Bin"],["qty_change","Change"],["reason","Reason"],["status","Status"],["requested_by","Requester"]], rows, isManager() ? (row) => row.status === "PENDING" && row.requested_by !== user.id ? `<button class="primary small" data-action="approve-adjustment" data-id="${row.id}">Approve</button>` : "" : null)}</div>`;
  }

  async function renderCounts() {
    const [counts, warehouses, locations] = await Promise.all([api("/cycle-counts/"), api("/warehouses/"), api("/locations/")]);
    content.innerHTML = `<div class="page-heading"><h1>Cycle counts</h1></div>
      ${isManager() ? `<div class="panel"><h2>Create count task</h2><form id="count-create-form">
        <label class="field">Warehouse<select name="warehouse">${getRows(warehouses).map((w) => `<option value="${w.id}">${esc(w.code)}</option>`).join("")}</select></label>
        <label class="field">Bins (comma-separated location IDs)<input name="location_ids" placeholder="${getRows(locations).slice(0, 2).map((l) => l.id).join(",")}" required></label>
        <button class="primary" type="submit">Create cycle count</button></form></div>` : ""}
      ${getRows(counts).map((count) => `<div class="panel"><h2>Count ${count.id} · ${esc(count.status)}</h2>
        ${renderTable([["id","Line"],["sku","SKU"],["bin_code","Bin"],["lot_number","Lot"],["expiry_date","Expiry"],["expected_qty","Expected"],["counted_qty","Counted"]], count.lines)}
        ${count.lines.map((line) => line.counted_qty === null ? `<form class="count-line-form" data-count="${count.id}"><input type="hidden" name="line_id" value="${line.id}"><div class="scan-step">Scan ${esc(line.bin_code)} then ${esc(line.sku)}${line.lot_number ? ` · Lot ${esc(line.lot_number)}` : ""}${line.expiry_date ? ` · Exp ${esc(line.expiry_date)}` : ""}</div><div class="form-grid"><label class="field">Bin<input name="bin_code" required></label><label class="field">Item barcode<input name="barcode" required></label><label class="field">Lot (if shown)<input name="lot_number"></label><label class="field">Expiry (if shown)<input name="expiry_date" type="date"></label><label class="field">Counted quantity<input name="counted_qty" type="number" min="0" step="0.001" required></label></div><button class="primary" type="submit">Submit count</button></form>` : "").join("")}
        ${isManager() && count.status !== "CLOSED" ? `<button class="primary" data-action="approve-count" data-id="${count.id}">Approve variances</button>` : ""}</div>`).join("") || '<div class="empty">No count tasks.</div>'}`;
  }

  async function renderReports() {
    const [low, moves] = await Promise.all([api("/reports/low-stock/"), api("/movement-history/?page_size=20")]);
    content.innerHTML = `<div class="page-heading"><h1>Reports</h1></div>
      <div class="panel"><h2>Low stock</h2>${renderTable([["sku","SKU"],["description","Item"],["on_hand","Usable on hand"],["reserved","Reserved"],["available","Available"],["expired_qty","Expired"],["missing_expiry_qty","Missing expiry"],["min_stock","Minimum"]], getRows(low))}</div>
      <div class="panel"><h2>Recent stock movements</h2>${renderTable([["occurred_at","Time"],["sku","SKU"],["transaction_type","Type"],["bin_code","Bin"],["qty_change","Change"],["username","User"]], getRows(moves))}</div>
      <p class="subtle">Turnover and productivity reports require reliable cost and task-time data; they are not inferred by this MVP.</p>`;
  }

  async function renderExpiry(days = 30) {
    const report = await api(`/reports/expiry/?days=${encodeURIComponent(days)}`);
    const rows = getRows(report.results);
    const expired = rows.filter((row) => row.status === "EXPIRED");
    const expiring = rows.filter((row) => row.status === "EXPIRING_SOON");
    const missing = rows.filter((row) => row.status === "MISSING_EXPIRY");
    content.innerHTML = `
      <div class="page-heading"><h1>Expiry watch</h1></div>
      <p class="subtle">Expired and missing-expiry lots are excluded from order allocation and usable stock calculations.</p>
      <div class="card-grid">
        ${card("Expired lots", expired.length, "Remove from pickable stock")}
        ${card("Expiring soon", expiring.length, `Within ${report.days} days`)}
        ${card("Missing expiry", missing.length, "Tracked stock requiring data correction")}
      </div>
      <div class="panel"><form id="expiry-filter-form" class="form-grid">
        <label class="field">Upcoming window<select name="days">${[7, 30, 60, 90, 180, 365].map((value) => `<option value="${value}" ${Number(report.days) === value ? "selected" : ""}>${value} days</option>`).join("")}</select></label>
        <div class="actions"><button class="primary" type="submit">Apply</button></div>
      </form></div>
      <div class="panel"><h2>Lots requiring attention</h2>
        ${renderTable([
          ["status","Status"], ["sku","SKU"], ["description","Item"], ["bin_code","Bin"],
          ["lot_number","Lot"], ["expiry_date","Expiry"], ["days_to_expiry","Days remaining"],
          ["qty_on_hand","On hand"], ["qty_reserved","Reserved"], ["available","Available"]
        ], rows)}
      </div>`;
    document.getElementById("expiry-filter-form").addEventListener("submit", (event) => {
      event.preventDefault();
      renderExpiry(Number(new FormData(event.currentTarget).get("days"))).catch((error) => {
        content.innerHTML = `<div class="notice error">${esc(error.message)}</div>`;
      });
    });
  }

  async function renderReplenishment() {
    const rows = getRows(await api("/reports/replenishment/"));
    const reorderRows = rows.filter((row) => row.status === "REORDER");
    const inboundCovered = rows.filter((row) => row.status === "INBOUND_COVERS");
    content.innerHTML = `
      <div class="page-heading"><h1>Replenishment advisor</h1>
        <button id="export-replenishment" class="secondary">Export purchase suggestions CSV</button>
      </div>
      <p class="subtle">Suggestions restore available stock to each SKU's minimum. Open PO quantities and received stock awaiting putaway are included, so covered items are not ordered twice.</p>
      <div class="card-grid">
        ${card("Items to reorder", reorderRows.length, "Projected available below minimum")}
        ${card("Covered by inbound", inboundCovered.length, "No additional order suggested")}
        ${card("SKUs monitored", rows.length, "Active items with a minimum stock")}
      </div>
      <div class="panel"><h2>Purchase suggestions</h2>
        ${renderTable([
          ["status","Status"], ["sku","SKU"], ["description","Item"], ["uom","UOM"],
          ["on_hand","On hand"], ["reserved","Reserved"], ["available","Available"],
          ["expired_qty","Expired"], ["missing_expiry_qty","Missing expiry"],
          ["open_po_qty","Open PO"], ["pending_putaway_qty","Pending putaway"],
          ["projected_available","Projected"], ["min_stock","Minimum"],
          ["suggested_order_qty","Suggested order"]
        ], rows)}
      </div>`;
    document.getElementById("export-replenishment").addEventListener("click", () => {
      const columns = [
        ["sku", "SKU"], ["description", "Description"], ["uom", "UOM"],
        ["available", "Available"], ["expired_qty", "Expired quantity"],
        ["missing_expiry_qty", "Missing expiry quantity"], ["open_po_qty", "Open PO quantity"],
        ["pending_putaway_qty", "Pending putaway quantity"],
        ["projected_available", "Projected available"], ["min_stock", "Minimum stock"],
        ["suggested_order_qty", "Suggested order quantity"], ["status", "Status"]
      ];
      const escapeCsv = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
      const csv = [
        columns.map(([, title]) => escapeCsv(title)).join(","),
        ...reorderRows.map((row) => columns.map(([key]) => escapeCsv(row[key])).join(","))
      ].join("\r\n");
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "wms-replenishment-suggestions.csv";
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  async function renderUsers() {
    if (user.role !== "ADMIN") throw new Error("Administrator role required.");
    const users = getRows(await api("/users/"));
    content.innerHTML = `<div class="page-heading"><h1>Users and roles</h1></div>
      <div class="panel"><h2>Create user</h2><form id="user-create-form"><div class="form-grid">
        <label class="field">Username<input name="username" required></label><label class="field">Email<input name="email" type="email"></label>
        <label class="field">Role<select name="role"><option>OPERATOR</option><option>MANAGER</option><option>VIEWER</option><option>ADMIN</option></select></label>
        <label class="field">Temporary password<input name="password" type="password" minlength="12" required></label></div><button class="primary" type="submit">Create user</button></form></div>
      <div class="panel"><h2>Accounts</h2>${renderTable([["id","ID"],["username","Username"],["email","Email"],["role","Role"],["is_active","Active"]], users)}</div>`;
  }

  async function renderAudit() {
    const logs = getRows(await api("/audit-logs/?page_size=100"));
    content.innerHTML = `<div class="page-heading"><h1>Audit log</h1></div>${renderTable([["occurred_at","Time"],["username","User"],["action","Action"],["entity_type","Entity"],["entity_id","ID"],["reference_type","Reference"],["reference_id","Ref ID"]], logs)}`;
  }

  function formObject(form) {
    const data = new FormData(form);
    const result = {};
    for (const [key, value] of data.entries()) result[key] = value;
    form.querySelectorAll('input[type="checkbox"]').forEach((input) => { result[input.name] = input.checked; });
    return result;
  }

  async function submitMaster(form) {
    const page = form.dataset.page;
    const config = masterConfig[page];
    const body = formObject(form);
    for (const key of ["warehouse", "sequence", "min_stock", "capacity"]) {
      if (body[key] === "") delete body[key];
    }
    if (body.warehouse) body.warehouse = Number(body.warehouse);
    if (body.sequence) body.sequence = Number(body.sequence);
    const id = form.dataset.id;
    await api(`/${config.endpoint}/${id ? `${id}/` : ""}`, {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify(body)
    });
    setMessage(`${config.title.slice(0, -1)} saved.`, "success");
    await navigate(page);
  }

  async function submitReceipt(form) {
    const body = formObject(form);
    const payload = {
      warehouse: Number(body.warehouse),
      source_type: body.source_type,
      source_reference: body.source_reference,
      supplier: body.supplier ? Number(body.supplier) : null,
      receiving_location: Number(body.receiving_location),
      lines: [{ sku: body.sku, expected_qty: body.expected_qty }]
    };
    const receipt = await api("/receipts/", { method: "POST", body: JSON.stringify(payload) });
    setMessage(`Receipt ${receipt.source_reference} created.`, "success");
    location.hash = `receive?receipt=${receipt.id}`;
    await navigate("receive");
  }

  async function submitReceive(form) {
    const values = formObject(form);
    const receiptId = values.receipt_id;
    const body = {
      line_id: Number(values.line_id),
      barcode: values.barcode,
      quantity: values.quantity,
      lot_number: values.lot_number || "",
      expiry_date: values.expiry_date || null,
      discrepancy_type: values.discrepancy_type || "",
      discrepancy_note: values.discrepancy_note || ""
    };
    const result = await api(`/receipts/${receiptId}/receive/`, {
      method: "POST", headers: { "Idempotency-Key": submissionKey(form) }, body: JSON.stringify(body)
    });
    clearSubmissionKey(form);
    setMessage(`Received ${result.received_qty} units. Ledger entry ${result.ledger_id}.`, "success");
    await renderReceive();
  }

  async function submitPutaway(form) {
    const values = formObject(form);
    const result = await api(`/receipts/${values.receipt_id}/putaway/`, {
      method: "POST",
      headers: { "Idempotency-Key": submissionKey(form) },
      body: JSON.stringify({
        line_id: Number(values.line_id), barcode: values.barcode,
        bin_code: values.bin_code, quantity: values.quantity
      })
    });
    clearSubmissionKey(form);
    setMessage(`Putaway confirmed to ${result.actual_bin}.`, "success");
    await renderReceive();
  }

  async function submitInventorySearch(form) {
    const values = formObject(form);
    const params = new URLSearchParams();
    if (values.query) params.set("query", values.query);
    if (values.bin_code) params.set("bin_code", values.bin_code);
    const rows = getRows(await api(`/inventory/?${params}`));
    document.getElementById("inventory-results").innerHTML =
      `<h2>Stock by bin</h2>${renderTable([["sku","SKU"],["description","Item"],["bin_code","Bin"],["lot_number","Lot"],["expiry_date","Expiry"],["qty_on_hand","On hand"],["qty_reserved","Reserved"],["available","Available"]], rows)}`;
  }

  async function submitOrder(form) {
    const values = formObject(form);
    const lines = values.lines.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
      const [sku, quantity] = line.split(",").map((part) => part.trim());
      return { sku, qty_ordered: quantity };
    });
    if (!lines.length || lines.some((line) => !line.sku || !line.qty_ordered)) throw new Error("Enter order lines as SKU,quantity.");
    const body = {
      warehouse: Number(values.warehouse),
      customer: values.customer ? Number(values.customer) : null,
      external_reference: values.external_reference || null,
      priority: Number(values.priority),
      lines
    };
    await api("/orders/", {
      method: "POST", headers: { "Idempotency-Key": submissionKey(form) }, body: JSON.stringify(body)
    });
    clearSubmissionKey(form);
    setMessage("Order created.", "success");
    await renderOrders();
  }

  async function submitCsvImport(form) {
    const file = form.querySelector('input[type="file"]').files[0];
    if (!file) throw new Error("Choose a CSV file.");
    const body = new FormData();
    body.append("file", file);
    const result = await api("/orders/import-orders/", {
      method: "POST",
      headers: { "Idempotency-Key": submissionKey(form) },
      body
    });
    clearSubmissionKey(form);
    setMessage(`Imported ${result.orders.length} orders.`, "success");
    await renderOrders();
  }

  async function submitTransfer(form) {
    const values = formObject(form);
    const result = await api("/inventory/transfer/", {
      method: "POST",
      headers: { "Idempotency-Key": submissionKey(form) },
      body: JSON.stringify({
        warehouse: Number(values.warehouse),
        barcode: values.barcode,
        source_bin: values.source_bin,
        destination_bin: values.destination_bin,
        quantity: values.quantity,
        lot_number: values.lot_number,
        expiry_date: values.expiry_date || null,
        notes: values.notes
      })
    });
    clearSubmissionKey(form);
    setMessage(`Transferred ${result.quantity} ${result.sku}: ${result.source_bin} → ${result.destination_bin}.`, "success");
    await renderTransfer();
  }

  async function submitPick(form) {
    const values = formObject(form);
    const result = await api(`/pick-tasks/${form.dataset.task}/confirm/`, {
      method: "POST", headers: { "Idempotency-Key": submissionKey(form) },
      body: JSON.stringify({
        line_id: Number(form.dataset.line), bin_code: values.bin_code,
        barcode: values.barcode, quantity: values.quantity
      })
    });
    clearSubmissionKey(form);
    setMessage(`Pick confirmed: ${result.qty_picked}.`, "success");
    await renderPicks();
  }

  async function submitPack(form) {
    const values = formObject(form);
    const result = await api(`/orders/${values.order_id}/pack-verify/`, {
      method: "POST", headers: { "Idempotency-Key": submissionKey(form) },
      body: JSON.stringify({ barcode: values.barcode, quantity: values.quantity })
    });
    clearSubmissionKey(form);
    setMessage(`Verified ${result.sku}; packed ${result.qty_packed}.`, "success");
    await renderPack();
  }

  async function submitShip(form) {
    const values = formObject(form);
    const shipment = await api(`/orders/${values.order_id}/ship/`, {
      method: "POST", headers: { "Idempotency-Key": submissionKey(form) },
      body: JSON.stringify({ carrier: values.carrier, tracking_number: values.tracking_number })
    });
    clearSubmissionKey(form);
    setMessage(`Order shipped. Shipment ${shipment.id}.`, "success");
    await renderPack();
  }

  async function submitAdjustment(form) {
    const values = formObject(form);
    await api("/adjustments/", { method: "POST", body: JSON.stringify({
      item: Number(values.item), location: Number(values.location),
      qty_change: values.qty_change, reason: values.reason, notes: values.notes
    }) });
    setMessage("Adjustment request submitted for approval.", "success");
    await renderAdjustments();
  }

  async function submitCountCreate(form) {
    const values = formObject(form);
    const locationIds = values.location_ids.split(",").map((value) => Number(value.trim())).filter(Number.isInteger);
    if (!locationIds.length) throw new Error("Enter one or more location IDs.");
    await api("/cycle-counts/", { method: "POST", body: JSON.stringify({ warehouse: Number(values.warehouse), location_ids: locationIds }) });
    setMessage("Cycle count created.", "success");
    await renderCounts();
  }

  async function submitCountLine(form) {
    const values = formObject(form);
    await api(`/cycle-counts/${form.dataset.count}/count-line/`, {
      method: "POST", body: JSON.stringify({
        line_id: Number(values.line_id), bin_code: values.bin_code,
        barcode: values.barcode, counted_qty: values.counted_qty,
        lot_number: values.lot_number, expiry_date: values.expiry_date || null
      })
    });
    setMessage("Count recorded; inventory is unchanged until approval.", "success");
    await renderCounts();
  }

  async function submitReturnDisposition(form) {
    const values = formObject(form);
    const result = await api(`/receipts/${form.dataset.receipt}/inspect-return/`, {
      method: "POST",
      headers: { "Idempotency-Key": submissionKey(form) },
      body: JSON.stringify({
        line_id: Number(values.line_id),
        barcode: values.barcode,
        quantity: values.quantity,
        disposition: values.disposition,
        destination_bin: values.destination_bin,
        lot_number: values.lot_number,
        expiry_date: values.expiry_date || null,
        reason: values.reason
      })
    });
    clearSubmissionKey(form);
    setMessage(`Return disposition posted: ${result.disposition} ${result.quantity}.`, "success");
    await renderReturns();
  }

  async function submitReturnClose(form) {
    await api(`/receipts/${form.dataset.receipt}/close/`, {
      method: "POST",
      body: JSON.stringify({ short_close_reason: form.elements.short_close_reason.value })
    });
    setMessage("Return closed.", "success");
    await renderReturns();
  }

  async function submitUser(form) {
    const values = formObject(form);
    await api("/users/", { method: "POST", body: JSON.stringify(values) });
    setMessage("User created.", "success");
    await renderUsers();
  }

  async function handleSubmit(event) {
    const form = event.target;
    if (!form.matches("form")) return;
    event.preventDefault();
    try {
      const handlers = {
        "login-form": submitLogin,
        "master-form": submitMaster,
        "receipt-create-form": submitReceipt,
        "receive-form": submitReceive,
        "putaway-form": submitPutaway,
        "inventory-search-form": submitInventorySearch,
        "transfer-form": submitTransfer,
        "order-create-form": submitOrder,
        "order-import-form": submitCsvImport,
        "adjustment-form": submitAdjustment,
        "count-create-form": submitCountCreate,
        "user-create-form": submitUser
      };
      if (form.classList.contains("pick-form")) return await submitPick(form);
      if (form.classList.contains("count-line-form")) return await submitCountLine(form);
      if (form.classList.contains("return-disposition-form")) return await submitReturnDisposition(form);
      if (form.classList.contains("return-close-form")) return await submitReturnClose(form);
      if (form.id === "pack-form") return await submitPack(form);
      if (form.id === "ship-form") return await submitShip(form);
      if (handlers[form.id]) await handlers[form.id](form);
    } catch (error) {
      setMessage(error.message, "error");
    }
  }

  async function submitLogin(form) {
    const values = formObject(form);
    const response = await fetch(`${API}/token/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: values.username, password: values.password })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Sign-in failed.");
    sessionStorage.setItem(tokenKey, data.access);
    sessionStorage.setItem(refreshKey, data.refresh);
    user = data.user;
    sessionStorage.setItem(userKey, JSON.stringify(user));
    showShell();
  }

  async function handleClick(event) {
    const button = event.target.closest("[data-action]");
    if (button) {
      try {
        const id = button.dataset.id;
        switch (button.dataset.action) {
          case "master-edit":
            masterEditing = Number(id);
            return navigate(currentPage);
          case "master-cancel":
            masterEditing = null;
            return navigate(currentPage);
          case "master-deactivate":
            if (!confirm("Deactivate this record? History will be preserved.")) return;
            await api(`/${masterConfig[currentPage].endpoint}/${id}/`, { method: "DELETE" });
            setMessage("Record deactivated.", "success");
            return navigate(currentPage);
          case "open-receipt":
            if (receiptCache.find((receipt) => String(receipt.id) === String(id))?.source_type === "RETURN") {
              const returned = receiptCache.find((receipt) => String(receipt.id) === String(id));
              if (returned.status === "INSPECTING") return navigate("returns");
            }
            location.hash = `receive?receipt=${id}`;
            return navigate("receive");
          case "suggest-bin": {
            const form = document.getElementById("putaway-form");
            const values = formObject(form);
            const result = await api(`/receipts/${values.receipt_id}/putaway-suggestion/?line_id=${values.line_id}&quantity=${values.quantity || 1}`);
            document.getElementById("suggestion").textContent = `Suggested: ${result.bin_code} · ${result.zone || "No zone"}`;
            form.elements.bin_code.value = result.bin_code;
            return;
          }
          case "allocate-order":
            await api(`/orders/${id}/allocate/`, { method: "POST", headers: { "Idempotency-Key": `allocate-${id}` }, body: JSON.stringify({}) });
            setMessage("Order allocated; pick task created.", "success");
            return navigate("picks");
          case "approve-adjustment":
            if (!confirm("Approve and post this stock adjustment?")) return;
            await api(`/adjustments/${id}/approve/`, { method: "POST", body: JSON.stringify({}) });
            setMessage("Adjustment posted to stock ledger.", "success");
            return renderAdjustments();
          case "approve-count":
            if (!confirm("Approve count variances and post adjustments?")) return;
            await api(`/cycle-counts/${id}/approve/`, { method: "POST", body: JSON.stringify({}) });
            setMessage("Count variances approved and posted.", "success");
            return renderCounts();
        }
      } catch (error) {
        setMessage(error.message, "error");
      }
      return;
    }
    const edit = event.target.closest("[data-page]");
    if (edit && edit.dataset.action === "master-edit") return;
    const nav = event.target.closest("#navigation [data-page]");
    if (nav) navigate(nav.dataset.page);
  }

  async function logout() {
    sessionStorage.removeItem(tokenKey);
    sessionStorage.removeItem(refreshKey);
    sessionStorage.removeItem(userKey);
    user = null;
    appShell.classList.add("hidden");
    loginScreen.classList.remove("hidden");
    document.getElementById("login-form").reset();
  }

  document.getElementById("login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitLogin(event.target).catch((error) => loginMessage(error.message));
  });
  document.getElementById("logout-button").addEventListener("click", logout);
  document.getElementById("navigation").addEventListener("click", handleClick);
  content.addEventListener("click", handleClick);
  content.addEventListener("submit", handleSubmit);
  window.addEventListener("online", setConnection);
  window.addEventListener("offline", setConnection);
  decorateIcons();
  new MutationObserver(decorateIcons).observe(content, { childList: true, subtree: true });
  setConnection();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js").catch(() => {});

  if (user && sessionStorage.getItem(tokenKey)) {
    showShell();
  } else {
    user = null;
    sessionStorage.removeItem(userKey);
  }
})();
