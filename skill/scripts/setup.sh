#!/bin/bash
# Cashew quick setup for OpenClaw agents
# Usage: bash scripts/setup.sh [--dir /path/to/notes]
set -euo pipefail

echo "🥜 Setting up cashew..."

# Check if cashew is installed
if ! command -v cashew &>/dev/null; then
    echo "Installing cashew-core..."
    pip install git+https://github.com/jugaad-lab/cashew.git 2>&1 | tail -3
fi

# Initialize if no DB exists
DB="${CASHEW_DB:-./data/graph.db}"
if [ ! -f "$DB" ]; then
    echo "Initializing new graph database..."
    cashew init
fi

# Import notes if --dir provided
DIR=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dir) DIR="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -n "$DIR" ] && [ -d "$DIR" ]; then
    echo "Importing notes from $DIR..."
    cashew migrate-files --dir "$DIR"
fi

echo ""
cashew stats
echo ""
echo "✅ Cashew ready. Add to your AGENTS.md:"
echo '   "Before answering substantive questions, run: cashew context --hints <keywords>"'
