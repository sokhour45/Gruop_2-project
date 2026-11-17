(() => {
  "use strict";

  const drawings = {
    dashboard: '<rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="5" rx="1"/><rect x="13" y="10" width="8" height="11" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/>',
    package: '<path d="m12 3 8.2 4.5v9L12 21l-8.2-4.5v-9L12 3Z"/><path d="m3.8 7.5 8.2 4.6 8.2-4.6M12 12.1V21"/>',
    receive: '<path d="M12 3v12m-5-5 5 5 5-5"/><path d="M5 17v4h14v-4"/>',
    ship: '<path d="M3 7h11v11H3z"/><path d="M14 10h4l3 3v5h-7z"/><circle cx="7.5" cy="19" r="1.5"/><circle cx="17.5" cy="19" r="1.5"/>',
    history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2M3 4v5h5"/>',
    chart: '<path d="M3 3v18h18"/><path d="m7 14 4-4 4 3 6-7"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    logout: '<path d="M10 17l5-5-5-5m5 5H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/>',
    login: '<path d="m14 17 5-5-5-5m5 5H9"/><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7"/>',
    plus: '<path d="M12 5v14m-7-7h14"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    filter: '<path d="M4 7h16M7 12h10m-7 5h4"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
    delete: '<path d="M3 6h18m-2 0-.9 14H5.9L5 6m4 0V4h6v2m-5 4v6m4-6v6"/>',
    save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5m-5 5V3"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    alert: '<path d="m10.3 3.9-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3l-8-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/>'
  };

  function svg(name, className = "ui-icon") {
    const drawing = drawings[name];
    if (!drawing) return "";
    return `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${drawing}</svg>`;
  }

  function nameFromText(text) {
    const value = text.toLowerCase();
    if (/stock in|receive|inbound/.test(value)) return "receive";
    if (/stock out|ship|export/.test(value)) return /export/.test(value) ? "download" : "ship";
    if (/product|inventory|sku/.test(value)) return "package";
    if (/history|transaction/.test(value)) return "history";
    if (/report|category|stock value/.test(value)) return "chart";
    if (/user|account|role/.test(value)) return "users";
    if (/search/.test(value)) return "search";
    if (/apply|filter/.test(value)) return "filter";
    if (/delete|remove/.test(value)) return "delete";
    if (/edit/.test(value)) return "edit";
    if (/save/.test(value)) return "save";
    if (/add|create|new/.test(value)) return "plus";
    if (/log in|sign in/.test(value)) return "login";
    if (/log out|sign out/.test(value)) return "logout";
    if (/low.stock|alert|error/.test(value)) return "alert";
    if (/healthy|success/.test(value)) return "check";
    return "";
  }

  function decorate() {
    document.querySelectorAll("[data-icon]").forEach((element) => {
      if (element.querySelector("svg")) return;
      const markup = svg(element.dataset.icon, "ui-icon");
      if (markup) element.insertAdjacentHTML("afterbegin", markup);
    });

    document.querySelectorAll("button, .button, .link-button").forEach((element) => {
      if (element.querySelector("svg")) return;
      const name = nameFromText(element.textContent);
      const markup = svg(name);
      if (markup) element.insertAdjacentHTML("afterbegin", markup);
    });

    const pageIcon = ({
      "/": "dashboard",
      "/dashboard": "dashboard",
      "/products": "package",
      "/stock-in": "receive",
      "/stock-out": "ship",
      "/history": "history",
      "/reports": "chart",
      "/users": "users"
    })[window.location.pathname.replace(/\/$/, "") || "/"];
    document.querySelectorAll(".page-header h1").forEach((heading) => {
      if (heading.querySelector("svg")) return;
      const markup = svg(pageIcon);
      if (markup) heading.insertAdjacentHTML("afterbegin", markup);
    });

    document.querySelectorAll(".panel h3").forEach((heading) => {
      if (heading.querySelector("svg")) return;
      const markup = svg(nameFromText(heading.textContent));
      if (markup) heading.insertAdjacentHTML("afterbegin", markup);
    });

    document.querySelectorAll(".metric-label").forEach((label) => {
      if (label.querySelector("svg")) return;
      const markup = svg(nameFromText(label.textContent) || "chart", "metric-icon");
      if (markup) label.insertAdjacentHTML("afterbegin", markup);
    });

    document.querySelectorAll(".login-card h2").forEach((heading) => {
      if (heading.querySelector("svg")) return;
      heading.insertAdjacentHTML("afterbegin", svg("login", "heading-icon"));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", decorate, { once: true });
  } else {
    decorate();
  }
})();
