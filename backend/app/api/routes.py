
"""
Routes de l'API de pisciculture intelligente.

Fonctionnalités :
- Consulter les espèces de poissons.
- Consulter les bassins.
- Consulter les informations d'un bassin.
- Consulter les mesures d'eau d'un bassin.
- Enregistrer les mesures transmises par les appareils ESP32.
"""

from datetime import datetime, timezone,timedelta
from decimal import Decimal
import asyncio
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, status,WebSocket,WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.responses import StreamingResponse
from io import BytesIO, StringIO
from openpyxl import Workbook

# Dépendance permettant de récupérer une session de base de données.
from app.database.connection import get_db

# Modèles SQLAlchemy représentant les tables de la base de données.
from app.models.models import Bassin, Espece, MesureEau, Appareils

# Schémas Pydantic pour valider les entrées et formater les réponses.
from app.schemas.schemas import (
    BassinReponse,
    EspeceReponse,
    MesureCreate,
    MesureReponse,
)
from app.services.gestion_alertes import traiter_alertes_mesure
from app.models.models import Alerte

from app.schemas.schemas import (
    AlerteReponse,
    ResumeAlertesReponse
)
from app.models.models import SeuilQualiteEau

from app.schemas.schemas import (
    SeuilModification,
    SeuilReponse
)

from app.services.service_seuils import (
    obtenir_seuils_bassin,
    valider_seuil
)

from app.services.validation_mesures import valider_mesure_iot


# Toutes les routes de ce module commencent par /api/v1.
router = APIRouter(
    prefix="/api/v1",
    tags=["Pisciculture"]
)


# ============================================================
# 1. CONSULTER LES ESPÈCES
# GET /api/v1/especes
# ============================================================

@router.get(
    "/especes",
    response_model=list[EspeceReponse]
)
def lister_especes(db: Session = Depends(get_db)):
    """
    Récupère toutes les espèces enregistrées.

    Les espèces sont triées par nom commun.
    """

    # Construire la requête SQLAlchemy.
    requete = select(Espece).order_by(Espece.nom_commun)

    # Exécuter la requête et retourner les espèces.
    return db.scalars(requete).all()


# ============================================================
# 2. CONSULTER TOUS LES BASSINS
# GET /api/v1/bassins
# ============================================================

@router.get(
    "/bassins",
    response_model=list[BassinReponse]
)
def lister_bassins(db: Session = Depends(get_db)):
    """
    Récupère tous les bassins enregistrés.

    Les bassins sont triés par code.
    """

    # Préparer la requête de sélection.
    requete = select(Bassin).order_by(Bassin.code)

    # Retourner la liste des bassins.
    return db.scalars(requete).all()


# ============================================================
# 3. CONSULTER UN BASSIN PAR SON IDENTIFIANT
# GET /api/v1/bassins/{bassin_id}
# ============================================================

@router.get(
    "/bassins/{bassin_id}",
    response_model=BassinReponse
)
def consulter_bassin(
    bassin_id: int,
    db: Session = Depends(get_db)
):
    """
    Récupère les informations d'un bassin.

    Retourne une erreur HTTP 404 si le bassin n'existe pas.
    """

    # Rechercher le bassin par sa clé primaire.
    bassin = db.get(Bassin, bassin_id)

    # Vérifier que le bassin existe.
    if bassin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bassin avec l'ID {bassin_id} non trouvé."
        )

    return bassin


# ============================================================
# 4. CONSULTER LES MESURES D'UN BASSIN
# GET /api/v1/bassins/{bassin_id}/mesures
# ============================================================

@router.get(
    "/bassins/{bassin_id}/mesures",
    response_model=list[MesureReponse]
)
def liste_mesures(
    bassin_id: int,

    # Nombre maximal de mesures à récupérer.
    # Valeur par défaut : 100.
    # Valeur minimale : 1.
    # Valeur maximale : 500.
    limite: int = Query(default=100, ge=1, le=500),

    db: Session = Depends(get_db)
):
    """
    Récupère les dernières mesures d'eau d'un bassin.

    Les mesures sont triées de la plus récente
    à la plus ancienne.
    """

    # Vérifier l'existence du bassin.
    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bassin avec l'ID {bassin_id} non trouvé."
        )

    # Préparer la requête de récupération des mesures.
    requete = (
        select(MesureEau)
        .where(MesureEau.bassin_id == bassin_id)
        .order_by(MesureEau.measure_at.desc(),MesureEau.id.desc())
        .limit(limite)
    )

    # Retourner les mesures.
    return db.scalars(requete).all()


# ============================================================
# 5. ENREGISTRER UNE NOUVELLE MESURE
# POST /api/v1/mesures
# ============================================================

@router.post(
    "/mesures",
    response_model=MesureReponse,
    status_code=status.HTTP_201_CREATED
)
def enregistrer_mesure(
    donnees: MesureCreate,
    db: Session = Depends(get_db)
):
    # ============================================================
    # JOUR 14 — VALIDATION AVANT ENREGISTREMENT
    # ============================================================

    validation = valider_mesure_iot(
        db=db,
        donnees=donnees
    )

    # Appareil vérifié et autorisé.
    appareil = validation["appareil"]

    # Bassin vérifié et associé à cet appareil.
    bassin = validation["bassin"]

    # Date validée et normalisée en UTC.
    date_mesure = validation["date_mesure"]
    
    identifiant_appareil = donnees.device_id.strip()

    # 2. Rechercher l'appareil dans PostgreSQL
    # en utilisant son identifiant texte.
    appareil = db.scalar(
        select(Appareils).where(
            Appareils.identifiant == identifiant_appareil
        )
    )

    # 3. Vérifier que l'appareil existe.
    if appareil is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"L'appareil {identifiant_appareil} "
                "n'existe pas dans la base de données."
            )
        )

    # 4. Vérifier que l'appareil est actif.
    if appareil.statut.upper() == "INACTIF":
        raise HTTPException(
            status_code=403,
            detail=(
                f"L'appareil {identifiant_appareil} "
                "est désactivé. "
                "L'enregistrement des mesures est interdit."
            )
        )

    """
    Enregistre une mesure d'eau provenant d'un appareil.

    Vérifications :
    1. Au moins un paramètre d'eau est renseigné.
    2. Le bassin existe.
    3. L'appareil existe.
    4. L'appareil est affecté au bassin.
    5. La date de mesure contient un fuseau horaire.
    """

    # --------------------------------------------------------
    # ÉTAPE 1 : Vérifier les paramètres de mesure.
    # --------------------------------------------------------

    # Une mesure doit contenir au moins une valeur :
    # température, pH ou oxygène dissous.
    if all(
        valeur is None
        for valeur in (
            donnees.temperature_c,
            donnees.ph,
            donnees.oxygene_dissous_mg_l
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Au moins une mesure est obligatoire."
        )

    # --------------------------------------------------------
    # ÉTAPE 2 : Rechercher le bassin.
    # --------------------------------------------------------

    # Le champ donnees.bassin_id est ici supposé contenir
    # le code du bassin, conformément au code initial.
    bassin = db.scalar(
        select(Bassin).where(
            Bassin.code == donnees.bassin_id
        )
    )

    if bassin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bassin introuvable."
        )

    # --------------------------------------------------------
    # ÉTAPE 3 : Rechercher l'appareil.
    # --------------------------------------------------------

    # Le device_id transmis par l'ESP32 est recherché
    # dans le champ identifiant de la table des appareils.
    appareil = db.scalar(
        select(Appareils).where(
            Appareils.identifiant == donnees.device_id
        )
    )

    if appareil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appareil introuvable."
        )

    # --------------------------------------------------------
    # ÉTAPE 4 : Vérifier l'affectation de l'appareil.
    # --------------------------------------------------------

    # Un appareil ne peut envoyer des mesures que pour
    # le bassin auquel il est affecté.
    if appareil.bassin_id != bassin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appareil non affecté à ce bassin."
        )

    # --------------------------------------------------------
    # ÉTAPE 5 : Déterminer la date de mesure.
    # --------------------------------------------------------

    # Utiliser la date transmise par l'appareil.
    date_mesure = donnees.measure_at

    if date_mesure is None:
        # Si aucune date n'est transmise,
        # utiliser l'heure actuelle en UTC.
        date_mesure = datetime.now(timezone.utc)

    elif (
        date_mesure.tzinfo is None
        or date_mesure.utcoffset() is None
    ):
        # Refuser les dates sans indication de fuseau horaire.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La date doit inclure un fuseau horaire."
        )

    # Convertir la date en UTC pour uniformiser les mesures.
    date_mesure = date_mesure.astimezone(timezone.utc)

    # --------------------------------------------------------
    # ÉTAPE 6 : Construire l'enregistrement SQLAlchemy.
    # --------------------------------------------------------

    mesure = MesureEau(
        bassin_id=bassin.id,
        appareil_id=appareil.id,
        temperature_c=donnees.temperature_c,
        ph=donnees.ph,
        oxygene_dissous_mg_l=donnees.oxygene_dissous_mg_l,
        measure_at=date_mesure,
        source=donnees.source
    )

    # --------------------------------------------------------
    # ÉTAPE 7 : Enregistrer la mesure dans PostgreSQL.
    # --------------------------------------------------------

    try:

        # Ajouter la mesure à la transaction.
        db.add(mesure)

        # Envoyer l'INSERT à PostgreSQL sans valider
        # définitivement la transaction.
        #
        # Cela permet de récupérer mesure.id
        # pour l'associer aux alertes.
        db.flush()

        # Analyser la nouvelle mesure.
        #
        # Le service crée, actualise ou résout
        # les alertes correspondantes.
        traiter_alertes_mesure(
            db=db,
            mesure=mesure
        )

        # Valider la mesure ET les alertes ensemble.
        db.commit()

        # Recharger la mesure depuis PostgreSQL.
        db.refresh(mesure)

    except Exception:

        # Si une opération échoue, annuler
        # toutes les modifications de la transaction.
        db.rollback()

        # Conserver la trace de l'erreur pour
        # faciliter le diagnostic.
        raise

    # --------------------------------------------------------
    # ÉTAPE 8 : Retourner la mesure enregistrée.
    # --------------------------------------------------------

    return mesure
# ============================================================
# 6. LISTER LES ALERTES
# GET /api/v1/alertes
# ============================================================

@router.get(
    "/alertes",
    response_model=list[AlerteReponse]
)
def lister_alertes(
    limite: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Récupérer les dernières alertes,
    quel que soit leur statut.
    """

    requete = (
        select(Alerte)
        .order_by(Alerte.created_at.desc(), Alerte.id.desc())
        .limit(limite)
    )

    return db.scalars(requete).all()


# ============================================================
# 7. RÉSUMÉ DES ALERTES NON RÉSOLUES
# GET /api/v1/alertes/resume
# ============================================================

@router.get(
    "/alertes/resume",
    response_model=ResumeAlertesReponse
)
def resume_alertes(
    db: Session = Depends(get_db)
):
    """
    Calculer les statistiques des alertes
    qui ne sont pas encore résolues.
    """

    requete = select(Alerte).where(
        Alerte.statut.in_(["ACTIVE", "ACQUITTEE"])
    )

    alertes = list(db.scalars(requete).all())

    return {
        "total": len(alertes),
        "avertissements": sum(
            a.niveau == "AVERTISSEMENT"
            for a in alertes
        ),
        "critiques": sum(
            a.niveau == "CRITIQUE"
            for a in alertes
        ),
        "actives": sum(
            a.statut == "ACTIVE"
            for a in alertes
        ),
        "acquittees": sum(
            a.statut == "ACQUITTEE"
            for a in alertes
        )
    }


# ============================================================
# 8. LISTER LES ALERTES NON RÉSOLUES
# GET /api/v1/alertes/actives
# ============================================================

@router.get(
    "/alertes/actives",
    response_model=list[AlerteReponse]
)
def lister_alertes_actives(
    db: Session = Depends(get_db)
):
    """
    Récupérer les alertes encore ouvertes,
    y compris celles déjà acquittées.
    """

    requete = (
        select(Alerte)
        .where(
            Alerte.statut.in_(
                ["ACTIVE", "ACQUITTEE"]
            )
        )
        .order_by(
            Alerte.created_at.desc(),
            Alerte.id.desc()
        )
    )

    return db.scalars(requete).all()


# ============================================================
# 9. ALERTES D'UN BASSIN
# GET /api/v1/bassins/{bassin_id}/alertes
# ============================================================

@router.get(
    "/bassins/{bassin_id}/alertes",
    response_model=list[AlerteReponse]
)
def alertes_bassin(
    bassin_id: int,
    db: Session = Depends(get_db)
):
    """
    Récupérer les alertes d'un bassin.
    """

    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    requete = (
        select(Alerte)
        .where(Alerte.bassin_id == bassin_id)
        .order_by(
            Alerte.created_at.desc(),
            Alerte.id.desc()
        )
    )

    return db.scalars(requete).all()


# ============================================================
# 10. ACQUITTER UNE ALERTE
# PATCH /api/v1/alertes/{alerte_id}/acquitter
# ============================================================

@router.patch(
    "/alertes/{alerte_id}/acquitter",
    response_model=AlerteReponse
)
def acquitter_alerte(
    alerte_id: int,
    db: Session = Depends(get_db)
):
    """
    Marquer une alerte comme prise en compte.

    Une alerte acquittée n'est pas
    automatiquement résolue.
    """

    try:

        alerte = db.scalar(
            select(Alerte)
            .where(Alerte.id == alerte_id)
            .with_for_update()
        )

        if alerte is None:
            raise HTTPException(
                status_code=404,
                detail="Alerte introuvable."
            )

        if alerte.statut == "RESOLUE":
            raise HTTPException(
                status_code=409,
                detail="Cette alerte est déjà résolue."
            )

        if alerte.statut == "ACTIVE":

            alerte.statut = "ACQUITTEE"

            alerte.acknowledged_at = datetime.now(
                timezone.utc
            )

            db.commit()
            db.refresh(alerte)

        return alerte

    except Exception:
        db.rollback()
        raise

# ============================================================
# JOUR 8 : RÉCUPÉRER LA DERNIÈRE MESURE D'UN BASSIN
# ============================================================

@router.get(
    "/bassins/{bassin_id}/derniere-mesure",
    response_model=MesureReponse
)
def obtenir_derniere_mesure(
    bassin_id: int,
    db: Session = Depends(get_db)
):
    """
    Récupère la dernière mesure enregistrée pour un bassin.

    - Vérifie que le bassin existe.
    - Trie les mesures de la plus récente à la plus ancienne.
    - Retourne HTTP 404 si aucune mesure n'est disponible.
    """

    # Vérifier l'existence du bassin.
    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    # Chercher la mesure la plus récente.
    derniere_mesure = db.scalar(
        select(MesureEau)
        .where(MesureEau.bassin_id == bassin_id)
        .order_by(
            MesureEau.measure_at.desc(),
            MesureEau.id.desc()
        )
        .limit(1)
    )

    if derniere_mesure is None:
        raise HTTPException(
            status_code=404,
            detail="Aucune mesure disponible pour ce bassin."
        )

    return derniere_mesure

# ============================================================
# JOUR 9 — ROUTES DE PARAMÉTRAGE DES SEUILS
# ============================================================

@router.get(
    "/seuils",
    response_model=list[SeuilReponse]
)
def lister_seuils(
    db: Session = Depends(get_db)
):
    """Lister toutes les configurations enregistrées."""

    return db.scalars(
        select(SeuilQualiteEau)
        .order_by(
            SeuilQualiteEau.parametre,
            SeuilQualiteEau.id
        )
    ).all()


@router.get(
    "/seuils/{seuil_id}",
    response_model=SeuilReponse
)
def consulter_seuil(
    seuil_id: int,
    db: Session = Depends(get_db)
):
    """Consulter une configuration par son identifiant."""

    seuil = db.get(SeuilQualiteEau, seuil_id)

    if seuil is None:
        raise HTTPException(
            status_code=404,
            detail="Seuil introuvable."
        )

    return seuil


@router.put(
    "/seuils/{seuil_id}",
    response_model=SeuilReponse
)
def modifier_seuil(
    seuil_id: int,
    donnees: SeuilModification,
    db: Session = Depends(get_db)
):
    """
    Remplacer les limites d'une configuration existante.

    L'identifiant du seuil et son paramètre restent inchangés.
    """

    seuil = db.scalar(select(SeuilQualiteEau).where(SeuilQualiteEau.id == seuil_id).with_for_update())


    if seuil is None:
        raise HTTPException(
            status_code=404,
            detail="Seuil introuvable."
        )

    valeurs = donnees.model_dump()

    # Valider les valeurs avant l'enregistrement.
    erreur = valider_seuil(
        seuil.parametre,
        valeurs
    )

    if erreur:
        raise HTTPException(
            status_code=422,
            detail=erreur
        )

    # Mettre à jour les colonnes modifiables.
    seuil.normal_min = donnees.normal_min
    seuil.normal_max = donnees.normal_max
    seuil.critique_min = donnees.critique_min
    seuil.critique_max = donnees.critique_max
    seuil.actif = donnees.actif

    # Conserver la date de modification.
    seuil.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(seuil)

    except Exception:
        db.rollback()
        raise

    return seuil


@router.get(
    "/bassins/{bassin_id}/seuils",
    response_model=list[SeuilReponse]
)
def consulter_seuils_bassin(
    bassin_id: int,
    db: Session = Depends(get_db)
):
    """
    Retourner les règles effectivement applicables
    au bassin demandé.
    """

    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    return obtenir_seuils_bassin(
        db,
        bassin_id
    )

# ============================================================
# JOUR 10 — HISTORIQUE ET ANALYSE DES MESURES
# ============================================================


def normaliser_date_historique(date):
    """
    Convertir une date reçue en UTC.

    Une date sans fuseau horaire est considérée
    comme UTC pour ce module.
    """

    if date is None:
        return None

    if date.tzinfo is None:
        return date.replace(tzinfo=timezone.utc)

    return date.astimezone(timezone.utc)


def verifier_periode_historique(date_debut, date_fin):
    """
    Vérifier que la période demandée est valide.
    """

    debut = normaliser_date_historique(date_debut)
    fin = normaliser_date_historique(date_fin)

    if debut and fin and debut >= fin:
        raise HTTPException(
            status_code=422,
            detail=(
                "La date de fin doit être "
                "postérieure à la date de début."
            )
        )

    return debut, fin


# ============================================================
# 11. HISTORIQUE DES MESURES D'UN BASSIN
# GET /api/v1/historique/mesures
# ============================================================

@router.get("/historique/mesures")
def consulter_historique_mesures(
    bassin_id: int,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    limite: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Consulter les mesures d'un bassin avec :

    - Filtrage par date de début.
    - Filtrage par date de fin.
    - Pagination.
    - Tri chronologique décroissant.
    """

    # Vérifier que le bassin existe.
    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    # Vérifier et normaliser les dates.
    debut, fin = verifier_periode_historique(
        date_debut,
        date_fin
    )

    # Construire les conditions SQL.
    conditions = [
        MesureEau.bassin_id == bassin_id
    ]

    if debut is not None:
        conditions.append(
            MesureEau.measure_at >= debut
        )

    if fin is not None:
        conditions.append(
            MesureEau.measure_at < fin
        )

    # Compter toutes les mesures filtrées.
    total = db.scalar(
        select(func.count(MesureEau.id))
        .where(*conditions)
    ) or 0

    # Récupérer uniquement la page demandée.
    mesures = db.scalars(
        select(MesureEau)
        .where(*conditions)
        .order_by(
            MesureEau.measure_at.desc(),
            MesureEau.id.desc()
        )
        .offset(offset)
        .limit(limite)
    ).all()

    # Utiliser le schéma Pydantic existant.
    return {
        "bassin_id": bassin_id,
        "total": total,
        "limite": limite,
        "offset": offset,
        "mesures": [
            MesureReponse.model_validate(mesure)
            for mesure in mesures
        ]
    }


# ============================================================
# 12. STATISTIQUES DES MESURES D'UN BASSIN
# GET /api/v1/historique/statistiques
# ============================================================

@router.get("/historique/statistiques")
def statistiques_historique(
    bassin_id: int,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    db: Session = Depends(get_db)
):
    """
    Calculer les statistiques des mesures :

    - Nombre total de mesures.
    - Température minimale, maximale et moyenne.
    - pH minimal, maximal et moyen.
    - Oxygène minimal, maximal et moyen.

    Les calculs sont exécutés par PostgreSQL.
    """

    # Vérifier l'existence du bassin.
    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    # Vérifier la période.
    debut, fin = verifier_periode_historique(
        date_debut,
        date_fin
    )

    # Préparer les filtres SQL.
    conditions = [
        MesureEau.bassin_id == bassin_id
    ]

    if debut is not None:
        conditions.append(
            MesureEau.measure_at >= debut
        )

    if fin is not None:
        conditions.append(
            MesureEau.measure_at < fin
        )

    # Calculer les statistiques en une seule requête.
    resultat = db.execute(
        select(
            func.count(MesureEau.id),

            func.min(MesureEau.temperature_c),
            func.max(MesureEau.temperature_c),
            func.avg(MesureEau.temperature_c),

            func.min(MesureEau.ph),
            func.max(MesureEau.ph),
            func.avg(MesureEau.ph),

            func.min(MesureEau.oxygene_dissous_mg_l),
            func.max(MesureEau.oxygene_dissous_mg_l),
            func.avg(MesureEau.oxygene_dissous_mg_l)
        )
        .where(*conditions)
    ).one()

    # Convertir les Decimal en float pour JSON.
    def convertir_nombre(valeur):
        return (
            float(valeur)
            if valeur is not None
            else None
        )

    return {
        "bassin_id": bassin_id,
        "nombre_mesures": resultat[0],

        "temperature": {
            "min": convertir_nombre(resultat[1]),
            "max": convertir_nombre(resultat[2]),
            "moyenne": convertir_nombre(resultat[3])
        },

        "ph": {
            "min": convertir_nombre(resultat[4]),
            "max": convertir_nombre(resultat[5]),
            "moyenne": convertir_nombre(resultat[6])
        },

        "oxygene": {
            "min": convertir_nombre(resultat[7]),
            "max": convertir_nombre(resultat[8]),
            "moyenne": convertir_nombre(resultat[9])
        }
    }

# ============================================================
# JOUR 10 — ANALYSE DES DÉPASSEMENTS
# ============================================================

# Correspondance entre les paramètres des seuils
# et les colonnes du modèle MesureEau.
PARAMETRES_HISTORIQUE = {
    "temperature_c": "temperature_c",
    "ph": "ph",
    "oxygene_dissous_mg_l": "oxygene_dissous_mg_l"
}


def construire_filtres_historique(
    bassin_id,
    date_debut,
    date_fin
):
    """
    Construire les conditions communes aux routes
    d'analyse et d'export.

    La date de fin est exclusive.
    """

    debut, fin = verifier_periode_historique(
        date_debut,
        date_fin
    )

    conditions = [
        MesureEau.bassin_id == bassin_id
    ]

    if debut is not None:
        conditions.append(
            MesureEau.measure_at >= debut
        )

    if fin is not None:
        conditions.append(
            MesureEau.measure_at < fin
        )

    return conditions


def classifier_valeur_historique(valeur, seuil):
    """
    Classifier une valeur selon les seuils PostgreSQL.

    Retour possible :
    - NORMAL
    - AVERTISSEMENT
    - CRITIQUE
    - INDISPONIBLE

    Les limites critiques sont inclusives.
    """

    if valeur is None or seuil is None:
        return "INDISPONIBLE"

    if not seuil.actif:
        return "INDISPONIBLE"

    valeur = Decimal(str(valeur))

    def nombre(champ):
        v = getattr(seuil, champ)
        return Decimal(str(v)) if v is not None else None

    normal_min = nombre("normal_min")
    normal_max = nombre("normal_max")
    critique_min = nombre("critique_min")
    critique_max = nombre("critique_max")

    # Priorité absolue au niveau critique.
    if critique_min is not None and valeur <= critique_min:
        return "CRITIQUE"

    if critique_max is not None and valeur >= critique_max:
        return "CRITIQUE"

    # En dehors de la plage normale : avertissement.
    if normal_min is not None and valeur < normal_min:
        return "AVERTISSEMENT"

    if normal_max is not None and valeur > normal_max:
        return "AVERTISSEMENT"

    return "NORMAL"


def charger_seuils_historique(db, bassin_id):
    """
    Charger les seuils applicables au bassin.

    Réutilise le service du Jour 9 :
    obtenir_seuils_bassin().
    """

    seuils = obtenir_seuils_bassin(db, bassin_id)

    return {
        seuil.parametre: seuil
        for seuil in seuils
        if seuil.actif
    }


def analyser_une_mesure(mesure, seuils):
    """
    Retourner les états des trois paramètres
    pour une mesure enregistrée.
    """

    resultats = {}

    for parametre, attribut in PARAMETRES_HISTORIQUE.items():

        valeur = getattr(mesure, attribut)

        seuil = seuils.get(parametre)

        resultats[parametre] = classifier_valeur_historique(
            valeur,
            seuil
        )

    return resultats


# ============================================================
# 13. ANALYSE DES PÉRIODES ANORMALES
# GET /api/v1/historique/anomalies
# ============================================================

@router.get("/historique/anomalies")
def historique_anomalies(
    bassin_id: int,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    db: Session = Depends(get_db)
):
    """
    Détecter les périodes anormales du bassin.

    Deux mesures anormales successives sont regroupées
    lorsqu'elles concernent le même paramètre,
    le même niveau et que leur écart est inférieur
    ou égal à 30 secondes.

    Ce délai est adapté au simulateur de 10 secondes.
    Il pourra être configuré ultérieurement.
    """

    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    conditions = construire_filtres_historique(
        bassin_id,
        date_debut,
        date_fin
    )

    seuils = charger_seuils_historique(
        db,
        bassin_id
    )

    requete = (
        select(MesureEau)
        .where(*conditions)
        .order_by(
            MesureEau.measure_at.asc(),
            MesureEau.id.asc()
        )
    )

    # Conserver uniquement les périodes ouvertes.
    ouvertes = {}

    # Liste des périodes terminées.
    periodes = []

    # Nombre de mesures présentant au moins une anomalie.
    nombre_mesures_anormales = 0

    # Nombre de dépassements par paramètre.
    nombre_depassements = {
        parametre: 0
        for parametre in PARAMETRES_HISTORIQUE
    }

    # Itération progressive pour ne pas charger
    # tout l'historique en mémoire simultanément.
    mesures = db.scalars(
        requete.execution_options(yield_per=500)
    )

    for mesure in mesures:

        etats = analyser_une_mesure(
            mesure,
            seuils
        )

        mesure_anormale = False

        for parametre, niveau in etats.items():

            est_anormal = niveau in (
                "AVERTISSEMENT",
                "CRITIQUE"
            )

            periode = ouvertes.get(parametre)

            # Une période se poursuit seulement si
            # le niveau est identique et le délai court.
            continuer = (
                est_anormal
                and periode is not None
                and periode["niveau"] == niveau
                and (
                    mesure.measure_at
                    - periode["_fin_brute"]
                ).total_seconds() <= 30
            )

            if continuer:

                periode["_fin_brute"] = mesure.measure_at
                periode["fin"] = mesure.measure_at.isoformat()
                periode["nombre_mesures"] += 1

            else:

                # Terminer l'ancienne période.
                if periode is not None:
                    periodes.append(periode)
                    ouvertes.pop(parametre, None)

                # Ouvrir une nouvelle période si nécessaire.
                if est_anormal:
                    ouvertes[parametre] = {
                        "parametre": parametre,
                        "niveau": niveau,
                        "debut": mesure.measure_at.isoformat(),
                        "fin": mesure.measure_at.isoformat(),
                        "nombre_mesures": 1,
                        "_fin_brute": mesure.measure_at
                    }

            if est_anormal:
                mesure_anormale = True
                nombre_depassements[parametre] += 1

        if mesure_anormale:
            nombre_mesures_anormales += 1

    # Fermer les périodes encore ouvertes.
    periodes.extend(ouvertes.values())

    # Supprimer les champs techniques.
    for periode in periodes:
        periode.pop("_fin_brute", None)

    # Afficher les périodes les plus récentes d'abord.
    periodes.sort(
        key=lambda p: p["debut"],
        reverse=True
    )

    return {
        "bassin_id": bassin_id,
        "nombre_mesures_anormales": nombre_mesures_anormales,
        "nombre_depassements": nombre_depassements,
        "nombre_periodes": len(periodes),
        "periodes": periodes
    }

# ============================================================
# 14. EXPORT CSV / EXCEL DE L'HISTORIQUE
# GET /api/v1/historique/export
# ============================================================

@router.get("/historique/export")
def exporter_historique(
    bassin_id: int,
    format: str = Query(
        default="xlsx",
        pattern="^(csv|xlsx)$"
    ),
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    db: Session = Depends(get_db)
):
    """
    Exporter les mesures d'un bassin.

    Formats disponibles :
    - csv : compatible Excel, encodage UTF-8 BOM.
    - xlsx : classeur Excel natif.

    Le fichier contient également le statut
    de chaque paramètre selon les seuils actuels.

    Limite de sécurité : 50 000 mesures par export.
    """

    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    conditions = construire_filtres_historique(
        bassin_id,
        date_debut,
        date_fin
    )

    total = db.scalar(
        select(func.count(MesureEau.id))
        .where(*conditions)
    ) or 0

    if total > 50000:
        raise HTTPException(
            status_code=422,
            detail=(
                "L'export est limité à 50 000 mesures. "
                "Sélectionnez une période plus courte."
            )
        )

    seuils = charger_seuils_historique(
        db,
        bassin_id
    )

    mesures = db.scalars(
        select(MesureEau)
        .where(*conditions)
        .order_by(
            MesureEau.measure_at.desc(),
            MesureEau.id.desc()
        )
    ).all()

    entetes = [
        "Bassin",
        "Date UTC",
        "Température (°C)",
        "État température",
        "pH",
        "État pH",
        "Oxygène (mg/L)",
        "État oxygène",
        "Source"
    ]

    def creer_lignes():
        """
        Produire les lignes communes aux exports.
        """

        for mesure in mesures:

            etats = analyser_une_mesure(
                mesure,
                seuils
            )

            yield [
                bassin.code,
                mesure.measure_at.isoformat(),
                float(mesure.temperature_c)
                if mesure.temperature_c is not None else None,
                etats["temperature_c"],
                float(mesure.ph)
                if mesure.ph is not None else None,
                etats["ph"],
                float(mesure.oxygene_dissous_mg_l)
                if mesure.oxygene_dissous_mg_l is not None else None,
                etats["oxygene_dissous_mg_l"],
                mesure.source
            ]

    nom_fichier = (
        f"historique_{bassin.code}_"
        f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"
    )

    if format == "csv":

        import csv

        # Générer un CSV UTF-8 avec BOM.
        # Le séparateur ; facilite l'ouverture
        # dans Excel avec les paramètres français.
        contenu = StringIO()

        writer = csv.writer(
            contenu,
            delimiter=";",
            lineterminator="\r\n"
        )

        writer.writerow(entetes)

        for ligne in creer_lignes():
            writer.writerow(ligne)

        donnees = (
            "\ufeff" + contenu.getvalue()
        ).encode("utf-8")

        return StreamingResponse(
            iter([donnees]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{nom_fichier}.csv"'
            }
        )

    # ========================================================
    # EXPORT EXCEL .XLSX
    # ========================================================

    classeur = Workbook(write_only=True)
    feuille = classeur.create_sheet(
        title="Historique des mesures"
    )

    feuille.append(entetes)

    for ligne in creer_lignes():
        feuille.append(ligne)

    fichier = BytesIO()
    classeur.save(fichier)
    fichier.seek(0)

    return StreamingResponse(
        fichier,
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom_fichier}.xlsx"'
        }
    )

# ============================================================
# JOUR 12 — SUPERVISION WEBSOCKET MULTI-BASSINS
# ============================================================

# Fréquence de lecture des données PostgreSQL.
INTERVALLE_WEBSOCKET = 5

# Nombre maximal d'alertes ouvertes transmises.
LIMITE_ALERTES_WEBSOCKET = 100


def construire_etat_supervision(db: Session):
    """
    Construire un instantané de supervision.

    Pour chaque bassin :
    - Récupérer ses informations.
    - Récupérer sa dernière mesure.
    - Récupérer le nombre d'alertes ouvertes.

    Les résultats sont ensuite envoyés aux clients
    WebSocket connectés.
    """

    # Charger les bassins.
    bassins = db.scalars(
        select(Bassin).order_by(Bassin.code)
    ).all()

    # Récupérer l'identifiant de la dernière mesure
    # de chaque bassin avec une sous-requête PostgreSQL.
    #
    # DISTINCT ON permet de conserver la mesure
    # la plus récente de chaque bassin.
    dernieres_mesures_ids = (
        select(MesureEau.id)
        .distinct(MesureEau.bassin_id)
        .order_by(
            MesureEau.bassin_id,
            MesureEau.measure_at.desc(),
            MesureEau.id.desc()
        )
    )

    dernieres_mesures = db.scalars(
        select(MesureEau)
        .where(
            MesureEau.id.in_(dernieres_mesures_ids)
        )
    ).all()

    # Indexer les mesures par bassin.
    mesures_par_bassin = {
        mesure.bassin_id: mesure
        for mesure in dernieres_mesures
    }

    # Récupérer les alertes non résolues.
    alertes = db.scalars(
        select(Alerte)
        .where(
            Alerte.statut.in_([
                "ACTIVE",
                "ACQUITTEE"
            ])
        )
        .order_by(
            Alerte.created_at.desc(),
            Alerte.id.desc()
        )
        .limit(LIMITE_ALERTES_WEBSOCKET)
    ).all()

    # Compter toutes les alertes ouvertes par bassin.
    comptages = db.execute(
        select(
            Alerte.bassin_id,
            func.count(Alerte.id)
        )
        .where(
            Alerte.statut.in_([
                "ACTIVE",
                "ACQUITTEE"
            ])
        )
        .group_by(Alerte.bassin_id)
    ).all()

    alertes_par_bassin = {
        bassin_id: total
        for bassin_id, total in comptages
    }

    # Construire la liste des bassins supervisés.
    resultat_bassins = []

    for bassin in bassins:

        mesure = mesures_par_bassin.get(bassin.id)

        derniere_mesure = None

        if mesure is not None:
            derniere_mesure = {
                "id": mesure.id,
                "temperature_c": (
                    float(mesure.temperature_c)
                    if mesure.temperature_c is not None
                    else None
                ),
                "ph": (
                    float(mesure.ph)
                    if mesure.ph is not None
                    else None
                ),
                "oxygene_dissous_mg_l": (
                    float(mesure.oxygene_dissous_mg_l)
                    if mesure.oxygene_dissous_mg_l is not None
                    else None
                ),
                "measure_at": mesure.measure_at,
                "source": mesure.source
            }

        resultat_bassins.append({
            "id": bassin.id,
            "code": bassin.code,
            "nom": bassin.nom,
            "statut": bassin.statut,
            "derniere_mesure": derniere_mesure,
            "alertes_ouvertes": (
                alertes_par_bassin.get(bassin.id, 0)
            )
        })

    # Préparer les alertes pour le frontend.
    resultat_alertes = []

    for alerte in alertes:

        resultat_alertes.append({
            "id": alerte.id,
            "bassin_id": alerte.bassin_id,
            "niveau": alerte.niveau,
            "statut": alerte.statut,
            "created_at": alerte.created_at
        })

    return {
        "type": "supervision",
        "date_serveur": datetime.now(timezone.utc),
        "nombre_bassins": len(resultat_bassins),
        "nombre_alertes_ouvertes": sum(
            alertes_par_bassin.values()
        ),
        "bassins": resultat_bassins,
        "alertes": resultat_alertes
    }


# ============================================================
# ENDPOINT WEBSOCKET
# ws://127.0.0.1:8000/api/v1/ws/supervision
# ============================================================

@router.websocket("/ws/supervision")
async def websocket_supervision(
    websocket: WebSocket
):
    """
    Maintenir une connexion WebSocket.

    Toutes les 5 secondes :
    1. Lire les dernières données PostgreSQL.
    2. Construire un instantané.
    3. Envoyer le JSON au frontend.

    Chaque cycle ouvre sa propre session SQLAlchemy,
    afin de ne pas conserver une transaction ouverte
    pendant toute la durée de la connexion.
    """

    # Accepter la connexion.
    await websocket.accept()

    try:
        while True:

            try:
                # Utiliser la dépendance existante.
                # get_db() fournit une session SQLAlchemy.
                generateur_db = get_db()
                db = next(generateur_db)

                try:
                    donnees = await asyncio.to_thread(
                        construire_etat_supervision,
                        db
                    )
                finally:
                    generateur_db.close()

                # Encoder les datetime et Decimal en JSON.
                donnees_json = jsonable_encoder(donnees)

                # Envoyer l'instantané au navigateur.
                await websocket.send_json(donnees_json)

            except (WebSocketDisconnect, RuntimeError):
                raise

            except Exception:
                # Ne pas exposer les détails internes SQL.
                await websocket.send_json({
                    "type": "erreur",
                    "message": (
                        "Impossible de récupérer les données "
                        "de supervision."
                    )
                })

            # Attendre avant la prochaine lecture.
            await asyncio.sleep(INTERVALLE_WEBSOCKET)

    except WebSocketDisconnect:
        # Le navigateur a fermé la connexion.
        pass

    except RuntimeError:
        # La connexion a été fermée pendant l'envoi.
        pass

# ============================================================
# JOUR 13 — GESTION DES APPAREILS IOT
# ============================================================

# Durée maximale sans mesure avant de considérer
# un appareil comme hors ligne.
DELAI_HORS_LIGNE_SECONDES = 60


class AppareilCreation(BaseModel):
    """
    Données nécessaires pour enregistrer un appareil.
    """

    identifiant: str = Field(
        min_length=3,
        max_length=100
    )

    bassin_id: int = Field(gt=0)


class AppareilModification(BaseModel):
    """
    Données modifiables d'un appareil.

    Les champs sont facultatifs pour permettre
    une modification partielle avec PATCH.
    """

    bassin_id: int | None = Field(
        default=None,
        gt=0
    )

    statut: str | None = None


def verifier_bassin_appareil(
    db: Session,
    bassin_id: int
):
    """
    Vérifier que le bassin existe avant d'y
    affecter un appareil.
    """

    bassin = db.get(Bassin, bassin_id)

    if bassin is None:
        raise HTTPException(
            status_code=404,
            detail="Bassin introuvable."
        )

    return bassin


def obtenir_derniere_mesure_appareil(
    db: Session,
    appareil_id: int
):
    """
    Récupérer la dernière mesure transmise
    par un appareil IoT.
    """

    return db.scalars(
        select(MesureEau)
        .where(
            MesureEau.appareil_id == appareil_id
        )
        .order_by(
            MesureEau.measure_at.desc(),
            MesureEau.id.desc()
        )
        .limit(1)
    ).first()


def calculer_etat_appareil(
    appareil,
    derniere_mesure
):
    """
    Déterminer l'état opérationnel de l'appareil.

    Ce calcul repose sur l'activité enregistrée
    dans PostgreSQL, pas sur un ping réseau.
    """

    # Un appareil désactivé ne doit pas être
    # considéré comme disponible.
    if appareil.statut == "INACTIF":
        return "DESACTIVE"

    # Aucune mesure reçue depuis l'enregistrement.
    if derniere_mesure is None:
        return "SANS_DONNEES"

    date_mesure = derniere_mesure.measure_at

    # Normaliser les dates en UTC.
    if date_mesure.tzinfo is None:
        date_mesure = date_mesure.replace(
            tzinfo=timezone.utc
        )

    maintenant = datetime.now(timezone.utc)

    difference = (
        maintenant - date_mesure
    ).total_seconds()

    if 0 <= difference <= DELAI_HORS_LIGNE_SECONDES:
        return "EN_LIGNE"

    return "HORS_LIGNE"


def construire_reponse_appareil(
    db: Session,
    appareil
):
    """
    Préparer les informations complètes
    d'un appareil pour le frontend.
    """

    bassin = db.get(
        Bassin,
        appareil.bassin_id
    )

    derniere_mesure = (
        obtenir_derniere_mesure_appareil(
            db,
            appareil.id
        )
    )

    etat = calculer_etat_appareil(
        appareil,
        derniere_mesure
    )

    return {
        "id": appareil.id,
        "identifiant": appareil.identifiant,
        "bassin_id": appareil.bassin_id,
        "bassin_code": (
            bassin.code if bassin else None
        ),
        "bassin_nom": (
            bassin.nom if bassin else None
        ),
        "statut": appareil.statut,
        "etat_connexion": etat,
        "derniere_communication": (
            derniere_mesure.measure_at
            if derniere_mesure else None
        ),
        "derniere_mesure": (
            {
                "temperature_c": (
                    float(derniere_mesure.temperature_c)
                    if derniere_mesure.temperature_c is not None
                    else None
                ),
                "ph": (
                    float(derniere_mesure.ph)
                    if derniere_mesure.ph is not None
                    else None
                ),
                "oxygene_dissous_mg_l": (
                    float(
                        derniere_mesure.oxygene_dissous_mg_l
                    )
                    if derniere_mesure.oxygene_dissous_mg_l
                    is not None
                    else None
                )
            }
            if derniere_mesure else None
        )
    }


# ============================================================
# 1. LISTER LES APPAREILS
# GET /api/v1/appareils
# ============================================================

@router.get("/appareils")
def lister_appareils(
    bassin_id: int | None = None,
    db: Session = Depends(get_db)
):
    """
    Lister tous les appareils ou filtrer
    les appareils d'un bassin.
    """

    requete = select(Appareils)

    if bassin_id is not None:
        verifier_bassin_appareil(
            db,
            bassin_id
        )

        requete = requete.where(
            Appareils.bassin_id == bassin_id
        )

    appareils = db.scalars(
        requete.order_by(Appareils.identifiant)
    ).all()

    return [
        construire_reponse_appareil(db, appareil)
        for appareil in appareils
    ]


# ============================================================
# 2. CONSULTER UN APPAREIL
# GET /api/v1/appareils/{appareil_id}
# ============================================================

@router.get("/appareils/{appareil_id}")
def consulter_appareil(
    appareil_id: int,
    db: Session = Depends(get_db)
):
    """
    Récupérer un appareil avec son état actuel.
    """

    appareil = db.get(
        Appareils,
        appareil_id
    )

    if appareil is None:
        raise HTTPException(
            status_code=404,
            detail="Appareil introuvable."
        )

    return construire_reponse_appareil(
        db,
        appareil
    )


# ============================================================
# 3. CRÉER UN APPAREIL
# POST /api/v1/appareils
# ============================================================

@router.post(
    "/appareils",
    status_code=201
)
def creer_appareil(
    donnees: AppareilCreation,
    db: Session = Depends(get_db)
):
    """
    Enregistrer un nouvel appareil IoT.

    Chaque identifiant doit être unique.
    """

    identifiant = donnees.identifiant.strip()

    if len(identifiant) < 3:
        raise HTTPException(
            status_code=422,
            detail="Identifiant trop court."
        )

    verifier_bassin_appareil(
        db,
        donnees.bassin_id
    )

    existe = db.scalars(
        select(Appareils)
        .where(
            Appareils.identifiant == identifiant
        )
    ).first()

    if existe is not None:
        raise HTTPException(
            status_code=409,
            detail="Cet identifiant existe déjà."
        )

    appareil = Appareils(
        identifiant=identifiant,
        bassin_id=donnees.bassin_id,
        statut="ACTIF"
    )

    db.add(appareil)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Impossible de créer cet appareil."
        )

    db.refresh(appareil)

    return construire_reponse_appareil(
        db,
        appareil
    )


# ============================================================
# 4. MODIFIER UN APPAREIL
# PATCH /api/v1/appareils/{appareil_id}
# ============================================================

@router.patch("/appareils/{appareil_id}")
def modifier_appareil(
    appareil_id: int,
    donnees: AppareilModification,
    db: Session = Depends(get_db)
):
    """
    Modifier le bassin affecté à un appareil
    ou son statut administratif.

    Statuts autorisés :
    - ACTIF
    - INACTIF
    """

    appareil = db.get(
        Appareils,
        appareil_id
    )

    if appareil is None:
        raise HTTPException(
            status_code=404,
            detail="Appareil introuvable."
        )

    modifications = donnees.model_dump(
        exclude_unset=True
    )

    if not modifications:
        raise HTTPException(
            status_code=422,
            detail="Aucune modification fournie."
        )

    if "bassin_id" in modifications:

        nouveau_bassin = modifications["bassin_id"]

        if nouveau_bassin is None:
            raise HTTPException(
                status_code=422,
                detail="Le bassin est obligatoire."
            )

        verifier_bassin_appareil(
            db,
            nouveau_bassin
        )

        appareil.bassin_id = nouveau_bassin

    if "statut" in modifications:

        statut = modifications["statut"]

        if statut not in ("ACTIF", "INACTIF"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Statut autorisé : ACTIF ou INACTIF."
                )
            )

        appareil.statut = statut

    db.commit()
    db.refresh(appareil)

    return construire_reponse_appareil(
        db,
        appareil
    )


# ============================================================
# 5. RÉSUMÉ DES APPAREILS
# GET /api/v1/appareils-supervision/resume
# ============================================================

@router.get("/appareils-supervision/resume")
def resume_appareils(
    db: Session = Depends(get_db)
):
    """
    Retourner les indicateurs de disponibilité
    des appareils IoT.
    """

    appareils = db.scalars(
        select(Appareils)
    ).all()

    compteurs = {
        "total": len(appareils),
        "en_ligne": 0,
        "hors_ligne": 0,
        "sans_donnees": 0,
        "desactives": 0
    }

    correspondance = {
        "EN_LIGNE": "en_ligne",
        "HORS_LIGNE": "hors_ligne",
        "SANS_DONNEES": "sans_donnees",
        "DESACTIVE": "desactives"
    }

    for appareil in appareils:

        mesure = obtenir_derniere_mesure_appareil(
            db,
            appareil.id
        )

        etat = calculer_etat_appareil(
            appareil,
            mesure
        )

        compteurs[correspondance[etat]] += 1

    return compteurs
