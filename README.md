# C/C++ Search Extension

<img align="right" width="280" src="extension/logo.png">

### The ultimate search extension for C/C++.

![Chrome Web Store](https://img.shields.io/chrome-web-store/v/ifpcmhciihicaljnhgobnhoehoabidhd.svg)
![Mozilla Add-on](https://img.shields.io/amo/v/c-c-search-extension?color=%2320123A)
![Microsoft Edge](https://img.shields.io/badge/microsoft--edge-v0.4.0-1D4F8C)
[![license-mit](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/huhu/rust-search-extension/blob/master/LICENSE-MIT)
[![license-apache](https://img.shields.io/badge/license-Apache-blue.svg)](https://github.com/huhu/cpp-search-extension/blob/master/LICENSE)
[![Discord](https://img.shields.io/discord/711895914494558250?label=chat&logo=discord)](https://discord.gg/xucZNVd)

[https://cpp.extension.sh/](https://cpp.extension.sh/)

## Installation

- [Chrome Web Store](https://chrome.google.com/webstore/detail/cc++-search-extension/ifpcmhciihicaljnhgobnhoehoabidhd)

- [Firefox](https://addons.mozilla.org/en-US/firefox/addon/c-c-search-extension/)

- [Microsoft Edge](https://microsoftedge.microsoft.com/addons/detail/ffajabficigcddnckikojejmkammkmpe)


## Features

- Search standard library docs
- Offline mode supported
- Builtin commands (`:header`, `:posix` and `:history` etc)

## How to use it
   
Input keyword **cc** in the address bar, press `Space` to activate the search bar. Then enter any word 
you want to search, the extension will response the related search results instantly.

## Contribution

[jsonnet](https://jsonnet.org/) is required before getting started. To install `jsonnet`, please check `jsonnet`'s [README](https://github.com/google/jsonnet#packages). For Linux users, the `snap` is a good choice to [install jsonnet](https://snapcraft.io/install/jsonnet/ubuntu).

```bash
$ git clone --recursive https://github.com/huhu/cpp-search-extension
Cloning into 'cpp-search-extension'...

$ cd cpp-search-extension

$ make chrome # For Chrome version

$ make firefox # For Firefox version

$ make edge # For Edge version
```

## Updating the search index

The extension searches `extension/index/std.js`, which maps `std::name` to a cppreference page. It
is a snapshot of the cppreference offline docs built by `tools/std`, so a new C++ release makes
symbols such as `std::print`, `std::expected` or `std::jthread` silently unsearchable:

```bash
$ make index   # needs python3 (stdlib only) and cargo
```

[`tools/std/gen_symbol_map.py`](tools/std/gen_symbol_map.py) downloads the newest "html book"
from the [unofficial cppreference-doc releases](https://github.com/PeterFeicht/cppreference-doc/releases)
(the official archive is stuck at 2019-06-07) and rebuilds `tools/std/search-cpp` / `search-c`
from the docs themselves: page titles, symbol index pages, member tables and the doxygen tag
file. `tools/std` (Rust) then joins them with the description tables of every page and writes
`extension/index/std.js`. Names whose page is gone are dropped, so the index never links to a
404; `--check` fails the run when well-known symbols go missing, and
`.github/workflows/refresh-index.yml` opens a pull request with the monthly refresh.

Both steps can also be run by hand:

```bash
$ python tools/std/gen_symbol_map.py latest --extract-to .docs-offline --check
$ cd tools/std && cargo run --release -- ../../.docs-offline/reference/en && cd ../..
```

## Get involved

- You can contact us on Discord Channel: https://discord.gg/xucZNVd
