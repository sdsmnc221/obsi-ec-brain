"""
01a-timeline-to-vault.py — Generate Obsidian timeline notes from dataset_timeline.json.

Creates one note per timeline entry in vault/timeline/, writes concept stubs to
vault/concepts/, and produces a _timeline_index.md with Dataview blocks.

Concept extraction uses the same primitives as 01c-question-to-concept.py:
  - exact match against KNOWN_CONCEPTS
  - named-entity regex (caps joined by prepositions only, no verb phrases)
  - article stripping, stopword filtering, deduplication

Usage:
    python3 01a-timeline-to-vault.py
    python3 01a-timeline-to-vault.py --input dataset_timeline.json --output ./vault
    python3 01a-timeline-to-vault.py --link-questions ../ec-in-cli/unified_dataset_complete.json
    python3 01a-timeline-to-vault.py --force     # overwrite existing concept stubs
    python3 01a-timeline-to-vault.py --dry-run
"""

import json
import re
import argparse
from pathlib import Path


# ─── Concept extraction primitives (shared with 01c-question-to-concept.py) ───

KNOWN_CONCEPTS = [
    # Institutions
    "Assemblée nationale", "Sénat", "Parlement", "Conseil constitutionnel",
    "Conseil d'État", "Conseil des ministres", "Cour de cassation",
    "Cour des comptes", "Défenseur des droits", "Haute Cour",
    "Conseil supérieur de la magistrature", "Médiateur de la République",
    # Personnes historiques
    "Jeanne d'Arc", "Napoléon Bonaparte", "Charles de Gaulle",
    "Simone Veil", "Simone de Beauvoir", "Robert Badinter",
    "Victor Hugo", "Voltaire", "Montesquieu", "Molière",
    "Marie Curie", "Louis Pasteur", "Abbé Pierre",
    # Textes fondateurs & lois
    "Constitution", "Déclaration des droits de l'homme", "Code civil",
    "Code pénal", "Loi de 1905", "Charte de l'environnement",
    "Préambule de 1946",
    # Principes & valeurs
    "Laïcité", "Égalité", "Fraternité", "Liberté", "Solidarité",
    "Liberté Égalité Fraternité", "Séparation des pouvoirs",
    "Égalité professionnelle", "Droit d'asile",
    # Événements
    "Révolution française", "Appel du 18 juin", "Résistance",
    "Guerre de Cent Ans", "Première Guerre mondiale", "Seconde Guerre mondiale",
    "Cinquième République", "Quatrième République", "Troisième République",
    "Commune de Paris",
    # Symboles
    "Marseillaise", "Drapeau tricolore", "Marianne", "Coq gaulois",
    "Fête nationale", "Bastille",
    # Géographie
    "Corse", "Alsace", "Bretagne", "Normandie", "Île-de-France",
    "Guyane", "Martinique", "Guadeloupe", "Réunion", "Mayotte",
    "Seine", "Loire", "Rhône", "Garonne", "Rhin",
    # Droits & social
    "Droit de vote", "Suffrage universel", "IVG", "SMIC",
    "Sécurité sociale", "Assurance maladie", "Retraite",
    "CAF", "Allocations familiales", "RSA", "Pôle emploi",
    # Éducation
    "Académie", "Baccalauréat", "École républicaine",
]

STOPWORDS = {
    "France", "Depuis", "Cette", "Entre", "Chaque", "Toute", "Sans",
    "Ainsi", "Selon", "Celui", "Celle", "Ceux", "Celles",
    "Leur", "Leurs", "Tout", "Tous", "Toutes", "Pour", "Dans", "Avec",
    "Non", "Oui", "Aussi", "Alors", "Comme", "Après", "Avant", "Même",
    "Aucun", "Autre", "Plusieurs", "Certain", "Certaine",
    "Citoyens", "Judiciaire", "Journées", "Quatre", "Cinq", "Trois",
}

_QUESTION_STARTERS = re.compile(
    r"^(quel|quelle|quels|quelles|comment|pourquoi|quand|"
    r"que|qui|où|à quoi|de quand|depuis quand|combien|lequel|laquelle)\b",
    re.IGNORECASE,
)

_SENTENCE_STARTERS = re.compile(
    r"^(à|au|aux|en|par|pour|sur|sous|avec|dans|vers|chez|dès|depuis|"
    r"pendant|après|avant|entre|selon|grâce|non|oui|tous|toutes|tout|"
    r"toute|ces|ses|son|sa|leur|leurs|chaque|aucun|plusieurs|certains|"
    r"c'est|ce sont|il |il faut|il est|il n'|elle |on |nous |ils |elles |"
    r"je |j'|payer|respecter|choisir|voter|signaler|appeler|prévenir|"
    r"abolie|interdite|décentralisée|autorisée|obligatoire|"
    r"toujours|jamais|souvent|parfois)\b",
    re.IGNORECASE,
)

_ARTICLE_RE = re.compile(
    r"^(?:le\s+|la\s+|les\s+|l['']\s*|un\s+|une\s+|du\s+|des\s+|de\s+la\s+|de\s+l['']\s*|au\s+|aux\s+)",
    re.IGNORECASE,
)


def clean(text: str) -> str:
    text = text.replace("’", "'").replace("ʼ", "'")
    return _ARTICLE_RE.sub("", text.strip())


def extract_concepts(label: str, explication: str) -> list[str]:
    """Extract civics concepts from a timeline entry (no correct_answer branch)."""
    found: list[str] = []

    full_text = f"{label} {explication}"

    for c in KNOWN_CONCEPTS:
        if c.lower() in full_text.lower():
            found.append(c)

    multi = re.findall(
        r"\b[A-ZÀÂÉÈÊÎÏÔÙÛ][a-zàâéèêîïôùû]{2,}"
        r"(?:\s+(?:de|du|des|la|le|les|l'|d'|et|à|au|aux|en|sur|sous)\s+)?"
        r"(?:\s+[A-ZÀÂÉÈÊÎÏÔÙÛ][a-zàâéèêîïôùû]{2,})+\b",
        explication,
    )
    found.extend(m for m in multi if not _QUESTION_STARTERS.match(m))

    seen: set[str] = set()
    unique: list[str] = []
    for c in found:
        c = clean(c).strip()
        if not c or len(c) < 5:
            continue
        if c in STOPWORDS:
            continue
        c_lower = c.lower()
        if c_lower in seen:
            continue
        if any(c_lower in kept.lower() and len(kept) > len(c) for kept in unique):
            continue
        seen.add(c_lower)
        unique.append(c)

    return unique[:8]


# ─── Note builders ─────────────────────────────────────────────────────────────

def build_timeline_note(entry: dict, concepts: list[str], question_map: dict) -> str:
    year      = entry["year"]
    year_end  = entry.get("year_end")
    label     = entry["label"]
    explication = entry["explication"]
    theme     = entry.get("theme", "")
    question_ids  = entry.get("question_ids", [])
    quiz_capable  = entry.get("quiz_capable", False)

    period_str = f"{year}–{year_end}" if year_end else str(year)
    note_type  = "periode" if year_end else "evenement"

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

# {period_str} — {label}

## Ce qu'il faut retenir
{explication}

## Concepts clés
{concept_links}

## Thème
[[{theme}]]

## Questions QCM liées
{q_lines}
"""


def build_concept_stub(concept: str) -> str:
    return f"""---
type: concept
---

# {concept}

_Concept transversal — les références apparaissent automatiquement dans les Backlinks._

## Notes
_À compléter comme aide-mémoire._
"""


def build_timeline_index(entries: list[dict]) -> str:
    sorted_entries = sorted(entries, key=lambda e: e["year"])
    lines = []
    for e in sorted_entries:
        year     = e["year"]
        year_end = e.get("year_end")
        period   = f"{year}–{year_end}" if year_end else str(year)
        label    = e["label"]
        theme    = e.get("theme", "")
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate Obsidian timeline notes from dataset_timeline.json"
    )
    parser.add_argument("--input",          default="dataset_timeline.json",
                        help="Timeline JSON (default: dataset_timeline.json)")
    parser.add_argument("--output",         default="./vault",
                        help="Vault root (default: ./vault)")
    parser.add_argument("--extract-concepts", choices=["rules", "llm"], default="rules",
                        help="Concept extraction method (default: rules)")
    parser.add_argument("--link-questions", default=None,
                        help="Dataset JSON to resolve question IDs → text")
    parser.add_argument("--force",          action="store_true",
                        help="Overwrite existing concept stubs")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Preview without writing any files")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        raise SystemExit(1)

    with open(input_path, encoding="utf-8") as f:
        entries = json.load(f)

    question_map: dict[str, str] = {}
    if args.link_questions:
        lq_path = Path(args.link_questions)
        if not lq_path.exists():
            print(f"❌ File not found: {lq_path}")
            raise SystemExit(1)
        with open(lq_path, encoding="utf-8") as f:
            questions = json.load(f)
        question_map = {q["id"]: q["question"][:80] for q in questions}

    vault       = Path(args.output)
    timeline_dir = vault / "timeline"
    concepts_dir = vault / "concepts"

    if not args.dry_run:
        timeline_dir.mkdir(parents=True, exist_ok=True)
        concepts_dir.mkdir(parents=True, exist_ok=True)

    all_concepts: set[str] = set()

    for entry in entries:
        year     = entry["year"]
        year_end = entry.get("year_end")
        label    = entry["label"]
        period   = f"{year}–{year_end}" if year_end else str(year)
        filename = f"{period} — {label[:50]}.md"
        path     = timeline_dir / filename

        concepts = extract_concepts(label, entry.get("explication", ""))
        all_concepts.update(concepts)

        note = build_timeline_note(entry, concepts, question_map)

        if args.dry_run:
            print(f"[dry-run] {path}  concepts: {concepts}")
        else:
            path.write_text(note, encoding="utf-8")

    written = skipped = 0
    for concept in sorted(all_concepts):
        path = concepts_dir / f"{concept}.md"
        if path.exists() and not args.force:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] concept: {path}")
        else:
            path.write_text(build_concept_stub(concept), encoding="utf-8")
            written += 1

    index_path = timeline_dir / "_timeline_index.md"
    if not args.dry_run:
        index_path.write_text(build_timeline_index(entries), encoding="utf-8")

    tag = "(simulé) " if args.dry_run else ""
    print(f"✅ {len(entries)} timeline notes {tag}+ _timeline_index.md")
    print(f"   {len(all_concepts)} concepts found  —  {written} stubs written, {skipped} skipped (use --force to overwrite)")


if __name__ == "__main__":
    main()
