# AGENTS.md

A fork of [huhu/cpp-search-extension](https://github.com/huhu/cpp-search-extension) that ships a
regenerated cppreference search index. It is not on a browser store: the releases on GitHub are the
distribution. [README.md](README.md) holds the user-facing view, [RELEASING.md](RELEASING.md) the
release and store procedure.

## Layout

- `extension/` is the shipped package. `extension/manifest.json` and `extension/core/` are build
  output, not sources.
- `tools/std/` builds the index: `gen_symbol_map.py` produces `tools/std/search-cpp` and `search-c`,
  the Rust crate turns them into `extension/index/std.js`.
- `core/` is the shared omnibox runtime as a submodule. Changes belong in `extension/`.
- `docs/` is the zola site, `manifest.jsonnet` the manifest template.

## Commands

- `make chrome | edge | firefox` — builds that browser's `extension/manifest.json`. Needs `jsonnet`
  installed and the submodules checked out (`git submodule update --init`).
- `make index` — refreshes the search index end to end (python3 + cargo; caches the ~55 MB docs
  archive in the system temp dir).
- `gh workflow run release.yml` — builds and checks the three packages without publishing.

No test suite. The index generator self-checks with `--check`, packages and the site are checked by
CI only (`zola` is not installed locally, and the theme is a submodule).

## Rules

- Regenerate, never hand-edit: `extension/index/std.js`, `tools/std/search-cpp` and `search-c` come
  from `make index`. A symbol that does not show up is a data problem, not a searcher problem.
- Keep generation deterministic — sorted keys, sorted directory walk. The monthly
  `refresh-index.yml` diffs the regenerated index against the committed one, so non-determinism
  turns into an empty pull request on every run.
- Keep the extension offline: the index ships inside the package, no remote code, CSP stays
  `script-src 'self'`, and settings and history stay in `chrome.storage.local`.
  [privacy.md](docs/content/privacy.md) states this, and store declarations must match it.
- Point links at this repository. `cpp.extension.sh`, the original store listings, its Discord and
  its sponsors are not ours; the only upstream references kept on purpose are the fork note at the
  end of [README.md](README.md) and in the site footer.
- Commit messages: one imperative English subject line, body only for the non-obvious why. Repo prose
  is hard-wrapped near 110 columns; release notes are the exception, since GitHub renders their
  newlines as line breaks.
- Push to `origin`. `upstream` is for comparison only, and `gh` resolves to `huhu/...` in this
  clone, so pass `--repo Arteiimis/cpp-search-extension` to commands that need a repository.

## Release

The version lives in `manifest.jsonnet`, the changelog heading (`# v0.5 - 2026-10-15`) is what the
release workflow copies into the GitHub release, and a tag that does not match the manifest version
fails before anything is built. Store publishing is paused by the owner: the upstream listings still
serve 0.4.0, and [RELEASING.md](RELEASING.md) documents what submission would take.
