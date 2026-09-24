#!/usr/bin/env python3
"""Build the Projected ST3 dashboard page (site/st3-dashboard.html).

Self-contained HTML: embedded JSON data, vanilla JS tree table, works over
file:// with no server. Phone-first: sticky row labels + sticky header,
horizontal month scroll, CSV export button.

Data:
  actuals: AER ST3 from the repo duckdb, 2025-08..2026-07 (kb/d)
  gap:     2026-08/2026-09 nowcast (ST3 unpublished; _seasonal_baseline +
            confirmed maintenance events, built 2026-09-23)
  forecast: 2026-10..2027-09, per-line _seasonal_baseline recompute +
            sd_balance.json aggregates, 21 grossed-up ST53 project leaves,
            and ST39 facility rows (mined bitumen + SCO by plant, actuals
            through 2026-05) whose forecasts are scaled pro-rata to tie to
            the ST3 lines. Every row carries a "why" annotation explaining
            the reasoning behind its forecast.

Run with the repo venv python:
    /home/hatch/workspace/wcsb-sd/.venv/bin/python site/build_st3_dashboard.py
"""
import calendar
import html
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent          # .../hidden_files/woodmack_storage (data + outputs)
REPO = SITE.parent.parent.parent  # .../wcsb-sd (code + duckdb)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BASE))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.model.forecast import _seasonal_baseline  # noqa: E402
from src.analytics.project_forecast import project_observed  # noqa: E402
import build_sd_balance as BSB  # noqa: E402

sys.path.insert(0, str(SITE))
import textutil as TU  # noqa: E402  (license labels, anonymity; no circular import)

ACT_MONTHS = [f"{y}-{m:02d}" for y, m in
              [(2025, m) for m in range(8, 13)] + [(2026, m) for m in range(1, 8)]]
GAP_MONTHS = ["2026-08", "2026-09"]
FC_MONTHS = BSB.MONTHS
ALL_MONTHS = ACT_MONTHS + GAP_MONTHS + FC_MONTHS

VINT_ACT = "AER ST3 actuals through 2026-07, pulled 2026-09-22"
VINT_ST53 = "AER ST53 actuals through 2026-07, pulled 2026-09-22"
VINT_FC = "model _seasonal_baseline, built 2026-09-22"
VINT_NC = "model nowcast (_seasonal_baseline + confirmed maintenance), built 2026-09-23"
# Gap-month maintenance offline totals (kb/d). These are MEMO values: the
# outages are modeled down at the project/plant leaves (see LEAF_MAINT) and
# this line is not subtracted in the storage identity.
# Coker 8-2 event rate 77 kb/d comes from the approved Oct derivation
# (77x9/31 = 22.4): Aug 20-31 is 12 days (77x12/31 = 29.8), Sep is a full
# month (77.0). Horizon Sep -230 is the September bridge of the Sep 8 35-day
# turnaround (Blaine ruling 2026-09-22; the Oct residual -119 is already in
# the forecast, not double counted). Cold Lake -3 is the Q3/Q4 guidance rate
# (Imperial). Suncor Base Plant Q4 cuts sit in Oct-Dec only.
MAINT_NC = {"2026-08": round(77.0 * 12 / 31 + 3.0, 1),
            "2026-09": round(230.0 + 77.0 + 3.0, 1)}

# Named assumptions for the Coker 8-2 disposition (FINAL ruling by Blaine
# 2026-09-24, supersedes the 2026-09-23 redirect approval; documented in
# annotations/maintenance_disposition_history.md). NO interconnect redirect:
# in a planned upgrader turnaround the mine plan is set months ahead to match
# reduced upgrader demand, so there is no hungry upgrader for the interconnect
# to feed. The Q1 2026 precedent (16.4 kb/d Syncrude bitumen to Base) was an
# unplanned outage where the mine could not react in time; it does not
# transfer to planned turnarounds.
# Coker 8-2 mine dial-back: OPERATIONAL MEMO ONLY. Full bitumen-equivalent of
# the coker rate at the observed Syncrude yield (SCO/0.843): Aug 29.8/0.843=
# 35.4; Sep 77.0/0.843=91.4; Oct 22.4/0.843=26.6. Not deducted at any leaf;
# heavy-market impact zero.
SYNCRUDE_MINE_DIALBACK_MEMO = {"2026-08": 35.4, "2026-09": 91.4,
                               "2026-10": 26.6}
SYNCRUDE_UPGRADER_YIELD = 0.843      # observed Syncrude yield (ST39 2017-2026)

# Leaf-level maintenance deductions (kb/d offline), approved by Blaine
# 2026-09-23. Applied AFTER gross-up/scaling at the post-display level, to
# nowcast + forecast months only (actuals untouched). Keys are dashboard row
# ids. The maint parent row keeps its values as a MEMO of the outage events
# (not the disposition) and is no longer subtracted in the storage identity.
# Ruling 2026-09-24 (Blaine): the Horizon 35-day turnaround is an upgrader
# outage, so the -230/-119 kb/d is deducted at the SCO leaf, not the mine
# leaf. SCO needs no blending: the SCO-leaf cut reduces tradable synthetic
# barrels 1:1 (September -230 SCO = -230 tradable syn barrels). The mine leaf
# keeps an operational note only.
LEAF_MAINT = {
    "scoplant_CNRL HORIZON OIL SANDS PROJECT":
        {"2026-09": 230.0, "2026-10": 119.0},
    "scoplant_SYNCRUDE MILDRED LAKE":
        {"2026-08": 29.8, "2026-09": 77.0, "2026-10": 22.4},
    # NOTE (final ruling by Blaine 2026-09-24): the Coker 8-2 mine dial-back
    # is NOT deducted at any leaf. Market accounting: the event's impact is
    # the gross coker rate on synthetic crude only (Aug -29.8, Sep -77.0,
    # Oct -22.4 kb/d); no interconnect redirect; heavy-market impact is zero.
    # The dial-back survives only as the operational memo
    # SYNCRUDE_MINE_DIALBACK_MEMO.
    "plant_SUNCOR ENERGY OSG": {"2026-11": 15.0},
    "scoplant_SUNCOR ENERGY OSG": {"2026-11": 5.0},
    "proj_imo_cold_lake": {"2026-08": 3.0, "2026-09": 3.0, "2026-10": 3.0,
                           "2026-11": 3.0, "2026-12": 3.0},
    "proj_cve_christina_lake": {"2026-10": 20.0},
    # MacKay River Sep 2027 turnaround (CADENCE-MODELED, Blaine-approved
    # 2026-09-23, E2): -12 kb/d, the median of observed September dips
    # (5.4-33.2 kb/d, median 12.2) in the AER ST53 seasonal dip analysis
    # (2019-2025). In the numbers, labeled CADENCE-MODELED everywhere,
    # never presented as company-confirmed.
    "proj_su_mackay_river": {"2027-09": 12.0},
    # Primrose/Wolf Lake Apr 2027 turnaround (CADENCE-MODELED,
    # Blaine-approved 2026-09-23, E3): -26 kb/d, the median of observed
    # April dips in the AER ST53 seasonal dip analysis (6 of 16 years).
    # WEAK-SIGNAL FLAG: April dip signal has weakened in 2017-2026 data
    # (3 flags in the last decade); weakening, not dead. In the numbers,
    # labeled CADENCE-MODELED everywhere, never presented as
    # company-confirmed.
    "proj_cnq_primrose": {"2027-04": 26.0},
}
# Diluent back-out (Rule 2, Blaine 2026-09-24): when bitumen that would have
# been blended to dilbit is offline, the diluent that would have blended it
# is freed and is not imported. Back-out = bitumen cut x 0.43 (the 30% cut:
# 0.30/0.70). Applies only to dilbit-bound bitumen leaves (SAGD/CSS); never
# to upgrader-locked bitumen (Horizon/Syncrude/Suncor Base mines) or SCO
# leaves. Tradeable supply lost exceeds the straight bitumen number by this
# amount: e.g. -20 kb/d SAGD bitumen => -28.6 dilbit => -8.6 diluent.
# Components: Cold Lake -3 x 0.43 = 1.3 (Aug-Dec 2026); Christina Lake -20 x
# 0.43 = 8.6 (Oct 2026); Primrose -26 x 0.43 = 11.1 (Apr 2027); MacKay River
# -12 x 0.43 = 5.1 (Sep 2027).
DILUENT_BACKOUT = {
    "2026-08": 1.3, "2026-09": 1.3, "2026-10": 9.9, "2026-11": 1.3,
    "2026-12": 1.3, "2027-04": 11.1, "2027-09": 5.1,
}
# Per-event maintenance decomposition (Blaine 2026-09-24): the monthly kb/d
# offline by event. No longer visible rows on the dashboard tree (event
# detail lives on the Maintenance tab); the Maintenance tab's modeled-offline
# table reads this constant and checks it sums to the aggregate maint row.
#   Aug 2026: 29.8 + 3.0 = 32.8
#   Sep 2026: 230 + 77.0 + 3.0 = 310.0
#   Oct 2026: 119 + 22.4 + 3.0 + 20.0 = 164.4
#   Nov 2026: 20.0 + 3.0 = 23.0
#   Dec 2026: 3.0
#   Sep 2027: 12.0 (MacKay River, CADENCE-MODELED per Blaine 2026-09-23)
#   Apr 2027: 26.0 (Primrose/Wolf Lake, CADENCE-MODELED per Blaine 2026-09-23, weak-signal flag)
MAINT_CHILDREN = {
    "maint_horizon": {"2026-09": 230.0, "2026-10": 119.0},
    "maint_coker82": {"2026-08": 29.8, "2026-09": 77.0, "2026-10": 22.4},
    "maint_suncor_bp": {"2026-11": 20.0},
    "maint_cold_lake": {"2026-08": 3.0, "2026-09": 3.0, "2026-10": 3.0,
                        "2026-11": 3.0, "2026-12": 3.0},
    "maint_cve_cl": {"2026-10": 20.0},
    "maint_mackay": {"2027-09": 12.0},
    "maint_primrose": {"2027-04": 26.0},
}
# Blaine-approved growth ramps (2026-09-23). Applied AFTER gross-up/scaling
# at the post-display level, to forecast months only (actuals and nowcasts
# untouched), mirroring LEAF_MAINT so the ST3 impact is exactly the approved
# kb/d. The recompute below re-ties parents and the storage identity.
# Only growth with primary corporate confirmation enters the numbers; all
# other proposed growth stays flagged-only in annotations/project_intel/.
LEAF_GROWTH_ADD = {
    # Christina Lake North expansion: +40 kb/d by Dec 2028, linear from
    # Jul 2026 (40/29 kb/d per month). Source: Cenovus Q1 2026 results news
    # release (2026-05-06): "increase production volumes by approximately
    # 40,000 bbls/d by 2028"; 40-well redevelopment ramping H2 2026, first
    # new steam generator online before year-end 2026. Applied to the
    # cve_christina_lake leaf (North facility barrels are folded into it
    # per build_sd_balance).
    "proj_cve_christina_lake": {
        "2026-10": 4.1, "2026-11": 5.5, "2026-12": 6.9,
        "2027-01": 8.3, "2027-02": 9.7, "2027-03": 11.0,
        "2027-04": 12.4, "2027-05": 13.8, "2027-06": 15.2,
        "2027-07": 16.6, "2027-08": 17.9, "2027-09": 19.3,
        # ramp continues through the extended Dec 2027 window at the same
        # approved rate (40/29 kb/d per month) toward Dec 2028
        "2027-10": 20.7, "2027-11": 22.1, "2027-12": 23.4,
    },
    # Leismer expansion: linear ramp to 40 kb/d by Dec 2027, +0.5 kb/d per
    # month from Jul 2026 (17 months). Sized so the grossed seasonal
    # baseline lands exactly on 40.0 in Dec 2027. Source: Athabasca Oil
    # Corporation 2026 budget news release (2025-12-11): $300M expansion,
    # 12 wells at Pads L10/L11, two steam generators, substantially
    # complete end of 2026, production to 40,000 bbl/d by end of 2027;
    # confirmed on track in the Q2 2026 press release (2026-07-29).
    # Approved by Blaine 2026-09-23.
    "proj_ath_leismer": {
        "2026-10": 1.5, "2026-11": 2.0, "2026-12": 2.5,
        "2027-01": 3.0, "2027-02": 3.5, "2027-03": 4.0,
        "2027-04": 4.5, "2027-05": 5.0, "2027-06": 5.5,
        "2027-07": 6.0, "2027-08": 6.5, "2027-09": 7.0,
        # ramp continues at the approved +0.5 kb/d per month so the leaf
        # lands on the approved 40.0 kb/d target in Dec 2027
        "2027-10": 7.5, "2027-11": 8.0, "2027-12": 8.5,
    },
    # Blackrod Phase 1: ramp to the 30 kb/d plateau by late 2027 (Nov
    # 2027), about +1.79 kb/d per month from Jul 2026 (16 months). Sized
    # so the grossed baseline lands exactly on 30.0 in Nov 2027. Source:
    # IPC: first oil May 31, 2026; 30,000 bopd plateau "by late 2027, a
    # quarter earlier than originally guided". ST53 (current DB vintage)
    # shows 2.4 kb/d in Jun 2026 and 4.0 in Jul 2026. Approved by Blaine
    # 2026-09-23.
    "proj_ipc_blackrod": {
        "2026-10": 5.4, "2026-11": 7.2, "2026-12": 8.9,
        "2027-01": 10.7, "2027-02": 12.5, "2027-03": 14.3,
        "2027-04": 16.1, "2027-05": 17.9, "2027-06": 19.7,
        "2027-07": 21.5, "2027-08": 23.2, "2027-09": 25.0,
        # ramp continues at the approved rate to the Nov 2027 plateau, then
        # holds the plateau through the extended Dec 2027 window
        "2027-10": 26.8, "2027-11": 28.6, "2027-12": 28.6,
    },
}
# Sunrise: hold at 70.0 kb/d flat across forecast months (override, not
# additive). Source: Cenovus Q1 2026 results news release (2026-05-06):
# "production continues to ramp up towards 70,000 bbls/d by 2028"; first of
# four east pads producing Apr 2026, second later 2026. Current output
# ~68 kb/d (ST53, 2026-07), so the hold replaces the declining seasonal
# baseline.
LEAF_GROWTH_SET = {"proj_cve_sunrise": 70.0}
LEAF_GROWTH_INFO = {
    "proj_cve_christina_lake": {
        "event": "Christina Lake North expansion ramp (+40 kb/d by Dec 2028)",
        "source": "Cenovus Q1 2026 results news release (2026-05-06)",
    },
    "proj_cve_sunrise": {
        "event": "Sunrise hold at 70 kb/d",
        "source": "Cenovus Q1 2026 results news release (2026-05-06)",
    },
    "proj_ath_leismer": {
        "event": "Leismer expansion ramp (40 kb/d by Dec 2027, +0.5 kb/d per month from Jul 2026)",
        "source": "Athabasca Oil 2026 budget news release (2025-12-11); confirmed on track in Q2 2026 press release (2026-07-29)",
    },
    "proj_ipc_blackrod": {
        "event": "Blackrod Phase 1 ramp (30 kb/d plateau by Nov 2027, first oil May 31 2026)",
        "source": "IPC operational update: 30,000 bopd plateau by late 2027, a quarter earlier than originally guided",
    },
    "scoplant_CNRL HORIZON OIL SANDS PROJECT": {
        "event": "Horizon NRUTT (Naphtha Recovery Unit Tailings Treatment) "
                 "+6.3 kb/d SCO step change from Q3 2027",
        "source": "CNRL 2026 budget news release (2025-12-16)",
    },
}
# Blaine-approved growth on ST39 plant leaves (2026-09-23). Applied to V
# AFTER the plant scaling and the LEAF_MAINT deductions (so the ST3 impact
# is exactly the approved kb/d), to forecast months only (actuals and
# nowcasts untouched). The recompute below re-ties upgraded_production,
# mined_grp, supply_total, and the storage identity. Fail loudly on a
# missing leaf or month. Only growth with primary corporate confirmation
# enters the numbers.
LEAF_GROWTH_PLANT_ADD = {
    # Horizon NRUTT: +6.3 kb/d SCO step change from Jul 2027 (the Q3/27
    # start inside the forecast window). Step change, not a ramp: it persists
    # through the extended Dec 2027 window. Source: Canadian Natural Resources Limited, "Canadian
    # Natural Resources Limited Announces 2026 Budget", 2025-12-16:
    # 'At Horizon, the Company is progressing its Naphtha Recovery Unit
    # Tailings Treatment ("NRUTT") project that targets incremental
    # production in Q3/27 of approximately 6,300 bbl/d of SCO following
    # mechanical completion.' Approved by Blaine 2026-09-23. The previously
    # flagged implied ~277,300 bbl/d post-NRUTT nameplate is moot:
    # demonstrated ST39 peak is 309.8 kb/d SCO (2025-11) and history wins
    # per the standing rule, so only the +6.3 increment is modeled.
    "scoplant_CNRL HORIZON OIL SANDS PROJECT": {
        "2027-07": 6.3, "2027-08": 6.3, "2027-09": 6.3,
        "2027-10": 6.3, "2027-11": 6.3, "2027-12": 6.3,
    },
}
# Human-readable event names + sources for the leaf deductions (drives the
# detail panels and the quarterly narrative).
LEAF_MAINT_INFO = {
    "scoplant_CNRL HORIZON OIL SANDS PROJECT": {
        "event": "Horizon 35-day turnaround (started Sep 8 2026), deducted at the SCO leaf",
        "source": "CNRL 2026 budget guidance (2025-12-16); final ruling by Blaine 2026-09-24",
    },
    "plant_CNRL HORIZON OIL SANDS PROJECT": {
        "event": "Horizon mine offline with the 35-day complex turnaround (operational note only; market impact booked at the SCO leaf)",
        "source": "Final ruling by Blaine 2026-09-24",
    },
    "scoplant_SYNCRUDE MILDRED LAKE": {
        "event": "Syncrude Coker 8-2 turnaround (planned start Aug 20 2026, about 50 days)",
        "source": "Suncor Q2 2026 MD&A (2026-08-04); Suncor Q1 2026 investor presentation",
    },
    "plant_SYNCRUDE MILDRED LAKE": {
        "event": "Syncrude Coker 8-2 mine dial-back (operational note only, full bitumen-equivalent of coker rate)",
        "source": "Final ruling by Blaine 2026-09-24; Suncor Q2 2026 MD&A (2026-08-04)",
    },
    "plant_SUNCOR ENERGY OSG": {
        "event": "Suncor Base Plant Q4 bitumen maintenance",
        "source": "Suncor 2026 planned maintenance table (Q1 2026 investor presentation, 2026-04-01)",
    },
    "scoplant_SUNCOR ENERGY OSG": {
        "event": "Suncor Base Plant Q4 SCO and diesel maintenance",
        "source": "Suncor 2026 planned maintenance table (Q1 2026 investor presentation, 2026-04-01)",
    },
    "proj_imo_cold_lake": {
        "event": "Imperial Cold Lake 3Q/4Q 2026 turnaround",
        "source": "Imperial 2026 corporate guidance (via Oil Sands Magazine 2026-01-15), annualized rate",
    },
    "proj_cve_christina_lake": {
        "event": "Christina Lake F/G turnaround tail (ASSUMED model carry, not company-stated)",
        "source": "Assumed model carry; Cenovus Q2 2026 results (2026-07-29) state no Oil Sands maintenance planned in Q4 2026",
    },
    "proj_su_mackay_river": {
        "event": "MacKay River September 2027 turnaround (CADENCE-MODELED)",
        "source": "AER ST53 seasonal dip analysis, MacKay River Suncor rows (vintage July 2026, retrieved 2026-09-23); CADENCE-MODELED, editorially approved 2026-09-23; no company-confirmed 2027 statement",
    },
    "proj_cnq_primrose": {
        "event": "Primrose/Wolf Lake April 2027 turnaround (CADENCE-MODELED, weak-signal flag)",
        "source": "AER ST53 seasonal dip analysis, Primrose and Wolf Lake CNRL rows (vintage July 2026, retrieved 2026-09-23); CADENCE-MODELED, editorially approved 2026-09-23; WEAK-SIGNAL FLAG: April dip signal has weakened in 2017-2026 data (3 flags in the last decade vs 6/16 over the long record); no company-confirmed 2027 statement",
    },
}
METH_FC = ("forecast: _seasonal_baseline (trailing-12m mean x seasonal factor "
           "from last 3 complete years)")

OP_SHORT = {
    "Cenovus Energy Inc.": "Cenovus",
    "Suncor Energy Inc.": "Suncor",
    "Canadian Natural Resources Limited": "CNRL",
    "ConocoPhillips Canada Resources Corp.": "ConocoPhillips",
    "Athabasca Oil Corporation": "Athabasca",
    "Greenfire Resources Operating Corporation": "Greenfire",
    "Strathcona Resources Ltd.": "Strathcona",
    "Harvest Operations Corp.": "Harvest",
    "Ipc Canada Ltd.": "IPC",
    "PetroChina Canada Ltd.": "PetroChina",
    "Imperial Oil Resources Limited": "Imperial",
    "Canadian Natural Upgrading Limited": "CNRL",
}


def kbd(v, ym):
    if v is None:
        return None
    y, m = int(ym[:4]), int(ym[5:7])
    return round(float(v) * 6.2898 / 1000.0 / calendar.monthrange(y, m)[1], 1)


def main():
    con = duckdb.connect(str(REPO / "data/processed/wcsb.duckdb"), read_only=True)
    df = con.execute(
        "SELECT category_id, year_month, value_m3 FROM st3_latest").df()
    piv = df.pivot_table(index="year_month", columns="category_id",
                         values="value_m3", aggfunc="first")
    act = {cid: {ym: kbd(piv[cid].get(ym), ym) for ym in ACT_MONTHS}
           for cid in BSB.ST3_LEAVES}

    # The plug (Blaine 2026-09-24): AER reporting_adjustment, forecast at
    # its trailing-12-month mean, recomputed every build. AER books it on
    # the disposition side, so a positive plug is SUBTRACTED in the
    # inventory identity. Disclosed as its own line, never buried in supply,
    # and never entering the five marketed supply rows.
    _plug_hist = [kbd(piv["reporting_adjustment"].get(ym), ym)
                  for ym in sorted(piv.index) if ym <= "2026-07"]
    PLUG_KBD = round(sum(_plug_hist[-12:]) / 12, 1)
    # Closing-inventory history (million barrels) for the Balance page
    # implied-storage level chart.
    _inv = piv["closing_inventory"]
    INV_MM_BBL = {ym: round(float(_inv.get(ym)) * 6.2898 / 1e6, 2)
                  for ym in sorted(piv.index)
                  if ym <= "2026-07" and _inv.get(ym) is not None}

    hist = BSB.st3_history(con)
    fc = {cid: _seasonal_baseline(hist, cid, FC_MONTHS) for cid in BSB.ST3_LEAVES}
    fcv = {cid: {m: round(float(fc[cid].loc[m]), 1) for m in FC_MONTHS}
           for cid in BSB.ST3_LEAVES}

    bal = json.loads((BASE / "sd_balance.json").read_text())
    months = {r["month"]: r for r in bal["months"]}
    coverage = bal["metadata"]["coverage_factor"]
    gross = 1.0 / coverage
    leaves = bal["granular_leaves"]
    pmap = {p["id"]: p for p in
            yaml.safe_load((REPO / "annotations/projects.yaml").read_text())["projects"]}

    proj_act, proj_fc = {}, {}
    for pid, leaf in leaves.items():
        if pid == "meg_christina_lake":
            continue  # folded into cve_christina_lake per build_sd_balance
        obs = project_observed(con, pid)
        proj_act[pid] = {ym: (round(float(obs.loc[ym]) * gross, 1)
                              if ym in obs.index else None)
                         for ym in ACT_MONTHS}
        proj_fc[pid] = {m: round(float(leaf[m]) * gross, 1) for m in FC_MONTHS}

    # ---- Blaine-approved growth (2026-09-23): applied post-gross-up so the
    # ST3 impact is exactly the approved kb/d, mirroring LEAF_MAINT.
    # Additive ramps first, then flat overrides; the LEAF_MAINT deductions
    # below apply on top. Fail loudly on a missing leaf or month.
    for _rid, _series in LEAF_GROWTH_ADD.items():
        _pid = _rid[len("proj_"):]
        for _m, _v in _series.items():
            _cur = proj_fc[_pid].get(_m)
            if _cur is None:
                raise SystemExit(
                    f"FAIL: growth leaf {_rid} has no value for {_m}; "
                    "refusing to add")
            proj_fc[_pid][_m] = round(_cur + _v, 1)
    for _rid, _v in LEAF_GROWTH_SET.items():
        _pid = _rid[len("proj_"):]
        for _m in FC_MONTHS:
            if _m not in proj_fc[_pid]:
                raise SystemExit(
                    f"FAIL: growth leaf {_rid} has no value for {_m}; "
                    "refusing to set")
            proj_fc[_pid][_m] = round(_v, 1)

    sagd_ids = [pid for pid in proj_fc
                if leaves[pid]["type"] == "sagd"]
    css_ids = [pid for pid in proj_fc
               if leaves[pid]["type"] == "css"]

    # ---- ST39 plant drill-down (mined bitumen + SCO by facility) ----
    PLANT_NAMES = {
        "CNRL HORIZON OIL SANDS PROJECT": "Horizon (CNRL)",
        "SUNCOR ENERGY OSG": "Suncor OSG",
        "KEARL MINE PROJECT 2-9-097-07W4M": "Kearl (Imperial)",
        "MUSKEG RIVER MINE": "Muskeg River (Shell)",
        "SYNCRUDE AURORA": "Syncrude Aurora",
        "FORT HILLS MINE": "Fort Hills",
        "SYNCRUDE MILDRED LAKE": "Syncrude Mildred Lake",
        "JACKPINE MINE": "Jackpine (CNRL)",
        "SHELL SCOTFORD UPGRADER": "Scotford (Shell)",
        "STURGEON REFINERY": "Sturgeon (NWR)",
    }
    PLANT_OP = {
        "CNRL HORIZON OIL SANDS PROJECT": "Canadian Natural Resources Limited",
        "SUNCOR ENERGY OSG": "Suncor Energy Inc.",
        "KEARL MINE PROJECT 2-9-097-07W4M": "Imperial Oil Resources Limited",
        "MUSKEG RIVER MINE": "Shell Canada Energy",
        "SYNCRUDE AURORA": "Syncrude Canada Ltd.",
        "FORT HILLS MINE": "Fort Hills Energy Corporation",
        "SYNCRUDE MILDRED LAKE": "Syncrude Canada Ltd.",
        "JACKPINE MINE": "Canadian Natural Upgrading Limited",
        "SHELL SCOTFORD UPGRADER": "Shell Canada Energy",
        "STURGEON REFINERY": "North West Redwater Holdings Corp.",
    }
    mb_df = con.execute(
        "SELECT plant, year_month, kbd FROM st39_mined_bitumen").df()
    sco_df = con.execute(
        "SELECT plant, year_month, kbd FROM st39_sco").df()
    for _df in (mb_df, sco_df):
        _df["pkey"] = _df["plant"].str.strip().str.upper()
    # material plants: >1 kb/d in the latest ST39 month (2026-05)
    mb_keys = [k for k, v in
               mb_df[mb_df["year_month"] == "2026-05"].groupby("pkey")["kbd"].sum().items()
               if v > 1 and k in PLANT_NAMES]
    sco_keys = [k for k, v in
                sco_df[sco_df["year_month"] == "2026-05"].groupby("pkey")["kbd"].sum().items()
                if v > 1 and k in PLANT_NAMES]
    mb_keys.sort(key=lambda k: -mb_df[mb_df["pkey"] == k]["kbd"].sum())
    sco_keys.sort(key=lambda k: -sco_df[sco_df["pkey"] == k]["kbd"].sum())

    def _plant_series(df, key):
        sub = df[df["pkey"] == key].sort_values("year_month")
        return pd.Series(sub["kbd"].values, index=sub["year_month"].values)

    plant_act_mb, plant_fc_raw_mb, plant_note_mb = {}, {}, {}
    for key in mb_keys:
        s = _plant_series(mb_df, key)
        plant_act_mb[key] = {ym: (round(float(s.loc[ym]), 1) if ym in s.index else None)
                             for ym in ACT_MONTHS}
        try:
            f = _seasonal_baseline(pd.DataFrame({"q": s}), "q", FC_MONTHS)
            plant_fc_raw_mb[key] = {m: round(float(f.loc[m]), 1) for m in FC_MONTHS}
            plant_note_mb[key] = "seasonal baseline"
        except Exception:
            base = round(float(s.tail(12).mean()), 1)
            plant_fc_raw_mb[key] = {m: base for m in FC_MONTHS}
            plant_note_mb[key] = "flat trailing-12m mean (short history)"
    plant_act_sco, plant_fc_raw_sco, plant_note_sco = {}, {}, {}
    for key in sco_keys:
        s = _plant_series(sco_df, key)
        plant_act_sco[key] = {ym: (round(float(s.loc[ym]), 1) if ym in s.index else None)
                              for ym in ACT_MONTHS}
        try:
            f = _seasonal_baseline(pd.DataFrame({"q": s}), "q", FC_MONTHS)
            plant_fc_raw_sco[key] = {m: round(float(f.loc[m]), 1) for m in FC_MONTHS}
            plant_note_sco[key] = "seasonal baseline"
        except Exception:
            base = round(float(s.tail(12).mean()), 1)
            plant_fc_raw_sco[key] = {m: base for m in FC_MONTHS}
            plant_note_sco[key] = "flat trailing-12m mean (short history)"
    # scale plant forecasts pro-rata so they tie exactly to the ST3-line
    # aggregates (the approved model numbers are untouched)
    plant_fc_mb, plant_fc_sco = {}, {}
    for m in FC_MONTHS:
        raw = {k: plant_fc_raw_mb[k][m] for k in mb_keys}
        tot = sum(raw.values()) or 1.0
        tgt = fcv["mined"][m]
        for k in mb_keys:
            plant_fc_mb.setdefault(k, {})[m] = round(raw[k] / tot * tgt, 1)
        raws = {k: plant_fc_raw_sco[k][m] for k in sco_keys}
        tots = sum(raws.values()) or 1.0
        tgts = fcv["upgraded_production"][m]
        for k in sco_keys:
            plant_fc_sco.setdefault(k, {})[m] = round(raws[k] / tots * tgts, 1)

    # ---- row definitions: (id, label, depth, kind, license) ----
    rows = []
    rows.append(("supply_total", "Total WCSB crude supply", 0, "agg", "public"))
    rows.append(("in_situ", "In-situ bitumen", 1, "agg", "public"))
    rows.append(("sagd", "SAGD", 2, "subagg", "public"))
    for pid in sagd_ids:
        p = pmap[pid]
        rows.append((f"proj_{pid}",
                     f"{p['name']} ({OP_SHORT.get(p['operator'], p['operator'])})",
                     3, "project", "public"))
    rows.append(("css", "CSS", 2, "subagg", "public"))
    for pid in css_ids:
        p = pmap[pid]
        rows.append((f"proj_{pid}",
                     f"{p['name']} ({OP_SHORT.get(p['operator'], p['operator'])})",
                     3, "project", "public"))
    rows.append(("in_situ_unmapped", "Unmapped in-situ (ST53 gap)", 2, "line", "public"))
    rows.append(("mined_grp", "Mined bitumen + SCO", 1, "agg", "public"))
    rows.append(("mined", "Mined bitumen", 2, "line", "public"))
    for key in mb_keys:
        rows.append((f"plant_{key}", PLANT_NAMES[key], 3, "plant", "public"))
    rows.append(("resid_mined", "Other/unallocated (ST39 gap)", 3, "line", "public"))
    rows.append(("upgraded_production", "Upgraded production (SCO)", 2, "line", "public"))
    for key in sco_keys:
        rows.append((f"scoplant_{key}", PLANT_NAMES[key], 3, "plant", "public"))
    rows.append(("resid_sco", "Other/unallocated (ST39 gap)", 3, "line", "public"))
    # NOTE (Blaine 2026-09-24): the ST3 sent-for-further-processing line
    # (bitumen fed to upgraders) is kept in the values below (the dilbit
    # grade and the mined aggregate need it) but is NOT a visible row. It
    # is a manufacturing feed, not a market stream: nobody prices the
    # upgrader feed. It is documented in the grade method note instead.
    rows.append(("conv", "Conventional crude", 1, "agg", "public"))
    for cid, lab in [("crude_light", "Light"), ("crude_medium", "Medium"),
                     ("crude_heavy", "Heavy"),
                     ("crude_ultra_heavy", "Ultra-heavy"),
                     ("condensate_production", "Condensate")]:
        rows.append((cid, lab, 2, "line", "public"))
    # ---- grade layer (rebuilt 2026-09-24 per Blaine: five market streams) ----
    # The same supply cut the way the market thinks about it: conventional
    # lights, conventional sours, blended heavy conventional, synthetic
    # crude oil (SCO), and blended dilbit, then the total. Depth-0 rows
    # placed after the supply subtree (before diluent) so the existing tree
    # structure is untouched. Computed from the ST3 lines, so they tie
    # exactly; the leaf-to-grade mapping is documentary (see GRADE_LEAF_MAP
    # and the row detail panels). Sent for further processing (the upgrader
    # feed) is not a grade row: the dilbit row is already net of it.
    rows.append(("grade_conv_light", "Conventional lights", 0, "grade", "public"))
    rows.append(("grade_conv_sour", "Conventional sours", 0, "grade", "public"))
    rows.append(("grade_conv_heavy", "Blended heavy conventional", 0, "grade", "public"))
    rows.append(("grade_sco", "SCO (synthetic crude oil)", 0, "grade", "public"))
    rows.append(("grade_dilbit", "Blended dilbit", 0, "grade", "public"))
    rows.append(("grade_total", "Total crude supply", 0, "grade", "public"))
    rows.append(("diluent", "Diluent imports", 0, "agg", "public"))
    rows.append(("imports_condensates", "Condensate imports", 1, "line", "public"))
    rows.append(("imports_pentanes_plus", "Pentanes plus imports", 1, "line", "public"))
    rows.append(("ab_use", "Total Alberta use", 0, "agg", "public"))
    rows.append(("alberta_refinery_sales", "Alberta refinery sales", 1, "line", "public"))
    rows.append(("ab_use_other", "Other Alberta use (residual)", 1, "line", "public"))
    rows.append(("removals_from_alberta", "Removals from Alberta", 0, "line", "public"))
    rows.append(("maint", "Maintenance offline", 0, "line", "public"))
    # NOTE (Blaine 2026-09-24): the per-event maintenance children are not
    # visible rows. The aggregate memo row stays; event detail lives on the
    # Maintenance tab. Leaf-level deductions in the model are unchanged.
    # ---- storage-identity accounting rows (Blaine 2026-09-24) ----
    # The exact AER ST3 inventory identity, shown so the implied storage
    # change ties visibly: stor_chg = supply_total(net of maintenance at the
    # leaves) + total_receipts - losses + adjustments - ab_use - removals
    # - aer_plug. The plug is AER disposition-side (subtracted), disclosed
    # as its own line, and never enters the five marketed supply rows.
    rows.append(("total_receipts", "Total receipts (ST3)", 0, "line", "public"))
    rows.append(("losses_ffl", "Losses: flare, fuel, shrinkage", 0, "line", "public"))
    rows.append(("adjustments", "ST3 adjustments", 0, "line", "public"))
    rows.append(("aer_plug", "AER reporting adjustment (plug)", 0, "line", "public"))
    rows.append(("stor_chg", "Implied storage change", 0, "line", "public"))

    # ---- values ----
    V = {rid: {} for rid, _, _, _, _ in rows}
    # Hidden data line (Blaine 2026-09-24): sent for further processing is
    # kept in the values because the dilbit grade and the mined aggregate
    # need it, but it is not a visible row.
    V["sent_for_further_processing"] = {}
    # Hidden loss legs: the visible row is the combined losses_ffl; the
    # three leaves are kept for the identity math.
    V["flare_waste"] = {}
    V["fuel"] = {}
    V["shrinkage"] = {}

    def set_series(rid, series):
        for ym, v in series.items():
            V[rid][ym] = v

    st3_ids = [c for c, _ in
               [("mined", ""), ("sent_for_further_processing", ""),
                ("upgraded_production", ""), ("crude_light", ""),
                ("crude_medium", ""), ("crude_heavy", ""),
                ("crude_ultra_heavy", ""), ("condensate_production", ""),
                ("imports_condensates", ""), ("imports_pentanes_plus", ""),
                ("alberta_refinery_sales", ""), ("removals_from_alberta", "")]]
    for cid in st3_ids:
        set_series(cid, act[cid])
        for m in FC_MONTHS:
            V[cid][m] = fcv[cid][m]
    # nowcast: same _seasonal_baseline machinery run on the gap months
    ncv = {cid: {m: round(float(_seasonal_baseline(hist, cid, GAP_MONTHS).loc[m]), 1)
                 for m in GAP_MONTHS}
           for cid in BSB.ST3_LEAVES}
    for cid in st3_ids:
        for m in GAP_MONTHS:
            V[cid][m] = ncv[cid][m]

    # ST39 plant values
    for key in mb_keys:
        rid = f"plant_{key}"
        set_series(rid, plant_act_mb[key])
        for m in FC_MONTHS:
            V[rid][m] = plant_fc_mb[key][m]
    for key in sco_keys:
        rid = f"scoplant_{key}"
        set_series(rid, plant_act_sco[key])
        for m in FC_MONTHS:
            V[rid][m] = plant_fc_sco[key][m]
    # plant nowcasts for the gap months: each facility's own seasonal
    # baseline, scaled pro-rata to the ST3-line nowcast (same convention as
    # the forecast; turnaround impacts live in the maint line, not here)
    def _plant_raw_nc(df, key):
        s = _plant_series(df, key)
        try:
            f = _seasonal_baseline(pd.DataFrame({"q": s}), "q", GAP_MONTHS)
            return {m: round(float(f.loc[m]), 1) for m in GAP_MONTHS}
        except Exception:
            base = round(float(s.tail(12).mean()), 1)
            return {m: base for m in GAP_MONTHS}

    plant_nc_mb, plant_nc_sco = {}, {}
    for m in GAP_MONTHS:
        raw = {k: _plant_raw_nc(mb_df, k)[m] for k in mb_keys}
        tot = sum(raw.values()) or 1.0
        for k in mb_keys:
            plant_nc_mb.setdefault(k, {})[m] = round(
                raw[k] / tot * ncv["mined"][m], 1)
        raws = {k: _plant_raw_nc(sco_df, k)[m] for k in sco_keys}
        tots = sum(raws.values()) or 1.0
        for k in sco_keys:
            plant_nc_sco.setdefault(k, {})[m] = round(
                raws[k] / tots * ncv["upgraded_production"][m], 1)
    for key in mb_keys:
        for m in GAP_MONTHS:
            V[f"plant_{key}"][m] = plant_nc_mb[key][m]
    for key in sco_keys:
        for m in GAP_MONTHS:
            V[f"scoplant_{key}"][m] = plant_nc_sco[key][m]
    for ym in ACT_MONTHS:
        mbv = [plant_act_mb[k][ym] for k in mb_keys]
        scv = [plant_act_sco[k][ym] for k in sco_keys]
        V["resid_mined"][ym] = (round(V["mined"][ym] - sum(mbv), 1)
                                if V["mined"][ym] is not None
                                and all(v is not None for v in mbv) else None)
        V["resid_sco"][ym] = (round(V["upgraded_production"][ym] - sum(scv), 1)
                               if V["upgraded_production"][ym] is not None
                               and all(v is not None for v in scv) else None)
    for m in FC_MONTHS:
        V["resid_mined"][m] = round(
            fcv["mined"][m] - sum(plant_fc_mb[k][m] for k in mb_keys), 1)
        V["resid_sco"][m] = round(
            fcv["upgraded_production"][m]
            - sum(plant_fc_sco[k][m] for k in sco_keys), 1)

    for pid in proj_fc:
        rid = f"proj_{pid}"
        set_series(rid, proj_act[pid])
        for m in FC_MONTHS:
            V[rid][m] = proj_fc[pid][m]
    for pid in proj_fc:
        # project nowcasts: same per-project seasonal baseline as the
        # balance leaves, grossed up; events live in the maint line
        obs = project_observed(con, pid)
        fnc = _seasonal_baseline(pd.DataFrame({"q": obs}), "q", GAP_MONTHS)
        for m in GAP_MONTHS:
            V[f"proj_{pid}"][m] = round(float(fnc.loc[m]) * gross, 1)

    def colsum(rids, ym):
        vals = [V[r].get(ym) for r in rids]
        if any(v is None for v in vals):
            return None
        return round(sum(vals), 1)

    sagd_rows = [f"proj_{p}" for p in sagd_ids]
    css_rows = [f"proj_{p}" for p in css_ids]
    for ym in ACT_MONTHS + FC_MONTHS:
        V["sagd"][ym] = colsum(sagd_rows, ym)
        V["css"][ym] = colsum(css_rows, ym)
    for ym in ACT_MONTHS:
        V["in_situ"][ym] = act_line("in_situ", act, ym)
        unmapped = (V["in_situ"][ym] - V["sagd"][ym] - V["css"][ym]
                    if None not in (V["in_situ"][ym], V["sagd"][ym], V["css"][ym])
                    else None)
        V["in_situ_unmapped"][ym] = round(unmapped, 1) if unmapped is not None else None
    conv_rows = ["crude_light", "crude_medium", "crude_heavy",
                 "crude_ultra_heavy", "condensate_production"]
    for m in FC_MONTHS:
        r = months[m]
        # Aggregates are summed from the displayed (rounded) child rows so the
        # drill-down ties exactly; this can differ from sd_balance.json by
        # <0.5 kb/d of rounding on the big lines.
        V["sagd"][m] = colsum(sagd_rows, m)
        V["css"][m] = colsum(css_rows, m)
        V["in_situ"][m] = round(V["sagd"][m] + V["css"][m], 1)
        V["in_situ_unmapped"][m] = round(
            V["in_situ"][m] - V["sagd"][m] - V["css"][m], 1)
        V["mined_grp"][m] = r["supply_mined_kbd"]
        V["conv"][m] = colsum(conv_rows, m)
        V["supply_total"][m] = round(
            V["in_situ"][m] + V["mined_grp"][m] + V["conv"][m], 1)
        V["diluent"][m] = r["diluent_imports_kbd"]
        V["ab_use"][m] = r["refinery_demand_kbd"]
        V["alberta_refinery_sales"][m] = r["refinery_sales_only_kbd"]
        V["ab_use_other"][m] = round(r["refinery_demand_kbd"] - r["refinery_sales_only_kbd"], 1)
        V["removals_from_alberta"][m] = r["exports_kbd"]
        V["maint"][m] = r["maintenance_offline_kbd"]
        # Storage-identity legs (exact AER identity; Blaine 2026-09-24).
        # Fail loudly if the balance file is missing a leg: a silent null
        # here would corrupt the identity.
        for _k, _j in (("total_receipts", "total_receipts_kbd"),
                       ("flare_waste", "flare_waste_kbd"),
                       ("fuel", "fuel_kbd"),
                       ("shrinkage", "shrinkage_kbd"),
                       ("adjustments", "adjustments_kbd"),
                       ("aer_plug", "aer_reporting_adjustment_plug_kbd")):
            if _j not in r or r[_j] is None:
                raise SystemExit(
                    f"FAIL: sd_balance.json month {m} missing {_j}; "
                    f"refusing to build with an incomplete identity")
            V[_k][m] = r[_j]
        V["losses_ffl"][m] = round(
            V["flare_waste"][m] + V["fuel"][m] + V["shrinkage"][m], 1)
        V["stor_chg"][m] = r["implied_storage_change_kbd"]

    for m in GAP_MONTHS:
        # Same aggregation math as the forecast months, on nowcast inputs,
        # so parent-child ties hold by construction.
        V["sagd"][m] = colsum(sagd_rows, m)
        V["css"][m] = colsum(css_rows, m)
        V["in_situ"][m] = round(V["sagd"][m] + V["css"][m], 1)
        V["in_situ_unmapped"][m] = round(
            V["in_situ"][m] - V["sagd"][m] - V["css"][m], 1)
        V["mined_grp"][m] = round(
            V["mined"][m] + V["sent_for_further_processing"][m]
            + V["upgraded_production"][m], 1)
        V["conv"][m] = colsum(conv_rows, m)
        V["supply_total"][m] = round(
            V["in_situ"][m] + V["mined_grp"][m] + V["conv"][m], 1)
        V["diluent"][m] = round(
            V["imports_condensates"][m] + V["imports_pentanes_plus"][m]
            - DILUENT_BACKOUT.get(m, 0), 1)
        V["ab_use"][m] = ncv["total_alberta_use"][m]
        V["ab_use_other"][m] = round(
            V["ab_use"][m] - V["alberta_refinery_sales"][m], 1)
        V["maint"][m] = MAINT_NC[m]
        # Storage-identity legs on nowcast inputs (seasonal baselines via
        # ncv; the plug at its trailing-12m mean, same approved treatment
        # as the forecast months).
        V["total_receipts"][m] = ncv["total_receipts"][m]
        V["flare_waste"][m] = ncv["flare_waste"][m]
        V["fuel"][m] = ncv["fuel"][m]
        V["shrinkage"][m] = ncv["shrinkage"][m]
        V["adjustments"][m] = ncv["adjustments"][m]
        V["aer_plug"][m] = PLUG_KBD
        V["losses_ffl"][m] = round(
            V["flare_waste"][m] + V["fuel"][m] + V["shrinkage"][m], 1)
        # Exact AER identity. maint is subtracted here because this pass
        # runs before the leaf-level deductions; the recompute pass below
        # nets maintenance into supply_total instead (identical algebra).
        V["stor_chg"][m] = round(
            V["supply_total"][m] - V["maint"][m] + V["total_receipts"][m]
            - V["losses_ffl"][m] + V["adjustments"][m]
            - V["ab_use"][m] - V["removals_from_alberta"][m]
            - V["aer_plug"][m], 1)
        V["resid_mined"][m] = round(
            V["mined"][m] - sum(plant_nc_mb[k][m] for k in mb_keys), 1)
        V["resid_sco"][m] = round(
            V["upgraded_production"][m]
            - sum(plant_nc_sco[k][m] for k in sco_keys), 1)

    # ---- maintenance drill-down values (Blaine 2026-09-24): per-event detail
    # lives on the Maintenance tab, not in this tree. The aggregate maint
    # row above carries the monthly totals (from the forecast/nowcast math);
    # the outages themselves are modeled down at the project/plant leaves
    # (LEAF_MAINT), never subtracted again.

    # ---- leaf-level maintenance modeling (approved by Blaine 2026-09-23) ----
    # Deduct the approved outages at the individual project/plant leaves, in
    # nowcast + forecast months only (actuals untouched). ST53 in-situ leaves
    # are deducted post-gross-up so the ST3 impact is exactly the approved
    # kb/d. ST39 plant leaves are deducted after the pro-rata scaling; the
    # ST3 lines are then recomputed as sum(plants) + residual with the
    # residual fixed. Fail loudly if a leaf would go negative.
    for _rid, _series in LEAF_MAINT.items():
        for _m, _v in _series.items():
            _cur = V[_rid].get(_m)
            if _cur is None:
                raise SystemExit(
                    f"FAIL: leaf {_rid} has no value for {_m}; refusing to deduct")
            _new = round(_cur - _v, 1)
            if _new < 0:
                raise SystemExit(
                    f"FAIL: leaf {_rid} would go negative in {_m}: {_cur} - {_v}")
            V[_rid][_m] = _new
    # ---- Blaine-approved plant growth (2026-09-23): additive, applied
    # after the LEAF_MAINT deductions so the ST3 impact is exactly the
    # approved kb/d. Fail loudly on a missing leaf or month.
    for _rid, _series in LEAF_GROWTH_PLANT_ADD.items():
        for _m, _v in _series.items():
            _cur = V[_rid].get(_m)
            if _cur is None:
                raise SystemExit(
                    f"FAIL: growth plant leaf {_rid} has no value for {_m}; "
                    "refusing to add")
            V[_rid][_m] = round(_cur + _v, 1)
    # Recompute parents from the adjusted leaves for every nowcast and
    # forecast month, so the tree ties and the storage identity holds exactly
    # on displayed numbers in all of them. (Previously only deduction months
    # were recomputed; the other forecast months carried sd_balance.json's own
    # rounding chain, which differed 0.1-0.4 kb/d from the displayed component
    # sums. Extending the recompute reconciles that latent difference; no
    # event's numbers change, only aggregate rounding.) The maint row stays
    # as a memo (its values are unchanged) and is NOT subtracted: the outages
    # are already embedded in supply, so the storage identity drops the maint
    # term: stor_chg = supply_total(net) + total_receipts - losses_ffl
    # + adjustments - alberta_use - removals - aer_plug. The plug is
    # disposition-side (subtracted) and disclosed on its own row.
    # Actuals months are untouched.
    _affected = sorted(set(GAP_MONTHS) | set(FC_MONTHS))
    for _ym in _affected:
        V["sagd"][_ym] = colsum(sagd_rows, _ym)
        V["css"][_ym] = colsum(css_rows, _ym)
        V["in_situ"][_ym] = round(V["sagd"][_ym] + V["css"][_ym], 1)
        V["in_situ_unmapped"][_ym] = round(
            V["in_situ"][_ym] - V["sagd"][_ym] - V["css"][_ym], 1)
        V["mined"][_ym] = round(
            sum(V[f"plant_{k}"][_ym] for k in mb_keys)
            + V["resid_mined"][_ym], 1)
        V["upgraded_production"][_ym] = round(
            sum(V[f"scoplant_{k}"][_ym] for k in sco_keys)
            + V["resid_sco"][_ym], 1)
        V["mined_grp"][_ym] = round(
            V["mined"][_ym] + V["sent_for_further_processing"][_ym]
            + V["upgraded_production"][_ym], 1)
        V["conv"][_ym] = colsum(conv_rows, _ym)
        V["diluent"][_ym] = colsum(["imports_condensates",
                                   "imports_pentanes_plus"], _ym)
        V["supply_total"][_ym] = round(
            V["in_situ"][_ym] + V["mined_grp"][_ym] + V["conv"][_ym], 1)
        V["stor_chg"][_ym] = round(
            V["supply_total"][_ym] + V["total_receipts"][_ym]
            - V["losses_ffl"][_ym] + V["adjustments"][_ym]
            - V["ab_use"][_ym] - V["removals_from_alberta"][_ym]
            - V["aer_plug"][_ym], 1)

    for ym in ACT_MONTHS:
        V["mined_grp"][ym] = colsum(["mined", "sent_for_further_processing",
                                    "upgraded_production"], ym)
        V["conv"][ym] = colsum(["crude_light", "crude_medium", "crude_heavy",
                                "crude_ultra_heavy", "condensate_production"], ym)
        V["diluent"][ym] = colsum(["imports_condensates",
                                   "imports_pentanes_plus"], ym)
        V["ab_use"][ym] = act_line("total_alberta_use", act, ym)
        V["alberta_refinery_sales"][ym] = act["alberta_refinery_sales"][ym]
        a, b = V["ab_use"][ym], V["alberta_refinery_sales"][ym]
        V["ab_use_other"][ym] = round(a - b, 1) if None not in (a, b) else None
        V["supply_total"][ym] = colsum(
            ["in_situ", "mined", "sent_for_further_processing",
             "upgraded_production", "crude_light", "crude_medium",
             "crude_heavy", "crude_ultra_heavy", "condensate_production"], ym)
        # Storage-identity legs, actuals (the plug row shows the actual AER
        # reporting adjustment in actual months).
        V["total_receipts"][ym] = act_line("total_receipts", act, ym)
        V["flare_waste"][ym] = act_line("flare_waste", act, ym)
        V["fuel"][ym] = act_line("fuel", act, ym)
        V["shrinkage"][ym] = act_line("shrinkage", act, ym)
        V["adjustments"][ym] = act_line("adjustments", act, ym)
        V["aer_plug"][ym] = kbd(piv["reporting_adjustment"].get(ym), ym)
        _fl = [V["flare_waste"][ym], V["fuel"][ym], V["shrinkage"][ym]]
        V["losses_ffl"][ym] = round(sum(_fl), 1) if None not in _fl else None

    # ---- grade layer values (rebuilt 2026-09-24 per Blaine's five streams) ----
    # Computed from the ST3 lines (the approved model numbers, after all leaf
    # deductions and offsets), so the grades tie exactly. Fail loudly on any
    # missing input: no null bridge cells. grade_total must equal supply_total
    # every month (same barrels, cut by market stream instead of by source).
    # Conventional mapping (Blaine 2026-09-24): lights = light + condensate
    # (condensate is not dropped, it is folded into lights and labeled);
    # sours = medium (ST3 reports density grades; sulfur is not separated in
    # ST3); blended heavy conventional = heavy + ultra-heavy.
    # The dilbit row is bitumen net of the upgrader feed; the feed itself is
    # not a visible row.
    for _ym in ALL_MONTHS:
        _u = V["upgraded_production"].get(_ym)
        _mb = V["mined"].get(_ym)
        _is = V["in_situ"].get(_ym)
        _sf = V["sent_for_further_processing"].get(_ym)
        _li = V["crude_light"].get(_ym)
        _me = V["crude_medium"].get(_ym)
        _hv = V["crude_heavy"].get(_ym)
        _uh = V["crude_ultra_heavy"].get(_ym)
        _cd = V["condensate_production"].get(_ym)
        _st = V["supply_total"].get(_ym)
        if None in (_u, _mb, _is, _sf, _li, _me, _hv, _uh, _cd, _st):
            raise SystemExit(
                f"FAIL: grade layer missing input for {_ym}; refusing null "
                f"bridge cell")
        V["grade_sco"][_ym] = _u
        V["grade_dilbit"][_ym] = round(_mb + _is + _sf, 1)
        V["grade_conv_light"][_ym] = round(_li + _cd, 1)
        V["grade_conv_sour"][_ym] = _me
        V["grade_conv_heavy"][_ym] = round(_hv + _uh, 1)
        V["grade_total"][_ym] = round(
            V["grade_conv_light"][_ym] + V["grade_conv_sour"][_ym]
            + V["grade_conv_heavy"][_ym] + V["grade_sco"][_ym]
            + V["grade_dilbit"][_ym], 1)
        if abs(V["grade_total"][_ym] - _st) > 0.051:
            raise SystemExit(
                f"FAIL: grade_total {V['grade_total'][_ym]} != supply_total "
                f"{_st} in {_ym}")

    # ---- detail text per row: source, vintage, method, and WHY ----
    WHY = {
        "supply_total":
            "Oct 2026 is the maintenance-heavy month: 164.4 kb/d of outages "
            "modeled down at the leaves (Horizon SCO -119 Oct 1-12 tail, "
            "Syncrude Mildred Lake SCO -22.4 Oct 1-9 tail, Christina Lake "
            "-20 assumed model carry, Cold Lake -3). Nov-Dec rebound as "
            "turnarounds clear. May 2027 is the forecast low (3,817): the "
            "spring seasonal dip in SAGD plus "
            "conventional decline. Apr 2027 carries the Primrose/Wolf Lake "
            "CADENCE-MODELED turnaround (-26 kb/d, weak-signal flag). Aug-Sep "
            "2027 recover on normal seasonality.",
        "in_situ":
            "21 ST53 commercial-scheme project forecasts, grossed up 1.30x to "
            "the ST3 in-situ line (mapped projects cover 76.7%). Confirmed "
            "turnarounds are modeled down at the affected project leaves "
            "(Cold Lake -3 kb/d Aug-Dec 2026, Christina Lake -20 assumed Oct "
            "2026). Single-month dips (notably Sep 2027) are seasonal factors "
            "repeating the last 3 years, not scheduled events.",
        "sagd":
            "18 SAGD schemes. May is the seasonally soft month "
            "(the method flags it as pattern-soft at several SAGD schemes). "
            "The method repeats the last 3 years of seasonality "
            "around a flat trailing-12m baseline.",
        "css":
            "3 CSS schemes (Cold Lake, Primrose/Wolf Lake, Peace River). The "
            "only confirmed CSS event in the window is Cold Lake Q4 2026 "
            "(-3 kb/d, Imperial guidance).",
        "in_situ_unmapped":
            "ST3 in-situ minus the grossed-up mapped projects. Small "
            "month-to-month wobble is the coverage factor being a trailing-12m "
            "average, not new information.",
        "mined_grp":
            "Oct 2026 carries the two big mining turnarounds, modeled down at "
            "the plant leaves: Horizon -119 (Oct 1-12 tail of the Sep 8 35-day "
            "turnaround; CNRL guided 10,585 kb total, Sep bridge accounted "
            "6,900 kb, residual per editorial ruling 2026-09-22) and Syncrude "
            "Coker 8-2 -22.4 (Oct 1-9 tail, derived). Nov adds Suncor Base "
            "Plant Q4 cuts (-15 bitumen at the mine leaf, -5 SCO at the "
            "upgrader leaf; timing within Q4 unpublished, placed mid-quarter).",
        "mined":
            "ST3 mined bitumen line. Plant detail from AER ST39 (actuals through "
            "2026-05). Plant forecasts are each facility's seasonal baseline "
            "scaled pro-rata, then modeled down for confirmed turnarounds at "
            "the affected plants (Horizon, Suncor Base); the line is "
            "sum(plants) plus the fixed ST39 coverage residual.",
        "upgraded_production":
            "ST3 upgraded-production (SCO) line. Upgrader detail from AER ST39 "
            "(actuals through 2026-05). Scotford is the largest SCO source "
            "(347 kb/d in May 2026). Plant forecasts are scaled pro-rata, "
            "then modeled down for confirmed turnarounds at the affected "
            "upgraders (Syncrude Mildred Lake Coker 8-2, Suncor Base); the "
            "line is sum(upgraders) plus the fixed ST39 coverage residual.",
        "resid_mined":
            "ST3 mined bitumen minus the ST39 plant actuals: the ST39 coverage "
            "gap. Forecast months tie by construction (plants scaled to the "
            "line).",
        "resid_sco":
            "ST3 upgraded production minus the ST39 upgrader actuals: the ST39 "
            "coverage gap. Forecast months tie by construction (plants scaled "
            "to the line).",
        "conv":
            "Alberta conventional crude in structural decline; month-to-month "
            "moves are seasonal factors, not new information. No public "
            "project or well-level mapping in the repo, so the five ST3 "
            "streams are the leaves.",
        "crude_light":
            "ST3 light-crude stream. Seasonal baseline; decline assumption is "
            "baked into the trailing-12m mean.",
        "crude_medium":
            "ST3 medium-crude stream. Seasonal baseline; decline assumption is "
            "baked into the trailing-12m mean.",
        "crude_heavy":
            "ST3 heavy-crude stream. Seasonal baseline; decline assumption is "
            "baked into the trailing-12m mean.",
        "crude_ultra_heavy":
            "ST3 ultra-heavy stream. Small and noisy; seasonal baseline.",
        "condensate_production":
            "ST3 condensate stream. Seasonal baseline.",
        "diluent":
            "Condensate plus pentanes-plus imports; tracks blended-bitumen "
            "egress. Seasonal baseline. Net of the diluent back-out in "
            "maintenance months: bitumen that would have been blended to "
            "dilbit is offline, so its diluent is freed and not imported "
            "(bitumen cut x 0.43; e.g. Oct 2026 -9.9 on Cold Lake -3 and "
            "Christina Lake -20). Upgrader outages never free diluent.",
        "imports_condensates":
            "ST3 condensate imports. Seasonal baseline.",
        "imports_pentanes_plus":
            "ST3 pentanes-plus imports. Seasonal baseline.",
        "ab_use":
            "ST3 total Alberta use: refinery sales (about 85%) plus other "
            "Alberta sales, injection-well use, fuel and plant use.",
        "alberta_refinery_sales":
            "ST3 Alberta refinery sales. Seasonal baseline.",
        "ab_use_other":
            "Total Alberta use minus refinery sales (other sales, injection "
            "wells, fuel, plant use).",
        "removals_from_alberta":
            "Pipeline, rail and truck disposition out of province. Seasonal "
            "baseline; the demand side of the storage identity.",
        "maint":
            "MEMO row: the deductions already modeled down at the "
            "project/plant leaves (Horizon, Syncrude Coker 8-2, Suncor Base "
            "Plant, Cold Lake, Christina Lake F/G assumed). It details the "
            "outages for reference and is NOT subtracted again in the storage "
            "identity. Oct 2026 (164.4): Horizon -119, Syncrude Coker 8-2 "
            "tail -22.4, Cenovus Christina Lake F/G tail -20 (assumed "
            "model carry), Cold Lake -3. Nov 2026 (23.0): Suncor Base Plant "
            "-15 bitumen and -5 SCO (Q4 event-rate; timing within Q4 "
            "unpublished, placed mid-quarter), Cold Lake -3. Dec 2026 (3.0): "
            "Cold Lake -3. 2027-01 onward: no public-confirmed maintenance in "
            "the math. Two CADENCE-MODELED events are in the math, labeled "
            "everywhere, never as company-confirmed: Primrose/Wolf Lake Apr "
            "2027 (-26 kb/d, weak-signal flag) and MacKay River Sep 2027 "
            "(-12 kb/d). No other 2027 turnarounds "
            "are modeled.",
        "stor_chg":
            "Exact AER ST3 inventory identity: supply total (maintenance "
            "already netted at the leaves, so no separate maintenance term; "
            "the Maintenance offline row is a memo) plus total receipts "
            "minus losses (flare, fuel, shrinkage) plus ST3 adjustments "
            "minus Alberta use minus removals minus the AER reporting "
            "adjustment plug. Ties to the reported closing-minus-opening "
            "inventory change in all 199 history months within 0.1 kb/d. "
            "Negative means a draw from commercial storage.",
        "total_receipts":
            "Full ST3 receipt leg: pentanes-plus plant and fractionation "
            "yield, skim oil, waste plant receipts, other Alberta receipts, "
            "butanes and NGL as crude, and all imports. Forecast by the "
            "standard seasonal-baseline method.",
        "losses_ffl":
            "ST3 loss legs: flare and waste plus fuel plus shrinkage. "
            "Forecast by the standard seasonal-baseline method.",
        "adjustments":
            "ST3 adjustments leg (metering and reporting corrections). "
            "Forecast by the standard seasonal-baseline method.",
        "aer_plug":
            "The AER reporting adjustment: the disposition-side plug the "
            "AER uses to force total supply to equal total disposition. "
            "Actuals show the reported value; forecast months carry its "
            "trailing-12-month mean (+95.5 kb/d, recomputed each build). "
            "Persistently positive (mean +56 kb/d over 199 months), so it "
            "is subtracted in the identity. Carried as its own disclosed "
            "line, never buried in supply, and never entering the five "
            "marketed supply rows.",
        "grade_conv_light":
            "Conventional light crude plus condensate production (AER ST3 "
            "lines). Condensate is mostly diluent supply; it is folded into "
            "lights and labeled as such, matching the supply hub's "
            "tradeable buckets.",
        "grade_conv_sour":
            "Conventional medium crude (AER ST3 line). ST3 reports density "
            "grades and does not separate sulfur, so medium stands in for "
            "the conventional sour stream.",
        "grade_conv_heavy":
            "Conventional heavy plus ultra-heavy crude (AER ST3 lines): the "
            "blended heavy conventional stream.",
        "grade_sco":
            "The synthetic crude oil (SCO) grade: every SCO barrel the ST3 "
            "upgraded-production line counts. The Coker 8-2 disposition shows "
            "here: Syncrude's upgrader leaf is down 29.8/77.0/22.4 kb/d in "
            "Aug/Sep/Oct 2026, the gross coker rate (final ruling by Blaine "
            "2026-09-24: no interconnect redirect in a planned turnaround). "
            "SCO market impact: -29.8/-77.0/-22.4 kb/d.",
        "grade_dilbit":
            "The tradable dilbit number: every bitumen barrel produced that "
            "does not feed an upgrader. The blend pool is steam-assisted "
            "gravity drainage (SAGD) bitumen net of the upgrader-bound share "
            "plus mined bitumen from Kearl and Fort Hills; mined bitumen at "
            "Horizon, Syncrude, and Suncor Base is upgrader-locked and never "
            "blended (Blaine 2026-09-24). Bitumen sent for further "
            "processing (the upgrader feed) is a manufacturing transfer, not "
            "a market stream, so it is not shown as a row; the dilbit number "
            "is already net of it. This is the grade the industry "
            "struggles to sign during Suncor/Syncrude turnarounds, because "
            "interconnect redirect and flexible SAGD/PFT barrels tilting to "
            "dilbit net out differently every event. Coker 8-2 market "
            "accounting (final ruling by Blaine 2026-09-24): the Syncrude "
            "mine dial-back (Aug -35.4, Sep -91.4, Oct -26.6 kb/d bitumen) "
            "is an operational note only and does not reduce tradable heavy; "
            "the event's market impact is on synthetic crude only (Sep 2026 "
            "-77.0 kb/d gross coker rate, no interconnect redirect). Cleanest "
            "precedent: Q1 2026, when Suncor non-upgraded bitumen rose to "
            "279.5 kb/d 'primarily due to decreased upgrader availability.'",
        "grade_total":
            "Total crude supply: conventional lights plus conventional sours "
            "plus blended heavy conventional plus synthetic crude oil (SCO) "
            "plus blended dilbit. The same barrels as the Total WCSB crude "
            "supply row, verified to tie exactly every month. Use this view "
            "when the question is what stream clears; use the source view "
            "when the question is where it was produced.",
    }
    # Grade layer provenance (added 2026-09-23). Grades are computed from the
    # ST3 lines (the approved model numbers); the leaf-to-grade mapping below
    # is documentary. Where public data cannot support a leaf split, the grade
    # carries the ST3 line and the split is labeled null, never plugged.
    GRADE_SOURCE = {
        "grade_conv_light": "AER ST3 (crude-light and condensate-production lines)",
        "grade_conv_sour": "AER ST3 (crude-medium line)",
        "grade_conv_heavy": "AER ST3 (crude-heavy and crude-ultra-heavy lines)",
        "grade_sco": "AER ST3 (upgraded-production line); ST39 upgrader drill-down in the tree",
        "grade_dilbit": "WCSB S&D model grade layer (AER ST3 lines)",
        "grade_total": "WCSB S&D model grade layer (AER ST3 lines)",
    }
    GRADE_METHOD = {
        "grade_conv_light":
            "Light plus condensate production, from the approved ST3 lines. "
            "Condensate is folded into lights and labeled as such, never "
            "dropped.",
        "grade_conv_sour":
            "Carries the ST3 crude-medium line. ST3 reports density grades "
            "and does not separate sulfur, so medium stands in for the "
            "conventional sour stream.",
        "grade_conv_heavy":
            "Heavy plus ultra-heavy, from the approved ST3 lines: the "
            "blended heavy conventional stream.",
        "grade_sco":
            "Carries the ST3 upgraded-production line (the approved model "
            "number). The ST39 upgrader leaves in the tree (Scotford, "
            "Syncrude Mildred Lake, Suncor Base, Horizon, Sturgeon) plus the "
            "ST39 coverage residual sum to this line by construction.",
        "grade_dilbit":
            "Residual: ST3 mined + ST3 in-situ - |ST3 sent for further "
            "processing|, from the approved ST3 lines. The "
            "sent-for-further-processing line (bitumen fed to upgraders) is "
            "kept in the data but is not a visible row: it is an "
            "intermediate manufacturing transfer, not a market stream. "
            "Never a plug; ties by construction.",
        "grade_total":
            "Conventional lights + conventional sours + blended heavy "
            "conventional + synthetic crude oil (SCO) + blended dilbit, from "
            "the approved ST3 lines. Verified in the build to tie exactly "
            "to Total WCSB crude supply every month.",
    }
    GRADE_LEAF_MAP = {
        "grade_conv_light":
            "Leaf mapping: none; the grade carries the ST3 crude-light and "
            "condensate-production lines directly.",
        "grade_conv_sour":
            "Leaf mapping: none; the grade carries the ST3 crude-medium line "
            "directly.",
        "grade_conv_heavy":
            "Leaf mapping: none; the grade carries the ST3 crude-heavy and "
            "crude-ultra-heavy lines directly.",
        "grade_sco":
            "Leaf mapping: all ST39 upgrader leaves (scoplant_Scotford, "
            "scoplant_Syncrude Mildred Lake, scoplant_Suncor Base, "
            "scoplant_Horizon, scoplant_Sturgeon) plus resid_sco sum to the "
            "ST3 upgraded-production line; the grade carries the line.",
        "grade_dilbit":
            "Leaf mapping (conceptual): the dilbit blend pool is steam-assisted "
            "gravity drainage (SAGD) bitumen net of the upgrader-bound share "
            "plus Kearl and Fort Hills mined bitumen (the KDB/FRB dilbit "
            "grades); mined bitumen at Horizon, Syncrude, and Suncor Base is "
            "upgrader-locked and never blended (Blaine 2026-09-24). The ST3 "
            "lines do not support a leaf-level dilbit split, so the grade is "
            "the residual and the leaf split is labeled null, never plugged. "
            "Disposition defaults: PFT mines are swing barrels at the "
            "highest-netback outlet; SAGD output is unchanged by upgrader "
            "outages, with the upgrader-bound share assumed diverted to "
            "dilbit.",
        "grade_total":
            "Leaf mapping: the union of the five grade mappings. Grade "
            "conversion default: 0.87 SCO per barrel of bitumen feed "
            "(observed: fleet 0.865, Horizon 0.888, Syncrude 0.843).",
    }
    PROJ_WHY = {
        "cve_christina_lake":
            "Oct 2026 carries the Christina Lake F/G turnaround tail (-20 kb/d, "
            "assumed model carry), modeled down at this leaf. The Sep 2027 dip to "
            "243.5 is a seasonal factor repeating prior Septembers, not a "
            "scheduled event.",
        "cop_surmont":
            "Aug 2027 dip to 122.3 is a seasonal factor. No 2027 turnaround "
            "statements from ConocoPhillips.",
        "su_mackay_river":
            "Sep 2027 carries the MacKay River turnaround at -12 kb/d, "
            "CADENCE-MODELED (editorially approved 2026-09-23; median "
            "observed September dip, AER ST53 analysis). In the model math, "
            "labeled CADENCE-MODELED everywhere, never as company-confirmed.",
        "cve_sunrise":
            "Choppy seasonal shape; May dip to 50.1 is seasonal. No "
            "Sunrise-specific 2027 maintenance stated.",
        "ipc_blackrod":
            "First oil May 2026. The seasonal baseline only sees about 1 kb/d "
            "of history, so the guided ramp to a 30 kb/d plateau by end 2027 "
            "is NOT in this forecast. Known upside gap.",
        "cve_foster_creek":
            "Apr 2027 dip to 188.4 is seasonal. Q2 2026 turnaround complete; "
            "no 2027 plan stated.",
        "su_firebag":
            "May dip is seasonal (May flagged 5 of 16 years, incl. the 2026 "
            "major turnaround). Next major turnaround is on the stated 5-year "
            "cycle, around 2031.",
        "ath_leismer":
            "May dip is seasonal (May flagged 4 of 9 years). Next routine "
            "turnaround on the stated 4-year frequency, around 2030.",
        "cnq_primrose":
            "Apr 2027: -26 kb/d CADENCE-MODELED turnaround (editorially "
            "approved 2026-09-23; median observed April dip, AER ST53; "
            "Apr flagged 6 of 16 years). WEAK-SIGNAL FLAG: April dip signal "
            "has weakened in 2017-2026 data (3 flags in the last decade); "
            "weakening, not dead. Not company-confirmed.",
        "imo_cold_lake":
            "Q4 2026 turnaround (-3 kb/d, Imperial guidance) is modeled down "
            "at this leaf for Aug-Dec 2026.",
    }
    VINT_ST39 = "AER ST39 actuals through 2026-05, pulled 2026-09-22"
    detail = {}
    for rid, label, depth, kind, lic in rows:
        if kind == "project":
            pid = rid[5:]
            p = pmap[pid]
            leaf = leaves[pid]
            why = PROJ_WHY.get(
                pid,
                f"Seasonal baseline off a {leaf['baseline_trailing12m_kbd']} "
                f"kb/d trailing-12m baseline. No 2027 turnaround statements; "
                f"single-month dips are seasonal factors repeating the last 3 "
                f"years.")
            detail[rid] = {
                "source": "AER ST53, commercial scheme mapping (Heavy Reading project roster)",
                "vintage": VINT_ST53,
                "method": ("actuals: ST53 scheme observed, grossed up by "
                           f"{gross:.2f} to ST3 in-situ level (mapped projects cover "
                           f"{coverage:.1%}). " + METH_FC + "."),
                "why": why,
                "extra": (f"Type: {leaf['type'].upper()}. Operator: {p['operator']}."),
            }
        elif kind == "plant":
            key = rid.split("_", 1)[1]
            if rid.startswith("scoplant_"):
                key = rid[len("scoplant_"):]
            line_lab = ("upgraded production (SCO)"
                        if rid.startswith("scoplant_") else "mined bitumen")
            note = (plant_note_sco[key] if rid.startswith("scoplant_")
                    else plant_note_mb[key])
            detail[rid] = {
                "source": "AER ST39, oil-sands plant data (mined bitumen and SCO by facility)",
                "vintage": VINT_ST39 + "; forecast " + VINT_FC,
                "method": ("actuals: ST39 plant reported. forecast: "
                           + note
                           + ", scaled pro-rata to tie to the ST3 "
                           + line_lab + " line."),
                "why": (f"{PLANT_OP[key]} facility. Actuals through 2026-05; "
                        "Jun-Jul 2026 are blank until AER publishes them. The "
                        "forecast repeats this plant's own seasonality; the "
                        "pro-rata scaling only changes the level so the "
                        "drill-down ties to the approved aggregate."),
                "extra": "",
            }
        elif kind == "grade":
            detail[rid] = {
                "source": GRADE_SOURCE[rid],
                "vintage": VINT_ACT + "; " + VINT_FC,
                "method": GRADE_METHOD[rid],
                "why": WHY.get(rid, ""),
                "extra": GRADE_LEAF_MAP[rid],
            }
        elif kind in ("line",):
            detail[rid] = {
                "source": "AER ST3" if rid in BSB.ST3_LEAVES else "WCSB S&D model",
                "vintage": (VINT_ACT + "; " + VINT_FC) if rid in BSB.ST3_LEAVES else VINT_FC,
                "method": ("actuals: reported. " + METH_FC + "."
                           if rid in BSB.ST3_LEAVES else
                           "model identity / maintenance calendar; see methodology."),
                "why": WHY.get(rid, ""),
                "extra": "",
            }
        else:
            detail[rid] = {
                "source": "WCSB S&D model (sums of child rows)",
                "vintage": VINT_ACT + "; " + VINT_FC,
                "method": "Sum of child rows. In-situ children grossed up by "
                          f"{gross:.2f} to reconcile to the ST3 in-situ line.",
                "why": WHY.get(rid, ""),
                "extra": "",
            }

    # ---- aggregate maint row points at the Maintenance tab for event detail ----
    detail["maint"]["why"] = (detail["maint"]["why"]
                              + ' Per-event detail lives on the <a href="maintenance/index.html">'
                                'Maintenance tab</a>.')
    # ---- leaf-level maintenance notes on the deducted leaves ----
    LEAF_MAINT_NOTES = {
        "scoplant_CNRL HORIZON OIL SANDS PROJECT":
            "Maintenance modeled down at this leaf: Horizon 35-day turnaround "
            "(started Sep 8 2026). Sep 2026 -230 kb/d (September bridge per "
            "editorial ruling 2026-09-22 on CNRL 2026 budget guidance); Oct 2026 "
            "-119 kb/d (Oct 1-12 residual tail). Pure upgrader outage: SCO "
            "needs no blending, so the cut reduces tradable synthetic barrels "
            "1:1. Source: CNRL 2026 budget (2025-12-16), final ruling by Blaine "
            "2026-09-24. The Maintenance offline memo row shows the same "
            "outage for reference; it is not subtracted again.",
        "scoplant_SYNCRUDE MILDRED LAKE":
            "Maintenance modeled down at this leaf: Syncrude Coker 8-2 "
            "turnaround (planned start Aug 20 2026, about 50 days). Aug 2026 "
            "-29.8 kb/d (Aug 20-31, 77 x 12/31), Sep 2026 -77.0 kb/d (full "
            "month), Oct 2026 -22.4 kb/d (Oct 1-9 tail, 77 x 9/31). Source: "
            "Suncor Q2 2026 MD&A (2026-08-04), Q1 2026 investor presentation. "
            "The paired mine dial-back (Aug -35.4, Sep -91.4, Oct -26.6 "
            "kb/d bitumen) is an operational note only, not modeled down "
            "(final ruling by Blaine 2026-09-24: no interconnect redirect "
            "in a planned turnaround, zero heavy-market impact). SCO market "
            "impact is the gross coker rate: Sep 2026 -77.0 kb/d.",
        "plant_SYNCRUDE MILDRED LAKE":
            "Operational note only (final ruling by Blaine 2026-09-24): "
            "Syncrude Coker 8-2 mine dial-back, Aug 2026 -35.4, Sep 2026 "
            "-91.4, Oct 2026 -26.6 kb/d bitumen (full bitumen-equivalent of "
            "the coker rate at the observed 0.843 Syncrude yield: the mine "
            "plan is set months ahead to match reduced upgrader demand). NOT "
            "modeled down at this leaf: the Coker 8-2 market impact is on "
            "synthetic crude only (Sep 2026 -77.0 kb/d gross coker rate, no "
            "interconnect redirect); heavy-market impact is zero. The paired "
            "upgrader leaf carries the SCO deduction.",
        "plant_SUNCOR ENERGY OSG":
            "Maintenance modeled down at this leaf: Suncor Base Plant Q4 "
            "bitumen maintenance, Nov 2026 -15 kb/d (quarterly event-rate; "
            "timing within Q4 unpublished, placed mid-quarter). Source: "
            "Suncor 2026 planned maintenance table (Q1 2026 investor "
            "presentation, 2026-04-01).",
        "scoplant_SUNCOR ENERGY OSG":
            "Maintenance modeled down at this leaf: Suncor Base Plant Q4 SCO "
            "and diesel maintenance, Nov 2026 -5 kb/d. Source: Suncor 2026 "
            "planned maintenance table (Q1 2026 investor presentation, "
            "2026-04-01).",
        "proj_imo_cold_lake":
            "Maintenance modeled down at this leaf: Imperial Cold Lake "
            "3Q/4Q 2026 turnaround, -3 kb/d Aug-Dec 2026 (annualized guidance "
            "rate). Source: Imperial 2026 corporate guidance (via Oil Sands "
            "Magazine 2026-01-15).",
        "proj_cve_christina_lake":
            "Maintenance modeled down at this leaf: Christina Lake F/G "
            "turnaround tail, Oct 2026 -20 kb/d. ASSUMED model carry, not "
            "company-stated: Cenovus Q2 2026 results (2026-07-29) state no Oil "
            "Sands maintenance planned in Q4 2026, and the next F/G turnaround "
            "is guided for 2031.",
        "proj_su_mackay_river":
            "Maintenance modeled down at this leaf: MacKay River September "
            "2027 turnaround, -12 kb/d (CADENCE-MODELED, editorially approved "
            "2026-09-23; median of observed September dips 5.4-33.2 kb/d, "
            "median 12.2, in the AER ST53 seasonal dip analysis, vintage "
            "July 2026, retrieved 2026-09-23). In the numbers and labeled "
            "CADENCE-MODELED everywhere; never presented as company-confirmed. "
            "No 2027 company statement exists.",
        "proj_cnq_primrose":
            "Maintenance modeled down at this leaf: Primrose/Wolf Lake April "
            "2027 turnaround, -26 kb/d (CADENCE-MODELED, editorially approved "
            "2026-09-23; median of observed April dips in the AER ST53 "
            "seasonal dip analysis, vintage July 2026, retrieved 2026-09-23). "
            "WEAK-SIGNAL FLAG: April dip signal has weakened in 2017-2026 "
            "data (3 flagged years in the last decade vs 6/16 over the long "
            "record); weakening, not dead. In the numbers and labeled "
            "CADENCE-MODELED everywhere; never presented as company-confirmed. "
            "No 2027 company statement exists.",
    }
    for _rid, _note in LEAF_MAINT_NOTES.items():
        detail[_rid]["why"] = (detail[_rid].get("why", "") + " " + _note).strip()
        detail[_rid]["method"] = (detail[_rid].get("method", "")
                                  + " Confirmed maintenance is deducted at "
                                    "this leaf after the baseline (see Why).")
    LEAF_GROWTH_NOTES = {
        "proj_cve_christina_lake":
            "Growth modeled up at this leaf: Christina Lake North expansion "
            "ramp, +4.1 kb/d Oct 2026 rising linearly to +23.4 kb/d Dec 2027 "
            "(+40 kb/d by Dec 2028). Source: Cenovus Q1 2026 results news "
            "release (2026-05-06). Editorially approved 2026-09-23.",
        "proj_cve_sunrise":
            "Growth modeled at this leaf: Sunrise held at 70.0 kb/d flat "
            "across forecast months (replaces the declining seasonal "
            "baseline). Source: Cenovus Q1 2026 results news release "
            "(2026-05-06): production ramping towards 70,000 bbl/d by 2028. "
            "Editorially approved 2026-09-23.",
        "proj_ath_leismer":
            "Growth modeled up at this leaf: Leismer expansion ramp, +1.5 "
            "kb/d Oct 2026 rising linearly to +8.5 kb/d Dec 2027 (+0.5 "
            "kb/d per month from Jul 2026, landing on 40.0 kb/d by Dec "
            "2027). Source: Athabasca Oil 2026 budget news release "
            "(2025-12-11), confirmed on track in the Q2 2026 press release "
            "(2026-07-29). Editorially approved 2026-09-23.",
        "proj_ipc_blackrod":
            "Growth modeled up at this leaf: Blackrod Phase 1 ramp, +5.4 "
            "kb/d Oct 2026 rising linearly to +28.6 kb/d Nov 2027, plateau "
            "held through Dec 2027, landing on the 30 kb/d plateau. First oil May 31, 2026; "
            "plateau guided a quarter earlier than originally planned. "
            "Source: IPC operational update. Editorially approved 2026-09-23.",
        "scoplant_CNRL HORIZON OIL SANDS PROJECT":
            "Growth modeled up at this leaf: Horizon NRUTT (Naphtha Recovery "
            "Unit Tailings Treatment) +6.3 kb/d SCO step change from Jul 2027, "
            "persisting through the Dec 2027 window end. Source: CNRL "
            "2026 budget news release (2025-12-16). Editorially approved "
            "2026-09-23. The implied ~277,300 bbl/d post-NRUTT nameplate is "
            "not used: demonstrated ST39 peak is 309.8 kb/d SCO (2025-11) "
            "and history wins, so only the +6.3 increment is modeled.",
    }
    for _rid, _note in LEAF_GROWTH_NOTES.items():
        detail[_rid]["why"] = (detail[_rid].get("why", "") + " " + _note).strip()
    NC_LINE = ("Seasonal baseline (_seasonal_baseline), built 2026-09-23. "
               "Known maintenance events are now deducted at the affected "
               "project/plant leaves; the Maintenance offline line is a memo "
               "of those deductions.")
    NC_SUM = "Sum of child nowcasts; ties by construction."
    NC_WHY = {
        "supply_total":
            "Sum of the in-situ, mined-group, and conventional nowcasts; ties by construction.",
        "in_situ": NC_SUM, "sagd": NC_SUM, "css": NC_SUM,
        "in_situ_unmapped":
            "Zero by construction: the grossed-up mapped projects are the in-situ nowcast.",
        "mined_grp":
            "Mined bitumen plus sent-for-further-processing plus SCO nowcasts; ties by construction.",
        "conv": NC_SUM,
        "diluent":
            "Condensate plus pentanes-plus import nowcasts; ties by construction.",
        "ab_use_other":
            "Alberta-use nowcast minus refinery-sales nowcast; ties by construction.",
        "resid_mined":
            "Mined-bitumen nowcast minus the scaled ST39 plant nowcasts; ties by construction.",
        "resid_sco":
            "SCO nowcast minus the scaled ST39 upgrader nowcasts; ties by construction.",
        "maint":
            "Aug 2026 nowcast 32.8 kb/d offline: Syncrude Coker 8-2 Aug 20-31 "
            "(77 kb/d event rate x 12/31 days = 29.8) plus Cold Lake Q3 turnaround "
            "-3 (Imperial guidance). Sep 2026 nowcast 310.0 kb/d offline: Horizon "
            "-230 (September bridge of the Sep 8 35-day turnaround, per editorial ruling "
            "2026-09-22), Coker 8-2 full month -77.0, Cold Lake -3. No other "
            "confirmed events fall in the gap; Suncor Base Plant Q4 cuts sit in "
            "Oct-Dec only. MEMO: these outages are modeled down at the leaves "
            "and this line is not subtracted in the storage identity.",
        "stor_chg":
            "Physical identity on nowcast inputs: supply total plus diluent "
            "imports minus Alberta use minus removals. Maintenance outages are "
            "embedded in the nowcast leaves; the maint line is a memo, not "
            "subtracted. Negative means a draw from commercial storage.",
        "grade_conv_light":
            "Light + condensate nowcasts; ties by construction.",
        "grade_conv_sour":
            "Medium nowcast; ties by construction.",
        "grade_conv_heavy":
            "Heavy + ultra-heavy nowcasts; ties by construction.",
        "grade_sco":
            "Carries the upgraded-production nowcast; the Coker 8-2 gross "
            "SCO deduction is at the Syncrude upgrader leaf (no "
            "interconnect redirect in a planned turnaround).",
        "grade_dilbit":
            "Mined + in-situ - |sent for further processing| on nowcast "
            "inputs; the Coker mine dial-back is in the Syncrude mined leaf.",
        "grade_total":
            "Lights + sours + heavy conventional + SCO + dilbit nowcasts; "
            "ties to Total WCSB crude supply.",
        "imo_cold_lake":
            "Seasonal baseline; the Q3/Q4 turnaround (-3 kb/d, Imperial "
            "guidance) is modeled down at this leaf for Aug and Sep.",
    }
    for rid in list(detail):
        if rid in NC_WHY:
            detail[rid]["nowcast"] = NC_WHY[rid]
        elif rid.startswith("proj_"):
            pid = rid[5:]
            detail[rid]["nowcast"] = NC_WHY.get(
                pid, "Seasonal baseline only; no confirmed maintenance events "
                     "affect this project in Aug-Sep 2026.")
        elif rid.startswith("plant_") or rid.startswith("scoplant_"):
            key = rid.split("_", 1)[1]
            if rid.startswith("scoplant_"):
                key = rid[len("scoplant_"):]
            if key == "CNRL HORIZON OIL SANDS PROJECT":
                detail[rid]["nowcast"] = (
                    "Sep nowcast is this plant's seasonal baseline minus the "
                    "Sep 8 turnaround's -230 kb/d September impact, modeled "
                    "down at this leaf (see the maintenance note in Why).")
            elif rid == "scoplant_SYNCRUDE MILDRED LAKE":
                detail[rid]["nowcast"] = (
                    "Coker 8-2 SCO impacts (Aug -29.8, Sep -77.0 kb/d) are "
                    "modeled down at this upgrader leaf, not carried "
                    "separately.")
            elif rid == "plant_SYNCRUDE MILDRED LAKE":
                detail[rid]["nowcast"] = (
                    "Coker 8-2 mine dial-back (Aug -35.4, Sep -91.4, "
                    "Oct -26.6 kb/d bitumen, full bitumen-equivalent of the "
                    "coker rate at the observed 0.843 Syncrude yield) is an "
                    "operational note only at this mined-bitumen leaf, not "
                    "modeled down (Blaine ruling 2026-09-24: zero "
                    "heavy-market impact).")
            elif rid == "scoplant_SUNCOR ENERGY OSG":
                detail[rid]["nowcast"] = (
                    "No Coker 8-2 effect at this leaf: the interconnect "
                    "redirect was removed per Blaine's final ruling "
                    "2026-09-24 (planned turnaround, mine plan set months "
                    "ahead, no hungry upgrader). Seasonal baseline only.")
            else:
                detail[rid]["nowcast"] = (
                    "Seasonal baseline, scaled pro-rata to tie to the ST3 line "
                    "nowcast. No confirmed maintenance events affect this plant "
                    "in Aug-Sep 2026.")
        elif rid.startswith("grade_"):
            detail[rid]["nowcast"] = NC_WHY[rid]
        else:
            detail[rid]["nowcast"] = NC_LINE
        detail[rid]["vintage"] = detail[rid]["vintage"] + "; " + VINT_NC

    data = {
        "built": "2026-09-23",
        "act_months": ACT_MONTHS,
        "gap_months": GAP_MONTHS,
        "fc_months": FC_MONTHS,
        "gross_up": round(gross, 4),
        "coverage": coverage,
        "leaf_maint": {rid: dict(s) for rid, s in LEAF_MAINT.items()},
        # Closing-inventory history, million barrels (AER ST3 actuals) --
        # feeds the Balance page implied-storage level chart.
        "inventory_mm_bbl": INV_MM_BBL,
        # The plug: AER reporting_adjustment forecast, trailing-12m mean
        # kb/d, recomputed each build (used for gap months; forecast months
        # carry sd_balance.json's own identical-method value).
        "plug_kbd": PLUG_KBD,
        "rows": [
            {"id": rid, "label": label, "depth": depth, "kind": kind,
             "license": lic, "values": V[rid], "detail": detail[rid]}
            for rid, label, depth, kind, lic in rows
        ],
    }
    (BASE / "st3_dashboard.json").write_text(json.dumps(data, indent=1))

    page = render_page(data)
    (SITE / "st3-dashboard.html").write_text(page)
    print(f"wrote {SITE / 'st3-dashboard.html'} "
          f"({len(data['rows'])} rows, {len(ALL_MONTHS)} months)")


def act_line(cid, act, ym):
    return act[cid][ym]


def esc(t):
    return html.escape(str(t), quote=False)


PAGE_CSS = """
/* ---- Heavy Reading design system (dashboard) ----
   Same tokens as shared PAGE_CSS: Fraunces display + Inter UI, neutrals +
   one brand accent. Data-table semantics preserved: sticky band headers,
   sticky row labels, maintenance highlights, detail drawers. ---- */
:root {
  --ink:#1e1b16; --mut:#6f675b; --faint:#a79d8d;
  --line:#e6e1d4; --line2:#f0ece1; --wash:#faf8f4; --paper:#faf8f4;
  --acc:#a13c22; --acc-deep:#7c2e1a;
  --band-trad:#5a7a5e;
  --ncbg:#efe6cf; --fcbg:#e7ebee; --tradbg:#e9ede9;
  --d-nc:#e9dfc2; --d-nc-sub:#efe5cb;
  --d-trad:#e2eee2; --d-trad-sub:#e8f2e8;
  --d-fc:#e7edf9; --d-fc-sub:#edf1f9;
  --d-subagg:#f5f1e8; --d-detail:#fffdf6;
  --serif:"Fraunces",Georgia,"Times New Roman",serif;
  --sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Helvetica,Arial,sans-serif;
}
/* Dark: warm charcoal, never pure black. Table band washes deepen instead
   of inverting, so the vintage semantics survive the theme. */
[data-theme="dark"] {
  --ink:#ece6d9; --mut:#a89d89; --faint:#7e7565;
  --line:#38332b; --line2:#2c2822; --wash:#201d18; --paper:#201d18;
  --acc:#cf7150; --acc-deep:#e08a63;
  --band-trad:#7ba37f;
  --ncbg:#2c2820; --fcbg:#222a31; --tradbg:#1f2c22;
  --d-nc:#3a3220; --d-nc-sub:#322c1e;
  --d-trad:#1f2c22; --d-trad-sub:#1c2820;
  --d-fc:#202b36; --d-fc-sub:#1e2833;
  --d-subagg:#26221b; --d-detail:#241f18;
}
* { box-sizing:border-box; }
html { -webkit-text-size-adjust:100%; }
::selection { background:rgba(161,60,34,.16); }
:focus-visible { outline:2px solid var(--acc); outline-offset:3px; border-radius:2px; }
body { font-family:var(--sans); color:var(--ink); line-height:1.65; margin:0;
       background:var(--paper); font-size:16px; font-variant-numeric:tabular-nums;
       font-feature-settings:"pnum" on, "lnum" on, "liga" on; }
.wrap { max-width:1200px; margin:0 auto; padding:0 18px 64px; }
html, body { overflow-x:clip; }

/* masthead: brand lockup + magazine section bar. Nothing else above the brand. */
.masthead { position:relative; }
.themetoggle { position:absolute; top:2px; right:0; background:none; border:0;
  padding:6px 2px; font:inherit; font-size:12px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--faint); cursor:pointer; }
.themetoggle:hover { color:var(--acc); }
.brandlock { padding:26px 0 6px; }
.brandlink { display:inline-flex; align-items:center; gap:14px; text-decoration:none;
  color:var(--ink); }
.mark { width:40px; height:40px; display:block; flex:none; }
.wordstack { display:flex; flex-direction:column; }
.wordmark { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:32px; letter-spacing:-0.02em; line-height:1; }
.wordsub { font-size:10.5px; letter-spacing:.24em; text-transform:uppercase;
  color:var(--mut); margin-top:7px; font-weight:600; }
/* section nav: shared dropdown pattern (mirrors shared PAGE_CSS) */
.mnav { display:block; margin:0; padding:0; border:0; }
.mnav > summary { list-style:none; }
.mnav > summary::-webkit-details-marker { display:none; }
.mnav > summary::marker { content:""; }
.navburger { display:none; }
.sitenav { display:flex; gap:0; border-top:1px solid var(--ink);
  border-bottom:1px solid var(--line); margin:18px 0 0; }
.navdrop { position:relative; }
.nd > summary { list-style:none; display:flex; align-items:center; cursor:pointer; }
.nd > summary::-webkit-details-marker { display:none; }
.nd-top { color:var(--ink); text-decoration:none; font-size:12px; font-weight:600;
  letter-spacing:.1em; text-transform:uppercase; padding:15px 16px 13px;
  white-space:nowrap; border-bottom:2px solid transparent; margin-bottom:-1px; }
.nd-caret { display:inline-block; width:0; height:0; margin:1px 14px 0 -8px;
  border-left:4px solid transparent; border-right:4px solid transparent;
  border-top:5px solid var(--faint); flex:none; }
@media (hover:hover) {
  .nd-menu .mi:hover { color:var(--acc-deep); }
  .nd-top:hover { color:var(--acc-deep); }
}
.navdrop.active .nd-top { border-bottom-color:var(--acc); }
.nd-menu { display:none; position:absolute; top:100%; left:0; z-index:50;
  background:var(--paper); border:1px solid var(--line); padding:6px; min-width:230px;
  max-width:calc(100vw - 32px); }
.navdrop:last-child .nd-menu, .navdrop:nth-last-child(2) .nd-menu {
  left:auto; right:0; }
.nd:hover .nd-menu, .nd[open] .nd-menu { display:block; }
.nd-menu .mi { display:block; color:var(--ink); text-decoration:none;
  font-size:14px; padding:8px 12px; white-space:nowrap; }
.nd-menu .mi[aria-current="page"] { font-weight:700; }
.nd-megahead .mi { font-weight:600; }
.nd-mega { display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
  gap:4px 10px; min-width:600px; padding:4px 0 2px; }
.mcol .mcat { display:block; font-size:11px; font-weight:700; letter-spacing:.1em;
  text-transform:uppercase; color:var(--acc); text-decoration:none;
  padding:8px 12px 3px; }
.mcol .mi.small { font-size:12.5px; padding:5px 12px; white-space:normal; }
.masthead h1 { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:clamp(2.4rem, 1.75rem + 3.2vw, 3.5rem); line-height:1.03;
  letter-spacing:-0.022em; margin:30px 0 14px; text-wrap:balance; max-width:20ch; }
.sub { color:var(--mut); font-size:15px; margin:0 0 12px; max-width:68ch; line-height:1.6; }
.edition { font-size:12.5px; font-weight:600; margin:0 0 8px; letter-spacing:.02em; }
a { color:var(--ink); text-decoration:underline; text-decoration-color:#cfc8b8;
    text-decoration-thickness:1px; text-underline-offset:3px; }
a:visited { color:var(--ink); }
a:hover { color:var(--acc-deep); text-decoration-color:var(--acc); }
.sitenav a, .sr-hit, h1 a, h2 a { text-decoration:none; }
/* site search (masthead) */
.searchbox { position:relative; margin:14px 0 0; }
.searchbox input { width:100%; max-width:340px; padding:9px 12px; font-size:14px;
  font-family:var(--sans); border:1px solid var(--line); border-radius:0;
  background:var(--paper); color:var(--ink); }
.searchres { position:absolute; top:100%; left:0; width:min(430px,100%);
  background:var(--paper); border:1px solid var(--line);
  z-index:70; margin-top:4px; overflow:hidden; text-align:left; }
.sr-hit { display:block; padding:10px 14px; text-decoration:none;
  color:var(--ink); border-bottom:1px solid var(--line2); }
.sr-hit:last-child { border-bottom:none; }
.sr-hit b { display:block; font-size:14px; }
.sr-hit span { display:block; font-size:12.5px; color:var(--mut); margin-top:2px; }
.sr-none { padding:12px 14px; font-size:13px; color:var(--mut); }
/* data vintage: one discreet disclosure instead of the pill wall */
details.vintage { margin:2px 0 6px; }
details.vintage > summary { cursor:pointer; font-size:12.5px; color:var(--mut);
  list-style:none; display:inline-block; padding:4px 0; }
details.vintage > summary::-webkit-details-marker { display:none; }
details.vintage > summary::before { content:"+ "; font-weight:700; }
details.vintage[open] > summary::before { content:"\2013  "; }
details.vintage ul { margin:8px 0 4px; padding-left:18px; font-size:12.5px;
  color:var(--mut); }
details.vintage li { margin:3px 0; }
details.vintage li b { color:var(--ink); font-weight:600; }
/* site footer (shared with the section pages) */
.sitefoot { margin-top:56px; padding-top:26px; border-top:1px solid var(--ink); }
.fcols { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:20px; }
.fcol h4 { font-size:11.5px; letter-spacing:.14em; text-transform:uppercase;
  margin:0 0 8px; color:var(--mut); font-weight:700; }
.fcol a { display:block; font-size:14px; color:var(--ink); text-decoration:none;
  padding:4px 0; }
.fcol a:hover { text-decoration:underline; }
.fcolophon { font-size:13px; color:var(--mut); margin:22px 0 0; max-width:76ch; }
.fcolophon a { color:var(--ink); }
/* quarterly maintenance: scannable event lists, not paragraph walls */
.qev { margin:8px 0 20px; padding-left:20px; }
.qev > li { margin:9px 0; font-size:14.5px; }
.qev .qnote { font-size:13px; color:var(--mut); }

/* executive panel: a red hairline, not a box (matches the section pages) */
.exec { margin:28px 0; padding:2px 0 2px 20px; border-left:2px solid var(--acc); }
.exec h2 { font-family:var(--sans); font-size:11px; font-weight:700; letter-spacing:.18em;
  text-transform:uppercase; color:var(--acc); margin:0 0 10px; }
.exec ul { margin:0; padding-left:20px; max-width:70ch; }
.exec li { margin:7px 0; font-size:15px; line-height:1.6; }
.exec li::marker { color:var(--acc); }
.exec .exec-vint { font-size:12px; color:var(--mut); margin:10px 0 0; }

/* controls */
.controls { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:18px 0 14px; }
.btn { font-family:var(--sans); font-size:13px; font-weight:600; min-height:40px; padding:8px 14px;
       border:1px solid var(--line); border-radius:0; background:var(--paper); color:var(--ink); cursor:pointer; }
.btn:hover { border-color:var(--ink); }
.btn.on { border-color:var(--ink); }
.btn.primary { background:var(--ink); color:var(--paper); }
.btn.primary:hover { border-color:var(--ink); background:var(--acc-deep); }
.legend { font-size:12px; color:var(--mut); display:flex; flex-wrap:wrap; align-items:center; gap:2px 4px; }
.legend .sw { display:inline-block; width:12px; height:12px; border:1px solid var(--line);
              border-radius:2px; vertical-align:-1px; margin:0 4px 0 10px; }

/* data table: quiet band headers. The vintage bands read as ink text on the
   same light tints as their columns (no white-on-solid terminal headers);
   the one strong rule is the ink hairline under the month row. */
.tblwrap { overflow-x:auto; border:1px solid var(--line);
           -webkit-overflow-scrolling:touch;
  background:
    linear-gradient(to right, var(--paper) 30%, rgba(250,247,240,0)),
    linear-gradient(to right, rgba(250,247,240,0), var(--paper) 70%) 100% 0,
    radial-gradient(farthest-side at 0 50%, rgba(30,27,22,.13), rgba(30,27,22,0)),
    radial-gradient(farthest-side at 100% 50%, rgba(30,27,22,.13), rgba(30,27,22,0)) 100% 0;
  background-repeat:no-repeat;
  background-size:44px 100%, 44px 100%, 16px 100%, 16px 100%;
  background-attachment:local, local, scroll, scroll; }
/* tbox: tall scrollbox: the two header rows stick on vertical scroll and the
   corner cells pin on both axes above the sticky row labels. */
.tblwrap.tbox { overflow:auto; max-height:min(78vh, 860px); }
table.data { border-collapse:separate; border-spacing:0; font-size:13px; min-width:100%; }
/* Fixed layout for the ST3 grid (Blaine 2026-09-24): column widths come from
   the server-rendered colgroup (172px labels, 68px months). This keeps the
   sticky date header (vertical scroll) and sticky row labels (horizontal
   scroll) working at phone width. */
.tblwrap.tbox table.data { table-layout:fixed; }
table.data thead th { position:sticky; background:var(--paper); color:var(--ink); z-index:3;
                      padding:8px; font-size:11px; font-weight:700; white-space:nowrap;
                      letter-spacing:.04em; }
table.data thead tr.band th { top:0; height:38px; padding:4px 8px; font-size:11px;
  letter-spacing:.09em; text-transform:uppercase; }
table.data thead tr.months th { top:38px; border-bottom:1px solid var(--ink); }
table.data thead th.rowhead { background:var(--paper); z-index:6; left:0;
  box-shadow:1px 0 0 var(--line2); }
table.data thead th.fcband { background:var(--fcbg); }
table.data thead th.ncband { background:var(--ncbg); }
table.data thead th.tradband { background:var(--tradbg); }
/* sticky first column: row labels (th.rowlab in tbody; td.rowlab kept for safety).
   Placed before the agg rules so aggregate backgrounds still win. */
table.data th.rowlab, table.data td.rowlab { position:sticky; left:0; background:var(--paper); z-index:2;
                      text-align:left; min-width:172px; max-width:232px; white-space:normal; }
table.data td, table.data th.month { text-align:right; font-variant-numeric:tabular-nums;
                      padding:8px 10px; border-bottom:1px solid var(--line2); white-space:nowrap; }
table.data td.nc { background:var(--ncbg); }
table.data td.fc { background:var(--fcbg); }
table.data td.trad { background:var(--tradbg); }
table.data td.trad-first, table.data thead th.trad-first { border-left:3px solid var(--band-trad); }
/* maintenance outage highlight: deliberate warm orange on nonzero cells in the
   maintenance subtree and on every deducted leaf cell. After the band rules so
   it wins at equal specificity. */
table.data td.mx { background:rgba(161,60,34,.10); color:var(--ink); font-weight:700; }
/* badge on a deducted leaf cell: the kb/d hit, tap to open the detail */
.mhit { display:inline-block; font-size:11px; line-height:1.2;
        background:none; color:var(--acc); padding:0; margin-left:8px;
        font-weight:700; cursor:pointer; vertical-align:1px; white-space:nowrap; }
tr.agg td.nc { background:var(--d-nc); }
tr.subagg td.nc { background:var(--d-nc-sub); }
tr.agg td.trad { background:var(--d-trad); }
tr.subagg td.trad { background:var(--d-trad-sub); }
tr.agg td, tr.agg th.rowlab { font-weight:700; background:var(--wash); }
tr.agg td.fc { background:var(--d-fc); }
tr.subagg td, tr.subagg th.rowlab { font-weight:600; background:var(--d-subagg); }
tr.subagg td.fc { background:var(--d-fc-sub); }
tr.d2 th.rowlab, tr.d2 td.rowlab { padding-left:12px; }
tr.d3 th.rowlab, tr.d3 td.rowlab { padding-left:24px; }
/* expand/collapse affordance: a real 44px tap target on phones */
.tgl { cursor:pointer; user-select:none; color:var(--acc); font-weight:700;
       display:inline-flex; align-items:center; justify-content:center;
       min-width:44px; min-height:44px; font-size:17px; line-height:1;
       border:1px solid var(--line); border-radius:8px; background:var(--wash);
       margin-right:8px; vertical-align:middle; }
/* row-name tap area for the detail drawer */
.leaf { cursor:pointer; display:inline-block; padding:10px 2px; vertical-align:middle; }
tr.detail td { background:var(--d-detail); border-bottom:2px solid var(--acc); font-size:12.5px;
               color:#33302a; white-space:normal; text-align:left; padding:12px 14px 12px 16px; }
tr.detail td b { display:inline-block; min-width:72px; }
/* Drawer text must stay readable at phone width wherever the table is
   scrolled horizontally (Blaine 2026-09-24): the sticky wrapper pins to the
   visible left edge and wraps, instead of running the full table width. */
tr.detail td .detwrap { position:sticky; left:0; width:calc(100vw - 48px);
               max-width:780px; }
tr.hidden { display:none; }
.lic-tag { font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
           color:var(--acc); margin-left:8px; white-space:nowrap; }
.vintage-inline { font-size:11px; color:var(--mut); }

/* KPI strip: four quiet stats between the call and the table */
.statgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px; background:var(--line); border:1px solid var(--line); margin:6px 0 22px; }
.stat { background:var(--paper); padding:14px 16px 12px; }
.stat .k { font-size:10.5px; font-weight:700; letter-spacing:.09em; text-transform:uppercase;
  color:var(--mut); margin-bottom:6px; }
.stat .v { font-size:26px; font-weight:650; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums; line-height:1.1; }
.stat .s { font-size:12px; color:var(--mut); margin-top:5px; line-height:1.5; }

/* footer */
.foot { font-size:12.5px; color:var(--mut); margin-top:24px; }
.foot h2 { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:clamp(1.4rem, 1.2rem + 1vw, 1.65rem); letter-spacing:-0.015em; line-height:1.2;
  margin:3rem 0 1rem; padding-top:1.4rem; border-top:1px solid var(--line);
  text-wrap:balance; }
.foot h3 { font-family:var(--serif); font-optical-sizing:auto; font-weight:560;
  font-size:1.18rem; letter-spacing:-0.01em; line-height:1.3; margin:1.8rem 0 .55rem; }
.foot p { max-width:80ch; }
dl.assumps { margin:8px 0 0; }
dl.assumps dt { font-weight:700; margin:10px 0 2px; color:var(--ink); }
dl.assumps dd { margin:0 0 0 16px; color:#3a352c; }
.foot p.qnote { font-style:italic; }
.foot table.src { border-collapse:collapse; width:100%; font-size:12px; margin-top:8px; }
.foot table.src th, .foot table.src td { border:1px solid var(--line); padding:8px;
               text-align:left; vertical-align:top; }
.foot table.src th { background:var(--wash); font-size:11px; text-transform:uppercase;
  letter-spacing:.06em; color:var(--mut); }
.backlink { font-size:13px; margin:16px 0 0; }
.backlink a { color:var(--acc); }

@media (max-width:600px) {
  .wrap { padding:0 14px 56px; }
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
    .nd { border-bottom:1px solid var(--line); }
    .nd-top { padding:14px 2px; font-size:13px; }
    .nd-caret { margin-left:auto; margin-right:2px; }
    .nd:hover .nd-menu { display:none; }
    .nd[open] .nd-menu { display:block; position:static; border:none; padding:0 0 12px; }
    .nd-menu .mi { padding:9px 2px; font-size:14.5px; white-space:normal; }
    .nd-mega { grid-template-columns:1fr; min-width:0; gap:0; }
  .wordmark { font-size:26px; }
  .mark { width:34px; height:34px; }
  .masthead h1 { font-size:28px; }
  .fcols { grid-template-columns:repeat(2,1fr); }
  .searchbox input { max-width:none; }
}

@media print {
  body { font-size:12px; }
  .wrap { max-width:none; padding:0 0 24px; }
  .controls, .legend, .mnav, .searchbox, .searchres { display:none; }
  .brandlock { padding:10px 0 2px; }
  .wordmark { font-size:26px; }
  .mark { width:32px; height:32px; }
  .exec { break-inside:avoid; }
  .tblwrap { overflow:visible; border:none; border-radius:0; }
  .tblwrap.tbox { max-height:none; }
  table.data { font-size:10.5px; }
  /* sticky positioning breaks paged output: drop it for print */
  table.data thead th, table.data thead tr.band th, table.data thead tr.months th,
  table.data thead th.rowhead, table.data th.rowlab, table.data td.rowlab { position:static; }
  table.data th.rowlab, table.data td.rowlab { min-width:0; max-width:none; }
  table.data tr { break-inside:avoid; }
  .tgl { min-width:0; min-height:0; border:none; background:none; margin-right:4px; }
  .mhit { min-height:0; }
}
"""

PAGE_JS = """
(function () {
  __LICENSE_DISPLAY_JS__
  var DATA = __DATA__;
  var ROW_LINKS = __ROW_LINKS__; /* dashboard row id -> project page */
  var rowsById = {};
  DATA.rows.forEach(function (r) { rowsById[r.id] = r; });
  var order = DATA.rows.map(function (r) { return r.id; });
  var childrenOf = {};
  var depthOf = {};
  var stack = [];
  DATA.rows.forEach(function (r) {
    while (stack.length && depthOf[stack[stack.length-1]] >= r.depth) stack.pop();
    if (stack.length) {
      var p = stack[stack.length-1];
      (childrenOf[p] = childrenOf[p] || []).push(r.id);
    }
    depthOf[r.id] = r.depth;
    stack.push(r.id);
  });
  function fmt(v) {
    if (v === null || v === undefined) return "";
    return Number(v).toLocaleString("en-US", {minimumFractionDigits:1, maximumFractionDigits:1});
  }
  function monthLabel(ym) {
    var y = ym.slice(0,4), m = +ym.slice(5,7);
    var names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return names[m-1] + " " + y.slice(2);
  }
  function buildHead() {
    var fcCtx = DATA.fc_months.slice(0, 1);
    var fcTrad = DATA.fc_months.slice(1);
    var band = '<tr class="band"><th class="rowhead" rowspan="2">Line (kb/d)</th>' +
      '<th class="actband" colspan="' + DATA.act_months.length + '">ACTUALS</th>' +
      '<th class="ncband" colspan="' + DATA.gap_months.length + '">NOWCAST (EST.)</th>' +
      '<th class="fcband" colspan="' + fcCtx.length + '">OCT 2026: CONTEXT</th>' +
      '<th class="tradband" colspan="' + fcTrad.length + '">TRADABLE FROM NOV 2026</th></tr>';
    var months = '<tr class="months">';
    DATA.act_months.forEach(function (m) { months += '<th class="month">' + monthLabel(m) + '</th>'; });
    DATA.gap_months.forEach(function (m) { months += '<th class="month ncband">' + monthLabel(m) + '</th>'; });
    fcCtx.forEach(function (m) { months += '<th class="month fcband">' + monthLabel(m) + '</th>'; });
    fcTrad.forEach(function (m, i) {
      months += '<th class="month tradband' + (i === 0 ? ' trad-first' : '') + '">' +
        monthLabel(m) + '</th>';
    });
    return band + months + '</tr>';
  }
  /* ids whose nonzero cells get the maintenance highlight: the Maintenance
     offline aggregate row only. Per-event rows were removed 2026-09-24;
     event detail lives on the Maintenance tab. Pattern-indicated rows excluded.
     Leaf-level deductions (DATA.leaf_maint) are highlighted per-cell below. */
  var MAINT_IDS = { maint: 1 };
  function cellVal(r, ym, cls) {
    var v = r.values[ym];
    /* bright highlight on nonzero cells in the maintenance subtree, plus every
       deducted leaf cell; zero, blank, and null cells (incl. the
       pattern-indicated rows) are untouched */
    var mx = MAINT_IDS[r.id] && v !== null && v !== undefined && Number(v) !== 0;
    var lm = (DATA.leaf_maint[r.id] || {})[ym];
    var badge = "";
    if (lm !== undefined) {
      mx = true;
      badge = ' <span class="mhit" data-leaf="' + r.id + '" title="Modeled maintenance offline: ' +
        Number(lm).toFixed(1) + ' kb/d. Tap for source and detail.">-' +
        Number(lm).toFixed(1) + '</span>';
    }
    return '<td class="' + cls + (mx ? " mx" : "") + '">' + fmt(v === undefined ? null : v) + badge + '</td>';
  }
  function rowHtml(r) {
    var kids = childrenOf[r.id] || [];
    var hasKids = kids.length > 0;
    var tgl = hasKids ? '<span class="tgl" data-tgl="' + r.id + '">+</span>'
                      : '<span class="tgl" style="visibility:hidden">+</span>';
    var licTag = r.license && r.license !== "public"
      ? '<span class="lic-tag">' + licenseLabel(r.license) + '</span>' : '';
    var licAttr = r.license && r.license !== "public"
      ? ' data-licensed="' + r.license + '"' : '';
    var cls = "d" + r.depth + (r.kind === "agg" ? " agg" : "") +
              (r.kind === "subagg" ? " subagg" : "") + (hasKids ? "" : " leaf");
    var rlink = ROW_LINKS[r.id];
    var labHtml = rlink ? '<a href="' + rlink + '">' + r.label + '</a>' : r.label;
    var h = '<tr class="' + cls + '" data-row="' + r.id + '"' + licAttr + '>' +
      '<th class="rowlab" scope="row">' + tgl +
      '<span class="leaf" data-leaf="' + r.id + '">' + labHtml + '</span>' + licTag + '</th>';
    DATA.act_months.forEach(function (m) { h += cellVal(r, m, ""); });
    DATA.gap_months.forEach(function (m) { h += cellVal(r, m, "nc"); });
    DATA.fc_months.forEach(function (m, i) {
      h += cellVal(r, m, "fc" + (i === 0 ? "" : " trad") + (i === 1 ? " trad-first" : ""));
    });
    return h + '</tr>';
  }
  function detailHtml(r) {
    var d = r.detail || {};
    var h = '<tr class="detail hidden" data-detail="' + r.id + '"><td colspan="' +
      (DATA.act_months.length + DATA.gap_months.length + DATA.fc_months.length + 1) + '">';
    h += '<div class="detwrap">';
    h += '<b>Source:</b> ' + (d.source || "not stated") + '<br>';
    h += '<b>Vintage:</b> ' + (d.vintage || "not stated") + '<br>';
    h += '<b>Method:</b> ' + (d.method || "not stated");
    if (d.why) h += '<br><b>Why:</b> ' + d.why;
    if (d.nowcast) h += '<br><b>Nowcast Aug-Sep 2026:</b> ' + d.nowcast;
    if (d.extra) h += '<br><b>Note:</b> ' + d.extra;
    return h + '</div></td></tr>';
  }
  function render() {
    document.querySelector("#st3head").innerHTML = buildHead();
    var body = "";
    DATA.rows.forEach(function (r) {
      body += rowHtml(r) + detailHtml(r);
    });
    document.querySelector("#st3body").innerHTML = body;
  }
  function setKidsVisible(id, visible) {
    (childrenOf[id] || []).forEach(function (kid) {
      var tr = document.querySelector('tr[data-row="' + kid + '"]');
      var det = document.querySelector('tr[data-detail="' + kid + '"]');
      if (visible) { tr.classList.remove("hidden"); }
      else {
        tr.classList.add("hidden");
        if (det) det.classList.add("hidden");
        var t = document.querySelector('[data-tgl="' + kid + '"]');
        if (t) t.textContent = "+";
        setKidsVisible(kid, false);
      }
    });
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-tgl]");
    if (t) {
      var id = t.getAttribute("data-tgl");
      var open = t.textContent === "+";
      t.textContent = open ? "-" : "+";
      setKidsVisible(id, open);
      return;
    }
    var l = e.target.closest("[data-leaf]");
    if (l) {
      var det = document.querySelector('tr[data-detail="' + l.getAttribute("data-leaf") + '"]');
      if (det) det.classList.toggle("hidden");
    }
  });
  function expandAll() {
    DATA.rows.forEach(function (r) {
      document.querySelector('tr[data-row="' + r.id + '"]').classList.remove("hidden");
      var t = document.querySelector('[data-tgl="' + r.id + '"]');
      if (t) t.textContent = "-";
    });
  }
  function collapseAll() {
    DATA.rows.forEach(function (r) {
      if (r.depth > 0) {
        document.querySelector('tr[data-row="' + r.id + '"]').classList.add("hidden");
        document.querySelector('tr[data-detail="' + r.id + '"]').classList.add("hidden");
      }
      var t = document.querySelector('[data-tgl="' + r.id + '"]');
      if (t) t.textContent = "+";
    });
  }
  document.querySelector("#collapseAll").addEventListener("click", collapseAll);
  document.querySelector("#expandAll").addEventListener("click", expandAll);
  document.querySelector("#dlCsv").addEventListener("click", function () {
    var cols = ["line_path", "line"].concat(
      DATA.act_months, DATA.gap_months, DATA.fc_months);
    var lines = [cols.join(",")];
    var path = [];
    DATA.rows.forEach(function (r) {
      while (path.length && path[path.length-1].depth >= r.depth) path.pop();
      path.push(r);
      var label = path.map(function (p) { return p.label; }).join(" > ");
      var cells = ['"' + label.replace(/"/g, '""') + '"',
                   '"' + r.label.replace(/"/g, '""') + '"'];
      cols.slice(2).forEach(function (m) {
        var v = r.values[m];
        cells.push(v === null || v === undefined ? "" : v);
      });
      lines.push(cells.join(","));
    });
    var blob = new Blob([lines.join("\\n")], {type: "text/csv"});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "projected_st3_2026-09-23.csv";
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  });
  try {
    if (new URLSearchParams(window.location.search).get("public") === "1") {
      document.querySelectorAll("[data-licensed]").forEach(function (el) {
        el.style.display = "none";
      });
    }
  } catch (e) {}
  render();
  collapseAll();
  /* print: expand the full tree for a complete hard copy, then restore */
  window.addEventListener("beforeprint", expandAll);
  window.addEventListener("afterprint", collapseAll);
})();
"""


def quarterly_maintenance_html():
    """Forward maintenance by quarter, in paragraph form. The kb/d impacts
    are read from the dashboard's own LEAF_MAINT deduction table and the
    sources from the annotation files, so the narrative stays in sync with
    the model automatically."""
    cal = yaml.safe_load(
        (REPO / "annotations/maintenance_forward.yaml").read_text())
    recs = {r["id"]: r for r in cal.get("records", [])}

    lm = LEAF_MAINT
    hz = lm["scoplant_CNRL HORIZON OIL SANDS PROJECT"]  # SCO leaf (ruling 2026-09-24)
    ck = lm["scoplant_SYNCRUDE MILDRED LAKE"]
    sync_mine = SYNCRUDE_MINE_DIALBACK_MEMO  # operational memo only, not a leaf deduction
    sb = lm["plant_SUNCOR ENERGY OSG"]
    su = lm["scoplant_SUNCOR ENERGY OSG"]
    cl = lm["proj_imo_cold_lake"]
    cv = lm["proj_cve_christina_lake"]
    mk = lm["proj_su_mackay_river"]

    def f(v):
        return f"{v:.1f}"

    def li(lead, detail=""):
        d = f' <span class="qnote">{detail}</span>' if detail else ""
        return f"<li><b>{lead}</b>{d}</li>"

    q3_2026 = [
        li(f"Horizon 35-day turnaround: -{f(hz['2026-09'])} kb/d in September",
           "Began September 8 (CNRL 2026 budget guidance, 2025-12-16). "
           "Editorial ruling 2026-09-22 allocated 6,900 kb of the "
           "guidance-implied 10,585 kb to September, at the Horizon SCO leaf "
           "(final ruling by Blaine 2026-09-24: pure upgrader outage, no "
           "blending, straight against tradable synthetic barrels)."),
        li(f"Syncrude Coker 8-2 turnaround: -{f(ck['2026-09'])} kb/d September, "
           f"-{f(ck['2026-08'])} kb/d August",
           "Down since the planned August 20 start (Suncor Q2 2026 MD&A, "
           "2026-08-04; deferred from Q2 per the Imperial Q2 2026 call). "
           "September is a full outage month at the Syncrude Mildred Lake "
           "upgrader leaf; August carries the Aug 20-31 ramp."),
        li(f"Syncrude mine dial-back (operational note): -{f(sync_mine['2026-08'])} kb/d August, "
           f"-{f(sync_mine['2026-09'])} kb/d September",
           "The mine plan is set months ahead to match reduced upgrader "
           "demand: the dial-back is the full bitumen-equivalent of the "
           "coker rate (SCO/0.843). Operational note only (final ruling by "
           "Blaine 2026-09-24): not modeled down at any leaf, no "
           "interconnect redirect; zero heavy-market impact."),
        li(f"Imperial Cold Lake 3Q/4Q turnaround: -{f(cl['2026-08'])} kb/d each month",
           "Imperial 2026 corporate guidance, annualized rate."),
        li("Nowcast, not published data",
           "All August and September figures are nowcast estimates built "
           "2026-09-23, not AER published data."),
    ]
    q4_2026 = [
        li(f"Horizon turnaround tail: -{f(hz['2026-10'])} kb/d in October",
           "October 1-12 residual of the September 8 turnaround at the Horizon "
           "SCO leaf (final ruling by Blaine 2026-09-24; the September bridge is "
           "not double-counted)."),
        li(f"Syncrude Coker 8-2 tail: -{f(ck['2026-10'])} kb/d in October",
           "October 1-9 tail (derived 77 x 9/31; Suncor Q2 2026 MD&A) at the "
           "Syncrude Mildred Lake upgrader leaf, with a mine dial-back of "
           f"-{f(sync_mine['2026-10'])} kb/d bitumen (operational note only, "
           "not modeled down; no interconnect redirect)."),
        li(f"Christina Lake F/G tail: -{f(cv['2026-10'])} kb/d in October",
           "Assumed model carry, flagged as such: Cenovus Q2 2026 results "
           "(2026-07-29) state no Oil Sands maintenance planned in Q4 2026, "
           "and the next F/G turnaround is guided for 2031."),
        li(f"Cold Lake: -{f(cl['2026-10'])} kb/d through the quarter",
           "Imperial 2026 guidance."),
        li(f"Suncor Base Plant Q4 maintenance (November): -{f(sb['2026-11'])} kb/d "
           f"bitumen, -{f(su['2026-11'])} kb/d SCO",
           "Suncor 2026 planned maintenance table, Q1 2026 investor "
           "presentation (2026-04-01). Timing within Q4 is unpublished; the "
           "cuts are placed mid-quarter, on the Suncor OSG mine and upgrader "
           "leaves."),
        li(f"December: Cold Lake -{f(cl['2026-12'])} kb/d only",
           "No other confirmed events fall in Q4 2026."),
    ]
    horizon_2028 = recs.get("fwd_cnq_horizon_2028", {})
    kearl_2029 = recs.get("fwd_imo_kearl_2029", {})
    clfg_2031 = recs.get("fwd_cve_christina_lake_2031", {})
    q1_2027 = [
        li("No confirmed maintenance in the model math for Q1 2027",
           "The forward calendar is quiet."),
        li("Next Horizon turnaround targeted for 2028",
           f"{esc(horizon_2028.get('source_document', 'CNRL 2026 budget'))}, "
           f"{esc(horizon_2028.get('source_date', '2025-12-16'))}."),
        li("Kearl's next planned turnaround is 2029",
           "Per the Imperial Q2 2026 earnings call "
           f"({esc(kearl_2029.get('source_date', '2026-07-31'))})."),
        li("Next Christina Lake F/G turnaround guided for 2031",
           f"Cenovus Q2 2026 call ({esc(clfg_2031.get('source_date', '2026-07-29'))})."),
    ]
    q2_2027 = [
        li("No confirmed or cadence-modeled maintenance in the math for Q2 2027",
           "The forward calendar is quiet: April and May carry no scheduled events."),
    ]
    q3_2027 = [
        li(f"MacKay River September: -{f(mk['2027-09'])} kb/d, CADENCE-MODELED",
           "Editorially approved 2026-09-23: the median of observed September "
           "dips (5.4-33.2 kb/d, median 12.2) in the AER ST53 seasonal dip "
           "analysis (vintage July 2026, retrieved 2026-09-23). Labeled "
           "CADENCE-MODELED everywhere; not company-confirmed, and no 2027 "
           "company statement exists."),
        li("No other confirmed or modeled events fall in Q3 2027"),
    ]
    q4_2027 = [
        li("No confirmed or cadence-modeled events in the math for Q4 2027",
           "Mined and upgrader 2027 calendars are empty pending sourced 2027 "
           "company schedules. Watch for 2028 announcements, including the "
           "targeted 2028 Horizon turnaround (CNRL 2026 budget)."),
    ]
    quarters = [("Q3 2026: nowcast bridge", q3_2026),
                ("Q4 2026", q4_2026),
                ("Q1 2027", q1_2027),
                ("Q2 2027", q2_2027),
                ("Q3 2027", q3_2027),
                ("Q4 2027", q4_2027)]
    out = ['<h2>Forward maintenance by quarter</h2>',
           '<p class="qnote">Planned outages by quarter, generated from the forward '
           'maintenance calendar and the '
           'offline-barrel registry. Outages are '
           'modeled down at the project and plant leaves; the Maintenance offline '
           'row is a memo of those deductions.</p>']
    for title, items in quarters:
        out.append(f"<h3>{esc(title)}</h3>"
                   f'<ul class="qev">{"".join(items)}</ul>')
    return "\n".join(out)


def grade_assumptions_html():
    """Named grade-layer assumptions (approved by Blaine 2026-09-23; grade rows
    rebuilt to the five market streams 2026-09-24).
    The grade rows are computed from the ST3 lines; these assumptions govern
    the Coker 8-2 disposition and the documented leaf-to-grade mapping."""
    items = [
        ("Horizon-style, no interconnect",
         "Symmetric mine/upgrader dial-back. Horizon and Scotford have no "
         "documented third-party interconnects, so their upgrader outages are "
         "modeled as straight dial-backs. Confirmed 2026-09-23."),
        ("Suncor/Syncrude upgrader-only event",
         "Planned turnarounds: the mine plan is set months ahead to match "
         "reduced upgrader demand, so the mine dials back in full "
         "bitumen-equivalent and NO interconnect redirect is modeled "
         "(Coker 8-2 ruling, final 2026-09-24). Unplanned outages: the mine "
         "cannot react in time, so the interconnect relief valve applies: "
         "mine down ~30-60% of the SCO rate, balance redirected via the "
         "interconnect (Q1 2026 precedent)."),
        ("PFT mines (Kearl, Fort Hills)",
         "Output flows to the highest-netback outlet. Proven by Fort Hills "
         "holding output flat (+4%) in Q1 2026 while redirecting 66.9 kb/d "
         "from dilbit sales to Base upgrader feed."),
        ("SAGD",
         "Output unchanged by another asset's upgrader outage; the "
         "upgrader-bound share is assumed diverted to dilbit. MacKay River "
         "held at -5% during the Q2 2026 Suncor upgrader outage."),
        ("Default upgrader yield",
         "0.87 SCO per barrel of bitumen feed. Observed context: fleet "
         "0.865 (ST3, stable 2017-2026), Horizon 0.888, Syncrude 0.843 "
         "(model-computed from AER ST3/ST39, 2026-09-23)."),
        ("Limitations",
         "No project-level SAGD/PFT disposition shares are invented. Where "
         "the ST3 lines cannot support a leaf-level dilbit split, the grade "
         "is the ST3 residual and the leaf split is labeled null, never "
         "plugged."),
    ]
    out = ['<h2>Grade-layer assumptions</h2>',
           '<p class="qnote">Named assumptions behind the grade rows and the '
           'Coker 8-2 disposition. Guidance-sourced and pattern-indicated '
           'maintenance are kept separate throughout.</p>',
           '<dl class="assumps">']
    for name, text in items:
        out.append(f"<dt>{esc(name)}</dt><dd>{esc(text)}</dd>")
    out.append("</dl>")
    return "\n".join(out)


_MNAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MNAMES_FULL = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


def _mname(ym):
    return f"{_MNAMES[int(ym[5:7]) - 1]} {ym[:4]}"


def _edition_date(built):
    # "2026-09-23" -> "September 23, 2026"
    y, m, d = built.split("-")
    return f"{_MNAMES_FULL[int(m) - 1]} {int(d)}, {y}"


def _f1(v):
    return f"{v:,.1f}"


def exec_panel_html(data, max_bullets=5, more_href=None):
    """Executive summary panel, computed from the dashboard's own series.

    3-5 bullets: the tradable-window supply call, the heaviest modeled
    maintenance month (events named from LEAF_MAINT_INFO), the largest
    projected month-to-month supply moves, and implied-storage extremes.
    A bullet is omitted when its value is null; nothing is invented.
    max_bullets trims the list (front pages take 2); more_href appends a
    link to the full call."""
    rows = {r["id"]: r for r in data["rows"]}
    fc = data["fc_months"]
    gap = data["gap_months"]
    trad = fc[1:]  # Nov 2026 onward
    bullets = []

    sup = rows["supply_total"]["values"]
    oct_v = sup.get(fc[0])
    trad_vals = [sup[m] for m in trad if sup.get(m) is not None]
    if oct_v is not None and trad_vals:
        avg = sum(trad_vals) / len(trad_vals)
        bullets.append(
            "Tradable supply averages <b>" + _f1(avg) + " kb/d</b> from Nov 2026 "
            "onward, " + f"{avg - oct_v:+,.1f}" + " kb/d versus the Oct 2026 "
            "context month (" + _f1(oct_v) + " kb/d).")

    maint = rows["maint"]["values"]
    mvals = [(m, maint.get(m)) for m in gap + fc
             if maint.get(m) not in (None, 0)]
    if mvals:
        top_m, top_v = max(mvals, key=lambda t: t[1])
        evts = []
        for rid, series in data["leaf_maint"].items():
            if series.get(top_m) not in (None, 0):
                info = LEAF_MAINT_INFO.get(rid, {})
                short = info.get("event", rid).split(" (")[0]
                if "ASSUMED" in info.get("source", "").upper():
                    short += " (assumed, not company-stated)"
                if "CADENCE-MODELED" in info.get("event", "").upper():
                    short += " (CADENCE-MODELED)"
                evts.append(esc(short))
        if evts:
            bullets.append(
                _mname(top_m) + " is the heaviest modeled maintenance month at "
                "<b>" + _f1(top_v) + " kb/d</b> offline:"
                f"<ul><li>{'</li><li>'.join(evts)}</li></ul>")
        else:
            bullets.append(
                _mname(top_m) + " is the heaviest modeled maintenance month at "
                "<b>" + _f1(top_v) + " kb/d</b> offline.")
        bullets.append(
            "No public-confirmed maintenance sits in the model math from "
            "Jan 2027 onward:"
            "<ul><li>April 2027: Primrose/Wolf Lake CADENCE-MODELED "
            "turnaround (-26 kb/d, weak-signal flag)</li>"
            "<li>September 2027: MacKay River CADENCE-MODELED turnaround "
            "(-12 kb/d)</li></ul>")

    seq = gap[-1:] + fc  # Sep 2026 -> Oct 2026 -> ... -> Dec 2027
    deltas = []
    for a, b in zip(seq, seq[1:]):
        va, vb = sup.get(a), sup.get(b)
        if va is not None and vb is not None:
            deltas.append((a, b, vb - va))
    deltas.sort(key=lambda t: abs(t[2]), reverse=True)
    if deltas:
        parts = "".join(f"<li>{_mname(a)} to {_mname(b)}: {d:+,.1f} kb/d</li>"
                        for a, b, d in deltas[:3])
        bullets.append("Largest projected month-to-month supply moves:"
                       f"<ul>{parts}</ul>")

    st = rows["stor_chg"]["values"]
    tvals = [(m, st.get(m)) for m in trad if st.get(m) is not None]
    if tvals:
        mx = max(tvals, key=lambda t: t[1])
        mn = min(tvals, key=lambda t: t[1])
        bullets.append(
            "Implied storage change ranges from a high of <b>" + f"{mx[1]:+,.1f}" + " kb/d</b> in "
            + _mname(mx[0]) + " to a low of <b>" + f"{mn[1]:+,.1f}" + " kb/d</b> in "
            + _mname(mn[0]) + " (positive = build into commercial storage, "
            "negative = draw).")

    lis = "".join(f"<li>{b}</li>" for b in bullets[:max_bullets])
    more = (f' Full call: <a href="{more_href}">the Dashboard</a>.'
            if more_href else "")
    return ('<section class="exec" aria-label="Executive summary">'
            '<h2>Executive call</h2><ul>' + lis + '</ul>'
            '<p class="exec-vint">All figures kb/d, computed from the model '
            'tables.' + more + '</p></section>')


# Dashboard row ids that correspond to a project profile page.
_PLANT_PROJECT = {
    "plant_CNRL HORIZON OIL SANDS PROJECT": "cnq_horizon",
    "plant_SUNCOR ENERGY OSG": "su_base_plant",
    "plant_KEARL MINE PROJECT 2-9-097-07W4M": "imo_kearl",
    "plant_FORT HILLS MINE": "su_fort_hills",
    "plant_SYNCRUDE AURORA": "syncrude",
    "plant_SYNCRUDE MILDRED LAKE": "syncrude",
    "scoplant_CNRL HORIZON OIL SANDS PROJECT": "cnq_horizon",
    "scoplant_SUNCOR ENERGY OSG": "su_base_plant",
    "scoplant_SYNCRUDE MILDRED LAKE": "syncrude",
}


def _kpi_strip_html(data):
    """Four quiet stats between the Executive Call and the table, computed
    from the dashboard's own series plus the CER egress watch."""
    import shared as S  # noqa: E402, lazy (see render_page)
    rows = {r["id"]: r for r in data["rows"]}
    fc = data["fc_months"]
    gap = data["gap_months"]
    trad = fc[1:]  # Nov 2026 onward
    stats = []
    sup = rows["supply_total"]["values"]
    act_last = data["act_months"][-1]
    if sup.get(act_last) is not None:
        stats.append(("Supply, latest actual",
                      f"{_f1(sup[act_last])} <span>kb/d</span>",
                      f"{_mname(act_last)} · AER ST3 actual"))
    trad_vals = [sup[m] for m in trad if sup.get(m) is not None]
    if trad_vals:
        avg = sum(trad_vals) / len(trad_vals)
        stats.append(("Tradable supply, avg",
                      f"{_f1(avg)} <span>kb/d</span>",
                      "Nov 2026 onward"))
    maint = rows["maint"]["values"]
    mvals = [(m, maint.get(m)) for m in gap + fc
             if maint.get(m) not in (None, 0)]
    if mvals:
        top_m, top_v = max(mvals, key=lambda t: t[1])
        stats.append(("Heaviest maintenance",
                      f"{_f1(top_v)} <span>kb/d</span>",
                      f"{_mname(top_m)} offline"))
    try:
        ew = json.loads((BASE / "egress_watch.json").read_text())
        spare = ew.get("system_spare_kbd") or sum(
            r.get("spare_kbd", 0) for r in ew.get("routes", [])
            if isinstance(r, dict))
        if spare:
            stats.append(("Egress spare capacity",
                          f"{spare:,.1f} <span>kb/d</span>",
                          f"Jun 2026 · CER, pulled {ew.get('pulled', '')}"))
    except (OSError, ValueError):
        pass
    if not stats:
        return ""
    return S.kpi_strip(stats)


def render_page(data):
    vintages = "".join(
        f"<li><b>{esc(l)}</b>: {esc(v)}</li>" for l, v in [
            ("ST3 actuals", "AER, through 2026-07, pulled 2026-09-22"),
            ("ST53 actuals", "AER, through 2026-07, pulled 2026-09-22"),
            ("ST39 actuals", "AER, through 2026-05, pulled 2026-09-22"),
            ("Forecast", "model build 2026-09-22"),
            ("Aug-Sep 2026 nowcast", "estimated, built 2026-09-23"),
            ("Maintenance", "forward calendar 2026-09-22; modeled at the leaves 2026-09-23"),
        ])
    vintage_html = (
        '<details class="vintage"><summary>Data vintage &amp; sources</summary>'
        f"<ul>{vintages}</ul></details>")
    edition = _edition_date(data.get("built", "2026-09-23"))
    # Lazy import: shared imports this module at load time, so a top-level
    # import would be circular. By render time both modules are loaded.
    import shared as S  # noqa: E402
    masthead = (
        f'    {S.theme_toggle()}\n'
        f'    {S.brand_lockup("index.html")}\n'
        f'    {S.nav("trading", 0)}\n'
        f'    {S.search_box(0)}'
    )
    exec_html = exec_panel_html(data)
    kpi_html = _kpi_strip_html(data)
    data_json = json.dumps(TU.anon_data(data))
    row_links = {}
    for r in data["rows"]:
        rid = r["id"]
        if rid.startswith("proj_"):
            row_links[rid] = f"projects/{rid[5:]}.html"
    for key, pid in _PLANT_PROJECT.items():
        row_links[key] = f"projects/{pid}.html"
    js = (PAGE_JS.replace("__LICENSE_DISPLAY_JS__", TU.LICENSE_DISPLAY_JS)
          .replace("__DATA__", data_json)
          .replace("__ROW_LINKS__", json.dumps(row_links)))
    quarters = quarterly_maintenance_html()
    assumps = grade_assumptions_html()
    # Fixed column widths for the ST3 table (Blaine 2026-09-24): the table is
    # wider than a phone screen, so the label column must hold at 172px and
    # every month column at 68px. table-layout:fixed (see PAGE_CSS) is what
    # makes the sticky date header and the sticky row-label column actually
    # work on mobile: under auto layout the label column blew out to ~2184px,
    # burying the date columns off-screen behind the pinned labels.
    n_mon = (len(data["act_months"]) + len(data["gap_months"]) +
             len(data["fc_months"]))
    colgroup = ('<colgroup><col style="width:172px">' +
                '<col style="width:68px">' * n_mon + '</colgroup>')
    # Explicit table width: fixed layout needs it to honor the colgroup.
    table_w = 172 + 68 * n_mon
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{S.THEME_HEAD}
<title>Projected ST3 | Heavy Reading</title>
<meta name="description" content="The Projected ST3 dashboard: AER ST3 lines with 12 months of actuals, a 2-month nowcast, and 12 months of model forecast for Western Canadian crude supply, drillable to project and plant leaves.">
<link rel="canonical" href="https://heavyreading.ca/st3-dashboard.html">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Heavy Reading">
<meta property="og:title" content="Projected ST3 | Heavy Reading">
<meta property="og:description" content="AER ST3 lines: 12 months of actuals, a 2-month nowcast, and 12 months of model forecast for Western Canadian crude supply.">
<meta property="og:url" content="https://heavyreading.ca/st3-dashboard.html">
<meta name="twitter:card" content="summary">
{TU.FAVICON_LINK}
{TU.FONT_LINKS}
<style>{PAGE_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    {masthead}
    <h1>Projected ST3</h1>
    <p class="sub">AER ST3 lines: 12 months of actuals, a 2-month nowcast, and 12 months
    of model forecast. History, the nowcast, and Oct 2026 are context; the tradable
    barrel is Nov 2026 onward (green). Tap + to drill from an aggregate line into
    projects and plants; tap any row name for its source, vintage, method, and the
    reasoning behind the numbers. All flows in kb/d.</p>
    <div class="edition">Edition: {edition}</div>
    {vintage_html}
  </header>
  {exec_html}
  {kpi_html}
  <div class="controls">
    <button class="btn primary" id="dlCsv">Download CSV</button>
    <button class="btn" id="expandAll">Expand all</button>
    <button class="btn" id="collapseAll">Collapse all</button>
    <span class="legend"><span class="sw" style="background:#fff"></span>actuals
    <span class="sw" style="background:var(--ncbg)"></span>nowcast (est.)
    <span class="sw" style="background:var(--fcbg)"></span>Oct 2026 context
    <span class="sw" style="background:var(--tradbg)"></span>tradable from Nov 2026
    <span class="sw" style="background:var(--acc)"></span>maintenance offline (kb/d)</span>
  </div>
  <div class="tblwrap tbox">
    <table class="data" style="width:{table_w}px">
      {colgroup}
      <thead id="st3head"></thead>
      <tbody id="st3body"></tbody>
    </table>
  </div>
  <div class="foot">
    {quarters}
    {assumps}
    <h2>How to read this</h2>
    <p>Actuals run Aug 2025 through Jul 2026 (AER ST3). Aug-Sep 2026 (amber) are
    nowcast estimates: each line's seasonal baseline plus confirmed maintenance
    events, built 2026-09-23; they are not AER published data. Oct 2026 (blue) is
    the last context month, post-nominations. The tradable window (green) runs
    Nov 2026 onward: that is the barrel that prices.</p>
    <p>Bright orange cells mark modeled maintenance offline: the Maintenance
    offline memo row and every project or plant cell modeled down for an
    outage. A dark badge on a deducted leaf cell shows the kb/d hit; a
    positive badge (for example on the Suncor Base upgrader leaf in
    Aug-Oct 2026) shows a modeled redirect offset; tap either for the source
    and reasoning. Per-event detail lives on the Maintenance tab.</p>
    <p>The grade rows at the bottom of the table cut the same supply the way
    the market sees it: conventional lights, conventional sours, blended
    heavy conventional, synthetic crude oil (SCO), and blended dilbit, then
    the total, which ties exactly to Total WCSB crude supply every month.
    Bitumen sent for further processing (the upgrader feed) is a
    manufacturing transfer, not a market stream, so it is not shown as a
    row; the dilbit number is already net of it. See the grade-layer
    assumptions panel below for the named assumptions and the leaf-to-grade
    mapping.</p>
    <p>In-situ project forecasts are AER ST53 commercial-scheme forecasts,
    grossed up by {data['gross_up']:.2f} so they reconcile to the ST3 in-situ
    line (mapped projects cover {data['coverage']:.1%} of ST3 in-situ; the
    remainder sits on the "Unmapped in-situ" row). Mined bitumen and SCO drill
    into AER ST39 facility rows (actuals through 2026-05; Jun-Jul 2026 blank
    until AER publishes), with plant forecasts scaled to tie exactly to the ST3
    lines. Every row carries a <b>Why</b> note explaining the reasoning behind
    its forecast: named maintenance events with dates and kb/d impacts, decline
    assumptions, project ramps, and where a single-month dip is just the
    seasonal factor repeating.</p>
    <p>Confirmed turnarounds are modeled down at the affected project and plant
    leaves (orange cells with a kb/d badge). Maintenance offline is a memo row
    that details those same outages (tap +): confirmed turnarounds with kb/d
    impacts, plus pattern-indicated 2027 windows that carry no volume. Implied
    storage change is a model output with no actuals counterpart. Unknown values
    are blank, never filled in.</p>
    <h2>Sources</h2>
    <table class="src">
      <tr><th>Publisher</th><th>Dataset</th><th>Vintage / coverage</th><th>Retrieved</th></tr>
      <tr><td>Alberta Energy Regulator</td><td>ST3 - Alberta Energy Resource Industries Monthly Statistics</td>
          <td>Actuals through 2026-07 (latest file vintage 2026-08-27)</td><td>2026-09-22</td></tr>
      <tr><td>Alberta Energy Regulator</td><td>ST53 - In-situ project data (commercial schemes)</td>
          <td>Actuals through 2026-07</td><td>2026-09-22</td></tr>
      <tr><td>Alberta Energy Regulator</td><td>ST39 - Oil sands plant data (mined bitumen and SCO by facility)</td>
          <td>Actuals through 2026-05</td><td>2026-09-22</td></tr>
      <tr><td>Heavy Reading model</td><td>Aug-Sep 2026 nowcast (seasonal baseline plus confirmed maintenance)</td>
          <td>Built 2026-09-23; not AER published data</td><td>2026-09-23</td></tr>
      <tr><td>Heavy Reading model</td><td>15-month forward S&D balance, 21 granular leaves</td>
          <td>Oct 2026-Dec 2027, built 2026-09-23</td><td>2026-09-23</td></tr>
      <tr><td>Heavy Reading model</td><td>Forward maintenance calendar</td>
          <td>Compiled 2026-09-22</td><td>2026-09-22</td></tr>
    </table>
    <p class="backlink"><a href="index.html">&larr; Back to the Heavy Reading dashboard</a></p>
    {S.footer(0)}
  </div>
</div>
{S.NAV_JS}
{S.THEME_JS}
{S.SEARCH_JS}
<script>
{js}
</script>
</body>
</html>
"""
    # Anonymous publication: neutralize any identity references in rendered
    # copy (annotations, maintenance sources). Data JSON already anoned above.
    return TU.anon_text(page)


if __name__ == "__main__":
    main()
