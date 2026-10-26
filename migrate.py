#!/usr/bin/env python3
"""Apply pending SQL migrations to the cookbook database.

Migrations live in migrations/NNN_description.sql, where NNN is a positive
integer. The database records the highest NNN applied in PRAGMA user_version,
so running this on every start is cheap and idempotent. Each file runs inside
a single transaction together with the user_version bump, so a failing file
leaves the database at the previous version. Do not put BEGIN/COMMIT in the
files.

Usage: python migrate.py            (uses DATABASE_URL like app.py)
"""

import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(HERE, 'migrations')
NAME_RE = re.compile(r'^(\d+)_.*\.sql$')


def database_path():
    url = os.environ.get('DATABASE_URL', 'sqlite:///cookbook.db')
    if url.startswith('sqlite:///'):
        return url[len('sqlite:///'):]
    return 'cookbook.db'


def pending(current):
    found = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return found
    for name in os.listdir(MIGRATIONS_DIR):
        m = NAME_RE.match(name)
        if m and int(m.group(1)) > current:
            found.append((int(m.group(1)), name))
    found.sort()
    return found


def main():
    path = database_path()
    if not os.path.exists(path):
        print(f'migrate: database {path} does not exist; nothing to do')
        return 0
    conn = sqlite3.connect(path)
    conn.isolation_level = None  # explicit transactions below
    current = conn.execute('PRAGMA user_version').fetchone()[0]
    todo = pending(current)
    if not todo:
        print(f'migrate: {path} at version {current}, up to date')
        return 0
    for version, name in todo:
        with open(os.path.join(MIGRATIONS_DIR, name), encoding='utf-8') as f:
            sql = f.read()
        try:
            conn.executescript(
                f'BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;'
            )
        except sqlite3.Error as e:
            conn.execute('ROLLBACK')
            print(f'migrate: {name} FAILED: {e}', file=sys.stderr)
            return 1
        print(f'migrate: applied {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
