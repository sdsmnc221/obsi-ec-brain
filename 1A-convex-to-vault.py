"""
1A-convex-to-vault.py — Sync Convex stats → Obsidian vault frontmatter.

Pulls two tables from Convex and patches vault note frontmatter in-place:
  questionStats    → vault/questions/<id>.md
                     fields: vues, tentatives, correct_count, taux_reussite,
                             temps_moyen_ms, difficulte_calculee
  conceptProgress  → vault/concepts/<id>.md
                     fields: seen, bookmarked

Credentials are never hardcoded or logged:
  CONVEX_URL  — loaded from whim-ec/.env.local (or env var)
  syncKey     — read from ~/.civique_stats.json

Usage:
    python3 1A-convex-to-vault.py
    python3 1A-convex-to-vault.py --vault ./vault
    python3 1A-convex-to-vault.py --dry-run
    python3 1A-convex-to-vault.py --questions-only
    python3 1A-convex-to-vault.py --concepts-only

Dependencies:
    pip install httpx python-dotenv
"""

import json
import os
import re
import argparse
import sys
from pathlib import Path


# ─── Credentials ──────────────────────────────────────────────────────────────

def _load_env() -> None:
    """Load .env.local from ../whim-ec/ without exposing values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # fall through to bare os.getenv
    candidates = [
        Path(__file__).parent.parent / "whim-ec" / ".env.local",
        Path(__file__).parent / ".env.local",
        Path(__file__).parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=False)
            return


def _require_env(name: str, hint: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        print(f"❌ {name} manquant. {hint}")
        sys.exit(1)
    return val


def _load_sync_key() -> str:
    path = Path.home() / ".civique_stats.json"
    if not path.exists():
        print(f"❌ {path} introuvable — lancez d'abord l'application CLI.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    key = data.get("sync_key", "").strip()
    if not key:
        print("❌ sync_key absent de ~/.civique_stats.json")
        sys.exit(1)
    return key


# ─── Convex HTTP ──────────────────────────────────────────────────────────────

def _convex_query(base_url: str, fn: str, args: dict) -> dict | list:
    try:
        import httpx
    except ImportError:
        print("❌ pip install httpx")
        sys.exit(1)
    resp = httpx.post(
        f"{base_url}/api/query",
        json={"path": fn, "args": args},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "error":
        raise RuntimeError(data.get("errorMessage", str(data)))
    return data.get("value", {})


# ─── Difficulty formula (mirrors ec-in-cli/civ/stats.py) ─────────────────────

def _difficulty(views: int, correct: int, total_ms: int) -> str:
    if views == 0:
        return "standard"
    error_rate   = (views - correct) / views
    speed_norm   = min((total_ms / views) / 60_000, 1.0)
    score = error_rate * 0.5 + speed_norm * 0.3 + min(views / 20, 1.0) * 0.2
    if score < 0.3:
        return "standard"
    if score < 0.6:
        return "hard"
    return "piege"


# ─── Frontmatter patching ─────────────────────────────────────────────────────

def _patch_frontmatter(filepath: Path, updates: dict, dry_run: bool = False) -> bool:
    """
    Update or append fields inside the YAML frontmatter block.
    Only touches keys listed in `updates` — all other fields are preserved.
    Returns True if the file was (or would be) changed.
    """
    content = filepath.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return False
    end = content.find("---", 3)
    if end == -1:
        return False

    fm   = content[3:end]       # frontmatter text, no delimiters
    body = content[end + 3:]    # rest of file after closing ---

    changed = False
    for key, value in updates.items():
        pattern  = re.compile(rf"^{re.escape(key)}\s*:.*$", re.MULTILINE)
        new_line = f"{key}: {value}"
        if pattern.search(fm):
            new_fm = pattern.sub(new_line, fm)
            if new_fm != fm:
                fm, changed = new_fm, True
        else:
            fm     = fm.rstrip("\n") + f"\n{new_line}\n"
            changed = True

    if not changed:
        return False
    if not dry_run:
        filepath.write_text(f"---{fm}---{body}", encoding="utf-8")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sync Convex stats → Obsidian vault frontmatter"
    )
    parser.add_argument("--vault",          default="./vault",   help="Vault root (default: ./vault)")
    parser.add_argument("--dry-run",        action="store_true", help="Preview without writing any file")
    parser.add_argument("--questions-only", action="store_true", help="Only patch question notes")
    parser.add_argument("--concepts-only",  action="store_true", help="Only patch concept notes")
    args = parser.parse_args()

    vault        = Path(args.vault)
    do_questions = not args.concepts_only
    do_concepts  = not args.questions_only

    _load_env()
    convex_url = _require_env(
        "CONVEX_URL",
        "Ajoutez CONVEX_URL=https://<deployment>.convex.cloud dans whim-ec/.env.local"
    ).rstrip("/")
    sync_key = _load_sync_key()

    print(f"\n🔄 Sync Convex → vault  {'(DRY RUN)' if args.dry_run else ''}")

    # ── Question stats ─────────────────────────────────────────────────────────
    if do_questions:
        print("   ↓ questionStats…")
        try:
            remote = _convex_query(convex_url, "stats:getStats", {"syncKey": sync_key})
        except Exception as e:
            print(f"❌ Erreur Convex (stats:getStats) : {e}")
            sys.exit(1)

        q_dir             = vault / "questions"
        patched = skipped = 0

        for q_id, r in remote.items():
            note = q_dir / f"{q_id}.md"
            if not note.exists():
                skipped += 1
                continue

            views    = int(r.get("views",      0))
            correct  = int(r.get("correct",    0))
            attempts = int(r.get("attempts",   0))
            total_ms = int(r.get("totalTimeMs",0))

            if _patch_frontmatter(note, {
                "vues":               views,
                "tentatives":         attempts,
                "correct_count":      correct,
                "taux_reussite":      round(correct / attempts * 100) if attempts else 0,
                "temps_moyen_ms":     total_ms // views if views else 0,
                "difficulte_calculee": _difficulty(views, correct, total_ms),
            }, dry_run=args.dry_run):
                patched += 1

        tag = "(simulé) " if args.dry_run else ""
        print(f"   ✅ {patched} question notes {tag}patchées")
        if skipped:
            print(f"   ⚠️  {skipped} question IDs absents du vault (ignorés)")

    # ── Concept progress ───────────────────────────────────────────────────────
    if do_concepts:
        print("   ↓ conceptProgress…")
        try:
            rows = _convex_query(convex_url, "conceptProgress:list", {"syncKey": sync_key})
        except Exception as e:
            print(f"❌ Erreur Convex (conceptProgress:list) : {e}")
            sys.exit(1)

        c_dir                         = vault / "concepts"
        patched = skipped = seen_n = bk_n = 0

        for row in rows:
            concept_id = row.get("conceptId", "").strip()
            if not concept_id:
                continue

            note = c_dir / f"{concept_id}.md"
            if not note.exists():
                skipped += 1
                continue

            seen       = int(row.get("seen",       0))
            bookmarked = bool(row.get("bookmarked", False))

            if _patch_frontmatter(note, {
                "seen":       seen,
                "bookmarked": str(bookmarked).lower(),
            }, dry_run=args.dry_run):
                patched += 1
                if seen:       seen_n += 1
                if bookmarked: bk_n   += 1

        tag = "(simulé) " if args.dry_run else ""
        print(f"   ✅ {patched} concept notes {tag}patchées  "
              f"({seen_n} vues, {bk_n} bookmarkées)")
        if skipped:
            print(f"   ⚠️  {skipped} concept IDs absents du vault (ignorés)")

    print()


if __name__ == "__main__":
    main()
