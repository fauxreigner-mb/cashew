#!/usr/bin/env bash
# Inject cashew brain context into every Claude Code prompt.
# Fires on UserPromptSubmit. Query is pure local (no LLM, no network).
#
# Setup:
#   1. Copy this file to ~/.claude/hooks/cashew-userpromptsubmit.sh
#   2. chmod +x ~/.claude/hooks/cashew-userpromptsubmit.sh
#   3. In Claude Code settings (hooks), add a UserPromptSubmit hook pointing to this script.
#
# Required env vars (set in your shell profile):
#   CASHEW_DB — path to your cashew graph database
#
# Optional:
#   CASHEW_BIN — path to the cashew executable (default: cashew)

CASHEW="${CASHEW_BIN:-cashew}"
DB="${CASHEW_DB:-$HOME/.cashew/graph.db}"

input=$(cat)

# Extract first 300 chars of prompt as retrieval hints.
hints=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
prompt = data.get('prompt', '')
print(prompt[:300])
" 2>/dev/null)

# Skip if prompt is too short to produce meaningful hints.
# Short acknowledgments ("yes", "ok", "go") yield low-signal retrievals
# that add noise without value.
if [ -z "$hints" ] || [ ${#hints} -lt 25 ]; then
    exit 0
fi

context=$(PYTHONUTF8=1 KMP_DUPLICATE_LIB_OK=TRUE "$CASHEW" --db "$DB" context --hints "$hints" 2>/dev/null)

if [ -z "$context" ]; then
    exit 0
fi

python3 -c "
import json, sys
context = sys.argv[1]
print(json.dumps({'hookSpecificOutput': {'additionalSystemPrompt': context}}))
" "$context"
