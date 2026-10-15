# Lessons learned

Things that went wrong or cost time before. Add a line when a run learns something new.

## Git

- **`goldens.json` conflicts in the `notes` list almost every time main moves.**
  Keep main's notes, add this PR's note after them, and check the JSON parses.
  Then run the goldens part that holds the PR's seeds, so the merge claim is true.
- **Trial-merge before you claim "merges cleanly".** `git merge --no-commit upstream/main`, inspect, then commit or abort.
- **A shallow single-branch clone hides other branches.** Fetch with an explicit refspec:
  `git fetch origin +refs/heads/<b>:refs/remotes/origin/<b>`.
- **Name a local branch the same as its remote branch.** A stop hook reports "no remote branch" otherwise.
- **After switching worktrees on one target dir, touch the sources** (`find crates vendor apps xtask -name '*.rs' -print0 | xargs -0 touch`)
  or cargo may reuse stale objects.
- **A local triage harness file** (for example `crates/engine/tests/zz_triage.rs`) must never be committed. Check `git status` before each commit.

## GitHub access from the cloud

- The cloud session cannot use `gh` or the REST API on `bherbruck/solidcraft`. It returns 403.
- `git fetch https://github.com/bherbruck/solidcraft main` works anonymously.
- The search API works through WebFetch:
  `https://api.github.com/search/issues?q=repo:bherbruck/solidcraft+author:Ian-cmd-ops`
  gives state, comment counts and `updated_at`.
- The PR page `https://github.com/bherbruck/solidcraft/pull/<n>` works through WebFetch for reading comments,
  but it can be stale or summarised. Treat it as a hint. Ask Ian to paste `gh pr view <n> -R bherbruck/solidcraft --comments` when the exact words matter.
- The fork accepts pushes after `add_repo` with `access: push`.

## Posting

- **Posting upstream is Ian's step.** A run writes a kit; Ian runs `tools/post_kit.sh`.
- **Two items that name each other** need one stub body first. `post_kit.sh` handles it; never hand-roll it.
- **Do not post a claim before the check finishes.** On 2026-10-15 a comment said seed 83 was checked
  about 15 minutes before the check passed. It passed, but it could have been wrong in public.
- **Edits to a PR description send no notification.** After finishing what the owner asked, add a one-line comment saying so.
- **Delete nothing upstream.** If a duplicate or stale comment exists, list the delete command for Ian.

## Time on 2 cores

- A cold build for engine tests takes 7 to 10 minutes. One goldens part takes about 11 minutes.
- Parts vary: `all_3` took 11 minutes on 2026-10-15, and one part once took 49 minutes.
  Budget up to 2 hours for all four. A kernel change can move any seed, so run all four
  before claiming "goldens unchanged". After a notes-only merge, the part holding the PR's seeds is enough.
- Put a time limit on each seed in a loop (`timeout`), so one slow seed cannot stall the run.
- Print a progress line per seed or per step. Never run silent for more than a few minutes.

## Kit and opskit member

- **A colon in a YAML header value breaks the whole file.** Replacing an em dash with ": " in an
  agent description made `opskit member sync-mount` crash. `opskit-aware.py check` did not catch it.
  Run `bash tests/test_member.sh` after any change to `agents/`, `.opencode/` or `.opskit/`.
- **opskit prefixes member renders with the member name.** A file `agents/dev.md` in member
  `solidcraft` renders as `@solidcraft-dev`. Name files so the result reads well.
