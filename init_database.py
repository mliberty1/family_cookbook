"""
Manual Database Initialization Script

This script initializes the database from schema.sql and creates an initial admin user.
Run this on Render via the Shell after deployment.
"""

import sqlite3
import os
import sys

# Database path - from environment variable or default
database_url = os.environ.get('DATABASE_URL', 'sqlite:///cookbook.db')
if database_url.startswith('sqlite:///'):
    db_path = database_url.replace('sqlite:///', '')
else:
    db_path = 'cookbook.db'

print(f"Initializing database at: {db_path}")

# Ensure the directory exists
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)
    print(f"Created directory: {db_dir}")

# Read schema.sql
schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
if not os.path.exists(schema_path):
    print(f"ERROR: schema.sql not found at {schema_path}")
    sys.exit(1)

print(f"Reading schema from: {schema_path}")
with open(schema_path, 'r', encoding='utf-8') as f:
    schema = f.read()

# Connect to database and execute schema
print("Connecting to database...")
conn = sqlite3.connect(db_path)

print("Creating tables, views, and indexes...")
conn.executescript(schema)
conn.commit()

print("Database initialized successfully!")

# Create initial admin user
print("\nCreating initial admin user...")
import uuid

cursor = conn.cursor()
cursor.execute("""
    INSERT INTO users (name, email, auth_token, is_admin, is_active)
    VALUES (?, ?, ?, ?, ?)
""", ('Admin User', 'admin@cookbook.family', str(uuid.uuid4()), 1, 1))
conn.commit()

# Get the auth token for login
cursor.execute("SELECT auth_token FROM users WHERE email = 'admin@cookbook.family'")
token = cursor.fetchone()[0]

print(f"\nAdmin user created!")
print(f"Email: admin@cookbook.family")
print(f"Login URL: /login?token={token}")
print(f"\nFull login URL will be: https://your-app.onrender.com/login?token={token}")

conn.close()

print("\n=== Database initialization complete! ===")
print("\nNext step: Import recipes from cookbook.jsonld")
print("Run: python import_recipes.py")
