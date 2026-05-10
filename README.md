# obsi-ec-brain

Obsidian vault + generation scripts for the French civics exam (naturalisation / CSP residency permit).



https://github.com/user-attachments/assets/d08d9a6b-8e53-4baf-9c40-eea7053cc988



Converts `unified_dataset_complete.json` (247 MCQ questions) into an Obsidian knowledge graph: one note per question, linked to 5 theme hubs, with cross-cutting concept notes.

**Parent repo**: [`civique/`](https://github.com/sdsmnc221/ec-in-cli) — Python dataset pipeline + CLI exam trainer.

---

## Vault structure

```
vault/
├── questions/        245 notes (conn-0001.md … mise-XXXX.md)
├── themes/           5 theme hub notes
├── concepts/         119 concept notes (Marianne, Sénat, Révolution…)
├── timelines/        timeline civique / républicains
└── _index.md         Global dashboard + Dataview queries
```

### Themes (hubs)

| Theme                                 |
| ------------------------------------- |
| Principes et valeurs de la République |
| Vivre dans la société française       |
| Système institutionnel et politique   |
| Histoire, géographie et culture       |
| Droits et devoirs                     |

### Question note format

```markdown
---
id: conn-0001
theme: Principes et valeurs de la République
type: connaissance
difficulte: standard
source: connaissances
vu: false
correct: false
---

# [Question text]

## Réponses

- ✅ [Correct answer]
- ❌ [Distractor 1]
- ❌ [Distractor 2]
- ❌ [Distractor 3]

## Explication

[Explanation text]

## Thème

[[Principes et valeurs de la République]]
```

> `vu` and `correct` are local tracking fields — update them manually in Obsidian as you study.
> `correct_index` is always `0` in the dataset: `answers[0]` is always the correct answer.

---

## Scripts

### Full build (run in order)

All commands are run from the `obsi-ec-brain/` directory. Replace the dataset paths with your actual files.

**Example dataset**

I think it can be found here:

- Dataset sample:  [ec-in-cli](https://github.com/sdsmnc221/ec-in-cli/blob/main/dataset_sample.json).
- Timeline sample (maybe full): [whim-ec](https://github.com/sdsmnc221/whim-ec/blob/main/assets/data/timeline_dataset.json).
---

**Step 1 — Question notes + theme hubs**

```bash
python3 00-json-to-vault.py \
  --input ../ec-in-cli/dataset_sample.json \
  --output ./vault
```

**Step 2 — Timeline notes + concept stubs from timeline**

```bash
python3 01a-timeline-to-vault.py \
  --input ../ec-in-cli/timeline_dataset.json \
  --output ./vault \
  --link-questions ../ec-in-cli/dataset_sample.json
```

**Step 3 — Concept stubs from MCQ questions**

```bash
python3 01c-question-to-concept.py \
  --input ../ec-in-cli/dataset_sample.json \
  --output ./vault
```

> Steps 2 and 3 both write to `vault/concepts/` and skip stubs that already exist — safe to run in either order.

**Step 4 — Fill concept notes with LLM content**

```bash
python3 03-concept-generator.py --vault ./vault           # Claude Haiku (default)
python3 03-concept-generator.py --vault ./vault --sonnet  # Claude Sonnet (better quality)
python3 03-concept-generator.py --vault ./vault --provider hf  # HuggingFace Qwen
```

Requires `ANTHROPIC_API_KEY` (Anthropic) or `HF_TOKEN` (HuggingFace).

**Step 5 — Inject backlinks into concept notes**

Must run after steps 1–3 so all question and timeline notes exist.

```bash
python3 04-enrich-concept.py --vault ./vault
# If already run before and timeline notes were added since:
python3 04-enrich-concept.py --vault ./vault --force
```

**Step 6 — Export concepts to JSON (for whim-ec)**

```bash
python3 05-concept-md-to-json.py \
  --vault ./vault \
  --out ../data/concepts_$(date +%Y%m%d).json
```

---

### Optional / utility scripts

### `01b-json-to-obs-timeline.py` — Timeline plugin index

Generates a Markdown file compatible with the Obsidian **Timeline** plugin.

```bash
python3 01b-json-to-obs-timeline.py --input ../ec-in-cli/timeline_dataset_20260504.json
python3 01b-json-to-obs-timeline.py --output vault/timeline/_timeline_index.md
python3 01b-json-to-obs-timeline.py --theme-filter "Droits et devoirs"
python3 01b-json-to-obs-timeline.py --dry-run
```

### `1A-convex-to-vault.py` — Sync Convex stats → frontmatter

Imports revision stats (views, attempts, score) from Convex into vault note frontmatter. Requires `~/.civique_stats.json` and `CONVEX_URL` in `../whim-ec/.env.local`.

```bash
python3 1A-convex-to-vault.py                # sync questions + concepts
python3 1A-convex-to-vault.py --dry-run      # preview without writing
python3 1A-convex-to-vault.py --questions-only
python3 1A-convex-to-vault.py --concepts-only
```

---

### Script reference

| Script | Purpose | Deps |
|---|---|---|
| `00-json-to-vault.py` | Question notes + theme hubs + `_index.md` | stdlib only |
| `01a-timeline-to-vault.py` | Timeline notes + concept stubs from timeline | stdlib only |
| `01b-json-to-obs-timeline.py` | Timeline plugin index (optional) | stdlib only |
| `01c-question-to-concept.py` | Concept stubs from MCQ questions | stdlib only |
| `03-concept-generator.py` | Fill concept stubs via LLM | `anthropic` or `httpx` |
| `04-enrich-concept.py` | Inject backlinks into concept notes | stdlib only |
| `05-concept-md-to-json.py` | Export concepts to JSON for whim-ec | stdlib only |
| `1A-convex-to-vault.py` | Sync Convex stats → frontmatter | `httpx`, `python-dotenv` |

---

## Recommended Obsidian plugins

### Core

| Plugin        | Purpose                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| **Dataview**  | SQL-like queries on frontmatter — filter by difficulty, `vu`, `correct` |
| **Templater** | Templates for creating notes manually                                   |
| **Calendar**  | Date navigation for daily study sessions                                |

### Visualisation

| Plugin                | Purpose                                      |
| --------------------- | -------------------------------------------- |
| **Canvas** (built-in) | Spatial board for arranging questions freely |
| **Excalidraw**        | Whiteboard for hand-drawn concept maps       |
| **Timeline**          | Chronological view of historical events      |

### UI

| Plugin                                 | Purpose                                               |
| -------------------------------------- | ----------------------------------------------------- |
| **Minimal theme** + **Style Settings** | Clean interface, customisable typography              |
| **Pretty Properties**                  | Frontmatter rendered with icons and visual formatting |

### Local AI (optional)

| Plugin                | Purpose                                                  |
| --------------------- | -------------------------------------------------------- |
| **Smart Connections** | Local embeddings + vault chat via Ollama                 |
| **Text Generator**    | Generation/summarisation via Anthropic or local endpoint |

---

## Graph View

The hub-and-spoke graph forms automatically from `[[wikilinks]]` to themes and concepts.

**Recommended config** (Settings → Graph View):

- **Groups**: `path:themes/` → orange (larger node) · `tag:#piège` → red · `tag:#hard` → yellow · `tag:#mise-situation` → purple
- **Filters**: exclude `_config/`
- **Forces**: increase "Link distance" to spread theme clusters apart

---

## Dataview queries (`_index.md`)

```dataview
TABLE theme, difficulte
FROM "vault/questions"
WHERE vues = 0
SORT theme ASC
```

```dataview
TABLE theme
FROM "vault/questions"
WHERE type = "mise-situation"
```

---
