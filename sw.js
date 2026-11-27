/* CheckMap — service worker : appli hors ligne et cache des tuiles */
const SHELL = 'checkmap-shell-v4', TILES = 'checkmap-tiles-v2', MAX_TILES = 800;
const PRECACHE = ['./', './index.html', './manifest.webmanifest', './icon.svg', './icon-192.png', './icon-512.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css', 'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => Promise.allSettled(PRECACHE.map(u => c.add(u)))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => ![SHELL, TILES].includes(k)).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
async function trim(){
  const c = await caches.open(TILES), keys = await c.keys();
  for (let i = 0; i < keys.length - MAX_TILES; i++) await c.delete(keys[i]);
}
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // API : toujours le réseau
  if (/overpass|photon\.komoot|nominatim|georisques|cerema|routing\.openstreetmap|valhalla|api\.gouv/.test(url.host) || url.pathname.includes('/freq/')) return;
  // Tuiles, polices et style de carte : cache d'abord, mise à jour en arrière-plan
  if (/tile\.openstreetmap\.(org|fr)|arcgisonline\.com|tiles\.openfreemap\.org/.test(url.host)) {
    e.respondWith(caches.open(TILES).then(async c => {
      const hit = await c.match(req);
      const net = fetch(req).then(r => { if (r.ok || r.type === 'opaque') { c.put(req, r.clone()); trim(); } return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  // Page : réseau d'abord, cache si hors ligne
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(r => { caches.open(SHELL).then(c => c.put('./index.html', r.clone())); return r; })
      .catch(() => caches.match('./index.html')));
    return;
  }
  // Bibliothèques, polices, icônes : cache d'abord
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok && (url.origin === location.origin || /unpkg\.com|fonts\.(googleapis|gstatic)\.com/.test(url.host))) {
      const copy = r.clone(); caches.open(SHELL).then(c => c.put(req, copy));
    }
    return r;
  })));
});
