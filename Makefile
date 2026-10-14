include core/extension.mk

PYTHON ?= python3

.PHONY: chrome

# Refresh the search index from the newest cppreference offline docs.
# Needs python3 (stdlib only) and cargo; the ~55 MB archive is cached in the
# system temp dir, so re-running only downloads it when a new release is out.
.PHONY: index
index:
	$(PYTHON) tools/std/gen_symbol_map.py latest --extract-to .docs-offline --check
	cd tools/std && cargo run --release -- ../../.docs-offline/reference/en
	rm -rf .docs-offline
