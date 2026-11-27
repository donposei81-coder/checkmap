# CheckMap pour iPhone (Capacitor)

L'appli iPhone reprend `index.html` tel quel, avec en plus :
- le widget « Mon quartier » (petit et moyen) : score, verdict et temps de marche du dernier quartier analysé ;
- trois raccourcis Siri : « Score de mon quartier avec CheckMap », « Analyse ce quartier avec CheckMap », « Analyse une adresse avec CheckMap » ;
- le partage natif du bilan (image, PDF) et la position via iOS.

## Ce qu'il faut
- Un Mac avec Xcode (App Store) et Node.js (https://nodejs.org).
- Un compte Apple Developer (99 € par an) pour installer sur un iPhone hors câble et publier sur l'App Store.

## Installation
Dans le Terminal, depuis ce dossier :

```
chmod +x installer-ios.sh
./installer-ios.sh
```

Pour un autre identifiant d'appli (conseillé, `com.checkmap.app` peut être déjà pris) :

```
APP_ID=fr.votrenom.checkmap ./installer-ios.sh
```

Le script installe Capacitor, crée le projet `ios/`, ajoute le code natif (`natif-ios/`), la cible du widget, l'App Group partagé, les autorisations (position, appareil photo, photos), passe le projet en français et en iOS 17 minimum, puis ouvre Xcode.

Dans Xcode :
1. Cliquer sur le projet « App » à gauche, cible **App**, onglet *Signing & Capabilities* : choisir votre *Team*.
2. Même chose pour la cible **MonQuartierWidget**.
3. Brancher l'iPhone, le choisir en haut de la fenêtre, puis ▶︎.

Si Xcode signale un souci d'App Group : dans *Signing & Capabilities* de chaque cible, *+ Capability* > *App Groups*, cocher `group.<identifiant de l'appli>`.

## Après une modification de l'appli web
```
npm run ios
```
(recopie `index.html` dans le projet et ouvre Xcode).

## Réglages dans index.html
En haut du script :
- `SITE_URL` : adresse publique de la version web. Sert aux liens partagés depuis l'iPhone et à trouver les fréquences des transports.
- `FREQ_URL` : adresse des fichiers de fréquence, si elle est différente (voir `outils/frequences`).

## Publier sur l'App Store
Dans Xcode : *Product* > *Archive*, puis *Distribute App* > *App Store Connect*. Prévoir dans App Store Connect les captures d'écran, la description, la politique de confidentialité : pas de compte, favoris et photos restent sur l'appareil ; les adresses et positions analysées sont envoyées aux services cartographiques publics (liste dans le README principal).

## Fichiers
- `installer-ios.sh` : préparation du projet (Mac).
- `natif-ios/App/CheckMapNatif.swift` : plugin MonQuartier (lien appli ↔ widget), raccourcis Siri.
- `natif-ios/MonQuartierWidget/` : widget.
- `natif-ios/configurer-xcode.rb` : ajout de la cible widget au projet Xcode.
- `copier-web.js` : copie de l'appli web dans `www/`.
