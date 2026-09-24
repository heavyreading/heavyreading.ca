"""Trump watch tab: live Truth Social energy feed + research archive.

Reads (build time):
  ~/workspace/goals/wcsb-s-d-model/hidden_files/trump_watch/trump_watch.jsonl
    energy/oil-relevant posts: {id, created_at, text, url, media, matched, alert}
  ~/workspace/goals/wcsb-s-d-model/hidden_files/datasets/world_watches/trump.json
    research archive (tariff episode reconstruction etc.), if complete.

Design law: his words as plain text in Heavy Reading typography. Never Truth
Social styling, no screenshots, no embeds. One line per entry on why it
matters for oil (editorial framing from the matched keywords, clearly the
watch's read). Market impact only where the archive sources it. Raw text in
a collapsed <details> for verification.

Watch framework (same as build_watches.py):
  - how_to_read / wcs_stakes render near the top (after the intro sub),
  - "Where sources disagree" renders after the archive (only if present),
  - wcs_closer renders last.
TMW/ARV tokens in the framework text link only to verified site pages.
"""
import json
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SITE = "/home/hatch/workspace/wcsb-sd/hidden_files/woodmack_storage/site"
FEED_DIR = ("/home/hatch/workspace/goals/wcsb-s-d-model/hidden_files/"
            "trump_watch")
ARCHIVE = ("/home/hatch/workspace/goals/wcsb-s-d-model/hidden_files/"
           "datasets/world_watches/trump.json")
EDMONTON = ZoneInfo("America/Edmonton")

# matched keyword -> one line on why it matters for oil. Editorial framing,
# not a factual claim; kept to a single quiet line per entry.
WHY = {
    "tariff": "Tariffs on Canadian crude were the 2025 differential shock — "
              "new tariff talk reprices WCS treatment risk.",
    "export ban": "A crude export ban would trap barrels inland and blow out "
                  "Canadian differentials.",
    "sanction": "Sanctions move the global sour barrel (Iran, Russia, "
                "Venezuela) that WCS prices against.",
    "embargo": "Embargo talk moves the sour barrel WCS tracks.",
    "spr": "SPR releases add sour barrels to the market; refills remove "
           "them. Both move the complex WCS clears against.",
    "strategic petroleum": "SPR policy moves the sour barrel directly.",
    "venezuela": "Venezuelan heavy is the closest comp to WCS; its fate "
                 "moves Canadian diffs.",
    "iran": "Iranian barrels and sanction risk price straight into the "
            "sour complex.",
    "putin": "Russian supply and sanctions shape the Atlantic sour balance.",
    "opec": "OPEC+ supply decisions set the global sour balance WCS clears "
            "against.",
    "saudi": "Saudi supply decisions set the sour balance WCS clears against.",
    "keystone": "Keystone is Canadian egress itself — its fate is WCS "
                "differential fate.",
    "pipeline": "Pipeline policy is egress policy for Canadian barrels.",
    "drilling": "US supply-side policy; marginal for Canadian diffs, "
                "directional for flat price.",
    "frack": "US supply-side policy; directional for flat price.",
    "refiner": "Downstream margin policy feeds back into crude demand.",
    "gasoline": "Pump-price politics drive SPR-release pressure — the 2022 "
                "playbook.",
    "gas prices": "Pump-price politics drive SPR-release pressure — the 2022 "
                  "playbook.",
    "diesel": "Diesel politics feed refinery-run and export policy.",
    "oil": "Direct commentary on the commodity under WCS flat price.",
    "crude": "Direct commentary on the commodity under WCS flat price.",
    "barrel": "Direct commentary on the commodity under WCS flat price.",
    "petroleum": "Policy signal on the petroleum balance.",
    "natural gas": "Gas-market spillover; second-order for crude diffs.",
    "lng": "Gas-market spillover; second-order for crude diffs.",
    "energy": "Broad energy-policy signal — read the specifics.",
}
# priority: most market-relevant keyword first
PRIORITY = ["export ban", "tariff", "embargo", "sanction", "spr",
            "strategic petroleum", "venezuela", "iran", "keystone", "opec",
            "saudi", "putin", "pipeline", "refiner", "gasoline", "gas prices",
            "diesel", "drilling", "frack", "oil", "crude", "barrel",
            "petroleum", "energy", "natural gas", "lng"]

# Tradable instruments -> candidate target pages (site-root-relative), in
# priority order. Mirrors build_watches.py INSTRUMENT_TARGETS; a candidate is
# used only if the file exists in the built site AND mentions the instrument.
INSTRUMENT_TARGETS = {
    "TMW": ["venezuela/index.html", "st3-dashboard.html"],
    "ARV": ["venezuela/index.html", "st3-dashboard.html"],
}


def _instrument_targets():
    """token -> site-root-relative page path, verified against the built site.

    Only a page that exists on disk and actually mentions the instrument is
    returned; anything else renders as plain text (no invented URLs).
    """
    targets = {}
    for tok, cands in INSTRUMENT_TARGETS.items():
        for rel in cands:
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
        srcs = x.get("sources") or [x.get("source_a"), x.get("source_b")]
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


def _parse_ts(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(EDMONTON)
    except Exception:
        return None


def _fmt_date(ts):
    dt = _parse_ts(ts)
    if not dt:
        return ts
    return dt.strftime("%b %-d, %Y · %-I:%M %p MDT")


def _why(matched):
    for k in PRIORITY:
        if k in matched and k in WHY:
            return WHY[k]
    return None


def _entry_html(rec, S):
    text = rec.get("text", "")
    url = rec.get("url", "")
    ts = rec.get("created_at", "")
    matched = rec.get("matched", []) or []
    alert = rec.get("alert", False)
    date = _fmt_date(ts)
    why = _why(matched)
    tags = " ".join(f'<span class="wtag">{S.esc(k)}</span>' for k in matched)

    limit = 480
    if len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0] + " …"
    else:
        cut = text
    body = f'<p class="wtext">{S.esc(cut)}</p>'
    if why:
        body += f'<p class="wwhy"><b>Why it matters:</b> {S.esc(why)}</p>'
    if "tariff" in matched:
        body += ('<p class="wwhy">Archive: the Feb 2025 tariff episode — '
                 'what was threatened and what happened to diffs — is '
                 'reconstructed below.</p>')
    flag = ""
    if alert:
        flag = ('<p class="wflag">Flagged by the feed as potentially '
                'market-relevant (tariff / export-ban / sanctions / SPR '
                'language).</p>')
    ver = (f'<details class="verbatim"><summary>Verbatim &amp; source</summary>'
           f'<p class="wraw">{S.esc(text)}</p>'
           f'<p class="vintage-inline">Posted {S.esc(ts)} · '
           f'<a href="{S.esc(url)}">truthsocial.com</a> · id {S.esc(rec.get("id", ""))}</p>'
           f'</details>')
    return (f'<article class="wpost">{flag}'
            f'<p class="wdate">{S.esc(date)}</p>'
            f'{body}'
            f'<p class="wtags">{tags}</p>'
            f'{ver}</article>')


def _group_bullets(bullets):
    """Group flat research bullets into themed archive sections."""
    groups = [
        ("The tariff episode",
         ["tariff", "ieepa", "usmca", "liberation day", "fentanyl"]),
        ("WCS differentials",
         ["wcs", "differential", "heavy differential"]),
        ("Sanctions",
         ["sanction", "chevron", "lukoil", "rosneft", "secondary tariff"]),
        ("Export ban",
         ["export ban", "export-ban", "banning crude", "banning oil",
          "ruled out banning"]),
        ("Drilling & permitting",
         ["drill", "permit", "lease sale", "anwr", "ocs"]),
        ("SPR",
         ["spr", "strategic petroleum", "bryan mound"]),
        ("The Truth Social channel",
         ["truth social"]),
        ("Archive",
         ["2017", "keystone xl permit", "presidential permit"]),
    ]
    placed, sections = set(), []
    for heading, keys in groups:
        items = [b for i, b in enumerate(bullets)
                 if i not in placed and
                 any(k in b.get("text", "").lower() for k in keys)]
        # keep tariff chronology separate from sanctions secondary-tariff
        if heading == "The tariff episode":
            items = [b for b in items
                     if "venezuela" not in b.get("text", "").lower()]
        if items:
            for b in items:
                placed.add(bullets.index(b))
            items.sort(key=lambda b: b.get("vintage", ""))
            sections.append((heading, items))
    rest = [b for i, b in enumerate(bullets) if i not in placed]
    if rest:
        rest.sort(key=lambda b: b.get("vintage", ""))
        sections.append(("Other", rest))
    return sections


def _archive_html(S):
    """Research archive sections, tolerating the worker's shape."""
    try:
        with open(ARCHIVE) as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ('<h2>Archive</h2><p class="sub">The tariff-episode '
                'reconstruction and policy archive are in preparation.</p>')
    out = ["<h2>Archive</h2>",
           '<p class="sub">Dated episodes with market impact where sourced. '
           'All facts paraphrased; conflict claims are attribute-framed as '
           'reported.</p>']
    sections = d.get("sections") or []
    if not sections and d.get("bullets"):
        sections = [{"heading": h, "bullets": bs}
                    for h, bs in _group_bullets(d["bullets"])]
    if not sections:
        out.append('<p class="sub">The tariff-episode reconstruction and '
                   'policy archive are in preparation.</p>')
        return "\n".join(out)
    for sec in sections:
        out.append(f"  <h3>{S.esc(sec.get('heading', ''))}</h3>")
        out.append('  <ul class="ev">')
        for b in sec.get("bullets", []):
            text = S.esc(b.get("text", ""))
            vintage = S.esc(b.get("vintage", ""))
            src = S.esc(b.get("source", ""))
            url = b.get("source_url", "") or b.get("url", "")
            link = (f' <a href="{S.esc(url)}">{src}</a>' if url and src
                    else (f" {src}" if src else ""))
            meta = (f'<span class="vintage-inline">{vintage}{link}</span>'
                    if (vintage or link) else "")
            out.append(f"  <li>{text}<br>{meta}</li>" if meta else f"  <li>{text}</li>")
        out.append("  </ul>")
    gaps = d.get("gaps") or []
    if gaps:
        out.append("  <h3>Gaps</h3>")
        out.append('  <ul class="ev">')
        out.extend(f"  <li>{S.esc(g)}</li>" for g in gaps)
        out.append("  </ul>")
    return "\n".join(out)


def build_page():
    import sys
    sys.path.insert(0, SITE)
    import shared as S

    recs = []
    seen = set()
    hits_path = os.path.join(FEED_DIR, "trump_watch.jsonl")
    if os.path.exists(hits_path):
        with open(hits_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("id") in seen or not r.get("text"):
                    continue
                seen.add(r["id"])
                recs.append(r)
    recs.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    if recs:
        first = _fmt_date(recs[-1].get("created_at", ""))
        last = _fmt_date(recs[0].get("created_at", ""))
        feed_note = (f"{len(recs)} energy-relevant posts, {first} to {last}. "
                     "The poller checks Truth Social hourly; this "
                     "page reflects the feed at build time.")
        entries = "\n".join(_entry_html(r, S) for r in recs)
        feed_html = (f'<p class="sub">{S.esc(feed_note)}</p>\n{entries}')
    else:
        feed_html = ('<p class="sub">No energy-relevant posts in the feed yet. '
                     'The poller checks Truth Social hourly.</p>')

    out = [
        '<p class="sub">Trump as a first-order driver of Canadian '
        'differentials: his energy-relevant posts as plain text, what each '
        'one means for oil, and the archive of past episodes with dates and '
        'market impact.</p>',
    ]

    # watch framework fields from the trump.json research archive
    fw = {}
    try:
        with open(ARCHIVE) as f:
            fw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        fw = {}

    how = (fw.get("how_to_read") or "").strip()
    if how:
        out.append(f'  <p class="note">{S.esc(how)}</p>')

    stakes = (fw.get("wcs_stakes") or "").strip()
    if stakes:
        targets = _instrument_targets()
        out.append(f'  <p class="lede">{_link_instruments(stakes, targets, S)}</p>')

    out += [
        '<h2>The feed</h2>',
        feed_html,
        _archive_html(S),
    ]

    dis = _disagreements_html(fw.get("disagreements"), S)
    if dis:
        out.append(dis)

    closer = (fw.get("wcs_closer") or "").strip()
    if closer:
        targets = _instrument_targets()
        out.append(f'  <p class="lede">{_link_instruments(closer, targets, S)}</p>')

    title = "Trump watch"
    dek = ("Trump's energy-relevant posts as plain text, what each means for "
           "oil, and the archive of past episodes.")
    return S.page_shell(
        title, title, dek,
        '<a href="../../index.html">Home</a> / <a href="../index.html">World</a> / Trump watch',
        "\n".join(out), "trump", 2, S.edition_date("2026-09-23"),
        "Truth Social poller feed + public sources; every entry dated",
        description=dek, url_path="world/trump/index.html")


def main():
    page = build_page()
    d = os.path.join(SITE, "world", "trump")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w") as f:
        f.write(page)
    print("wrote world/trump/index.html (live feed)")


if __name__ == "__main__":
    main()
