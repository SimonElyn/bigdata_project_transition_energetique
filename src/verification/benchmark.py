"""
BENCHMARK - pandas, DuckDB et Spark sur le même calcul (mesures pour le rapport)

Le sujet demande de justifier ses choix d'outils avec SES PROPRES MESURES.
On chronomètre les 3 outils sur le même travail, typique du projet :
    lire le CSV brut des DPE, puis calculer par département et par énergie
    la consommation médiane et le nombre de maisons.

Pour voir ce qui se passe quand les données grossissent, on multiplie le jeu de données
en mémoire (×1, ×10, ×50) sans écrire de gros fichiers sur le disque.
Chaque mesure est répétée 3 fois ; on garde la médiane (plus stable).

Sorties (dans evidence/, preuves pour le rendu) :
  benchmark.csv : les temps mesurés
  benchmark.png : le graphique des temps

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\verification\\benchmark.py
"""
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd              # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import RACINE, spark_session  # noqa: E402

DPE_BRUT = RACINE / "data" / "bronze" / "dpe" / "dpe_maisons.csv"
EVIDENCE = RACINE / "evidence"
FACTEURS = [1, 10, 50]           # taille des données : ×1 = 22 457 maisons, ×50 ≈ 1,1 million
REPETITIONS = 3
COLONNES = ["code_departement_ban", "type_energie_principale_chauffage", "conso_chauffage_ef"]


# ---- Le même calcul, écrit avec chaque outil ----
def avec_pandas(facteur):
    df = pd.read_csv(DPE_BRUT, usecols=COLONNES)
    df = pd.concat([df] * facteur, ignore_index=True)        # données multipliées en mémoire
    return (df.groupby(["code_departement_ban", "type_energie_principale_chauffage"])["conso_chauffage_ef"]
              .agg(["median", "count"]))


def avec_duckdb(facteur):
    return duckdb.sql(f"""
        SELECT code_departement_ban, type_energie_principale_chauffage,
               MEDIAN(conso_chauffage_ef), COUNT(*)
        FROM read_csv('{DPE_BRUT.as_posix()}', header = true), range({facteur})   -- ×facteur
        GROUP BY ALL
    """).fetchall()


def avec_spark(facteur):
    df = spark.read.csv(f"file:///{DPE_BRUT.as_posix().lstrip('/')}", header=True, inferSchema=True)
    df = df.select(*COLONNES).crossJoin(spark.range(facteur))  # données multipliées en mémoire
    return (df.groupBy("code_departement_ban", "type_energie_principale_chauffage")
              .agg(F.median("conso_chauffage_ef"), F.count("*")).collect())


spark = spark_session("benchmark")
avec_spark(1)                    # « échauffement » : le premier calcul Spark est toujours lent (démarrage)

mesures = []
for facteur in FACTEURS:
    for outil, fonction in [("pandas", avec_pandas), ("DuckDB", avec_duckdb), ("Spark", avec_spark)]:
        temps = []
        for _ in range(REPETITIONS):
            debut = time.perf_counter()
            fonction(facteur)
            temps.append(time.perf_counter() - debut)
        mediane = statistics.median(temps)
        mesures.append({"facteur": facteur, "lignes": 22457 * facteur, "outil": outil,
                        "secondes": round(mediane, 3)})
        print(f"×{facteur:<3} {22457 * facteur:>9} lignes  {outil:<7} {mediane:6.2f} s")
spark.stop()

# ---- Sauvegarde des mesures + graphique ----
EVIDENCE.mkdir(exist_ok=True)
resultats = pd.DataFrame(mesures)
resultats["machine"] = f"{platform.system()} {platform.machine()}, {os.cpu_count()} coeurs"
resultats.to_csv(EVIDENCE / "benchmark.csv", index=False)

fig, ax = plt.subplots(figsize=(11, 6))
couleurs = {"pandas": "#e76f51", "DuckDB": "#e9c46a", "Spark": "#457b9d"}
for i, (outil, d) in enumerate(resultats.groupby("outil", sort=False)):
    x = [j + (i - 1) * 0.27 for j in range(len(FACTEURS))]
    b = ax.bar(x, d["secondes"], 0.27, color=couleurs[outil], label=outil)
    ax.bar_label(b, labels=[f"{s:.2f} s" for s in d["secondes"]], padding=3, fontsize=9)
ax.set_xticks(range(len(FACTEURS)), [f"×{f}\n{22457 * f:,} maisons".replace(",", " ") for f in FACTEURS])
ax.set_ylabel("Temps (secondes, médiane de 3 essais) - moins = mieux")
ax.set_title("Lire le CSV des DPE et calculer la conso médiane par département et énergie",
             fontweight="bold")
ax.legend(frameon=False)
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(EVIDENCE / "benchmark.png", dpi=120)
print(f"Écrit : evidence/benchmark.csv et evidence/benchmark.png ({time.strftime('%Y-%m-%d %H:%M:%S')})")
