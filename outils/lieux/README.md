# Lieux du quotidien (OpenStreetMap)

`lieux_osm.py` prépare, pour toute la France (métropole et outre-mer), les lieux que CheckMap compte autour d'une adresse :
commerces alimentaires, restaurants, santé, écoles et crèches, parcs, sport, poste et banques, arrêts de transport,
bornes de recharge, stations vélos, toilettes. Ce sont les mêmes étiquettes que la requête Overpass de l'appli.

L'appli lit d'abord ces fichiers statiques (une ou deux secondes, aucune limite de requêtes) et n'interroge les serveurs
publics Overpass qu'en secours : dossier absent, erreur réseau, ou aucun lieu dans la zone (hors de France par exemple).

## Utilisation
Il faut Python 3.9+ et osmium-tool (`sudo apt install osmium-tool`, ou `brew install osmium-tool` sur Mac).

    python lieux_osm.py --sortie lieux --cache cache-osm --efface   # France entière, environ 20 min
    python lieux_osm.py --extrait https://download.geofabrik.de/europe/france/reunion-latest.osm.pbf
    python lieux_osm.py --verifie 48.8675,2.3636                     # résumé autour d'un point

Le dossier `lieux/` se place à côté de `index.html` (ou renseigner `LIEUX_URL` en haut du script de l'appli).
Le fichier `.github/workflows/publier.yml` le recalcule chaque lundi et le publie sur GitHub Pages.

## Format
- `index.json` : date, tailles des tuiles, nombre de lieux, zones couvertes.
- `t/{y}_{x}.tsv` avec y = floor(lat / 0,05) et x = floor(lon / 0,05) : une ligne par lieu, colonnes séparées par des tabulations
  (type, lat, lon, name, brand, network, operator, shop, amenity, leisure, healthcare, railway, station, highway, access), puis une ligne `fin`.
- Une tuile de plus de 3 000 lieux contient seulement `decoupe` : ses lieux sont dans `s/{Y}_{X}.tsv`, en 0,01°.

## Licence
Données © contributeurs OpenStreetMap, sous licence ODbL 1.0 (https://www.openstreetmap.org/copyright). La mention est affichée dans l'appli.
