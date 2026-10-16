use std::cell::RefCell;
use std::collections::{BTreeMap, HashMap};
use std::error::Error;
use std::fs::{DirEntry, File};
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::rc::Rc;
use std::{fs, io};

use select::document::Document;
use select::predicate::{Class, Name, Predicate};

type Result<T> = std::result::Result<T, Box<dyn Error>>;

type DocPath = String;
type DocIdentifier = String;
type DocDescription = String;

/// The same escape gen_symbol_map.py applies: a page name can contain characters
/// Windows cannot store in a file name, and both sides have to spell those paths
/// the same way for the descriptions to join.
fn escape_name(name: &str) -> String {
    let mut escaped = String::with_capacity(name.len());
    for c in name.chars() {
        if matches!(c, '<' | '>' | ':' | '"' | '|' | '?' | '*' | '%') {
            escaped.push_str(&format!("%{:02X}", c as u32));
        } else {
            escaped.push(c);
        }
    }
    escaped
}

fn main() -> Result<()> {
    // The cppreference.com offline docs path
    let docs_path = std::env::args().nth(1).expect("docs_path is required");
    let raw_search_index = generate_index(&["search-cpp", "search-c"])?;
    println!("Raw search index length: {}", raw_search_index.len());
    let search_index = parse_docs(&docs_path, raw_search_index)?;
    println!("Search index length: {}", search_index.len());
    // Sorted keys: HashMap order is randomised per process, which would make every
    // regeneration of std.js differ even when nothing about the docs changed.
    let sorted: BTreeMap<_, _> = search_index.into_iter().collect();
    let contents = serde_json::to_string(&sorted)?;
    let path = Path::new("../../extension/index/std.js");
    fs::write(path, format!("var searchIndex={};", contents))?;
    Ok(())
}

fn generate_index(files: &[&str]) -> Result<HashMap<DocIdentifier, DocPath>> {
    let mut map = HashMap::new();
    for file_name in files {
        let file = File::open(file_name)?;
        let br = BufReader::new(file);
        for line in br.lines() {
            let line = line?;
            let mut pair: Vec<String> = line.split(" => ").map(String::from).collect();
            map.insert(pair.remove(0), pair.remove(0));
        }
    }
    Ok(map)
}

fn parse_docs(
    path: &str,
    raw_search_index: HashMap<DocIdentifier, DocPath>,
) -> Result<HashMap<DocIdentifier, (DocPath, Option<DocDescription>)>> {
    let pair_map = Rc::new(RefCell::new(HashMap::<DocPath, DocDescription>::new()));
    visit_dirs(Path::new(path), &|entry| {
        if let Ok(html) = fs::read_to_string(entry.path()) {
            let document = Document::from(html.as_str());
            for node in document.find(Class("t-dsc-begin").descendant(Class("t-dsc"))) {
                if node.find(Name("td")).count() == 2 {
                    if let Some(Some(title)) = node
                        .find(Class("t-dsc-member-div").descendant(Name("a")))
                        .map(|n| {
                            n.attr("title")
                                .filter(|title| !title.contains("page does not exist"))
                        })
                        .next()
                    {
                        let path = escape_name(&title.replace(' ', "_"));

                        if let Some(dt) = node.last_child() {
                            let description = dt.text().trim().to_string();
                            pair_map.borrow_mut().insert(path, description);
                        }
                    }
                }
            }
        }
    })?;
    let search_index = raw_search_index
        .into_iter()
        .map(|(doc_identifier, doc_path)| {
            let description = pair_map.borrow().get(&doc_path).map(|d| d.to_owned());
            (doc_identifier, (doc_path, description))
        })
        .collect();
    Ok(search_index)
}

fn visit_dirs(dir: &Path, cb: &dyn Fn(&DirEntry)) -> io::Result<()> {
    if dir.is_dir() {
        // fs::read_dir yields entries in filesystem order; several pages can offer a
        // description for the same page (the last one wins), so an unsorted walk would
        // make extension/index/std.js depend on the machine that generated it.
        let mut entries = fs::read_dir(dir)?.collect::<io::Result<Vec<_>>>()?;
        entries.sort_by_key(|entry| entry.file_name());
        for entry in entries {
            let path = entry.path();
            if path.is_dir() {
                visit_dirs(&path, cb)?;
            } else {
                cb(&entry);
            }
        }
    }
    Ok(())
}
