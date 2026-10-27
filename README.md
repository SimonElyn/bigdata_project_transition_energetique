# Rentabilité de la transition énergétique : comparatif par zone climatique

## Auteur
- Simon Elyn

## Prérequis
- Un compte Onyxia (SSP Cloud) et un service **VSCode-python** ou **Jupyter-pyspark** lancé.
- Python ≥ 3.10 : `pip install -r requirements.txt`
- Variable d'environnement : `export S3_BUCKET=<votre_id_onyxia>`. Les identifiants S3 sont injectés par Onyxia.

## Dataset
| Source | URL | Licence | Téléchargé le | Taille |
|---|---|---|---|---|
| DPE logements existants (ADEME) | _à compléter_ | Licence Ouverte 2.0 | _AAAA-MM-JJ_ | _x Mo_ |
| Prix des carburants, flux instantané | _à compléter_ | Licence Ouverte 2.0 | _AAAA-MM-JJ_ | _x Mo_ |
| PVGIS (JRC) | _à compléter_ | _à vérifier_ | _AAAA-MM-JJ_ | _x Mo_ |
| Tarifs électricité / gaz (CRE) | _à compléter_ | _à compléter_ | _AAAA-MM-JJ_ | _x Mo_ |
| Coûts des travaux et aides (construit par l'équipe) | `src/hypotheses/` | — | — | _x Mo_ |
| **Total brut** | | | | **_x Mo_ (≤ 5 Mo)** |

## Problématique
_≤ 3 phrases : en combien d'années se rentabilisent l'isolation, la pompe à chaleur, le solaire et la voiture électrique pour une maison individuelle, et comment ce délai varie selon la zone climatique H1/H2/H3 ?_

## Chemins S3
- Bucket : `s3://<id_onyxia>/`
- Données brutes : `energie/raw/<source>/`
- Données traitées : `energie/processed/` (`dpe_clean/`, `quality/`, `final/`)

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
