const CACHE_NAME = "warehouse-shell-v7";
const APP_SHELL = [
  "/",
  "/static/warehouse_api/app.css",
  "/static/warehouse_api/app.js",
  "/static/warehouse_api/manifest.webmanifest"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request).then((cached) => cached || Response.error()))
  );
});
