
# ============================================================
# JOUR 14 — VALIDATION DES MESURES IoT
# Fichier : app/services/validation_mesures.py
# ============================================================

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Appareils, Bassin, MesureEau


# ------------------------------------------------------------
# PARAMÈTRES DE VALIDATION
# ------------------------------------------------------------

# Tolérance maximale pour une date dans le futur.
TOLERANCE_FUTUR_MINUTES = 5

# Ancienneté maximale acceptée pour une mesure.
# 24 h permettent de récupérer des mesures après
# une interruption temporaire de connexion.
ANCIENNETE_MAX_HEURES = 24

# Tolérance utilisée pour comparer les valeurs décimales.
# Les colonnes de mesures utilisent une précision de 2 décimales.
PRECISION_MESURE = 2


def erreur_mesure(code_http: int, message: str):
    """Produire une erreur HTTP compréhensible."""
    raise HTTPException(
        status_code=code_http,
        detail=message
    )


def normaliser_date_mesure(date_mesure):
    """
    Convertir la date reçue en UTC.

    Si le simulateur ne transmet aucune date,
    utiliser l'heure actuelle du serveur.
    """

    maintenant = datetime.now(timezone.utc)

    if date_mesure is None:
        return maintenant

    if (
        date_mesure.tzinfo is None
        or date_mesure.utcoffset() is None
    ):
        erreur_mesure(
            422,
            "La date de mesure doit contenir un fuseau "
            "horaire, par exemple Z ou +03:00."
        )

    date_utc = date_mesure.astimezone(timezone.utc)

    if date_utc > maintenant + timedelta(
        minutes=TOLERANCE_FUTUR_MINUTES
    ):
        erreur_mesure(
            422,
            "La date de mesure est trop éloignée dans le futur."
        )

    if date_utc < maintenant - timedelta(
        hours=ANCIENNETE_MAX_HEURES
    ):
        erreur_mesure(
            422,
            "La mesure est trop ancienne pour être enregistrée."
        )

    return date_utc


def verifier_valeurs_mesure(donnees):
    """
    Contrôler les données transmises.

    Les limites sont des limites de validation technique,
    pas des seuils de qualité adaptés à chaque espèce.
    """

    valeurs = [
        donnees.temperature_c,
        donnees.ph,
        donnees.oxygene_dissous_mg_l
    ]

    # Au moins un capteur doit fournir une valeur.
    if all(valeur is None for valeur in valeurs):
        erreur_mesure(
            422,
            "La mesure doit contenir au moins une valeur : "
            "température, pH ou oxygène dissous."
        )

    # Contrôles supplémentaires de cohérence.
    # Les bornes de température et de pH sont déjà
    # déclarées dans MesureCreate.
    if (
        donnees.oxygene_dissous_mg_l is not None
        and donnees.oxygene_dissous_mg_l > 30
    ):
        erreur_mesure(
            422,
            "La valeur d'oxygène dissous dépasse "
            "la limite technique de 30 mg/L."
        )


def rechercher_appareil_et_bassin(
    db: Session,
    donnees
):
    """
    Retrouver l'appareil et le bassin à partir
    des identifiants texte transmis par l'ESP32.

    Exemple :
      device_id = ESP32-001
      bassin_id = BAS-001
    """

    identifiant = donnees.device_id.strip()
    code_bassin = donnees.bassin_id.strip()

    if not identifiant or not code_bassin:
        erreur_mesure(
            422,
            "L'identifiant de l'appareil et le code "
            "du bassin sont obligatoires."
        )

    appareil = db.scalar(
        select(Appareils).where(
            Appareils.identifiant == identifiant
        )
    )

    if appareil is None:
        erreur_mesure(
            404,
            f"Appareil introuvable : {identifiant}"
        )

    if appareil.statut.strip().upper() != "ACTIF":
        erreur_mesure(
            403,
            f"L'appareil {identifiant} est désactivé."
        )

    bassin = db.scalar(
        select(Bassin).where(
            Bassin.code == code_bassin
        )
    )

    if bassin is None:
        erreur_mesure(
            404,
            f"Bassin introuvable : {code_bassin}"
        )

    if appareil.bassin_id != bassin.id:
        erreur_mesure(
            409,
            "Cet appareil n'est pas affecté "
            "au bassin indiqué."
        )

    return appareil, bassin


def meme_valeur(valeur_a, valeur_b):
    """
    Comparer deux valeurs de capteur.

    None reste différent d'une valeur numérique.
    """

    if valeur_a is None or valeur_b is None:
        return valeur_a is None and valeur_b is None

    return round(float(valeur_a), PRECISION_MESURE) == (
        round(float(valeur_b), PRECISION_MESURE)
    )


def verifier_doublon_mesure(
    db: Session,
    donnees,
    appareil_id: int,
    date_mesure: datetime
):
    """
    Détecter une retransmission strictement identique.

    La vérification concerne le même appareil,
    la même date et les mêmes valeurs.

    Deux mesures différentes ayant les mêmes valeurs
    mais des dates différentes restent autorisées.
    """

    candidates = db.scalars(
        select(MesureEau).where(
            MesureEau.appareil_id == appareil_id,
            MesureEau.measure_at == date_mesure
        )
    ).all()

    for mesure in candidates:
        if (
            meme_valeur(
                mesure.temperature_c,
                donnees.temperature_c
            )
            and meme_valeur(mesure.ph, donnees.ph)
            and meme_valeur(
                mesure.oxygene_dissous_mg_l,
                donnees.oxygene_dissous_mg_l
            )
        ):
            erreur_mesure(
                409,
                "Cette mesure a déjà été enregistrée."
            )


def valider_mesure_iot(
    db: Session,
    donnees
):
    """
    Point d'entrée unique pour la validation.

    Retourne les objets nécessaires à la création
    de MesureEau dans le code existant.
    """

    # 1. Vérifier les valeurs.
    verifier_valeurs_mesure(donnees)

    # 2. Vérifier la date.
    date_mesure = normaliser_date_mesure(
        donnees.measure_at
    )

    # 3. Vérifier l'appareil et le bassin.
    appareil, bassin = rechercher_appareil_et_bassin(
        db,
        donnees
    )

    # 4. Vérifier les retransmissions identiques.
    verifier_doublon_mesure(
        db,
        donnees,
        appareil.id,
        date_mesure
    )

    return {
        "appareil": appareil,
        "bassin": bassin,
        "date_mesure": date_mesure
    }
