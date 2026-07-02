// Service Worker DISABILITATO — mantiene compatibilità PWA ma non intercetta fetch.
// (In dev il pass-through fetch handler causava blocchi di rete casuali:
//  event.respondWith(fetch(event.request)) fallisce a caldo su Windows.)

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// NESSUN fetch handler: il browser va direttamente in rete senza passare per il SW.
