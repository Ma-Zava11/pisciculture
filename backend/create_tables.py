
"""
Création des tables PostgreSQL
Projet : Pisciculture intelligente
"""

# Importer le moteur de connexion à PostgreSQL.
from app.database.connection import engine

# Importer Base depuis le fichier qui la définit.
# Les modèles SQLAlchemy sont déclarés dans ce module.
from app.models.models import Base

# Importer l'outil d'inspection SQLAlchemy.
from sqlalchemy import inspect


def creer_tables():
    """
    Créer les tables déclarées dans les modèles SQLAlchemy.

    Les tables existantes ne seront pas supprimées.
    """

    try:
        # Récupérer les noms des tables déclarées.
        tables = list(Base.metadata.tables.keys())

        print("Tables détectées dans les modèles :")
        for table in tables:
            print(f" - {table}")

        if not tables:
            print("Aucune table détectée.")
            return

        # Créer les tables manquantes dans PostgreSQL.
        Base.metadata.create_all(bind=engine)

        print("\nCréation des tables terminée.")

        # Vérifier les tables réellement présentes.
        inspecteur = inspect(engine)
        tables_existantes = inspecteur.get_table_names()

        print("\nTables présentes dans PostgreSQL :")
        for table in tables_existantes:
            print(f" - {table}")

    except Exception as erreur:
        print(f"Erreur lors de la création : {erreur}")
        raise


if __name__ == "__main__":
    creer_tables()
