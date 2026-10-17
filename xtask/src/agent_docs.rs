//! `CLAUDE.md` and `AGENTS.md` carry the same instructions: tools read one or the other. They
//! are kept as two identical files (a symlink does not survive every checkout, on Windows).

#[cfg(test)]
mod tests {
    use std::fs;

    #[test]
    fn claude_md_is_a_copy_of_agents_md() {
        let root = crate::root();
        let read = |name: &str| fs::read_to_string(root.join(name)).unwrap_or_else(|e| panic!("read {name}: {e}"));
        assert!(read("CLAUDE.md") == read("AGENTS.md"), "CLAUDE.md differs from AGENTS.md: edit AGENTS.md, then `cp AGENTS.md CLAUDE.md`");
    }
}
