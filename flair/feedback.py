"""Recueil du retour utilisateur sur le verdict, et stockage en base.

Deux moteurs possibles, choisis automatiquement :
  - PostgreSQL si la variable DATABASE_URL est definie (cas de Railway) ;
  - un fichier SQLite local sinon, pour developper sans base.

Le schema est cree au demarrage s'il n'existe pas.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH = os.getenv("FLAIR_SQLITE_PATH", "retours.db")


@dataclass(frozen=True)
class Motif:
    code: str  # stocke en base, agregeable
    label: str  # affiche a l'utilisateur


@dataclass(frozen=True)
class GroupeMotifs:
    titre: str
    aide: str
    motifs: tuple[Motif, ...]


# Catalogue des cases a cocher, organise par nature d'erreur.
GROUPES: tuple[GroupeMotifs, ...] = (
    GroupeMotifs(
        titre="Un document frauduleux est passé",
        aide="Le moteur n'a pas vu quelque chose.",
        motifs=(
            Motif("fn_retouche", "Le document a été retouché (montant, date ou nom modifié)"),
            Motif("fn_fabrique", "Le document est entièrement fabriqué ou généré par l'IA"),
            Motif("fn_ia_partielle", "Le document est partiellement modifié par l'IA"),
            Motif("fn_incoherence", "Les données du document se contredisent"),
            Motif("fn_emetteur", "Le document ne correspond pas à l'émetteur qu'il prétend"),
        ),
    ),
    GroupeMotifs(
        titre="Un document authentique a été signalé à tort",
        aide="Le moteur a vu quelque chose qui n'en est pas.",
        motifs=(
            Motif("fp_logiciel", "Le logiciel signalé est légitime pour ce type de document"),
            Motif("fp_metadonnees", "L'absence de métadonnées est normale ici (scan, messagerie)"),
            Motif("fp_modifs", "Les modifications signalées sont anodines (signature, annotation)"),
        ),
    ),
    GroupeMotifs(
        titre="Le niveau de risque est mal calibré",
        aide="Le constat est bon, le niveau ne l'est pas.",
        motifs=(
            Motif("cal_trop_severe", "Trop sévère"),
            Motif("cal_pas_assez", "Pas assez sévère"),
        ),
    ),
)

TOUS_LES_MOTIFS = {m.code: m.label for g in GROUPES for m in g.motifs}


def type_de_document(filename: str) -> str:
    """Le type renvoye par l'API, deduit de l'extension du nom de fichier."""
    extension = str(filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
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

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS retours (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cree_le      TEXT    NOT NULL,
    nom_document TEXT    NOT NULL,
    type_document TEXT   NOT NULL,
    verdict      TEXT,
    satisfait    TEXT    NOT NULL,
    motifs       TEXT,
    justification TEXT
)
"""

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS retours (
    id            SERIAL PRIMARY KEY,
    cree_le       TIMESTAMPTZ NOT NULL,
    nom_document  TEXT        NOT NULL,
    type_document TEXT        NOT NULL,
    verdict       TEXT,
    satisfait     TEXT        NOT NULL,
    motifs        TEXT,
    justification TEXT
)
"""


def _postgres():
    """Connexion PostgreSQL, ou None si indisponible."""
    if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        return None
    try:
        import psycopg
    except ImportError:
        return None
    return psycopg.connect(DATABASE_URL)


def init() -> str:
    """Cree le schema. Renvoie le moteur reellement utilise, pour les logs."""
    connexion = _postgres()
    if connexion is not None:
        with connexion:
            with connexion.cursor() as curseur:
                curseur.execute(_SCHEMA_POSTGRES)
        connexion.close()
        return "postgresql"
    with sqlite3.connect(SQLITE_PATH) as connexion:
        connexion.execute(_SCHEMA_SQLITE)
    return f"sqlite ({SQLITE_PATH})"


def enregistrer(nom_document: str, verdict: str, satisfait: bool,
                motifs: list[str], justification: str) -> None:
    """Ajoute une ligne de retour. Ne leve jamais : un echec de base ne doit
    pas empecher la demonstration de continuer."""
    ligne = (
        datetime.now(timezone.utc).isoformat(),
        str(nom_document or ""),
        type_de_document(nom_document),
        str(verdict or ""),
        "oui" if satisfait else "non",
        ",".join(motifs) if motifs else "",
        (justification or "").strip(),
    )
    try:
        connexion = _postgres()
        if connexion is not None:
            with connexion:
                with connexion.cursor() as curseur:
                    curseur.execute(
                        "INSERT INTO retours (cree_le, nom_document, type_document,"
                        " verdict, satisfait, motifs, justification)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s)", ligne)
            connexion.close()
            return
        with sqlite3.connect(SQLITE_PATH) as connexion:
            connexion.execute(
                "INSERT INTO retours (cree_le, nom_document, type_document,"
                " verdict, satisfait, motifs, justification)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)", ligne)
    except Exception as erreur:  # base injoignable, schema absent…
        print(f"[flair] retour non enregistré : {erreur}")
