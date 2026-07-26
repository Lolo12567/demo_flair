# Contrat d'API — ce que le front lit

Vérifié en direct sur `https://api.myflair.app/v1/analyze` le **26/07/2026**.

Le front (`flair/adapter.py`) est câblé sur les champs ci-dessous. Ce qui n'y figure
pas s'affiche ⚪ « non applicable » ou « à venir » — jamais une erreur.

---

## Correspondance couches API → couches affichées

| # | Couche affichée | Couche API | État |
|---|---|---|---|
| 1 | Historique & modifications | `revision_history` | ✅ opérationnelle |
| 2 | Métadonnées | `metadata` + `hidden_content` | ✅ opérationnelle |
| 3 | 2D-DOC & QR code | `qr_2ddoc` | ✅ câblée, jamais déclenchée en test |
| 4 | Images générées par IA | `ai_generated_image` | ✅ opérationnelle (images seules) |
| 5 | Cohérence sémantique | `coherence` | ⏳ attend l'OCR côté moteur |

---

## Codes d'anomalie — le point central

Chaque couche renvoie `signals.anomalies`, une liste de codes machine. Le front les
traduit en phrases métier via la table `ANOMALIES` dans `adapter.py`.

| Code | Affichage | Couleur |
|---|---|---|
| `high_risk_tool` | Document produit ou retouché avec un logiciel d'édition graphique | 🔴 Élevé |
| `text_content_changed` | Le texte du document a été modifié après sa création | 🔴 Élevé |
| `hidden_text` | Texte masqué détecté sous le contenu visible | 🔴 Élevé |
| `overlapping_layers` | Calques superposés détectés | 🔴 Élevé |
| `font_mismatch` | Police incohérente à l'intérieur du document | 🔴 Élevé |
| `revision_summary` | Le fichier a été enregistré plusieurs fois après sa création | 🟠 Moyen |
| `editing_software_trace` | Traces d'un logiciel d'édition dans le contenu du fichier | 🟠 Moyen |
| `modified_after_creation` | Date de modification postérieure à la création | 🟠 Moyen |
| `encrypted` | Document protégé par chiffrement | 🟠 Moyen |
| `missing_exif` | Aucune métadonnée de capture | ⚪ N/A |

Les cinq premiers 🔴 et `hidden_text`/`overlapping_layers`/`font_mismatch` sont
**anticipés** : ils n'ont pas encore été observés en réponse réelle, la formulation
est prête si le moteur les émet.

> **Un code inconnu n'est jamais ignoré.** Il s'affiche en 🟠 avec sa formulation
> brute (`Anomalie signalée par le moteur : …`). Ajouter un code côté moteur ne
> casse donc rien — il suffit ensuite de lui écrire une phrase dans `ANOMALIES`.

---

## Structures observées

### `revision_history` — couche 1

```jsonc
"signals": {
  "anomalies": ["revision_summary", "text_content_changed"],
  "revision_history": {
    "fonts":     { "count": 1, "embedded_count": 1 },
    "revisions": { "count": 2, "changed_fields": null,
                   "modified_after_creation": true },
    "technical": { "encrypted": false, "page_count": 1, "pdf_version": "1.4" }
  }
}
```

`revisions.count ≥ 2` → 🟠 « N enregistrements successifs détectés ».
`changed_fields` est **toujours `null`** aujourd'hui — c'est le champ qui manque
pour construire la vue diff double colonne. Format attendu :

```jsonc
"changed_fields": [
  { "field": "Salaire net", "before": "1 850,00", "after": "2 940,00",
    "from_version": 1, "to_version": 2, "page": 1,
    "bbox": { "x1": 0, "y1": 0, "x2": 0, "y2": 0 } }
]
```

Le front affiche déjà une liste de `changed_fields` si elle arrive sous forme de
chaînes. `bbox` servirait au surlignage sur le rendu du document.

### `metadata` — couche 2

Deux formes selon le type de document. Les deux sont gérées.

```jsonc
// PDF
"metadata": {
  "creation": { "creator": "…", "producer": "…",
                "created_at": null, "modified_at": "D:20260726180000+02'00'" },
  "document": { "title": null, "author": "…", "page_count": 1 },
  "security": { "is_form": false, "encrypted": false }
}
// Image
"metadata": {
  "capture":   { "has_exif": false, "camera_make": null, "camera_model": null,
                 "capture_date": null, "gps_present": false },
  "editing":   { "software": null },
  "technical": { "format": "JPEG", "dimensions": {"width":1,"height":1},
                 "dpi": {"x":96,"y":96} }
}
```

Manque pour être complet : **signature numérique et sa validité**, permissions
(impression / copie / modification). Affiché « non exposée par l'API ».

### `hidden_content` — replié dans la couche 2

Ne renvoie que `verdict`, `score` et `anomalies`. Pas de détail sur *quel* texte
est masqué ni *où*. Suffisant pour l'état, insuffisant pour justifier auprès d'un
assuré.

### `ai_generated_image` — couche 4

```jsonc
"signals": { "label": "human", "ai_generated": false,
             "deepfake": { "confidence": 0.0, "is_detected": false } }
```

Absente de la réponse pour un PDF → la couche s'affiche ⚪ N/A.

### `coherence` — couche 5

Renvoie systématiquement `na` / `"aucune donnée à recouper"`. Le front lit déjà
`signals.inconsistencies` (ou `issues`, ou `findings`) : liste de chaînes, ou
d'objets avec une clé `label`. 1–2 → 🟠 · 3 et plus → 🔴.

---

## 🔴 Bug bloquant — `ai_coherence` échoue à chaque fois

Constaté le 26/07/2026 sur un bulletin de paie image (1240×1754, texte net) :

```jsonc
{ "name": "ai_coherence", "verdict": "na", "duration_ms": 44401,
  "external_api_call": true,
  "skip_reason": "cohérence indisponible: réponse non parsable:
                  Expecting value: line 1 column 1 (char 0)" }
```

La couche s'exécute (44 s, 90 % du temps d'analyse), appelle le modèle, puis
**échoue au parsing de la réponse**. `Expecting value: line 1 column 1 (char 0)`
= `json.loads()` sur une chaîne vide ou non-JSON.

Cause la plus probable : le modèle renvoie son JSON enrobé dans un bloc Markdown
(```` ```json … ``` ````) et le code appelle `json.loads()` sur la réponse brute.
Correctif habituel : retirer l'enrobage avant parsing, et journaliser la réponse
brute en cas d'échec pour pouvoir diagnostiquer.

Conséquences aujourd'hui :
- **Aucune incohérence sémantique n'est jamais détectée**, sur aucun document.
- Un bulletin où `brut 3200 − cotisations 700 = 2500` mais `net à payer = 2940`
  ressort `clean` en PDF et `needs_review` en image.
- 44 s de latence sont consommées pour un résultat systématiquement jeté.

Second point : **`ai_coherence` est absente de la réponse pour un PDF.** Le
chemin vision ne s'exécute que sur les images. Un bulletin de paie transmis en
PDF — le cas le plus courant — n'est jamais recoupé.

---

## 🟠 `changed_fields` — trois points à reprendre côté moteur

Constaté le 26/07/2026. `changed_fields` **est bien renvoyé** par l'API HTTP
(16 entrées sur un justificatif à 58 révisions). Format actuel :

```jsonc
{ "field": "postal", "severity": "high",
  "old_value": "94500 CHAMPIGNY SUR MARNE\nCHAMPIGNY SUR\nGERMAIN\nM",
  "new_value": "94470 BOISSY ST LÉGER\nC\nCÉ\nD\nE\nETAGE" }
```

**1. `old_value: null` fréquent, et ambigu.** Sur un document, les 5 modifications
avaient toutes `old_value: null` tout en étant classées `severity: high`. Deux
causes possibles que l'API ne distingue pas : le champ a réellement été ajouté,
ou le moteur n'a pas su l'extraire de la version antérieure. Dans le second cas,
le document est peint en rouge par du bruit d'extraction.
→ Utile : un champ distinguant `added` de `extraction_failed`.

**2. Valeurs bruitées.** Les valeurs contiennent des fragments d'extraction
(`\nM`, `\nau`, `\nDE L`, `\nCÉ`) et des retours à la ligne. Le front les nettoie
à l'affichage (première ligne utile, brut consultable en dépliant), mais c'est
un pansement : l'extraction gagnerait à ne renvoyer que le champ identifié.

**3. Pas de rattachement aux versions.** Aucun numéro de version n'accompagne
les modifications — vérifié, la structure ne contient que `field`, `severity`,
`old_value`, `new_value`. Les changements forment une liste à plat impossible à
relier aux 58 révisions. Deux champs suffiraient à débloquer la timeline
cliquable côté front :

```jsonc
{ ..., "from_version": 12, "to_version": 13 }
```

Accessoirement, les paires semblent appariées de façon non ordonnée : une même
valeur apparaît en `new_value` d'une entrée et en `old_value` d'une autre, sans
séquence cohérente.

---

## Points ouverts pour l'équipe API

1. **`debug` est `null`** — testé avec `?debug=true` et l'en-tête `X-Debug: true`,
   sans effet. On y perdait le classement par générateur d'images (GPT-4o 73 %,
   FLUX 21 %…), qui était l'un des détails les plus démonstratifs. Intentionnel ?
2. **`changed_fields` toujours `null`** — bloque la vue diff, la fonctionnalité la
   plus différenciante face à Finovox / Resistant AI.
3. **`external_api_call`** n'est plus présent que sur `ai_generated_image`.
4. **`qr_2ddoc` a pris 19,5 s** sur un PDF d'une page sans QR code — à profiler,
   c'est 95 % du temps total de l'analyse.
5. **Pas de `file_type`** dans la réponse : le front le déduit de l'extension du
   nom de fichier.

---

## Score global

`adapter.py`, `_global_score` : maximum pondéré des `score` de couches, poids dans
`LAYER_WEIGHTS`. Le **maximum** est volontaire — en fraude un seul signal fort
suffit, une moyenne diluerait un 0.73 dans cinq couches à 0.
