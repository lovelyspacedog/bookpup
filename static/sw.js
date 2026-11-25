/* BookPup offline shell — guide/changelog + sign-in assets only (__VERSION__) */
"use strict";

const CACHE = "bookpup-shell-__VERSION__";

const SHELL = [
  "/",
  "/index.html",
  "/static/kennel/theme.css?v=__VERSION__",
  "/static/bookpup.css?v=__VERSION__",
  "/static/app-core.js?v=__VERSION__",
  "/static/app-boot.js?v=__VERSION__",
  "/static/app-docs.js?v=__VERSION__",
  "/static/app-dig.js?v=__VERSION__",
  "/static/data/dig-bestsellers.json",
  "/static/app-ux.js?v=__VERSION__",
  "/static/app-pwa.js?v=__VERSION__",
  "/static/app-offline-store.js?v=__VERSION__",
  "/static/reader.js?v=__VERSION__",
  "/static/vendor/jszip.min.js",
  "/static/vendor/epub.min.js",
  "/static/guide.md",
  "/static/changelog.md",
  "/static/about.md",
  "/static/pwa/icon-192.png",
  "/static/pwa/icon-512.png",
  "/static/pwa/icon-192-maskable-flat.png",
  "/static/pwa/icon-512-maskable-flat.png",
  "/static/pwa/apple-touch-icon.png",
  "/static/pwa/favicon-32-flat.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await Promise.all(
        SHELL.map(async (url) => {
          try {
            const res = await fetch(url, { cache: "reload" });
            if (res.ok) await cache.put(url, res);
          } catch {
            /* skip unreachable asset during install */
          }
        })
      );
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("bookpup-shell-") && k !== CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

function matchesShell(url) {
  const full = url.pathname + url.search;
  return SHELL.some((entry) => {
    const [base, qs] = entry.split("?");
    if (qs) return full === entry;
    return url.pathname === base;
  });
}

function docPath(pathname) {
  return (
    pathname === "/static/guide.md" ||
    pathname === "/static/changelog.md" ||
    pathname === "/static/about.md"
  );
}

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/opds/")) return;

  if (url.pathname === "/" || url.pathname === "/index.html") {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request).then((r) => r || caches.match("/index.html")))
    );
    return;
  }

  if (matchesShell(url) || docPath(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const network = fetch(event.request)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(event.request, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});