"""
Import Recipes from cookbook.jsonld

This script imports recipes from the cookbook.jsonld file into the database.
Run this after initializing the database with init_database.py.

Usage:
    python import_recipes.py
"""

import sqlite3
import json
import os
import sys
import re
from datetime import datetime


def slugify(text):
    """Convert recipe name to URL-friendly slug."""
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    # Remove leading/trailing hyphens
    return text.strip('-')


def import_recipes(db_path='cookbook.db', jsonld_path='cookbook.jsonld'):
    """Import recipes from JSON-LD file into database."""

    print(f"Importing recipes from {jsonld_path} into {db_path}")

    # Check if files exist
    if not os.path.exists(jsonld_path):
        print(f"ERROR: {jsonld_path} not found")
        return False

    if not os.path.exists(db_path):
        print(f"ERROR: {db_path} not found. Run init_database.py first.")
        return False

    # Read JSON-LD file
    print(f"Reading {jsonld_path}...")
    with open(jsonld_path, 'r', encoding='utf-8') as f:
        recipes = json.load(f)

    print(f"Found {len(recipes)} recipes to import")

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ensure System Migration user exists
    cursor.execute("SELECT id FROM users WHERE email = 'system@cookbook.family'")
    system_user = cursor.fetchone()

    if not system_user:
        print("Creating System Migration user...")
        import uuid
        cursor.execute("""
            INSERT INTO users (name, email, auth_token, is_admin, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, ('System Migration', 'system@cookbook.family', str(uuid.uuid4()), 0, 1))
        conn.commit()
        system_user_id = cursor.lastrowid
    else:
        system_user_id = system_user['id']

    print(f"Using user ID {system_user_id} for recipe attribution")

    # Import each recipe
    imported = 0
    skipped = 0
    errors = 0

    for recipe_data in recipes:
        try:
            name = recipe_data.get('name', 'Unnamed Recipe')
            slug = slugify(name)

            # Check if recipe already exists
            cursor.execute("SELECT id FROM recipes WHERE slug = ?", (slug,))
            if cursor.fetchone():
                print(f"  SKIP: {name} (already exists with slug: {slug})")
                skipped += 1
                continue

            print(f"  Importing: {name}")

            # Insert recipe
            cursor.execute("""
                INSERT INTO recipes (slug, created_by_user_id)
                VALUES (?, ?)
            """, (slug, system_user_id))
            recipe_id = cursor.lastrowid

            # Create version 1
            cursor.execute("""
                INSERT INTO recipe_versions (
                    recipe_id, version_number, name, author, description,
                    recipe_category, educational_level, total_time, recipe_yield,
                    creative_work_status, date_created, date_modified, date_published,
                    jsonld_data, created_by_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recipe_id,
                1,  # version_number
                recipe_data.get('name'),
                recipe_data.get('author'),
                recipe_data.get('description'),
                recipe_data.get('recipeCategory'),
                recipe_data.get('educationalLevel'),
                recipe_data.get('totalTime'),
                recipe_data.get('recipeYield'),
                recipe_data.get('creativeWorkStatus', 'Published'),
                recipe_data.get('dateCreated'),
                recipe_data.get('dateModified'),
                recipe_data.get('datePublished'),
                json.dumps(recipe_data),
                system_user_id
            ))
            version_id = cursor.lastrowid

            # Update recipe to point to this version
            cursor.execute("""
                UPDATE recipes SET current_version_id = ? WHERE id = ?
            """, (version_id, recipe_id))

            # Insert ingredients
            ingredients = recipe_data.get('recipeIngredient', [])
            for idx, ingredient_text in enumerate(ingredients):
                # Check if this is a section header
                is_section = ingredient_text.startswith('## ')
                section_name = ingredient_text[3:] if is_section else None

                cursor.execute("""
                    INSERT INTO recipe_ingredients (
                        recipe_version_id, order_index, ingredient_text,
                        is_section_header, section_name
                    ) VALUES (?, ?, ?, ?, ?)
                """, (version_id, idx, ingredient_text, is_section, section_name))

            # Insert instructions
            instructions = recipe_data.get('recipeInstructions', [])
            for idx, instruction_text in enumerate(instructions):
                # Check if this is a note
                is_note = instruction_text.startswith('🛈 ')

                cursor.execute("""
                    INSERT INTO recipe_instructions (
                        recipe_version_id, order_index, instruction_text, is_note
                    ) VALUES (?, ?, ?, ?)
                """, (version_id, idx, instruction_text, is_note))

            # Note: Full-text search is automatically populated by FTS5 triggers
            # No manual insertion needed

            imported += 1

        except Exception as e:
            print(f"  ERROR importing {recipe_data.get('name', 'unknown')}: {e}")
            errors += 1
            continue

    conn.commit()
    conn.close()

    print(f"\n=== Import Summary ===")
    print(f"Imported: {imported} recipes")
    print(f"Skipped:  {skipped} recipes (already exist)")
    print(f"Errors:   {errors} recipes")
    print(f"Total:    {len(recipes)} recipes in file")

    return errors == 0


if __name__ == '__main__':
    # Get database path from environment or use default
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///cookbook.db')
    if database_url.startswith('sqlite:///'):
        db_path = database_url.replace('sqlite:///', '')
    else:
        db_path = 'cookbook.db'

    # Get JSON-LD path (default to cookbook.jsonld in same directory)
    jsonld_path = os.path.join(os.path.dirname(__file__), 'cookbook.jsonld')

    print(f"Database: {db_path}")
    print(f"JSON-LD:  {jsonld_path}")
    print()

    success = import_recipes(db_path, jsonld_path)

    if success:
        print("\n✓ Import completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Import completed with errors")
        sys.exit(1)
