/**
 * ShopMate AI - Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const elements = {
        userIdInput: document.getElementById('user-id'),
        loadMemoryBtn: document.getElementById('load-memory-btn'),
        memCategory: document.getElementById('mem-category'),
        memBudget: document.getElementById('mem-budget'),
        memHistory: document.getElementById('mem-history'),
        
        updateCategory: document.getElementById('update-category'),
        updateBudget: document.getElementById('update-budget'),
        updateMemoryBtn: document.getElementById('update-memory-btn'),
        
        searchQuery: document.getElementById('search-query'),
        searchBtn: document.getElementById('search-btn'),
        searchLoader: document.getElementById('search-loader'),
        searchBtnText: document.querySelector('.btn-text'),
        
        errorMsg: document.getElementById('error-message'),
        
        welcomeState: document.getElementById('welcome-state'),
        loadingState: document.getElementById('loading-state'),
        resultsContent: document.getElementById('results-content'),
        productsAnalyzed: document.getElementById('products-analyzed'),
        markdownBody: document.getElementById('recommendations-markdown')
    };

    const API_BASE = '/api';

    const renderRecommendations = (text) => {
        if (window.marked) {
            return marked.parse(text || '');
        }

        const escaped = (text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return `<pre>${escaped}</pre>`;
    };

    // Configure Marked.js for safe rendering when the CDN is available.
    if (window.marked) {
        marked.setOptions({
            headerIds: false,
            mangle: false,
            breaks: true
        });
    }

    // Helper: Show Error
    const showError = (message) => {
        elements.errorMsg.textContent = message;
        elements.errorMsg.classList.remove('hidden');
        setTimeout(() => {
            elements.errorMsg.classList.add('hidden');
        }, 5000);
    };

    // Helper: Update Memory UI
    const updateMemoryUI = (memory) => {
        elements.memCategory.textContent = memory.category || 'Not determined';
        
        if (memory.budget) {
            elements.memBudget.textContent = `₹${memory.budget.toLocaleString()}`;
        } else {
            elements.memBudget.textContent = 'Not specified';
        }

        // Update history
        elements.memHistory.innerHTML = '';
        if (memory.history && memory.history.length > 0) {
            // Show last 5
            const recent = memory.history.slice(-5).reverse();
            recent.forEach(query => {
                const li = document.createElement('li');
                li.textContent = query;
                li.title = query;
                elements.memHistory.appendChild(li);
            });
        } else {
            elements.memHistory.innerHTML = '<li class="empty-state">No history yet</li>';
        }
    };

    // API: Load Memory
    const loadMemory = async () => {
        const userId = elements.userIdInput.value.trim();
        if (!userId) return showError('Please enter a User ID');

        try {
            const res = await fetch(`${API_BASE}/memory/${userId}`);
            if (!res.ok) {
                if (res.status === 404) {
                    // New user effectively
                    updateMemoryUI({ category: null, budget: null, history: [] });
                    return;
                }
                throw new Error('Failed to load memory');
            }
            
            const data = await res.json();
            updateMemoryUI(data.memory);
        } catch (err) {
            console.error(err);
            showError('Could not load user profile.');
        }
    };

    // API: Update Memory Manually
    const updateMemory = async () => {
        const userId = elements.userIdInput.value.trim();
        if (!userId) return showError('Please enter a User ID');

        const category = elements.updateCategory.value.trim();
        const budgetVal = elements.updateBudget.value.trim();
        const budget = budgetVal ? parseFloat(budgetVal) : null;

        try {
            const originalText = elements.updateMemoryBtn.textContent;
            elements.updateMemoryBtn.textContent = 'Updating...';
            elements.updateMemoryBtn.disabled = true;

            const res = await fetch(`${API_BASE}/memory/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    category: category || null,
                    budget: budget
                })
            });

            if (!res.ok) throw new Error('Failed to update memory');
            
            const data = await res.json();
            updateMemoryUI(data.updated_memory);
            
            // Clear inputs
            elements.updateCategory.value = '';
            elements.updateBudget.value = '';

        } catch (err) {
            console.error(err);
            showError('Could not update profile.');
        } finally {
            elements.updateMemoryBtn.textContent = 'Update Profile';
            elements.updateMemoryBtn.disabled = false;
        }
    };

    // API: Get Recommendations
    const getRecommendations = async () => {
        const userId = elements.userIdInput.value.trim();
        const query = elements.searchQuery.value.trim();

        if (!userId) return showError('Please enter a User ID first');
        if (!query) return showError('Please enter a search query');

        // UI State transition
        elements.welcomeState.classList.add('hidden');
        elements.resultsContent.classList.add('hidden');
        elements.loadingState.classList.remove('hidden');
        
        elements.searchBtn.disabled = true;
        elements.searchBtnText.textContent = 'Searching...';
        elements.searchLoader.classList.remove('hidden');
        elements.errorMsg.classList.add('hidden');

        try {
            const res = await fetch(`${API_BASE}/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    query: query
                })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Failed to fetch recommendations');
            }

            const data = await res.json();
            
            // Update UI with results
            updateMemoryUI(data.memory_snapshot);
            
            elements.productsAnalyzed.textContent = `${data.products_analyzed} products analyzed`;
            
            // Render markdown to HTML
            elements.markdownBody.innerHTML = renderRecommendations(data.recommendations || '');
            
            // Show results
            elements.loadingState.classList.add('hidden');
            elements.resultsContent.classList.remove('hidden');

        } catch (err) {
            console.error(err);
            showError(err.message || 'An error occurred while getting recommendations.');
            elements.loadingState.classList.add('hidden');
            elements.welcomeState.classList.remove('hidden');
        } finally {
            elements.searchBtn.disabled = false;
            elements.searchBtnText.textContent = 'Search';
            elements.searchLoader.classList.add('hidden');
        }
    };

    // Event Listeners
    elements.loadMemoryBtn.addEventListener('click', loadMemory);
    elements.updateMemoryBtn.addEventListener('click', updateMemory);
    elements.searchBtn.addEventListener('click', getRecommendations);
    
    // Enter key support for search
    elements.searchQuery.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            getRecommendations();
        }
    });

    // Initial load
    loadMemory();
});
