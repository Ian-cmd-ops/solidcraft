# Daily run procedure

One scheduled run, start to finish. It is opskit's `grind` loop (sync, triage, rank,
work one item, test, ship) adapted to a repo where we cannot post. Read
`standards.md`, `repo-facts.md` and `lessons.md` before step 1.

**Time budget:** about 3 hours. Start no new item after 2 hours 15 minutes.
Spend the rest finishing, checking, and writing the kit and report.

## Hard rules

- **Never post to `bherbruck/solidcraft`.** No PRs, issues, comments, edits or reviews. Ian posts the kit.
- **Never force-push** a branch that has an open PR, and never rewrite the `ops` branch history.
- **Never delete** a branch, a comment or a file Ian made.
- **Never touch the homelab**, CT 115 or any device. This work is code only.
- **Never put a secret, the owner's full name, or a session link** in any file, commit or kit.
- **Two failed attempts at the same fix: stop that item.** Record what you found and move on.
- **Never claim what you did not run.** See `standards.md` section 4.

## Step 1. Set up (about 15 minutes)

1. Attach the fork with `add_repo` (`owner: Ian-cmd-ops`, `repo: solidcraft`, `access: push`).
2. Clone the fork shallow. Add upstream as a second remote and fetch its `main` anonymously.
3. Check out the `ops` branch into its own worktree. All state and kits live there.
4. Clone `https://github.com/CascadeSTEAM/opskit` read-only. Read
   `.opencode/skills/grind/SKILL.md`, `.opencode/skills/dogfood-cycle/SKILL.md` and
   `agents/code-reviewer.md`. Follow their method where this file is silent. Never push to opskit.
5. Read `state/RESUME.md`, `state/grind-state.md` and `state/seen.json`.
6. Start the cold build in the background now (`repo-facts.md`), so it is ready when you need it.

## Step 2. Observe (about 15 minutes)

1. Record upstream `main`'s SHA and what changed since the last run (`git log --oneline <last>..upstream/main`).
2. Read `state/upstream/SUMMARY.md` and the `<number>.json` files. CT 115 writes them twice a day
   with `gh`, so they hold the owner's exact comments, mergeable state and failing checks.
   Check the commit time of `state/upstream/`. If it is older than 24 hours, say so in the report.
3. Also query the search API (`lessons.md`) and compare with `state/seen.json`. It catches
   activity newer than the last sync. For such an item, read its PR page as a hint only.
   Quote nothing longer than one sentence in the report; summarise the rest.
4. For each open PR branch, trial-merge `upstream/main`. Note conflicts.
5. Note merged or closed items. A merged fix may change the failing-seed list.

## Step 3. Triage and rank (about 10 minutes)

Build the queue in `state/grind-state.md`. Score each item: priority (1 to 5) times speed (1 to 5).
Use this order of priority, from highest:

1. **Owner feedback** on an open PR: anything he asked for and did not get.
2. **A conflict** on an open PR.
3. **A failing robustness seed** that has a likely fix (`repo-facts.md` table).
4. **Missing unit tests** around code the open PRs or recent upstream commits touch.
5. **The STEP round trip** for seeds 40 to 95: export, import, compare volume and area, with a time limit per seed.

Pick the top item. Pick a second only if it fits the time left.
An item that needs Ian's or the owner's decision is not work for this run. Put it in the report as a question.

## Step 4. Work one item (most of the run)

Follow `standards.md`. In outline:

1. Make a worktree on a new branch from `upstream/main` (or the PR's own branch for PR feedback).
2. Reproduce. Shrink. Write the failing test. Commit it.
3. Fix. Run the new test, the nearby tests, and the goldens parts the change can affect. Commit.
4. Run `cargo fmt --all -- --check` and clippy on the touched crates.
5. Ask a fresh subagent to review, as in `standards.md` section 6. Fix what it confirms.
6. Push the branch to the fork. Pushing to the fork is allowed; it posts nothing upstream.

For a conflict: merge `upstream/main`, resolve, run the part of the goldens or the tests that
cover the conflict, then push the merge commit. Never rebase a branch with an open PR.

## Step 5. Write the post kit (about 15 minutes)

Make `kits/<YYYY-MM-DD>/` on the `ops` branch with `repo`, `actions.tsv` and one `.md` per body.
The format is in `tools/post_kit.py`. Then:

- Use `{{VAR}}` placeholders for numbers that do not exist yet. Never write `#NNNN`.
- Fill PR bodies with every template section, measured values and "Not run".
- Run `tools/post_kit.sh kits/<date> --dry-run`. It must pass.
- If there is nothing to post, make no kit.

## Step 6. Save state and report (about 10 minutes)

1. Rewrite `state/grind-state.md` (queue, active item, phase) and update `state/seen.json`.
2. Append one dated line to `state/RESUME.md` "Session Summary", and rewrite its other sections.
3. Write `reports/<YYYY-MM-DD>.md`: what changed upstream, what this run did (with commits),
   what is in the kit, questions for Ian, and the next item. Label every claim as in `standards.md`.
4. Commit each of these as its own commit on `ops`, and push `ops`.
5. Send Ian a short message: the headline, the one command to post the kit if there is one,
   and any question. Keep it under 15 lines.

## Ian's side

**Laptop:**
```bash
cd ~/solidcraft-kit && git pull
tools/post_kit.sh kits/<date> --dry-run   # check first
tools/post_kit.sh kits/<date>             # post
```

The first time: `git clone -b ops --single-branch https://github.com/Ian-cmd-ops/solidcraft ~/solidcraft-kit`.
