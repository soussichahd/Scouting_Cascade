<<<<<<< HEAD
# Scouting_Cascade
=======
# Scouting Gardien de But – SIF de Mamdani en cascade

Outil d'aide à la décision : 15 critères → 4 sous-scores (SS1…SS4) → note finale /100 et Niveau 1–6, par un
système d'inférence floue de Mamdani en cascade (approche du cas d'école « arrière latéral » de M. Ramdani & L. Machaa).

## Lancer (≈ 2 minutes)
```bash
pip install numpy pyyaml fastapi uvicorn reportlab matplotlib httpx pytest hypothesis
cd scouting-cascade
PYTHONPATH=engine/src:. python3 -m uvicorn api.app:app --port 8000 ou set PYTHONPATH=engine/src;.
                                                                       python -m uvicorn api.app:app --port 8000
# puis ouvrir http://localhost:8000
python3 -m pytest -q          # 27 tests
```
La base SQLite `data/app.db` est créée et alimentée au premier démarrage (règles/variables seed + 60 gardiens fictifs).
Pour repartir de zéro : supprimer `data/app.db`.

## Contenu
| Dossier | Rôle |
|---|---|
| `engine/src/scouting_engine/` | Moteur pur : `domain` (fonctions d'appartenance), `model` (Mamdani + cascade lue dans `cascade.yaml`, trace), `rulegen` (génération pondérée), `validation`, `explain`, `sensitivity`, `fcm` (profils + similarité), `ga` (calibration) |
| `data/seed/goalkeeper/` | `variables.yaml`, `cascade.yaml`, `rulebases/*.yaml` (81+81+27+81+243 règles + potentiel + fiabilité) |
| `data/seed/lateral/` | Cas d'école du professeur, **même moteur, autres fichiers** (ENF-12) |
| `data/fixtures/` | `goalkeepers/` (60 gardiens **fictifs**), `golden/` (valeurs d'or) |
| `api/` | FastAPI + SQLite (versions immuables, A/B, PDF) |
| `web/index.html` | Écran 1 règles · écran 2 variables · écran 3 évaluation/traceur/radar · gardiens/FCM |
| `scripts/` | `build_seed.py` (régénère les YAML), `make_goalkeepers.py`, `make_golden.py` |

## Scénario de démonstration
1. Onglet **Gardiens** → choisir un gardien → *Évaluer ce gardien* ; ajuster les curseurs (note, niveau, traceur, radar, commentaire en direct).
2. *Enregistrer l'évaluation* → *Rapport PDF*.
3. Onglet **Règles** : changer une règle, *Enregistrer* (nouvelle version) → *Comparer A/B* → *activer* ou revenir en arrière.
4. Onglet **Variables** : déplacer un sommet de trapèze (courbe et avertissements en temps réel).

## Écarts / hypothèses à valider avec le professeur (section 13 du cahier)
- SQLite au lieu de PostgreSQL ; interface HTML/JS sans build au lieu de React/Vite ; FastAPI conservé (à valider ADR 0001).
- Tacle : paramètres du **graphe** retenus (national [0,0,60,70], pro [60,70,80,90], international [80,90,100,100]).
- Temps de réaction : termes Rapide/Moyen/Lent (variable inversée). Agilité : 4 entrées (celles dont la diapo donne les fonctions ; « angle de croisement » non défini).
- Une variable partagée avec fonctions différentes selon le sous-système (distance, temps de réaction) est modélisée par `source:` dans `variables.yaml`.
- Poids de génération (gardien) = propositions ; ceux du latéral (0,40 / 0,20 / 0,25 / 0,15) reproduisent les 6 règles de la diapo 3.
- Fiabilité : marge = 15 × (1 − indice) (à fixer avec l'expert). Âge : Confirmé > Expérimenté > Jeune pour la valeur immédiate, inversé pour le potentiel.
- Valeurs d'or : calculées par une implémentation de référence **indépendante** (boucles pures) + 2 cas analytiques (centroïde 93,33 / 6,67) ; à compléter par des calculs manuels de l'expert. Pas de scikit-fuzzy (non installé).
- Non fait : tests Playwright/Vitest, CI GitHub, ANFIS, import CSV, historique de variables dans l'UI, authentification.
>>>>>>> 6653251 (Initial commit)
