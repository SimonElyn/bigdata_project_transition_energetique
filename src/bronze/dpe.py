"""
BRONZE - DPE (Diagnostics de Performance Énergétique) de l'ADEME

Ce script télécharge un extrait du jeu de données « DPE Logements existants »
et l'enregistre TEL QUEL (aucune correction) dans data/bronze/dpe/dpe_maisons.csv.

Ce qu'on prend :
  - seulement les MAISONS (pas les appartements)
  - 4 départements : 67 (H1), 75 (H1), 35 (H2), 13 (H3)
  - 12 colonnes utiles au projet (sur plus de 200)
  - un tirage AU HASARD de lignes par département (sort=_rand)

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\bronze\\dpe.py
"""
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# 1. PARAMÈTRES
# ---------------------------------------------------------------------------

# Adresse de l'API de l'ADEME (le jeu de données s'appelle "dpe03existant")
URL = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"

# Département -> nombre de maisons à prendre
# Paris n'a qu'environ 4 457 maisons : avec 5000 on les prend toutes.
DEPARTEMENTS = {
    "67": 6000,   # Bas-Rhin         - zone H1 (nord-est, froid)
    "75": 5000,   # Paris            - zone H1
    "35": 6000,   # Ille-et-Vilaine  - zone H2 (ouest, tempéré)
    "13": 6000,   # Bouches-du-Rhône - zone H3 (méditerranée)
}

# Les 12 colonnes gardées (l'API en propose plus de 200)
COLONNES = [
    "numero_dpe",                                   # identifiant (repérer les doublons)
    "date_etablissement_dpe",                       # date du diagnostic
    "code_departement_ban",                         # département
    "zone_climatique",                              # H1a, H2b, H3...
    "surface_habitable_logement",                   # surface en m²
    "annee_construction",                           # année de construction (souvent vide)
    "etiquette_dpe",                                # classe A à G
    "conso_chauffage_ef",                           # kWh de chauffage par an (donnée clé)
    "type_energie_principale_chauffage",            # gaz, fioul, électricité...
    "qualite_isolation_murs",                       # insuffisante / moyenne / bonne / très bonne
    "qualite_isolation_plancher_haut_comble_perdu", # isolation de la toiture
    "cout_chauffage",                               # facture estimée par le diagnostiqueur (€/an)
]

# Où écrire le fichier.
# Path(__file__) = ce script ; .parents[2] = remonter de 2 dossiers (bronze -> src -> racine).
# Comme ça, le fichier atterrit toujours au bon endroit, d'où que tu lances le script.
RACINE = Path(__file__).resolve().parents[2]
DOSSIER_SORTIE = RACINE / "data" / "bronze" / "dpe"
FICHIER_SORTIE = DOSSIER_SORTIE / "dpe_maisons.csv"


# ---------------------------------------------------------------------------
# 2. APPEL DE L'API POUR CHAQUE DÉPARTEMENT
# ---------------------------------------------------------------------------

print(f"Début : {datetime.now():%Y-%m-%d %H:%M:%S}")

morceaux = []   # on range ici le CSV reçu pour chaque département

for departement, nombre in DEPARTEMENTS.items():
    params = {
        "qs": f"code_departement_ban:{departement} AND type_batiment:maison",  # filtre
        "select": ",".join(COLONNES),   # les colonnes, séparées par des virgules
        "size": nombre,                 # combien de lignes
        "sort": "_rand",                # ordre aléatoire = tirage au hasard
        "format": "csv",                # réponse en CSV plutôt qu'en JSON
    }
    print(f"Département {departement} : demande de {nombre} maisons...")
    reponse = requests.get(URL, params=params, timeout=300)
    reponse.raise_for_status()   # arrête le script avec une erreur claire si l'API répond mal

    # "utf-8-sig" retire le caractère invisible (BOM) que l'ADEME met au début du CSV
    texte = reponse.content.decode("utf-8-sig").strip()
    nb_lignes = len(texte.splitlines()) - 1   # -1 pour ne pas compter l'en-tête
    print(f"   -> {nb_lignes} maisons reçues")
    morceaux.append(texte)


# ---------------------------------------------------------------------------
# 3. COLLER LES 4 MORCEAUX (EN-TÊTE UNE SEULE FOIS)
# ---------------------------------------------------------------------------

# Le 1er morceau est gardé entier (avec la ligne des noms de colonnes).
# Pour les suivants, on enlève la 1re ligne : split("\n", 1) coupe au 1er retour à la ligne,
# [1] garde tout ce qui vient après.
resultat = morceaux[0]
for morceau in morceaux[1:]:
    resultat += "\n" + morceau.split("\n", 1)[1]


# ---------------------------------------------------------------------------
# 4. ÉCRIRE LE FICHIER
# ---------------------------------------------------------------------------

DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)   # crée data/bronze/dpe/ si besoin
FICHIER_SORTIE.write_text(resultat + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. VÉRIFICATION : NOMBRE DE LIGNES ET TAILLE (budget 5 Mo pour tout le projet)
# ---------------------------------------------------------------------------

total_lignes = len(resultat.splitlines()) - 1
taille_mo = FICHIER_SORTIE.stat().st_size / 1_000_000
print(f"Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")
print(f"Total : {total_lignes} maisons, {taille_mo:.2f} Mo")
print(f"Fin : {datetime.now():%Y-%m-%d %H:%M:%S}")
