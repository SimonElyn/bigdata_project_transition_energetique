"""
BRONZE - Températures (PVGIS, Commission européenne, JRC, données météo ERA5)

Pour chaque chef-lieu (Strasbourg, Paris, Rennes, Marseille), on demande à PVGIS
la température moyenne de chaque mois, de 2005 à 2023 (19 ans × 12 mois).
Sert à calculer un INDICE DE FROID par zone climatique (température moyenne de l'année
et degrés-jours de chauffage), affiché sur le graphique par zone.
La réponse complète (JSON) est gardée TELLE QUELLE dans data/bronze/pvgis/temperatures_villes.json.

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\bronze\\temperatures.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import DEPARTEMENTS, RACINE  # noqa: E402

# MRcalc = "Monthly Radiation" : données mensuelles ; avtemp=1 ajoute la température
URL = "https://re.jrc.ec.europa.eu/api/v5_3/MRcalc"
FICHIER_SORTIE = RACINE / "data" / "bronze" / "pvgis" / "temperatures_villes.json"

print(f"Début : {datetime.now():%Y-%m-%d %H:%M:%S}")
reponses = {}
for departement, info in DEPARTEMENTS.items():
    params = {
        "lat": info["lat"], "lon": info["lon"],   # position du chef-lieu
        "horirrad": 0,               # on ne veut pas l'ensoleillement ici...
        "avtemp": 1,                 # ...seulement la température moyenne de chaque mois
        "outputformat": "json",
    }
    print(f"{info['ville']} ({departement})...")
    reponse = requests.get(URL, params=params, timeout=120)
    reponse.raise_for_status()
    reponses[departement] = reponse.json()
    mois = reponses[departement]["outputs"]["monthly"]
    moyenne = sum(m["T2m"] for m in mois) / len(mois)
    print(f"   -> {len(mois)} mois, température moyenne {moyenne:.1f} °C")

FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
FICHIER_SORTIE.write_text(json.dumps(reponses, ensure_ascii=False), encoding="utf-8")
print(f"Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)} ({FICHIER_SORTIE.stat().st_size / 1e6:.3f} Mo)")
print(f"Fin : {datetime.now():%Y-%m-%d %H:%M:%S}")
