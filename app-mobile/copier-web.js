// Copie l'appli web (dossier parent) dans www/ pour Capacitor
const fs = require('fs');
const path = require('path');
const src = path.join(__dirname, '..');
const dest = path.join(__dirname, 'www');
fs.rmSync(dest, { recursive: true, force: true });
fs.mkdirSync(dest);
for (const f of ['index.html', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png']) {
  fs.copyFileSync(path.join(src, f), path.join(dest, f));
}
console.log('Appli web copiée dans www/');
