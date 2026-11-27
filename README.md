# CheckMap

Carte interactive qui note un quartier sur 100 : commerces, santé, écoles, parcs, transports, avec le temps de marche jusqu'au lieu le plus proche.

En ligne : https://donposei81-coder.github.io/checkmap/

## Fichiers
- `index.html` : toute l'application (HTML, CSS, JavaScript).
- `manifest.webmanifest`, `sw.js`, `icon.svg`, `icon-192.png`, `icon-512.png` : installation en PWA et mode hors ligne (seulement quand le site est servi en http/https).
- `outils/frequences/` : calcul de la fréquence des lignes de transport (horaires GTFS).
- `.github/workflows/publier.yml` : publication sur GitHub Pages à chaque modification de l'appli, et nouveau calcul des fréquences chaque lundi.
- `app-mobile/` : appli iPhone (Capacitor), widget « Mon quartier » et raccourcis Siri.

## Tester
- Le plus simple : double-cliquer sur `index.html` (Chrome, Edge, Firefox, Safari). Une connexion internet est nécessaire.
- Pour avoir aussi le plan OpenStreetMap et le mode hors ligne, servir le dossier en local : `py -m http.server 8000` (Python) ou `npx serve .` (Node.js), puis ouvrir http://localhost:8000 (ou 3000 avec serve).
- Sur téléphone : héberger le dossier (GitHub Pages, Netlify, etc.), ouvrir l'adresse, puis « Ajouter à l'écran d'accueil ».

## Fonctionnalités
- Recherche d'adresse avec autocomplétion, clic sur la carte, repère déplaçable, géolocalisation.
- Rayon 500 m à 1,5 km, score sur 100 et détail par catégorie (15 catégories, 4 univers), repères regroupés.
- Temps de marche réels : zones à 5, 10 et 15 min sur le réseau piéton et « Score 15 minutes ».
- Mes lieux importants : travail, école, famille… avec le temps de trajet à pied, à vélo et en voiture depuis chaque adresse testée.
- Fiche de l'adresse : risques naturels et technologiques (Géorisques), prix médian au m² des ventes récentes (DVF), transports en commun avec la fréquence de chaque ligne (attente aux heures de pointe, premier et dernier passage) quand les fichiers de fréquence sont publiés, sinon les lignes OpenStreetMap à moins de 400 m.
- Favoris et historique consultables hors ligne, notes de visite et photos (stockées sur l'appareil).
- Bilan partageable en image PNG ou PDF (feuille de partage du téléphone si disponible).
- Comparaison A / B, lien partageable, assistant qui comprend des phrases en français.

## Styles de carte (bouton calques, le choix est retenu)
- **Lagon** (par défaut) : plan vectoriel clair, eau turquoise, plages, accents rose et sarcelle. Tuiles OpenFreeMap rendues avec MapLibre GL, chargé seulement quand ce style est affiché. Si WebGL ou les tuiles ne répondent pas, l'appli passe automatiquement au style suivant.
- **Soleil**, **Néon nuit** : plans Esri recolorés.
- Plans classiques : OpenStreetMap (uniquement en http/https, car les serveurs OSM refusent les pages ouvertes en fichier local), Esri, OSM France, Humanitaire.

## Services utilisés (gratuits, sans clé)
- Lieux : API Overpass, 5 serveurs (OpenStreetMap France en premier). Une seule requête par zone, au format CSV (huit fois plus léger que le JSON), puis filtrage dans l'appli ; si un serveur tarde plus de 6 s, le suivant est interrogé en parallèle, et au bout de 50 s l'appli affiche un message avec un bouton « Réessayer ». Résultats gardés 24 h.
- Adresses : Photon (autocomplétion), Nominatim en secours.
- Temps de trajet : OSRM (serveurs FOSSGIS). Zones de marche : Valhalla (FOSSGIS).
- Fréquence des transports : horaires GTFS de transport.data.gouv.fr, pré-calculés en fichiers statiques (`outils/frequences`).
- Risques : API Géorisques. Prix : DVF via l'API du Cerema (URL de préproduction `apidf-preprod.cerema.fr`, à surveiller ; DVF ne couvre pas l'Alsace, la Moselle et Mayotte).
- Fonds de carte : OpenFreeMap (usage commercial autorisé, sans clé), Esri, OpenStreetMap. Les mentions © restent affichées en bas de la carte.
- Pour un usage public à fort trafic, prévoir des serveurs Overpass / Photon / OSRM dédiés ou un fournisseur payant : les serveurs publics limitent le nombre de requêtes.

## Score sur 100
Chaque catégorie cochée a un poids (ex. transports 3, supermarchés 3, pharmacies 2,5, toilettes 0,5), une distance idéale et un nombre de lieux visé.
Note d'une catégorie = 55 % proximité du lieu le plus proche (pleine note sous la distance idéale, puis divisée par deux à chaque distance idéale en plus) + 45 % choix (nombre de lieux, échelle logarithmique).
Score = moyenne pondérée des catégories cochées. Temps de marche estimé = distance × 1,3 (détours) à 5 km/h.

## Assistant
Analyse les phrases en français directement sur l'appareil : besoins (famille, sans voiture, senior, étudiant, voiture électrique, sport), catégories citées, ajout ou retrait (« ajoute », « retire »), adresse (« près de… », « à Lyon », « 12 rue… »), temps ou distance (« 10 min à pied », « 1 km »), comparaison (« compare avec… »).

## Appli iPhone
Voir `app-mobile/README.md` : un script prépare le projet Xcode (Capacitor, widget « Mon quartier », raccourcis Siri, partage et position natifs). Il faut un Mac avec Xcode pour compiler et un compte Apple Developer pour publier.
Android : même principe avec `npx cap add android` (widget et raccourcis à faire en Kotlin).

## Réglages en haut du script (index.html)
- `FREQ_URL` : adresse des fichiers de fréquence. Vide : l'appli cherche un dossier `freq/` à côté d'elle.
- `SITE_URL` : adresse publique de la version web, pour les liens partagés depuis l'appli iPhone ou un fichier ouvert en local, et pour y trouver les fréquences.
