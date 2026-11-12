
"""
JOUR 9 — Analyse dynamique des mesures.

Les seuils sont lus dans PostgreSQL pour chaque mesure.
Une modification des seuils est donc prise en compte
dès la prochaine mesure reçue.

IMPORTANT :
Les niveaux retournés sont compatibles avec la gestion
des alertes du Jour 7.
"""

from app.services.service_seuils import (
    obtenir_seuils_bassin
)


def analyser_mesure_dynamique(db, mesure):
    """
    Analyser une mesure SQLAlchemy avec les seuils du bassin.

    Retourne une liste de dictionnaires d'alertes.
    Les valeurs absentes ne sont pas analysées.
    """

    seuils = obtenir_seuils_bassin(
        db,
        mesure.bassin_id
    )

    # Associer chaque paramètre à son unité.
    unites = {
        "temperature_c": "°C",
        "ph": "",
        "oxygene_dissous_mg_l": "mg/L"
    }

    alertes = []

    for seuil in seuils:
        # Récupérer la valeur correspondante
        # dans le modèle MesureEau.
        valeur_brute = getattr(
            mesure,
            seuil.parametre,
            None
        )

        if valeur_brute is None:
            continue

        valeur = float(valeur_brute)

        # Convertir les limites Numeric de PostgreSQL.
        normal_min = (
            float(seuil.normal_min)
            if seuil.normal_min is not None
            else None
        )

        normal_max = (
            float(seuil.normal_max)
            if seuil.normal_max is not None
            else None
        )

        critique_min = (
            float(seuil.critique_min)
            if seuil.critique_min is not None
            else None
        )

        critique_max = (
            float(seuil.critique_max)
            if seuil.critique_max is not None
            else None
        )

        # Les limites critiques sont inclusives.
        est_critique = (
            (
                critique_min is not None
                and valeur <= critique_min
            )
            or
            (
                critique_max is not None
                and valeur >= critique_max
            )
        )

        # Les limites normales sont inclusives.
        est_hors_normal = (
            (
                normal_min is not None
                and valeur < normal_min
            )
            or
            (
                normal_max is not None
                and valeur > normal_max
            )
        )

        if est_critique:
            niveau = "CRITIQUE"
        elif est_hors_normal:
            niveau = "AVERTISSEMENT"
        else:
            # Une valeur normale ne produit pas
            # de nouvelle alerte.
            continue

        unite = unites.get(seuil.parametre, "")

        message = (
            f"{seuil.parametre} hors seuil : "
            f"{valeur} {unite} "
            f"({niveau})."
        )

        alertes.append({
            "parametre": seuil.parametre,
            "valeur": valeur,
            "niveau": niveau,
            "message": message,
            "unite": unite
        })

    return alertes
