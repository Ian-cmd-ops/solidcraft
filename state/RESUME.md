# RESUME: SolidCraft work

## Session Summary
- **2026-10-15** Setup: kit and run procedure built on the `ops` branch; daily scheduled run created.
  Open: PRs #1307, #1308, #1309, #1316, #1495, #1496, #1497, #1498 and issue #1494.

- **2026-10-15 (evening run, stopped by Ian)** #1497 merged with main 843c548 and pushed to the fork at 622f234; the diff is now the two seed 17 tests. Kit kits/2026-10-15 is ready and not posted. Not done: the uneven-split seam check (notched tube shelled; no shape failed so far, not reproduced), state/grind-state.md, state/seen.json, reports/2026-10-15.md. Seed 55 shrinks to 4 commands (see the kit issue). Handed to the local OpenCode machine.

## Active
- none

## Awaiting Review
Each open PR and what the owner last asked. All asks are answered as of 2026-10-15.

| PR | Branch | Owner's last ask | Status |
|---|---|---|---|
| #1307 mesh collision speedup | perf/mesh-collision | description; equivalence test in crates/ | done; reply posted |
| #1308 boolean property tests | tests/properties | description; what the saved seed is | done; he runs the heavy tests locally before merge |
| #1309 point-in-trim speedup | perf/tess-include | test that runs; numbers on current main | done; reply posted; CI green |
| #1316 shell saddle corners | fix/shell-saddle-corners | description and before/after | done; main merged at b6806b1, all_3 passed; he said he will merge |
| #1495 shell open face next to a concave edge | fix/shell-open-face-concave-edge | none yet | new |
| #1496 STEP export of shelled revolved bodies | fix/step-export-scaled-revolution | none yet | new |
| #1497 STEP export merged partial cylinder | fix/step-merged-face-surface | none yet | new |
| #1498 nightly property tests | ci/property-tests-nightly | none yet | new; stacked on #1308 |
| issue #1494 seed 6 cylinder-seam saddle | none | none yet | new |

## Task List
- **[should]** seed-baseline: which failing seeds the open PRs fix, score 15, Status: pending
- **[nice]** seeds-cut: boolean Cut no-result seeds, score 10, Status: pending
- **[nice]** seed-55, step-roundtrip, unit-tests, score 9 each, Status: pending
- **[nice]** seeds-offset, score 8, Status: pending
- **[nice]** seeds-union, seeds-lumps, score 6 each, Status: pending
- **[low]** seed-6-curved (issue #1494), score 4, Status: pending
