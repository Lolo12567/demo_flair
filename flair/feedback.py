"""Journal des analyses.

Une ligne est ecrite des le depot d'un document : qui (identifiant Clerk et
adresse), quoi, quel verdict.

Les colonnes `satisfait`, `motifs` et `justification` datent du questionnaire
de fin d'analyse, retire depuis. Elles restent en base pour ne pas perdre les
reponses deja collectees, mais plus rien ne les alimente.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .base import MARQUEUR, colonne_si_absente, curseur, moteur, utilise_postgres


def type_de_document(filename: str) -> str:
    """Le type renvoye par l'API, deduit de l'extension du nom de fichier."""
    nom = str(filename or "")
    extension = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
    if extension == "pdf":
        return "pdf"
    if extension in ("jpg", "jpeg"):
        return "jpeg"
    if extension in ("png", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif"):
        return extension
    return extension or "inconnu"


# --------------------------------------------------------------------------
# Stockage
# --------------------------------------------------------------------------

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS retours (
    id            SERIAL PRIMARY KEY,
    cree_le       TIMESTAMPTZ NOT NULL,
    clerk_id      TEXT,
    email         TEXT,
    nom_document  TEXT        NOT NULL,
    type_document TEXT        NOT NULL,
    verdict       TEXT,
    satisfait     TEXT,
    motifs        TEXT,
    justification TEXT
)
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS retours (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cree_le       TEXT NOT NULL,
    clerk_id      TEXT,
    email         TEXT,
    nom_document  TEXT NOT NULL,
    type_document TEXT NOT NULL,
    verdict       TEXT,
    satisfait     TEXT,
    motifs        TEXT,
    justification TEXT
)
"""


def init() -> str:
    """Cree le schema et renvoie le moteur utilise, pour les journaux."""
    with curseur() as c:
        c.execute(_SCHEMA_POSTGRES if utilise_postgres() else _SCHEMA_SQLITE)
    # Bases deja deployees : les colonnes email puis clerk_id n'existaient pas,
    # et `satisfait` etait obligatoire alors qu'une analyse sans retour doit
    # pouvoir exister.
    colonne_si_absente("retours", "email", "TEXT")
    colonne_si_absente("retours", "clerk_id", "TEXT")
    if utilise_postgres():
        try:
            with curseur() as c:
                c.execute("ALTER TABLE retours ALTER COLUMN satisfait DROP NOT NULL")
        except Exception:
            pass
    return moteur()


def enregistrer_analyse(identifiant: str, email: str, nom_document: str,
                        verdict: str) -> int | None:
    """Ecrit une ligne des le depot du document. Renvoie son identifiant.

    Ne leve jamais : un echec de base ne doit pas empecher la demonstration.
    """
    ligne = (
        datetime.now(timezone.utc).isoformat(),
        str(identifiant or ""),
        str(email or ""),
        str(nom_document or ""),
        type_de_document(nom_document),
        str(verdict or ""),
    )
    try:
        with curseur() as c:
            colonnes = ("cree_le, clerk_id, email, nom_document, type_document,"
                        " verdict")
            valeurs = ", ".join([MARQUEUR] * 6)
            if utilise_postgres():
                c.execute(f"INSERT INTO retours ({colonnes}) VALUES ({valeurs})"
                          " RETURNING id", ligne)
                resultat = c.fetchone()
                return int(resultat[0]) if resultat else None
            c.execute(f"INSERT INTO retours ({colonnes}) VALUES ({valeurs})", ligne)
            return int(c.lastrowid)
    except Exception as erreur:
        print(f"[flair] analyse non enregistrée : {erreur}")
        return None
