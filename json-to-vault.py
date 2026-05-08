import json
import os
import argparse

THEMES = [
    "Principes et valeurs de la République",
    "Vivre dans la société française",
    "Système institutionnel et politique",
    "Histoire, géographie et culture",
    "Droits et devoirs",
]

THEME_REMAP = {
    "Symboles de la République": "Principes et valeurs de la République",
}

# Tag deck Spaced Repetition par thème
THEME_DECK = {
    "Principes et valeurs de la République":    "#flashcards/Principes",
    "Vivre dans la société française":          "#flashcards/Société",
    "Système institutionnel et politique":      "#flashcards/Institutions",
    "Histoire, géographie et culture":          "#flashcards/Histoire",
    "Droits et devoirs":                        "#flashcards/Droits",
}

def slugify_difficulty(d):
    return {"standard": "standard", "hard": "hard", "piege": "piège"}.get(d, d)

def build_question_note(q):
    theme = THEME_REMAP.get(q["theme"], q["theme"])
    answers = q["answers"]
    correct = answers[0]
    distractors = answers[1:]
    explication = q.get("explication") or "_Pas d'explication disponible._"

    tag = ""
    if q.get("difficulte") == "piege":
        tag = "\n#piège"
    elif q.get("difficulte") == "hard":
        tag = "\n#hard"
    if q.get("type") == "mise-situation":
        tag += "\n#mise-situation"

    distractor_lines = "\n".join(f"- ❌ {d}" for d in distractors)

    # ── Frontmatter ───────────────────────────────────────────────────────────
    lines = [
        "---",
        f"id: {q['id']}",
        f"theme: {theme}",
        f"type: {q['type']}",
        f"difficulte: {slugify_difficulty(q.get('difficulte', 'standard'))}",
        f"source: {q['source']}",
        "vu: false",
        "correct: false",
        "vues: 0",
        "tentatives: 0",
        "correct_count: 0",
        "temps_total_ms: 0",
        "difficulte_calculee: standard",
        "---",
        "",
        f"# {q['question']}",
        "",
        "## Réponses",
        f"- ✅ {correct}",
        distractor_lines,
        "",
        "## Explication",
        explication,
        "",
        "## Thème",
        f"[[{theme}]]",
        tag,
        "",
        "---",
        "",
    ]

    # ── Bloc Spaced Repetition ─────────────────────────────────────────────────
    deck_tag = THEME_DECK.get(theme, "#flashcards/Examen_civique")

    # Type connaissance → Q::A single-line (question + bonne réponse seulement)
    # Type mise-situation → multiline avec toutes les options + explication
    if q.get("type") == "mise-situation":
        sr_block = [
            deck_tag + " #mise-situation",
            "",
            q["question"],
            "?",
            f"✅ {correct}",
            *[f"❌ {d}" for d in distractors],
            "",
            f"> {explication}",
        ]
    else:
        sr_block = [
            deck_tag,
            "",
            q["question"],
            "?",
            f"✅ {correct}",
            *[f"❌ {d}" for d in distractors],
            "",
            f"> {explication}",
        ]

    lines.extend(sr_block)
    lines.append("")

    return "\n".join(lines)


def build_theme_hub(theme, count):
    return f"""---
type: hub
theme: {theme}
---

# {theme}

{count} questions dans ce thème.

## Résumé thématique
_À rédiger comme aide-mémoire._

---
Les questions de ce thème apparaissent automatiquement dans les **Backlinks** ci-dessous.
"""

def build_index(questions):
    by_theme = {}
    for q in questions:
        t = THEME_REMAP.get(q["theme"], q["theme"])
        by_theme.setdefault(t, []).append(q)

    theme_lines = "\n".join(
        f"| [[{t}]] | {len(qs)} |"
        for t, qs in sorted(by_theme.items(), key=lambda x: -len(x[1]))
    )

    return f"""# Examen Civique — Index

## Statistiques
| Thème | Questions |
|---|---|
{theme_lines}
| **Total** | **{len(questions)}** |

## Révision Spaced Repetition
Decks disponibles :
- `#flashcards/Principes` — Principes et valeurs
- `#flashcards/Société` — Société française
- `#flashcards/Institutions` — Institutions
- `#flashcards/Histoire` — Histoire & culture
- `#flashcards/Droits` — Droits et devoirs

## Dataview — Questions à revoir

```dataview
TABLE vues, correct_count, difficulte_calculee
FROM "questions"
WHERE vues > 0
SORT (vues - correct_count) / vues DESC
LIMIT 20
```

## Dataview — Non vues
```dataview
TABLE theme, difficulte
FROM "questions"
WHERE vues = 0
SORT theme ASC
```
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="unified_dataset_complete.json")
    parser.add_argument("--output", default="./vault")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        questions = json.load(f)

    dirs = [
        os.path.join(args.output, "questions"),
        os.path.join(args.output, "themes"),
    ]
    if not args.dry_run:
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    for q in questions:
        path = os.path.join(args.output, "questions", f"{q['id']}.md")
        if args.dry_run:
            print(f"[dry-run] {path}")
            continue
        if os.path.exists(path) and not args.force:
            print(f"[skip] {path}")
            continue
        with open(path, "w", encoding="utf-8") as out:
            out.write(build_question_note(q))

    by_theme = {}
    for q in questions:
        t = THEME_REMAP.get(q["theme"], q["theme"])
        by_theme.setdefault(t, []).append(q)

    for theme, qs in by_theme.items():
        path = os.path.join(args.output, "themes", f"{theme}.md")
        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as out:
                out.write(build_theme_hub(theme, len(qs)))

    index_path = os.path.join(args.output, "_index.md")
    if not args.dry_run:
        with open(index_path, "w", encoding="utf-8") as out:
            out.write(build_index(questions))

    print(f"✅ {len(questions)} notes + {len(by_theme)} hubs + _index.md")

if __name__ == "__main__":
    main()