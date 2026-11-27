# Fréquence des transports

`gtfs_frequences.py` lit les horaires GTFS publiés sur transport.data.gouv.fr et produit des fichiers JSON statiques que CheckMap affiche dans « Transports en commun » : niveau de desserte, attente aux heures de pointe, premier et dernier passage, nombre de passages par jour.

Pas de serveur à faire tourner : les fichiers se mettent sur n'importe quel hébergement statique gratuit (GitHub Pages, Cloudflare Pages, Netlify).

## Lancer le calcul
Python 3.9 ou plus récent, aucune bibliothèque à installer.

```
python gtfs_frequences.py --tout                       # tous les réseaux de France (long : plusieurs Go à télécharger)
python gtfs_frequences.py --cherche Lyon --cherche Rennes   # quelques villes, pour essayer
python gtfs_frequences.py --gtfs mon_reseau.zip        # un fichier GTFS déjà téléchargé
python gtfs_frequences.py --verifie 45.7578,4.8320     # lignes autour d'un point, après le calcul
```

Options : `--sortie` (dossier, `freq` par défaut), `--cache` (fichiers téléchargés, réutilisés pendant 6 jours), `--jour AAAA-MM-JJ` (jour de référence).

## Ce qui est calculé
- Jour de référence : le mardi ou jeudi le plus chargé des 4 prochaines semaines, réseau par réseau (évite jours fériés et vacances).
- Pour chaque arrêt (quais regroupés par station) et chaque ligne, dans le sens le plus fréquent : passages par jour, entre 7 h et 9 h, entre 10 h et 16 h, premier et dernier départ. Les trajets décrits par fréquence (`frequencies.txt`) sont pris en compte.
- Dans l'appli : lignes à moins de 400 m (800 m pour métro et train), chacune à son arrêt le mieux desservi. Niveau de desserte selon le nombre de passages par heure entre 7 h et 9 h : excellente (60 et plus), très bonne (25), bonne (10), moyenne (4), faible.

## Format
- `freq/index.json` : date du calcul, liste des réseaux (titre, licence, page, jour de référence).
- `freq/t/{y}_{x}.json` : tuiles de 0,05° (`y = floor(lat / 0.05)`, `x = floor(lon / 0.05)`), contenant `{"v":1,"s":[[lat, lon, "Arrêt", [["Ligne", mode, "#couleur", jour, 7h-9h, 10h-16h, premier, dernier], ...]], ...]}`. Modes : 0 tram, 1 métro, 2 train, 3 bus, 4 bateau, 6 câble. Heures en minutes depuis minuit (au-delà de 1440 après minuit).

## Brancher l'appli
- Version web : si le dossier `freq/` est publié à côté de `index.html`, l'appli le trouve toute seule.
- Sinon, ou pour l'appli iPhone : renseigner `FREQ_URL` (ou `SITE_URL`) en haut du script dans `index.html`.
- Sans fichiers de fréquence, l'appli affiche comme avant les lignes OpenStreetMap qui desservent le quartier.

## Publication automatique (GitHub Pages)
Le fichier `.github/workflows/publier.yml` calcule les fréquences de toute la France et publie l'appli web avec le dossier `freq/` sur GitHub Pages, chaque lundi.
- Une fois : Settings > Pages > Source : « GitHub Actions ».
- À chaque modification de l'appli sur `main` : publication rapide (une minute environ), avec les horaires du dernier calcul (sauvegardés 90 jours).
- À la demande : onglet Actions > « Publier CheckMap » > Run workflow. Le champ « Réseaux » permet de ne calculer que quelques villes (ex. `Lyon, Rennes`) pour un essai rapide ; vide, toute la France. Décocher « Recalculer les horaires » republie l'appli sans refaire le calcul.

## Licences
Les horaires sont publiés par les réseaux de transport, le plus souvent sous licence ODbL ou Licence Ouverte : la liste est dans `index.json`, et l'appli cite transport.data.gouv.fr sous les lignes affichées.
