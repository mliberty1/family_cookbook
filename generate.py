# Copyright 2023 Matthew Liberty
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
import json
import re
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader


_MYPATH = os.path.dirname(__file__)
_BUILD = os.path.join(_MYPATH, 'build')
_HTML = os.path.join(_BUILD, 'html')
_TEMPLATE_DIR = os.path.join(_MYPATH, 'html')


def _format_duration(duration_str):
    """Convert ISO 8601 duration (e.g., PT30M) to human-readable format."""
    if not duration_str or duration_str == 'TODO':
        return 'Not specified'

    # Parse ISO 8601 duration format (PT#H#M)
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


def _slugify(text):
    """Convert recipe name to URL-friendly filename."""
    # Remove special characters and replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def _generate():
    # Load recipes
    with open(os.path.join(_MYPATH, 'cookbook.jsonld'), 'rt', encoding='utf-8') as src:
        recipes = json.load(src)

    # Setup output directory
    shutil.rmtree(_HTML, ignore_errors=True)
    os.makedirs(_HTML, exist_ok=True)

    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
    env.filters['format_duration'] = _format_duration

    # Load templates
    recipe_template = env.get_template('recipe.html')
    index_template = env.get_template('index.html')

    # Copy CSS files
    shutil.copy(
        os.path.join(_TEMPLATE_DIR, 'style.css'),
        os.path.join(_HTML, 'style.css')
    )
    shutil.copy(
        os.path.join(_TEMPLATE_DIR, 'print.css'),
        os.path.join(_HTML, 'print.css')
    )

    # Generate individual recipe pages
    recipes_with_filenames = []
    for recipe in recipes:
        # Create filename from recipe name
        filename = _slugify(recipe['name']) + '.html'
        recipe['filename'] = filename
        recipes_with_filenames.append(recipe)

        # Render recipe page
        html_content = recipe_template.render(
            recipe=recipe,
            json_ld=json.dumps(recipe, indent=2)
        )

        # Write recipe file
        output_path = os.path.join(_HTML, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Generated: {filename}")

    # Organize recipes by category for index page
    recipes_by_category = defaultdict(list)
    for recipe in recipes_with_filenames:
        category = recipe.get('recipeCategory', 'Uncategorized')
        recipes_by_category[category].append(recipe)

    # Sort categories and recipes
    category_order = ['Breakfast', 'Appetizers', 'Salads', 'Sides', 'Entrees', 'Breads', 'Desserts', 'Beverages']
    sorted_categories = {}

    for category in category_order:
        if category in recipes_by_category:
            sorted_categories[category] = sorted(
                recipes_by_category[category],
                key=lambda r: r['name']
            )

    # Add any categories not in the predefined order
    for category in sorted(recipes_by_category.keys()):
        if category not in sorted_categories:
            sorted_categories[category] = sorted(
                recipes_by_category[category],
                key=lambda r: r['name']
            )

    # Generate index page
    index_content = index_template.render(
        recipe_count=len(recipes),
        recipes_by_category=sorted_categories
    )

    with open(os.path.join(_HTML, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_content)

    print(f"\nGenerated index.html with {len(recipes)} recipes across {len(sorted_categories)} categories")
    print(f"Output directory: {_HTML}")


if __name__ == '__main__':
    _generate()
