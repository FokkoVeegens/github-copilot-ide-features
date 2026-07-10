/**
 * Pure, dependency-free search logic for the feature matrix.
 * Can be used in browser or Node.js environments.
 * @module search
 */

/**
 * Validate a search query.
 * @param {string} q - The query string
 * @returns {string | null} Trimmed query if valid, null if invalid (≤4 chars)
 */
export function validateQuery(q) {
  const trimmed = String(q || '').trim();
  return trimmed.length > 4 ? trimmed : null;
}

/**
 * Strip "GitHub Copilot" prefix from IDE name for display.
 * @param {string} ideName - Full IDE name
 * @returns {string} Shortened IDE name
 */
export function formatIdeName(ideName) {
  return String(ideName || '').replace(/^GitHub Copilot\s+/, '');
}

/**
 * Search the index for a keyword.
 * Case-insensitive substring match over snippet text.
 * @param {Array<Object>} index - Array of records with 'snippet' field
 * @param {string} keyword - The keyword to search for
 * @returns {Array<Object>} Matching records
 */
export function searchIndex(index, keyword) {
  if (!keyword || !Array.isArray(index)) return [];
  
  const lowerKeyword = keyword.toLowerCase();
  return index.filter(record =>
    String(record.snippet || '').toLowerCase().includes(lowerKeyword)
  );
}

/**
 * Strip "GitHub Copilot" from IDE name for display.
 * @param {string} ideName - Full IDE name
 * @returns {string} Shortened IDE name
 */
function stripGitHubCopilotPrefix(ideName) {
  return ideName.replace(/^GitHub Copilot\s+/, '');
}

/**
 * Get a sort key for custom IDE ordering.
 * @param {string} ideName - Full IDE name
 * @returns {number} Sort priority (lower = earlier)
 */
function getIdeOrderPriority(ideName) {
  const order = [
    /VS Code|GitHub Copilot for VS Code/i,
    /GitHub Copilot CLI|\bCLI\b/i,
    /Visual Studio 2022/i,
    /Visual Studio 2026/i,
    /JetBrains|GitHub Copilot for JetBrains/i,
    /Xcode|GitHub Copilot for Xcode/i,
    /Eclipse|Copilot for Eclipse/i,
    /Vim|Neovim|GitHub Copilot for Vim/i,
  ];
  
  for (let i = 0; i < order.length; i++) {
    if (order[i].test(ideName)) {
      return i;
    }
  }
  return 999; // Unknown IDEs go last
}

/**
 * Build a feature matrix from search results.
 * Pivots results into: rows = matched snippets, columns = IDEs.
 * @param {Array<Object>} results - Results from searchIndex()
 * @returns {Object} Matrix with shape: { snippets: [...], ides: [...], cells: {...} }
 */
export function buildMatrix(results) {
  if (!Array.isArray(results) || results.length === 0) {
    return { snippets: [], ides: [], cells: {}, summary: [] };
  }

  // Collect unique IDEs and snippets
  const ideSet = new Set();
  const snippetMap = new Map(); // snippet -> { ide_names, versions, earliest_date }

  for (const record of results) {
    const ide = record.ide_name || record.ide || '';
    const snippet = record.snippet || '';
    ideSet.add(ide);

    if (!snippetMap.has(snippet)) {
      snippetMap.set(snippet, { earliest_date: null });
    }

    const ideData = snippetMap.get(snippet);
    if (!ideData[ide]) {
      ideData[ide] = [];
    }
    ideData[ide].push({
      version: record.version,
      release_date: record.release_date,
      url: record.url,
    });

    // Track earliest release date for this snippet
    if (!ideData.earliest_date || record.release_date < ideData.earliest_date) {
      ideData.earliest_date = record.release_date;
    }
  }

  // Sort IDEs by custom priority, then by name
  const ides = Array.from(ideSet).sort((a, b) => {
    const priorityA = getIdeOrderPriority(a);
    const priorityB = getIdeOrderPriority(b);
    if (priorityA !== priorityB) {
      return priorityA - priorityB;
    }
    return a.localeCompare(b);
  });

  const snippets = Array.from(snippetMap.keys()).sort(
    (a, b) => snippetMap.get(a).earliest_date.localeCompare(snippetMap.get(b).earliest_date)
  );

  // Build cells: cells[snippet][ide] = { versions: [...], earliest: "1.0.0" }
  const cells = {};
  for (const snippet of snippets) {
    cells[snippet] = {};
    for (const ide of ides) {
      const versions = snippetMap.get(snippet)[ide];
      if (versions) {
        // Sort versions numerically and pick earliest
        versions.sort(
          (a, b) => compareVersions(a.version, b.version)
        );
        cells[snippet][ide] = {
          versions: versions.map(v => v.version),
          earliest: versions[0].version,
          url: versions[0].url,
        };
      }
    }
  }

  // Build summary: first version per IDE that mentions the keyword
  const summary = [];
  for (const ide of ides) {
    let earliestVersion = null;
    let earliestDate = null;

    for (const snippet of snippets) {
      if (cells[snippet][ide]) {
        const cell = cells[snippet][ide];
        if (!earliestVersion || compareVersions(cell.earliest, earliestVersion) < 0) {
          earliestVersion = cell.earliest;
          earliestDate = results.find(
            r => r.ide_name === ide && r.version === earliestVersion
          )?.release_date;
        }
      }
    }

    if (earliestVersion) {
      summary.push({ ide, version: earliestVersion, date: earliestDate });
    }
  }

  return { snippets, ides, cells, summary };
}

/**
 * Compare two version strings.
 * Returns: -1 if a < b, 0 if a === b, 1 if a > b
 * Handles numeric components: "1.10.0" > "1.9.0"
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function compareVersions(a, b) {
  const aParts = String(a || '0')
    .split('.')
    .map(x => {
      const num = parseInt(x, 10);
      return isNaN(num) ? 0 : num;
    });
  const bParts = String(b || '0')
    .split('.')
    .map(x => {
      const num = parseInt(x, 10);
      return isNaN(num) ? 0 : num;
    });

  const maxLen = Math.max(aParts.length, bParts.length);
  for (let i = 0; i < maxLen; i++) {
    const aPart = aParts[i] || 0;
    const bPart = bParts[i] || 0;
    if (aPart < bPart) return -1;
    if (aPart > bPart) return 1;
  }
  return 0;
}
