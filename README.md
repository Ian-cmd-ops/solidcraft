# solidcraft-kit

The working kit for Ian's SolidCraft contributions. It lives on the `ops` branch of
`Ian-cmd-ops/solidcraft`, apart from the code branches, so it never reaches an upstream PR.

## What is here

| Path | What it is |
|---|---|
| `docs/standards.md` | How every change is made: test first, atomic commits, labelled claims |
| `docs/repo-facts.md` | Commands, 2-core timings, the owner's review asks, failing seeds |
| `docs/lessons.md` | Pitfalls from earlier rounds |
| `docs/run-procedure.md` | What the daily scheduled run does, step by step |
| `tools/post_kit.sh` | Posts a run's kit upstream with your `gh` login |
| `tests/` | Tests for the tools (`bash tests/test_post_kit.sh`) |
| `state/` | Where the work stands: `RESUME.md`, `grind-state.md`, `seen.json` |
| `state/upstream/` | The owner's exact comments and CI state, written by CT 115 twice a day |
| `tools/sync_upstream.py`, `tools/systemd/`, `tools/ansible/` | The CT 115 sync job, its timer, and the playbook that installs it |
| `kits/<date>/` | What a run prepared for you to post |
| `reports/<date>.md` | What a run did and found |
| `agents/`, `.opencode/skills/`, `.opskit/` | The OpsKit member: `@solidcraft-dev` and the `solidcraft-workflow` skill |

## Post a run's kit

**Laptop:**
```bash
git clone -b ops --single-branch https://github.com/Ian-cmd-ops/solidcraft ~/solidcraft-kit   # first time only
cd ~/solidcraft-kit && git pull
tools/post_kit.sh kits/<date> --dry-run
tools/post_kit.sh kits/<date>
```

The tool stops before posting anything if a body holds a leftover placeholder, `#NNNN`,
a session link or a generated-by footer, or if `gh` is logged in as another account.
A re-run after a failure posts nothing twice.

## Mount in opskit

This lets OpenCode in CT 115 use `@solidcraft-dev` and the `solidcraft-workflow` skill.

**CT 115 (opskit), as user ian:**
```bash
git clone -b ops --single-branch https://github.com/Ian-cmd-ops/solidcraft ~/Projects/solidcraft-kit
cd ~/Projects/opskit
python3 bin/opskit-aware.py check ~/Projects/solidcraft-kit
echo "solidcraft /home/ian/Projects/solidcraft-kit" >> .project-remotes
bin/opskit member sync-mount
bin/opskit member status
```

Then restart the OpenCode session. `.project-remotes` is gitignored, so this changes
no tracked file in opskit. To pick up a run's changes later, run `git pull` in
`~/Projects/solidcraft-kit`.

Building SolidCraft inside CT 115 needs a Rust toolchain and a SolidCraft checkout there.
The scheduled run does not need either; it works in the cloud.

## The CT 115 sync job

The cloud run cannot read comments on tangency-labs/solidcraft. CT 115 can, because `gh` there is
logged in as Ian-cmd-ops. `tools/sync_upstream.py` writes the owner's exact comments and the CI
state to `state/upstream/` and pushes `ops`. It only reads GitHub. It runs at 08:20 and 18:20 Pacific.

**CT 115 (opskit), as ian, once:**
```bash
gh auth setup-git
cd ~/Projects/solidcraft-kit && git pull
python3 tools/sync_upstream.py ~/Projects/solidcraft-kit --no-push
cat state/upstream/SUMMARY.md
```

The `--no-push` run writes the files without a commit, so you can look first.
Install the timer with the playbook: copy `tools/ansible/solidcraft-sync.yml` into
`~/Projects/opskit/environments/<env>/playbooks/` and run it with `bin/ap.sh`.
