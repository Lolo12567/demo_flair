# Démo FLAIR — passation

À coller au début d'une nouvelle discussion pour reprendre le travail sans
relire l'historique.

---

## Le projet

Interface web de démonstration du moteur d'analyse forensique documentaire
FLAIR, en **NiceGUI** (Python génère la page, pas de JS). Elle sert aux
rendez-vous commerciaux : on dépose une pièce justificative, elle affiche un
verdict et cinq couches de détection.

**Dossier** : `C:\Users\leolo\OneDrive\Desktop\Dossiers\Perso\Entrepreneuriat\SaaS\demo_flair-main`

### Lancer en local

```
cd "C:\Users\leolo\OneDrive\Desktop\Dossiers\Perso\Entrepreneuriat\SaaS\demo_flair-main"
.\venv\Scripts\Activate.ps1
$env:FLAIR_API_URL = "https://api.myflair.app/v1/analyze"; $env:FLAIR_API_KEY = "..."; $env:FLAIR_RELOAD = "1"; python app.py
```

Puis `http://localhost:8080` et **Ctrl+F5** (le CSS change souvent).
`FLAIR_RELOAD=1` active le rechargement automatique.

### Particularité de la machine

Avast inspecte le HTTPS : Python rejette son certificat. `truststore` est
installé et appelé au démarrage d'`app.py` pour utiliser le magasin de
certificats Windows. **Sans lui, tout appel API échoue en TLS.** Idem pour
`pip`, qui a besoin de `--cert <bundle.pem>`.

---

## Architecture

| Fichier | Rôle |
|---|---|
| `app.py` | appel API, page, orchestration |
| `flair/adapter_v2.py` | **lecture du format d'API actuel** — c'est ici qu'on travaille |
| `flair/adapter.py` | lecture de l'ancien format + aiguillage entre les deux |
| `flair/model.py` | modèle de vue : State, Signal, Layer, MetaRow, DiffRow, CheckRow, Report |
| `flair/components.py` | briques d'affichage |
| `flair/theme.py` | tout le CSS + le logo SVG |
| `flair/feedback.py` | questionnaire de fin + base de données |
| `flair/preview.py` | aperçu du document, servi depuis la mémoire vive |
| `flair/policy.py` | catalogue de logiciels, utilisé seulement par le lecteur historique |

**Principe** : l'interface ne connaît jamais le format de l'API. Quand l'API
change, seul l'adaptateur bouge.

### Double lecture des formats

`adapter.build_report()` aiguille : si les couches portent un `label` ou des
`signals` en liste, c'est le nouveau format (`adapter_v2`), sinon l'ancien.

Ce n'est pas transitoire : **un document analysé avant la migration rejoue son
analyse stockée, donc à l'ancien format**, même aujourd'hui.

---

## L'API

`POST https://api.myflair.app/v1/analyze` — fichier en multipart, clé en
`Authorization: Bearer`.

Réponse : `document` avec `verdict` (high / moderate / low / na), `summary`
rédigé, et **5 couches** : `revision_history`, `metadata`, `qr_2ddoc`,
`ai_generated_image`, `coherence`.

Chaque couche : `label`, `verdict`, `description`, `duration_ms`, `signals[]`,
parfois `skip_reason`. Chaque signal : `label`, `verdict`, souvent `value`,
`details`, `description`, `code`.

### Pièges connus

- **`name` a disparu** des couches et des signaux. Le front retombe sur le
  libellé français normalisé (`_cle()` dans `adapter_v2`). Fragile : une
  reformulation de « Métadonnées » casserait l'affichage sans erreur visible.
  À supprimer dès que `name` revient.
- **Déduplication par SHA-256 du contenu** : un document déjà analysé rejoue
  son ancien résultat sans consommer de crédit. **Aucun paramètre de
  contournement ne fonctionne** — testés sans succès : `no_cache`, `force`,
  `refresh`, `skip_cache`, `dedup=false`, en-têtes `X-No-Cache` et
  `Cache-Control`. Il faut que le dev en ajoute un.
- `changed_fields` est souvent vide, et sans numéro de version.
- La couche `coherence` ne reçoit pas le document : son prompt n'a aucun
  emplacement pour l'image ou le texte OCR. Elle reformule les constats des
  autres couches. Ses `duration_ms` de 1 ou 21 ms le confirment.
- `external_api_call: true` ment parfois (21 ms avec appel externe annoncé).

`CONTRAT_API.md` détaille tout ça, à jour pour l'essentiel.

---

## Les écarts assumés du front

Le front ne suit pas l'API à la lettre. **Chacun de ces écarts est délibéré et
commenté dans le code** — à retirer quand le moteur s'améliorera.

1. **Logiciel non reconnu** — l'API met en modéré tout éditeur inconnu, ce qui
   alerte sur des documents authentiques. Le front annule, sauf si le logiciel
   figure dans `LOGICIELS_SIGNALES` (outils PDF : iLovePDF, Smallpdf, PDF24,
   Nitro, Foxit, LibreOffice, Google Docs, Canva, CutePDF, img2pdf…).
   **Une alerte forte du moteur est toujours conservée** — sinon Photoshop
   passerait au vert, faute de figurer dans la liste.
2. **Métadonnées** — liste blanche stricte : logiciel de création, logiciel de
   modification, date de création, date de modification, appareil photo, date
   de la photo. Le reste est ignoré, pas seulement masqué.
3. **Appareil et date de la photo** — toujours au vert, jamais en alerte. Leur
   absence ne prouve rien : un PDF ou un scan n'en a jamais.
4. **Modifications sans valeur d'origine** — ni affichées ni signalées : sans
   point de comparaison, on ne peint pas un document en rouge.
5. **QR sans 2D-Doc** — reformulé et signalé en modéré, là où l'API dit `na`.
6. **Couche Cohérence** — un seul bloc, celui de synthèse.
7. **État d'une couche recalculé** quand des signaux sont écartés — sinon
   l'en-tête reste coloré sans raison visible en dessous.

### Affichage actuel

Les cinq couches sont **actives et non dépliables** : une ligne de verdict
chacune, sans détail. Les signaux restent calculés — ils alimentent le résumé,
la couleur et le compteur d'alertes.

Le bandeau de verdict affiche le niveau de risque et la synthèse du moteur,
rien d'autre.

---

## Questionnaire de fin

Après chaque analyse : « Le verdict est-il correct ? » Oui / Non, avec dix
cases groupées par nature d'erreur (`fn_` faux négatif, `fp_` faux positif,
`cal_` calibrage) et un champ libre.

Stockage : **PostgreSQL** si `DATABASE_URL` existe (Railway), SQLite sinon.
Table `retours` créée au démarrage. Un échec d'écriture n'interrompt jamais la
démonstration.

Le **blocage du dépôt** tant qu'on n'a pas répondu est désactivé par défaut.
Pour l'activer chez de vrais utilisateurs : `FLAIR_RETOUR_BLOQUANT = 1`.

---

## Déploiement

- **Railway** suit `Lolo12567/demo_flair` (le fork), branche `main`.
  URL : `demo.myflair.app`. Service PostgreSQL lié par `DATABASE_URL`.
- Le dépôt de référence est `Nassim-dev/demo_flair`, remote `flair` en local.
- Pousser : `git push origin main` → Railway redéploie tout seul.
- Variables Railway : `FLAIR_API_KEY`, `FLAIR_API_URL`, `DATABASE_URL`.

**Attention** : ne jamais faire `git switch main` sans vérifier où pointe la
branche — la `main` du fork a déjà été en retard sur celle de Nassim, ce qui a
fait revenir tout le code à sa version d'origine sur le disque.

---

## Points ouverts

- Faire revenir `name` dans l'API, pour supprimer le repli sur les libellés.
- Paramètre de contournement de la déduplication, pour les tests.
- Donner le document au module de cohérence (image ou texte OCR) — aujourd'hui
  il ne voit que les résultats des autres couches.
- `from_version` / `to_version` sur `changed_fields`, pour la vue comparative.
- Faire remonter les sévérités depuis l'API plutôt que de les décider dans le
  front : une quarantaine de décisions y sont encore codées en dur.

---

## Façon de travailler

Léo est débutant en développement. Expliquer avant d'agir, signaler les
conséquences d'un choix, et vérifier dans le navigateur avant d'annoncer que
ça marche : plusieurs fois, un « problème d'API » venait en réalité du front
qui lisait la mauvaise clé.
