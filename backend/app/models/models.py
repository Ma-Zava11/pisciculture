from datetime import datetime
from decimal import Decimal 
from sqlalchemy import Boolean, CheckConstraint, Index

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,  
    Numeric,
    String,
    UniqueConstraint,
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



# ============================================================
# MODÈLE : ALERTE DE QUALITÉ D'EAU
# ============================================================

class Alerte(Base):
    """
    Représente une anomalie détectée dans un bassin.

    Une alerte peut être :
    - ACTIVE : anomalie toujours présente ;
    - ACQUITTEE : anomalie reconnue par un utilisateur ;
    - RESOLUE : retour à une situation normale.

    Le champ occurrences indique combien de mesures
    ont confirmé l'anomalie.
    """

    __tablename__ = "alertes"

    __table_args__ = (
        CheckConstraint(
            "niveau IN ('AVERTISSEMENT', 'CRITIQUE')",
            name="ck_alertes_niveau"
        ),
        CheckConstraint(
            "statut IN ('ACTIVE', 'ACQUITTEE', 'RESOLUE')",
            name="ck_alertes_statut"
        ),
        Index(
            "ix_alertes_bassin_statut",
            "bassin_id",
            "statut"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # Bassin concerné par l'anomalie.
    bassin_id: Mapped[int] = mapped_column(
        ForeignKey("bassins.id"),
        nullable=False,
        index=True
    )

    # Première mesure ayant déclenché l'alerte.
    mesure_id: Mapped[int] = mapped_column(
        ForeignKey("mesures_eau.id"),
        nullable=False
    )

    parametre: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    valeur: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=3),
        nullable=False
    )

    niveau: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    statut: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE"
    )

    # Nombre d'observations associées à l'alerte.
    occurrences: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1
    )

    # Date de première détection.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Date de la dernière observation anormale.
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Date de prise en compte par un utilisateur.
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # Date de résolution.
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
# ============================================================
# JOUR 9 : SEUILS DE QUALITÉ DE L'EAU
# ============================================================

class SeuilQualiteEau(Base):
    __tablename__ = "seuils_qualite_eau"

    __table_args__ = (
        # Empêcher les seuils incohérents.
        CheckConstraint(
            "normal_min IS NULL OR normal_max IS NULL "
            "OR normal_min <= normal_max",
            name="ck_seuil_normal"
        ),

        CheckConstraint(
            "critique_min IS NULL OR normal_min IS NULL "
            "OR critique_min <= normal_min",
            name="ck_seuil_critique_min"
        ),

        CheckConstraint(
            "critique_max IS NULL OR normal_max IS NULL "
            "OR critique_max >= normal_max",
            name="ck_seuil_critique_max"
        ),

        # Un paramètre ne doit être défini qu'une fois
        # pour une combinaison espèce + bassin.
        # L'unicité avec NULL sera traitée séparément
        # par des index PostgreSQL.
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    espece_id: Mapped[int | None] = mapped_column(
        ForeignKey("especes.id"),
        nullable=True
    )

    bassin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bassins.id"),
        nullable=True
    )

    parametre: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    normal_min: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )

    normal_max: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )

    critique_min: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )

    critique_max: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )

    actif: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
