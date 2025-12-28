#!/usr/bin/env python3
"""
Migration: Normalize difficulty levels from "Difficult" to "Hard"
Date: 2025-12-28
Description: Updates all recipe versions with educational_level = 'Difficult' to 'Hard'
             to match the standardized difficulty levels in the application
"""

import sqlite3
import sys
import os

# Add parent directory to path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_database_path():
    """Get the database path from environment or use default."""
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///cookbook.db')
    if database_url.startswith('sqlite:///'):
        return database_url.replace('sqlite:///', '')
    return 'cookbook.db'


def run_migration():
    """Run the difficulty level normalization migration."""
    db_path = get_database_path()

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Show current state
        print("\n--- Current difficulty level distribution ---")
        cursor.execute("""
            SELECT educational_level, COUNT(*) as count
            FROM recipe_versions
            GROUP BY educational_level
            ORDER BY educational_level
        """)

        for row in cursor.fetchall():
            print(f"  {row['educational_level']}: {row['count']} recipes")

        # Count how many will be affected
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM recipe_versions
            WHERE educational_level = 'Difficult'
        """)
        difficult_count = cursor.fetchone()['count']

        if difficult_count == 0:
            print("\n[OK] No 'Difficult' entries found. Database is already normalized.")
            return

        print(f"\n--- Will update {difficult_count} recipe(s) from 'Difficult' to 'Hard' ---")

        # Ask for confirmation
        response = input("Proceed with migration? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Migration cancelled.")
            sys.exit(0)

        # Perform the update
        cursor.execute("""
            UPDATE recipe_versions
            SET educational_level = 'Hard'
            WHERE educational_level = 'Difficult'
        """)

        affected_rows = cursor.rowcount
        conn.commit()

        print(f"\n[OK] Successfully updated {affected_rows} recipe(s)")

        # Show new state
        print("\n--- New difficulty level distribution ---")
        cursor.execute("""
            SELECT educational_level, COUNT(*) as count
            FROM recipe_versions
            GROUP BY educational_level
            ORDER BY educational_level
        """)

        for row in cursor.fetchall():
            print(f"  {row['educational_level']}: {row['count']} recipes")

        print("\n[OK] Migration completed successfully!")

    except Exception as e:
        print(f"\n[ERROR] Error during migration: {str(e)}")
        conn.rollback()
        sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Difficulty Level Normalization Migration")
    print("This will change 'Difficult' to 'Hard' in recipe_versions")
    print("=" * 60)

    run_migration()
