// Parcours complet de CheckMap dans un vrai navigateur, avec les vrais services en ligne
// (fonds de carte, adresses, itinéraires, zones de marche, lieux, fiche de l'adresse).
// Résultat : verification/rapport.json et des captures PNG.
// Usage : servir l'appli (ex. python3 -m http.server 8080), puis node outils/verification/verifier.mjs
import { chromium } from 'playwright';
import fs from 'node:fs';

const SITE = process.env.SITE || 'http://127.0.0.1:8080/';
const DONNEES = process.env.DONNEES || 'https://donposei81-coder.github.io/checkmap/';   // lieux/ et freq/ publiés
const SORTIE = process.env.SORTIE || 'verification';
fs.mkdirSync(SORTIE, { recursive: true });

const rapport = { site: SITE, debut: new Date().toISOString(), scenarios: [] };
const pause = ms => new Promise(r => setTimeout(r, ms));
// Captures en JPEG ; avec AFFICHER_CAPTURES=1 elles sont aussi écrites dans le journal (base64), lisibles sans télécharger l'artefact
const captures = [];
async function capture(page, nom){
  const f = `${SORTIE}/${nom}.jpg`;
  await page.screenshot({ path: f, type: 'jpeg', quality: 70 });
  captures.push(f);
}
// Exemples de réponses brutes de la Géoplateforme, pour contrôler leur format
rapport.exemples = {};
for (const [nom, url] of [
  ['adresse-lyon', 'https://data.geopf.fr/geocodage/reverse?lat=45.757800&lon=4.832000&index=address&limit=1'],
  ['adresse-paris', 'https://data.geopf.fr/geocodage/reverse?lat=48.867450&lon=2.363620&index=address&limit=1'],
  ['recherche-montmartre', 'https://data.geopf.fr/geocodage/search?q=montmartre&limit=3&index=address,poi&autocomplete=1&lat=48.86745&lon=2.36362']
]) {
  try { rapport.exemples[nom] = JSON.stringify(await (await fetch(url)).json()).slice(0, 2500); } catch (e) { rapport.exemples[nom] = String(e); }
}
// Réponses brutes de la recherche (sans position et autour de République), pour régler l'ordre des suggestions hors ligne
const RECHERCHES = ['15 rue nationale lille', 'montmartre', 'gare de lyon', 'place bellecour', 'tour eiffel', 'hopital rennes', 'hopital ren',
  '5 avenue anatole france', 'fort-de-france', 'mairie de bordeaux', 'rue de la gare', 'bastille', 'lyon', 'marseille vieux port', 'chu rennes', 'aeroport nice'];
rapport.brut = {};
for (const q of RECHERCHES) {
  const url = `https://data.geopf.fr/geocodage/search?q=${encodeURIComponent(q)}&limit=10&index=address,poi&autocomplete=1`;
  try {
    rapport.brut[q] = { sans: await (await fetch(url)).json(), avec: await (await fetch(url + '&lat=48.86745&lon=2.36362')).json() };
  } catch (e) { rapport.brut[q] = String(e); }
}
if (process.env.AFFICHER_BRUT) console.log('BRUT ' + JSON.stringify(rapport.brut));
delete rapport.brut;
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });

async function contexte(mobile){
  const ctx = await browser.newContext(mobile
    ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true, locale: 'fr-FR', timezoneId: 'Europe/Paris', serviceWorkers: 'block', acceptDownloads: true }
    : { viewport: { width: 1280, height: 820 }, deviceScaleFactor: 1, locale: 'fr-FR', timezoneId: 'Europe/Paris', serviceWorkers: 'block', acceptDownloads: true });
  // Les fichiers de lieux et de fréquences ne sont pas dans le dépôt : on prend ceux publiés en ligne
  await ctx.route(/\/(lieux|freq)\//, async route => {
    const u = new URL(route.request().url());
    const cible = new URL(u.pathname.replace(/^.*?\/(lieux|freq)\//, '$1/'), DONNEES).href;
    try { await route.fulfill({ response: await route.fetch({ url: cible }) }); } catch { await route.abort(); }
  });
  return ctx;
}
function suivre(page, s){
  s.hotes = {}; s.erreurs = [];
  page.on('request', r => { const h = new URL(r.url()).host; s.hotes[h] = (s.hotes[h] || 0) + 1; });
  page.on('requestfailed', r => s.erreurs.push(`échec ${r.url().slice(0, 150)} ${(r.failure() || {}).errorText || ''}`));
  page.on('response', r => { if (r.status() >= 400) s.erreurs.push(`${r.status()} ${r.url().slice(0, 150)}`); });
  page.on('pageerror', e => s.erreurs.push(`js ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') s.erreurs.push(`console ${m.text().slice(0, 200)}`); });
}
const etat = page => page.evaluate(() => {
  const t = id => { const e = document.getElementById(id); return e && !e.hidden ? e.innerText.replace(/\s*\n+\s*/g, ' | ').trim() : null; };
  return {
    score: t('scoreV'), adresse: t('placeLabel'), erreur: t('err'), statut: t('status'),
    q15: t('q15'), trajets: t('trips'), fiche: t('fiche'),
    marqueurs: document.querySelectorAll('.xm, .cl').length,
    zonesMarche: document.querySelectorAll('.leaflet-overlay-pane path').length,
    carteGL: !!document.querySelector('canvas.maplibregl-canvas'),
    fond: [...document.querySelectorAll('.leaflet-control-layers-base input')].findIndex(i => i.checked),
    mentions: (document.querySelector('.leaflet-control-attribution') || {}).innerText,
    theme: document.body.className
  };
});
async function attendreScore(page){
  await page.waitForFunction(() => /\d/.test(document.getElementById('scoreV').textContent) || !document.getElementById('err').hidden, null, { timeout: 70000 }).catch(() => {});
}

// 1. Parcours sur téléphone, à plusieurs adresses
const ADRESSES = [
  { nom: 'paris-republique', hash: '#lat=48.86745&lon=2.36362&r=800' },
  { nom: 'lyon-bellecour', hash: '#lat=45.75780&lon=4.83200&r=800' },
  { nom: 'fort-de-france', hash: '#lat=14.60370&lon=-61.07310&r=800' },
  { nom: 'loches', hash: '#lat=47.12830&lon=0.99520&r=1500' }
];
const LIEUX = [
  { id: 'p1', kind: 'travail', name: 'Bureau', c: [48.8738, 2.2950], label: 'Place Charles de Gaulle, Paris' },
  { id: 'p2', kind: 'ecole', name: 'École', c: [48.8650, 2.3700], label: 'Paris 11e' },
  { id: 'p3', kind: 'famille', name: 'Famille à Lyon', c: [45.7640, 4.8357], label: 'Lyon' }
];
for (const a of ADRESSES) {
  const s = { nom: a.nom, appareil: 'téléphone' }; rapport.scenarios.push(s);
  const ctx = await contexte(true), page = await ctx.newPage(); suivre(page, s);
  await page.addInitScript(l => { if (!sessionStorage.getItem('init')) { localStorage.clear(); localStorage.setItem('cm:places', JSON.stringify(l)); sessionStorage.setItem('init', '1'); } }, LIEUX);
  const t0 = Date.now();
  await page.goto(SITE + 'index.html' + a.hash);
  await attendreScore(page);
  s.secondesScore = (Date.now() - t0) / 1000;
  await page.waitForFunction(() => { const q = document.getElementById('q15'); return q && !q.hidden; }, null, { timeout: 30000 }).catch(() => {});
  await page.waitForFunction(() => !/…/.test(document.getElementById('trips').innerText), null, { timeout: 30000 }).catch(() => {});
  await pause(6000);
  Object.assign(s, await etat(page));
  await capture(page, `${a.nom}-telephone`);
  await ctx.close();
}

// 2. Chaque fond de carte, sur ordinateur
{
  const s = { nom: 'fonds-de-carte', appareil: 'ordinateur', fonds: [] }; rapport.scenarios.push(s);
  const ctx = await contexte(false), page = await ctx.newPage(); suivre(page, s);
  await page.goto(SITE + 'index.html#lat=48.86745&lon=2.36362&r=800');
  await attendreScore(page); await pause(5000);
  const noms = await page.$$eval('.leaflet-control-layers-base label', l => l.map(x => x.innerText.trim()));
  for (let i = 0; i < noms.length; i++) {
    await page.evaluate(i => document.querySelectorAll('.leaflet-control-layers-base input')[i].click(), i);
    await pause(7000);
    const e = await etat(page);
    s.fonds.push({ nom: noms[i], actif: e.fond === i, theme: e.theme, carteGL: e.carteGL, mentions: e.mentions });
    await capture(page, `fond-${i + 1}`);
  }
  await ctx.close();
}

// 3. Recherche d'adresse : suggestions puis recherche validée
{
  const s = { nom: 'recherche', appareil: 'ordinateur', suggestions: {}, recherches: {} }; rapport.scenarios.push(s);
  const ctx = await contexte(false), page = await ctx.newPage(); suivre(page, s);
  await page.goto(SITE + 'index.html#lat=48.86745&lon=2.36362&r=800');
  await attendreScore(page);
  for (const q of ['15 rue nationale lille', 'montmartre', 'gare de lyon', 'place bellecour', 'tour eiffel', 'hopital rennes', '5 avenue anatole france', 'fort-de-france']) {
    await page.fill('#q', ''); await page.type('#q', q, { delay: 30 });
    await page.waitForFunction(() => !document.getElementById('sugg').hidden && document.querySelector('#sugg li'), null, { timeout: 12000 }).catch(() => {});
    await pause(900);
    s.suggestions[q] = await page.$$eval('#sugg li', l => l.map(x => x.innerText.replace(/\s*\n\s*/g, ' / ')));
  }
  await capture(page, 'recherche');
  for (const q of ['15 rue nationale lille', '10 rue de la paix paris', 'mairie de bordeaux']) {
    const avant = await page.evaluate(() => location.hash);
    await page.fill('#q', q); await page.press('#q', 'Enter');
    await page.waitForFunction(h => location.hash !== h, avant, { timeout: 15000 }).catch(() => {});
    await attendreScore(page); await pause(1500);
    s.recherches[q] = await page.evaluate(() => ({ adresse: document.getElementById('placeLabel').textContent, position: location.hash.slice(0, 40), score: document.getElementById('scoreV').textContent }));
  }
  await ctx.close();
}

// 4. Bilan PNG et PDF
{
  const s = { nom: 'bilan', appareil: 'ordinateur' }; rapport.scenarios.push(s);
  const ctx = await contexte(false), page = await ctx.newPage(); suivre(page, s);
  await page.goto(SITE + 'index.html#lat=48.86745&lon=2.36362&r=800');
  await attendreScore(page); await pause(3000);
  await page.click('#bilanBtn');
  await page.waitForSelector('#bilanPrev img', { timeout: 20000 }).catch(() => {});
  const dl = page.waitForEvent('download', { timeout: 25000 }).catch(() => null);
  await page.click('#bilanPdf');
  const d = await dl;
  s.pdf = d ? d.suggestedFilename() : null;
  if (d) { await d.saveAs(`${SORTIE}/bilan.pdf`); s.pdfOctets = fs.statSync(`${SORTIE}/bilan.pdf`).size; }
  await capture(page, 'bilan');
  await ctx.close();
}

rapport.fin = new Date().toISOString();
fs.writeFileSync(`${SORTIE}/rapport.json`, JSON.stringify(rapport, null, 2));
await browser.close();
console.log(JSON.stringify(rapport, null, 2));
if (process.env.AFFICHER_CAPTURES) for (const f of captures) console.log(`CAPTURE ${f.split('/').pop()} ${fs.readFileSync(f).toString('base64')}`);
