#!/usr/bin/env bash
# PostToolUse hook for Edit/Write/MultiEdit.
# Runs `ruff check` on the edited Python file and, if ruff reports problems,
# feeds the output back to Claude (exit 2 -> stderr is returned to the model).
# On success, or for non-Python / unresolvable files, it stays completely
# silent (exit 0). It errs on the side of silence: anything it cannot inspect
# is allowed through without noise.

set -uo pipefail

input=$(cat)

# Extract the edited file path from the tool input.
if command -v jq >/dev/null 2>&1; then
    file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""')
else
    file=""
fi

# No path, or not a Python file -> nothing to do.
[ -z "$file" ] && exit 0
case "$file" in
    *.py) ;;
    *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

# Resolve a ruff executable: PATH first, then the committed venvs.
proj="${CLAUDE_PROJECT_DIR:-.}"
ruff=""
if command -v ruff >/dev/null 2>&1; then
    ruff="ruff"
else
    for candidate in \
        "$proj/.venv_py312/Scripts/ruff.exe" \
        "$proj/.venv_py313/Scripts/ruff.exe" \
        "$proj/.venv_py312/bin/ruff" \
        "$proj/.venv_py313/bin/ruff"; do
        [ -f "$candidate" ] && { ruff="$candidate"; break; }
    done
fi

# ruff not installed anywhere we know -> stay silent rather than nagging.
[ -z "$ruff" ] && exit 0

# Run the linter. On clean code ruff exits 0; we emit nothing.
out=$("$ruff" check "$file" 2>&1)
if [ $? -ne 0 ]; then
    printf 'ruff check found issues in %s:\n%s\n' "$file" "$out" >&2
    exit 2
fi

exit 0
