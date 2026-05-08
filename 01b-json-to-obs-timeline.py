import json
import argparse
from pathlib import Path

# ── Regroupement par époque ────────────────────────────────────────────────────

EPOCHS = [
    (0,    1399, "Moyen Âge</br>et avant"),
    (1400, 1599, "15e–16e siècle"),
    (1600, 1699, "17e siècle"),
    (1700, 1799, "18e siècle"),
    (1800, 1870, "19e siècle</br>— début"),
    (1871, 1913, "19e siècle</br>— fin"),
    (1914, 1944, "Première et</br>Deuxième Guerre"),
    (1945, 1969, "Après-guerre</br>& Ve République"),
    (1970, 1999, "Fin du</br>20e siècle"),
    (2000, 2015, "Début du</br>21e siècle"),
    (2016, 9999, "Période</br>contemporaine"),
]

THEME_EMOJI = {
    "Histoire, géographie et culture":          "🏛️",
    "Principes et valeurs de la République":    "🇫🇷",
    "Système institutionnel et politique":      "⚖️",
    "Droits et devoirs":                        "📜",
    "Vivre dans la société française":          "🏘️",
}

def get_epoch(year: int) -> str:
    for start, end, label in EPOCHS:
        if start <= year <= end:
            return label
    return str(year)

# ── Formatage d'un événement ───────────────────────────────────────────────────

def format_date(entry: dict) -> str:
    year = entry["year"]
    year_end = entry.get("year_end")
    if year_end:
        return f"{year}–{year_end}"
    return str(year)

def format_entry_labeled(entry: dict) -> str:
    date = format_date(entry)
    label = entry.get("label", "").strip()
    explication = entry.get("explication", "").strip()
    theme = entry.get("theme", "")
    emoji = THEME_EMOJI.get(theme, "•")

    # Titre = date + label court (première phrase ou 80 chars)
    short_label = label


    # Contenu = explication complète + thème
    content_lines = []
    if explication and explication != label:
        content_lines.append(explication)
    else:
        content_lines.append(label)
    content_lines.append(f"\n_{emoji} {theme}_")

    content = "\n".join(content_lines)

    return f"date: {date}\ntitle: {short_label}\ncontent:\n{content}"

# ── Groupement & génération du bloc timeline ───────────────────────────────────

def build_timeline_block(entries: list, style: str) -> str:
    # Trier par année
    sorted_entries = sorted(entries, key=lambda e: e["year"])

    # Grouper par époque
    groups: dict[str, list] = {}
    for entry in sorted_entries:
        epoch = get_epoch(entry["year"])
        groups.setdefault(epoch, []).append(entry)

    lines = [f"```timeline-labeled", f"[{style}]", ""]

    for epoch_label, epoch_entries in groups.items():
        # Séparateur d'époque : entrée sans contenu (juste date + titre vide)
        lines.append(f"date: ──────────────")
        lines.append(f"title: {epoch_label}")
        lines.append(f"content:")
        lines.append("")

        for entry in epoch_entries:
            lines.append(format_entry_labeled(entry))
            lines.append("")  # ligne vide entre entrées

    lines.append("```")
    return "\n".join(lines)

# ── Document Markdown complet ──────────────────────────────────────────────────

def build_document(entries: list, style: str, title: str) -> str:
    stats_by_theme: dict[str, int] = {}
    for e in entries:
        t = e.get("theme", "Autre")
        stats_by_theme[t] = stats_by_theme.get(t, 0) + 1

    theme_lines = "\n".join(
        f"| {THEME_EMOJI.get(t, '•')} {t} | {count} |"
        for t, count in sorted(stats_by_theme.items(), key=lambda x: -x[1])
    )

    header = f"""# {title}

> {len(entries)} événements · de {min(e['year'] for e in entries)} à {max(e['year'] for e in entries)}

| Thème | Événements |
|---|---|
{theme_lines}

---

"""
    return header + build_timeline_block(entries, style)

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convertit dataset_timeline.json en Markdown pour le plugin Obsidian Timeline"
    )
    parser.add_argument(
        "--input", "-i",
        default="dataset_timeline.json",
        help="Fichier JSON source (défaut: dataset_timeline.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default="vault/timeline/_timeline_index.md",
        help="Fichier Markdown de sortie (défaut: vault/timeline/_timeline_index.md)"
    )
    parser.add_argument(
        "--theme-filter",
        default=None,
        help="Filtrer par thème (ex: 'Droits et devoirs')"
    )
    parser.add_argument(
        "--style",
        default="line-3, body-2, active-color-interactive-accent",
        help="Classes CSS du plugin Timeline (défaut: line-3, body-2, active-color-interactive-accent)"
    )
    parser.add_argument(
        "--title",
        default="Timeline — Examen Civique français",
        help="Titre du document"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche le résultat sans écrire le fichier"
    )
    args = parser.parse_args()

    # Chargement
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        return

    with open(input_path, encoding="utf-8") as f:
        entries = json.load(f)

    print(f"✅ {len(entries)} entrées chargées depuis {input_path}")

    # Filtre optionnel par thème
    if args.theme_filter:
        entries = [e for e in entries if e.get("theme") == args.theme_filter]
        print(f"🔍 Filtré → {len(entries)} entrées pour le thème '{args.theme_filter}'")

    if not entries:
        print("⚠️  Aucune entrée à traiter.")
        return

    # Génération
    doc = build_document(entries, args.style, args.title)

    # Sortie
    if args.dry_run:
        print("\n" + "─" * 60)
        print(doc)
        print("─" * 60)
        print(f"\n[dry-run] Aucun fichier écrit.")
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(doc)
        print(f"📄 Fichier écrit → {output_path}")


if __name__ == "__main__":
    main()