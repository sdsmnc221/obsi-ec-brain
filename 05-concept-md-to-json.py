"""
05-md-to-json.py — Converts vault/concepts/*.md to concepts.json
for import into whim-ec (Nuxt 4 + Convex).

Parses all sections including ## Dans le vault wikilinks.
timeline_refs → [{ year, year_end }] matched against timeline JSON by year.

Usage:
  python3 05-md-to-json.py
  python3 05-md-to-json.py --vault ./vault --out ./concepts.json
  python3 05-md-to-json.py --dry-run        # prints first 2 parsed concepts, writes nothing
  python3 05-md-to-json.py --limit 5        # process only N notes (test)
  python3 05-md-to-json.py --report         # summary table, no file written
"""

import re
import json
import argparse
import unicodedata
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

ENRICHED_MARKER = "<!-- enriched-by-enrich_concepts -->"

THEME_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"histoire.+culture|culture.+histoire", re.I),             "Histoire, géographie et culture"),
    (re.compile(r"principes.+r[eé]publicains|valeurs.+r[eé]publ", re.I),  "Principes et valeurs de la République"),
    (re.compile(r"institutions|[ée]lectoral|politique", re.I),             "Système institutionnel et politique"),
    (re.compile(r"droits.+devoirs|devoirs.+droits", re.I),                 "Droits et devoirs"),
    (re.compile(r"soci[eé]t[eé] française|vivre.+soci[eé]t[eé]|int[eé]gration", re.I), "Vivre dans la société française"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """'Algérie' → 'algerie', 'IVe République' → 'ive-republique'"""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text


def parse_year_token(token: str) -> tuple[int | None, int | None]:
    """
    '1830'      → (1830, None)
    '1954-1962' → (1954, 1962)
    '1941-1945' → (1941, 1945)
    Returns (None, None) if no year found.
    """
    token = token.strip()
    range_match = re.match(r"^(\d{4})[–\-](\d{4})$", token)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    single_match = re.match(r"^(\d{4})$", token)
    if single_match:
        return int(single_match.group(1)), None
    return None, None


def extract_year_from_wikilink_id(wikilink_id: str) -> tuple[int | None, int | None]:
    """
    '1830 — L'Algérie a été colonisée...' → (1830, None)
    '1954-1962 — Guerre d'Algérie'        → (1954, 1962)
    '1941 — ...'                          → (1941, None)
    Splits on em-dash or spaced hyphen, takes the first token as year.
    """
    parts = re.split(r"\s[—\-]\s", wikilink_id, maxsplit=1)
    if not parts:
        return None, None
    return parse_year_token(parts[0].strip())

# ── Markdown parsers ──────────────────────────────────────────────────────────

def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter block, return body only."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return content
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1:])
    return content  # malformed frontmatter — return as-is


def extract_h1(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def extract_section(content: str, heading: str) -> str:
    """
    Returns the raw text between ## {heading} and the next ## heading (or EOF).
    Strips the heading line itself. Returns "" if not found.
    """
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.+?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return ""
    return match.group(1).strip()


def parse_key_points(section_text: str) -> list[str]:
    """
    Extracts bullet points from '## À retenir pour l'examen'.
    Strips leading '- ' or '* ', ignores blank lines.
    """
    points = []
    for line in section_text.splitlines():
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            points.append(line[2:].strip())
    return points


def parse_themes(thematic_links_text: str) -> list[str]:
    """
    Infers official exam themes from bold spans (**...**) in Liens thématiques.
    Falls back to scanning full text if no bold match.
    """
    bold_spans = re.findall(r"\*\*(.+?)\*\*", thematic_links_text)

    found = []
    for pattern, theme_name in THEME_HINTS:
        matched = any(pattern.search(span) for span in bold_spans)
        if not matched:
            matched = bool(pattern.search(thematic_links_text))
        if matched and theme_name not in found:
            found.append(theme_name)
    return found


def parse_timeline_refs(vault_section: str) -> list[dict]:
    """
    Parses wikilinks from ## Dans le vault → ### Événements timeline.
    Pattern: [[wikilink_id|label]]
    Extracts { year, year_end } from the wikilink id prefix.
    Skips bare non-year wikilinks (e.g. [[timeline|Timeline — ...]]).
    """
    # Narrow to the timeline subsection if present
    timeline_match = re.search(
        r"###\s+[Éé]v[eé]nements timeline.*?(?=###|\Z)",
        vault_section,
        re.DOTALL,
    )
    search_text = timeline_match.group(0) if timeline_match else vault_section

    wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]", search_text)

    refs = []
    seen = set()

    for wikilink_id, _label in wikilinks:
        year, year_end = extract_year_from_wikilink_id(wikilink_id)
        if year is None:
            continue  # skip non-year wikilinks
        key = (year, year_end)
        if key in seen:
            continue
        seen.add(key)
        refs.append({"year": year, "year_end": year_end})

    # Sort chronologically
    refs.sort(key=lambda r: r["year"])
    return refs

# ── Main parser ───────────────────────────────────────────────────────────────

def parse_concept(path: Path) -> dict | None:
    raw = path.read_text(encoding="utf-8")
    body = strip_frontmatter(raw)

    title = extract_h1(body)
    if not title:
        return None  # skip malformed notes

    # Split at enriched marker — vault section lives below it
    if ENRICHED_MARKER in body:
        main_body, vault_body = body.split(ENRICHED_MARKER, 1)
    else:
        main_body = body
        vault_body = ""

    definition      = extract_section(main_body, "Définition")
    key_points_raw  = extract_section(main_body, "À retenir pour l'examen")
    thematic_links  = extract_section(main_body, "Liens thématiques")

    # Clean markdown bold/italic from thematic_links for plain text storage
    thematic_links_clean = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", thematic_links)

    key_points    = parse_key_points(key_points_raw)
    themes        = parse_themes(thematic_links)
    timeline_refs = parse_timeline_refs(vault_body)

    return {
        "id":             path.stem,
        "slug":           slugify(path.stem),
        "title":          title,
        "definition":     definition,
        "key_points":     key_points,
        "thematic_links": thematic_links_clean,
        "themes":         themes,
        "timeline_refs":  timeline_refs,
    }

# ── Report ────────────────────────────────────────────────────────────────────

def print_report(concepts: list[dict]):
    print(f"\n{'Concept':<35} {'Th':>3} {'KP':>4} {'TL refs':>8} {'Def?':>5}")
    print("─" * 60)
    no_theme = no_def = no_kp = 0
    for c in concepts:
        t      = len(c["themes"])
        kp     = len(c["key_points"])
        tl     = len(c["timeline_refs"])
        has_def = bool(c["definition"])
        flags  = ""
        if not c["themes"]:  flags += " ⚠️theme";  no_theme += 1
        if not has_def:      flags += " ⚠️def";    no_def   += 1
        if not kp:           flags += " ⚠️kp";     no_kp    += 1
        print(f"  {c['id']:<33} {t:>3} {kp:>4} {tl:>8} {'✅' if has_def else '❌':>5}{flags}")
    print("─" * 60)
    print(f"  {len(concepts)} concepts")
    print(f"  ⚠️  {no_theme} sans thème  ·  {no_def} sans définition  ·  {no_kp} sans key_points")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert vault/concepts/*.md → concepts.json for whim-ec"
    )
    parser.add_argument("--vault",   default="./vault")
    parser.add_argument("--out",     default="./concepts.json")
    parser.add_argument("--limit",   type=int, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print first 2 parsed concepts, write nothing")
    parser.add_argument("--report",  action="store_true",
                        help="Print summary table, write nothing")
    args = parser.parse_args()

    concepts_dir = Path(args.vault) / "concepts"
    if not concepts_dir.exists():
        print(f"❌ Dossier introuvable : {concepts_dir}")
        return

    notes = sorted(n for n in concepts_dir.glob("*.md") if not n.stem.startswith("_"))
    if args.limit:
        notes = notes[: args.limit]

    print(f"📂 {len(notes)} notes trouvées dans {concepts_dir}\n")

    concepts = []
    errors   = 0

    for note in notes:
        try:
            concept = parse_concept(note)
            if concept is None:
                print(f"  ⚠️  {note.name} — pas de titre H1, skippée")
                continue
            concepts.append(concept)
            tl = len(concept["timeline_refs"])
            th = len(concept["themes"])
            print(f"  ✅ {concept['id']:<35} themes={th}  timeline_refs={tl}")
        except Exception as e:
            print(f"  ❌ {note.name} — {e}")
            errors += 1

    print(f"\n{'─' * 42}")
    print(f"  {len(concepts)} concepts parsés  ·  {errors} erreurs")

    if args.report:
        print_report(concepts)
        return

    if args.dry_run:
        print("\n── dry-run: 2 premiers concepts ──\n")
        print(json.dumps(concepts[:2], ensure_ascii=False, indent=2))
        return

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(concepts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n💾 {out_path} écrit — {len(concepts)} concepts")


if __name__ == "__main__":
    main()
