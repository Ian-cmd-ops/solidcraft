# Standards for SolidCraft work

These rules apply to every change a run or an OpenCode session makes. They adapt
opskit's development cycle (AGENTS.md "Task-Level Execution Cycle", the `grind`
and `dogfood-cycle` skills, the `@code-reviewer` agent) to a repo we do not own.

## 1. Prove the bug before you fix it

1. Reproduce the failure on current upstream `main`. Record the exact error and values.
2. Shrink it to the smallest case (`fuzz::minimise`, or by hand).
3. Write a test that fails on `main` for that reason. Run it and see it fail.
4. Commit the test alone. This is the first commit on the branch.
5. Fix the code. Run the test and see it pass.
6. Commit the fix alone.

A test you never saw fail proves nothing. Say in the PR that it fails without the change.

## 2. Make each commit atomic

- One logical change per commit: a test, a fix, a goldens re-record, a doc.
- Each commit builds and passes its own tests. Never commit a broken state to "fix later".
- Never mix formatting churn with a behaviour change.
- Subject line: `Area: what changed`, in plain words, as upstream does
  (for example `Shell: a saddle corner splits in two`). Use `test:` for test-only commits.
- Body: why, and the evidence (values before and after, which tests ran).
- Footer: only the `Co-Authored-By` line from `repo-facts.md`. No session link.

## 3. Write tests that pin behaviour

- Prefer exact values (closed-form volume, area, face count) over tolerance bands.
- Check `Body::validity`, body count and shell count, not only that a call returned `Ok`.
- Property tests (proptest) suit invariants: inclusion-exclusion, commutativity, scale and translation invariance.
- An equivalence test (old code against new) must have a mutation check:
  break the new code on purpose, and show the test fails. Say so in the PR.
- A test must run in CI. If it cannot (heavy, vendored), say exactly where and when it runs.

## 4. Check before you claim

Every statement in a PR, comment or report is one of three kinds. Label it.

- **I ran this and saw X.** Give the command and the commit.
- **Reading the code, I believe Y.** Say it is unverified.
- **I did not run this.** List it under "Not run".

Never post a claim the run has not verified. If a check is still running, wait or leave the claim out.

## 5. Keep PRs small and reviewable

- One topic per PR. A CI change, a new dependency and a fix are three PRs.
- Branch from current `upstream/main`: `fix/<topic>`, `perf/<topic>`, `tests/<topic>`, `ci/<topic>`.
- Fill every template section. Use the owner's own words for what he asked.
- If two PRs touch the same lines, say so under Integration status.

## 6. Get an independent review before posting

Before a PR or a claim goes into a post kit, a separate agent that has not seen the work
reviews it, in the style of opskit's `@code-reviewer`:

- It reads the diff and the description, and runs the stated tests itself.
- It reports each finding as "ran and saw" or "believe". A refuted finding is a good result.
- It never edits the branch. Fix findings yourself, then ask again.

## 7. Write for the reader

- Simplified Technical English: short sentences, active voice, one idea per sentence.
- No em dashes. No filler. No praise of the change.
- Label every command block with the host it runs on when more than one host is involved.
