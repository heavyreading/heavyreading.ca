"""Hot Topics: weekly markdown posts -> hot-topics/ section of the site.

Source posts live outside the site tree (the weekly Hot Topics feed job writes
them), e.g. ~/workspace/podcast-intel/arc-energy-ideas/hot-topics/weekly/.

Each post: weekly/YYYY-MM-DD-weekly.md
    frontmatter: title, week_of (YYYY-MM-DD), dek (optional),
                 sources: [{feed, title, url, date}, ...]  (hidden; NOT rendered)
    body: markdown in Heavy Reading's voice. The published copy names no feeds
    and carries no attributions; full sourcing stays in the data files behind
    it (hot-topics.json) plus a hidden HTML comment for traceability.

Builds:
    site/hot-topics/<YYYY-MM-DD>.html   one page per week
    site/hot-topics/index.html          reverse-chronological archive

Run build_hottopics.main() before build_sections.main() so the nav's
"Latest week" link resolves.
"""
import html
import re
import sys
from pathlib import Path

import yaml

SITE = Path(__file__).resolve().parent
SRC_DIR = Path.home() / "workspace" / "podcast-intel" / "arc-energy-ideas" / "hot-topics" / "weekly"

sys.path.insert(0, str(SITE))
import shared as S  # noqa: E402

OUT = SITE / "hot-topics"
UPDATED_LABEL = "September 23, 2026"

# ---------------------------------------------------------------- markdown

_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"`(.+?)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">\1</a>'),
]


def _inline(t):
    t = html.escape(t)
    for rx, rep in _INLINE:
        t = rx.sub(rep, t)
    return t


def _autolink(t):
    """Link bare http(s) URLs in already-escaped text (skip URLs already
    inside an href or anchor text); trailing punctuation stays outside."""
    def _link(m):
        url = m.group(1)
        trail = ""
        while url and url[-1] in ".,;:!?":
            trail = url[-1] + trail
            url = url[:-1]
        return f'<a href="{url}">{url}</a>{trail}'
    return re.sub(r'(?<![">\=])(https?://[^\s<]+)', _link, t)


def md_to_html(md):
    """Small markdown renderer: headings, bold/italic/code, links, ul/ol,
    blockquotes, hr, paragraphs. No raw HTML passthrough (escaped).

    Presentation normalizations (copy unchanged):
    - a "related_links" heading (feed-pipeline convention) renders as
      "Related links", and its "- title: ..." items render as clean titles
    - a leading "# ..." H1 is dropped: page_shell already prints the title
    - bare URLs in paragraphs become links
    """
    # The article header carries the title; a body H1 would stack a second
    # one directly beneath it.
    md = re.sub(r"^#\s+.*\n?", "", md, count=1)
    out, para, lst = [], [], None  # lst: "ul" or "ol"
    rel_links = False  # inside a related-links list
    def flush_para():
        if para:
            out.append("<p>" + _autolink(" ".join(para)) + "</p>")
            para.clear()
    def close_list():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None
    for raw in md.split("\n"):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            flush_para(); close_list(); continue
        if s == "---" or s == "***":
            flush_para(); close_list(); out.append("<hr>"); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            flush_para(); close_list()
            lvl = len(m.group(1))
            htext = m.group(2).strip()
            rel_links = (htext.lower().replace("_", " ") == "related links")
            if rel_links:
                htext = "Related links"
            out.append(f"<h{lvl}>{_inline(htext)}</h{lvl}>")
            continue
        if s.startswith("> "):
            flush_para(); close_list()
            out.append(f"<blockquote><p>{_inline(s[2:])}</p></blockquote>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            flush_para()
            item = m.group(1).strip()
            if rel_links:
                tm = re.match(r'^title:\s*"?(.*?)"?$', item)
                if tm:
                    item = tm.group(1)
            if lst != "ul":
                close_list(); out.append("<ul class=\"ev\">"); lst = "ul"
            out.append(f"<li>{_inline(item)}</li>")
            continue
        m = re.match(r"^(\d+)[.)]\s+(.*)$", s)
        if m:
            flush_para()
            if lst != "ol":
                close_list(); out.append("<ol class=\"ev\">"); lst = "ol"
            out.append(f"<li>{_inline(m.group(2))}</li>")
            continue
        close_list()
        para.append(_inline(s))
    flush_para(); close_list()
    return "\n".join(out)


# ---------------------------------------------------------------- posts

def parse_post(path):
    text = path.read_text(encoding="utf-8")
    fm, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            fm = _normalize(yaml.safe_load(parts[1]) or {})
            body = parts[2].lstrip("\n")
    return fm, body


def _normalize(v):
    """YAML date/datetime objects -> ISO strings (JSON-safe, stable)."""
    import datetime
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_normalize(x) for x in v]
    return v


def _week_label(week_of):
    try:
        y, m, d = (int(x) for x in str(week_of).split("-"))
        names = ["January", "February", "March", "April", "May", "June",
                 "July", "August", "September", "October", "November",
                 "December"]
        return f"{names[m - 1]} {d}, {y}"
    except Exception:
        return str(week_of)


def _clean_teaser(s):
    t = re.sub(r"[*_`]", "", s)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return t[:220] + ("..." if len(t) > 220 else "")


def _teaser(body):
    """First real paragraph, plain text, ~220 chars. Falls back to the first
    list item (verification annotation stripped) so archive teasers and the
    article dek never render blank now the episode header lines are gone."""
    for line in body.split("\n"):
        s = line.strip()
        if s and not s.startswith(("#", ">", "-", "*", "1")) and s not in ("---", "***"):
            return _clean_teaser(s)
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("- "):
            t = re.sub(
                r"\s*\((secondary-source|podcast-sourced), needs primary verification\)\s*$",
                "", s[2:])
            return _clean_teaser(t)
    return ""


def _sources_comment(sources):
    """Hidden traceability comment. Never rendered as copy."""
    lines = ["<!-- hot-topics sources (not rendered as copy):"]
    for s in sources or []:
        feed = str(s.get("feed", "")).replace("--", " - ")
        title = str(s.get("title", "")).replace("--", " - ")
        url = str(s.get("url", "")).replace("--", " - ")
        date = str(s.get("date", "")).replace("--", " - ")
        lines.append(f"  - {feed} | {title} | {url} | {date}")
    lines.append("-->")
    return "\n".join(lines)


def _topic_count(body):
    return len(re.findall(r"^##\s+", body, re.M))


def _week_nav(older, newer):
    """Prev/next week links: the archive is a web, not a dead end."""
    if not older and not newer:
        return ""
    left = (f'<a href="{older["week_of"]}.html">&larr; '
            f'{html.escape(older["title"])}</a>' if older else "<span></span>")
    right = (f'<a href="{newer["week_of"]}.html">'
             f'{html.escape(newer["title"])} &rarr;</a>' if newer else "<span></span>")
    return (f'<nav class="weeknav" aria-label="More Hot Topics weeks">'
            f"{left}{right}</nav>")


def build_post(path, fm, body, older=None, newer=None):
    week_of = str(fm.get("week_of") or path.stem[:10])
    title = fm.get("title") or f"Week of {_week_label(week_of)}"
    dek = fm.get("dek") or _teaser(body)
    sources = fm.get("sources") or []
    html_body = md_to_html(body)
    n_topics = _topic_count(body)

    meta = (f"<span><b>Week of</b> {_week_label(week_of)}</span>"
            f'<span class="dot"></span><span>{n_topics} topic'
            f'{"s" if n_topics != 1 else ""}</span>')
    heading = S.article_head("Hot Topics", html.escape(title),
                             html.escape(dek), meta)
    body_html = (html_body + "\n" + _sources_comment(sources) + "\n" +
                 _week_nav(older, newer) + "\n" + _back_link())
    page = S.page_shell(
        title=f"{title} | Hot Topics",
        h1="", sub="",
        crumb='<a href="../index.html">Home</a> &rsaquo; '
              '<a href="index.html">Hot Topics</a>',
        body=body_html,
        current="hot-topics", depth=1,
        updated=UPDATED_LABEL,
        source_line="Hot Topics weekly feed; full source metadata published with each edition",
        raw_heading=heading,
        description=dek[:155],
        url_path=f"hot-topics/{week_of}.html",
    )
    out = OUT / f"{week_of}.html"
    out.write_text(page, encoding="utf-8")
    return {"week_of": week_of, "title": title, "dek": dek,
            "teaser": _teaser(body), "n_topics": n_topics,
            "url": f"/hot-topics/{week_of}.html", "sources": sources}


def _back_link():
    return ('<p class="note backlink">'
            '<a href="index.html">&larr; All Hot Topics weeks</a></p>')


def build_index(posts):
    if posts:
        items = []
        for p in posts:
            items.append(
                f'<a class="ht-item" href="{p["week_of"]}.html">'
                f'<p class="ht-date">Week of {_week_label(p["week_of"])}</p>'
                f'<h3><span>{html.escape(p["title"])}</span></h3>'
                f'<p class="teaser">{html.escape(p["teaser"])}</p>'
                f'<p class="ht-n">{p["n_topics"]} topic'
                f'{"s" if p["n_topics"] != 1 else ""}</p></a>')
        list_html = '<div class="ht-list">\n' + "\n".join(items) + "\n</div>"
    else:
        list_html = (
            '<div class="ht-empty"><p><b>Hot Topics launches here.</b> '
            'A weekly feed cross-checking the energy conversation against the '
            'week&apos;s actual market news: what corroborated the take, what '
            'updated it, what contradicted it. The archive is filling now; '
            'check back soon.</p></div>')
    page = S.page_shell(
        title="Hot Topics", h1="", sub="",
        crumb='<a href="../index.html">Home</a>',
        body=list_html,
        current="hot-topics", depth=1,
        updated=UPDATED_LABEL,
        source_line="Hot Topics weekly feed",
        raw_heading=S.article_head(
            "Hot Topics", "Hot Topics",
            "The week in WCSB, tested against the tape.",
            f'<span><b>{len(posts)}</b> week{"s" if len(posts) != 1 else ""} archived</span>'
            if posts else ""),
        description="Hot Topics: the week in WCSB, tested against the tape.",
        url_path="hot-topics/index.html",
    )
    (OUT / "index.html").write_text(page, encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    if SRC_DIR.is_dir():
        for md in sorted(SRC_DIR.glob("*.md")):
            try:
                fm, body = parse_post(md)
                items.append({"path": md, "fm": fm, "body": body,
                              "week_of": str(fm.get("week_of") or md.stem[:10]),
                              "title": fm.get("title") or md.stem[:10]})
            except Exception as e:
                print(f"hot-topics: skipping {md.name}: {e}", file=sys.stderr)
    items.sort(key=lambda t: t["week_of"], reverse=True)
    posts = []
    for i, it in enumerate(items):
        older = items[i + 1] if i + 1 < len(items) else None
        newer = items[i - 1] if i > 0 else None
        posts.append(build_post(it["path"], it["fm"], it["body"],
                                older=older, newer=newer))
    build_index(posts)
    # machine-readable manifest (full source metadata stays here, not in copy)
    import json
    manifest = [{"id": p["week_of"], "week_of": p["week_of"],
                 "title": p["title"], "condensation": p["teaser"],
                 "needs_verification": False, "sources": p["sources"]}
                for p in posts]
    (OUT / "hot-topics.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"hot-topics: {len(posts)} week(s) -> {OUT}/")


if __name__ == "__main__":
    main()
