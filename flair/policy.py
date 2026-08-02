"""Politique de risque sur les logiciels de creation et de modification.

Le catalogue ci-dessous regroupe les logiciels par famille. Chaque famille se
regle independamment sur trois niveaux, depuis le panneau d'options de la demo.

Ce fichier est un prototype de ce que l'API devra exposer par client : la
politique de risque appartient au metier, pas au code d'affichage.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import State

# Les trois niveaux reglables, du plus permissif au plus severe.
LEVELS: list[tuple[str, State]] = [
    ("Neutre", State.NA),
    ("Modéré", State.SUSPECT),
    ("Élevé", State.FRAUD),
]
LEVEL_BY_NAME = {nom: etat for nom, etat in LEVELS}
NAME_BY_LEVEL = {etat: nom for nom, etat in LEVELS}


@dataclass(frozen=True)
class Family:
    key: str
    name: str
    examples: str
    patterns: tuple[str, ...]  # fragments cherches en minuscules
    default: State
    note: str  # phrase metier affichee quand la famille declenche une alerte


FAMILIES: tuple[Family, ...] = (
    Family(
        key="retouche",
        name="Retouche graphique",
        examples="Photoshop, GIMP, Illustrator, Canva…",
        patterns=(
            "photoshop", "gimp", "illustrator", "inkscape", "affinity",
            "pixelmator", "krita", "paint.net", "coreldraw", "corel draw",
            "canva", "figma", "photopea", "pixlr", "sketch",
        ),
        default=State.FRAUD,
        note="Logiciel de retouche graphique sur un document administratif — "
             "un document officiel est produit par un système de gestion.",
    ),
    Family(
        key="pdf_en_ligne",
        name="Éditeurs PDF en ligne",
        examples="iLovePDF, Smallpdf, Sejda, PDF24…",
        patterns=(
            "ilovepdf", "smallpdf", "sejda", "pdfescape", "pdf24", "sodapdf",
            "soda pdf", "pdfcandy", "pdf candy", "docfly", "xodo", "pdffiller",
        ),
        default=State.NA,
        note="Éditeur PDF en ligne, gratuit et sans installation — c'est l'outil "
             "le plus courant pour modifier un montant sur un document.",
    ),
    Family(
        key="pdf_pro",
        name="Éditeurs PDF professionnels",
        examples="Acrobat Pro, Nitro, Foxit…",
        patterns=(
            "acrobat", "nitro", "foxit", "pdfelement", "pdf-xchange",
            "pdf xchange", "able2extract", "pdfsam",
        ),
        default=State.NA,
        note="Éditeur PDF professionnel — usage legitime frequent (fusion, "
             "signature, annotation), a interpreter selon le contexte.",
    ),
    Family(
        key="bureautique",
        name="Bureautique",
        examples="Word, LibreOffice, Google Docs…",
        patterns=(
            "microsoft word", "microsoft® word", "microsoft excel",
            "powerpoint", "libreoffice", "openoffice", "google", "skia/pdf",
            "wps office", "pages", "quartz pdfcontext",
        ),
        default=State.NA,
        note="Document produit par une suite bureautique plutôt que par un "
             "système de gestion — inhabituel chez un grand émetteur.",
    ),
    Family(
        key="scanner_mobile",
        name="Scanners mobiles",
        examples="CamScanner, Adobe Scan, Microsoft Lens…",
        patterns=(
            "camscanner", "adobe scan", "microsoft lens", "office lens",
            "genius scan", "turboscan", "scanbot", "tiny scanner", "scannable",
        ),
        default=State.NA,
        note="Application de numerisation mobile — usage massivement legitime, "
             "mais certaines embarquent des fonctions de retouche.",
    ),
)

FAMILY_BY_KEY = {f.key: f for f in FAMILIES}


def default_policy() -> dict[str, State]:
    """La politique appliquee a l'ouverture de la demo."""
    return {f.key: f.default for f in FAMILIES}


def classify(software, policy: dict[str, State] | None = None) -> tuple[State, str]:
    """Renvoie (niveau de risque, phrase metier) pour un nom de logiciel.

    (State.OK, "") si le logiciel ne figure dans aucune famille surveillee :
    c'est un logiciel identifie et non signale, donc une preuve positive.
    """
    if not software:
        return State.NA, ""
    politique = policy or default_policy()
    lowered = str(software).lower()
    for famille in FAMILIES:
        if any(motif in lowered for motif in famille.patterns):
            niveau = politique.get(famille.key, famille.default)
            return niveau, (famille.note if niveau != State.NA else "")
    return State.OK, ""
