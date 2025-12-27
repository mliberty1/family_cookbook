/**
 * Recipe Scaler - Parses and scales ingredient quantities
 * Copyright 2023 Matthew Liberty
 * Licensed under the Apache License, Version 2.0
 */

class RecipeScaler {
    constructor() {
        // Unicode fraction characters
        this.unicodeFractions = {
            '¼': 0.25, '½': 0.5, '¾': 0.75,
            '⅐': 1/7, '⅑': 1/9, '⅒': 0.1,
            '⅓': 1/3, '⅔': 2/3,
            '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
            '⅙': 1/6, '⅚': 5/6,
            '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875
        };

        // Reverse mapping for display
        this.decimalToFraction = {
            0.125: '⅛', 0.25: '¼', 0.333: '⅓', 0.375: '⅜',
            0.5: '½', 0.625: '⅝', 0.666: '⅔', 0.75: '¾', 0.875: '⅞'
        };
    }

    /**
     * Parse a quantity string to a number
     * Handles: whole numbers, fractions, mixed numbers, decimals, ranges
     */
    parseQuantity(text) {
        if (!text || typeof text !== 'string') return null;

        text = text.trim();

        // Replace unicode fractions with decimal equivalents for parsing
        let normalized = text;
        for (let [frac, dec] of Object.entries(this.unicodeFractions)) {
            normalized = normalized.replace(frac, ' ' + dec.toString() + ' ');
        }

        // Clean up extra spaces
        normalized = normalized.replace(/\s+/g, ' ').trim();

        // Handle ranges (e.g., "2-3 cups") - take the first number
        const rangeMatch = normalized.match(/^(\d+(?:\.\d+)?)\s*-\s*\d+/);
        if (rangeMatch) {
            return parseFloat(rangeMatch[1]);
        }

        // Handle mixed fractions (e.g., "1 1/2") - must check before decimal
        const mixedMatch = normalized.match(/^(\d+)\s+(\d+)\s*\/\s*(\d+)/);
        if (mixedMatch) {
            const whole = parseInt(mixedMatch[1]);
            const num = parseInt(mixedMatch[2]);
            const denom = parseInt(mixedMatch[3]);
            return whole + (num / denom);
        }

        // Handle mixed fractions with decimals (e.g., "1 0.5" from "1½")
        // Only match if there's a decimal point or it's less than 1
        const mixedDecimalMatch = normalized.match(/^(\d+)\s+0?\.(\d+)/);
        if (mixedDecimalMatch) {
            return parseFloat(mixedDecimalMatch[1]) + parseFloat('0.' + mixedDecimalMatch[2]);
        }

        // Handle simple fractions (e.g., "1/2")
        const fracMatch = normalized.match(/^(\d+)\s*\/\s*(\d+)/);
        if (fracMatch) {
            return parseInt(fracMatch[1]) / parseInt(fracMatch[2]);
        }

        // Handle decimals and whole numbers
        const numMatch = normalized.match(/^(\d+(?:\.\d+)?)/);
        if (numMatch) {
            return parseFloat(numMatch[1]);
        }

        return null;
    }

    /**
     * Convert a decimal number to a fraction string
     */
    toFraction(num, tolerance = 0.01) {
        if (num === 0) return '0';
        if (Number.isInteger(num)) return num.toString();

        const whole = Math.floor(num);
        const decimal = num - whole;

        // Check common fractions first
        for (let [dec, frac] of Object.entries(this.decimalToFraction)) {
            if (Math.abs(decimal - dec) < tolerance) {
                return whole > 0 ? `${whole}${frac}` : frac;
            }
        }

        // Fall back to slash notation for uncommon fractions
        // Find best fraction approximation
        let bestNum = 1, bestDenom = 1, bestError = Math.abs(decimal - 1);

        for (let denom = 2; denom <= 16; denom++) {
            const num = Math.round(decimal * denom);
            const error = Math.abs(decimal - (num / denom));
            if (error < bestError) {
                bestNum = num;
                bestDenom = denom;
                bestError = error;
            }
        }

        if (bestError < tolerance) {
            const fracStr = `${bestNum}/${bestDenom}`;
            return whole > 0 ? `${whole} ${fracStr}` : fracStr;
        }

        // If no good fraction found, use decimal
        return num.toFixed(2).replace(/\.?0+$/, '');
    }

    /**
     * Scale an ingredient text by a multiplier
     * Returns the scaled ingredient with quantities updated
     */
    scaleIngredient(ingredient, multiplier) {
        if (!ingredient || multiplier === 1) return ingredient;

        // Don't scale ingredient group headers
        if (ingredient.startsWith('## ')) return ingredient;

        const quantity = this.parseQuantity(ingredient);
        if (quantity === null) return ingredient;

        const scaled = quantity * multiplier;
        const scaledStr = this.toFraction(scaled);

        // Find where the quantity ends in the original string
        const quantityPattern = /^[\d¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞\s\/.-]+/;
        const match = ingredient.match(quantityPattern);

        if (match) {
            // Replace the quantity part, ensuring there's a space after
            const remainder = ingredient.substring(match[0].length);
            if (remainder && !remainder.startsWith(' ')) {
                return scaledStr + ' ' + remainder;
            }
            return scaledStr + remainder;
        }

        return ingredient;
    }

    /**
     * Scale a yield value
     */
    scaleYield(yieldText, multiplier) {
        if (!yieldText || multiplier === 1) return yieldText;
        if (yieldText === 'TODO' || yieldText === 'Not specified') return yieldText;

        const quantity = this.parseQuantity(yieldText);
        if (quantity === null) return yieldText;

        const scaled = quantity * multiplier;
        const scaledStr = this.toFraction(scaled);

        // Replace the number in the yield text
        return yieldText.replace(/^[\d¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞\s\/.-]+/, scaledStr + ' ');
    }
}

// Export for use in browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RecipeScaler;
}

// Global instance for browser use
const scaler = new RecipeScaler();

/**
 * Scale all ingredients on the page
 * Called by buttons in the recipe page
 */
function scaleRecipe(multiplier) {
    const ingredientLists = document.querySelectorAll('[data-scalable]');

    ingredientLists.forEach(list => {
        const items = list.querySelectorAll('li');

        items.forEach(item => {
            // Store original text on first scale
            if (!item.dataset.original) {
                item.dataset.original = item.textContent;
            }

            // Scale from original text
            const original = item.dataset.original;
            const scaled = scaler.scaleIngredient(original, multiplier);
            item.textContent = scaled;
        });
    });

    // Scale yield if present
    const yieldElement = document.querySelector('[data-yield]');
    if (yieldElement) {
        if (!yieldElement.dataset.original) {
            yieldElement.dataset.original = yieldElement.textContent;
        }

        const original = yieldElement.dataset.original;
        const scaled = scaler.scaleYield(original, multiplier);
        yieldElement.textContent = scaled;
    }
}
