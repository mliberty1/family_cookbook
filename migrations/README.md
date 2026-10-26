# Schema migrations

Applied by `migrate.py`, which the edge start script runs before gunicorn
on every (re)start. Files are named `NNN_description.sql` and applied in
numeric order; the database's `PRAGMA user_version` tracks the highest one
applied. The existing production database is at version 0, so the first
migration is `001_...sql`.

Rules:

- Plain SQLite SQL. No `BEGIN`/`COMMIT`; the runner wraps each file in one
  transaction with the version bump.
- Never edit or renumber a file after it has been pushed to `main`.
- `schema.sql` is the full schema for a fresh database (`init_database.py`).
  Keep it in sync by hand so a fresh install matches a migrated one, and
  set `PRAGMA user_version` in a fresh install to the latest migration.
