"""
BRONZE - Prix des carburants (flux instantané, data.economie.gouv.fr)

Télécharge le prix du gazole et de l'essence (E10, SP95) dans toutes les stations
des 4 départements étudiés, avec la date de mise à jour de chaque prix.
Résultat TEL QUEL dans data/bronze/carburants/prix_carburants.csv.

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\bronze\\carburants.py
"""
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import DEPARTEMENTS, RACINE  # noqa: E402

# "exports/csv" renvoie TOUTES les lignes qui correspondent au filtre, en CSV
URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/exports/csv")
COLONNES = ["id", "cp", "ville", "code_departement",
            "gazole_prix", "gazole_maj", "e10_prix", "e10_maj", "sp95_prix", "sp95_maj"]
FICHIER_SORTIE = RACINE / "data" / "bronze" / "carburants" / "prix_carburants.csv"

print(f"Début : {datetime.now():%Y-%m-%d %H:%M:%S}")
liste_depts = ",".join(f'"{d}"' for d in DEPARTEMENTS)        # "67","75","35","13"
params = {
    "where": f"code_departement IN ({liste_depts})",           # filtre, comme un WHERE en SQL
    "select": ",".join(COLONNES),                              # les colonnes gardées
    "delimiter": ",",                                          # séparateur virgule (sinon ";")
}
reponse = requests.get(URL, params=params, timeout=120)
reponse.raise_for_status()

FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
FICHIER_SORTIE.write_bytes(reponse.content)                    # on écrit la réponse brute

nb_stations = reponse.content.count(b"\n") - 1
print(f"Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")
print(f"Total : {nb_stations} stations, {FICHIER_SORTIE.stat().st_size / 1e6:.3f} Mo")
print(f"Fin : {datetime.now():%Y-%m-%d %H:%M:%S}")
