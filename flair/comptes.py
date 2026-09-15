"""Credits d'analyse, rattaches a l'identifiant utilisateur fourni par Clerk.

La connexion (adresse, mot de passe, code par e-mail) est geree par Clerk : ce
module ne s'occupe que du decompte. Chaque visiteur connecte dispose de
CREDITS_OFFERTS analyses, sauf allocation particuliere fixee pour son adresse
dans FLAIR_CREDITS_SPECIAUX. Deux adresses internes ont des credits illimites
et voient la reponse brute de l'API.

L'adresse comparee a ces listes est celle que Clerk a verifiee : personne ne
peut obtenir ces droits en tapant simplement une adresse.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .base import MARQUEUR, curseur, utilise_postgres

CREDITS_OFFERTS = 10

ADMINS = ("leo.lorenzo2001@gmail.com", "nassim.yazi2001@gmail.com")

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    clerk_id         TEXT PRIMARY KEY,
    email            TEXT,
    credits_utilises INTEGER     NOT NULL DEFAULT 0,
    cree_le          TIMESTAMPTZ NOT NULL
)
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    clerk_id         TEXT PRIMARY KEY,
    email            TEXT,
    credits_utilises INTEGER NOT NULL DEFAULT 0,
    cree_le          TEXT    NOT NULL
)
"""


def init() -> None:
    with curseur() as c:
        c.execute(_SCHEMA_POSTGRES if utilise_postgres() else _SCHEMA_SQLITE)


def normaliser(email: str) -> str:
    return str(email or "").strip().lower()


def est_admin(email: str) -> bool:
    return normaliser(email) in ADMINS


def allocations_particulieres() -> dict[str, int]:
    """Credits accordes a certaines adresses, lus dans FLAIR_CREDITS_SPECIAUX.

    Format : "adresse:credits,adresse:credits". La liste vit dans une variable
    d'environnement plutot que dans le code : ce sont des adresses de personnes
    exterieures, elles n'ont rien a faire dans le depot.
    """
    allocations: dict[str, int] = {}
    for morceau in os.getenv("FLAIR_CREDITS_SPECIAUX", "").split(","):
        adresse, _, nombre = morceau.rpartition(":")
        adresse, nombre = normaliser(adresse), nombre.strip()
        if adresse and nombre.isdigit():
            allocations[adresse] = int(nombre)
    return allocations


def credits_alloues(email: str) -> int:
    """Nombre total d'analyses auxquelles une adresse a droit."""
    return allocations_particulieres().get(normaliser(email), CREDITS_OFFERTS)


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def _credits_de_l_ancien_compte(adresse: str) -> int:
    """Compteur laisse par l'ancien acces par lien maison (table `comptes`).

    Sans cette reprise, un visiteur ayant epuise ses dix analyses avant le
    passage a Clerk en retrouverait dix neuves en se reconnectant.
    """
    if not adresse:
        return 0
    try:
        with curseur() as c:
            c.execute(
                "SELECT credits_utilises FROM comptes"
                f" WHERE email = {MARQUEUR} AND confirme", (adresse,))
            ligne = c.fetchone()
        return int(ligne[0] or 0) if ligne else 0
    except Exception:
        return 0  # base neuve : l'ancienne table n'existe pas


def enregistrer(identifiant: str, email: str) -> None:
    """Cree la fiche au premier passage, puis tient l'adresse a jour."""
    adresse = normaliser(email)
    with curseur() as c:
        c.execute(f"SELECT 1 FROM utilisateurs WHERE clerk_id = {MARQUEUR}",
                  (identifiant,))
        if c.fetchone() is not None:
            if adresse:
                c.execute(
                    f"UPDATE utilisateurs SET email = {MARQUEUR}"
                    f" WHERE clerk_id = {MARQUEUR}", (adresse, identifiant))
            return
    anciens = _credits_de_l_ancien_compte(adresse)
    with curseur() as c:
        c.execute(
            "INSERT INTO utilisateurs (clerk_id, email, credits_utilises, cree_le)"
            f" VALUES ({MARQUEUR}, {MARQUEUR}, {MARQUEUR}, {MARQUEUR})"
            " ON CONFLICT (clerk_id) DO NOTHING",
            (identifiant, adresse, anciens, _maintenant()))


def etat(identifiant: str) -> dict:
    """Situation d'un compte : credits consommes, credits restants."""
    with curseur() as c:
        c.execute(
            "SELECT email, credits_utilises FROM utilisateurs"
            f" WHERE clerk_id = {MARQUEUR}", (identifiant,))
        ligne = c.fetchone()
    if not ligne:
        return {"existe": False, "utilises": 0, "illimite": False, "restants": 0}
    illimite = est_admin(ligne[0])
    utilises = int(ligne[1] or 0)
    return {
        "existe": True,
        "utilises": utilises,
        "illimite": illimite,
        "restants": -1 if illimite else max(0, credits_alloues(ligne[0]) - utilises),
    }


def peut_analyser(identifiant: str) -> bool:
    situation = etat(identifiant)
    return situation["existe"] and (situation["illimite"]
                                    or situation["restants"] > 0)


def consommer(identifiant: str) -> None:
    """Decompte une analyse. Sans effet sur les comptes illimites."""
    if etat(identifiant)["illimite"]:
        return
    with curseur() as c:
        c.execute(
            "UPDATE utilisateurs SET credits_utilises = credits_utilises + 1"
            f" WHERE clerk_id = {MARQUEUR}", (identifiant,))
