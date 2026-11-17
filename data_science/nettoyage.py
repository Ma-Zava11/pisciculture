
# ============================================================
# JOUR 15 — EXPLORATION DES DONNÉES
# Fichier : data_science/exploration.py
# ============================================================

import matplotlib

# Utiliser un moteur non interactif pour générer
# les graphiques PNG sans ouvrir de fenêtre.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from config import (
    COLONNES_CAPTEURS,
    DOSSIER_RAPPORTS
)


PARAMETRES = {
    "temperature_c": (
        "Température de l'eau",
        "Température (°C)"
    ),
    "ph": (
        "Évolution du pH",
        "pH"
    ),
    "oxygene_dissous_mg_l": (
        "Oxygène dissous",
        "Oxygène (mg/L)"
    )
}


def explorer_mesures(df):
    """
    Produire des statistiques descriptives et
    des graphiques pour chaque bassin.

    Les données de différents bassins ne sont
    pas mélangées dans une seule courbe.
    """

    if df.empty:
        print(
            "[ATTENTION] Aucune donnée à explorer."
        )
        return

    # --------------------------------------------------------
    # 1. Statistiques descriptives par bassin.
    # --------------------------------------------------------

    statistiques = df.groupby(
        "bassin_code"
    )[COLONNES_CAPTEURS].agg(
        ["count", "mean", "min", "max", "std"]
    )

    chemin_stats = (
        DOSSIER_RAPPORTS / "statistiques_bassins.csv"
    )

    statistiques.to_csv(
        chemin_stats,
        encoding="utf-8-sig"
    )

    print("\n=== STATISTIQUES DES BASSINS ===")
    print(statistiques.round(2))

    # --------------------------------------------------------
    # 2. Répartition des sources de données.
    # --------------------------------------------------------

    print("\n=== SOURCES DES MESURES ===")
    print(
        df["source"].value_counts(
            dropna=False
        )
    )

    # --------------------------------------------------------
    # 3. Générer les graphiques par bassin.
    # --------------------------------------------------------

    for code_bassin, groupe in df.groupby(
        "bassin_code"
    ):

        groupe = groupe.sort_values(
            "measure_at"
        )

        # Nom utilisable dans un chemin Windows.
        code_fichier = "".join(
            caractere
            if caractere.isalnum()
            or caractere in "-_"
            else "_"
            for caractere in str(code_bassin)
        )

        for colonne, (titre, unite) in PARAMETRES.items():

            fig, ax = plt.subplots(
                figsize=(12, 5)
            )

            ax.plot(
                groupe["measure_at"],
                groupe[colonne],
                linewidth=1
            )

            ax.set_title(
                f"{titre} — {code_bassin}"
            )

            ax.set_xlabel("Date UTC")
            ax.set_ylabel(unite)

            ax.grid(
                True,
                alpha=0.3
            )

            fig.autofmt_xdate()
            fig.tight_layout()

            chemin = DOSSIER_RAPPORTS / (
                f"{code_fichier}_{colonne}.png"
            )

            fig.savefig(
                chemin,
                dpi=140
            )

            plt.close(fig)

        # ----------------------------------------------------
        # 4. Disponibilité des capteurs.
        # ----------------------------------------------------

        disponibilite = (
            groupe[COLONNES_CAPTEURS]
            .notna()
            .mean()
            .mul(100)
        )

        fig, ax = plt.subplots(
            figsize=(9, 5)
        )

        ax.bar(
            disponibilite.index,
            disponibilite.values
        )

        ax.set_title(
            f"Disponibilité des capteurs — {code_bassin}"
        )

        ax.set_ylabel(
            "Mesures disponibles (%)"
        )

        ax.set_ylim(0, 100)
        ax.tick_params(
            axis="x",
            rotation=15
        )

        fig.tight_layout()

        fig.savefig(
            DOSSIER_RAPPORTS
            / f"{code_fichier}_disponibilite.png",
            dpi=140
        )

        plt.close(fig)

    print(
        "\n[OK] Graphiques enregistrés dans rapports/"
    )
