# Examen Civique — Index

## Statistiques
| Thème | Questions |
|---|---|
| [[Droits et devoirs]] | 197 |
| [[Histoire, géographie et culture]] | 140 |
| [[Système institutionnel et politique]] | 107 |
| [[Principes et valeurs de la République]] | 77 |
| [[Vivre dans la société française]] | 67 |
| **Total** | **588** |

## Révision Spaced Repetition
Decks disponibles :
- `#flashcards/Principes` — Principes et valeurs
- `#flashcards/Société` — Société française
- `#flashcards/Institutions` — Institutions
- `#flashcards/Histoire` — Histoire & culture
- `#flashcards/Droits` — Droits et devoirs

## Dataview — Questions à revoir

```dataview
TABLE vues, correct_count, difficulte_calculee
FROM "questions"
WHERE vues > 0
SORT (vues - correct_count) / vues DESC
LIMIT 20
```

## Dataview — Non vues
```dataview
TABLE theme, difficulte
FROM "questions"
WHERE vues = 0
SORT theme ASC
```
