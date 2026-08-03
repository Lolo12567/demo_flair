"""Traduction : réponse JSON de l'API FLAIR  ->  modèle de vue.

>>> C'EST LE SEUL FICHIER À MODIFIER QUAND L'API CHANGE. <<<

L'API expose 6 couches techniques :
    metadata, revision_history, hidden_content, qr_2ddoc, coherence,
    ai_generated_image

La démo en expose 5, orientées métier :
    1. Historique & modifications      <- revision_history
    2. Métadonnées                     <- metadata + hidden_content (+ polices)
    3. 2D-DOC & QR code                <- qr_2ddoc
    4. Images générées par IA          <- ai_generated_image
    5. Cohérence sémantique            <- coherence

Tout est lu défensivement (.get partout) : si un champ disparaît côté API,
l'interface affiche "non disponible" au lieu de planter. Et tout code
d'anomalie inconnu est affiché quand même (en orange), jamais ignoré.
"""

from __future__ import annotations

import re

from .model import CheckRow, DiffRow, Layer, MetaRow, Report, Severity, Signal, State
from .policy import FAMILY_BY_KEY, classify

# Libellés métier des champs renvoyés dans `changed_fields`.
FIELD_LABELS = {
    "address": "Adresse",
    "postal": "Code postal / ville",
    "city": "Ville",
    "name": "Nom",
    "firstname": "Prénom",
    "birthdate": "Date de naissance",
    "iban": "IBAN",
    "bic": "BIC",
    "amount": "Montant",
    "salary": "Salaire",
    "date": "Date",
    "siren": "SIREN",
    "siret": "SIRET",
    "email": "Adresse e-mail",
    "phone": "Téléphone",
    "employer": "Employeur",
}

# Sévérité renvoyée par le moteur -> état et badge affichés.
SEVERITY_FROM_API = {
    "high": (State.FRAUD, Severity.HIGH),
    "critical": (State.FRAUD, Severity.HIGH),
    "medium": (State.SUSPECT, Severity.MEDIUM),
    "moderate": (State.SUSPECT, Severity.MEDIUM),
    "low": (State.SUSPECT, Severity.LOW),
}


def _useful_lines(raw) -> list[str]:
    """Les lignes exploitables d'une valeur brute, sans les fragments parasites."""
    lignes = [ligne.strip() for ligne in str(raw or "").split("\n")]
    return [ligne for ligne in lignes if len(ligne) > 2]


def _clean_value(raw, depth: int = 1) -> str | None:
    """Rend lisible une valeur extraite par le moteur.

    Les valeurs arrivent sous forme de fragments multi-lignes bruités
    (« 94500 CHAMPIGNY SUR MARNE\\nCHAMPIGNY SUR\\nGERMAIN\\nM »). On garde les
    premières lignes utiles ; la valeur brute reste consultable dans les détails.
    """
    if raw is None:
        return None
    lignes = _useful_lines(raw)
    if not lignes:
        return str(raw).strip() or None
    valeur = " ".join(lignes[:depth])
    # Une première ligne très courte ne dit rien : on prend la suivante.
    if depth == 1 and len(valeur) < 8 and len(lignes) > 1:
        valeur = f"{valeur} {lignes[1]}"
    return valeur


def _clean_pair(old_raw, new_raw) -> tuple[str | None, str | None]:
    """Nettoie les deux valeurs, en gardant assez de contexte pour qu'elles diffèrent.

    Sans ça, deux valeurs qui ne se distinguent que par leurs lignes suivantes
    s'afficheraient à l'identique — et passeraient pour un bug en démonstration.
    """
    for depth in (1, 2, 3):
        avant, apres = _clean_value(old_raw, depth), _clean_value(new_raw, depth)
        if avant != apres:
            return avant, apres
    return _clean_value(old_raw, 3), _clean_value(new_raw, 3)


def _build_diffs(changed_fields) -> list[DiffRow]:
    """`changed_fields` -> lignes avant/après affichables."""
    rows: list[DiffRow] = []
    for entry in changed_fields or []:
        if not isinstance(entry, dict):
            # Format dégradé : une simple chaîne descriptive.
            rows.append(DiffRow(
                field_label="Modification",
                before=None, after=str(entry),
                state=State.SUSPECT, severity=Severity.MEDIUM,
            ))
            continue
        champ = str(entry.get("field") or "")
        state, severity = SEVERITY_FROM_API.get(
            str(entry.get("severity") or "").lower(),
            (State.SUSPECT, Severity.MEDIUM),
        )
        avant, apres = _clean_pair(entry.get("old_value"), entry.get("new_value"))
        rows.append(DiffRow(
            field_label=FIELD_LABELS.get(champ, champ.replace("_", " ").capitalize()
                                         or "Modification"),
            before=avant,
            after=apres,
            state=state,
            severity=severity,
            raw_before=str(entry.get("old_value") or ""),
            raw_after=str(entry.get("new_value") or ""),
        ))
    return rows

# --------------------------------------------------------------------------
# Réglages métier — seuils, pondérations et traductions vivent ici.
# --------------------------------------------------------------------------

# Le catalogue des logiciels vit dans flair/policy.py. Il n'est utilisé que par
# ce lecteur historique : l'ancien format ne renvoyait que des codes d'anomalie,
# sans niveau de risque. Le nouveau format fournit le sien, et le front s'y tient.

# Pondération de chaque couche API dans le score global (0-1).
LAYER_WEIGHTS = {
    "revision_history": 1.0,
    "metadata": 0.8,
    "hidden_content": 0.7,
    "qr_2ddoc": 1.0,
    "ai_generated_image": 1.0,
    "coherence": 1.0,
    "ai_coherence": 1.0,
}

# Marqueurs d'un échec technique dans un `skip_reason`. Un contrôle qui a planté
# n'est PAS un contrôle "non applicable" : il faut que ça se voie.
FAILURE_MARKERS = (
    "indisponible", "non parsable", "unparsable", "erreur", "error",
    "échec", "echec", "failed", "timeout", "exception", "unavailable",
)


def _is_failure(reason: str | None) -> bool:
    return bool(reason) and any(m in str(reason).lower() for m in FAILURE_MARKERS)

# Traduction des codes d'anomalie renvoyés par l'API en langage métier.
#   code -> (état, sévérité, phrase, explication complémentaire)
ANOMALIES: dict[str, tuple[State, Severity, str, str]] = {
    "high_risk_tool": (
        State.FRAUD, Severity.HIGH,
        "Document produit ou retouché avec un logiciel d'édition graphique",
        "Un document officiel est généré par un système de gestion, jamais par "
        "un outil de retouche d'image.",
    ),
    "editing_software_trace": (
        State.SUSPECT, Severity.MEDIUM,
        "Traces d'un logiciel d'édition laissées dans le contenu du fichier",
        "Des objets internes portent la signature d'un outil de retouche.",
    ),
    "unknown_producer": (
        State.SUSPECT, Severity.LOW,
        "Logiciel de création non reconnu",
        "Le logiciel déclaré ne figure pas parmi les émetteurs légitimes connus "
        "du moteur — sans être pour autant un outil de retouche.",
    ),
    "missing_exif": (
        State.SUSPECT, Severity.LOW,
        "Aucune métadonnée de capture (EXIF absent)",
        "Fréquent après un passage par une messagerie ou un scanner — non "
        "concluant à lui seul, mais mérite un coup d'œil.",
    ),
    "revision_summary": (
        State.SUSPECT, Severity.MEDIUM,
        "Le fichier a été enregistré plusieurs fois après sa création",
        "Chaque ré-enregistrement laisse une trace dans la structure du PDF.",
    ),
    "c2pa_manifest": (
        State.FRAUD, Severity.HIGH,
        "Manifeste C2PA détecté — le fichier déclare avoir été généré par IA",
        "Le C2PA est une signature que les générateurs d'images apposent "
        "eux-mêmes. Ce n'est pas une estimation statistique : c'est le fichier "
        "qui déclare son origine.",
    ),
    "ai_generation_signature": (
        State.FRAUD, Severity.HIGH,
        "Signature de génération par IA trouvée dans le fichier",
        "Des traces laissées par un modèle génératif subsistent dans les "
        "données internes du document.",
    ),
    "duplicate_objects": (
        State.SUSPECT, Severity.MEDIUM,
        "Objets dupliqués dans la structure du fichier",
        "Trace typique d'un contenu recopié d'une version à l'autre.",
    ),
    "xref_eof_ratio": (
        State.SUSPECT, Severity.MEDIUM,
        "Structure interne anormalement fragmentée",
        "Le rapport entre tables d'index et marqueurs de fin de fichier trahit "
        "de nombreux ré-enregistrements successifs.",
    ),
    "text_content_changed": (
        State.FRAUD, Severity.HIGH,
        "Le texte du document a été modifié après sa création",
        "Une valeur imprimée a été remplacée dans une version ultérieure du fichier.",
    ),
    "modified_after_creation": (
        State.SUSPECT, Severity.MEDIUM,
        "Date de modification postérieure à la date de création",
        "",
    ),
    "encrypted": (
        State.SUSPECT, Severity.MEDIUM,
        "Document protégé par chiffrement",
        "",
    ),
    "hidden_text": (
        State.FRAUD, Severity.HIGH,
        "Texte masqué détecté sous le contenu visible",
        "Ancienne valeur laissée sous la nouvelle — signature classique d'une retouche.",
    ),
    "overlapping_layers": (
        State.FRAUD, Severity.HIGH,
        "Calques superposés détectés",
        "Un bloc a été collé par-dessus le contenu d'origine.",
    ),
    "font_mismatch": (
        State.FRAUD, Severity.HIGH,
        "Police incohérente à l'intérieur du document",
        "Une police différente sur un montant trahit un collage.",
    ),
}


def _anomaly(code: str) -> tuple[State, Severity, str, str]:
    """Traduit un code d'anomalie. Un code inconnu reste visible, en orange."""
    known = ANOMALIES.get(code)
    if known:
        return known
    lisible = str(code).replace("_", " ")
    return (
        State.SUSPECT,
        Severity.MEDIUM,
        f"Anomalie signalée par le moteur : {lisible}",
        "Ce signal n'a pas encore de formulation métier dans l'interface.",
    )


# --------------------------------------------------------------------------
# Petits utilitaires
# --------------------------------------------------------------------------

def _pct(value) -> str:
    try:
        return f"{float(value) * 100:.0f} %"
    except (TypeError, ValueError):
        return "—"


def _txt(value, fallback: str = "non renseigné") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        return "oui" if value else "non"
    return str(value)


def _ms(value) -> str:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return "—"
    return f"{value / 1000:.1f} s" if value >= 1000 else f"{value} ms"


def _pdf_date(value) -> str:
    """Convertit une date PDF (D:20260726180000+02'00') en 26/07/2026 18:00."""
    if not value:
        return "absente"
    text = str(value)
    if text.startswith("D:"):
        text = text[2:]
    digits = "".join(c for c in text if c.isdigit())
    if len(digits) >= 12:
        return (f"{digits[6:8]}/{digits[4:6]}/{digits[0:4]} "
                f"{digits[8:10]}:{digits[10:12]}")
    if len(digits) >= 8:
        return f"{digits[6:8]}/{digits[4:6]}/{digits[0:4]}"
    return str(value)


def _api_layers(document: dict) -> dict[str, dict]:
    """La liste `layers` de l'API, transformée en dictionnaire par nom."""
    result: dict[str, dict] = {}
    for entry in document.get("layers") or []:
        if isinstance(entry, dict) and entry.get("name"):
            result[entry["name"]] = entry
    return result


def _anomaly_codes(layer: dict) -> list[str]:
    codes = ((layer or {}).get("signals") or {}).get("anomalies") or []
    return [str(c) for c in codes if c]


def _skip_reason(layer: dict, fallback: str) -> str:
    reason = (layer or {}).get("skip_reason")
    if not reason:
        return fallback
    text = str(reason).strip()
    return text[:1].upper() + text[1:]


def _subtitle(layer: dict, fallback: str) -> str:
    """L'API fournit maintenant une description par couche — on la préfère."""
    return str((layer or {}).get("description") or fallback)


def _extra_anomalies(layer: dict, consumed: set[str]) -> list[Signal]:
    """Toute anomalie non traitée par un signal nommé devient sa propre carte.

    Garantit qu'un code ajouté par l'API demain sera visible sans modifier le code.
    """
    signals = []
    for code in _anomaly_codes(layer):
        if code in consumed:
            continue
        state, severity, phrase, explication = _anomaly(code)
        signals.append(
            Signal(
                title=str(code).replace("_", " ").upper(),
                state=state,
                severity=severity,
                verdict=phrase,
                bullets=[explication] if explication else [],
                details=[("Code moteur", code)],
            )
        )
    return signals


def _layer_headline(signals: list[Signal], ok_text: str, fallback: str) -> str:
    """Résumé d'une couche : le signal le plus grave, pas le premier rencontré."""
    reds = [s for s in signals if s.state == State.FRAUD]
    if reds:
        return reds[0].verdict
    oranges = [s for s in signals if s.state == State.SUSPECT]
    if oranges:
        return oranges[0].verdict
    errors = [s for s in signals if s.state == State.ERROR]
    if errors:
        return errors[0].verdict
    if any(s.state == State.OK for s in signals):
        return ok_text
    return fallback


def _file_type(document: dict, api: dict) -> str:
    """L'API ne renvoie plus `debug.file_type` — on déduit du nom de fichier."""
    name = str(document.get("filename") or "").lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.rsplit(".", 1)[-1] in (
        "jpg", "jpeg", "png", "webp", "heic", "heif", "tif", "tiff", "bmp", "gif"
    ):
        return "image"
    # Repli : la couche revision_history dit "non applicable (image)".
    reason = str((api.get("revision_history") or {}).get("skip_reason") or "").lower()
    if "image" in reason:
        return "image"
    return "pdf" if "revision_history" in api and reason == "" else "inconnu"


# --------------------------------------------------------------------------
# Couche 1 — Historique & modifications  (revision_history)
# --------------------------------------------------------------------------

def _build_history(api: dict, file_type: str) -> Layer:
    raw = api.get("revision_history") or {}
    payload = raw.get("signals") or {}
    block = payload.get("revision_history") or {}
    revisions = block.get("revisions") or {}
    technical = block.get("technical") or {}
    codes = _anomaly_codes(raw)

    signals: list[Signal] = []
    consumed: set[str] = set()

    count = revisions.get("count")
    modified = revisions.get("modified_after_creation")
    changed_fields = revisions.get("changed_fields")

    # --- Bloc 1 : versions --------------------------------------------------
    if count is None:
        versions = Signal(
            title="VERSIONS DU FICHIER",
            state=State.NA,
            severity=Severity.NA,
            verdict=_skip_reason(raw, "Historique des versions non applicable à ce document"),
        )
    elif count <= 1:
        versions = Signal(
            title="VERSIONS DU FICHIER",
            state=State.OK,
            severity=Severity.LOW,
            verdict="Un seul enregistrement — aucune trace de ré-enregistrement",
        )
    else:
        versions = Signal(
            title="VERSIONS DU FICHIER",
            state=State.SUSPECT,
            severity=Severity.MEDIUM,
            verdict=f"{count} enregistrements successifs détectés",
            bullets=[
                "Un document officiel téléchargé puis transmis tel quel ne "
                "comporte qu'un seul enregistrement.",
            ],
        )
        consumed.add("revision_summary")
    versions.details = [
        ("Nombre d'enregistrements", _txt(count, "non déterminé")),
        ("Modifié après création", _txt(modified, "non déterminé")),
        ("Version du format PDF", _txt(technical.get("pdf_version"))),
        ("Nombre de pages", _txt(technical.get("page_count"))),
        ("Document chiffré", _txt(technical.get("encrypted"), "non")),
    ]
    signals.append(versions)

    # --- Bloc 2 : modifications de contenu ----------------------------------
    # Une modification n'est retenue que si le moteur a fourni les DEUX valeurs.
    # Sans valeur d'origine, on ne peut pas parler de modification avérée : on
    # les compte sans les afficher ni les compter comme alerte.
    tous_diffs = _build_diffs(changed_fields)
    diffs = [d for d in tous_diffs if d.before and d.after]
    incompletes = len(tous_diffs) - len(diffs)

    if diffs:
        consumed.add("text_content_changed")
        graves = sum(1 for d in diffs if d.state == State.FRAUD)
        champs = sorted({d.field_label for d in diffs})
        puces = [f"Champs touchés : {', '.join(champs)}."] if champs else []
        if incompletes:
            puces.append(
                f"{incompletes} autre(s) modification(s) signalée(s) sans valeur "
                "d'origine exploitable — non retenues."
            )
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=State.FRAUD if graves else State.SUSPECT,
            severity=Severity.HIGH if graves else Severity.MEDIUM,
            verdict=(f"{len(diffs)} modification(s) de contenu avérée(s)"
                     + (f", dont {graves} de sévérité élevée" if graves else "")),
            bullets=puces,
        )
    elif incompletes:
        consumed.add("text_content_changed")
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=State.NA,
            severity=Severity.NA,
            verdict=f"{incompletes} modification(s) signalée(s), aucune exploitable",
            bullets=[
                "Le moteur n'a renvoyé aucune valeur d'origine à comparer. "
                "Sans point de comparaison, aucune modification ne peut être "
                "considérée comme avérée.",
            ],
        )
    elif "text_content_changed" in codes:
        state, severity, phrase, explication = _anomaly("text_content_changed")
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=state,
            severity=severity,
            verdict=phrase,
            bullets=[explication] if explication else [],
        )
        consumed.add("text_content_changed")
    elif modified:
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=State.SUSPECT,
            severity=Severity.MEDIUM,
            verdict="Le fichier a été modifié après sa création, sans que le "
                    "détail des champs soit identifiable",
        )
    elif count is not None:
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=State.OK,
            severity=Severity.LOW,
            verdict="Aucune modification de contenu détectée",
        )
    else:
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=State.NA,
            severity=Severity.NA,
            verdict="Aucun historique de contenu à comparer sur ce document",
        )
    modifs.details = [
        ("Modifications avérées", str(len(diffs))),
        ("Signalées sans valeur d'origine", str(incompletes)),
        ("Rattachement aux versions", "non fourni par l'API — les modifications "
                                      "ne sont pas datées par version"),
    ]
    signals.append(modifs)

    # Les autres anomalies structurelles restent dans cette couche, mais en
    # complément du signal « versions » plutôt qu'en cartes séparées : la couche
    # ne doit parler que de versions et de modifications.
    # dict.fromkeys : dédoublonne en conservant l'ordre (l'API répète des codes).
    for code in dict.fromkeys(_anomaly_codes(raw)):
        if code in consumed:
            continue
        _state, _severity, phrase, explication = _anomaly(code)
        versions.bullets.append(phrase + (f" {explication}" if explication else ""))

    headline = _layer_headline(
        signals,
        "Aucune trace de ré-enregistrement ni de modification",
        _skip_reason(raw, "Non applicable à ce document"),
    )

    return Layer(
        number=1,
        key="revision_history",
        name="Historique & modifications",
        subtitle=_subtitle(raw, "Enregistrements successifs · différences de contenu"),
        headline=headline,
        signals=signals,
        diffs=diffs,
        duration_ms=raw.get("duration_ms") or 0,
        external_api=bool(raw.get("external_api_call")),
        score=raw.get("score"),
    )


# --------------------------------------------------------------------------
# Couche 2 — Métadonnées  (metadata + hidden_content + polices)
# --------------------------------------------------------------------------


def _pdf_digits(value) -> str:
    """Les chiffres d'une date PDF, pour comparer deux dates entre elles."""
    return "".join(c for c in str(value or "") if c.isdigit())[:14]


def _tool_row(label: str, value) -> MetaRow:
    """Ligne « logiciel », classée selon la politique de risque configurée.

    Un éditeur simplement non reconnu n'est jamais signalé : la liste des
    logiciels légitimes est par nature incomplète, et chaque oubli produisait
    une alerte sur un document authentique.
    """
    if not value:
        return MetaRow(label, "absent", State.NA)
    etat, note = classify(value)
    return MetaRow(label, str(value), etat, note)


def _build_metadata(api: dict, file_type: str) -> Layer:
    """Couche 2 — affichée sous forme de tableau catégorie / information / risque."""
    raw = api.get("metadata") or {}
    meta = ((raw.get("signals") or {}).get("metadata")) or {}
    codes = _anomaly_codes(raw)

    # Deux formes possibles selon le type de document.
    creation = meta.get("creation") or {}      # PDF
    doc_info = meta.get("document") or {}      # PDF
    capture = meta.get("capture") or {}        # image
    editing = meta.get("editing") or {}        # image

    creator = creation.get("creator")
    # Le « producteur » est réécrit par le dernier logiciel ayant touché le
    # fichier : c'est là qu'une retouche se voit, d'où le libellé « modification ».
    producer = creation.get("producer") or editing.get("software")

    ligne_creation = _tool_row("Logiciel de création", creator)
    ligne_modif = _tool_row("Logiciel de modification", producer)

    # Le moteur signale un outil à risque sans dire lequel. Si aucune famille
    # surveillée ne reconnaît les logiciels déclarés, on impute l'alerte au
    # logiciel de modification, au niveau réglé pour la retouche graphique.
    if "high_risk_tool" in codes and State.FRAUD not in (
        ligne_creation.state, ligne_modif.state
    ):
        famille = FAMILY_BY_KEY["retouche"]
        niveau = famille.default
        if niveau != State.NA and producer:
            ligne_modif = MetaRow(
                "Logiciel de modification", str(producer), niveau, famille.note
            )

    created_raw = creation.get("created_at")
    modified_raw = creation.get("modified_at") or capture.get("capture_date")

    rows: list[MetaRow] = [
        ligne_creation,
        ligne_modif,
        MetaRow(
            "Date de création",
            _pdf_date(created_raw) if created_raw else "absente",
            State.OK if created_raw else State.NA,
        ),
        # Une date de modification sans date de création n'est pas suspecte :
        # les métadonnées d'origine ont pu être simplement écrasées.
        MetaRow(
            "Date de modification",
            _pdf_date(modified_raw) if modified_raw else "absente",
            State.OK if modified_raw else State.NA,
        ),
    ]

    reds = [r for r in rows if r.state == State.FRAUD]
    if reds:
        headline = reds[0].note or f"{reds[0].label} : {reds[0].value}"
    elif any(r.state == State.OK for r in rows):
        headline = "Métadonnées cohérentes avec un document authentique"
    else:
        headline = "Aucune métadonnée exploitable sur ce document"

    return Layer(
        number=2,
        key="metadata",
        name="Métadonnées",
        subtitle=_subtitle(raw, "Logiciel · dates · auteur déclaré"),
        headline=headline,
        table=rows,
        duration_ms=raw.get("duration_ms") or 0,
        external_api=bool(raw.get("external_api_call")),
        score=raw.get("score"),
    )



# --------------------------------------------------------------------------
# Couche 3 — 2D-DOC & QR code
# --------------------------------------------------------------------------

def _parse_checks(layer: dict) -> list[CheckRow]:
    """`signals.checks` de l'API -> lignes de recoupement affichables.

    Format observé :
        {"label": "62 du 2D-Doc présent dans le document",
         "detail": "« LORENZO » trouvé", "passed": true}
    """
    rows: list[CheckRow] = []
    for check in ((layer or {}).get("signals") or {}).get("checks") or []:
        if not isinstance(check, dict):
            continue
        label = str(check.get("label") or "").strip()
        detail = str(check.get("detail") or "").strip()
        passed = check.get("passed")

        # La valeur portée par l'ancre est entre guillemets français.
        entre_guillemets = re.search(r"«\s*(.*?)\s*»", detail)
        if entre_guillemets:
            attendu = entre_guillemets.group(1)
            constate = detail.replace(entre_guillemets.group(0), "").strip()
        else:
            attendu = detail
            constate = ""
        if not constate:
            constate = "concordant" if passed else "non concordant"

        # « 62 du 2D-Doc présent dans le document » -> « Champ 62 du 2D-Doc »
        propre = re.sub(r"\s*(présent|présente)\s+dans le document\s*$", "", label)
        if re.match(r"^\d+\b", propre):
            propre = f"Champ {propre}"

        rows.append(CheckRow(
            label=propre or "Recoupement",
            expected=attendu or "—",
            observed=constate,
            state=State.OK if passed else State.FRAUD,
            detail=detail,
        ))
    return rows


def _is_twodoc_check(row: CheckRow) -> bool:
    return "2d-doc" in row.label.lower() or "2ddoc" in row.label.lower()


def _build_twodoc(api: dict, checks: list[CheckRow]) -> Layer:
    """Couche 3 — détection de l'ancre, puis recoupement champ par champ.

    Les recoupements 2D-Doc sont renvoyés par l'API dans la couche `coherence` ;
    ils sont remontés ici, où ils ont leur sens métier.
    """
    raw = api.get("qr_2ddoc") or {}
    verdict = raw.get("verdict")
    payload = raw.get("signals") or {}

    verifie = payload.get("twoddoc_verified")
    if verifie is None:
        verifie = payload.get("twodoc_verified")
    detectes = payload.get("detected_count")

    signals: list[Signal] = []

    if verdict == "fail":
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.FRAUD,
            severity=Severity.HIGH,
            verdict="2D-Doc présent mais illisible ou signature invalide",
        )
    elif verifie:
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.OK,
            severity=Severity.LOW,
            verdict="2D-Doc détecté et signature vérifiée (norme AFNOR XP Z42-105)",
        )
    elif detectes:
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.NA,
            severity=Severity.NA,
            verdict=f"{detectes} code(s) détecté(s), sans signature 2D-Doc vérifiable",
            bullets=[
                "Un QR code sans signature n'est pas anormal en soi : beaucoup "
                "de documents en portent un à usage purement informatif.",
            ],
        )
    else:
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.NA,
            severity=Severity.NA,
            verdict=_skip_reason(raw, "Aucun QR code ni 2D-Doc détecté"),
            bullets=[
                "L'absence de 2D-Doc n'est pas une fraude : un RIB ou une "
                "facture n'en comporte pas.",
            ],
        )
    detection.details = [
        ("Codes détectés", _txt(detectes, "aucun")),
        ("Signature 2D-Doc vérifiée", _txt(verifie, "non")),
    ]
    signals.append(detection)

    if checks:
        echecs = sum(1 for c in checks if c.state != State.OK)
        signals.append(
            Signal(
                title="COHÉRENCE 2D-DOC / DOCUMENT",
                state=State.FRAUD if echecs else State.OK,
                severity=Severity.HIGH if echecs else Severity.LOW,
                verdict=(f"{echecs} champ(s) du 2D-Doc ne correspondent pas au "
                         "document" if echecs
                         else f"{len(checks)} recoupement(s) concordant(s) entre "
                              "le 2D-Doc et le document"),
            )
        )

    signals.extend(_extra_anomalies(raw, set()))

    return Layer(
        number=3,
        key="qr_2ddoc",
        name="2D-DOC & QR code",
        subtitle=_subtitle(raw, "Lecture de l'ancre cryptographique · recoupement"),
        headline=_layer_headline(signals, signals[0].verdict, signals[0].verdict),
        signals=signals,
        checks=checks,
        duration_ms=raw.get("duration_ms") or 0,
        external_api=bool(raw.get("external_api_call")),
        score=raw.get("score"),
    )


# --------------------------------------------------------------------------
# Couche 4 — Images générées par IA  (ai_generated_image)
# --------------------------------------------------------------------------

GENERATOR_LABELS = {
    "ai": "Modèle IA (score global)",
    "human": "Origine humaine",
    "midjourney": "Midjourney",
    "dall_e": "DALL·E",
    "stable_diffusion": "Stable Diffusion",
    "this_person_does_not_exist": "StyleGAN — visage synthétique",
    "adobe_firefly": "Adobe Firefly",
    "flux": "FLUX",
    "four_o": "GPT-4o / images ChatGPT",
    "nano_banana": "Nano Banana (Gemini)",
}


def _c2pa_signature(payload: dict) -> dict | None:
    """Cherche une signature de provenance C2PA dans les signaux de la couche.

    Le nom du champ n'est pas encore fixé côté moteur : on essaie les
    appellations courantes. Renvoie le détail à afficher, ou None si absent.
    """
    for cle in ("c2pa", "content_credentials", "contentCredentials",
                "provenance", "manifest"):
        valeur = payload.get(cle)
        if valeur in (None, False, {}, [], ""):
            continue
        if isinstance(valeur, dict):
            # Un bloc explicite « non détecté » ne doit pas déclencher d'alerte.
            if valeur.get("is_detected") is False or valeur.get("present") is False:
                continue
            return valeur
        if valeur is True:
            return {"Signature détectée": "oui"}
        return {"Signature détectée": str(valeur)}
    return None


def _build_ai_media(api: dict, document: dict, debug: dict,
                             file_type: str) -> Layer:
    raw = api.get("ai_generated_image") or {}
    payload = raw.get("signals") or {}
    # Les preuves de provenance sont remontées par le moteur dans hidden_content.
    hidden_codes = _anomaly_codes(api.get("hidden_content") or {})
    # Le bloc debug a disparu de l'API ; on le lit encore s'il revient un jour.
    ai_block = (((debug.get("external_api") or {}).get("raw_response") or {})
                .get("report") or {}).get("ai_generated") or {}

    signals: list[Signal] = []

    # --- Génération par IA --------------------------------------------------
    is_ai = payload.get("ai_generated")
    score = raw.get("score")
    label = payload.get("label")

    if not raw and file_type == "image":
        generation = Signal(
            title="IMAGE GÉNÉRÉE PAR IA",
            state=State.NA,
            severity=Severity.NA,
            verdict="Détecteur d'images générées non exécuté sur ce document",
        )
    elif not raw:
        generation = Signal(
            title="IMAGE GÉNÉRÉE PAR IA",
            state=State.NA,
            severity=Severity.NA,
            verdict="Non applicable — cette couche ne s'exécute que sur les images",
        )
    elif is_ai is True:
        generation = Signal(
            title="IMAGE GÉNÉRÉE PAR IA",
            state=State.FRAUD,
            severity=Severity.HIGH,
            verdict=f"Image produite par un modèle génératif — confiance {_pct(score)}",
            bullets=[
                "Le document soumis n'est pas la photographie d'un objet ou "
                "d'un papier réel : il a été fabriqué.",
            ],
        )
    elif is_ai is False:
        generation = Signal(
            title="IMAGE GÉNÉRÉE PAR IA",
            state=State.OK,
            severity=Severity.LOW,
            verdict=f"Aucune trace de génération par IA — score {_pct(score)}",
        )
    else:
        generation = Signal(
            title="IMAGE GÉNÉRÉE PAR IA",
            state=State.NA,
            severity=Severity.NA,
            verdict=_skip_reason(raw, "Détection de génération par IA non applicable"),
        )

    generators = ai_block.get("generator") or {}
    ranked = sorted(
        ((k, v) for k, v in generators.items() if isinstance(v, dict)),
        key=lambda item: item[1].get("confidence") or 0,
        reverse=True,
    )
    generation.details = [("Classement du modèle", _txt(label, "non renseigné")),
                          ("Score du moteur", _pct(score))] + [
        (GENERATOR_LABELS.get(name, name), _pct(data.get("confidence")))
        for name, data in ranked
    ]
    signals.append(generation)

    # --- Signatures de provenance -------------------------------------------
    # Le moteur remonte ces preuves comme codes d'anomalie dans `hidden_content`.
    # Elles appartiennent metier a cette couche : on les y affiche.
    for code in ("c2pa_manifest", "ai_generation_signature"):
        if code not in hidden_codes:
            continue
        etat, severite, phrase, explication = _anomaly(code)
        signals.append(
            Signal(
                title=("SIGNATURE DE PROVENANCE C2PA" if code == "c2pa_manifest"
                       else "SIGNATURE DE GÉNÉRATION PAR IA"),
                state=etat,
                severity=severite,
                verdict=phrase,
                bullets=[explication] if explication else [],
                details=[("Code moteur", code),
                         ("Couche d'origine", "hidden_content")],
            )
        )

    # Champ structure, si le moteur en expose un un jour en plus des codes.
    c2pa = _c2pa_signature(payload)
    if c2pa and "c2pa_manifest" not in hidden_codes:
        signals.append(
            Signal(
                title="SIGNATURE DE PROVENANCE C2PA",
                state=State.FRAUD,
                severity=Severity.HIGH,
                verdict="Signature C2PA détectée — le fichier porte une preuve "
                        "de génération par intelligence artificielle",
                details=[(str(k), _txt(v)) for k, v in c2pa.items()],
            )
        )

    signals.extend(_extra_anomalies(raw, set()))

    headline = _layer_headline(
        signals,
        "Aucun indice de fabrication par intelligence artificielle",
        "Non applicable — cette couche ne s'exécute que sur les images",
    )

    return Layer(
        number=4,
        key="ai_generated_image",
        name="Images générées par IA",
        subtitle=_subtitle(raw, "Détection de génération par IA · signature C2PA"),
        headline=headline,
        signals=signals,
        duration_ms=raw.get("duration_ms") or 0,
        external_api=bool(raw.get("external_api_call")),
        score=score,
    )


# --------------------------------------------------------------------------
# Couche 5 — Cohérence
# --------------------------------------------------------------------------

def _inconsistencies(layer: dict) -> list[str]:
    payload = (layer or {}).get("signals") or {}
    issues = (payload.get("inconsistencies") or payload.get("issues")
              or payload.get("findings") or [])
    return [str(i.get("label") if isinstance(i, dict) else i) for i in issues]


def _build_coherence(api: dict, debug: dict, file_type: str,
                            checks: list[CheckRow] | None = None) -> Layer:
    raw = api.get("coherence") or {}
    verdict = raw.get("verdict")
    checks = checks or []

    bullets = _inconsistencies(raw)

    signals: list[Signal] = []

    # --- Recoupement par IA (couche `ai_coherence`) -------------------------
    ai_raw = api.get("ai_coherence")
    ai_bullets = _inconsistencies(ai_raw or {})
    ai_reason = (ai_raw or {}).get("skip_reason")

    if ai_raw is None and file_type == "pdf":
        vision = Signal(
            title="RECOUPEMENT PAR IA",
            state=State.NA,
            severity=Severity.NA,
            verdict="Le contrôle par IA ne s'exécute pas sur les PDF",
            bullets=[
                "Seules les images sont aujourd'hui soumises au modèle ; un PDF "
                "n'est pas analysé par ce contrôle.",
            ],
        )
    elif ai_raw is None:
        vision = Signal(
            title="RECOUPEMENT PAR IA",
            state=State.NA,
            severity=Severity.NA,
            verdict="Recoupement par IA non exécuté sur ce document",
        )
    elif ai_bullets:
        vision = Signal(
            title="RECOUPEMENT PAR IA",
            state=State.FRAUD if len(ai_bullets) >= 3 else State.SUSPECT,
            severity=Severity.HIGH if len(ai_bullets) >= 3 else Severity.MEDIUM,
            verdict=f"{len(ai_bullets)} incohérence(s) relevée(s) par l'analyse visuelle",
            bullets=ai_bullets,
        )
    elif _is_failure(ai_reason):
        vision = Signal(
            title="RECOUPEMENT PAR IA",
            state=State.ERROR,
            severity=Severity.NA,
            verdict="Le contrôle par IA n'a pas abouti — résultat indisponible",
            bullets=[
                "Le document n'a pas été écarté : il n'a simplement pas pu être "
                "recoupé par ce contrôle. Une vérification manuelle reste requise.",
            ],
        )
    elif (ai_raw or {}).get("verdict") == "pass":
        vision = Signal(
            title="RECOUPEMENT PAR IA",
            state=State.OK,
            severity=Severity.LOW,
            verdict="Aucune incohérence relevée par l'analyse visuelle du document",
        )
    else:
        vision = Signal(
            title="RECOUPEMENT PAR IA",
            state=State.NA,
            severity=Severity.NA,
            verdict=_skip_reason(ai_raw or {}, "Recoupement par IA non applicable"),
        )
    vision.details = [
        ("Durée du contrôle", _ms((ai_raw or {}).get("duration_ms"))),
        ("Appel à un service externe",
         _txt((ai_raw or {}).get("external_api_call"), "non")),
        ("Motif renvoyé par le moteur", _txt(ai_reason, "aucun")),
    ]
    signals.append(vision)

    signals.extend(_extra_anomalies(raw, set()))
    signals.extend(_extra_anomalies(ai_raw or {}, set()))

    return Layer(
        number=5,
        key="coherence",
        name="Cohérence",
        subtitle=_subtitle(raw, "Recoupement des données du document par IA"),
        headline=_layer_headline(
            signals,
            "Aucune incohérence détectée dans le contenu du document",
            vision.verdict,
        ),
        signals=signals,
        checks=checks,
        duration_ms=(raw.get("duration_ms") or 0)
        + ((ai_raw or {}).get("duration_ms") or 0),
        external_api=bool(raw.get("external_api_call"))
        or bool((ai_raw or {}).get("external_api_call")),
        score=raw.get("score") or (ai_raw or {}).get("score"),
    )


# --------------------------------------------------------------------------
# Couche 0 — verdict global
# --------------------------------------------------------------------------

VERDICT_LABELS = {
    "fraud": ("Risque élevé", State.FRAUD),
    "fraude": ("Risque élevé", State.FRAUD),
    "suspect": ("Risque modéré", State.SUSPECT),
    "suspicious": ("Risque modéré", State.SUSPECT),
    "review": ("Risque modéré", State.SUSPECT),
    "needs_review": ("Risque modéré", State.SUSPECT),
    "to_review": ("Risque modéré", State.SUSPECT),
    "inconclusive": ("Risque modéré", State.SUSPECT),
    "clean": ("Risque faible", State.OK),
    "authentic": ("Risque faible", State.OK),
    "pass": ("Risque faible", State.OK),
    "ok": ("Risque faible", State.OK),
}


def _global_score(api: dict) -> int:
    """Score indicatif 0-100 : le pire signal pondéré l'emporte."""
    worst = 0.0
    for name, layer in api.items():
        score = layer.get("score")
        if score is None:
            continue
        try:
            worst = max(worst, float(score) * LAYER_WEIGHTS.get(name, 1.0))
        except (TypeError, ValueError):
            continue
    return max(0, min(100, round(worst * 100)))


def build_report(data: dict) -> Report:
    """Point d'entrée unique. Aiguille vers le lecteur correspondant au format reçu.

    Les deux formats coexistent durablement : un document analysé avant la
    migration rejoue son analyse telle qu'elle avait été stockée, donc à
    l'ancien format, même longtemps après le déploiement du nouveau.
    """
    from . import adapter_v2

    if adapter_v2.est_format_v2(data):
        return adapter_v2.build_report(data)
    return _build_report_legacy(data)


def _build_report_legacy(data: dict) -> Report:
    """Point d'entrée : réponse brute de l'API -> objet Report affichable."""
    document = data.get("document") or {}
    debug = data.get("debug") or {}
    api = _api_layers(document)
    file_type = _file_type(document, api)

    # Les recoupements sont renvoyés par l'API dans `coherence`. Ceux qui portent
    # sur le 2D-Doc appartiennent métier à la couche 3 : on les y remonte.
    tous_checks = _parse_checks(api.get("coherence") or {})
    checks_twodoc = [c for c in tous_checks if _is_twodoc_check(c)]
    checks_autres = [c for c in tous_checks if not _is_twodoc_check(c)]

    layers = [
        _build_history(api, file_type),
        _build_metadata(api, file_type),
        _build_twodoc(api, checks_twodoc),
        _build_ai_media(api, document, debug, file_type),
        _build_coherence(api, debug, file_type, checks_autres),
    ]

    # Le detail de chaque couche n'est plus affiche : seule la ligne de verdict
    # reste. Les signaux continuent d'alimenter le resume et la couleur.
    for couche in layers:
        couche.depliable = False

    key = str(document.get("verdict") or "").lower()
    label, verdict_state = VERDICT_LABELS.get(key, ("INDÉTERMINÉ", State.NA))

    # Les alertes viennent des cartes de signaux ET des lignes de tableau.
    alerts = [item for layer in layers for item in layer.alerts()]
    reds = [phrase for state, phrase in alerts if state == State.FRAUD]
    oranges = [phrase for state, phrase in alerts if state == State.SUSPECT]
    errors = [phrase for state, phrase in alerts if state == State.ERROR]

    # La phrase suit le verdict de l'API : on ne titre pas "Risque faible" au-dessus
    # d'une phrase alarmante. Les signaux mineurs descendent en puces.
    if verdict_state == State.OK:
        headline = "Aucune anomalie détectée sur les couches applicables"
        reasons = (reds + oranges + errors)[:4]
    elif reds:
        headline = reds[0]
        reasons = (reds + oranges + errors)[1:5]
    elif oranges:
        headline = oranges[0]
        reasons = (oranges + errors)[1:5]
    elif errors:
        headline = errors[0]
        reasons = errors[1:5]
    else:
        headline = str(document.get("summary") or "Analyse terminée")
        reasons = []

    anomaly_total = sum(len(_anomaly_codes(layer)) for layer in api.values())

    deduplicated = bool(document.get("deduplicated"))
    duree = f"{(document.get('duration_ms') or 0) / 1000:.2f} s"
    kpis = [
        ("Crédits consommés", str(document.get("credits_used", "—"))),
        # Sur un doublon, l'API rejoue la durée de l'analyse d'origine : on le dit.
        ("Durée d'analyse", f"{duree} (d'origine)" if deduplicated else duree),
        ("Anomalies détectées", str(anomaly_total)),
        ("Escalade IA", "oui" if document.get("used_external_api") else "non"),
    ]

    return Report(
        verdict_label=label,
        verdict_state=verdict_state,
        headline=headline,
        reasons=reasons,
        summary=str(document.get("summary") or ""),
        score=_global_score(api),
        layers=layers,
        kpis=kpis,
        raw=data,
        deduplicated=deduplicated,
    )
