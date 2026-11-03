# Resort sizing

Ce projet R&D public classe les stations de ski par taille, puis estime une taille
pour les stations qui ne disposent pas de toutes les mesures nécessaires au
clustering principal.

Le projet est autonome : les jeux de données d'entrée nécessaires à l'analyse sont
versionnés dans `data/imported/`. Il ne nécessite ni base de données, ni fichier
d'environnement, ni autre dépôt local.

## Contenu

- `data/imported/classification_features.csv` : données d'entrée de la classification ;
- `data/imported/prediction_features.csv` : données d'entrée de la prédiction ;
- `notebooks/resort_data_analysis.ipynb` : profil des colonnes, qualité des données et visualisations ;
- `notebooks/resort_size_classification.ipynb` : classification par taille ;
- `notebooks/resort_size_prediction.ipynb` : prédiction pour les stations incomplètes ;
- `data/outputs/` : résultats publiables produits par les notebooks.

Les fichiers de `data/imported/` sont des instantanés publics préparés pour cette
analyse. Ils ne contiennent aucun secret de connexion.

## Installation

Le projet utilise Python 3.12. Depuis la racine du dépôt SkiJo :

```bash
cd resort_sizing
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## Exécution complète

La commande suivante exécute les trois notebooks dans le bon ordre :

```bash
./.venv/bin/python scripts/run_analysis.py
```

Elle régénère :

- `data/outputs/classified_resorts.csv` ;
- `data/outputs/predicted_resort_sizes.csv`.

Les notebooks peuvent aussi être ouverts dans JupyterLab :

```bash
./.venv/bin/jupyter lab
```

## Fichiers générés et Git

Les petits CSV de `data/outputs/` sont versionnés volontairement : les résultats
sont ainsi consultables sans exécuter Python et toute nouvelle exécution peut être
comparée à la version publiée. Les sorties intégrées aux cellules des notebooks ne
sont pas versionnées afin de garder des notebooks lisibles et des diffs Git utiles.
