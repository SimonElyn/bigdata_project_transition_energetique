"""
VÉRIFICATION INDÉPENDANTE d'un résultat avec DuckDB (SQL), sans Spark

Le sujet demande de vérifier au moins un résultat par une autre méthode.
On refait ici, avec un autre outil (DuckDB) et un autre langage (SQL), le calcul de la
POMPE À CHALEUR, en repartant des données BRUTES (bronze) et pas des données nettoyées par Spark :
  1. on réapplique les mêmes règles de nettoyage en SQL
  2. on recalcule la consommation médiane, le gain par an et les années de retour
  3. on compare avec le tableau final de Spark (gold/rentabilite.csv)
Si les deux méthodes donnent les mêmes chiffres, le pipeline Spark est validé.

Le compte rendu est écrit dans evidence/verification_duckdb.txt (preuve pour le rendu).

Lancer depuis la racine du projet (après rentabilite.py) :
    .venv\\Scripts\\python src\\verification\\verif_duckdb.py
"""
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import DEPARTEMENTS, RACINE  # noqa: E402

DPE_BRUT = (RACINE / "data" / "bronze" / "dpe" / "dpe_maisons.csv").as_posix()
RESULTAT_SPARK = RACINE / "data" / "gold" / "rentabilite.csv"
HYPOTHESES = RACINE / "src" / "hypotheses"
RAPPORT = RACINE / "evidence" / "verification_duckdb.txt"

lignes = []                                  # tout ce qu'on affiche est aussi écrit dans le rapport


def afficher(texte=""):
    print(texte)
    lignes.append(texte)


afficher(f"Vérification indépendante DuckDB {duckdb.__version__} - {datetime.now():%Y-%m-%d %H:%M:%S}")
afficher(f"Source : {Path(DPE_BRUT).relative_to(RACINE)} (données brutes, bronze)\n")

con = duckdb.connect()                       # base DuckDB en mémoire

# ---- 1. Nettoyage refait en SQL (mêmes règles que silver/nettoyage.py) ----
con.execute(f"""
    CREATE TABLE dpe AS
    SELECT DISTINCT ON (numero_dpe)                         -- doublons supprimés
           CAST(code_departement_ban AS VARCHAR)          AS departement,
           type_energie_principale_chauffage              AS energie,
           TRY_CAST(surface_habitable_logement AS DOUBLE) AS surface,
           TRY_CAST(conso_chauffage_ef AS DOUBLE)         AS conso
    FROM read_csv('{DPE_BRUT}', header = true, all_varchar = true)
    WHERE TRY_CAST(surface_habitable_logement AS DOUBLE) BETWEEN 15 AND 500
      AND TRY_CAST(conso_chauffage_ef AS DOUBLE) > 0
      AND TRY_CAST(conso_chauffage_ef AS DOUBLE)
          / TRY_CAST(surface_habitable_logement AS DOUBLE) BETWEEN 5 AND 800
""")
n_duckdb = con.execute("SELECT COUNT(*) FROM dpe").fetchone()[0]
afficher(f"Maisons après nettoyage : DuckDB = {n_duckdb} (Spark a trouvé 22195 lors du nettoyage silver)")

# ---- 2. Calcul de la pompe à chaleur en SQL ----
# hypothèses lues dans les mêmes fichiers que Spark
H = dict(pd.read_csv(HYPOTHESES / "couts_travaux.csv")[["parametre", "valeur"]].values)
prix = dict(pd.read_csv(HYPOTHESES / "tarifs_energie.csv")[["energie", "prix_eur_kwh"]].values)
cop_sql = " ".join(f"WHEN '{d}' THEN {H['pac_scop_' + i['zone']]}" for d, i in DEPARTEMENTS.items())
investissement = H["pac_cout"] - H["pac_aide"]

cas = [("Gaz naturel",      "energie = 'Gaz naturel'",        H["rendement_chaudiere_gaz"],        "gaz"),
       ("Fioul domestique", "energie = 'Fioul domestique'",   H["rendement_chaudiere_fioul"],      "fioul"),
       ("Électricité",      "energie LIKE 'Électricité%'",    H["rendement_chauffage_electrique"], "radiateurs électriques")]
morceaux = []
for energie, filtre, rendement, nom in cas:
    morceaux.append(con.execute(f"""
        WITH base AS (
            SELECT departement, MEDIAN(conso) AS conso_actuelle,
                   CASE departement {cop_sql} END AS cop
            FROM dpe WHERE {filtre}
            GROUP BY departement
        )
        SELECT departement,
               'Pompe à chaleur (remplace {nom})' AS solution,
               conso_actuelle * {prix[energie]}
                 - conso_actuelle * {rendement} / cop * {prix['Électricité']} AS gain_duckdb
        FROM base
    """).df())
duck = pd.concat(morceaux)
duck["retour_duckdb"] = (investissement / duck["gain_duckdb"]).round(1)

# ---- 3. Comparaison avec le résultat de Spark ----
spark = pd.read_csv(RESULTAT_SPARK, dtype={"departement": str})
comparaison = duck.merge(spark[["departement", "solution", "gain_annuel_eur", "retour_annees"]],
                         on=["departement", "solution"])
comparaison["ecart_eur"] = (comparaison["gain_duckdb"].round(0) - comparaison["gain_annuel_eur"]).abs()
comparaison["identique"] = (comparaison["ecart_eur"] <= 1) & (comparaison["retour_duckdb"] == comparaison["retour_annees"])

afficher("\nPompe à chaleur : gain par an et années de retour, Spark contre DuckDB")
afficher(comparaison.rename(columns={"gain_annuel_eur": "gain_spark", "retour_annees": "retour_spark"})
         [["departement", "solution", "gain_spark", "gain_duckdb", "retour_spark", "retour_duckdb", "identique"]]
         .round({"gain_duckdb": 0}).sort_values(["solution", "departement"]).to_string(index=False))

ok = comparaison["identique"].sum()
afficher(f"\nRÉSULTAT : {ok}/{len(comparaison)} résultats identiques entre Spark et DuckDB"
         + ("  -> pipeline Spark VALIDÉ" if ok == len(comparaison) else "  -> ÉCARTS À EXPLIQUER"))

RAPPORT.parent.mkdir(exist_ok=True)
RAPPORT.write_text("\n".join(lignes), encoding="utf-8")
print(f"\nCompte rendu écrit : {RAPPORT.relative_to(RACINE)}")
