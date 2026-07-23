/**
 * DOM wiring for the feature matrix search application.
 * Fetches search-index.json, handles user input, and renders results.
 */
import { validateQuery, searchIndex, buildMatrix, formatIdeName, buildSnippetExcerpt, filterLaunchAnnouncements, dedupeByIdeVersion, collectIdeNames } from './search.js';

let searchIndexData = [];

/** Logo image per IDE id. IDEs without a logo fall back to a text header. */
const IDE_LOGOS = {
  'vs-code': './images/vs-code.svg',
  'copilot-cli': './images/copilot-cli.svg',
  'visual-studio-2022': './images/visual-studio-2022.svg',
  'visual-studio-2026': './images/visual-studio-2026.svg',
  'jetbrains': './images/jetbrains.svg',
  'xcode': './images/xcode.svg',
  'eclipse': './images/eclipse.svg',
  'vim-neovim': './images/vim-neovim.svg',
  'sql-server-management-studio': './images/sql-server-management-studio.png',
};

/** Map from IDE display name to IDE id, built from the search index. */
let ideIdByName = new Map();

/**
 * Build the header cell for an IDE: logo image with tooltip, or text fallback.
 */
function buildIdeHeader(ideName) {
  const displayName = formatIdeName(ideName);
  const logo = IDE_LOGOS[ideIdByName.get(ideName)];
  if (logo) {
    return `<img class="ide-logo" src="${escapeHtml(logo)}" alt="${escapeHtml(displayName)}" title="${escapeHtml(displayName)}" />`;
  }
  return `<span title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</span>`;
}

/**
 * Initialize the application.
 * Fetches the search index and sets up event listeners.
 */
async function init() {
  try {
    const response = await fetch('./search-index.json');
    if (!response.ok) throw new Error(`Failed to fetch search-index.json: ${response.status}`);
    searchIndexData = await response.json();
    ideIdByName = new Map(searchIndexData.map(r => [r.ide_name || r.ide || '', r.ide]));
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

  const launchOnlyFilter = document.getElementById('launch-only-filter');
  launchOnlyFilter.addEventListener('change', () => {
    handleSearch({ target: searchInput });
  });

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
  const allMatches = searchIndex(searchIndexData, validQuery);
  const launchOnly = document.getElementById('launch-only-filter')?.checked ?? false;
  const matches = launchOnly
    ? dedupeByIdeVersion(filterLaunchAnnouncements(allMatches))
    : allMatches;

  if (matches.length === 0) {
    if (launchOnly && allMatches.length > 0) {
      results.innerHTML = `<p style="padding: 1rem; color: #666;">No launch announcements found for this feature (${allMatches.length} other mention${allMatches.length === 1 ? '' : 's'} hidden). Uncheck “Only launch announcements” to see all results.</p>`;
    } else {
      results.innerHTML = '<p style="padding: 1rem; color: #666;">No matching features found.</p>';
    }
    return;
  }

  const matrix = buildMatrix(matches, collectIdeNames(searchIndexData));
  renderMatrix(matrix, validQuery, launchOnly ? allMatches.length - matches.length : 0);
}

/**
 * Render the feature matrix table.
 */
function renderMatrix(matrix, query, hiddenCount = 0) {
  const resultsDiv = document.getElementById('results');

  // Note about filtered-out results
  let filterNoteHtml = '';
  if (hiddenCount > 0) {
    filterNoteHtml = `<p class="filter-note">${hiddenCount} mention${hiddenCount === 1 ? '' : 's'} without launch keywords hidden. Uncheck “Only launch announcements” to see all results.</p>`;
  }

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
          ${matrix.ides.map(ide => `<th>${buildIdeHeader(ide)}</th>`).join('')}
        </tr>
      </thead>
      <tbody>
  `;

  for (const snippet of matrix.snippets) {
    const excerpt = buildSnippetExcerpt(snippet, query);
    const snippetPreviewHtml = highlightMatch(excerpt, query);
    tableHtml += `
      <tr>
        <td class="snippet-cell">
          <span class="snippet-text" tabindex="0" title="${escapeHtml(snippet)}">${snippetPreviewHtml}</span>
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

  resultsDiv.innerHTML = filterNoteHtml + summaryHtml + tableHtml;
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

/**
 * Escape text for use inside a RegExp.
 */
function escapeRegExp(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Highlight all query matches in an excerpt.
 */
function highlightMatch(text, query) {
  const source = String(text || '');
  const keyword = String(query || '').trim();
  if (!source || !keyword) {
    return escapeHtml(source);
  }

  const regex = new RegExp(escapeRegExp(keyword), 'gi');
  let html = '';
  let lastIndex = 0;
  let match = regex.exec(source);

  while (match) {
    html += escapeHtml(source.slice(lastIndex, match.index));
    html += `<mark class="snippet-match">${escapeHtml(match[0])}</mark>`;
    lastIndex = match.index + match[0].length;
    match = regex.exec(source);
  }
  html += escapeHtml(source.slice(lastIndex));
  return html;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);
