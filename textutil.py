#!/usr/bin/env python3
"""Central text utilities for the Heavy Reading site builders.

No dependencies on other site modules, so every builder (including
build_st3_dashboard, which shared.py itself imports) can use these without
circular imports.

Two jobs:
  1. license_label(): the single canonical mapping from internal license keys
     (which drive the data-licensed gating) to user-facing display labels.
     The vendor behind "wood-mackenzie" is never named in rendered copy.
  2. anon_text() / anon_data(): Heavy Reading publishes anonymously. These
     strip identity references from rendered copy. Applied to data at render
     time in the builders; repo-internal records keep their provenance.
"""
import re
from pathlib import Path

# Internal license keys -> user-facing display labels. Never render a raw key.
LICENSE_DISPLAY = {
    "wood-mackenzie": "commercial storage",
    "eikon": "licensed: Eikon transcription",
    "public": "public",
}


def license_label(key):
    """User-facing label for a license key. Unknown keys pass through."""
    return LICENSE_DISPLAY.get(key, key)


_ANON_RULES = [
    # Vendor: never name Wood Mackenzie in rendered copy; it reads as
    # "commercial storage" (Blaine's label).
    (re.compile(r"(?i)\bwood mackenzie\b(?!-)"), "commercial storage"),
    (re.compile(r"(?i)\bwood mack\b(?!-)"), "commercial storage"),
    (re.compile(r"[Aa]pproved by Blaine"), "Approved"),
    (re.compile(r"per Blaine's ruling"), "per the editorial ruling"),
    (re.compile(r"Blaine's ruling"), "the editorial ruling"),
    (re.compile(r"\bBlaine ruling\b"), "editorial ruling"),
    (re.compile(r"\(Blaine-approved ([^)]*)\)"), r"(approved \1)"),
    (re.compile(r"Blaine-approved"), "approved"),
    (re.compile(r"Blaine's"), "the editor's"),
    (re.compile(r"\bBlaine\b"), "the editor"),
    (re.compile(r"(?i)\bhodder\b"), ""),
    (re.compile(r"blainehodder@gmail\.com"), ""),
]


def anon_text(t):
    """Neutralize identity references in a rendered string."""
    if not isinstance(t, str):
        return t
    for rx, rep in _ANON_RULES:
        t = rx.sub(rep, t)
    return t


def anon_data(o):
    """Recursively apply anon_text to every string in a nested structure."""
    if isinstance(o, dict):
        return {k: anon_data(v) for k, v in o.items()}
    if isinstance(o, list):
        return [anon_data(v) for v in o]
    if isinstance(o, str):
        return anon_text(o)
    return o


# ----------------------------------------------------------------------------
# Brand identity: Heavy Reading. Self-contained (inline SVG / data URIs only),
# so the static output makes no asset requests beyond the font stylesheet.
# ----------------------------------------------------------------------------

# Wordmark: "Heavy Reading" in the Fraunces serif (loaded via FONT_LINKS).
# Mark: rising bars, ink tile with a red lead bar (data, strata, momentum).
LOGO_SVG = (
    '<svg class="mark" viewBox="0 0 44 44" aria-hidden="true" focusable="false">'
    '<rect x="1.5" y="1.5" width="41" height="41" rx="9" fill="#17191d"/>'
    '<rect x="10" y="25" width="6.5" height="8" fill="#f4f1e8"/>'
    '<rect x="18.75" y="18" width="6.5" height="15" fill="#f4f1e8"/>'
    '<rect x="27.5" y="11" width="6.5" height="22" fill="#a13c22"/>'
    "</svg>"
)

FAVICON_LINK = (
    '<link rel="icon" href="data:image/svg+xml,'
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 44 44'%3E"
    "%3Crect x='1.5' y='1.5' width='41' height='41' rx='9' fill='%2317191d'/%3E"
    "%3Crect x='10' y='25' width='6.5' height='8' fill='%23f4f1e8'/%3E"
    "%3Crect x='18.75' y='18' width='6.5' height='15' fill='%23f4f1e8'/%3E"
    "%3Crect x='27.5' y='11' width='6.5' height='22' fill='%23a13c22'/%3E"
    "%3C/svg%3E\">"
)

# Editorial type system: Fraunces (display serif) + Inter (grotesque, tabular
# numerals), fully self-contained. The variable WOFF2 files live in
# site/fonts/ (latin subsets, OFL licensed) and are embedded as data URIs so
# the public build makes zero external requests. Variable weight range
# 100-900 covers every weight the CSS uses (400-800).
def _font_face():
    import base64
    fdir = Path(__file__).resolve().parent / "fonts"
    out = ["<style>"]
    for family, fname in (("Fraunces", "fraunces-latin.woff2"),
                          ("Inter", "inter-latin.woff2")):
        b64 = base64.b64encode((fdir / fname).read_bytes()).decode("ascii")
        out.append(
            f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:100 900;font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
    out.append("</style>")
    return "\n".join(out)


FONT_LINKS = _font_face()


def brand_lockup(home_href, wordmark_tag="span"):
    """Masthead lockup: logo mark + serif wordmark + tagline. No emojis.

    wordmark_tag="h1" on the home page so the page has exactly one h1
    (the brand) instead of a duplicated heading below the masthead."""
    return (
        f'<div class="brandlock"><a class="brandlink" href="{home_href}" '
        'aria-label="Heavy Reading: home">'
        f"{LOGO_SVG}"
        f'<span class="wordstack"><{wordmark_tag} class="wordmark">Heavy Reading</{wordmark_tag}>'
        '<span class="wordsub">The WCSB supply letter</span></span>'
        "</a></div>"
    )


# JavaScript twin of LICENSE_DISPLAY, for builders that render lic-tags
# client-side (st3 dashboard rowHtml). Keep in sync.
LICENSE_DISPLAY_JS = """var LICENSE_LABEL = {
  "wood-mackenzie": "commercial storage",
  "eikon": "licensed: Eikon transcription",
  "public": "public"
};
function licenseLabel(k) { return LICENSE_LABEL[k] || k; }"""


# ----------------------------------------------------------------------------
# Heavy Reading design system v3.
#
# Typography is the design. Fraunces (display serif, optical sizing) carries
# every headline; Inter carries body and UI. Three sizes do all the work:
# display, body, whisper. Color is almost invisible: warm paper, warm ink,
# hairlines, one muted oxide red used sparingly. No boxes, no shadows, no
# saturated color anywhere. Dense-but-calm: the calm of a printed magazine
# applied to data, never a trading terminal.
# ----------------------------------------------------------------------------
PAGE_CSS = """
:root {
  --paper:#faf8f4; --ink:#1e1b16; --mut:#6f675b; --faint:#a79d8d;
  --line:#e6e1d4; --line2:#f0ece1;
  --acc:#a13c22; --acc-deep:#7c2e1a;
  --serif:"Fraunces",Georgia,"Times New Roman",serif;
  --sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  /* chart instrument: every color a chart may use, so one build serves both
     themes and the toggle switches instantly. */
  --ch-ink:#1e1b16; --ch-ink-lab:#f6f2e9;
  --ch-ink2:#2e2a23; --ch-ink2-lab:#f6f2e9;
  --ch-acc:#a13c22; --ch-acc-lab:#f6f2e9;
  --ch-steel:#6f7d8c; --ch-steel-lab:#f6f2e9;
  --ch-g1:#5c564a; --ch-g1-lab:#f6f2e9;
  --ch-g2:#8a8177; --ch-g2-lab:#f6f2e9;
  --ch-g3:#b9ab8d; --ch-g3-lab:#1e1b16;
  --ch-g4:#c9bfae; --ch-g4-lab:#1e1b16;
  --ch-nc:#97814f; --ch-nc-lab:#f6f2e9;
  --ch-fc:#62798b; --ch-fc-lab:#f6f2e9;
  --ch-sand:#a89c86; --ch-sand-lab:#1e1b16;
  --ch-blue:#2f6fb2; --ch-blue-lab:#f6f2e9;
  --ch-red:#b42318; --ch-red-lab:#f6f2e9;
  --ch-gray:#7a7a7a; --ch-gray-lab:#1e1b16;
  --ch-grid:#e6e1d4; --ch-axis:#d8d2c2;
  --ch-band-nc:#efe6cf; --ch-band-fc:#e7ebee;
  --ch-evt:#a89c86;
  --ch-wash-acc:rgba(161,60,34,.10); --ch-wash-acc2:rgba(161,60,34,.45);
  --ch-wash-nc:rgba(151,129,79,.10);
  --ch-pat:rgba(201,138,27,.35);
}
/* Dark: warm charcoal, never pure black. Restrained and muted throughout;
   charts keep their relative ordering, lifted for the dark ground. */
[data-theme="dark"] {
  --paper:#201d18; --ink:#ece6d9; --mut:#a89d89; --faint:#7e7565;
  --line:#38332b; --line2:#2c2822;
  --acc:#cf7150; --acc-deep:#e08a63;
  --ch-ink:#ece6d9; --ch-ink-lab:#201d18;
  --ch-ink2:#cfc7b4; --ch-ink2-lab:#201d18;
  --ch-acc:#cf7150; --ch-acc-lab:#201d18;
  --ch-steel:#8ba0b3; --ch-steel-lab:#201d18;
  --ch-g1:#9a917f; --ch-g1-lab:#201d18;
  --ch-g2:#7d7466; --ch-g2-lab:#ece6d9;
  --ch-g3:#6b6252; --ch-g3-lab:#ece6d9;
  --ch-g4:#57503f; --ch-g4-lab:#ece6d9;
  --ch-nc:#b39a5e; --ch-nc-lab:#201d18;
  --ch-fc:#7d94a8; --ch-fc-lab:#201d18;
  --ch-sand:#6e6656; --ch-sand-lab:#ece6d9;
  --ch-blue:#6f9fd8; --ch-blue-lab:#201d18;
  --ch-red:#d95f4e; --ch-red-lab:#201d18;
  --ch-gray:#9a9a9a; --ch-gray-lab:#201d18;
  --ch-grid:#37322a; --ch-axis:#4a4438;
  --ch-band-nc:#2c2820; --ch-band-fc:#222a31;
  --ch-evt:#6e6656;
  --ch-wash-acc:rgba(207,113,80,.16); --ch-wash-acc2:rgba(207,113,80,.5);
  --ch-wash-nc:rgba(179,154,94,.18);
  --ch-pat:rgba(179,154,94,.45);
}
* { box-sizing:border-box; }
html { -webkit-text-size-adjust:100%; scroll-behavior:smooth; }
html, body { overflow-x:clip; }
::selection { background:rgba(161,60,34,.16); }
body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans);
       font-size:16px; line-height:1.65; -webkit-font-smoothing:antialiased;
       font-optical-sizing:auto;
       font-feature-settings:"pnum" on, "lnum" on, "liga" on, "tnum" on; }
.wrap { max-width:1080px; margin:0 auto; padding:0 24px 80px; }
:focus-visible { outline:2px solid var(--acc); outline-offset:3px; border-radius:2px; }

/* ---- masthead: brand, then nav, then search. Nothing else. ---- */
.masthead { padding:26px 0 0; }
.brandlock { padding:0 0 6px; }
.brandlink { display:inline-flex; align-items:center; gap:14px; text-decoration:none;
  color:var(--ink); }
.mark { width:40px; height:40px; display:block; flex:none; }
.wordstack { display:flex; flex-direction:column; }
.wordmark { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:32px; letter-spacing:-0.02em; line-height:1; }
.wordsub { font-size:10.5px; letter-spacing:.24em; text-transform:uppercase;
  color:var(--mut); margin-top:7px; font-weight:600; }
/* theme toggle: one quiet word, top-right of the masthead. */
.masthead { position:relative; }
.themetoggle { position:absolute; top:2px; right:0; background:none; border:0;
  padding:6px 2px; font:inherit; font-size:12px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--faint); cursor:pointer; }
.themetoggle:hover { color:var(--acc); }

/* section nav: a quiet ruled bar. Text links, hairlines, no pills, no shadows. */
.mnav { display:block; margin:18px 0 0; padding:0; border:0; }
.mnav > summary { list-style:none; }
.mnav > summary::-webkit-details-marker { display:none; }
.mnav > summary::marker { content:""; }
.navburger { display:none; }
.sitenav { display:flex; gap:0; border-top:1px solid var(--ink);
  border-bottom:1px solid var(--line); }
.navdrop { position:relative; }
.nd > summary { list-style:none; display:flex; align-items:center; cursor:pointer; }
.nd > summary::-webkit-details-marker { display:none; }
.nd-top { color:var(--ink); text-decoration:none; font-size:12px; font-weight:600;
  letter-spacing:.1em; text-transform:uppercase; padding:15px 16px 13px;
  white-space:nowrap; border-bottom:2px solid transparent; margin-bottom:-1px; }
.nd-caret { display:inline-block; width:0; height:0; margin:1px 14px 0 -8px;
  border-left:4px solid transparent; border-right:4px solid transparent;
  border-top:5px solid var(--faint); flex:none; }
.navdrop.active .nd-top { border-bottom-color:var(--acc); }
.nd-menu { display:none; position:absolute; top:100%; left:0; z-index:50;
  background:var(--paper); border:1px solid var(--line);
  padding:6px; min-width:230px; max-width:calc(100vw - 32px); }
.navdrop:last-child .nd-menu, .navdrop:nth-last-child(2) .nd-menu {
  left:auto; right:0; }
.nd:hover .nd-menu, .nd[open] .nd-menu, .nd:focus-within .nd-menu {
  display:block; opacity:1; visibility:visible; transform:none;
  transition:opacity .12s ease .08s, visibility 0s, transform .12s ease .08s; }
/* hover intent: a short fuse on open, a longer one on close, so a stray
   pass doesn't fling a menu over the page heading */
.nd-menu { opacity:0; visibility:hidden; transform:translateY(-3px);
  transition:opacity .12s ease, transform .12s ease, visibility 0s linear .22s; }
.nd-menu .mi { display:block; color:var(--ink); text-decoration:none;
  font-size:14px; padding:8px 12px; white-space:nowrap; }
.nd-menu .mi[aria-current="page"] { font-weight:700; }
@media (hover:hover) {
  .nd-menu .mi:hover { color:var(--acc-deep); }
  .nd-top:hover { color:var(--acc-deep); }
}
.nd-megahead .mi { font-weight:600; }
.nd-mega { display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
  gap:4px 10px; min-width:560px; padding:4px 0 2px; }
.mcol .mcat { display:block; font-size:11px; font-weight:700; letter-spacing:.1em;
  text-transform:uppercase; color:var(--acc); text-decoration:none;
  padding:8px 12px 3px; }
.mcol .mi.small { font-size:12.5px; padding:5px 12px; white-space:normal; }

/* search: one quiet field under the nav */
.searchbox { position:relative; margin:14px 0 0; }
.searchbox input { width:100%; max-width:480px; padding:9px 12px; font-size:14px;
  font-family:var(--sans); border:1px solid var(--line); border-radius:0;
  background:var(--paper); color:var(--ink); }
.searchbox input::placeholder { color:var(--faint); }
.searchbox input:focus { border-color:var(--ink); outline:none; }
.searchres { position:absolute; top:100%; left:0; width:min(430px,100%);
  background:var(--paper); border:1px solid var(--line);
  z-index:70; margin-top:4px; overflow:hidden; }
.sr-hit { display:block; padding:10px 14px; text-decoration:none;
  color:var(--ink); border-bottom:1px solid var(--line2); }
.sr-hit:last-child { border-bottom:none; }
.sr-hit b { display:block; font-size:14px; font-weight:600; }
.sr-hit span { display:block; font-size:12.5px; color:var(--mut); margin-top:2px; }
.sr-none { padding:12px 14px; font-size:13px; color:var(--mut); }

/* ---- home: the weekly edition leads, the data follows.
   Data-first, never a banner: quiet kicker, one serif line, one whisper row,
   one outlined action. ---- */
.herosub { font-family:var(--serif); font-optical-sizing:auto; font-size:1.22rem;
  line-height:1.5; color:var(--mut); margin:34px 0 0; max-width:56ch; }
.hero { margin:32px 0 0; padding:0 0 34px; border-bottom:1px solid var(--line); }
.herotitle { border:none; padding:0; margin:0 0 12px; font-family:var(--serif);
  font-optical-sizing:auto; font-weight:560; letter-spacing:-0.022em;
  font-size:clamp(2rem, 1.5rem + 2.4vw, 2.9rem); line-height:1.06;
  max-width:22ch; text-wrap:balance; }
.hero .dek { font-size:1.12rem; }
.hero .artmeta { margin-top:14px; }
.hero .btn { margin-top:20px; }
/* the quiet button: an outlined whisper, never a glossy CTA */
.btn { display:inline-block; font-family:var(--sans); font-size:12px; font-weight:700;
  letter-spacing:.12em; text-transform:uppercase; color:var(--ink);
  border:1px solid var(--ink); background:transparent; padding:13px 22px;
  text-decoration:none; cursor:pointer; }
.btn:hover { background:var(--ink); color:var(--paper); }
.btn.primary { background:var(--ink); color:var(--paper); }
.btn.primary:hover { background:var(--acc-deep); border-color:var(--acc-deep); }
/* metadata dot separator */
.dot { display:inline-block; width:3px; height:3px; border-radius:50%;
  background:var(--faint); margin:0 10px; vertical-align:2px; }
.backlink { margin:2.5rem 0 0; }

/* ---- article header: kicker / display headline / dek / whisper meta ---- */
.kicker { font-size:12px; font-weight:700; letter-spacing:.18em;
  text-transform:uppercase; color:var(--acc); margin:0 0 14px; }
.arthead { margin:36px 0 8px; padding-bottom:24px; border-bottom:1px solid var(--line); }
h1.arttitle, h1 { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:clamp(2.4rem, 1.75rem + 3.2vw, 3.5rem);
  line-height:1.03; letter-spacing:-0.022em; margin:0 0 14px; max-width:20ch;
  text-wrap:balance; }
.dek, .sub { font-family:var(--serif); font-optical-sizing:auto; font-size:1.18rem;
  line-height:1.5; color:var(--mut); margin:0; max-width:54ch; }
/* the whisper: date/source/vintage, one quiet line, never competing */
.artmeta { display:flex; flex-wrap:wrap; gap:4px 14px; align-items:baseline;
  margin-top:16px; font-size:12px; color:var(--mut); letter-spacing:.02em; }
.artmeta b { color:var(--ink); font-weight:600; }
.tline { font-size:12px; color:var(--mut); letter-spacing:.02em; margin:30px 0 0; }

/* ---- body rhythm ---- */
.crumb { font-size:12px; color:var(--mut); margin:24px 0 4px; letter-spacing:.02em; }
.crumb a { color:var(--ink); }
.lede { font-size:1.06rem; line-height:1.65; max-width:64ch; color:var(--ink); }
h2 { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:clamp(1.4rem, 1.2rem + 1vw, 1.65rem); letter-spacing:-0.015em;
  line-height:1.2; margin:3rem 0 1rem; padding-top:1.4rem;
  border-top:1px solid var(--line); text-wrap:balance; }
h2:first-of-type { border-top:none; padding-top:0; margin-top:2rem; }
/* a section list already ends on a rule; the next h2 must not double it */
.seclist + h2, .ht-list + h2 { border-top:none; padding-top:0; margin-top:2.2rem; }
h3 { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:1.18rem; margin:1.8rem 0 .55rem; letter-spacing:-0.01em; line-height:1.3; }
p { max-width:68ch; margin:0 0 1.05rem; }
ul.ev, ol.ev { margin:0 0 1.05rem; padding-left:22px; max-width:68ch; }
ul.ev li, ol.ev li { margin:.5rem 0; padding-left:2px; }
ul.ev li::marker { color:var(--acc); }
ul.tight { margin:8px 0 1rem; padding-left:22px; max-width:68ch; }
ul.tight li { margin:.38rem 0; }

/* links: quiet, warm on interaction. Visited links keep the same ink color:
   a data publication never shows browser-default blue/purple. */
main a, .wrap > a, p a, li a, td a, th a, figcaption a, .fcolophon a,
main a:visited, p a:visited, li a:visited, td a:visited, th a:visited,
figcaption a:visited, .fcolophon a:visited {
  color:var(--ink); text-decoration:underline;
  text-decoration-color:#cfc8b8; text-decoration-thickness:1px;
  text-underline-offset:3px; }
main a:hover, p a:hover, li a:hover, td a:hover, th a:hover,
figcaption a:hover, .fcolophon a:hover {
  color:var(--acc-deep); text-decoration-color:var(--acc); }
h1 a, h2 a, h3 a { text-decoration:none; color:var(--ink); }
h1 a:hover, h2 a:hover, h3 a:hover { color:var(--acc-deep); }
.morelink { color:var(--acc); font-weight:700; font-size:14px; text-decoration:none;
  letter-spacing:.01em; }
.morelink:hover { color:var(--acc-deep); }
.morelink::after { content:" \\2192"; }

/* pull quote */
.pullquote { font-family:var(--serif); font-optical-sizing:auto;
  font-size:clamp(1.2rem, 1.05rem + .8vw, 1.45rem); font-weight:500;
  line-height:1.4; letter-spacing:-0.008em; color:#33302a;
  border-left:2px solid var(--acc); padding:2px 0 2px 22px; margin:2.4rem 0;
  max-width:58ch; }
.pullquote cite { display:block; font-family:var(--sans); font-style:normal;
  font-size:12px; color:var(--mut); margin-top:10px; letter-spacing:.04em; }

/* ---- numbers are the product: tabular, quiet units, hairlines ---- */
.statgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:0 28px; margin:22px 0; border-top:1px solid var(--ink); }
.stat { padding:14px 0; border-bottom:1px solid var(--line); }
.stat .v { font-size:29px; font-weight:700; letter-spacing:-0.02em;
  font-variant-numeric:tabular-nums; line-height:1.1; }
.stat .l { font-size:11px; color:var(--mut); margin-top:6px; letter-spacing:.07em;
  text-transform:uppercase; font-weight:600; line-height:1.5; }
.stat .d { font-size:12px; color:var(--mut); margin-top:2px; }

/* tables: small-caps headers, hairline rows, tabular numerals.
   Scroll affordance: soft edge shadows that only appear when there is more
   to scroll toward (local-attachment gradient trick). */
.tblwrap { overflow-x:auto; -webkit-overflow-scrolling:touch; margin:16px -24px;
  padding:0 24px;
  background:
    linear-gradient(to right, var(--paper) 30%, rgba(250,247,240,0)),
    linear-gradient(to right, rgba(250,247,240,0), var(--paper) 70%) 100% 0,
    radial-gradient(farthest-side at 0 50%, rgba(30,27,22,.13), rgba(30,27,22,0)),
    radial-gradient(farthest-side at 100% 50%, rgba(30,27,22,.13), rgba(30,27,22,0)) 100% 0;
  background-repeat:no-repeat;
  background-size:44px 100%, 44px 100%, 16px 100%, 16px 100%;
  background-attachment:local, local, scroll, scroll; }
/* tbox: a tall table in a scrollbox: sticky header row AND sticky first
   column, with the corner cell layered above both. */
.tblwrap.tbox { overflow:auto; max-height:min(76vh, 840px); }
.tblwrap.tbox table.data thead th { position:sticky; top:0; z-index:4;
  background:var(--paper); }
.tblwrap.tbox table.data thead th:first-child { left:0; z-index:6;
  box-shadow:1px 0 0 var(--line); }
.tblwrap.tbox table.data tbody th:first-child,
.tblwrap.tbox table.data tbody td:first-child { position:sticky; left:0;
  background:var(--paper); z-index:3; box-shadow:1px 0 0 var(--line); }
table.data { border-collapse:collapse; width:100%; font-size:13.5px; }
table.data caption { text-align:left; font-family:var(--serif);
  font-optical-sizing:auto; font-weight:560; font-size:1.02rem;
  letter-spacing:-0.008em; padding:0 0 10px; }
table.data th, table.data td { padding:10px 12px; text-align:left; vertical-align:top; }
table.data th { font-size:11px; text-transform:uppercase; letter-spacing:.07em;
  color:var(--mut); font-weight:700; border-bottom:1px solid var(--ink);
  white-space:nowrap; }
table.data td { border-bottom:1px solid var(--line);
  font-variant-numeric:tabular-nums; }
table.data tbody tr:last-child td { border-bottom:none; }
table.data td.num, table.data th.num { text-align:right; font-variant-numeric:tabular-nums; }
table.data tr.tot td { font-weight:700; }
table.data td.n, table.data th.n { text-align:right; font-variant-numeric:tabular-nums; }
table.data td.k { color:var(--faint); font-size:12px; white-space:nowrap; }
table.data td.up { color:var(--acc-deep); font-weight:700; }
table.data td.dn { color:var(--mut); font-weight:700; }
table.movers { display:block; overflow-x:auto; }
table.movers thead th { white-space:nowrap; }
table.movers td.sig { color:var(--acc-deep); font-weight:700; font-size:12px;
  white-space:nowrap; }
/* ---- Trump watch live feed: plain-text posts, Heavy Reading typography ---- */
.wpost { border-top:1px solid var(--line); padding:18px 0 20px; max-width:68ch; }
.wpost:first-of-type { border-top:none; }
.wdate { font-size:12px; color:var(--mut); letter-spacing:.04em; margin:0 0 8px;
  text-transform:uppercase; }
.wtext { font-size:1.02rem; line-height:1.62; margin:0 0 10px; }
.wwhy { font-size:13.5px; color:var(--mut); margin:0 0 6px; max-width:64ch; }
.wwhy b { color:var(--ink); font-weight:600; }
.wflag { font-size:12px; color:var(--acc-deep); margin:0 0 8px; font-weight:600; }
.wtags { margin:8px 0 0; }
.wtag { display:inline-block; font-size:11px; letter-spacing:.06em;
  text-transform:uppercase; color:var(--faint);
  border:1px solid var(--line); border-radius:20px; padding:2px 9px;
  margin:0 6px 6px 0; }
details.verbatim { margin-top:10px; }
details.verbatim > summary { cursor:pointer; font-size:12px; color:var(--mut); }
details.verbatim > summary::-webkit-details-marker { display:none; }
details.verbatim > summary::before { content:"+ "; color:var(--faint); }
details.verbatim[open] > summary::before { content:"\2212  "; }
.wraw { font-size:13px; color:var(--mut); white-space:pre-wrap; max-width:66ch;
  border-left:2px solid var(--line); padding-left:12px; }
table.facts td:first-child { font-weight:600; width:34%; color:#3a352c; }
.tblnote { font-size:12px; color:var(--mut); margin:8px 0 0; max-width:68ch;
  line-height:1.6; }

/* executive call: a red hairline, not a box */
.exec { margin:28px 0; padding:2px 0 2px 20px; border-left:2px solid var(--acc); }
.exec h2 { border:none; margin:0 0 10px; padding:0; font-family:var(--sans);
  font-size:11px; font-weight:700; letter-spacing:.18em; text-transform:uppercase;
  color:var(--acc); }
.exec ul { margin:0; padding-left:20px; max-width:70ch; }
.exec li { margin:7px 0; font-size:15px; line-height:1.6; }
.exec li::marker { color:var(--acc); }
.exec-vint { font-size:12px; color:var(--mut); margin:10px 0 0; }

/* section entrances: hairline rows, not cards.
   Home "Inside" runs as a two-column editorial grid on desktop. */
.seclist { display:grid; grid-template-columns:1fr 1fr; column-gap:36px;
  border-bottom:1px solid var(--line); }
.srow { display:block; padding:18px 2px; border-top:1px solid var(--line);
  text-decoration:none !important; color:var(--ink); }
.srow.last { border-bottom:none; }
.srow .kicker { font-size:11px; margin:0 0 8px; }
.srow h3 { margin:0 0 6px; font-size:1.14rem; }
.srow p { margin:0; font-size:13.5px; color:var(--mut); line-height:1.6; }
.srow .go { display:inline-block; margin-top:8px; font-size:13px; font-weight:700;
  color:var(--acc); letter-spacing:.02em; }
.srow:hover h3 { color:var(--acc-deep); }

/* prev/next week: quiet hairline nav, never a button */
.weeknav { display:flex; justify-content:space-between; gap:16px;
  margin:44px 0 0; padding-top:18px; border-top:1px solid var(--line); }
.weeknav a { font-size:14px; font-weight:600; text-decoration:none; color:var(--ink);
  max-width:44%; line-height:1.5; }
.weeknav a:last-child { text-align:right; }
.weeknav a:hover { color:var(--acc-deep); }

/* desk monitors: hairline-divided entries, status as quiet colored text */
.idea { border-top:1px solid var(--line); padding:18px 2px; margin:0; }
.idea.last { border-bottom:1px solid var(--line); }
.idea h3 { margin:0 0 8px; }
.idea p { margin:7px 0; font-size:15px; }
.flag { font-size:11px; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; margin-left:10px; white-space:nowrap; }
.flag.on { color:#2e7d43; } .flag.off { color:var(--faint); }
.flag.bull { color:#2e7d43; } .flag.bear { color:var(--acc); }
.flag.watch { color:#8a6d1f; } .flag.neu { color:var(--mut); }
.value { font-size:28px; font-weight:700; font-variant-numeric:tabular-nums;
  letter-spacing:-0.02em; }
.chartbox { margin:14px 0; }
.chart-placeholder { border-top:1px solid var(--line); border-bottom:1px solid var(--line);
  padding:20px 2px; color:var(--mut); font-size:13px; }

/* whisper tags */
.chip { display:inline-block; font-size:11px; font-weight:600; letter-spacing:.05em;
  text-transform:uppercase; color:var(--mut); padding:4px 0; margin:2px 14px 2px 0; }
.badge-ok { color:#2e7d43; } .badge-warn { color:var(--acc); } .badge-info { color:#4a6b8a; }
.lic-tag { font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
  color:var(--acc); margin-left:8px; white-space:nowrap; }

/* figures: airy, captions carry vintage + legend in whisper italic */
figure.chart { margin:26px 0; }
figure.chart svg { width:100%; height:auto; display:block; }
figure.chart figcaption { font-size:12.5px; font-style:italic; color:var(--mut);
  margin-top:10px; max-width:68ch; border-left:2px solid var(--line);
  padding-left:12px; line-height:1.55; }
figure.chart figcaption b, figure.chart figcaption strong { color:var(--ink);
  font-weight:600; font-style:normal; }
.lg { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:12px; color:var(--mut);
  margin-top:10px; }
.lg .sw { display:inline-block; width:10px; height:10px; border-radius:2px;
  margin-right:6px; vertical-align:-1px; border:1px solid var(--line); }
/* chart takeaway title + csv download line */
.ctake { font-size:1.04rem; letter-spacing:-.01em; margin:30px 0 4px;
  max-width:62ch; line-height:1.35; }
figure.chart { margin:8px 0 6px; }
.csvdl { font-size:12.5px; margin:4px 0 26px; }
.csvdl .vintageline { color:var(--mut); }

/* footnotes, sources, provenance: the whisper layer. Attribution stays
   complete; it just never shouts. */
sup.fnref { font-size:.68em; line-height:0; }
sup.fnref a { color:var(--acc); text-decoration:none; font-weight:700; padding:0 1px; }
sup.fnref a:hover { color:var(--acc-deep); text-decoration:underline; }
.footnotes { margin:3rem 0 0; padding-top:1.2rem; border-top:1px solid var(--ink);
  max-width:76ch; }
.footnotes h2 { border:none; margin:0 0 .7rem; padding:0; font-family:var(--sans);
  font-size:11px; font-weight:700; letter-spacing:.16em; text-transform:uppercase;
  color:var(--mut); }
.footnotes ol { margin:0; padding-left:20px; font-size:13px; line-height:1.6; color:var(--mut); }
.footnotes li { margin:.4rem 0; padding-left:4px; }
.footnotes li::marker { color:var(--ink); font-weight:600; }
.footnotes a.fnback { color:var(--faint); text-decoration:none; margin-left:6px; }
.footnotes a.fnback:hover { color:var(--acc); }
.src { font-size:12.5px; color:var(--mut); margin:10px 0; max-width:68ch; line-height:1.6; }
.src b, .src strong { color:var(--ink); font-weight:600; }
/* page provenance: full attribution, collapsed to one quiet line at page end */
.prov { margin:44px 0 0; border-top:1px solid var(--line); padding-top:10px; max-width:76ch; }
.prov > summary { cursor:pointer; font-size:12px; color:var(--mut); list-style:none;
  display:inline-block; letter-spacing:.02em; }
.prov > summary::-webkit-details-marker { display:none; }
.prov > summary::before { content:"+ "; font-weight:700; }
.prov[open] > summary::before { content:"\\2014  "; }
.prov .prov-body { font-size:12px; color:var(--mut); line-height:1.65; margin-top:8px; }
.prov .prov-body b { color:var(--ink); font-weight:600; }
.note { font-size:13.5px; color:var(--mut); max-width:68ch; line-height:1.6; }
.vintage { font-size:12px; color:var(--mut); max-width:68ch; line-height:1.6; }
.vintage-inline { font-size:12px; color:var(--mut); }
details.vintage { margin:2px 0 6px; max-width:76ch; }
details.vintage > summary { cursor:pointer; font-size:12px; color:var(--mut);
  list-style:none; display:inline-block; padding:4px 0; }
details.vintage > summary::-webkit-details-marker { display:none; }
details.vintage > summary::before { content:"+ "; font-weight:700; }
details.vintage[open] > summary::before { content:"\\2014  "; }
details.vintage ul { margin:8px 0 4px; padding-left:18px; font-size:12px; color:var(--mut); }
details.vintage li { margin:3px 0; }
.nullnote { color:var(--mut); font-style:italic; }
.panel { margin:26px 0; }
hr { border:none; border-top:1px solid var(--line); margin:2.6rem 0; max-width:76ch; }

/* footer */
.sitefoot { margin-top:64px; padding-top:26px; border-top:1px solid var(--ink); }
.fcols { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:20px; }
.fcol h4 { font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  margin:0 0 8px; color:var(--mut); font-weight:700; }
.fcol a { display:block; font-size:13.5px; color:var(--ink); text-decoration:none;
  padding:4px 0; }
.fcol a:hover { color:var(--acc-deep); text-decoration:underline;
  text-decoration-color:var(--acc); text-underline-offset:3px; }
.fcolophon { font-size:12.5px; color:var(--mut); margin:24px 0 0; max-width:76ch;
  line-height:1.6; }
.fcolophon a { color:var(--ink); }

@media (max-width:640px) {
  body { font-size:16px; }
  .wrap { padding:0 18px 60px; }
  .masthead { padding-top:20px; }
  .wordmark { font-size:26px; }
  .mark { width:34px; height:34px; }
  .wordsub { font-size:9.5px; }
  .arthead { margin-top:28px; padding-bottom:20px; }
  .herosub { font-size:1.1rem; margin-top:26px; }
  .hero { margin-top:24px; padding-bottom:26px; }
  .dek, .sub { font-size:1.08rem; }
  /* mobile menu: labeled button, in-flow stacked groups, hairline dividers */
  .navburger { display:flex; align-items:center; gap:10px; margin:16px 0 0;
    padding:12px 2px; border-top:1px solid var(--ink); border-bottom:1px solid var(--line);
    background:none; cursor:pointer; font-size:12px; font-weight:700;
    letter-spacing:.12em; text-transform:uppercase; color:var(--ink); width:100%;
    -webkit-tap-highlight-color:transparent; font-family:var(--sans); }
  .navburger .nb-ic { display:flex; flex-direction:column; gap:4px; }
  .navburger .nb-ic span { display:block; width:18px; height:2px; background:var(--ink); }
  .mnav .sitenav { display:none; flex-direction:column; border-top:none; border-bottom:none; }
  .mnav[open] .sitenav { display:flex; }
  .mnav[open] .navburger { border-bottom:none; }
  .navdrop { border-bottom:1px solid var(--line); }
  .nd-top { padding:14px 2px; font-size:13px; }
  .nd-caret { margin-left:auto; margin-right:2px; }
  .nd:hover .nd-menu { display:none; }
  .nd[open] .nd-menu { display:block; position:static; border:none; padding:0 0 12px; }
  .nd-menu .mi { padding:9px 2px; font-size:14.5px; white-space:normal; }
  .nd-mega { grid-template-columns:1fr; min-width:0; gap:0; }
  /* tables: horizontal scroll with a sticky first column */
  .tblwrap { margin:14px -18px; padding:0 18px; }
  table.data { font-size:13px; }
  table.data th, table.data td { padding:9px 10px; }
  table.data thead th:first-child, table.data tbody th:first-child,
  table.data tbody td:first-child { position:sticky; left:0; background:var(--paper);
    z-index:1; box-shadow:1px 0 0 var(--line); }
  .stat .v { font-size:25px; }
  figure.chart { overflow-x:auto; -webkit-overflow-scrolling:touch; }
  figure.chart svg { min-width:600px; }
  .fcols { grid-template-columns:repeat(2,1fr); }
  .searchbox input { max-width:none; }
  .seclist { grid-template-columns:1fr; }
  .srow h3 { font-size:1.2rem; }
  .weeknav { flex-direction:column; gap:10px; }
  .weeknav a { max-width:none; }
  .weeknav a:last-child { text-align:left; }
  .ht-item { padding:20px 2px; }
  .ht-item h3 { font-size:1.25rem; }
  .pullquote { padding-left:16px; margin:2rem 0; }
}

@media print {
  body { background:#fff; }
  .mnav, .searchbox, .searchres { display:none; }
  .brandlock { padding:0; }
  .wordmark { font-size:24px; }
  .mark { width:30px; height:30px; }
  .wrap { max-width:none; padding:0 0 24px; }
  table.data, .stat, .idea, figure.chart { break-inside:avoid; }
  h2, h3 { break-after:avoid; }
  a { color:var(--ink); text-decoration:none; }
  .tblwrap { overflow:visible; margin:14px 0; padding:0; background:none; }
  .tblwrap.tbox { max-height:none; overflow:visible; }
  table.data thead th, table.data thead th:first-child,
  table.data tbody th:first-child,
  table.data tbody td:first-child { position:static; box-shadow:none; }
  .prov { break-inside:avoid; }
  p, li { orphans:3; widows:3; }
  /* collapsed metadata is information, not chrome: expand it on paper */
  details:not([open]) > :not(summary) { display:block; }
  .prov > summary::before, details.vintage > summary::before { content:none; }
  .hero { padding-bottom:26px; }
}
"""
