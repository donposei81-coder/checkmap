#!/bin/bash
# Prépare le projet iOS de CheckMap (à lancer sur un Mac avec Xcode).
#   ./installer-ios.sh
#   APP_ID=fr.monnom.checkmap ./installer-ios.sh   # autre identifiant d'appli
set -euo pipefail
cd "$(dirname "$0")"

APP_ID="${APP_ID:-com.checkmap.app}"
[ "$(uname)" = "Darwin" ] || { echo "Ce script se lance sur un Mac."; exit 1; }
command -v xcodebuild >/dev/null || { echo "Installez Xcode depuis l'App Store, puis relancez."; exit 1; }
command -v node >/dev/null || { echo "Installez Node.js (https://nodejs.org), puis relancez."; exit 1; }

echo "1/6 Dépendances"
npm install

echo "2/6 Identifiant de l'appli : $APP_ID"
sed -i '' "s/\"appId\": \"[^\"]*\"/\"appId\": \"$APP_ID\"/" capacitor.config.json
node copier-web.js

echo "3/6 Projet Capacitor"
[ -d ios ] || npx cap add ios
npx cap sync ios

echo "4/6 Code natif (plugin, Siri, widget)"
APP=ios/App/App
WID=ios/App/MonQuartierWidget
mkdir -p "$WID"
cp natif-ios/App/CheckMapNatif.swift natif-ios/App/App.entitlements "$APP/"
cp natif-ios/MonQuartierWidget/* "$WID/"
for f in "$APP/CheckMapNatif.swift" "$APP/App.entitlements" "$WID/MonQuartierWidget.swift" "$WID/MonQuartierWidget.entitlements"; do
  sed -i '' "s/group\.com\.checkmap\.app/group.$APP_ID/g" "$f"
done
sed -i '' 's/customClass="CAPBridgeViewController" customModule="Capacitor"/customClass="MainViewController" customModule="App" customModuleProvider="target"/' "$APP/Base.lproj/Main.storyboard"

echo "5/6 Autorisations et langue"
PL="$APP/Info.plist"
setkey() { plutil -replace "$1" -string "$2" "$PL"; }
setkey NSLocationWhenInUseUsageDescription "CheckMap utilise votre position pour noter le quartier autour de vous."
setkey NSCameraUsageDescription "CheckMap utilise l'appareil photo pour vos photos de visite."
setkey NSPhotoLibraryUsageDescription "CheckMap permet d'ajouter des photos de visite depuis votre photothèque."
setkey NSPhotoLibraryAddUsageDescription "CheckMap peut enregistrer le bilan d'un quartier dans vos photos."
setkey CFBundleDevelopmentRegion fr

echo "6/6 Cible widget et réglages Xcode"
if ! ruby -e "require 'xcodeproj'" 2>/dev/null; then
  gem install --user-install --no-document xcodeproj
fi
sed "s/^APP_ID = .*/APP_ID = '$APP_ID'/" natif-ios/configurer-xcode.rb > /tmp/checkmap-configurer-xcode.rb
ruby /tmp/checkmap-configurer-xcode.rb ios/App/App.xcodeproj

echo
echo "Terminé. Dans Xcode (il va s'ouvrir) :"
echo "  1. Cliquez sur « App » à gauche, onglet Signing & Capabilities : choisissez votre Team."
echo "  2. Même chose pour la cible « MonQuartierWidget »."
echo "  3. Branchez l'iPhone, choisissez-le en haut, puis ▶︎."
npx cap open ios
