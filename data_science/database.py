
# CONNEXION POSTGRESQL
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config import DATABASE_URL


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
