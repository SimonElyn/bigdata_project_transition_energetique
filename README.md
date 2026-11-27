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

## Chemins S3
- Bucket : `s3://<id_onyxia>/energie/`
- Données brutes : `energie/bronze/` (`dpe/`, `carburants/`, `pvgis/`) et hypothèses : `energie/bronze/hypotheses/`
- Données nettoyées : `energie/silver/` (`dpe_propre/`, `carburants_propre/`, `rapport_qualite/`)
- Résultats : `energie/gold/` (`rentabilite/`, `detail_isolation/`, `rentabilite_par_zone/`)

## Reproduction
```bash
git clone <url_du_repo> && cd bigdata_project
pip install -r requirements.txt
export S3_BUCKET=<votre_id_onyxia>
python src/check_s3.py            # 0. vérifie l'accès S3
# 1. ingestion  : à compléter
# 2. qualité    : à compléter
# 3. pipeline   : à compléter
# 4. vérification : à compléter
```
Relancer une étape : _à compléter_.
