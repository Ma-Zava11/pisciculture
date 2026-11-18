
# PIPELINE DATA SCIENCE

import json
from datetime import datetime, timezone

from database import tester_connexion
from extraction import extraire_mesures
from nettoyage import nettoyer_mesures
from exploration import explorer_mesures
from preparation import preparer_machine_learning

from config import (
    DOSSIER_PROCESSED,
    DOSSIER_RAPPORTS
)


def main():
    """
    Exécuter le pipeline complet de préparation :

    1. Tester PostgreSQL.
    2. Extraire les mesures.
    3. Nettoyer les données.
    4. Explorer les données.
    5. Préparer le dataset Machine Learning.
    6. Produire un rapport de qualité.
    """

    print("=" * 55)
    print("PISCICULTURE INTELLIGENTE — DATA SCIENCE")
    print("PRÉPARATION DES DONNÉES")
    print("=" * 55)

    # Vérifier la connexion.
    tester_connexion()

    # Extraire les données.
    donnees_brutes = extraire_mesures()

    if donnees_brutes.empty:
        print(
            "[ATTENTION] Aucune mesure dans PostgreSQL."
        )
        return

    # Nettoyer les données.
    donnees_nettoyees, rapport = nettoyer_mesures(
        donnees_brutes
    )

    chemin_nettoye = (
        DOSSIER_PROCESSED / "mesures_nettoyees.csv"
    )

    donnees_nettoyees.to_csv(
        chemin_nettoye,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"[OK] Mesures nettoyées : "
        f"{len(donnees_nettoyees)}"
    )

    # Analyse exploratoire.
    explorer_mesures(
        donnees_nettoyees
    )

    # Préparation Machine Learning.
    dataset_ml = preparer_machine_learning(
        donnees_nettoyees
    )
    # Produire le rapport.
    rapport["date_execution_utc"] = (
        datetime.now(timezone.utc).isoformat()
    )

    rapport["lignes_dataset_ml"] = (
        len(dataset_ml)
    )

    rapport["nombre_bassins"] = int(
        donnees_nettoyees["bassin_id"].nunique()
    )

    rapport["sources"] = {
        str(cle): int(valeur)
        for cle, valeur in (
            donnees_nettoyees["source"]
            .value_counts(dropna=False)
            .items()
        )
    }

    chemin_rapport = (
        DOSSIER_RAPPORTS / "qualite_donnees.json"
    )

    with open(
        chemin_rapport,
        "w",
        encoding="utf-8"
    ) as fichier:
        json.dump(
            rapport,
            fichier,
            indent=4,
            ensure_ascii=False
        )

    print("\n=== RAPPORT DE QUALITÉ ===")

    print(
        json.dumps(
            rapport,
            indent=4,
            ensure_ascii=False
        )
    )

    print("\n" + "=" * 35)
    print("PIPELINE TERMINÉ")
    print("=" * 35)


if __name__ == "__main__":
    main()
