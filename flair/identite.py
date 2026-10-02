"""Identification des visiteurs par Clerk.

Clerk affiche l'ecran de connexion (adresse et mot de passe), envoie le
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
from urllib.parse import urlparse

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import TokenVerificationError, VerifyTokenOptions
from clerk_backend_api.security.verifytoken import verify_token

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


# --------------------------------------------------------------------------
# Lecture du jeton de session
# --------------------------------------------------------------------------
#
# On ne passe pas par `authenticate_request` du SDK : il lit les cookies avec
# SimpleCookie et ne garde que le premier `__session*` trouve. Deux defauts
# observes en pratique :
#   - un seul cookie au format inattendu (valeur JSON, virgule…) pose par un
#     autre site du domaine fait abandonner TOUT l'en-tete : aucune session lue ;
#   - un ancien cookie de l'instance Clerk de developpement, reste dans le
#     navigateur des premiers testeurs, est lu a la place du bon, et rejete.
# Ici, chaque cookie `__session*` est examine, et le premier valable l'emporte.


def _contenu(jeton: str) -> dict:
    """Contenu d'un JWT, lu SANS verifier la signature : ne sert qu'au tri."""
    try:
        partie = jeton.split(".")[1]
        partie += "=" * (-len(partie) % 4)
        return json.loads(base64.urlsafe_b64decode(partie))
    except Exception:
        return {}


def jetons_candidats(entete_cookie: str, entete_auth: str = "") -> list[tuple[str, str]]:
    """Tous les jetons de session de la requete, dans l'ordre recu, doublons compris."""
    jetons: list[tuple[str, str]] = []
    if entete_auth.startswith("Bearer "):
        jetons.append(("Authorization", entete_auth[7:].strip()))
    for morceau in (entete_cookie or "").split(";"):
        nom, signe, valeur = morceau.strip().partition("=")
        valeur = valeur.strip().strip('"')
        if signe and nom.startswith("__session") and valeur.count(".") == 2:
            jetons.append((nom, valeur))
    return jetons


def emis_par_cette_instance(jeton: str) -> bool:
    """Ecarte d'emblee, sans appel reseau, un jeton emis par une autre instance."""
    emetteur = str(_contenu(jeton).get("iss") or "")
    return not emetteur or urlparse(emetteur).hostname == HOTE


def _verifier(jeton: str) -> dict:
    """Signature, expiration et origine (`azp`) verifiees par le SDK Clerk."""
    return verify_token(jeton, VerifyTokenOptions(
        secret_key=CLE_SECRETE, authorized_parties=[BASE_URL]))


def visiteur(request) -> Visiteur | None:
    """Le visiteur connecte, ou None si la requete ne porte aucune session valide."""
    if not est_configure():
        return None
    candidats = jetons_candidats(request.headers.get("cookie", ""),
                                 request.headers.get("authorization", ""))
    refus: list[str] = []
    for nom, jeton in candidats:
        if not emis_par_cette_instance(jeton):
            refus.append(f"{nom} : autre instance Clerk")
            continue
        try:
            charge = _verifier(jeton)
        except TokenVerificationError as erreur:
            refus.append(f"{nom} : {erreur.reason.name}")
            continue
        except Exception as erreur:
            refus.append(f"{nom} : {type(erreur).__name__}")
            continue
        identifiant = charge.get("sub")
        if identifiant:
            return Visiteur(identifiant=identifiant,
                            email=adresse_verifiee(identifiant))

    # Un jeton expire est le cas normal d'un retour apres plus d'une minute : le
    # navigateur le renouvelle et recharge. Les autres refus meritent d'etre vus
    # dans les journaux, sans jamais y ecrire le jeton lui-meme.
    anormaux = [r for r in refus if not r.endswith("TOKEN_EXPIRED")]
    if anormaux:
        print(f"[flair] session refusée — {' | '.join(anormaux)}")
    return None


# --------------------------------------------------------------------------
# Cote navigateur
# --------------------------------------------------------------------------

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
  const HOTE = __HOTE__;
  const GARDE = "flair-clerk-reprise";
  const ESSAIS_MAX = 2;
  let repriseEnCours = false;

  function attendre(selecteur) {
    return new Promise(function (resoudre) {
      (function guetter() {
        const el = document.querySelector(selecteur);
        if (el) resoudre(el); else setTimeout(guetter, 50);
      })();
    });
  }

  function pause(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function essais() {
    try { return Number(sessionStorage.getItem(GARDE) || 0); } catch (e) { return 0; }
  }
  function noterEssais(n) {
    try { sessionStorage.setItem(GARDE, String(n)); } catch (e) {}
  }

  // Le cookie __session contient-il un jeton de CETTE instance, encore
  // valable ? Les anciens cookies de l'instance de developpement sont ignores.
  function jetonPret() {
    const maintenant = Date.now() / 1000;
    return document.cookie.split(";").some(function (c) {
      const i = c.indexOf("=");
      const nom = c.slice(0, i).trim();
      const valeur = c.slice(i + 1).trim();
      if (!nom.startsWith("__session") || valeur.split(".").length !== 3) return false;
      try {
        const p = JSON.parse(atob(valeur.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
        return p.exp > maintenant + 5 && (!p.iss || new URL(p.iss).hostname === HOTE);
      } catch (e) { return false; }
    });
  }

  // Le navigateur a une session que le serveur n'a pas vue (jeton expire entre
  // deux visites, ou cookie pas encore ecrit juste apres la connexion). On
  // force un jeton neuf, on ATTEND que clerk-js l'ait ecrit dans le cookie,
  // puis seulement on recharge. Renvoie false apres deux essais infructueux.
  async function reprendreSession() {
    if (repriseEnCours) return true;
    const n = essais();
    if (n >= ESSAIS_MAX) return false;
    repriseEnCours = true;
    noterEssais(n + 1);
    try { await window.Clerk.session.getToken({ skipCache: true }); } catch (e) {}
    const limite = Date.now() + 5000;
    while (!jetonPret() && Date.now() < limite) await pause(100);
    window.location.replace(RETOUR);
    return true;
  }

  window.flairDeconnexion = async function () {
    noterEssais(0);
    try { await window.Clerk.signOut(); } catch (e) {}
    window.location.replace(RETOUR);
  };

  // Attend une variable globale posee par un script Clerk. Les balises sont en
  // `defer`, mais un reseau lent, ou une page chargee pendant un redemarrage,
  // peut les retarder ou les faire echouer : on ne suppose rien.
  function attendreGlobale(nom, delaiMs) {
    return new Promise(function (resoudre, rejeter) {
      const limite = Date.now() + delaiMs;
      (function guetter() {
        if (window[nom]) resoudre(window[nom]);
        else if (Date.now() > limite) rejeter(new Error(nom + " absent"));
        else setTimeout(guetter, 100);
      })();
    });
  }

  window.addEventListener("load", async function () {
    let ClerkUI;
    try {
      [, ClerkUI] = await Promise.all([
        attendreGlobale("Clerk", 20000),
        attendreGlobale("__internal_ClerkUICtor", 20000),
      ]);
    } catch (e) {
      console.error("[flair] scripts Clerk non chargés", e);
      if (!CONNECTE) {
        (await attendre(".clerk-etat")).textContent =
          "La connexion n'a pas pu se charger. Vérifiez votre réseau, puis rechargez la page.";
      }
      return;
    }

    let traduction;
    try {
      traduction = (await import(__TRADUCTION__)).frFR;
    } catch (e) {
      console.warn("[flair] traduction Clerk indisponible, composant en anglais", e);
    }
    await window.Clerk.load({
      ui: { ClerkUI: ClerkUI },
      localization: traduction,
    });
    if (CONNECTE) {
      noterEssais(0);
      return;
    }

    const etat = await attendre(".clerk-etat");
    if (window.Clerk.isSignedIn) {
      etat.textContent = "Reprise de votre session…";
      if (await reprendreSession()) return;
      // Le serveur refuse encore cette session apres deux jetons neufs : plutot
      // que de laisser le visiteur bloque, on la ferme et on repropose la
      // connexion. La cause exacte est ecrite dans les journaux du serveur.
      console.warn("[flair] session refusée par le serveur, reconnexion proposée");
      noterEssais(0);
      try { await window.Clerk.signOut(); } catch (e) {}
      etat.textContent = "Votre session a expiré. Merci de vous reconnecter.";
    } else {
      etat.style.display = "none";
    }
    window.Clerk.mountSignIn(await attendre(".clerk-connexion"), {
      withSignUp: true,
      forceRedirectUrl: RETOUR,
      signUpForceRedirectUrl: RETOUR,
    });
    window.Clerk.addListener(function (emission) {
      if (emission.user) reprendreSession();
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
            .replace("__HOTE__", json.dumps(HOTE))
            .replace("__TRADUCTION__", json.dumps(TRADUCTION)))
