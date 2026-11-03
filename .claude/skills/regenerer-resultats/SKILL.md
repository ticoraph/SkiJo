---
name: regenerer-resultats
description: Régénère et vérifie les CSV de résultats de SkiJo (resort_sizing et resort_slope_maps) depuis un checkout propre. À utiliser après un changement de notebook, de code, de données d'entrée ou de dépendance, ou pour confirmer que les résultats publiés sont reproductibles.
---

# Régénérer les résultats

Les deux projets doivent redonner **exactement** les CSV versionnés de `data/outputs/`. Aucun appel réseau ni clé API n'est nécessaire.

## Étapes

1. Partir d'un état connu : `git status` ne doit montrer que les changements voulus. Pour un test à l'abri des effets du venv local, exporter le dépôt dans le scratchpad : `git archive HEAD | tar -x -C <scratchpad>/skijo`.
2. Pour chaque projet, dans son dossier, créer un venv Python 3.12 neuf (`uv venv --python 3.12 .venv`) et installer les dépendances :
   - `resort_sizing` : `uv pip install --python .venv/bin/python -r requirements.txt ipykernel`
   - `resort_slope_maps` : `uv pip install --python .venv/bin/python -e ".[notebook]"`
3. Lancer `.venv/bin/python scripts/run_analysis.py` (≈ 40 s pour `resort_sizing`, ≈ 12 s pour `resort_slope_maps`). Les messages `Kernel is running over TCP without encryption` sont normaux.
4. Comparer les sorties : `git diff --stat -- '*/data/outputs'` dans le dépôt, ou `diff -rq` entre l'export et le dépôt.
5. Conclure :
   - aucune différence : les résultats sont reproductibles ;
   - différence voulue (donnée ou méthode modifiée) : relire le diff, puis committer CSV et code ensemble ;
   - différence non voulue : chercher la cause (version de dépendance, graine aléatoire, ordre de tri) avant de committer quoi que ce soit.

## À ne pas faire

- Ne pas passer `RUN_EXTRACTION = True` : c'est payant et sans rapport avec la reproductibilité.
- Ne pas enregistrer de kernel Jupyter global (`ipykernel install --user`) : `run_analysis.py` utilise `python3` et n'en a pas besoin. Si on en crée un pour un test, le supprimer ensuite.
- `run_analysis.py` n'écrit pas les notebooks : les sorties intégrées de `resort_sizing/notebooks/` ne se mettent à jour qu'en rouvrant le notebook dans JupyterLab.
