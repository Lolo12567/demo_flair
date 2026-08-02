"""Modèle de vue — le vocabulaire unique de l'interface.

L'interface ne connaît QUE ces objets. Elle ne sait pas que l'API existe.
C'est ce qui permet de changer l'API sans retoucher l'affichage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class State(Enum):
    """Les 4 états visuels de la spec, + 2 états techniques."""

    OK = "ok"  # 🟢 vérifié, preuve positive
    SUSPECT = "suspect"  # 🟠 signal détecté, non conclusif
    FRAUD = "fraud"  # 🔴 signal fort de fraude
    NA = "na"  # ⚪ non applicable / non vérifiable
    TBU = "tbu"  # ⚪ pas encore exposé par l'API
    # ⚫ le contrôle a échoué techniquement. À NE PAS confondre avec NA :
    # "non applicable" veut dire qu'il n'y avait rien à vérifier ; ERROR veut
    # dire qu'il y avait quelque chose à vérifier et qu'on n'a pas pu le faire.
    ERROR = "error"
    PENDING = "pending"  # analyse en cours (affichage transitoire)


class Severity(Enum):
    """Badge à droite, redondant avec la couleur (accessibilité + scan rapide)."""

    LOW = "Faible"
    MEDIUM = "Moyen"
    HIGH = "Élevé"
    NA = "N/A"


# Libellé du chip + classe CSS, par état.
STATE_META: dict[State, tuple[str, str]] = {
    State.OK: ("VÉRIFIÉ", "ok"),
    State.SUSPECT: ("SUSPECT", "suspect"),
    State.FRAUD: ("ALERTE", "fraud"),
    State.NA: ("N/A", "na"),
    State.TBU: ("À VENIR", "tbu"),
    State.ERROR: ("INDISPONIBLE", "error"),
    State.PENDING: ("ANALYSE…", "pending"),
}

# Du plus grave au moins grave — sert à agréger l'état d'une couche.
# ERROR passe devant OK : une couche dont un contrôle a échoué ne doit jamais
# s'afficher en vert, sinon on croit l'avoir vérifiée.
# NA passe avant TBU : une couche qui contient au moins un contrôle réellement
# effectué s'affiche "non applicable", pas "à venir".
STATE_ORDER: list[State] = [
    State.FRAUD,
    State.SUSPECT,
    State.ERROR,
    State.OK,
    State.NA,
    State.TBU,
    State.PENDING,
]


def worst_state(states: list[State]) -> State:
    """État agrégé d'un ensemble de signaux : le plus grave l'emporte."""
    for candidate in STATE_ORDER:
        if candidate in states:
            return candidate
    return State.NA


@dataclass
class Signal:
    """Une carte de signal — le format unifié de la spec."""

    title: str  # ex. "IMAGE GÉNÉRÉE PAR IA"
    state: State
    verdict: str  # une phrase, en langage métier
    severity: Severity = Severity.NA
    bullets: list[str] = field(default_factory=list)  # affichées sous le verdict
    details: list[tuple[str, str]] = field(default_factory=list)  # repliées


@dataclass
class MetaRow:
    """Une ligne du tableau de métadonnées : catégorie · information · risque."""

    label: str  # colonne 1 — la catégorie
    value: str  # colonne 2 — ce que disent les métadonnées
    state: State  # colonne 3 — le niveau de risque
    note: str = ""  # phrase métier, affichée sous la ligne si risque


@dataclass
class DiffRow:
    """Une modification de contenu : valeur d'origine à gauche, valeur finale à droite."""

    field_label: str  # "Code postal / ville"
    before: str | None  # None = le champ a été ajouté
    after: str | None  # None = le champ a été supprimé
    state: State
    severity: Severity = Severity.NA
    raw_before: str = ""  # valeur brute du moteur, consultable en dépliant
    raw_after: str = ""


@dataclass
class CheckRow:
    """Un recoupement : ce que dit l'ancre, face à ce qu'on trouve sur le document."""

    label: str  # "Champ 62 du 2D-Doc"
    expected: str  # valeur portée par l'ancre
    observed: str  # ce qui a été constaté sur le document
    state: State  # OK si le recoupement passe, FRAUD sinon
    detail: str = ""  # phrase brute renvoyée par le moteur


@dataclass
class Layer:
    """Une des 5 couches de détection.

    Une couche s'affiche en cartes de signaux, en tableau (`table`) et/ou en
    comparaison avant/après (`diffs`). Tous alimentent l'état de la couche.
    """

    number: int
    key: str
    name: str
    subtitle: str
    headline: str  # résumé de la couche, en une phrase
    signals: list[Signal] = field(default_factory=list)
    table: list[MetaRow] = field(default_factory=list)
    diffs: list[DiffRow] = field(default_factory=list)
    checks: list[CheckRow] = field(default_factory=list)
    duration_ms: int = 0
    external_api: bool = False
    score: float | None = None
    # Verdict fourni par le moteur. Quand il est présent, il fait foi : on
    # n'agrège pas soi-même ce que l'API a déjà tranché.
    state_override: State | None = None

    def _states(self) -> list[State]:
        return (
            [s.state for s in self.signals]
            + [r.state for r in self.table]
            + [d.state for d in self.diffs]
            + [c.state for c in self.checks]
        )

    @property
    def state(self) -> State:
        if self.state_override is not None:
            return self.state_override
        return worst_state(self._states())

    @property
    def alert_count(self) -> int:
        """Nombre de signaux en alerte affiché sur l'en-tête de la couche.

        Les `diffs` en sont exclus : ils sont déjà résumés par le signal
        « Modifications de contenu », les compter deux fois gonflerait le badge.
        """
        states = (
            [s.state for s in self.signals]
            + [r.state for r in self.table]
            + [c.state for c in self.checks if c.state == State.FRAUD]
        )
        return sum(1 for s in states if s in (State.FRAUD, State.SUSPECT))

    def alerts(self) -> list[tuple[State, str]]:
        """(état, phrase) de tout ce qui mérite d'apparaître dans le verdict global.

        Les lignes de `diffs` en sont volontairement exclues : sur un document à
        58 révisions elles noieraient le verdict. Elles sont représentées par le
        signal de synthèse « Modifications de contenu ».
        """
        found = [(s.state, s.verdict) for s in self.signals]
        found += [
            (r.state, r.note or f"{r.label} : {r.value}")
            for r in self.table
        ]
        found += [
            (c.state, f"{c.label} : {c.observed}")
            for c in self.checks if c.state == State.FRAUD
        ]
        return [
            item for item in found
            if item[0] in (State.FRAUD, State.SUSPECT, State.ERROR)
        ]


@dataclass
class Report:
    """Couche 0 — le verdict global, plus les 5 couches."""

    verdict_label: str  # "FRAUDE PROBABLE", "AUTHENTIQUE"…
    verdict_state: State
    headline: str  # raison principale, en langage métier
    reasons: list[str]  # raisons secondaires
    summary: str  # synthèse rédigée par le moteur
    score: int  # 0-100, calculé mais plus affiché — sert au tri et au débogage
    layers: list[Layer]
    kpis: list[tuple[str, str]]
    raw: dict
    deduplicated: bool = False  # résultat rejoué depuis une analyse antérieure
