#!/usr/bin/env python3
"""Lieux du quotidien pour CheckMap, extraits d'OpenStreetMap.

Commerces, santé, écoles, parcs, sport, poste, arrêts de transport, bornes, vélos, toilettes :
les mêmes lieux que ceux demandés à l'API Overpass, mais calculés une fois par semaine à partir
des extraits Geofabrik et découpés en tuiles de 0,05°. L'appli lit les tuiles autour de
l'adresse analysée ; elle n'interroge Overpass qu'en secours.

Python 3.9+ et osmium-tool (paquet « osmium-tool » sous Debian et Ubuntu, « brew install osmium-tool » sur Mac).

    python lieux_osm.py --sortie lieux                       # France métropolitaine et outre-mer
    python lieux_osm.py --extrait https://download.geofabrik.de/europe/france/reunion-latest.osm.pbf
    python lieux_osm.py --pbf mon_extrait.osm.pbf            # fichier local
    python lieux_osm.py --verifie 48.8675,2.3636              # résumé autour d'un point, après génération

Format d'une tuile (t/{y}_{x}.tsv, y = floor(lat / 0,05), x = floor(lon / 0,05)) : une ligne par lieu,
colonnes séparées par des tabulations, dans l'ordre de la requête Overpass de l'appli :
type, lat, lon, name, brand, network, operator, shop, amenity, leisure, healthcare, railway, station, highway, access.
La dernière ligne est « fin ». Une tuile trop chargée (centre des grandes villes) contient seulement
« decoupe » : ses lieux sont alors dans des sous-tuiles de 0,01° (s/{Y}_{X}.tsv).
"""
import argparse
import datetime as dt
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.request

GEOFABRIK = 'https://download.geofabrik.de/europe/'
EXTRAITS = [
    ('France métropolitaine', GEOFABRIK + 'france-latest.osm.pbf'),
    ('Guadeloupe', GEOFABRIK + 'france/guadeloupe-latest.osm.pbf'),
    ('Martinique', GEOFABRIK + 'france/martinique-latest.osm.pbf'),
    ('Guyane', GEOFABRIK + 'france/guyane-latest.osm.pbf'),
    ('La Réunion', GEOFABRIK + 'france/reunion-latest.osm.pbf'),
    ('Mayotte', GEOFABRIK + 'france/mayotte-latest.osm.pbf'),
]
TILE = 0.05      # tuiles
SUB = 0.01       # sous-tuiles des zones denses
SEUIL = 3000     # lieux au-delà desquels une tuile est découpée
UA = 'CheckMap-lieux/1.0'
COLONNES = ['name', 'brand', 'network', 'operator', 'shop', 'amenity', 'leisure', 'healthcare', 'railway', 'station', 'highway', 'access']

# Mêmes étiquettes que la requête Overpass de l'appli (index.html, buildQuery)
FILTRES = [
    'nwr/shop=bakery,pastry,supermarket,convenience,greengrocer,butcher,cheese,seafood,farm',
    'nwr/amenity=restaurant,cafe,fast_food,marketplace,doctors,clinic,hospital,pharmacy,dentist,school,kindergarten,childcare,post_office,bank,charging_station,bicycle_rental,toilets',
    'nwr/healthcare=doctor,dentist,physiotherapist',
    'nwr/leisure=park,playground,garden,fitness_centre,sports_centre,swimming_pool',
    'n/highway=bus_stop',
    'nwr/railway=station,halt,tram_stop',
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


VALEURS = {}
for _f in FILTRES:
    _k, _v = _f.split('/', 1)[1].split('=')
    VALEURS[_k] = set(_v.split(','))


def garde(t):
    """Garde les lieux demandés (et pas les nœuds voisins qu'osmium ajoute pour dessiner les surfaces),
    sans ce que l'appli ignorerait de toute façon : lieux privés, piscines de jardin, jardins sans nom."""
    if not any(t.get(k) in v for k, v in VALEURS.items()):
        return False
    if t.get('access') in ('private', 'no'):
        return False
    lei = t.get('leisure')
    autres = any(t.get(k) in VALEURS[k] for k in ('shop', 'amenity', 'healthcare', 'railway', 'highway'))
    if lei == 'swimming_pool' and not autres and not (t.get('name') or t.get('access') in ('yes', 'customers')):
        return False
    if lei == 'garden' and not autres and not t.get('name'):
        return False
    return True


def centre(geom):
    """Centre du rectangle englobant, comme « out center » d'Overpass."""
    if geom['type'] == 'Point':
        return geom['coordinates'][1], geom['coordinates'][0]
    lo1 = la1 = 1e9
    lo2 = la2 = -1e9
    pile = [geom['coordinates']]
    while pile:
        c = pile.pop()
        if c and isinstance(c[0], (int, float)):
            lo, la = c[0], c[1]
            lo1, lo2, la1, la2 = min(lo1, lo), max(lo2, lo), min(la1, la), max(la2, la)
        else:
            pile.extend(c)
    if lo1 > lo2:
        return None
    return (la1 + la2) / 2, (lo1 + lo2) / 2


def propre(v):
    return ' '.join(str(v).split())[:120]


def telecharge(url, dest):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    tmp = dest + '.part'
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
        shutil.copyfileobj(r, f, 1 << 22)
    os.replace(tmp, dest)


def osmium(*args):
    subprocess.run(['osmium', *args], check=True)


def lit_extrait(nom, pbf, travail, lieux, vus):
    """Filtre un extrait avec osmium et ajoute ses lieux à la liste. Renvoie (nombre, rectangle)."""
    filtre = os.path.join(travail, 'filtre.osm.pbf')
    seq = os.path.join(travail, 'lieux.geojsonseq')
    t0 = time.time()
    osmium('tags-filter', pbf, *FILTRES, '-o', filtre, '--overwrite', '--no-progress')
    osmium('export', filtre, '-f', 'geojsonseq', '-a', 'type,id', '-o', seq, '--overwrite', '--no-progress')
    n, bb = lit_geojsonseq(seq, lieux, vus)
    for f in (filtre, seq):
        os.remove(f)
    log(f'  {nom} : {n} lieux en {time.time() - t0:.0f} s')
    return n, bb


def lit_geojsonseq(chemin, lieux, vus):
    n = 0
    bb = [90.0, 180.0, -90.0, -180.0]
    with open(chemin, encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip().lstrip('\x1e')
            if not ligne:
                continue
            try:
                ft = json.loads(ligne)
            except ValueError:
                continue
            p = ft.get('properties') or {}
            typ, oid = p.get('@type', ''), p.get('@id', '')
            if typ == 'area':                      # anciennes versions d'osmium : surfaces numérotées à part
                typ, oid = ('relation', oid // 2) if isinstance(oid, int) and oid % 2 else ('way', oid // 2 if isinstance(oid, int) else oid)
            if oid != '' and (typ, oid) in vus:
                continue
            if not garde(p):
                continue
            c = ft.get('geometry') and centre(ft['geometry'])
            if not c:
                continue
            vus.add((typ, oid))
            lat, lon = c
            lieux.append((lat, lon, '\t'.join([typ or 'node', f'{lat:.6f}', f'{lon:.6f}', *(propre(p.get(k, '')) for k in COLONNES)])))
            bb = [min(bb[0], lat), min(bb[1], lon), max(bb[2], lat), max(bb[3], lon)]
            n += 1
    return n, [round(v, 4) for v in bb]


def ecrit_tuiles(lieux, sortie):
    for d in ('t', 's'):
        shutil.rmtree(os.path.join(sortie, d), ignore_errors=True)
        os.makedirs(os.path.join(sortie, d))
    tuiles = {}
    for la, lo, row in lieux:
        tuiles.setdefault((math.floor(la / TILE), math.floor(lo / TILE)), []).append((la, lo, row))
    decoupees = 0
    sous = 0
    for (y, x), rows in tuiles.items():
        chemin = os.path.join(sortie, 't', f'{y}_{x}.tsv')
        if len(rows) <= SEUIL:
            with open(chemin, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(r for _, _, r in rows) + '\nfin\n')
            continue
        decoupees += 1
        with open(chemin, 'w', encoding='utf-8', newline='\n') as f:
            f.write(f'decoupe\t{SUB}\nfin\n')
        parts = {}
        for la, lo, r in rows:
            parts.setdefault((math.floor(la / SUB), math.floor(lo / SUB)), []).append(r)
        for (yy, xx), rr in parts.items():
            with open(os.path.join(sortie, 's', f'{yy}_{xx}.tsv'), 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(rr) + '\nfin\n')
            sous += 1
    return len(tuiles), decoupees, sous


def verifie(sortie, point, rayon=800):
    la0, lo0 = (float(v) for v in point.split(','))
    y, x = math.floor(la0 / TILE), math.floor(lo0 / TILE)
    chemin = os.path.join(sortie, 't', f'{y}_{x}.tsv')
    if not os.path.exists(chemin):
        return print('Aucune tuile pour ce point.')
    lignes = open(chemin, encoding='utf-8').read().split('\n')
    if lignes[0].startswith('decoupe'):
        yy, xx = math.floor(la0 / SUB), math.floor(lo0 / SUB)
        lignes = open(os.path.join(sortie, 's', f'{yy}_{xx}.tsv'), encoding='utf-8').read().split('\n')
        print(f'Tuile découpée, sous-tuile {yy}_{xx}')
    compte = {}
    for l in lignes:
        v = l.split('\t')
        if len(v) < 15:
            continue
        la, lo = float(v[1]), float(v[2])
        d = math.hypot((la - la0) * 111320, (lo - lo0) * 111320 * math.cos(math.radians(la0)))
        if d <= rayon:
            k = next((f'{c}={v[3 + i]}' for i, c in enumerate(COLONNES) if c in ('shop', 'amenity', 'leisure', 'healthcare', 'railway', 'highway') and v[3 + i]), '?')
            compte[k] = compte.get(k, 0) + 1
    for k, n in sorted(compte.items(), key=lambda kv: -kv[1]):
        print(f'{n:6d}  {k}')


def main():
    ap = argparse.ArgumentParser(description='Lieux OpenStreetMap en tuiles pour CheckMap')
    ap.add_argument('--sortie', default='lieux', help='dossier de sortie (défaut : lieux)')
    ap.add_argument('--cache', default='cache-osm', help='dossier des extraits téléchargés')
    ap.add_argument('--extrait', action='append', help='adresse d\'un extrait .osm.pbf (remplace la liste par défaut)')
    ap.add_argument('--pbf', action='append', help='fichier .osm.pbf local')
    ap.add_argument('--geojson', help='fichier GeoJSON Lines déjà exporté par osmium (essais)')
    ap.add_argument('--efface', action='store_true', help='supprime chaque extrait après lecture (place disque limitée)')
    ap.add_argument('--verifie', metavar='LAT,LON', help='résumé des lieux à 800 m d\'un point, à partir des tuiles générées')
    a = ap.parse_args()
    if a.verifie:
        return verifie(a.sortie, a.verifie)

    os.makedirs(a.sortie, exist_ok=True)
    os.makedirs(a.cache, exist_ok=True)
    lieux, vus, zones = [], set(), []
    if a.geojson:
        n, bb = lit_geojsonseq(a.geojson, lieux, vus)
        zones.append({'nom': os.path.basename(a.geojson), 'lieux': n, 'rectangle': bb})
    sources = [(os.path.basename(p), p, False) for p in (a.pbf or [])]
    if not a.geojson and not a.pbf:
        liste = [(os.path.basename(u).replace('-latest.osm.pbf', ''), u) for u in a.extrait] if a.extrait else EXTRAITS
        sources += [(nom, url, True) for nom, url in liste]
    for nom, src, distant in sources:
        pbf = src
        try:
            if distant:
                pbf = os.path.join(a.cache, os.path.basename(src))
                if not os.path.exists(pbf):
                    log(f'Téléchargement : {nom}')
                    telecharge(src, pbf)
            n, bb = lit_extrait(nom, pbf, a.cache, lieux, vus)
            zones.append({'nom': nom, 'source': src if distant else os.path.basename(src), 'lieux': n, 'rectangle': bb})
        except Exception as e:                      # un extrait manquant n'empêche pas les autres
            log(f'  {nom} : ignoré ({e})')
        finally:
            if distant and a.efface and os.path.exists(pbf):
                os.remove(pbf)
    if not lieux:
        sys.exit('Aucun lieu : rien n\'est écrit.')
    nt, nd, ns = ecrit_tuiles(lieux, a.sortie)
    with open(os.path.join(a.sortie, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump({'v': 1, 'genere': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'tuile': TILE, 'sous': SUB, 'seuil': SEUIL, 'tuiles': nt, 'decoupees': nd, 'sous_tuiles': ns,
                   'lieux': len(lieux), 'zones': zones,
                   'licence': 'ODbL 1.0, © contributeurs OpenStreetMap', 'source': 'https://www.openstreetmap.org/copyright'},
                  f, ensure_ascii=False, indent=1)
    log(f'{len(lieux)} lieux, {nt} tuiles dont {nd} découpées en {ns} sous-tuiles, dans {a.sortie}/')


if __name__ == '__main__':
    main()
