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
 * Build a compact snippet excerpt around the first keyword match.
 * @param {string} snippet - Full feature description
 * @param {string} keyword - Search keyword
 * @param {number} contextChars - Approximate max chars when clipping fallback text
 * @returns {string} Excerpt with optional ellipses
 */
export function buildSnippetExcerpt(snippet, keyword, contextChars = 90) {
  const normalized = String(snippet || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return '';

  const trimmedKeyword = String(keyword || '').trim();
  if (!trimmedKeyword) {
    return clipText(normalized, contextChars);
  }

  const match = findBestMatch(normalized, trimmedKeyword);
  if (!match) {
    return clipText(normalized, contextChars);
  }

  const words = getWordsWithOffsets(normalized);
  if (words.length === 0) {
    return clipText(normalized, contextChars);
  }

  const matchStartWord = findWordIndexAtOffset(words, match.start);
  const matchEndWord = findWordIndexAtOffset(words, Math.max(match.end - 1, match.start));

  const beforeWords = 3;
  const afterWords = 8;
  const excerptStartWord = Math.max(0, matchStartWord - beforeWords);
  const excerptEndWord = Math.min(words.length - 1, matchEndWord + afterWords);

  const start = words[excerptStartWord].start;
  const end = words[excerptEndWord].end;

  let excerpt = normalized.slice(start, end);

  const prefix = start > 0 ? '... ' : '';
  const suffix = end < normalized.length ? ' ...' : '';
  excerpt = `${prefix}${excerpt}${suffix}`;

  return clipText(excerpt, contextChars + 25);
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

/**
 * Clip plain text to a max length, preserving whole words when possible.
 * @param {string} text
 * @param {number} maxChars
 * @returns {string}
 */
function clipText(text, maxChars) {
  if (text.length <= maxChars) {
    return text;
  }
  const clipped = text.slice(0, maxChars);
  const splitAt = clipped.lastIndexOf(' ');
  if (splitAt > 0) {
    return `${clipped.slice(0, splitAt)} ...`;
  }
  return `${clipped} ...`;
}

/**
 * Find the best matching region in text for the query.
 * Prefers an exact phrase; falls back to the first matching query term.
 * @param {string} text
 * @param {string} query
 * @returns {{start: number, end: number} | null}
 */
function findBestMatch(text, query) {
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();

  const exactStart = lowerText.indexOf(lowerQuery);
  if (exactStart !== -1) {
    return { start: exactStart, end: exactStart + lowerQuery.length };
  }

  const terms = lowerQuery
    .split(/\s+/)
    .map(term => term.trim())
    .filter(term => term.length >= 3);

  for (const term of terms) {
    const termStart = lowerText.indexOf(term);
    if (termStart !== -1) {
      return { start: termStart, end: termStart + term.length };
    }
  }
  return null;
}

/**
 * Get all non-whitespace tokens and their offsets.
 * @param {string} text
 * @returns {Array<{text: string, start: number, end: number}>}
 */
function getWordsWithOffsets(text) {
  const matches = text.matchAll(/\S+/g);
  const words = [];
  for (const match of matches) {
    words.push({
      text: match[0],
      start: match.index,
      end: match.index + match[0].length,
    });
  }
  return words;
}

/**
 * Find token index that contains the provided text offset.
 * @param {Array<{start: number, end: number}>} words
 * @param {number} offset
 * @returns {number}
 */
function findWordIndexAtOffset(words, offset) {
  for (let i = 0; i < words.length; i++) {
    if (offset >= words[i].start && offset < words[i].end) {
      return i;
    }
  }

  if (offset <= words[0].start) {
    return 0;
  }

  return words.length - 1;
}
