PANDOC ?= pandoc
POSTS  := $(wildcard posts/*.md)
PAGES  := $(patsubst posts/%.md,site/%.html,$(POSTS))

.PHONY: all indexes static clean

.DELETE_ON_ERROR:

all: $(PAGES) indexes static

site/%.html: posts/%.md template.html defaults.yaml refs.bib csl/chicago-author-date.csl
	@mkdir -p site
	$(PANDOC) --defaults defaults.yaml $< -o $@

indexes: $(PAGES) scripts/build_indexes.py
	python3 scripts/build_indexes.py

static:
	@if [ -d static ]; then mkdir -p site/static && cp -r static/. site/static/; fi

clean:
	rm -rf site
