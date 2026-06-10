# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pandoc-built static blog, deployed by `.github/workflows/build.yml` (pinned pandoc → `make` → Pages artifact) to https://0xC000005.github.io/blog/. Posts are `posts/*.md` (front matter: flat `key: value` pairs — `title`, `date`, optional `description`, optional `author` for crediting reposted articles; no inline comments); citations resolve against `refs.bib` via citeproc; math compiles to MathML (zero JS). `scripts/build_indexes.py` (stdlib only; tests in `tests/`) generates `index.html` + `feed.xml` from rendered pages using the `<!-- content-start/end -->` markers in `template.html`.

Build/test: `make` to build into `site/`; `python3 -m unittest discover -s tests` for the generator tests.

Keep output HTML minimal and hand-written-looking: no CSS files, no JS except the giscus embed, no favicons/OpenGraph.
