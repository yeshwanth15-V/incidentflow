import sqlite3
import os
from datetime import datetime, timezone

def run_migrations(db_path=None):
    """
    Safely inspects and extends existing SQLite database schema
    without dropping tables or losing any existing incident records.
    """
    if db_path is None:
        # Default instance path
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, "instance", "incidents.db")
    
    if not os.path.exists(db_path):
        print(f"[Migration] Database file not found at {db_path}. Will be created on init.")
        return
        
    print(f"[Migration] Checking database schema at {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Check existing columns in incident table
    cur.execute("PRAGMA table_info(incident);")
    existing_columns = {row[1]: row[2] for row in cur.fetchall()}
    print(f"[Migration] Existing incident columns: {list(existing_columns.keys())}")
    
    columns_to_add = [
        ("category", "VARCHAR(50) DEFAULT 'General'"),
        ("assigned_user_id", "INTEGER REFERENCES user(id) ON DELETE SET NULL"),
        ("created_at", "DATETIME"),
        ("updated_at", "DATETIME"),
        ("due_date", "DATETIME"),
        ("resolved_at", "DATETIME")
    ]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            print(f"[Migration] Adding column '{col_name}' ({col_type}) to incident table...")
            cur.execute(f"ALTER TABLE incident ADD COLUMN {col_name} {col_type};")
            
    # Backfill created_at / updated_at for any records with NULL
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE incident SET created_at = ? WHERE created_at IS NULL;", (now_iso,))
    cur.execute("UPDATE incident SET updated_at = ? WHERE updated_at IS NULL;", (now_iso,))
    cur.execute("UPDATE incident SET category = 'General' WHERE category IS NULL OR category = '';")
    
    conn.commit()
    conn.close()
    print("[Migration] SQLite schema upgrade completed safely.")

if __name__ == "__main__":
    run_migrations()
