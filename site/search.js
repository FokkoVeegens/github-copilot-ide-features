/**
 * Pure, dependency-free search logic for the feature matrix.
 * Can be used in browser or Node.js environments.
 * @module search
 */

/**
 * Validate a search query.
 * @param {string} q - The query string
 * @returns {string | null} Trimmed query if valid, null if invalid (≤2 chars)
 */
export function validateQuery(q) {
  const trimmed = String(q || '').trim();
  return trimmed.length >= 3 ? trimmed : null;
}

/**
 * Strip "GitHub Copilot" / "Copilot for" prefixes from IDE name for display,
 * leaving only the real IDE name (e.g. "VS Code", "Eclipse", "CLI").
 * @param {string} ideName - Full IDE name
 * @returns {string} Shortened IDE name
 */
export function formatIdeName(ideName) {
  return String(ideName || '').replace(/^(?:GitHub\s+)?Copilot\s+(?:for\s+)?/i, '');
}

/**
 * Patterns that indicate a snippet announces a feature launch
 * (as opposed to an incremental change, fix, or improvement).
 * Matching is fuzzy: case-insensitive with common word variants.
 */
const LAUNCH_PATTERNS = [
  /\breleas(?:e[ds]?|ing)\b/i,          // release, released, releases, releasing
  /\bpreview\b/i,                        // preview, public preview, (Preview)
  /\bgenerally available\b/i,
  /\bgeneral availability\b/i,
  /\bGA\b/,                              // GA (case-sensitive to avoid false hits)
  /\bnow available\b/i,
  /\bavailable (?:in|for|to)\b/i,
  /\bintroduc(?:e[ds]?|ing)\b/i,         // introduce, introduced, introducing
  /\blaunch(?:e[ds]|ing)?\b/i,           // launch, launched, launching
  /\brolling out\b/i,
  /\bnow supports?\b/i,
  /\badded support\b/i,
  /\bnew feature\b/i,
  /\benabled by default\b/i,
];

/**
 * Patterns that unambiguously indicate a feature has reached General
 * Availability, as opposed to merely being introduced or still in preview.
 * Deliberately narrower than LAUNCH_PATTERNS: phrases like "now available"
 * are too ambiguous (they also show up in preview announcements).
 */
const GA_PATTERNS = [
  /\bgenerally available\b/i,
  /\bgeneral availability\b/i,
  /\bGA\b/,                              // GA (case-sensitive to avoid false hits)
  /\bout of preview\b/i,
  /\bno longer (?:in )?preview\b/i,
  /\bgraduated? (?:from|out of) preview\b/i,
];

/**
 * Check whether a snippet looks like a feature launch announcement.
 * @param {string} snippet - Feature description text
 * @returns {boolean} True if the snippet contains a launch-indicating phrase
 */
export function isLaunchAnnouncement(snippet) {
  const text = String(snippet || '');
  return LAUNCH_PATTERNS.some(pattern => pattern.test(text));
}

/**
 * Check whether a snippet unambiguously announces General Availability.
 * @param {string} snippet - Feature description text
 * @returns {boolean} True if the snippet contains a GA-indicating phrase
 */
export function isGaAnnouncement(snippet) {
  const text = String(snippet || '');
  return GA_PATTERNS.some(pattern => pattern.test(text));
}

/**
 * Filter search results down to a single canonical record per IDE: the one
 * that marks the feature's most meaningful "first appearance".
 *
 * Selection per IDE:
 * - If any snippet unambiguously announces General Availability, the
 *   earliest such GA record is kept (this "wins" over an earlier preview
 *   mention, since GA is the more useful milestone to show).
 * - Otherwise, the earliest record that matches any launch keyword is kept.
 * - Otherwise (no launch keywords at all), the earliest record overall is
 *   kept, since the first mention marks when the feature appeared.
 * @param {Array<Object>} results - Results from searchIndex()
 * @returns {Array<Object>} At most one record per IDE
 */
export function filterLaunchAnnouncements(results) {
  if (!Array.isArray(results)) return [];

  // Group records per IDE
  const byIde = new Map();
  for (const record of results) {
    const ide = record.ide_name || record.ide || '';
    if (!byIde.has(ide)) byIde.set(ide, []);
    byIde.get(ide).push(record);
  }

  const kept = new Set();
  for (const records of byIde.values()) {
    const gaRecords = records.filter(r => isGaAnnouncement(r.snippet));
    const launchRecords = records.filter(r => isLaunchAnnouncement(r.snippet));
    const candidates = gaRecords.length > 0 ? gaRecords : (launchRecords.length > 0 ? launchRecords : records);

    let earliest = candidates[0];
    for (const r of candidates) {
      if (compareVersions(r.version, earliest.version) < 0) earliest = r;
    }
    kept.add(earliest);
  }

  // Preserve original result order
  return results.filter(record => kept.has(record));
}

/**
 * Deduplicate results so each IDE + version combination appears once.
 * When a release mentions the same feature in multiple notes, the
 * shortest (most headline-like) snippet is kept.
 * @param {Array<Object>} results - Results from searchIndex()
 * @returns {Array<Object>} At most one record per IDE + version
 */
export function dedupeByIdeVersion(results) {
  if (!Array.isArray(results)) return [];

  const best = new Map(); // "ide|version" -> record
  for (const record of results) {
    const key = `${record.ide_name || record.ide || ''}|${record.version || ''}`;
    const current = best.get(key);
    if (!current || String(record.snippet || '').length < String(current.snippet || '').length) {
      best.set(key, record);
    }
  }

  const kept = new Set(best.values());
  // Preserve original result order
  return results.filter(record => kept.has(record));
}

/**
 * Apply the launch-only filter and version deduplication used by the UI.
 * @param {Array<Object>} results - Results from searchIndex()
 * @param {boolean} launchOnly - Whether to keep launch announcements only
 * @returns {{ matches: Array<Object>, hiddenCount: number }} Prepared results
 */
export function prepareSearchResults(results, launchOnly) {
  if (!Array.isArray(results)) return { matches: [], hiddenCount: 0 };
  if (!launchOnly) return { matches: results, hiddenCount: 0 };

  const matches = dedupeByIdeVersion(filterLaunchAnnouncements(results));
  return {
    matches,
    hiddenCount: results.length - matches.length,
  };
}

/**
 * Collect the unique IDE names present in a search index.
 * @param {Array<Object>} index - Full search index records
 * @returns {Array<string>} Unique IDE names
 */
export function collectIdeNames(index) {
  if (!Array.isArray(index)) return [];
  const names = new Set();
  for (const record of index) {
    const ide = record.ide_name || record.ide || '';
    if (ide) names.add(ide);
  }
  return Array.from(names);
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
 * Limit the rendered release rows for each IDE without changing which IDEs
 * are represented in the search result.
 * @param {Object} ideRows - Result from buildIdeRows()
 * @param {number} maxRowsPerIde - Maximum rows to retain for each IDE
 * @returns {Object} Limited rows and the number of omitted rows
 */
export function limitRowsPerIde(ideRows, maxRowsPerIde) {
  const matched = Array.isArray(ideRows?.matched) ? ideRows.matched : [];
  const missing = Array.isArray(ideRows?.missing) ? ideRows.missing : [];
  const limit = Number.isInteger(maxRowsPerIde) && maxRowsPerIde > 0
    ? maxRowsPerIde
    : Infinity;

  let hiddenRowCount = 0;
  const limitedMatched = matched.map(group => {
    const rows = Array.isArray(group.rows) ? group.rows : [];
    hiddenRowCount += Math.max(0, rows.length - limit);
    return { ...group, rows: rows.slice(0, limit) };
  });

  return { matched: limitedMatched, missing, hiddenRowCount };
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
 * Build per-IDE rows from search results.
 * Pivots results into one group per IDE, each holding every matching
 * record (version, release date, snippet, url) sorted oldest first.
 * IDEs with no matching record are reported separately so the caller can
 * render them as a single "not available" row.
 * @param {Array<Object>} results - Results from searchIndex()
 * @param {Array<string>} [allIdes] - Optional full list of IDE names to always
 *   consider, even when they have no matching results
 * @returns {Object} Shape: { matched: [{ ide, rows: [...] }], missing: [...] }
 */
export function buildIdeRows(results, allIdes = null) {
  const records = Array.isArray(results) ? results : [];

  const ideSet = new Set(Array.isArray(allIdes) ? allIdes.filter(Boolean) : []);
  const byIde = new Map(); // ide -> Map(version -> { version, release_date, snippet, url })

  for (const record of records) {
    const ide = record.ide_name || record.ide || '';
    if (!ide) continue;
    ideSet.add(ide);

    if (!byIde.has(ide)) byIde.set(ide, new Map());
    const versionMap = byIde.get(ide);
    const version = record.version;
    const candidate = {
      version: record.version,
      release_date: record.release_date,
      snippet: record.snippet || '',
      url: record.url,
    };

    // A release can match the search keyword in more than one note. Keep a
    // single row per IDE + version, preferring the shortest (most
    // headline-like) snippet, matching dedupeByIdeVersion's behavior.
    const existing = versionMap.get(version);
    if (!existing || candidate.snippet.length < existing.snippet.length) {
      versionMap.set(version, candidate);
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

  const matched = [];
  const missing = [];

  for (const ide of ides) {
    const versionMap = byIde.get(ide);
    if (!versionMap || versionMap.size === 0) {
      missing.push(ide);
      continue;
    }

    // Sort oldest first: by version, falling back to release date for ties.
    const rows = Array.from(versionMap.values()).sort((a, b) => {
      const cmp = compareVersions(a.version, b.version);
      if (cmp !== 0) return cmp;
      return String(a.release_date || '').localeCompare(String(b.release_date || ''));
    });

    matched.push({ ide, rows });
  }

  return { matched, missing };
}

/**
 * Compare two version strings.
 * Returns: -1 if a < b, 0 if a === b, 1 if a > b
 * Handles numeric components: "1.10.0" > "1.9.0"
 * Also splits on hyphens so numeric build suffixes compare correctly, e.g.
 * CLI-style versions "0.0.81-10" > "0.0.81-2" (not equal, as a plain
 * dot-split would treat "81-10" and "81-2" both as the integer 81).
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function compareVersions(a, b) {
  const toParts = v =>
    String(v || '0')
      .split(/[.-]/)
      .map(x => {
        const num = parseInt(x, 10);
        return isNaN(num) ? 0 : num;
      });

  const aParts = toParts(a);
  const bParts = toParts(b);

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
