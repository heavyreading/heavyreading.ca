#!/usr/bin/env python3
"""Build the Phase 1 trading-layer sections and the tradable-call-led home.

Pages (all public-info only, same ?public=1 rule as the rest of the site):
  site/balance/index.html       S&D balance, storage, removals (the page they lack)
  site/maintenance/index.html   forward 12-month maintenance calendar
  site/weekly/index.html        Heavy Reading weekly archive
  site/methodology/index.html   standing methodology
  site/sources/index.html       full citation block, every publisher/URL on record
  site/data/index.html          free CSV downloads of every public series used
  site/index.html               home, rebuilt: executive call first

Data comes only from the dashboard DATA (rebuilt first via build_projects,
which runs build_st3_dashboard.main()), cycle.json, the weekly editions, and
repo annotations. No licensed series are written to these pages; the home
keeps the desk monitors (ideas/momentum/flags) with their data-licensed
attributes and the ?public=1 gate.

Run with the repo venv python:
    python site/build_sections.py
Idempotent: reruns produce byte-identical output when inputs are unchanged.
"""
import csv
import json
import re
import sys
import calendar
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent

sys.path.insert(0, str(SITE))
import build_st3_dashboard as B  # noqa: E402
import build_projects as P  # noqa: E402  (runs B.main() via load_inputs)
import build_site as BS  # noqa: E402  (licensed panel generators)
import shared as S  # noqa: E402

VINTAGE = ("AER ST3/ST53 actuals through 2026-07 (ST39 through 2026-05), "
           "pulled 2026-09-22; Aug-Sep 2026 nowcast estimated, built "
           "2026-09-23; forecast built 2026-09-22.")

SOURCE_LINE = ("AER ST3/ST39/ST53 via the WCSB S&amp;D model; company guidance "
               "via the forward maintenance calendar (revised 2026-09-23)")


def load_inputs():
    data, roster, fwd, overlap, weekly = P.load_inputs()
    return data, roster, fwd, overlap, weekly


def R_(data):
    return {r["id"]: r for r in data["rows"]}


def bands(data):
    b = {}
    for m in data["act_months"]:
        b[m] = "act"
    for m in data["gap_months"]:
        b[m] = "nc"
    for m in data["fc_months"]:
        b[m] = "fc"
    return b


def maint_months(data, R):
    mv = R["maint"]["values"]
    return {m for m in data["act_months"] + data["gap_months"] + data["fc_months"]
            if mv.get(m) not in (None, 0)}


# ----------------------------------------------------------------------------
# Shared charts
# ----------------------------------------------------------------------------

def supply_stack_chart(data, R, months):
    parts = [("In-situ bitumen", R["in_situ"]["values"], "blue"),
             ("Mined bitumen + SCO", R["mined_grp"]["values"], "red"),
             ("Conventional crude", R["conv"]["values"], "gray")]
    svg = S.svg_stack(months, parts, bands(data), maint_months(data, R),
                      title="WCSB supply stack")
    cap = (S.vintage_caption(VINTAGE) + " Stack: in-situ bitumen, mined "
           "bitumen + SCO, conventional crude; ties exactly to Total WCSB "
           "crude supply every month. Orange shading marks months with "
           "modeled maintenance offline.")
    return S.chart_figure(svg, cap,
                          [("In-situ", "var(--ch-blue)"), ("Mined + SCO", "var(--ch-red)"),
                           ("Conventional", "var(--ch-gray)")] + S.band_legend())


def svg_storage_level(inv, band_min, band_max, cur_vals, fc26, fc27,
                      max_lvl, max_ym):
    """Implied-storage level chart (EIA five-year-channel presentation).

    x = Jan..Dec. Band = seasonal min/max of closing inventory over the
    last five complete years. cur_vals = current-year actuals (Jan..last
    actual). fc26/fc27 = forecast level segments (Aug-Dec of the current
    year, then the full next year, dashed). max_lvl = full-history maximum
    horizontal line. All values in million barrels.
    """
    W, H = 680, 330
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    allv = ([v for v in band_min + band_max if v is not None]
            + [v for _, v in cur_vals] + [v for _, v in fc26]
            + [v for _, v in fc27] + [max_lvl])
    lo0, hi0 = min(allv), max(allv)
    pad = (hi0 - lo0) * 0.07 or 1.0
    lo, hi = lo0 - pad, hi0 + pad
    ml, mr, mt, mb = 56, 14, 30, 44
    iw, ih = W - ml - mr, H - mt - mb

    def x(i):
        return ml + iw * i / 11.0

    def y(v):
        return mt + ih * (1 - (v - lo) / (hi - lo))

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="Implied Alberta storage level, million barrels" '
             'style="width:100%;height:auto;display:block">',
             S._bg(W, H)]
    # five-year band
    fwd = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(band_max))
    bwd = " ".join(f"{x(i):.1f},{y(v):.1f}"
                   for i, v in reversed(list(enumerate(band_min))))
    parts.append(f'<polygon points="{fwd} {bwd}" '
                 'style="fill:var(--ch-band-nc);opacity:0.55"/>')
    # gridlines + y labels
    for g in range(5):
        gv = lo + (hi - lo) * g / 4
        gy = y(gv)
        parts.append(
            f'<line x1="{ml}" y1="{gy:.1f}" x2="{W - mr}" y2="{gy:.1f}" '
            'style="stroke:var(--ch-grid)" stroke-width="1"/>')
        parts.append(
            f'<text x="{ml - 8}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" style="fill:var(--mut)">{gv:,.1f}</text>')
    for i, lab in enumerate(labels):
        parts.append(
            f'<text x="{x(i):.1f}" y="{H - 22}" text-anchor="middle" '
            f'font-size="11" style="fill:var(--faint)">{lab}</text>')
    parts.append(
        f'<text x="{ml}" y="{H - 6}" font-size="11" '
        f'style="fill:var(--faint)">Million barrels</text>')

    def polyline(pts, color, dash="", width=2):
        s = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<polyline points="{s}" fill="none" stroke="{color}" '
                     f'stroke-width="{width}"{d}/>')

    polyline(cur_vals, "var(--ch-blue)", width=2.5)
    polyline(fc26, "#b45309", width=2.5)
    if fc27:
        polyline(fc27, "#b45309", dash="6,4", width=2.5)
    # full-history maximum
    my = y(max_lvl)
    parts.append(
        f'<line x1="{ml}" y1="{my:.1f}" x2="{W - mr}" y2="{my:.1f}" '
        'stroke="#6b7280" stroke-width="1.5" stroke-dasharray="4,3"/>')
    parts.append(
        f'<text x="{W - mr}" y="{my - 6:.1f}" text-anchor="end" '
        f'font-size="11" style="fill:#6b7280">Full-history max '
        f'{max_lvl:,.1f} ({S.esc(max_ym)})</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def storage_level_chart(data, R):
    """Implied-storage LEVEL chart (million barrels), replacing the old
    monthly-change bars. History = AER ST3 closing inventory; forecast =
    last actual plus cumulative monthly implied storage changes from the
    exact ST3 identity."""
    inv = data.get("inventory_mm_bbl", {})
    if not inv:
        raise SystemExit("FAIL: inventory_mm_bbl missing from dashboard DATA; "
                         "cannot build the storage level chart")
    last_act = data["act_months"][-1]
    cur_year = int(last_act[:4])
    chan_years = list(range(cur_year - 5, cur_year))
    band_min, band_max = [], []
    for m in range(1, 13):
        vals = [inv[f"{y}-{m:02d}"] for y in chan_years
                if f"{y}-{m:02d}" in inv]
        if not vals:
            raise SystemExit(
                f"FAIL: no channel history for month {m:02d}")
        band_min.append(min(vals))
        band_max.append(max(vals))
    last_m = int(last_act[5:7])
    cur_vals = [(m - 1, inv[f"{cur_year}-{m:02d}"])
                for m in range(1, last_m + 1)
                if f"{cur_year}-{m:02d}" in inv]
    stor = R["stor_chg"]["values"]
    lvl = inv[last_act]
    fc26, fc27 = [], []
    for m in data["gap_months"] + data["fc_months"]:
        v = stor.get(m)
        if v is None:
            raise SystemExit(
                f"FAIL: stor_chg missing for {m}; cannot extend the "
                f"storage level forecast")
        d = calendar.monthrange(int(m[:4]), int(m[5:7]))[1]
        lvl = round(lvl + v * d / 1000.0, 2)
        (fc26 if int(m[:4]) == cur_year else fc27).append(
            (int(m[5:7]) - 1, lvl))
    max_ym = max(inv, key=lambda k: inv[k])
    max_lvl = inv[max_ym]
    svg = svg_storage_level(inv, band_min, band_max, cur_vals, fc26, fc27,
                            max_lvl, max_ym)
    cap = (S.vintage_caption(
        "AER ST3 closing inventory actuals through 2026-07 (pulled "
        "2026-09-22); Aug-Sep 2026 nowcast estimated; forecast built "
        "2026-09-24.") +
        " Implied Alberta commercial storage level, million barrels. "
        "History = reported ST3 closing inventory. Shaded band = seasonal "
        f"five-year min/max of closing inventory ({chan_years[0]}-"
        f"{chan_years[-1]}). Blue = 2026 actuals. Amber = forecast from the "
        "Jul 2026 closing inventory plus cumulative monthly implied storage "
        "changes from the exact ST3 identity (AER reporting-adjustment plug "
        "carried at its trailing-12-month mean, disclosed on its own row). "
        f"Dashed gray = full-history maximum ({max_lvl:,.1f} MMbbl, "
        f"{S.esc(max_ym)}).")
    return S.chart_figure(
        svg, cap,
        [("5-year range", "var(--ch-band-nc)"),
         ("2026 actual", "var(--ch-blue)"),
         ("Forecast", "#b45309"),
         ("Full-history max", "#6b7280")] + S.band_legend())


def maintenance_chart(data, R, months):
    svg = S.svg_bars(months, R["maint"]["values"], bands(data), (),
                     title="Modeled maintenance offline")
    cap = (S.vintage_caption(VINTAGE + " Maintenance calendar compiled "
                                      "2026-09-22; modeled at the leaves "
                                      "2026-09-23.") +
           " Maintenance offline memo: modeled kb/d offline by month, major "
           "turnarounds only, incremental to the baseline forecast. Routine "
           "annual maintenance is embedded in the baseline, not double-counted.")
    return S.chart_figure(svg, cap, S.band_legend())


# Maintenance children in table order: (row id, event label, validation tag).
MAINT_EVENT_META = [
    ("maint_horizon", "Horizon 35-day turnaround", "CONFIRMED"),
    ("maint_coker82", "Syncrude Coker 8-2 turnaround", "CONFIRMED"),
    ("maint_suncor_bp", "Suncor Base Plant Q4 maintenance "
     "(15 bitumen, 5 SCO/diesel)", "CONFIRMED"),
    ("maint_cold_lake", "Imperial Cold Lake 3Q/4Q turnaround",
     "GUIDANCE-SOURCED"),
    ("maint_cve_cl", "Christina Lake F/G turnaround tail",
     "ASSUMED (model carry, not company-stated)"),
    ("maint_mackay", "MacKay River Sep 2027 turnaround", "CADENCE-MODELED"),
    ("maint_primrose", "Primrose/Wolf Lake Apr 2027 turnaround",
     "CADENCE-MODELED, WEAK-SIGNAL"),
]


def modeled_offline_table(data, R, months):
    """Monthly modeled-offline totals with contributing events, Oct 2026-Dec 2027.

    Totals are the model's maint parent row; the per-event decomposition comes
    from B.MAINT_CHILDREN (the dashboard tree no longer carries event rows).
    Children must sum to the parent exactly or the build fails loudly.
    """
    out = ["  <h2>Modeled offline</h2>",
           '  <p class="note">Major-turnaround offline, incremental to '
           "baseline. Routine annual maintenance is embedded in the baseline "
           "forecast (project leaves are forecast from trailing-12-month "
           "actuals times a seasonal factor, which already include past "
           "routine shutdowns); it is not double-counted here.</p>",
           '  <div class="tblwrap"><table class="data">',
           '    <tr><th>Month</th><th class="num">Modeled offline kb/d</th>'
           "<th>Contributing events</th></tr>"]
    children = B.MAINT_CHILDREN
    for m in months:
        total = R["maint"]["values"].get(m) or 0.0
        evs = []
        for rid, label, tag in MAINT_EVENT_META:
            v = children.get(rid, {}).get(m)
            if v:
                evs.append(f"{S.esc(label)} [{S.esc(tag)}], {v:+.1f} kb/d")
        check = sum(children.get(rid, {}).get(m) or 0.0
                    for rid, _, _ in MAINT_EVENT_META)
        if abs(total - check) > 0.051:
            raise SystemExit(
                f"maintenance child sum mismatch in {m}: parent {total}, "
                f"children {check}")
        ev_cell = "<br>".join(evs) if evs else "No major turnaround modeled"
        out.append(f'    <tr><td>{S.mname(m)}</td><td class="num">'
                   f"{total:,.1f}</td><td>{ev_cell}</td></tr>")
    out.append("  </table></div>")
    return "\n".join(out)


# ----------------------------------------------------------------------------
# /balance/
# ----------------------------------------------------------------------------

BAL_ROWS = ["supply_total", "in_situ", "mined_grp", "conv",
            "grade_conv_light", "grade_conv_sour", "grade_conv_heavy",
            "grade_sco", "grade_dilbit", "grade_total",
            "diluent", "ab_use", "removals_from_alberta",
            "maint", "total_receipts", "losses_ffl", "adjustments",
            "aer_plug", "stor_chg"]


def build_balance(data):
    R = R_(data)
    fc = data["fc_months"]
    out = [B.exec_panel_html(data)]
    out.append("  <h2>Forward balance (kb/d)</h2>")
    out.append('  <p class="note">Oct 2026 is the context month '
               "(post-nominations); the tradable window runs Nov 2026 "
               "onward.</p>")
    out.append('  <div class="tblwrap"><table class="data">')
    head = ["<tr><th>Line</th>"] + [
        f'<th class="num" style="background:{"#e7ebee" if m == fc[0] else "#e9ede9"}">'
        f"{S.mname(m)}</th>" for m in fc] + ['<th class="num">12-mo avg</th></tr>']
    out.append("    " + "".join(head))
    for rid in BAL_ROWS:
        r = R[rid]
        tds = []
        vals = [r["values"].get(m) for m in fc]
        have = [v for v in vals if v is not None]
        avg = sum(have) / len(have) if have else None
        for m in fc:
            v = r["values"].get(m)
            bg = "#e7ebee" if m == fc[0] else "#e9ede9"
            tds.append(f'<td class="num" style="background:{bg}">'
                       f"{S.f1(v)}</td>")
        tds.append(f'<td class="num"><b>{S.f1(avg)}</b></td>')
        out.append(f'    <tr><td>{S.esc(r["label"])}</td>{"".join(tds)}</tr>')
    out.append("  </table></div>")
    out.append('  <p class="tblnote">All flows in kb/d. Blank cells are months '
               "AER has not published yet, not zeros.</p>")

    months = data["act_months"] + data["gap_months"] + fc
    out.append("  <h2>Supply stack</h2>")
    out.append(supply_stack_chart(data, R, months))
    out.append("  <h2>Implied storage level</h2>")
    out.append(storage_level_chart(data, R))
    out.append('  <p class="tblnote">The forward maintenance calendar lives '
               'on the <a href="../maintenance/index.html">Maintenance '
               "tab</a>.</p>")
    out.append("  <h2>Sources</h2>")
    out.append(S.sources_table())

    d = SITE / "balance"
    d.mkdir(parents=True, exist_ok=True)
    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "Balance", "Balance",
        "The WCSB supply/demand balance, storage, and removals. The page "
        "Oilsands Magazine does not have.",
        '<a href="../index.html">Home</a> / <a href="../supply/index.html">Supply</a> / Balance', "\n".join(out),
        "balance", 1, updated, SOURCE_LINE,
        description="The WCSB supply/demand balance: storage, removals, and the "
                    "forward balance behind the weekly letter.",
        url_path="balance/index.html"))
    print(f"wrote {d / 'index.html'}")


# ----------------------------------------------------------------------------
# /maintenance/
# ----------------------------------------------------------------------------

def build_maintenance(data, fwd, overlap):
    R = R_(data)
    fc = data["fc_months"]
    out = ['  <p class="sub">Forward maintenance calendar: '
           "2026-10-01 through 2027-12-31, revised 2026-09-23 under the "
           'editorial fused-maintenance rulings, from company guidance, '
           "transcripts, and cadence analysis.</p>"]
    out.append("  <h2>Reading the calendar</h2>")
    out.append('  <ul class="ev">'
               "<li><b>Public confirmed:</b> the company stated the number "
               "and the timing. Only these enter model math, and only after "
               "approval.</li>"
               "<li><b>Cadence-modeled:</b> an editorially approved turnaround "
               "volume estimated from observed project history (MacKay River "
               "Sep 2027, -12 kb/d; Primrose/Wolf Lake Apr 2027, -26 kb/d, "
               "weak-signal flag). In the model math, labeled "
               "CADENCE-MODELED everywhere, never presented as "
               "company-confirmed.</li>"
               "<li><b>Guidance sourced:</b> verified from company guidance or "
               "transcripts (e.g. positive statements of no turnaround).</li>"
               "<li>Unknown volumes and dates stay null, never guessed.</li>"
               "</ul>")

    if overlap:
        out.append("  <h2>Window-boundary events (in the model math)</h2>")
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>Event</th><th>Project</th><th>Note</th></tr>")
        for pid in sorted(overlap):
            for o in overlap[pid]:
                out.append(f"    <tr><td>{S.esc(o['event_id'])}</td>"
                           f"<td>{S.esc(pid)}</td><td>{S.esc(o['note'])}</td></tr>")
        out.append("  </table></div>")

    recs = []
    for pid, rs in fwd.items():
        recs.extend(rs)
    recs.sort(key=lambda r: (r.get("validation", ""), r.get("window_start", "")))
    groups = [("public-confirmed", "Public confirmed"),
              ("cadence-modeled", "Cadence-modeled (editorially approved)"),
              ("guidance-sourced", "Guidance sourced")]
    for val, label in groups:
        grp = [r for r in recs if r.get("validation") == val]
        if not grp:
            continue
        out.append(f"  <h2>{label} ({len(grp)})</h2>")
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>Project</th><th>Timing</th><th>Event</th>"
                   '<th class="num">Impact kb/d</th><th>Source</th></tr>')
        for r in grp:
            imp = r.get("impact_kbd")
            imp_s = (f"{imp:+.1f}" if imp is not None
                     else '<span class="nullnote">null (never estimated)</span>')
            src = (f"{S.esc(r.get('source_company', ''))}, "
                   f"{S.esc(r.get('source_document', ''))} "
                   f"({S.esc(r.get('source_date', ''))})")
            kind = {"turnaround": "Turnaround",
                    "none_found": "No turnaround in window (stated)",
                    "forward_schedule": "Scheduled (future window)"}.get(
                        r.get("kind"), r.get("kind", ""))
            out.append(f"    <tr><td>{S.esc(r['project_id'])}</td>"
                       f"<td>{S.esc(P.timing_str(r))}</td>"
                       f"<td>{S.esc(kind)}</td>"
                       f'<td class="num">{imp_s}</td>'
                       f"<td>{src}</td></tr>")
        out.append("  </table></div>")

    out.append(modeled_offline_table(data, R, fc))
    out.append("  <h2>Modeled maintenance offline by month</h2>")
    out.append(maintenance_chart(data, R, fc))
    out.append('  <p class="note">Per-asset calendars live on each '
               '<a href="../projects/index.html">project profile</a>.</p>')
    out.append("  <h2>Sources</h2>")
    out.append(S.sources_table())

    d = SITE / "maintenance"
    d.mkdir(parents=True, exist_ok=True)
    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "Maintenance", "Maintenance",
        "Forward maintenance calendar by asset, Oct 2026-Dec 2027: "
        "confirmed, cadence-modeled, and guidance-sourced, with kb/d impacts.",
        '<a href="../index.html">Home</a> / <a href="../supply/index.html">Supply</a> / Maintenance', "\n".join(out),
        "maintenance", 1, updated, SOURCE_LINE,
        description="Forward maintenance calendar by asset, Oct 2026-Dec 2027: "
                    "confirmed, cadence-modeled, and guidance-sourced outages "
                    "with kb/d impacts.",
        url_path="maintenance/index.html"))
    print(f"wrote {d / 'index.html'}")


# ----------------------------------------------------------------------------
# /weekly/
# ----------------------------------------------------------------------------

def weekly_meta(w):
    t = Path(BASE / "reports/weekly" / w["file"]).read_text()
    m = re.search(r"<!-- REPORT-META (.*?) -->", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return {}
    return {}


def exec_bullets(w):
    t = Path(BASE / "reports/weekly" / w["file"]).read_text()
    m = re.search(r'<div class="exec"><h2>The call</h2><ul>(.*?)</ul>', t, re.S)
    if not m:
        return []
    return [re.sub(r"<[^>]+>", "", b).strip()
            for b in re.findall(r"<li>(.*?)</li>", m.group(1), re.S)]


def build_weekly(data, weekly):
    newest = max(weekly, key=lambda x: x["date"]) if weekly else None
    # Editions live in the same directory as this archive page (/weekly/).
    newest_href = newest["file"] if newest else "index.html"
    out = ['  <p class="sub">The Heavy Reading weekly letter: every edition, '
           "newest first. Each edition carries its masthead, date, vintages, "
           "executive call, charts, risks, methodology, and source appendix.</p>"]
    out.append('  <p class="note">This section: '
               f'<a href="{newest_href}">Latest edition</a> &middot; '
               '<a href="index.html" aria-current="page">Edition archive</a></p>')
    out.append('  <div class="tblwrap"><table class="data">')
    out.append("    <tr><th>Edition</th><th>Date</th><th>The call (teaser)</th>"
               "<th>License</th></tr>")
    for w in sorted(weekly, key=lambda x: x["date"], reverse=True):
        meta = weekly_meta(w)
        lic = meta.get("license", "public")
        lic_s = (f'<span class="lic-tag">{S.esc(S.license_label(lic))}</span>'
                 if lic != "public" else "public")
        bullets = exec_bullets(w)
        teaser = ("<br>".join(f"&middot; {S.esc(b)}" for b in bullets[:2])
                  if bullets else '<span class="nullnote">n/a</span>')
        out.append(f'    <tr><td><a href="{w["file"]}">WCSB Weekly</a></td>'
                   f"<td>{S.esc(w['date'])}</td><td>{teaser}</td>"
                   f"<td>{lic_s}</td></tr>")
    out.append("  </table></div>")
    out.append("  <h2>Sources</h2>")
    out.append(S.sources_table())

    d = SITE / "weekly"
    d.mkdir(parents=True, exist_ok=True)
    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "The Letter", "The Letter",
        "The Heavy Reading weekly letter, and its full edition archive.",
        '<a href="../index.html">Home</a> / The Letter', "\n".join(out),
        "weekly", 1, updated, SOURCE_LINE,
        description="The Heavy Reading weekly letter: every edition of the WCSB "
                    "supply letter, newest first, each with its executive call, "
                    "charts, risks, and source appendix.",
        url_path="weekly/index.html"))
    print(f"wrote {d / 'index.html'}")


# ----------------------------------------------------------------------------
# /methodology/ and /sources/
# ----------------------------------------------------------------------------

def build_methodology(data):
    out = ["  <h2>What this model is</h2>",
           "  <p>A physical supply/demand balance for the Western Canadian "
           "Sedimentary Basin. It is not a differential forecast. Every "
           "number carries its publisher, vintage, and method; unknown values "
           "stay null, never fabricated.</p>",
           "  <h2>Supply forecast</h2>",
           "  <p>Forecast at the most granular public leaves, then aggregate: "
           "AER ST53 commercial-scheme leaves for SAGD/CSS, ST39 facility "
           "rows for mined bitumen and SCO, ST3 lines for conventional "
           "streams. Each leaf is a trailing-12-month mean times a seasonal "
           "factor from the last three complete years. Mapped ST53 projects "
           "cover 76.7% of ST3 in-situ; the balance is grossed up with an "
           "explicit coverage factor.</p>",
           "  <h2>Maintenance</h2>",
           "  <p>Maintenance offline counts public-confirmed company "
           "guidance and transcript items plus two editorially approved "
           "cadence-modeled events (Primrose/Wolf Lake Apr 2027, -26 kb/d, "
           "weak-signal flag; MacKay River Sep 2027, -12 kb/d; labeled "
           "CADENCE-MODELED everywhere, never as confirmed), modeled at the "
           "project leaves. The "
           "forward calendar (2026-10-01 to 2027-12-31, revised 2026-09-23) "
           "distinguishes public-confirmed, cadence-modeled, and "
           "guidance-sourced entries; unknown volumes stay null.</p>",
           "  <h2>Grade layer</h2>",
           "  <p>Supply is cut by grade as well as by source: SCO (upgraded "
           "production), marketable bitumen (dilbit), and bitumen sent for "
           "further processing. Grade conversion default: 0.87 SCO per barrel "
           "of bitumen feed (observed: fleet 0.865, Horizon 0.888, Syncrude "
           "0.843). NFT mined bitumen (Suncor Base, Syncrude, Horizon) is "
           "upgrader-locked and cannot meet pipeline dilbit spec; PFT mines "
           "(Kearl, Fort Hills) sell dilbit directly; SAGD bitumen is "
           "flexible between dilbit sales and upgrader feed. See the "
           "dashboard grade-layer assumptions panel for the full leaf "
           "mapping.</p>",
           "  <h2>Supply by type</h2>",
           "  <p>The /supply/ stack cuts ST3 actuals, nowcast, and forecast "
           "into four buckets every month. Heavy = marketable bitumen "
           "(dilbit) + conventional heavy + ultra-heavy. SCO = upgraded "
           "synthetic crude. Light = conventional light plus condensate "
           "production (condensate is mostly diluent supply and is folded "
           "into Light, labeled as such). Medium = the ST3 density grade; "
           "medium sour cannot be isolated because ST3 carries no sulfur "
           "cut. A tie-out guard runs at build time: the four buckets must "
           "foot to total WCSB crude supply within 0.2 kb/d every month, or "
           "the build fails.</p>",
           "  <h2>Egress</h2>",
           "  <p>Available egress capacity (Enbridge Mainline, Keystone, "
           "Trans Mountain) is stacked against total throughput each month "
           "from CER open data (pulled 2026-09-22). Spare capacity = "
           "available capacity minus throughput; utilization = throughput "
           "divided by available capacity. Express and crude-by-rail are "
           "omitted: no verified repo series exists for either, and the "
           "model does not invent one.</p>",
           "  <h2>Storage</h2>",
           "  <p>Implied storage change follows the exact AER ST3 inventory "
           "identity: supply total (maintenance already netted at the "
           "project leaves, so no separate maintenance term) plus total "
           "receipts minus flare, fuel, and shrinkage plus ST3 adjustments "
           "minus Alberta use minus removals minus the AER reporting "
           "adjustment (all kb/d). The identity reproduces the reported "
           "closing-minus-opening inventory change in all 199 history "
           "months (2010-01 through 2026-07) within 0.1 kb/d; the build "
           "fails loudly otherwise. The reporting adjustment is the AER's "
           "own disposition-side plug: persistently positive (mean +56 "
           "kb/d over full history, +95.5 kb/d trailing 12 months), so it "
           "enters the identity subtracted. History uses the reported "
           "value; forecast months carry the trailing-12-month mean, "
           "recomputed each build. The plug is disclosed on its own row, "
           "never buried in supply, and never enters the five marketed "
           "supply rows. The Balance page charts the implied storage "
           "level in million barrels: reported closing inventory history, "
           "a seasonal five-year min/max channel, and the forecast from "
           "the last actual inventory plus cumulative monthly implied "
           "changes, against the full-history maximum.</p>",
           "  <h2>Trading cycle</h2>",
           "  <p>Injection-month barrels trade during the prior calendar "
           "month, before noms day. The tradable barrel is always past the "
           "current maintenance window, so the forward balance for the next "
           "tradable injection month is what prices barrels, not the current "
           "outage snapshot.</p>",
           "  <h2>Sources</h2>",
           S.sources_table()]
    d = SITE / "methodology"
    d.mkdir(parents=True, exist_ok=True)
    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "Methodology", "Methodology",
        "Standing methodology for the WCSB S&D model.",
        '<a href="../index.html">Home</a> / Methodology', "\n".join(out),
        "methodology", 1, updated, SOURCE_LINE,
        description="Standing methodology for the WCSB S&D model: how supply "
                    "is forecast, how maintenance is modeled, and how storage "
                    "is implied.",
        url_path="methodology/index.html"))
    print(f"wrote {d / 'index.html'}")


def build_sources_page(data):
    out = ['  <p class="sub">Every publisher, dataset, URL, publication date, '
           "vintage, and retrieval date behind the numbers on this site. "
           "Anything without a URL on record is labeled, never invented.</p>",
           S.sources_table()]
    d = SITE / "sources"
    d.mkdir(parents=True, exist_ok=True)
    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "Sources", "Sources",
        "Full citation block for Heavy Reading.",
        '<a href="../index.html">Home</a> / <a href="../methodology/index.html">Methodology</a> / Sources',
        "\n".join(out), "sources", 1, updated, SOURCE_LINE,
        description="Full citation block for Heavy Reading: every dataset, "
                    "company disclosure, and model build behind the site.",
        url_path="sources/index.html"))
    print(f"wrote {d / 'index.html'}")


# ----------------------------------------------------------------------------
# /data/ : free CSV downloads of every public series used
# ----------------------------------------------------------------------------

def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def build_data(data, fwd, overlap):
    R = R_(data)
    months = data["act_months"] + data["gap_months"] + data["fc_months"]
    b_ = bands(data)
    d = SITE / "data"

    def col(rid, m):
        v = R[rid]["values"].get(m)
        return "" if v is None else f"{v:.1f}"

    bal_ids = ["supply_total", "in_situ", "mined_grp", "conv", "diluent",
               "ab_use", "removals_from_alberta", "maint", "total_receipts",
               "losses_ffl", "adjustments", "aer_plug", "stor_chg"]
    write_csv(d / "wcsb_balance_monthly.csv",
              ["month", "band"] + bal_ids,
              [[m, b_[m]] + [col(i, m) for i in bal_ids] for m in months])

    grade_ids = ["grade_conv_light", "grade_conv_sour", "grade_conv_heavy",
                 "grade_sco", "grade_dilbit", "grade_total"]
    write_csv(d / "wcsb_grades_monthly.csv",
              ["month", "band"] + grade_ids,
              [[m, b_[m]] + [col(i, m) for i in grade_ids] for m in months])

    leaf_ids = sorted(r["id"] for r in data["rows"]
                      if r["id"].startswith(("proj_", "plant_", "scoplant_")))
    write_csv(d / "wcsb_project_leaves_monthly.csv",
              ["month", "band"] + leaf_ids,
              [[m, b_[m]] + [col(i, m) for i in leaf_ids] for m in months])

    cal_rows = []
    for pid in sorted(set(list(fwd) + list(overlap))):
        for o in overlap.get(pid, []):
            cal_rows.append([pid, "", "", "", "in_model_math", "",
                             "", "", "", "", o["note"]])
        for r in fwd.get(pid, []):
            cal_rows.append([pid, r.get("window_start", ""),
                             r.get("window_end", ""),
                             r.get("window_precision", ""), r.get("kind", ""),
                             r.get("validation", ""),
                             "" if r.get("impact_kbd") is None
                             else f"{r['impact_kbd']:+.1f}",
                             r.get("source_company", ""),
                             r.get("source_document", ""),
                             r.get("source_date", ""),
                             r.get("source_url", "")])
    write_csv(d / "wcsb_maintenance_calendar.csv",
              ["project_id", "window_start", "window_end", "window_precision",
               "kind", "validation", "impact_kbd", "source_company",
               "source_document", "source_date", "source_url"],
              cal_rows)

    files = [
        ("wcsb_balance_monthly.csv", "Monthly S&D balance: supply, diluent, "
         "Alberta use, removals, maintenance offline, implied storage change.",
         "AER ST3/ST39/ST53 via the model"),
        ("wcsb_grades_monthly.csv", "Monthly supply by market stream: "
         "conventional lights, conventional sours, blended heavy "
         "conventional, synthetic crude oil (SCO), blended dilbit, total "
         "crude supply.",
         "Model grade layer"),
        ("wcsb_project_leaves_monthly.csv", "Monthly production by project "
         "leaf (ST53 schemes, ST39 plants and upgraders).",
         "AER ST53/ST39 via the model"),
        ("wcsb_maintenance_calendar.csv", "Forward maintenance calendar, "
         "Oct 2026 to Dec 2027: public-confirmed, cadence-modeled "
         "(CADENCE-MODELED), and guidance-sourced, kb/d impacts.",
         "Forward maintenance calendar (revised 2026-09-23)"),
    ]  # S&D purity: Venezuela datasets live on the Venezuela watch page (World).
    out = ['  <p class="sub">Free CSV downloads of every public WCSB supply/demand '
           "series used on this site. Their $195 paywall, drained. No licensed "
           "data appears in any file.</p>"]
    out.append('  <div class="tblwrap"><table class="data">')
    out.append("    <tr><th>File</th><th>Contents</th><th>Source</th></tr>")
    for fn, desc, src in files:
        out.append(f'    <tr><td><a href="{fn}" download>{fn}</a></td>'
                   f"<td>{S.esc(desc)}</td><td>{S.esc(src)}</td></tr>")
    out.append("  </table></div>")
    out.append(f'  <p class="tblnote">{S.esc(VINTAGE)} Months run '
               f'{data["act_months"][0]} to {data["fc_months"][-1]}; band is '
               "act (AER actuals), nc (model nowcast), or fc (model forecast). "
               "Blank cells are unpublished months, not zeros.</p>")
    out.append("  <h2>Sources</h2>")
    out.append(S.sources_table())

    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "Data", "Data",
        "Free downloads. Every public series behind the site, as CSV.",
        '<a href="../index.html">Home</a> / <a href="../fieldguide/index.html">Reference</a> / Data', "\n".join(out),
        "data", 1, updated, SOURCE_LINE,
        description="Free downloads: every public series behind Heavy Reading, "
                    "as CSV.",
        url_path="data/index.html"))
    print(f"wrote {d / 'index.html'} + 4 CSVs")


# ----------------------------------------------------------------------------
# /venezuela/ : the WCS comp barrel — public data, charts, and the WCS read
# ----------------------------------------------------------------------------

VE_DIR = Path("/home/hatch/workspace/goals/crude-oil-morning-digest"
              "/hidden_files/venezuela")

VE_DATA_FILES = []  # populated by build_venezuela; appended on /data/


def _ve_read_csv(name):
    p = VE_DIR / name
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def _ve_weekly_bars(weeks, values, title, unit="kb/d", palkey="ink"):
    """Simple weekly bars with week-ending labels (shared helpers are monthly)."""
    W, H = 720, 250
    n = len(weeks)
    have = [v for v in values if v is not None]
    top = S._nice_top(max(have)) if have else 1
    # Size the left margin off the widest y tick label so large values never
    # clip past the SVG edge.
    L = S._left_for_ticks([S.f1(top * k / 4) for k in range(5)], 48)
    R, T, Bm = 10, 12, 38
    cw = (W - L - R) / max(n, 1)
    bw = min(cw * 0.62, 30)

    def ypix(v):
        return T + ((top - v) / top) * (H - T - Bm)

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="{S.esc(title)}">']
    parts.append(f"<title>{S.esc(title)}</title>")
    parts.append(S._bg(W, H))
    for k in range(5):
        v = top * k / 4
        y = ypix(v)
        parts.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" '
                     f'style="stroke:var(--ch-grid)"/>')
        parts.append(f'<text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end" '
                     f'font-size="11" style="fill:var(--mut)">{S.f1(v)}</text>')
    for i, wk in enumerate(weeks):
        v = values[i]
        if v is None:
            continue
        x = L + i * cw + (cw - bw) / 2
        yv = ypix(v)
        lab = f"{B._MNAMES[int(wk[5:7]) - 1]} {int(wk[8:10])}"
        parts.append(f'<rect x="{x:.1f}" y="{yv:.1f}" width="{bw:.1f}" '
                     f'height="{max(H - T - Bm - (yv - T), 1.5):.1f}" '
                     f'style="fill:{S.PAL[palkey]}"><title>{lab}: {S.f1(v)} {unit}'
                     f"</title></rect>")
    step = max(1, n // 8)
    for i, wk in enumerate(weeks):
        if i % step == 0:
            x = L + i * cw + cw / 2
            lab = f"{B._MNAMES[int(wk[5:7]) - 1]} {int(wk[8:10])}"
            # Edge labels are pulled inside the viewBox rather than spilling.
            lw = S._est_text_w(lab, 11)
            tx = min(max(x, lw / 2 + 2), W - lw / 2 - 2)
            parts.append(f'<text x="{tx:.1f}" y="{H - 14}" text-anchor="middle" '
                         f'font-size="11" style="fill:var(--mut)">{lab}</text>')
    parts.append(f'<text x="{L - 6}" y="{T - 2}" font-size="11" '
                 f'style="fill:var(--mut)">{S.esc(unit)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _ve_num(s):
    try:
        return float(s) if s not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_venezuela(data):
    d = SITE / "venezuela"
    d.mkdir(parents=True, exist_ok=True)
    data_d = SITE / "data"
    updated = S.edition_date(data.get("built", "2026-09-23"))

    imports = _ve_read_csv("eia_ve_imports_weekly.csv")
    exp_w = _ve_read_csv("eia_us_exports_weekly.csv")
    exp_m = _ve_read_csv("eia_us_exports_monthly.csv")
    prod = _ve_read_csv("momr_ve_production.csv")
    merey = _ve_read_csv("merey_pricing.csv")
    freight = _ve_read_csv("freight_rates.csv")

    copies = [
        ("eia_ve_imports_weekly.csv", "venezuela_imports_weekly.csv",
         "Weekly US imports of Venezuelan crude, kb/d.",
         "EIA WPSR Table 8 (EIA API v2)"),
        ("eia_us_exports_weekly.csv", "us_crude_exports_weekly.csv",
         "Weekly US crude exports, kb/d.",
         "EIA Weekly Petroleum Status Report (EIA API v2)"),
        ("eia_us_exports_monthly.csv", "us_crude_exports_monthly.csv",
         "Monthly US crude exports, kb/d.",
         "EIA Petroleum Supply Monthly (EIA API v2)"),
        ("momr_ve_production.csv", "venezuela_production_monthly.csv",
         "Venezuelan crude production: OPEC secondary sources vs direct "
         "communication, kb/d.",
         "OPEC Monthly Oil Market Report"),
        ("merey_pricing.csv", "merey_pricing.csv",
         "Reported Merey outright prices and Brent differentials.",
         "Reported assessments (see Sources)"),
        ("freight_rates.csv", "venezuela_freight_rates.csv",
         "Aframax Jose-to-USGC lump sums and $/bbl equivalents.",
         "Reported fixtures (see Sources)"),
    ]
    VE_DATA_FILES.clear()
    for src, dst, desc, pub in copies:
        p = VE_DIR / src
        if p.exists():
            (data_d / dst).write_bytes(p.read_bytes())
            VE_DATA_FILES.append((dst, desc, pub))

    out = ['  <p class="sub">Venezuelan heavy sour is the waterborne '
           "competitor that prices WCS. Public data only: EIA imports and "
           "exports, OPEC production, reported Merey prices and freight. "
           "Nothing here is licensed data.</p>"]

    # --- weekly imports chart
    if imports:
        rows = sorted(imports, key=lambda r: r["week_ending"])[-26:]
        weeks = [r["week_ending"] for r in rows]
        vals = [_ve_num(r.get("imports_kbd")) for r in rows]
        svg = _ve_weekly_bars(weeks, vals, "US imports of Venezuelan crude")
        latest = rows[-1]
        cap = (S.vintage_caption(
            "EIA WPSR Table 8 via EIA API v2, series "
            "W_EPC0_IM0_NUS-NVE_MBBLD; weeks ending %s to %s, pulled %s."
            % (weeks[0], weeks[-1], latest.get("retrieved_date", "")))
            + " Latest week: %s kb/d." % latest.get("imports_kbd", ""))
        out.append("  <h2>US imports of Venezuelan crude</h2>")
        out.append(S.chart_figure(
            svg, cap, [("Weekly imports", "#2b2f36")]))
    else:
        out.append("  <h2>US imports of Venezuelan crude</h2>")
        out.append("  <p>Awaiting first prints.</p>")

    # --- production: secondary vs direct
    if prod:
        rows = sorted(prod, key=lambda r: r["month"])
        months = [r["month"] for r in rows]
        sec = {r["month"]: _ve_num(r.get("secondary_kbd")) for r in rows}
        drc = {r["month"]: _ve_num(r.get("direct_kbd")) for r in rows}
        bands = {m: "act" for m in months}
        src_note = rows[-1].get("source", "")
        out.append("  <h2>Venezuelan production: secondary sources vs direct "
                   "communication</h2>")
        svg = S.svg_bars(months, sec, bands, (),
                         title="Venezuela production, secondary sources")
        out.append(S.chart_figure(
            svg, S.vintage_caption(
                "%s; months %s to %s." % (src_note, months[0], months[-1]))
            + " OPEC secondary-source estimates, kb/d.",
            [("Secondary sources", "#2b2f36")]))
        svg = S.svg_bars(months, drc, bands, (),
                         title="Venezuela production, direct communication")
        out.append(S.chart_figure(
            svg, S.vintage_caption(
                "%s; months %s to %s." % (src_note, months[0], months[-1]))
            + " PDVSA self-reported (direct communication), kb/d. Treat "
              "with skepticism; history wins over announcements.",
            [("Direct communication", "#b42318")]))
        last = rows[-1]
        out.append('  <p>Latest: %s secondary, %s direct (kb/d, %s).</p>'
                   % (last.get("secondary_kbd"), last.get("direct_kbd"),
                      last.get("month")))
    else:
        out.append("  <h2>Venezuelan production</h2>")
        out.append("  <p>Awaiting first prints.</p>")

    # --- Merey pricing table
    out.append("  <h2>Merey pricing</h2>")
    if merey:
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>Observation</th><th>Value</th><th>Basis</th>"
                   "<th>Source</th></tr>")
        for r in sorted(merey, key=lambda r: r.get("date", "")):
            out.append("    <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                       % (S.esc(r.get("date", "")), S.esc(r.get("value", "")),
                          S.esc(r.get("basis", "")), S.esc(r.get("source", ""))))
        out.append("  </table></div>")
        out.append('  <p class="tblnote">Points come on different bases '
                   "(outright vs Brent differential); they are not one "
                   "continuous series. A chart appears once a consistent "
                   "differential series accumulates.</p>")
    else:
        out.append("  <p>Awaiting first prints.</p>")

    # --- freight
    out.append("  <h2>Jose to USGC freight</h2>")
    if freight:
        rows = sorted(freight, key=lambda r: r.get("date", ""))
        # normalize to YYYY-MM keys for the shared chart helper
        fmonths = [r["date"][:7] for r in rows]
        fvals = {m: _ve_num(v) for m, v in
                 zip(fmonths, [r.get("value") for r in rows])}
        svg = S.svg_bars(fmonths, fvals, {m: "act" for m in fmonths}, (),
                         title="Aframax Jose-USGC freight", unit="$/bbl")
        out.append(S.chart_figure(
            svg, S.vintage_caption(
                "Reported Aframax fixtures, Jose to USGC, $/bbl equivalent "
                "(lump sum / ~700 kb cargo).")
            + " Freight up widens the FOB netback wedge and pressures "
              "PDVSA to lower its offer.",
            [("Freight, $/bbl", "#2b2f36")]))
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>Observation</th><th>$/bbl</th><th>Basis</th>"
                   "<th>Source</th></tr>")
        for r in rows:
            out.append("    <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                       % (S.esc(r.get("date", "")), S.esc(r.get("value", "")),
                          S.esc(r.get("basis", "")), S.esc(r.get("source", ""))))
        out.append("  </table></div>")
    else:
        out.append("  <p>Awaiting first prints.</p>")

    # --- US exports (export-arb context)
    out.append("  <h2>US crude exports: the export-arb read</h2>")
    if exp_w:
        rows = sorted(exp_w, key=lambda r: r["week_ending"])[-26:]
        weeks = [r["week_ending"] for r in rows]
        vals = [_ve_num(r.get("exports_kbd")) for r in rows]
        svg = _ve_weekly_bars(weeks, vals, "US crude exports, weekly",
                              palkey="blue")
        out.append(S.chart_figure(
            svg, S.vintage_caption(
                "EIA via API v2, series WCREXUS2; weeks ending %s to %s."
                % (weeks[0], weeks[-1]))
            + " Export arb = Brent minus WTI Houston minus freight. "
              "Positive arb opens the window and exports respond with a lag; "
              "negative arb backs barrels into PADD 3 and pressures WTI, "
              "then WCS through the light-heavy spread.",
            [("Weekly exports", "var(--ch-blue)")]))
    else:
        out.append("  <p>Awaiting first prints.</p>")

    # --- destinations (estimates)
    out.append("  <h2>Where the barrels go</h2>")
    out.append("  <p>Destination splits are <b>estimates</b>: dark-fleet AIS "
               "gaps and ship-to-ship transfers mean no exact accounting "
               "exists. August 2026 estimates from tanker-tracking reporting "
               "(Reuters, September 2026):</p>")
    out.append('  <div class="tblwrap"><table class="data">')
    out.append("    <tr><th>Destination</th><th>Est. kb/d</th></tr>")
    out.append("    <tr><td>United States (Chevron-licensed)</td>"
               "<td>~553</td></tr>")
    out.append("    <tr><td>India</td><td>~297</td></tr>")
    out.append("    <tr><td>Europe</td><td>~260</td></tr>")
    out.append("  </table></div>")

    # --- how this prices WCS
    out.append("  <h2>How this prices WCS</h2>")
    out.append("  <p>Merey and WCS are alternative heavy-sour barrels for "
               "USGC cokers and Asian teapots. A refiner choosing between "
               "discounted Merey and WCS treats them as alternates, so "
               "Venezuelan crude prices WCS even when it never lands in "
               "the US.</p>")
    out.append("  <ul>")
    out.append("    <li>Higher freight widens the FOB netback wedge and "
               "pressures PDVSA to lower its offer to keep barrels placed.</li>")
    out.append("    <li>Lower Merey offers reprice the competing heavy-sour "
               "complex (Merey, WCS, Arab Heavy, Basrah Heavy): if Merey is "
               "offered lower into China or Europe, WCS must follow to "
               "clear.</li>")
    out.append("    <li>ARV minus TMW is the Hardisty-to-Houston export-arb "
               "context for this read, not a modeled differential "
               "forecast.</li>")
    out.append("  </ul>")

    # --- downloads: the venezuela CSVs live here, not on the S&D Data page
    if VE_DATA_FILES:
        out.append("  <h2>Downloads</h2>")
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>File</th><th>Contents</th><th>Source</th></tr>")
        for fn, desc, pub in VE_DATA_FILES:
            out.append(f'    <tr><td><a href="../data/{fn}" download>{fn}</a></td>'
                       f"<td>{S.esc(desc)}</td><td>{S.esc(pub)}</td></tr>")
        out.append("  </table></div>")

    # --- sources
    out.append("  <h2>Sources</h2>")
    out.append('  <div class="tblwrap"><table class="data">')
    out.append("    <tr><th>Series</th><th>Publisher</th><th>Detail</th>"
               "<th>Observation</th><th>Retrieved</th></tr>")
    src_rows = []
    if imports:
        last = max(imports, key=lambda r: r["week_ending"])
        src_rows.append((
            "US imports of Venezuelan crude", "EIA",
            'WPSR Table 8, API v2 series W_EPC0_IM0_NUS-NVE_MBBLD '
            '(<a href="https://www.eia.gov/petroleum/">eia.gov/petroleum</a>)',
            "week ending " + last["week_ending"],
            last.get("retrieved_date", "")))
    if prod:
        last = max(prod, key=lambda r: r["month"])
        src_rows.append((
            "Venezuelan production", "OPEC",
            'MOMR Tables 5-7/5-8 (<a href="https://www.opec.org/assets/'
            'assetdb/momr-august-2026.pdf">August 2026 MOMR PDF</a>)',
            last["month"], last.get("retrieved_date", "")))
    if exp_w:
        last = max(exp_w, key=lambda r: r["week_ending"])
        src_rows.append((
            "US crude exports (weekly)", "EIA",
            'API v2 series WCREXUS2 '
            '(<a href="https://www.eia.gov/petroleum/">eia.gov/petroleum</a>)',
            "week ending " + last["week_ending"],
            last.get("retrieved_date", "")))
    if exp_m:
        last = max(exp_m, key=lambda r: r["month"])
        src_rows.append((
            "US crude exports (monthly)", "EIA",
            'API v2 series MCREXUS2 '
            '(<a href="https://www.eia.gov/petroleum/">eia.gov/petroleum</a>)',
            last["month"], last.get("retrieved_date", "")))
    for r in sorted(merey, key=lambda r: r.get("date", "")):
        url = r.get("source_url", "")
        link = (f'<a href="{S.esc(url)}">link</a>' if url else "")
        src_rows.append(("Merey " + r.get("date", ""), "Reported",
                         "%s %s" % (S.esc(r.get("source", "")), link),
                         r.get("date", ""), "2026-09-23"))
    for r in sorted(freight, key=lambda r: r.get("date", "")):
        url = r.get("source_url", "")
        link = (f'<a href="{S.esc(url)}">link</a>' if url else "")
        src_rows.append(("Freight " + r.get("date", ""), "Reported",
                         "%s %s" % (S.esc(r.get("source", "")), link),
                         r.get("date", ""), "2026-09-23"))
    for s in src_rows:
        out.append("    <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                   "<td>%s</td></tr>" % s)
    out.append("  </table></div>")

    (d / "index.html").write_text(S.page_shell(
        "Venezuela", "Venezuela",
        "The WCS comp barrel: public data on Venezuelan crude, freight, "
        "and how they price WCS.",
        '<a href="../index.html">Home</a> / <a href="../world/index.html">World</a> / Venezuela',
        "\n".join(out),
        "venezuela", 1, updated,
        "EIA WPSR/API; OPEC MOMR; reported Merey and freight assessments",
        description="The WCS comp barrel: public data on Venezuelan crude, "
                    "freight, and how they price WCS.",
        url_path="venezuela/index.html"))
    print(f"wrote {d / 'index.html'} + {len(VE_DATA_FILES)} CSVs")


# ----------------------------------------------------------------------------
# /world/ : geopolitical supply coverage landing page
# ----------------------------------------------------------------------------

def build_world(data):
    out = ['  <p class="sub">WCSB crude is effectively global sour now: it '
           "prices against Dubai, Mars, and Merey, and moves on Hormuz "
           "transits, Red Sea freight, Russian refinery outages, Chinese "
           "buying, SPR policy, and Washington. These watches track those "
           "drivers. Kept separate from the supply/demand model pages by "
           "design.</p>",
           "  <h2>Coverage</h2>",
           '  <ul class="ev">',
           "  <li><b><a href=\"hormuz/index.html\">Hormuz watch</a></b>: Tanker movement through the world\'s most important oil chokepoint.</li>",
           "  <li><b><a href=\"iran/index.html\">Iran watch</a></b>: Iranian oil exports under sanctions and blockade: tanker-tracked estimates, floating storage, the shadow fleet, and China\'s buying.</li>",
           "  <li><b><a href=\"redsea/index.html\">Red Sea</a></b>: Shipping disruptions and rerouting around the Red Sea.</li>",
           "  <li><b><a href=\"russia-refining/index.html\">Russian refineries</a></b>: Refinery capacity offline in the Russia-Ukraine war.</li>",
           "  <li><b><a href=\"china-imports/index.html\">China imports</a></b>: China\'s crude-import appetite, the marginal call on sour barrels.</li>",
           "  <li><b><a href=\"spr-storage/index.html\">SPR & storage</a></b>: US SPR and commercial storage: refills, capacity, policy.</li>",
           "  <li><b><a href=\"trump/index.html\">Trump watch</a></b>: Trump as a first-order driver of Canadian differentials: tariffs, meetings, SPR moves, and the archive of past episodes.</li>",
           "  <li><b><a href=\"sour/index.html\">The global sour barrel</a></b>: Dubai, Mars, Merey: the sour comparables that price WCS, and the arb drivers that move them.</li>",
           "  <li><b><a href=\"opec-middle-east/index.html\">OPEC &amp; Middle East</a></b>: Organization of the Petroleum Exporting Countries (OPEC+) supply decisions and Middle East crude flows: quotas, compliance, and spare capacity.</li>",
           "  <li><b><a href=\"condensate-diluent/index.html\">Condensate &amp; diluent</a></b>: Condensate supply and diluent demand for oil-sands blending: the other half of the Western Canadian Select (WCS) barrel.</li>",
           "  <li><b><a href=\"refinery-margins/index.html\">Refinery margins</a></b>: Refining margins and runs: what refineries earn cracking the barrel, and what that means for crude demand.</li>",
           '  <li><b><a href="../venezuela/index.html">Venezuela watch</a></b>: '
           "the WCS comp barrel. Public data on Venezuelan crude production, "
           "US imports, reported Merey prices, and freight, and how they "
           "price WCS.</li>",
           "  </ul>",
           '  <p class="note">Atlantic basin notes will land here as they are built.</p>',
           "  <h2>Sources</h2>",
           S.sources_table()]
    d = SITE / "world"
    d.mkdir(parents=True, exist_ok=True)
    updated = S.edition_date(data.get("built", "2026-09-23"))
    (d / "index.html").write_text(S.page_shell(
        "World", "World",
        "Geopolitical supply coverage, separate from the WCSB S&D model.",
        '<a href="../index.html">Home</a> / World', "\n".join(out),
        "world", 1, updated, SOURCE_LINE,
        description="Geopolitical supply coverage, separate from the WCSB S&D "
                    "model.",
        url_path="world/index.html"))
    print(f"wrote {d / 'index.html'}")


# ----------------------------------------------------------------------------
# Home: magazine front page. Light on purpose: the executive call (short),
# the four sections, and the latest weekly teaser. Everything else already
# has a section page; nothing heavy is duplicated here.
# ----------------------------------------------------------------------------

_GEO_RULES = [
    ("yanbu", "Saudi supply and export flows"),
    ("petroline", "Saudi supply and export flows"),
    ("east-west pipeline", "Saudi supply and export flows"),
    ("hormuz", "the Strait of Hormuz closure"),
    ("red sea", "Red Sea shipping disruptions"),
    ("iran", "Iranian export flows"),
    ("saudi", "Saudi supply and export flows"),
    ("russia", "Russian refinery outages and crude exports"),
    ("opec", "Organization of the Petroleum Exporting Countries (OPEC) supply policy"),
    ("china", "Chinese crude buying"),
    ("strategic petroleum reserve", "United States Strategic Petroleum Reserve policy"),
    ("spr", "United States Strategic Petroleum Reserve (SPR) policy"),
    ("tariff", "Washington trade and tariff policy"),
    ("trump", "Washington policy"),
]


def _geo_phrase(text):
    b = text.lower()
    for kw, phrase in _GEO_RULES:
        if kw in b:
            return phrase
    return None


def _digest_driver():
    """Single most important geopolitical driver, from the newest morning
    edition's dek. Returns None when no edition exists."""
    ed = SITE / "digest" / "editions"
    if not ed.is_dir():
        return None
    paths = sorted(ed.glob("*.md"))
    if not paths:
        return None
    txt = paths[-1].read_text()
    m = re.search(r"^dek:\s*(.+)$", txt, re.M)
    if not m:
        return None
    return _geo_phrase(m.group(1)) or _geo_phrase(paths[-1].read_text()[:2000])


def _compress_driver(bullet):
    """Compress a lead "The call" bullet to one driver phrase.

    Keyword map first (deterministic, build-time); fallback is the bullet's
    first sentence clipped to a card-sized phrase.
    """
    b = bullet.lower()
    rules = [
        ("injection", "the November injection window into storage"),
        ("basis", "the Western Canadian Select (WCS) basis move"),
        ("maintenance", "heavy maintenance outages"),
        ("apportionment", "pipeline apportionment and egress tightness"),
        ("hormuz", "the Strait of Hormuz closure"),
        ("iran", "Iranian export flows"),
        ("strategic petroleum reserve", "United States Strategic Petroleum Reserve policy"),
        ("spr", "United States Strategic Petroleum Reserve (SPR) policy"),
        ("china", "Chinese crude buying"),
        ("tariff", "Washington trade and tariff policy"),
        ("trump", "Washington policy"),
        ("storage", "storage builds"),
    ]
    for kw, phrase in rules:
        if kw in b:
            return phrase
    first = bullet.split(".")[0].strip()
    return first if len(first) <= 110 else first[:107] + "..."


def _lead_driver(weekly):
    """Single most important geopolitical driver right now. Prefers the newest
    morning edition's dek, then a geopolitical keyword hit anywhere in the
    newest weekly's call bullets, then the lead bullet's general driver.
    Returns None when nothing is available."""
    driver = _digest_driver()
    if driver:
        return driver
    if not weekly:
        return None
    newest = sorted(weekly, key=lambda x: x["date"], reverse=True)[0]
    bullets = exec_bullets(newest)
    if not bullets:
        return None
    for bullet in bullets:
        phrase = _geo_phrase(bullet)
        if phrase:
            return phrase
    return _compress_driver(bullets[0])


def build_home(data, weekly):
    out = []
    if weekly:
        w = sorted(weekly, key=lambda x: x["date"], reverse=True)[0]
        w_href = f"weekly/{w['file']}"
        w_date = S.edition_date(w["date"])
        w_title = f"WCSB Weekly, {w_date}"
        out.append(
            '  <section class="hero">'
            '  <p class="kicker">This week&apos;s edition</p>'
            f'  <h2 class="herotitle"><a href="{w_href}">{w_title}</a></h2>'
            '  <p class="dek">The tradable call first, history as context.</p>'
            f'  <div class="artmeta"><span><b>Published</b> {w_date}</span>'
            f'<span class="dot"></span><span>WCSB supply letter</span></div>'
            f'  <a class="btn" href="{w_href}">Read the edition</a>'
            "  </section>")
    out.append(B.exec_panel_html(data, max_bullets=2,
                                 more_href="st3-dashboard.html"))
    # Geopolitics block: quiet list of the world watches, one plain-English
    # stakes line each, direct links to world/<slug>/. No data, no dateline
    # strip, no announcements. Sits after the executive core (exec panel)
    # and before the section entrances below.
    geo_watches = [
        ("iran", "Iran watch",
         "Iran's sanctioned barrels still sail, and China buys most of them. "
         "The shadow fleet is the swing tanker supply on the sour market."),
        ("hormuz", "Hormuz watch",
         "A Hormuz disruption is the fastest way sour barrels reprice, and "
         "Western Canadian Select (WCS) prices as sour."),
        ("redsea", "Red Sea",
         "Rerouting around the Red Sea lengthens voyages and raises freight, "
         "which changes what it costs to move a barrel across oceans."),
        ("russia-refining", "Russian refineries",
         "Russian refinery outages push more Russian crude onto export "
         "routes, where it competes with the sour barrels WCS buyers bid on."),
        ("china-imports", "China imports",
         "China is the marginal buyer of the world's sour barrels, including "
         "Iranian and Russian grades that compete with WCS."),
        ("opec-middle-east", "OPEC & Middle East",
         "Organization of the Petroleum Exporting Countries (OPEC+) quota "
         "decisions set the Middle East sour supply that WCS competes against."),
        ("trump", "Trump watch",
         "Tariffs and policy moves from Washington hit Canadian differentials "
         "directly."),
        ("sour", "The global sour barrel",
         "Dubai, Mars, and Merey are the sour benchmarks WCS is priced "
         "against. Their spreads are the arb that matters."),
    ]
    out.append("  <h2>Geopolitics</h2>")
    out.append("  <ul class=\"ev\">\n" + "\n".join(
        f'  <li><b><a href="world/{slug}/index.html">{title}</a></b>: {line}</li>'
        for slug, title, line in geo_watches) + "\n  </ul>")
    # Geopolitics card names the single most important driver right now,
    # derived at build time from the newest weekly edition's lead call.
    driver = _lead_driver(weekly)
    if driver:
        geo_desc = ("WCSB crude is effectively global sour now. The single "
                    f"biggest driver right now is {driver}, "
                    "per the latest edition.")
    else:
        geo_desc = ("WCSB crude is effectively global sour now: Hormuz, the Red Sea, "
                    "Russian refineries, China, the SPR, Trump, and the sour barrel.")
    cards = [
        ("Weekly", "The Letter", "weekly/index.html",
         "This week&apos;s edition and the full archive. The tradable call first, history as context."),
        ("The model", "Supply", "st3-dashboard.html",
         "The drillable ST3 dashboard, the S&amp;D balance, the maintenance calendar, and 29 project profiles."),
        ("Geopolitics", "World", "world/index.html",
         geo_desc),
        ("The library", "Reference", "fieldguide/index.html",
         "The field guide, free data downloads, every source, and the methodology."),
    ]
    out.append("  <h2>Inside</h2>")
    # Section entrances are hairline rows, not cards (design law: clutter is
    # the enemy). The v3 .srow pattern carries kicker / title / dek / go-link.
    rows = []
    for i, (kicker, title, href_, desc) in enumerate(cards):
        last = " last" if i == len(cards) - 1 else ""
        rows.append(
            f'  <a class="srow{last}" href="{href_}">'
            f'<p class="kicker">{kicker}</p><h3>{title}</h3><p>{desc}</p>'
            f'<span class="go">Open &rarr;</span></a>')
    out.append('  <nav class="seclist" aria-label="Sections">'
               + "".join(rows) + "  </nav>")

    updated = S.edition_date(data.get("built", "2026-09-23"))
    (SITE / "index.html").write_text(S.page_shell(
        "The WCSB supply letter", "Heavy Reading",
        "The WCSB supply letter: the tradable call first, history as context. "
        "Weekly editions, a drillable supply dashboard, and 29 project profiles.",
        None, "\n".join(out), "home", 0, updated, SOURCE_LINE,
        description="Heavy Reading: the weekly WCSB supply letter. Tradable "
                    "supply calls, a drillable ST3 dashboard, maintenance "
                    "calendar, and project profiles, all from public data.",
        masthead_h1=True))
    print(f"wrote {SITE / 'index.html'}")


def main():
    data, roster, fwd, overlap, weekly = load_inputs()
    P.main()  # projects section (runs B.main() again; idempotent)
    build_balance(data)
    build_maintenance(data, fwd, overlap)
    build_weekly(data, weekly)
    build_methodology(data)
    build_sources_page(data)
    build_world(data)
    import build_watches
    build_watches.main()
    build_venezuela(data)
    build_data(data, fwd, overlap)
    build_home(data, weekly)
    print("sections + home built")


if __name__ == "__main__":
    main()
