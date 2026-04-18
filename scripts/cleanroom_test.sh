#!/bin/bash
# Clean-room installation test for cashew
# Tests the full install → init → extract → context pipeline
set -e

CLEAN="/tmp/cashew-cleanroom-$(date +%s)"
CASHEW_SRC="$(cd "$(dirname "$0")/.." && pwd)"
DB="$CLEAN/data/graph.db"

echo "🧹 Clean-room test starting..."
echo "   Source: $CASHEW_SRC"
echo "   Clean dir: $CLEAN"
echo ""

# Step 1: Create isolated venv
echo "📦 Step 1: Creating isolated venv..."
python3 -m venv "$CLEAN/venv"
source "$CLEAN/venv/bin/activate"
pip install --quiet --upgrade pip

# Step 2: Install cashew from source
echo "📦 Step 2: Installing cashew..."
pip install -e "$CASHEW_SRC" 2>&1 | tail -5

# Step 3: Verify CLI exists
echo ""
echo "🔍 Step 3: Verifying CLI..."
which cashew || { echo "❌ cashew CLI not found"; exit 1; }
cashew --help > /dev/null || { echo "❌ cashew --help failed"; exit 1; }
echo "   ✅ CLI available"

# Step 4: Init database
echo ""
echo "🗄  Step 4: Initializing database..."
cashew init --db "$DB"

# Step 5: Verify schema
echo ""
echo "🔍 Step 5: Verifying schema..."
python3 -c "
# Route DB access through the shared helper — no raw sqlite3 here.
import os
os.environ['CASHEW_DB_PATH'] = '$DB'
from core import db as cdb
conn = cdb.connect('$DB')
try:
    cols = cdb.pragma_columns(conn, cdb.NODES_TABLE)
    tables = cdb.list_tables(conn)
    print(f'   Tables: {tables}')
    print(f'   Columns: {cols}')
    assert 'tags' in cols, 'MISSING: tags column'
    assert 'hotspots' not in tables, 'UNEXPECTED: hotspots table still exists'
    print('   ✅ Schema correct')
finally:
    conn.close()
"

# Step 6: Create test conversation and extract
echo ""
echo "📝 Step 6: Testing extraction..."
cat > "$CLEAN/test-conversation.md" << 'TESTEOF'
User: I've been thinking about how graph databases could be used for personal knowledge management.