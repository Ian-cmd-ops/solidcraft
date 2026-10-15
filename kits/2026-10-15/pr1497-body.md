## Change

This PR is now tests only. It adds two regression tests for robustness seed 17: a thin three-quarter tube, shelled 1 mm with its bottom open, must read back from STEP with the same volume and area.

Before #1438, the STEP writer merged each 270° wall into one face, but it kept the first quarter piece's sheet as that face's surface. The body read back closed, with no warning, and 7% too small (2968.53 mm³ became 2754.67 mm³).

This PR first fixed that with its own seam search (`gap_middle`). #1438 then changed the same code, and current main passes both seed 17 tests without `gap_middle`. I did not check which part of #1438's change sets the seam for seed 17. So the merge with main takes main's `step_out.rs` and drops `gap_middle`. The tests stay, so the case stays pinned in CI.

Files:
- `crates/kernel/src/step_in/tests.rs`: `shelled_three_quarter_tube_round_trips` (kernel level, uses the shared `round_trip` check).
- `crates/engine/tests/step_merge_regressions.rs`: `shelled_thin_three_quarter_tube_keeps_its_volume` (the same design through the engine commands).

## Validation

All runs used `cargo test --profile ci` on 2 cores.

| Check | Commit | Result |
|---|---|---|
| `step_in::tests::shelled_three_quarter_tube_round_trips` | d8a088f^ (main before #1438) | fails: volume 2754.67 vs 2968.53 |
| same test | 843c548 (main) | passes |
| `--test step_merge_regressions` | 843c548 plus this PR's tests | passes |
| `cargo fmt --all -- --check` | 622f234 | clean |
| `cargo clippy --profile ci -p solidcraft-kernel -p solidcraft-engine --all-targets -- -D warnings` | 622f234 | 0 warnings |

The diff against main holds only these two test files. Neither test is filtered out of PR CI in `.config/nextest.toml`.

Open question: a reviewer believes main's edge-sample mean can put the seam inside a face whose rim is split unevenly, where `gap_middle` would not. I tried 270° and 300° tubes with a 3 x 3 x 5 mm box notch cut at the rim at 9 angles. All round-tripped within 1e-3 on main, and also on main before #1438, so these shapes likely do not reach that code. The concern is neither reproduced nor refuted.

Not run: the full `cargo xtask ci`, the robustness goldens, and the wasm build. This PR changes no non-test code.

## Screenshots of the behavior (when observable)

None. The PR changes no behavior. It only adds tests.

## Integration status

- The fork branch `fix/step-merged-face-surface` is at 622f234. It includes a merge of main at 843c548. The conflict in `crates/kernel/src/step_out.rs` was resolved by taking main's version.
- #1496 also adds a test to `crates/kernel/src/step_in/tests.rs`, in another place. A trial merge of the two branches has no conflict.
