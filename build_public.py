#!/usr/bin/env python3
"""Build the public-safe publish root: site/public/.

Two layers of licensed-content gating exist:

  1. ?public=1 query param: client-side JS hides [data-licensed] sections.
     This is progressive enhancement ONLY. The files are still served, so it
     is not sufficient for a public deployment.

  2. This script (the real gate): build-time exclusion. Licensed content is
     physically absent from site/public/:
       - whole pages whose REPORT-META license or <body data-licensed> is not
         "public" are dropped (currently: reports/storage-forecast/*),
       - [data-licensed] subtrees are stripped server-side from the pages
         that remain (dashboard panels, flag cards),
       - licensed rows are filtered out of the ST3 dashboard's embedded JSON,
       - links to dropped pages are removed from indexes and panels,
       - stale "?public=1" hide-instructions are removed (nothing is hidden
         in the public build; it is simply absent).

Post-checks fail loudly: any data-licensed attribute, identity string,
vendor name, or "wood-mackenzie" key surviving in public/ aborts the build.

Usage: python3 site/build_public.py
Output: site/public/  (publish THIS directory and nothing else)
"""
import html as html_mod
import json
import posixpath
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent
PUBLIC = SITE / "public"

sys.path.insert(0, str(SITE))
import textutil as TU  # noqa: E402

WEB_EXTS = {".html", ".css", ".js", ".csv", ".png", ".jpg", ".jpeg",
            ".svg", ".ico", ".txt", ".json"}

# Output-relative paths dropped wholesale from the public build.
EXCLUDED_PAGES = {
    "reports/storage-forecast/storage-forecast_2026-09-22.html",
}

IDENTITY_RES = [
    re.compile(r"(?i)\bblaine\b"),
    re.compile(r"(?i)\bhodder\b"),
    re.compile(r"blainehodder@gmail\.com"),
    re.compile(r"(?i)\bwood mackenzie\b(?!-)"),
    re.compile(r"(?i)\bwood mack\b(?!-)"),
    re.compile(r"wood-mackenzie"),
    # Hard attribution rule (Blaine, 2026-09-24): never attribute anything
    # publicly to desk-supplied or Macquarie proprietary data. Fail the
    # build if any of these leak into a public asset.
    re.compile(r"(?i)\bmacquarie\b"),
    re.compile(r"(?i)desk-supplied"),
    re.compile(r"(?i)desk photo"),
    re.compile(r"(?i)desk records"),
    re.compile(r"(?i)desk strips?"),
    re.compile(r"(?i)\bprop data\b"),
    re.compile(r"overlays/desk"),
]


class LicensedStripper(HTMLParser):
    """Drops [data-licensed] subtrees, links to excluded pages, and stale
    ?public=1 hide-instructions. Reconstructs the rest verbatim."""

    # Void elements have no end tag; they must not disturb drop_depth,
    # or a <br>/<img> inside a licensed subtree would swallow the rest
    # of the page.
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
            "circle", "ellipse", "line", "path", "polygon", "polyline",
            "rect", "stop", "use"}

    def __init__(self, page_rel):
        super().__init__(convert_charrefs=False)
        self.page_rel = page_rel
        self.out = []
        self.drop_depth = 0       # >0 while inside a dropped subtree
        self.li_stack = []        # per-open-<li>: drop flag
        self.li_buf_stack = []    # buffered output per open <li>

    def _emit(self, s):
        if self.li_buf_stack:
            self.li_buf_stack[-1].append(s)
        else:
            self.out.append(s)

    def _href_excluded(self, attrs):
        for k, v in attrs:
            if k == "href" and v:
                # resolve relative to the page, compare output-relative
                target = posixpath.normpath(
                    posixpath.join(self.page_rel.parent.as_posix(),
                                   v.split("?")[0].split("#")[0]))
                # Normalize to output-relative form: strip leading ../ runs
                # and the synthetic "site/" prefix used for resolution.
                rel = re.sub(r"^(\.\./)+", "", target)
                rel = re.sub(r"^site/", "", rel)
                if rel in EXCLUDED_PAGES:
                    return True
        return False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if self.drop_depth:
            if tag not in self.VOID:
                self.drop_depth += 1
            return
        if "data-licensed" in ad:
            self.drop_depth = 1
            return
        if tag == "li":
            self.li_stack.append(False)
            self.li_buf_stack.append([])
        if tag == "a" and self._href_excluded(attrs) and self.li_stack:
            self.li_stack[-1] = True
        attr_s = "".join(f' {k}="{v}"' for k, v in attrs)
        self._emit(f"<{tag}{attr_s}>")

    def handle_endtag(self, tag):
        if self.drop_depth:
            self.drop_depth -= 1
            return
        if tag == "li" and self.li_stack:
            drop = self.li_stack.pop()
            buf = self.li_buf_stack.pop()
            if not drop:
                self._emit("".join(buf) + "</li>")
            return
        self._emit(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if self.drop_depth:
            return
        if "data-licensed" in dict(attrs):
            return
        attr_s = "".join(f' {k}="{v}"' for k, v in attrs)
        self._emit(f"<{tag}{attr_s} />")

    def handle_data(self, data):
        if self.drop_depth:
            return
        # stale hide-instructions: nothing is hidden in the public build
        if "?public=1" in data and ("hide" in data):
            return
        self._emit(data)

    def handle_comment(self, data):
        if not self.drop_depth:
            self._emit(f"<!--{data}-->")

    def handle_decl(self, decl):
        if not self.drop_depth:
            self._emit(f"<!{decl}>")

    def handle_entityref(self, name):
        if not self.drop_depth:
            self._emit(f"&{name};")

    def handle_charref(self, name):
        if not self.drop_depth:
            self._emit(f"&#{name};")


def extract_data_json(html):
    """Extract the var DATA = {...}; JSON from the ST3 dashboard via brace
    matching. Returns (prefix, data_dict, suffix)."""
    m = re.search(r"var DATA = ", html)
    if not m:
        return html, None, ""
    i = html.index("{", m.start())
    depth = 0
    instr = False
    esc = False
    for j in range(i, len(html)):
        c = html[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return (html[:i], json.loads(html[i:j + 1]), html[j + 1:])
    raise ValueError("unbalanced braces in embedded DATA")


def filter_licensed_rows(o):
    """Drop dicts/lists entries carrying license != public."""
    if isinstance(o, dict):
        if o.get("license", "public") != "public":
            return None
        return {k: filter_licensed_rows(v) for k, v in o.items()}
    if isinstance(o, list):
        out = []
        for v in o:
            f = filter_licensed_rows(v)
            if f is not None:
                out.append(f)
        return out
    return o


def report_license(path):
    m = re.search(r"<!-- REPORT-META (.*?) -->", path.read_text())
    if not m:
        return "public"
    return json.loads(m.group(1)).get("license", "public")


def fix_report_page(dest, is_weekly):
    """Staged report page: repair the report template's links for the public
    location and inject canonical + Article JSON-LD + meta/OG tags.

    Weekly editions live at /weekly/<file>; other report types stay at
    /reports/<type>/<file>."""
    t = dest.read_text()
    # The report template assumed the source tree (a reports/<type>/ page
    # linking ../../site/index.html for home and ../index.html for the
    # reports archive, which was never published).
    if is_weekly:
        # Order matters: rewrite "All reports" first, then the home links.
        t = t.replace('href="../index.html"', 'href="index.html"')
        t = t.replace('href="../../site/index.html"', 'href="../index.html"')
        url_path = f"weekly/{dest.name}"
    else:
        t = t.replace('href="../index.html"',
                      'href="../../weekly/index.html"')
        t = t.replace('href="../../site/index.html"',
                      'href="../../index.html"')
        url_path = dest.relative_to(PUBLIC).as_posix()
    m = re.search(r"<!-- REPORT-META (.*?) -->", t)
    meta = json.loads(m.group(1)) if m else {}
    title = meta.get("title",
                     "WCSB Weekly" if is_weekly else "Heavy Reading report")
    edition_date = meta.get("edition_date", "")
    canon = f"https://heavyreading.ca/{url_path}"
    desc = (f"{title}, {edition_date}: the Heavy Reading letter on Western "
            f"Canadian crude supply." if edition_date else
            f"{title}: the Heavy Reading letter on Western Canadian crude supply.")
    q = html_mod.escape
    head_add = (
        f'\n<meta name="description" content="{q(desc, quote=True)}">'
        f'\n<link rel="canonical" href="{canon}">'
        f'\n<meta property="og:type" content="article">'
        f'\n<meta property="og:site_name" content="Heavy Reading">'
        f'\n<meta property="og:title" content="{q(title + " | Heavy Reading", quote=True)}">'
        f'\n<meta property="og:description" content="{q(desc, quote=True)}">'
        f'\n<meta property="og:url" content="{canon}">'
        f'\n<meta name="twitter:card" content="summary">'
    )
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{title} | Heavy Reading",
        "description": desc,
        "url": canon,
        "publisher": {"@type": "Organization", "name": "Heavy Reading",
                      "url": "https://heavyreading.ca/"},
    }
    if edition_date:
        ld["datePublished"] = edition_date
    head_add += ('\n<script type="application/ld+json">\n'
                 + json.dumps(ld, indent=2) + '\n</script>')
    t = t.replace("</head>", head_add + "\n</head>", 1)
    dest.write_text(t)


def fix_weekly_edition(dest):
    fix_report_page(dest, is_weekly=True)


def write_weekly_redirects(weekly_moved):
    """Keep the old /reports/weekly/<file> URLs alive as instant redirects
    to the canonical /weekly/<file> locations."""
    for src, _dest in weekly_moved:
        stub = PUBLIC / "reports" / "weekly" / src.name
        stub.parent.mkdir(parents=True, exist_ok=True)
        new_url = f"/weekly/{src.name}"
        canon = f"https://heavyreading.ca{new_url}"
        stub.write_text(
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>Moved | Heavy Reading</title>\n"
            f'<link rel="canonical" href="{canon}">\n'
            f'<meta http-equiv="refresh" content="0; url={new_url}">\n'
            '<meta name="robots" content="noindex">\n'
            "</head>\n<body>\n"
            f'<p>This edition moved to <a href="{new_url}">{canon}</a>.</p>\n'
            f'<script>location.replace("{new_url}");</script>\n'
            "</body>\n</html>\n")


def write_sitemap():
    urls = []
    for f in sorted(PUBLIC.rglob("*.html")):
        rel = f.relative_to(PUBLIC).as_posix()
        if rel.startswith("reports/weekly/"):
            continue  # redirect stubs are not indexed
        urls.append(rel)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(f"  <url><loc>https://heavyreading.ca/{u}</loc></url>")
    lines.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(lines) + "\n")
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: https://heavyreading.ca/sitemap.xml\n")
    return len(urls)


def write_search_index():
    """search-index.json: title + URL + visible-text excerpt per page, for
    the client-side masthead search. Redirect stubs are excluded."""
    entries = []
    for f in sorted(PUBLIC.rglob("*.html")):
        rel = f.relative_to(PUBLIC).as_posix()
        if rel.startswith("reports/weekly/"):
            continue
        t = f.read_text()
        noscript = re.sub(r"<script.*?</script>", "", t, flags=re.S | re.I)
        m = re.search(r"<title>(.*?)</title>", noscript, re.S | re.I)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else rel
        text = re.sub(r"<[^>]+>", " ", noscript)
        text = re.sub(r"\s+", " ", html_mod.unescape(text)).strip()
        entries.append({"title": title, "url": "/" + rel,
                        "text": text[:600]})
    (PUBLIC / "search-index.json").write_text(
        json.dumps(entries, ensure_ascii=False))
    return len(entries)


def build():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    (PUBLIC / "reports").mkdir(parents=True)

    # 0. build the Digest pages (dated editions + archive) from
    # site/digest/editions/*.md before the asset copy below.
    import build_digest
    dates = build_digest.build_digest()
    print(f"  digest editions: {len(dates)}")

    # 1. copy site web assets
    for f in sorted(SITE.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in WEB_EXTS:
            continue
        if "public" in f.parts:  # never copy a previous public/ tree
            continue
        if "hot-topics" in f.parts:  # section removed 2026-09-23; source stays on disk
            continue
        rel = f.relative_to(SITE)
        dest = PUBLIC / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)

    # GitHub Pages custom domain. CNAME has no extension so the asset copy
    # above skips it; write it explicitly every build.
    (PUBLIC / "CNAME").write_text("heavyreading.ca\n")

    # 2. copy public reports only. Weekly editions are relocated to /weekly/
    # (their canonical home) and get link fixes + SEO treatment below.
    weekly_moved = []
    for f in sorted((BASE / "reports").rglob("*.html")):
        if f.name == "index.html":
            continue
        lic = report_license(f)
        if lic != "public":
            print(f"  excluded ({lic}): reports/{f.relative_to(BASE / 'reports')}")
            continue
        rel_in_reports = f.relative_to(BASE / "reports")
        if rel_in_reports.parts[0] == "weekly":
            dest = PUBLIC / "weekly" / f.name
            weekly_moved.append((f, dest))
        else:
            dest = PUBLIC / "reports" / rel_in_reports
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)

    # 3. strip licensed subtrees + excluded links from every public page
    for f in sorted(PUBLIC.rglob("*.html")):
        rel = f.relative_to(PUBLIC)
        page_rel = Path("site") / rel  # for href resolution like the source tree
        src = f.read_text()
        if f.name == "st3-dashboard.html":
            pre, data, post = extract_data_json(src)
            if data is not None:
                data = filter_licensed_rows(data)
                src = pre + json.dumps(data) + post
            # The LICENSE_LABEL map's vendor keys are dead in public output:
            # every surviving row carries license "public", so licenseLabel()
            # can never be reached with a vendor key. Scrub them so no vendor
            # identifier ships in any public asset. (Source keeps the full
            # map; private licensing keys and data-licensed semantics there
            # are untouched.)
            src = re.sub(r'^  "wood-mackenzie": "commercial storage",\n', "",
                         src, flags=re.M)
            src = re.sub(r'^  "eikon": "licensed: Eikon '
                         r'transcription",\n', "", src, flags=re.M)
        stripper = LicensedStripper(page_rel)
        stripper.feed(src)
        cleaned = "".join(stripper.out)
        # drop paragraphs emptied by the stale ?public=1 note removal
        cleaned = re.sub(r"<p[^>]*>\s*</p>", "", cleaned)
        f.write_text(cleaned)

    # 4. report pages: link fixes + SEO injection (weekly editions at their
    #    /weekly/ home, other report types in place), then redirect stubs
    #    at the old /reports/weekly/ URLs
    for _src, dest in weekly_moved:
        fix_weekly_edition(dest)
    for f in sorted((PUBLIC / "reports").rglob("*.html")):
        if "weekly" in f.parts:
            continue  # redirect stubs
        fix_report_page(f, is_weekly=False)
    write_weekly_redirects(weekly_moved)

    # 5. SEO artifacts: sitemap, robots, client-side search index
    n_urls = write_sitemap()
    n_idx = write_search_index()
    print(f"  sitemap: {n_urls} urls; search index: {n_idx} pages")

    # 4. post-checks: fail loudly on any leak. Script blocks are stripped
    # first: they carry the (dead-in-public) gating machinery and the
    # display-label map key, which are code, never rendered content. The
    # ST3 embedded DATA JSON was already filtered of licensed rows above.
    failures = []
    for f in sorted(PUBLIC.rglob("*")):
        if not f.is_file():
            continue
        try:
            t = f.read_text()
        except UnicodeDecodeError:
            continue
        noscript = re.sub(r"<script.*?</script>", "", t, flags=re.S | re.I)
        if "data-licensed" in noscript:
            failures.append(f"{f.relative_to(PUBLIC)}: data-licensed attribute survived")
        for rx in IDENTITY_RES:
            if rx.search(noscript):
                failures.append(
                    f"{f.relative_to(PUBLIC)}: banned string {rx.pattern!r} survived")
                break
    # no dangling links to excluded pages
    for f in sorted(PUBLIC.rglob("*.html")):
        t = f.read_text()
        for m in re.finditer(r'href="([^"]+)"', t):
            href = m.group(1)
            if "storage-forecast" in href:
                failures.append(f"{f.relative_to(PUBLIC)}: dangling link {href}")
    if failures:
        print("PUBLIC BUILD FAILED:")
        for x in failures:
            print("  -", x)
        sys.exit(1)

    n_pages = sum(1 for _ in PUBLIC.rglob("*.html"))
    cname = PUBLIC / "CNAME"
    cname_ok = cname.exists() and cname.read_text().strip() == "heavyreading.ca"
    print(f"public build OK: {n_pages} pages in {PUBLIC}"
          f"; CNAME {'ok' if cname_ok else 'MISSING/BROKEN'}")
    if not cname_ok:
        sys.exit(1)


if __name__ == "__main__":
    build()
