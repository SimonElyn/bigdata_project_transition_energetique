"""
BRONZE - PVGIS (Commission européenne, JRC) : production des panneaux solaires

Pour chaque chef-lieu (Strasbourg, Paris, Rennes, Marseille), on demande à PVGIS
combien produit 1 kWc de panneaux en toiture sur une année.
La réponse complète (JSON) est gardée TELLE QUELLE dans data/bronze/pvgis/pvgis_villes.json.

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\bronze\\pvgis.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

# Permet d'importer src/commun.py (le dossier parent de ce script)
sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import DEPARTEMENTS, RACINE  # noqa: E402

URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
FICHIER_SORTIE = RACINE / "data" / "bronze" / "pvgis" / "pvgis_villes.json"

print(f"Début : {datetime.now():%Y-%m-%d %H:%M:%S}")
reponses = {}
for departement, info in DEPARTEMENTS.items():
    params = {
        "lat": info["lat"], "lon": info["lon"],   # position du chef-lieu
        "peakpower": 1,              # 1 kWc : on multipliera ensuite par la taille de l'installation
        "loss": 14,                  # 14 % de pertes (câbles, onduleur...) : valeur conseillée par PVGIS
        "mountingplace": "building", # panneaux posés sur un toit
        "optimalangles": 1,          # inclinaison et orientation optimales
        "outputformat": "json",
    }
    print(f"{info['ville']} ({departement})...")
    reponse = requests.get(URL, params=params, timeout=120)
    reponse.raise_for_status()
    reponses[departement] = reponse.json()
    production = reponses[departement]["outputs"]["totals"]["fixed"]["E_y"]
    print(f"   -> {production:.0f} kWh par an pour 1 kWc")

FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
FICHIER_SORTIE.write_text(json.dumps(reponses, ensure_ascii=False), encoding="utf-8")
print(f"Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)} ({FICHIER_SORTIE.stat().st_size / 1e6:.3f} Mo)")
print(f"Fin : {datetime.now():%Y-%m-%d %H:%M:%S}")
