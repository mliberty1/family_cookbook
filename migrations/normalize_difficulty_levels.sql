-- Migration: Normalize difficulty levels from "Difficult" to "Hard"
-- Date: 2025-12-28
-- Description: Updates all recipe versions with educational_level = 'Difficult' to 'Hard'
--              to match the standardized difficulty levels in the application

-- Check current difficulty level distribution (for verification before running)
-- Uncomment to see what will be changed:
-- SELECT educational_level, COUNT(*) as count
-- FROM recipe_versions
-- GROUP BY educational_level;

-- Update all "Difficult" entries to "Hard"
UPDATE recipe_versions
SET educational_level = 'Hard'
WHERE educational_level = 'Difficult';

-- Verify the change
SELECT educational_level, COUNT(*) as count
FROM recipe_versions
GROUP BY educational_level
ORDER BY educational_level;

-- Expected result: Should show Easy, Medium, Hard (no Difficult)
