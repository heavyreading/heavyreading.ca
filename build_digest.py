#!/usr/bin/env python3
"""Build The Digest: dated morning-crude editions + archive, under /digest/.

Reads reader-facing markdown editions from digest/editions/*.md and writes:
  digest/<YYYY-MM-DD>/index.html   (dated edition page, depth 2)
  digest/index.html                 (edition archive, reverse-chron, depth 1)

Edition markdown contract (the 5:35 AM digest cron writes these):
  ---
  date: 2026-09-23
  title: <edition headline>
  dek: <one-line summary shown on the archive>
  sources:
  - "<vintage chip, e.g. 'ICE delayed quotes, Sep 23, 2026'>"
  ---
  ## The call
  - **Bold** leads, [links](https://...) supported.
  ...

Public-safety: pages must carry no identity strings and no internal ops
notes. The builder aborts loudly on forbidden tokens rather than
publishing them.
"""

import html
import re
from pathlib import Path

import shared as S

SITE = Path(__file__).resolve().parent
ED_DIR = SITE / "digest" / "editions"

SOURCE_LINE = ("Public market data: ICE, EIA, AER ST3/ST39/ST53, CER, StatCan, "
               "company guidance; news via wire services")

FORBIDDEN = ("blaine", "hodder")

# ----------------------------------------------------------------------------
# Frontmatter + tiny markdown -> HTML
# ----------------------------------------------------------------------------

def _strip_fm(lines):
    meta = {}
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        key = None
        while i < len(lines) and lines[i].strip() != "---":
            ln = lines[i]
            if ln.strip().startswith("- ") and key == "sources":
                if not isinstance(meta.get(key), list):
                    meta[key] = []
                meta[key].append(ln.strip()[2:])
            elif ":" in ln and not ln.startswith(" "):
                k, v = ln.split(":", 1)
                key = k.strip()
                meta[key] = v.strip()
            elif key == "dek" and ln.strip():
                meta[key] = (meta[key] + " " + ln.strip()).strip()
            i += 1
        i += 1  # past closing ---
    return meta, lines[i:]


def _inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">'
                         f'{m.group(1)}</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", t)
    return t


def md_to_html(text):
    """Headings (##/###), bullets, numbered lists, paragraphs, bold/links."""
    out = []
    para = []
    in_list = None  # None | "ul" | "ol"

    def flush_para():
        if para:
            out.append("  <p>" + " ".join(para) + "</p>")
            para.clear()

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"  </{in_list}>")
            in_list = None

    for raw in text.splitlines():
        ln = raw.rstrip()
        stripped = ln.strip()
        if not stripped:
            flush_para()
            close_list()
            continue
        m = re.match(r"^(#{2,3})\s+(.*)$", stripped)
        if m:
            flush_para()
            close_list()
            tag = "h2" if m.group(1) == "##" else "h3"
            out.append(f"  <{tag}>{_inline(m.group(2))}</{tag}>")
            continue
        bm = re.match(r"^[-*]\s+(.*)$", stripped)
        nm = re.match(r"^\d+\.\s+(.*)$", stripped)
        if bm or nm:
            flush_para()
            kind, item = ("ul", bm.group(1)) if bm else ("ol", nm.group(1))
            if in_list != kind:
                close_list()
                out.append('  <ul class="ev">' if kind == "ul" else "  <ol>")
                in_list = kind
            out.append(f"  <li>{_inline(item)}</li>")
            continue
        close_list()
        para.append(_inline(stripped))
    flush_para()
    close_list()
    return "\n".join(out)


def parse_edition(path):
    meta, body_lines = _strip_fm(path.read_text(encoding="utf-8").splitlines())
    meta["date"] = meta.get("date", "").strip()
    meta["title"] = meta.get("title", "").strip()
    meta["dek"] = meta.get("dek", "").strip()
    if isinstance(meta.get("sources"), str):
        meta["sources"] = [s.strip() for s in meta["sources"].split(";") if s.strip()]
    if isinstance(meta.get("sources"), list):
        meta["sources"] = [s.strip().strip('"').strip("'")
                           for s in meta["sources"] if s.strip()]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["date"]):
        raise ValueError(f"{path.name}: frontmatter date must be YYYY-MM-DD")
    return meta, "\n".join(body_lines).strip()


# ----------------------------------------------------------------------------
# Page builders
# ----------------------------------------------------------------------------

def _safety_check(html_text, label):
    for tok in FORBIDDEN:
        if tok in html_text.lower():
            raise SystemExit(f"SAFETY ABORT: forbidden token '{tok}' in {label}")


def build_edition(meta, body_md):
    date = meta["date"]
    date_long = S.edition_date(date)
    body_html = md_to_html(body_md)

    notes = []
    if meta.get("sources"):
        notes = [(i + 1, S.esc(s)) for i, s in enumerate(meta["sources"])]

    out = []
    out.append(body_html)
    out.append('  <p class="note">Published from market data as of '
               f'{S.esc(date_long)}; every figure carries its vintage in the '
               "sources list below. Public data only.</p>")
    out.append(S.footnotes(notes))

    head = S.article_head(
        "The morning crude digest",
        S.esc(meta["title"]),
        S.esc(meta["dek"]) if meta.get("dek") else "",
        f'<span><b>Published</b> {S.esc(date_long)}</span>'
        '<span class="dot"></span><span>Heavy Reading</span>')

    page = S.page_shell(
        f"The Morning Digest — {date_long}", "", "",
        f'<a href="../../index.html">Home</a> / '
        f'<a href="../index.html">The Digest</a> / {S.esc(date_long)}',
        head + "\n" + "\n".join(out),
        "digest", 2, date_long, SOURCE_LINE,
        description=meta.get("dek", "The Heavy Reading morning crude digest: "
                                   "overnight geopolitics, prices, egress, and "
                                   "the Canadian diff complex."),
        url_path=f"digest/{date}/index.html")

    _safety_check(page, f"digest/{date}")
    d = SITE / "digest" / date
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {d / 'index.html'}")


def build_archive(editions):
    rows = []
    for i, meta in enumerate(sorted(editions, key=lambda m: m["date"],
                                   reverse=True)):
        last = " last" if i == len(editions) - 1 else ""
        href_ = f"{meta['date']}/index.html"
        rows.append(
            f'  <a class="srow{last}" href="{href_}">'
            f'<p class="kicker">{S.edition_date(meta["date"])}</p>'
            f'<h3>{S.esc(meta["title"])}</h3>'
            f'<p>{S.esc(meta.get("dek", ""))}</p>'
            f'<span class="go">Read &rarr;</span></a>')

    newest = max(editions, key=lambda m: m["date"])
    out = [
        '  <p class="sub">The morning crude briefing, published daily at '
        '5:35 AM Mountain: overnight geopolitics through a supply/demand '
        'lens, flat prices, cracks and positioning, Canadian egress and '
        'refinery watch, and the 12-month forward strip of the liquid '
        'Canadian diffs. Every edition carries its data vintages.</p>',
        '  <p class="note">This section: '
        f'<a href="{newest["date"]}/index.html">Latest edition</a> '
        '&middot; <a href="index.html" aria-current="page">Edition archive</a></p>',
        '  <nav class="seclist" aria-label="Digest editions">'
        + "".join(rows) + "  </nav>",
        "  <h2>About</h2>",
        "  <p>Each edition is built from public data only: ICE, EIA, AER "
        "ST3/ST39/ST53, CER, StatCan, company guidance, and wire reporting. "
        "Quotes that cannot be verified from a public source are described "
        "as such, never printed as levels.</p>",
        "  <h2>Sources</h2>",
        S.sources_table()]

    page = S.page_shell(
        "The Digest", "The Digest",
        "The Heavy Reading morning crude briefing, and its full edition archive.",
        '<a href="../index.html">Home</a> / The Digest',
        "\n".join(out),
        "digest", 1, S.edition_date(newest["date"]), SOURCE_LINE,
        description="The Heavy Reading morning crude briefing: daily at "
                    "5:35 AM Mountain, with the full edition archive.",
        url_path="digest/index.html")
    _safety_check(page, "digest/index")
    d = SITE / "digest"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {d / 'index.html'}")


def build_digest():
    ED_DIR.mkdir(parents=True, exist_ok=True)
    editions = []
    for path in sorted(ED_DIR.glob("*.md")):
        meta, body = parse_edition(path)
        editions.append(meta)
        build_edition(meta, body)
    if editions:
        build_archive(editions)
    return [m["date"] for m in editions]


if __name__ == "__main__":
    dates = build_digest()
    print(f"digest editions: {len(dates)}")
