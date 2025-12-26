-- Family Cookbook Database Schema
-- SQLite database schema with full JSON-LD support and versioning
--
-- Design Principles:
-- 1. Never delete data - all changes create new versions
-- 2. Full JSON-LD preserved in jsonld_data column
-- 3. Denormalized searchable fields for performance
-- 4. Token-based authentication (no passwords)
-- 5. Support for ingredient grouping and instruction notes

-- =============================================================================
-- USERS TABLE
-- =============================================================================
-- Stores family members who can view/edit recipes
-- Authentication via email-distributed tokens (no password needed)
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                    -- Display name (e.g., "Diana Liberty")
    email TEXT UNIQUE NOT NULL,            -- For sending auth links
    auth_token TEXT UNIQUE NOT NULL,       -- UUID for URL-based auth
    is_active BOOLEAN DEFAULT 1,           -- Soft delete for users
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_auth_token ON users(auth_token);
CREATE INDEX idx_users_email ON users(email);

-- =============================================================================
-- RECIPES TABLE
-- =============================================================================
-- Core recipe metadata and current version pointer
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,             -- URL-friendly name (e.g., "buttermilk-ebleskiver")
    current_version_id INTEGER,            -- FK to recipe_versions (latest published version)
    created_by_user_id INTEGER NOT NULL,   -- FK to users (original creator)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (created_by_user_id) REFERENCES users(id),
    FOREIGN KEY (current_version_id) REFERENCES recipe_versions(id)
);

CREATE INDEX idx_recipes_slug ON recipes(slug);
CREATE INDEX idx_recipes_created_by ON recipes(created_by_user_id);

-- =============================================================================
-- RECIPE_VERSIONS TABLE
-- =============================================================================
-- Stores complete version history of each recipe
-- Each edit creates a new version row (never delete/update existing versions)
CREATE TABLE recipe_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,            -- FK to recipes
    version_number INTEGER NOT NULL,       -- 1, 2, 3, etc. (increments per recipe)

    -- Full JSON-LD data (source of truth, preserves everything)
    jsonld_data TEXT NOT NULL,             -- Complete Schema.org Recipe JSON object

    -- Denormalized fields from JSON-LD for efficient searching/querying
    -- (These are redundant with jsonld_data but enable fast SQL queries)
    name TEXT NOT NULL,                    -- Recipe name
    author TEXT,                           -- Recipe author (not system user, e.g., "Den Mattingly")
    description TEXT,                      -- Short description
    recipe_category TEXT,                  -- Breakfast, Desserts, Entrees, etc.
    educational_level TEXT,                -- Easy, Medium, Hard
    total_time TEXT,                       -- ISO 8601 duration (e.g., "PT30M")
    recipe_yield TEXT,                     -- Servings or quantity
    creative_work_status TEXT,             -- Published, Draft, etc.

    -- Original recipe dates (from legacy data)
    date_created TEXT,                     -- When recipe was originally created
    date_modified TEXT,                    -- Last modification date
    date_published TEXT,                   -- When published

    -- Version metadata
    created_by_user_id INTEGER NOT NULL,   -- FK to users (who created this version)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When this version was created
    change_description TEXT,               -- Optional: user-provided change notes

    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id),
    UNIQUE(recipe_id, version_number)
);

CREATE INDEX idx_recipe_versions_recipe_id ON recipe_versions(recipe_id);
CREATE INDEX idx_recipe_versions_created_by ON recipe_versions(created_by_user_id);
CREATE INDEX idx_recipe_versions_name ON recipe_versions(name);
CREATE INDEX idx_recipe_versions_author ON recipe_versions(author);
CREATE INDEX idx_recipe_versions_category ON recipe_versions(recipe_category);
CREATE INDEX idx_recipe_versions_created_at ON recipe_versions(created_at);

-- Full-text search virtual table for recipe content
CREATE VIRTUAL TABLE recipe_versions_fts USING fts5(
    name,
    author,
    description,
    content=recipe_versions,
    content_rowid=id
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER recipe_versions_fts_insert AFTER INSERT ON recipe_versions BEGIN
    INSERT INTO recipe_versions_fts(rowid, name, author, description)
    VALUES (new.id, new.name, new.author, new.description);
END;

CREATE TRIGGER recipe_versions_fts_delete AFTER DELETE ON recipe_versions BEGIN
    DELETE FROM recipe_versions_fts WHERE rowid = old.id;
END;

CREATE TRIGGER recipe_versions_fts_update AFTER UPDATE ON recipe_versions BEGIN
    DELETE FROM recipe_versions_fts WHERE rowid = old.id;
    INSERT INTO recipe_versions_fts(rowid, name, author, description)
    VALUES (new.id, new.name, new.author, new.description);
END;

-- =============================================================================
-- RECIPE_INGREDIENTS TABLE
-- =============================================================================
-- Normalized ingredient list for each recipe version
-- Enables searching by ingredient and preserves ingredient grouping
CREATE TABLE recipe_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_version_id INTEGER NOT NULL,    -- FK to recipe_versions
    order_index INTEGER NOT NULL,          -- Position in ingredient list (0, 1, 2, ...)
    ingredient_text TEXT NOT NULL,         -- Full text (e.g., "3 eggs, separated")
    is_section_header BOOLEAN DEFAULT 0,   -- True if starts with "## " (grouping header)
    section_name TEXT,                     -- If is_section_header, the section name without "## "

    FOREIGN KEY (recipe_version_id) REFERENCES recipe_versions(id) ON DELETE CASCADE
);

CREATE INDEX idx_recipe_ingredients_version_id ON recipe_ingredients(recipe_version_id);
CREATE INDEX idx_recipe_ingredients_text ON recipe_ingredients(ingredient_text);

-- Full-text search for ingredients
CREATE VIRTUAL TABLE recipe_ingredients_fts USING fts5(
    ingredient_text,
    content=recipe_ingredients,
    content_rowid=id
);

CREATE TRIGGER recipe_ingredients_fts_insert AFTER INSERT ON recipe_ingredients BEGIN
    INSERT INTO recipe_ingredients_fts(rowid, ingredient_text)
    VALUES (new.id, new.ingredient_text);
END;

CREATE TRIGGER recipe_ingredients_fts_delete AFTER DELETE ON recipe_ingredients BEGIN
    DELETE FROM recipe_ingredients_fts WHERE rowid = old.id;
END;

CREATE TRIGGER recipe_ingredients_fts_update AFTER UPDATE ON recipe_ingredients BEGIN
    DELETE FROM recipe_ingredients_fts WHERE rowid = old.id;
    INSERT INTO recipe_ingredients_fts(rowid, ingredient_text)
    VALUES (new.id, new.ingredient_text);
END;

-- =============================================================================
-- RECIPE_INSTRUCTIONS TABLE
-- =============================================================================
-- Normalized instruction list for each recipe version
-- Preserves instruction notes (items starting with "🛈 ")
CREATE TABLE recipe_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_version_id INTEGER NOT NULL,    -- FK to recipe_versions
    order_index INTEGER NOT NULL,          -- Position in instruction list (0, 1, 2, ...)
    instruction_text TEXT NOT NULL,        -- Full instruction text
    is_note BOOLEAN DEFAULT 0,             -- True if starts with "🛈 " (info note)

    FOREIGN KEY (recipe_version_id) REFERENCES recipe_versions(id) ON DELETE CASCADE
);

CREATE INDEX idx_recipe_instructions_version_id ON recipe_instructions(recipe_version_id);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- View for current (published) recipe versions with all metadata
CREATE VIEW current_recipes AS
SELECT
    r.id AS recipe_id,
    r.slug,
    r.created_at AS recipe_created_at,
    rv.id AS version_id,
    rv.version_number,
    rv.name,
    rv.author,
    rv.description,
    rv.recipe_category,
    rv.educational_level,
    rv.total_time,
    rv.recipe_yield,
    rv.creative_work_status,
    rv.jsonld_data,
    rv.created_at AS version_created_at,
    rv.created_by_user_id AS version_created_by_user_id,
    u.name AS version_created_by_name,
    creator.name AS recipe_created_by_name
FROM recipes r
JOIN recipe_versions rv ON r.current_version_id = rv.id
LEFT JOIN users u ON rv.created_by_user_id = u.id
LEFT JOIN users creator ON r.created_by_user_id = creator.id;

-- View for all recipe versions with edit history
CREATE VIEW recipe_history AS
SELECT
    r.id AS recipe_id,
    r.slug,
    rv.id AS version_id,
    rv.version_number,
    rv.name,
    rv.author,
    rv.description,
    rv.recipe_category,
    rv.created_at AS version_created_at,
    rv.change_description,
    u.name AS edited_by_user_name,
    u.email AS edited_by_user_email
FROM recipes r
JOIN recipe_versions rv ON r.id = rv.recipe_id
LEFT JOIN users u ON rv.created_by_user_id = u.id
ORDER BY r.id, rv.version_number DESC;

-- =============================================================================
-- SAMPLE QUERIES
-- =============================================================================

-- Find all recipes by a specific recipe author (e.g., "Diana Liberty")
-- SELECT * FROM current_recipes WHERE author = 'Diana Liberty';

-- Find all recipes edited by a specific user
-- SELECT * FROM current_recipes WHERE version_created_by_name = 'Alice Smith';

-- Search recipes by ingredient (e.g., find all recipes with "eggs")
-- SELECT DISTINCT r.*
-- FROM current_recipes r
-- JOIN recipe_ingredients ri ON r.version_id = ri.recipe_version_id
-- WHERE ri.ingredient_text LIKE '%eggs%';

-- Full-text search across recipe names and descriptions
-- SELECT * FROM current_recipes
-- WHERE version_id IN (
--     SELECT rowid FROM recipe_versions_fts
--     WHERE recipe_versions_fts MATCH 'chocolate'
-- );

-- Get version history for a specific recipe
-- SELECT * FROM recipe_history WHERE slug = 'buttermilk-ebleskiver';

-- Get a specific version of a recipe
-- SELECT * FROM recipe_versions
-- WHERE recipe_id = (SELECT id FROM recipes WHERE slug = 'buttermilk-ebleskiver')
-- AND version_number = 2;
