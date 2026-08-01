"""Tout le CSS et le logo de la démo. Aucun code Python métier ici."""

# Logo officiel. `currentColor` au lieu de la couleur d'origine (#1A1A1B) pour
# qu'il suive la couleur du texte définie en CSS.
LOGO = """
<svg class="logo" viewBox="0 0 168 62" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Flair">
  <path fill="currentColor" d="M24.8827 24.032C25.1786 23.9885 26.0419 24.0024 26.3915 24.0012L37.3333 24.032C40 24.032 40 24.0012 40 27.3205L39.998 44.5726L30.5258 44.5674C28.9152 44.5655 25.7296 44.4499 24.3008 44.7901C22.9888 45.1109 21.7869 45.8118 20.8305 46.8142C19.8825 47.8107 19.2121 49.0639 18.8932 50.4367C18.5593 51.8456 18.6617 54.2438 18.663 55.8018L18.6636 62H0.00629865L0.00387221 55.0249C0.0036754 53.2219 -0.0341777 50.4377 0.131008 48.6411C0.666517 42.8197 2.9599 37.3355 6.67179 32.9996C11.4823 27.376 17.7663 24.4128 24.8827 24.032Z"/>
  <path fill="currentColor" d="M23.2972 0.0785514C24.4818 -0.0619647 27.5897 0.0288812 28.9192 0.028952L40 0.0254864V17C40 20 40 20.9986 37.3333 20.9986L7.62498e-10 21C1.15373 17.016 2.8082 12.6596 5.36951 9.50473C9.92926 3.89293 16.3903 0.495784 23.2972 0.0785514Z"/>
  <path fill="currentColor" d="M45.0002 62C45.0002 62 45.0005 30.2377 45 27C44.9997 25.251 50 24.5067 50 22.5C50 20.4933 44.9998 19.8917 45 18C44.9996 16.4613 45.0002 0 45.0002 0H58.3606V62H45.0002Z"/>
  <path fill="currentColor" d="M82.9001 62C79.1703 62 75.8303 61.0258 72.8798 59.0774C69.9851 57.0734 67.6749 54.3456 65.9491 50.8942C64.2234 47.3871 63.3606 43.4346 63.3606 39.0368C63.3606 34.5277 64.2234 30.5474 65.9491 27.096C67.6749 23.6446 70.0408 20.9447 73.0468 18.9963C76.0529 16.9922 79.4765 15.9902 83.3176 15.9902C85.433 15.9902 87.3536 16.2964 89.0793 16.9087C90.8607 17.5211 92.4194 18.3839 93.7554 19.4973C95.0915 20.555 96.2327 21.8075 97.179 23.2549C98.1254 24.6466 98.8213 26.1496 99.2666 27.764L96.511 27.43V16.9087H109.788V61.2485H96.2605V50.5602L99.2666 50.4767C98.8213 52.0354 98.0976 53.5106 97.0955 54.9023C96.0935 56.294 94.8688 57.5187 93.4214 58.5764C91.9741 59.6341 90.3597 60.4691 88.5783 61.0815C86.7969 61.6938 84.9042 62 82.9001 62ZM86.5742 50.7272C88.634 50.7272 90.4153 50.254 91.9184 49.3076C93.4214 48.3613 94.5905 47.0252 95.4255 45.2995C96.2605 43.5181 96.678 41.4306 96.678 39.0368C96.678 36.6431 96.2605 34.5834 95.4255 32.8577C94.5905 31.0763 93.4214 29.7124 91.9184 28.7661C90.4153 27.764 88.634 27.263 86.5742 27.263C84.5702 27.263 82.8166 27.764 81.3136 28.7661C79.8662 29.7124 78.725 31.0763 77.89 32.8577C77.055 34.5834 76.6374 36.6431 76.6374 39.0368C76.6374 41.4306 77.055 43.5181 77.89 45.2995C78.725 47.0252 79.8662 48.3613 81.3136 49.3076C82.8166 50.254 84.5702 50.7272 86.5742 50.7272Z"/>
  <path fill="currentColor" d="M116.021 62V17.6602C121.443 18.8754 124.398 19.0466 129.381 17.6602V62H116.021ZM122.83 14.6146C120.317 14.6146 118.334 14.0206 116.882 12.8328C115.486 11.5883 114.788 9.83478 114.788 7.57215C114.788 5.53579 115.514 3.8671 116.966 2.56609C118.418 1.26509 120.373 0.614578 122.83 0.614578C125.343 0.614578 127.298 1.2368 128.694 2.48125C130.09 3.66913 130.788 5.3661 130.788 7.57215C130.788 9.66508 130.062 11.3621 128.61 12.6631C127.214 13.9641 125.287 14.6146 122.83 14.6146Z"/>
  <path fill="currentColor" d="M135.788 62V17.6602H148.48L149.065 32.1061L146.56 29.3506C147.228 26.9568 148.313 24.8136 149.816 22.9209C151.375 21.0282 153.184 19.5251 155.244 18.4118C157.304 17.2984 159.503 16.7417 161.841 16.7417C162.843 16.7417 163.761 16.8252 164.596 16.9922C165.487 17.1592 166.294 17.3541 167.018 17.5767L163.344 32.3567C162.731 31.967 161.896 31.6608 160.839 31.4381C159.837 31.1598 158.779 31.0206 157.666 31.0206C156.441 31.0206 155.3 31.2433 154.242 31.6886C153.184 32.0783 152.294 32.6628 151.57 33.4422C150.846 34.2215 150.262 35.1401 149.816 36.1978C149.427 37.2555 149.232 38.4523 149.232 39.7884V62H135.788Z"/>
</svg>
"""

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@0,500;0,600;1,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --paper:#F5F4EE; --card:#FFFFFF; --ink:#14171C; --ink-2:#5B626B;
  --line:#E2E0D6; --line-2:#CFCDC2; --accent:#1F3D8F; --accent-soft:#EEF1F9;
  --ok:#1B7A4C;      --ok-soft:#EDF6F0;
  --suspect:#B4700F; --suspect-soft:#FBF2E4;
  --fraud:#B02A21;   --fraud-soft:#FAECEA;
  --na:#8A9099;      --na-soft:#F1F2F4;
  --tbu:#6E7681;     --tbu-soft:#F4F5F7;
  --err:#5A4B7C;     --err-soft:#EFECF6;
}
body {
  background-color:var(--paper) !important; color:var(--ink);
  font-family:'IBM Plex Sans',sans-serif;
  background-image:radial-gradient(rgba(31,61,143,.055) 1px, transparent 1px);
  background-size:26px 26px;
}
.nicegui-content { padding:0 !important; }
.mono { font-family:'IBM Plex Mono',monospace; }

/* ---------- barre supérieure ---------- */
.topbar { position:sticky; top:0; z-index:50; width:100%;
  background:rgba(245,244,238,.82); backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line); }
.topbar-inner { max-width:56rem; margin:0 auto; padding:14px 24px; }
.logo { height:26px; width:auto; display:block; color:var(--ink); }
.logo-footer { height:20px; width:auto; display:block; color:var(--na); opacity:.75; }
.live-badge { display:flex; align-items:center; gap:8px;
  border:1px solid var(--line-2); border-radius:99px; padding:5px 14px;
  background:var(--card); }
.live-dot { width:7px; height:7px; border-radius:50%; background:var(--ok);
  animation:pulse 2.2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

/* ---------- en-tête de page ---------- */
.eyebrow { font-family:'IBM Plex Mono',monospace; font-size:.66rem;
  letter-spacing:.28em; text-transform:uppercase; color:var(--accent); }
.hero-title { font-family:'IBM Plex Serif',serif; font-weight:600;
  font-size:clamp(2.1rem,4.5vw,3rem); line-height:1.12; letter-spacing:-.01em; }
.hero-title em { font-style:italic; font-weight:500; color:var(--accent); }
.hero-sub { color:var(--ink-2); font-size:.95rem; line-height:1.65; max-width:38rem; }

/* ---------- zone de dépôt ---------- */
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

/* ---------- conteneurs ---------- */
.panel { background:var(--card); border:1px solid var(--line); border-radius:10px; }
.section-title { font-family:'IBM Plex Mono',monospace; font-size:.66rem;
  letter-spacing:.24em; text-transform:uppercase; color:var(--ink-2); }
.doc-card { position:relative; overflow:hidden; }
.scanline { position:absolute; left:0; right:0; top:0; height:2px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent);
  box-shadow:0 0 16px 2px rgba(31,61,143,.35); animation:scan 1.5s linear infinite; }
@keyframes scan { 0%{top:0} 100%{top:100%} }
.fade-in { animation:fadein .45s ease-out; }
@keyframes fadein { from{opacity:0; transform:translateY(8px)} to{opacity:1; transform:none} }

/* ---------- aperçu du document analysé ---------- */
.preview { width:100%; background:#EFEEE8; border:1px solid var(--line);
  border-radius:8px; padding:12px; display:flex; justify-content:center;
  align-items:center; }
.preview img { max-width:100%; max-height:440px; object-fit:contain;
  border-radius:3px; background:#fff;
  box-shadow:0 1px 3px rgba(20,23,28,.10), 0 6px 18px rgba(20,23,28,.10); }
.preview-pdf { padding:0; background:var(--card); overflow:hidden; }
.preview-pdf iframe { width:100%; height:540px; border:none; display:block;
  background:var(--card); }
.preview-none { font-size:.8rem; color:var(--ink-2); text-align:center;
  padding:26px 16px; line-height:1.6; }
.preview-caption { font-family:'IBM Plex Mono',monospace; font-size:.62rem;
  letter-spacing:.16em; text-transform:uppercase; color:var(--na); }

/* ---------- pastilles d'état ---------- */
.dot { width:11px; height:11px; border-radius:50%; flex:none; }
.dot-ok      { background:var(--ok); }
.dot-suspect { background:var(--suspect); }
.dot-fraud   { background:var(--fraud); }
.dot-na      { background:transparent; border:2px solid var(--na); }
.dot-tbu     { background:transparent; border:2px dashed var(--tbu); }
.dot-error   { background:var(--err); box-shadow:0 0 0 3px var(--err-soft); }
.dot-pending { background:var(--accent); animation:pulse 1.1s infinite; }

/* ---------- badges de sévérité ---------- */
.sev { font-family:'IBM Plex Mono',monospace; font-size:.6rem; letter-spacing:.12em;
  text-transform:uppercase; padding:2px 9px; border-radius:3px;
  border:1px solid transparent; white-space:nowrap; }
.sev-ok      { color:var(--ok);      border-color:rgba(27,122,76,.35);  background:var(--ok-soft); }
.sev-suspect { color:var(--suspect); border-color:rgba(180,112,15,.35); background:var(--suspect-soft); }
.sev-fraud   { color:var(--fraud);   border-color:rgba(176,42,33,.35);  background:var(--fraud-soft); }
.sev-na      { color:var(--na);      border-color:var(--line-2);        background:var(--na-soft); }
.sev-tbu     { color:var(--tbu);     border-color:var(--line-2);        background:var(--tbu-soft); }
.sev-error   { color:var(--err);     border-color:rgba(90,75,124,.35);  background:var(--err-soft); }
.sev-pending { color:var(--accent);  border-color:var(--accent); animation:pulse 1.1s infinite; }

/* ---------- carte de signal ---------- */
.signal { border:1px solid var(--line); border-left-width:4px; border-radius:8px;
  background:var(--card); padding:13px 15px; }
.signal-ok      { border-left-color:var(--ok); }
.signal-suspect { border-left-color:var(--suspect); }
.signal-fraud   { border-left-color:var(--fraud); }
.signal-na      { border-left-color:var(--line-2); }
.signal-tbu     { border-left-color:var(--tbu); }
.signal-error   { border-left-color:var(--err); }
.signal-pending { border-left-color:var(--accent); }
.signal-title { font-family:'IBM Plex Mono',monospace; font-size:.67rem;
  letter-spacing:.16em; text-transform:uppercase; font-weight:500; }
.signal-verdict { font-size:.88rem; line-height:1.5; }
.signal-bullets { font-size:.8rem; line-height:1.6; color:var(--ink-2);
  padding-left:16px; margin:0; }
.signal-bullets li { margin:2px 0; }

/* ---------- bloc dépliable ---------- */
.disclosure-head { font-family:'IBM Plex Mono',monospace; font-size:.66rem;
  letter-spacing:.16em; text-transform:uppercase; color:var(--ink-2);
  cursor:pointer; user-select:none; padding-top:9px; }
.disclosure-head:hover { color:var(--accent); }
.caret { display:inline-block; transition:transform .2s; }
.caret-open { transform:rotate(90deg); }
.sep { height:1px; background:var(--line); width:100%; }

/* ---------- tableau clé / valeur ---------- */
.kv { padding:5px 0; border-bottom:1px dashed var(--line); align-items:flex-start; gap:16px; }
.kv:last-child { border-bottom:none; }
.kv-k { font-size:.76rem; color:var(--ink-2); flex:1 1 45%; }
.kv-v { font-size:.76rem; text-align:right; flex:1 1 55%; word-break:break-word; }

/* ---------- couche ---------- */
.layer { overflow:hidden; }
.layer-head { padding:15px 18px; cursor:pointer; user-select:none;
  transition:background .2s; }
.layer-head:hover { background:var(--accent-soft); }
.layer-num { font-family:'IBM Plex Mono',monospace; font-size:.7rem;
  color:var(--line-2); font-weight:500; min-width:24px; }
.layer-name { font-size:.94rem; font-weight:600; }
.layer-headline { font-size:.8rem; color:var(--ink-2); line-height:1.45; }
.layer-body { border-top:1px solid var(--line); padding:16px 18px; background:#FCFCFA; }
.layer-meta { font-family:'IBM Plex Mono',monospace; font-size:.63rem; color:var(--na); }

/* ---------- verdict global ---------- */
.verdict { border-left:5px solid var(--na); }
.verdict-ok      { border-left-color:var(--ok); }
.verdict-suspect { border-left-color:var(--suspect); }
.verdict-fraud   { border-left-color:var(--fraud); }
.verdict-na      { border-left-color:var(--na); }
.verdict-word { font-family:'IBM Plex Serif',serif; font-weight:600; font-size:2.1rem;
  letter-spacing:.01em; line-height:1.1; }
.verdict-headline { font-size:1rem; line-height:1.55; font-weight:500; }
.kpi-label { font-size:.6rem; letter-spacing:.2em; text-transform:uppercase; color:var(--ink-2); }
.engine-summary { border-left:2px solid var(--line-2); padding:2px 0 2px 14px; }
.engine-summary-text { font-size:.83rem; line-height:1.6; color:var(--ink-2); }
.kpi-value { font-family:'IBM Plex Mono',monospace; font-size:.95rem; font-weight:500; }
.dedup-banner { background:var(--accent-soft); border:1px solid rgba(31,61,143,.18);
  border-radius:7px; padding:11px 14px; color:var(--accent); }
.dedup-text { font-size:.79rem; line-height:1.55; color:var(--ink-2); }

/* ---------- retour utilisateur ---------- */
.feedback { border-left:5px solid var(--accent); }
.feedback-title { font-family:'IBM Plex Serif',serif; font-weight:600; font-size:1.15rem; }
.feedback-question { font-size:.9rem; font-weight:500; }
.fb-btn { min-width:88px; border-radius:6px !important; font-size:.85rem !important; }
.fb-btn-active { background:var(--accent) !important; color:#fff !important;
  border-color:var(--accent) !important; }
.fb-submit { background:var(--accent) !important; color:#fff !important;
  border-radius:6px !important; font-size:.85rem !important; }
.fbgroup { padding:10px 0 4px 0; border-top:1px dashed var(--line); }
.fbgroup-title { font-family:'IBM Plex Mono',monospace; font-size:.66rem;
  letter-spacing:.16em; text-transform:uppercase; color:var(--ink); font-weight:500; }
.fbgroup-help { font-size:.74rem; color:var(--ink-2); margin-bottom:2px; }
.fbcheck .q-checkbox__label { font-size:.83rem; line-height:1.45; }
.fbtext .q-field__control { background:var(--card); font-size:.85rem; }
.fberror { font-size:.8rem; color:var(--fraud); }

/* zone de dépôt verrouillée tant que le retour n'est pas donné */
.dropzone-locked { opacity:.45; pointer-events:none; filter:grayscale(1); }
.dropzone-notice { font-size:.78rem; color:var(--accent); text-align:center;
  padding-top:8px; }

/* ---------- panneau d'options ---------- */
.optpanel { overflow:hidden; }
.optpanel-head { padding:12px 18px; cursor:pointer; user-select:none;
  transition:background .2s; }
.optpanel-head:hover { background:var(--accent-soft); }
.optpanel-title { font-family:'IBM Plex Mono',monospace; font-size:.68rem;
  letter-spacing:.2em; text-transform:uppercase; font-weight:500; }
.optpanel-body { border-top:1px solid var(--line); padding:16px 18px;
  background:#FCFCFA; gap:0; }
.optrow { padding:11px 0; border-bottom:1px dashed var(--line); }
.optrow:last-child { border-bottom:none; }
.optname { font-size:.85rem; font-weight:500; }
.optexamples { font-size:.74rem; color:var(--ink-2); }
.optselect { min-width:132px; }
.optselect .q-field__control { font-family:'IBM Plex Mono',monospace;
  font-size:.75rem; background:var(--card); }

/* ---------- comparaison avant / après ---------- */
.difflegend { padding:4px 0 10px 0; border-bottom:1px solid var(--line);
  margin-bottom:10px; }
.diffcard { border:1px solid var(--line); border-left-width:4px; border-radius:8px;
  background:var(--card); padding:12px 14px; margin-bottom:10px; }
.diffcard-fraud   { border-left-color:var(--fraud); }
.diffcard-suspect { border-left-color:var(--suspect); }
.diffcard-na      { border-left-color:var(--line-2); }
.diffgrid { display:grid; grid-template-columns:1fr auto 1fr; gap:12px;
  align-items:stretch; }
.diffside { border-radius:6px; padding:9px 12px; gap:4px; min-width:0; }
.diffside-before { background:#F6F5F0; border:1px solid var(--line); }
.diffside-after  { background:var(--fraud-soft); border:1px solid rgba(176,42,33,.28); }
.difflabel { font-family:'IBM Plex Mono',monospace; font-size:.58rem;
  letter-spacing:.16em; text-transform:uppercase; color:var(--na); }
.diffvalue { font-family:'IBM Plex Mono',monospace; font-size:.82rem;
  line-height:1.45; color:var(--ink); word-break:break-word; white-space:normal; }
.diffside-after .diffvalue { color:var(--fraud); font-weight:500; }
.diffvalue-empty { color:var(--na) !important; font-style:italic; font-weight:400 !important; }
.diffarrow { align-self:center; color:var(--na); font-size:1rem; }
/* Recoupements : la couleur du panneau droit suit le résultat du contrôle. */
.checkside-ok    { background:var(--ok-soft);    border:1px solid rgba(27,122,76,.28); }
.checkside-fraud { background:var(--fraud-soft); border:1px solid rgba(176,42,33,.28); }
.checkside-na    { background:#F6F5F0;           border:1px solid var(--line); }
.checkvalue-ok    { color:var(--ok);    font-weight:500; }
.checkvalue-fraud { color:var(--fraud); font-weight:500; }
.diffhint { font-size:.73rem; line-height:1.5; color:var(--ink-2); font-style:italic;
  padding-left:2px; }
@media (max-width:640px) {
  .diffgrid { grid-template-columns:1fr; }
  .diffarrow { transform:rotate(90deg); justify-self:center; }
}

/* ---------- tableau des métadonnées ---------- */
.mtable { border:1px solid var(--line); border-radius:9px; overflow:hidden;
  background:var(--card); }
.mrow { display:grid; grid-template-columns:minmax(150px,1fr) minmax(0,1.5fr) 92px;
  gap:16px; padding:11px 15px; border-bottom:1px solid var(--line);
  align-items:center; }
.mrow:last-child { border-bottom:none; }
.mrow:nth-child(even) { background:#FBFBF7; }
.mhead { background:#F4F3ED !important; padding-top:9px; padding-bottom:9px; }
.mhead .mcat { font-family:'IBM Plex Mono',monospace; font-size:.6rem;
  letter-spacing:.18em; text-transform:uppercase; color:var(--na); }
.mrow-fraud   { box-shadow:inset 3px 0 0 var(--fraud); }
.mrow-suspect { box-shadow:inset 3px 0 0 var(--suspect); }
.mrow-error   { box-shadow:inset 3px 0 0 var(--err); }
.mcat { font-size:.79rem; color:var(--ink-2); font-weight:500; }
.mval { font-family:'IBM Plex Mono',monospace; font-size:.79rem; color:var(--ink);
  word-break:break-word; }
.mrisk { justify-self:end; text-align:center; min-width:82px;
  font-family:'IBM Plex Mono',monospace; font-size:.6rem; letter-spacing:.1em;
  text-transform:uppercase; padding:3px 8px; border-radius:4px;
  border:1px solid transparent; }
.mnote { grid-column:1 / -1; font-size:.74rem; line-height:1.5; color:var(--ink-2);
  margin-top:-2px; }
@media (max-width:640px) {
  .mrow { grid-template-columns:1fr auto; gap:6px 12px; }
  .mval { grid-column:1 / -1; }
}

/* ---------- pied de page ---------- */
.smallprint { font-size:.72rem; color:var(--ink-2); line-height:1.6; }
.footer { border-top:1px solid var(--line); margin-top:40px; }

@media (prefers-reduced-motion: reduce) {
  .scanline, .live-dot, .dot-pending, .sev-pending { animation:none; }
  .risk-fill { transition:none; }
}
</style>
"""

# Relaie le clic sur la zone de dépôt vers l'input fichier caché en dessous.
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
