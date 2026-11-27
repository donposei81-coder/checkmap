# Ajoute au projet Xcode généré par Capacitor :
#  - CheckMapNatif.swift (plugin, raccourcis Siri) dans la cible App
#  - la cible MonQuartierWidget (extension WidgetKit), intégrée à l'appli
#  - l'App Group partagé, iOS 17 minimum, langue française
# Utilisation : ruby natif-ios/configurer-xcode.rb ios/App/App.xcodeproj
require 'xcodeproj'

APP_ID = 'com.checkmap.app'
WIDGET = 'MonQuartierWidget'
IOS = '17.0'

path = ARGV[0] || 'ios/App/App.xcodeproj'
proj = Xcodeproj::Project.open(path)
app = proj.targets.find { |t| t.name == 'App' } or abort("Cible App introuvable dans #{path}")

def ref_for(group, name)
  group.files.find { |f| f.path == name } || group.new_reference(name)
end

# Appli
app_group = proj.main_group['App'] or abort('Groupe App introuvable')
natif = ref_for(app_group, 'CheckMapNatif.swift')
app.add_file_references([natif]) unless app.source_build_phase.files_references.include?(natif)
ref_for(app_group, 'App.entitlements')
version = app.build_configurations.first.build_settings['MARKETING_VERSION'] || '1.0'
build = app.build_configurations.first.build_settings['CURRENT_PROJECT_VERSION'] || '1'
app.build_configurations.each do |c|
  c.build_settings['PRODUCT_BUNDLE_IDENTIFIER'] = APP_ID
  c.build_settings['CODE_SIGN_ENTITLEMENTS'] = 'App/App.entitlements'
  c.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = IOS
end
proj.build_configurations.each { |c| c.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = IOS }

# Langue de développement : français (phrases Siri)
root = proj.root_object
root.development_region = 'fr'
root.known_regions = (root.known_regions + ['fr']).uniq

# Widget
w = proj.targets.find { |t| t.name == WIDGET } || proj.new_target(:app_extension, WIDGET, :ios, IOS)
g = proj.main_group[WIDGET] || proj.main_group.new_group(WIDGET, WIDGET)
src = ref_for(g, "#{WIDGET}.swift")
w.add_file_references([src]) unless w.source_build_phase.files_references.include?(src)
ref_for(g, 'Info.plist')
ref_for(g, "#{WIDGET}.entitlements")
w.build_configurations.each do |c|
  s = c.build_settings
  s['PRODUCT_NAME'] = '$(TARGET_NAME)'
  s['PRODUCT_BUNDLE_IDENTIFIER'] = "#{APP_ID}.widget"
  s['INFOPLIST_FILE'] = "#{WIDGET}/Info.plist"
  s['GENERATE_INFOPLIST_FILE'] = 'YES'
  s['INFOPLIST_KEY_CFBundleDisplayName'] = 'CheckMap'
  s['CODE_SIGN_ENTITLEMENTS'] = "#{WIDGET}/#{WIDGET}.entitlements"
  s['CODE_SIGN_STYLE'] = 'Automatic'
  s['SWIFT_VERSION'] = '5.0'
  s['SWIFT_EMIT_LOC_STRINGS'] = 'YES'
  s['TARGETED_DEVICE_FAMILY'] = '1,2'
  s['SKIP_INSTALL'] = 'YES'
  s['IPHONEOS_DEPLOYMENT_TARGET'] = IOS
  s['MARKETING_VERSION'] = version
  s['CURRENT_PROJECT_VERSION'] = build
  s['LD_RUNPATH_SEARCH_PATHS'] = ['$(inherited)', '@executable_path/Frameworks', '@executable_path/../../Frameworks']
end
app.add_dependency(w) unless app.dependencies.any? { |d| d.target == w }
embed = app.copy_files_build_phases.find { |p| p.name == 'Embed Foundation Extensions' } ||
        app.new_copy_files_build_phase('Embed Foundation Extensions')
embed.symbol_dst_subfolder_spec = :plug_ins
unless embed.files_references.include?(w.product_reference)
  bf = embed.add_file_reference(w.product_reference, true)
  bf.settings = { 'ATTRIBUTES' => ['RemoveHeadersOnCopy'] }
end

proj.save
puts "Projet Xcode configuré : #{path}"
