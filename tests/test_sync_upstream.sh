#!/usr/bin/env bash
# Tests for tools/sync_upstream.py. Uses a fake gh and a local bare repo; nothing reaches GitHub.
# Run: bash tests/test_sync_upstream.sh   (about 3 seconds)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="$HERE/tools/sync_upstream.py"
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; }

setup() {
  T="$(mktemp -d)"; mkdir -p "$T/bin"
  # Fake gh: two PRs (one open, one merged long ago) and one issue.
  cat > "$T/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "$FAKE_LOG"
case "$1 $2" in
  "api user") echo "${FAKE_LOGIN:-Ian-cmd-ops}";;
  "pr list") echo '[{"number":1316,"state":"OPEN","updatedAt":"2026-10-15T19:08:25Z"},{"number":900,"state":"MERGED","updatedAt":"2026-01-01T00:00:00Z"}]';;
  "issue list") echo '[{"number":1494,"state":"OPEN","updatedAt":"2026-10-15T18:57:24Z"}]';;
  "pr view") echo '{"number":1316,"title":"Fix/shell saddle corners","state":"OPEN","mergeable":"MERGEABLE","headRefName":"fix/shell-saddle-corners","headRefOid":"b36b1632","updatedAt":"2026-10-15T19:08:25Z","url":"u","comments":[{"author":{"login":"bherbruck"},"createdAt":"2026-10-15T17:00:00Z","body":"I will merge once the description is in."}],"reviews":[],"statusCheckRollup":[{"name":"ci","conclusion":"SUCCESS"},{"name":"lint","conclusion":"FAILURE"}]}';;
  "issue view") echo '{"number":1494,"title":"Seed 6","state":"OPEN","updatedAt":"2026-10-15T18:57:24Z","url":"u","comments":[]}';;
esac
EOF
  chmod +x "$T/bin/gh"
  export PATH="$T/bin:$PATH" FAKE_LOG="$T/log"
  unset FAKE_LOGIN
  git init -q --bare "$T/origin.git"
  git clone -q "$T/origin.git" "$T/kit" 2>/dev/null
  git -C "$T/kit" checkout -q -b ops
  mkdir -p "$T/kit/state" && echo '{}' > "$T/kit/state/seen.json"
  git -C "$T/kit" add -A && git -C "$T/kit" -c user.name=t -c user.email=t@t commit -q -m init
  git -C "$T/kit" push -q origin ops 2>/dev/null
  git -C "$T/kit" branch -q --set-upstream-to=origin/ops ops
}

# 1. Writes one file per item, a summary, commits as Ian-cmd-ops, and pushes.
setup
out="$(python3 "$TOOL" "$T/kit" 2>&1)"; rc=$?
[ $rc -eq 0 ] && ok "run exits 0" || { bad "run exits 0 (rc=$rc)"; echo "$out"; }
[ -f "$T/kit/state/upstream/1316.json" ] && [ -f "$T/kit/state/upstream/1494.json" ] && ok "one file per open item" || bad "one file per open item"
[ ! -f "$T/kit/state/upstream/900.json" ] && ok "old merged PR skipped" || bad "old merged PR skipped"
grep -q "I will merge once the description is in." "$T/kit/state/upstream/1316.json" && ok "owner comment kept word for word" || bad "owner comment kept word for word"
grep -q "1316.*OPEN.*MERGEABLE.*1 failing" "$T/kit/state/upstream/SUMMARY.md" && ok "summary line has state, mergeable, failing checks" || bad "summary line"
grep -q "bherbruck 2026-10-15T17:00:00Z" "$T/kit/state/upstream/SUMMARY.md" && ok "summary names the last owner comment" || bad "summary last owner comment"
author="$(git -C "$T/origin.git" log -1 --format='%an <%ae>' ops)"
[ "$author" = "Ian-cmd-ops <78785932+Ian-cmd-ops@users.noreply.github.com>" ] && ok "pushed commit authored as Ian-cmd-ops" || bad "author was: $author"
git -C "$T/origin.git" log -1 --format=%B ops | grep -q "claude.ai/code/session" && bad "no session link in commit" || ok "no session link in commit"

# 2. A second run with nothing new makes no commit.
before="$(git -C "$T/origin.git" rev-parse ops)"
python3 "$TOOL" "$T/kit" >/dev/null 2>&1
after="$(git -C "$T/origin.git" rev-parse ops)"
[ "$before" = "$after" ] && ok "no change, no commit" || bad "no change, no commit"

# 3. Someone else pushed to ops meanwhile: the run pulls first and still pushes, without force.
setup
git clone -q -b ops "$T/origin.git" "$T/other" 2>/dev/null
echo x > "$T/other/state/x.txt"; git -C "$T/other" add -A; git -C "$T/other" -c user.name=t -c user.email=t@t commit -q -m other; git -C "$T/other" push -q origin ops
python3 "$TOOL" "$T/kit" >/dev/null 2>&1; rc=$?
git -C "$T/origin.git" log --format=%s ops | grep -q "^other$" && [ $rc -eq 0 ] && [ -n "$(git -C "$T/origin.git" ls-tree -r --name-only ops | grep upstream/1316.json)" ] && ok "concurrent push kept, sync still landed" || bad "concurrent push kept, sync still landed (rc=$rc)"

# 4. Wrong gh account: stop before writing anything.
setup
FAKE_LOGIN=someone-else python3 "$TOOL" "$T/kit" >/dev/null 2>&1; rc=$?
[ $rc -ne 0 ] && [ ! -d "$T/kit/state/upstream" ] && ok "wrong account refused" || bad "wrong account refused"

# 5. --no-push writes files but does not commit or push.
setup
python3 "$TOOL" "$T/kit" --no-push >/dev/null 2>&1; rc=$?
[ $rc -eq 0 ] && [ -f "$T/kit/state/upstream/SUMMARY.md" ] && [ "$(git -C "$T/origin.git" log --oneline ops | wc -l)" = 1 ] && ok "--no-push writes only" || bad "--no-push writes only"

echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
