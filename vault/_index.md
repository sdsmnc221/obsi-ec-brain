# Examen Civique — Index

## Statistiques

| Thème                                     | Questions |
| ----------------------------------------- | --------- |
| [[Droits et devoirs]]                     | 91        |
| [[Histoire, géographie et culture]]       | 44        |
| [[Système institutionnel et politique]]   | 44        |
| [[Principes et valeurs de la République]] | 34        |
| [[Vivre dans la société française]]       | 32        |
| **Total**                                 | **245**   |

## Révision Spaced Repetition

Decks disponibles :

- `#flashcards/Principes` — Principes et valeurs
- `#flashcards/Société` — Société française
- `#flashcards/Institutions` — Institutions
- `#flashcards/Histoire` — Histoire & culture
- `#flashcards/Droits` — Droits et devoirs

## Queries Dataview

### Questions non vues

```dataview
TABLE theme, difficulte
FROM "vault/questions"
WHERE vues = 0
SORT difficulte DESC
```

### Stats

#### Questions difficiles

```dataview
TABLE vues, erreurs, difficulte_calculee
FROM "vault/questions"
WHERE difficulte_calculee = "hard" OR difficulte_calculee = "piege"
SORT erreurs DESC
```

#### Questions Stats

```dataview
TABLE
  vues,
  tentatives,
  correct_count,
  (temps_total_ms / vues) AS "moy ms",
  difficulte_calculee
FROM "vault/questions"
WHERE vues > 0
SORT (vues - correct_count) / vues DESC
```

### Debug

```dataview
TABLE file.path
LIMIT 5
```
