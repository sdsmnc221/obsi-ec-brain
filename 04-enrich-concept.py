"""
enrich_concepts.py — Enrichit vault/concepts/*.md avec des wikilinks
vers les notes questions et timeline qui mentionnent ce concept.

Ce script NE génère PAS de texte via LLM — il scanne le vault et injecte
des backlinks réels pour que le Graph View connecte les nœuds concepts.

Utilise fill_concepts.py pour la génération de contenu textuel.

Usage :
  python3 enrich_concepts.py
  python3 enrich_concepts.py --vault ./vault
  python3 enrich_concepts.py --dry-run
  python3 enrich_concepts.py --force     # réécrit même si déjà enrichi
  python3 enrich_concepts.py --report    # affiche un rapport sans écrire
"""

import re
import argparse
from pathlib import Path
from collections import defaultdict

# ── Scanner ───────────────────────────────────────────────────────────────────

def extract_title(content: str) -> str | None:
    """Extrait le titre H1 d'une note."""
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None

def scan_vault(vault: Path) -> dict:
    """
    Scanne questions/ et timeline/ et retourne un index :
    {
      "conn-0001": { "title": "Quel est...", "content": "...", "path": Path },
      "1789 — ...": { ... },
    }
    """
    index = {}
    for folder in ["questions", "timeline"]:
        for note in (vault / folder).glob("*.md"):
            if note.stem.startswith("_"):
                continue
            content = note.read_text(encoding="utf-8")
            title = extract_title(content) or note.stem
            index[note.stem] = {
                "title":   title,
                "content": content.lower(),
                "path":    note,
                "folder":  folder,
            }
    return index

def find_mentions(concept_name: str, vault_index: dict) -> dict:
    """
    Trouve toutes les notes qui mentionnent le concept.
    Retourne { "questions": [...], "timeline": [...] }
    """
    # Variantes de recherche : nom exact + sans accents + mots clés
    variants = build_variants(concept_name)

    matches = defaultdict(list)
    for note_id, meta in vault_index.items():
        text = meta["content"]
        if any(v in text for v in variants):
            matches[meta["folder"]].append({
                "id":    note_id,
                "title": meta["title"],
            })

    return dict(matches)

def build_variants(name: str) -> list[str]:
    """Génère des variantes de recherche pour un nom de concept."""
    variants = [name.lower()]

    # Version sans parenthèses : "IVG (interruption...)" → "ivg"
    clean = re.sub(r'\(.*?\)', '', name).strip().lower()
    if clean != name.lower():
        variants.append(clean)

    # Acronyme si présent entre parenthèses
    acro = re.findall(r'\(([A-Z]{2,})\)', name)
    variants.extend(a.lower() for a in acro)

    # Mots significatifs (> 4 chars, pas stopwords)
    STOPWORDS = {"dans", "pour", "avec", "les", "des", "une", "par",
                 "sur", "aux", "que", "qui", "est", "son", "leur"}
    words = [w for w in re.findall(r'\b\w{4,}\b', name.lower())
             if w not in STOPWORDS]
    # Ajoute les bigrammes significatifs
    for i in range(len(words) - 1):
        variants.append(f"{words[i]} {words[i+1]}")

    return list(dict.fromkeys(variants))  # dédupliqué, ordre conservé

# ── Patch note ────────────────────────────────────────────────────────────────

ENRICHED_MARKER = "<!-- enriched-by-enrich_concepts -->"

def is_enriched(content: str) -> bool:
    return ENRICHED_MARKER in content

def build_links_section(mentions: dict, max_per_section: int = 15) -> str:
    """Construit le bloc Markdown des wikilinks à injecter."""
    lines = [ENRICHED_MARKER, "", "## Dans le vault", ""]

    questions = mentions.get("questions", [])
    timeline  = mentions.get("timeline", [])

    if questions:
        lines.append(f"### Questions QCM ({len(questions)})")
        for q in questions[:max_per_section]:
            short = q["title"][:70] + "…" if len(q["title"]) > 70 else q["title"]
            lines.append(f"- [[{q['id']}|{short}]]")
        if len(questions) > max_per_section:
            lines.append(f"_… et {len(questions) - max_per_section} autres_")
        lines.append("")

    if timeline:
        lines.append(f"### Événements timeline ({len(timeline)})")
        for t in timeline[:max_per_section]:
            short = t["title"][:70] + "…" if len(t["title"]) > 70 else t["title"]
            lines.append(f"- [[{t['id']}|{short}]]")
        if len(timeline) > max_per_section:
            lines.append(f"_… et {len(timeline) - max_per_section} autres_")
        lines.append("")

    if not questions and not timeline:
        lines.append("_Aucune mention trouvée dans les notes QCM ou timeline._")
        lines.append("")

    return "\n".join(lines)

def patch_concept_note(path: Path, mentions: dict, force: bool = False) -> bool:
    """
    Injecte la section ## Dans le vault dans la note concept.
    Retourne True si la note a été modifiée.
    """
    content = path.read_text(encoding="utf-8")

    if is_enriched(content) and not force:
        return False

    # Supprime l'ancienne section enrichie si présente (pour --force)
    if ENRICHED_MARKER in content:
        marker_pos = content.index(ENRICHED_MARKER)
        content = content[:marker_pos].rstrip() + "\n"

    links_section = build_links_section(mentions)
    new_content = content.rstrip() + "\n\n" + links_section + "\n"
    path.write_text(new_content, encoding="utf-8")
    return True

# ── Rapport ───────────────────────────────────────────────────────────────────

def print_report(concepts_dir: Path, vault_index: dict):
    """Affiche un rapport des concepts et leurs mentions sans écrire."""
    notes = sorted(concepts_dir.glob("*.md"))
    print(f"\n{'Concept':<40} {'QCM':>5} {'Timeline':>10} {'Total':>7}")
    print("─" * 66)

    total_q = total_t = isolated = 0
    for note in notes:
        if note.stem.startswith("_"):
            continue
        mentions = find_mentions(note.stem, vault_index)
        q = len(mentions.get("questions", []))
        t = len(mentions.get("timeline", []))
        total_q += q
        total_t += t
        if q + t == 0:
            isolated += 1
        marker = " ⚠️" if q + t == 0 else ""
        print(f"  {note.stem:<38} {q:>5} {t:>10} {q+t:>7}{marker}")

    print("─" * 66)
    print(f"  {'TOTAL':<38} {total_q:>5} {total_t:>10} {total_q+total_t:>7}")
    print(f"\n  ⚠️  {isolated} concepts isolés (aucune mention dans le vault)")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Injecte des wikilinks dans concepts/*.md pour le Graph View"
    )
    parser.add_argument("--vault",   default="./vault")
    parser.add_argument("--force",   action="store_true",
                        help="Réécrit la section même si déjà enrichie")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report",  action="store_true",
                        help="Affiche le rapport de mentions sans écrire")
    args = parser.parse_args()

    vault = Path(args.vault)
    concepts_dir = vault / "concepts"

    if not concepts_dir.exists():
        print(f"❌ {concepts_dir} introuvable")
        return

    # 1. Scanner le vault
    print("🔍 Scan du vault (questions/ + timeline/)...")
    vault_index = scan_vault(vault)
    print(f"   {len(vault_index)} notes indexées")

    # 2. Rapport seul
    if args.report:
        print_report(concepts_dir, vault_index)
        return

    # 3. Enrichir chaque concept
    notes = sorted(n for n in concepts_dir.glob("*.md")
                   if not n.stem.startswith("_"))
    print(f"📂 {len(notes)} concepts à traiter\n")

    patched = skipped = isolated = 0

    for note in notes:
        concept = note.stem
        mentions = find_mentions(concept, vault_index)
        total = sum(len(v) for v in mentions.values())

        if total == 0:
            isolated += 1
            status = "⚪ isolé"
        else:
            q = len(mentions.get("questions", []))
            t = len(mentions.get("timeline", []))
            status = f"🔗 {q}q + {t}t"

        if args.dry_run:
            print(f"  [dry-run] {concept:<35} {status}")
            continue

        modified = patch_concept_note(note, mentions, force=args.force)
        if modified:
            print(f"  ✅ {concept:<35} {status}")
            patched += 1
        else:
            print(f"  [skip] {concept:<35} déjà enrichi")
            skipped += 1

    if not args.dry_run:
        print(f"\n─────────────────────────────────────")
        print(f"✅ {patched} enrichis  ⏭ {skipped} skippés  ⚪ {isolated} isolés")
        print(f"\n💡 Lance --report pour voir le détail des mentions par concept")


if __name__ == "__main__":
    main()