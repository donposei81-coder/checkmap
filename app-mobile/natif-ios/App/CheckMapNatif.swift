import UIKit
import Capacitor
import WidgetKit
import AppIntents

// MARK: - Données partagées avec le widget (App Group)

enum Partage {
    static let groupe = "group.com.checkmap.app"
    static let cleQuartier = "quartier"
    static let cleAction = "action"
    static var defaults: UserDefaults { UserDefaults(suiteName: groupe) ?? .standard }
}

extension Notification.Name {
    static let checkmapAction = Notification.Name("checkmapAction")
}

struct Quartier: Codable {
    struct Categorie: Codable {
        var nom: String
        var minutes: Int?
        var nombre: Int
    }
    var label: String
    var score: Int?
    var verdict: String
    var rayon: Int
    var date: Double
    var categories: [Categorie]
    var transports: String?

    static func charger() -> Quartier? {
        guard let data = Partage.defaults.data(forKey: Partage.cleQuartier) else { return nil }
        return try? JSONDecoder().decode(Quartier.self, from: data)
    }
}

// MARK: - Contrôleur principal : enregistre le plugin de l'appli

class MainViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(MonQuartierPlugin())
    }
}

// MARK: - Plugin MonQuartier (appelé depuis index.html)

@objc(MonQuartierPlugin)
public class MonQuartierPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "MonQuartierPlugin"
    public let jsName = "MonQuartier"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "enregistrer", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "actionEnAttente", returnType: CAPPluginReturnPromise)
    ]

    override public func load() {
        NotificationCenter.default.addObserver(self, selector: #selector(signalerAction), name: UIApplication.didBecomeActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(signalerAction), name: .checkmapAction, object: nil)
    }

    @objc func signalerAction() {
        guard Partage.defaults.dictionary(forKey: Partage.cleAction) != nil else { return }
        notifyListeners("action", data: [:])
    }

    // Dernier quartier analysé, au format JSON, pour le widget et Siri
    @objc func enregistrer(_ call: CAPPluginCall) {
        guard let json = call.getString("json"), let data = json.data(using: .utf8),
              (try? JSONDecoder().decode(Quartier.self, from: data)) != nil else {
            call.reject("Données invalides")
            return
        }
        Partage.defaults.set(data, forKey: Partage.cleQuartier)
        WidgetCenter.shared.reloadAllTimelines()
        call.resolve()
    }

    // Action demandée par un raccourci Siri, lue une seule fois
    @objc func actionEnAttente(_ call: CAPPluginCall) {
        var resultat: [String: Any] = [:]
        if let action = Partage.defaults.dictionary(forKey: Partage.cleAction) {
            for (cle, valeur) in action { resultat[cle] = valeur }
            Partage.defaults.removeObject(forKey: Partage.cleAction)
        }
        call.resolve(resultat)
    }
}

// MARK: - Raccourcis Siri

struct ScoreQuartierIntent: AppIntent {
    static let title: LocalizedStringResource = "Score de mon quartier"
    static let description: IntentDescription? = IntentDescription("Donne le score du dernier quartier analysé dans CheckMap.")

    func perform() async throws -> some IntentResult & ProvidesDialog {
        guard let q = Quartier.charger() else {
            return .result(dialog: "Aucun quartier analysé pour l'instant. Ouvrez CheckMap et recherchez une adresse.")
        }
        let score = q.score.map { "\($0) sur 100" } ?? "pas encore de score"
        let transports = q.transports.map { ". \($0)" } ?? ""
        return .result(dialog: "\(q.label) : \(score), \(q.verdict.lowercased())\(transports).")
    }
}

struct AnalyserIciIntent: AppIntent {
    static let title: LocalizedStringResource = "Analyser le quartier où je suis"
    static let description: IntentDescription? = IntentDescription("Ouvre CheckMap et note le quartier autour de votre position.")
    static let openAppWhenRun: Bool = true

    @MainActor
    func perform() async throws -> some IntentResult {
        Partage.defaults.set(["type": "position"], forKey: Partage.cleAction)
        NotificationCenter.default.post(name: .checkmapAction, object: nil)
        return .result()
    }
}

struct AnalyserAdresseIntent: AppIntent {
    static let title: LocalizedStringResource = "Analyser une adresse"
    static let description: IntentDescription? = IntentDescription("Ouvre CheckMap et note le quartier d'une adresse.")
    static let openAppWhenRun: Bool = true

    @Parameter(title: "Adresse", requestValueDialog: "Quelle adresse voulez-vous analyser ?")
    var adresse: String

    @MainActor
    func perform() async throws -> some IntentResult {
        Partage.defaults.set(["type": "adresse", "q": adresse], forKey: Partage.cleAction)
        NotificationCenter.default.post(name: .checkmapAction, object: nil)
        return .result()
    }
}

struct CheckMapRaccourcis: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: ScoreQuartierIntent(),
            phrases: [
                "Score de mon quartier avec \(.applicationName)",
                "Mon quartier dans \(.applicationName)"
            ],
            shortTitle: "Mon quartier",
            systemImageName: "map"
        )
        AppShortcut(
            intent: AnalyserIciIntent(),
            phrases: [
                "Analyse ce quartier avec \(.applicationName)",
                "Note ce quartier avec \(.applicationName)"
            ],
            shortTitle: "Analyser ici",
            systemImageName: "location"
        )
        AppShortcut(
            intent: AnalyserAdresseIntent(),
            phrases: [
                "Analyse une adresse avec \(.applicationName)"
            ],
            shortTitle: "Analyser une adresse",
            systemImageName: "magnifyingglass"
        )
    }
}
