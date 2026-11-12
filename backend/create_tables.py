
"""
============================================================
PISCICULTURE INTELLIGENTE
SCRIPT DE CRÉATION DES TABLES POSTGRESQL
============================================================

Fonctionnalités :
1. Lire DATABASE_URL depuis la configuration du backend.
2. Vérifier la connexion au serveur PostgreSQL.
3. Créer la base de données si elle n'existe pas.
4. Créer les tables SQLAlchemy manquantes.
5. Conserver les tables et données existantes.
6. Afficher le résultat de la création.

IMPORTANT :
- Ce script ne supprime aucune table.
- Il ne supprime aucune donnée.
- Il ne modifie pas la structure des tables existantes.
- La création de la base nécessite les permissions PostgreSQL.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from psycopg import sql
from psycopg.errors import DuplicateDatabase

# ------------------------------------------------------------
# IMPORT DE LA CONFIGURATION EXISTANTE
# ------------------------------------------------------------

# On récupère DATABASE_URL et engine depuis le même
# fichier que celui utilisé par FastAPI.
#
# Cela évite d'avoir deux configurations différentes.
from app.database.connection import DATABASE_URL

# Importer Base et TOUS les modèles SQLAlchemy.
#
# L'import des classes permet à SQLAlchemy de connaître
# toutes les tables avant l'appel à create_all().
from app.models.models import (
    Base,
    Espece,
    Bassin,
    Appareils,
    MesureEau,
    Alerte,
    SeuilQualiteEau
)


# ------------------------------------------------------------
# 1. VÉRIFIER LA CONFIGURATION
# ------------------------------------------------------------

def verifier_configuration():
    """
    Vérifier que DATABASE_URL est correctement renseignée.

    On affiche uniquement les informations non sensibles.
    Le mot de passe n'est jamais affiché.
    """

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL n'est pas configurée."
        )

    url = make_url(DATABASE_URL)

    if not url.database:
        raise RuntimeError(
            "Le nom de la base est absent de DATABASE_URL."
        )

    print("\n=== CONFIGURATION POSTGRESQL ===")

    print(f"Serveur : {url.host}")
    print(f"Port : {url.port or 5432}")
    print(f"Utilisateur : {url.username}")
    print(f"Base cible : {url.database}")

    return url


# ------------------------------------------------------------
# 2. VÉRIFIER / CRÉER LA BASE DE DONNÉES
# ------------------------------------------------------------

def creer_base_si_absente(url):
    """
    Se connecter à la base administrative 'postgres'.

    Si la base cible n'existe pas, la créer.

    PostgreSQL interdit CREATE DATABASE à l'intérieur
    d'une transaction : AUTOCOMMIT est donc nécessaire.
    """

    nom_base = url.database

    # Connexion administrative au même serveur.
    #
    # On conserve :
    # - utilisateur
    # - mot de passe
    # - hôte
    # - port
    #
    # Seul le nom de la base est remplacé.
    url_admin = url.set(database="postgres")

    moteur_admin = create_engine(
        url_admin,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True
    )

    try:
        with moteur_admin.connect() as connexion:

            # Vérifier si la base existe.
            resultat = connexion.execute(
                text(
                    "SELECT 1 "
                    "FROM pg_database "
                    "WHERE datname = :nom"
                ),
                {"nom": nom_base}
            ).scalar_one_or_none()

            if resultat is not None:
                print(
                    f"\n[OK] La base '{nom_base}' existe."
                )
                return

            print(
                f"\n[INFO] Base '{nom_base}' absente."
            )

            print(
                "[INFO] Tentative de création..."
            )

            # Les identifiants SQL (noms de bases, tables)
            # ne peuvent pas être passés comme paramètres
            # ordinaires.
            #
            # psycopg.sql.Identifier protège correctement
            # le nom de la base.
            instruction = sql.SQL(
                "CREATE DATABASE {}"
            ).format(
                sql.Identifier(nom_base)
            )

            # Récupérer la connexion psycopg sous-jacente.
            connexion_brute = (
                connexion.connection.driver_connection
            )

            try:
                with connexion_brute.cursor() as curseur:
                    curseur.execute(instruction)

                print(
                    f"[OK] Base '{nom_base}' créée."
                )

            except DuplicateDatabase:
                # Une autre opération a pu créer la base
                # entre notre vérification et sa création.
                print(
                    f"[OK] La base '{nom_base}' existe déjà."
                )

    finally:
        moteur_admin.dispose()


# ------------------------------------------------------------
# 3. CRÉER LES TABLES
# ------------------------------------------------------------

def creer_tables():
    """
    Créer toutes les tables manquantes.

    SQLAlchemy utilise les ForeignKey pour déterminer
    automatiquement l'ordre de création des tables.
    """

    print("\n=== CRÉATION DES TABLES ===")

    # Construire un moteur vers la base cible.
    #
    # On crée ce moteur après la création éventuelle
    # de la base PostgreSQL.
    moteur = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False
    )

    try:
        # Vérifier la connexion réelle à PostgreSQL.
        with moteur.connect() as connexion:
            connexion.execute(text("SELECT 1"))

        print("[OK] Connexion PostgreSQL établie.")

        inspecteur = inspect(moteur)

        # Tables connues avant la création.
        tables_avant = set(
            inspecteur.get_table_names()
        )

        print("\nTables déjà présentes :")

        if tables_avant:
            for nom in sorted(tables_avant):
                print(f"  - {nom}")
        else:
            print("  Aucune table.")

        # ------------------------------------------------
        # CRÉATION DES TABLES MANQUANTES
        # ------------------------------------------------

        # checkfirst=True :
        # ne recrée pas les tables déjà présentes.
        #
        # Les données existantes sont conservées.
        Base.metadata.create_all(
            bind=moteur,
            checkfirst=True
        )

        # Réinspecter PostgreSQL après création.
        inspecteur = inspect(moteur)

        tables_apres = set(
            inspecteur.get_table_names()
        )

        # Tables déclarées dans models.py.
        tables_attendues = set(
            Base.metadata.tables.keys()
        )

        # Déterminer les nouvelles tables.
        nouvelles_tables = (
            tables_apres - tables_avant
        )

        # Vérifier les éventuelles tables manquantes.
        tables_manquantes = (
            tables_attendues - tables_apres
        )

        print("\n=== RÉSULTAT ===")

        print("\nTables nouvellement créées :")

        if nouvelles_tables:
            for nom in sorted(nouvelles_tables):
                print(f"  [CRÉÉE] {nom}")
        else:
            print("  Aucune nouvelle table.")

        print("\nVérification des modèles :")

        for nom in sorted(tables_attendues):

            if nom in tables_apres:
                print(f"  [OK] {nom}")
            else:
                print(f"  [MANQUANTE] {nom}")

        if tables_manquantes:
            raise RuntimeError(
                "Certaines tables n'ont pas été créées : "
                + ", ".join(sorted(tables_manquantes))
            )

        print("\n===================================")
        print("CRÉATION DES TABLES TERMINÉE")
        print("===================================")

        print(
            f"{len(tables_attendues)} tables "
            "SQLAlchemy vérifiées."
        )

    finally:
        moteur.dispose()


# ------------------------------------------------------------
# 4. EXÉCUTION PRINCIPALE
# ------------------------------------------------------------

def main():
    try:
        print("=" * 55)
        print("INITIALISATION BASE PISCICULTURE")
        print("=" * 55)

        # Vérifier DATABASE_URL.
        url = verifier_configuration()

        # Créer la base si elle est absente.
        creer_base_si_absente(url)

        # Créer toutes les tables.
        creer_tables()

        print(
            "\n[SUCCESS] Initialisation terminée."
        )

    except SQLAlchemyError as erreur:
        print("\n[ERREUR SQLALCHEMY]")
        print(erreur)
        raise

    except Exception as erreur:
        print("\n[ERREUR]")
        print(erreur)
        raise


if __name__ == "__main__":
    main()
