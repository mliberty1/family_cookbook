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
import os
from datetime import datetime
from functools import wraps

import requests
from jinja2 import Template
from email_validator import validate_email, EmailNotValidError

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, g, flash, jsonify, send_file
)


# =============================================================================
# App Configuration
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Database configuration - handle both local and production
database_url = os.environ.get('DATABASE_URL', 'sqlite:///cookbook.db')
if database_url.startswith('sqlite:///'):
    # Extract path from sqlite:///path format
    app.config['DATABASE'] = database_url.replace('sqlite:///', '')
else:
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


def admin_required(f):
    """Decorator to require admin permissions for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))

        user = query_db('SELECT is_admin FROM users WHERE id = ?', [session['user_id']], one=True)
        if not user or not user['is_admin']:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)
    return decorated_function


def sanitize_name(name):
    """Sanitize name to prevent email header injection."""
    if not name:
        return ""
    # Remove newlines and other control characters
    return re.sub(r'[\r\n\t]', '', name)


def send_user_email(user, base_url, subject, body_template):
    """Send email to a user using Mailgun API.

    Args:
        user: User dict with 'name', 'email', and 'auth_token' keys
        base_url: Base URL for the application
        subject: Email subject line
        body_template: Email body as Jinja2 template string.
                      Supports {{ login_url }} and {{ display_name }} variables.

    Returns:
        requests.Response object
    """
    api_key = os.environ.get('MAILGUN_API_KEY')
    if not api_key:
        raise ValueError('MAILGUN_API_KEY environment variable not set')

    mailgun_domain = os.environ.get('MAILGUN_DOMAIN')
    if not mailgun_domain:
        raise ValueError('MAILGUN_DOMAIN environment variable not set')

    email_from = os.environ.get('EMAIL_FROM')
    if not email_from:
        raise ValueError('EMAIL_FROM environment variable not set')

    # Sanitize names to prevent email header injection
    display_name = sanitize_name(user.get('name', user.get('display_name', '')))
    user_name = sanitize_name(user['name'])

    login_url = f"{base_url}/login?token={user['auth_token']}"

    # Render body template with Jinja2
    template = Template(body_template)
    email_body = template.render(
        login_url=login_url,
        display_name=display_name
    )

    response = requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", api_key),
        data={
            "from": email_from,
            "to": f"{user_name} <{user['email']}>",
            "subject": subject,
            "text": email_body
        }
    )

    return response


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
            SELECT rv.*, rv.id AS version_id, r.slug, r.id AS recipe_id
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
            session['is_admin'] = bool(user['is_admin'])

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
            session['is_admin'] = bool(user['is_admin'])
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
# Routes - Admin Panel
# =============================================================================

@app.route('/admin')
@admin_required
def admin_panel():
    """Admin panel home."""
    users = query_db('SELECT * FROM users ORDER BY created_at DESC')
    user_count = len(users)
    active_count = len([u for u in users if u['is_active']])
    admin_count = len([u for u in users if u['is_admin']])

    return render_template('admin/index.html',
                         users=users,
                         user_count=user_count,
                         active_count=active_count,
                         admin_count=admin_count)


@app.route('/admin/users')
@admin_required
def admin_users():
    """Manage users."""
    users = query_db('SELECT * FROM users ORDER BY created_at DESC')
    return render_template('admin/users.html', users=users)


@app.route('/admin/user/add', methods=['GET', 'POST'])
@admin_required
def admin_user_add():
    """Add a new user."""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            is_admin = request.form.get('is_admin') == 'on'

            # Validate
            if not name:
                flash('Name is required', 'error')
                return redirect(url_for('admin_user_add'))

            if not email:
                flash('Email is required', 'error')
                return redirect(url_for('admin_user_add'))

            # Validate email format
            try:
                validate_email(email)
            except EmailNotValidError as e:
                flash(f'Invalid email address: {str(e)}', 'error')
                return redirect(url_for('admin_user_add'))

            # Check if email already exists
            existing = query_db('SELECT id FROM users WHERE email = ?', [email], one=True)
            if existing:
                flash('A user with this email already exists', 'error')
                return redirect(url_for('admin_user_add'))

            # Generate token
            auth_token = str(uuid.uuid4())

            # Insert user
            user_id = execute_db('''
                INSERT INTO users (name, email, auth_token, is_admin, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [name, email, auth_token, is_admin, 1, datetime.now()])

            flash(f'User "{name}" created successfully!', 'success')
            return redirect(url_for('admin_user_detail', user_id=user_id))

        except Exception as e:
            flash(f'Error creating user: {str(e)}', 'error')
            return redirect(url_for('admin_user_add'))

    return render_template('admin/user_form.html', user=None)


@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    """View user details."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)

    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))

    # Get base URL for login link
    base_url = request.url_root.rstrip('/')
    login_url = f"{base_url}/login?token={user['auth_token']}"

    return render_template('admin/user_detail.html', user=user, login_url=login_url)


@app.route('/admin/user/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def admin_user_toggle_active(user_id):
    """Toggle user active status."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)

    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))

    # Don't allow disabling yourself
    if user_id == session['user_id']:
        flash('You cannot deactivate your own account', 'error')
        return redirect(url_for('admin_user_detail', user_id=user_id))

    new_status = not user['is_active']
    execute_db('UPDATE users SET is_active = ? WHERE id = ?', [new_status, user_id])

    status_text = 'activated' if new_status else 'deactivated'
    flash(f'User "{user["name"]}" {status_text}', 'success')
    return redirect(url_for('admin_user_detail', user_id=user_id))


@app.route('/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_user_toggle_admin(user_id):
    """Toggle user admin status."""
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)

    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))

    # Don't allow removing your own admin permissions
    if user_id == session['user_id']:
        flash('You cannot remove your own admin permissions', 'error')
        return redirect(url_for('admin_user_detail', user_id=user_id))

    new_status = not user['is_admin']
    execute_db('UPDATE users SET is_admin = ? WHERE id = ?', [new_status, user_id])

    status_text = 'granted' if new_status else 'revoked'
    flash(f'Admin permissions {status_text} for "{user["name"]}"', 'success')
    return redirect(url_for('admin_user_detail', user_id=user_id))


@app.route('/admin/email', methods=['GET', 'POST'])
@admin_required
def admin_email_users():
    """Send emails to users."""
    users = query_db('SELECT * FROM users WHERE is_active = 1 ORDER BY name')

    if request.method == 'POST':
        try:
            subject = request.form.get('subject', '').strip()
            body_template = request.form.get('body', '').strip()
            target_users = request.form.getlist('users')

            # Validate
            if not subject:
                flash('Subject is required', 'error')
                return redirect(url_for('admin_email_users'))

            if not body_template:
                flash('Email body is required', 'error')
                return redirect(url_for('admin_email_users'))

            if not target_users:
                flash('Please select at least one user', 'error')
                return redirect(url_for('admin_email_users'))

            # Get base URL
            base_url = request.url_root.rstrip('/')

            # Send emails
            success_count = 0
            error_count = 0
            errors = []

            for user_id in target_users:
                user = query_db('SELECT * FROM users WHERE id = ?', [int(user_id)], one=True)
                if not user or not user['is_active']:
                    continue

                if not user['email']:
                    errors.append(f"{user['name']}: No email address")
                    error_count += 1
                    continue

                try:
                    response = send_user_email(user, base_url, subject, body_template)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        errors.append(f"{user['name']}: {response.text}")
                        error_count += 1
                except Exception as e:
                    errors.append(f"{user['name']}: {str(e)}")
                    error_count += 1

            # Show results
            if success_count > 0:
                flash(f'Successfully sent {success_count} email(s)', 'success')

            if error_count > 0:
                flash(f'Failed to send {error_count} email(s)', 'error')
                for error in errors[:5]:  # Show first 5 errors
                    flash(f'  • {error}', 'error')

            return redirect(url_for('admin_email_users'))

        except Exception as e:
            flash(f'Error sending emails: {str(e)}', 'error')
            return redirect(url_for('admin_email_users'))

    # Default email template
    default_template = """Hello {{ display_name }},

You've been invited to access the Family Cookbook!

Click here to login:
{{ login_url }}

This link is unique to you and will log you in automatically.

Enjoy the recipes!
"""

    return render_template('admin/email.html',
                         users=users,
                         default_template=default_template)


@app.route('/admin/backup')
@admin_required
def admin_backup_database():
    """Download database backup as SQL export."""
    try:
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        download_name = f'family_cookbook_backup_{timestamp}.sql'

        # Create SQL dump
        conn = sqlite3.connect(app.config['DATABASE'])

        # Generate SQL dump
        sql_dump = '\n'.join(conn.iterdump())

        conn.close()

        # Create temporary file with SQL dump
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sql', encoding='utf-8')
        temp_file.write(sql_dump)
        temp_file.close()

        # Send the SQL file and delete after sending
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=download_name,
            mimetype='text/plain'
        )
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'error')
        return redirect(url_for('admin_panel'))


# =============================================================================
# Run Application
# =============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
