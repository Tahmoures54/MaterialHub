const CACHE='materialhub-vnext-1';
const ASSETS=['/static/css/style.css','/static/js/notifications.js','/static/js/charts.js','/static/manifest.json'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request).then(r=>r||caches.match('/warehouse'))));});
