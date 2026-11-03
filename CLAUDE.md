# SkiJo

Skījō (スキー場) = « station de ski » en japonais. Dépôt de R&D public, deux projets Python indépendants, tous deux pilotés par des notebooks Jupyter. Voir [README.md](README.md) pour la présentation.

## Organisation

- `resort_sizing/` : classe les stations par taille (KMeans sur pistes, longueur, dénivelé et débit des remontées), puis prédit la taille des stations incomplètes. Trois notebooks dans `notebooks/` (analyse, classification, prédiction), à exécuter dans cet ordre ; entrées dans `data/imported/`, résultats dans `data/outputs/`. Python 3.12.
- `resort_slope_maps/` : extrait pistes, remontées, légendes et activités des plans de pistes avec un LLM de vision, puis compare les remontées extraites à `database_lifts.csv`. Le code réutilisable est dans `src/resort_slope_maps/` (`slope_map_extraction.py`, `llm_provider.py` pour LiteLLM, OpenAI ou Gemini), un seul notebook dans `notebooks/`. Python 3.11 ou 3.12.
- Chaque projet a son `README.md`, son `requirements.txt`, son `scripts/run_analysis.py` et son propre venv `.venv` (ignoré par git). Ils ne partagent aucun code.
- `.claude/skills/` : `regenerer-resultats` et `verifier-avant-push`.

## Commandes

```bash
# resort_sizing
cd resort_sizing && python -m venv .venv && ./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python scripts/run_analysis.py       # ~40 s, réécrit data/outputs/*.csv

# resort_slope_maps
cd resort_slope_maps && python -m venv .venv && ./.venv/bin/python -m pip install -e ".[notebook]"
./.venv/bin/python scripts/run_analysis.py       # ~12 s, sans réseau ni clé API, réécrit data/outputs/*.csv
```

Pas de tests automatisés : la vérification, c'est que `run_analysis.py` s'exécute sans erreur et que `git diff data/outputs` reste vide (les deux projets sont reproductibles à l'identique depuis un checkout propre, état au 2026-11-03).

## Pièges

- `scripts/run_analysis.py` exécute les notebooks **en mémoire** : il ne réécrit que les CSV. Pour mettre à jour les sorties intégrées d'un notebook (`resort_sizing`), l'ouvrir dans JupyterLab et l'enregistrer.
- Les notebooks de `resort_sizing` sont versionnés **avec leurs sorties** (graphiques inclus, ~1,3 Mo). Garder `kernelspec` à `python3` (pas de nom de kernel local) et ne rien afficher qui contienne un chemin personnel.
- `resort_slope_maps/data/imported/extraction_records.jsonl` est la source de vérité des extractions publiées ; les CSV de `data/outputs/` en sont dérivés. Ne jamais les éditer à la main.
- Relancer l'extraction vision est **payant** (`RUN_EXTRACTION = True` dans le notebook, clé dans `.env`). Toujours garder `LIMIT = 3` d'abord. Les réponses brutes, l'OCR et les caches vont dans `data/cache/`, `data/working/` et `data/maps/`, tous ignorés par git.
- `src/resort_slope_maps/` est consommé par d'autres applications qui épinglent une révision git : ne pas changer ses signatures publiques sans l'annoncer.
- Les dépendances sont épinglées exactement (`==`) : mettre à jour `pyproject.toml` et `requirements.txt` ensemble, puis rejouer `run_analysis.py`.

## Dépôt public : règles impératives

Ce dépôt **est public** (licence MIT pour le code uniquement). Tout ce qui est versionné est lisible par tous, pour toujours.

- **Jamais dans git** : clés API, `.env`, plans de pistes (images, PDF), réponses brutes du LLM, texte OCR, chemins absolus personnels (`/Users/<nom>/…`), adresses e-mail personnelles, identifiants de facturation ou de compte.
- **Données tierces** : les plans de pistes appartiennent à leurs titulaires. On versionne leur URL et leur SHA-256, jamais l'image. Ne pas ajouter de nouvelle source sans vérifier ses conditions d'utilisation, et garder la mention de licence du README de `resort_slope_maps`.
- **Adresses e-mail dans les données** : `extraction_records.jsonl` et `other_information.csv` contiennent quelques adresses de contact d'exploitants de stations, lues sur des plans publics. Ne pas en ajouter de nouvelles : supprimer le champ ou masquer l'adresse avant de publier de nouvelles extractions.
- **Avant tout `git push`** : lancer le skill `verifier-avant-push`, relire `git log origin/main..HEAD` et le diff, et demander l'accord de l'utilisateur. Ne jamais pousser sans lui.
- **Avant un commit** : relire `git status` et `git diff --cached`. Ne jamais forcer l'ajout d'un fichier ignoré (`git add -f`). Ne jamais réécrire l'historique sans l'accord de l'utilisateur.
- **Identité git** : commiter avec l'adresse `noreply` GitHub (`38759501+ticoraph@users.noreply.github.com`), comme les autres dépôts publics, pas avec une adresse personnelle.
- Si un secret ou une donnée personnelle a déjà été commité : le dire tout de suite à l'utilisateur, la clé est à révoquer chez son fournisseur avant toute autre chose.
- `.pre-commit-config.yaml` et `.github/workflows/checks.yml` appliquent ces garde-fous en local et sur GitHub : ne pas les contourner (`--no-verify`).

## Conventions

- Documentation, commentaires de notebook, messages de commit : français. Identifiants de code et docstrings des scripts : anglais, comme l'existant.
- Les dépôts publics de l'auteur sont fermés aux contributions : issues et wiki désactivés, contact via les Discussions du dépôt de profil `ticoraph/ticoraph`.
- Le modèle par défaut (`gpt-6-luna`) est défini à deux endroits : `DEFAULT_OPENAI_MODEL` dans `llm_provider.py` et `MODEL` dans le notebook. `OPENAI_MODEL` (`.env`) les remplace tous les deux ; en changer le défaut, c'est modifier les deux.
