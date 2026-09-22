/**
 * Browser tests for the responsive search-results rendering.
 *
 * Below 600px the four-column table is hidden and each release is rendered as
 * a stacked card. These tests load the real page in Chromium with a stubbed
 * search index and verify the card layout at a narrow viewport.
 */
import { test, expect } from '@playwright/test';

const MOBILE_VIEWPORT = { width: 390, height: 844 };
const DESKTOP_VIEWPORT = { width: 1280, height: 900 };
const FIELD_LABELS = ['Version', 'Date released', 'Feature description'];

/**
 * Deterministic search index:
 * - VS Code has three releases matching "agent mode" (multiple rows per IDE)
 * - Copilot CLI has a single matching release
 * - Eclipse has no matching release, so it renders as an N/A entry
 */
const SEARCH_INDEX = [
  {
    ide: 'vs-code',
    ide_name: 'GitHub Copilot for VS Code',
    version: '1.90.0',
    release_date: '2026-01-15',
    url: 'https://example.test/vs-code/1.90.0',
    snippet: 'Agent mode is available in preview for all users.',
  },
  {
    ide: 'vs-code',
    ide_name: 'GitHub Copilot for VS Code',
    version: '1.91.0',
    release_date: '2026-02-12',
    url: 'https://example.test/vs-code/1.91.0',
    snippet: 'Agent mode now supports custom instructions.',
  },
  {
    ide: 'vs-code',
    ide_name: 'GitHub Copilot for VS Code',
    version: '1.92.0',
    release_date: '2026-03-10',
    url: 'https://example.test/vs-code/1.92.0',
    snippet: 'Agent mode is generally available.',
  },
  {
    ide: 'copilot-cli',
    ide_name: 'GitHub Copilot CLI',
    version: '0.5.0',
    release_date: '2026-02-20',
    url: 'https://example.test/cli/0.5.0',
    snippet: 'Introducing agent mode in the CLI.',
  },
  {
    ide: 'eclipse',
    ide_name: 'Copilot for Eclipse',
    version: '0.9.0',
    release_date: '2026-01-30',
    url: 'https://example.test/eclipse/0.9.0',
    snippet: 'Improved inline completion latency.',
  },
];

async function loadSite(page) {
  await page.route('**/search-index.json', route => route.fulfill({ json: SEARCH_INDEX }));
  await page.route('**/meta.json', route =>
    route.fulfill({ json: { generated_at: '2026-03-15T09:00:00Z' } }),
  );
  await page.goto('/index.html');
  await expect(page.locator('#hint')).toBeVisible();
}

async function search(page, query, { launchOnly = true } = {}) {
  if (!launchOnly) {
    await page.locator('#launch-only-filter').uncheck();
  }
  await page.locator('#search-input').fill(query);
  await expect(page.locator('#results .summary-section')).toBeVisible();
}

/** Locate the value of a labelled field inside a stacked card. */
function fieldValue(card, label) {
  return card
    .locator('.mobile-field')
    .filter({ has: card.page().getByText(label, { exact: true }) })
    .locator('.mobile-field-value');
}

async function expectReleaseCard(card, expected) {
  await expect(card.locator('.mobile-field-label')).toHaveText(FIELD_LABELS);
  await expect(fieldValue(card, 'Version')).toHaveText(`v${expected.version}`);
  await expect(fieldValue(card, 'Date released')).toHaveText(expected.date);
  await expect(fieldValue(card, 'Feature description')).toHaveText(expected.description);
  await expect(card.locator('.desc-cell a')).toHaveAttribute('href', expected.url);
  await expect(card).toBeVisible();
}

test.describe('stacked cards below 600px', () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  test.beforeEach(async ({ page }) => {
    await loadSite(page);
  });

  test('replaces the table with the card layout', async ({ page }) => {
    await search(page, 'agent mode');

    await expect(page.locator('.table-wrapper')).toBeHidden();
    await expect(page.locator('.mobile-results')).toBeVisible();
  });

  test('renders every release of an IDE in its own card, exactly once', async ({ page }) => {
    await search(page, 'agent mode', { launchOnly: false });

    const groups = page.locator('.mobile-results .mobile-ide-group');
    await expect(groups).toHaveCount(3);
    await expect(groups.locator('.mobile-ide-heading')).toHaveText([
      'VS Code',
      'CLI',
      'Eclipse',
    ]);

    const vsCode = groups.nth(0);
    await expect(vsCode.locator('.mobile-ide-heading')).toHaveText('VS Code');
    await expect(vsCode.locator('.mobile-ide-heading img.ide-logo')).toHaveAttribute(
      'src',
      './images/vs-code.svg',
    );
    const vsCodeCards = vsCode.locator('.mobile-release-card');
    await expect(vsCodeCards).toHaveCount(3);
    const expectedVsCodeReleases = [
      {
        version: '1.90.0',
        date: '15-Jan-2026',
        description: 'Agent mode is available in preview for all users.',
        url: 'https://example.test/vs-code/1.90.0',
      },
      {
        version: '1.91.0',
        date: '12-Feb-2026',
        description: 'Agent mode now supports custom instructions.',
        url: 'https://example.test/vs-code/1.91.0',
      },
      {
        version: '1.92.0',
        date: '10-Mar-2026',
        description: 'Agent mode is generally available.',
        url: 'https://example.test/vs-code/1.92.0',
      },
    ];
    for (let index = 0; index < expectedVsCodeReleases.length; index += 1) {
      await expectReleaseCard(vsCodeCards.nth(index), expectedVsCodeReleases[index]);
    }

    const cli = groups.nth(1);
    await expect(cli.locator('.mobile-ide-heading')).toHaveText('CLI');
    await expect(cli.locator('.mobile-ide-heading img.ide-logo')).toHaveAttribute(
      'src',
      './images/copilot-cli.svg',
    );
    const cliCards = cli.locator('.mobile-release-card');
    await expect(cliCards).toHaveCount(1);
    await expectReleaseCard(cliCards.nth(0), {
      version: '0.5.0',
      date: '20-Feb-2026',
      description: 'Introducing agent mode in the CLI.',
      url: 'https://example.test/cli/0.5.0',
    });

    // Only the card layout is visible: each release appears once on screen.
    await expect(page.locator('.mobile-release-card:not(.mobile-release-card-na)')).toHaveCount(4);
    await expect(page.locator('.version-badge:visible')).toHaveCount(4);
  });

  test('shows the IDE logo in each card heading', async ({ page }) => {
    await search(page, 'agent mode', { launchOnly: false });

    const logos = page.locator('.mobile-ide-heading img.ide-logo');
    await expect(logos).toHaveCount(3);
    const expectedSources = [
      './images/vs-code.svg',
      './images/copilot-cli.svg',
      './images/eclipse.svg',
    ];

    for (let index = 0; index < expectedSources.length; index += 1) {
      const logo = logos.nth(index);
      await expect(logo).toHaveAttribute('alt', '');
      await expect(logo).toHaveAttribute('src', expectedSources[index]);
      await expect(logo).toBeVisible();
      const loaded = await logo.evaluate(img => img.complete && img.naturalWidth > 0);
      expect(loaded).toBe(true);
    }
  });

  test('renders IDEs without a matching release as N/A cards', async ({ page }) => {
    await search(page, 'agent mode');

    await expect(page.locator('.mobile-section-title')).toHaveText('Not yet available');

    const naGroups = page.locator('.mobile-ide-group-na');
    await expect(naGroups).toHaveCount(1);
    await expect(naGroups.locator('.mobile-ide-heading')).toHaveText('Eclipse');
    await expect(naGroups.locator('.mobile-ide-heading img.ide-logo')).toHaveAttribute(
      'src',
      './images/eclipse.svg',
    );
    await expect(naGroups.locator('.mobile-field-label')).toHaveText('Availability');
    await expect(naGroups.locator('.mobile-field-value')).toHaveText('❌N/A');
    await expect(naGroups.locator('.na-badge')).toBeVisible();

    // The launch-only filter keeps a single release per IDE; nothing duplicates.
    await expect(page.locator('.mobile-ide-group:not(.mobile-ide-group-na)')).toHaveCount(2);
    await expect(page.locator('.version-badge:visible')).toHaveCount(2);
  });

  test('keeps cards inside the viewport width', async ({ page }) => {
    await search(page, 'agent mode', { launchOnly: false });

    const overflows = await page.evaluate(
      () =>
        [...document.querySelectorAll('.mobile-release-card')].some(
          card => card.getBoundingClientRect().right > window.innerWidth + 1,
        ),
    );
    expect(overflows).toBe(false);
  });
});

test.describe('table layout on wide viewports', () => {
  test.use({ viewport: DESKTOP_VIEWPORT });

  test('shows the table and hides the card layout', async ({ page }) => {
    await loadSite(page);
    await search(page, 'agent mode', { launchOnly: false });

    await expect(page.locator('.table-wrapper')).toBeVisible();
    await expect(page.locator('.mobile-results')).toBeHidden();

    // 3 VS Code rows + 1 CLI row + divider + Eclipse N/A row
    await expect(page.locator('.rows-table tbody tr')).toHaveCount(6);
    await expect(page.locator('.version-badge:visible')).toHaveCount(4);
  });
});
