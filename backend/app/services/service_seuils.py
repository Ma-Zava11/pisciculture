
"""
JOUR 9 — Service de gestion des seuils.

Priorité actuelle :
1. Configuration spécifique au bassin.
2. Configuration globale.

Les seuils par espèce seront intégrés après confirmation
de la relation entre bassins et espèces.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import SeuilQualiteEau


PARAMETRES = (
    "temperature_c",
    "ph",
    "oxygene_dissous_mg_l",
)

# Limites techniques pour valider les configurations.
BORNES = {
    "temperature_c": (-10, 60),
    "ph": (0, 14),
    "oxygene_dissous_mg_l": (0, None),
}


def valider_seuil(parametre, valeurs):
    """
    Valider une configuration complète de seuil.

    Retourne un message d'erreur ou None si tout est valide.
    """

    if parametre not in PARAMETRES:
        return "Paramètre de surveillance inconnu."

    minimum = valeurs["normal_min"]
    maximum = valeurs["normal_max"]
    critique_min = valeurs["critique_min"]
    critique_max = valeurs["critique_max"]

    if minimum is None:
        return "normal_min est obligatoire."

    borne_min, borne_max = BORNES[parametre]

    for nom, valeur in valeurs.items():
        if nom == "actif" or valeur is None:
            continue

        if valeur < borne_min:
            return f"{nom} ne peut pas être inférieur à {borne_min}."

        if borne_max is not None and valeur > borne_max:
            return f"{nom} ne peut pas dépasser {borne_max}."

    if maximum is not None and minimum > maximum:
        return "normal_min doit être inférieur ou égal à normal_max."

    if critique_min is not None and critique_min > minimum:
        return "critique_min doit être inférieur ou égal à normal_min."

    if critique_max is not None:
        if maximum is None:
            return "normal_max est nécessaire si critique_max est défini."

        if critique_max < maximum:
            return "critique_max doit être supérieur ou égal à normal_max."

    return None


def obtenir_seuils_bassin(db: Session, bassin_id: int):
    """
    Retourner les seuils effectifs d'un bassin.

    Une configuration propre au bassin remplace la
    configuration globale du même paramètre.
    """

    # Règles globales : ni bassin ni espèce.
    globaux = db.scalars(
        select(SeuilQualiteEau)
        .where(
            SeuilQualiteEau.bassin_id.is_(None),
            SeuilQualiteEau.espece_id.is_(None),
            SeuilQualiteEau.actif.is_(True)
        )
        .order_by(SeuilQualiteEau.id)
    ).all()

    # Règles spécifiques au bassin.
    specifiques = db.scalars(
        select(SeuilQualiteEau)
        .where(
            SeuilQualiteEau.bassin_id == bassin_id,
            SeuilQualiteEau.espece_id.is_(None),
            SeuilQualiteEau.actif.is_(True)
        )
        .order_by(SeuilQualiteEau.id)
    ).all()

    # Dictionnaire indexé par le nom du paramètre.
    # Une règle spécifique remplace une règle globale.
    resultat = {}

    for seuil in globaux:
        resultat[seuil.parametre] = seuil

    for seuil in specifiques:
        resultat[seuil.parametre] = seuil

    return [
        resultat[parametre]
        for parametre in PARAMETRES
        if parametre in resultat
    ]
