"""Static site build: inject generated panels into site/index.html.

Reads:  ../ideas.json     (panel 6, actionable ideas -- data-licensed="wood-mackenzie")
        ../cycle.json      (panel 8, trading-cycle summary -- PUBLIC-SAFE)
        ../prototype/charts/*.png  (referenced with onerror fallbacks; file://-safe)
Writes: index.html (in place; panels injected between AUTO-PANELS markers,
        stale snapshot/footer copy refreshed)

Idempotent: rerun any time after run_latest.py / ideas.py / build_charts.py /
cycle.py. Licensed sections keep their data-licensed attributes so ?public=1
gating keeps working. Nothing is fetched at runtime (file:// safe).
"""
import html
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent
INDEX = SITE / "index.html"

sys.path.insert(0, str(SITE))
import shared as S  # noqa: E402  (license labels, anonymity)

PANEL6_OPEN = "<!-- BEGIN AUTO-PANELS -->"
PANEL6_CLOSE = "<!-- END AUTO-PANELS -->"


def esc(t):
    return html.escape(str(t), quote=False)


def panel6_ideas():
    d = S.anon_data(json.loads((BASE / "ideas.json").read_text()))
    cards = []
    for i, it in enumerate(d["ideas"], 1):
        cr = it["current_reading"]
        inv = "".join(f"<li>{esc(x)}</li>" for x in it["invalidation"])
        cards.append(f"""
  <div class="idea">
    <h3>{i}. {esc(it['title'])} <span class="flag {'on' if it['status']=='ARMED' else 'off'}">{esc(it['status'])}</span></h3>
    <p><strong>Trigger:</strong> {esc(it['trigger_rule'])}</p>
    <p><strong>Now:</strong> {esc(cr['text'])}<br>
       <span class="vintage-inline">Vintage: {esc(cr['vintage'])}</span></p>
    <p><strong>2018 analog:</strong> {esc(it['historical_analog'])}</p>
    <p><strong>Invalidated if:</strong></p>
    <ul class="tight">{inv}</ul>
  </div>""")
    return f"""
<!-- PANEL 6 : actionable ideas. Licensed commercial storage (current readings embed licensed levels). -->
<section class="panel" id="panel-ideas" data-licensed="wood-mackenzie">
  <h2>Actionable ideas <span class="lic-tag">{S.license_label("wood-mackenzie")}</span></h2>
  <p class="note">Monitor-driven conditions worth trading around (<strong>not validated forecasts</strong>).
  {esc(d.get('label', ''))} As of {esc(d.get('asof', ''))}: {d.get('n_armed', 0)}/{d.get('n_total', 0)} armed.</p>
  {''.join(cards)}
</section>"""


def panel7_momentum():
    return f"""
<!-- PANEL 7 : price momentum overlay. LICENSED: Eikon transcription. -->
<section class="panel" id="panel-momentum" data-licensed="eikon">
  <h2>Price momentum overlay <span class="lic-tag">{S.license_label("eikon")}</span></h2>
  <div class="chartbox">
    <img src="../prototype/charts/momentum.png" alt="TMW 1a index level and three-month rate of change"
         onerror="this.style.display='none';document.getElementById('ph-momentum').style.display='block';">
    <div class="chart-placeholder" id="ph-momentum" style="display:none;">
      Momentum chart could not be loaded (<code>momentum.png</code> missing or failed to render).
    </div>
  </div>
  <ul class="tight">
    <li>TMW 1a index, Aug 2026 final: <strong>-23.16</strong> USD/bbl; 3-month rate of change <strong>-20.5%</strong> (weakening into the injection window).</li>
    <li>Joint point-in-time test (differential changes): naive carry MAE <strong>1.06</strong> $/bbl vs monitor OLS <strong>1.42</strong> $/bbl; naive wins, and momentum is the hard timing benchmark.</li>
    <li>Role: regime awareness before the move, not a timing signal. No storage/differential relationship enters any model until point-in-time tests beat naive carry.</li>
  </ul>
  <p class="vintage">
    <strong>Vintage:</strong> ICE 1a settles transcribed from Eikon by the desk, Dec 2023&ndash;Aug 2026.
    Realized-index proxy only; not a tradable M1&ndash;M2 spread. Full test detail in <code>appendix_joint_test.md</code> (private).
  </p>
</section>"""


def panel9_flags():
    d = S.anon_data(json.loads((BASE / "flags.json").read_text()))
    sig_class = {"BULLISH-BASIS": "bull", "BEARISH-BASIS": "bear",
                 "WATCH": "watch", "NEUTRAL": "neu"}
    cards = []
    for f in d["flags"]:
        lic = (f' data-licensed="{f["license"]}"' if f["license"] != "public" else "")
        lic_tag = (f' <span class="lic-tag">{esc(S.license_label(f["license"]))}</span>'
                   if f["license"] != "public" else "")
        cls = sig_class.get(f["signal"], "neu")
        cards.append(f"""
  <div class="idea"{lic}>
    <h3>{f['n']}. {esc(f['title'])}{lic_tag}
      <span class="flag {cls}">{esc(f['signal'])}</span></h3>
    <p>{esc(f['read'])}</p>
    <p><strong>Flips:</strong> {esc(f['flip'])}</p>
    <p class="vintage-inline">Vintage: {esc(f['vintage'])}</p>
  </div>""")
    return f"""
<!-- PANEL 9 : six-flag dashboard. Per-card licensing: storage = commercial storage, basis = eikon. -->
<section class="panel" id="panel-flags">
  <h2>Six flags <span class="lic-tag">mixed: 4 public, 2 licensed</span></h2>
  <p class="note">Live regime reads as of {esc(d['asof'])}. {esc(d['note'])}</p>
  {''.join(cards)}
  <p class="note">Append <code>?public=1</code> to hide the two licensed cards.</p>
</section>"""


def panel_reports():
    editions = []
    for f in sorted((BASE / "reports").glob("*/*.html")):
        if f.name == "index.html":
            continue
        m = re.search(r"<!-- REPORT-META (.*?) -->", f.read_text())
        if not m:
            continue
        meta = json.loads(m.group(1))
        editions.append({
            "href": f"../reports/{f.parent.name}/{f.name}",
            **meta})
    editions.sort(key=lambda e: (e["report_type"], e["edition_date"]), reverse=True)
    latest = editions[:6]
    items = "".join(
        f'<li><a href="{esc(e["href"])}">{esc(e["title"])}: {esc(e["edition"])}</a> '
        f'<span class="vintage-inline">published {esc(e["edition_date"])}</span>'
        + (f' <span class="lic-tag">{esc(S.license_label(e["license"]))}</span>'
           if e["license"] != "public" else '')
        + '</li>'
        for e in latest)
    body = (f'<ul class="tight">{items}</ul>' if items
            else '<p class="note">No editions published yet.</p>')
    return f"""
<!-- PANEL 10 : reports archive. PUBLIC-SAFE: links only; licensed editions gated per-link. -->
<section class="panel" id="panel-reports">
  <h2>Reports <span class="lic-tag">public</span></h2>
  <p class="note">Agency-grade deep reads, one consistent template. Phone-readable,
  prints cleanly to PDF. Every chart and table carries a source line; every edition
  carries a full source appendix.</p>
  {body}
  <p class="note"><a href="../reports/index.html">Reports archive: every edition, newest first</a></p>
</section>"""


def panel11_st3():
    return """
<!-- PANEL 11 : projected ST3 dashboard. PUBLIC: AER ST3/ST53 actuals + model forecasts, no licensed data. -->
<section class="panel" id="panel-st3">
  <h2>Projected ST3 <span class="lic-tag">public</span></h2>
  <p class="note">Energy-Aspects-style balance sheet: ST3 lines with 12 months of
  actuals, a 2-month nowcast, and 12 months of model forecast. Drill from any aggregate into
  ST53 project leaves and ST39 facility rows; tap any row for its source,
  vintage, method, and the reasoning behind the numbers. Maintenance offline
  drills into per-event turnaround rows.
  Full-page table with CSV export.</p>
  <p class="note"><a href="st3-dashboard.html"><strong>Open the Projected ST3 dashboard</strong></a>
   (26 months, kb/d, file:// safe).</p>
  <p class="vintage-inline">Vintage: AER ST3/ST53 actuals through 2026-07, ST39 through 2026-05 (pulled 2026-09-22);
  Aug-Sep 2026 nowcast (estimated) built 2026-09-23; forecast built 2026-09-22.
  Green columns from Nov 2026 are the tradable window.</p>
</section>"""


def panel8_cycle():
    c = S.anon_data(json.loads((BASE / "cycle.json").read_text()))
    rows = "".join(
        f"<tr><td>{esc(r['injection_month'])}</td>"
        f"<td class=\"num\">{r['surplus_kbd']:+.1f}</td></tr>"
        for r in c["forward_balances"])
    cw = c["current_window"]
    nw = c["next_window"]
    if nw.get("window_opens"):
        nxt_html = (f"Next tradable: <strong>{esc(nw['injection_month'])} injections</strong> "
                    f": window opens {esc(nw['window_opens'])} "
                    f"(<strong>{nw['days_until_open']} days</strong>).")
    else:
        nxt_html = (f"Prompt barrel: <strong>{esc(nw['injection_month'])}</strong> "
                    f"({esc(nw['status'])}; {nw['days_to_month_end']} days to month-end, "
                    f"{esc(nw['days_note'])}).")
    return f"""
<!-- PANEL 8 : trading-cycle summary. PUBLIC-SAFE: cycle dates + AER balances only, no licensed data. -->
<section class="panel" id="panel-cycle">
  <h2>Trading cycle: where are we <span class="lic-tag">public</span></h2>
  <p class="note">As of <strong>{esc(c['asof'])}</strong>. {esc(c['rule'])}</p>
  <ul class="tight">
    <li>Injection month {esc(cw['injection_month'])}: <strong>{esc(cw['status'])}</strong></li>
    <li>{nxt_html}</li>
  </ul>
  <table class="data">
    <tr><th>Tradable injection month</th><th style="text-align:right;">Supply&minus;egress (kb/d)</th></tr>
    {rows}
  </table>
  <p class="note">Positive = builds into commercial storage; negative = draws.
  Balances are the delta-projector surpluses from public AER ST3/ST53 model leaves: the same series that drives the storage trajectory.</p>
  <p class="vintage"><strong>{esc(c['noms_caveat'])}</strong><br>{esc(c['note'])}</p>
</section>"""


def main():
    print("build_site.main() is retired: site/index.html is now generated by "
          "site/build_sections.py (build_home). The panel generators in this "
          "module are still imported by build_sections.py for the licensed "
          "desk monitors on the home page.")
    return
    s = INDEX.read_text()

    # --- stale snapshot refresh (AER-driven window, Sep 2026-09-22 run) ---
    s = s.replace(
        '<div class="value">~223</div>\n      <div class="sub">naive straight-line at Sep 2025 build rate (+22.1 Mbbl/d); monitor projector pending</div>',
        '<div class="value">9</div>\n      <div class="sub">AER-driven: Apr 2027 end of tradable window at 81.6% utilization (naive: 64.0%)</div>')
    s = s.replace(
        '<span class="flag off">OFF</span>',
        '<span class="flag on">FIRED</span>')
    s = s.replace(
        '<div class="sub">utilization 43.0% below 70% grid-searched threshold (in-sample, not validated)</div>',
        '<div class="sub">AER-driven projection crosses the 75% construction-default threshold in Apr 2027 with egress stress present</div>')

    # --- chart placeholder copy: charts are delivered now; keep onerror fallbacks ---
    s = s.replace("Snapshot chart pending &mdash; charts agent has not delivered <code>snapshot.png</code> yet.",
                  "Snapshot chart could not be loaded (<code>snapshot.png</code> missing or failed to render).")
    s = s.replace("Projection chart pending &mdash; charts agent has not delivered <code>utilization_projection.png</code> yet.<br>\n      Expected: monthly utilization Jan 2018&ndash;Sep 2025, 6-month projection cone, grid-searched threshold band, weeks-to-tank-top marker.",
                  "Projection chart could not be loaded (<code>utilization_projection.png</code> missing or failed to render).")
    s = s.replace("Egress chart pending &mdash; charts agent has not delivered <code>egress_stress.png</code> yet.<br>\n      Expected: per-route utilization and apportionment, Jan 2018&ndash;present.",
                  "Egress chart could not be loaded (<code>egress_stress.png</code> missing or failed to render).")
    s = s.replace("2018 timeline chart pending &mdash; charts agent has not delivered <code>episode_2018.png</code> yet.<br>\n      Expected: utilization, apportionment stress, WCS diff, and constraint-flag markers, Oct&ndash;Dec 2018.",
                  "2018 timeline chart could not be loaded (<code>episode_2018.png</code> missing or failed to render).")

    # --- inject auto panels (6/7/8/9/10) before the footer ---
    panels = "\n".join([PANEL6_OPEN, panel6_ideas(), panel7_momentum(),
                        panel8_cycle(), panel9_flags(), panel_reports(),
                        panel11_st3(), PANEL6_CLOSE])
    if PANEL6_OPEN in s:
        pre, rest = s.split(PANEL6_OPEN, 1)
        _, post = rest.split(PANEL6_CLOSE, 1)
        # Canonical panel boundaries: exactly one blank line on each side, so
        # reruns converge instead of accumulating newlines at the junction.
        s = pre.rstrip("\n") + "\n\n" + panels + "\n\n" + post.lstrip("\n")
    else:
        s = s.replace("<footer>", panels + "\n\n<footer>", 1)

    # --- top license-comment mapping: normalize to one canonical block.
    # (The old append-based approach re-duplicated this block on every rerun;
    # this pass collapses any run of mapping lines to the canonical list.)
    _map_order = ["ideas", "momentum", "cycle", "flags", "st3", "reports"]
    _canon = {
        "ideas": '  - #panel-ideas        data-licensed="wood-mackenzie"  (current readings embed licensed levels)',
        "momentum": '  - #panel-momentum     data-licensed="eikon"           (Eikon ICE 1a transcription)',
        "cycle": '  - #panel-cycle        PUBLIC (cycle dates + AER balances only; no licensed data)',
        "flags": '  - #panel-flags        MIXED (per-card: storage card wood-mackenzie, basis card eikon; 4 cards public)',
        "st3": '  - #panel-st3          PUBLIC (AER ST3/ST53 actuals + model forecasts; no licensed data)',
        "reports": '  - #panel-reports      PUBLIC (links only; licensed editions gated per-link)',
    }
    s = re.sub(r"(?:  - #panel-(?:ideas|momentum|cycle|flags|st3|reports) +[^\n]*\n)+",
               "".join(_canon[k] + "\n" for k in _map_order), s)
    s = s.replace(
        "in-sample (F1 0.091, n=21) and <strong>not validated</strong>. Nothing on this page changes model numbers.\n  Scaffold generated 2026-09-22; charts pending from the parallel charts build.",
        "construction defaults (F1 = 0 on the 2023&ndash;2025 monthly grid search) and <strong>not validated</strong>. Nothing on this page changes model numbers.\n  Site built 2026-09-22; charts delivered. Rerun pipeline: prototype/run_latest.py, ideas.py, build_charts.py, cycle.py, then site/build_site.py.")


    INDEX.write_text(s)
    print(f"wrote {INDEX}")


if __name__ == "__main__":
    main()
