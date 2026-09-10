"""Comptes, confirmation par e-mail et credits d'analyse.

Un visiteur saisit son adresse, recoit un lien de confirmation, et dispose
ensuite de CREDITS_OFFERTS analyses. Deux adresses internes ont des credits
illimites et voient la reponse brute de l'API.

Ces deux adresses passent elles aussi par la confirmation : sans cela,
n'importe qui obtiendrait leurs privileges en tapant leur adresse.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

from .base import MARQUEUR, colonne_si_absente, curseur, utilise_postgres

CREDITS_OFFERTS = 10

ADMINS = ("leo.lorenzo2001@gmail.com", "nassim.yazi2001@gmail.com")

FORMAT_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS comptes (
    email            TEXT PRIMARY KEY,
    jeton            TEXT,
    confirme         BOOLEAN     NOT NULL DEFAULT FALSE,
    credits_utilises INTEGER     NOT NULL DEFAULT 0,
    cree_le          TIMESTAMPTZ NOT NULL,
    confirme_le      TIMESTAMPTZ
)
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS comptes (
    email            TEXT PRIMARY KEY,
    jeton            TEXT,
    confirme         INTEGER NOT NULL DEFAULT 0,
    credits_utilises INTEGER NOT NULL DEFAULT 0,
    cree_le          TEXT    NOT NULL,
    confirme_le      TEXT
)
"""


def init() -> None:
    with curseur() as c:
        c.execute(_SCHEMA_POSTGRES if utilise_postgres() else _SCHEMA_SQLITE)
    colonne_si_absente("comptes", "credits_utilises", "INTEGER DEFAULT 0")


def normaliser(email: str) -> str:
    return str(email or "").strip().lower()


def est_valide(email: str) -> bool:
    return bool(FORMAT_EMAIL.match(normaliser(email)))


def est_admin(email: str) -> bool:
    return normaliser(email) in ADMINS


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def demander_acces(email: str) -> str:
    """Cree ou met a jour le compte et renvoie un nouveau jeton de confirmation.

    Le jeton est renouvele a chaque demande : un lien ancien cesse d'etre
    valable des qu'un nouveau est envoye.
    """
    adresse = normaliser(email)
    jeton = secrets.token_urlsafe(32)
    with curseur() as c:
        if utilise_postgres():
            c.execute(
                "INSERT INTO comptes (email, jeton, confirme, credits_utilises, cree_le)"
                f" VALUES ({MARQUEUR}, {MARQUEUR}, FALSE, 0, {MARQUEUR})"
                " ON CONFLICT (email) DO UPDATE SET jeton = EXCLUDED.jeton",
                (adresse, jeton, _maintenant()))
        else:
            c.execute(
                "INSERT INTO comptes (email, jeton, confirme, credits_utilises, cree_le)"
                f" VALUES ({MARQUEUR}, {MARQUEUR}, 0, 0, {MARQUEUR})"
                " ON CONFLICT(email) DO UPDATE SET jeton = excluded.jeton",
                (adresse, jeton, _maintenant()))
    return jeton


def confirmer(jeton: str) -> str | None:
    """Valide un jeton et renvoie l'adresse confirmee, ou None s'il est inconnu."""
    if not jeton:
        return None
    with curseur() as c:
        c.execute(f"SELECT email FROM comptes WHERE jeton = {MARQUEUR}", (jeton,))
        ligne = c.fetchone()
        if not ligne:
            return None
        adresse = ligne[0]
        vrai = "TRUE" if utilise_postgres() else "1"
        c.execute(
            f"UPDATE comptes SET confirme = {vrai}, confirme_le = {MARQUEUR}"
            f" WHERE email = {MARQUEUR}", (_maintenant(), adresse))
    return adresse


def etat(email: str) -> dict:
    """Situation d'un compte : confirme, credits consommes, credits restants."""
    adresse = normaliser(email)
    illimite = est_admin(adresse)
    with curseur() as c:
        c.execute(
            f"SELECT confirme, credits_utilises FROM comptes WHERE email = {MARQUEUR}",
            (adresse,))
        ligne = c.fetchone()
    if not ligne:
        return {"existe": False, "confirme": False, "utilises": 0,
                "illimite": illimite, "restants": 0}
    utilises = int(ligne[1] or 0)
    return {
        "existe": True,
        "confirme": bool(ligne[0]),
        "utilises": utilises,
        "illimite": illimite,
        "restants": -1 if illimite else max(0, CREDITS_OFFERTS - utilises),
    }


def peut_analyser(email: str) -> bool:
    situation = etat(email)
    return situation["confirme"] and (situation["illimite"]
                                      or situation["restants"] > 0)


def consommer(email: str) -> None:
    """Decompte une analyse. Sans effet sur les comptes illimites."""
    adresse = normaliser(email)
    if est_admin(adresse):
        return
    with curseur() as c:
        c.execute(
            "UPDATE comptes SET credits_utilises = credits_utilises + 1"
            f" WHERE email = {MARQUEUR}", (adresse,))
