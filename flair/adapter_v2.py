"""Lecture du format d'API homogene (5 couches, verdicts en niveau de risque).

Ce lecteur est court parce que le moteur fait desormais le travail : il fournit
lui-meme les libelles, les descriptions en langage metier et un verdict a chaque
etage. Le front ne fait plus que mettre en forme.

L'ancien format reste lu par `adapter.py` : les documents analyses avant la
migration rejouent leur analyse telle qu'elle avait ete stockee.
"""

from __future__ import annotations

import unicodedata

from .model import (CheckRow, DiffRow, Layer, MetaRow, Report, Severity, Signal,
                    State, worst_state)

# --------------------------------------------------------------------------
# Identification des couches et des signaux
#
# L'API n'envoie plus systématiquement `name`. Quand il manque, on retombe sur
# le libellé normalisé. C'est un repli, pas une solution : un libellé est fait
# pour être réécrit, un identifiant non. À supprimer dès que `name` revient.
# --------------------------------------------------------------------------

CLES_PAR_LIBELLE = {
    # couches
    "historique & modifications": "revision_history",
    "metadonnees": "metadata",
    "2d-doc & qr code": "qr_2ddoc",
    "images generees par ia": "ai_generated_image",
    "coherence": "coherence",
    # signaux
    "versions du fichier": "versions",
    "modifications de contenu": "content_changes",
    "logiciel de creation": "creation_software",
    "logiciel de modification": "editing_software",
    "date de creation": "creation_date",
    "date de modification": "modification_date",
    "prise de vue": "capture",
    "date de prise de vue": "capture_date",
    "polices": "fonts",
    "coherence ia": "ai_coherence",
    "recoupement semantique": "ai_coherence",
    "empreinte de generateur": "generator_fingerprint",
    "detection statistique": "generative_model",
    "code detecte": "code_detected",
}


def _sans_accent(texte) -> str:
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    return "".join(c for c in decompose if not unicodedata.combining(c)).strip().lower()


def _cle(brut: dict) -> str:
    """Identifiant stable d'une couche ou d'un signal."""
    nom = str(brut.get("name") or "").strip().lower()
    if nom:
        return nom
    return CLES_PAR_LIBELLE.get(_sans_accent(brut.get("label")), "")

# Verdict renvoye par l'API -> etat affiche.
ETATS = {
    "high": State.FRAUD,
    "critical": State.FRAUD,
    "moderate": State.SUSPECT,
    "medium": State.SUSPECT,
    "low": State.OK,
    "pass": State.OK,
    "na": State.NA,
    "error": State.ERROR,
}

SEVERITES = {
    State.FRAUD: Severity.HIGH,
    State.SUSPECT: Severity.MEDIUM,
    State.OK: Severity.LOW,
    State.NA: Severity.NA,
    State.ERROR: Severity.NA,
    State.TBU: Severity.NA,
}

VERDICTS_DOCUMENT = {
    "high": "Risque élevé",
    "critical": "Risque élevé",
    "moderate": "Risque modéré",
    "medium": "Risque modéré",
    "needs_review": "Risque modéré",
    "low": "Risque faible",
    "clean": "Risque faible",
}

# Reformulations : quelques codes meritent une phrase plus parlante, ou un
# niveau de risque que le moteur ne leur donne pas encore.
#   code -> (etat impose ou None pour garder celui de l'API, phrase affichee)
REFORMULATIONS: dict[str, tuple[State | None, str]] = {
    "qr_without_2ddoc": (
        State.SUSPECT,
        "Un code est présent sur le document, mais il n'est pas lisible comme "
        "2D-Doc — rien ne permet d'en vérifier la signature.",
    ),
}

# Couche Métadonnées : liste blanche, dans l'ordre d'affichage du tableau.
# Tout le reste (polices, dimensions, format) est écarté.
METADONNEES_CONSERVEES = (
    "creation_software", "editing_software", "creation_date", "modification_date",
    "capture", "capture_date",
)

# Les deux dernières lignes sont purement informatives : elles renseignent
# l'appareil et la date de la photo quand ils existent. Leur absence ne prouve
# rien — un PDF ou un scan n'en a jamais — donc elles ne s'affichent jamais en
# alerte, quel que soit le verdict du moteur.
METADONNEES_INFORMATIVES = {
    "capture": "Appareil (photo)",
    "capture_date": "Date de la photo",
}

# Outils de conversion, de fusion ou d'édition PDF. Leur présence sur un
# document justificatif est signalée en modéré. Tout autre logiciel — même
# inconnu du moteur — n'est pas signalé : une liste d'éditeurs légitimes est
# par nature incomplète, et chaque oubli produirait une fausse alerte.
LOGICIELS_SIGNALES = (
    "ilovepdf", "smallpdf", "pdf24", "nitro", "foxit", "libreoffice",
    "google docs", "canva", "cutepdf", "img2pdf",
    # autres outils de la même famille
    "sejda", "pdfescape", "soda pdf", "sodapdf", "pdfsam", "pdfelement",
    "pdftk", "pdfcreator", "dopdf", "bullzip", "print to pdf",
)

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")


def _date_lisible(valeur) -> str | None:
    """« 2026-05-23T08:54:58 » -> « 23 mai 2026 à 08:54 ».

    Accepte aussi le format PDF (« D:20260523085458+02'00' »). Renvoie None si
    la valeur n'est pas une date plausible, pour ne rien inventer.
    """
    chiffres = "".join(c for c in str(valeur or "") if c.isdigit())
    if len(chiffres) < 8:
        return None
    try:
        annee, mois, jour = int(chiffres[0:4]), int(chiffres[4:6]), int(chiffres[6:8])
    except ValueError:
        return None
    if not (1 <= mois <= 12 and 1 <= jour <= 31 and 1900 <= annee <= 2200):
        return None
    date = f"{jour} {MOIS[mois - 1]} {annee}"
    if len(chiffres) >= 12:
        heure, minute = int(chiffres[8:10]), int(chiffres[10:12])
        if heure < 24 and minute < 60:
            return f"{date} à {heure:02d}:{minute:02d}"
    return date


def _nom_logiciel(valeur) -> str:
    """Allège les mentions de copyright, qui noient le nom du logiciel."""
    texte = " ".join(str(valeur or "").split())
    for separateur in (" - Copyright", " Copyright", " ©", " (c)", " (C)"):
        position = texte.find(separateur)
        if position > 0:
            texte = texte[:position]
    return texte.strip(" -,;") or str(valeur or "")


def _appareil(brut: dict) -> str:
    """Marque et modèle de l'appareil ayant pris la photo, s'ils sont connus."""
    if brut.get("value"):
        return _txt(brut["value"])
    details = brut.get("details") or {}
    morceaux = [str(details[cle]) for cle in ("camera_make", "camera_model")
                if details.get(cle)]
    return " ".join(morceaux) if morceaux else "non renseigné"


def _etat_logiciel(valeur, etat_api: State, phrase_api: str) -> tuple[State, str]:
    """Niveau de risque d'un logiciel.

    Une alerte forte du moteur (Photoshop, GIMP…) est conservée telle quelle.
    En revanche son « logiciel non reconnu », qui n'est qu'une absence de
    preuve, est remplacé par notre liste d'outils de conversion PDF : un
    éditeur inconnu ne doit pas déclencher d'alerte.
    """
    if etat_api == State.FRAUD:
        return etat_api, phrase_api

    minuscules = _sans_accent(valeur)
    for motif in LOGICIELS_SIGNALES:
        if motif in minuscules:
            return State.SUSPECT, ("Outil de conversion ou d'édition PDF : un "
                                   "document officiel est produit par le système "
                                   "de gestion de son émetteur.")
    return State.OK, ""

MARQUEURS_ECHEC = (
    "indisponible", "non parsable", "unparsable", "erreur", "error",
    "échec", "echec", "failed", "timeout", "exception", "unavailable",
)


def est_format_v2(data: dict) -> bool:
    """Reconnait le nouveau format : couches porteuses d'un `label` et de
    `signals` sous forme de liste."""
    for couche in ((data.get("document") or {}).get("layers") or []):
        if isinstance(couche, dict) and (
            couche.get("label") or isinstance(couche.get("signals"), list)
        ):
            return True
    return False


def _echec(motif) -> bool:
    return bool(motif) and any(m in str(motif).lower() for m in MARQUEURS_ECHEC)


def _etat(verdict, motif=None) -> State:
    if _echec(motif):
        return State.ERROR
    return ETATS.get(str(verdict or "").lower(), State.NA)


def _txt(valeur, defaut="—") -> str:
    if valeur is None or valeur == "":
        return defaut
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, (list, tuple)):
        return " × ".join(str(v) for v in valeur)
    return str(valeur)


def _details(signal: dict) -> list[tuple[str, str]]:
    """Le bloc `details`, aplati en lignes lisibles. `evidence` en est exclu :
    il alimente les puces, pas le tableau."""
    brut = signal.get("details")
    lignes: list[tuple[str, str]] = []
    if isinstance(brut, dict):
        for cle, valeur in brut.items():
            if cle == "evidence":
                continue
            lisible = str(cle).replace("_", " ").capitalize()
            lignes.append((lisible, _txt(valeur)))
    if signal.get("code"):
        lignes.append(("Code moteur", str(signal["code"])))
    return lignes


def _puces(signal: dict) -> list[str]:
    brut = signal.get("details")
    if isinstance(brut, dict) and isinstance(brut.get("evidence"), list):
        return [str(e) for e in brut["evidence"]]
    return []


def _valeur_tableau(brut: dict) -> str:
    """La colonne « information » du tableau des métadonnées.

    Tous les signaux ne portent pas de `value` : on se rabat sur le motif
    d'exclusion, puis sur un condensé des `details`.
    """
    if brut.get("value") not in (None, ""):
        return _txt(brut["value"])
    if brut.get("skip_reason"):
        return str(brut["skip_reason"])
    details = brut.get("details")
    if isinstance(details, dict):
        renseignes = [
            f"{str(cle).replace('_', ' ')} : {_txt(valeur)}"
            for cle, valeur in details.items()
            if valeur not in (None, "", False) and cle != "evidence"
        ]
        if renseignes:
            return " · ".join(renseignes[:2])
        return "aucune donnée"
    return "—"


def _signal(brut: dict) -> Signal:
    motif = brut.get("skip_reason")
    etat = _etat(brut.get("verdict"), motif)

    phrase = brut.get("description") or brut.get("value") or motif or brut.get("label")

    reformulation = REFORMULATIONS.get(str(brut.get("code") or ""))
    if reformulation:
        etat_impose, phrase = reformulation
        if etat_impose is not None:
            etat = etat_impose

    return Signal(
        title=str(brut.get("label") or brut.get("name") or "Signal").upper(),
        state=etat,
        severity=SEVERITES.get(etat, Severity.NA),
        verdict=str(phrase or "—"),
        bullets=_puces(brut),
        details=_details(brut),
    )


def _est_signal_modifications(brut: dict) -> bool:
    """Le signal qui porte les différences de contenu entre deux versions."""
    return _cle(brut) == "content_changes" or "changed_fields" in brut


def _neutraliser(signal: Signal) -> Signal:
    """Un signal de modification sans valeur d'origine n'est pas une alerte.

    Le moteur affirme que le texte a changé, mais ne fournit rien à comparer :
    on l'indique sans le compter comme anomalie, plutôt que de peindre le
    document en rouge sur une affirmation invérifiable.
    """
    signal.state = State.NA
    signal.severity = Severity.NA
    signal.verdict = ("Des modifications sont signalées, mais aucune valeur "
                      "d'origine n'est disponible : rien à comparer.")
    signal.bullets = []
    return signal


def _lignes_metadonnees(signaux: list[dict]) -> list[MetaRow]:
    """La couche Metadonnees s'affiche en tableau categorie / valeur / risque."""
    lignes: list[tuple[int, MetaRow]] = []
    for brut in signaux:
        cle = _cle(brut)
        if cle not in METADONNEES_CONSERVEES:
            continue

        etat = _etat(brut.get("verdict"), brut.get("skip_reason"))
        valeur = _valeur_tableau(brut)
        note = str(brut.get("description") or "")
        etiquette = str(brut.get("label") or brut.get("name") or "—")

        if cle in METADONNEES_INFORMATIVES:
            # Information de contexte, jamais une alerte : présente ou absente,
            # la ligne reste au vert.
            etiquette = METADONNEES_INFORMATIVES[cle]
            etat, note = State.OK, ""
            valeur = (_appareil(brut) if cle == "capture"
                      else _date_lisible(brut.get("value")) or "non renseignée")
        elif cle in ("creation_software", "editing_software") and brut.get("value"):
            # On affiche le nom du logiciel, pas le commentaire du moteur.
            valeur = _nom_logiciel(brut["value"])
            etat, note = _etat_logiciel(brut["value"], etat, note)
        elif "date" in cle or "date" in _sans_accent(brut.get("label")):
            valeur = _date_lisible(brut.get("value")) or valeur

        # Le rang suit METADONNEES_CONSERVEES : l'ordre du tableau ne dépend
        # donc pas de celui des signaux renvoyés par l'API.
        lignes.append((METADONNEES_CONSERVEES.index(cle), MetaRow(
            label=etiquette,
            value=valeur,
            state=etat,
            note=note if etat in (State.FRAUD, State.SUSPECT) else "",
        )))

    return [ligne for _, ligne in sorted(lignes, key=lambda paire: paire[0])]


def _diffs(signaux: list[dict]) -> list[DiffRow]:
    lignes: list[DiffRow] = []
    for brut in signaux:
        for champ in brut.get("changed_fields") or []:
            if not isinstance(champ, dict):
                continue
            etat = _etat(champ.get("verdict") or champ.get("severity"))
            lignes.append(DiffRow(
                field_label=str(champ.get("field_label") or champ.get("field") or "Champ"),
                before=champ.get("old_value"),
                after=champ.get("new_value"),
                state=etat,
                severity=SEVERITES.get(etat, Severity.NA),
                raw_before=str(champ.get("old_value") or ""),
                raw_after=str(champ.get("new_value") or ""),
            ))
    return lignes


def _checks(signaux: list[dict]) -> list[CheckRow]:
    lignes: list[CheckRow] = []
    for brut in signaux:
        for check in brut.get("checks") or []:
            if not isinstance(check, dict):
                continue
            etat = _etat(check.get("verdict"))
            lignes.append(CheckRow(
                label=str(check.get("field_label") or check.get("field") or "Recoupement"),
                expected=_txt(check.get("expected")),
                observed=_txt(check.get("observed"), "—"),
                state=etat,
                detail=str(check.get("description") or ""),
            ))
    return lignes


def _couche(numero: int, brut: dict) -> Layer:
    signaux_bruts = [s for s in (brut.get("signals") or []) if isinstance(s, dict)]
    cle_couche = _cle(brut)
    en_tableau = cle_couche == "metadata"

    # Métadonnées : les signaux hors liste blanche sont ignorés, pas seulement
    # masqués. Ils ne doivent donc alimenter ni le tableau, ni le résumé de la
    # couche — sinon l'en-tête annonce une raison introuvable en dessous.
    metadonnees_filtrees = False
    if en_tableau:
        retenus = [s for s in signaux_bruts if _cle(s) in METADONNEES_CONSERVEES]
        metadonnees_filtrees = len(retenus) != len(signaux_bruts)
        signaux_bruts = retenus

    # Une modification n'est montrée que si le moteur fournit la valeur d'origine
    # ET la valeur finale. Sans point de comparaison, il n'y a rien à opposer :
    # on n'affiche pas la ligne, et on ne signale pas la modification.
    diffs = [d for d in _diffs(signaux_bruts) if d.before and d.after]
    sans_comparaison = (
        any(_est_signal_modifications(s) for s in signaux_bruts) and not diffs
    )

    signaux = [] if en_tableau else [
        _neutraliser(_signal(s)) if sans_comparaison and _est_signal_modifications(s)
        else _signal(s)
        for s in signaux_bruts
    ]
    tableau = _lignes_metadonnees(signaux_bruts) if en_tableau else []
    checks = _checks(signaux_bruts)

    # Un tableau vidé par le filtrage ne doit pas laisser la couche muette.
    if en_tableau and not tableau and signaux_bruts:
        tableau = [MetaRow(
            label="Logiciel et dates",
            value="aucune métadonnée exploitable",
            state=State.NA,
        )]

    # Le résumé vient des signaux bruts, avant tout filtrage d'affichage :
    # une ligne masquée dans le tableau ne doit pas faire disparaître la raison
    # pour laquelle le moteur a classé la couche.
    def _phrase(s: dict) -> str:
        reformulation = REFORMULATIONS.get(str(s.get("code") or ""))
        if reformulation:
            return reformulation[1]
        return str(s.get("description") or s.get("value")
                   or s.get("skip_reason") or s.get("label") or "—")

    def _niveau(s: dict) -> State:
        if sans_comparaison and _est_signal_modifications(s):
            return State.NA
        reformulation = REFORMULATIONS.get(str(s.get("code") or ""))
        if reformulation and reformulation[0] is not None:
            return reformulation[0]
        return _etat(s.get("verdict"), s.get("skip_reason"))

    if en_tableau:
        # Le tableau porte l'état final des lignes (nom du logiciel, liste des
        # outils PDF) : c'est lui qui fait foi, pas le verdict brut du moteur.
        candidats = [r.note or f"{r.label} : {r.value}" for r in tableau
                     if r.state == State.FRAUD]
        candidats += [r.note or f"{r.label} : {r.value}" for r in tableau
                      if r.state == State.SUSPECT]
    else:
        candidats = [_phrase(s) for s in signaux_bruts if _niveau(s) == State.FRAUD]
        candidats += [_phrase(s) for s in signaux_bruts if _niveau(s) == State.SUSPECT]
    if candidats:
        resume = candidats[0]
    elif brut.get("skip_reason"):
        motif = str(brut["skip_reason"]).strip()
        resume = motif[:1].upper() + motif[1:]
    elif signaux_bruts:
        resume = "Aucune anomalie relevée sur cette couche"
    else:
        resume = str(brut.get("description") or "—")

    couche = Layer(
        number=numero,
        key=cle_couche or f"couche_{numero}",
        name=str(brut.get("label") or brut.get("name") or f"Couche {numero}"),
        subtitle=str(brut.get("description") or ""),
        headline=resume,
        signals=signaux,
        table=tableau,
        diffs=diffs,
        checks=checks,
        duration_ms=brut.get("duration_ms") or 0,
        external_api=bool(brut.get("external_api_call")),
        score=None,
    )
    # Le verdict de la couche est celui du moteur. Seule exception : un signal
    # reformulé auquel on impose un niveau que l'API ne lui donne pas encore
    # (cf. REFORMULATIONS) doit faire remonter la couche avec lui, sinon on
    # affiche une alerte sous un en-tête neutre.
    etat_couche = _etat(brut.get("verdict"), brut.get("skip_reason"))
    imposes = [
        REFORMULATIONS[str(s.get("code") or "")][0]
        for s in signaux_bruts
        if str(s.get("code") or "") in REFORMULATIONS
        and REFORMULATIONS[str(s.get("code") or "")][0] is not None
    ]
    if en_tableau:
        # L'état de la couche suit les lignes affichées : un signal écarté ou
        # requalifié ne doit pas laisser un en-tête coloré sans justification.
        couche.state_override = worst_state([r.state for r in tableau] or [State.NA])
    elif sans_comparaison:
        # On vient de neutraliser un signal : forcer le verdict du moteur
        # afficherait une couche rouge dont plus rien ne justifie la couleur.
        couche.state_override = worst_state(
            [_niveau(s) for s in signaux_bruts] or [State.NA])
    elif imposes:
        couche.state_override = worst_state([etat_couche, *imposes])
    else:
        couche.state_override = etat_couche
    return couche


def build_report(data: dict) -> Report:
    document = data.get("document") or {}
    couches_brutes = [c for c in (document.get("layers") or []) if isinstance(c, dict)]

    layers = [_couche(i, brut) for i, brut in enumerate(couches_brutes, start=1)]
    # Le detail de chaque couche n'est plus affiche : on n'en garde que la
    # ligne de verdict. Les signaux restent calcules, ils alimentent le resume,
    # la couleur et le compteur d'alertes.
    for couche in layers:
        couche.depliable = False

    cle = str(document.get("verdict") or "").lower()
    etiquette = VERDICTS_DOCUMENT.get(cle, "Indéterminé")
    etat_global = _etat(cle)

    alertes = [item for couche in layers for item in couche.alerts()]
    rouges = [phrase for etat, phrase in alertes if etat == State.FRAUD]
    oranges = [phrase for etat, phrase in alertes if etat == State.SUSPECT]
    erreurs = [phrase for etat, phrase in alertes if etat == State.ERROR]

    if etat_global == State.OK:
        titre = "Aucune anomalie détectée sur les couches applicables"
        raisons = (rouges + oranges + erreurs)[:4]
    elif rouges:
        titre, raisons = rouges[0], (rouges + oranges + erreurs)[1:5]
    elif oranges:
        titre, raisons = oranges[0], (oranges + erreurs)[1:5]
    elif erreurs:
        titre, raisons = erreurs[0], erreurs[1:5]
    else:
        titre, raisons = str(document.get("summary") or "Analyse terminée"), []

    doublon = bool(document.get("deduplicated"))
    duree = f"{(document.get('duration_ms') or 0) / 1000:.2f} s"
    total_signaux = sum(len(c.get("signals") or []) for c in couches_brutes)

    return Report(
        verdict_label=etiquette,
        verdict_state=etat_global,
        headline=titre,
        reasons=raisons,
        summary=str(document.get("summary") or ""),
        score=0,
        layers=layers,
        kpis=[
            ("Crédits consommés", str(document.get("credits_used", "—"))),
            ("Durée d'analyse", f"{duree} (d'origine)" if doublon else duree),
            ("Signaux analysés", str(total_signaux)),
            ("Escalade IA", "oui" if document.get("used_external_api") else "non"),
        ],
        raw=data,
        deduplicated=doublon,
    )
