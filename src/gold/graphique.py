"""
GOLD - Graphiques des résultats

Trois images, enregistrées dans data/gold/ et ouvertes automatiquement sur ton PC :

  graphique_rentabilite.png : BARRES. Un graphique par département, une barre par solution
                              = nombre d'années pour rembourser l'investissement.

  graphique_bilan.png       : BILAN NET. Un graphique par département, une courbe par solution.
                              Chaque courbe part de -investissement (l'argent dépensé au départ),
                              remonte chaque année avec les économies, et passe au-dessus de 0
                              l'année où l'investissement est remboursé.
                              Hauteur à 25 ans = bénéfice final.

  graphique_bilan_5ans.png  : TABLEAU COLORÉ. Le bilan net de chaque solution tous les 5 ans
                              (rouge = encore en perte, vert = bénéfice).

Appelé automatiquement à la fin de rentabilite.py.
On peut aussi le relancer seul (sans Spark, il relit data/gold/rentabilite.csv) :
    .venv\\Scripts\\python src\\gold\\graphique.py
"""
import os
import platform
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")            # dessine dans un fichier, sans ouvrir de fenêtre (marche aussi sur Onyxia)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402
import pandas as pd              # noqa: E402

sys.path.append(str(Path(__file__).resolve().parents[1]))
from commun import DEPARTEMENTS, RACINE  # noqa: E402

DOSSIER = RACINE / "data" / "gold"
DUREE_ANS = 25                   # durée de vie typique d'une installation (isolation, panneaux)

# Une couleur par solution (courbes du bilan net)
COULEURS = {
    "Isolation de la toiture":          "#2a9d8f",   # verts = isolation
    "Isolation des murs":               "#8ac926",
    "Pompe à chaleur (remplace fioul)": "#e63946",   # rouges = pompe à chaleur
    "Pompe à chaleur (remplace gaz)":   "#f4a261",
    "Voiture électrique (vs essence)":  "#1d3557",   # bleus = voiture
    "Voiture électrique (vs diesel)":   "#6c9bd2",
    "Panneaux solaires (3 kWc)":        "#e9c46a",   # jaune = solaire
}


def _enregistrer(fig, nom: str) -> Path:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    chemin = DOSSIER / nom
    try:
        fig.savefig(chemin, dpi=120)
    except OSError:
        # Windows bloque l'écriture tant que l'image est ouverte dans l'application Photos
        sys.exit(f"Impossible d'écrire {chemin.name} : ferme la fenêtre Photos qui l'affiche, puis relance.")
    plt.close(fig)
    print(f"   -> graphique : {chemin.relative_to(RACINE)}")
    return chemin


# =============================================================================
# 1. BARRES : années de retour, un graphique par département
# =============================================================================
# une couleur par FAMILLE de solution (isolation, pompe à chaleur, voiture, solaire)
COULEURS_FAMILLE = {"Isolation": "#2a9d8f", "Pompe": "#e76f51", "Voiture": "#457b9d", "Panneaux": "#e9c46a"}


def barres(resultats: pd.DataFrame) -> Path:
    def couleur(solution):
        # "Isolation des murs" -> famille "Isolation" -> vert
        return next((c for debut, c in COULEURS_FAMILLE.items() if solution.startswith(debut)), "grey")

    fig, axes = plt.subplots(2, 2, figsize=(15, 9), sharex=True)
    maximum = resultats["retour_annees"].max()
    for ax, (dept, infos) in zip(axes.flat, DEPARTEMENTS.items()):
        # les solutions du département, la plus rentable en haut
        d = resultats[resultats["departement"] == dept].sort_values("retour_annees", ascending=False)
        b = ax.barh(d["solution"], d["retour_annees"], color=[couleur(s) for s in d["solution"]])
        # le nombre d'années écrit au bout de chaque barre
        ax.bar_label(b, labels=[f"{a:.1f} ans" for a in d["retour_annees"]], padding=4, fontsize=9)
        ax.set_title(f"{infos['nom']} ({dept}) - zone {infos['zone']}", fontweight="bold")
        ax.set_xlim(0, maximum * 1.15)                    # de la place pour les étiquettes
        ax.grid(axis="x", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axes[1]:
        ax.set_xlabel("Années pour rembourser l'investissement (moins = mieux)")
    fig.suptitle("Rentabilité de la transition énergétique d'une maison, par zone climatique",
                 fontsize=15, fontweight="bold")
    fig.tight_layout()
    return _enregistrer(fig, "graphique_rentabilite.png")


# =============================================================================
# 2. BILAN NET : argent gagné moins argent dépensé, année après année
#    bilan(t) = gain annuel × t - investissement     (prix de l'énergie fixes)
#    bilan < 0 : pas encore remboursé   |   bilan = 0 : remboursé   |   bilan > 0 : bénéfice
# =============================================================================
def bilan(resultats: pd.DataFrame) -> Path:
    t = np.linspace(0, DUREE_ANS, 200)                    # le temps, en années
    fig, axes = plt.subplots(2, 2, figsize=(19, 11), sharey=True)

    # limites verticales communes aux 4 cases : du pire départ au meilleur bilan final
    bas = -resultats["investissement_net_eur"].max() / 1000 * 1.1
    haut = (resultats["gain_annuel_eur"] * DUREE_ANS - resultats["investissement_net_eur"]).max() / 1000 * 1.05
    ecart_min = (haut - bas) * 0.045                      # espace minimum entre deux étiquettes

    for ax, (dept, infos) in zip(axes.flat, DEPARTEMENTS.items()):
        d = resultats[resultats["departement"] == dept].sort_values("retour_annees")
        etiquettes = []                                   # (hauteur, texte, couleur) au bout des courbes
        for _, r in d.iterrows():
            G, I = r["gain_annuel_eur"], r["investissement_net_eur"]
            c = COULEURS.get(r["solution"], "grey")
            ax.plot(t, (G * t - I) / 1000, color=c, lw=2.2, label=r["solution"])
            # un point à l'année où la courbe passe au-dessus de 0 (= remboursé)
            if G > 0 and I / G <= DUREE_ANS:
                ax.plot(I / G, 0, "o", color=c, ms=7, mec="white", zorder=3)
                quand = f"remboursé en {I / G:.1f} ans".replace(".", ",")
            else:
                quand = "pas remboursé"
            final = (G * DUREE_ANS - I) / 1000            # bilan au bout de 25 ans, en k€
            montant = f"{final:+.1f}" if abs(final) < 10 else f"{final:+.0f}"   # +0,3 plutôt que +0
            etiquettes.append((final, f"{montant.replace('.', ',')} k€  ({quand})", c))

        # Étiquettes au bout des courbes, décalées vers le haut si elles se chevauchent
        etiquettes.sort()
        precedente = -1e9
        for final, texte, c in etiquettes:
            y = max(final, precedente + ecart_min)
            precedente = y
            ax.annotate(texte, xy=(DUREE_ANS, final), xytext=(DUREE_ANS + 0.4, y),
                        color=c, fontsize=9, fontweight="bold", va="center", annotation_clip=False,
                        arrowprops=dict(arrowstyle="-", color=c, lw=0.6))

        # fond rouge sous 0 (on perd encore de l'argent), vert au-dessus (on en gagne)
        ax.axhspan(-1000, 0, color="#e63946", alpha=0.06)
        ax.axhspan(0, 1000, color="#2a9d8f", alpha=0.06)
        ax.axhline(0, color="black", lw=1)
        ax.set_title(f"{infos['nom']} ({dept}) - zone {infos['zone']}", fontweight="bold")
        ax.set_xlim(0, DUREE_ANS)
        ax.grid(alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("Années après les travaux / l'achat")
        ax.set_ylabel("Bilan net (k€)")
        # même échelle pour les 4 cases, mais les montants (k€) affichés sur chacune,
        # y compris celles de droite (Paris, Bouches-du-Rhône) que matplotlib masque sinon
        ax.tick_params(labelleft=True)

    axes[0, 0].set_ylim(bas, haut)                        # (le fond coloré ne doit pas les agrandir)

    # une seule légende pour les 4 cases, sous les graphiques
    poignees, noms = axes[0, 0].get_legend_handles_labels()
    fig.legend(poignees, noms, loc="lower center", ncol=4, fontsize=11, frameon=False)
    fig.suptitle(f"Bilan net sur {DUREE_ANS} ans : remboursé quand la courbe passe au-dessus de 0 (point), "
                 f"gain final écrit au bout", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0.07, 1, 1))               # laisse la place à la légende en bas
    fig.subplots_adjust(wspace=0.55)                      # de la place à droite de chaque case pour les étiquettes
    return _enregistrer(fig, "graphique_bilan.png")


# =============================================================================
# 3. TABLEAU COLORÉ : bilan net tous les 5 ans
#    Une ligne par solution, une colonne tous les 5 ans. Rouge = encore en perte,
#    vert = bénéfice (plus c'est foncé, plus on gagne). On lit d'un coup d'œil
#    quand ça devient rentable et combien on a gagné à chaque étape.
# =============================================================================
def tableau_bilan(resultats: pd.DataFrame) -> Path:
    from matplotlib.colors import TwoSlopeNorm
    annees = [0, 5, 10, 15, 20, 25]
    fig, axes = plt.subplots(2, 2, figsize=(20, 12))

    # même échelle de couleurs pour les 4 départements (0 = blanc)
    plus_haut = (resultats["gain_annuel_eur"] * DUREE_ANS - resultats["investissement_net_eur"]).max() / 1000
    plus_bas = -resultats["investissement_net_eur"].max() / 1000
    couleurs = TwoSlopeNorm(vmin=plus_bas, vcenter=0, vmax=plus_haut)

    for ax, (dept, infos) in zip(axes.flat, DEPARTEMENTS.items()):
        d = resultats[resultats["departement"] == dept].sort_values("retour_annees")
        # bilan net (k€) de chaque solution après 0, 5, 10... ans
        bilans = np.array([[(r["gain_annuel_eur"] * a - r["investissement_net_eur"]) / 1000 for a in annees]
                           for _, r in d.iterrows()])
        ax.imshow(bilans, cmap="RdYlGn", norm=couleurs, aspect="auto")

        # le montant écrit dans chaque case
        for i in range(bilans.shape[0]):
            for j in range(bilans.shape[1]):
                v = bilans[i, j]
                montant = (f"{v:+.1f}" if abs(v) < 1 else f"{v:+.0f}").replace(".", ",")   # +0,3 plutôt que +0
                ax.text(j, i, f"{montant} k€", ha="center", va="center", fontsize=10,
                        fontweight="bold", color="white" if abs(bilans[i, j]) > plus_haut * 0.6 else "black")

        # à gauche : la solution et l'année où elle devient rentable
        noms = []
        for _, r in d.iterrows():
            retour = f"rentable après {r['retour_annees']:.1f} ans".replace(".", ",") \
                if r["retour_annees"] <= DUREE_ANS else "jamais rentable en 25 ans"
            noms.append(f"{r['solution']}\n{retour}")
        ax.set_yticks(range(len(noms)), noms, fontsize=9)
        ax.set_xticks(range(len(annees)), ["Départ\n(on paie)"] + [f"après\n{a} ans" for a in annees[1:]])
        ax.xaxis.tick_top()
        ax.tick_params(length=0)
        ax.set_title(f"{infos['nom']} ({dept}) - zone {infos['zone']}", fontweight="bold", pad=38)
        # fines lignes blanches entre les cases
        ax.set_xticks(np.arange(-0.5, len(annees)), minor=True)
        ax.set_yticks(np.arange(-0.5, len(noms)), minor=True)
        ax.grid(which="minor", color="white", lw=2)
        ax.tick_params(which="minor", length=0)
        ax.spines[:].set_visible(False)

    fig.suptitle("Argent gagné (ou encore perdu) tous les 5 ans, travaux et achat compris\n"
                 "rouge = pas encore remboursé    vert = bénéfice", fontsize=15, fontweight="bold")
    fig.tight_layout()
    return _enregistrer(fig, "graphique_bilan_5ans.png")


# =============================================================================
def dessiner(resultats: pd.DataFrame, ouvrir: bool = True) -> None:
    """resultats = le tableau final (une ligne par solution et par département)."""
    resultats = resultats.copy()
    resultats["departement"] = resultats["departement"].astype(str)
    images = [barres(resultats), bilan(resultats), tableau_bilan(resultats)]
    # Ouvre les images avec la visionneuse de Windows (seulement sur ton PC)
    if ouvrir and platform.system() == "Windows":
        for image in images:
            os.startfile(image)


if __name__ == "__main__":
    # Lancé seul : relit le CSV écrit par rentabilite.py
    dessiner(pd.read_csv(DOSSIER / "rentabilite.csv", dtype={"departement": str}))
