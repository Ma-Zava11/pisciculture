
# ============================================================
# JOUR 15 — CONNEXION POSTGRESQL
# Fichier : data_science/database.py
# ============================================================

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config import DATABASE_URL


# Adapter le dialecte SQLAlchemy pour psycopg 3.
# Si le backend utilise psycopg2, le remplacer
# uniquement pour cette connexion Data Science.
url = make_url(DATABASE_URL)

if url.drivername in ("postgresql", "postgresql+psycopg2"):
    url = url.set(drivername="postgresql+psycopg")

engine = create_engine(
    url,
    pool_pre_ping=True
)


def tester_connexion():
    """
    Vérifier que PostgreSQL est accessible.

    La transaction est configurée en lecture seule :
    aucun INSERT, UPDATE ou DELETE n'est autorisé.
    """

    with engine.connect() as connexion:
        with connexion.begin():
            connexion.execute(
                text("SET TRANSACTION READ ONLY")
            )

            resultat = connexion.execute(
                text("SELECT current_database()")
            ).scalar_one()

            print(
                f"[OK] Connexion PostgreSQL : {resultat}"
            )


if __name__ == "__main__":
    tester_connexion()
