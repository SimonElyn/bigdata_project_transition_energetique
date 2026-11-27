# Rentabilité de la transition énergétique : comparatif par zone climatique

## Auteurs
- Simon Elyn ([@SimonElyn](https://github.com/SimonElyn))
- Yohann ([@Yohannkp](https://github.com/Yohannkp))
- Yacine ([@Yacine0808](https://github.com/Yacine0808))

## Problématique
En combien d'années se rentabilisent l'isolation (murs, toiture), la pompe à chaleur, les panneaux solaires et la voiture électrique pour une maison individuelle ?
Ce délai change-t-il selon la zone climatique (H1, H2, H3) ? On compare quatre départements : Bas-Rhin (H1b), Paris (H1a), Ille-et-Vilaine (H2a) et Bouches-du-Rhône (H3).

Une seule formule pour toutes les solutions : **années de retour = investissement net ÷ gain par an**.

## Prérequis
- Python ≥ 3.10 et Java 17 ou plus récent (pour Spark) : `pip install -r requirements.txt`
- Pour travailler sur S3 : un compte Onyxia (SSP Cloud) avec un service **VSCode-python** ou **Jupyter-pyspark**, puis `export S3_BUCKET=<votre_id_onyxia>`. Les identifiants S3 sont injectés par Onyxia ; sur un PC, les copier depuis *Mon compte > Connexion au stockage*.

## Dataset
| Source | URL | Licence | Contenu gardé | Taille |
|---|---|---|---|---|
| DPE logements existants (ADEME) | [data.ademe.fr/datasets/dpe03existant](https://data.ademe.fr/datasets/dpe03existant) | Licence Ouverte 2.0 (Etalab) | ~22 500 maisons tirées au hasard, 12 colonnes | 2,30 Mo |
| Prix des carburants, flux instantané | [data.economie.gouv.fr](https://data.economie.gouv.fr/explore/dataset/prix-des-carburants-en-france-flux-instantane-v2/) | Licence Ouverte 2.0 (Etalab) | ~620 stations, gazole, E10, SP95 | 0,06 Mo |
| PVGIS : production solaire (JRC) | [re.jrc.ec.europa.eu/api/v5_3/PVcalc](https://re.jrc.ec.europa.eu/pvg_tools/fr/) | Réutilisation libre avec citation (Commission européenne) | 1 kWc en toiture, 4 chefs-lieux | 0,02 Mo |
| PVGIS : températures mensuelles 2005-2023 | [re.jrc.ec.europa.eu/api/v5_3/MRcalc](https://re.jrc.ec.europa.eu/pvg_tools/fr/) | Réutilisation libre avec citation (Commission européenne) | 19 ans × 12 mois, 4 chefs-lieux | 0,04 Mo |
| Tarifs de l'énergie (CRE, ministère) | sources citées ligne par ligne dans `src/hypotheses/tarifs_energie.csv` | données publiques | électricité, gaz, fioul, bois en €/kWh | < 0,01 Mo |
| Coûts des travaux et aides (construit par l'équipe) | `src/hypotheses/couts_travaux.csv` | — | 25 paramètres, chacun sourcé ou marqué HYPOTHÈSE | < 0,01 Mo |
| **Total brut** | | | | **≈ 2,4 Mo (≤ 5 Mo)** |

Les données sont téléchargées par les scripts `src/bronze/` à chaque exécution ; le DPE est un tirage aléatoire, donc les chiffres varient légèrement d'une exécution à l'autre. Tailles mesurées le 27/11/2026.

## Architecture (bronze, silver, gold)
| Couche | Contenu | Scripts |
|---|---|---|
| bronze | données brutes, telles que téléchargées (CSV, JSON) | `src/bronze/*.py` |
| silver | données nettoyées et typées + rapport qualité (Parquet) | `src/silver/nettoyage.py` |
| gold | tableau de rentabilité, synthèse par zone, graphiques (Parquet, CSV, PNG) | `src/gold/rentabilite.py`, `src/gold/graphique.py` |

Outils partagés (chemins, Spark, lecture/écriture) : `src/commun.py`. La variable `STORAGE` choisit le stockage : `local` (par défaut, dossier `data/`) ou `s3`.

## Chemins S3
- Bucket : `s3://<id_onyxia>/energie/`
- Données brutes : `energie/bronze/` (`dpe/`, `carburants/`, `pvgis/`) et hypothèses : `energie/bronze/hypotheses/`
- Données nettoyées : `energie/silver/` (`dpe_propre/`, `carburants_propre/`, `rapport_qualite/`)
- Résultats : `energie/gold/` (`rentabilite/`, `detail_isolation/`, `rentabilite_par_zone/`)

## Reproduction
```bash
git clone https://github.com/SimonElyn/bigdata_project_transition_energetique.git
cd bigdata_project_transition_energetique
pip install -r requirements.txt

# 1. Ingestion (bronze) : téléchargement des données brutes dans data/bronze/
python src/bronze/dpe.py
python src/bronze/carburants.py
python src/bronze/pvgis.py
python src/bronze/temperatures.py

# 2. Qualité et nettoyage (silver)
python src/silver/nettoyage.py

# 3. Rentabilité et graphiques (gold) : data/gold/*.csv et data/gold/graphique_*.png
python src/gold/rentabilite.py

# 4. Vérification et mesures : evidence/
python src/verification/verif_duckdb.py
python src/verification/benchmark.py
```

**Sur Onyxia (S3)** : après l'étape 1, lancer `python src/bronze/envoi_s3.py` pour copier les données brutes et les hypothèses sur le bucket, puis les étapes 2 et 3 avec `STORAGE=s3` (par exemple `STORAGE=s3 python src/silver/nettoyage.py`). La vérification DuckDB relit les fichiers locaux de `data/` : la lancer en mode local.

**Relancer une étape** : chaque script relit la couche précédente et réécrit la sienne (mode `overwrite`). On peut donc relancer une étape seule, par exemple `python src/gold/rentabilite.py` après avoir modifié une hypothèse. `python src/gold/graphique.py` redessine les graphiques sans Spark, à partir de `data/gold/rentabilite.csv`.

## Résultats et preuves
- `src/resultats.ipynb` : tableau des années de retour par solution et par département, classement, graphique.
- `src/hypotheses/hypotheses_projet_transition_energetique.html` : synthèse lisible de toutes les hypothèses.
- `evidence/verification_duckdb.txt` : le calcul de la pompe à chaleur refait en SQL avec DuckDB à partir des données brutes donne 12 résultats sur 12 identiques à Spark.
- `evidence/benchmark.csv` et `benchmark.png` : temps de pandas, DuckDB et Spark sur le même calcul, de 22 000 à 1,1 million de lignes.
