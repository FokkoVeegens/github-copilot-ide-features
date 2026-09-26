/**
 * Tests for site/search.js using Node's built-in test runner.
 * Run with: node --test site/search.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert';
import { validateQuery, searchIndex, buildIdeRows, formatIdeName, buildSnippetExcerpt, isLaunchAnnouncement, isGaAnnouncement, filterLaunchAnnouncements, dedupeByIdeVersion, prepareSearchResults, collectIdeNames, limitRowsPerIde } from './search.js';
import { buildResultsMarkup } from './app.js';

test('validateQuery rejects empty string', () => {
  assert.strictEqual(validateQuery(''), null);
});

test('validateQuery rejects whitespace-only string', () => {
  assert.strictEqual(validateQuery('   '), null);
});

test('validateQuery rejects strings shorter than three characters', () => {
  assert.strictEqual(validateQuery('ab'), null);
  assert.strictEqual(validateQuery('  1  '), null);
});

test('validateQuery accepts strings with at least three characters', () => {
  assert.strictEqual(validateQuery('MCP'), 'MCP');
  assert.strictEqual(validateQuery('hello'), 'hello');
  assert.strictEqual(validateQuery('  hello  '), 'hello');
});

test('searchIndex returns empty array for empty input', () => {
  assert.deepStrictEqual(searchIndex([], 'test'), []);
  assert.deepStrictEqual(searchIndex(null, 'test'), []);
});

test('searchIndex returns empty array for empty keyword', () => {
  const index = [{ snippet: 'test content' }];
  assert.deepStrictEqual(searchIndex(index, ''), []);
});

test('searchIndex performs case-insensitive substring match', () => {
  const index = [
    { snippet: 'Improved Chat', ide: 'vscode' },
    { snippet: 'New Feature', ide: 'eclipse' },
    { snippet: 'improved debugging', ide: 'jetbrains' },
  ];
  
  const results = searchIndex(index, 'improved');
  assert.strictEqual(results.length, 2);
  assert(results.some(r => r.ide === 'vscode'));
  assert(results.some(r => r.ide === 'jetbrains'));
});

test('searchIndex finds multiple matches', () => {
  const index = [
    { snippet: 'Chat support', version: '1.0.0' },
    { snippet: 'Chat integration', version: '1.1.0' },
    { snippet: 'Code completion', version: '1.2.0' },
  ];
  
  const results = searchIndex(index, 'chat');
  assert.strictEqual(results.length, 2);
});

test('limitRowsPerIde caps each IDE while retaining missing IDEs and counts hidden rows', () => {
  const ideRows = {
    matched: [
      { ide: 'vscode', rows: [{ version: '1' }, { version: '2' }, { version: '3' }] },
      { ide: 'cli', rows: [{ version: '1' }] },
    ],
    missing: ['xcode'],
  };

  const limited = limitRowsPerIde(ideRows, 2);

  assert.deepStrictEqual(limited.matched[0].rows, [{ version: '1' }, { version: '2' }]);
  assert.deepStrictEqual(limited.matched[1].rows, [{ version: '1' }]);
  assert.deepStrictEqual(limited.missing, ['xcode']);
  assert.strictEqual(limited.hiddenRowCount, 1);
});

test('buildSnippetExcerpt centers around matching term with ellipses', () => {
  const snippet = 'This is a very long description where Copilot Chat appears in the middle with additional details for context and clarity.';
  const excerpt = buildSnippetExcerpt(snippet, 'Copilot Chat', 20);

  assert(excerpt.includes('Copilot Chat'));
  assert(excerpt.startsWith('... '));
  assert(excerpt.endsWith(' ...'));
});

test('buildSnippetExcerpt clips text when no match is found', () => {
  const snippet = 'A long descriptive text without the searched phrase but still needing clipping for compact display in the table.';
  const excerpt = buildSnippetExcerpt(snippet, 'nonexistent-term', 18);

  assert(excerpt.endsWith(' ...'));
  assert(excerpt.length < snippet.length);
});

test('buildSnippetExcerpt keeps the full match visible instead of clipping it at line start', () => {
  const snippet = 'With this preview, we are excited to release a new preview feature, **Copilot Next Edit Suggestions (Preview)**, that improves flow.';
  const excerpt = buildSnippetExcerpt(snippet, 'next edit suggestions', 90);

  assert(excerpt.includes('Next Edit Suggestions'));
  assert(!excerpt.includes('... **Copilot Next...'));
});

test('isLaunchAnnouncement matches launch keywords', () => {
  assert(isLaunchAnnouncement('Copilot Next Edit Suggestions (Preview) is now available'));
  assert(isLaunchAnnouncement('We released a new agent mode'));
  assert(isLaunchAnnouncement('Agent mode is generally available'));
  assert(isLaunchAnnouncement('Introducing Copilot Vision'));
  assert(isLaunchAnnouncement('Next Edit Suggestions reaches general availability'));
  assert(isLaunchAnnouncement('Copilot Chat is GA'));
  assert(isLaunchAnnouncement('Launched agent skills for everyone'));
  assert(isLaunchAnnouncement('Copilot now supports MCP servers'));
  assert(isLaunchAnnouncement('Added support for custom instructions'));
});

test('isLaunchAnnouncement rejects incremental change notes', () => {
  assert(!isLaunchAnnouncement('Fixed a bug in Next Edit Suggestions'));
  assert(!isLaunchAnnouncement('Improved performance of Next Edit Suggestions'));
  assert(!isLaunchAnnouncement('Next Edit Suggestions no longer flickers when typing'));
  assert(!isLaunchAnnouncement('Updated the ga tracking pixel')); // lowercase "ga" must not match GA
  assert(!isLaunchAnnouncement(''));
  assert(!isLaunchAnnouncement(null));
});

test('filterLaunchAnnouncements keeps the GA record for an IDE over an earlier preview note', () => {
  const results = [
    { ide: 'vscode', snippet: 'Next Edit Suggestions is now available in preview', version: '1.0.0', release_date: '2025-01-01' },
    { ide: 'vscode', snippet: 'Fixed flickering in Next Edit Suggestions', version: '1.1.0', release_date: '2025-02-01' },
    { ide: 'vscode', snippet: 'Next Edit Suggestions is generally available', version: '1.2.0', release_date: '2025-03-01' },
  ];

  const filtered = filterLaunchAnnouncements(results);
  assert.strictEqual(filtered.length, 1);
  assert.strictEqual(filtered[0].version, '1.2.0');
});

test('filterLaunchAnnouncements keeps the earliest launch announcement for an IDE when there is no GA record', () => {
  const results = [
    { ide: 'vscode', snippet: 'Next Edit Suggestions (preview) released', version: '1.0.0', release_date: '2025-01-01' },
    { ide: 'vscode', snippet: 'Fixed flickering in Next Edit Suggestions', version: '1.1.0', release_date: '2025-02-01' },
    { ide: 'vscode', snippet: 'Improved Next Edit Suggestions preview reliability', version: '1.2.0', release_date: '2025-03-01' },
  ];

  const filtered = filterLaunchAnnouncements(results);
  assert.strictEqual(filtered.length, 1);
  assert.strictEqual(filtered[0].version, '1.0.0');
});

test('filterLaunchAnnouncements falls back to the earliest version for IDEs without launch keywords', () => {
  const results = [
    // Eclipse launch note without any launch keyword
    { ide: 'eclipse', snippet: 'Support Next Edit Suggestion (NES).', version: '0.13.0', release_date: '2025-05-01' },
    { ide: 'eclipse', snippet: 'Fixed NES rendering glitch', version: '0.14.0', release_date: '2025-06-01' },
    { ide: 'vscode', snippet: 'Next Edit Suggestions (preview) released', version: '1.97.0', release_date: '2025-01-01' },
    { ide: 'vscode', snippet: 'NES now uses less memory', version: '1.100.0', release_date: '2025-04-01' },
  ];

  const filtered = filterLaunchAnnouncements(results);
  assert.strictEqual(filtered.length, 2);
  assert(filtered.some(r => r.ide === 'eclipse' && r.version === '0.13.0'));
  assert(filtered.some(r => r.ide === 'vscode' && r.version === '1.97.0'));
});

test('isGaAnnouncement only matches unambiguous GA phrases', () => {
  assert(isGaAnnouncement('Next Edit Suggestions is now generally available'));
  assert(isGaAnnouncement('NES has graduated from preview'));
  assert(!isGaAnnouncement('Next Edit Suggestions is now available in preview'));
  assert(!isGaAnnouncement('Updated the ga tracking pixel')); // lowercase "ga" must not match
});

test('dedupeByIdeVersion keeps one record per IDE + version, preferring the shortest snippet', () => {
  const results = [
    { ide: 'vscode', snippet: 'GitHub Copilot code completions are great at autocomplete, and we are excited to release Next Edit Suggestions', version: '1.97.0' },
    { ide: 'vscode', snippet: 'Copilot Next Edit Suggestions (Preview)', version: '1.97.0' },
    { ide: 'vscode', snippet: 'Next Edit Suggestions (preview) - Copilot predicts the next edit.', version: '1.97.0' },
    { ide: 'vscode', snippet: 'Next Edit Suggestions (preview) - Copilot predicts the next edit.', version: '1.98.0' },
    { ide: 'eclipse', snippet: 'Support Next Edit Suggestion (NES).', version: '0.13.0' },
  ];

  const deduped = dedupeByIdeVersion(results);
  assert.strictEqual(deduped.length, 3);
  const vscode197 = deduped.filter(r => r.ide === 'vscode' && r.version === '1.97.0');
  assert.strictEqual(vscode197.length, 1);
  assert.strictEqual(vscode197[0].snippet, 'Copilot Next Edit Suggestions (Preview)');
  assert(deduped.some(r => r.ide === 'vscode' && r.version === '1.98.0'));
  assert(deduped.some(r => r.ide === 'eclipse' && r.version === '0.13.0'));
});

test('dedupeByIdeVersion handles invalid input', () => {
  assert.deepStrictEqual(dedupeByIdeVersion(null), []);
  assert.deepStrictEqual(dedupeByIdeVersion(undefined), []);
  assert.deepStrictEqual(dedupeByIdeVersion([]), []);
});

test('prepareSearchResults counts every non-kept mention as hidden when launch filtering is on', () => {
  const results = [
    { ide: 'vscode', snippet: 'Agent mode is available in preview', version: '1.0.0' },
    { ide: 'vscode', snippet: 'Agent mode preview released to all users', version: '1.0.0' },
    { ide: 'vscode', snippet: 'Fixed an agent mode crash', version: '1.1.0' },
  ];

  const prepared = prepareSearchResults(results, true);

  assert.strictEqual(prepared.matches.length, 1);
  assert.strictEqual(prepared.hiddenCount, 2);
});

test('collectIdeNames returns unique IDE names from the index', () => {
  const index = [
    { ide_name: 'GitHub Copilot for VS Code', snippet: 'a' },
    { ide_name: 'GitHub Copilot for Xcode', snippet: 'b' },
    { ide_name: 'GitHub Copilot for VS Code', snippet: 'c' },
    { ide: 'eclipse', snippet: 'd' },
  ];

  const names = collectIdeNames(index);
  assert.strictEqual(names.length, 3);
  assert(names.includes('GitHub Copilot for VS Code'));
  assert(names.includes('GitHub Copilot for Xcode'));
  assert(names.includes('eclipse'));
});

test('collectIdeNames handles invalid input', () => {
  assert.deepStrictEqual(collectIdeNames(null), []);
  assert.deepStrictEqual(collectIdeNames(undefined), []);
});

test('buildIdeRows includes IDEs without matches in "missing" when allIdes is given', () => {
  const results = [
    {
      snippet: 'Next Edit Suggestions (preview)',
      ide: 'vscode',
      ide_name: 'GitHub Copilot for VS Code',
      version: '1.97.0',
      release_date: '2025-01-01',
      url: 'https://example.com/1.97.0',
    },
  ];
  const allIdes = [
    'GitHub Copilot for VS Code',
    'GitHub Copilot for Xcode',
    'GitHub Copilot for Vim/Neovim',
    'GitHub Copilot for Eclipse',
  ];

  const ideRows = buildIdeRows(results, allIdes);
  assert.strictEqual(ideRows.matched.length, 1);
  assert.strictEqual(ideRows.matched[0].ide, 'GitHub Copilot for VS Code');
  assert.strictEqual(ideRows.missing.length, 3);
  assert(ideRows.missing.includes('GitHub Copilot for Xcode'));
  assert(ideRows.missing.includes('GitHub Copilot for Vim/Neovim'));
  assert(ideRows.missing.includes('GitHub Copilot for Eclipse'));
});

test('buildIdeRows without allIdes only reports IDEs present in results', () => {
  const results = [
    {
      snippet: 'Agent mode released',
      ide: 'vscode',
      ide_name: 'GitHub Copilot for VS Code',
      version: '1.99.0',
      release_date: '2025-04-01',
      url: 'https://example.com/1.99.0',
    },
  ];

  const ideRows = buildIdeRows(results);
  assert.deepStrictEqual(ideRows.matched.map(g => g.ide), ['GitHub Copilot for VS Code']);
  assert.deepStrictEqual(ideRows.missing, []);
});

test('filterLaunchAnnouncements handles invalid input', () => {
  assert.deepStrictEqual(filterLaunchAnnouncements(null), []);
  assert.deepStrictEqual(filterLaunchAnnouncements(undefined), []);
  assert.deepStrictEqual(filterLaunchAnnouncements([]), []);
});

test('buildIdeRows returns expected structure', () => {
  const results = [
    {
      snippet: 'New feature',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/1.0.0',
    },
  ];

  const ideRows = buildIdeRows(results);
  assert('matched' in ideRows);
  assert('missing' in ideRows);
  assert(Array.isArray(ideRows.matched));
  assert(Array.isArray(ideRows.missing));
  assert('ide' in ideRows.matched[0]);
  assert('rows' in ideRows.matched[0]);
});

test('buildIdeRows returns empty structure for empty input', () => {
  const ideRows = buildIdeRows([]);
  assert.deepStrictEqual(ideRows.matched, []);
  assert.deepStrictEqual(ideRows.missing, []);
});

test('buildIdeRows groups multiple releases for the same IDE together', () => {
  const results = [
    {
      snippet: 'Chat feature',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.80.0',
      release_date: '2023-06-01',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Chat feature',
      ide: 'eclipse',
      ide_name: 'Eclipse',
      version: '1.5.0',
      release_date: '2023-06-15',
      url: 'https://example.com/2',
    },
  ];

  const ideRows = buildIdeRows(results);
  const ideNames = ideRows.matched.map(g => g.ide);
  assert(ideNames.includes('VS Code'));
  assert(ideNames.includes('Eclipse'));
  // VS Code should come before Eclipse due to custom ordering
  assert.strictEqual(ideNames[0], 'VS Code');
  assert.strictEqual(ideNames[1], 'Eclipse');
  assert.strictEqual(ideRows.matched.find(g => g.ide === 'VS Code').rows.length, 1);
});

test('buildIdeRows sorts an IDE\'s rows oldest version first', () => {
  const results = [
    {
      snippet: 'Feature X',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.5.0',
      release_date: '2023-06-15',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Feature X',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2023-01-01',
      url: 'https://example.com/2',
    },
  ];

  const ideRows = buildIdeRows(results);
  const group = ideRows.matched.find(g => g.ide === 'VS Code');
  assert.strictEqual(group.rows[0].version, '1.0.0');
  assert.strictEqual(group.rows[1].version, '1.5.0');
});

test('buildIdeRows sorts hyphenated build versions numerically, not lexically', () => {
  const results = [
    {
      snippet: 'Feature X',
      ide: 'cli',
      ide_name: 'CLI',
      version: '0.0.81-10',
      release_date: '2023-06-15',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Feature X',
      ide: 'cli',
      ide_name: 'CLI',
      version: '0.0.81-2',
      release_date: '2023-06-01',
      url: 'https://example.com/2',
    },
  ];

  const ideRows = buildIdeRows(results);
  const group = ideRows.matched.find(g => g.ide === 'CLI');
  assert.strictEqual(group.rows[0].version, '0.0.81-2');
  assert.strictEqual(group.rows[1].version, '0.0.81-10');
});

test('buildIdeRows deduplicates multiple matching snippets for the same IDE + version', () => {
  const results = [
    {
      snippet: 'A much longer sentence mentioning the feature in passing',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.5.0',
      release_date: '2023-06-15',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Feature X',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.5.0',
      release_date: '2023-06-15',
      url: 'https://example.com/2',
    },
  ];

  const ideRows = buildIdeRows(results);
  const group = ideRows.matched.find(g => g.ide === 'VS Code');
  assert.strictEqual(group.rows.length, 1);
  assert.strictEqual(group.rows[0].snippet, 'Feature X');
});

test('formatIdeName removes "GitHub Copilot" and "Copilot for" prefixes', () => {
  assert.strictEqual(formatIdeName('GitHub Copilot for VS Code'), 'VS Code');
  assert.strictEqual(formatIdeName('GitHub Copilot CLI'), 'CLI');
  assert.strictEqual(formatIdeName('GitHub Copilot for JetBrains'), 'JetBrains');
  assert.strictEqual(formatIdeName('Copilot for Eclipse'), 'Eclipse');
});

test('formatIdeName handles IDE names without prefix', () => {
  assert.strictEqual(formatIdeName('VS Code'), 'VS Code');
  assert.strictEqual(formatIdeName('Eclipse'), 'Eclipse');
  assert.strictEqual(formatIdeName(''), '');
});

test('buildIdeRows sorts IDEs in custom order (VS Code, CLI, VS 2022, VS 2026, JetBrains, Xcode, Eclipse, Vim)', () => {
  const results = [
    {
      snippet: 'Chat',
      ide: 'eclipse',
      ide_name: 'Copilot for Eclipse',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Chat',
      ide: 'vscode',
      ide_name: 'GitHub Copilot for VS Code',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/2',
    },
    {
      snippet: 'Chat',
      ide: 'jetbrains',
      ide_name: 'GitHub Copilot for JetBrains',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/3',
    },
    {
      snippet: 'Chat',
      ide: 'cli',
      ide_name: 'GitHub Copilot CLI',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/4',
    },
  ];

  const ideRows = buildIdeRows(results);
  const ideNames = ideRows.matched.map(g => g.ide);
  // Should follow custom order: VS Code, CLI, JetBrains, Eclipse
  assert.strictEqual(ideNames[0], 'GitHub Copilot for VS Code');
  assert.strictEqual(ideNames[1], 'GitHub Copilot CLI');
  assert.strictEqual(ideNames[2], 'GitHub Copilot for JetBrains');
  assert.strictEqual(ideNames[3], 'Copilot for Eclipse');
});

test('buildResultsMarkup renders accessible mobile labels in the DOM', () => {
  const markup = buildResultsMarkup(
    {
      matched: [
        {
          ide: 'GitHub Copilot CLI',
          rows: [
            {
              snippet: 'Agent mode is generally available for CLI.',
              version: '1.2.3',
              release_date: '2026-03-15',
              url: 'https://example.com/cli',
            },
          ],
        },
      ],
      missing: ['Copilot for Eclipse'],
      hiddenRowCount: 0,
    },
    'agent mode',
  );

  assert.match(markup, /<div class="mobile-results" role="region" aria-label="Search results by IDE">/);
  assert.match(markup, /<span class="mobile-field-label">Version<\/span>/);
  assert.match(markup, /<span class="mobile-field-label">Date released<\/span>/);
  assert.match(markup, /<span class="mobile-field-label">Feature description<\/span>/);
  assert.match(markup, /<span class="mobile-field-label">Availability<\/span>/);
  assert.match(markup, /Not yet available/);
});

test('buildResultsMarkup renders Unknown when a release date is missing', () => {
  const markup = buildResultsMarkup(
    {
      matched: [
        {
          ide: 'GitHub Copilot CLI',
          rows: [
            {
              snippet: 'Agent mode is generally available for CLI.',
              version: '1.2.3',
              release_date: null,
              url: 'https://example.com/cli',
            },
          ],
        },
      ],
      missing: [],
      hiddenRowCount: 0,
    },
    'agent mode',
  );

  assert.match(markup, /<td class="date-cell">Unknown<\/td>/);
  assert.match(markup, /<div class="mobile-field-value">Unknown<\/div>/);
});
