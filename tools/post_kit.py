#!/usr/bin/env python3
"""Post one run's kit to GitHub with YOUR gh login.

A kit is a folder with:
  repo          one line, e.g. bherbruck/solidcraft (default if missing)
  actions.tsv   one action per line, tab-separated, in posting order
  *.md          the bodies the actions name

Action lines (fields are separated by a TAB):
  issue          VAR  title  body.md            open an issue, remember its number as VAR
  pr             VAR  head-branch  base  title  body.md
                                                open a PR from <your login>:head-branch
  edit           TARGET  body.md                replace a PR description
  comment        TARGET  body.md                comment on a PR
  issue-edit     TARGET  body.md                replace an issue description
  issue-comment  TARGET  body.md                comment on an issue
TARGET is a number (1316) or a placeholder ({{PR_A}}). Bodies and titles may hold
{{VAR}} placeholders; each is filled with the number once that item exists. Two
items that name each other work: the first is opened with a stub body, and its
real body is set as soon as the second exists.

Before posting anything, the tool refuses a kit with an unknown placeholder, a
leftover #NNNN, a session link or a generated-by footer, and it checks that gh
is logged in as the expected account. Numbers and finished actions are kept in
<kit>/state.json, so a re-run after a failure posts nothing twice.

Usage: post_kit.py <kit-dir> [--dry-run]
Env:   EXPECT_LOGIN (default Ian-cmd-ops)
Run time: about 2 to 3 seconds per action. One line is printed per action.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PH = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
JUNK = [
    (re.compile(r"#NNNN"), "a leftover #NNNN"),
    (re.compile(r"claude\.ai/code/session"), "a session link"),
    (re.compile(r"Generated with \[Claude"), "a generated-by footer"),
]
STUB = "Description follows in a moment.\n"
CREATE = {"issue", "pr"}
FIELDS = {"issue": 4, "pr": 6, "edit": 3, "comment": 3, "issue-edit": 3, "issue-comment": 3}


def say(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def die(msg, code=2):
    print(f"STOP: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()}", 1)
    return r.stdout.strip()


def parse(kit):
    path = kit / "actions.tsv"
    if not path.is_file():
        die(f"{path} is missing")
    acts = []
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        f = raw.split("\t")
        kind = f[0]
        if kind not in FIELDS or len(f) != FIELDS[kind]:
            die(f"actions.tsv line {no}: expected {FIELDS.get(kind, '?')} tab-separated fields for '{kind}'")
        a = {"no": no, "kind": kind}
        if kind == "issue":
            a.update(var=f[1], title=f[2], body=f[3])
        elif kind == "pr":
            a.update(var=f[1], head=f[2], base=f[3], title=f[4], body=f[5])
        else:
            a.update(target=f[1], body=f[2])
        bp = kit / a["body"]
        if not bp.is_file():
            die(f"actions.tsv line {no}: body file {a['body']} is missing")
        a["text"] = bp.read_text(encoding="utf-8")
        acts.append(a)
    return acts


def validate(acts):
    made, order = set(), {}
    for i, a in enumerate(acts):
        if a["kind"] in CREATE:
            if a["var"] in made:
                die(f"line {a['no']}: {a['var']} is created twice")
            made.add(a["var"])
            order[a["var"]] = i
    for i, a in enumerate(acts):
        texts = [a["text"], a.get("title", ""), a.get("target", "")]
        for t in texts:
            for v in PH.findall(t):
                if v not in made:
                    die(f"line {a['no']}: unknown placeholder {{{{{v}}}}}")
            for rx, what in JUNK:
                if rx.search(t):
                    die(f"line {a['no']} ({a['body']}): holds {what}")
        for v in PH.findall(a.get("title", "")):
            if order[v] >= i:
                die(f"line {a['no']}: title names {{{{{v}}}}}, which is not opened before it")
        if "target" in a and not PH.fullmatch(a["target"]) and not a["target"].isdigit():
            die(f"line {a['no']}: target must be a number or one placeholder")


def fill(text, nums):
    return PH.sub(lambda m: f"#{nums[m.group(1)]}" if m.group(1) in nums else m.group(0), text)


def main():
    if len(sys.argv) < 2:
        die(__doc__.strip().splitlines()[0] + "\nUsage: post_kit.py <kit-dir> [--dry-run]")
    kit = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv[2:]
    repo = (kit / "repo").read_text().strip() if (kit / "repo").is_file() else "bherbruck/solidcraft"
    login = os.environ.get("EXPECT_LOGIN", "Ian-cmd-ops")
    acts = parse(kit)
    validate(acts)
    say(f"Kit {kit.name}: {len(acts)} actions for {repo}. Checks passed.")

    if dry:
        for a in acts:
            say(f"would {a['kind']} {a.get('var') or a.get('target')} from {a['body']}")
        return

    who = gh("api", "user", "--jq", ".login")
    if who != login:
        die(f"gh is logged in as '{who}', not {login}")

    sf = kit / "state.json"
    st = json.loads(sf.read_text()) if sf.is_file() else {"nums": {}, "stub": [], "done": []}
    nums = st["nums"]
    out = kit / "out"
    out.mkdir(exist_ok=True)

    def save():
        sf.write_text(json.dumps(st, indent=1))

    def body_file(a, text):
        p = out / f"{a['no']}-{Path(a['body']).name}"
        p.write_text(text, encoding="utf-8")
        return str(p)

    def ready(text):
        return all(v in nums for v in PH.findall(text))

    # Pass 1: open issues and PRs in order. A body that names an item not open yet goes up as a stub.
    for a in acts:
        if a["kind"] not in CREATE:
            continue
        if a["var"] in nums:
            say(f"{a['var']} already open as #{nums[a['var']]} (skipped)")
            continue
        text = fill(a["text"], nums) if ready(a["text"]) else STUB
        title = fill(a["title"], nums)
        if a["kind"] == "issue":
            say(f"Opening issue: {title}")
            url = gh("issue", "create", "-R", repo, "--title", title, "--body-file", body_file(a, text))
        else:
            say(f"Opening PR from {login}:{a['head']}: {title}")
            url = gh("pr", "create", "-R", repo, "--base", a["base"], "--head", f"{login}:{a['head']}",
                     "--title", title, "--body-file", body_file(a, text))
        nums[a["var"]] = int(re.search(r"(\d+)\s*$", url).group(1))
        if text == STUB:
            st["stub"].append(a["var"])
        save()
        say(f"  {a['var']} -> #{nums[a['var']]}")

    # Pass 2: set the real body on anything opened with a stub.
    for a in acts:
        if a["kind"] in CREATE and a["var"] in st["stub"]:
            noun = "issue" if a["kind"] == "issue" else "pr"
            say(f"Setting the description of #{nums[a['var']]}")
            gh(noun, "edit", str(nums[a["var"]]), "-R", repo, "--body-file", body_file(a, fill(a["text"], nums)))
            st["stub"].remove(a["var"])
            save()

    # Pass 3: edits and comments, in order.
    for a in acts:
        if a["kind"] in CREATE:
            continue
        key = f"{a['no']}:{a['kind']}:{a['target']}:{a['body']}"
        if key in st["done"]:
            say(f"{a['kind']} on {a['target']} already done (skipped)")
            continue
        target = fill(a["target"], nums).lstrip("#")
        noun, verb = ("issue", a["kind"].split("-")[1]) if a["kind"].startswith("issue-") else ("pr", a["kind"])
        say(f"{verb.capitalize()} on {noun} #{target}")
        gh(noun, verb, target, "-R", repo, "--body-file", body_file(a, fill(a["text"], nums)))
        st["done"].append(key)
        save()

    say("Done.")
    for v, n in nums.items():
        print(f"  {v} = #{n}")
    print(f"  {len(st['done'])} edits/comments posted")


if __name__ == "__main__":
    main()
