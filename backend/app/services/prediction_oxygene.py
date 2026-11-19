
# ============================================================
# JOUR 18 - SERVICE DE PREDICTION DE L'OXYGENE DISSOUS
# ============================================================

import json
import math

from datetime import timedelta, timezone
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd


# ------------------------------------------------------------
# 1. CONFIGURATION
# ------------------------------------------------------------

# Chemin : pisciculture/backend/app/services/
# parents[3] correspond au dossier pisciculture.
RACINE_PROJET = Path(__file__).resolve().parents[3]

DOSSIER_MODELES = RACINE_PROJET / "ai" / "models"

CHEMIN_MODELE = DOSSIER_MODELES / "modele_oxygene.joblib"
CHEMIN_METADATA = DOSSIER_MODELES / "metadata.json"

# Fréquence du simulateur temporel : 10 secondes.
PAS_SECONDES = 10

# La variable oxygene_retard_30 nécessite 30 mesures
# précédentes et une mesure actuelle, soit 31 mesures.
NOMBRE_MESURES = 31

FEATURES_ATTENDUES = [
    "temperature_c",
    "ph",
    "oxygene_dissous_mg_l",
    "oxygene_retard_1",
    "oxygene_retard_6",
    "oxygene_retard_30",
    "variation_o2_1min",
    "variation_o2_5min",
    "heure_sin",
    "heure_cos",
    "aeration_active",
    "bassin_id",
]


# ------------------------------------------------------------
# 2. CHARGEMENT DU MODELE
# ------------------------------------------------------------

@lru_cache(maxsize=1)
def charger_modele():
    """
    Charger le modèle entraîné au Jour 17.

    Le fichier joblib contient un dictionnaire :
    - approche
    - pipeline
    - features
    - horizon_minutes
    - source_entrainement
    - statut
    - seuil_alerte_experimental

    Le cache évite de relire le modèle à chaque requête.
    """

    if not CHEMIN_MODELE.is_file():
        raise FileNotFoundError(
            f"Modele introuvable : {CHEMIN_MODELE}"
        )

    if not CHEMIN_METADATA.is_file():
        raise FileNotFoundError(
            f"Metadonnees introuvables : {CHEMIN_METADATA}"
        )

    # Charger uniquement un modèle créé localement
    # et provenant d'une source de confiance.
    contenu = joblib.load(CHEMIN_MODELE)

    with CHEMIN_METADATA.open(
        "r", encoding="utf-8"
    ) as fichier:
        metadata = json.load(fichier)

    if not isinstance(contenu, dict):
        raise ValueError(
            "Le fichier joblib doit contenir un dictionnaire."
        )

    pipeline = contenu.get("pipeline")
    features = contenu.get("features")

    if pipeline is None or not callable(
        getattr(pipeline, "predict", None)
    ):
        raise ValueError(
            "Pipeline de prediction introuvable."
        )

    if features != FEATURES_ATTENDUES:
        raise ValueError(
            "Les variables du modele sont incompatibles."
        )

    if metadata.get("features") != features:
        raise ValueError(
            "Incoherence entre le modele et metadata.json."
        )

    if contenu.get("horizon_minutes") != 10:
        raise ValueError(
            "Le modele doit predire a +10 minutes."
        )

    return contenu, metadata


# ------------------------------------------------------------
# 3. VALIDATION DE L'HISTORIQUE
# ------------------------------------------------------------

def valider_historique(mesures):
    """
    Vérifier la cohérence temporelle des 31 mesures.

    Conditions :
    - 31 mesures au minimum ;
    - dates avec fuseau horaire ;
    - ordre chronologique ;
    - espacement proche de 10 secondes ;
    - température, pH et oxygène présents ;
    - valeurs numériques finies.
    """

    if len(mesures) < NOMBRE_MESURES:
        raise ValueError(
            "Historique insuffisant : "
            "31 mesures sont necessaires."
        )

    # Vérifier les dates avant de les trier.
    for mesure in mesures:
        date = mesure.measure_at

        if (
            date is None
            or date.tzinfo is None
            or date.utcoffset() is None
        ):
            raise ValueError(
                "Chaque mesure doit avoir une date "
                "avec fuseau horaire."
            )

    # Trier selon la date réelle, en UTC.
    mesures = sorted(
        mesures,
        key=lambda m: m.measure_at.astimezone(timezone.utc)
    )[-NOMBRE_MESURES:]

    # Vérifier la fréquence des mesures.
    for precedent, courant in zip(
        mesures, mesures[1:]
    ):
        ecart = (
            courant.measure_at.astimezone(timezone.utc)
            - precedent.measure_at.astimezone(timezone.utc)
        ).total_seconds()

        # Tolérance de 2 secondes.
        if not 8 <= ecart <= 12:
            raise ValueError(
                "Historique temporel irregulier : "
                "les mesures doivent etre espacees "
                "d'environ 10 secondes."
            )

    # Vérifier les valeurs.
    for mesure in mesures:
        for champ in (
            "temperature_c",
            "ph",
            "oxygene_dissous_mg_l"
        ):
            valeur = getattr(mesure, champ, None)

            if valeur is None:
                raise ValueError(
                    f"Valeur manquante : {champ}"
                )

            try:
                nombre = float(valeur)
            except (TypeError, ValueError, OverflowError):
                raise ValueError(
                    f"Valeur non numerique : {champ}"
                )

            if not math.isfinite(nombre):
                raise ValueError(
                    f"Valeur non finie : {champ}"
                )

    return mesures


# ------------------------------------------------------------
# 4. CONSTRUCTION DES VARIABLES
# ------------------------------------------------------------

def construire_variables(
    mesures,
    bassin_id,
    aeration_active
):
    """
    Construire les 12 variables attendues par Extra Trees.

    Retards :
    - 1 pas  = 10 secondes ;
    - 6 pas  = 1 minute ;
    - 30 pas = 5 minutes.

    Les variations sont calculées par rapport
    à la mesure actuelle.
    """

    mesures = valider_historique(mesures)

    actuel = mesures[-1]
    retard_1 = mesures[-2]
    retard_6 = mesures[-7]
    retard_30 = mesures[-31]

    oxygene_actuel = float(
        actuel.oxygene_dissous_mg_l
    )

    oxygene_1 = float(
        retard_1.oxygene_dissous_mg_l
    )

    oxygene_6 = float(
        retard_6.oxygene_dissous_mg_l
    )

    oxygene_30 = float(
        retard_30.oxygene_dissous_mg_l
    )

    # Normaliser la date en UTC.
    date_mesure = actuel.measure_at.astimezone(
        timezone.utc
    )

    # IMPORTANT :
    # Cette formule doit être identique à celle
    # utilisée dans ai/preparer_dataset.py.
    #
    # L'heure est calculée ici en UTC.
    heure = date_mesure.hour

    variables = {
        "temperature_c": float(
            actuel.temperature_c
        ),

        "ph": float(actuel.ph),

        "oxygene_dissous_mg_l": oxygene_actuel,

        "oxygene_retard_1": oxygene_1,

        "oxygene_retard_6": oxygene_6,

        "oxygene_retard_30": oxygene_30,

        "variation_o2_1min": (
            oxygene_actuel - oxygene_6
        ),

        "variation_o2_5min": (
            oxygene_actuel - oxygene_30
        ),

        "heure_sin": math.sin(
            2 * math.pi * heure / 24
        ),

        "heure_cos": math.cos(
            2 * math.pi * heure / 24
        ),

        "aeration_active": int(aeration_active),

        "bassin_id": int(bassin_id),
    }

    dataframe = pd.DataFrame(
        [variables],
        columns=FEATURES_ATTENDUES
    )

    return dataframe, date_mesure


# ------------------------------------------------------------
# 5. EXECUTION DE LA PREDICTION
# ------------------------------------------------------------

def predire_oxygene(
    mesures,
    bassin_id,
    aeration_active,
    source_donnees
):
    """
    Prédire l'oxygène dissous dans 10 minutes.

    Retourne une réponse JSON compatible FastAPI.

    Attention :
    le modèle a été entraîné sur des données
    synthétiques et n'est pas validé sur capteurs réels.
    """

    contenu, metadata = charger_modele()

    variables, date_mesure = construire_variables(
        mesures=mesures,
        bassin_id=bassin_id,
        aeration_active=aeration_active
    )

    pipeline = contenu["pipeline"]

    resultat = pipeline.predict(variables)

    prediction = float(resultat[0])

    if not math.isfinite(prediction):
        raise ValueError(
            "La prediction produite est invalide."
        )

    seuil = float(
        contenu["seuil_alerte_experimental"]
    )

    oxygene_actuel = float(
        variables.iloc[0]["oxygene_dissous_mg_l"]
    )

    date_prediction = date_mesure + timedelta(
        minutes=10
    )

    # L'alerte est uniquement indicative.
    alerte = prediction < seuil

    return {
        "bassin_id": int(bassin_id),

        "date_derniere_mesure": (
            date_mesure.isoformat()
        ),

        "date_prediction": (
            date_prediction.isoformat()
        ),

        "horizon_minutes": 10,

        "oxygene_actuel_mg_l": round(
            oxygene_actuel, 3
        ),

        "oxygene_predit_mg_l": round(
            prediction, 3
        ),

        "variation_predite_mg_l": round(
            prediction - oxygene_actuel, 3
        ),

        "aeration_active": bool(
            aeration_active
        ),

        "alerte_experimentale": alerte,

        "seuil_alerte_experimental_mg_l": seuil,

        "modele": contenu["approche"],

        "source_donnees": source_donnees,

        "source_entrainement": contenu[
            "source_entrainement"
        ],

        "statut": metadata["statut"],

        "message": (
            "Prediction experimentale : "
            "modele non valide sur des capteurs reels."
        )
    }
