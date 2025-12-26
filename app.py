"""
Family Cookbook Flask Application

A web application for managing and viewing family recipes with:
- Token-based authentication
- Recipe CRUD operations
- Version history tracking
- Full-text search
"""

import sqlite3
import json
import re
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, g, flash, jsonify
)


# =============================================================================
# App Configuration
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['DATABASE'] = 'cookbook.db'


# =============================================================================
# Database Helpers
# =============================================================================

def get_db():
    """Get database connection for the current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Execute a query and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute a query that modifies the database."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid


# =============================================================================
# Helper Functions
# =============================================================================

def slugify(text):
    """Convert recipe name to URL-friendly slug."""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def parse_ingredients(ingredients_text):
    """Parse ingredient text area into list, identifying sections.

    Returns list of dicts with: ingredient_text, is_section_header, section_name
    """
    lines = [line.strip() for line in ingredients_text.split('\n') if line.strip()]
    parsed = []

    for line in lines:
        if line.startswith('## '):
            parsed.append({
                'ingredient_text': line,
                'is_section_header': True,
                'section_name': line[3:].strip()
            })
        else:
            parsed.append({
                'ingredient_text': line,
                'is_section_header': False,
                'section_name': None
            })

    return parsed


def parse_instructions(instructions_text):
    """Parse instruction text area into list, identifying notes.

    Returns list of dicts with: instruction_text, is_note
    """
    lines = [line.strip() for line in instructions_text.split('\n') if line.strip()]
    parsed = []

    for line in lines:
        if line.startswith('🛈 '):
            parsed.append({
                'instruction_text': line,
                'is_note': True
            })
        else:
            parsed.append({
                'instruction_text': line,
                'is_note': False
            })

    return parsed


def format_duration(duration_str):
    """Convert ISO 8601 duration (e.g., PT30M) to human-readable format."""
    if not duration_str or duration_str == 'TODO':
        return 'Not specified'

    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration_str)
    if not match:
        return duration_str

    hours, minutes = match.groups()
    parts = []

    if hours:
        parts.append(f"{hours} hour{'s' if int(hours) > 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if int(minutes) > 1 else ''}")

    return ' '.join(parts) if parts else 'Not specified'


# Add custom filters to Jinja2
app.jinja_env.filters['format_duration'] = format_duration


@app.context_processor
def inject_current_year():
    """Make current_year() available in all templates."""
    return {'current_year': lambda: datetime.now().year}


# =============================================================================
# Authentication
# =============================================================================

def login_required(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def validate_token(token):
    """Validate authentication token and return user if valid."""
    user = query_db(
        'SELECT * FROM users WHERE auth_token = ? AND is_active = 1',
        [token],
        one=True
    )
    return user


# =============================================================================
# Routes - Public
# =============================================================================

@app.route('/')
def index():
    """Home page - recipe listing."""
    # Get all recipes grouped by category
    recipes = query_db('''
        SELECT * FROM current_recipes
        ORDER BY recipe_category, name
    ''')

    # Group by category
    from collections import defaultdict
    by_category = defaultdict(list)
    for recipe in recipes:
        by_category[recipe['recipe_category']].append(recipe)

    return render_template('index.html', by_category=dict(by_category))


@app.route('/recipe/<slug>')
def recipe_detail(slug):
    """View a specific recipe."""
    # Get version number from query param, default to current
    version = request.args.get('v', type=int)

    if version:
        # Get specific version
        recipe = query_db('''
            SELECT rv.*, r.slug
            FROM recipe_versions rv
            JOIN recipes r ON rv.recipe_id = r.id
            WHERE r.slug = ? AND rv.version_number = ?
        ''', [slug, version], one=True)
    else:
        # Get current version
        recipe = query_db('''
            SELECT * FROM current_recipes WHERE slug = ?
        ''', [slug], one=True)

    if not recipe:
        flash('Recipe not found', 'error')
        return redirect(url_for('index'))

    # Get ingredients
    ingredients = query_db('''
        SELECT * FROM recipe_ingredients
        WHERE recipe_version_id = ?
        ORDER BY order_index
    ''', [recipe['version_id']])

    # Get instructions
    instructions = query_db('''
        SELECT * FROM recipe_instructions
        WHERE recipe_version_id = ?
        ORDER BY order_index
    ''', [recipe['version_id']])

    return render_template('recipe.html',
                         recipe=recipe,
                         ingredients=ingredients,
                         instructions=instructions)


@app.route('/search')
def search():
    """Search recipes."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')
    category = request.args.get('category', '')

    if not query and not category:
        return render_template('search.html', recipes=[], query='')

    recipes = []

    if category:
        # Filter by category only
        recipes = query_db('''
            SELECT * FROM current_recipes
            WHERE recipe_category = ?
            ORDER BY name
        ''', [category])
    elif search_type == 'ingredient':
        # Search by ingredient
        recipes = query_db('''
            SELECT DISTINCT r.*
            FROM current_recipes r
            JOIN recipe_ingredients ri ON r.version_id = ri.recipe_version_id
            WHERE ri.ingredient_text LIKE ?
            ORDER BY r.name
        ''', [f'%{query}%'])
    elif search_type == 'author':
        # Search by author
        recipes = query_db('''
            SELECT * FROM current_recipes
            WHERE author LIKE ?
            ORDER BY name
        ''', [f'%{query}%'])
    else:
        # Full-text search
        recipes = query_db('''
            SELECT * FROM current_recipes
            WHERE version_id IN (
                SELECT rowid FROM recipe_versions_fts
                WHERE recipe_versions_fts MATCH ?
            )
            ORDER BY name
        ''', [query])

    return render_template('search.html',
                         recipes=recipes,
                         query=query,
                         search_type=search_type,
                         category=category)


# =============================================================================
# Routes - Authentication
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login with token."""
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        user = validate_token(token)

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['auth_token'] = token

            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid token. Please check your email for the correct link.', 'error')

    # Check if token is in URL (magic link)
    token = request.args.get('token')
    if token:
        user = validate_token(token)
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['auth_token'] = token
            flash(f'Welcome, {user["name"]}!', 'success')
            return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout current user."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# =============================================================================
# Routes - Recipe Management (Auth Required)
# =============================================================================

@app.route('/recipe/new', methods=['GET', 'POST'])
@login_required
def recipe_new():
    """Create a new recipe."""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            author = request.form.get('author', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', '').strip()
            difficulty = request.form.get('difficulty', 'Medium')
            total_time = request.form.get('total_time', '').strip()
            recipe_yield = request.form.get('recipe_yield', '').strip()
            ingredients_text = request.form.get('ingredients', '').strip()
            instructions_text = request.form.get('instructions', '').strip()

            # Validate required fields
            if not name:
                flash('Recipe name is required', 'error')
                return redirect(url_for('recipe_new'))

            # Generate slug
            slug = slugify(name)

            # Check if slug already exists
            existing = query_db('SELECT id FROM recipes WHERE slug = ?', [slug], one=True)
            if existing:
                flash(f'A recipe with this name already exists', 'error')
                return redirect(url_for('recipe_new'))

            # Parse ingredients and instructions
            ingredients = parse_ingredients(ingredients_text)
            instructions = parse_instructions(instructions_text)

            # Build JSON-LD object
            jsonld_data = {
                "@context": "https://schema.org",
                "@type": "Recipe",
                "creativeWorkStatus": "Published",
                "dateCreated": datetime.now().strftime('%Y-%m-%d'),
                "dateModified": datetime.now().strftime('%Y-%m-%d'),
                "datePublished": datetime.now().strftime('%Y-%m-%d'),
                "name": name,
                "recipeCategory": category,
                "author": author,
                "description": description,
                "educationalLevel": difficulty,
                "totalTime": total_time or "TODO",
                "recipeYield": recipe_yield or "TODO",
                "recipeIngredient": [ing['ingredient_text'] for ing in ingredients],
                "recipeInstructions": [inst['instruction_text'] for inst in instructions]
            }

            # Insert recipe
            recipe_id = execute_db(
                'INSERT INTO recipes (slug, created_by_user_id, created_at) VALUES (?, ?, ?)',
                [slug, session['user_id'], datetime.now()]
            )

            # Insert recipe version
            version_id = execute_db('''
                INSERT INTO recipe_versions (
                    recipe_id, version_number, jsonld_data,
                    name, author, description, recipe_category,
                    educational_level, total_time, recipe_yield,
                    creative_work_status, date_created, date_modified,
                    date_published, created_by_user_id, created_at,
                    change_description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                recipe_id, 1, json.dumps(jsonld_data, ensure_ascii=False),
                name, author, description, category,
                difficulty, total_time or "TODO", recipe_yield or "TODO",
                "Published", datetime.now().strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d'),
                session['user_id'], datetime.now(),
                "Initial version"
            ])

            # Update current version pointer
            execute_db(
                'UPDATE recipes SET current_version_id = ? WHERE id = ?',
                [version_id, recipe_id]
            )

            # Insert ingredients
            for idx, ing in enumerate(ingredients):
                execute_db('''
                    INSERT INTO recipe_ingredients (
                        recipe_version_id, order_index, ingredient_text,
                        is_section_header, section_name
                    ) VALUES (?, ?, ?, ?, ?)
                ''', [
                    version_id, idx, ing['ingredient_text'],
                    ing['is_section_header'], ing['section_name']
                ])

            # Insert instructions
            for idx, inst in enumerate(instructions):
                execute_db('''
                    INSERT INTO recipe_instructions (
                        recipe_version_id, order_index, instruction_text, is_note
                    ) VALUES (?, ?, ?, ?)
                ''', [
                    version_id, idx, inst['instruction_text'], inst['is_note']
                ])

            flash(f'Recipe "{name}" created successfully!', 'success')
            return redirect(url_for('recipe_detail', slug=slug))

        except Exception as e:
            flash(f'Error creating recipe: {str(e)}', 'error')
            return redirect(url_for('recipe_new'))

    # GET request - show form
    categories = ['Appetizers', 'Beverages', 'Breads', 'Breakfast', 'Desserts', 'Entrees', 'Salads', 'Sides']
    return render_template('recipe_form.html', recipe=None, categories=categories)


@app.route('/recipe/<slug>/edit', methods=['GET', 'POST'])
@login_required
def recipe_edit(slug):
    """Edit an existing recipe (creates new version)."""
    # Get current recipe
    recipe = query_db('SELECT * FROM current_recipes WHERE slug = ?', [slug], one=True)

    if not recipe:
        flash('Recipe not found', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            author = request.form.get('author', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', '').strip()
            difficulty = request.form.get('difficulty', 'Medium')
            total_time = request.form.get('total_time', '').strip()
            recipe_yield = request.form.get('recipe_yield', '').strip()
            ingredients_text = request.form.get('ingredients', '').strip()
            instructions_text = request.form.get('instructions', '').strip()
            change_description = request.form.get('change_description', '').strip()

            # Validate required fields
            if not name:
                flash('Recipe name is required', 'error')
                return redirect(url_for('recipe_edit', slug=slug))

            # Parse ingredients and instructions
            ingredients = parse_ingredients(ingredients_text)
            instructions = parse_instructions(instructions_text)

            # Build JSON-LD object (preserve original dates, update modified)
            jsonld_data = {
                "@context": "https://schema.org",
                "@type": "Recipe",
                "creativeWorkStatus": "Published",
                "dateCreated": recipe['date_created'],
                "dateModified": datetime.now().strftime('%Y-%m-%d'),
                "datePublished": recipe['date_published'],
                "name": name,
                "recipeCategory": category,
                "author": author,
                "description": description,
                "educationalLevel": difficulty,
                "totalTime": total_time or "TODO",
                "recipeYield": recipe_yield or "TODO",
                "recipeIngredient": [ing['ingredient_text'] for ing in ingredients],
                "recipeInstructions": [inst['instruction_text'] for inst in instructions]
            }

            # Get next version number
            max_version = query_db(
                'SELECT MAX(version_number) as max_v FROM recipe_versions WHERE recipe_id = ?',
                [recipe['recipe_id']],
                one=True
            )
            next_version = (max_version['max_v'] or 0) + 1

            # Insert new recipe version
            version_id = execute_db('''
                INSERT INTO recipe_versions (
                    recipe_id, version_number, jsonld_data,
                    name, author, description, recipe_category,
                    educational_level, total_time, recipe_yield,
                    creative_work_status, date_created, date_modified,
                    date_published, created_by_user_id, created_at,
                    change_description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                recipe['recipe_id'], next_version, json.dumps(jsonld_data, ensure_ascii=False),
                name, author, description, category,
                difficulty, total_time or "TODO", recipe_yield or "TODO",
                "Published", recipe['date_created'],
                datetime.now().strftime('%Y-%m-%d'),
                recipe['date_published'],
                session['user_id'], datetime.now(),
                change_description or f"Updated by {session['user_name']}"
            ])

            # Update current version pointer
            execute_db(
                'UPDATE recipes SET current_version_id = ? WHERE id = ?',
                [version_id, recipe['recipe_id']]
            )

            # Insert ingredients
            for idx, ing in enumerate(ingredients):
                execute_db('''
                    INSERT INTO recipe_ingredients (
                        recipe_version_id, order_index, ingredient_text,
                        is_section_header, section_name
                    ) VALUES (?, ?, ?, ?, ?)
                ''', [
                    version_id, idx, ing['ingredient_text'],
                    ing['is_section_header'], ing['section_name']
                ])

            # Insert instructions
            for idx, inst in enumerate(instructions):
                execute_db('''
                    INSERT INTO recipe_instructions (
                        recipe_version_id, order_index, instruction_text, is_note
                    ) VALUES (?, ?, ?, ?)
                ''', [
                    version_id, idx, inst['instruction_text'], inst['is_note']
                ])

            flash(f'Recipe "{name}" updated successfully! (Version {next_version})', 'success')
            return redirect(url_for('recipe_detail', slug=slug))

        except Exception as e:
            flash(f'Error updating recipe: {str(e)}', 'error')
            return redirect(url_for('recipe_edit', slug=slug))

    # GET request - show form with current data
    ingredients = query_db('''
        SELECT * FROM recipe_ingredients
        WHERE recipe_version_id = ?
        ORDER BY order_index
    ''', [recipe['version_id']])

    instructions = query_db('''
        SELECT * FROM recipe_instructions
        WHERE recipe_version_id = ?
        ORDER BY order_index
    ''', [recipe['version_id']])

    # Convert ingredients/instructions to text
    ingredients_text = '\n'.join([ing['ingredient_text'] for ing in ingredients])
    instructions_text = '\n'.join([inst['instruction_text'] for inst in instructions])

    categories = ['Appetizers', 'Beverages', 'Breads', 'Breakfast', 'Desserts', 'Entrees', 'Salads', 'Sides']

    return render_template('recipe_form.html',
                         recipe=recipe,
                         ingredients_text=ingredients_text,
                         instructions_text=instructions_text,
                         categories=categories)


@app.route('/recipe/<slug>/history')
def recipe_history(slug):
    """View version history for a recipe."""
    # Get all versions
    versions = query_db('''
        SELECT * FROM recipe_history
        WHERE slug = ?
        ORDER BY version_number DESC
    ''', [slug])

    if not versions:
        flash('Recipe not found', 'error')
        return redirect(url_for('index'))

    recipe_name = versions[0]['name']

    return render_template('history.html',
                         recipe_name=recipe_name,
                         slug=slug,
                         versions=versions)


# =============================================================================
# Run Application
# =============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
