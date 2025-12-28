/**
 * Unit tests for RecipeScaler
 * Run with: node test_scaler.js
 */

const RecipeScaler = require('./static/recipe-scaler.js');

class TestRunner {
    constructor() {
        this.passed = 0;
        this.failed = 0;
        this.scaler = new RecipeScaler();
    }

    assert(condition, message) {
        if (condition) {
            this.passed++;
            console.log(`✓ ${message}`);
        } else {
            this.failed++;
            console.log(`✗ FAILED: ${message}`);
        }
    }

    assertEqual(actual, expected, message) {
        const passed = actual === expected;
        if (passed) {
            this.passed++;
            console.log(`✓ ${message}`);
        } else {
            this.failed++;
            console.log(`✗ FAILED: ${message}`);
            console.log(`  Expected: ${expected}`);
            console.log(`  Actual: ${actual}`);
        }
    }

    assertClose(actual, expected, tolerance, message) {
        const passed = Math.abs(actual - expected) < tolerance;
        if (passed) {
            this.passed++;
            console.log(`✓ ${message}`);
        } else {
            this.failed++;
            console.log(`✗ FAILED: ${message}`);
            console.log(`  Expected: ${expected}`);
            console.log(`  Actual: ${actual}`);
        }
    }

    summary() {
        console.log('\n' + '='.repeat(50));
        console.log(`Tests passed: ${this.passed}`);
        console.log(`Tests failed: ${this.failed}`);
        console.log(`Total: ${this.passed + this.failed}`);
        return this.failed === 0;
    }

    // Test parseQuantity
    testParseQuantity() {
        console.log('\n--- Testing parseQuantity ---');

        // Whole numbers
        this.assertEqual(this.scaler.parseQuantity('2 cups'), 2, 'Parse whole number');
        this.assertEqual(this.scaler.parseQuantity('10 eggs'), 10, 'Parse double digit');

        // Simple fractions
        this.assertEqual(this.scaler.parseQuantity('1/2 cup'), 0.5, 'Parse 1/2');
        this.assertEqual(this.scaler.parseQuantity('1/4 teaspoon'), 0.25, 'Parse 1/4');
        this.assertEqual(this.scaler.parseQuantity('3/4 cup'), 0.75, 'Parse 3/4');
        this.assertEqual(this.scaler.parseQuantity('1/3 cup'), 1/3, 'Parse 1/3');

        // Unicode fractions
        this.assertEqual(this.scaler.parseQuantity('½ cup'), 0.5, 'Parse unicode ½');
        this.assertEqual(this.scaler.parseQuantity('¼ teaspoon'), 0.25, 'Parse unicode ¼');
        this.assertEqual(this.scaler.parseQuantity('¾ cup'), 0.75, 'Parse unicode ¾');
        this.assertEqual(this.scaler.parseQuantity('⅓ cup'), 1/3, 'Parse unicode ⅓');

        // Mixed numbers
        this.assertEqual(this.scaler.parseQuantity('1 1/2 cups'), 1.5, 'Parse mixed 1 1/2');
        this.assertEqual(this.scaler.parseQuantity('2 1/4 teaspoons'), 2.25, 'Parse mixed 2 1/4');
        this.assertEqual(this.scaler.parseQuantity('1½ cups'), 1.5, 'Parse mixed 1½');

        // Decimals
        this.assertEqual(this.scaler.parseQuantity('1.5 cups'), 1.5, 'Parse decimal');
        this.assertEqual(this.scaler.parseQuantity('0.25 teaspoon'), 0.25, 'Parse decimal 0.25');

        // Ranges (takes first value)
        this.assertEqual(this.scaler.parseQuantity('2-3 cups'), 2, 'Parse range 2-3');
        this.assertEqual(this.scaler.parseQuantity('1-2 pounds'), 1, 'Parse range 1-2');

        // Edge cases
        this.assertEqual(this.scaler.parseQuantity(''), null, 'Parse empty string');
        this.assertEqual(this.scaler.parseQuantity('a pinch of salt'), null, 'Parse non-numeric');
    }

    // Test toFraction
    testToFraction() {
        console.log('\n--- Testing toFraction ---');

        // Whole numbers
        this.assertEqual(this.scaler.toFraction(0), '0', 'Convert 0');
        this.assertEqual(this.scaler.toFraction(1), '1', 'Convert 1');
        this.assertEqual(this.scaler.toFraction(2), '2', 'Convert 2');
        this.assertEqual(this.scaler.toFraction(10), '10', 'Convert 10');

        // Common fractions
        this.assertEqual(this.scaler.toFraction(0.5), '½', 'Convert 0.5 to ½');
        this.assertEqual(this.scaler.toFraction(0.25), '¼', 'Convert 0.25 to ¼');
        this.assertEqual(this.scaler.toFraction(0.75), '¾', 'Convert 0.75 to ¾');
        // 1/3 converts to ⅓ because it's close enough to the unicode fraction
        this.assert(
            this.scaler.toFraction(1/3) === '⅓' || this.scaler.toFraction(1/3) === '1/3',
            'Convert 1/3 to ⅓ or 1/3'
        );

        // Mixed numbers
        this.assertEqual(this.scaler.toFraction(1.5), '1½', 'Convert 1.5 to 1½');
        this.assertEqual(this.scaler.toFraction(2.25), '2¼', 'Convert 2.25 to 2¼');
        this.assertEqual(this.scaler.toFraction(3.75), '3¾', 'Convert 3.75 to 3¾');

        // Uncommon fractions (slash notation)
        this.assertEqual(this.scaler.toFraction(1/6), '1/6', 'Convert 1/6');
        this.assertEqual(this.scaler.toFraction(2/3), '⅔', 'Convert 2/3 to ⅔');
    }

    // Test scaleIngredient
    testScaleIngredient() {
        console.log('\n--- Testing scaleIngredient ---');

        // Basic scaling
        this.assertEqual(
            this.scaler.scaleIngredient('2 cups flour', 2),
            '4 cups flour',
            'Double 2 cups'
        );

        this.assertEqual(
            this.scaler.scaleIngredient('1 cup sugar', 0.5),
            '½ cup sugar',
            'Half 1 cup'
        );

        this.assertEqual(
            this.scaler.scaleIngredient('1/2 teaspoon salt', 2),
            '1 teaspoon salt',
            'Double 1/2 teaspoon'
        );

        this.assertEqual(
            this.scaler.scaleIngredient('3 eggs', 1.5),
            '4½ eggs',
            'Scale 3 eggs by 1.5'
        );

        // Unicode fractions
        this.assertEqual(
            this.scaler.scaleIngredient('½ cup milk', 2),
            '1 cup milk',
            'Double ½ cup'
        );

        // Mixed numbers
        this.assertEqual(
            this.scaler.scaleIngredient('1 1/2 cups water', 2),
            '3 cups water',
            'Double 1 1/2 cups'
        );

        // Complex ingredients
        this.assertEqual(
            this.scaler.scaleIngredient('2 Tablespoons butter, softened', 0.5),
            '1 Tablespoons butter, softened',
            'Half with description'
        );

        // Ingredient groups (should not scale)
        this.assertEqual(
            this.scaler.scaleIngredient('## Cake', 2),
            '## Cake',
            'Do not scale group headers'
        );

        // No quantity (should return unchanged)
        this.assertEqual(
            this.scaler.scaleIngredient('a pinch of salt', 2),
            'a pinch of salt',
            'Non-numeric unchanged'
        );

        // Multiplier of 1 (should return unchanged)
        this.assertEqual(
            this.scaler.scaleIngredient('2 cups flour', 1),
            '2 cups flour',
            'Multiplier of 1'
        );
    }

    // Test scaleYield
    testScaleYield() {
        console.log('\n--- Testing scaleYield ---');

        this.assertEqual(
            this.scaler.scaleYield('6 servings', 2),
            '12 servings',
            'Double 6 servings'
        );

        this.assertEqual(
            this.scaler.scaleYield('12 cookies', 0.5),
            '6 cookies',
            'Half 12 cookies'
        );

        this.assertEqual(
            this.scaler.scaleYield('8 servings', 1.5),
            '12 servings',
            'Scale 8 servings by 1.5'
        );

        // Edge cases
        this.assertEqual(
            this.scaler.scaleYield('TODO', 2),
            'TODO',
            'TODO unchanged'
        );

        this.assertEqual(
            this.scaler.scaleYield('Not specified', 2),
            'Not specified',
            'Not specified unchanged'
        );
    }

    // Test with real recipe ingredients
    testRealRecipeIngredients() {
        console.log('\n--- Testing Real Recipe Ingredients ---');

        // From Buttermilk Ebleskiver
        this.assertEqual(
            this.scaler.scaleIngredient('3 eggs, separated', 2),
            '6 eggs, separated',
            'Real: 3 eggs doubled'
        );

        this.assertEqual(
            this.scaler.scaleIngredient('2 Tablespoons sugar', 0.5),
            '1 Tablespoons sugar',
            'Real: 2 Tablespoons halved'
        );

        this.assertEqual(
            this.scaler.scaleIngredient('1/2 teaspoon salt', 2),
            '1 teaspoon salt',
            'Real: 1/2 teaspoon doubled'
        );

        // From Cheese Streusel Coffee Cake
        this.assertEqual(
            this.scaler.scaleIngredient('16 ounces cream cheese, softened (2 packages)', 0.5),
            '8 ounces cream cheese, softened (2 packages)',
            'Real: 16 ounces halved'
        );

        this.assertEqual(
            this.scaler.scaleIngredient('2/3 cups warm water (105° - 115°)', 3),
            '2 cups warm water (105° - 115°)',
            'Real: 2/3 cups tripled'
        );
    }

    runAll() {
        console.log('Running RecipeScaler Unit Tests...');
        this.testParseQuantity();
        this.testToFraction();
        this.testScaleIngredient();
        this.testScaleYield();
        this.testRealRecipeIngredients();
        return this.summary();
    }
}

// Run tests
const runner = new TestRunner();
const success = runner.runAll();
process.exit(success ? 0 : 1);
