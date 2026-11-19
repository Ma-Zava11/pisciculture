
# PRÉPARATION POUR LE MACHINE LEARNING

import pandas as pd
import shutil
from pathlib import Path

from config import DOSSIER_PROCESSED

# En haut du fichier (ou dans config.py)
PROJET_DIR = Path(__file__).resolve().parent.parent
DESTINATION_ML = PROJET_DIR / "ai" / "datasets"


# Horizon de prédiction choisi pour le premier modèle.
HORIZON_MINUTES = 10

# Écart maximal toléré entre l'horizon demandé
# et la date réelle de la mesure cible.
TOLERANCE_CIBLE_MINUTES = 2


def preparer_machine_learning(df):
    """
    Construire un jeu de données supervisé.

    Objectif :
    prédire l'oxygène dissous environ 10 minutes
    après la mesure actuelle.

    Les mesures sont traitées séparément
    pour chaque couple bassin/appareil.

    La cible future est obtenue par une recherche
    chronologique, et non par un décalage fixe
    de 60 lignes.
    """

    if df.empty:
        print(
            "[ATTENTION] Aucune donnée pour le ML."
        )
        return pd.DataFrame()

    donnees = df.copy()

    # Trier les données chronologiquement.

    donnees = donnees.sort_values(
        [
            "bassin_id",
            "device_id",
            "measure_at",
            "mesure_id"
        ]
    ).reset_index(drop=True)

    # Construire les variables temporelles.

    donnees["heure"] = (
        donnees["measure_at"].dt.hour
    )

    donnees["jour_semaine"] = (
        donnees["measure_at"].dt.dayofweek
    )

    # Calculer les mesures précédentes.

    groupes = donnees.groupby(
        ["bassin_id", "device_id"],
        dropna=False
    )

    donnees["temperature_precedente"] = (
        groupes["temperature_c"].shift(1)
    )

    donnees["ph_precedent"] = (
        groupes["ph"].shift(1)
    )

    donnees["oxygene_precedent"] = (
        groupes["oxygene_dissous_mg_l"].shift(1)
    )

    # Chercher la mesure cible à environ 10 minutes.

    # Préparer les observations cibles.
    # Les mesures sans oxygène connu ne peuvent
    # pas servir de valeur cible.
    cibles = donnees[
        donnees["oxygene_dissous_mg_l"].notna()
    ][
        [
            "bassin_id",
            "device_id",
            "measure_at",
            "oxygene_dissous_mg_l"
        ]
    ].copy()

    cibles = cibles.rename(
        columns={
            "measure_at": "date_cible",
            "oxygene_dissous_mg_l": "oxygene_cible"
        }
    )

    # Chercher la première mesure disponible
    # à partir de l'horizon demandé.
    donnees["date_recherche"] = (
        donnees["measure_at"]
        + pd.Timedelta(minutes=HORIZON_MINUTES)
    )

    # merge_asof exige un tri par clé temporelle.
    donnees = donnees.sort_values(
        "date_recherche"
    ).reset_index(drop=True)

    cibles = cibles.sort_values(
        "date_cible"
    ).reset_index(drop=True)

    donnees = pd.merge_asof(
        donnees,
        cibles,
        left_on="date_recherche",
        right_on="date_cible",
        by=["bassin_id", "device_id"],
        direction="forward",
        tolerance=pd.Timedelta(
            minutes=TOLERANCE_CIBLE_MINUTES
        )
    )

    # Retirer les lignes sans cible future.

    donnees = donnees.dropna(
        subset=["oxygene_cible"]
    ).copy()

    # Sélectionner les colonnes ML.
    colonnes = [
        "mesure_id",
        "bassin_id",
        "device_id",
        "measure_at",
        "date_cible",
        "source",
        "temperature_c",
        "ph",
        "oxygene_dissous_mg_l",
        "heure",
        "jour_semaine",
        "temperature_precedente",
        "ph_precedent",
        "oxygene_precedent",
        "oxygene_cible"
    ]

    donnees = donnees[colonnes].copy()

    # Rétablir l'ordre chronologique.
    donnees = donnees.sort_values(
        ["measure_at", "mesure_id"]
    ).reset_index(drop=True)

    # Enregistrer le dataset préparé.

    chemin = (
        DOSSIER_PROCESSED / "dataset_ml.csv"
    )

    donnees.to_csv(
        chemin,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"[OK] Dataset ML : {len(donnees)} lignes"
    )

    print(f"Fichier : {chemin}")
    donnees.to_csv(
        chemin,
        index=False,
        encoding="utf-8-sig"
    )

    # Copier le dataset vers le dossier du module IA.
    DESTINATION_ML.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chemin, DESTINATION_ML / "dataset_ml.csv")

    print(f"[OK] Copie : {DESTINATION_ML / 'dataset_ml.csv'}")
    

    return donnees
