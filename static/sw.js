// v3 evicts any /llcheck/ responses this worker cached before it learned to
// keep out of that app's way.
const CACHE = 'recipeparse-v3';

const PRECACHE = [
  '/',
  '/static/app.js?v=12',
  '/static/style.css?v=12',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  // llcheck is a different app sharing this origin at /llcheck/, with its own
  // service worker scoped there. Leave its requests alone entirely.
  //
  // Two reasons, and the second is the serious one. The catch-all at the bottom
  // is cache-first, and /llcheck/api/... does not match the /api/ test above,
  // so live Lightning Lane return times would be cached and replayed as
  // current — that app suppresses a stale reading rather than show it, because
  // acting on one means walking across a park for a pass that no longer
  // exists. And nothing here catches a failed fetch, so on a flaky network a
  // navigation rejects and the browser shows ERR_FAILED instead of letting
  // that app render its own error state.
  if (url.pathname === '/llcheck' || url.pathname.startsWith('/llcheck/')) return;

  // API: network first, fall back to cache for offline read
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok && request.method === 'GET') {
            const clone = response.clone();
            caches.open(CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Images in static/imported: cache on first load
  if (url.pathname.startsWith('/static/imported/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Everything else: cache first
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE).then(cache => cache.put(request, clone));
        }
        return response;
      });
    })
  );
});
