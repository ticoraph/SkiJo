# SkiJo

Skījō (スキー場) signifie « station de ski » en japonais.

Ce dépôt regroupe deux projets de R&D autour des stations de ski, en Python et notebooks Jupyter. Les données d'entrée et les résultats sont versionnés : tout se reproduit sans base de données, sans clé API et sans autre dépôt.

## Projets

| Projet | Ce qu'il fait | Résultats |
| --- | --- | --- |
| [`resort_sizing`](resort_sizing/) | Classe environ 200 stations par taille (petite, moyenne, intermédiaire, grande, hors catégorie) avec un KMeans sur les kilomètres de pistes et la longueur, le dénivelé et le débit des remontées, puis prédit la taille des stations pour lesquelles il manque des mesures. | `data/outputs/classified_resorts.csv`, `predicted_resort_sizes.csv` |
| [`resort_slope_maps`](resort_slope_maps/) | Transforme des plans de pistes en données structurées (pistes, remontées, légendes, activités) avec un LLM de vision, puis compare les remontées lues aux remontées d'une base de référence. | `data/outputs/*.csv` |

## Démarrage rapide

Python 3.12 (3.11 accepté pour `resort_slope_maps`).

```bash
# Classification de la taille des stations (~40 s)
cd resort_sizing
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python scripts/run_analysis.py

# Extraction depuis les plans de pistes (~12 s, sans appel réseau ni clé)
cd ../resort_slope_maps
python -m venv .venv
./.venv/bin/python -m pip install -e ".[notebook]"
./.venv/bin/python scripts/run_analysis.py
```

Les notebooks s'ouvrent aussi dans JupyterLab. Le détail de chaque projet est dans son `README.md`.

## Données et droits

La licence MIT couvre le code. Elle ne donne aucun droit sur les plans de pistes, les marques ni les noms de stations, qui restent à leurs titulaires : les plans ne sont pas redistribués, seuls leur URL et leur empreinte SHA-256 le sont. Les adresses de contact d'exploitants qui figurent sur certains plans publics apparaissent dans quelques lignes des extractions ; pour en demander le retrait, passez par les [Discussions](https://github.com/ticoraph/ticoraph/discussions).

## Contribuer

Ce dépôt n'est pas ouvert aux contributions. Pour échanger, utilisez les [Discussions](https://github.com/ticoraph/ticoraph/discussions) du dépôt de profil.

## Licence

[MIT](LICENSE)
