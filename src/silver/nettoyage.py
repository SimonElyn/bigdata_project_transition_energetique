"""
SILVER - Contrôle qualité et nettoyage (Spark)

Lit les données brutes (bronze), COMPTE chaque problème de qualité, puis nettoie.

Sorties (couche silver, format Parquet) :
  rapport_qualite   : une ligne par problème : nombre de lignes touchées, % et traitement appliqué
  dpe_propre        : maisons nettoyées, colonnes typées (nombres, dates), zone et énergie normalisées
  carburants_propre : un prix par station et par carburant, prix récents et plausibles uniquement

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\silver\\nettoyage.py
"""
import sys
from pathlib import Path

from pyspark.sql import functions as F

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import BRONZE, DEPARTEMENTS, ecrire, petite_table, spark_session  # noqa: E402

# Bornes des valeurs plausibles (au-delà = erreur de saisie)
SURFACE_MIN, SURFACE_MAX = 15, 500        # m² pour une maison
CONSO_M2_MIN, CONSO_M2_MAX = 5, 800       # kWh de chauffage par m² et par an
PRIX_MIN, PRIX_MAX = 1.0, 3.0             # € par litre de carburant
PRIX_AGE_MAX_JOURS = 30                   # un prix plus vieux n'est plus représentatif

spark = spark_session("silver_nettoyage")
zone_du_dept = F.create_map(*[F.lit(x) for d, i in DEPARTEMENTS.items() for x in (d, i["zone"])])
problemes = []   # (source, problème, nb lignes, nb total, traitement)

# =============================================================================
# 1. DPE
# =============================================================================
brut = spark.read.csv(f"{BRONZE}/dpe/dpe_maisons.csv", header=True)   # tout est lu en texte
n = brut.count()
print(f"DPE bruts : {n} lignes")

dpe = (brut
       # conversion texte -> nombres (une valeur illisible devient vide/NULL)
       .withColumn("surface", F.col("surface_habitable_logement").cast("double"))
       .withColumn("conso_chauffage", F.col("conso_chauffage_ef").cast("double"))
       .withColumn("annee", F.col("annee_construction").cast("int"))
       .withColumn("conso_m2", F.col("conso_chauffage") / F.col("surface"))
       # zone attendue d'après le département, et zone saisie par le diagnostiqueur (H1b -> H1)
       .withColumn("zone_attendue", zone_du_dept[F.col("code_departement_ban")])
       .withColumn("zone_saisie", F.substring("zone_climatique", 1, 2))
       .cache())

# ---- Comptage des problèmes (AVANT nettoyage) ----
def compter(condition):
    return dpe.filter(condition).count()

surface, conso, conso_m2 = F.col("surface"), F.col("conso_chauffage"), F.col("conso_m2")
zone_saisie = F.col("zone_saisie")
problemes += [
    ("DPE", "doublon de numero_dpe", n - dpe.select("numero_dpe").distinct().count(), n, "ligne supprimée"),
    ("DPE", "surface manquante", compter(surface.isNull()), n, "ligne supprimée"),
    ("DPE", f"surface hors de [{SURFACE_MIN}, {SURFACE_MAX}] m²",
     compter((surface < SURFACE_MIN) | (surface > SURFACE_MAX)), n, "ligne supprimée"),
    ("DPE", "consommation de chauffage manquante ou nulle", compter(conso.isNull() | (conso <= 0)), n, "ligne supprimée"),
    ("DPE", f"consommation par m² hors de [{CONSO_M2_MIN}, {CONSO_M2_MAX}] kWh",
     compter((conso_m2 < CONSO_M2_MIN) | (conso_m2 > CONSO_M2_MAX)), n, "ligne supprimée"),
    ("DPE", "zone climatique vide ou 'Non affecté'",
     compter(zone_saisie.isNull() | ~zone_saisie.isin("H1", "H2", "H3")), n, "zone reprise du département"),
    ("DPE", "zone climatique incohérente avec le département",
     compter(zone_saisie.isin("H1", "H2", "H3") & (zone_saisie != F.col("zone_attendue"))), n,
     "zone reprise du département"),
    ("DPE", "énergie de chauffage manquante", compter(F.col("type_energie_principale_chauffage").isNull()), n,
     "ligne gardée, exclue des calculs en euros"),
    ("DPE", "année de construction manquante", compter(F.col("annee").isNull()), n,
     "ligne gardée (colonne non utilisée dans les calculs)"),
    ("DPE", "qualité d'isolation des murs manquante", compter(F.col("qualite_isolation_murs").isNull()), n,
     "ligne exclue du calcul isolation des murs"),
    ("DPE", "qualité d'isolation de la toiture manquante",
     compter(F.col("qualite_isolation_plancher_haut_comble_perdu").isNull()), n,
     "ligne exclue du calcul isolation toiture (souvent combles aménagés)"),
]

# ---- Nettoyage ----
energie = F.col("type_energie_principale_chauffage")
dpe_propre = (dpe
              .dropDuplicates(["numero_dpe"])
              .filter(surface.between(SURFACE_MIN, SURFACE_MAX))
              .filter(conso > 0)
              .filter(conso_m2.between(CONSO_M2_MIN, CONSO_M2_MAX))
              # 12 libellés d'énergie différents -> 7 catégories
              .withColumn("energie",
                          F.when(energie.startswith("Électricité"), "Électricité")
                           .when(energie == "Gaz naturel", "Gaz naturel")
                           .when(energie == "Fioul domestique", "Fioul domestique")
                           .when(energie == "Bois – Bûches", "Bois – Bûches")
                           .when(energie.startswith("Bois"), "Bois – autres")
                           .when(energie.isin("GPL", "Propane"), "GPL / Propane")
                           .otherwise("Autres"))
              .select("numero_dpe",
                      F.to_date("date_etablissement_dpe").alias("date_dpe"),
                      F.col("code_departement_ban").alias("departement"),
                      F.col("zone_attendue").alias("zone"),        # zone fiable, déduite du département
                      "zone_saisie", "annee", "surface", "etiquette_dpe", "energie",
                      "conso_chauffage", "conso_m2",
                      F.col("qualite_isolation_murs").alias("isolation_murs"),
                      F.col("qualite_isolation_plancher_haut_comble_perdu").alias("isolation_toiture"),
                      F.col("cout_chauffage").cast("double").alias("cout_chauffage_dpe")))
print(f"DPE propres : {dpe_propre.count()} lignes")
ecrire(dpe_propre, "silver", "dpe_propre")
dpe.unpersist()

# =============================================================================
# 2. CARBURANTS : passage en format "long" (une ligne = une station + un carburant)
# =============================================================================
carbu = spark.read.csv(f"{BRONZE}/carburants/prix_carburants.csv", header=True)
date_ref = carbu.agg(F.max(F.col("gazole_maj").cast("timestamp"))).first()[0]   # ~ date de l'extraction
print(f"Stations : {carbu.count()} | date de référence des prix : {date_ref}")

long = None
for c in ("gazole", "e10"):
    part = carbu.select(F.col("id").alias("station"),
                        F.col("code_departement").cast("string").alias("departement"),
                        F.lit(c).alias("carburant"),
                        F.col(f"{c}_prix").cast("double").alias("prix"),
                        F.col(f"{c}_maj").cast("timestamp").alias("mise_a_jour"))
    long = part if long is None else long.unionByName(part)

trop_vieux = F.col("mise_a_jour") < F.lit(date_ref) - F.expr(f"INTERVAL {PRIX_AGE_MAX_JOURS} DAYS")
nl = long.count()
problemes += [
    ("Carburants", "prix absent (carburant non vendu dans la station)", long.filter(F.col("prix").isNull()).count(), nl,
     "ligne supprimée"),
    ("Carburants", f"prix de plus de {PRIX_AGE_MAX_JOURS} jours",
     long.filter(F.col("prix").isNotNull() & trop_vieux).count(), nl, "ligne supprimée"),
    ("Carburants", f"prix hors de [{PRIX_MIN}, {PRIX_MAX}] €/L",
     long.filter(F.col("prix").isNotNull() & ~F.col("prix").between(PRIX_MIN, PRIX_MAX)).count(), nl,
     "ligne supprimée"),
]
carbu_propre = long.filter(F.col("prix").between(PRIX_MIN, PRIX_MAX) & ~trop_vieux)
print(f"Prix de carburant propres : {carbu_propre.count()} lignes")
ecrire(carbu_propre, "silver", "carburants_propre")

# =============================================================================
# 3. RAPPORT QUALITÉ
# =============================================================================
rapport = petite_table(spark,
                       [(s, p, int(k), int(t), round(100 * k / t, 2), tr) for s, p, k, t, tr in problemes],
                       ["source", "probleme", "lignes_touchees", "lignes_total", "pourcentage", "traitement"])
rapport.show(truncate=False)
ecrire(rapport, "silver", "rapport_qualite", csv=True)
spark.stop()
