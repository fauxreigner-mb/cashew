#!/bin/bash
# Cashew full setup for OpenClaw agents
# Usage: bash scripts/setup.sh [--dir /path/to/notes] [--install-crons]
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
INSTALL_CRONS=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dir) DIR="$2"; shift 2 ;;
        --install-crons) INSTALL_CRONS=true; shift ;;
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
echo "✅ Cashew engine ready."

if [ "$INSTALL_CRONS" = true ]; then
    echo ""
    echo "📋 Cron jobs need to be installed via OpenClaw."
    echo "   Ask your agent: 'Install cashew cron jobs'"
    echo "   Or run: cashew install-crons (coming soon)"
fi
