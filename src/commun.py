"""
OUTILS PARTAGÉS par tous les scripts du projet : chemins, Spark, lecture/écriture.

Deux modes de stockage, choisis avec la variable d'environnement STORAGE :
  - STORAGE=local (par défaut) : tout se passe dans le dossier data/ du projet (tests sur ton PC)
  - STORAGE=s3                 : tout se passe sur ton bucket Onyxia, s3://$S3_BUCKET/energie/

Les couches :
  bronze = données brutes, telles que téléchargées (CSV, JSON)
  silver = données nettoyées (Parquet)
  gold   = résultats (Parquet + CSV)
"""
import os
import platform
import time
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]           # dossier racine du projet
STORAGE = os.environ.get("STORAGE", "local")

# Les 4 départements étudiés : zone climatique, sous-zone (zonage officiel de la
# réglementation thermique : H1a, H1b, H2a...) et chef-lieu (coordonnées pour PVGIS)
DEPARTEMENTS = {
    "67": {"zone": "H1", "sous_zone": "H1b", "nom": "Bas-Rhin",         "ville": "Strasbourg",
           "lat": 48.5734, "lon": 7.7521},
    "75": {"zone": "H1", "sous_zone": "H1a", "nom": "Paris",            "ville": "Paris",
           "lat": 48.8566, "lon": 2.3522},
    "35": {"zone": "H2", "sous_zone": "H2a", "nom": "Ille-et-Vilaine",  "ville": "Rennes",
           "lat": 48.1173, "lon": -1.6778},
    "13": {"zone": "H3", "sous_zone": "H3",  "nom": "Bouches-du-Rhône", "ville": "Marseille",
           "lat": 43.2965, "lon": 5.3698},
}

# ----- Chemins des 3 couches -----
if STORAGE == "s3":
    BUCKET = os.environ["S3_BUCKET"]                     # ton identifiant Onyxia
    BASE = f"s3a://{BUCKET}/energie"
    HYPOTHESES = f"{BASE}/bronze/hypotheses"             # envoyées sur S3 par envoi_s3.py
else:
    # "file:///C:/..." : Spark ne comprend pas les espaces encodés en %20, on écrit le chemin tel quel
    BASE = "file:///" + (RACINE / "data").as_posix().lstrip("/")
    HYPOTHESES = "file:///" + (RACINE / "src" / "hypotheses").as_posix().lstrip("/")
BRONZE, SILVER, GOLD = f"{BASE}/bronze", f"{BASE}/silver", f"{BASE}/gold"


def spark_session(nom: str):
    """Démarre Spark. Sur Onyxia, la configuration S3 est complétée avec les variables d'environnement."""
    from pyspark.sql import SparkSession
    builder = (SparkSession.builder.appName(f"energie-{nom}")
               .config("spark.sql.session.timeZone", "Europe/Paris")
               # Arrow : échange rapide pandas <-> Spark
               .config("spark.sql.execution.arrow.pyspark.enabled", "true"))
    if STORAGE == "s3":
        endpoint = os.environ.get("AWS_S3_ENDPOINT", "minio.lab.sspcloud.fr")
        builder = (builder
                   .config("spark.hadoop.fs.s3a.endpoint", f"https://{endpoint}")
                   .config("spark.hadoop.fs.s3a.path.style.access", "true")
                   .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                           "org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider"))
    else:
        builder = (builder.master("local[*]")
                   .config("spark.ui.showConsoleProgress", "false")
                   # 512 Mo suffisent largement pour 3 Mo de données, et évitent de saturer un petit PC
                   .config("spark.driver.memory", "512m")
                   # 4 morceaux au lieu de 200 par défaut : moins de tâches, moins de mémoire
                   .config("spark.sql.shuffle.partitions", "4"))
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Spark {spark.version} | script={nom} | stockage={BASE}")
    return spark


def _windows_local() -> bool:
    # Sous Windows, Spark ne sait pas lire/écrire des Parquet en local sans un utilitaire
    # Hadoop (winutils.exe). On passe alors par pandas. Sur Onyxia (Linux), Spark fait tout seul.
    return STORAGE != "s3" and platform.system() == "Windows"


def ecrire(df, couche: str, nom: str, csv: bool = False) -> None:
    """Écrit un DataFrame Spark dans <couche>/<nom> (Parquet), plus une copie CSV si csv=True."""
    chemin = f"{BASE}/{couche}/{nom}"
    if _windows_local():
        dossier = RACINE / "data" / couche / nom
        dossier.mkdir(parents=True, exist_ok=True)
        pdf = df.toPandas()
        pdf.to_parquet(dossier / "part-00000.parquet", index=False)
        if csv:
            pdf.to_csv(dossier.with_suffix(".csv"), index=False, encoding="utf-8")
    else:
        df.write.mode("overwrite").parquet(chemin)
        if csv:
            df.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{chemin}_csv")
    print(f"   -> écrit : {couche}/{nom} ({df.count()} lignes)")


def lire(spark, couche: str, nom: str):
    """Lit <couche>/<nom> écrit par ecrire()."""
    if _windows_local():
        return spark.createDataFrame(pd.read_parquet(RACINE / "data" / couche / nom))
    return spark.read.parquet(f"{BASE}/{couche}/{nom}")


def petite_table(spark, lignes: list, colonnes: list):
    """Crée un petit DataFrame Spark à partir d'une liste Python (passe par pandas)."""
    return spark.createDataFrame(pd.DataFrame(lignes, columns=colonnes))


def lire_hypotheses(spark) -> dict:
    """couts_travaux.csv -> dictionnaire {parametre: valeur}."""
    lignes = spark.read.csv(f"{HYPOTHESES}/couts_travaux.csv", header=True).collect()
    return {l["parametre"]: float(l["valeur"]) for l in lignes}


def lire_tarifs(spark) -> dict:
    """tarifs_energie.csv -> dictionnaire {energie: prix en €/kWh}."""
    lignes = spark.read.csv(f"{HYPOTHESES}/tarifs_energie.csv", header=True).collect()
    return {l["energie"]: float(l["prix_eur_kwh"]) for l in lignes}
