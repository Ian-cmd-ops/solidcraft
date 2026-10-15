#!/usr/bin/env bash
# Tests for tools/post_kit.sh. Runs against a fake `gh`; nothing reaches GitHub.
# Run: bash tests/test_post_kit.sh   (about 2 seconds)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="$HERE/tools/post_kit.sh"
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; }

# A fake gh: logs every call, hands out numbers from 2000 up, answers `api user`.
setup() {
  T="$(mktemp -d)"; mkdir -p "$T/bin" "$T/kit"
  cat > "$T/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "$FAKE_LOG"
for a in "$@"; do
  if [ -f "$a" ] && [ "$prev" = "--body-file" ]; then echo "--- body of $a" >> "$FAKE_LOG"; cat "$a" >> "$FAKE_LOG"; fi
  prev="$a"
done
case "$1 $2" in
  "api user") echo "${FAKE_LOGIN:-Ian-cmd-ops}";;
  "issue create"|"pr create")
    n=$(cat "$FAKE_N" 2>/dev/null || echo 2000); n=$((n+1)); echo $n > "$FAKE_N"
    echo "https://github.com/o/r/pull/$n";;
esac
EOF
  chmod +x "$T/bin/gh"
  export PATH="$T/bin:$PATH" FAKE_LOG="$T/log" FAKE_N="$T/n"
  unset FAKE_LOGIN
  printf 'o/r\n' > "$T/kit/repo"
}

# 1. Creates in order and fills each number into later bodies, titles and targets.
setup
printf 'Seed 6 shell bug\n' > "$T/kit/issue.md"
printf 'Fixes part of {{ISSUE}}. Pairs with {{PR_B}}.\n' > "$T/kit/a.md"
printf 'Pairs with {{PR_A}}.\n' > "$T/kit/b.md"
printf 'New text; see {{ISSUE}} and {{PR_A}}.\n' > "$T/kit/old.md"
printf 'Thanks, done.\n' > "$T/kit/c.md"
printf '# comment line\nissue\tISSUE\tShell refuses a corner\tissue.md\npr\tPR_A\tfeat/a\tmain\tFix A\ta.md\npr\tPR_B\tfeat/b\tmain\tFix B (after {{PR_A}})\tb.md\nedit\t1316\told.md\ncomment\t{{PR_A}}\tc.md\n' > "$T/kit/actions.tsv"
out="$(bash "$TOOL" "$T/kit" 2>&1)"; rc=$?
[ $rc -eq 0 ] && ok "full run exits 0" || { bad "full run exits 0 (rc=$rc)"; echo "$out"; }
grep -q 'Fixes part of #2001. Pairs with #2003.' "$T/log" && ok "circular reference filled after both PRs exist" || bad "circular reference filled"
grep -q 'Pairs with #2002.' "$T/log" && ok "forward reference filled" || bad "forward reference filled"
grep -q -- '--title Fix B (after #2002)' "$T/log" && ok "title placeholder filled" || bad "title placeholder filled"
grep -q 'gh pr comment 2002' "$T/log" && ok "comment target placeholder filled" || bad "comment target filled"
grep -q 'gh pr edit 1316' "$T/log" && ok "plain-number edit target kept" || bad "plain-number edit target"
grep -q -- '--head Ian-cmd-ops:feat/a' "$T/log" && ok "head branch comes from the fork" || bad "head from fork"
grep -q '{{' "$T/log" && bad "no placeholder reaches GitHub" || ok "no placeholder reaches GitHub"

# 2. A re-run posts nothing new.
before=$(grep -c 'create\|comment\|edit' "$T/log")
bash "$TOOL" "$T/kit" >/dev/null 2>&1
after=$(grep -c 'create\|comment\|edit' "$T/log")
[ "$before" = "$after" ] && ok "re-run skips finished actions" || bad "re-run skips finished actions ($before -> $after)"

# 3. An unknown placeholder stops the run before any post.
setup
printf 'See {{NOPE}}.\n' > "$T/kit/a.md"
printf 'pr\tPR_A\tfeat/a\tmain\tFix A\ta.md\n' > "$T/kit/actions.tsv"
bash "$TOOL" "$T/kit" >/dev/null 2>&1; rc=$?
[ $rc -ne 0 ] && ! grep -q create "$T/log" && ok "unknown placeholder refused up front" || bad "unknown placeholder refused up front"

# 4. Leftover #NNNN, a session link or a generated-by footer stops the run.
for junk in 'see #NNNN' 'https://claude.ai/code/session_x' 'Generated with [Claude Code](x)'; do
  setup
  printf '%s\n' "$junk" > "$T/kit/a.md"
  printf 'pr\tPR_A\tfeat/a\tmain\tFix A\ta.md\n' > "$T/kit/actions.tsv"
  bash "$TOOL" "$T/kit" >/dev/null 2>&1; rc=$?
  [ $rc -ne 0 ] && ! grep -q create "$T/log" && ok "refuses: $junk" || bad "refuses: $junk"
done

# 5. The wrong gh account stops the run.
setup
printf 'x\n' > "$T/kit/a.md"
printf 'comment\t1308\ta.md\n' > "$T/kit/actions.tsv"
FAKE_LOGIN=someone-else bash "$TOOL" "$T/kit" >/dev/null 2>&1; rc=$?
[ $rc -ne 0 ] && ! grep -q 'pr comment' "$T/log" && ok "wrong account refused" || bad "wrong account refused"

# 6. --dry-run makes no write calls.
setup
printf 'x {{PR_A}}\n' > "$T/kit/a.md"
printf 'pr\tPR_A\tfeat/a\tmain\tFix A\ta.md\ncomment\t{{PR_A}}\ta.md\n' > "$T/kit/actions.tsv"
bash "$TOOL" "$T/kit" --dry-run >/dev/null 2>&1; rc=$?
[ $rc -eq 0 ] && ! grep -q 'create\|comment\|edit' "$T/log" 2>/dev/null && ok "dry run writes nothing" || bad "dry run writes nothing"

echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
