#!/usr/bin/env python3
"""Record what the owner said on Ian's SolidCraft PRs and issues, word for word.

The cloud run cannot read comments on bherbruck/solidcraft (the API answers 403).
This job runs where `gh` is logged in as Ian-cmd-ops (CT 115), writes the exact
comments and CI state into the kit, and pushes the ops branch. It only reads
GitHub; it never posts there.

Writes into <kit>/state/upstream/:
  <number>.json   gh's JSON for each open item, or any item updated in the last 14 days
  SUMMARY.md      one line per item: state, mergeable, failing checks, last owner comment

Usage: sync_upstream.py <kit-dir> [--no-push]
Env:   REPO (default bherbruck/solidcraft), AUTHOR and EXPECT_LOGIN (default Ian-cmd-ops),
       OWNER (default bherbruck), RECENT_DAYS (default 14)
Run time: about 2 seconds per item, plus one pull and one push. One line per step.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = os.environ.get("REPO", "bherbruck/solidcraft")
AUTHOR = os.environ.get("AUTHOR", "Ian-cmd-ops")
LOGIN = os.environ.get("EXPECT_LOGIN", "Ian-cmd-ops")
OWNER = os.environ.get("OWNER", "bherbruck")
RECENT = dt.timedelta(days=int(os.environ.get("RECENT_DAYS", "14")))
IDENT = ["-c", "user.name=Ian-cmd-ops", "-c", "user.email=78785932+Ian-cmd-ops@users.noreply.github.com"]
PR_FIELDS = "number,title,state,mergedAt,mergeable,headRefName,headRefOid,updatedAt,url,comments,reviews,statusCheckRollup"
ISSUE_FIELDS = "number,title,state,updatedAt,url,comments"


def say(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def die(msg):
    print(f"STOP: {msg}", file=sys.stderr, flush=True)
    sys.exit(2)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"{' '.join(cmd[:4])} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def git(kit, *args):
    return run(["git", *IDENT, *args], cwd=kit)


def wanted(item, now):
    if item["state"] == "OPEN":
        return True
    upd = dt.datetime.fromisoformat(item["updatedAt"].replace("Z", "+00:00"))
    return now - upd <= RECENT


def checks(rollup):
    bad = [c for c in rollup or [] if (c.get("conclusion") or c.get("state") or "").upper()
           in {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}]
    pend = [c for c in rollup or [] if (c.get("status") or "").upper() in {"QUEUED", "IN_PROGRESS", "PENDING"}]
    if not rollup:
        return "no checks"
    if bad:
        return f"{len(bad)} failing ({', '.join(c.get('name', '?') for c in bad)})"
    if pend:
        return f"{len(pend)} pending"
    return "all passing"


def last_owner(d):
    times = [(c["createdAt"], "comment") for c in d.get("comments", []) if c.get("author", {}).get("login") == OWNER]
    times += [(r.get("submittedAt", ""), "review") for r in d.get("reviews", []) if r.get("author", {}).get("login") == OWNER]
    times = [t for t in times if t[0]]
    return f"{OWNER} {max(times)[0]}" if times else "none"


def main():
    if len(sys.argv) < 2:
        die("usage: sync_upstream.py <kit-dir> [--no-push]")
    kit = Path(sys.argv[1]).resolve()
    push = "--no-push" not in sys.argv[2:]

    who = run(["gh", "api", "user", "--jq", ".login"])
    if who != LOGIN:
        die(f"gh is logged in as '{who}', not {LOGIN}")

    if push:
        say("Pulling the ops branch")
        git(kit, "pull", "--rebase", "-q")

    now = dt.datetime.now(dt.timezone.utc)
    items = []
    for kind in ("pr", "issue"):
        listed = json.loads(run(["gh", kind, "list", "-R", REPO, "--author", AUTHOR, "--state", "all",
                                 "--limit", "100", "--json", "number,state,updatedAt"]))
        items += [(kind, i["number"]) for i in listed if wanted(i, now)]
    say(f"{len(items)} items to record from {REPO}")

    out = kit / "state" / "upstream"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind, n in sorted(items, key=lambda x: x[1]):
        say(f"Reading {kind} #{n}")
        fields = PR_FIELDS if kind == "pr" else ISSUE_FIELDS
        d = json.loads(run(["gh", kind, "view", str(n), "-R", REPO, "--json", fields]))
        (out / f"{n}.json").write_text(json.dumps(d, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        merge = d.get("mergeable", "-") if kind == "pr" else "-"
        ck = checks(d.get("statusCheckRollup")) if kind == "pr" else "-"
        rows.append(f"| {n} | {kind} | {d['state']} | {merge} | {ck} | {len(d.get('comments', []))} | {last_owner(d)} | {d['title']} |")

    summary = ["# Upstream state (written by tools/sync_upstream.py; exact comments are in <number>.json)", "",
               "| # | Kind | State | Mergeable | Checks | Comments | Last owner comment | Title |",
               "|---|---|---|---|---|---|---|---|", *rows, ""]
    (out / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")

    if not push:
        say("Wrote files; --no-push, so no commit")
        return
    git(kit, "add", "state/upstream")
    if not run(["git", "status", "--porcelain", "state/upstream"], cwd=kit):
        say("Nothing changed upstream; no commit")
        return
    git(kit, "commit", "-q", "-m", f"state: upstream comments and CI as of {now:%Y-%m-%d %H:%M}Z",
        "-m", "Written by tools/sync_upstream.py from gh. Read-only on GitHub.")
    for attempt in (1, 2):
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD:ops"], cwd=kit, capture_output=True, text=True)
        if r.returncode == 0:
            say("Pushed ops")
            return
        say(f"Push rejected (attempt {attempt}); pulling and retrying")
        git(kit, "pull", "--rebase", "-q")
    die("push failed twice; the commit stays local and the next run will push it")


if __name__ == "__main__":
    main()
