# C/C++ Search Extension

<img align="right" width="280" src="extension/logo.png">

### The ultimate search extension for C/C++.

[![release](https://img.shields.io/github/v/release/Arteiimis/cpp-search-extension?label=release)](https://github.com/Arteiimis/cpp-search-extension/releases)
[![license-mit](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
[![license-apache](https://img.shields.io/badge/license-Apache-blue.svg)](LICENSE-APACHE)

## Installation

This fork is not published to a browser store, and the store listings of the original project still
ship their 0.4.0 build with the search index of 2023. Install a release package instead:

1. Download `cpp-search-extension-<version>-chrome.zip` (or `-edge.zip`) from
   [Releases](https://github.com/Arteiimis/cpp-search-extension/releases) and unpack it.
2. Chrome: open `chrome://extensions`, enable **Developer mode**, click **Load unpacked** and select
   the unpacked folder. Edge: the same under `edge://extensions`.
3. Firefox: unpack `-firefox.zip` and load the folder as a temporary add-on from
   `about:debugging#/runtime/this-firefox`. Release builds of Firefox only install signed add-ons,
   so a permanent install needs a build signed by addons.mozilla.org.

Updating means unpacking the newer package and reloading the extension, since nothing updates it in
the background.

## Features

- Search the C and C++ standard library docs: 20709 names from the 2026-10 cppreference snapshot,
  including C++20/23/26 additions such as `std::print`, `std::expected`, `std::jthread`,
  `std::mdspan`, `std::hive`, `std::ranges` views and `std::stacktrace`
- Results ranked by match quality, with inherited members linked to the page that declares them
- Offline mode: search a local copy of the cppreference offline docs
- Builtin commands (`:header`, `:posix` and `:history` etc)

## How to use it

Input keyword **cc** in the address bar, press `Space` to activate the search bar. Then enter any word
you want to search, the extension will response the related search results instantly.

Commands are prefixed with `:` (`cc :header print`), and a trailing `-` pages down through the
results (`cc print -`).

### Offline mode

Open the extension options, enable offline mode and set the path of an unpacked cppreference archive
(for example `file:///home/me/cppreference/en/`). Results then open local pages instead of
cppreference.com. The offline docs have to match the snapshot the index was built from.

## Development

[jsonnet](https://jsonnet.org/) is required before getting started. To install `jsonnet`, check
`jsonnet`'s [README](https://github.com/google/jsonnet#packages); on Linux the `snap` is a good
choice to [install jsonnet](https://snapcraft.io/install/jsonnet/ubuntu).

```bash
$ git clone --recursive https://github.com/Arteiimis/cpp-search-extension
Cloning into 'cpp-search-extension'...

$ cd cpp-search-extension

$ make chrome # For Chrome version

$ make firefox # For Firefox version

$ make edge # For Edge version
```

Each target writes `extension/manifest.json` for that browser and copies the shared code from the
`core` submodule into `extension/core`; `make pack <browser>` zips the result with
[web-ext](https://github.com/mozilla/web-ext). A clone that was not made with `--recursive` needs
`git submodule update --init` first. Packaging a release and submitting it to a store is documented
in [RELEASING.md](RELEASING.md).

## Updating the search index

The extension searches `extension/index/std.js`, which maps `std::name` to a cppreference page. It
is a snapshot of the cppreference offline docs built by `tools/std`, so a new C++ release makes
symbols such as `std::print`, `std::expected` or `std::jthread` silently unsearchable:

```bash
$ make index   # needs python3 (stdlib only) and cargo
```

[`tools/std/gen_symbol_map.py`](tools/std/gen_symbol_map.py) downloads the newest docs archive,
preferring the [maintained cppreference-doc fork](https://github.com/cristianadam/cppreference-doc/releases)
over the [html book releases](https://github.com/PeterFeicht/cppreference-doc/releases) it came from
(the official archive is stuck at 2019-06-07, and the html book stopped in 2025-02 when the
cppreference upgrade broke its tooling), and rebuilds `tools/std/search-cpp` / `search-c` from the
docs themselves: page titles, symbol index pages, member tables and the doxygen tag file pinned in
`tools/std` (the fork ships none). `tools/std` (Rust) then joins them with the description tables
of every page and writes `extension/index/std.js`. Names whose page is gone are dropped, so the
index never links to a 404; `--check` fails the run when well-known symbols go missing or the maps
shrink suspiciously, and `.github/workflows/refresh-index.yml` opens a pull request with the
monthly refresh.

Both steps can also be run by hand:

```bash
$ python tools/std/gen_symbol_map.py latest --extract-to .docs-offline --check
$ cd tools/std && cargo run --release -- ../../.docs-offline/reference/en && cd ../..
```

## About this fork

This repository is a fork of [huhu/cpp-search-extension](https://github.com/huhu/cpp-search-extension).
It exists because the original is no longer maintained and its search index was built from a
2023-07-29 cppreference snapshot, which left newer library symbols unsearchable; see
[Updating the search index](#updating-the-search-index) for how the index is rebuilt here. The
original project, its browser store listings and its documentation site remain its own.
