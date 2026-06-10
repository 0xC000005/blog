#!/usr/bin/env python3
"""Generate site/index.html and site/feed.xml from posts/*.md and rendered HTML.

Stdlib only. Front matter is a flat YAML subset: `key: value` string pairs.
"""
import html
import re
import sys
from pathlib import Path

SITE_URL = "https://0xC000005.github.io/blog"
FEED_TITLE = "Blog"
POSTS_DIR = Path("posts")
SITE_DIR = Path("site")

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blog</title>
<link rel="alternate" type="application/atom+xml" href="feed.xml" title="Blog">
</head>
<body>
<h1>Blog</h1>
<ul>
{items}
</ul>
<hr>
<form action="https://duckduckgo.com/" method="get">
<input type="hidden" name="sites" value="0xC000005.github.io/blog">
<input type="text" name="q" size="25">
<input type="submit" value="Search">
</form>
<small>
<a href="feed.xml">feed</a><br>
Last updated: {updated}
<!-- goatcounter: enabled later, after signup
<img src="https://FIXME-CODE.goatcounter.com/counter/TOTAL.png" alt="">
-->
</small>
</body>
</html>
"""

FEED_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{title}</title>
  <link href="{site_url}/"/>
  <link rel="self" href="{site_url}/feed.xml"/>
  <id>{site_url}/</id>
  <updated>{updated}</updated>
  <author><name>{title}</name></author>
{entries}
</feed>
"""

ENTRY_TEMPLATE = """  <entry>
    <title>{title}</title>
    <link href="{url}"/>
    <id>{url}</id>
    <updated>{date}T00:00:00Z</updated>
    <content type="html">{content}</content>
  </entry>"""


def parse_front_matter(text):
    """Parse a leading `---` block as flat `key: value` pairs."""
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta


def sort_posts(posts):
    return sorted(posts, key=lambda p: (p["date"], p["slug"]), reverse=True)


def load_posts(posts_dir=POSTS_DIR):
    posts = []
    for path in sorted(posts_dir.glob("*.md")):
        meta = parse_front_matter(path.read_text(encoding="utf-8"))
        for required in ("title", "date"):
            if required not in meta:
                sys.exit(f"error: {path} front matter is missing '{required}'")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["date"]):
            sys.exit(f"error: {path} date must be YYYY-MM-DD")
        posts.append({
            "slug": path.stem,
            "title": meta["title"],
            "date": meta["date"],
            "description": meta.get("description", ""),
        })
    return sort_posts(posts)


def extract_content(slug, site_dir=SITE_DIR):
    page = (site_dir / f"{slug}.html").read_text(encoding="utf-8")
    m = re.search(r"<!-- content-start -->(.*?)<!-- content-end -->", page, re.S)
    if not m:
        sys.exit(f"error: {site_dir}/{slug}.html lacks content markers")
    return m.group(1).strip()


def build_index(posts):
    items = []
    for p in posts:
        desc = f" &mdash; {html.escape(p['description'])}" if p["description"] else ""
        items.append(
            f'<li>{p["date"]} &mdash; '
            f'<a href="{p["slug"]}.html">{html.escape(p["title"])}</a>{desc}</li>'
        )
    updated = posts[0]["date"] if posts else "n/a"
    return INDEX_TEMPLATE.format(items="\n".join(items), updated=updated)


def build_feed(posts, contents):
    entries = "\n".join(
        ENTRY_TEMPLATE.format(
            title=html.escape(p["title"]),
            url=f"{SITE_URL}/{p['slug']}.html",
            date=p["date"],
            content=html.escape(contents[p["slug"]]),
        )
        for p in posts
    )
    updated = f"{posts[0]['date']}T00:00:00Z" if posts else "1970-01-01T00:00:00Z"
    return FEED_TEMPLATE.format(
        title=FEED_TITLE, site_url=SITE_URL, updated=updated, entries=entries
    )


def main():
    posts = load_posts()
    contents = {p["slug"]: extract_content(p["slug"]) for p in posts}
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(build_index(posts), encoding="utf-8")
    (SITE_DIR / "feed.xml").write_text(build_feed(posts, contents), encoding="utf-8")
    print(f"wrote site/index.html and site/feed.xml ({len(posts)} posts)")


if __name__ == "__main__":
    main()
