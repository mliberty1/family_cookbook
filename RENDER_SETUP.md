# Render Deployment Setup Instructions

## Manual Database Initialization

After deploying to Render, you need to manually initialize the database. Follow these steps:

---

## Method 1: Using Python Script (Recommended)

1. **Go to your Render Dashboard**
   - Navigate to your service: https://dashboard.render.com/

2. **Open Shell**
   - Click on your `family-cookbook` service
   - Click the **Shell** tab (or **SSH** button)

3. **Run the initialization script**
   ```bash
   python init_database.py
   ```

4. **Save the login URL**
   - The script will output an admin login token
   - Copy the full URL (it will look like: `/login?token=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
   - Visit: `https://your-app.onrender.com/login?token=YOUR-TOKEN-HERE`

---

## Method 2: Using SQLite Commands

If the Python script doesn't work, use SQLite directly:

1. **Open Shell on Render**
   - Go to your service → Shell tab

2. **Check if sqlite3 is available**
   ```bash
   which sqlite3
   ```

3. **Initialize the database**
   ```bash
   sqlite3 /var/data/cookbook.db < schema.sql
   ```

4. **Create admin user**
   ```bash
   python3 << 'EOF'
import sqlite3
import uuid

conn = sqlite3.connect('/var/data/cookbook.db')
cursor = conn.cursor()

# Create admin user
token = str(uuid.uuid4())
cursor.execute("""
    INSERT INTO users (name, email, auth_token, is_admin, is_active)
    VALUES (?, ?, ?, ?, ?)
""", ('Admin User', 'admin@cookbook.family', token, 1, 1))
conn.commit()

print(f"Admin user created!")
print(f"Login token: {token}")
print(f"Login URL: /login?token={token}")

conn.close()
EOF
   ```

5. **Copy the login token** and visit your app with the login URL

---

## Method 3: Using Python One-Liner

1. **Open Shell on Render**

2. **Run this command** (all one line):
   ```bash
   python3 -c "import sqlite3; conn = sqlite3.connect('/var/data/cookbook.db'); conn.executescript(open('schema.sql').read()); conn.commit(); import uuid; token = str(uuid.uuid4()); conn.execute('INSERT INTO users (name, email, auth_token, is_admin, is_active) VALUES (?, ?, ?, ?, ?)', ('Admin', 'admin@cookbook.family', token, 1, 1)); conn.commit(); print(f'Login: /login?token={token}'); conn.close()"
   ```

---

## Verification

After initialization, verify the database is working:

1. **Check tables exist**:
   ```bash
   python3 -c "import sqlite3; conn = sqlite3.connect('/var/data/cookbook.db'); cursor = conn.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); print([row[0] for row in cursor.fetchall()]); conn.close()"
   ```

   Should output: `['users', 'recipes', 'recipe_versions', 'recipe_ingredients', 'recipe_instructions', 'recipe_search', 'recipe_search_data', 'recipe_search_idx', ...]`

2. **Check admin user exists**:
   ```bash
   python3 -c "import sqlite3; conn = sqlite3.connect('/var/data/cookbook.db'); cursor = conn.cursor(); cursor.execute('SELECT name, email, is_admin FROM users'); print(cursor.fetchall()); conn.close()"
   ```

   Should output: `[('Admin User', 'admin@cookbook.family', 1)]`

3. **Visit your app**:
   - Go to: `https://your-app.onrender.com`
   - You should see the landing page (empty, no recipes yet)

4. **Login as admin**:
   - Use the login URL from the initialization output
   - You should see "Admin" link in the navigation bar

---

## Troubleshooting

### Error: "no such table: current_recipes"
- Database wasn't initialized properly
- Re-run the initialization steps above

### Error: "unable to open database file"
- Database path is incorrect
- Verify the path is `/var/data/cookbook.db` (as set in render.yaml)
- Check that the disk is mounted: `ls -la /var/data/`

### Can't find schema.sql
- Make sure schema.sql is in your repository
- Check current directory: `pwd` and `ls -la`
- Schema.sql should be in the project root

### Database exists but is empty
- Drop and recreate:
  ```bash
  rm /var/data/cookbook.db
  python init_database.py
  ```

---

## Importing Existing Data

If you have an existing database backup (SQL file):

```bash
sqlite3 /var/data/cookbook.db < your_backup.sql
```

Or if you have the cookbook.jsonld file, you can import it after initialization.

---

## Next Steps After Initialization

1. Login as admin
2. Add additional users via Admin Panel
3. Import recipes or create new ones
4. Configure Mailgun environment variables (optional, for email features)
