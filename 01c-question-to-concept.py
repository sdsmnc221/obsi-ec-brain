"""
01c-question-to-concept.py — Extract factual concepts from MCQ questions and generate concept stubs.

Scans the `question`, `explication`, and correct answer fields of the dataset,
extracts named entities and known civics concepts, and creates stub notes in
vault/concepts/ for any concept not already present.

Usage:
    python3 01c-question-to-concept.py
    python3 01c-question-to-concept.py --input ../ec-in-cli/unified_dataset_complete_20260504.json
    python3 01c-question-to-concept.py --output ./vault
    python3 01c-question-to-concept.py --dry-run
    python3 01c-question-to-concept.py --report
    python3 01c-question-to-concept.py --force    # overwrite existing stubs
"""

import json
import re
import argparse
from pathlib import Path

# ─── Known civics concepts (canonical names, used for exact matching) ──────────

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
    # Too vague / not standalone civics concepts
    "Citoyens", "Judiciaire", "Journées", "Quatre", "Cinq", "Trois",
}

# Words that open a question — never start a valid concept
_QUESTION_STARTERS = re.compile(
    r"^(quel|quelle|quels|quelles|comment|pourquoi|quand|"
    r"que|qui|où|à quoi|de quand|depuis quand|combien|lequel|laquelle)\b",
    re.IGNORECASE,
)

# Starters that signal a sentence/clause answer, not a noun phrase
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

# Strip leading French articles — handles both elided (l'Algérie) and spaced (le Sénat) forms
_ARTICLE_RE = re.compile(
    r"^(?:le\s+|la\s+|les\s+|l['']\s*|un\s+|une\s+|du\s+|des\s+|de\s+la\s+|de\s+l['']\s*|au\s+|aux\s+)",
    re.IGNORECASE,
)


def clean(text: str) -> str:
    # Normalize typographic apostrophes so l'/d' patterns match reliably
    text = text.replace("’", "'").replace("ʼ", "'")
    return _ARTICLE_RE.sub("", text.strip())


def extract_concepts(question: str, explication: str, correct_answer: str) -> list[str]:
    found: list[str] = []

    full_text = f"{question} {explication} {correct_answer}"

    # 1. Exact match against known concepts in the full text
    for c in KNOWN_CONCEPTS:
        if c.lower() in full_text.lower():
            found.append(c)

    # 2. Named entities from explication only (avoids capturing question phrasing).
    #    Caps words joined only by French prepositions/articles — not arbitrary verbs.
    #    e.g. "Charles de Gaulle", "Simone Veil", "Cinquième République" — but NOT
    #    "Marianne symbolise la République" (verb between caps → no match).
    multi = re.findall(
        r"\b[A-ZÀÂÉÈÊÎÏÔÙÛ][a-zàâéèêîïôùû]{2,}"
        r"(?:\s+(?:de|du|des|la|le|les|l'|d'|et|à|au|aux|en|sur|sous)\s+)?"
        r"(?:\s+[A-ZÀÂÉÈÊÎÏÔÙÛ][a-zàâéèêîïôùû]{2,})+\b",
        explication,
    )
    found.extend(m for m in multi if not _QUESTION_STARTERS.match(m))

    # 3. Correct answer as concept — strip article, keep clean noun phrases only
    ca = clean(correct_answer)
    words = ca.split()
    if (
        ca
        and 1 <= len(words) <= 4
        and not re.search(r"\d+", ca)           # no numbers (ages, years, durations)
        and "," not in ca                        # no comma-lists ("Bleu, blanc, rouge")
        and "(" not in ca                        # no parentheticals ("Commune (ou Mairie)")
        and not _QUESTION_STARTERS.match(ca)
        and not _SENTENCE_STARTERS.match(ca)    # not a prepositional/sentence answer
        and ca[0].isupper()
    ):
        found.append(ca)

    # Deduplicate: prefer longer forms, drop substrings of already-kept concepts
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
        # Drop if a longer form covering this one is already in unique
        if any(c_lower in kept.lower() and len(kept) > len(c) for kept in unique):
            continue
        seen.add(c_lower)
        unique.append(c)

    return unique[:12]


def build_concept_stub(concept: str) -> str:
    return f"""---
type: concept
---

# {concept}

_Concept transversal — les références apparaissent automatiquement dans les Backlinks._

## Notes
_À compléter comme aide-mémoire._
"""


def main():
    parser = argparse.ArgumentParser(
        description="Extract factual concepts from MCQ questions and generate concept stubs"
    )
    parser.add_argument(
        "--input", default="../ec-in-cli/unified_dataset_complete.json",
        help="Path to the JSON dataset (default: ../ec-in-cli/unified_dataset_complete.json)",
    )
    parser.add_argument(
        "--output", default="./vault",
        help="Vault root — stubs written to <output>/concepts/ (default: ./vault)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing concept stubs",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing any files",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print extracted concepts per question, no writes",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        raise SystemExit(1)

    with open(input_path, encoding="utf-8") as f:
        questions = json.load(f)

    concepts_dir = Path(args.output) / "concepts"
    if not args.dry_run and not args.report:
        concepts_dir.mkdir(parents=True, exist_ok=True)

    # canonical name → list of question IDs that mention it
    # key: normalised lowercase for dedup, value: (canonical_name, [qids])
    concept_index: dict[str, tuple[str, list[str]]] = {}

    for q in questions:
        qid        = q["id"]
        question   = q.get("question", "")
        explication = q.get("explication", "") or ""
        correct    = q["answers"][0] if q.get("answers") else ""

        concepts = extract_concepts(question, explication, correct)

        if args.report:
            print(f"[{qid}] {question[:65]}")
            print(f"       correct  : {correct[:55]}")
            print(f"       concepts : {concepts}")
            print()
            continue

        for c in concepts:
            key = c.lower()
            if key not in concept_index:
                concept_index[key] = (c, [qid])
            else:
                concept_index[key][1].append(qid)

    concept_sources = {canonical: qids for canonical, qids in concept_index.values()}

    if args.report:
        return

    written = skipped = 0
    for concept in sorted(concept_sources):
        path = concepts_dir / f"{concept}.md"
        if path.exists() and not args.force:
            skipped += 1
            continue
        if args.dry_run:
            sources = concept_sources[concept]
            print(f"[dry-run] {concept}.md  ({len(sources)} question(s))")
        else:
            path.write_text(build_concept_stub(concept), encoding="utf-8")
            written += 1

    total = len(concept_sources)
    print(f"✅ {total} concepts extracted from {len(questions)} questions")
    if not args.dry_run:
        print(f"   {written} stubs written, {skipped} skipped (already exist — use --force to overwrite)")


if __name__ == "__main__":
    main()
