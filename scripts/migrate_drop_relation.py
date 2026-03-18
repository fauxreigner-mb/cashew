#!/usr/bin/env python3
"""
Migration Script: Drop relation column from derivation_edges

This script migrates the derivation_edges table to remove the relation column.
All edges become untyped connections, with relation information moved to the reasoning text.

Steps:
1. Backup the database
2. Create new derivation_edges table without relation column
3. Migrate data, deduplicating edges that only differed by relation (keep highest weight)
4. Drop old table and rename new table

Run this ONCE to migrate from the old schema to the new schema.
"""

import sqlite3
import shutil
import sys
import os
from datetime import datetime
from pathlib import Path

def backup_database(db_path: str) -> str:
    """Create a timestamped backup of the database"""
    backup_name = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_name)
    print(f"✅ Database backed up to: {backup_name}")
    return backup_name

def migrate_drop_relation(db_path: str):
    """Migrate derivation_edges to drop relation column"""
    
    # Verify database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Create backup
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if relation column exists (migration might have already been run)
        cursor.execute("PRAGMA table_info(derivation_edges)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'relation' not in columns:
            print("✅ Migration already completed - relation column not found")
            conn.close()
            return True
        
        print("🔄 Starting migration...")
        
        # Step 1: Create new table without relation column
        cursor.execute("""
            CREATE TABLE derivation_edges_new (
                parent_id TEXT,
                child_id TEXT,
                weight REAL,
                reasoning TEXT,
                confidence REAL,
                timestamp TEXT,
                PRIMARY KEY (parent_id, child_id),
                FOREIGN KEY (parent_id) REFERENCES thought_nodes(id),
                FOREIGN KEY (child_id) REFERENCES thought_nodes(id)
            )
        """)
        print("✅ Created new table schema")
        
        # Step 2: Migrate data with deduplication
        # For edges that only differ by relation, keep the one with highest weight
        cursor.execute("""
            INSERT INTO derivation_edges_new 
            SELECT 
                parent_id,
                child_id,
                MAX(weight) as weight,
                GROUP_CONCAT(
                    CASE 
                        WHEN relation IS NOT NULL AND relation != ''
                        THEN relation || ' - ' || COALESCE(reasoning, '')
                        ELSE COALESCE(reasoning, '')
                    END, 
                    ' | '
                ) as reasoning,
                MAX(confidence) as confidence,
                MAX(timestamp) as timestamp
            FROM derivation_edges
            GROUP BY parent_id, child_id
        """)
        
        migrated_edges = cursor.rowcount
        print(f"✅ Migrated {migrated_edges} edges (deduplicated)")
        
        # Step 3: Get edge counts for verification
        cursor.execute("SELECT COUNT(*) FROM derivation_edges")
        old_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM derivation_edges_new")
        new_count = cursor.fetchone()[0]
        
        print(f"📊 Edge count: {old_count} → {new_count}")
        
        # Step 4: Replace old table with new table
        cursor.execute("DROP TABLE derivation_edges")
        cursor.execute("ALTER TABLE derivation_edges_new RENAME TO derivation_edges")
        
        # Step 5: Recreate indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_parent ON derivation_edges(parent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_edges_child ON derivation_edges(child_id)')
        
        conn.commit()
        conn.close()
        
        print("✅ Migration completed successfully!")
        print(f"📁 Backup available at: {backup_path}")
        
        # Verify the new schema
        verify_migration(db_path)
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print(f"🔄 Restoring from backup: {backup_path}")
        
        # Restore from backup
        shutil.copy2(backup_path, db_path)
        print("✅ Database restored from backup")
        return False

def verify_migration(db_path: str):
    """Verify the migration was successful"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check schema
    cursor.execute("PRAGMA table_info(derivation_edges)")
    columns = [row[1] for row in cursor.fetchall()]
    
    expected_columns = ['parent_id', 'child_id', 'weight', 'reasoning', 'confidence', 'timestamp']
    
    print("\n🔍 Migration Verification:")
    
    if 'relation' in columns:
        print("❌ FAILED: relation column still exists")
        return False
    
    missing_columns = [col for col in expected_columns if col not in columns]
    if missing_columns:
        print(f"❌ FAILED: Missing columns: {missing_columns}")
        return False
    
    # Check sample data
    cursor.execute("SELECT COUNT(*) FROM derivation_edges")
    edge_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT reasoning FROM derivation_edges WHERE reasoning IS NOT NULL LIMIT 5")
    sample_reasoning = cursor.fetchall()
    
    print(f"✅ Schema correct: {len(columns)} columns")
    print(f"✅ No relation column")
    print(f"✅ {edge_count} edges in new table")
    
    if sample_reasoning:
        print("✅ Sample reasoning values:")
        for reasoning, in sample_reasoning:
            print(f"   - {reasoning[:80]}...")
    
    conn.close()
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate derivation_edges to drop relation column")
    parser.add_argument("--db", required=True, help="Path to the database file")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if not args.force:
        print("🚨 This migration will permanently modify your database structure.")
        print(f"🗄️  Database: {args.db}")
        print("📝 Changes:")
        print("   - Remove 'relation' column from derivation_edges")
        print("   - Merge relation info into reasoning text")
        print("   - Deduplicate edges that only differed by relation")
        print("   - Update PRIMARY KEY to (parent_id, child_id)")
        
        confirm = input("\nContinue? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("❌ Migration cancelled")
            return 1
    
    print(f"\n🚀 Starting migration of: {args.db}")
    
    success = migrate_drop_relation(args.db)
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("⚠️  Important: All code using 'relation' column must be updated")
        return 0
    else:
        print("\n💥 Migration failed - database restored from backup")
        return 1

if __name__ == "__main__":
    sys.exit(main())