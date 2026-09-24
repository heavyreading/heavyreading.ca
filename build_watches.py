"""Build the world watch pages from datasets/world_watches/*.json.

Framework rendering order per page:
  1. how_to_read   - quiet framework note near the top (rendered only if present)
  2. wcs_stakes    - the 3-sentence lede, right after the dek (only if present)
  3. data-freshness strip (Updated <date> + STALE flag past the refresh interval)
  4. chart         - one inline SVG chart, only when the dataset carries real
                     "chart" data (series with values); skipped silently otherwise
  5. CSV download  - only when the dataset carries real "csv_series"
                     (columns + rows with values); skipped silently otherwise
  6. sections      - the standard h2 + ul.ev rhythm
  7. disagreements - "Where sources disagree" (only if the list is non-empty)
  8. wcs_closer    - closing note before Standing watch (only if present)
  9. Standing watch, Gaps, Sources (unchanged)

Tradable instruments (TMW, ARV) named in wcs_stakes/wcs_closer are linked
only to a page that really exists in the built site and really mentions the
instrument; otherwise the token renders as plain text. No URLs are invented.
"""
import csv
import json
import os
import re
from datetime import date

SITE = "/home/hatch/workspace/wcsb-sd/hidden_files/woodmack_storage/site"
WATCH_DIR = ("/home/hatch/workspace/goals/wcsb-s-d-model/hidden_files/"
             "datasets/world_watches")

# slug, nav key (must match shared.py _TARGETS)
WATCHES = [
    "hormuz",
    "iran",
    "redsea",
    "russia-refining",
    "china-imports",
    "spr-storage",
    "trump",
    "sour",
    "opec-middle-east",
    "condensate-diluent",
    "refinery-margins",
]

# Refresh cadence per watch, in days. The data-freshness strip renders
# "Updated <Mon D, YYYY>" plus a STALE flag once the dataset's "updated"
# date is older than this.
REFRESH_DAYS = {
    "hormuz": 7,
    "iran": 7,
    "redsea": 7,
    "russia-refining": 7,
    "china-imports": 14,
    "spr-storage": 14,
    "trump": 7,
    "sour": 14,
    "opec-middle-east": 14,
    "condensate-diluent": 14,
    "refinery-margins": 14,
}
DEFAULT_REFRESH_DAYS = 7

# Tradable instruments -> candidate target pages (site-root-relative), in
# priority order. A candidate is used only if the file exists in the built
# site AND mentions the instrument.
INSTRUMENT_TARGETS = {
    "TMW": ["venezuela/index.html", "st3-dashboard.html"],
    "ARV": ["venezuela/index.html", "st3-dashboard.html"],
}


def _bullet_html(b):
    from shared import esc
    text = esc(b.get("text", ""))
    vintage = esc(b.get("vintage", ""))
    src = esc(b.get("source", ""))
    url = b.get("source_url", "")
    link = f' <a href="{esc(url)}">{src}</a>' if url and src else (f" {src}" if src else "")
    meta = f'<span class="vintage-inline">{vintage}{link}</span>' if (vintage or link) else ""
    return f"<li>{text}<br>{meta}</li>" if meta else f"<li>{text}</li>"


def _stub_page(slug):
    import sys
    sys.path.insert(0, SITE)
    import shared as S
    titles = {
        "hormuz": ("Hormuz watch", "Tanker movement through the world's most important oil chokepoint."),
        "iran": ("Iran watch", "Iranian oil exports under sanctions and blockade: tracked exports, floating storage, and the shadow fleet."),
        "redsea": ("Red Sea", "Shipping disruptions and rerouting around the Red Sea."),
        "russia-refining": ("Russian refineries", "Refinery capacity offline in the Russia-Ukraine war."),
        "china-imports": ("China imports", "China's crude-import appetite."),
        "spr-storage": ("SPR & storage", "US SPR and commercial storage: refills, capacity, policy."),
        "trump": ("Trump watch", "Trump as a first-order driver of Canadian differentials."),
        "sour": ("The global sour barrel", "Dubai, Mars, Merey: the sour comparables that price WCS."),
        "opec-middle-east": ("OPEC & Middle East", "Organization of the Petroleum Exporting Countries (OPEC+) supply decisions and Middle East crude flows: quotas, compliance, and spare capacity."),
        "condensate-diluent": ("Condensate & diluent", "Condensate supply and diluent demand for oil-sands blending: the other half of the Western Canadian Select (WCS) barrel."),
        "refinery-margins": ("Refinery margins", "Refining margins and runs: what refineries earn cracking the barrel, and what that means for crude demand."),
    }
    title, dek = titles.get(slug, (slug, ""))
    body = ('<p class="sub">First edition in preparation. No sourced material '
            'has been published yet; this page will carry dated, cited '
            'entries once the first edition lands.</p>')
    return S.page_shell(
        title, title, dek,
        f'<a href="../../index.html">Home</a> / <a href="../index.html">World</a> / {title}',
        body, slug, 2, S.edition_date("2026-09-23"),
        "Heavy Reading",
        description=dek, url_path=f"world/{slug}/index.html")


def _freshness_strip(slug, d, S):
    """Data-freshness strip: Updated <Mon D, YYYY> + STALE past the interval."""
    raw = (d.get("updated") or "").strip()
    try:
        upd = date.fromisoformat(raw)
    except ValueError:
        return ""
    interval = REFRESH_DAYS.get(slug, DEFAULT_REFRESH_DAYS)
    age = (date.today() - upd).days
    stale = age > interval
    flag = (' <span class="stale" style="color:#a33;font-weight:600">'
            "STALE</span>" if stale else "")
    cadence = "weekly" if interval == 7 else f"every {interval} days"
    return (f'  <p class="note freshness">Updated {S.edition_date(raw)}'
            f" &middot; refreshes {cadence}{flag}</p>")


def _instrument_targets():
    """token -> site-root-relative page path, verified against the built site.

    Only a page that exists on disk and actually mentions the instrument is
    returned; anything else renders as plain text (no invented URLs).
    """
    targets = {}
    for tok, cands in INSTRUMENT_TARGETS.items():
        for rel in cands:
            if rel.startswith("public/"):
                continue
            p = os.path.join(SITE, rel)
            if not os.path.isfile(p):
                continue
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    if tok in f.read():
                        targets[tok] = rel
                        break
            except OSError:
                continue
    return targets


def _link_instruments(text, targets, S):
    """Wrap TMW/ARV whole-word mentions in links to verified target pages."""
    t = S.esc(text)
    for tok, rel in targets.items():
        href = "../../" + rel
        t = re.sub(r"\b" + re.escape(tok) + r"\b",
                   lambda m: f'<a href="{href}">{m.group(0)}</a>', t)
    return t


def _disagreements_html(dis, S):
    """'Where sources disagree': topic + the two sources + note."""
    items = []
    for x in dis or []:
        if not isinstance(x, dict):
            continue
        topic = S.esc(x.get("topic", ""))
        srcs = (x.get("sources")
                or [x.get("source_a"), x.get("source_b"),
                    x.get("a_source"), x.get("b_source")])
        srcs = [S.esc(s) for s in srcs if s]
        note = S.esc(x.get("note", ""))
        head = f"<b>{topic}</b>" if topic else ""
        vs = " vs ".join(srcs)
        if head and vs:
            line = f"{head}: {vs}"
        else:
            line = head or vs
        if note:
            line = f"{line}. {note}" if line else note
        if line:
            items.append(f"  <li>{line}</li>")
    if not items:
        return ""
    return ("  <h2>Where sources disagree</h2>\n"
            '  <ul class="ev">\n' + "\n".join(items) + "\n  </ul>")


def _chart_svg(chart, S):
    """One inline SVG line chart, only for real chart data (series w/ values)."""
    series = []
    for s in chart.get("series", []) or []:
        if not isinstance(s, dict):
            continue
        vals = s.get("values", s.get("data", [])) or []
        vals = [v if isinstance(v, (int, float)) else None for v in vals]
        if not any(v is not None for v in vals):
            continue
        series.append({"label": str(s.get("label", s.get("name", ""))),
                       "values": vals, "dash": bool(s.get("dash"))})
    if not series:
        return ""
    labels = [str(x) for x in (chart.get("labels", []) or [])]
    W, H = 680, 300
    allv = [v for s in series for v in s["values"] if v is not None]
    # optional 5-year-range band: {"label": str, "min": [...], "max": [...]}
    band = chart.get("band") or {}
    _bmin = [v if isinstance(v, (int, float)) and not isinstance(v, bool)
             else None for v in (band.get("min") or [])]
    _bmax = [v if isinstance(v, (int, float)) and not isinstance(v, bool)
             else None for v in (band.get("max") or [])]
    _has_band = (isinstance(band, dict) and len(_bmin) == len(_bmax)
                 and len(_bmin) > 1
                 and any(v is not None for v in _bmin)
                 and any(v is not None for v in _bmax))
    if _has_band:
        allv += [v for v in _bmin + _bmax if v is not None]
    _lo0, _hi0 = min(allv), max(allv)
    if _lo0 == _hi0:
        _lo0, _hi0 = _lo0 - 1, _hi0 + 1
    _pad = (_hi0 - _lo0) * 0.06
    # dynamic left margin so y-tick labels never spill past x=0
    _tick_w = max(len(f"{_lo0 - _pad + (_hi0 - _lo0 + 2 * _pad) * g / 4:,.1f}")
                  for g in range(5)) * 6.2
    ml, mr, mt, mb = max(60, int(8 + _tick_w + 8)), 14, 36, 46
    iw, ih = W - ml - mr, H - mt - mb
    lo, hi = _lo0 - _pad, _hi0 + _pad
    n = max(len(s["values"]) for s in series)

    def x(i):
        return ml + (iw * i / (n - 1) if n > 1 else iw / 2)

    def y(v):
        return mt + ih * (1 - (v - lo) / (hi - lo))

    colors = ["#1f6feb", "#b45309", "#0e7c3e", "#a21caf", "#475569", "#b91c1c"]
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="{S.esc(chart.get("title", "watch chart"))}" '
             'style="width:100%;height:auto;display:block">',
             S._bg(W, H)]
    if _has_band:
        _fwd = " ".join(f"{x(i):.1f},{y(v):.1f}"
                        for i, v in enumerate(_bmax) if v is not None)
        _bwd = " ".join(f"{x(i):.1f},{y(v):.1f}"
                        for i, v in reversed(list(enumerate(_bmin)))
                        if v is not None)
        parts.append(
            f'<polygon points="{_fwd} {_bwd}" '
            'style="fill:var(--ch-band-nc);opacity:0.55"/>')
    for g in range(5):
        gv = lo + (hi - lo) * g / 4
        gy = y(gv)
        parts.append(
            f'<line x1="{ml}" y1="{gy:.1f}" x2="{W - mr}" y2="{gy:.1f}" '
            'style="stroke:var(--ch-grid)" stroke-width="1"/>')
        parts.append(
            f'<text x="{ml - 8}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" style="fill:var(--mut)">{gv:,.1f}</text>')
    step = max(1, n // 6)
    for i in range(n):
        if i < len(labels) and (n <= 12 or i % step == 0 or i == n - 1):
            # edge labels anchor inward so long labels never spill past x=0/W
            _anc = "middle"
            _xx = x(i)
            if i == 0:
                _anc, _xx = "start", ml
            elif i == n - 1:
                _anc, _xx = "end", W - mr
            parts.append(
                f'<text x="{_xx:.1f}" y="{H - 16}" text-anchor="{_anc}" '
                f'font-size="11" style="fill:var(--faint)">'
                f'{S.esc(labels[i])}</text>')
    for si, s in enumerate(series):
        _dash = ' stroke-dasharray="6,4"' if s.get("dash") else ""
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}"
                       for i, v in enumerate(s["values"]) if v is not None)
        parts.append(
            f'<polyline points="{pts}" fill="none" '
            f'stroke="{colors[si % len(colors)]}" stroke-width="2"{_dash}/>')
    lx, ly = ml, 10
    if _has_band:
        _blab = str(band.get("label", "range"))
        _blw = 20 + len(_blab) * 6.8 + 18
        if lx + _blw > W - mr and lx > ml:
            lx, ly = ml, ly + 18
        parts.append(
            f'<rect x="{lx:.0f}" y="{ly}" width="16" height="10" '
            'style="fill:var(--ch-band-nc);opacity:0.75"/>'
            f'<text x="{lx + 20:.0f}" y="{ly + 9}" font-size="12" '
            f'style="fill:var(--ch-ink)">{S.esc(_blab)}</text>')
        lx += _blw
    for si, s in enumerate(series):
        c = colors[si % len(colors)]
        _lab = s["label"]
        _lw = 20 + len(_lab) * 6.8 + 18
        if lx + _lw > W - mr and lx > ml:
            lx, ly = ml, ly + 18
        if s.get("dash"):
            parts.append(
                f'<line x1="{lx:.0f}" y1="{ly + 2}" x2="{lx + 16:.0f}" '
                f'y2="{ly + 2}" stroke="{c}" stroke-width="2" '
                'stroke-dasharray="6,4"/>')
        else:
            parts.append(
                f'<rect x="{lx:.0f}" y="{ly}" width="16" height="5" '
                f'fill="{c}"/>')
        parts.append(
            f'<text x="{lx + 20:.0f}" y="{ly + 6}" font-size="12" '
            f'style="fill:var(--ch-ink)">{S.esc(_lab)}</text>')
        lx += _lw
    parts.append("</svg>")

    cap_bits = []
    title = chart.get("title", "")
    if title:
        cap_bits.append(f"<b>{S.esc(title)}</b>")
    src = chart.get("source", "")
    vintage = chart.get("vintage", "")
    if src or vintage:
        cap_bits.append(
            f'<span class="vintage-inline">{S.esc(vintage)}'
            f'{" " if vintage and src else ""}{S.esc(src)}</span>')
    cap = ("<figcaption>" + "<br>".join(cap_bits) + "</figcaption>"
           if cap_bits else "")

    # data table for screen readers / exact values
    rows = []
    for i in range(n):
        lab = S.esc(labels[i]) if i < len(labels) else str(i)
        cells = "".join(
            f"<td>{v:,.1f}</td>" if v is not None else "<td>n/a</td>"
            for v in (s["values"][i] if i < len(s["values"]) else None
                      for s in series))
        rows.append(f"<tr><th>{lab}</th>{cells}</tr>")
    head = "".join(f"<th>{S.esc(s['label'])}</th>" for s in series)
    tbl = ('<details class="note"><summary>Chart data</summary>'
           '<div class="tblwrap"><table class="data">'
           f"<tr><th></th>{head}</tr>{''.join(rows)}</table></div></details>")
    return ('  <figure class="chart">\n    ' + "\n    ".join(parts) +
            ("\n    " + cap if cap else "") + "\n  </figure>\n  " + tbl)


def _csv_download(slug, csv_series, S):
    """Write the CSV next to the page and link it; skip silently if no data."""
    if not isinstance(csv_series, dict):
        return ""
    cols = csv_series.get("columns", csv_series.get("header", [])) or []
    rows = csv_series.get("rows", []) or []
    if not cols or not rows:
        return ""
    if not any(any(v is not None and v != "" for v in r) for r in rows):
        return ""
    fname = str(csv_series.get("filename") or f"{slug}.csv")
    fname = re.sub(r"[^a-zA-Z0-9_.\-]", "_", fname)
    d = os.path.join(SITE, "world", slug)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, fname), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([("" if v is None else v) for v in r] for r in rows)
    return (f'  <p class="note"><a href="{S.esc(fname)}">'
            "Download the data (CSV)</a></p>")


def build_watch(slug):
    import sys
    sys.path.insert(0, SITE)
    import shared as S
    path = f"{WATCH_DIR}/{slug}.json"
    try:
        with open(path) as f:
            d = json.load(f)
    except FileNotFoundError:
        return _stub_page(slug), False
    out = []

    # (a) framework note: quiet, near the top
    how = (d.get("how_to_read") or "").strip()
    if how:
        out.append(f'  <p class="note">{S.esc(how)}</p>')

    # (b) WCS stakes lede, right after the dek
    stakes = (d.get("wcs_stakes") or "").strip()
    if stakes:
        targets = _instrument_targets()
        out.append(f'  <p class="lede">{_link_instruments(stakes, targets, S)}</p>')

    # data-freshness strip
    fresh = _freshness_strip(slug, d, S)
    if fresh:
        out.append(fresh)

    # charts for real chart data; one CSV only for real csv_series
    _charts = d.get("charts") or []
    if isinstance(_charts, list):
        for _ch in _charts:
            _svg = _chart_svg(_ch or {}, S)
            if _svg:
                out.append(_svg)
    chart = _chart_svg(d.get("chart") or {}, S)
    if chart:
        out.append(chart)
    dl = _csv_download(slug, d.get("csv_series"), S)
    if dl:
        out.append(dl)

    # (c) existing sections: h2 + ul.ev
    for sec in d.get("sections", []):
        out.append(f"  <h2>{S.esc(sec.get('heading', ''))}</h2>")
        out.append('  <ul class="ev">')
        out.extend("  " + _bullet_html(b) for b in sec.get("bullets", []))
        out.append("  </ul>")

    # (d) where sources disagree
    dis = _disagreements_html(d.get("disagreements"), S)
    if dis:
        out.append(dis)

    # (e) closer, before Standing watch
    closer = (d.get("wcs_closer") or "").strip()
    if closer:
        targets = _instrument_targets()
        out.append(f'  <p class="lede">{_link_instruments(closer, targets, S)}</p>')

    # (f) standing watch, gaps, sources (unchanged)
    track = d.get("track") or []
    if track:
        out.append("  <h2>Standing watch</h2>")
        out.append('  <p class="sub">What the daily feed updates on this page.</p>')
        out.append('  <ul class="ev">')
        out.extend(f"  <li>{S.esc(t)}</li>" for t in track)
        out.append("  </ul>")
    gaps = d.get("gaps") or []
    if gaps:
        out.append("  <h2>Gaps</h2>")
        out.append('  <ul class="ev">')
        out.extend(f"  <li>{S.esc(g)}</li>" for g in gaps)
        out.append("  </ul>")
    # sources appendix from the bullets
    seen = []
    for sec in d.get("sections", []):
        for b in sec.get("bullets", []):
            key = (b.get("source", ""), b.get("source_url", ""))
            if key not in seen:
                seen.append(key)
    if seen:
        out.append("  <h2>Sources</h2>")
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>Publisher</th><th>Link</th></tr>")
        for src, url in seen:
            link = f'<a href="{S.esc(url)}">link</a>' if url else ""
            out.append(f"    <tr><td>{S.esc(src)}</td><td>{link}</td></tr>")
        out.append("  </table></div>")
    title = d.get("title", slug)
    dek = d.get("dek", "")
    updated = S.edition_date(d.get("updated", "2026-09-23"))
    page = S.page_shell(
        title, title, dek,
        f'<a href="../../index.html">Home</a> / <a href="../index.html">World</a> / {S.esc(title)}',
        "\n".join(out), slug, 2, updated,
        "Public sources; every entry carries its publisher and vintage",
        description=dek, url_path=f"world/{slug}/index.html")
    return page, True


def main():
    import os
    built = []
    for slug in WATCHES:
        if slug == "trump":
            import build_trump
            build_trump.main()
            built.append((slug, True))
            continue
        page, ok = build_watch(slug)
        d = os.path.join(SITE, "world", slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(page)
        built.append((slug, ok))
        print(("wrote " if ok else "stub ") + f"world/{slug}/index.html")
    return built


if __name__ == "__main__":
    main()
