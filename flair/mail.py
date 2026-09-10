"""Envoi du lien de confirmation, via Resend.

Sans RESEND_API_KEY, aucun envoi n'a lieu : la fonction le signale, et
l'interface affiche alors le lien a l'ecran. Le parcours reste testable en
local sans compte chez un prestataire.
"""

from __future__ import annotations

import os

import httpx

CLE_API = os.getenv("RESEND_API_KEY", "")
EXPEDITEUR = os.getenv("FLAIR_MAIL_FROM", "FLAIR <onboarding@resend.dev>")
URL_RESEND = "https://api.resend.com/emails"

SUJET = "Votre accès à la démonstration FLAIR"


def _corps(lien: str) -> str:
    return f"""
<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;
            font-size:15px;line-height:1.6;color:#14171C;max-width:520px">
  <p>Bonjour,</p>
  <p>Vous avez demandé un accès à la démonstration de <strong>FLAIR</strong>,
     notre moteur d'analyse de fraude documentaire.</p>
  <p style="margin:26px 0">
    <a href="{lien}"
       style="background:#1F3D8F;color:#ffffff;text-decoration:none;
              padding:12px 22px;border-radius:6px;display:inline-block">
      Confirmer mon adresse
    </a>
  </p>
  <p>Ce lien vous donne <strong>10 analyses</strong> de documents.</p>
  <p style="color:#5B626B;font-size:13px">
     Si le bouton ne fonctionne pas, copiez cette adresse dans votre
     navigateur :<br>{lien}
  </p>
  <p style="color:#5B626B;font-size:13px">
     Vous n'êtes pas à l'origine de cette demande ? Ignorez ce message.
  </p>
</div>
"""


def envoyer_confirmation(destinataire: str, lien: str) -> bool:
    """Envoie le lien. Renvoie False si l'envoi n'a pas pu se faire."""
    if not CLE_API:
        print("[flair] RESEND_API_KEY absente : lien affiché à l'écran, pas d'envoi.")
        return False
    try:
        reponse = httpx.post(
            URL_RESEND,
            headers={"Authorization": f"Bearer {CLE_API}"},
            json={
                "from": EXPEDITEUR,
                "to": [destinataire],
                "subject": SUJET,
                "html": _corps(lien),
            },
            timeout=20,
        )
        if reponse.status_code >= 300:
            print(f"[flair] envoi refusé par Resend ({reponse.status_code}) : "
                  f"{reponse.text[:200]}")
            return False
        return True
    except Exception as erreur:
        print(f"[flair] envoi impossible : {erreur}")
        return False
