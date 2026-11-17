
# ============================================================
# JOUR 15 — EXTRACTION DES MESURES IoT
# Fichier : data_science/extraction.py
# ============================================================

import pandas as pd
from sqlalchemy import text

from database import engine
from config import DOSSIER_RAW


def extraire_mesures():
    """
    Extraire les mesures d'eau depuis PostgreSQL.

    Les jointures permettent de récupérer :
    - Le code et le nom du bassin.
    - L'identifiant de l'appareil.
    - Les trois valeurs des capteurs.
    - La date de mesure.
    - La source : SIMULATION ou APPAREIL.

    Aucune donnée n'est modifiée dans PostgreSQL.
    """

    requete = text("""
        SELECT
            m.id AS mesure_id,
            m.bassin_id,
            b.code AS bassin_code,
            b.nom AS bassin_nom,
            m.appareil_id,
            a.identifiant AS device_id,
            m.temperature_c,
            m.ph,
            m.oxygene_dissous_mg_l,
            m.measure_at,
            m.source
        FROM mesures_eau AS m

        INNER JOIN bassins AS b
            ON b.id = m.bassin_id

        LEFT JOIN appareils AS a
            ON a.id = m.appareil_id

        ORDER BY
            m.measure_at ASC,
            m.id ASC
    """)

    # Exécuter l'extraction dans une transaction
    # explicitement configurée en lecture seule.
    with engine.connect() as connexion:
        with connexion.begin():
            connexion.execute(
                text("SET TRANSACTION READ ONLY")
            )

            donnees = pd.read_sql_query(
                requete,
                connexion
            )

    # Convertir les Decimal SQL en nombres flottants.
    colonnes_numeriques = [
        "temperature_c",
        "ph",
        "oxygene_dissous_mg_l"
    ]

    for colonne in colonnes_numeriques:
        donnees[colonne] = pd.to_numeric(
            donnees[colonne],
            errors="coerce"
        )

    # Normaliser les dates en UTC.
    donnees["measure_at"] = pd.to_datetime(
        donnees["measure_at"],
        utc=True,
        errors="coerce"
    )

    # Sauvegarder une copie brute de l'extraction.
    chemin = DOSSIER_RAW / "mesures_brutes.csv"

    donnees.to_csv(
        chemin,
        index=False,
        encoding="utf-8-sig"
    )

    print("[OK] Extraction PostgreSQL terminée")
    print(f"Nombre de mesures : {len(donnees)}")
    print(f"Fichier : {chemin}")

    return donnees


if __name__ == "__main__":
    extraire_mesures()
