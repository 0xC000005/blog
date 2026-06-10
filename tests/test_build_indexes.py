import sys
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
    def test_feed_is_wellformed_unsigned_atom(self):
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


if __name__ == "__main__":
    unittest.main()
