from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict,model_validator


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class EspeceReponse(SchemaBase):
    id: int
    nom_commun: str
    nom_scientifique: str | None = None 
    description: str | None = None

class BassinReponse(SchemaBase):
    id: int
    code: str
    nom: str
    capacite_litres: float
    statut: str 

class MesureCreate(SchemaBase):
    device_id: str
    bassin_id: str
    temperature_c: float | None = Field(default=None, ge=-10.0, le=60.0)
    ph: float | None = Field(default=None, ge=0.0, le=14.0)
    oxygene_dissous_mg_l: float | None = Field(default=None, ge=0.0)
    measure_at: datetime | None = None 
    source: str = Field(default="SIMULATION",pattern="^(SIMULATION|APPAREIL)$")

class MesureReponse(SchemaBase):
    id: int
    bassin_id: int
    appareil_id: int | None = None
    temperature_c: float | None = None
    ph: float | None = None
    oxygene_dissous_mg_l: float | None = None
    measure_at: datetime
    source: str

class AlerteReponse(SchemaBase):
    """
    Format JSON d'une alerte retournée par FastAPI.
    """

    id: int
    bassin_id: int
    mesure_id: int

    parametre: str
    valeur: float
    niveau: str
    message: str
    statut: str

    occurrences: int

    created_at: datetime
    last_seen_at: datetime

    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class ResumeAlertesReponse(SchemaBase):
    """
    Statistiques des alertes non résolues.
    """

    total: int
    avertissements: int
    critiques: int
    actives: int
    acquittees: int
# ============================================================
# JOUR 9 — SCHÉMAS DE CONFIGURATION DES SEUILS
# ============================================================

PARAMETRES_AUTORISES = {
    "temperature_c",
    "ph",
    "oxygene_dissous_mg_l"
}


class SeuilModification(BaseModel):
    """
    Données autorisées lors de la modification d'un seuil.

    Les identifiants, le paramètre et le bassin ne sont
    pas modifiables avec cette route.
    """

    normal_min: float | None = None
    normal_max: float | None = None
    critique_min: float | None = None
    critique_max: float | None = None
    actif: bool = True

    @model_validator(mode="after")
    def verifier_limites(self):
        """
        Vérifier que les limites critiques entourent
        correctement la plage normale.
        """

        if self.normal_min is None:
            raise ValueError(
                "La limite normale minimale est obligatoire."
            )

        if (
            self.normal_max is not None
            and self.normal_min > self.normal_max
        ):
            raise ValueError(
                "normal_min doit être inférieur ou égal "
                "à normal_max."
            )

        if (
            self.critique_min is not None
            and self.critique_min > self.normal_min
        ):
            raise ValueError(
                "critique_min doit être inférieur ou égal "
                "à normal_min."
            )

        if (
            self.critique_max is not None
            and self.normal_max is not None
            and self.critique_max < self.normal_max
        ):
            raise ValueError(
                "critique_max doit être supérieur ou égal "
                "à normal_max."
            )

        return self


class SeuilReponse(BaseModel):
    """Représentation d'un seuil enregistré en base."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    espece_id: int | None
    bassin_id: int | None
    parametre: str

    normal_min: float | None
    normal_max: float | None
    critique_min: float | None
    critique_max: float | None

    actif: bool
    updated_at: datetime
