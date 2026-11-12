
# ============================================================
# JOUR 15 — CONFIGURATION DATA SCIENCE
# Fichier : data_science/config.py
# ============================================================

from pathlib import Path
from dotenv import load_dotenv
import os

# Racine du projet Data Science.
BASE_DIR = Path(__file__).resolve().parent

# Racine générale du projet pisciculture.
PROJET_DIR = BASE_DIR.parent

# Réutiliser le fichier .env du backend.
ENV_BACKEND = PROJET_DIR / "backend" / ".env"

load_dotenv(ENV_BACKEND)

# Récupérer l'URL de PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL introuvable dans backend/.env"
    )

# Chemins de stockage.
DOSSIER_RAW = BASE_DIR / "data" / "raw"
DOSSIER_PROCESSED = BASE_DIR / "data" / "processed"
DOSSIER_RAPPORTS = BASE_DIR / "rapports"

# Créer automatiquement les dossiers.
for dossier in (
    DOSSIER_RAW,
    DOSSIER_PROCESSED,
    DOSSIER_RAPPORTS
):
    dossier.mkdir(parents=True, exist_ok=True)

# Colonnes des capteurs utilisées par les analyses.
COLONNES_CAPTEURS = [
    "temperature_c",
    "ph",
    "oxygene_dissous_mg_l"
]
