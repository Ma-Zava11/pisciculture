
#  NETTOYAGE DES DONNÉES

import pandas as pd

from config import COLONNES_CAPTEURS


def nettoyer_mesures(donnees):
    """
    Nettoyer une copie des données IoT.

    Cette fonction ne modifie jamais PostgreSQL.

    Retourne :
    - Un DataFrame nettoyé.
    - Un dictionnaire contenant les indicateurs
      de qualité des données.
    """

    df = donnees.copy()

    rapport = {
        "lignes_initiales": len(df),
        "dates_invalides": 0,
        "doublons_supprimes": 0,
        "valeurs_invalides": {},
        "valeurs_manquantes": {},
        "lignes_finales": 0
    }

    # Vérifier les dates.

    df["measure_at"] = pd.to_datetime(
        df["measure_at"],
        utc=True,
        errors="coerce"
    )

    rapport["dates_invalides"] = int(
        df["measure_at"].isna().sum()
    )

    # Une mesure sans date exploitable ne peut pas
    # servir correctement à l'analyse temporelle.
    df = df.dropna(subset=["measure_at"]).copy()

    # Convertir les mesures en nombres.

    for colonne in COLONNES_CAPTEURS:
        df[colonne] = pd.to_numeric(
            df[colonne],
            errors="coerce"
        )

    # Vérifier les limites techniques.

    limites = {
        "temperature_c": (-10.0, 60.0),
        "ph": (0.0, 14.0),
        "oxygene_dissous_mg_l": (0.0, 30.0)
    }

    for colonne, (minimum, maximum) in limites.items():

        invalides = (
            df[colonne].notna()
            & ~df[colonne].between(
                minimum,
                maximum
            )
        )

        rapport["valeurs_invalides"][colonne] = int(
            invalides.sum()
        )

        # Ne pas inventer une valeur de remplacement.
        # Une valeur incohérente devient manquante.
        df.loc[invalides, colonne] = float("nan")

    # Supprimer les doublons exacts.

    nombre_avant = len(df)

    # Une retransmission identique possède :
    # - Le même appareil.
    # - Le même bassin.
    # - La même date.
    # - Les mêmes valeurs.
    # - La même source.
    #
    # Deux mesures identiques à des dates différentes
    # restent donc conservées.

    colonnes_doublons = [
        "device_id",
        "bassin_id",
        "measure_at",
        "temperature_c",
        "ph",
        "oxygene_dissous_mg_l",
        "source"
    ]

    df = df.drop_duplicates(
        subset=colonnes_doublons,
        keep="first"
    ).copy()

    rapport["doublons_supprimes"] = (
        nombre_avant - len(df)
    )

    # Écarter les lignes sans aucune mesure exploitable.

    lignes_sans_capteur = df[
        COLONNES_CAPTEURS
    ].isna().all(axis=1)

    rapport["lignes_sans_capteur"] = int(
        lignes_sans_capteur.sum()
    )

    df = df.loc[~lignes_sans_capteur].copy()

    # Trier chronologiquement.

    df = df.sort_values(
        ["measure_at", "mesure_id"]
    ).reset_index(drop=True)

    # Calculer les valeurs manquantes restantes.

    rapport["valeurs_manquantes"] = {
        colonne: int(df[colonne].isna().sum())
        for colonne in COLONNES_CAPTEURS
    }

    rapport["lignes_finales"] = len(df)

    return df, rapport
