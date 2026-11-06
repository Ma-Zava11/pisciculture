
"""
Routes de l'API de pisciculture intelligente.

Fonctionnalités :
- Consulter les espèces de poissons.
- Consulter les bassins.
- Consulter les informations d'un bassin.
- Consulter les mesures d'eau d'un bassin.
- Enregistrer les mesures transmises par les appareils ESP32.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

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
        .order_by(MesureEau.measure_at.desc())
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
        # Ajouter la nouvelle mesure à la session.
        db.add(mesure)

        # Valider la transaction.
        db.commit()

        # Recharger les valeurs depuis la base de données.
        db.refresh(mesure)

    except Exception:
        # Annuler la transaction en cas d'échec.
        db.rollback()

        # Propager l'erreur pour permettre son diagnostic.
        raise

    # --------------------------------------------------------
    # ÉTAPE 8 : Retourner la mesure enregistrée.
    # --------------------------------------------------------

    return mesure
