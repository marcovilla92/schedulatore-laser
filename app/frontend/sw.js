// Service Worker minimale per PWA installability
// Non fa cache offline — l'app richiede il server attivo

const CACHE_NAME = 'ferrotrack-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass-through: non intercetta le richieste, tutto va al server
  event.respondWith(fetch(event.request));
});
