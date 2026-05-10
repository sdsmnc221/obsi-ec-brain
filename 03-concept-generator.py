"""
fill_concepts.py — Enrichit vault/concepts/*.md avec Claude Haiku (ou Sonnet)
via l'API Anthropic.

Usage :
  python3 fill_concepts.py
  python3 fill_concepts.py --vault ./vault --dry-run
  python3 fill_concepts.py --force          # réécrit même les notes déjà remplies
  python3 fill_concepts.py --limit 10       # batch limité pour tester
  python3 fill_concepts.py --provider hf    # utilise HuggingFace à la place
  python3 fill_concepts.py --sonnet         # utilise claude-sonnet-4-6 (plus lent, meilleur)
"""

import os
import time
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un assistant pédagogique spécialisé dans la préparation 
à l'examen civique français (naturalisation / titre de séjour CSP).
Tu réponds uniquement en Markdown propre, sans preamble, sans balises de code, 
sans répéter le titre."""

def build_user_prompt(concept: str) -> str:
    return f"""Génère le contenu d'une fiche de connaissance pour le concept : **{concept}**

Contexte :
- Public : candidat à la naturalisation française
- Langue : français clair et accessible
- Thèmes de l'examen : Principes et valeurs de la République, Société française,
  Institutions, Histoire & culture, Droits et devoirs

Réponds UNIQUEMENT avec ce Markdown (sans titre, il existe déjà) :

## Définition
[3 à 5 phrases définissant le concept et sa place dans la République française]

## À retenir pour l'examen
- [fait clé ou date 1]
- [fait clé ou date 2]
- [fait clé ou date 3 — optionnel]

## Liens thématiques
[1 à 2 phrases reliant ce concept aux thèmes de l'examen civique]"""

# ── Providers ─────────────────────────────────────────────────────────────────

ANTHROPIC_MODEL_HAIKU  = "claude-haiku-4-5-20251001"
ANTHROPIC_MODEL_SONNET = "claude-sonnet-4-6"

_anthropic_model = ANTHROPIC_MODEL_HAIKU  # overridden by --sonnet


def call_anthropic(concept: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=_anthropic_model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(concept)}],
    )
    return msg.content[0].text.strip()


def call_hf(concept: str) -> str:
    import httpx
    api_key = os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise RuntimeError("HF_API_KEY manquant dans .env")

    resp = httpx.post(
        "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "Qwen/Qwen2.5-72B-Instruct",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(concept)},
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


PROVIDERS = {
    "anthropic": call_anthropic,
    "hf":        call_hf,
}

# ── Note helpers ──────────────────────────────────────────────────────────────

PLACEHOLDER = "_À compléter comme aide-mémoire._"

def is_empty(content: str) -> bool:
    """Note considérée vide si elle ne contient que le placeholder ou pas de ## section."""
    return PLACEHOLDER in content or "## Définition" not in content


def patch_note(path: Path, generated: str):
    """
    Remplace le contenu sous le titre H1 avec le contenu généré.
    Conserve le frontmatter si présent.
    """
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()

    # Sépare frontmatter / titre H1 / reste
    frontmatter_end = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                frontmatter_end = i + 1
                break

    # Trouve le titre H1
    h1_line = None
    for i, line in enumerate(lines[frontmatter_end:], frontmatter_end):
        if line.startswith("# "):
            h1_line = i
            break

    # Reconstruit : frontmatter + H1 + contenu généré
    parts = []
    if frontmatter_end > 0:
        parts.extend(lines[:frontmatter_end])
        parts.append("")
    if h1_line is not None:
        parts.append(lines[h1_line])
    parts.append("")
    parts.append(generated)
    parts.append("")

    path.write_text("\n".join(parts), encoding="utf-8")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enrichit vault/concepts/*.md via Claude Haiku ou HuggingFace"
    )
    parser.add_argument("--vault",    default="./vault")
    parser.add_argument("--concepts-dir", default=None,
                        help="Override concepts folder (default: <vault>/concepts)")
    parser.add_argument("--provider", choices=["anthropic", "hf"], default="anthropic")
    parser.add_argument("--sonnet",   action="store_true",
                        help="Utilise claude-sonnet-4-6 au lieu de Haiku (anthropic only)")
    parser.add_argument("--force",    action="store_true",
                        help="Réécrit même les notes déjà remplies")
    parser.add_argument("--limit",    type=int, default=None,
                        help="Nombre max de notes à traiter (test)")
    parser.add_argument("--delay",    type=float, default=0.5,
                        help="Délai entre appels API en secondes (défaut: 0.5)")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    if args.sonnet:
        global _anthropic_model
        _anthropic_model = ANTHROPIC_MODEL_SONNET

    concepts_dir = Path(args.concepts_dir) if args.concepts_dir else Path(args.vault) / "concepts"
    if not concepts_dir.exists():
        print(f"❌ Dossier introuvable : {concepts_dir}")
        return

    notes = sorted(concepts_dir.glob("*.md"))
    print(f"📂 {len(notes)} notes trouvées dans {concepts_dir}")

    call_fn = PROVIDERS[args.provider]
    model_label = _anthropic_model if args.provider == "anthropic" else args.provider
    print(f"🤖 Provider : {args.provider}  ({model_label})")

    to_process = []
    for note in notes:
        content = note.read_text(encoding="utf-8")
        if args.force or is_empty(content):
            to_process.append(note)
        else:
            print(f"  [skip] {note.name} — déjà remplie")

    if args.limit:
        to_process = to_process[: args.limit]

    print(f"✏️  {len(to_process)} notes à enrichir\n")

    ok = skipped = errors = 0

    for i, note in enumerate(to_process, 1):
        concept = note.stem  # nom du fichier sans .md = nom du concept
        print(f"  [{i}/{len(to_process)}] {concept} ...", end=" ", flush=True)

        if args.dry_run:
            print("[dry-run]")
            continue

        try:
            generated = call_fn(concept)
            patch_note(note, generated)
            print("✅")
            ok += 1
        except Exception as e:
            print(f"❌ {e}")
            errors += 1

        if i < len(to_process):
            time.sleep(args.delay)

    print(f"\n─────────────────────────────")
    print(f"✅ {ok} enrichies  ⏭ {skipped} skippées  ❌ {errors} erreurs")


if __name__ == "__main__":
    main()