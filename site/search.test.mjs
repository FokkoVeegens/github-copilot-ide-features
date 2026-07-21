/**
 * Tests for site/search.js using Node's built-in test runner.
 * Run with: node --test site/search.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert';
import { validateQuery, searchIndex, buildMatrix, formatIdeName, buildSnippetExcerpt } from './search.js';

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

test('formatIdeName removes "GitHub Copilot" prefix', () => {
  assert.strictEqual(formatIdeName('GitHub Copilot for VS Code'), 'for VS Code');
  assert.strictEqual(formatIdeName('GitHub Copilot CLI'), 'CLI');
  assert.strictEqual(formatIdeName('GitHub Copilot for JetBrains'), 'for JetBrains');
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
