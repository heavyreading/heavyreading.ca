#!/usr/bin/env python3
"""Build the Projects section: site/projects/index.html + per-project profiles.

Every profile is a live model output: monthly actuals from the ST53/ST39
leaves with forecast bands, SVG production charts with maintenance-month
shading, fact blocks (operator, capacity, product, status per the teardown
template), per-asset forward maintenance calendars (public-confirmed, "
"cadence-modeled, and guidance-sourced, with kb/d impacts), a market-relevance line derived from
the model's own numbers, and full citation discipline (UPDATED, SOURCE,
per-series source/vintage, citation block).

Data comes only from the existing model leaves and repo annotations:
  - ST53/ST39 leaf rows from the dashboard DATA (via build_st3_dashboard.main(),
    run here first so the pages always match the dashboard numbers exactly)
  - annotations/projects.yaml for the roster (operator, type, ticker, scheme)
  - annotations/maintenance_forward.yaml for per-asset forward calendars
All values are model/public. Unknown values render as labeled nulls, never
plugged. Project pages are public-info only, so they render identically with
or without ?public=1.

Run with the repo venv python:
    python site/build_projects.py
Idempotent: reruns produce byte-identical output when inputs are unchanged.
"""
import json
import re
import sys
from pathlib import Path

import yaml

SITE = Path(__file__).resolve().parent
BASE = SITE.parent
REPO = SITE.parent.parent.parent  # .../wcsb-sd (code + duckdb)
PROJDIR = SITE / "projects"

sys.path.insert(0, str(SITE))
import build_st3_dashboard as B  # noqa: E402  (constants + main(); import is side-effect free)
import shared as S  # noqa: E402
import intel as IX  # noqa: E402  (annotations/project_intel filing research)

# project id -> dashboard row ids for mined/integrated projects (ST39 leaves).
# SAGD/CSS projects map to their proj_<id> ST53 leaf automatically.
PROJECT_ROWS = {
    "imo_kearl": ["plant_KEARL MINE PROJECT 2-9-097-07W4M"],
    "su_fort_hills": ["plant_FORT HILLS MINE"],
    "cnq_horizon": ["plant_CNRL HORIZON OIL SANDS PROJECT",
                    "scoplant_CNRL HORIZON OIL SANDS PROJECT"],
    "su_base_plant": ["plant_SUNCOR ENERGY OSG",
                      "scoplant_SUNCOR ENERGY OSG"],
    "syncrude": ["plant_SYNCRUDE MILDRED LAKE",
                 "plant_SYNCRUDE AURORA",
                 "scoplant_SYNCRUDE MILDRED LAKE"],
}
METHOD_GROUPS = [
    ("in-situ", "In-situ", ["sagd", "css"]),
    ("mining", "Mined", ["mined", "integrated"]),
    ("upgrading", "Upgrading", ["upgrading"]),
]
TYPE_LABEL = {"sagd": "SAGD", "css": "CSS", "mined": "Mined",
              "integrated": "Integrated (mine + upgrader)",
              "upgrading": "Upgrading"}
NULL_CAP = ('<span class="nullnote">not tracked in the public data used '
            'here</span>')
GRADE_SRC = ("Dashboard grade-layer panel (leaf mapping lineage); disposition "
             "defaults from Heavy Reading maintenance records")
DISP_SRC = "Heavy Reading maintenance records"


def load_inputs():
    """Rebuild the dashboard (idempotent) and return DATA + roster + calendars."""
    B.main()
    text = (SITE / "st3-dashboard.html").read_text()
    data = None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("var DATA = {"):
            data = json.loads(s[len("var DATA = "):-1])
            break
    if data is None:
        raise RuntimeError("dashboard DATA block not found")
    roster = yaml.safe_load((REPO / "annotations/projects.yaml").read_text())["projects"]
    cal = yaml.safe_load((REPO / "annotations/maintenance_forward.yaml").read_text())
    fwd = {}
    for r in cal.get("records", []):
        fwd.setdefault(r["project_id"], []).append(r)
    overlap = {}
    for r in cal.get("window_overlap", []):
        overlap.setdefault(r["project_id"], []).append(r)
    # weekly editions for related-notes matching
    weekly = []
    for f in sorted((BASE / "reports/weekly").glob("*.html")):
        t = f.read_text()
        txt = re.sub(r"<[^>]+>", " ", t).lower()
        txt = re.sub(r"\s+", " ", txt)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        weekly.append({"file": f.name,
                       "href": f"../weekly/{f.name}",
                       "date": m.group(1) if m else f.name,
                       "text": txt})
    return data, roster, fwd, overlap, weekly


def project_row_ids(pid, row_ids):
    """Dashboard row ids backing a project profile, in display order."""
    leaf = f"proj_{pid}"
    if leaf in row_ids:
        return [leaf]
    return [r for r in PROJECT_ROWS.get(pid, []) if r in row_ids]


def bands(data):
    b = {}
    for m in data["act_months"]:
        b[m] = "act"
    for m in data["gap_months"]:
        b[m] = "nc"
    for m in data["fc_months"]:
        b[m] = "fc"
    return b


def favg(R, rid, months):
    v = [R[rid]["values"].get(m) for m in months
         if R[rid]["values"].get(m) is not None]
    return sum(v) / len(v) if v else None


def latest_actual(R, rid, act_months):
    for m in reversed(act_months):
        if R[rid]["values"].get(m) is not None:
            return m, R[rid]["values"][m]
    return None, None


# ----------------------------------------------------------------------------
# Live status
# ----------------------------------------------------------------------------

def live_status(p, rids, R, data, fwd):
    """(badge text, badge class). Model-derived, nothing invented."""
    for rid in rids:
        s = data["leaf_maint"].get(rid, {})
        hits = [(m, s[m]) for m in data["fc_months"]
                if s.get(m) not in (None, 0)]
        if hits:
            m, v = max(hits, key=lambda t: abs(t[1]))
            info = B.LEAF_MAINT_INFO.get(rid, {})
            full_evt = info.get("event", "maintenance")
            evt = full_evt.split(" (")[0]
            # Parentheticals are model-honesty labels: preserve them all.
            if "CADENCE-MODELED" in full_evt.upper():
                evt += " (CADENCE-MODELED)"
            if "ASSUMED" in full_evt.upper():
                evt += " (ASSUMED model carry, not company-stated)"
            # LEAF_MAINT stores positive magnitudes that the model subtracts:
            # always display as a deduction.
            return (f"Turnaround in model: {S.mname(m)} (-{abs(v):.1f} kb/d, "
                    f"{evt})", "badge-warn")
    pat = [r for r in fwd.get(p["id"], [])
           if r.get("validation") == "pattern-indicated"]
    if pat:
        ms = sorted({r["window_start"][:7] for r in pat})
        return (f"Pattern-indicated maintenance: "
                f"{', '.join(S.mname(m) for m in ms)} (indicator only, no "
                f"volume in model math)", "badge-info")
    if rids:
        return ("No modeled maintenance in the forward window", "badge-ok")
    return ("No production leaf in the model", "")


# ----------------------------------------------------------------------------
# Fact panel (teardown template, nulls labeled never plugged)
# ----------------------------------------------------------------------------

def product_info(p):
    pid, t = p["id"], p["type"]
    if pid == "imo_kearl":
        return ("Dilbit to market (marketed grade: Kearl Lake Dilbit, KDB); "
                "swing barrels that can also feed upgraders", GRADE_SRC)
    if pid == "su_fort_hills":
        return ("Dilbit to market (marketed grade: Fort Hills Dilbit, FRB); "
                "swing barrels that can also feed upgraders", GRADE_SRC)
    if t in ("sagd", "css"):
        return ("Bitumen: flexible disposition, dilbit to market or upgrader "
                "feed (economically optimized)", GRADE_SRC)
    if t == "integrated":
        return ("SCO from the upgrader; mined bitumen to the upgrader "
                "(froth treatment NFT: upgrader-locked, cannot meet pipeline "
                "dilbit spec)", DISP_SRC)
    return (None, None)


def intel_bullets_html(bullets):
    """Render intel fact bullets; each keeps its own document+date citation.

    Conflicting sources are all shown with their dates, never resolved
    silently. Pure 'not disclosed' bullets render as labeled nulls.
    """
    parts = []
    for b in bullets:
        t = b["text"].strip()
        if IX.is_null_bullet(t):
            parts.append('<span class="nullnote">not disclosed in reviewed '
                         "sources</span>")
            continue
        cell = S.esc(t)
        for c in b["cites"]:
            cell += (f'<div class="vintage-inline">Source: '
                     f"{S.esc(c)}</div>")
        parts.append(cell)
    return "<br>".join(parts)


# intel section -> fact-panel label
INTEL_LABELS = [
    ("Operator and ownership", "Operator / ownership"),
    ("Capacity", "Nameplate capacity"),
    ("Growth and expansions", "Growth / expansions"),
    ("Maintenance", "Company-disclosed maintenance"),
    ("Operating costs", "Operating costs"),
    ("Technology and process", "Process / technology"),
    ("Regulatory status", "Status"),
]


def facts_table(p, ix):
    prod, prod_src = product_info(p)
    t = p["type"]
    if t in ("mined", "integrated"):
        if p["id"] in ("imo_kearl", "su_fort_hills"):
            ft = "PFT (paraffinic froth treatment): sells dilbit directly"
            ft_src = DISP_SRC
        else:
            ft = "NFT (naphthenic froth treatment): upgrader-locked"
            ft_src = DISP_SRC
    else:
        ft, ft_src = "not applicable (in-situ / upgrading)", None
    if p["id"] in ("su_base_plant", "syncrude"):
        ic = ("Suncor-Syncrude bi-directional interconnects (in service "
              "~2020/21): bitumen can flow either way")
        ic_src = ("Suncor Energy, Suncor to assume Syncrude operatorship, "
                  "2020-11-24 (bi-directional pipelines connecting Base Plant "
                  "and Syncrude operations)")
    else:
        ic, ic_src = None, None
    own = p.get("note") if "JV" in p.get("note", "") else None

    def row(k, v, src=None):
        cell = esc_cell(v) if v else NULL_CAP
        if src and v:
            cell += f'<div class="vintage-inline">Source: {S.esc(src)}</div>'
        return f"    <tr><td>{k}</td><td>{cell}</td></tr>"

    def irow(sec, label):
        bullets = ix["sections"].get(sec, []) if ix else []
        if not bullets:
            return None
        return (f"    <tr><td>{label}</td><td>"
                f"{intel_bullets_html(bullets)}</td></tr>")

    def desc_row():
        if not ix or not ix["description"]:
            return None
        cell = S.esc(ix["description"])
        for c in ix["desc_cites"]:
            cell += (f'<div class="vintage-inline">Source: '
                     f"{S.esc(c)}</div>")
        return f"    <tr><td>Description</td><td>{cell}</td></tr>"

    # Ownership: prefer intel detail, fall back to the projects.yaml note.
    own_row = irow("Operator and ownership", "Ownership / JV split")
    if own_row is None:
        own_row = row("Ownership / JV split", S.esc(own) if own else None,
                      "Heavy Reading project roster" if own else None)

    rows = [
        row("Operator", S.esc(p["operator"])),
        row("Type", TYPE_LABEL.get(t, t)),
        row("Ticker", S.esc(p.get("ticker")) if p.get("ticker") else None),
        row("ST53 scheme", S.esc(p["st53_scheme"]) if p.get("st53_scheme")
            else "not in ST53"),
    ]
    for r in (desc_row(),
              irow("Regulatory status", "Status"),
              irow("Capacity", "Nameplate capacity"),
              row("Start-up / phases", None),
              own_row,
              row("Product and disposition", S.esc(prod) if prod else None,
                  prod_src),
              irow("Technology and process", "Process / technology"),
              row("Froth treatment", S.esc(ft), ft_src),
              row("Interconnects", S.esc(ic) if ic else None, ic_src),
              irow("Growth and expansions", "Growth / expansions"),
              irow("Maintenance", "Company-disclosed maintenance"),
              irow("Operating costs", "Operating costs")):
        if r:
            rows.append(r)
    if p.get("note") and not own:
        rows.append(row("Note", S.esc(S.anon_text(p["note"]))))
    return ('  <div class="tblwrap"><table class="data facts">\n' + "\n".join(rows) +
            '\n  </table></div>\n  <p class="tblnote">Blank "not tracked" cells are '
            'facts not present in the public data used here. They are labeled, '
            'never estimated. Filing-sourced facts carry their document name '
            'and date; where sources disclose multiple bases for one figure, '
            "all are shown.</p>")


def esc_cell(v):
    return v  # callers pre-escape


# ----------------------------------------------------------------------------
# Production: live SVG chart + compact tables
# ----------------------------------------------------------------------------

def production_section(p, rows, data, R, fwd):
    out = ["  <h2>Production</h2>"]
    if not rows:
        if p["id"] == "meg_christina_lake":
            why = ("Production is tracked at the Christina Lake scheme level, "
                   "shared with Cenovus Christina Lake since the Nov 13, 2025 "
                   "acquisition. No separate "
                   "MEG-only leaf exists in AER ST53, so no separate series "
                   "is shown here. Figures are not split or estimated. "
                   'See the <a href="cve_christina_lake.html">Christina Lake '
                   "(Cenovus) profile</a> for the scheme series.")
        elif p["id"] == "cnooc_long_lake_upgrader":
            why = ("No ST39 upgrader leaf is mapped in the model for Long Lake, "
                   "and no proj_ SAGD leaf was built for the Long Lake scheme. "
                   "Figures are not estimated.")
        else:
            why = "No per-project production series in the model. Figures are not estimated."
        out.append(f'  <p class="nullnote">{why}</p>')
        return "\n".join(out)

    rids = [r["id"] for r in rows]
    stats = []
    la_m, la_v = latest_actual(R, rids[0], data["act_months"])
    if la_m:
        stats.append((S.f1(la_v) + " kb/d",
                      f"latest actual, {S.mname(la_m)} ({S.esc(rows[0]['label'])})"))
    a = favg(R, rids[0], data["fc_months"])
    stats.append((S.f1(a) + " kb/d" if a is not None else "n/a",
                  "12-month forecast average, Oct 2026 to Sep 2027"))
    out.append('  <div class="statgrid">')
    for v, lab in stats:
        out.append(f'    <div class="stat"><div class="v">{v}</div>'
                   f'<div class="l">{lab}</div></div>')
    out.append("  </div>")

    months = data["act_months"] + data["gap_months"] + data["fc_months"]
    b_ = bands(data)
    # pattern-indicated months: shaded differently, never in model math
    ind_ms = set()
    for rec in fwd.get(p["id"], []):
        if rec.get("validation") != "pattern-indicated":
            continue
        prec = rec.get("window_precision", "")
        s = rec.get("window_start", "")[:7]
        if prec == "quarter" and len(s) == 7:
            y, m0 = int(s[:4]), int(s[5:7])
            for k in range(3):
                ind_ms.add(f"{y}-{m0 + k:02d}")
        elif prec != "year" and len(s) == 7:
            ind_ms.add(s)
    legend = S.band_legend()
    if ind_ms:
        legend = legend + [("Pattern-indicated (not in model math)",
                            "var(--ch-pat)")]
    for r in rows:
        rid = r["id"]
        maint_ms = {m for m in months
                    if data["leaf_maint"].get(rid, {}).get(m) not in (None, 0)}
        svg = S.svg_bars(months, r["values"], b_, maint_ms,
                         title=f'{r["label"]} monthly production',
                         ind_months=ind_ms)
        cap = (S.vintage_caption(
            "AER ST53 actuals through 2026-07 (ST39 through 2026-05), pulled "
            "2026-09-22; Aug-Sep 2026 nowcast estimated, built 2026-09-23; "
            "forecast built 2026-09-22. Solid orange shading marks months "
            "with modeled maintenance on this series."
            + (" Dashed shading marks pattern-indicated months (indicator "
               "only, no volume in the model math)." if ind_ms else "")) +
            f' <b>Series:</b> {S.esc(r["label"])}.')
        out.append(S.chart_figure(svg, cap, legend))

    # compact tables: last 6 actuals, first 6 forecast
    def mini(ms, caption):
        th = "".join(f"<th>{S.mname(m)}</th>" for m in ms)
        trs = []
        for r in rows:
            tds = "".join(
                f'<td class="num">{S.f1(r["values"].get(m))}</td>' for m in ms)
            trs.append(f"    <tr><td>{S.esc(r['label'])}</td>{tds}</tr>")
        return (f'  <div class="tblwrap"><table class="data">\n'
                f'    <caption style="text-align:left;font-weight:700;'
                f'padding:6px 0;">{caption} (kb/d)</caption>\n'
                f'    <tr><th>Series</th>{th}</tr>\n' +
                "\n".join(trs) + "\n  </table></div>")

    out.append(mini(data["act_months"][-6:], "Latest actuals"))
    out.append(mini(data["fc_months"][:6], "First forecast months"))
    out.append('  <p class="tblnote">Full 26-month table with drill-down lives '
               'in the <a href="../st3-dashboard.html">trading dashboard</a>. '
               "Blank cells are months AER has not published yet, not zeros.</p>")
    for r in rows:
        why = r.get("detail", {}).get("why", "")
        if why:
            out.append(f'  <p class="src"><b>How to read {S.esc(r["label"])}:</b> '
                       f'{S.esc(why)}</p>')
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Maintenance: model events + per-asset forward calendar
# ----------------------------------------------------------------------------

VAL_LABEL = {"public-confirmed": "Public confirmed",
             "guidance-sourced": "Guidance sourced",
             "cadence-modeled": "Cadence-modeled (CADENCE-MODELED, editorially approved)",
             "pattern-indicated": "Pattern indicated (indicator only)"}
KIND_LABEL = {"turnaround": "Turnaround",
              "none_found": "No turnaround in window (stated)",
              "forward_schedule": "Scheduled (future window)"}


def timing_str(r):
    s, e = r.get("window_start", ""), r.get("window_end", "")
    prec = r.get("window_precision", "")
    if prec == "year":
        return f"{s[:4]} (year precision)"
    if prec == "quarter":
        return f"{S.mname(s[:7])} to {S.mname(e[:7])} (quarter precision)"
    if s[:7] == e[:7]:
        return S.mname(s[:7])
    return f"{S.mname(s[:7])} to {S.mname(e[:7])}"


def maintenance_section(p, rids, data, fwd, overlap):
    out = ["  <h2>Maintenance</h2>"]
    items = []
    for rid in rids:
        series = data["leaf_maint"].get(rid, {})
        if series:
            info = B.LEAF_MAINT_INFO.get(rid, {})
            event = info.get("event", rid)
            src = S.anon_text(info.get("source", ""))
            months = ", ".join(f"{S.mname(m)} (-{abs(v):.1f})"
                               for m, v in sorted(series.items()))
            items.append((event, months, src))
    if items:
        out.append("  <h3>In the model math</h3>")
        out.append('  <ul class="ev">')
        for event, months, src in items:
            out.append(f"    <li><b>{S.esc(event)}</b><br>{S.esc(months)} kb/d"
                       + (f'<br><span class="src">Source: {S.esc(src)}</span>'
                          if src else "") + "</li>")
        out.append("  </ul>")
    else:
        out.append('  <p class="nullnote">No maintenance events in the current '
                   "model math for this project.</p>")

    recs = sorted(fwd.get(p["id"], []), key=lambda r: r.get("window_start", ""))
    ovs = overlap.get(p["id"], [])
    if recs or ovs:
        out.append("  <h3>Forward calendar (Oct 2026 to Dec 2027)</h3>")
        out.append('  <div class="tblwrap"><table class="data">')
        out.append("    <tr><th>Timing</th><th>Event</th>"
                   '<th class="num">Impact kb/d</th><th>Standing</th><th>Source</th></tr>')
        for o in ovs:
            out.append(f"    <tr><td>{S.esc(o['event_id'])}</td>"
                       f"<td>{S.esc(S.anon_text(o['note']))}</td>"
                       f'<td class="num">modeled</td>'
                       f"<td>In model math</td><td>See note</td></tr>")
        for r in recs:
            imp = r.get("impact_kbd")
            imp_s = (f"{imp:+.1f}" if imp is not None
                     else '<span class="nullnote">not stated (null, never '
                          'estimated)</span>')
            src = (f"{S.esc(r.get('source_company', ''))}, "
                   f"{S.esc(r.get('source_document', ''))} "
                   f"({S.esc(r.get('source_date', ''))})")
            out.append(f"    <tr><td>{S.esc(timing_str(r))}</td>"
                       f"<td>{S.esc(KIND_LABEL.get(r.get('kind'), r.get('kind', '')))}</td>"
                       f'<td class="num">{imp_s}</td>'
                       f"<td>{S.esc(VAL_LABEL.get(r.get('validation'), r.get('validation', '')))}</td>"
                       f"<td>{src}</td></tr>")
        out.append("  </table></div>")
        out.append('  <p class="tblnote">CADENCE-MODELED entries are '
                   "editorially approved estimates in the model math, labeled as "
                   "such everywhere; they are never presented as "
                   "company-confirmed. Math "
                   "otherwise requires public-confirmed guidance.</p>")
    else:
        out.append('  <p class="nullnote">No forward-calendar entries for this '
                   "project in the public maintenance calendar.</p>")
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Outlook + market relevance + related + sources
# ----------------------------------------------------------------------------

def outlook_section(p, rows, R):
    out = ["  <h2>Outlook</h2>"]
    whys = [r.get("detail", {}).get("why", "") for r in rows]
    whys = [w for w in whys if w]
    if whys:
        for w in whys:
            out.append(f'  <p class="src"><b>Named assumptions:</b> {S.esc(w)}</p>')
        out.append('  <p class="src"><b>Confirmation status:</b> model '
                   "forecast; maintenance impacts enter the math only from "
                   "public-confirmed guidance.</p>")
    else:
        out.append('  <p class="nullnote">No project-specific outlook '
                   "assumptions are recorded for this asset. The forecast is "
                   "the seasonal baseline (trailing-12-month mean times a "
                   "seasonal factor); nothing beyond that is assumed.</p>")
    return "\n".join(out)


def market_relevance(p, rids, R, data):
    """One line on what this asset means for the tradable balance.

    Derived from the model's own numbers only."""
    t, pid, name = p["type"], p["id"], p["name"]
    fc = data["fc_months"]
    out = ["  <h2>Market relevance</h2>"]
    line = None
    if rids and t in ("sagd", "css"):
        a = favg(R, rids[0], fc)
        line = (f"In-situ bitumen has flexible disposition (dilbit to market "
                f"or upgrader feed). In the model, {name} output is unchanged "
                f"by upgrader outages and any upgrader-bound share is assumed "
                f"diverted to dilbit, so its {S.f1(a)} kb/d 12-month forecast "
                f"average is a steady contributor to marketable dilbit across "
                f"the tradable window.")
    elif pid in ("imo_kearl", "su_fort_hills"):
        grade = "Kearl Lake Dilbit (KDB)" if pid == "imo_kearl" else "Fort Hills Dilbit (FRB)"
        a = favg(R, rids[0], fc) if rids else None
        line = (f"PFT mine selling dilbit directly ({grade}): {S.f1(a)} kb/d "
                f"12-month forecast average of marketable dilbit. PFT mines "
                f"are the model's swing supplier")
        if pid == "su_fort_hills":
            line += (" (Fort Hills held output flat in Q1 2026 while "
                     "redirecting 66.9 kb/d from dilbit sales to Suncor Base "
                     "upgrader feed, per Heavy Reading maintenance records)")
        line += "."
    elif t == "integrated" and rids:
        sco_r = next((r for r in rids if r.startswith("scoplant_")), None)
        y = favg(R, sco_r, fc) if sco_r else None
        evts = []
        for rid in rids:
            s = data["leaf_maint"].get(rid, {})
            for m in fc:
                if s.get(m) not in (None, 0):
                    evts.append((m, s[m]))
        if pid == "cnq_horizon":
            line = (f"Horizon SCO averages {S.f1(y)} kb/d over the forecast. "
                    f"Horizon has no documented third-party interconnect, so "
                    f"the model dials mine and upgrader back together during "
                    f"turnarounds: SCO supply tightens one-for-one with the "
                    f"modeled outage.")
        else:
            dil = R.get("grade_dilbit", {}).get("values", {})
            evt_ms = ["2026-08", "2026-09", "2026-10"]
            da = [dil.get(m) for m in evt_ms if dil.get(m) is not None]
            db = [dil.get(m) for m in fc if dil.get(m) is not None]
            lift = ""
            if da and db and sum(da) / len(da) > sum(db) / len(db):
                lift = (f" During the Aug-Oct 2026 Coker 8-2 outage window the "
                        f"model shows marketable dilbit averaging "
                        f"{S.f1(sum(da) / len(da))} kb/d versus "
                        f"{S.f1(sum(db) / len(db))} kb/d across the "
                        f"Nov 2026-Sep 2027 tradable window: upgrader outages "
                        f"here can lift marketable dilbit even as SCO falls.")
            line = (f"{name} SCO averages {S.f1(y)} kb/d over the forecast. "
                    f"At interconnected Suncor/Syncrude sites the interconnect "
                    f"acts as a relief valve during unplanned upgrader outages "
                    f"(Q1 2026 precedent), and flexible SAGD/PFT barrels tilt "
                    f"toward dilbit; planned upgrader turnarounds instead "
                    f"coordinate the mine to reduced demand, with no redirect "
                    f"modeled (Coker 8-2 ruling, 2026-09-24)." + lift)
        if evts:
            m, v = max(evts, key=lambda x: abs(x[1]))
            line += (f" Modeled maintenance peaks at {S.mname(m)} "
                     f"(-{abs(v):.1f} kb/d).")
    if line:
        out.append(f"  <p>{line}</p>")
        out.append('  <p class="src"><b>Basis:</b> model-derived from the '
                   "dashboard series above; no external view is added.</p>")
    else:
        out.append('  <p class="nullnote">No market-relevance line: this asset '
                   "has no production leaf in the model, so nothing can be "
                   "derived.</p>")
    return "\n".join(out)


def related_section(p, weekly):
    out = ["  <h2>Related weekly notes</h2>"]
    kws = set()
    pre = p["id"].split("_")[0]
    op_kw = {"su": "suncor", "cnq": "cnrl", "cve": "cenovus", "imo": "imperial",
             "ath": "athabasca", "cop": "conocophillips", "scr": "strathcona",
             "gfr": "greenfire", "connacher": "greenfire", "harvest": "harvest",
             "ipc": "ipc", "petrochina": "petrochina"}
    if pre in op_kw:
        kws.add(op_kw[pre])
    if "syncrude" in p["id"]:
        kws.add("syncrude")
    if "cnooc" in p["id"]:
        kws.add("cnooc")
    stop = {"river", "lake", "creek", "hills", "plant", "north", "black",
            "great", "peace", "divide", "gold", "expansion"}
    for w in p["name"].lower().split():
        if len(w) > 4 and w not in stop:
            kws.add(w)
    kws.add(p["name"].lower())
    hits = [w for w in weekly
            if any(k in w["text"] for k in kws)]
    if hits:
        out.append('  <ul class="ev">')
        for w in hits:
            out.append(f'    <li><a href="{w["href"]}">WCSB Weekly, '
                       f'{S.esc(w["date"])}</a> '
                       f'<span class="vintage-inline">(keyword match)</span></li>')
        out.append("  </ul>")
    else:
        out.append('  <p class="nullnote">No weekly edition to date mentions '
                   "this asset by name.</p>")
    return "\n".join(out)


def sources_section(rids, R, updated):
    out = ["  <h2>Sources</h2>"]
    for rid in rids:
        d = R[rid].get("detail", {})
        out.append(f'  <p class="src"><b>{S.esc(R[rid]["label"])}</b><br>'
                   f'Source: {S.esc(d.get("source", "n/a"))}<br>'
                   f'Vintage: {S.esc(d.get("vintage", "n/a"))}<br>'
                   f'Method: {S.esc(d.get("method", "n/a"))}</p>')
    out.append("  <h3>Full citation block</h3>")
    out.append(S.sources_table())
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Page assembly
# ----------------------------------------------------------------------------

SOURCE_LINE = ("AER ST3/ST39/ST53 via the WCSB S&amp;D model; forward "
               "maintenance calendar (compiled 2026-09-22)")


def profile_page(p, rows, data, R, fwd, overlap, weekly, ix):
    rids = [r["id"] for r in rows]
    badge, bcls = live_status(p, rids, R, data, fwd)
    badge_html = (f'<span class="chip {bcls}">{S.esc(badge)}</span>'
                  if badge else "")
    body = [facts_table(p, ix),
            production_section(p, rows, data, R, fwd),
            maintenance_section(p, rids, data, fwd, overlap),
            outlook_section(p, rows, R),
            market_relevance(p, rids, R, data),
            related_section(p, weekly)]
    if rows:
        body.append(sources_section(rids, R, data["built"]))
    else:
        body.append("  <h2>Sources</h2>\n  <h3>Full citation block</h3>\n"
                    + S.sources_table())
    crumb = ('<a href="../index.html">Home</a> / '
             '<a href="../st3-dashboard.html">Supply</a> / '
             '<a href="index.html">Projects</a> / ' + S.esc(p["name"]))
    sub = (f'{S.esc(p["operator"])}<br>{badge_html}'
           f'<span class="chip">{S.esc(TYPE_LABEL.get(p["type"], p["type"]))}</span>'
           + (f'<span class="chip">{S.esc(p["ticker"])}</span>'
              if p.get("ticker") else ""))
    updated = S.edition_date(data.get("built", "2026-09-23"))
    desc = (f'{p["name"]}: {p["operator"]} '
            f'{TYPE_LABEL.get(p["type"], p["type"])} project profile. '
            f'Production history, forecast, maintenance calendar, and capacity, '
            f'from the WCSB S&D model.')
    return S.page_shell(f'{p["name"]} | Projects', S.esc(p["name"]), sub,
                        crumb, "\n".join(body), "projects", 1, updated,
                        SOURCE_LINE, description=desc,
                        url_path=f'projects/{p["id"]}.html')


def short_status(p, rids, R, data, fwd):
    badge, _ = live_status(p, rids, R, data, fwd)
    return badge


def production_peak_chart(roster, data, R):
    """Chart D: latest actual production vs trailing-12m demonstrated peak
    for the 12 largest projects. The demonstrated peak stands in for
    nameplate where the repo carries no structured announced-capacity series;
    nothing is estimated."""
    import csv
    act = data["act_months"]
    last = act[-1]
    items = []
    for p in roster:
        rids = project_row_ids(p["id"], set(R))
        if not rids:
            continue
        vals = R[rids[0]]["values"]
        lv = vals.get(last)
        if lv is None:
            continue
        peak = max((vals.get(m) or 0) for m in act)
        items.append((p["name"], p["operator"], lv, peak))
    items.sort(key=lambda t: t[2], reverse=True)
    top = items[:12]
    if not top:
        return ""
    cats = [t[0] for t in top]
    series = [(f"Latest actual ({S.mname(last)})", [t[2] for t in top], "ink"),
              ("Trailing-12m peak", [t[3] for t in top], "sand")]
    near = sum(1 for t in top if t[2] >= 0.95 * t[3])
    svg = S.svg_grouped(cats, series)
    title = (f"{near} of the 12 largest projects are producing within 5% of "
             f"their trailing-12-month peak")
    vintage = (f"AER ST3/ST53 actuals through {S.mname(last)}, "
               f"pulled 2026-09-22")
    caption = (f"Latest actual vs the highest month in the trailing 12, the "
               f"demonstrated peak. Announced nameplates live on the project "
               f"profiles where disclosed; where a project runs above its "
               f"announced figure the profile says so. <b>Vintage:</b> "
               f"{vintage}.")
    csv_path = SITE / "data" / "charts" / "project-production-vs-peak.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["project", "operator", "latest_month", "latest_kbd",
                    "trailing_12m_peak_kbd", "vintage"])
        for name, op, lv, peak in top:
            w.writerow([name, op, last, f"{lv:.1f}", f"{peak:.1f}", vintage])
    html = S.chart_figure(svg, caption,
                          [(f"Latest actual ({S.mname(last)})", "#1e1b16"),
                           ("Trailing-12m peak", "#a89c86")],
                          title=title)
    html += S.csv_link("../data/charts/project-production-vs-peak.csv",
                       f"CSV · {vintage}")
    return html


def index_page(roster, data, R, fwd, ixmap):
    row_ids = set(R)
    out = ['  <p class="sub">Every producing oil-sands project in the model, '
           'grouped by extraction method and operator. Live status is computed '
           "from the model's own maintenance math and forward calendar. "
           "Capacity figures are company or regulatory disclosures carried "
           "with their source; where sources disclose multiple capacity "
           "bases, all are shown on the profile. 'Not disclosed' means the "
           "reviewed public sources do not state a figure; nothing is "
           "estimated.</p>"]
    out.append(production_peak_chart(roster, data, R))
    for gkey, glabel, types in METHOD_GROUPS:
        members = [p for p in roster if p["type"] in types]
        if not members:
            continue
        out.append(f'  <h2 id="{gkey}">{glabel} ({len(members)})</h2>')
        # group by operator, stable order
        ops = []
        for p in members:
            if p["operator"] not in ops:
                ops.append(p["operator"])
        for op in ops:
            grp = [p for p in members if p["operator"] == op]
            out.append(f"  <h3>{S.esc(op)} ({len(grp)})</h3>")
            out.append('  <div class="tblwrap"><table class="data">')
            out.append("    <tr><th>Project</th><th>Live status</th>"
                       "<th>Capacity</th>"
                       '<th class="num">Latest actual kb/d</th>'
                       '<th class="num">12-mo fcst avg kb/d</th></tr>')
            for p in grp:
                rids = project_row_ids(p["id"], row_ids)
                rows = [R[r] for r in rids]
                la = favg_none = None
                if rows:
                    lm, lv = latest_actual(R, rids[0], data["act_months"])
                    la = (f"{S.f1(lv)} ({S.mname(lm)})" if lm
                          else '<span class="nullnote">n/a</span>')
                    fa = favg(R, rids[0], data["fc_months"])
                    favg_none = (S.f1(fa) if fa is not None
                                 else '<span class="nullnote">n/a</span>')
                else:
                    la = '<span class="nullnote">no leaf</span>'
                    favg_none = '<span class="nullnote">no leaf</span>'
                st = S.esc(short_status(p, rids, R, data, fwd))
                cap_short, cap_null = IX.capacity_short(ixmap.get(p["id"]))
                if cap_null:
                    cap = ('<span class="nullnote">'
                           f'{S.esc(cap_short) if cap_short else "not tracked"}'
                           "</span>")
                else:
                    cap = S.esc(cap_short)
                out.append(f'    <tr><td><a href="{p["id"]}.html">'
                           f'{S.esc(p["name"])}</a></td>'
                           f"<td>{st}</td>"
                           f"<td>{cap}</td>"
                           f'<td class="num">{la}</td>'
                           f'<td class="num">{favg_none}</td></tr>')
            out.append("  </table></div>")
    crumb = ('<a href="../index.html">Home</a> / '
             '<a href="../supply/index.html">Supply</a> / Projects')
    sub = ("Project profiles fed by the WCSB S&amp;D model leaves: live "
           "production charts, maintenance calendars, and market-relevance "
           "lines. All public information.")
    updated = S.edition_date(data.get("built", "2026-09-23"))
    return S.page_shell("Projects", "Projects", sub, crumb, "\n".join(out),
                        "projects", 1, updated, SOURCE_LINE,
                        description="Every producing oil-sands project in the "
                                    "WCSB S&D model, grouped by extraction "
                                    "method and operator, with live production "
                                    "charts and maintenance calendars.",
                        url_path="projects/index.html")


def main():
    data, roster, fwd, overlap, weekly = load_inputs()
    R = {r["id"]: r for r in data["rows"]}
    row_ids = set(R)
    ixmap = {p["id"]: S.anon_data(IX.load(p["id"])) for p in roster}
    PROJDIR.mkdir(parents=True, exist_ok=True)

    (PROJDIR / "index.html").write_text(index_page(roster, data, R, fwd, ixmap))
    n = 0
    for p in roster:
        rids = project_row_ids(p["id"], row_ids)
        rows = [R[r] for r in rids]
        (PROJDIR / f'{p["id"]}.html').write_text(
            profile_page(p, rows, data, R, fwd, overlap, weekly,
                         ixmap.get(p["id"])))
        n += 1
    n_intel = sum(1 for v in ixmap.values() if v)
    print(f"wrote {PROJDIR / 'index.html'} + {n} project profiles "
          f"({n_intel} with filing intel)")


if __name__ == "__main__":
    main()
