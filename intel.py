#!/usr/bin/env python3
"""Parser for annotations/project_intel/<slug>.md filing intelligence.

Reads the per-project research files (one per project slug) and exposes
structured fact bullets with per-fact document+date citations, for the
Projects section fact panels.

Rules enforced here:
- The Proposals section ("needs Blaine approval, NOT applied") is never
  parsed and never surfaces in output. Proposal numbers must not appear
  as facts anywhere.
- Internal model notes (standing-treatment / do-not-overwrite lines) are
  dropped: they are model instructions, not public filing facts.
- "not disclosed" bullets are surfaced as labeled nulls, never filled.
- Where sources conflict, every bullet is kept with its own source and
  date; nothing is resolved silently.

Parsing is deterministic: reruns over unchanged files produce identical
output.
"""
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent
INTEL_DIR = BASE / "annotations" / "project_intel"

# Sections folded into the fact panel. Anything else (Asset summary is
# handled separately; Sources feeds the registry; Proposals is excluded).
SECTIONS = [
    "Operator and ownership",
    "Capacity",
    "Growth and expansions",
    "Maintenance",
    "Operating costs",
    "Technology and process",
    "Regulatory status",
]

DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
INTERNAL_RE = re.compile(r"standing treatment|do not overwrite", re.I)
NULL_RE = re.compile(r"^(?:[^:()]{0,80}:\s*)?not disclosed\.?$", re.I)


def parse_source_text(s):
    """Parse 'Publisher, document title, date, URL' into a dict.

    URL and date are optional; publisher is the first comma segment and
    the document title is everything between publisher and date/URL.
    """
    s = s.strip()
    url = None
    m = re.search(r"https?://\S+", s)
    if m:
        url = m.group(0).rstrip(").,")
        s = (s[:m.start()] + s[m.end():]).strip().rstrip(",").strip()
    date = ""
    dm = DATE_RE.search(s)
    if dm:
        date = dm.group(1)
        s = (s[:dm.start()] + s[dm.end():]).strip().rstrip(",").strip()
        s = re.sub(r"\b(accessed|updated|via)\s*$", "", s).strip().rstrip(",").strip()
    parts = [p.strip() for p in s.split(",") if p.strip()]
    publisher = parts[0] if parts else ""
    doc = ", ".join(parts[1:]) if len(parts) > 1 else ""
    doc = doc.replace('"', "").strip(" '")
    return {"publisher": publisher, "doc": doc, "date": date, "url": url or ""}


def split_sources(text):
    """Split trailing (Source: ...) groups off a bullet.

    Returns (clean_text, [raw_source_strs]). Multiple sources joined by
    '; ' inside one group are split apart.
    """
    t = text.strip()
    srcs = []
    while True:
        m = re.search(r"\(Source:\s*([^()]*)\)\s*$", t)
        if not m:
            break
        srcs.insert(0, m.group(1).strip())
        t = t[:m.start()].strip()
    out = []
    for s in srcs:
        out.extend(x.strip() for x in re.split(r";\s*", s) if x.strip())
    return t, out


def match_registry(raw, registry):
    """Match an inline source string to the file's Sources registry."""
    raw_low = raw.lower()
    for e in registry:
        if e["url"] and e["url"].lower() in raw_low:
            return e
    for e in registry:
        if e["doc"] and len(e["doc"]) > 8 and e["doc"].lower() in raw_low:
            return e
    return None


def cite_str(e):
    """'document name + document date' citation string."""
    s = ", ".join(b for b in (e["publisher"], e["doc"]) if b)
    if e["date"]:
        s += f", {e['date']}"
    return s


# Public-anonymity: internal pipeline identifiers never reach rendered copy.
# Applied to every cite string in cites_for(), so all render sites inherit it.
CITE_SCRUBS = [
    # "projects.yaml project master[, `pid` record[, note][, k: v]]"
    (re.compile(r"^projects\.yaml project master.*$"),
     "Heavy Reading project roster"),
]


def public_cite(s):
    for rx, rep in CITE_SCRUBS:
        s = rx.sub(rep, s)
    return s


def load(pid):
    """Parse one intel file. Returns None when no file exists for pid."""
    p = INTEL_DIR / f"{pid}.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    sections = {}
    cur = None
    for line in text.splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            cur = h.group(1)
            sections.setdefault(cur, [])
            continue
        if cur is not None:
            sections[cur].append(line)

    registry = []
    for line in sections.get("Sources", []):
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m:
            registry.append(parse_source_text(m.group(1)))

    def cites_for(srcs):
        out = []
        for s in srcs:
            e = match_registry(s, registry)
            out.append(public_cite(cite_str(e)) if e else public_cite(s))
        # dedupe, keep order
        seen, ded = set(), []
        for c in out:
            if c not in seen:
                seen.add(c)
                ded.append(c)
        return ded

    facts = {}
    for sec in SECTIONS:
        bullets = []
        for line in sections.get(sec, []):
            m = re.match(r"^\s*-\s+(.*)$", line)
            if not m:
                continue
            raw = m.group(1).strip()
            if INTERNAL_RE.search(raw):
                continue
            clean, srcs = split_sources(raw)
            bullets.append({"text": clean, "cites": cites_for(srcs)})
        facts[sec] = bullets

    # Asset summary: join paragraphs, strip trailing source groups.
    paras = [ln.strip() for ln in sections.get("Asset summary", [])
             if ln.strip()]
    desc_text, desc_srcs = split_sources(" ".join(paras))

    return {
        "present": True,
        "slug": pid,
        "title": re.match(r"^#\s+(.+?)\s*$", text, re.M).group(1)
        if re.match(r"^#\s+(.+?)\s*$", text, re.M) else pid,
        "sections": facts,
        "description": desc_text,
        "desc_cites": cites_for(desc_srcs),
    }


def is_null_bullet(text):
    """True when the bullet is a pure 'not disclosed' labeled null."""
    return bool(NULL_RE.match(text.strip()))


def capacity_short(ix):
    """Compact index-cell capacity string, or (text, is_null)."""
    if ix is None:
        return None, True
    bullets = ix["sections"].get("Capacity", [])
    if not bullets:
        return None, True
    first = bullets[0]["text"]
    if is_null_bullet(first):
        return "not disclosed in reviewed sources", True
    short = first if len(first) <= 90 else first[:87].rsplit(" ", 1)[0] + "..."
    if len(bullets) > 1:
        short += " (see profile)"
    return short, False
