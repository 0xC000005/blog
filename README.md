# Blog

Static site built with pandoc. Served at https://0xC000005.github.io/blog/

## Add a post

1. Create `posts/<slug>.md` with front matter:

       ---
       title: Some title
       date: 2026-06-10
       description: Optional one-liner for the index.
       ---

2. Cite with `[@bibkey]` (entries live in `refs.bib`); math with `$...$` / `$$...$$`.
3. Push. CI builds and deploys in ~2 minutes. Drafts go in `posts/drafts/` (ignored).

## Build locally

`make` (needs pandoc + python3), then open `site/index.html`. `make clean` to reset.
