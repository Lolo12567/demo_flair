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

from .model import DiffRow, Layer, MetaRow, Report, Severity, Signal, State

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

# Logiciels dont la présence sur un document administratif est un signal fort.
GRAPHIC_EDITORS = (
    "photoshop", "gimp", "illustrator", "inkscape", "canva", "affinity",
    "pixelmator", "krita", "paint.net", "figma", "acrobat pro", "pdfelement",
    "foxit phantom", "nitro pro", "ilovepdf", "smallpdf",
)

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
    diffs = _build_diffs(changed_fields)
    if diffs:
        consumed.add("text_content_changed")
        graves = sum(1 for d in diffs if d.state == State.FRAUD)
        champs = sorted({d.field_label for d in diffs})
        modifs = Signal(
            title="MODIFICATIONS DE CONTENU",
            state=State.FRAUD if graves else State.SUSPECT,
            severity=Severity.HIGH if graves else Severity.MEDIUM,
            verdict=(f"{len(diffs)} modification(s) de contenu"
                     + (f", dont {graves} de sévérité élevée" if graves else "")),
            bullets=[f"Champs touchés : {', '.join(champs)}."] if champs else [],
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
        ("Modifications détaillées", str(len(diffs)) if diffs else "non détaillées par l'API"),
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


def _is_graphic_tool(value) -> bool:
    return bool(value) and any(e in str(value).lower() for e in GRAPHIC_EDITORS)


def _tool_row(label: str, value, *, risky: bool, unknown: bool) -> MetaRow:
    """Ligne « logiciel ». `risky` n'est vrai que pour l'outil réellement fautif."""
    if not value:
        return MetaRow(label, "absent", State.NA)
    if risky:
        return MetaRow(
            label, str(value), State.FRAUD,
            "Logiciel de retouche graphique sur un document administratif — "
            "un document officiel est produit par un système de gestion.",
        )
    if unknown:
        return MetaRow(
            label, str(value), State.SUSPECT,
            "Éditeur non reconnu parmi les émetteurs légitimes connus du moteur.",
        )
    return MetaRow(label, str(value), State.OK)


def _build_metadata(api: dict, file_type: str) -> Layer:
    """Couche 2 — affichée sous forme de tableau catégorie / information / risque."""
    raw = api.get("metadata") or {}
    meta = ((raw.get("signals") or {}).get("metadata")) or {}
    codes = _anomaly_codes(raw)

    # Deux formes possibles selon le type de document.
    creation = meta.get("creation") or {}      # PDF
    doc_info = meta.get("document") or {}      # PDF
    security = meta.get("security") or {}      # PDF
    capture = meta.get("capture") or {}        # image
    editing = meta.get("editing") or {}        # image
    technical = meta.get("technical") or {}    # image

    hidden = api.get("hidden_content") or {}
    hidden_codes = _anomaly_codes(hidden)
    fonts = (((api.get("revision_history") or {}).get("signals") or {})
             .get("revision_history") or {}).get("fonts") or {}

    rows: list[MetaRow] = []
    consumed: set[str] = set()

    # ---------------- Logiciels ----------------
    producer = creation.get("producer") or editing.get("software")
    creator = creation.get("creator")
    prod_risky = _is_graphic_tool(producer)
    crea_risky = _is_graphic_tool(creator)
    # Le moteur signale un outil à risque sans dire lequel : on l'impute au
    # producteur, qui est le champ écrit en dernier par le logiciel d'édition.
    if "high_risk_tool" in codes:
        consumed.add("high_risk_tool")
        if not (prod_risky or crea_risky):
            prod_risky = True

    unknown = "unknown_producer" in codes
    if unknown:
        consumed.add("unknown_producer")

    rows.append(_tool_row("Logiciel de production", producer,
                          risky=prod_risky, unknown=unknown and not prod_risky))
    rows.append(_tool_row("Logiciel de création", creator,
                          risky=crea_risky, unknown=False))

    # ---------------- Dates ----------------
    created_raw = creation.get("created_at")
    modified_raw = creation.get("modified_at") or capture.get("capture_date")
    created, modified = _pdf_digits(created_raw), _pdf_digits(modified_raw)

    rows.append(MetaRow(
        "Date de création",
        _pdf_date(created_raw) if created_raw else "absente",
        State.OK if created_raw else State.NA,
    ))

    if modified_raw and not created_raw:
        rows.append(MetaRow(
            "Date de modification", _pdf_date(modified_raw), State.SUSPECT,
            "Date de modification présente alors que la date de création est absente.",
        ))
        consumed.add("modified_after_creation")
    elif modified_raw and created and modified > created:
        rows.append(MetaRow(
            "Date de modification", _pdf_date(modified_raw), State.SUSPECT,
            "Le document a été modifié après sa création.",
        ))
        consumed.add("modified_after_creation")
    elif modified_raw:
        rows.append(MetaRow("Date de modification", _pdf_date(modified_raw), State.OK))
    else:
        rows.append(MetaRow("Date de modification", "absente", State.NA))

    # ---------------- Identité du document ----------------
    rows.append(MetaRow(
        "Auteur déclaré", _txt(doc_info.get("author"), "absent"),
        State.OK if doc_info.get("author") else State.NA))
    rows.append(MetaRow(
        "Titre du document", _txt(doc_info.get("title"), "absent"),
        State.OK if doc_info.get("title") else State.NA))

    if doc_info.get("page_count") is not None:
        rows.append(MetaRow("Nombre de pages", str(doc_info["page_count"]), State.NA))

    # ---------------- Capture (images) ----------------
    if capture or file_type == "image":
        has_exif = capture.get("has_exif")
        make, model = capture.get("camera_make"), capture.get("camera_model")

        if has_exif is False or "missing_exif" in codes:
            consumed.add("missing_exif")
            rows.append(MetaRow(
                "Métadonnées de capture (EXIF)", "absentes", State.SUSPECT,
                "Une photo prise avec un téléphone conserve normalement ses "
                "données EXIF — leur absence suit souvent un ré-enregistrement.",
            ))
        elif has_exif and not (make or model):
            rows.append(MetaRow(
                "Métadonnées de capture (EXIF)", "présentes mais vides", State.SUSPECT,
                "Bloc EXIF conservé mais vidé de son appareil et de sa date.",
            ))
        elif has_exif:
            rows.append(MetaRow("Métadonnées de capture (EXIF)", "présentes", State.OK))
        else:
            rows.append(MetaRow("Métadonnées de capture (EXIF)", "non évaluées", State.NA))

        rows.append(MetaRow("Marque de l'appareil", _txt(make, "absente"),
                            State.OK if make else State.NA))
        rows.append(MetaRow("Modèle de l'appareil", _txt(model, "absent"),
                            State.OK if model else State.NA))
        rows.append(MetaRow(
            "Date de prise de vue", _txt(capture.get("capture_date"), "absente"),
            State.OK if capture.get("capture_date") else State.NA))
        rows.append(MetaRow(
            "Coordonnées GPS",
            "présentes" if capture.get("gps_present") else "absentes",
            State.OK if capture.get("gps_present") else State.NA))

    # ---------------- Caractéristiques techniques ----------------
    if technical:
        dimensions = technical.get("dimensions") or {}
        dpi = technical.get("dpi") or {}
        rows.append(MetaRow("Format", _txt(technical.get("format")), State.NA))
        if dimensions.get("width"):
            rows.append(MetaRow(
                "Dimensions",
                f"{dimensions.get('width')} × {dimensions.get('height')} px", State.NA))
        if dpi.get("x"):
            rows.append(MetaRow("Résolution", f"{dpi.get('x')} × {dpi.get('y')} DPI",
                                State.NA))

    # ---------------- Sécurité (PDF) ----------------
    if security:
        encrypted = security.get("encrypted")
        rows.append(MetaRow(
            "Chiffrement", "oui" if encrypted else "non",
            State.SUSPECT if encrypted else State.OK,
            "Document chiffré — une partie des contrôles peut être empêchée."
            if encrypted else "",
        ))
        consumed.add("encrypted")
        rows.append(MetaRow(
            "Formulaire interactif", "oui" if security.get("is_form") else "non",
            State.NA))

    # ---------------- Polices ----------------
    if fonts:
        total, embedded = fonts.get("count"), fonts.get("embedded_count")
        mismatch = "font_mismatch" in codes or "font_mismatch" in hidden_codes
        rows.append(MetaRow(
            "Polices utilisées", _txt(total, "non renseigné"),
            State.FRAUD if mismatch else State.OK,
            "Police incohérente à l'intérieur du document — signature d'un collage."
            if mismatch else "",
        ))
        if mismatch:
            consumed.add("font_mismatch")
        rows.append(MetaRow("Polices embarquées", _txt(embedded, "non renseigné"),
                            State.NA))

    # ---------------- Contenu masqué / calques ----------------
    if hidden_codes:
        for code in hidden_codes:
            state, _severity, phrase, explication = _anomaly(code)
            rows.append(MetaRow("Contenu masqué / calques", phrase, state, explication))
    elif hidden.get("verdict") == "pass":
        rows.append(MetaRow(
            "Contenu masqué / calques", "aucun détecté", State.OK,
            "", ))
    else:
        rows.append(MetaRow(
            "Contenu masqué / calques",
            _skip_reason(hidden, "non évalué"), State.NA))

    # ---------------- Anomalies non encore consommées ----------------
    for code in codes:
        if code in consumed:
            continue
        state, _severity, phrase, explication = _anomaly(code)
        rows.append(MetaRow(str(code).replace("_", " ").capitalize(),
                            phrase, state, explication))

    # ---------------- Résumé de la couche ----------------
    reds = [r for r in rows if r.state == State.FRAUD]
    oranges = [r for r in rows if r.state == State.SUSPECT]
    if reds:
        headline = reds[0].note or f"{reds[0].label} : {reds[0].value}"
    elif oranges:
        headline = oranges[0].note or f"{oranges[0].label} : {oranges[0].value}"
    elif any(r.state == State.OK for r in rows):
        headline = "Métadonnées cohérentes avec un document authentique"
    else:
        headline = "Aucune métadonnée exploitable sur ce document"

    return Layer(
        number=2,
        key="metadata",
        name="Métadonnées",
        subtitle=_subtitle(raw, "Logiciel · appareil · dates · polices · calques"),
        headline=headline,
        table=rows,
        duration_ms=(raw.get("duration_ms") or 0) + (hidden.get("duration_ms") or 0),
        external_api=bool(raw.get("external_api_call")),
        score=raw.get("score"),
    )



# --------------------------------------------------------------------------
# Couche 3 — 2D-DOC & QR code
# --------------------------------------------------------------------------

def _build_twodoc(api: dict) -> Layer:
    raw = api.get("qr_2ddoc") or {}
    verdict = raw.get("verdict")
    payload = raw.get("signals") or {}
    twodoc = payload.get("twodoc") or payload.get("2ddoc") or {}
    mismatches = [str(m) for m in (payload.get("mismatches") or [])]

    signals: list[Signal] = []

    if verdict == "fail":
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.FRAUD,
            severity=Severity.HIGH,
            verdict="2D-Doc présent mais illisible ou signature invalide",
        )
    elif verdict == "pass" and twodoc:
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.OK,
            severity=Severity.LOW,
            verdict="2D-Doc valide (norme AFNOR XP Z42-105)",
            details=[(str(k), _txt(v)) for k, v in twodoc.items()],
        )
    elif verdict == "pass":
        detection = Signal(
            title="CODE DÉTECTÉ",
            state=State.SUSPECT,
            severity=Severity.MEDIUM,
            verdict="QR code détecté, mais ce n'est pas un 2D-Doc officiel",
            details=[(str(k), _txt(v)) for k, v in payload.items()],
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
    signals.append(detection)

    if twodoc:
        if mismatches:
            signals.append(
                Signal(
                    title="COHÉRENCE 2D-DOC / DOCUMENT",
                    state=State.FRAUD,
                    severity=Severity.HIGH,
                    verdict=f"{len(mismatches)} champ(s) du 2D-Doc ne correspondent "
                            "pas au texte imprimé",
                    bullets=mismatches,
                )
            )
        else:
            signals.append(
                Signal(
                    title="COHÉRENCE 2D-DOC / DOCUMENT",
                    state=State.OK,
                    severity=Severity.LOW,
                    verdict="Les champs du 2D-Doc correspondent au texte imprimé",
                )
            )

    signals.extend(_extra_anomalies(raw, set()))

    return Layer(
        number=3,
        key="qr_2ddoc",
        name="2D-DOC & QR code",
        subtitle=_subtitle(raw, "Lecture de l'ancre cryptographique · recoupement"),
        headline=signals[0].verdict,
        signals=signals,
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


def _build_ai_media(api: dict, document: dict, debug: dict, file_type: str) -> Layer:
    raw = api.get("ai_generated_image") or {}
    payload = raw.get("signals") or {}
    # Le bloc debug a disparu de l'API ; on le lit encore s'il revient un jour.
    ai_block = (((debug.get("external_api") or {}).get("raw_response") or {})
                .get("report") or {}).get("ai_generated") or {}

    signals: list[Signal] = []

    # --- Génération par IA --------------------------------------------------
    is_ai = payload.get("ai_generated")
    score = raw.get("score")
    label = payload.get("label")

    if not raw:
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

    # --- Deepfake -----------------------------------------------------------
    deepfake = payload.get("deepfake") or {}
    if raw and deepfake:
        detected = deepfake.get("is_detected")
        conf = deepfake.get("confidence")
        signals.append(
            Signal(
                title="VISAGE MANIPULÉ / DEEPFAKE",
                state=State.FRAUD if detected else State.OK,
                severity=Severity.HIGH if detected else Severity.LOW,
                verdict=(f"Manipulation de visage détectée — confiance {_pct(conf)}"
                         if detected
                         else f"Aucune manipulation de visage détectée — score {_pct(conf)}"),
                details=[("Score de détection", _pct(conf))],
            )
        )

    # --- Photo d'écran ------------------------------------------------------
    recaptured = document.get("is_recaptured")
    if recaptured is True:
        signals.append(
            Signal(
                title="PHOTO D'ÉCRAN / REPHOTOGRAPHIE",
                state=State.SUSPECT,
                severity=Severity.MEDIUM,
                verdict="Le document semble être la photo d'un écran plutôt qu'un original",
                bullets=[
                    "Rephotographier un écran est la méthode la plus simple pour "
                    "effacer les traces d'une retouche.",
                ],
            )
        )
    elif recaptured is False and raw:
        signals.append(
            Signal(
                title="PHOTO D'ÉCRAN / REPHOTOGRAPHIE",
                state=State.OK,
                severity=Severity.LOW,
                verdict="Aucun indice de photo d'écran ou de rephotographie",
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
        subtitle=_subtitle(raw, "Modèle générateur · deepfake · photo d'écran"),
        headline=headline,
        signals=signals,
        duration_ms=raw.get("duration_ms") or 0,
        external_api=bool(raw.get("external_api_call")),
        score=score,
    )


# --------------------------------------------------------------------------
# Couche 5 — Cohérence sémantique
# --------------------------------------------------------------------------

def _inconsistencies(layer: dict) -> list[str]:
    payload = (layer or {}).get("signals") or {}
    issues = (payload.get("inconsistencies") or payload.get("issues")
              or payload.get("findings") or [])
    return [str(i.get("label") if isinstance(i, dict) else i) for i in issues]


def _build_coherence(api: dict, debug: dict, file_type: str) -> Layer:
    raw = api.get("coherence") or {}
    verdict = raw.get("verdict")

    bullets = _inconsistencies(raw)

    signals: list[Signal] = []

    if bullets:
        semantic = Signal(
            title="COHÉRENCE SÉMANTIQUE",
            state=State.FRAUD if len(bullets) >= 3 else State.SUSPECT,
            severity=Severity.HIGH if len(bullets) >= 3 else Severity.MEDIUM,
            verdict=f"{len(bullets)} incohérence(s) détectée(s) dans le document",
            bullets=bullets,
        )
    elif verdict == "pass":
        semantic = Signal(
            title="COHÉRENCE SÉMANTIQUE",
            state=State.OK,
            severity=Severity.LOW,
            verdict="Aucune incohérence détectée entre les données du document",
        )
    else:
        semantic = Signal(
            title="COHÉRENCE SÉMANTIQUE",
            state=State.NA,
            severity=Severity.NA,
            verdict=_skip_reason(raw, "Aucune donnée exploitable à recouper"),
        )
    semantic.details = [
        ("Texte extrait (OCR)", "oui" if debug.get("ocr_text") else "non exposé par l'API"),
        ("Ce qui est recoupé", "Cohérence des calculs, des dates, des identités et "
                               "des références bancaires entre eux"),
    ]
    signals.append(semantic)

    # --- Recoupement par IA en vision (couche `ai_coherence`) ---------------
    ai_raw = api.get("ai_coherence")
    ai_bullets = _inconsistencies(ai_raw or {})
    ai_reason = (ai_raw or {}).get("skip_reason")

    if ai_raw is None:
        vision = Signal(
            title="RECOUPEMENT PAR IA (VISION)",
            state=State.NA,
            severity=Severity.NA,
            verdict="Le contrôle par IA ne s'exécute pas sur ce type de document",
            bullets=[
                "Seules les images sont soumises au modèle de vision ; un PDF "
                "n'est aujourd'hui pas analysé par ce contrôle.",
            ] if file_type == "pdf" else [],
        )
    elif ai_bullets:
        vision = Signal(
            title="RECOUPEMENT PAR IA (VISION)",
            state=State.FRAUD if len(ai_bullets) >= 3 else State.SUSPECT,
            severity=Severity.HIGH if len(ai_bullets) >= 3 else Severity.MEDIUM,
            verdict=f"{len(ai_bullets)} incohérence(s) relevée(s) par l'analyse visuelle",
            bullets=ai_bullets,
        )
    elif _is_failure(ai_reason):
        vision = Signal(
            title="RECOUPEMENT PAR IA (VISION)",
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
            title="RECOUPEMENT PAR IA (VISION)",
            state=State.OK,
            severity=Severity.LOW,
            verdict="Aucune incohérence relevée par l'analyse visuelle du document",
        )
    else:
        vision = Signal(
            title="RECOUPEMENT PAR IA (VISION)",
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

    signals.append(
        Signal(
            title="CARACTÈRES UNICODE SUSPECTS",
            state=State.TBU,
            severity=Severity.NA,
            verdict="Détection des homoglyphes (ex. « о » cyrillique dans un IBAN) — "
                    "bientôt disponible",
            details=[
                ("Statut", "En cours d'intégration côté moteur"),
                ("Principe", "Un caractère visuellement identique mais issu d'un "
                             "autre alphabet casse un contrôle automatique tout en "
                             "restant invisible à l'œil"),
            ],
        )
    )

    signals.extend(_extra_anomalies(raw, set()))
    signals.extend(_extra_anomalies(ai_raw or {}, set()))

    return Layer(
        number=5,
        key="coherence",
        name="Cohérence sémantique",
        subtitle=_subtitle(raw, "Recoupement des données par IA · calculs · dates"),
        headline=_layer_headline(
            signals,
            "Aucune incohérence détectée dans le contenu du document",
            semantic.verdict,
        ),
        signals=signals,
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
    """Point d'entrée : réponse brute de l'API -> objet Report affichable."""
    document = data.get("document") or {}
    debug = data.get("debug") or {}
    api = _api_layers(document)
    file_type = _file_type(document, api)

    layers = [
        _build_history(api, file_type),
        _build_metadata(api, file_type),
        _build_twodoc(api),
        _build_ai_media(api, document, debug, file_type),
        _build_coherence(api, debug, file_type),
    ]

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
