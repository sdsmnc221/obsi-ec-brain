# convex_to_vault.py
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ec-in-cli"))
from civ.outside import pull, convex_to_local

SYNC_KEY = open(Path.home() / ".civique_stats.json").read()  # ou parser le JSON
VAULT_QUESTIONS = Path("vault/questions")

def convex_to_local(remote: dict) -> dict:
    converted = {}
    for q_id, r in remote.items():
        views    = r.get("views", 0)
        correct  = r.get("correct", 0)
        attempts = r.get("attempts", 0)
        total_ms = r.get("totalTimeMs", 0)

        converted[q_id] = {
            "vues":              views,
            "tentatives":        attempts,
            "correct_count":     correct,
            "temps_total_ms":    total_ms,
            "difficulte_calculee": _compute_difficulty(views, correct, total_ms),
        }
    return converted

def _compute_difficulty(views, correct, total_ms):
    # Même formule que stats.py du CLI
    if views == 0:
        return "standard"
    taux_erreur  = (views - correct) / views
    vitesse_norm = min((total_ms / views) / 60000, 1.0)  # normalisé sur 60s
    score = taux_erreur * 0.5 + vitesse_norm * 0.3 + min(views / 20, 1.0) * 0.2
    if score < 0.3:
        return "standard"
    elif score < 0.6:
        return "hard"
    return "piege"

def patch_frontmatter(filepath: Path, updates: dict):
    content = filepath.read_text(encoding="utf-8")
    for key, value in updates.items():
        # Remplace la ligne `key: ancienne_valeur` dans le frontmatter
        pattern = rf"^{key}: .*$"
        replacement = f"{key}: {value}"
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    filepath.write_text(content, encoding="utf-8")

def main():
    # 1. Charger syncKey depuis ~/.civique_stats.json
    stats_path = Path.home() / ".civique_stats.json"
    with open(stats_path) as f:
        local = json.load(f)
    sync_key = local.get("sync_key")
    if not sync_key:
        print("❌ Pas de sync_key dans ~/.civique_stats.json")
        return

    # 2. Pull Convex
    remote = pull(sync_key)
    converted = convex_to_local(remote)
    print(f"✅ {len(converted)} questions récupérées depuis Convex")

    # 3. Patch frontmatter des notes vault
    patched = 0
    for q_id, stats in converted.items():
        note_path = VAULT_QUESTIONS / f"{q_id}.md"
        if not note_path.exists():
            continue
        patch_frontmatter(note_path, {
            "vues":               stats["vues"],
            "erreurs":            stats["erreurs"],
            "correct":            stats["correct"],
            "temps_moyen_ms":     stats["temps_moyen_ms"],
            "difficulte_calculee": stats["difficulte_calculee"],
        })
        patched += 1

    print(f"📝 {patched} notes mises à jour dans le vault")

if __name__ == "__main__":
    main()