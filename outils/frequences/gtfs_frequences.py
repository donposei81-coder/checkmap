#!/usr/bin/env python3
"""Fréquence des lignes de transport en commun pour CheckMap.

Lit les horaires GTFS publiés sur transport.data.gouv.fr et produit des fichiers JSON
statiques, découpés en tuiles de 0,05°, que l'appli lit autour de l'adresse analysée.
Pour chaque arrêt et chaque ligne : passages par jour, passages entre 7 h et 9 h,
entre 10 h et 16 h, premier et dernier départ, un jour de semaine type.

Python 3.9+, bibliothèque standard uniquement.

    python gtfs_frequences.py --tout                  # tous les réseaux de France
    python gtfs_frequences.py --cherche Lyon --cherche Rennes
    python gtfs_frequences.py --jeu reseau-urbain-et-interurbain-dile-de-france-mobilites
    python gtfs_frequences.py --gtfs mon_reseau.zip   # fichier local
    python gtfs_frequences.py --verifie 45.7578,4.8320  # résumé autour d'un point, après génération
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import os
import shutil
import sys
import time
import urllib.request
import zipfile

API = 'https://transport.data.gouv.fr/api/datasets'
TILE = 0.05              # taille des tuiles en degrés
PEAK = (7 * 60, 9 * 60)  # heure de pointe du matin
DAY = (10 * 60, 16 * 60) # journée
UA = 'CheckMap-frequences/1.0'
csv.field_size_limit(10 ** 8)

# Types de lignes : 0 tram, 1 métro, 2 train, 3 bus, 4 bateau, 6 câble
def mode(route_type):
    try:
        t = int(route_type)
    except ValueError:
        return 3
    if t in (0, 5, 900, 901, 902, 903, 904, 905, 906):
        return 0
    if t in (1, 12, 400, 401, 402, 403, 404, 405, 1100):
        return 1
    if t == 2 or 100 <= t < 200 or 300 <= t < 400:
        return 2
    if t == 4 or 1000 <= t < 1100 or 1200 <= t < 1300:
        return 4
    if t in (6, 7) or 1300 <= t < 1500:
        return 6
    return 3


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------- Lecture du GTFS ----------

class Feed:
    def __init__(self, path):
        self.zf = zipfile.ZipFile(path)
        self.files = {}
        for info in self.zf.infolist():
            name = os.path.basename(info.filename).lower()
            if name.endswith('.txt') and not name.startswith('.'):
                self.files.setdefault(name, info)

    def has(self, name):
        return name in self.files

    def rows(self, name):
        """(index des colonnes, itérateur de lignes) ; fichier absent : ({}, [])."""
        info = self.files.get(name)
        if not info:
            return {}, iter(())
        text = io.TextIOWrapper(self.zf.open(info), encoding='utf-8-sig', errors='replace', newline='')
        reader = csv.reader(text)
        header = next(reader, [])
        return {h.strip().lower(): i for i, h in enumerate(header)}, reader


def col(idx, row, name, default=''):
    i = idx.get(name)
    if i is None or i >= len(row):
        return default
    return row[i].strip()


def minutes(hms):
    if not hms:
        return None
    p = hms.strip().split(':')
    try:
        return int(p[0]) * 60 + int(p[1])
    except (ValueError, IndexError):
        return None


def ymd(s):
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, TypeError):
        return None


def read_calendar(feed):
    cal, extra = {}, {}
    idx, rows = feed.rows('calendar.txt')
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for r in rows:
        sid = col(idx, r, 'service_id')
        a, b = ymd(col(idx, r, 'start_date')), ymd(col(idx, r, 'end_date'))
        if sid and a and b:
            cal[sid] = (a, b, [col(idx, r, d) == '1' for d in days])
    idx, rows = feed.rows('calendar_dates.txt')
    for r in rows:
        sid, d = col(idx, r, 'service_id'), ymd(col(idx, r, 'date'))
        if sid and d:
            extra.setdefault(d, {})[sid] = col(idx, r, 'exception_type') == '1'
    return cal, extra


def active_services(cal, extra, day):
    on = {sid for sid, (a, b, wd) in cal.items() if a <= day <= b and wd[day.weekday()]}
    for sid, added in extra.get(day, {}).items():
        (on.add if added else on.discard)(sid)
    return on


def pick_day(cal, extra, trips_per_service, forced=None, window=28):
    """Mardi ou jeudi le plus chargé des 4 prochaines semaines (ou de la période couverte)."""
    if forced:
        return forced
    bounds = [d for a, b, _ in cal.values() for d in (a, b)] + list(extra)
    if not bounds:
        return None
    lo, hi, today = min(bounds), max(bounds), dt.date.today()
    start = today if lo <= today <= hi else (lo if today < lo else max(lo, hi - dt.timedelta(days=window)))
    best, best_n = None, -1
    for k in range(window):
        d = start + dt.timedelta(days=k)
        if d > hi or d.weekday() not in (1, 3):
            continue
        n = sum(trips_per_service.get(s, 0) for s in active_services(cal, extra, d))
        if n > best_n:
            best, best_n = d, n
    return best


def process(path, forced_day=None):
    feed = Feed(path)
    if not (feed.has('stops.txt') and feed.has('stop_times.txt') and feed.has('trips.txt')):
        raise ValueError('fichiers GTFS manquants')

    cal, extra = read_calendar(feed)

    idx, rows = feed.rows('routes.txt')
    routes = {}
    for r in rows:
        name = col(idx, r, 'route_short_name') or col(idx, r, 'route_long_name')[:24] or '?'
        color = col(idx, r, 'route_color').lstrip('#')
        routes[col(idx, r, 'route_id')] = (name[:24], mode(col(idx, r, 'route_type', '3')), ('#' + color.upper()) if len(color) == 6 else '')

    trip_rows, per_service = [], {}
    idx, rows = feed.rows('trips.txt')
    for r in rows:
        sid = col(idx, r, 'service_id')
        per_service[sid] = per_service.get(sid, 0) + 1
        direction = col(idx, r, 'direction_id') or col(idx, r, 'trip_headsign')[:30] or '0'
        trip_rows.append((col(idx, r, 'trip_id'), col(idx, r, 'route_id'), sid, direction))

    day = pick_day(cal, extra, per_service, forced_day)
    if not day:
        raise ValueError('aucun calendrier')
    on = active_services(cal, extra, day)
    trips = {t: (rid, d) for t, rid, sid, d in trip_rows if sid in on and rid in routes}
    del trip_rows

    freq = {}
    idx, rows = feed.rows('frequencies.txt')
    for r in rows:
        t = col(idx, r, 'trip_id')
        a, b = minutes(col(idx, r, 'start_time')), minutes(col(idx, r, 'end_time'))
        try:
            h = int(col(idx, r, 'headway_secs')) / 60
        except ValueError:
            continue
        if t in trips and a is not None and b is not None and h > 0:
            freq.setdefault(t, []).append((a, b, h))

    idx, rows = feed.rows('stops.txt')
    raw = {}
    for r in rows:
        try:
            lat, lon = float(col(idx, r, 'stop_lat')), float(col(idx, r, 'stop_lon'))
        except ValueError:
            continue
        raw[col(idx, r, 'stop_id')] = (col(idx, r, 'parent_station'), lat, lon, col(idx, r, 'stop_name')[:40])
    station = {sid: (p if p in raw else sid) for sid, (p, *_rest) in raw.items()}

    # (station, route, sens) -> [total, pointe, journée, premier, dernier, avant 3 h, premier après 3 h, dernier en comptant 0-3 h comme fin de soirée]
    # Certains réseaux notent « 00:09 » au lieu de « 24:09 » pour les passages après minuit : sans correction,
    # une ligne de jour afficherait « premier départ 0h09 ».
    agg = {}

    def add(st, rid, d, t):
        k = (st, rid, d)
        v = agg.get(k)
        if v is None:
            v = agg[k] = [0, 0, 0, 10 ** 6, -1, 0, 10 ** 6, -1]
        v[0] += 1
        if PEAK[0] <= t < PEAK[1]:
            v[1] += 1
        if DAY[0] <= t < DAY[1]:
            v[2] += 1
        if t < v[3]:
            v[3] = t
        if t > v[4]:
            v[4] = t
        if t < 180:
            v[5] += 1
            t += 1440
        elif t < v[6]:
            v[6] = t
        if t > v[7]:
            v[7] = t

    pattern = {}  # trajets à fréquence : (arrêt, décalage depuis le premier départ)
    idx, rows = feed.rows('stop_times.txt')
    it, ist, idep, iarr, ipick = idx.get('trip_id'), idx.get('stop_id'), idx.get('departure_time'), idx.get('arrival_time'), idx.get('pickup_type')
    n = 0
    for r in rows:
        n += 1
        try:
            trip = trips.get(r[it].strip())
        except IndexError:
            continue
        if not trip:
            continue
        if ipick is not None and ipick < len(r) and r[ipick].strip() == '1':
            continue
        t = minutes(r[idep] if idep is not None and idep < len(r) and r[idep].strip() else (r[iarr] if iarr is not None and iarr < len(r) else ''))
        st = station.get(r[ist].strip())
        if t is None or st is None:
            continue
        tid = r[it].strip()
        if tid in freq:
            pattern.setdefault(tid, []).append((st, t))
        else:
            add(st, trip[0], trip[1], t)

    for tid, stops in pattern.items():
        t0 = min(t for _, t in stops)
        rid, d = trips[tid]
        for a, b, h in freq[tid]:
            runs = max(1, math.ceil((b - a) / h))
            for k in range(runs):
                for st, t in stops:
                    add(st, rid, d, round(a + k * h + t - t0))

    # Regroupement par arrêt et par ligne : sens le plus desservi
    out = {}
    for (st, rid, _d), v in agg.items():
        lines = out.setdefault(st, {})
        cur = lines.get(rid)
        if cur is None:
            lines[rid] = list(v)
        else:
            cur[0], cur[1], cur[2] = max(cur[0], v[0]), max(cur[1], v[1]), max(cur[2], v[2])
            cur[3], cur[4] = min(cur[3], v[3]), max(cur[4], v[4])
            cur[5], cur[6], cur[7] = max(cur[5], v[5]), min(cur[6], v[6]), max(cur[7], v[7])
    def first_last(v):
        # Ligne de jour avec quelques passages notés entre 0 h et 3 h : ce sont des fins de soirée
        if v[6] < 10 ** 6 and v[5] < 0.25 * v[0]:
            return v[6], v[7]
        return v[3], v[4]

    stations = []
    for st, lines in out.items():
        if st not in raw:
            continue
        _p, lat, lon, name = raw[st]
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            continue
        rl = [[routes[rid][0], routes[rid][1], routes[rid][2], v[0], v[1], v[2], *first_last(v)] for rid, v in lines.items()]
        rl.sort(key=lambda x: (x[1], -x[4], -x[3]))
        stations.append([round(lat, 5), round(lon, 5), name, rl])
    return {'day': day.isoformat(), 'stations': stations, 'rows': n, 'trips': len(trips)}


# ---------- Catalogue transport.data.gouv.fr ----------

def http_get(url, timeout=120):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=timeout)


def catalog():
    with http_get(API) as r:
        data = json.load(r)
    feeds, seen = [], set()
    today = dt.date.today().isoformat()
    for d in data:
        if d.get('type') != 'public-transit':
            continue
        for res in d.get('resources') or []:
            if res.get('format') != 'GTFS' or not res.get('is_available', True) or not res.get('url'):
                continue
            end = (res.get('metadata') or {}).get('end_date')
            if end and end < today:
                continue
            if res['url'] in seen:
                continue
            seen.add(res['url'])
            feeds.append({
                'id': res.get('id'), 'url': res['url'], 'slug': d.get('slug'), 'titre': d.get('title'),
                'ressource': res.get('title'), 'licence': d.get('licence'), 'page': d.get('page_url'),
            })
    return feeds


def download(feed, cache, max_age_days=6):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, f"{feed['id']}.zip")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return path
    tmp = path + '.part'
    with http_get(feed['url'], timeout=600) as r, open(tmp, 'wb') as f:
        shutil.copyfileobj(r, f, 1 << 20)
    os.replace(tmp, path)
    return path


# ---------- Écriture des tuiles ----------

def tile_key(lat, lon):
    return f'{math.floor(lat / TILE)}_{math.floor(lon / TILE)}'


def merge_into(tiles, stations):
    for s in stations:
        t = tiles.setdefault(tile_key(s[0], s[1]), {})
        k = (round(s[0], 4), round(s[1], 4), s[2])
        cur = t.get(k)
        if cur is None:
            t[k] = s
            continue
        by = {(r[0], r[1]): r for r in cur[3]}
        for r in s[3]:
            o = by.get((r[0], r[1]))
            if o is None:
                cur[3].append(r)
            elif (r[4], r[3]) > (o[4], o[3]):
                o[:] = r


def write(tiles, out, sources):
    t_dir = os.path.join(out, 't')
    if os.path.isdir(t_dir):
        shutil.rmtree(t_dir)
    os.makedirs(t_dir)
    for key, st in tiles.items():
        with open(os.path.join(t_dir, key + '.json'), 'w', encoding='utf-8') as f:
            json.dump({'v': 1, 's': list(st.values())}, f, ensure_ascii=False, separators=(',', ':'))
    index = {'v': 1, 'genere': dt.datetime.now().isoformat(timespec='seconds'), 'tuile': TILE,
             'tuiles': len(tiles), 'reseaux': sources}
    with open(os.path.join(out, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, '_headers'), 'w') as f:  # Cloudflare Pages
        f.write('/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=86400\n')
    open(os.path.join(out, '.nojekyll'), 'w').close()  # GitHub Pages


# ---------- Vérification ----------

NAMES = {0: 'Tram', 1: 'Métro', 2: 'Train', 3: 'Bus', 4: 'Bateau', 6: 'Câble'}


def check(out, point):
    lat, lon = (float(x) for x in point.split(','))
    rows = []
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            p = os.path.join(out, 't', tile_key(lat + a * TILE, lon + b * TILE) + '.json')
            if os.path.exists(p):
                rows += json.load(open(p, encoding='utf-8'))['s']
    best = {}
    for s in rows:
        d = 6371000 * math.hypot(math.radians(s[0] - lat), math.radians(s[1] - lon) * math.cos(math.radians(lat)))
        for r in s[3]:
            if d > (800 if r[1] in (1, 2) else 400):
                continue
            k = (r[0], r[1])
            if k not in best or (r[4], r[3]) > (best[k][0][4], best[k][0][3]):
                best[k] = (r, s[2], round(d))
    if not best:
        print('Aucune ligne à proximité.')
    for (name, m), (r, stop, d) in sorted(best.items(), key=lambda x: (x[0][1], -x[1][0][4])):
        wait = f'toutes les {round(120 / r[4])} min (7h-9h)' if r[4] else 'pas de passage 7h-9h'
        print(f'{NAMES.get(m, "?"):6} {name:12} {wait:28} {r[3]:4} passages/jour  {r[6] // 60}h{r[6] % 60:02d}-{r[7] // 60 % 24}h{r[7] % 60:02d}  arrêt {stop} ({d} m)')


def main():
    ap = argparse.ArgumentParser(description='Fréquence des lignes GTFS pour CheckMap')
    ap.add_argument('--tout', action='store_true', help='tous les réseaux GTFS de transport.data.gouv.fr')
    ap.add_argument('--jeu', action='append', default=[], help='identifiant (slug) d\'un jeu de données')
    ap.add_argument('--cherche', action='append', default=[], help='mot(s) dans le titre du jeu ou de la ressource, séparés par des virgules')
    ap.add_argument('--gtfs', action='append', default=[], help='fichier GTFS local (.zip)')
    ap.add_argument('--jour', help='jour de référence AAAA-MM-JJ (par défaut : mardi ou jeudi le plus chargé)')
    ap.add_argument('--sortie', default='freq', help='dossier de sortie (défaut : freq)')
    ap.add_argument('--cache', default='cache-gtfs', help='dossier des fichiers téléchargés')
    ap.add_argument('--efface', action='store_true', help='supprime chaque fichier téléchargé après calcul (peu de place disque)')
    ap.add_argument('--verifie', metavar='LAT,LON', help='affiche les lignes autour d\'un point (après génération)')
    ap.add_argument('--duree-max', type=float, metavar='MIN', help='arrête de traiter de nouveaux réseaux après ce nombre de minutes et écrit ce qui est calculé')
    a = ap.parse_args()

    if a.verifie and not (a.tout or a.jeu or a.cherche or a.gtfs):
        return check(a.sortie, a.verifie)

    forced = dt.date.fromisoformat(a.jour) if a.jour else None
    feeds = [{'id': os.path.basename(p), 'path': p, 'titre': os.path.basename(p)} for p in a.gtfs]
    if a.tout or a.jeu or a.cherche:
        cat = catalog()
        log(f'{len(cat)} fichiers GTFS au catalogue')
        if not a.tout:
            words = [w.strip().lower() for c in a.cherche for w in c.split(',') if w.strip()]
            cat = [f for f in cat if f['slug'] in a.jeu or any(w in f"{f['titre']} {f['ressource']}".lower() for w in words)]
        feeds += cat
    if not feeds:
        ap.error('indiquez --tout, --jeu, --cherche ou --gtfs')

    tiles, sources, t0 = {}, [], time.time()
    for i, f in enumerate(feeds, 1):
        if a.duree_max and time.time() - t0 > a.duree_max * 60:
            log(f'Durée maximale atteinte : {len(feeds) - i + 1} réseaux non traités sur {len(feeds)}')
            break
        label = f"{f.get('titre')} / {f.get('ressource') or ''}".strip(' /')
        try:
            path = f.get('path') or download(f, a.cache)
            r = process(path, forced)
        except Exception as e:  # un réseau en erreur ne bloque pas les autres
            log(f'[{i}/{len(feeds)}] ÉCHEC {label} : {e}')
            continue
        finally:
            if a.efface and not f.get('path'):
                try:
                    os.remove(os.path.join(a.cache, f"{f['id']}.zip"))
                except OSError:
                    pass
        merge_into(tiles, r['stations'])
        sources.append({k: f.get(k) for k in ('titre', 'ressource', 'slug', 'licence', 'page')} | {'jour': r['day'], 'arrets': len(r['stations'])})
        log(f"[{i}/{len(feeds)}] {label} : {len(r['stations'])} arrêts, {r['trips']} courses le {r['day']}")
    write(tiles, a.sortie, sources)
    log(f'{len(tiles)} tuiles écrites dans {a.sortie}/ en {round(time.time() - t0)} s')
    if a.verifie:
        check(a.sortie, a.verifie)


if __name__ == '__main__':
    main()
