from datetime import datetime
from decimal import Decimal 


from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Espece(Base):
    __tablename__ = "especes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nom_commun: Mapped[str] = mapped_column(String(100), nullable=False)
    nom_scientifique: Mapped[str | None] = mapped_column(String(150))

    description: Mapped[str | None] = mapped_column(Text)

class Bassin(Base):
    __tablename__ ="bassins" 

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    capacite_litres: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="actif")

class Appareils(Base):
    __tablename__ = "appareils"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    identifiant: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    bassin_id: Mapped[int] = mapped_column(ForeignKey("bassins.id"), nullable=False)
    statut:Mapped[str] = mapped_column(String(20), nullable=False)
    
class MesureEau(Base):
    __tablename__ = "mesures_eau"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bassin_id: Mapped[int] = mapped_column(ForeignKey("bassins.id"), nullable=False)
    appareil_id: Mapped[int | None] = mapped_column(ForeignKey("appareils.id"))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(precision=5, scale=2))
    ph: Mapped[Decimal | None] = mapped_column(Numeric(precision=4, scale=2))
    oxygene_dissous_mg_l: Mapped[Decimal | None] = mapped_column(Numeric(precision=6, scale=2))
    measure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source: Mapped[str] = mapped_column(String(50), nullable=False)
        