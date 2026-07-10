/**
 * DOM wiring for the feature matrix search application.
 * Fetches search-index.json, handles user input, and renders results.
 */
import { validateQuery, searchIndex, buildMatrix, formatIdeName } from './search.js';

let searchIndexData = [];

/**
 * Initialize the application.
 * Fetches the search index and sets up event listeners.
 */
async function init() {
  try {
    const response = await fetch('./search-index.json');
    if (!response.ok) throw new Error(`Failed to fetch search-index.json: ${response.status}`);
    searchIndexData = await response.json();
  } catch (error) {
    document.getElementById('error-message').innerHTML = `
      <strong>Error loading search index:</strong> ${error.message}
    `;
    return;
  }

  // Fetch metadata for "last updated" info
  try {
    const metaResponse = await fetch('./meta.json');
    if (metaResponse.ok) {
      const meta = await metaResponse.json();
      document.getElementById('last-updated').textContent =
        new Date(meta.generated_at).toLocaleString();
    }
  } catch (e) {
    console.error('Failed to fetch meta.json:', e);
  }

  // Set up event listeners
  const searchInput = document.getElementById('search-input');
  searchInput.addEventListener('input', debounce(handleSearch, 300));

  // Show initial hint
  document.getElementById('hint').style.display = 'block';
}

/**
 * Debounce helper: delays function calls.
 */
function debounce(fn, delayMs) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn.apply(this, args), delayMs);
  };
}

/**
 * Handle search input changes.
 */
function handleSearch(event) {
  const query = event.target.value;
  const validQuery = validateQuery(query);

  const hint = document.getElementById('hint');
  const results = document.getElementById('results');
  const error = document.getElementById('error-message');

  error.innerHTML = '';
  error.style.display = 'none';

  if (!validQuery) {
    hint.style.display = 'block';
    results.innerHTML = '';
    return;
  }

  hint.style.display = 'none';
  const matches = searchIndex(searchIndexData, validQuery);

  if (matches.length === 0) {
    results.innerHTML = '<p style="padding: 1rem; color: #666;">No matching features found.</p>';
    return;
  }

  const matrix = buildMatrix(matches);
  renderMatrix(matrix);
}

/**
 * Render the feature matrix table.
 */
function renderMatrix(matrix) {
  const resultsDiv = document.getElementById('results');

  // Build summary row
  let summaryHtml = '<div class="summary-section"><h3>First appearance by IDE</h3><ul>';
  for (const entry of matrix.summary) {
    const dateStr = formatDate(entry.date);
    const displayName = formatIdeName(entry.ide);
    summaryHtml += `<li><strong>${escapeHtml(displayName)}</strong>: v${entry.version} (${dateStr})</li>`;
  }
  summaryHtml += '</ul></div>';

  // Build matrix table
  let tableHtml = `
    <table class="matrix-table">
      <thead>
        <tr>
          <th>Feature / Snippet</th>
          ${matrix.ides.map(ide => `<th>${escapeHtml(formatIdeName(ide))}</th>`).join('')}
        </tr>
      </thead>
      <tbody>
  `;

  for (const snippet of matrix.snippets) {
    tableHtml += `
      <tr>
        <td class="snippet-cell">
          <span class="snippet-text">${escapeHtml(snippet)}</span>
        </td>
    `;

    for (const ide of matrix.ides) {
      const cell = matrix.cells[snippet][ide];
      if (cell) {
        const versions = cell.versions.join(', ');
        const earliest = cell.earliest;
        tableHtml += `
          <td class="match-cell" title="First in v${earliest}">
            <a href="${escapeHtml(cell.url)}" target="_blank" rel="noopener noreferrer">
              <span class="earliest-badge">v${escapeHtml(earliest)}</span>
            </a>
            <div class="all-versions">${escapeHtml(versions)}</div>
          </td>
        `;
      } else {
        tableHtml += '<td class="no-match-cell">—</td>';
      }
    }

    tableHtml += '</tr>';
  }

  tableHtml += `
      </tbody>
    </table>
  `;

  resultsDiv.innerHTML = summaryHtml + tableHtml;
}

/**
 * Format a date string (YYYY-MM-DD) as dd-MMM-yyyy.
 */
function formatDate(dateString) {
  const date = new Date(dateString + 'T00:00:00Z'); // Ensure UTC parsing
  const day = String(date.getUTCDate()).padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  const year = date.getUTCFullYear();
  return `${day}-${month}-${year}`;
}

/**
 * Escape HTML special characters.
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return String(text).replace(/[&<>"']/g, char => map[char]);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);
