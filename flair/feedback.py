"""Journal des analyses et retour utilisateur sur le verdict.

Une ligne est ecrite des le depot d'un document : qui, quoi, quel verdict.
Elle est completee ensuite si la personne repond au questionnaire. Une analyse
sans retour reste donc visible, avec `satisfait` vide.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .base import MARQUEUR, colonne_si_absente, curseur, moteur, utilise_postgres


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
    # Bases deja deployees : la colonne email n'existait pas, et `satisfait`
    # etait obligatoire alors qu'une analyse sans retour doit pouvoir exister.
    colonne_si_absente("retours", "email", "TEXT")
    if utilise_postgres():
        try:
            with curseur() as c:
                c.execute("ALTER TABLE retours ALTER COLUMN satisfait DROP NOT NULL")
        except Exception:
            pass
    return moteur()


def enregistrer_analyse(email: str, nom_document: str, verdict: str) -> int | None:
    """Ecrit une ligne des le depot du document. Renvoie son identifiant.

    Ne leve jamais : un echec de base ne doit pas empecher la demonstration.
    """
    ligne = (
        datetime.now(timezone.utc).isoformat(),
        str(email or ""),
        str(nom_document or ""),
        type_de_document(nom_document),
        str(verdict or ""),
        "",
    )
    try:
        with curseur() as c:
            colonnes = ("cree_le, email, nom_document, type_document, verdict, satisfait")
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


def enregistrer_retour(identifiant: int | None, satisfait: bool,
                       motifs: list[str], justification: str) -> None:
    """Complete la ligne de l'analyse avec l'avis de la personne."""
    if identifiant is None:
        return
    try:
        with curseur() as c:
            c.execute(
                f"UPDATE retours SET satisfait = {MARQUEUR}, motifs = {MARQUEUR},"
                f" justification = {MARQUEUR} WHERE id = {MARQUEUR}",
                ("oui" if satisfait else "non",
                 ",".join(motifs) if motifs else "",
                 (justification or "").strip(),
                 identifiant))
    except Exception as erreur:
        print(f"[flair] retour non enregistré : {erreur}")
