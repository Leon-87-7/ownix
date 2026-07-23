const CACHE_PREFIX = "ownix-offline-";
const CACHE_NAME = CACHE_PREFIX + "v1";
const OFFLINE_URL = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            // Origin-wide listing: only reap our own stale versions, never
            // caches owned by other features (e.g. MSW in mock mode).
            .filter(
              (key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME,
            )
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(
    fetch(event.request).catch(() =>
      // Scope the lookup to our own cache (caches.match is origin-wide).
      // Cache can miss (install fetch failed, storage evicted) — a plain
      // network error beats respondWith(undefined), which throws.
      caches
        .open(CACHE_NAME)
        .then((cache) => cache.match(OFFLINE_URL))
        .then((cached) => cached ?? Response.error()),
    ),
  );
});
