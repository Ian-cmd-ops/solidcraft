---
name: solidcraft-workflow
description: Quick reference for fixing SolidCraft (Rust CAD) bugs test-first and posting PR kits to bherbruck/solidcraft
mode: skill
triggers: solidcraft,robustness seed,goldens,post kit,bherbruck
---

# solidcraft-workflow

> Load this skill when: working on SolidCraft code, its robustness seeds or goldens,
> or posting a run's kit to bherbruck/solidcraft.

## Quick Reference

| Task | Command or place |
|------|------------------|
| One goldens part (seed mod 4 = N) | `cargo test --profile ci -p solidcraft-engine --lib -- --include-ignored --exact tests::robustness_goldens::all_N` |
| Record a goldens change | prefix `ROBUSTNESS_GOLDENS_BLESS="why"` |
| Shrink a failing seed | `solidcraft-cli fuzz-one <seed> --minimise` |
| Format and lint | `cargo fmt --all -- --check`; clippy `--profile ci -p <crates> --all-targets -- -D warnings` |
| Post a kit (Ian) | `tools/post_kit.sh kits/<date> --dry-run`, then without `--dry-run` |
| Full facts and timings | `docs/repo-facts.md` |

## Key Rules

- Failing test first, in its own commit; then the fix in its own commit.
- Every commit builds and passes on its own. One logical change each.
- Label each claim: ran and saw, believe, or not run.
- Exact values over tolerance bands. Mutation-check equivalence tests.
- Merge `upstream/main` on conflict. Never force-push an open PR.
- Author `Ian-cmd-ops` with the noreply email. No full name, no session link.

## Do NOT

- Do NOT post to bherbruck/solidcraft from an agent. Ian posts the kit.
- Do NOT write `#NNNN`. Use `{{VAR}}` placeholders in kits.
- Do NOT run the full `cargo xtask ci` on 2 cores. List it under "Not run".
- Do NOT claim a check you have not finished.

## Related

- `docs/standards.md`: how every change is made
- `docs/run-procedure.md`: the daily scheduled run
- `docs/lessons.md`: known pitfalls
