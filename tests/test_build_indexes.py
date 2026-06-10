import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_indexes as bi


POSTS = [
    {"slug": "older", "title": "Older & wiser", "date": "2026-01-05", "description": ""},
    {"slug": "newer", "title": "Newer", "date": "2026-06-10", "description": "A one-liner."},
]


class TestFrontMatter(unittest.TestCase):
    def test_parses_flat_keys(self):
        meta = bi.parse_front_matter("---\ntitle: Hello\ndate: 2026-06-10\n---\nbody")
        self.assertEqual(meta, {"title": "Hello", "date": "2026-06-10"})

    def test_strips_quotes_and_skips_comments(self):
        meta = bi.parse_front_matter('---\ntitle: "Quoted"\n# note\ndate: 2026-06-10\n---\n')
        self.assertEqual(meta["title"], "Quoted")
        self.assertNotIn("# note", meta)

    def test_no_front_matter_returns_empty(self):
        self.assertEqual(bi.parse_front_matter("just text"), {})


class TestSorting(unittest.TestCase):
    def test_reverse_chronological(self):
        ordered = bi.sort_posts(list(POSTS))
        self.assertEqual([p["slug"] for p in ordered], ["newer", "older"])


class TestIndex(unittest.TestCase):
    def test_index_lists_posts_in_order_and_escapes(self):
        out = bi.build_index(bi.sort_posts(list(POSTS)))
        self.assertLess(out.find("newer.html"), out.find("older.html"))
        self.assertIn("Older &amp; wiser", out)
        self.assertIn("A one-liner.", out)
        self.assertIn("<h1>Blog</h1>", out)


class TestFeed(unittest.TestCase):
    def test_feed_author_is_literal_blog(self):
        contents = {"older": "<p>x &amp; y</p>", "newer": "<p>z</p>"}
        out = bi.build_feed(bi.sort_posts(list(POSTS)), contents)
        root = ET.fromstring(out)
        ns = "{http://www.w3.org/2005/Atom}"
        self.assertEqual(root.tag, f"{ns}feed")
        self.assertEqual(root.find(f"{ns}author/{ns}name").text, "Blog")
        entries = root.findall(f"{ns}entry")
        self.assertEqual(len(entries), 2)
        self.assertIn("<p>x &amp; y</p>", entries[1].find(f"{ns}content").text)
        self.assertTrue(entries[0].find(f"{ns}id").text.endswith("/newer.html"))


class TestLoadPostsValidation(unittest.TestCase):
    def _write(self, tmp, name, text):
        p = Path(tmp) / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_missing_title_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.md", "---\ndate: 2026-06-10\n---\n")
            with self.assertRaises(SystemExit):
                bi.load_posts(Path(tmp))

    def test_empty_title_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.md", "---\ntitle:\ndate: 2026-06-10\n---\n")
            with self.assertRaises(SystemExit):
                bi.load_posts(Path(tmp))

    def test_impossible_date_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.md", "---\ntitle: A\ndate: 2026-13-99\n---\n")
            with self.assertRaises(SystemExit):
                bi.load_posts(Path(tmp))

    def test_bad_slug_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "bad slug.md", "---\ntitle: A\ndate: 2026-06-10\n---\n")
            with self.assertRaises(SystemExit):
                bi.load_posts(Path(tmp))

    def test_drafts_subdir_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "drafts").mkdir()
            self._write(tmp, "ok.md", "---\ntitle: A\ndate: 2026-06-10\n---\n")
            self._write(tmp, "drafts/d.md", "---\ntitle: D\ndate: 2026-06-10\n---\n")
            posts = bi.load_posts(Path(tmp))
            self.assertEqual([p["slug"] for p in posts], ["ok"])


class TestExtractContent(unittest.TestCase):
    def test_missing_markers_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.html").write_text("<html>no markers</html>", encoding="utf-8")
            with self.assertRaises(SystemExit):
                bi.extract_content("x", Path(tmp))

    def test_duplicate_end_marker_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.html").write_text(
                "<!-- content-start -->a<!-- content-end -->b<!-- content-end -->",
                encoding="utf-8")
            with self.assertRaises(SystemExit):
                bi.extract_content("x", Path(tmp))

    def test_reversed_markers_exit_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.html").write_text(
                "<!-- content-end -->x<!-- content-start -->", encoding="utf-8")
            with self.assertRaises(SystemExit):
                bi.extract_content("x", Path(tmp))

    def test_extracts_between_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.html").write_text(
                "<head/><!-- content-start -->\n<p>Hi</p>\n<!-- content-end --><small/>",
                encoding="utf-8")
            self.assertEqual(bi.extract_content("x", Path(tmp)), "<p>Hi</p>")


class TestAuthorField(unittest.TestCase):
    REPOST = {"slug": "repost", "title": "Borrowed", "date": "2026-03-01",
              "description": "", "author": "Jane Q. Author"}

    def test_index_shows_repost_author(self):
        out = bi.build_index(bi.sort_posts([dict(POSTS[0]), dict(self.REPOST)]))
        self.assertIn("(Jane Q. Author)", out)

    def test_index_omits_author_when_absent(self):
        out = bi.build_index([dict(POSTS[0])])
        self.assertNotIn("()", out)

    def test_feed_entry_author_only_for_reposts(self):
        posts = bi.sort_posts([dict(POSTS[0]), dict(self.REPOST)])
        contents = {"older": "<p>a</p>", "repost": "<p>b</p>"}
        out = bi.build_feed(posts, contents)
        root = ET.fromstring(out)
        ns = "{http://www.w3.org/2005/Atom}"
        by_id = {e.find(f"{ns}id").text: e for e in root.findall(f"{ns}entry")}
        repost_entry = by_id["https://0xC000005.github.io/blog/repost.html"]
        older_entry = by_id["https://0xC000005.github.io/blog/older.html"]
        self.assertEqual(repost_entry.find(f"{ns}author/{ns}name").text, "Jane Q. Author")
        self.assertIsNone(older_entry.find(f"{ns}author"))

    def test_index_has_neutral_description_line(self):
        out = bi.build_index([dict(POSTS[0])])
        self.assertIn("Reposted articles carry their original authors", out)

    def test_index_links_stylesheets(self):
        out = bi.build_index([dict(POSTS[0])])
        self.assertIn('href="static/latex.css"', out)
        self.assertIn('href="static/site.css"', out)


if __name__ == "__main__":
    unittest.main()
