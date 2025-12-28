// Auto-search functionality with debouncing and browser history support

let searchTimeout = null;
let currentAbortController = null;
const DEBOUNCE_DELAY = 300; // milliseconds

// Debounce function to limit search frequency
function debounce(func, delay) {
    return function(...args) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => func.apply(this, args), delay);
    };
}

// Perform the search via AJAX
function performAutoSearch() {
    const query = document.getElementById('search-query').value.trim();
    const type = document.getElementById('search-type').value;
    const category = document.getElementById('category').value;

    // Build query parameters
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (type !== 'all') params.set('type', type);
    if (category) params.set('category', category);

    // Update URL without reload using History API
    const newUrl = `/search${params.toString() ? '?' + params.toString() : ''}`;
    window.history.pushState({ query, type, category }, '', newUrl);

    // Cancel previous request if still in flight
    if (currentAbortController) {
        currentAbortController.abort();
    }
    currentAbortController = new AbortController();

    // Show loading indicator
    showLoading(true);

    // Fetch results from API
    fetch(`/api/search?${params.toString()}`, {
        signal: currentAbortController.signal
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Search request failed');
            }
            return response.json();
        })
        .then(data => {
            updateResults(data);
            showLoading(false);
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                // Request was cancelled, ignore
                return;
            }
            console.error('Search error:', error);
            showError('An error occurred while searching. Please try again.');
            showLoading(false);
        });
}

// Update the results on the page
function updateResults(data) {
    const resultsContainer = document.getElementById('results-container');

    if (!data.recipes || data.recipes.length === 0) {
        resultsContainer.innerHTML = `
            <div class="search-results">
                <h2>Search Results</h2>
                <p class="empty-state">No recipes found matching your search.</p>
            </div>
        `;
        return;
    }

    // Build recipe cards HTML
    let recipesHtml = data.recipes.map(recipe => `
        <div class="recipe-card">
            <a href="/recipe/${recipe.slug}">
                <h3>${escapeHtml(recipe.name)}</h3>
                <p class="recipe-author">by ${escapeHtml(recipe.author)}</p>
                <p class="recipe-description">${escapeHtml(recipe.description)}</p>
                <div class="recipe-meta">
                    <span class="recipe-category">${escapeHtml(recipe.recipe_category)}</span>
                    <span class="recipe-difficulty">${escapeHtml(recipe.educational_level)}</span>
                </div>
            </a>
        </div>
    `).join('');

    resultsContainer.innerHTML = `
        <div class="search-results">
            <h2>Search Results</h2>
            <p class="result-count">Found ${data.count} recipe(s)</p>
            <div class="recipe-grid">
                ${recipesHtml}
            </div>
        </div>
    `;
}

// Show/hide loading indicator
function showLoading(isLoading) {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }
}

// Show error message
function showError(message) {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = `
        <div class="search-results">
            <p class="error-message">${escapeHtml(message)}</p>
        </div>
    `;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// Debounced search function
const debouncedSearch = debounce(performAutoSearch, DEBOUNCE_DELAY);

// Handle browser back/forward navigation
window.addEventListener('popstate', function(event) {
    if (event.state) {
        // Update form fields from state
        document.getElementById('search-query').value = event.state.query || '';
        document.getElementById('search-type').value = event.state.type || 'all';
        document.getElementById('category').value = event.state.category || '';
    } else {
        // Read from URL params
        const params = new URLSearchParams(window.location.search);
        document.getElementById('search-query').value = params.get('q') || '';
        document.getElementById('search-type').value = params.get('type') || 'all';
        document.getElementById('category').value = params.get('category') || '';
    }

    // Perform search with current form values
    performAutoSearch();
});

// Initialize auto-search when page loads
document.addEventListener('DOMContentLoaded', function() {
    const searchQuery = document.getElementById('search-query');
    const searchType = document.getElementById('search-type');
    const categorySelect = document.getElementById('category');

    if (!searchQuery || !searchType || !categorySelect) {
        return; // Not on search page
    }

    // Attach event listeners for auto-search
    searchQuery.addEventListener('input', debouncedSearch);
    searchType.addEventListener('change', performAutoSearch); // No debounce for dropdowns
    categorySelect.addEventListener('change', performAutoSearch);

    // Prevent form submission (we handle it via AJAX)
    const searchForm = document.querySelector('.search-form form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(event) {
            event.preventDefault();
            performAutoSearch();
        });
    }

    // If there's a query on page load, perform initial search
    const params = new URLSearchParams(window.location.search);
    if (params.get('q') || params.get('category')) {
        performAutoSearch();
    }
});
