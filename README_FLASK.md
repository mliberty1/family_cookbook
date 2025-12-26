# Family Cookbook Flask Application

## Overview

A web application for managing and viewing family recipes with:
- Token-based authentication (no passwords needed)
- Recipe CRUD operations (Create, Read, Update, Delete)
- Full version history tracking
- Advanced search (by ingredient, author, full-text)
- Mobile-responsive design
- Print-friendly recipe pages

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```

The application will start on http://localhost:5000

### 3. Login

A test user has been created for you:

- **Login URL with token**: http://localhost:5000/login?token=3f4044b3-227e-4f23-8af2-106dacad4330
- Or manually enter the token on the login page

## Features

### Public Features (No Login Required)

- **Browse Recipes**: View all 92 recipes organized by category
- **Recipe Details**: View full recipe with ingredients, instructions, and notes
- **Search**: Search by ingredient, author, or text across all recipes
- **Version History**: View all previous versions of any recipe
- **Print Recipes**: Print-friendly layout for physical cookbooks

### Authenticated Features (Login Required)

- **Create Recipes**: Add new recipes to the cookbook
- **Edit Recipes**: Update existing recipes (creates a new version)
- **Version Tracking**: All edits are tracked with timestamps and user attribution

## How It Works

### Authentication

This app uses **token-based authentication** instead of passwords:

1. Each user has a unique authentication token (UUID)
2. Tokens are distributed via email links
3. Users click the magic link or paste the token on the login page
4. Sessions persist until logout

**To add a new user:**

```python
import sqlite3
import uuid

conn = sqlite3.connect('cookbook.db')
cursor = conn.cursor()

token = str(uuid.uuid4())
cursor.execute('''
    INSERT INTO users (name, email, auth_token, is_active)
    VALUES (?, ?, ?, ?)
''', ('User Name', 'user@email.com', token, 1))

conn.commit()
print(f'Login URL: http://localhost:5000/login?token={token}')
conn.close()
```

### Versioning

**Every recipe edit creates a new version:**

- Version 1: Original recipe (migrated from `cookbook.jsonld`)
- Version 2+: Each edit adds a new version
- Old versions are never deleted
- View history at `/recipe/<slug>/history`
- View specific version at `/recipe/<slug>?v=2`

**Example workflow:**
1. User edits "Chocolate Cake"
2. System creates version 2 with current timestamp
3. Updates `recipes.current_version_id` to point to version 2
4. Version 1 remains in database for history view

### Database Schema

- **users**: Family members with auth tokens
- **recipes**: Core recipe metadata (slug, current version pointer)
- **recipe_versions**: All versions of all recipes (full JSON-LD + searchable fields)
- **recipe_ingredients**: Normalized ingredients with section support
- **recipe_instructions**: Normalized instructions with note support

Full schema in `schema.sql` and design docs in `DATABASE_DESIGN.md`.

### Search Features

1. **Full-Text Search**: SQLite FTS5 indexes on names, descriptions, authors
   ```sql
   WHERE recipe_versions_fts MATCH 'chocolate'
   ```

2. **Ingredient Search**: Find recipes containing specific ingredients
   ```sql
   WHERE ingredient_text LIKE '%eggs%'
   ```

3. **Author Search**: Find all recipes by a specific person
   ```sql
   WHERE author LIKE '%Diana Liberty%'
   ```

4. **Category Filter**: Browse recipes by type (Desserts, Entrees, etc.)

## File Structure

```
family_cookbook/
├── app.py                    # Flask application (main entry point)
├── cookbook.db               # SQLite database (all recipe data)
├── schema.sql                # Database schema definition
├── migrate.py                # Migration script (JSON-LD → SQLite)
├── DATABASE_DESIGN.md        # Database design documentation
├── WEB_FRAMEWORK_RECOMMENDATION.md  # Framework comparison
│
├── templates/                # Jinja2 HTML templates
│   ├── base.html             # Base template (navbar, footer, flash messages)
│   ├── index.html            # Recipe listing by category
│   ├── recipe.html           # Recipe detail page
│   ├── recipe_form.html      # Create/edit recipe form
│   ├── search.html           # Search interface
│   ├── history.html          # Version history timeline
│   └── login.html            # Login page
│
├── static/                   # Static assets (CSS, JS)
│   ├── style.css             # Main stylesheet
│   ├── print.css             # Print-specific styles
│   └── recipe-scaler.js      # Recipe scaling functionality
│
├── requirements.txt          # Python dependencies
└── cookbook.jsonld           # Original JSON-LD data (archived)
```

## Customization

### Change Secret Key

For production, change the secret key in `app.py`:

```python
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
```

Generate a secure key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Add Categories

Edit the `categories` list in routes:
- `recipe_new()` line 421
- `recipe_edit()` line 543

### Customize Styling

Edit `static/style.css` CSS variables:

```css
:root {
    --color-primary: #2c3e50;    /* Main heading color */
    --color-accent: #3498db;     /* Buttons, highlights */
    --color-bg-alt: #f8f9fa;     /* Background cards */
}
```

## Deployment

### Option 1: PythonAnywhere (Free)

1. Upload files to PythonAnywhere
2. Set up a web app with Flask
3. Point to `app.py`
4. Set up static files mapping: `/static` → `static/`

### Option 2: Heroku

1. Create `Procfile`:
   ```
   web: gunicorn app:app
   ```

2. Add `gunicorn` to `requirements.txt`:
   ```
   gunicorn==21.2.0
   ```

3. Deploy:
   ```bash
   heroku create family-cookbook
   git push heroku main
   ```

### Option 3: Self-Hosted (Raspberry Pi, Home Server)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   gunicorn app:app
   ```

2. Use a production WSGI server:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. Set up reverse proxy with nginx or Apache

## Troubleshooting

### "No such table" error

Run the migration script:
```bash
python migrate.py
```

### Recipe scaler not working

Make sure `recipe-scaler.js` is in `static/` folder and linked in `base.html`.

### Search returns no results

Check FTS5 indexes:
```sql
SELECT * FROM recipe_versions_fts WHERE recipe_versions_fts MATCH 'test';
```

Rebuild FTS indexes if needed:
```sql
INSERT INTO recipe_versions_fts(recipe_versions_fts) VALUES('rebuild');
```

### Login token not working

Check user exists and is active:
```sql
SELECT * FROM users WHERE auth_token = 'your-token-here';
```

## Development

### Run in Debug Mode

Debug mode is enabled by default in `app.py`:

```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

This enables:
- Auto-reload on code changes
- Detailed error pages
- Interactive debugger

**Disable for production!**

### Add New Routes

1. Add route in `app.py`:
   ```python
   @app.route('/my-route')
   def my_view():
       return render_template('my_template.html')
   ```

2. Create template in `templates/my_template.html`

3. Add navigation link in `templates/base.html`

### Database Queries

Use the helper functions:

```python
# Read query (returns list of rows)
recipes = query_db('SELECT * FROM current_recipes WHERE category = ?', ['Desserts'])

# Read query (returns single row)
recipe = query_db('SELECT * FROM recipes WHERE slug = ?', ['chocolate-cake'], one=True)

# Write query (returns last inserted row ID)
recipe_id = execute_db('INSERT INTO recipes (slug, ...) VALUES (?, ...)', ['new-slug', ...])
```

## Support

For questions or issues:

1. Check `DATABASE_DESIGN.md` for schema details
2. Check `WEB_FRAMEWORK_RECOMMENDATION.md` for Flask rationale
3. Review code comments in `app.py`
4. Check Flask documentation: https://flask.palletsprojects.com/

## License

Apache 2.0 (same as original cookbook project)
