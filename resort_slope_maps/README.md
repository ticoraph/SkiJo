# Resort slope maps

Ce projet R&D public transforme des plans de pistes en données structurées : pistes,
remontées mécaniques, légendes, activités et autres informations visibles.

Le projet est autonome pour reproduire les résultats publiés. Il contient un
inventaire public des plans, des remontées de référence et des extractions structurées
nettoyées. Il ne nécessite ni base de données, ni autre dépôt local, ni appel payant
pour régénérer les CSV de `data/outputs/`.

## Données publiées

`data/imported/` contient :

- `slope_map_inventory.csv` : métadonnées, URL source et SHA-256 des plans ;
- `database_lifts.csv` : remontées publiques utilisées pour la comparaison ;
- `extraction_records.jsonl` : extractions structurées publiables, sans OCR brut,
  identifiant interne, chemin local ou information de facturation.

Les images des plans ne sont pas redistribuées. Une image accessible publiquement
reste généralement protégée par le droit d'auteur. Les URLs sont conservées pour la
traçabilité et pour permettre un téléchargement facultatif dans le respect des
conditions de chaque source.

La licence MIT du dépôt couvre le code du projet. Elle ne concède aucun droit sur les
plans, marques, noms ou autres contenus provenant de tiers ; ces droits restent ceux
de leurs titulaires respectifs.

## Installation

Le projet utilise Python 3.11 ou 3.12. Depuis la racine du dépôt SkiJo :

```bash
cd resort_slope_maps
python -m venv .venv
./.venv/bin/python -m pip install -e ".[notebook]"
```

Tesseract est facultatif et sert uniquement aux nouvelles expériences d'extraction.
Sur macOS :

```bash
brew install tesseract
```

## Reproduire les résultats

Cette commande exécute le notebook sans appel réseau ni appel OpenAI :

```bash
./.venv/bin/python scripts/run_analysis.py
```

Elle relit `data/imported/extraction_records.jsonl` et régénère les fichiers de
`data/outputs/`.

Le notebook peut aussi être ouvert dans JupyterLab :

```bash
./.venv/bin/jupyter lab
```

## Télécharger des plans pour une nouvelle expérience

Le téléchargement est facultatif. Avant de l'utiliser, vérifier les conditions et
licences des sites sources. Les fichiers sont écrits dans `data/maps/`, ignoré par
Git, puis contrôlés avec leur SHA-256 :

```bash
./.venv/bin/python scripts/download_maps.py --accept-source-terms --limit 3
```

Certaines URLs peuvent avoir expiré ou retourner une version différente. Le script
signale alors l'erreur ou un `hash_mismatch` sans accepter silencieusement le fichier.

## Nouvelle extraction vision

Une nouvelle extraction nécessite une clé API et peut être payante :

```bash
cp .env.example .env
```

Dans le notebook, conserver d'abord `LIMIT = 3`, puis passer explicitement
`RUN_EXTRACTION = True`. Les réponses brutes, le texte OCR et les caches restent dans
`data/cache/` et `data/working/`, tous deux ignorés par Git.

## Hébergement futur des images

Si les titulaires des droits autorisent la redistribution, un dataset Hugging Face est
adapté à ces images et à leurs métadonnées. Une version JPEG limitée à 2 048 pixels et
une qualité de 82 représente environ 344 Mio pour l'inventaire actuel, contre environ
1,22 Gio pour les originaux. Kaggle peut servir de miroir analytique, mais n'est pas
nécessaire pour exécuter ce projet.

## Package Python

Le code réutilisable vit dans `src/resort_slope_maps/`. Les applications qui
l'utilisent en production doivent épingler une révision Git immuable. Une modification
du laboratoire n'est ainsi promue qu'après validation explicite.
