/**
 * DOM wiring for the feature matrix search application.
 * Fetches search-index.json, handles user input, and renders results.
 */
import { validateQuery, searchIndex, buildIdeRows, formatIdeName, buildSnippetExcerpt, prepareSearchResults, collectIdeNames, limitRowsPerIde } from './search.js';

const MAX_ROWS_PER_IDE = 20;

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
 * Build the IDE cell content: logo image (if available) plus display name,
 * wrapped in an inner flex element so the outer <td> keeps normal table-cell
 * layout (setting display:flex directly on a <td> causes browsers to center
 * its content instead of respecting text-align/left alignment).
 */
function buildIdeCell(ideName) {
  const displayName = formatIdeName(ideName);
  const logo = IDE_LOGOS[ideIdByName.get(ideName)];
  const logoHtml = logo
    ? `<img class="ide-logo" src="${escapeHtml(logo)}" alt="" />`
    : '';
  return `<span class="ide-name">${logoHtml}<span>${escapeHtml(displayName)}</span></span>`;
}

function buildMobileField(label, valueHtml, extraClass = '') {
  const className = extraClass ? `mobile-field ${extraClass}` : 'mobile-field';
  return `
    <div class="${className}">
      <span class="mobile-field-label">${escapeHtml(label)}</span>
      <div class="mobile-field-value">${valueHtml}</div>
    </div>
  `;
}

function buildMatchedMobileCard(group, query) {
  const releasesHtml = group.rows
    .map((row, index) => {
      const excerpt = buildSnippetExcerpt(row.snippet, query);
      const snippetPreviewHtml = highlightMatch(excerpt, query);
      const versionBadgeClass = index === 0 ? 'version-badge' : 'version-badge later';

      return `
        <article class="mobile-release-card">
          ${buildMobileField(
            'Version',
            `<a class="version-link" href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer"><span class="${versionBadgeClass}">v${escapeHtml(row.version)}</span></a>`,
          )}
          ${buildMobileField('Date released', escapeHtml(formatDate(row.release_date)))}
          ${buildMobileField(
            'Feature description',
            `<a href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(row.snippet)}">${snippetPreviewHtml}</a>`,
            'desc-cell',
          )}
        </article>
      `;
    })
    .join('');

  return `
    <section class="mobile-ide-group">
      <h3 class="mobile-ide-heading">${buildIdeCell(group.ide)}</h3>
      ${releasesHtml}
    </section>
  `;
}

function buildMissingMobileCard(ideName) {
  return `
    <section class="mobile-ide-group mobile-ide-group-na">
      <h3 class="mobile-ide-heading">${buildIdeCell(ideName)}</h3>
      <article class="mobile-release-card mobile-release-card-na">
        ${buildMobileField('Availability', '<span class="na-badge">❌</span>N/A', 'na-cell')}
      </article>
    </section>
  `;
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
    const errorMessage = document.getElementById('error-message');
    errorMessage.innerHTML = `
      <strong>Error loading search index:</strong> ${error.message}
    `;
    errorMessage.style.display = 'block';
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
  const { matches, hiddenCount } = prepareSearchResults(allMatches, launchOnly);

  if (matches.length === 0) {
    if (launchOnly && allMatches.length > 0) {
      results.innerHTML = `<p style="padding: 1rem; color: #666;">No launch announcements found for this feature (${allMatches.length} other mention${allMatches.length === 1 ? '' : 's'} hidden). Uncheck “Only launch announcements” to see all results.</p>`;
    } else {
      results.innerHTML = '<p style="padding: 1rem; color: #666;">No matching features found.</p>';
    }
    return;
  }

  const ideRows = limitRowsPerIde(
    buildIdeRows(matches, collectIdeNames(searchIndexData)),
    MAX_ROWS_PER_IDE,
  );
  renderIdeRows(ideRows, validQuery, hiddenCount);
}

/**
 * Render the feature table: one row per IDE + matching release, grouped by
 * IDE, with IDEs that have no match collapsed into a single N/A row.
 */
export function buildResultsMarkup(ideRows, query, hiddenCount = 0) {
  // Note about filtered-out results
  let filterNoteHtml = '';
  if (hiddenCount > 0) {
    filterNoteHtml = `<p class="filter-note">${hiddenCount} mention${hiddenCount === 1 ? '' : 's'} without launch keywords hidden. Uncheck “Only launch announcements” to see all results.</p>`;
  }
  if (ideRows.hiddenRowCount > 0) {
    filterNoteHtml += `<p class="filter-note"><span aria-hidden="true">&#9888;</span> Showing the first ${MAX_ROWS_PER_IDE} matching releases per IDE; ${ideRows.hiddenRowCount} additional release${ideRows.hiddenRowCount === 1 ? '' : 's'} hidden.</p>`;
  }

  const supportedCount = ideRows.matched.length;
  const missingCount = ideRows.missing.length;
  const summaryHtml = `
    <div class="summary-section">
      <h2>Search results</h2>
      <p>${supportedCount} IDE${supportedCount === 1 ? '' : 's'} support this feature${
        missingCount > 0 ? ` · ${missingCount} IDE${missingCount === 1 ? '' : 's'} have no matching release notes yet` : ''
      }</p>
    </div>
  `;

  let tableHtml = `
    <div class="table-wrapper">
    <table class="rows-table">
      <thead>
        <tr>
          <th>IDE</th>
          <th>Version</th>
          <th>Date released</th>
          <th>Feature description</th>
        </tr>
      </thead>
      <tbody>
  `;

  for (const group of ideRows.matched) {
    group.rows.forEach((row, index) => {
      const excerpt = buildSnippetExcerpt(row.snippet, query);
      const snippetPreviewHtml = highlightMatch(excerpt, query);
      const versionBadgeClass = index === 0 ? 'version-badge' : 'version-badge later';

      tableHtml += '<tr>';
      if (index === 0) {
        tableHtml += `<td class="ide-cell" rowspan="${group.rows.length}">${buildIdeCell(group.ide)}</td>`;
      }
      tableHtml += `
            <td><a class="version-link" href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer"><span class="${versionBadgeClass}">v${escapeHtml(row.version)}</span></a></td>
            <td class="date-cell">${escapeHtml(formatDate(row.release_date))}</td>
            <td class="desc-cell">
              <a href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(row.snippet)}">${snippetPreviewHtml}</a>
            </td>
          </tr>
      `;
    });
  }

  if (ideRows.missing.length > 0) {
    tableHtml += '<tr class="section-divider"><td colspan="4">Not yet available</td></tr>';
    for (const ide of ideRows.missing) {
      tableHtml += `
        <tr class="na-row">
          <td class="ide-cell">${buildIdeCell(ide)}</td>
          <td colspan="3" class="na-cell"><span class="na-badge">❌</span>N/A</td>
        </tr>
      `;
    }
  }

  tableHtml += `
      </tbody>
    </table>
    </div>
  `;

  let mobileHtml = '<div class="mobile-results" role="region" aria-label="Search results by IDE">';
  for (const group of ideRows.matched) {
    mobileHtml += buildMatchedMobileCard(group, query);
  }

  if (ideRows.missing.length > 0) {
    mobileHtml += '<h3 class="mobile-section-title">Not yet available</h3>';
    for (const ide of ideRows.missing) {
      mobileHtml += buildMissingMobileCard(ide);
    }
  }
  mobileHtml += '</div>';

  return filterNoteHtml + summaryHtml + tableHtml + mobileHtml;
}

function renderIdeRows(ideRows, query, hiddenCount = 0) {
  const resultsDiv = document.getElementById('results');
  resultsDiv.innerHTML = buildResultsMarkup(ideRows, query, hiddenCount);
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
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}
