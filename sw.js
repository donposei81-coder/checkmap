/* CheckMap — service worker : appli hors ligne et cache des tuiles */
const SHELL = 'checkmap-shell-v6', TILES = 'checkmap-tiles-v3', MAX_TILES = 800;
const PRECACHE = ['./', './index.html', './manifest.webmanifest', './icon.svg', './icon-192.png', './icon-512.png',
  './lib/leaflet/leaflet.css', './lib/leaflet/leaflet.js', './lib/leaflet/MarkerCluster.css', './lib/leaflet/leaflet.markercluster.js',
  './lib/maplibre/maplibre-gl.css', './lib/maplibre/maplibre-gl.js', './lib/maplibre/leaflet-maplibre-gl.js',
  './lib/fonts/overpass-latin-400-normal.woff2', './lib/fonts/overpass-latin-600-normal.woff2', './lib/fonts/overpass-latin-800-normal.woff2'];

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
  if (/overpass|photon\.komoot|georisques|cerema|api\.gouv/.test(url.host) || (url.host === 'data.geopf.fr' && !url.pathname.startsWith('/wmts')) || /\/(freq|lieux)\//.test(url.pathname)) return;
  // Tuiles, polices et style de carte : cache d'abord, mise à jour en arrière-plan
  if (url.host === 'tiles.openfreemap.org' || url.host === 'data.geopf.fr') {
    e.respondWith(caches.open(TILES).then(async c => {
      const hit = await c.match(req);
      const net = fetch(req).then(r => { if (r.ok || r.type === 'opaque') { c.put(req, r.clone()); trim(); } return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  // Page : réseau d'abord, toujours revalidée pour recevoir les mises à jour ; cache si hors ligne
  if (req.mode === 'navigate') {
    const key = /\/(index\.html)?$/.test(url.pathname) ? './index.html' : req.url;
    e.respondWith(fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' }).then(r => { if (r.ok) { const copy = r.clone(); caches.open(SHELL).then(c => c.put(key, copy)); } return r; })
      .catch(() => caches.match(key)));
    return;
  }
  // Bibliothèques, polices, icônes : cache d'abord
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok && url.origin === location.origin) {
      const copy = r.clone(); caches.open(SHELL).then(c => c.put(req, copy));
    }
    return r;
  })));
});
