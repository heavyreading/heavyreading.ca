"""Build the Supply hub page: the flagship supply view.

One page: the latest Executive Call, the KPI strip, the stacked egress
chart (capacity vs throughput, TMX in-service marked), the supply-by-type
chart (grouped bars by grade with a total tradable supply line), the
implied condensate import demand chart, and the forward maintenance
outlook. Every chart is built from real repo data only, carries a
takeaway title plus a vintage caption, and ships a CSV download of
exactly the chart data plus its vintage.

Event annotations follow the three-tier rule: structural events and the
maintenance dataset's own events are marked with their source; nothing
asserts that an event caused a visible move.
"""

import csv
import json
import statistics
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent  # .../hidden_files/woodmack_storage

import textutil as TU
import shared as S
import build_st3_dashboard as B

SOURCE_LINE = ("AER ST3/ST39/ST53 via the WCSB S&amp;D model; company guidance "
               "via the forward maintenance calendar (revised 2026-09-23)")

EGRESS_CSV = BASE / "egress_monthly_public.csv"
DASH_JSON = BASE / "st3_dashboard.json"
CHART_DIR = SITE / "data" / "charts"

EGRESS_VINTAGE = "CER open data (throughput + capacity), pulled 2026-09-22"
MODEL_VINTAGE = ("AER ST3 actuals through 2026-07 (pulled 2026-09-22); "
                 "Aug-Sep 2026 nowcast estimated; forecast model build 2026-09-22")


def _write_csv(path, fieldnames, rows, vintage):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames + ["vintage"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "vintage": vintage})


# ----------------------------------------------------------------------------
# Chart A: stacked egress capacity by system + total throughput line.
# ----------------------------------------------------------------------------

def build_egress():
    rows = list(csv.DictReader(EGRESS_CSV.open()))
    months = sorted({r["month"] for r in rows})
    caps, thru = {}, {}
    for r in rows:
        if r["route"] == "total_all_routes":
            thru[r["month"]] = float(r["throughput_kbd"])
        else:
            caps.setdefault(r["route"], {})[r["month"]] = float(r["capacity_kbd"])
    order = [("enbridge_mainline", "Enbridge", "ink2", "#f6f2e9"),
             ("keystone", "Keystone", "steel", "#f6f2e9"),
             ("trans_mountain", "Trans Mountain", "g3", "#1e1b16")]
    stacks = [(lab, caps[r], col, tc) for r, lab, col, tc in order]
    last = months[-1]
    tot_cap = sum(caps[r][last] for r, _, _, _ in order)
    tot_thr = thru[last]
    spare = tot_cap - tot_thr
    util = tot_thr / tot_cap * 100
    svg = S.svg_stack_line(
        months, stacks,
        line=(thru, "acc"),
        events=[("2024-05", "TMX in service")],
        line_end_label=f"Throughput · {tot_thr:,.0f} kb/d")
    title = (f"Egress is running {util:.0f}% full: "
             f"{spare:,.0f} kb/d of spare capacity in {B._mname(last)}")
    caption = (f"Stacked available capacity by pipeline system against total "
               f"throughput. Enbridge Mainline, Keystone, and Trans Mountain "
               f"only: Express and rail capacity series are not in the CER "
               f"dataset, so they are excluded rather than estimated. "
               f"<b>Vintage:</b> {EGRESS_VINTAGE}.")
    csv_rows = []
    for m in months:
        tc = sum(caps[r][m] for r, _, _, _ in order)
        tt = thru[m]
        csv_rows.append({
            "month": m,
            "enbridge_mainline_capacity_kbd": f"{caps['enbridge_mainline'][m]:.1f}",
            "keystone_capacity_kbd": f"{caps['keystone'][m]:.1f}",
            "trans_mountain_capacity_kbd": f"{caps['trans_mountain'][m]:.1f}",
            "total_capacity_kbd": f"{tc:.1f}",
            "total_throughput_kbd": f"{tt:.1f}",
            "utilization_pct": f"{tt / tc * 100:.1f}",
        })
    _write_csv(CHART_DIR / "egress-capacity-throughput.csv",
               ["month", "enbridge_mainline_capacity_kbd",
                "keystone_capacity_kbd", "trans_mountain_capacity_kbd",
                "total_capacity_kbd", "total_throughput_kbd",
                "utilization_pct"], csv_rows, EGRESS_VINTAGE)
    legend = [(f"{lab} capacity", col) for _, lab, col, _ in order
              ] + [("Total throughput", "var(--ch-acc)")]
    html = S.chart_figure(svg, caption, legend, title=title)
    html += S.csv_link("../data/charts/egress-capacity-throughput.csv",
                       f"CSV · {EGRESS_VINTAGE}")
    return html


# ----------------------------------------------------------------------------
# Inline renderer: grouped vertical bars (side by side per period, shared
# zero baseline) with an overlaid total line. shared.svg_grouped is a
# horizontal-bar renderer with no line-overlay support, so the grouped
# rendering lives here, next to its only use. Palette keys resolve
# through shared.PAL; 1060px wide so the figure content never scrolls
# on desktop, while phones get horizontal scroll via the wrapper.
# ----------------------------------------------------------------------------

_SCROLL_MINW = 1060


def _end_label_clamped(parts, x, y, text, color):
    """Line end-label that never spills past the SVG right edge: drawn at
    x + 8 when it fits, otherwise anchored end just inside the viewBox."""
    w = S._est_text_w(text, 12.5) * 1.22
    if x + 8 + w > _SCROLL_MINW - 4:
        parts.append(f'<text x="{_SCROLL_MINW - 4}" y="{y:.1f}" '
                     f'text-anchor="end" class="elab" '
                     f'fill="{color}">{S.esc(text)}</text>')
    else:
        parts.append(f'<text x="{x + 8:.1f}" y="{y:.1f}" '
                     f'text-anchor="start" class="elab" '
                     f'fill="{color}">{S.esc(text)}</text>')


def _scroll(svg, minw=_SCROLL_MINW):
    return (f'<div class="hscroll" style="overflow-x:auto;'
            f'-webkit-overflow-scrolling:touch">'
            f'<div style="min-width:{minw}px">{svg}</div></div>')


def _svg_grouped_line(months, series, line, line_label, bands=None, unit="kb/d"):
    W = _SCROLL_MINW
    L, R, T, Bm = 56, 110, 26, 52
    n = len(months)
    plot_w = W - L - R
    cw = plot_w / max(n, 1)
    nb = len(series)
    bw = min(cw * 0.78 / max(nb, 1) * 0.86, 24)
    vals = [[v.get(m) or 0 for _, v, _ in series] for m in months]
    lval = [line[0].get(m) for m in months]
    vmax = max([max(vv) for vv in vals] + [v or 0 for v in lval])
    top = S._nice_top(vmax)
    HH = 300
    H = T + HH + Bm

    def ypix(v):
        return T + ((top - v) / top) * HH

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img">', S._SVG2,
             S._bg(W, H)]
    if bands:
        for b, run in S._band_runs(months, bands):
            fill = S._BAND_FILL.get(b)
            if not fill:
                continue
            i0 = months.index(run[0])
            parts.append(f'<rect x="{L + i0 * cw:.1f}" y="{T}" '
                         f'width="{len(run) * cw:.1f}" height="{HH}" '
                         f'style="fill:{fill}"/>')
    S._cgrid(parts, L, R, W, T, H, Bm, top)
    for i, m in enumerate(months):
        x0 = L + i * cw + (cw - nb * bw) / 2
        for j, (lab, v, col) in enumerate(series):
            val = vals[i][j]
            if val <= 0:
                continue
            x = x0 + j * bw
            y1, y2 = ypix(0), ypix(val)
            parts.append(
                f'<rect x="{x:.1f}" y="{y2:.1f}" width="{bw - 1.5:.1f}" '
                f'height="{max(y1 - y2, 1):.1f}" rx="2" style="fill:{S.PAL[col]}">'
                f'<title>{S._xlab(m)} {S.esc(lab)}: {S.f1(val)} {unit}</title></rect>')
    pts = [(L + i * cw + cw / 2, ypix(v)) for i, v in enumerate(lval)
           if v is not None]
    if pts:
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="{S.PAL[line[1]]}" '
                     f'stroke-width="2.5"/>')
        lx, ly = pts[-1]
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" '
                     f'fill="{S.PAL[line[1]]}"/>')
        if line_label:
            _end_label_clamped(parts, lx, ly - 9, line_label, S.PAL[line[1]])
    S._cx_labels(parts, months, L, cw, n, H)
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_multiline(months, lines, bands=None, unit="kb/d"):
    """Multiple line series on one axis; a series may end early (values
    dicts carry only the months they cover). lines: (label, values, palkey,
    dash). End labels are de-collided vertically."""
    W = _SCROLL_MINW
    L, R, T, Bm = 56, 150, 26, 52
    n = len(months)
    plot_w = W - L - R
    cw = plot_w / max(n, 1)
    vmax = 0
    pts_all = []
    for _lab, vals, _col, _dash in lines:
        pts = [(i, vals.get(m)) for i, m in enumerate(months)
               if vals.get(m) is not None]
        pts_all.append(pts)
        vmax = max(vmax, max((v for _, v in pts), default=0))
    top = S._nice_top(vmax)
    HH = 300
    H = T + HH + Bm

    def ypix(v):
        return T + ((top - v) / top) * HH

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img">', S._SVG2,
             S._bg(W, H)]
    if bands:
        for b, run in S._band_runs(months, bands):
            fill = S._BAND_FILL.get(b)
            if not fill:
                continue
            i0 = months.index(run[0])
            parts.append(f'<rect x="{L + i0 * cw:.1f}" y="{T}" '
                         f'width="{len(run) * cw:.1f}" height="{HH}" '
                         f'style="fill:{fill}"/>')
    S._cgrid(parts, L, R, W, T, H, Bm, top)
    ends = []
    for (lab, _v, col, dash), pts in zip(lines, pts_all):
        if not pts:
            continue
        segs, cur = [], []
        for i, v in pts:
            if cur and i != cur[-1][0] + 1:
                segs.append(cur)
                cur = []
            cur.append((i, v))
        if cur:
            segs.append(cur)
        for seg in segs:
            d = "M" + " L".join(f"{L + i * cw + cw / 2:.1f},{ypix(v):.1f}"
                                for i, v in seg)
            da = f' stroke-dasharray="{dash}"' if dash else ""
            parts.append(f'<path d="{d}" fill="none" stroke="{S.PAL[col]}" '
                         f'stroke-width="2.5"{da}/>')
        i_last, v_last = pts[-1]
        ends.append((ypix(v_last), L + i_last * cw + cw / 2, v_last, lab, col))
    ends.sort()
    placed = []
    for y, x, v, lab, col in ends:
        y2 = y
        for py in placed:
            if abs(y2 - py) < 17:
                y2 = py + 17
        # De-collision pushes labels down; clamp so a crowded stack never
        # runs past the bottom of the viewBox.
        y2 = min(y2, H - 40)
        placed.append(y2)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" '
                     f'fill="{S.PAL[col]}"/>')
        _end_label_clamped(parts, x, y2 + 4, f"{lab} {S.f1(v)}", S.PAL[col])
    S._cx_labels(parts, months, L, cw, n, H)
    parts.append("</svg>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------
# Chart B: tradable supply by crude type (grouped bars + total line).
# ----------------------------------------------------------------------------

def build_supply_type(data):
    rows = {r["id"]: r for r in data["rows"]}
    months = data["act_months"] + data["gap_months"] + data["fc_months"]
    bands = ({m: "act" for m in data["act_months"]} |
             {m: "nc" for m in data["gap_months"]} |
             {m: "fc" for m in data["fc_months"]})
    g = lambda rid, m: rows[rid]["values"].get(m) or 0
    # Tradeable buckets, verified to tie exactly to Total crude supply:
    # grade_total = grade_sco + grade_dilbit + light + medium + heavy +
    #               ultra-heavy + condensate_production, every month.
    # Condensate (~100 kb/d, mostly diluent supply) is folded into Light and
    # labeled as such; Medium is the ST3 density grade (sulfur not separated).
    heavy = {m: g("grade_dilbit", m) + g("crude_heavy", m) + g("crude_ultra_heavy", m)
             for m in months}
    light = {m: g("crude_light", m) + g("condensate_production", m) for m in months}
    medium = {m: g("crude_medium", m) for m in months}
    syn = {m: g("grade_sco", m) for m in months}
    total = {m: heavy[m] + light[m] + medium[m] + syn[m] for m in months}
    for m in months:  # tie-out guard: never ship a total that doesn't foot
        assert abs(total[m] - (rows["grade_total"]["values"].get(m) or 0)) < 0.2, m
    series = [("Heavy", heavy, "ink2"),
              ("Synthetic", syn, "g1"),
              ("Light", light, "g2"),
              ("Medium", medium, "g4")]
    svg = _svg_grouped_line(
        months, series, (total, "acc"),
        line_label=f"Total · {total[months[-1]]:,.0f} kb/d",
        bands=bands)
    # Directional takeaway, computed: between the last two forecast months,
    # which grade is the biggest month-on-month add and which is the biggest
    # drag, each with its kb/d move. A grade-level number, never a share.
    m0, m1 = data["fc_months"][-2], data["fc_months"][-1]
    deltas = [(lab, s[m1] - s[m0]) for lab, s, _ in series]
    add_lab, add_d = max(deltas, key=lambda kv: kv[1])
    drag_lab, drag_d = min(deltas, key=lambda kv: kv[1])
    if add_d < 1 and drag_d > -1:
        title = f"Into {B._mname(m1)}: all four grades flat m/m"
    else:
        bits = []
        if add_d >= 1:
            bits.append(f"biggest add {add_lab} {add_d:+.0f} kb/d")
        if drag_d <= -1:
            bits.append(f"biggest drag {drag_lab} {drag_d:+.0f} kb/d")
        title = f"Into {B._mname(m1)}: " + "; ".join(bits)
    caption = (f"Western Canadian crude supply by tradeable type: total "
               f"tradable supply as a line, with Heavy, Synthetic, Light, "
               f"and Medium as grouped bars on a shared zero baseline so "
               f"period-to-period changes read directly. Heavy = marketable "
               f"bitumen (dilbit) + conventional heavy and ultra-heavy; "
               f"Synthetic = synthetic crude oil (SCO), the upgrader output; "
               f"Light includes condensate production (~100 kb/d, mostly "
               f"diluent supply). Medium is the ST3 (Alberta Energy Regulator "
               f"monthly statistics) density grade: the ST3 does not break "
               f"out sulfur, so medium sour cannot be separated from this "
               f"dataset. <b>Vintage:</b> {MODEL_VINTAGE}.")
    csv_rows = []
    for m in months:
        csv_rows.append({
            "month": m, "band": bands[m],
            "heavy_kbd": f"{heavy[m]:.1f}",
            "light_kbd": f"{light[m]:.1f}",
            "medium_kbd": f"{medium[m]:.1f}",
            "synthetic_sco_kbd": f"{syn[m]:.1f}",
        })
    _write_csv(CHART_DIR / "supply-by-type.csv",
               ["month", "band", "heavy_kbd", "light_kbd", "medium_kbd",
                "synthetic_sco_kbd"], csv_rows, MODEL_VINTAGE)
    legend = [(lab, S.PAL[col]) for lab, _, col in series
              ] + [("Total tradable supply", S.PAL["acc"])]
    html = S.chart_figure(_scroll(svg), caption, legend, title=title)
    html += S.csv_link("../data/charts/supply-by-type.csv",
                       f"CSV · {MODEL_VINTAGE}")
    return html


# ----------------------------------------------------------------------------
# Chart B2: implied C5 (condensate/diluent) import demand.
#
# Derived from the model's own series only. The blend-share assumption is
# the model's own: src/model/blend.py (implied_c5_demand_kbd) with the
# seasonal rates in overlays/desk/c5_blend_rates.csv -- each rate a
# condensate fraction of the blended barrel, applied separately to the
# blendable bitumen pool and to conventional heavy. No hardcoded 0.43
# blend factor, no fixed recovered-diluent figure.
#
#   gross_m    = bit_pool_m * rb_m/(1-rb_m) + conv_heavy_m * rh_m/(1-rh_m)
#                bit_pool_m = grade_dilbit_m (mined + in-situ + upgrader feed,
#                the upgrader feed stored negative, exactly per blend.py);
#                conv_heavy_m = crude_heavy_m + crude_ultra_heavy_m
#   local_m    = condensate_production_m
#   actual_m   = imports_condensates_m + imports_pentanes_plus_m
#   recovery_m = gross_m - local_m - actual_m, for AER actual months only
#   recovered_m = median(recovery) over those months, held for nowcast and
#                 forecast months (it is a calibrated residual, not measured)
#   implied_m  = gross_m - local_m - recovered_m, all months
#
# Where implied and actual imports diverge in history, the gap is the
# recovery residual running above or below its median -- itself a signal
# about diluent recycling or unmodeled C5 supply.
# ----------------------------------------------------------------------------

RATES_CSV = BASE.parents[1] / "overlays" / "desk" / "c5_blend_rates.csv"


def _load_blend_rates():
    rates = {}
    with open(RATES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            rates[int(row["month"])] = (float(row["bit_blend_rate"]),
                                        float(row["conv_heavy_blend_rate"]))
    return rates


def build_diluent(data):
    """PRIVATE RESEARCH ONLY. Blocked from the public page: the seasonal
    blend shares (overlays/desk/c5_blend_rates.csv) are Blaine's own
    estimates, not public data, and the CSV exposes them. Do not call from build() or
    publish the CSV until Blaine explicitly approves the assumption for
    public use."""
    rows = {r["id"]: r for r in data["rows"]}
    for rid in ("grade_dilbit", "crude_heavy", "crude_ultra_heavy",
                "condensate_production", "imports_condensates",
                "imports_pentanes_plus"):
        assert rid in rows, f"diluent chart missing row id: {rid}"
    rates = _load_blend_rates()
    assert sorted(rates) == list(range(1, 13)), "blend rates must cover 12 months"
    act = data["act_months"]
    months = act + data["gap_months"] + data["fc_months"]
    bands = ({m: "act" for m in act} |
             {m: "nc" for m in data["gap_months"]} |
             {m: "fc" for m in data["fc_months"]})
    g = lambda rid, m: rows[rid]["values"].get(m) or 0
    gross, local, actual = {}, {}, {}
    for m in months:
        rb, rh = rates[int(m[5:7])]
        bit_pool = g("grade_dilbit", m)
        conv_heavy = g("crude_heavy", m) + g("crude_ultra_heavy", m)
        gross[m] = bit_pool * rb / (1 - rb) + conv_heavy * rh / (1 - rh)
        local[m] = g("condensate_production", m)
        actual[m] = g("imports_condensates", m) + g("imports_pentanes_plus", m)
    hist_recovery = [gross[m] - local[m] - actual[m] for m in act]
    import statistics
    rec_med = statistics.median(hist_recovery)
    rec_min, rec_max = min(hist_recovery), max(hist_recovery)
    recovered = {m: rec_med for m in months}
    implied = {m: gross[m] - local[m] - recovered[m] for m in months}
    actual_hist = {m: actual[m] for m in act}
    lines = [("Gross diluent requirement", gross, "ink", None),
             ("Local C5 supply", local, "g2", None),
             ("Implied import requirement", implied, "acc", None),
             ("Actual imports (AER actuals)", actual_hist, "steel", "5,4")]
    svg = _svg_multiline(months, lines, bands=bands)
    fc_avg = sum(implied[m] for m in data["fc_months"]) / len(data["fc_months"])
    title = (f"Implied condensate import demand averages {fc_avg:,.0f} kb/d "
             f"in the forecast: Blaine's own seasonal blend rates, recovered "
             f"diluent held at its {rec_med:,.0f} kb/d historical median")
    caption = (f"Implied condensate (C5) import demand from the model's own "
               f"balance. Gross diluent requirement = blendable bitumen "
               f"(grade_dilbit: mined + in-situ bitumen minus raw bitumen "
               f"sent to upgraders, which is fed unblended) times the "
               f"seasonal bitumen blend share, plus conventional heavy "
               f"(crude_heavy + crude_ultra_heavy) times the seasonal "
               f"conventional-heavy blend share; each share is a fraction of "
               f"the blended barrel. The shares are a 2018 seasonal profile from "
               f"Blaine's own estimates (bitumen 23 to 27 percent, conventional "
               f"heavy 16 to 19 percent by month), not public data and not "
               f"measured current-year rates. Local C5 = condensate_production. "
               f"Actual imports = imports_condensates + imports_pentanes_plus. "
               f"Recovered/recycled diluent is not measured: it is the "
               f"historical residual (gross minus local minus actual "
               f"imports), which ran {rec_min:,.0f} to {rec_max:,.0f} kb/d "
               f"across the {len(act)} AER actual months; the forecast holds "
               f"the median, {rec_med:,.0f} kb/d. Implied imports = gross "
               f"minus local minus recovered. Where implied and actual "
               f"imports diverge in history, the gap is the recovery residual "
               f"running above or below its median: itself a signal about "
               f"diluent recycling or unmodeled C5 supply. Actual imports are "
               f"shown only through the latest AER actual. "
               f"<b>Vintage:</b> {MODEL_VINTAGE}.")
    csv_rows = []
    for m in months:
        rb, rh = rates[int(m[5:7])]
        csv_rows.append({
            "month": m, "band": bands[m],
            "gross_diluent_requirement_kbd": f"{gross[m]:.1f}",
            "local_c5_supply_kbd": f"{local[m]:.1f}",
            "recovered_diluent_kbd": f"{recovered[m]:.1f}",
            "implied_import_requirement_kbd": f"{implied[m]:.1f}",
            "actual_imports_kbd": (f"{actual[m]:.1f}"
                                   if m in actual_hist else ""),
            "bitumen_blend_share": f"{rb:.3f}",
            "conv_heavy_blend_share": f"{rh:.3f}",
        })
    _write_csv(CHART_DIR / "diluent-import-demand.csv",
               ["month", "band", "gross_diluent_requirement_kbd",
                "local_c5_supply_kbd", "recovered_diluent_kbd",
                "implied_import_requirement_kbd", "actual_imports_kbd",
                "bitumen_blend_share", "conv_heavy_blend_share"],
               csv_rows, MODEL_VINTAGE)
    legend = [(lab, S.PAL[col]) for lab, _, col, _ in lines]
    html = S.chart_figure(_scroll(svg), caption, legend, title=title)
    html += S.csv_link("../data/charts/diluent-import-demand.csv",
                       f"CSV · {MODEL_VINTAGE}")
    return html


# ----------------------------------------------------------------------------
# Chart C: forward maintenance offline volumes with sourced event markers.
# ----------------------------------------------------------------------------

def build_maintenance(data):
    # Blaine 2026-09-24: the hub carries no maintenance chart or event list.
    # The Maintenance tab is the home of the calendar; this is a one-line
    # pointer to it.
    return ('<p class="sub">The forward turnaround calendar, with per-event '
            'sources and modeled offline volumes, lives on the '
            '<a href="../maintenance/index.html">Maintenance tab</a>.</p>')


# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Biggest movers: largest month-over-month changes between the two latest
# ACTUAL months. The underlying sources are monthly (AER ST3), so this is a
# monthly movers table, never a weekly one. Universe: project + plant leaves
# plus the conventional ST3 native lines (which have no project/plant
# decomposition). Aggregates, ST3 lines that the leaves decompose, and grade
# derivations are excluded so no barrel is counted twice.
# ----------------------------------------------------------------------------
_MOVER_LINES = {"crude_light", "crude_medium", "crude_heavy",
                "crude_ultra_heavy", "condensate_production"}


def _mover_zscore(row, act, chg):
    """z-score of this month's move against the asset's own monthly swings.

    Takes the row's month-over-month changes over the prior one-year
    history (12 changes from the trailing values in act_months), computes
    the mean and the sample standard deviation, and returns
    latest_change / std. Null when fewer than 6 valid history changes
    exist or the history has zero variance. Deterministic: no modeling,
    just the asset's own published history.
    """
    vals = [row["values"].get(m) for m in act[-13:]]
    hist = [b - a for a, b in zip(vals, vals[1:])
            if a is not None and b is not None]
    if len(hist) < 6:
        return None
    mean = statistics.mean(hist)
    std = statistics.stdev(hist)
    if std == 0:
        return None
    _ = mean  # computed per spec; the score scales against std only
    return chg / std


def build_biggest_movers(data, n=10):
    act = data["act_months"]
    if len(act) < 2:
        return ""
    m0, m1 = act[-2], act[-1]
    cands = []
    for r in data["rows"]:
        kind = r.get("kind")
        if kind in ("project", "plant"):
            typ = "Project" if kind == "project" else "Plant"
        elif kind == "line" and r["id"] in _MOVER_LINES:
            typ = "ST3 line"
        else:
            continue
        v0 = r["values"].get(m0)
        v1 = r["values"].get(m1)
        if v0 is None or v1 is None:
            continue
        chg = v1 - v0
        cands.append((abs(chg), chg, v0, v1, r.get("label", r["id"]), typ, r))
    cands.sort(key=lambda t: -t[0])
    top = [c for c in cands if c[0] > 0][:n]
    if not top:
        return ""
    m0l = B._mname(m0)
    m1l = B._mname(m1)
    rows = []
    for _, chg, v0, v1, lab, typ, r in top:
        pct = f"{chg / v0 * 100:+.1f}%" if v0 else "n/a"
        cls = "up" if chg > 0 else "dn"
        z = _mover_zscore(r, act, chg)
        z_txt = "n/a" if z is None else f"{z:+.1f}"
        sig = z is not None and abs(z) >= 2
        sig_td = '<td class="sig">signal</td>' if sig else "<td></td>"
        rows.append(
            f"<tr><td>{S.esc(lab)}</td><td class=\"k\">{typ}</td>"
            f"<td class=\"n\">{v0:,.1f}</td><td class=\"n\">{v1:,.1f}</td>"
            f"<td class=\"n {cls}\">{chg:+,.1f}</td>"
            f"<td class=\"n\">{pct}</td>"
            f"<td class=\"n\">{z_txt}</td>{sig_td}</tr>")
    tbl = ("<table class=\"data movers\"><thead><tr><th>Asset</th><th>Type</th>"
           f"<th>{m0l}</th><th>{m1l}</th><th>Change kb/d</th><th>Change %</th>"
           "<th>z-score</th><th>Signal</th>"
           "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    explainer = (
        '<p class="tblnote">A z-score measures how unusual this month\'s move '
        'is for that specific asset. A score of 2 means the move was about '
        'twice the asset\'s typical monthly swing over the past year. Big '
        'assets post big raw moves all the time, so the raw number alone '
        'misleads; the score separates a real signal from normal noise, and '
        'rows marked signal moved at least twice their normal monthly '
        'range.</p>')
    cap = (S.vintage_caption(
        f"AER ST3 actuals, {m0l} to {m1l} (pulled 2026-09-22). Monthly "
        "source: these are month-over-month changes in published actuals, "
        "not weekly moves. Universe: 22 in-situ project leaves, 13 "
        f"mined/upgrader plant leaves, and the {len(_MOVER_LINES)} "
        "conventional ST3 native lines; aggregates, decomposed lines, and "
        "grade derivations are excluded so no barrel counts twice."))
    return (tbl + explainer + f"<p class=\"cap\">{cap}</p>")


# Page assembly.
# ----------------------------------------------------------------------------

def build():
    data = json.loads(DASH_JSON.read_text())
    updated = S.edition_date(data.get("built", "2026-09-23"))
    exec_html = B.exec_panel_html(data, more_href="../st3-dashboard.html")
    kpi_html = B._kpi_strip_html(data)
    out = [
        exec_html,
        kpi_html,
        '<h2 id="egress">Egress</h2>',
        '<p class="sub">How full the pipes are: available capacity by system '
        'against what actually flowed. The TMX expansion step is structural: '
        'the capacity series itself steps up in May 2024.</p>',
        build_egress(),
        '<h2 id="grades">Supply by type</h2>',
        '<p class="sub">What kind of barrel the WCSB produces: heavy, light, '
        'medium, and synthetic. The window runs from AER actuals through the '
        'nowcast into the model forecast.</p>',
        build_supply_type(data),
        '<h2 id="movers">Biggest movers</h2>',
        '<p class="sub">The largest month-over-month changes in the latest '
        'published actuals. Monthly data &mdash; this is not a weekly movers table.</p>',
        build_biggest_movers(data),
        '<h2 id="maintenance">Maintenance outlook</h2>',
        build_maintenance(data),
        '<h2>Go deeper</h2>',
        '<nav class="seclist" aria-label="Supply sections">',
        '  <a class="srow" href="../st3-dashboard.html">'
        '<p class="kicker">The table</p><h3>Projected ST3 dashboard</h3>'
        '<p>Every ST3 line, drillable to project and plant leaves.</p>'
        '<span class="go">Open the dashboard →</span></a>',
        '  <a class="srow" href="../balance/index.html">'
        '<p class="kicker">The balance</p><h3>Supply / demand balance</h3>'
        '<p>Storage, removals, and the forward balance behind the letter.</p>'
        '<span class="go">Open the balance →</span></a>',
        '  <a class="srow" href="../maintenance/index.html">'
        '<p class="kicker">The calendar</p><h3>Maintenance</h3>'
        '<p>The full forward turnaround calendar with sources.</p>'
        '<span class="go">Open maintenance →</span></a>',
        '  <a class="srow last" href="../projects/index.html">'
        '<p class="kicker">The assets</p><h3>Projects</h3>'
        '<p>Project profiles: production, maintenance, and outlook.</p>'
        '<span class="go">Open projects →</span></a>',
        '</nav>',
    ]
    page = S.page_shell(
        "Supply", "Supply",
        "The physical barrel: takeaway capacity, what grade it is, and when "
        "it goes offline for maintenance.",
        '<a href="../index.html">Home</a> / Supply',
        "\n".join(out), "supply", 1, updated, SOURCE_LINE,
        description="Western Canadian crude supply: egress capacity vs flows, "
                    "supply by crude type, and the forward maintenance outlook.",
        url_path="supply/index.html")
    d = SITE / "supply"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page)
    print(f"wrote {d / 'index.html'}")


if __name__ == "__main__":
    build()
