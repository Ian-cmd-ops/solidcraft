#!/usr/bin/env bash
# Checks the OpsKit member files. opskit's own `check` validates pack.yml but does
# not parse agent or skill frontmatter, and a bad header breaks `member sync-mount`.
# Run: bash tests/test_member.sh [path-to-opskit-checkout]   (about 1 second)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; }

out="$(cd "$ROOT" && python3 - <<'EOF'
import sys, yaml, pathlib
root = pathlib.Path(".")
pack = yaml.safe_load(open(".opskit/pack.yml"))
files = [(a["path"], None) for a in pack.get("agents", [])]
files += [(s["path"] + "/SKILL.md", ["name", "description", "mode", "triggers"]) for s in pack.get("skills", [])]
for path, need in files:
    try:
        text = open(path, encoding="utf-8").read()
        fm = yaml.safe_load(text.split("---")[1])
        assert isinstance(fm, dict), "frontmatter is not a mapping"
        missing = [k for k in (need or ["description", "mode"]) if k not in fm]
        assert not missing, f"missing {missing}"
        if need:
            lines = len(text.splitlines())
            assert lines <= 60, f"{lines} lines, opskit's limit is 60"
            want = "solidcraft-" + pathlib.Path(path).parent.name
            assert fm["name"] == want, f"name {fm['name']!r} but it renders as {want!r}"
        print(f"ok {path}")
    except Exception as e:
        print(f"FAIL {path}: {e}")
for d in pack.get("docs", []):
    print(("ok " if (root / d).is_file() else "FAIL missing ") + d)
EOF
)"
while IFS= read -r line; do
  case "$line" in ok*) ok "${line#ok }";; *) bad "${line#FAIL }";; esac
done <<<"$out"

dash="$(cd "$ROOT" && python3 -c '
import pathlib
hits = [str(p) for p in pathlib.Path(".").rglob("*") if p.is_file() and ".git" not in p.parts
        and p.suffix in {".md", ".yml", ".py", ".sh", ".tsv", ".json"}
        and chr(0x2014) in p.read_text(encoding="utf-8", errors="ignore")]
print(" ".join(hits))')"
[ -z "$dash" ] && ok "no em dashes" || bad "em dash in: $dash"

OPSKIT="${1:-}"
if [ -n "$OPSKIT" ]; then
  python3 "$OPSKIT/bin/opskit-aware.py" check "$ROOT" | grep -q '"ok": true' && ok "opskit-aware check" || bad "opskit-aware check"
fi

echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
