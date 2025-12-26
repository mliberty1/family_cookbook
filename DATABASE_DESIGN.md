# Family Cookbook Database Design

## Overview

This database schema supports a versioned recipe management system with:
- Full preservation of your extended JSON-LD recipe schema
- Complete version history (never delete old data)
- Token-based user authentication
- Advanced search capabilities (by author, ingredient, full-text)

## Schema Architecture

### Hybrid Approach: JSON-LD + Relational

The schema uses a **hybrid storage model** that balances flexibility with queryability:

1. **Complete JSON-LD Storage**: The full Schema.org Recipe object is stored as-is in `recipe_versions.jsonld_data`
   - Preserves all data including future extensions
   - Source of truth for generating HTML/exports
   - No risk of data loss from schema changes

2. **Denormalized Search Columns**: Key fields are also stored as table columns
   - Enables fast SQL queries without parsing JSON
   - Supports indexed searches on common fields (name, author, category)
   - Powers sorting, filtering, and aggregation

3. **Normalized Ingredient/Instruction Tables**: Arrays are broken out into separate tables
   - Enables searching within ingredients ("find recipes with eggs")
   - Preserves order and special formatting (section headers, notes)
   - SQLite FTS5 for full-text search

## Core Tables

### `users` Table
Stores family members who can edit recipes.

**Key Features:**
- `auth_token`: UUID-based token for passwordless authentication
  - You email these tokens to users as magic links
  - Example: `https://cookbook.family/recipes?token=abc123...`
- `is_active`: Soft delete without losing attribution
- No password storage or complex auth flows

**Sample Data:**
```sql
INSERT INTO users (name, email, auth_token) VALUES
  ('Diana Liberty', 'diana@example.com', 'uuid-diana-123'),
  ('Matt Herman', 'matt@example.com', 'uuid-matt-456');
```

### `recipes` Table
The canonical recipe entity with minimal metadata.

**Key Features:**
- `slug`: URL-friendly identifier (e.g., `buttermilk-ebleskiver`)
  - Generated from recipe name using the existing `_slugify()` function
  - Immutable - doesn't change even if recipe name changes
- `current_version_id`: Points to the "live" published version
  - Enables draft versions without affecting public view
  - Can be null for unpublished recipes

### `recipe_versions` Table
**The heart of the versioning system.** Every edit creates a new row here.

**Key Features:**
- `version_number`: Sequential per recipe (1, 2, 3, ...)
  - Allows URLs like `/recipe/slug?v=3` to view old versions
  - History view shows all versions in timeline
- `jsonld_data`: Complete JSON-LD object as TEXT
  - Includes all Schema.org fields: `@context`, `@type`, etc.
  - Your custom extensions: ingredient grouping (`## Section`), notes (`🛈 `)
  - Can be parsed back to Python dict with `json.loads()`

**Denormalized Fields:**
These duplicate data from `jsonld_data` for query performance:
- `name`, `author`, `description`: Full-text searchable
- `recipe_category`: Filter/group by type
- `educational_level`: Search by difficulty
- `total_time`, `recipe_yield`: Display in lists without parsing JSON

**Version Metadata:**
- `created_by_user_id`: Who made this edit (FK to `users`)
- `created_at`: When this version was saved
- `change_description`: Optional note like "Fixed typo in step 3"

**Original Recipe Dates** (from legacy data):
- `date_created`: Original creation date (e.g., "1997-12-21")
- `date_modified`: Last modified in legacy system
- `date_published`: Publication date
- These are preserved as-is from your current `cookbook.jsonld`

### `recipe_ingredients` Table
Normalized ingredient list for advanced search.

**Key Features:**
- `order_index`: Preserves display order (0, 1, 2, ...)
- `is_section_header`: Identifies grouping headers
  - Example: `"## Cake"` → `is_section_header=1, section_name="Cake"`
  - Example: `"1 package yellow cake mix"` → `is_section_header=0`
- `ingredient_text`: Full text including quantities
- Enables queries like: "Find all recipes with eggs" → `WHERE ingredient_text LIKE '%egg%'`

**Rendering Logic:**
```python
# Reconstruct ingredient list with sections
for ingredient in sorted_ingredients:
    if ingredient.is_section_header:
        print(f"<h4>{ingredient.section_name}</h4>")
    else:
        print(f"<li>{ingredient.ingredient_text}</li>")
```

### `recipe_instructions` Table
Normalized instruction list.

**Key Features:**
- `order_index`: Preserves step order
- `is_note`: Identifies instructions starting with `🛈 `
  - These are rendered as info boxes, not numbered steps
  - Example: `"🛈 Requires an ebleskiver pan."` → `is_note=1`

**Rendering Logic:**
```python
steps = [i for i in instructions if not i.is_note]
notes = [i for i in instructions if i.is_note]

# Render numbered steps
for idx, step in enumerate(steps, 1):
    print(f"{idx}. {step.instruction_text}")

# Render notes separately
if notes:
    print("<div class='recipe-notes'>")
    for note in notes:
        print(f"<p>ℹ️ {note.instruction_text.replace('🛈 ', '')}</p>")
    print("</div>")
```

## Full-Text Search

### SQLite FTS5 Virtual Tables
The schema includes FTS5 indexes for fast full-text search:

1. **`recipe_versions_fts`**: Search recipe names, authors, descriptions
   ```sql
   SELECT * FROM current_recipes
   WHERE version_id IN (
       SELECT rowid FROM recipe_versions_fts
       WHERE recipe_versions_fts MATCH 'chocolate cake'
   );
   ```

2. **`recipe_ingredients_fts`**: Search within ingredients
   ```sql
   SELECT DISTINCT r.*
   FROM current_recipes r
   JOIN recipe_ingredients ri ON r.version_id = ri.recipe_version_id
   WHERE ri.id IN (
       SELECT rowid FROM recipe_ingredients_fts
       WHERE recipe_ingredients_fts MATCH 'buttermilk'
   );
   ```

**FTS5 Features:**
- Phrase search: `"cream cheese"` (exact match)
- Boolean operators: `chocolate AND NOT white`
- Prefix search: `butter*` matches buttermilk, butterscotch, etc.
- Ranking: Results ordered by relevance

### Auto-Sync Triggers
The schema includes triggers to keep FTS indexes synchronized:
- `recipe_versions_fts_insert/update/delete`
- `recipe_ingredients_fts_insert/update/delete`

You never need to manually update the FTS tables - they stay in sync automatically.

## Views for Common Queries

### `current_recipes` View
Shows only the current (published) version of each recipe with denormalized user info.

**Use Cases:**
- Main recipe listing page
- Category browsing
- Search results

**Sample Query:**
```sql
-- Get all breakfast recipes
SELECT * FROM current_recipes
WHERE recipe_category = 'Breakfast'
ORDER BY name;

-- Get recipes by a specific author
SELECT * FROM current_recipes
WHERE author = 'Diana Liberty';
```

### `recipe_history` View
Shows all versions of all recipes with edit metadata.

**Use Cases:**
- Recipe history timeline
- "Who edited this?" attribution
- Audit trail

**Sample Query:**
```sql
-- Get edit history for a specific recipe
SELECT version_number, name, edited_by_user_name, version_created_at, change_description
FROM recipe_history
WHERE slug = 'buttermilk-ebleskiver'
ORDER BY version_number DESC;
```

## Versioning Workflow

### Creating a New Recipe
```sql
-- 1. Insert recipe shell
INSERT INTO recipes (slug, created_by_user_id)
VALUES ('new-recipe-slug', 1);

-- 2. Insert first version
INSERT INTO recipe_versions (
    recipe_id, version_number, jsonld_data, name, author, ..., created_by_user_id
) VALUES (
    last_insert_rowid(), 1, '{"@context": ...}', 'New Recipe', 'Author', ..., 1
);

-- 3. Update current version pointer
UPDATE recipes
SET current_version_id = last_insert_rowid()
WHERE id = <recipe_id>;

-- 4. Insert ingredients
INSERT INTO recipe_ingredients (recipe_version_id, order_index, ingredient_text, is_section_header)
VALUES (<version_id>, 0, '## Cake', 1),
       (<version_id>, 1, '1 cup flour', 0),
       ...;

-- 5. Insert instructions
INSERT INTO recipe_instructions (recipe_version_id, order_index, instruction_text, is_note)
VALUES (<version_id>, 0, 'Preheat oven to 350°', 0),
       ...;
```

### Editing an Existing Recipe
```sql
-- 1. Get current version number
SELECT MAX(version_number) FROM recipe_versions WHERE recipe_id = <id>;

-- 2. Insert new version (version_number = old + 1)
INSERT INTO recipe_versions (
    recipe_id, version_number, jsonld_data, ..., created_by_user_id, change_description
) VALUES (
    <recipe_id>, <old_version + 1>, '{"@context": ...}', ..., <user_id>, 'Fixed ingredient quantities'
);

-- 3. Update current version pointer
UPDATE recipes
SET current_version_id = last_insert_rowid()
WHERE id = <recipe_id>;

-- 4. Insert new ingredients/instructions for this version
-- (old version's ingredients/instructions remain unchanged via recipe_version_id FK)
```

### Viewing Old Versions
```sql
-- Get version 2 of a recipe
SELECT * FROM recipe_versions
WHERE recipe_id = (SELECT id FROM recipes WHERE slug = 'buttermilk-ebleskiver')
AND version_number = 2;

-- Get ingredients for that version
SELECT * FROM recipe_ingredients
WHERE recipe_version_id = <version_id>
ORDER BY order_index;
```

## Migration from JSON-LD

The existing `cookbook.jsonld` will be migrated with this approach:

1. **Create system user**: `INSERT INTO users (...) VALUES ('System', 'system@cookbook', 'migration-token')`

2. **For each recipe in `cookbook.jsonld`**:
   - Extract `name` → generate `slug` via `_slugify(name)`
   - Insert into `recipes` table
   - Insert into `recipe_versions` (version_number=1)
     - Store full JSON object in `jsonld_data`
     - Extract denormalized fields (name, author, description, etc.)
     - Use `author` from JSON-LD as `author` column
     - Use system user as `created_by_user_id`
     - Copy dates: `dateCreated` → `date_created`, etc.
   - Parse `recipeIngredient` array:
     - If item starts with `## ` → `is_section_header=1, section_name=<text without ##>`
     - Else → `is_section_header=0, ingredient_text=<text>`
   - Parse `recipeInstructions` array:
     - If item starts with `🛈 ` → `is_note=1`
     - Else → `is_note=0`
   - Update `recipes.current_version_id` to point to new version

3. **Preserve all legacy dates**: The `date_created`, `date_modified`, `date_published` fields keep original values from 1997+

## Search Capabilities

### 1. Search by Recipe Author
```sql
SELECT * FROM current_recipes
WHERE author = 'Diana Liberty';
```

### 2. Search by User Editor
```sql
SELECT * FROM current_recipes
WHERE version_created_by_name = 'Matt Herman';
```

### 3. Search by Ingredient
```sql
-- Simple LIKE search
SELECT DISTINCT r.*
FROM current_recipes r
JOIN recipe_ingredients ri ON r.version_id = ri.recipe_version_id
WHERE ri.ingredient_text LIKE '%buttermilk%';

-- FTS5 full-text search (better for multiple words)
SELECT DISTINCT r.*
FROM current_recipes r
JOIN recipe_ingredients ri ON r.version_id = ri.recipe_version_id
WHERE ri.id IN (
    SELECT rowid FROM recipe_ingredients_fts
    WHERE recipe_ingredients_fts MATCH 'cream cheese'
);
```

### 4. Full-Text Search Across Recipe Content
```sql
-- Search names, descriptions, authors
SELECT * FROM current_recipes
WHERE version_id IN (
    SELECT rowid FROM recipe_versions_fts
    WHERE recipe_versions_fts MATCH 'danish pancake'
);
```

### 5. Combined Search (Ingredients + Content)
```sql
-- Find chocolate recipes that use eggs
SELECT DISTINCT r.*
FROM current_recipes r
WHERE r.version_id IN (
    SELECT rowid FROM recipe_versions_fts
    WHERE recipe_versions_fts MATCH 'chocolate'
)
AND r.version_id IN (
    SELECT recipe_version_id FROM recipe_ingredients ri
    WHERE ri.id IN (
        SELECT rowid FROM recipe_ingredients_fts
        WHERE recipe_ingredients_fts MATCH 'eggs'
    )
);
```

### 6. Filter by Category + Search
```sql
SELECT * FROM current_recipes
WHERE recipe_category = 'Desserts'
AND version_id IN (
    SELECT rowid FROM recipe_versions_fts
    WHERE recipe_versions_fts MATCH 'cake'
)
ORDER BY name;
```

## Design Trade-offs

### Why Store Both JSON-LD and Denormalized Columns?

**Pros:**
- **JSON-LD**: Future-proof, preserves all data, easy to export
- **Columns**: Fast queries, indexes, joins, standard SQL tools

**Cons:**
- **Duplication**: Same data stored twice
- **Consistency**: Must keep in sync (handled by application layer)

**Decision:** Worth it for performance + flexibility. The duplication is minimal (text is cheap), and consistency is managed at write time.

### Why Separate Ingredient/Instruction Tables?

**Alternative:** Store as JSON arrays in `jsonld_data` only.

**Pros of Normalization:**
- **Searchability**: `WHERE ingredient LIKE '%eggs%'` is fast and simple
- **FTS5**: Full-text search on ingredients
- **Order Preservation**: `order_index` ensures display order
- **Metadata**: `is_section_header`, `is_note` flags enable custom rendering

**Cons:**
- **More Tables**: Slightly more complex queries
- **More Rows**: 92 recipes × ~10 ingredients = ~900 rows

**Decision:** The search benefits outweigh the complexity. Family members want "find recipes with chocolate" to be fast and accurate.

### Why Not Use JSON1 Extension for Querying JSON?

SQLite's `json_extract()` can query JSON directly:
```sql
SELECT * FROM recipe_versions
WHERE json_extract(jsonld_data, '$.author') = 'Diana Liberty';
```

**Why we don't rely on this:**
- **No Indexes**: Can't create indexes on JSON fields (slow full table scans)
- **No FTS**: Full-text search doesn't work on JSON values
- **Complex Queries**: Nested arrays require recursive CTEs
- **Performance**: Parsing JSON on every query is slower than indexed columns

**Decision:** Use `jsonld_data` for complete exports/display, use denormalized columns for queries.

## Next Steps

1. **Create Database**: Run `schema.sql` to create `cookbook.db`
2. **Migration Script**: Write Python script to load `cookbook.jsonld` into database
3. **Web Application**: Build Flask/FastAPI app with:
   - Token authentication middleware
   - Recipe CRUD endpoints
   - Search API
   - Version history UI
4. **Admin Interface**: Manual user management (INSERT INTO users)
5. **Testing**: Verify all 92 recipes migrate correctly

## Sample Data Verification

After migration, verify with:
```sql
-- Should return 92
SELECT COUNT(*) FROM recipes;

-- Should return 92 (all version 1 initially)
SELECT COUNT(*) FROM recipe_versions;

-- Should show all categories
SELECT DISTINCT recipe_category, COUNT(*) FROM current_recipes GROUP BY recipe_category;

-- Should show ingredient sections
SELECT * FROM recipe_ingredients
WHERE recipe_version_id = (
    SELECT current_version_id FROM recipes WHERE slug = 'cheese-streusel-coffee-cake'
)
ORDER BY order_index;
```
