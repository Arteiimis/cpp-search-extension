+++
title = "Changelog"
description = "Changelog"
weight = 3
+++


# v0.5 - 2026-10-15

- Rebuild the search index from the newest cppreference docs (2025-02), so C++20/23/26 symbols
  such as `std::print`, `std::println`, `std::expected`, `std::jthread`, `std::mdspan`,
  `std::ranges` views and `std::stacktrace` are searchable again (13018 -> 19960 entries)
- Add `tools/std/gen_symbol_map.py` plus `make index` to regenerate the index, and a monthly
  workflow that opens a pull request with the refresh
- Rank search results by match quality instead of match position only: an exact component match
  wins (`print` now finds `std::print` first, `sort` finds `std::sort`, `move` finds `std::move`),
  an exact case match wins (`hash` finds `std::hash` before `std::Hash`), C++ technical
  specification pages are demoted, and names pointing at the same page are listed once
- Link inherited members to the page that declares them (`std::ctype::print` and
  `std::bad_alloc::what` now open `std::ctype_base` and `std::exception::what`), which also
  stops one page from filling the results under four different class scopes

# v0.4 - 2023-07-29

- Update to last cppreference.com docs
- Add options page to configure offline docs path
- Migrate to latest jsonnet
- Add index generating tools

# v0.3 - 2022-06-02

- Migrate from `localStorage` to `chrome.storage` API. The new `storage` permission is required.
- Remove the `tabs` permission requirement.
- Remove offline doc path validation. Fixes {{ issue(id=8) }}.

# v0.2 - 2021-01-31

- Support multi-locale language cppreference docs search
- New command:
  - `:posix` - Show all POSIX [system interfaces](https://pubs.opengroup.org/onlinepubs/9799919799/functions/contents.html)
- Improve user experience of offline doc path configuration, thanks to the PR ([#3](https://github.com/huhu/cpp-search-extension/pull/3)) from [@knewbie](https://github.com/knewbie).

# v0.1 - 2020-09-30

First release version! 🎉🥳🥳

- Search C/C++ standard library docs
- Offline mode supported
- Command systems:
    - `:help` command to show all help messages
    - `:header` command to show all C++ header libraries
    - `:history` command to show your local search history


