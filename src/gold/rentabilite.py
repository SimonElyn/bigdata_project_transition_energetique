"""
GOLD - Calcul de la rentabilité de chaque solution, par département (Spark)

Une seule formule pour tout :   années de retour = investissement net ÷ gain par an

  1. Isolation (murs, toiture) : écart de consommation entre maisons mal et bien isolées
  2. Pompe à chaleur           : remplace une chaudière gaz, fioul ou des radiateurs électriques
  3. Panneaux solaires         : production PVGIS × (part autoconsommée × prix élec + surplus × tarif de rachat)
  4. Voiture électrique        : budget carburant - budget électricité

Sorties (couche gold) :
  rentabilite        : le TABLEAU FINAL (Parquet + CSV), une ligne par solution et par département, avec le rang
  detail_isolation   : le détail du calcul isolation par énergie de chauffage (pour le rapport)
  rentabilite_par_zone : moyenne par zone climatique et par domaine, avec l'indice de froid (CSV)
  graphique_*.png    : les 4 graphiques (voir graphique.py), ouverts automatiquement à la fin

Lancer depuis la racine du projet :
    .venv\\Scripts\\python src\\gold\\rentabilite.py
"""
import calendar
import json
import sys
from pathlib import Path

from pyspark.sql import Window
from pyspark.sql import functions as F

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import (BRONZE, DEPARTEMENTS, ecrire, lire, lire_hypotheses, lire_tarifs,  # noqa: E402
                    petite_table, spark_session)
from gold.graphique import dessiner  # noqa: E402

COLONNES_FINALES = ["departement", "solution", "investissement_net_eur", "gain_annuel_kwh",
                    "gain_annuel_eur", "n_observations", "detail"]

spark = spark_session("gold_rentabilite")
dpe = lire(spark, "silver", "dpe_propre")
carbu = lire(spark, "silver", "carburants_propre")
H = lire_hypotheses(spark)       # ex : H["pac_cout"] = 13000
prix = lire_tarifs(spark)        # ex : prix["Électricité"] = 0.2001 €/kWh
prix_elec = prix["Électricité"]
resultats = []                   # un DataFrame par solution, assemblés à la fin

# =============================================================================
# 1. ISOLATION
# Pour chaque département et chaque énergie, on compare la consommation de chauffage
# par m² (médiane) des maisons mal isolées et bien isolées. Écart × surface = kWh économisés.
# =============================================================================
prix_df = petite_table(spark, list(prix.items()), ["energie", "prix_eur_kwh"])
details = None
for solution, colonne, cle in [("Isolation des murs", "isolation_murs", "iso_murs"),
                               ("Isolation de la toiture", "isolation_toiture", "iso_toiture")]:
    mal = F.col(colonne) == "insuffisante"
    bien = F.col(colonne).isin("bonne", "très bonne")
    par_energie = (dpe.filter(F.col(colonne).isNotNull())
                   .join(prix_df, "energie")          # garde les énergies dont on connaît le prix
                   .groupBy("departement", "energie", "prix_eur_kwh").agg(
                       F.median(F.when(mal, F.col("conso_m2"))).alias("conso_m2_mal_isole"),
                       F.median(F.when(bien, F.col("conso_m2"))).alias("conso_m2_bien_isole"),
                       F.median(F.when(mal, F.col("surface"))).alias("surface_mediane"),
                       F.sum(mal.cast("int")).alias("n_mal_isole"),
                       F.sum(bien.cast("int")).alias("n_bien_isole"))
                   # au moins 30 maisons de chaque côté, sinon la médiane n'est pas fiable
                   .filter((F.col("n_mal_isole") >= 30) & (F.col("n_bien_isole") >= 30))
                   .withColumn("gain_kwh", (F.col("conso_m2_mal_isole") - F.col("conso_m2_bien_isole"))
                               * F.col("surface_mediane"))
                   .withColumn("gain_eur", F.col("gain_kwh") * F.col("prix_eur_kwh"))
                   .withColumn("solution", F.lit(solution)))
    details = par_energie if details is None else details.unionByName(par_energie)

    # moyenne par département, pondérée par le nombre de maisons mal isolées de chaque énergie
    poids = F.col("n_mal_isole")
    resultats.append(
        par_energie.groupBy("departement").agg(
            (F.sum(F.col("gain_kwh") * poids) / F.sum(poids)).alias("gain_annuel_kwh"),
            (F.sum(F.col("gain_eur") * poids) / F.sum(poids)).alias("gain_annuel_eur"),
            (F.sum(F.col("surface_mediane") * poids) / F.sum(poids)).alias("surface"),
            F.sum(poids).alias("n_observations"))
        .withColumn("investissement_net_eur",
                    F.col("surface") * H[f"{cle}_ratio_surface"] * H[f"{cle}_cout_m2"] - H[f"{cle}_aide"])
        .withColumn("solution", F.lit(solution))
        .withColumn("detail", F.format_string("maison de %.0f m², %d maisons mal isolées",
                                              "surface", "n_observations"))
        .select(*COLONNES_FINALES))

ecrire(details, "gold", "detail_isolation", csv=True)    # détail consultable dans le CSV

# =============================================================================
# 2. POMPE À CHALEUR
# Chaleur utile = conso actuelle × rendement de la chaudière ; la PAC consomme chaleur utile ÷ COP.
# =============================================================================
cop = F.create_map(*[F.lit(x) for z in ("H1", "H2", "H3") for x in (z, H[f"pac_scop_{z}"])])
# (énergie de chauffage actuelle, rendement de l'ancien chauffage, nom affiché)
for energie, rendement, nom in [
        ("Gaz naturel",      H["rendement_chaudiere_gaz"],        "gaz"),
        ("Fioul domestique", H["rendement_chaudiere_fioul"],      "fioul"),
        # radiateurs électriques : 1 kWh acheté = 1 kWh de chaleur ; la PAC en donne 2,8 à 3,6.
        # Limite : la catégorie "Électricité" du DPE contient aussi des maisons déjà
        # équipées d'une PAC (elles consomment moins), le gain est donc plutôt sous-estimé.
        ("Électricité",      H["rendement_chauffage_electrique"], "radiateurs électriques")]:
    resultats.append(
        dpe.filter(F.col("energie") == energie)
        .groupBy("departement", "zone").agg(F.median("conso_chauffage").alias("conso_actuelle"),
                                            F.count("*").alias("n_observations"))
        .withColumn("cop", cop[F.col("zone")])
        .withColumn("conso_pac", F.col("conso_actuelle") * rendement / F.col("cop"))
        .withColumn("gain_annuel_kwh", F.col("conso_actuelle") - F.col("conso_pac"))
        .withColumn("gain_annuel_eur", F.col("conso_actuelle") * prix[energie] - F.col("conso_pac") * prix_elec)
        .withColumn("investissement_net_eur", F.lit(H["pac_cout"] - H["pac_aide"]))
        .withColumn("solution", F.lit(f"Pompe à chaleur (remplace {nom})"))
        .withColumn("detail", F.format_string("chauffage actuel %.0f kWh/an, COP %.1f", "conso_actuelle", "cop"))
        .select(*COLONNES_FINALES))

# =============================================================================
# 3. PANNEAUX SOLAIRES (production lue dans la réponse brute PVGIS)
# =============================================================================
texte = "".join(l.value for l in spark.read.text(f"{BRONZE}/pvgis/pvgis_villes.json").collect())
pvgis = {d: rep["outputs"]["totals"]["fixed"]["E_y"] for d, rep in json.loads(texte).items()}
kwc, autoconso = H["pv_puissance_kwc"], H["pv_taux_autoconso"]
resultats.append(
    petite_table(spark, [(d, float(e)) for d, e in pvgis.items()], ["departement", "kwh_par_kwc"])
    .withColumn("gain_annuel_kwh", F.col("kwh_par_kwc") * kwc)
    .withColumn("gain_annuel_eur", F.col("gain_annuel_kwh")
                * (autoconso * prix_elec + (1 - autoconso) * H["pv_tarif_rachat"]))
    .withColumn("investissement_net_eur", F.lit(H["pv_cout"] - H["pv_aide"]))
    .withColumn("solution", F.lit(f"Panneaux solaires ({kwc:.0f} kWc)"))
    .withColumn("n_observations", F.lit(None).cast("long"))
    .withColumn("detail", F.format_string("%.0f kWh/kWc/an (PVGIS), %.0f %% autoconsommé",
                                          "kwh_par_kwc", F.lit(autoconso * 100)))
    .select(*COLONNES_FINALES))

# =============================================================================
# 4. VOITURE ÉLECTRIQUE (prix médian du carburant dans chaque département)
# =============================================================================
km = H["ve_km_an"]
budget_electrique = km * H["ve_conso_kwh_100km"] / 100 * prix_elec
litres_100km = F.when(F.col("carburant") == "e10", H["thermique_conso_essence_l_100km"]) \
                .otherwise(H["thermique_conso_diesel_l_100km"])
resultats.append(
    carbu.groupBy("departement", "carburant").agg(F.median("prix").alias("prix_litre"),
                                                  F.count("*").alias("n_observations"))
    .withColumn("gain_annuel_eur", km * litres_100km / 100 * F.col("prix_litre") - budget_electrique)
    .withColumn("gain_annuel_kwh", F.lit(None).cast("double"))
    .withColumn("investissement_net_eur", F.lit(H["ve_surcout_achat"] - H["ve_aide"]))
    .withColumn("solution", F.when(F.col("carburant") == "e10", "Voiture électrique (vs essence)")
                .otherwise("Voiture électrique (vs diesel)"))
    .withColumn("detail", F.format_string("carburant à %.3f €/L (%d stations), %.0f km/an",
                                          "prix_litre", "n_observations", F.lit(km)))
    .select(*COLONNES_FINALES))

# =============================================================================
# 5. TABLEAU FINAL + CLASSEMENT DANS CHAQUE DÉPARTEMENT
# =============================================================================
tout = resultats[0]
for r in resultats[1:]:
    tout = tout.unionByName(r)

infos = petite_table(spark, [(d, i["nom"], i["zone"]) for d, i in DEPARTEMENTS.items()],
                     ["departement", "nom_departement", "zone"])
rentable = F.col("gain_annuel_eur") > 0
classement = Window.partitionBy("departement").orderBy(
    F.when(rentable, F.col("investissement_net_eur") / F.col("gain_annuel_eur")).otherwise(F.lit(1e9)))

final = (tout.join(infos, "departement")
         .withColumn("retour_annees", F.when(rentable, F.col("investissement_net_eur") / F.col("gain_annuel_eur")))
         .withColumn("rang", F.row_number().over(classement))
         .select("zone", "departement", "nom_departement", "rang", "solution",
                 F.round("investissement_net_eur", 0).alias("investissement_net_eur"),
                 F.round("gain_annuel_kwh", 0).alias("gain_annuel_kwh"),
                 F.round("gain_annuel_eur", 0).alias("gain_annuel_eur"),
                 F.round("retour_annees", 1).alias("retour_annees"),
                 "n_observations", "detail")
         .orderBy("zone", "departement", "rang"))

ecrire(final, "gold", "rentabilite", csv=True)

# =============================================================================
# 6. MOYENNE PAR SOUS-ZONE CLIMATIQUE ET PAR DOMAINE, AVEC UN INDICE DE FROID
# Sous-zones officielles : Paris H1a, Bas-Rhin H1b, Ille-et-Vilaine H2a, Bouches-du-Rhône H3
# (une par département étudié).
# Indice de froid, calculé avec les températures mensuelles PVGIS 2005-2023 :
#   - température moyenne de l'année
#   - degrés-jours de chauffage (DJU) : chaque jour où il fait moins de 18 °C,
#     on compte l'écart (18 - température). Plus il y en a, plus on chauffe.
#     Ici calculé avec la moyenne de chaque mois (approximation).
# =============================================================================
texte = "".join(l.value for l in spark.read.text(f"{BRONZE}/pvgis/temperatures_villes.json").collect())
lignes_temp = []
for d, rep in json.loads(texte).items():
    mois = rep["outputs"]["monthly"]                  # 19 ans × 12 mois
    nb_annees = len({m["year"] for m in mois})
    dju = sum(max(0.0, 18 - m["T2m"]) * calendar.monthrange(m["year"], m["month"])[1] for m in mois) / nb_annees
    # indice de soleil = kWh produits en un an par 1 kWc de panneaux (PVGIS, partie 3)
    lignes_temp.append((d, sum(m["T2m"] for m in mois) / len(mois), dju, float(pvgis[d])))
temperatures = petite_table(spark, lignes_temp, ["departement", "temperature_moyenne", "dju", "soleil_kwh_kwc"])

# domaine = famille de solutions (on regroupe les 3 PAC, les 2 isolations, les 2 voitures)
s = F.col("solution")
domaine = (F.when(s.startswith("Isolation"), "Isolation")
            .when(s.startswith("Pompe"), "Chauffage (pompe à chaleur)")
            .when(s.startswith("Panneaux"), "Panneaux solaires")
            .otherwise("Voiture électrique"))
sous_zones = petite_table(spark, [(d, i["sous_zone"]) for d, i in DEPARTEMENTS.items()],
                          ["departement", "sous_zone"])
indice = (temperatures.join(sous_zones, "departement")
          .select("departement", "sous_zone",
                  F.round("temperature_moyenne", 1).alias("temperature_moyenne"),
                  F.round("dju", 0).alias("dju"),
                  F.round("soleil_kwh_kwc", 0).alias("soleil_kwh_kwc")))
par_zone = (final.withColumn("domaine", domaine)
            .groupBy("zone", "departement", "nom_departement", "domaine")
            .agg(F.round(F.avg("retour_annees"), 1).alias("retour_moyen_annees"),
                 F.count("*").alias("nb_resultats_moyennes"))
            .join(indice, "departement")
            .orderBy(F.desc("dju"), "domaine"))                    # du plus froid au plus doux
ecrire(par_zone, "gold", "rentabilite_par_zone", csv=True)

# Graphiques au lieu d'un tableau dans le terminal (voir graphique.py)
dessiner(final.toPandas(), par_zone.toPandas())
spark.stop()
