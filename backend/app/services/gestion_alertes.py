
"""
============================================================
GESTION DES ALERTES — PISCICULTURE INTELLIGENTE
============================================================

JOUR 9 : INTÉGRATION DES SEUILS DYNAMIQUES

Fonctionnalités :
- Lire les seuils configurés dans PostgreSQL.
- Détecter les anomalies de qualité de l'eau.
- Créer automatiquement les alertes.
- Actualiser les alertes persistantes.
- Réactiver une alerte acquittée si elle devient critique.
- Résoudre les alertes lorsque les valeurs redeviennent
  normales.
- Ignorer les paramètres absents ou non surveillés.

IMPORTANT :
Ce service ne réalise aucun commit.
La transaction est gérée par la route POST /api/v1/mesures.
============================================================
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

# Modèles SQLAlchemy.
from app.models.models import (
    Alerte,
    MesureEau
)

# Nouveau moteur de détection dynamique du Jour 9.
from app.services.detection_dynamique import (
    analyser_mesure_dynamique
)

# Service qui récupère les seuils effectifs du bassin.
from app.services.service_seuils import (
    obtenir_seuils_bassin
)


# ============================================================
# 1. PARAMÈTRES DE QUALITÉ DE L'EAU
# ============================================================

PARAMETRES = (
    "temperature_c",
    "ph",
    "oxygene_dissous_mg_l"
)


# ============================================================
# 2. FONCTION PRINCIPALE DE GESTION DES ALERTES
# ============================================================

def traiter_alertes_mesure(
    db: Session,
    mesure: MesureEau
):
    """
    Analyser une mesure et mettre à jour les alertes.

    Paramètres :
        db :
            Session SQLAlchemy active.

        mesure :
            MesureEau enregistrée dans la session.
            Son identifiant doit déjà être disponible,
            généralement après db.flush().

    Fonctionnement :

    1. Récupérer les seuils actifs du bassin.
    2. Détecter les anomalies avec ces seuils.
    3. Rechercher les alertes existantes.
    4. Créer ou mettre à jour les anomalies.
    5. Résoudre les alertes revenues à la normale.

    Aucun commit n'est effectué ici.
    """

    # --------------------------------------------------------
    # ÉTAPE 1 : VÉRIFIER LA MESURE
    # --------------------------------------------------------

    if mesure.id is None:
        raise ValueError(
            "La mesure doit posséder un identifiant. "
            "Exécuter db.flush() avant le traitement "
            "des alertes."
        )

    # --------------------------------------------------------
    # ÉTAPE 2 : RÉCUPÉRER LES SEUILS DU BASSIN
    # --------------------------------------------------------

    # Cette fonction applique la priorité :
    # seuil spécifique au bassin > seuil global.
    seuils = obtenir_seuils_bassin(
        db=db,
        bassin_id=mesure.bassin_id
    )

    # Construire un dictionnaire des paramètres
    # effectivement surveillés.
    #
    # Exemple :
    # {
    #     "temperature_c": seuil_temperature,
    #     "ph": seuil_ph
    # }
    #
    # Un paramètre absent de ce dictionnaire
    # n'est pas surveillé.
    seuils_par_parametre = {
        seuil.parametre: seuil
        for seuil in seuils
        if seuil.actif
        and seuil.parametre in PARAMETRES
    }

    # Si aucun seuil n'est actif pour ce bassin,
    # aucune anomalie ne peut être évaluée.
    #
    # On ne résout pas les anciennes alertes,
    # car l'absence de seuil ne signifie pas
    # que l'eau est revenue à la normale.
    if not seuils_par_parametre:
        return

    # --------------------------------------------------------
    # ÉTAPE 3 : PRÉPARER LES VALEURS MESURÉES
    # --------------------------------------------------------

    # Convertir les valeurs Decimal provenant
    # de SQLAlchemy en nombres Python.
    donnees = {}

    for parametre in PARAMETRES:

        valeur_brute = getattr(
            mesure,
            parametre,
            None
        )

        if valeur_brute is None:
            donnees[parametre] = None
        else:
            donnees[parametre] = float(
                valeur_brute
            )

    # --------------------------------------------------------
    # ÉTAPE 4 : ANALYSER LA MESURE AVEC POSTGRESQL
    # --------------------------------------------------------

    # Le moteur dynamique retourne une liste
    # de dictionnaires.
    #
    # Exemple :
    # [
    #     {
    #         "parametre": "temperature_c",
    #         "valeur": 35.0,
    #         "niveau": "CRITIQUE",
    #         "message": "...",
    #         "unite": "°C"
    #     }
    # ]
    anomalies = analyser_mesure_dynamique(
        db=db,
        mesure=mesure
    )

    # Organiser les anomalies par paramètre
    # pour accélérer leur recherche.
    anomalies_par_parametre = {
        anomalie["parametre"]: anomalie
        for anomalie in anomalies
    }

    # --------------------------------------------------------
    # ÉTAPE 5 : DATE DU TRAITEMENT
    # --------------------------------------------------------

    maintenant = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # ÉTAPE 6 : PARCOURIR LES PARAMÈTRES SURVEILLÉS
    # --------------------------------------------------------

    for parametre in PARAMETRES:

        # Ne traiter que les paramètres pour lesquels
        # une configuration active existe.
        if parametre not in seuils_par_parametre:
            continue

        # Récupérer la valeur de la mesure.
        valeur = donnees[parametre]

        # Si le capteur n'a pas fourni de valeur,
        # ne rien modifier pour ce paramètre.
        if valeur is None:
            continue

        # Récupérer l'anomalie éventuelle.
        anomalie = anomalies_par_parametre.get(
            parametre
        )

        # ----------------------------------------------------
        # ÉTAPE 7 : RECHERCHER LES ALERTES EXISTANTES
        # ----------------------------------------------------

        # Chercher les alertes non résolues
        # correspondant au bassin et au paramètre.
        #
        # with_for_update() verrouille les lignes
        # pendant la transaction PostgreSQL.
        requete = (
            select(Alerte)
            .where(
                Alerte.bassin_id == mesure.bassin_id,
                Alerte.parametre == parametre,
                Alerte.statut.in_(
                    ["ACTIVE", "ACQUITTEE"]
                )
            )
            .order_by(
                Alerte.id.desc()
            )
            .with_for_update()
        )

        alertes_existantes = list(
            db.scalars(requete).all()
        )

        # ====================================================
        # CAS 1 : UNE ANOMALIE EST DÉTECTÉE
        # ====================================================

        if anomalie is not None:

            niveau = anomalie["niveau"]
            message = anomalie["message"]

            # ------------------------------------------------
            # CAS 1.A : UNE ALERTE EXISTE DÉJÀ
            # ------------------------------------------------

            if alertes_existantes:

                # Utiliser l'alerte la plus récente.
                alerte = alertes_existantes[0]

                # Mémoriser l'ancien niveau pour détecter
                # une aggravation.
                ancien_niveau = alerte.niveau

                # Actualiser la valeur de la mesure.
                alerte.valeur = Decimal(
                    str(valeur)
                )

                # Actualiser le niveau et le message.
                alerte.niveau = niveau
                alerte.message = message

                # Relier l'alerte à la dernière mesure
                # ayant confirmé l'anomalie.
                alerte.mesure_id = mesure.id

                # Incrémenter le nombre d'occurrences.
                alerte.occurrences = (
                    (alerte.occurrences or 0) + 1
                )

                # Enregistrer la date de dernière détection.
                alerte.last_seen_at = maintenant

                # Si l'alerte était acquittée et que
                # son niveau s'aggrave jusqu'à CRITIQUE,
                # la rendre de nouveau ACTIVE.
                #
                # Une alerte déjà critique et acquittée
                # reste acquittée tant que son niveau
                # ne change pas.
                if (
                    alerte.statut == "ACQUITTEE"
                    and ancien_niveau != "CRITIQUE"
                    and niveau == "CRITIQUE"
                ):
                    alerte.statut = "ACTIVE"

                    # Annuler l'ancien acquittement.
                    alerte.acknowledged_at = None

                # Si plusieurs alertes ouvertes existent
                # pour le même paramètre, conserver
                # uniquement la plus récente.
                for doublon in alertes_existantes[1:]:
                    doublon.statut = "RESOLUE"
                    doublon.resolved_at = maintenant

            # ------------------------------------------------
            # CAS 1.B : AUCUNE ALERTE EXISTANTE
            # ------------------------------------------------

            else:

                # Créer une nouvelle alerte.
                nouvelle_alerte = Alerte(
                    bassin_id=mesure.bassin_id,
                    mesure_id=mesure.id,

                    parametre=parametre,

                    valeur=Decimal(
                        str(valeur)
                    ),

                    niveau=niveau,
                    message=message,

                    statut="ACTIVE",

                    occurrences=1,

                    created_at=maintenant,
                    last_seen_at=maintenant,

                    acknowledged_at=None,
                    resolved_at=None
                )

                # Ajouter l'alerte à la transaction.
                db.add(nouvelle_alerte)

        # ====================================================
        # CAS 2 : LE PARAMÈTRE EST NORMAL
        # ====================================================

        else:

            # Une mesure normale signifie que le paramètre
            # est revenu dans sa plage normale,
            # selon les seuils actuellement configurés.
            #
            # Résoudre toutes les alertes ouvertes
            # pour ce paramètre.
            for alerte in alertes_existantes:

                alerte.statut = "RESOLUE"

                # Date de résolution.
                alerte.resolved_at = maintenant

    # ========================================================
    # FIN DU TRAITEMENT
    # ========================================================

    # Toutes les modifications sont conservées
    # dans la session SQLAlchemy.
    #
    # Aucun db.commit() ici.
    #
    # La route POST /api/v1/mesures effectue le commit
    # pour enregistrer atomiquement :
    #
    # - la mesure ;
    # - les nouvelles alertes ;
    # - les mises à jour ;
    # - les résolutions.
