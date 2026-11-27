import WidgetKit
import SwiftUI

// Même groupe et même format que CheckMapNatif.swift (appli)
private let groupe = "group.com.checkmap.app"

struct QuartierWidget: Codable {
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

    static func charger() -> QuartierWidget? {
        guard let data = UserDefaults(suiteName: groupe)?.data(forKey: "quartier") else { return nil }
        return try? JSONDecoder().decode(QuartierWidget.self, from: data)
    }

    static let exemple = QuartierWidget(
        label: "Place de la République", score: 92, verdict: "Excellent quartier", rayon: 800, date: 0,
        categories: [
            .init(nom: "Supermarchés", minutes: 3, nombre: 10),
            .init(nom: "Transports", minutes: 2, nombre: 24),
            .init(nom: "Pharmacies", minutes: 4, nombre: 6),
            .init(nom: "Boulangeries", minutes: 3, nombre: 12)
        ],
        transports: "Très bonne desserte"
    )
}

struct Entree: TimelineEntry {
    let date: Date
    let quartier: QuartierWidget?
}

struct Fournisseur: TimelineProvider {
    func placeholder(in context: Context) -> Entree {
        Entree(date: .now, quartier: .exemple)
    }

    func getSnapshot(in context: Context, completion: @escaping (Entree) -> Void) {
        completion(Entree(date: .now, quartier: QuartierWidget.charger() ?? .exemple))
    }

    // L'appli recharge le widget à chaque nouvelle analyse : pas de mise à jour programmée
    func getTimeline(in context: Context, completion: @escaping (Timeline<Entree>) -> Void) {
        completion(Timeline(entries: [Entree(date: .now, quartier: QuartierWidget.charger())], policy: .never))
    }
}

extension Color {
    static let rose = Color(red: 1.0, green: 0.239, blue: 0.545)   // #ff3d8b
    static let lagon = Color(red: 0.078, green: 0.686, blue: 0.816) // #14afd0
}

struct AnneauScore: View {
    let score: Int?
    var epaisseur: CGFloat = 8

    var body: some View {
        ZStack {
            Circle().stroke(Color.lagon.opacity(0.15), lineWidth: epaisseur)
            Circle()
                .trim(from: 0, to: CGFloat(score ?? 0) / 100)
                .stroke(LinearGradient(colors: [.rose, .lagon], startPoint: .topLeading, endPoint: .bottomTrailing),
                        style: StrokeStyle(lineWidth: epaisseur, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: -2) {
                Text(score.map { String($0) } ?? "–")
                    .font(.system(size: 24, weight: .heavy, design: .rounded))
                Text("/100")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct VueMonQuartier: View {
    @Environment(\.widgetFamily) private var famille
    let entree: Entree

    var body: some View {
        if let q = entree.quartier {
            if famille == .systemSmall {
                petit(q)
            } else {
                moyen(q)
            }
        } else {
            VStack(alignment: .leading, spacing: 6) {
                Text("CheckMap").font(.headline).foregroundStyle(Color.rose)
                Text("Analysez une adresse dans l'appli pour la retrouver ici.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
    }

    private func petit(_ q: QuartierWidget) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            AnneauScore(score: q.score, epaisseur: 7).frame(width: 62, height: 62)
            Spacer(minLength: 0)
            Text(q.label)
                .font(.caption.weight(.semibold))
                .lineLimit(2)
            Text(q.verdict)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(Color.lagon)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private func moyen(_ q: QuartierWidget) -> some View {
        HStack(spacing: 14) {
            VStack(spacing: 6) {
                AnneauScore(score: q.score).frame(width: 74, height: 74)
                Text(q.verdict)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Color.lagon)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
            }
            .frame(width: 92)
            VStack(alignment: .leading, spacing: 3) {
                Text(q.label)
                    .font(.subheadline.weight(.bold))
                    .lineLimit(1)
                ForEach(Array(q.categories.prefix(4).enumerated()), id: \.offset) { _, c in
                    HStack(spacing: 4) {
                        Text(c.nom).font(.caption).lineLimit(1)
                        Spacer(minLength: 4)
                        Text(c.minutes.map { "\($0) min" } ?? "–")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Color.rose)
                    }
                }
                if let t = q.transports {
                    Text(t).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct MonQuartierWidget: Widget {
    let kind = "MonQuartierWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Fournisseur()) { entree in
            VueMonQuartier(entree: entree)
                .containerBackground(.background, for: .widget)
        }
        .configurationDisplayName("Mon quartier")
        .description("Le score du dernier quartier analysé et les temps de marche.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

@main
struct MonQuartierWidgetBundle: WidgetBundle {
    var body: some Widget {
        MonQuartierWidget()
    }
}
