#!/usr/bin/env python3
"""Shared site chrome for Heavy Reading: nav, CSS, SVG charts, citations.

Used by build_projects.py and build_sections.py so every page carries the
same masthead, section nav, UPDATED/SOURCE discipline, live SVG chart style,
and full citation block. No data is invented here; every number is passed in
by the builders from the dashboard DATA or repo annotations.
"""
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
sys.path.insert(0, str(SITE))
import build_st3_dashboard as B  # noqa: E402  (constants + _mname; import is side-effect free)

mname = B._mname
edition_date = B._edition_date

# License display labels and anonymity helpers live in textutil (no circular
# imports: build_st3_dashboard cannot import shared, but both import textutil).
# Re-exported here so builders can keep using S.license_label / S.anon_data.
from textutil import (  # noqa: E402
    FAVICON_LINK,
    FONT_LINKS,
    LICENSE_DISPLAY,
    LICENSE_DISPLAY_JS,
    PAGE_CSS,
    anon_data,
    anon_text,
    brand_lockup,
    license_label,
)
import re  # noqa: E402

# ----------------------------------------------------------------------------
# Interlinking: the site is a web, not isolated pages. Every project name that
# appears in page body copy (tables, lists, article bodies) links to its
# project page. This is a first-principles requirement for a data publication:
# the reader should never hit a dead end on an entity the site covers.
# Applied automatically in page_shell(); the JS-rendered ST3 dashboard gets
# the same treatment via ROW_LINKS in build_st3_dashboard.py.
# ----------------------------------------------------------------------------

# Names prose and tables use that differ from the roster's canonical name.
_PROJECT_ALIASES = {
    "Primrose/Wolf Lake": "cnq_primrose",
    "Primrose": "cnq_primrose",
    "Suncor Base Plant": "su_base_plant",
    "MEG Christina Lake": "meg_christina_lake",
}

# Fallback if annotations/projects.yaml is ever unreadable at build time.
_FALLBACK_PROJECTS = (
    ("Foster Creek", "cve_foster_creek"),
    ("Christina Lake", "cve_christina_lake"),
    ("Sunrise", "cve_sunrise"),
    ("Narrows Lake", "narrows_lake"),
    ("Firebag", "su_firebag"),
    ("MacKay River", "su_mackay_river"),
    ("Jackfish", "cnq_jackfish"),
    ("Kirby", "cnq_kirby"),
    ("Surmont", "cop_surmont"),
    ("Christina Lake North", "meg_christina_lake"),
    ("Leismer", "ath_leismer"),
    ("Hangingstone", "ath_hangingstone"),
    ("Hangingstone Expansion", "gfr_hangingstone_exp"),
    ("Orion", "scr_orion"),
    ("Lindbergh", "scr_lindbergh"),
    ("Tucker", "scr_tucker"),
    ("Great Divide", "connacher_great_divide"),
    ("BlackGold", "harvest_blackgold"),
    ("Blackrod", "ipc_blackrod"),
    ("MacKay River (PetroChina)", "petrochina_mackay"),
    ("Cold Lake", "imo_cold_lake"),
    ("Primrose and Wolf Lake", "cnq_primrose"),
    ("Peace River", "cnq_peace_river"),
    ("Kearl", "imo_kearl"),
    ("Fort Hills", "su_fort_hills"),
    ("Horizon", "cnq_horizon"),
    ("Base Plant", "su_base_plant"),
    ("Syncrude", "syncrude"),
    ("Long Lake Upgrader", "cnooc_long_lake_upgrader"),
)

_link_targets = None
_linkify_rx = None


def project_link_targets():
    """[(display name, project id)], longest name first. Cached."""
    global _link_targets
    if _link_targets is None:
        pairs = []
        try:
            import yaml
            yf = (SITE.parent.parent.parent / "annotations" / "projects.yaml")
            roster = yaml.safe_load(yf.read_text(encoding="utf-8"))["projects"]
            pairs = [(p["name"], p["id"]) for p in roster]
        except Exception:
            pairs = list(_FALLBACK_PROJECTS)
        seen = {n for n, _ in pairs}
        for name, pid in _PROJECT_ALIASES.items():
            if name not in seen:
                pairs.append((name, pid))
        pairs.sort(key=lambda t: -len(t[0]))
        _link_targets = pairs
    return _link_targets


_TAG_TOK = re.compile(r"(<[^>]+>)")
_OPEN_TAG = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9]*)")
_CLOSE_TAG = re.compile(r"<\s*/\s*([a-zA-Z][a-zA-Z0-9]*)")
# Elements whose text is never linkified: existing links, headlines (kept
# clean), code, scripts/styles, and SVG <title> tooltips.
_SKIP_EL = {"a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre",
            "script", "style", "textarea", "title"}


def linkify(html, depth, current_url=""):
    """Link known project names in body HTML to their project pages.

    Only bare text is touched: anything inside an existing link, heading,
    code block, or script/style element is left alone. depth sets the
    relative href prefix ("../" per level). current_url is the page's own
    root-relative path (e.g. "projects/cnq_horizon.html"); a project page
    never links to itself.
    """
    global _linkify_rx
    targets = project_link_targets()
    if not targets:
        return html
    if _linkify_rx is None:
        alt = "|".join(re.escape(n) for n, _ in targets)
        _linkify_rx = re.compile(r"(?<!\w)(?:" + alt + r")(?!\w)")
    by_name = dict(targets)
    prefix = "../" * depth
    cur = current_url or "index.html"
    stack, out = [], []
    for tok in _TAG_TOK.split(html):
        if not tok:
            continue
        if tok.startswith("<"):
            m = _CLOSE_TAG.match(tok)
            if m:
                tag = m.group(1).lower()
                if stack and stack[-1] == tag:
                    stack.pop()
            else:
                m = _OPEN_TAG.match(tok)
                if m:
                    tag = m.group(1).lower()
                    if tag in _SKIP_EL and not tok.rstrip().endswith("/>"):
                        stack.append(tag)
            out.append(tok)
            continue
        if stack:
            out.append(tok)
            continue

        def _rep(m):
            name = m.group(0)
            pid = by_name[name]
            if f"projects/{pid}.html" == cur:
                return name
            return (f'<a class="plink" href="{prefix}projects/{pid}.html">'
                    f"{name}</a>")

        out.append(_linkify_rx.sub(_rep, tok))
    return "".join(out)

# ----------------------------------------------------------------------------
# Section navigation: 5 intent groups shared by the desktop line nav and the
# mobile burger. The homepage itself is the latest (the brand lockup returns
# home), so there is no separate Latest item.
#
#   The Letter  -> this week's edition, edition archive
#   The Digest  -> the morning crude digest, published as dated pages + archive
#   Supply      -> dashboard, balance, maintenance, projects (29 asset pages
#                  grouped In-situ / Mined / Upgrading)
#   World       -> Venezuela watch (room for OPEC, Middle East, Atlantic basin)
#   Reference   -> field guide, data, sources, methodology
# ----------------------------------------------------------------------------
NAV_GROUPS = [
    {
        "key": "letter", "label": "The Letter", "landing": "weekly",
        "items": [
            {"key": "newest", "label": "This week's edition"},
            {"key": "weekly", "label": "Edition archive"},
        ],
    },
    {
        "key": "supply", "label": "Supply", "landing": "supply",
        "items": [
            {"key": "supply", "label": "Supply hub"},
            {"key": "trading", "label": "Dashboard"},
            {"key": "balance", "label": "Balance"},
            {"key": "maintenance", "label": "Maintenance"},
            {"key": "projects", "label": "Projects", "mega": True},
        ],
    },
    {
        "key": "world", "label": "World", "landing": "world",
        "items": [
            {"key": "hormuz", "label": "Hormuz watch"},
            {"key": "iran", "label": "Iran watch"},
            {"key": "redsea", "label": "Red Sea"},
            {"key": "russia-refining", "label": "Russian refineries"},
            {"key": "china-imports", "label": "China imports"},
            {"key": "spr-storage", "label": "SPR & storage"},
            {"key": "venezuela", "label": "Venezuela watch"},
            {"key": "trump", "label": "Trump watch"},
            {"key": "sour", "label": "The global sour barrel"},
        ],
    },
    {
        "key": "digest", "label": "The Digest", "landing": "digest",
        "items": [
            {"key": "digest", "label": "Edition archive"},
        ],
    },
    {
        "key": "reference", "label": "Reference", "landing": "fieldguide",
        "items": [
            {"key": "fieldguide", "label": "Field Guide"},
            {"key": "data", "label": "Data"},
            {"key": "sources", "label": "Sources"},
            {"key": "methodology", "label": "Methodology"},
        ],
    },
]

# page key -> nav group key, for the active-group highlight. Home stands alone.
GROUP_OF = {
    "home": None,
    "supply": "supply",
    "trading": "supply", "balance": "supply", "maintenance": "supply",
    "projects": "supply",
    "weekly": "letter",
    "digest": "digest",
    "world": "world", "venezuela": "world",
    "hormuz": "world", "iran": "world", "redsea": "world", "russia-refining": "world",
    "china-imports": "world", "spr-storage": "world", "sour": "world",
    "trump": "world",
    "fieldguide": "reference", "data": "reference",
    "sources": "reference", "methodology": "reference",
}

# href target for each nav key, relative to the site root.
_TARGETS = {
    "home": "index.html",
    "supply": "supply/index.html",
    "trading": "st3-dashboard.html",
    "balance": "balance/index.html",
    "maintenance": "maintenance/index.html",
    "projects": "projects/index.html",
    "fieldguide": "fieldguide/index.html",
    "weekly": "weekly/index.html",
    "sources": "sources/index.html",
    "data": "data/index.html",
    "venezuela": "venezuela/index.html",
    "world": "world/index.html",
    "hormuz": "world/hormuz/index.html",
    "iran": "world/iran/index.html",
    "redsea": "world/redsea/index.html",
    "russia-refining": "world/russia-refining/index.html",
    "china-imports": "world/china-imports/index.html",
    "spr-storage": "world/spr-storage/index.html",
    "sour": "world/sour/index.html",
    "opec-middle-east": "world/opec-middle-east/index.html",
    "condensate-diluent": "world/condensate-diluent/index.html",
    "refinery-margins": "world/refinery-margins/index.html",
    "trump": "world/trump/index.html",
    "digest": "digest/index.html",
    "methodology": "methodology/index.html",
    "reports": "../reports/index.html",
}


def href(key, depth, current):
    """Nav href for a key from a page at the given depth.

    depth: 0 = site root (index.html, st3-dashboard.html),
           1 = section dir (balance/, maintenance/, ...),
           2 = projects/<profile>.html.
    """
    base = ["", "../", "../../"][depth]
    if key == current and depth > 0:
        return "index.html"
    return base + _TARGETS[key]


def nav(current, depth):
    """4-group section nav: desktop dropdown line + mobile burger.

    Each group is a <details> whose summary carries the landing-page link and
    a caret toggle. Desktop opens the menu on hover (caret click also works);
    the burger checkbox reveals the stacked groups on phones.
    """
    base = ["", "../", "../../"][depth]
    newest = newest_weekly_file()
    if newest:
        # From the weekly archive itself, link by bare filename; from
        # anywhere else, prefix the weekly directory.
        newest_href = newest if current == "weekly" else base + "weekly/" + newest
    else:
        newest_href = href("weekly", depth, current)
    group = GROUP_OF.get(current)
    parts = [
        # Mobile menu is a <details> disclosure: a labeled button on phones,
        # an invisible wrapper on desktop. No hidden checkbox inputs.
        '<details class="mnav">',
        ('<summary class="navburger" aria-label="Sections menu">'
         '<span class="nb-ic" aria-hidden="true"><span></span><span></span><span></span></span>'
         '<span class="nb-tx">Sections</span></summary>'),
        '<nav class="sitenav" aria-label="Sections">',
    ]
    for g in NAV_GROUPS:
        active = " active" if g["key"] == group else ""
        open_attr = " open" if g["key"] == group else ""
        top_href = href(g["landing"], depth, current)
        top_cur = ' aria-current="page"' if g["landing"] == current else ""
        menu = []
        for it in g["items"]:
            if it["key"] == "newest":
                menu.append(f'<a class="mi" href="{newest_href}">'
                            "This week&apos;s edition</a>")
                continue
            if it.get("mega"):
                menu.append(_projects_mega(current, depth, base))
                continue
            h = href(it["key"], depth, current)
            cur = ' aria-current="page"' if it["key"] == current else ""
            menu.append(f'<a class="mi" href="{h}"{cur}>{it["label"]}</a>')
        parts.append(
            f'<div class="navdrop{active}"><details class="nd"{open_attr}>'
            f'<summary class="nd-sum"><a class="nd-top" href="{top_href}"{top_cur}>'
            f'{g["label"]}</a><span class="nd-caret" aria-hidden="true"></span></summary>'
            f'<div class="nd-menu">{"".join(menu)}</div>'
            "</details></div>")
    parts.append("</nav>")
    parts.append("</details>")
    return "\n      ".join(parts)


_NEWEST_WEEKLY = None


def newest_weekly_file():
    """Newest edition filename in reports/weekly, or None."""
    global _NEWEST_WEEKLY
    if _NEWEST_WEEKLY is None:
        files = sorted((SITE.parent / "reports" / "weekly").glob("wcsb-weekly_*.html"))
        _NEWEST_WEEKLY = files[-1].name if files else None
    return _NEWEST_WEEKLY


_PROJECT_MENU = None


def _project_menu_groups():
    """Roster for the Projects mega menu: [(label, anchor, [(id, name), ...])]."""
    global _PROJECT_MENU
    if _PROJECT_MENU is None:
        import yaml
        recs = yaml.safe_load(
            (SITE.parent.parent.parent / "annotations" / "projects.yaml"
             ).read_text())["projects"]
        buckets = {"in-situ": [], "mining": [], "upgrading": []}
        for r in recs:
            t = r.get("type", "")
            item = (r["id"], r["name"])
            if t in ("sagd", "css"):
                buckets["in-situ"].append(item)
            elif t in ("mined", "integrated"):
                buckets["mining"].append(item)
            elif t == "upgrading":
                buckets["upgrading"].append(item)
        _PROJECT_MENU = [
            ("In-situ", "in-situ", buckets["in-situ"]),
            ("Mined", "mining", buckets["mining"]),
            ("Upgrading", "upgrading", buckets["upgrading"]),
        ]
    return _PROJECT_MENU


def _projects_mega(current, depth, base):
    """Projects dropdown: four links, not 29. Every project profile is one
    tap away via All projects; the category anchors jump to the grouped
    sections on the projects index."""
    on_projects = current == "projects"
    idx = "index.html" if on_projects else base + "projects/index.html"
    links = [f'<a class="mi" href="{idx}">All projects</a>']
    for label, anchor in (("In-situ", "insitu"),
                          ("Mined", "mined"),
                          ("Upgrading", "upgrading")):
        links.append(f'<a class="mi" href="{idx}#{anchor}">{label}</a>')
    return '<div class="nd-megahead">' + "".join(links) + "</div>"


# ----------------------------------------------------------------------------
# Nav behavior: menus close themselves. One dropdown open at a time; a tap
# on any menu link, an outside tap, or Escape closes everything; the mobile
# Sections disclosure closes when a same-page anchor link is tapped so it
# never covers the content after navigation.
# ----------------------------------------------------------------------------
NAV_JS = """<script>
(function(){
  // The mobile-nav <details> is a disclosure on phones but the plain
  // ruled nav bar on desktop: open it wherever the burger is hidden.
  var mnav = document.querySelector('details.mnav');
  if (mnav && window.matchMedia('(min-width: 641px)').matches) {
    mnav.setAttribute('open', '');
  }
  function closeAll(){
    document.querySelectorAll('details.nd[open]').forEach(function(d){
      d.removeAttribute('open');
    });
  }
  function closeMobile(){
    // Never close the desktop bar: its burger is hidden, so a closed
    // details would strand the nav with no way back open.
    if (window.matchMedia('(min-width: 641px)').matches) return;
    var m = document.querySelector('details.mnav[open]');
    if (m) m.removeAttribute('open');
  }
  document.querySelectorAll('details.nd').forEach(function(d){
    d.addEventListener('toggle', function(){
      if (d.open) {
        document.querySelectorAll('details.nd').forEach(function(o){
          if (o !== d && o.open) o.removeAttribute('open');
        });
      }
    });
  });
  document.addEventListener('click', function(e){
    if (e.target.closest('.nd-menu a')) {
      closeAll();
      closeMobile();
      return;
    }
    if (!e.target.closest('.navdrop')) closeAll();
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') {
      closeAll();
      closeMobile();
    }
  });
})();
</script>"""


# ----------------------------------------------------------------------------
# Theme toggle: warm-charcoal dark mode. The choice persists in localStorage;
# with no stored choice the OS preference wins. A tiny inline script in
# <head> (THEME_HEAD) sets the theme before first paint so there is no flash.
# ----------------------------------------------------------------------------
THEME_HEAD = """<script>
(function(){try{var t=localStorage.getItem('hr-theme');
if(t){document.documentElement.setAttribute('data-theme',t);}else if
(window.matchMedia('(prefers-color-scheme: dark)').matches){
document.documentElement.setAttribute('data-theme','dark');}}catch(e){}})();
</script>"""

THEME_JS = """<script>
(function(){
  var btn = document.getElementById('themetoggle');
  if (!btn) return;
  function label(){
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    btn.textContent = dark ? 'Light' : 'Dark';
  }
  btn.addEventListener('click', function(){
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    try {
      if (dark) { document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('hr-theme', 'light'); }
      else { document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('hr-theme', 'dark'); }
    } catch (e) {
      if (dark) document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', 'dark');
    }
    label();
  });
  label();
})();
</script>"""


def theme_toggle():
    """One quiet word in the masthead corner. Label set by THEME_JS."""
    return ('<button class="themetoggle" id="themetoggle" type="button" '
            'aria-label="Toggle dark mode">Dark</button>')


# ----------------------------------------------------------------------------
# Site search: a small box in the masthead backed by search-index.json
# (generated by build_public.py). No dependencies, no server.
# ----------------------------------------------------------------------------
def search_box(depth):
    base = ["", "../", "../../"][depth]
    return (
        f'<div class="searchbox" role="search">'
        f'<input type="search" id="sitesearch" placeholder="Search Heavy Reading" '
        f'aria-label="Search Heavy Reading" autocomplete="off" '
        f'data-index="{base}search-index.json">'
        f'<div class="searchres" id="searchres" hidden></div>'
        f"</div>"
    )


SEARCH_JS = """<script>
(function(){
  var box = document.getElementById('sitesearch');
  if (!box) return;
  var res = document.getElementById('searchres');
  var idx = null;
  function esc(s){ return s.replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  box.addEventListener('input', function(){
    var q = box.value.trim().toLowerCase();
    if (q.length < 2) { res.hidden = true; res.innerHTML = ''; return; }
    function run(){
      var hits = [];
      var words = q.split(/\\s+/);
      idx.forEach(function(p){
        var hay = (p.title + ' ' + p.text).toLowerCase();
        var score = 0;
        words.forEach(function(w){
          if (p.title.toLowerCase().indexOf(w) !== -1) score += 3;
          else if (hay.indexOf(w) !== -1) score += 1;
        });
        if (score > 0) hits.push({p: p, s: score});
      });
      hits.sort(function(a, b){ return b.s - a.s; });
      hits = hits.slice(0, 8);
      if (!hits.length) {
        res.innerHTML = '<div class="sr-none">No matches. Try "maintenance", "Cold Lake", or "turnaround".</div>';
      } else {
        res.innerHTML = hits.map(function(h){
          return '<a class="sr-hit" href="' + h.p.url + '"><b>' + esc(h.p.title) +
                 '</b><span>' + esc(h.p.text.slice(0, 110)) + '</span></a>';
        }).join('');
      }
      res.hidden = false;
    }
    if (idx) { run(); return; }
    fetch(box.getAttribute('data-index')).then(function(r){ return r.json(); })
      .then(function(j){ idx = j; run(); })
      .catch(function(){ res.hidden = true; });
  });
  document.addEventListener('click', function(e){
    if (!e.target.closest('.searchbox')) { res.hidden = true; }
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') { res.hidden = true; box.blur(); }
  });
})();
</script>"""


def footer(depth, current=""):
    """Real footer: the four sections plus key pages, then a plain-language
    colophon. No implementation jargon."""
    base = ["", "../", "../../"][depth]
    newest = newest_weekly_file()
    newest_href = (newest if current == "weekly"
                   else base + "weekly/" + newest) if newest \
        else base + "weekly/index.html"
    letter_links = [
        ("This week&apos;s edition", newest_href),
        ("Edition archive", base + "weekly/index.html"),
    ]
    cols = [
        ("The Letter", letter_links),
        ("Supply", [("Supply hub", base + "supply/index.html"),
                       ("Dashboard", base + "st3-dashboard.html"),
                    ("S&amp;D balance", base + "balance/index.html"),
                    ("Maintenance", base + "maintenance/index.html"),
                    ("All projects", base + "projects/index.html")]),
        ("World", [("Hormuz watch", base + "world/hormuz/index.html"),
                   ("Iran watch", base + "world/iran/index.html"),
                   ("Red Sea", base + "world/redsea/index.html"),
                   ("Russian refineries", base + "world/russia-refining/index.html"),
                   ("China imports", base + "world/china-imports/index.html"),
                   ("SPR & storage", base + "world/spr-storage/index.html"),
                   ("The global sour barrel", base + "world/sour/index.html"),
                   ("Venezuela watch", base + "venezuela/index.html"),
                   ("Trump watch", base + "world/trump/index.html"),
                   ("World", base + "world/index.html")]),
        ("The Digest", [("Latest digest", base + "digest/index.html"),
                   ("Edition archive", base + "digest/index.html")]),
        ("Reference", [("Field guide", base + "fieldguide/index.html"),
                       ("Data downloads", base + "data/index.html"),
                       ("Sources", base + "sources/index.html"),
                       ("Methodology", base + "methodology/index.html")]),
    ]
    col_html = "".join(
        f'<div class="fcol"><h4>{title}</h4>' + "".join(
            f'<a href="{h}">{label}</a>' for label, h in links
        ) + "</div>"
        for title, links in cols)
    return (
        f'<footer class="sitefoot"><div class="fcols">{col_html}</div>'
        f'<p class="fcolophon"><b>Heavy Reading</b>: the WCSB supply letter. '
        f"Every number on this site comes from public sources: AER filings, "
        f"CER data, and company disclosures, run through the WCSB S&amp;D "
        f"model. How each figure was built is on the "
        f'<a href="{base}methodology/index.html">methodology</a> page; '
        f"where every fact came from is in <a href=\"{base}sources/index.html\">"
        f"sources</a>.</p></footer>"
    )


# ---- editorial components ----

def article_head(kicker, title, dek="", meta=""):
    """Magazine article header: kicker / serif headline / dek / meta row.
    kicker/title/dek/meta are HTML fragments (already escaped by the caller)."""
    out = ['<header class="arthead">']
    if kicker:
        out.append(f'<p class="kicker">{kicker}</p>')
    out.append(f'<h1 class="arttitle">{title}</h1>')
    if dek:
        out.append(f'<p class="dek">{dek}</p>')
    if meta:
        out.append(f'<div class="artmeta">{meta}</div>')
    out.append("</header>")
    return "\n".join(out)


def fnref(n):
    """Inline footnote reference: <sup class="fnref"><a href="#fn-3" id="fnref-3">3</a></sup>."""
    return (f'<sup class="fnref"><a href="#fn-{n}" id="fnref-{n}" '
            f'aria-label="See note {n}">{n}</a></sup>')


def footnotes(items):
    """Collected source notes at the foot of an article.

    items: [(n, html), ...] in the order cited. Each gets a back-link to
    its inline reference. Returns "" when empty."""
    if not items:
        return ""
    lis = "".join(
        f'<li id="fn-{n}">{html} '
        f'<a class="fnback" href="#fnref-{n}" aria-label="Back to text">&#8617;</a></li>'
        for n, html in items)
    return (f'<section class="footnotes" aria-label="Sources and notes">'
            f'<h2>Sources &amp; notes</h2><ol>{lis}</ol></section>')


def cap_src(caption, source):
    """Figure caption with a bolded Source line: caption HTML + source HTML."""
    return f"{caption} <b>Source:</b> {source}"



# Hide licensed blocks when ?public=1 is present. Same rule as the dashboard.
GATE_JS = """<script>
(function () {
  try {
    if (new URLSearchParams(window.location.search).get("public") === "1") {
      document.querySelectorAll("[data-licensed]").forEach(function (el) {
        el.style.display = "none";
      });
    }
  } catch (e) {}
})();
</script>"""


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def f1(v):
    return "n/a" if v is None else f"{v:,.1f}"


def page_shell(title, h1, sub, crumb, body, current, depth, updated,
               source_line, public_only=True, gate_js=False, description="",
               url_path="", masthead_h1=False, raw_heading=""):
    """Full page. updated: "September 23, 2026". source_line: short SOURCE text.
    description: meta description (also used for social preview tags).
    url_path: page path relative to the site root, e.g. "maintenance/index.html"
      ("" for the home page); drives the canonical URL and og:url.
    masthead_h1: render the brand wordmark as the page h1 (home page only)
      and skip the standalone h1, so the brand is not announced twice.
    raw_heading: full heading HTML (e.g. an article_head() block) used in
      place of the default h1/sub block when supplied.
    crumb: breadcrumb HTML, or None to omit (home page)."""
    gate = GATE_JS if gate_js else ""
    canon = f"https://heavyreading.ca/{url_path}" if url_path else "https://heavyreading.ca/"
    head_extra = ""
    if description:
        head_extra = (
            f'\n<meta name="description" content="{esc(description)}">'
            f'\n<link rel="canonical" href="{canon}">'
            f'\n<meta property="og:type" content="website">'
            f'\n<meta property="og:site_name" content="Heavy Reading">'
            f'\n<meta property="og:title" content="{esc(title)} | Heavy Reading">'
            f'\n<meta property="og:description" content="{esc(description)}">'
            f'\n<meta property="og:url" content="{canon}">'
            f'\n<meta name="twitter:card" content="summary">'
        )
    brand = brand_lockup(href("home", depth, current),
                         wordmark_tag="h1" if masthead_h1 else "span")
    crumb_html = f'<div class="crumb">{crumb}</div>' if crumb else ""
    if raw_heading:
        heading = raw_heading
    elif masthead_h1:
        heading = f'  <p class="sub herosub">{sub}</p>' if sub else ""
    else:
        heading = f"  <h1>{h1}</h1>\n  <p class=\"sub\">{sub}</p>"
    # The site is a web: project names in body copy link to project pages.
    body = linkify(body, depth, url_path or "index.html")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{THEME_HEAD}
<title>{esc(title)} | Heavy Reading</title>{head_extra}
{FAVICON_LINK}
{FONT_LINKS}
<style>{PAGE_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    {theme_toggle()}
    {brand}
    {nav(current, depth)}
    {search_box(depth)}
  </header>
  {crumb_html}
{heading}
{body}
  {footer(depth, current)}
</div>
{NAV_JS}
{THEME_JS}
{SEARCH_JS}
{gate}
</body>
</html>
"""


# ----------------------------------------------------------------------------
# Live SVG charts (rendered from the dashboard DATA at build time; no images,
# no paywalled data). Every chart is followed by an HTML caption carrying the
# vintage and a legend, so the provenance survives print/PDF.
# ----------------------------------------------------------------------------

# Chart palette. Builders pass palette KEYS (not hex); every key resolves to
# a CSS var() defined for both themes in PAGE_CSS, so one build serves light
# and dark and the toggle switches charts instantly. _lab(key) is the ink for
# labels drawn on top of that key's fill.
PAL = {
    "ink": "var(--ch-ink)", "ink2": "var(--ch-ink2)", "acc": "var(--ch-acc)",
    "steel": "var(--ch-steel)", "g1": "var(--ch-g1)", "g2": "var(--ch-g2)",
    "g3": "var(--ch-g3)", "g4": "var(--ch-g4)", "nc": "var(--ch-nc)",
    "fc": "var(--ch-fc)", "sand": "var(--ch-sand)", "blue": "var(--ch-blue)",
    "red": "var(--ch-red)", "gray": "var(--ch-gray)",
}
def _lab(key):
    return f"var(--ch-{key}-lab)"

_BAND_FILL = {"nc": "var(--ch-band-nc)", "fc": "var(--ch-band-fc)"}
_BAND_BAR = {"act": "var(--ch-ink)", "nc": "var(--ch-nc)", "fc": "var(--ch-fc)"}

# In-SVG type: Inter with tabular numerals, so chart figures match page type.
_SVG_STYLE = (
    "<style>"
    "text{font-family:'Inter',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    "font-variant-numeric:tabular-nums;}"
    ".ctitle{font-size:15px;font-weight:700;fill:var(--ink);}"
    ".cunit{font-size:12.5px;font-weight:500;fill:var(--mut);}"
    ".tick{font-size:13px;fill:var(--mut);}"
    ".xlab{font-size:12.5px;fill:var(--faint);}"
    ".val{font-size:13px;font-weight:700;fill:var(--ink);}"
    "</style>"
)


def _nice_top(vmax):
    if vmax <= 0:
        return 1.0
    import math
    exp = math.floor(math.log10(vmax))
    base = 10 ** exp
    for m in (1, 2, 2.5, 5, 10):
        if vmax <= m * base:
            return m * base
    return 10 * base


def _xlab(ym):
    # "2026-09" -> "Sep 26"
    return f"{B._MNAMES[int(ym[5:7]) - 1]} {ym[2:4]}"


def _est_text_w(text, px=12.5):
    # Inter averages ~0.56em per glyph on mixed text; conservative on purpose.
    return len(str(text)) * px * 0.56


def _left_for_ticks(tick_texts, base):
    # Size the left margin off the widest y tick label so values like
    # "5,000.0" never clip past the SVG edge. Tick labels are 13px.
    need = max((_est_text_w(t, 13.0) for t in tick_texts), default=0)
    return max(base, int(need) + 20)


def _x_candidates(months, n):
    """(index, text, priority) x-label candidates. The last month always wins;
    January years outrank stepped labels on long series."""
    cands = []
    if n > 30:
        for i, ym in enumerate(months):
            if ym[5:7] == "01":
                cands.append((i, ym[:4], 2))
    else:
        step = 1 if n <= 14 else max(2, n // 9)
        for i, ym in enumerate(months):
            if i % step == 0:
                cands.append((i, _xlab(ym), 1))
    if not any(i == n - 1 for i, _, _ in cands):
        cands.append((n - 1, _xlab(months[-1]), 3))
    else:
        cands = [(i, t, 3 if i == n - 1 else p) for i, t, p in cands]
    return cands


def _place_x_labels(parts, months, L, cw, n, H, y=None, min_gap=54):
    """Draw x labels with priority placement. When every label fits, keep the
    old dense look; otherwise the last month is always labeled and the rest
    are kept only when they clear min_gap px from every higher-priority
    label. Fixes Nov/Dec collisions on 29-month charts and year-label vs
    final-month-label overlaps."""
    yy = H - 14 if y is None else y
    if cw >= 46:
        for i, ym in enumerate(months):
            x = L + i * cw + cw / 2
            parts.append(f'<text x="{x:.1f}" y="{yy}" text-anchor="middle" '
                         f'class="xlab">{_xlab(ym)}</text>')
        return
    kept = []
    for i, text, _p in sorted(_x_candidates(months, n), key=lambda c: -c[2]):
        x = L + i * cw + cw / 2
        if all(abs(x - kx) >= min_gap for kx, _ in kept):
            kept.append((x, text))
    for x, text in sorted(kept):
        parts.append(f'<text x="{x:.1f}" y="{yy}" text-anchor="middle" '
                     f'class="xlab">{esc(text)}</text>')


def _band_runs(months, bands):
    runs = []
    for ym in months:
        b = bands.get(ym, "act")
        if runs and runs[-1][0] == b:
            runs[-1][1].append(ym)
        else:
            runs.append([b, [ym]])
    return runs


def _chart_title(parts, title, unit, L, W):
    if not title:
        return
    # Keep the title inside the viewBox: truncate with an ellipsis rather
    # than spill past the right edge. Estimated at 15px bold, which is
    # conservative for the mixed title/unit run.
    text = f"{title}  {unit}" if unit else title
    maxw = W - L - 8
    if _est_text_w(text, 15) * 1.22 > maxw:
        while len(text) > 4 and _est_text_w(text + "\u2026", 15) * 1.22 > maxw:
            text = text[:-1]
        parts.append(f'<text x="{L}" y="20" class="ctitle">{esc(text + "\u2026")}</text>')
    else:
        parts.append(f'<text x="{L}" y="20" class="ctitle">{esc(title)}'
                     f'<tspan class="cunit">  {esc(unit)}</tspan></text>')


def _x_labels(parts, months, L, cw, n, H):
    # Priority placement with a minimum gap; dense series keep every label.
    _place_x_labels(parts, months, L, cw, n, H)


def svg_bars(months, values, bands, maint_months=(), title="",
             zero_line=False, height=230, unit="kb/d", ind_months=()):
    """Single monthly series as bars. maint_months get orange shading;
    ind_months (pattern-indicated, never in model math) get dashed shading."""
    W, H = 720, height
    R, T, Bm = 14, 42 if title else 14, 40
    vals = [values.get(m) for m in months]
    have = [v for v in vals if v is not None]
    vmax = max(have) if have else 0
    vmin = min([0] + [v for v in have if v < 0]) if zero_line else 0
    top = _nice_top(max(vmax, -vmin if vmin < 0 else 0))
    span = top - vmin
    L = _left_for_ticks([f1(vmin + span * k / 4) for k in range(5)], 52)
    n = len(months)
    cw = (W - L - R) / max(n, 1)
    bw = min(cw * 0.62, 30)
    y0 = T + (top / span) * (H - T - Bm)  # pixel of value 0

    def ypix(v):
        return T + ((top - v) / span) * (H - T - Bm)

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">']
    parts.append(_SVG_STYLE)
    parts.append(_bg(W, H))
    if title:
        parts.append(f"<title>{esc(title)}</title>")
    _chart_title(parts, title, unit, L, W)
    # band backgrounds
    for b, run in _band_runs(months, bands):
        fill = _BAND_FILL.get(b)
        if not fill:
            continue
        i0 = months.index(run[0])
        x = L + i0 * cw
        parts.append(f'<rect x="{x:.1f}" y="{T}" width="{len(run) * cw:.1f}" '
                     f'height="{H - T - Bm}" style="fill:{fill}"/>')
    # maintenance shading
    for ym in sorted(maint_months):
        if ym in months:
            i = months.index(ym)
            x = L + i * cw
            parts.append(f'<rect x="{x:.1f}" y="{T}" width="{cw:.1f}" '
                         f'height="{H - T - Bm}" style="fill:var(--ch-wash-acc)"/>')
            parts.append(f'<rect x="{x:.1f}" y="{T}" width="{cw:.1f}" height="3" '
                         f'style="fill:var(--ch-acc)"/>')
    # pattern-indicated months: dashed outline, never in model math
    for ym in sorted(ind_months):
        if ym in months:
            i = months.index(ym)
            x = L + i * cw
            parts.append(f'<rect x="{x:.1f}" y="{T}" width="{cw:.1f}" '
                         f'height="{H - T - Bm}" style="fill:var(--ch-wash-nc);stroke:var(--ch-nc)" '
                         f'stroke-dasharray="4 3"/>')
    # gridlines + y labels
    for k in range(5):
        v = vmin + (top - vmin) * k / 4
        y = ypix(v)
        parts.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" '
                     f'style="stroke:var(--ch-grid)"/>')
        parts.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" '
                     f'class="tick">{f1(v)}</text>')
    if zero_line:
        parts.append(f'<line x1="{L}" y1="{y0:.1f}" x2="{W - R}" y2="{y0:.1f}" '
                     f'style="stroke:var(--faint)"/>')
    # x axis baseline
    parts.append(f'<line x1="{L}" y1="{H - Bm:.1f}" x2="{W - R}" y2="{H - Bm:.1f}" '
                 f'style="stroke:var(--ch-axis)"/>')
    # bars
    last_i = max((i for i, v in enumerate(vals) if v is not None), default=None)
    for i, ym in enumerate(months):
        v = vals[i]
        if v is None:
            continue
        x = L + i * cw + (cw - bw) / 2
        yv = ypix(v)
        top_y = min(yv, y0)
        hh = abs(yv - y0)
        col = _BAND_BAR[bands.get(ym, "act")]
        parts.append(f'<rect x="{x:.1f}" y="{top_y:.1f}" width="{bw:.1f}" '
                     f'height="{max(hh, 1.5):.1f}" rx="2.5" style="fill:{col}">'
                     f'<title>{_xlab(ym)}: {f1(v)} {unit}</title></rect>')
        if i == last_i and top_y - 16 > T:
            _lab = f1(v)
            _lx = min(x + bw / 2, W - _est_text_w(_lab, 13.0) * 1.22 / 2 - 2)
            parts.append(f'<text x="{_lx:.1f}" y="{top_y - 6:.1f}" '
                         f'text-anchor="middle" class="val">{_lab}</text>')
    _x_labels(parts, months, L, cw, n, H)
    parts.append("</svg>")
    return "\n".join(parts)


def svg_stack(months, series, bands, maint_months=(), title="",
              height=250, unit="kb/d"):
    """Stacked monthly bars. series: list of (label, values, color)."""
    W, H = 720, height
    R, T, Bm = 14, 42 if title else 14, 40
    totals = [sum((v.get(m) or 0) for _, v, _ in series) for m in months]
    top = _nice_top(max(totals) if totals else 0)
    L = _left_for_ticks([f1(top * k / 4) for k in range(5)], 52)
    n = len(months)
    cw = (W - L - R) / max(n, 1)
    bw = min(cw * 0.62, 34)

    def ypix(v):
        return T + ((top - v) / top) * (H - T - Bm)

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">']
    parts.append(_SVG_STYLE)
    parts.append(_bg(W, H))
    if title:
        parts.append(f"<title>{esc(title)}</title>")
    _chart_title(parts, title, unit, L, W)
    for b, run in _band_runs(months, bands):
        fill = _BAND_FILL.get(b)
        if not fill:
            continue
        i0 = months.index(run[0])
        x = L + i0 * cw
        parts.append(f'<rect x="{x:.1f}" y="{T}" width="{len(run) * cw:.1f}" '
                     f'height="{H - T - Bm}" style="fill:{fill}"/>')
    for ym in sorted(maint_months):
        if ym in months:
            i = months.index(ym)
            x = L + i * cw
            parts.append(f'<rect x="{x:.1f}" y="{T}" width="{cw:.1f}" '
                         f'height="{H - T - Bm}" style="fill:var(--ch-wash-acc)"/>')
    for k in range(5):
        v = top * k / 4
        y = ypix(v)
        parts.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" '
                     f'style="stroke:var(--ch-grid)"/>')
        parts.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" '
                     f'class="tick">{f1(v)}</text>')
    parts.append(f'<line x1="{L}" y1="{H - Bm:.1f}" x2="{W - R}" y2="{H - Bm:.1f}" '
                 f'style="stroke:var(--ch-axis)"/>')
    last_total = None
    for i, m in enumerate(months):
        acc = 0
        x = L + i * cw + (cw - bw) / 2
        for _lab, v, col in series:
            val = v.get(m) or 0
            y1, y2 = ypix(acc), ypix(acc + val)
            if val > 0:
                parts.append(f'<rect x="{x:.1f}" y="{y2:.1f}" width="{bw:.1f}" '
                             f'height="{max(y1 - y2, 0.5):.1f}" rx="2" style="fill:{PAL[col]}">'
                             f'<title>{_xlab(m)} {_lab}: {f1(val)} {unit}</title></rect>')
            acc += val
        if acc:
            last_total = (x + bw / 2, ypix(acc), acc)
    if last_total and last_total[1] - 16 > T:
        lx, ly, lacc = last_total
        _lab = f1(lacc)
        _lx = min(lx, W - _est_text_w(_lab, 13.0) * 1.22 / 2 - 2)
        parts.append(f'<text x="{_lx:.1f}" y="{ly - 6:.1f}" text-anchor="middle" '
                     f'class="val">{_lab}</text>')
    _x_labels(parts, months, L, cw, n, H)
    parts.append("</svg>")
    return "\n".join(parts)


def chart_figure(svg, caption, legend_items=(), title=None):
    """Wrap an SVG with its takeaway title, vintage caption and legend
    (HTML, print-safe)."""
    t = f'<h3 class="ctake">{esc(title)}</h3>\n' if title else ""
    lg = ""
    if legend_items:
        lg = ('<div class="lg">' + "".join(
            f'<span><span class="sw" style="background:{c}"></span>{esc(t)}</span>'
            for t, c in legend_items) + "</div>")
    return (f'{t}<figure class="chart">\n{svg}\n<figcaption>{caption}</figcaption>\n'
            f'{lg}\n</figure>')


def band_legend():
    return [("Actuals (AER)", "var(--ch-ink)"),
            ("Nowcast (model est.)", "var(--ch-nc)"),
            ("Forecast (model)", "var(--ch-fc)"),
            ("Modeled maintenance month", "var(--ch-wash-acc2)")]


def vintage_caption(text):
    return f'<b>Vintage:</b> {text}'


# ----------------------------------------------------------------------------
# Second-generation chart instrument (2026-09-23). One consistent renderer:
# SVG, direct end-labels instead of legend boxes, light horizontal gridlines
# only, zero-based bars, human numbers (kb/d, Mb/d), takeaway title + vintage
# caption in HTML, event markers that mark a window with its source and never
# assert that the event caused a visible move.
# ----------------------------------------------------------------------------

# (retired) _C_* hex constants were replaced by the PAL/var() system above;
# charts now resolve every color through CSS custom properties.

def _bg(W, H):
    """Opaque paper background rect: every chart paints its own ground so
    labels and axes always sit on a known background in both themes
    (fill follows the theme via var(--paper)). Must be the first drawn
    element, right after the <svg> tag (and any <style> block)."""
    return f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--paper)"/>'



_SVG2 = (
    "<style>"
    "text{font-family:'Inter',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    "font-variant-numeric:tabular-nums;}"
    ".tick{font-size:13px;fill:var(--mut);}"
    ".xlab{font-size:12.5px;fill:var(--faint);}"
    ".elab{font-size:12.5px;font-weight:700;}"
    ".evt{font-size:11px;fill:var(--mut);}"
    ".val{font-size:13px;font-weight:700;fill:var(--ink);}"
    "</style>"
)


def _human_tick(v, top):
    # Human axis labels: Mb/d scale once the axis runs into the thousands.
    if top >= 2000:
        return f"{v / 1000:g}"
    return f"{v:,.0f}"


def _axis_unit(top):
    return "Mb/d" if top >= 2000 else "kb/d"


def _cgrid(parts, L, R, W, T, H, Bm, top):
    for k in range(5):
        v = top * k / 4
        y = T + ((top - v) / top) * (H - T - Bm)
        parts.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" '
                     f'style="stroke:var(--ch-grid)"/>')
        parts.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" '
                     f'class="tick">{_human_tick(v, top)}</text>')
    parts.append(f'<text x="{L - 8}" y="{T - 8}" text-anchor="end" '
                 f'class="xlab">{_axis_unit(top)}</text>')
    parts.append(f'<line x1="{L}" y1="{H - Bm:.1f}" x2="{W - R}" y2="{H - Bm:.1f}" '
                 f'style="stroke:var(--ch-axis)"/>')


def _cevents(parts, months, events, L, cw, T, H, Bm, W):
    # Event windows: a quiet vertical marker with a sourced label. The marker
    # says the event happened and when; it never claims a causal link.
    # Labels alternate levels and never sit on top of each other: a crowded
    # level is skipped rather than overlapped. Labels at the plot edges are
    # clamped (and truncated if extreme) so they never spill past x=0 or W.
    lvl_y = [T - 26, T - 12]
    placed = []  # (x, level)
    for ei, (ym, label) in enumerate(events):
        if ym not in months:
            continue
        i = months.index(ym)
        x = L + i * cw + cw / 2
        parts.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{H - Bm:.1f}" '
                     f'style="stroke:var(--ch-evt)" stroke-width="1">'
                     f'<title>{esc(label)}</title></line>')
        gap = max(72, _est_text_w(label, 11) + 14)
        lvl = None
        for cand in (ei % 2, 1 - ei % 2):
            if all(pl != cand or abs(x - px) >= gap for px, pl in placed):
                lvl = cand
                break
        if lvl is None:
            continue  # both levels crowded; the marker line still shows
        placed.append((x, lvl))
        lab = str(label)
        lw = _est_text_w(lab, 11)
        if lw > W - 12:
            while len(lab) > 4 and _est_text_w(lab + "\u2026", 11) > W - 12:
                lab = lab[:-1]
            lab = lab + "\u2026"
            lw = _est_text_w(lab, 11)
        tx = min(max(x, lw / 2 + 4), W - lw / 2 - 4)
        parts.append(f'<text x="{tx:.1f}" y="{lvl_y[lvl]}" text-anchor="middle" '
                     f'class="evt">{esc(lab)}</text>')


def _cx_labels(parts, months, L, cw, n, H):
    # Priority placement with a minimum gap; dense series keep every label.
    _place_x_labels(parts, months, L, cw, n, H, y=H - 16)


def _banked_height(line_vals, plot_w, n, top):
    # Bank the median month-to-month move toward ~45 degrees.
    vals = [v for v in line_vals if v is not None]
    if len(vals) < 2 or n < 2:
        return 300
    d = sorted(abs(b - a) for a, b in zip(vals, vals[1:]))
    med = d[len(d) // 2]
    if med <= 0:
        return 300
    return min(430, max(230, int(top * plot_w / (med * (n - 1)))))


def svg_stack_line(months, stacks, line=None, events=(), line_end_label=None,
                   unit="kb/d", bands=None):
    """Stacked monthly bars with an optional overlaid line.

    stacks: list of (short_name, values_dict, palkey, _ignored).
    line: (values_dict, palkey) or None. events: list of (month, label).
    bands: optional dict month -> "act"/"nc"/"fc" for vintage tint washes.
    Bars are zero-based; the plot height is banked on the line's median slope.
    """
    W = 720
    R, Bm = 104, 48
    T = 44 if events else 20
    n = len(months)
    totals = [sum((v.get(m) or 0) for _, v, _, _ in stacks) for m in months]
    line_vals = [line[0].get(m) if line else None for m in months]
    top = _nice_top(max(totals + [v or 0 for v in line_vals] or [0]))
    L = _left_for_ticks([_human_tick(top * k / 4, top) for k in range(5)], 58)
    if line_end_label:
        # Keep the end label inside the viewBox: it is drawn at lx + 8 with
        # text-anchor start, so grow R until its estimated right edge fits.
        # Two passes because R moves cw which moves lx. (elab is 12.5px bold.)
        est = _est_text_w(line_end_label, 12.5) * 1.22
        for _ in range(2):
            cw = (W - L - R) / max(n, 1)
            lx = L + (n - 1) * cw + cw / 2
            need = lx + 8 + est + 8 - W
            if need <= 0:
                break
            R = int(R + need + 2)
    plot_w = W - L - R
    cw = plot_w / max(n, 1)
    bw = min(cw * 0.72, 30)
    totals = [sum((v.get(m) or 0) for _, v, _, _ in stacks) for m in months]
    line_vals = [line[0].get(m) if line else None for m in months]
    top = _nice_top(max(totals + [v or 0 for v in line_vals] or [0]))
    height = _banked_height(line_vals, plot_w, n, top) if line else 300
    H = T + height + Bm

    def ypix(v):
        return T + ((top - v) / top) * height

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img">', _SVG2,
             _bg(W, H)]
    if bands:
        for b, run in _band_runs(months, bands):
            fill = _BAND_FILL.get(b)
            if not fill:
                continue
            i0 = months.index(run[0])
            parts.append(f'<rect x="{L + i0 * cw:.1f}" y="{T}" '
                         f'width="{len(run) * cw:.1f}" height="{height}" style="fill:{fill}"/>')
    _cevents(parts, months, events, L, cw, T, H, Bm, W)
    _cgrid(parts, L, R, W, T, H, Bm, top)
    last = n - 1
    for i, m in enumerate(months):
        acc = 0
        x = L + i * cw + (cw - bw) / 2
        for _lname, v, col, _tc in stacks:
            val = v.get(m) or 0
            y1, y2 = ypix(acc), ypix(acc + val)
            if val > 0:
                parts.append(f'<rect x="{x:.1f}" y="{y2:.1f}" width="{bw:.1f}" '
                             f'height="{max(y1 - y2, 0.5):.1f}" style="fill:{PAL[col]}">'
                             f'<title>{_xlab(m)} {_lname}: {f1(val)} {unit}</title></rect>')
            acc += val
        if i == last:
            # Direct end-labels at the right edge: a pill in the segment
            # color behind each label, so text never overhangs the bar onto
            # paper in a color meant for the segment (unreadable there in
            # both themes). Pills are clamped inside the viewBox.
            acc = 0
            for lab, v, key, _tc in stacks:
                val = v.get(m) or 0
                y1, y2 = ypix(acc), ypix(acc + val)
                if val > 0 and y1 - y2 >= 20:
                    pw = _est_text_w(lab, 12.5) * 1.22 + 18
                    cx = x + bw / 2
                    cx = min(max(cx, pw / 2 + 2), W - pw / 2 - 2)
                    cy = (y1 + y2) / 2
                    parts.append(f'<rect x="{cx - pw / 2:.1f}" y="{cy - 10:.1f}" '
                                 f'width="{pw:.1f}" height="20" rx="10" '
                                 f'style="fill:{PAL[key]}"/>')
                    parts.append(f'<text x="{cx:.1f}" y="{cy + 4:.1f}" '
                                 f'text-anchor="middle" class="elab" '
                                 f'style="fill:{_lab(key)}">{esc(lab)}</text>')
                acc += val
    if line:
        lv, lcol = line
        lcol = PAL.get(lcol, lcol)  # callers pass palette keys ("acc"), not CSS
        pts = [(L + i * cw + cw / 2, ypix(v))
               for i, (m, v) in enumerate(zip(months, line_vals)) if v is not None]
        if pts:
            d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            parts.append(f'<path d="{d}" fill="none" stroke="{lcol}" stroke-width="2.5"/>')
            lx, ly = pts[-1]
            lv_last = [v for v in line_vals if v is not None][-1]
            parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="{lcol}"/>')
            if line_end_label:
                ly_lab = max(ly - 9, T + 12)  # never above the plot top
                lab_w = _est_text_w(line_end_label, 12.5) * 1.22
                if lx + 8 + lab_w > W - 4:
                    # estimate was short (fallback font): anchor inside
                    parts.append(f'<text x="{W - 4}" y="{ly_lab:.1f}" '
                                 f'text-anchor="end" class="elab" '
                                 f'fill="{lcol}">{esc(line_end_label)}</text>')
                else:
                    parts.append(f'<text x="{lx + 8:.1f}" y="{ly_lab:.1f}" class="elab" '
                                 f'fill="{lcol}">{esc(line_end_label)}</text>')
    _cx_labels(parts, months, L, cw, n, H)
    parts.append("</svg>")
    return "\n".join(parts)


def svg_event_bars(months, values, events=(), palkey="acc", unit="kb/d",
                   label_min=60):
    """Single monthly bar series with value labels and sourced event markers."""
    W = 720
    R, Bm = 20, 48
    T = 58
    vals = [values.get(m) or 0 for m in months]
    top = _nice_top(max(vals) if vals else 0)
    L = _left_for_ticks([_human_tick(top * k / 4, top) for k in range(5)], 52)
    n = len(months)
    plot_w = W - L - R
    cw = plot_w / max(n, 1)
    bw = min(cw * 0.66, 40)
    H = T + 300 + Bm

    def ypix(v):
        return T + ((top - v) / top) * 300

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img">', _SVG2,
             _bg(W, H)]
    _cevents(parts, months, events, L, cw, T, H, Bm, W)
    _cgrid(parts, L, R, W, T, H, Bm, top)
    _last_vlab = None
    for i, m in enumerate(months):
        v = vals[i]
        if v <= 0:
            continue
        x = L + i * cw + (cw - bw) / 2
        yv = ypix(v)
        parts.append(f'<rect x="{x:.1f}" y="{yv:.1f}" width="{bw:.1f}" '
                     f'height="{max(H - Bm - yv, 1.5):.1f}" rx="2.5" style="fill:{PAL[palkey]}">'
                     f'<title>{_xlab(m)}: {f1(v)} {unit} offline</title></rect>')
        if v >= label_min and yv - 18 > T:
            _lab = f1(v)
            _lx = x + bw / 2
            _gap = _est_text_w(_lab, 13.0) / 2 + 3
            if _last_vlab is not None and _lx - _last_vlab < _gap * 2:
                continue  # crowded: omit rather than overprint
            _lx = min(_lx, W - _gap)
            parts.append(f'<text x="{_lx:.1f}" y="{yv - 7:.1f}" '
                         f'text-anchor="middle" class="val">{_lab}</text>')
            _last_vlab = _lx
    _cx_labels(parts, months, L, cw, n, H)
    parts.append("</svg>")
    return "\n".join(parts)


def svg_grouped(cats, series, unit="kb/d"):
    """Horizontal grouped bars: long category names stay legible at any width. Series: (name, values, palkey)."""
    W = 720
    L, R, T, Bm = 168, 64, 14, 40
    row_h, gap = 40, 7
    n = len(cats)
    H = T + n * row_h + Bm
    vmax = max((v for _, vals, _ in series for v in vals if v), default=0)
    top = _nice_top(vmax)
    plot_w = W - L - R

    def xpix(v):
        return L + (v / top) * plot_w

    bh = (row_h - gap) / max(len(series), 1)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img">', _SVG2,
             _bg(W, H)]
    # light vertical gridlines + x labels
    for k in range(5):
        v = top * k / 4
        x = xpix(v)
        parts.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{H - Bm:.1f}" '
                     f'style="stroke:var(--ch-grid)"/>')
        parts.append(f'<text x="{x:.1f}" y="{H - Bm + 20}" text-anchor="middle" '
                     f'class="tick">{_human_tick(v, top)}</text>')
    parts.append(f'<text x="{L + plot_w}" y="{T - 2}" text-anchor="end" '
                 f'class="xlab">{_axis_unit(top)}</text>')
    for i, cat in enumerate(cats):
        y0 = T + i * row_h + gap / 2
        # Category names sit left of the plot; a long name must never spill
        # past x=0, so truncate with an ellipsis to the available width.
        cat_draw = str(cat)
        _cat_maxw = L - 10 - 6
        if _est_text_w(cat_draw, 13.0) > _cat_maxw:
            while len(cat_draw) > 4 and _est_text_w(cat_draw + "\u2026", 13.0) > _cat_maxw:
                cat_draw = cat_draw[:-1]
            cat_draw = cat_draw + "\u2026"
        parts.append(f'<text x="{L - 10}" y="{y0 + len(series) * bh / 2 + 4:.1f}" '
                     f'text-anchor="end" class="tick">{esc(cat_draw)}</text>')
        for j, (sname, vals, col) in enumerate(series):
            v = vals[i] or 0
            y = y0 + j * bh
            parts.append(f'<rect x="{L}" y="{y:.1f}" width="{max(xpix(v) - L, 1.5):.1f}" '
                         f'height="{bh - 2:.1f}" rx="2" style="fill:{PAL[col]}">'
                         f'<title>{esc(cat)} {esc(sname)}: {f1(v)} {unit}</title></rect>')
            if v > 0:
                lab = f1(v)
                lx = xpix(v) + 6
                if lx + _est_text_w(lab, 13.0) * 1.22 > W - 4:
                    # bar runs to the edge: anchor the value inside instead
                    parts.append(f'<text x="{xpix(v) - 6:.1f}" y="{y + bh / 2 + 1:.1f}" '
                                 f'text-anchor="end" class="tick">{lab}</text>')
                else:
                    parts.append(f'<text x="{lx:.1f}" y="{y + bh / 2 + 1:.1f}" '
                                 f'class="tick">{lab}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def kpi_strip(stats):
    """Four-up KPI strip. stats: list of (label, value_html, sub)."""
    cells = "".join(
        f'<div class="stat"><div class="k">{esc(k)}</div>'
        f'<div class="v">{v}</div><div class="s">{esc(s)}</div></div>'
        for k, v, s in stats)
    return f'<div class="statgrid kpi">{cells}</div>'


def csv_link(href, vintage_label):
    return (f'<p class="csvdl"><a href="{href}">Download CSV</a> '
            f'<span class="vintageline">{esc(vintage_label)}</span></p>')


# ----------------------------------------------------------------------------
# Full citation block (teardown discipline). Only publishers/URLs that appear
# in the repo annotations or weekly source appendices are used; anything else
# is labeled "URL not recorded in repo" rather than invented.
# ----------------------------------------------------------------------------

CITATIONS = [
    ("Alberta Energy Regulator", "ST3: Alberta Energy Resource Industries Monthly Statistics",
     "https://www.aer.ca/data-and-performance/data-and-publications/statistical-reports/st3",
     "Monthly", "Actuals through 2026-07 (latest file vintage 2026-08-27)", "2026-09-22"),
    ("Alberta Energy Regulator", "ST53: In-situ project data (BITUMEN sheet)",
     "https://www.aer.ca/data-and-performance/data-and-publications/statistical-reports/st53",
     "Monthly", "Actuals through 2026-07", "2026-09-22"),
    ("Alberta Energy Regulator", "ST39: Mine and upgrader facility data",
     "URL not recorded", "Monthly", "Actuals through 2026-05", "2026-09-22"),
    ("Canada Energy Regulator", "Pipeline throughput, capacity and apportionment (open data)",
     "https://www.cer-rec.gc.ca/open/energy/throughput-capacity/",
     "Monthly, ~3-month lag", "Jan 2018 to Jun 2026", "2026-09-22"),
    ("Company disclosures", "Quarterlies, budget releases, investor presentations, earnings calls",
     "URLs per record in the forward maintenance calendar", "As published",
     "Forward maintenance calendar window 2026-10-01 to 2027-09-30, compiled 2026-09-22", "2026-09-22"),
    ("Heavy Reading model", "WCSB S&D dashboard build (21 granular leaves, grade layer, maintenance math)",
     "No public URL (model build)", "Per build", "Forecast built 2026-09-22; Aug-Sep 2026 nowcast built 2026-09-23", "2026-09-23"),
    # --- Public sources used across the site --------------------------------
    ("U.S. Energy Information Administration", "Weekly Petroleum Status Report (WPSR): weekly preliminary crude imports by country (Table 8), weekly crude exports",
     "https://www.eia.gov", "Weekly", "Sep 2025 to Sep 2026 weekly series", "2026-09-23"),
    ("Organization of the Petroleum Exporting Countries (OPEC)", "Monthly Oil Market Report (MOMR): Venezuela crude production, secondary sources and direct communication",
     "https://www.opec.org", "Monthly", "Venezuela production series via Aug 2026 MOMR Tables 5-7/5-8", "2026-09-24"),
    ("ICE", "Delayed futures quotes",
     "https://www.ice.com", "Daily", "Brent settles referenced in weekly digest pricing", "Per edition"),
    ("Statistics Canada", "Canadian energy series referenced in weekly digest editions",
     "https://www.statcan.gc.ca", "As published", "Series per digest edition", "Per edition"),
    ("Suncor Energy", "Quarterly results, budget/guidance releases, investor presentations, earnings calls",
     "URLs per record in the forward maintenance calendar", "As published", "Forward maintenance outlook; project profiles", "2026-09-22"),
    ("Canadian Natural Resources (CNRL)", "Quarterly results, budget/guidance releases, investor presentations, earnings calls",
     "URLs per record in the forward maintenance calendar", "As published", "Forward maintenance outlook; project profiles", "2026-09-22"),
    ("Imperial Oil", "Quarterly results, budget/guidance releases, investor presentations, earnings calls",
     "URLs per record in the forward maintenance calendar", "As published", "Forward maintenance outlook; project profiles", "2026-09-22"),
    ("Cenovus Energy", "Quarterly results, budget/guidance releases, investor presentations, earnings calls",
     "URLs per record in the forward maintenance calendar", "As published", "Forward maintenance outlook; project profiles", "2026-09-22"),
    ("Reuters", "Wire reporting cited on watch pages: Venezuela Merey pricing, Signal Maritime freight rates",
     "https://www.reuters.com", "As published", "Venezuela watch Sep 2026; geopolitical watch pages", "2026-09-24"),
    ("The Associated Press", "Wire reporting cited on geopolitical watch pages",
     "https://apnews.com", "As published", "Per watch page", "Per watch page"),
    ("OilPrice.com", "Vitol Merey offer to China (Bloomberg-sourced), Jan 2026",
     "https://oilprice.com/Latest-Energy-News/World-News/China-Is-Importing-Its-Last-Ultra-Cheap-Sanctioned-Venezuelan-Oil.html",
     "As published", "Venezuela watch, Jan 2026", "2026-09-23"),
    ("Signal Maritime", "Aframax freight rates, Jose terminal to USGC, reported via Reuters",
     "URL not recorded", "As published", "Venezuela watch, Jan/Sep 2026", "2026-09-24"),
    ("U.S. Department of Energy", "Strategic Petroleum Reserve (SPR) data and policy statements",
     "https://www.energy.gov", "As published", "SPR & storage watch", "Per watch page"),
    # Licensed inputs: house rule is the words "commercial storage", no vendor names.
    ("Commercial storage", "Licensed market-data inputs embedded in model builds; vendor identities withheld per licence terms",
     "Not disclosed", "Per licence", "As embedded in builds", "Per build"),
]


def sources_table():
    rows = "".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td>"
        f"<td>{esc(c) if c.startswith('http') is False else f'<a href=\"{esc(c)}\">{esc(c)}</a>'}</td>"
        f"<td>{esc(d)}</td><td>{esc(e)}</td><td>{esc(f)}</td></tr>"
        for a, b, c, d, e, f in CITATIONS)
    return ('<div class="tblwrap"><table class="data">'
            "<caption style=\"text-align:left;font-weight:700;padding:6px 0;\">Sources</caption>"
            "<tr><th>Publisher</th><th>Dataset</th><th>URL</th><th>Published</th>"
            "<th>Vintage / coverage</th><th>Retrieved</th></tr>"
            f"{rows}</table></div>"
            '<p class="tblnote">Every number on this page traces to a row above. '
            "Anything missing its own source line is flagged in place; nothing "
            "ships with an unsourced number.</p>")
