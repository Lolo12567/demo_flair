"""Briques d'interface réutilisables.

Chaque fonction dessine un morceau de page à partir du modèle de vue.
Aucune de ces fonctions ne connaît le format de l'API.
"""

from __future__ import annotations

import html

from nicegui import ui

from .model import CheckRow, DiffRow, Layer, MetaRow, Report, Severity, Signal, State

# Libellé du niveau de risque affiché dans la colonne 3 du tableau.
RISK_LABEL = {
    State.FRAUD: "Élevé",
    State.SUSPECT: "Modéré",
    State.OK: "Faible",
    State.ERROR: "Indisponible",
    State.TBU: "À venir",
    State.NA: "—",
    State.PENDING: "…",
}


def _duration(ms: int) -> str:
    """Au-delà de la seconde, les millisecondes ne se lisent plus."""
    return f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms} ms"


def _bullet_list(items: list[str]) -> None:
    """Liste à puces échappée (les valeurs viennent de l'API, jamais de confiance)."""
    rendered = "".join(f"<li>{html.escape(str(item))}</li>" for item in items)
    ui.html(f'<ul class="signal-bullets">{rendered}</ul>')

SEVERITY_CLASS = {
    State.OK: "sev-ok",
    State.SUSPECT: "sev-suspect",
    State.FRAUD: "sev-fraud",
    State.NA: "sev-na",
    State.TBU: "sev-tbu",
    State.ERROR: "sev-error",
    State.PENDING: "sev-pending",
}


def _badge_text(signal: Signal) -> str:
    """Le badge dit ce qui compte : la sévérité, ou l'échec du contrôle."""
    if signal.state == State.ERROR:
        return "Indisponible"
    if signal.state == State.TBU:
        return "À venir"
    return signal.severity.value if signal.severity != Severity.NA else "N/A"


def disclosure(label: str, *, open_: bool = False):
    """Un bloc « > Détails » repliable. Renvoie le conteneur du contenu.

    À utiliser ainsi :
        with disclosure("Détails"):
            ui.label("…")
    """
    header = ui.row().classes("disclosure-head items-center gap-2 no-wrap")
    with header:
        caret = ui.label("›").classes("caret mono")
        ui.label(label)
    body = ui.column().classes("w-full gap-0 pt-2")
    body.set_visibility(open_)

    state = {"open": open_}

    def toggle() -> None:
        state["open"] = not state["open"]
        body.set_visibility(state["open"])
        if state["open"]:
            caret.classes(add="caret-open")
        else:
            caret.classes(remove="caret-open")

    header.on("click", toggle)
    return body


def key_values(rows: list[tuple[str, str]]) -> None:
    """Petit tableau clé / valeur utilisé dans les détails."""
    for label, value in rows:
        with ui.row().classes("kv w-full no-wrap"):
            ui.label(label).classes("kv-k")
            ui.label(str(value)).classes("kv-v mono")


def signal_card(signal: Signal) -> None:
    """Le format unifié de la spec : pastille · titre · badge · verdict · détails."""
    tone = signal.state.value
    with ui.column().classes(f"signal signal-{tone} w-full gap-2"):
        with ui.row().classes("w-full items-center justify-between no-wrap gap-3"):
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.element("div").classes(f"dot dot-{tone}")
                ui.label(signal.title).classes("signal-title")
            ui.label(_badge_text(signal)).classes(
                f"sev {SEVERITY_CLASS[signal.state]}"
            )

        ui.label(signal.verdict).classes("signal-verdict")

        if signal.bullets:
            _bullet_list(signal.bullets)

        if signal.details:
            ui.element("div").classes("sep")
            with disclosure("Détails"):
                key_values(signal.details)


def meta_table(rows: list[MetaRow]) -> None:
    """Tableau à trois colonnes : catégorie · information · niveau de risque."""
    with ui.element("div").classes("mtable w-full"):
        with ui.element("div").classes("mrow mhead"):
            ui.label("Catégorie").classes("mcat")
            ui.label("Information").classes("mcat")
            ui.label("Risque").classes("mcat text-right")
        for row in rows:
            with ui.element("div").classes(f"mrow mrow-{row.state.value}"):
                ui.label(row.label).classes("mcat")
                ui.label(row.value).classes("mval")
                ui.label(RISK_LABEL[row.state]).classes(
                    f"mrisk {SEVERITY_CLASS[row.state]}"
                )
                if row.note:
                    ui.label(row.note).classes("mnote")


def diff_list(diffs: list[DiffRow]) -> None:
    """Comparaison avant / après : valeur d'origine à gauche, valeur finale à droite."""
    with ui.column().classes("w-full gap-0"):
        with ui.row().classes("difflegend w-full items-center justify-between no-wrap"):
            ui.label(f"{len(diffs)} modification(s) de contenu").classes("section-title")
            ui.label("Non rattachées aux versions par l'API").classes("layer-meta")

        for diff in diffs:
            with ui.column().classes(f"diffcard diffcard-{diff.state.value} w-full gap-2"):
                with ui.row().classes("w-full items-center justify-between no-wrap gap-3"):
                    ui.label(diff.field_label).classes("signal-title")
                    ui.label(RISK_LABEL[diff.state]).classes(
                        f"sev {SEVERITY_CLASS[diff.state]}"
                    )

                with ui.element("div").classes("diffgrid w-full"):
                    with ui.column().classes("diffside diffside-before"):
                        ui.label("Valeur d'origine").classes("difflabel")
                        ui.label(diff.before or "non détectée").classes(
                            "diffvalue" if diff.before else "diffvalue diffvalue-empty"
                        )
                    ui.label("→").classes("diffarrow mono")
                    with ui.column().classes("diffside diffside-after"):
                        ui.label("Valeur finale").classes("difflabel")
                        ui.label(diff.after or "non détectée").classes(
                            "diffvalue" if diff.after else "diffvalue diffvalue-empty"
                        )

                # `old_value: null` est ambigu côté moteur : on ne tranche pas
                # entre « champ ajouté » et « champ illisible dans la version d'origine ».
                if not diff.before or not diff.after:
                    manquant = "antérieure" if not diff.before else "finale"
                    ui.label(
                        f"Le moteur n'a renvoyé aucune valeur {manquant} : soit le "
                        "champ a été ajouté, soit il n'a pas pu être lu à ce stade. "
                        "À confirmer manuellement."
                    ).classes("diffhint")

                if diff.raw_before or diff.raw_after:
                    with disclosure("Valeurs brutes du moteur"):
                        key_values([
                            ("Avant", diff.raw_before or "(vide)"),
                            ("Après", diff.raw_after or "(vide)"),
                        ])


def check_list(checks: list[CheckRow]) -> None:
    """Recoupements : donnée portée par l'ancre à gauche, constat à droite.

    Vert quand les deux concordent, rouge sinon — le même format que les
    modifications de contenu, mais avec la couleur pilotée par le résultat.
    """
    echecs = sum(1 for c in checks if c.state != State.OK)
    with ui.column().classes("w-full gap-0"):
        with ui.row().classes("difflegend w-full items-center justify-between no-wrap"):
            ui.label(f"{len(checks)} recoupement(s)").classes("section-title")
            ui.label(
                f"{echecs} en échec" if echecs else "tous concordants"
            ).classes("layer-meta")

        for check in checks:
            tone = check.state.value
            with ui.column().classes(f"diffcard diffcard-{tone} w-full gap-2"):
                with ui.row().classes("w-full items-center justify-between no-wrap gap-3"):
                    ui.label(check.label).classes("signal-title")
                    ui.label(RISK_LABEL[check.state]).classes(
                        f"sev {SEVERITY_CLASS[check.state]}"
                    )

                with ui.element("div").classes("diffgrid w-full"):
                    with ui.column().classes("diffside diffside-before"):
                        ui.label("Dans le 2D-Doc").classes("difflabel")
                        ui.label(check.expected).classes("diffvalue")
                    ui.label("→" if check.state == State.OK else "≠").classes(
                        "diffarrow mono"
                    )
                    with ui.column().classes(f"diffside checkside-{tone}"):
                        ui.label("Sur le document").classes("difflabel")
                        ui.label(check.observed).classes(f"diffvalue checkvalue-{tone}")


def layer_block(layer: Layer, *, open_: bool = False) -> None:
    """Une couche : en-tête cliquable + cartes de signaux."""
    # Pastille de couche : vert, orange ou rouge. Sans rien à signaler (non
    # applicable, pas encore exposé par l'API), elle est verte. Seul un contrôle
    # en échec technique garde sa couleur propre, pour ne pas passer pour un
    # risque faible.
    pastille = {
        State.SUSPECT: "suspect",
        State.FRAUD: "fraud",
        State.ERROR: "error",
    }.get(layer.state, "ok")
    with ui.column().classes("panel layer w-full gap-0 fade-in"):
        entete = "layer-head" if layer.depliable else "layer-head layer-head-fixe"
        header = ui.row().classes(
            f"{entete} w-full items-center justify-between no-wrap gap-4"
        )
        with header:
            with ui.row().classes("items-center gap-4 no-wrap"):
                ui.label(f"{layer.number:02d}").classes("layer-num")
                ui.element("div").classes(f"dot dot-{pastille}")
                with ui.column().classes("gap-1"):
                    ui.label(layer.name).classes("layer-name")
                    ui.label(layer.headline).classes("layer-headline")
            with ui.row().classes("items-center gap-3 no-wrap"):
                if layer.duration_ms:
                    ui.label(_duration(layer.duration_ms)).classes("layer-meta")
                if layer.alert_count:
                    ui.label(
                        f"{layer.alert_count} "
                        + ("signaux" if layer.alert_count > 1 else "signal")
                    ).classes(f"sev {SEVERITY_CLASS[layer.state]}")
                if layer.depliable:
                    caret = ui.label("›").classes("caret mono").style(
                        "color:var(--ink-2)"
                    )

        # Sans détail à montrer, la couche s'arrête à son en-tête.
        if not layer.depliable:
            return

        body = ui.column().classes("layer-body w-full gap-3")
        with body:
            ui.label(layer.subtitle).classes("section-title")
            if layer.table:
                meta_table(layer.table)
            for signal in layer.signals:
                signal_card(signal)
            if layer.diffs:
                diff_list(layer.diffs)
            if layer.checks:
                check_list(layer.checks)
            if layer.external_api:
                ui.label(
                    "Cette couche fait appel à un service d'analyse externe."
                ).classes("layer-meta pt-1")
        body.set_visibility(open_)

        state = {"open": open_}
        if open_:
            caret.classes(add="caret-open")

        def toggle() -> None:
            state["open"] = not state["open"]
            body.set_visibility(state["open"])
            if state["open"]:
                caret.classes(add="caret-open")
            else:
                caret.classes(remove="caret-open")

        header.on("click", toggle)


def verdict_card(report: Report) -> None:
    """Couche 0 — le verdict global, en haut de page."""
    tone = report.verdict_state.value
    color = {
        State.OK: "var(--ok)",
        State.SUSPECT: "var(--suspect)",
        State.FRAUD: "var(--fraud)",
    }.get(report.verdict_state, "var(--na)")

    with ui.column().classes(f"panel verdict verdict-{tone} w-full p-6 gap-5 fade-in"):
        with ui.row().classes("w-full items-start justify-between no-wrap gap-6"):
            ui.label(report.verdict_label).classes("verdict-word").style(
                f"color:{color}"
            )
            ui.element("div").classes(f"dot dot-{tone}").style(
                "width:16px; height:16px; margin-top:10px"
            )

        # Une seule phrase, celle du moteur. Le détail par signal reste dans
        # les couches ci-dessous — le bandeau ne le répète plus.
        texte = report.summary or report.headline
        if texte:
            with ui.column().classes("engine-summary w-full gap-1"):
                ui.label("Synthèse du moteur").classes("kpi-label")
                ui.label(texte).classes("engine-summary-text")

        if report.deduplicated:
            with ui.row().classes("dedup-banner w-full items-center gap-3 no-wrap"):
                ui.label("↺").classes("mono")
                ui.label(
                    "Résultat déjà connu — ce document a été reconnu à son empreinte "
                    "SHA-256. L'analyse complète est restituée sans nouveau traitement, "
                    "aucun crédit consommé."
                ).classes("dedup-text")


def document_preview(url: str, kind: str, message: str) -> None:
    """Rendu visuel du document soumis. Rien n'est écrit sur le disque."""
    if kind == "image":
        ui.html(
            f'<div class="preview">'
            f'<img src="{html.escape(url, quote=True)}" alt="Aperçu du document analysé">'
            f"</div>"
        )
    elif kind == "pdf":
        # NiceGUI assainit le HTML passé à ui.html() et en retire les balises
        # <iframe>/<object>/<embed>. On construit donc un vrai élément NiceGUI.
        # #toolbar=0 masque la barre d'outils du lecteur PDF du navigateur.
        with ui.element("div").classes("preview preview-pdf"):
            frame = ui.element("iframe")
            frame._props["src"] = f"{url}#toolbar=0&navpanes=0"
            frame._props["title"] = "Aperçu du document analysé"
    else:
        with ui.element("div").classes("preview"):
            ui.label(message or "Aperçu indisponible").classes("preview-none")


def pending_layer(number: int, name: str, subtitle: str) -> None:
    """Squelette affiché pendant l'attente de la réponse API."""
    with ui.column().classes("panel layer w-full gap-0"):
        with ui.row().classes("layer-head w-full items-center justify-between no-wrap"):
            with ui.row().classes("items-center gap-4 no-wrap"):
                ui.label(f"{number:02d}").classes("layer-num")
                ui.element("div").classes("dot dot-pending")
                with ui.column().classes("gap-1"):
                    ui.label(name).classes("layer-name")
                    ui.label(subtitle).classes("layer-headline")
            ui.label("Analyse…").classes("sev sev-pending")


def portail_connexion() -> None:
    """Ecran d'entree : cadre dans lequel Clerk dessine sa connexion.

    Le formulaire (adresse, mot de passe, code de verification) est monte par le
    script Clerk dans `.clerk-connexion` — voir flair/identite.py. Cote Python,
    on ne pose que le cadre et le texte.
    """
    with ui.column().classes("panel portail w-full p-8 gap-5 fade-in"):
        ui.label("Accès à la démonstration").classes("portail-titre")
        ui.label(
            "Créez votre accès avec l'adresse e-mail de votre choix et un mot de "
            "passe. Vous recevrez un code par e-mail pour confirmer votre adresse, "
            "puis vous disposerez de dix analyses de documents. Pour revenir, il "
            "suffira de vous reconnecter avec la même adresse et le même mot de "
            "passe : vos crédits restants vous attendront."
        ).classes("hero-sub").style("max-width:34rem")

        ui.label("Chargement de la connexion…").classes("clerk-etat")
        ui.element("div").classes("clerk-connexion")

        ui.label(
            "Votre adresse ne sert qu'à ouvrir cet accès et à rattacher vos "
            "analyses. Aucun démarchage."
        ).classes("smallprint").style("max-width:34rem")


def portail_indisponible() -> None:
    """A la place du portail, quand les cles Clerk ne sont pas definies."""
    with ui.column().classes("panel portail w-full p-8 gap-3 fade-in"):
        ui.label("Connexion non configurée").classes("portail-titre")
        ui.label(
            "Les clés Clerk sont absentes : définissez CLERK_PUBLISHABLE_KEY et "
            "CLERK_SECRET_KEY, puis relancez le serveur."
        ).classes("portail-erreur")


def bandeau_credits(email: str, restants: int, illimite: bool,
                    sur_deconnexion) -> None:
    """Rappel discret du compte utilise, des analyses restantes, et sortie."""
    with ui.row().classes("credits w-full items-center justify-between no-wrap gap-4"):
        ui.label(email).classes("mono credits-email")
        with ui.row().classes("items-center no-wrap gap-4"):
            if illimite:
                ui.label("accès interne · analyses illimitées").classes("credits-solde")
            elif restants > 0:
                ui.label(
                    f"{restants} analyse{'s' if restants > 1 else ''} restante"
                    f"{'s' if restants > 1 else ''}"
                ).classes("credits-solde")
            else:
                ui.label("crédits épuisés").classes("credits-solde credits-vide")
            ui.button("Se déconnecter", on_click=sur_deconnexion).props(
                "flat dense no-caps").classes("credits-sortie")
