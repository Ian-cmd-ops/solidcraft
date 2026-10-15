# grind-state (rewritten from scratch every run; see opskit .opencode/skills/grind)

## Active
- **seeds-cut** (boolean Cut no result: seeds 2, 5, 15, 18, 61, 95). Phase: triage. Claimed 2026-10-15 14:40 PT
  by an interactive cloud session. Other workers and the scheduled run: skip this item until it is
  released here. Branch, when one exists: fix/boolean-cut-seeds.

## Queue
Score = priority x speed. Owner feedback and conflicts found in Step 2 jump to the top.

| Key | Type | What | P | S | Score | Status |
|---|---|---|---|---|---|---|
| seed-baseline | local | Run all 4 goldens parts on `all-fixes` merged with upstream main, to learn which failing seeds the open PRs already fix | 5 | 3 | 15 | pending |
| seeds-cut | local | Triage "boolean Cut: no result" seeds 2, 5, 15, 18, 61, 95: shrink, group by cause, fix the commonest | 5 | 2 | 10 | claimed |
| seed-55 | local | Seed 55 "invalid Body": shrink and find which validity check fails | 3 | 3 | 9 | pending |
| step-roundtrip | local | STEP round trip for seeds 40 to 95 with a per-seed time limit; earlier list on hold: 53, 69, 83, 85, 86 | 3 | 3 | 9 | pending |
| unit-tests | local | Exact-value regression tests around boolean Cut with touching and coincident faces | 3 | 3 | 9 | pending |
| seeds-offset | local | Offset corner seeds 40, 78, 86: check which are planar saddles that #1316 already covers | 4 | 2 | 8 | pending |
| seeds-union | local | "Union: implausible result volume" seeds 45, 63 | 3 | 2 | 6 | pending |
| seeds-lumps | local | "lumps: shell boundaries intersect or touch" seeds 9, 70 | 3 | 2 | 6 | pending |
| seed-6-curved | issue #1494 | Saddle on a cylinder seam (also 38, 69, 73). Needs a curved split_corner; large | 4 | 1 | 4 | pending |

## Completed
- none yet

## Notes
- All PRs below wait on the owner. Watch for new comments; do not re-post what is already there.
