# obsi-ec-brain

Obsidian vault + generation scripts for the French civics exam (naturalisation / CSP residency permit).

Converts `unified_dataset_complete.json` (247 MCQ questions) into an Obsidian knowledge graph: one note per question, linked to 5 theme hubs, with cross-cutting concept notes.

**Parent repo**: [`civique/`](../) — Python dataset pipeline + CLI exam trainer.

---

## Vault structure

```
vault/
├── questions/        245 notes (conn-0001.md … mise-XXXX.md)
├── themes/           5 theme hub notes
├── concepts/         119 concept notes (Marianne, Sénat, Révolution…)
└── _index.md         Global dashboard + Dataview queries
```

### Themes (hubs)

| Theme | Questions |
|---|---|
| Principes et valeurs de la République | 106 |
| Vivre dans la société française | 76 |
| Système institutionnel et politique | 31 |
| Histoire, géographie et culture | 20 |
| Droits et devoirs | 14 |

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

### `json-to-vault.py` — Main generation

Generates question notes, theme hubs, and `_index.md` from the JSON dataset.

```bash
python3 json-to-vault.py                                            # defaults
python3 json-to-vault.py --input unified_dataset_complete.json --output ./vault
python3 json-to-vault.py --dry-run                                  # preview without writing
python3 json-to-vault.py --force                                    # overwrite existing notes
```

No external dependencies — stdlib Python only.

### `timeline-to-vault.py` — Chronological notes

Generates Obsidian notes from a `dataset_timeline.json`, with concept extraction and links back to MCQ questions.

```bash
python3 timeline-to-vault.py --input dataset_timeline.json --output ./vault
python3 timeline-to-vault.py --extract-concepts rules    # rule-based extraction (default)
python3 timeline-to-vault.py --extract-concepts llm      # LLM-based extraction
python3 timeline-to-vault.py --link-questions <dataset>  # link concepts to questions
python3 timeline-to-vault.py --dry-run
```

### `json-to-obs-timeline.py` — Timeline plugin index

Generates a Markdown file compatible with the Obsidian **Timeline** plugin.

```bash
python3 json-to-obs-timeline.py --input dataset_timeline.json
python3 json-to-obs-timeline.py --output vault/timeline/_timeline_index.md
python3 json-to-obs-timeline.py --theme-filter "Droits et devoirs"
python3 json-to-obs-timeline.py --dry-run
```

### `convex-to-vault.py` — Sync Convex stats → frontmatter

Imports revision stats (views, attempts, score) from Convex into vault note frontmatter. Requires `~/.civique_stats.json` and the `civ` lib from the parent repo.

---

## Recommended Obsidian plugins

### Core
| Plugin | Purpose |
|---|---|
| **Dataview** | SQL-like queries on frontmatter — filter by difficulty, `vu`, `correct` |
| **Templater** | Templates for creating notes manually |
| **Calendar** | Date navigation for daily study sessions |

### Visualisation
| Plugin | Purpose |
|---|---|
| **Canvas** (built-in) | Spatial board for arranging questions freely |
| **Excalidraw** | Whiteboard for hand-drawn concept maps |
| **Timeline** | Chronological view of historical events |

### UI
| Plugin | Purpose |
|---|---|
| **Minimal theme** + **Style Settings** | Clean interface, customisable typography |
| **Pretty Properties** | Frontmatter rendered with icons and visual formatting |

### Local AI (optional)
| Plugin | Purpose |
|---|---|
| **Smart Connections** | Local embeddings + vault chat via Ollama |
| **Text Generator** | Generation/summarisation via Anthropic or local endpoint |

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

