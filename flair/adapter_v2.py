"""Lecture du format d'API homogene (5 couches, verdicts en niveau de risque).

Ce lecteur est court parce que le moteur fait desormais le travail : il fournit
lui-meme les libelles, les descriptions en langage metier et un verdict a chaque
etage. Le front ne fait plus que mettre en forme.

L'ancien format reste lu par `adapter.py` : les documents analyses avant la
migration rejouent leur analyse telle qu'elle avait ete stockee.
"""

from __future__ import annotations

from .model import (CheckRow, DiffRow, Layer, MetaRow, Report, Severity, Signal,
                    State)

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
    return Signal(
        title=str(brut.get("label") or brut.get("name") or "Signal").upper(),
        state=etat,
        severity=SEVERITES.get(etat, Severity.NA),
        verdict=str(phrase or "—"),
        bullets=_puces(brut),
        details=_details(brut),
    )


def _lignes_metadonnees(signaux: list[dict]) -> list[MetaRow]:
    """La couche Metadonnees s'affiche en tableau categorie / valeur / risque."""
    lignes: list[MetaRow] = []
    for brut in signaux:
        etat = _etat(brut.get("verdict"), brut.get("skip_reason"))
        lignes.append(MetaRow(
            label=str(brut.get("label") or brut.get("name") or "—"),
            value=_valeur_tableau(brut),
            state=etat,
            note=str(brut.get("description") or "") if etat in (
                State.FRAUD, State.SUSPECT) else "",
        ))
    return lignes


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
    en_tableau = brut.get("name") == "metadata"

    signaux = [] if en_tableau else [_signal(s) for s in signaux_bruts]
    tableau = _lignes_metadonnees(signaux_bruts) if en_tableau else []
    diffs = _diffs(signaux_bruts)
    checks = _checks(signaux_bruts)

    # Le resume de la couche : le signal le plus grave, sinon le motif d'exclusion.
    candidats = [s.verdict for s in signaux if s.state == State.FRAUD]
    candidats += [s.verdict for s in signaux if s.state == State.SUSPECT]
    candidats += [r.note or f"{r.label} : {r.value}" for r in tableau
                  if r.state in (State.FRAUD, State.SUSPECT)]
    if candidats:
        resume = candidats[0]
    elif brut.get("skip_reason"):
        motif = str(brut["skip_reason"]).strip()
        resume = motif[:1].upper() + motif[1:]
    elif signaux or tableau:
        resume = "Aucune anomalie relevée sur cette couche"
    else:
        resume = str(brut.get("description") or "—")

    couche = Layer(
        number=numero,
        key=str(brut.get("name") or f"couche_{numero}"),
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
    # Le verdict de la couche est celui du moteur, pas une agregation maison.
    couche.state_override = _etat(brut.get("verdict"), brut.get("skip_reason"))
    return couche


def build_report(data: dict) -> Report:
    document = data.get("document") or {}
    couches_brutes = [c for c in (document.get("layers") or []) if isinstance(c, dict)]

    layers = [_couche(i, brut) for i, brut in enumerate(couches_brutes, start=1)]

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
