"""FLAIR — interface de démonstration.

Ce fichier ne fait que quatre choses :
  1. contrôler l'accès (adresse e-mail confirmée, crédits d'analyse),
  2. appeler l'API,
  3. dessiner la page,
  4. orchestrer l'attente et l'affichage du résultat.

Toute la logique de lecture de l'API vit dans flair/adapter.py.
Tout le style vit dans flair/theme.py.
Les comptes et les crédits vivent dans flair/comptes.py.
"""

import asyncio
import hashlib
import inspect
import json
import os

import httpx
from nicegui import app, events, ui

# Fait utiliser à Python le magasin de certificats du système d'exploitation.
# Indispensable derrière un antivirus qui inspecte le HTTPS (Avast, Kaspersky…)
# ou un proxy d'entreprise — cas de figure courant chez les assureurs.
# Sans cela : "CERTIFICATE_VERIFY_FAILED" à chaque appel API.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

from flair import components as fc
from flair import comptes, feedback, mail, preview, theme
from flair.adapter import build_report

print(f"[flair] base de retours : {feedback.init()}")
comptes.init()

# Adresse publique de la démo, utilisée dans le lien de confirmation.
BASE_URL = os.getenv("FLAIR_BASE_URL", "http://localhost:8080").rstrip("/")

# Secret de signature des sessions. À définir en production : sans lui, une
# reconnexion du service déconnecterait tout le monde.
SECRET_SESSION = os.getenv("FLAIR_SECRET", "flair-demo-secret-local")

API_URL = os.getenv("FLAIR_API_URL", "https://api.myflair.app/v1/analyze")
API_KEY = os.getenv("FLAIR_API_KEY", "")

# Le formulaire de retour s'affiche et s'enregistre toujours. Ce réglage décide
# seulement s'il *bloque* le dépôt d'un nouveau document tant qu'on n'a pas
# répondu. Désactivé pour les tests internes, à passer à 1 pour de vrais
# utilisateurs — c'est ce qui garantit le taux de réponse.
RETOUR_BLOQUANT = os.getenv("FLAIR_RETOUR_BLOQUANT", "0") == "1"

# Squelettes affichés pendant l'attente de la réponse (mêmes noms que l'adapter).
PENDING_LAYERS = [
    (1, "Historique & modifications", "Enregistrements successifs · différences de contenu"),
    (2, "Métadonnées", "Logiciel de création et de modification · dates"),
    (3, "2D-DOC & QR code", "Lecture de l'ancre cryptographique · recoupement"),
    (4, "Images générées par IA", "Modèle générateur · deepfake · photo d'écran"),
    (5, "Cohérence", "Recoupement des données du document par IA"),
]


async def read_upload(e: events.UploadEventArguments) -> tuple[str, bytes]:
    """Récupère (nom, octets) du fichier déposé, quelle que soit la version de NiceGUI."""
    upload = getattr(e, "file", None)
    if upload is not None:
        data = upload.read()
        if inspect.isawaitable(data):
            data = await data
        return upload.name, data
    data = e.content.read()
    if inspect.isawaitable(data):
        data = await data
    return e.name, data


async def call_flair_api(filename: str, content: bytes) -> dict:
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            API_URL,
            files={"file": (filename, content)},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        response.raise_for_status()
        return response.json()


# --------------------------------------------------------------------------
# Accès
# --------------------------------------------------------------------------

def demander_acces(saisie: str) -> tuple[bool, str]:
    """Traite la demande d'accès. Renvoie (succès, message affiché à l'écran)."""
    adresse = comptes.normaliser(saisie)
    if not comptes.est_valide(adresse):
        return False, "Cette adresse ne semble pas valide. Vérifiez la saisie."

    jeton = comptes.demander_acces(adresse)
    lien = f"{BASE_URL}/confirm?jeton={jeton}"

    if mail.envoyer_confirmation(adresse, lien):
        return True, (
            f"Un lien de confirmation vient d'être envoyé à {adresse}. "
            "Ouvrez-le pour activer vos dix analyses."
        )
    if not mail.CLE_API:
        # Développement local : aucun prestataire d'envoi n'est configuré,
        # on affiche le lien pour que le parcours reste testable.
        return True, f"Envoi non configuré. Lien de confirmation : {lien}"
    return False, (
        "L'envoi du courriel a échoué. Réessayez dans un instant ou "
        "écrivez-nous."
    )


def barre_haute() -> None:
    with ui.element("div").classes("topbar"):
        with ui.row().classes("topbar-inner w-full items-center justify-between no-wrap"):
            ui.html(theme.LOGO)
            with ui.row().classes("items-center gap-3 no-wrap"):
                with ui.element("div").classes("live-badge"):
                    ui.element("div").classes("live-dot")
                    ui.label("api.myflair.app").classes("mono text-xs").style(
                        "color:var(--ink-2)"
                    )
                with ui.link(
                    target="https://api.myflair.app/redoc", new_tab=True
                ).classes("doc-btn"):
                    ui.label("Documentation")
                    ui.label("↗").classes("doc-btn-arrow mono")


def pied_de_page() -> None:
    with ui.column().classes("footer w-full pt-5 gap-1 items-center"):
        ui.label(
            "Le document n'est jamais écrit sur le disque : ses octets restent "
            "en mémoire vive le temps de l'aperçu, puis sont libérés. Seuls "
            "l'empreinte SHA-256 et les résultats d'analyse sont conservés."
        ).classes("smallprint text-center").style("max-width:34rem")
        ui.html(theme.LOGO.replace('class="logo"', 'class="logo-footer"'))


@ui.page("/confirm")
def page_confirmation(jeton: str = ""):
    """Cible du lien envoyé par courriel : valide le jeton et ouvre la session."""
    ui.add_head_html(theme.HEAD)
    barre_haute()

    adresse = comptes.confirmer(jeton)

    with ui.column().classes("w-full max-w-4xl mx-auto px-6 pt-14 pb-6 gap-10"):
        with ui.column().classes("panel portail w-full p-8 gap-5 fade-in"):
            if adresse:
                app.storage.user["email"] = adresse
                ui.label("Adresse confirmée").classes("portail-titre")
                ui.label(
                    f"{adresse} — votre accès est ouvert. "
                    "Vous disposez de dix analyses de documents."
                    if not comptes.est_admin(adresse)
                    else f"{adresse} — accès interne, analyses illimitées."
                ).classes("hero-sub").style("max-width:34rem")
                with ui.link(target="/").classes("fb-submit portail-lien"):
                    ui.label("Accéder à la démonstration")
            else:
                ui.label("Lien non valable").classes("portail-titre")
                ui.label(
                    "Ce lien a expiré ou a été remplacé par une demande plus "
                    "récente. Redemandez un accès depuis la page d'accueil."
                ).classes("hero-sub").style("max-width:34rem")
                with ui.link(target="/").classes("fb-submit portail-lien"):
                    ui.label("Revenir à l'accueil")
        pied_de_page()


@ui.page("/")
def main_page():
    ui.add_head_html(theme.HEAD)
    ui.add_body_html(theme.CLICK_RELAY)

    barre_haute()

    email = comptes.normaliser(app.storage.user.get("email", ""))
    situation = comptes.etat(email) if email else {"confirme": False}
    admin = bool(email) and comptes.est_admin(email)

    with ui.column().classes("w-full max-w-4xl mx-auto px-6 pt-14 pb-6 gap-10"):

        with ui.column().classes("gap-4"):
            ui.label("Moteur d'analyse — démonstration").classes("eyebrow")
            ui.html("Cinq couches de détection.<br><em>Un verdict.</em>").classes(
                "hero-title"
            )
            ui.label(
                "Soumettez une pièce justificative — fiche de paie, justificatif de "
                "domicile, pièce d'identité, facture. Le moteur exécute ses couches "
                "déterministes, puis n'escalade vers l'IA que si aucune trace claire "
                "de fraude n'a été identifiée."
            ).classes("hero-sub")

        # Tant que l'adresse n'est pas confirmée, la démonstration reste fermée.
        if not situation.get("confirme"):
            fc.portail_email(demander_acces)
            pied_de_page()
            return

        credits_slot = ui.column().classes("w-full")

        def rafraichir_credits() -> None:
            etat = comptes.etat(email)
            credits_slot.clear()
            with credits_slot:
                fc.bandeau_credits(email, etat["restants"], etat["illimite"])

        rafraichir_credits()

        zone = ui.element("div").classes("dropzone")
        with zone:
            for pos in ("tl", "tr", "bl", "br"):
                ui.element("div").classes(f"corner {pos}")
            with ui.column().classes("w-full items-center gap-2"):
                ui.label("⌖").classes("dz-icon mono")
                ui.label("Glissez une pièce justificative").classes("dz-title")
                ui.label("PDF · JPEG · PNG — ou cliquez pour parcourir").classes("dz-hint")
            with ui.element("div").classes("overlay-upload"):
                upload = ui.upload(
                    auto_upload=True,
                    on_upload=lambda e: analyze(e),
                ).props('accept=".pdf,image/*" flat')

        notice = ui.label(
            "Donnez votre avis sur le verdict ci-dessous pour analyser un autre document."
        ).classes("dropzone-notice w-full")
        notice.set_visibility(False)

        doc_slot = ui.column().classes("w-full")
        verdict_slot = ui.column().classes("w-full")
        layers_slot = ui.column().classes("w-full gap-3")
        feedback_slot = ui.column().classes("w-full")
        raw_slot = ui.column().classes("w-full")

        pied_de_page()

        # ------------------------------------------------------------------
        # Orchestration
        # ------------------------------------------------------------------

        def verrouiller(actif: bool, message: str | None = None) -> None:
            """Bloque la zone de dépôt (retour attendu, ou crédits épuisés)."""
            upload.set_enabled(not actif)
            if message:
                notice.text = message
            notice.set_visibility(actif)
            if actif:
                zone.classes(add="dropzone-locked")
            else:
                zone.classes(remove="dropzone-locked")

        def epuiser() -> None:
            verrouiller(
                True,
                "Vos dix analyses ont été utilisées. Écrivez-nous pour "
                "poursuivre la démonstration.",
            )

        def show_error(message: str) -> None:
            layers_slot.clear()
            verdict_slot.clear()
            with verdict_slot:
                with ui.column().classes("panel verdict verdict-fraud w-full p-5 gap-2 fade-in"):
                    ui.label("Analyse impossible").classes("signal-title").style(
                        "color:var(--fraud)"
                    )
                    ui.label(message).classes("signal-verdict")

        def bloc_json(raw: dict) -> None:
            """Réponse brute de l'API — réservée aux accès internes."""
            if not admin:
                return
            with ui.expansion("Réponse JSON de l'API").classes(
                "panel w-full mono text-sm"
            ):
                ui.code(
                    json.dumps(raw, indent=2, ensure_ascii=False), language="json"
                ).classes("w-full")

        if not comptes.peut_analyser(email):
            epuiser()

        async def analyze(e: events.UploadEventArguments):
            filename, content = await read_upload(e)
            sha256 = hashlib.sha256(content).hexdigest()
            size_kb = len(content) / 1024
            upload.reset()

            for slot in (doc_slot, verdict_slot, layers_slot, feedback_slot, raw_slot):
                slot.clear()

            # Le contrôle des crédits se refait ici : la page a pu rester
            # ouverte pendant que le compte s'épuisait dans un autre onglet.
            if not comptes.peut_analyser(email):
                epuiser()
                show_error(
                    "Vos dix analyses ont été utilisées. Écrivez-nous pour "
                    "poursuivre la démonstration."
                )
                return

            # Aperçu : les octets restent en mémoire vive, jamais sur le disque.
            preview_url, preview_kind, preview_msg = preview.store(filename, content)

            with doc_slot:
                with ui.column().classes("panel doc-card w-full p-4 gap-3 fade-in"):
                    scan = ui.element("div").classes("scanline")
                    with ui.column().classes("gap-1"):
                        ui.label(filename).classes("mono text-sm font-medium")
                        ui.label(f"{size_kb:,.0f} Ko · SHA-256 {sha256[:20]}…").classes(
                            "mono text-xs"
                        ).style("color:var(--ink-2)")
                    ui.label("Document soumis").classes("preview-caption")
                    fc.document_preview(preview_url, preview_kind, preview_msg)

            with layers_slot:
                for number, name, subtitle in PENDING_LAYERS:
                    fc.pending_layer(number, name, subtitle)

            try:
                raw = await call_flair_api(filename, content)
            except httpx.HTTPStatusError as exc:
                scan.delete()
                show_error(
                    f"L'API a répondu {exc.response.status_code}. "
                    "Vérifiez la clé d'accès et le format du document."
                )
                return
            except Exception as exc:  # réseau, timeout, JSON invalide…
                scan.delete()
                show_error(f"Connexion à l'API impossible : {exc}")
                return

            scan.delete()

            try:
                report = build_report(raw)
            except Exception as exc:
                show_error(
                    "L'API a répondu, mais le format reçu n'est pas celui attendu "
                    f"({exc}). La réponse brute reste consultable ci-dessous."
                )
                with raw_slot:
                    bloc_json(raw)
                return

            # L'analyse a abouti : elle est journalisée et décomptée.
            analyse_id = feedback.enregistrer_analyse(
                email=email,
                nom_document=filename,
                verdict=report.verdict_label,
            )
            comptes.consommer(email)
            rafraichir_credits()

            # Couche 0 — verdict global
            with verdict_slot:
                fc.verdict_card(report)

            # Les 5 couches, révélées une à une pour l'effet de démonstration.
            layers_slot.clear()
            for layer in report.layers:
                await asyncio.sleep(0.18)
                with layers_slot:
                    fc.layer_block(layer, open_=layer.alert_count > 0)

            reste = comptes.peut_analyser(email)
            verrouiller(
                RETOUR_BLOQUANT,
                "Donnez votre avis sur le verdict ci-dessous pour analyser "
                "un autre document.",
            )
            if not reste:
                epuiser()

            with feedback_slot:
                fc.feedback_form(
                    analyse_id=analyse_id,
                    on_submit=lambda: (epuiser() if not comptes.peut_analyser(email)
                                       else verrouiller(False)),
                )

            with raw_slot:
                bloc_json(raw)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        title="FLAIR",
        favicon="🛡️",
        # FLAIR_RELOAD=1 => la page se rafraîchit toute seule quand tu modifies le code.
        reload=os.getenv("FLAIR_RELOAD", "0") == "1",
        storage_secret=SECRET_SESSION,
        show=False,
    )
