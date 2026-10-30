import os
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parents[2]

ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        f"DATABASE_URL non configurée. "
        f"Vérifie le fichier : {ENV_PATH}"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

def test_connexion():
    with engine.connect() as connexion:

        resultat = connexion.execute(
            text("SELECT current_database()")
        )
        nom_base = resultat.scalar_one()

        return nom_base

if __name__ == "__main__":

    print("Test de connexion à PostgreSQL...")

    nom_base = test_connexion()

    print("Connexion réussie !")
    print("Base de données :", nom_base)
