"""Aperçu visuel du document analysé.

Les octets du document ne sont JAMAIS écrits sur le disque. Ils sont conservés
en mémoire vive le temps de l'affichage, servis au navigateur sous une URL à
jeton aléatoire, puis évincés dès que de nouveaux documents arrivent.

On passe par une URL plutôt que par une image encodée en base64 dans la page
pour deux raisons : le PDF ne s'affiche pas de façon fiable en `data:` dans
Chrome, et un document de plusieurs méga-octets encodé dans la page saturerait
la liaison temps réel entre le serveur et le navigateur.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict

from fastapi import Response
from nicegui import app

# Nombre d'aperçus gardés en mémoire simultanément (les plus anciens sont évincés).
MAX_PREVIEWS = 6

# jeton -> (type MIME, octets)
_STORE: "OrderedDict[str, tuple[str, bytes]]" = OrderedDict()

MIMES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "heic": "image/heic",
    "heif": "image/heif",
}

# Formats que les navigateurs ne savent pas afficher nativement.
UNRENDERABLE = {"image/heic", "image/heif", "image/tiff"}


def store(filename: str, content: bytes) -> tuple[str, str, str]:
    """Met le document en mémoire et renvoie (url, genre, message).

    genre ∈ {"image", "pdf", "none"} — "none" quand le navigateur ne sait pas
    afficher le format, auquel cas `message` explique pourquoi.
    """
    extension = str(filename).rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime = MIMES.get(extension)

    if mime is None:
        return "", "none", f"Aperçu indisponible pour un fichier .{extension or '?'}"
    if mime in UNRENDERABLE:
        return "", "none", (
            f"Le format .{extension} n'est pas affichable par les navigateurs — "
            "l'analyse a bien été effectuée sur le fichier d'origine."
        )

    token = uuid.uuid4().hex
    _STORE[token] = (mime, content)
    while len(_STORE) > MAX_PREVIEWS:
        _STORE.popitem(last=False)

    return f"/apercu/{token}", ("pdf" if mime == "application/pdf" else "image"), ""


@app.get("/apercu/{token}")
def _serve_preview(token: str) -> Response:
    item = _STORE.get(token)
    if item is None:
        return Response(status_code=404)
    mime, data = item
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )
