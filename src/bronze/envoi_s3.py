"""
BRONZE - Envoi des données brutes sur le stockage S3 d'Onyxia

Copie :
  data/bronze/*          -> s3://<S3_BUCKET>/energie/bronze/
  src/hypotheses/*.csv   -> s3://<S3_BUCKET>/energie/bronze/hypotheses/
puis affiche le contenu du bucket avec les tailles (capture d'écran pour les preuves).

Identifiants :
  - dans un service Onyxia : déjà fournis automatiquement, il suffit de faire
        export S3_BUCKET=<ton_id_onyxia>
  - sur ton PC : copier depuis Onyxia > Mon compte > Connexion au stockage les variables
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_S3_ENDPOINT
    et définir S3_BUCKET.

Lancer depuis la racine du projet :
    python src/bronze/envoi_s3.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import s3fs

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import RACINE  # noqa: E402

bucket = os.environ.get("S3_BUCKET")
if not bucket:
    sys.exit("Variable S3_BUCKET manquante (ton identifiant Onyxia).")

endpoint = os.environ.get("AWS_S3_ENDPOINT", "minio.lab.sspcloud.fr")
fs = s3fs.S3FileSystem(
    client_kwargs={"endpoint_url": f"https://{endpoint}"},
    key=os.environ.get("AWS_ACCESS_KEY_ID"),
    secret=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    token=os.environ.get("AWS_SESSION_TOKEN"),
)
destination = f"{bucket}/energie/bronze"

print(f"Début : {datetime.now():%Y-%m-%d %H:%M:%S} | bucket : {bucket}")

# 1. Les fichiers téléchargés (dpe, carburants, pvgis)
for fichier in sorted((RACINE / "data" / "bronze").rglob("*")):
    if fichier.is_file():
        cible = f"{destination}/{fichier.relative_to(RACINE / 'data' / 'bronze').as_posix()}"
        fs.put(str(fichier), cible)
        print(f"   envoyé : {cible}")

# 2. Les hypothèses écrites à la main
for fichier in sorted((RACINE / "src" / "hypotheses").glob("*.csv")):
    cible = f"{destination}/hypotheses/{fichier.name}"
    fs.put(str(fichier), cible)
    print(f"   envoyé : {cible}")

# 3. Contenu final du bucket, avec les tailles
print(f"\nContenu de s3://{destination} :")
total = 0
for chemin, infos in sorted(fs.find(destination, detail=True).items()):
    total += infos["size"]
    print(f"   {chemin:<75} {infos['size'] / 1e6:8.3f} Mo")
print(f"   TOTAL : {total / 1e6:.3f} Mo (limite du sujet : 5 Mo)")
print(f"Fin : {datetime.now():%Y-%m-%d %H:%M:%S}")
