#!/usr/bin/env python3
"""Regenerate tools/std/search-cpp and tools/std/search-c from cppreference offline docs.

Upstream ships both files as static data, snapshotted once in 2023 (CHANGELOG
v0.4), which is why newer symbols (std::print, std::expected, std::jthread, ...)
cannot be found.  This script rebuilds them from a cppreference "html book"
archive, so the index can follow new C++ standards:

    python tools/std/gen_symbol_map.py latest --extract-to .docs-offline
    cd tools/std && cargo run --release -- ../../.docs-offline/reference/en

`make index` runs exactly that and deletes the extracted copy afterwards.  The
docs argument accepts a release zip, an extracted directory, or `latest` (which
downloads the newest unofficial html book release, the official one is stuck at
2019-06-07); `--extract-to` unpacks `reference/` for the Rust step that adds the
descriptions.

Keys are scraped from the docs themselves, most specific source first:

  * page titles         std::print                => cpp/io/print
  * symbol index pages  std::stacktrace           => cpp/utility/basic_stacktrace
                        (namespace aliases whose own page is named differently)
  * description tables  std::istrstream::in       => cpp/io/ios_base/openmode
                        std::errc::permission_denied => cpp/error/errc
                        (members, enumerators, operators, overload scopes)
  * the doxygen tag file std::pmr::pool_options::max_blocks_per_chunk
                        (what the tables do not spell out)

A name is only kept when its target page exists in the same archive, so the
generated index can never link to a page cppreference.com does not have.
"""
import argparse
import html
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from urllib.request import Request, urlopen, urlretrieve

DOC_RELEASE_API = "https://api.github.com/repos/PeterFeicht/cppreference-doc/releases/latest"
# symbols a regeneration must still find: (key, page)
PROBES = [
    ("std::print", "cpp/io/print"),
    ("std::println", "cpp/io/println"),
    ("std::format", "cpp/utility/format/format"),
    ("std::expected", "cpp/utility/expected"),
    ("std::jthread", "cpp/thread/jthread"),
    ("std::mdspan", "cpp/container/mdspan"),
    ("std::span", "cpp/container/span"),
    ("std::stacktrace", "cpp/utility/basic_stacktrace"),
    ("std::size_t", "cpp/types/size_t"),
    ("std::vector::push_back", "cpp/container/vector/push_back"),
    ("std::istrstream::in", "cpp/io/ios_base/openmode"),
    ("std::errc::permission_denied", "cpp/error/errc"),
    ("printf", "c/io/fprintf"),
]

TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
# rows are matched without crossing a nested <tr> (description tables embed tables)
ROW_RE = re.compile(r'<tr class="t-dsc">((?:(?!</?tr\b).)*?)</tr>', re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
INDEX_LINK_RE = re.compile(r'<a[^>]+title="([^"]*)"[^>]*>\s*<tt>(.*?)</tt>', re.S)
TITLE_ATTR_RE = re.compile(r'<a[^>]+title="([^"]*)"')
SINCE_RE = re.compile(r"^(?:\([^)]*\)|\[[^\]]*\]|\s)+")
SEE_ALSO_RE = re.compile(r'<h[23][^>]*>(?:(?!</h[23]>).)*?See also', re.S)
# a trailing parenthesised scope marks a non-member entity: "operator==(std::array)"
SCOPED_RE = re.compile(r"^(.*?)\s*\((.*?)\s*\)$")

OPERATORS = [
    "<=>", "->*", "<<=", ">>=", "->", "==", "!=", "<=", ">=", "<<", ">>", "&&", "||",
    "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "()", "[]",
    "<", ">", "+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "=", ",",
]
OP_TOKENS = "|".join(re.escape(o) for o in OPERATORS)
OPERATOR_RE = re.compile(r"operator\s*(?:" + OP_TOKENS + r")")
BARE_OPERATOR_RE = re.compile(r"^(?:" + OP_TOKENS + r")$")
PART = r"(?:[A-Za-z_~][A-Za-z0-9_]*|operator\s*(?:(?:" + OP_TOKENS + r")|[A-Za-z_][A-Za-z0-9_]*))"
NAME = r"(?:" + PART + r")(?:::(?:" + PART + r"))*"
SCOPE_PART = r"(?:[A-Za-z_~][A-Za-z0-9_-]*|operator\s*(?:(?:" + OP_TOKENS + r")|[A-Za-z_][A-Za-z0-9_]*))"
ANGLES = r"(?:<[^<>]*(?:<[^<>]*>)?[^<>]*>)?"
NAME_RE = re.compile(NAME + r"$")
KEY_RE = re.compile(NAME + ANGLES + r"(?:\((?:" + SCOPE_PART + r")(?:::" + SCOPE_PART + r")*\))?$")


def clean(text):
    """Strip tags, decode entities, collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub("", text))).strip().replace("\xa0", " ")


def strip_templates(name):
    """Drop the generic parameters of a class scope:

    std::basic_string<CharT,Traits,Allocator>::append -> std::basic_string::append

    Arguments of the entity itself are kept, they identify a specialisation:
    std::hash<std::basic_string> stays as it is, otherwise the page of the
    generic template (std::hash, std::formatter, std::iterator_traits, ...) would
    be shadowed by whichever specialisation page comes first.
    """
    protected = []

    def _protect(m):
        protected.append(m.group(0))
        return "\x00%d\x00" % (len(protected) - 1)

    name = OPERATOR_RE.sub(_protect, name)
    depth, split = 0, None
    for i, ch in enumerate(name):  # last scope separator outside template arguments
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0 and name.startswith("::", i):
            split = i
    name = (_strip_angles(name[:split]) + name[split:]) if split is not None else _strip_angles(name)
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], name)


def _strip_angles(text):
    out, depth = [], 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def normalize(name):
    """Turn a displayed name (already decoded text) into a search key."""
    name = re.sub(r"\s+", " ", name).strip().replace("\xa0", " ")
    while True:  # drop markers like "[virtual]" or "(since C++11)"
        stripped = SINCE_RE.sub("", name)
        if stripped == name:
            break
        name = stripped
    name = strip_templates(name).strip().rstrip(";").strip()
    if not name:
        return None
    # "operator==(std::array)" -> keep the scope, which identifies the overload
    m = SCOPED_RE.match(name)
    base = normalize_bare(m.group(1)) if m else normalize_bare(name)
    if base is None:
        return None
    scope_name = normalize_bare(m.group(2)) if m else None
    return "%s(%s)" % (base, scope_name) if base and scope_name else base


def normalize_bare(name):
    if name.endswith("()") and not name.endswith("operator()"):
        name = name[:-2]
    elif name.endswith("[]") and not name.endswith("operator[]"):
        name = name[:-2]
    return name if name and KEY_RE.match(name) else None


class NameUnits(HTMLParser):
    """Split a table cell into the entity names displayed in it.

    Rows list one name per <span> inside `<span class="t-lines">` (several names
    share one row when they share a description), while plain cells hold a single
    name in <code>/<tt>/<a>.  Nested spans (template arguments, [virtual] marks)
    belong to the surrounding name, so only siblings are treated as separators.
    """

    def __init__(self):
        # entities stay escaped: "&lt;std::pair&gt;" must not look like a tag
        super().__init__(convert_charrefs=False)
        self.units = []
        self._cur = []
        self._stack = []

    def handle_entityref(self, name):
        self._cur.append("&%s;" % name)

    def handle_charref(self, name):
        self._cur.append("&#%s;" % name)

    def _flush(self):
        text = html.unescape("".join(self._cur))
        self._cur = []
        if text.strip():
            self.units.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "tr", "table", "li"):
            self._flush()
        self._stack.append((tag, dict(attrs).get("class", "")))

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self._flush()

    def handle_endtag(self, tag):
        while self._stack:
            t, _ = self._stack.pop()
            if t == tag:
                break
        if tag in ("p", "div", "td", "table", "tr", "li", "dd"):
            self._flush()
        elif tag == "span" and self._stack and self._stack[-1][0] == "span" and "t-lines" in self._stack[-1][1]:
            self._flush()

    def handle_data(self, data):
        self._cur.append(data)


def split_names(text):
    """Split "a, b(std::c)" on the top-level commas only: std::map<Key,T> is one name."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def cell_names(cell):
    parser = NameUnits()
    parser.feed(cell)
    parser._flush()
    names = []
    for unit in parser.units:
        parts = split_names(unit)
        # one trailing scope can qualify a whole row: "operator==,!=,...,<=>(std::variant)"
        scope_name = None
        if len(parts) > 1:
            m = SCOPED_RE.match(parts[-1])
            candidate = normalize(m.group(2)) if m else None
            if candidate and "::" in candidate:
                scope_name, parts[-1] = candidate, m.group(1)
        for part in parts:
            part = strip_templates(part)
            name = normalize(part)
            if name is None and BARE_OPERATOR_RE.match(part.strip()):
                name = normalize("operator" + part.strip())
            if not name:
                continue
            if scope_name and "(" not in name:
                name = "%s(%s)" % (name, scope_name)
            if name not in names:
                names.append(name)
    return names


def scope(h1, doc_path):
    """Scope prefix used to qualify member names listed on a page."""
    names = [n for n in cell_names(h1) if "::" in n]
    if names:
        return max(names, key=len) + "::"
    return "std::" if doc_path.startswith("cpp/") else ""


def link_target(html_fragment, fallback):
    """Path of the first link in a table cell, else the page's own path."""
    m = TITLE_ATTR_RE.search(html_fragment)
    if not m:
        return fallback
    title = html.unescape(m.group(1))
    if "page does not exist" in title:
        return None
    # cppreference titles spell page names with spaces ("cpp/types/size t")
    return re.sub(r"\s", "_", title)


def parse_page(path, raw):
    """-> (doc_path, title names, description-table rows)

    Rows of a "See also" section describe *related* entities, so they are cut
    off: their names belong to other scopes than the page's own.
    """
    lang, _, rel = path.partition("/")
    doc_path = rel[:-len(".html")] if rel.endswith(".html") else rel

    m = TITLE_RE.search(raw)
    # keep the HTML entities: "std::hash&lt;std::pair&gt;" is a name, not a tag
    title = re.sub(r"\s*[-\u2013]\s*cppreference\.com\s*$", "", m.group(1)) if m else ""
    m = H1_RE.search(raw)
    prefix = scope(m.group(1) if m else "", doc_path)

    m = SEE_ALSO_RE.search(raw)
    if m:
        raw = raw[:m.start()]

    names = cell_names(title)
    rows = []
    for row in ROW_RE.findall(raw):
        cells = CELL_RE.findall(row)
        if len(cells) != 2 or not cells[0].strip():
            continue
        row_names = cell_names(cells[0])
        if not row_names:
            continue
        target = link_target(cells[0], doc_path)
        if target is None:
            continue
        for name in row_names:
            key = name if "::" in name or "(" in name or name.startswith("operator") else prefix + name
            rows.append((key, target))
    return doc_path, names, rows


def parse_symbol_index(raw):
    """Symbol index pages list aliases: <a title="cpp/..."><tt>name</tt></a>.

    Names are displayed relative to the index's namespace ("std", "std::ranges",
    "std::ranges::views"), which is why the page lists e.g. `stacktrace` for
    cpp/utility/basic_stacktrace and `filter` for cpp/ranges/filter_view.
    """
    m = TITLE_RE.search(raw)
    title = re.sub(r"\s*[-\u2013]\s*cppreference\.com\s*$", "", clean(m.group(1))) if m else ""
    ns = re.sub(r"\s*Symbol Index$", "", title).strip()
    prefix = ns + "::" if ns == "std" or ("::" in ns and NAME_RE.match(ns)) else ""
    out = []
    for target, body in INDEX_LINK_RE.findall(raw):
        target = re.sub(r"\s", "_", html.unescape(target))
        if target.startswith(("cpp/symbol_index", "c/symbol_index")):
            continue
        for name in cell_names(body):
            out.append((name if "::" in name else prefix + name, target))
    return out


class Pages:
    """Uniform read access to the pages of a release zip or an extracted tree."""

    def __init__(self, root):
        self.zip = zipfile.ZipFile(root) if zipfile.is_zipfile(root) else None
        self.dir = None if self.zip else root
        self.names = []
        for name in (self.zip.namelist() if self.zip else self._walk()):
            if not name.startswith("reference/") or not name.endswith(".html"):
                continue
            self.names.append(name[len("reference/"):])
        self.names.sort()

    def _walk(self):
        for dirpath, _, files in os.walk(self.dir):
            for f in files:
                if f.endswith(".html"):
                    full = os.path.join(dirpath, f).replace("\\", "/")
                    i = full.rfind("reference/")
                    if i >= 0:
                        yield full[i:]

    def read(self, name):
        if self.zip:
            return self.zip.read("reference/" + name).decode("utf-8", "replace")
        return open(os.path.join(self.dir, "reference", name), encoding="utf-8", errors="replace").read()

    def doc_paths(self):
        """Every page path the extension can link to, e.g. "cpp/io/print"."""
        return set(n[len("en/"):][:-len(".html")] for n in self.names if n.startswith("en/"))

    def read_tagfile(self):
        """The doxygen tag file shipped in the same archive (or None).

        It lists class members, including ones with no description table entry
        of their own (data members, inherited members), each with the page that
        documents it.  Since the 2025 archive its <arglist> values are all
        "(T... args)" placeholders, so only names and paths are used.
        """
        name = "cppreference-doxygen-web.tag.xml"
        if self.zip:
            if name not in self.zip.namelist():
                return None
            return self.zip.read(name)
        path = os.path.join(self.dir, name)
        return open(path, "rb").read() if os.path.exists(path) else None


def parse_tagfile(data):
    """-> [(qualified member name, page)]"""
    if not data:
        return []
    root = ET.fromstring(data)
    out = []
    for compound in root:
        if compound.get("kind") == "file":  # header pages list no members
            continue
        holder = normalize(compound.findtext("name") or "") or ""
        for member in compound.findall("member"):
            page = member.findtext("anchorfile") or compound.findtext("filename") or ""
            page = re.sub(r"\s", "_", page)
            member_name = normalize(member.findtext("name") or "")
            if member_name and page:
                out.append(("%s::%s" % (holder, member_name) if holder else member_name, page))
    return out


def build(docs):
    """Merge the name sources, most specific first, then drop dead links."""
    docs_pages = Pages(docs)
    if not docs_pages.names:
        sys.exit("no pages found - expected reference/en/cpp/**.html inside %s" % docs)

    parsed, index_entries = [], []
    for name in docs_pages.names:
        if not name.startswith("en/"):
            continue
        doc_path = name[len("en/"):][:-len(".html")]
        if "cpp/" not in doc_path and not doc_path.startswith("c/"):
            continue
        bucket = "cpp/" if "cpp/" in doc_path else "c/"
        if doc_path.endswith("symbol_index") or "/symbol_index/" in doc_path:
            for key, target in parse_symbol_index(docs_pages.read(name)):
                index_entries.append((bucket, key, target))
        else:
            page_path, names, rows = parse_page(name, docs_pages.read(name))
            parsed.append((bucket, page_path, names, rows))

    buckets = {"cpp/": {}, "c/": {}}
    # page titles name the page's own entity -> most precise target
    for bucket, page_path, names, _ in parsed:
        for key in names:
            buckets[bucket].setdefault(key, page_path)
    # symbol index pages carry the namespace aliases (std::stacktrace, ...)
    for bucket, key, target in index_entries:
        buckets[bucket].setdefault(key, target)
    # description tables cover members, enumerators and aliases without a page
    for bucket, _, _, rows in parsed:
        for key, target in rows:
            buckets[bucket].setdefault(key, target)
    # tag file members fill what the tables do not spell out
    for key, target in parse_tagfile(docs_pages.read_tagfile()):
        bucket = next((b for b in buckets if target.startswith(b)), None)
        if bucket:
            buckets[bucket].setdefault(key, target)

    # never index a name that would 404 on cppreference.com
    pages_set = docs_pages.doc_paths()
    for prefix, entries in buckets.items():
        buckets[prefix] = {k: v for k, v in entries.items() if v in pages_set}
    return buckets


def download_latest():
    """Fetch the newest unofficial html book (the official archive is from 2019)."""
    request = Request(DOC_RELEASE_API, headers={"User-Agent": "cpp-search-extension"})
    with urlopen(request, timeout=60) as response:
        release = json.load(response)
    asset = next(a for a in release["assets"] if a["name"].startswith("html-book") and a["name"].endswith(".zip"))
    target = os.path.join(tempfile.gettempdir(), asset["name"])
    if os.path.exists(target) and os.path.getsize(target) == asset["size"]:
        print("using cached %s" % target)
    else:
        print("downloading %s (%.0f MB)" % (asset["name"], asset["size"] / 1048576))
        urlretrieve(asset["browser_download_url"], target)
    return target


def extract(docs, target):
    """Unpack reference/ and the doxygen tag file for the Rust tool, which walks files on disk."""
    if not zipfile.is_zipfile(docs):
        return
    with zipfile.ZipFile(docs) as archive:
        members = [e for e in archive.infolist()
                   if e.filename.startswith("reference/") or e.filename.endswith(".tag.xml")]
        archive.extractall(target, members)
    print("extracted %d files to %s" % (len(members), target))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docs", help="html book zip, extracted directory, or 'latest' to download the newest release")
    ap.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--extract-to", metavar="DIR",
                    help="also unpack reference/ there, for tools/std that reads files")
    ap.add_argument("--check", action="store_true",
                    help="fail if well-known symbols are not found (used by CI)")
    args = ap.parse_args()

    docs = args.docs
    if docs == "latest":
        docs = download_latest()
    if args.extract_to:
        extract(docs, args.extract_to)
        docs = args.extract_to

    buckets = build(docs)
    for fname, prefix in (("search-cpp", "cpp/"), ("search-c", "c/")):
        entries = buckets[prefix]
        path = os.path.join(args.out_dir, fname)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for key in sorted(entries):
                f.write("%s => %s\n" % (key, entries[key]))
        print("%s: %d entries" % (path, len(entries)))

    missing = [probe for probe, target in PROBES if buckets["cpp/"].get(probe, buckets["c/"].get(probe)) != target]
    print("self-check: %d/%d known symbols mapped" % (len(PROBES) - len(missing), len(PROBES)))
    if missing:
        print("   not mapped: %s" % ", ".join(missing))
        if args.check:
            sys.exit(1)

    if args.extract_to:
        print("\nNow rebuild the index the extension loads:")
        print("  cd tools/std && cargo run --release -- %s/reference/en" % args.extract_to)


if __name__ == "__main__":
    main()
