# SolidCraft repo facts

Facts a run needs about tangency-labs/solidcraft. Each fact was checked on 2026-10-15
against upstream main `b6806b1`. Re-check a fact before you rely on it in a PR.

## Repositories and identity

| Item | Value |
|---|---|
| Upstream | `https://github.com/tangency-labs/solidcraft` (branch `main`) |
| Fork | `https://github.com/Ian-cmd-ops/solidcraft` |
| Kit and run state | branch `ops` on the fork (this branch) |
| Commit author | `Ian-cmd-ops <78785932+Ian-cmd-ops@users.noreply.github.com>` |
| Commit footer | `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and nothing else |
| Never in any commit, PR, issue or comment | the owner's full name, a `claude.ai/code/session` link, a "Generated with" footer |

## Build and test commands

Run from the repo root. Use `CARGO_TARGET_DIR=<repo>/target CARGO_BUILD_JOBS=2`.

| What | Command | Time on 2 cores |
|---|---|---|
| Build for the engine tests | `cargo test --profile ci -p solidcraft-engine --lib --no-run` | 7 to 10 min from cold |
| One goldens part | `cargo test --profile ci -p solidcraft-engine --lib -- --include-ignored --exact tests::robustness_goldens::all_N` | 11 min for `all_3` |
| Record a goldens change | `ROBUSTNESS_GOLDENS_BLESS="why" ` plus the command above | same |
| One engine test file | `cargo test --profile ci -p solidcraft-engine --test <file_stem>` | 1 to 5 min |
| Kernel lib tests by name | `cargo test --profile ci -p solidcraft-kernel --lib <filter>` | varies |
| Format | `cargo fmt --all -- --check` | under 1 min |
| Lint | `cargo clippy --profile ci -p solidcraft-kernel -p solidcraft-engine --all-targets -- -D warnings` | 10 to 20 min |
| Licences | `cargo xtask licences --check` (after any dependency change) | under 1 min |

- **Goldens parts:** `all_N` holds every seed where seed mod 4 equals N. There are 96 seeds.
- **PR CI** runs only `sample_0` to `sample_3` (every 8th seed). Pushes to `main` and the nightly run all parts.
- **Heavy tests** `boolean_props` and `atomic_commands` are filtered out of PR CI in `.config/nextest.toml`.
- **Do not run** the full `cargo xtask ci` on 2 cores. It takes hours. Say "Not run" in the PR instead.
- **No wasm32 target** is installed in the cloud workspace. Say so under "Not run".

## Fuzz and pictures

- `solidcraft_engine::fuzz::run(seed, 8)` builds a seed's random design. `fuzz::minimise(&run)` shrinks a failing one.
- `solidcraft-cli fuzz-one <seed> --minimise` does the same from the CLI.
- `solidcraft-cli snapshot <script.json> --out shot.png --camera '{...}' --no-grid --no-axes` renders a picture without a window.

## Rules from the repo's own CLAUDE.md that reviews enforce

- No `unwrap`, `expect`, `panic!`, `unreachable!`, `todo!` or `unsafe` in non-test code. Errors are `Result`.
- Every call into `truck` goes through `solidcraft_kernel::guard`.
- Every crash fix lands with a regression test.
- Never read or copy GPL, LGPL or AGPL code (OpenCASCADE, FreeCAD, SolveSpace and others).
- `vendor/` is outside the workspace. A vendored crate's own `#[cfg(test)]` tests never run.
  Expose a `#[doc(hidden)]` hook behind a `test-hooks` feature and test it from `crates/kernel`.
- Keep each PR to one topic. When a PR conflicts, rebase or merge `main` into it. Never force-push `main`.
  Our own practice is stricter: merge `main` and never force-push a branch with an open PR,
  so the owner's review history stays intact.

## What the owner asks for in reviews

Collected from reviews on #1307, #1308, #1309 and #1316.

- **A filled description** with the template sections: Change, Validation,
  Screenshots of the behavior (when observable), Integration status. He will not merge a template.
- **Measured values on current main**, with the case, the command, and before and after.
- **Exact values** (closed-form volumes) instead of loose bands.
- **A before and after picture** for anything visible.
- **Tests that run in CI.** A test that never runs counts as no test.
- **Separate decisions in separate PRs** (for example, a CI job apart from the tests it runs).
- **A skipped test belongs in an issue**, not in the code.
- **Regenerated `THIRD-PARTY-LICENSES.txt`** whenever dependencies change.

## Seeds that still fail on upstream main (b6806b1)

19 of 96 are not ok. #1316 fixes 83.

| Error | Seeds |
|---|---|
| boolean Cut: no result | 2, 5, 15, 18, 61, 95 |
| offset: a corner whose faces don't meet the same way | 6, 38, 40, 69, 73, 78, 83, 86 |
| boolean Union: implausible result volume | 45, 63 |
| lumps: shell boundaries intersect or touch | 9, 70 |
| invalid Body | 55 |

Seed 6 is a saddle on a cylinder seam (issue #1494). Seeds 38, 69 and 73 are related saddles on curved faces.
