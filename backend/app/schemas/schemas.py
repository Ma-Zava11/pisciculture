from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


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