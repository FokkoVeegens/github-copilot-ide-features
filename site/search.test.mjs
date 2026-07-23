/**
 * Tests for site/search.js using Node's built-in test runner.
 * Run with: node --test site/search.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert';
import { validateQuery, searchIndex, buildMatrix, formatIdeName, buildSnippetExcerpt, isLaunchAnnouncement, filterLaunchAnnouncements, dedupeByIdeVersion, collectIdeNames } from './search.js';

test('validateQuery rejects empty string', () => {
  assert.strictEqual(validateQuery(''), null);
});

test('validateQuery rejects whitespace-only string', () => {
  assert.strictEqual(validateQuery('   '), null);
});

test('validateQuery rejects ≤4 character strings', () => {
  assert.strictEqual(validateQuery('abc'), null);
  assert.strictEqual(validateQuery('1234'), null);
});

test('validateQuery accepts >4 character strings', () => {
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

test('filterLaunchAnnouncements drops non-launch records when launches exist', () => {
  const results = [
    { ide: 'vscode', snippet: 'Next Edit Suggestions is now available in preview', version: '1.0.0', release_date: '2025-01-01' },
    { ide: 'vscode', snippet: 'Fixed flickering in Next Edit Suggestions', version: '1.1.0', release_date: '2025-02-01' },
    { ide: 'vscode', snippet: 'Next Edit Suggestions is generally available', version: '1.2.0', release_date: '2025-03-01' },
  ];

  const filtered = filterLaunchAnnouncements(results);
  assert.strictEqual(filtered.length, 2);
  assert.strictEqual(filtered[0].version, '1.0.0');
  assert.strictEqual(filtered[1].version, '1.2.0');
});

test('filterLaunchAnnouncements falls back to earliest version for IDEs without launch keywords', () => {
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

test('buildMatrix includes IDEs without matches as empty columns when allIdes is given', () => {
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

  const matrix = buildMatrix(results, allIdes);
  assert.strictEqual(matrix.ides.length, 4);
  assert(matrix.ides.includes('GitHub Copilot for Xcode'));
  assert(matrix.ides.includes('GitHub Copilot for Vim/Neovim'));
  assert(matrix.ides.includes('GitHub Copilot for Eclipse'));
  // Empty IDEs have no cells and no summary entry
  assert.strictEqual(matrix.cells['Next Edit Suggestions (preview)']['GitHub Copilot for Xcode'], undefined);
  assert.strictEqual(matrix.summary.length, 1);
  assert.strictEqual(matrix.summary[0].ide, 'GitHub Copilot for VS Code');
});

test('buildMatrix without allIdes only shows IDEs present in results', () => {
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

  const matrix = buildMatrix(results);
  assert.deepStrictEqual(matrix.ides, ['GitHub Copilot for VS Code']);
});

test('filterLaunchAnnouncements handles invalid input', () => {
  assert.deepStrictEqual(filterLaunchAnnouncements(null), []);
  assert.deepStrictEqual(filterLaunchAnnouncements(undefined), []);
  assert.deepStrictEqual(filterLaunchAnnouncements([]), []);
});

test('buildMatrix returns expected structure', () => {
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
  
  const matrix = buildMatrix(results);
  assert('snippets' in matrix);
  assert('ides' in matrix);
  assert('cells' in matrix);
  assert('summary' in matrix);
  assert(Array.isArray(matrix.snippets));
  assert(Array.isArray(matrix.ides));
  assert(Array.isArray(matrix.summary));
});

test('buildMatrix returns empty structure for empty input', () => {
  const matrix = buildMatrix([]);
  assert.deepStrictEqual(matrix.snippets, []);
  assert.deepStrictEqual(matrix.ides, []);
  assert.deepStrictEqual(matrix.cells, {});
  assert.deepStrictEqual(matrix.summary, []);
});

test('buildMatrix pivots results correctly', () => {
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
  
  const matrix = buildMatrix(results);
  assert.deepStrictEqual(matrix.snippets, ['Chat feature']);
  assert(matrix.ides.includes('VS Code'));
  assert(matrix.ides.includes('Eclipse'));
  // VS Code should come before Eclipse due to custom ordering
  assert.strictEqual(matrix.ides[0], 'VS Code');
  assert.strictEqual(matrix.ides[1], 'Eclipse');
  assert('Chat feature' in matrix.cells);
  assert('VS Code' in matrix.cells['Chat feature']);
  assert('Eclipse' in matrix.cells['Chat feature']);
});

test('buildMatrix selects earliest version for each IDE', () => {
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
  
  const matrix = buildMatrix(results);
  const cell = matrix.cells['Feature X']['VS Code'];
  assert.strictEqual(cell.earliest, '1.0.0');
});

test('buildMatrix builds summary of earliest mention per IDE', () => {
  const results = [
    {
      snippet: 'Feature A',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.5.0',
      release_date: '2023-06-15',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Feature B',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2023-01-01',
      url: 'https://example.com/2',
    },
  ];
  
  const matrix = buildMatrix(results);
  const summaryEntry = matrix.summary.find(s => s.ide === 'VS Code');
  assert(summaryEntry);
  // Should pick the earliest version overall
  assert.strictEqual(summaryEntry.version, '1.0.0');
});

test('buildMatrix sorts snippets by earliest release date', () => {
  const results = [
    {
      snippet: 'Feature C',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2026-03-01',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Feature A',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/2',
    },
    {
      snippet: 'Feature B',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2026-02-01',
      url: 'https://example.com/3',
    },
  ];

  const matrix = buildMatrix(results);
  // Should be sorted by release_date, not alphabetically
  assert.deepStrictEqual(matrix.snippets, ['Feature A', 'Feature B', 'Feature C']);
});

test('buildMatrix orders rows by release date when same IDE shows features at different times', () => {
  const results = [
    {
      snippet: 'Inline edits',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.90.0',
      release_date: '2024-05-01',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Chat',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.88.0',
      release_date: '2024-03-01',
      url: 'https://example.com/2',
    },
    {
      snippet: 'Vision',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.91.0',
      release_date: '2024-06-01',
      url: 'https://example.com/3',
    },
  ];

  const matrix = buildMatrix(results);
  assert.deepStrictEqual(matrix.snippets, ['Chat', 'Inline edits', 'Vision']);
});

test('buildMatrix sorts snippets by alphabetically when IDEs showed features at different times', () => {
  const results = [
    {
      snippet: 'Zebra feature',
      ide: 'eclipse',
      ide_name: 'Eclipse',
      version: '1.0.0',
      release_date: '2026-01-01',
      url: 'https://example.com/1',
    },
    {
      snippet: 'Apple feature',
      ide: 'vscode',
      ide_name: 'VS Code',
      version: '1.0.0',
      release_date: '2026-02-01',
      url: 'https://example.com/2',
    },
  ];

  const matrix = buildMatrix(results);
  // Zebra was first (2026-01-01), so it comes first
  assert.deepStrictEqual(matrix.snippets, ['Zebra feature', 'Apple feature']);
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

test('buildMatrix sorts IDEs in custom order (VS Code, CLI, VS 2022, VS 2026, JetBrains, Xcode, Eclipse, Vim)', () => {
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

  const matrix = buildMatrix(results);
  // Should follow custom order: VS Code, CLI, JetBrains, Eclipse
  assert.strictEqual(matrix.ides[0], 'GitHub Copilot for VS Code');
  assert.strictEqual(matrix.ides[1], 'GitHub Copilot CLI');
  assert.strictEqual(matrix.ides[2], 'GitHub Copilot for JetBrains');
  assert.strictEqual(matrix.ides[3], 'Copilot for Eclipse');
});
