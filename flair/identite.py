"""Identification des visiteurs par Clerk.

Clerk affiche l'ecran de connexion (lien magique par e-mail), envoie le
courriel et tient la session. Ce module fait le lien cote serveur :
  1. il verifie le jeton de session que Clerk depose dans le cookie `__session`,
  2. il retrouve l'adresse verifiee rattachee a l'identifiant Clerk,
  3. il fournit les balises et le script qui chargent Clerk dans la page.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from clerk_backend_api import Clerk
from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions

CLE_PUBLIQUE = (os.getenv("CLERK_PUBLISHABLE_KEY")
                or os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")).strip()
CLE_SECRETE = os.getenv("CLERK_SECRET_KEY", "").strip()

# Adresse publique de la demo : destination apres connexion, et seule origine
# dont le serveur accepte les jetons de session.
BASE_URL = os.getenv("FLAIR_BASE_URL", "http://localhost:8080").rstrip("/")

# Versions conformes au guide « JavaScript quickstart » de Clerk.
VERSION_CLERK_JS = "6"
VERSION_CLERK_UI = "1"
# Seule la traduction francaise est chargee : 72 Ko, contre 4,9 Mo pour toutes.
TRADUCTION = "https://cdn.jsdelivr.net/npm/@clerk/localizations@4.16.1/fr-FR/+esm"


def _hote_frontend() -> str:
    """Le domaine du Frontend API Clerk est encode dans la cle publique."""
    try:
        code = CLE_PUBLIQUE.split("_", 2)[-1]
        code += "=" * (-len(code) % 4)
        return base64.b64decode(code).decode().rstrip("$")
    except Exception:
        return ""


HOTE = _hote_frontend() if CLE_PUBLIQUE else ""

_sdk: Clerk | None = None
_adresses: dict[str, str] = {}


@dataclass(frozen=True)
class Visiteur:
    identifiant: str  # "user_…", fourni par Clerk
    email: str        # adresse principale verifiee, vide si indisponible


def est_configure() -> bool:
    return bool(HOTE and CLE_SECRETE)


def resume() -> str:
    """Etat de la configuration, pour les journaux. N'affiche aucune cle."""
    if not est_configure():
        return "NON CONFIGURÉE (CLERK_PUBLISHABLE_KEY / CLERK_SECRET_KEY absentes ou illisibles)"
    return f"{HOTE} · sessions acceptées pour {BASE_URL}"


def _client() -> Clerk:
    global _sdk
    if _sdk is None:
        _sdk = Clerk(bearer_auth=CLE_SECRETE)
    return _sdk


def adresse_verifiee(identifiant: str) -> str:
    """Adresse principale du compte Clerk, seulement si elle est verifiee."""
    if identifiant in _adresses:
        return _adresses[identifiant]
    try:
        utilisateur = _client().users.get(user_id=identifiant)
    except Exception as erreur:
        print(f"[flair] adresse Clerk illisible pour {identifiant} : {erreur}")
        return ""
    adresse = ""
    for courriel in utilisateur.email_addresses:
        statut = getattr(getattr(courriel, "verification", None), "status", None)
        verifiee = str(getattr(statut, "value", statut)) == "verified"
        if courriel.id == utilisateur.primary_email_address_id and verifiee:
            adresse = courriel.email_address.strip().lower()
            break
    if adresse:
        _adresses[identifiant] = adresse
    return adresse


def visiteur(request) -> Visiteur | None:
    """Le visiteur connecte, ou None si la requete ne porte aucune session valide."""
    if not est_configure():
        return None
    try:
        etat = authenticate_request(request, AuthenticateRequestOptions(
            secret_key=CLE_SECRETE, authorized_parties=[BASE_URL]))
    except Exception as erreur:
        print(f"[flair] vérification de session impossible : {erreur}")
        return None
    if not etat.is_signed_in or not etat.payload:
        return None
    identifiant = etat.payload.get("sub")
    if not identifiant:
        return None
    return Visiteur(identifiant=identifiant, email=adresse_verifiee(identifiant))


def balises_script() -> str:
    """Chargement de Clerk par balises <script>, comme le prevoit sa documentation."""
    return f"""
<script defer crossorigin="anonymous" type="text/javascript"
  src="https://{HOTE}/npm/@clerk/ui@{VERSION_CLERK_UI}/dist/ui.browser.js"></script>
<script defer crossorigin="anonymous" type="text/javascript"
  data-clerk-publishable-key="{CLE_PUBLIQUE}"
  src="https://{HOTE}/npm/@clerk/clerk-js@{VERSION_CLERK_JS}/dist/clerk.browser.js"></script>
"""


_SCRIPT = """
<script>
(function () {
  const CONNECTE = __CONNECTE__;
  const RETOUR = __RETOUR__;
  const GARDE = "flair-clerk-rechargement";

  function attendre(selecteur) {
    return new Promise(function (resoudre) {
      (function guetter() {
        const el = document.querySelector(selecteur);
        if (el) resoudre(el); else setTimeout(guetter, 50);
      })();
    });
  }

  // Recharge la page pour que le serveur relise un cookie __session neuf.
  // Garde-fou : jamais deux fois en moins de 15 secondes, donc pas de boucle.
  function recharger() {
    let dernier = 0;
    try { dernier = Number(sessionStorage.getItem(GARDE) || 0); } catch (e) {}
    if (Date.now() - dernier < 15000) return false;
    try { sessionStorage.setItem(GARDE, String(Date.now())); } catch (e) {}
    window.location.replace(RETOUR);
    return true;
  }

  window.flairDeconnexion = async function () {
    try { await window.Clerk.signOut(); } catch (e) {}
    window.location.replace(RETOUR);
  };

  window.addEventListener("load", async function () {
    let traduction;
    try {
      traduction = (await import(__TRADUCTION__)).frFR;
    } catch (e) {
      console.warn("[flair] traduction Clerk indisponible, composant en anglais", e);
    }
    await window.Clerk.load({
      ui: { ClerkUI: window.__internal_ClerkUICtor },
      localization: traduction,
    });
    if (CONNECTE) return;

    const etat = await attendre(".clerk-etat");
    if (window.Clerk.isSignedIn) {
      // Le navigateur a une session que le serveur n'a pas vue (jeton expire
      // entre deux visites) : Clerk vient de le renouveler, on recharge.
      etat.textContent = recharger()
        ? "Reprise de votre session…"
        : "Session ouverte, mais refusée par le serveur. Vérifiez FLAIR_BASE_URL.";
      return;
    }
    etat.style.display = "none";
    window.Clerk.mountSignIn(await attendre(".clerk-connexion"), {
      withSignUp: true,
      forceRedirectUrl: RETOUR,
      signUpForceRedirectUrl: RETOUR,
    });
    window.Clerk.addListener(function (emission) {
      if (emission.user) recharger();
    }, { skipInitialEmit: true });
  });
})();
</script>
"""


def script_page(connecte: bool) -> str:
    """Script de page : charge Clerk, puis monte la connexion si besoin."""
    return (_SCRIPT
            .replace("__CONNECTE__", json.dumps(connecte))
            .replace("__RETOUR__", json.dumps(BASE_URL + "/"))
            .replace("__TRADUCTION__", json.dumps(TRADUCTION)))
