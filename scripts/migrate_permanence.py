#!/usr/bin/env python3
"""
Permanence Migration Script
Adds the permanent column to existing cashew databases
"""

import sqlite3
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

def migrate_database(db_path: str, backup: bool = True) -> bool:
    """
    Add the permanent column to the thought_nodes table.
    
    Args:
        db_path: Path to the database file
        backup: Whether to create a backup before migration
        
    Returns:
        True if successful, False otherwise
    """
    db_file = Path(db_path)
    
    if not db_file.exists():
        print(f"❌ Database file not found: {db_path}")
        return False
    
    # Create backup if requested
    if backup:
        backup_path = db_file.with_suffix(f'.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.db')
        print(f"📁 Creating backup: {backup_path}")
        try:
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"✅ Backup created successfully")
        except Exception as e:
            print(f"❌ Failed to create backup: {e}")
            return False
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if permanent column already exists
        cursor.execute("PRAGMA table_info(thought_nodes)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'permanent' in columns:
            print("✅ Column 'permanent' already exists in thought_nodes table")
            conn.close()
            return True
        
        print("🔧 Adding permanent column to thought_nodes table...")
        
        # Add the permanent column
        cursor.execute("""
            ALTER TABLE thought_nodes 
            ADD COLUMN permanent INTEGER DEFAULT 0
        """)
        
        # Commit the change
        conn.commit()
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(thought_nodes)")
        columns_after = [row[1] for row in cursor.fetchall()]
        
        if 'permanent' not in columns_after:
            print("❌ Failed to add permanent column")
            conn.close()
            return False
        
        print("✅ Successfully added permanent column")
        
        # Optionally, run an initial permanence evaluation
        print("🧠 Running initial permanence evaluation...")
        
        # Add the parent directory to path to import permanence module
        parent_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(parent_dir))
        
        try:
            from core.permanence import evaluate_all_permanence
            stats = evaluate_all_permanence(db_path)
            
            print("📊 Initial permanence evaluation completed:")
            print(f"   • Nodes evaluated: {stats['nodes_evaluated']}")
            print(f"   • Nodes made permanent: {stats['nodes_made_permanent']}")
            print(f"   • Hotspots made permanent: {stats['hotspots_made_permanent']}")
            
        except ImportError as e:
            print(f"⚠️  Could not import permanence module for initial evaluation: {e}")
            print("   You can run 'cashew permanent --stats' later to evaluate permanence")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error during migration: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during migration: {e}")
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate cashew database to support permanence feature",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_permanence.py ./data/graph.db
  python migrate_permanence.py ./data/brain.db --no-backup
  python migrate_permanence.py /path/to/custom.db --backup
        """)
    
    parser.add_argument("database", help="Path to the SQLite database file")
    parser.add_argument("--no-backup", action="store_true", 
                       help="Skip creating a backup before migration")
    parser.add_argument("--backup", action="store_true", default=True,
                       help="Create a backup before migration (default)")
    
    args = parser.parse_args()
    
    # Handle backup flag logic
    backup = not args.no_backup
    
    print("🥜 Cashew Permanence Migration")
    print(f"📂 Database: {args.database}")
    print(f"💾 Backup: {'Yes' if backup else 'No'}")
    print()
    
    success = migrate_database(args.database, backup=backup)
    
    if success:
        print()
        print("🎉 Migration completed successfully!")
        print()
        print("Next steps:")
        print("1. Run 'cashew permanent --stats' to see permanence statistics")
        print("2. Use 'cashew pin <node_id>' to manually mark important nodes permanent")
        print("3. Permanence will be automatically evaluated during sleep cycles")
        return 0
    else:
        print()
        print("💥 Migration failed!")
        print("Check the error messages above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())