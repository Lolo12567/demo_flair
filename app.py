import asyncio
import hashlib
import inspect
import json
import os

import httpx
from nicegui import events, ui

API_URL = os.getenv("FLAIR_API_URL", "https://api.myflair.app/v1/analyze")
API_KEY = os.getenv("FLAIR_API_KEY", "")

LAYERS = [
    ("hash", "Empreinte & déduplication", "SHA-256 · recherche de doublons"),
    ("metadata", "Métadonnées", "Producer · auteur · dates · traces d'impression"),
    ("structure", "Structure PDF", "Objets · mises à jour incrémentales"),
    ("twodoc", "2D-Doc & signatures", "Vérification cryptographique des ancres"),
    ("fonts", "Analyse typographique", "Substitutions · incohérences de polices"),
    ("recompress", "Recompression & édition", "Traces de réenregistrement"),
    ("capture", "Capture d'écran / photo", "EXIF · moiré (FFT)"),
    ("ai", "Escalade IA conditionnelle", "Cohérence sémantique"),
]

STATUS_META = {
    "wait": ("EN ATTENTE", "chip-wait"),
    "run": ("ANALYSE…", "chip-run"),
    "ok": ("VÉRIFIÉ", "chip-ok"),
    "alert": ("ALERTE", "chip-alert"),
    "na": ("N/A", "chip-na"),
    "skip": ("NON DÉCLENCHÉE", "chip-na"),
}

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@0,500;0,600;1,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --paper:#F5F4EE; --card:#FFFFFF; --ink:#14171C; --ink-2:#5B626B;
  --line:#E2E0D6; --line-2:#CFCDC2; --accent:#1F3D8F; --accent-soft:#EEF1F9;
  --ok:#1B7A4C; --alert:#B02A21; --na:#8A9099;
}
body {
  background-color:var(--paper) !important; color:var(--ink);
  font-family:'IBM Plex Sans',sans-serif;
  background-image:radial-gradient(rgba(31,61,143,.055) 1px, transparent 1px);
  background-size:26px 26px;
}
.nicegui-content { padding:0 !important; }
.mono { font-family:'IBM Plex Mono',monospace; }

.topbar { position:sticky; top:0; z-index:50; width:100%;
  background:rgba(245,244,238,.82); backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line); }
.topbar-inner { max-width:56rem; margin:0 auto; padding:14px 24px; }
.wordmark { font-family:'IBM Plex Serif',serif; font-weight:600;
  font-size:1.15rem; letter-spacing:.22em; }
.live-badge { display:flex; align-items:center; gap:8px;
  border:1px solid var(--line-2); border-radius:99px; padding:5px 14px;
  background:var(--card); }
.live-dot { width:7px; height:7px; border-radius:50%; background:var(--ok);
  animation:pulse 2.2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

.eyebrow { font-family:'IBM Plex Mono',monospace; font-size:.66rem;
  letter-spacing:.28em; text-transform:uppercase; color:var(--accent); }
.hero-title { font-family:'IBM Plex Serif',serif; font-weight:600;
  font-size:clamp(2.1rem,4.5vw,3rem); line-height:1.12; letter-spacing:-.01em; }
.hero-title em { font-style:italic; font-weight:500; color:var(--accent); }
.hero-sub { color:var(--ink-2); font-size:.95rem; line-height:1.65; max-width:38rem; }

.dropzone { position:relative; width:100%; padding:44px 24px;
  background:var(--card); cursor:pointer; transition:background .25s; }
.dropzone:hover { background:var(--accent-soft); }
.corner { position:absolute; width:22px; height:22px; border-color:var(--line-2);
  border-style:solid; border-width:0; transition:border-color .25s; }
.dropzone:hover .corner { border-color:var(--accent); }
.corner.tl { top:0; left:0; border-top-width:2px; border-left-width:2px; }
.corner.tr { top:0; right:0; border-top-width:2px; border-right-width:2px; }
.corner.bl { bottom:0; left:0; border-bottom-width:2px; border-left-width:2px; }
.corner.br { bottom:0; right:0; border-bottom-width:2px; border-right-width:2px; }
.dz-icon { font-size:1.6rem; color:var(--accent); }
.dz-title { font-weight:600; font-size:1rem; }
.dz-hint { font-family:'IBM Plex Mono',monospace; font-size:.7rem;
  letter-spacing:.12em; color:var(--ink-2); }
.overlay-upload { position:absolute !important; inset:0; opacity:0; }
.overlay-upload .q-uploader { width:100% !important; height:100% !important;
  max-height:none !important; }

.panel { background:var(--card); border:1px solid var(--line); border-radius:10px; }
.panel-head { border-bottom:1px solid var(--line); padding:14px 20px; }
.panel-head-title { font-family:'IBM Plex Mono',monospace; font-size:.68rem;
  letter-spacing:.24em; text-transform:uppercase; color:var(--ink); font-weight:500; }
.panel-head-sub { font-family:'IBM Plex Mono',monospace; font-size:.68rem;
  color:var(--ink-2); }

.layer-row { border-bottom:1px solid var(--line); padding:13px 20px;
  transition:background .3s; }
.layer-row:last-child { border-bottom:none; }
.layer-active { background:var(--accent-soft); }
.layer-num { font-family:'IBM Plex Mono',monospace; font-size:.7rem;
  color:var(--line-2); font-weight:500; min-width:22px; transition:color .3s; }
.layer-active .layer-num { color:var(--accent); }
.layer-name { font-size:.9rem; font-weight:500; }
.layer-detail { font-size:.76rem; color:var(--ink-2); line-height:1.45; }

.chip { font-family:'IBM Plex Mono',monospace; font-size:.62rem; letter-spacing:.1em;
  padding:3px 10px; border-radius:4px; border:1px solid transparent; white-space:nowrap; }
.chip-wait { color:var(--na); border-color:var(--line); }
.chip-run { color:var(--accent); border-color:var(--accent); animation:pulse 1.1s infinite; }
.chip-ok { color:var(--ok); border-color:rgba(27,122,76,.4); background:#EDF6F0; }
.chip-alert { color:var(--alert); border-color:rgba(176,42,33,.4); background:#FAECEA; }
.chip-na { color:var(--na); border-color:var(--line-2); background:#F1F2F4; }

.doc-card { position:relative; overflow:hidden; }
.scanline { position:absolute; left:0; right:0; top:0; height:2px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent);
  box-shadow:0 0 16px 2px rgba(31,61,143,.35); animation:scan 1.5s linear infinite; }
@keyframes scan { 0%{top:0} 100%{top:100%} }

.verdict-card { border-left:5px solid var(--na); }
.verdict-ok { border-left-color:var(--ok); }
.verdict-fraud { border-left-color:var(--alert); }
.verdict-word { font-family:'IBM Plex Serif',serif; font-weight:600; font-size:2.1rem;
  letter-spacing:.01em; }
.fade-in { animation:fadein .5s ease-out; }
@keyframes fadein { from{opacity:0; transform:translateY(8px)} to{opacity:1; transform:none} }
.kpi-label { font-size:.62rem; letter-spacing:.2em; text-transform:uppercase; color:var(--ink-2); }
.kpi-value { font-family:'IBM Plex Mono',monospace; font-size:1.05rem; font-weight:500; }
.risk-track { width:100%; height:6px; background:var(--line); border-radius:3px; overflow:hidden; }
.risk-fill { height:100%; border-radius:3px; width:0; transition:width 1.1s cubic-bezier(.2,.7,.3,1); }

.smallprint { font-size:.72rem; color:var(--ink-2); line-height:1.6; }
.footer { border-top:1px solid var(--line); margin-top:40px; }

@media (prefers-reduced-motion: reduce) {
  .scanline, .live-dot, .chip-run { animation:none; }
  .risk-fill { transition:none; }
}
</style>
"""

CLICK_RELAY = """
<script>
document.addEventListener('click', (e) => {
  const dz = e.target.closest('.dropzone');
  if (!dz) return;
  const inp = dz.querySelector('input[type=file]');
  if (inp) inp.click();
});
</script>
"""


async def read_upload(e: events.UploadEventArguments) -> tuple[str, bytes]:
    upload = getattr(e, "file", None)
    if upload is not None:
        data = upload.read()
        if inspect.isawaitable(data):
            data = await data
        return upload.name, data
    data = e.content.read()
    if inspect.isawaitable(data):
        data = await data
    return e.name, data


async def call_flair_api(filename: str, content: bytes) -> dict:
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            API_URL,
            files={"file": (filename, content)},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        response.raise_for_status()
        return response.json()


def map_api_response(data: dict) -> dict:
    layers = data.get("layers", {})
    return {
        "verdict": str(data.get("verdict", "indéterminé")).upper(),
        "risk_score": data.get("risk_score", 0),
        "risk_level": str(data.get("risk_level", "—")).upper(),
        "credits": data.get("credits_charged", 1),
        "layers": {
            key: (
                layers.get(key, {}).get("status", "na"),
                layers.get(key, {}).get("finding", "—"),
                layers.get(key, {}).get("duration_ms", 0),
            )
            for key, _, _ in LAYERS
        },
    }


@ui.page("/")
def main_page():
    ui.add_head_html(HEAD)
    ui.add_body_html(CLICK_RELAY)

    with ui.element("div").classes("topbar"):
        with ui.row().classes("topbar-inner w-full items-center justify-between no-wrap"):
            ui.label("FLAIR").classes("wordmark")
            with ui.element("div").classes("live-badge"):
                ui.element("div").classes("live-dot")
                ui.label("api.myflair.app").classes("mono text-xs").style("color:var(--ink-2)")

    with ui.column().classes("w-full max-w-4xl mx-auto px-6 pt-14 pb-6 gap-10"):

        with ui.column().classes("gap-4"):
            ui.label("Moteur d'analyse — démonstration").classes("eyebrow")
            ui.html(
                "Huit couches forensiques.<br><em>Un verdict.</em>",
            ).classes("hero-title")
            ui.label(
                "Soumettez une pièce justificative — fiche de paie, justificatif, pièce "
                "d'identité. Le moteur exécute ses couches déterministes, puis n'escalade "
                "vers l'IA que si aucune ancre forte ne peut être vérifiée."
            ).classes("hero-sub")

        with ui.element("div").classes("dropzone"):
            for pos in ("tl", "tr", "bl", "br"):
                ui.element("div").classes(f"corner {pos}")
            with ui.column().classes("w-full items-center gap-2"):
                ui.label("⌖").classes("dz-icon mono")
                ui.label("Glissez une pièce justificative").classes("dz-title")
                ui.label("PDF · JPEG · PNG — ou cliquez pour parcourir").classes("dz-hint")
            with ui.element("div").classes("overlay-upload"):
                upload = ui.upload(
                    auto_upload=True,
                    on_upload=lambda e: analyze(e),
                ).props('accept=".pdf,image/*" flat')

        doc_slot = ui.column().classes("w-full")

        with ui.column().classes("panel w-full gap-0"):
            with ui.row().classes("panel-head w-full items-center justify-between no-wrap"):
                ui.label("Pipeline d'analyse").classes("panel-head-title")
                ui.label("déterministe → IA conditionnelle").classes("panel-head-sub")
            rows = {}
            for i, (key, name, subtitle) in enumerate(LAYERS, start=1):
                with ui.row().classes(
                    "layer-row w-full items-center justify-between no-wrap"
                ) as row:
                    with ui.row().classes("items-center gap-4 no-wrap"):
                        num = ui.label(f"{i:02d}").classes("layer-num")
                        with ui.column().classes("gap-0"):
                            ui.label(name).classes("layer-name")
                            detail = ui.label(subtitle).classes("layer-detail")
                    with ui.row().classes("items-center gap-3 no-wrap"):
                        timing = ui.label("").classes("mono text-xs").style("color:var(--ink-2)")
                        chip = ui.label("EN ATTENTE").classes("chip chip-wait")
                rows[key] = (row, detail, chip, timing, subtitle)

        verdict_area = ui.column().classes("w-full gap-4")

        with ui.column().classes("footer w-full pt-5 gap-1 items-center"):
            ui.label(
                "Les octets du document sont supprimés après traitement — seuls "
                "l'empreinte SHA-256 et les résultats d'analyse sont conservés."
            ).classes("smallprint text-center")
            ui.label("FLAIR — analyse forensique documentaire").classes(
                "mono"
            ).style("font-size:.64rem; color:var(--na); letter-spacing:.18em")

        def reset_rows():
            for key, (row, detail, chip, timing, subtitle) in rows.items():
                row.classes(remove="layer-active")
                detail.text = subtitle
                timing.text = ""
                chip.text = STATUS_META["wait"][0]
                chip.classes(
                    remove="chip-run chip-ok chip-alert chip-na", add="chip-wait"
                )

        async def analyze(e: events.UploadEventArguments):
            filename, content = await read_upload(e)
            sha256 = hashlib.sha256(content).hexdigest()
            size_kb = len(content) / 1024
            upload.reset()
            reset_rows()
            doc_slot.clear()
            verdict_area.clear()

            with doc_slot:
                with ui.column().classes("panel doc-card w-full p-4 gap-1 fade-in"):
                    scan = ui.element("div").classes("scanline")
                    ui.label(filename).classes("mono text-sm font-medium")
                    ui.label(f"{size_kb:,.0f} Ko · SHA-256 {sha256[:20]}…").classes(
                        "mono text-xs"
                    ).style("color:var(--ink-2)")

            for key, _, _ in LAYERS:
                chip = rows[key][2]
                chip.text = STATUS_META["run"][0]
                chip.classes(remove="chip-wait", add="chip-run")

            try:
                raw = await call_flair_api(filename, content)
                report = map_api_response(raw)
            except httpx.HTTPStatusError as exc:
                scan.delete()
                reset_rows()
                with verdict_area:
                    ui.label(
                        f"L'API a répondu {exc.response.status_code}. "
                        "Vérifiez la clé d'accès et le format du document."
                    ).classes("text-sm fade-in").style("color:var(--alert)")
                return
            except Exception as exc:
                scan.delete()
                reset_rows()
                with verdict_area:
                    ui.label(f"Connexion à l'API impossible : {exc}").classes(
                        "text-sm fade-in"
                    ).style("color:var(--alert)")
                return

            scan.delete()

            for key, _, _ in LAYERS:
                row, detail, chip, timing, _ = rows[key]
                status, finding, ms = report["layers"][key]
                row.classes(add="layer-active")
                await asyncio.sleep(0.3)
                label, css = STATUS_META.get(status, STATUS_META["na"])
                chip.text = label
                chip.classes(remove="chip-run", add=css)
                detail.text = finding
                if ms:
                    timing.text = f"{ms} ms"
                row.classes(remove="layer-active")

            total_ms = sum(ms for _, _, ms in report["layers"].values())
            is_ok = report["verdict"] in ("AUTHENTIQUE", "AUTHENTIC", "CLEAN")
            score = max(0, min(100, int(report["risk_score"])))

            with verdict_area:
                with ui.column().classes(
                    "panel verdict-card fade-in w-full p-6 gap-5 "
                    + ("verdict-ok" if is_ok else "verdict-fraud")
                ):
                    with ui.row().classes("w-full items-baseline justify-between no-wrap"):
                        ui.label(report["verdict"]).classes("verdict-word").style(
                            f"color:var({'--ok' if is_ok else '--alert'})"
                        )
                        if total_ms:
                            ui.label(f"analyse complète · {total_ms/1000:.2f} s").classes(
                                "mono text-xs"
                            ).style("color:var(--ink-2)")
                    with ui.column().classes("w-full gap-2"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label("Score de risque").classes("kpi-label")
                            ui.label(f"{score} / 100").classes("kpi-value")
                        with ui.element("div").classes("risk-track"):
                            fill = ui.element("div").classes("risk-fill").style(
                                f"background:var({'--ok' if is_ok else '--alert'})"
                            )
                        ui.timer(0.15, lambda: fill.style(f"width:{score}%"), once=True)
                    with ui.row().classes("w-full gap-12"):
                        for lab, val in [
                            ("Niveau", report["risk_level"]),
                            ("Crédits consommés", str(report["credits"])),
                            ("Empreinte", f"{sha256[:12]}…"),
                        ]:
                            with ui.column().classes("gap-1"):
                                ui.label(lab).classes("kpi-label")
                                ui.label(val).classes("kpi-value")

                with ui.expansion("Réponse JSON de l'API").classes(
                    "panel w-full mono text-sm"
                ):
                    ui.code(
                        json.dumps(raw, indent=2, ensure_ascii=False), language="json"
                    ).classes("w-full")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        title="FLAIR",
        favicon="🛡️",
        reload=False,
        show=False,
    )
