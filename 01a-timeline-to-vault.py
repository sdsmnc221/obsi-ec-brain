import json, os, re, argparse

KNOWN_CONCEPTS = [
    "Jeanne d'Arc", "Guerre de Cent Ans", "Révolution française",
    "Déclaration des droits de l'homme", "Conseil constitutionnel",
    "Assemblée nationale", "Cinquième République", "Loi de 1905",
    "IVG", "Laïcité", "Marseillaise", "Drapeau tricolore",
    "Liberté Égalité Fraternité", "Napoléon Bonaparte", "De Gaulle",
    "Appel du 18 juin", "Vichy", "Résistance", "Code civil",
    "Montesquieu", "Voltaire", "Victor Hugo", "Badinter",
]

def extract_concepts_rules(label, explication):
    text = f"{label} {explication}"
    found = [c for c in KNOWN_CONCEPTS if c.lower() in text.lower()]
    # Capture les groupes de mots capitalisés (noms propres composés)
    extras = re.findall(
        r'\b[A-ZÀÂÉÈÊÎÏÔÙÛ][a-zàâéèêîïôùû]+(?:\s+(?:de\s+|d\'|des?\s+|la\s+|le\s+)?[A-ZÀÂÉÈÊÎÏÔÙÛ][a-zàâéèêîïôùû]+)*\b',
        text
    )
    all_found = list(dict.fromkeys(found + extras))
    # Exclure les mots trop courts ou trop génériques
    stopwords = {"France", "Depuis", "Cette", "Entre", "Chaque", "Toute", "Sans", "Elle"}
    return [c for c in all_found if c not in stopwords and len(c) > 4][:8]

def build_timeline_note(entry, concepts, question_map):
    year = entry["year"]
    year_end = entry.get("year_end")
    label = entry["label"]
    explication = entry["explication"]
    theme = entry.get("theme", "")
    question_ids = entry.get("question_ids", [])
    quiz_capable = entry.get("quiz_capable", False)

    period_str = f"{year}–{year_end}" if year_end else str(year)
    note_type = "periode" if year_end else "evenement"

    concept_links = " · ".join(f"[[{c}]]" for c in concepts) if concepts else "_aucun_"

    if question_ids and question_map:
        q_lines = "\n".join(
            f"- [[{qid}]] — _{question_map.get(qid, '?')}_"
            for qid in question_ids
        )
    elif not quiz_capable:
        q_lines = "_(aucune — quiz_capable: false)_"
    else:
        q_lines = "_(à lier manuellement)_"

    return f"""---
year: {year}
year_end: {year_end if year_end else 'null'}
type: {note_type}
theme: {theme}
quiz_capable: {str(quiz_capable).lower()}
question_ids: {json.dumps(question_ids)}
---

# {period_str} — {entry['label']}

## Ce qu'il faut retenir
{explication}

## Concepts clés
{concept_links}

## Thème
[[{theme}]]

## Questions QCM liées
{q_lines}
"""

def build_concept_note(concept):
    return f"""---
type: concept
---

# {concept}

_Concept transversal — les références apparaissent automatiquement dans les Backlinks._

## Notes
_À compléter comme aide-mémoire._
"""

def build_timeline_index(entries):
    sorted_entries = sorted(entries, key=lambda e: e["year"])
    lines = []
    for e in sorted_entries:
        year = e["year"]
        year_end = e.get("year_end")
        period = f"{year}–{year_end}" if year_end else str(year)
        label = e["label"]
        theme = e.get("theme", "")
        filename = f"{period} — {label[:50]}"
        lines.append(f"| [[{filename}\\|{period}]] | {label[:60]}… | {theme} |")

    rows = "\n".join(lines)
    return f"""# Timeline — Examen Civique

## Chronologie complète

| Date | Événement | Thème |
|---|---|---|
{rows}

## Dataview — Événements par thème

```dataview
TABLE year, year_end, theme
FROM "timeline"
WHERE type = "evenement" OR type = "periode"
SORT year ASC
```

## Dataview — Événements avec questions QCM

```dataview
TABLE year, quiz_capable
FROM "timeline"
WHERE quiz_capable = true
SORT year ASC
```
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="dataset_timeline.json")
    parser.add_argument("--output", default="./vault")
    parser.add_argument("--extract-concepts", choices=["rules", "llm"], default="rules")
    parser.add_argument("--link-questions", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        entries = json.load(f)

    question_map = {}
    if args.link_questions:
        with open(args.link_questions, encoding="utf-8") as f:
            questions = json.load(f)
        question_map = {q["id"]: q["question"][:80] for q in questions}

    dirs = [
        os.path.join(args.output, "timeline"),
        os.path.join(args.output, "concepts"),
    ]
    if not args.dry_run:
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    all_concepts = set()

    for entry in entries:
        year = entry["year"]
        year_end = entry.get("year_end")
        label = entry["label"]
        period = f"{year}–{year_end}" if year_end else str(year)
        filename = f"{period} — {label[:50]}.md"
        path = os.path.join(args.output, "timeline", filename)

        concepts = extract_concepts_rules(label, entry.get("explication", ""))
        all_concepts.update(concepts)

        note = build_timeline_note(entry, concepts, question_map)

        if args.dry_run:
            print(f"[dry-run] {path} — concepts: {concepts}")
        else:
            with open(path, "w", encoding="utf-8") as out:
                out.write(note)

    # Notes concepts
    for concept in all_concepts:
        path = os.path.join(args.output, "concepts", f"{concept}.md")
        if args.dry_run:
            print(f"[dry-run] concept: {path}")
        elif not os.path.exists(path):  # ne pas écraser si déjà enrichie manuellement
            with open(path, "w", encoding="utf-8") as out:
                out.write(build_concept_note(concept))

    # Index timeline
    index_path = os.path.join(args.output, "timeline", "_timeline_index.md")
    if not args.dry_run:
        with open(index_path, "w", encoding="utf-8") as out:
            out.write(build_timeline_index(entries))

    print(f"✅ {len(entries)} notes timeline + {len(all_concepts)} concepts + _timeline_index.md")

if __name__ == "__main__":
    main()