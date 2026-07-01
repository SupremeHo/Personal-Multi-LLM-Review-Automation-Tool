#!/usr/bin/env bash
# PreToolUse hook for the Bash tool.
# Reads the hook JSON on stdin, inspects tool_input.command, and denies known
# destructive patterns. On no match it exits 0 (allow). It errs on the side of
# allowing: if the command can't be parsed, it does NOT block.

set -uo pipefail

input=$(cat)

# Extract the command being run. Fall back to the raw stdin if jq is unavailable.
if command -v jq >/dev/null 2>&1; then
    cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')
else
    cmd=$input
fi

# Nothing to inspect -> allow.
[ -z "$cmd" ] && exit 0

# Emit a PreToolUse "deny" decision as JSON and stop.
deny() {
    local reason="$1"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}\n' \
        "$(printf '%s' "$reason" | jq -Rs . 2>/dev/null || printf '"%s"' "$reason")"
    exit 0
}

# Case-insensitive substring/regex helper.
matches() {
    printf '%s' "$cmd" | grep -Eiq -- "$1"
}

# --- rm -rf (recursive AND force, flags in any order/combination) ---
if matches '(^|[[:space:]])rm([[:space:]]|$)'; then
    if matches '(-[a-z]*r|--recursive)' && matches '(-[a-z]*f|--force)'; then
        deny 'Blocked by safety hook: recursive force delete (rm -rf). Remove the -r/-f flags or narrow the target, then retry.'
    fi
fi

# --- git push --force / -f ---
if matches 'git[[:space:]]+push' && matches '(--force|--force-with-lease|(^|[[:space:]])-f([[:space:]]|$))'; then
    deny 'Blocked by safety hook: force push (git push --force/-f). Force-pushing can overwrite remote history.'
fi

# --- git reset --hard / git clean -f (destroys uncommitted work) ---
if matches 'git[[:space:]]+reset' && matches '--hard'; then
    deny 'Blocked by safety hook: git reset --hard discards uncommitted changes irreversibly.'
fi
if matches 'git[[:space:]]+clean' && matches '(-[a-z]*f|--force)'; then
    deny 'Blocked by safety hook: git clean -f deletes untracked files (e.g. .env, local logs) irreversibly.'
fi

# --- DROP TABLE / DELETE FROM / TRUNCATE (SQL) ---
if matches 'drop[[:space:]]+table'; then
    deny 'Blocked by safety hook: destructive SQL (DROP TABLE).'
fi
if matches 'delete[[:space:]]+from'; then
    deny 'Blocked by safety hook: destructive SQL (DELETE FROM). This can wipe the audit history in db/llm_responses.db.'
fi
if matches '(^|[[:space:]"'"'"'])truncate([[:space:]"'"'"']|$)'; then
    deny 'Blocked by safety hook: destructive SQL (TRUNCATE).'
fi

# --- dd if=... (raw disk read/write) ---
if matches '(^|[[:space:]])dd([[:space:]]).*if='; then
    deny 'Blocked by safety hook: raw disk operation (dd if=).'
fi

# =====================================================================
# Project-specific rules (Multi-LLM Review Automation Tool)
# The audit trail (logs/*.jsonl + db/llm_responses.db), the committed
# venvs, and .env (API keys) are costly/impossible to recover. Protect
# them even from a plain, non-recursive rm.
# =====================================================================

# Paths whose deletion would destroy audit data, secrets, or committed envs.
protected='(\.env([[:space:]"'"'"']|$))|((^|[[:space:]]|/)(db|logs)(/|[[:space:]]|$))|(\.db([[:space:]"'"'"']|$))|(\.jsonl)|(\.venv)|(_create_table\.sql)'

# --- rm of a protected path (any flags, recursive or not) ---
if matches '(^|[[:space:]])rm([[:space:]]|$)' && matches "$protected"; then
    deny 'Blocked by safety hook: refusing to rm an audit/secret/env asset (db/, logs/, *.db, *.jsonl, .venv*, .env, _create_table.sql). Delete a specific unrelated file, or remove it manually if you are sure.'
fi

# --- shell truncation (> file) of the DB, an audit log, or .env ---
if matches '>[[:space:]]*[^|&;]*(\.env([[:space:]"'"'"']|$)|\.db([[:space:]"'"'"']|$)|\.jsonl|_create_table\.sql)'; then
    deny 'Blocked by safety hook: > redirect would truncate a protected file (.env / *.db / *.jsonl / _create_table.sql).'
fi

# --- reading .env to stdout (keeps API keys out of the transcript) ---
if matches '(^|[[:space:]])(cat|type|less|more|head|tail|bat|nl|xxd|strings|od)[[:space:]]+[^|&;]*\.env([[:space:]"'"'"']|$)'; then
    deny 'Blocked by safety hook: refusing to print .env (contains API keys). Use `python -m resources.cli check-env` to validate keys without exposing them.'
fi

# No dangerous pattern matched -> allow.
exit 0
