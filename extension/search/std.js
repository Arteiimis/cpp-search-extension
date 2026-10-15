function StdSearcher(rawIndex) {
    this.index = rawIndex;
    this.docs = Object.keys(this.index);
    // Lowercased once, the search runs on every keystroke.
    this.lowerDocs = this.docs.map(doc => doc.toLowerCase());
}

// How well does the keyword match the name? The lower the rank, the better.
// 0 the whole name, 1 a whole component (`print` in `std::print`), 2 the start of a
// component (`print` in `printf`), 3 the start of a word (`new` in `operator new`),
// 4 inside a word or a parameter list (`move` in `remove`, `size_t` in `end(size_type)`).
function matchRank(name, index, length) {
    if (name.length === length) return 0;

    const componentStart = index === 0 || (name[index - 2] === ':' && name[index - 1] === ':');
    if (componentStart) {
        return name.length - index === length ? 1 : 2;
    }

    const previous = name[index - 1];
    if (previous && previous !== '(' && !/[A-Za-z0-9_]/.test(previous)) return 3;
    return 4;
}

StdSearcher.prototype.search = function (keyword) {
    const query = keyword.toLowerCase();
    let result = [];
    for (let i = 0; i < this.docs.length; i++) {
        const name = this.docs[i];
        if (name.length < query.length) continue;

        const index = this.lowerDocs[i].indexOf(query);
        if (index === -1) continue;

        let [path, description] = this.index[name];
        result.push({
            name,
            path,
            description,
            rank: matchRank(this.lowerDocs[i], index, query.length),
            matchIndex: index,
            // Ranking is case-insensitive, but an exact case match is a better hit:
            // `hash` should find std::hash before the std::Hash named requirement.
            caseMiss: name.substr(index, query.length) === keyword ? 0 : 1,
            // The C++ technical specifications have their own pages (std::experimental::*,
            // cpp/experimental/*) that duplicate the paper wording. They are only worth
            // showing when nothing in the standard library matches.
            experimental: path.indexOf('/experimental/') !== -1 ? 1 : 0,
        });
    }

    // The lower the rank, the earlier the match, the shorter the name, the higher the
    // result. Sorting by name last keeps the order stable between equal matches.
    result.sort((a, b) => {
        return a.rank - b.rank
            || a.experimental - b.experimental
            || a.matchIndex - b.matchIndex
            || a.caseMiss - b.caseMiss
            || a.name.length - b.name.length
            || (a.name < b.name ? -1 : 1);
    });

    // Different names can point at the same page (printf and printf_s, or
    // println(std::ostream) and std::println(std::ostream)): list the page once.
    let seen = new Set();
    return result.filter(item => {
        if (seen.has(item.path)) return false;
        seen.add(item.path);
        return true;
    }).map(item => {
        return {
            name: item.name,
            path: item.path,
            description: item.description,
        };
    });
};
