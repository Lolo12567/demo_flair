"""Acces a la base, partage par les comptes et les retours.

PostgreSQL si DATABASE_URL est definie (cas de Railway), fichier SQLite sinon.
Les deux moteurs n'ecrivent pas les parametres de la meme facon : MARQUEUR vaut
"%s" pour Postgres et "?" pour SQLite.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH = os.getenv("FLAIR_SQLITE_PATH", "retours.db")


def utilise_postgres() -> bool:
    if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        return False
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False
    return True


MARQUEUR = "%s" if utilise_postgres() else "?"


def moteur() -> str:
    """Nom du moteur reellement utilise, pour les journaux de demarrage."""
    return "postgresql" if utilise_postgres() else f"sqlite ({SQLITE_PATH})"


@contextmanager
def curseur():
    """Curseur sur une transaction, quel que soit le moteur."""
    if utilise_postgres():
        import psycopg

        connexion = psycopg.connect(DATABASE_URL)
        try:
            with connexion:
                with connexion.cursor() as c:
                    yield c
        finally:
            connexion.close()
    else:
        connexion = sqlite3.connect(SQLITE_PATH)
        try:
            with connexion:
                yield connexion.cursor()
        finally:
            connexion.close()


def colonne_si_absente(table: str, colonne: str, type_sql: str) -> None:
    """Ajoute une colonne a une table existante, sans echouer si elle est la.

    Necessaire pour faire evoluer une base deja deployee sans la recreer.
    """
    try:
        with curseur() as c:
            if utilise_postgres():
                c.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {colonne} {type_sql}"
                )
            else:
                existantes = [ligne[1] for ligne in
                              c.execute(f"PRAGMA table_info({table})").fetchall()]
                if colonne not in existantes:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_sql}")
    except Exception as erreur:
        print(f"[flair] colonne {table}.{colonne} non ajoutée : {erreur}")
