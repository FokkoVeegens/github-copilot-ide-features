/**
 * Browser tests for the responsive search-results rendering.
 *
 * Below 600px the four-column table is hidden and each release is rendered as
 * a stacked card. These tests load the real page in Chromium with a stubbed
 * search index and verify the card layout at a narrow viewport.
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

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

async function expectNoAccessibilityViolations(page, selector) {
  const results = await new AxeBuilder({ page })
    .include(selector)
    .analyze();

  expect(results.violations).toEqual([]);
}

/** Locate the value of a labelled field inside a stacked card. */
function fieldValue(card, label) {
  const index = FIELD_LABELS.indexOf(label);
  if (index === -1) {
    throw new Error(`Unknown mobile field label: ${label}`);
  }

  return card.locator('.mobile-field').nth(index).locator('.mobile-field-value');
}

async function expectReleaseCard(card, expected) {
  await expect(card.locator('.mobile-field-label')).toHaveText(FIELD_LABELS);
  await expect(fieldValue(card, 'Version')).toHaveText(`v${expected.version}`);
  await expect(fieldValue(card, 'Date released')).toHaveText(expected.date);
  await expect(fieldValue(card, 'Feature description')).toHaveText(expected.description);
  await expect(card.locator('.desc-cell a')).toHaveAttribute('href', expected.url);
  await expect(card).toBeVisible();
}

test('loads a favicon matching the header colors', async ({ page }) => {
  await loadSite(page);

  const favicon = page.locator('link[rel="icon"]');
  await expect(favicon).toHaveAttribute('type', 'image/svg+xml');
  const href = await favicon.getAttribute('href');
  const nestedPage = new URL('/project/index.html', page.url());
  expect(new URL(href, nestedPage).pathname).toBe('/project/images/favicon.svg');

  const icon = await page.evaluate(async () => {
    const image = new Image();
    image.src = document.querySelector('link[rel="icon"]').href;
    await image.decode();

    const canvas = document.createElement('canvas');
    canvas.width = 16;
    canvas.height = 16;
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0, canvas.width, canvas.height);

    const colorComponents = color => color.match(/\d+/g).slice(0, 3).map(Number);
    const header = document.querySelector('header');
    const background = Array.from(context.getImageData(1, Math.floor(canvas.height / 2), 1, 1).data).slice(0, 3);
    const headerBackground = colorComponents(getComputedStyle(header).backgroundColor);
    const headerText = colorComponents(getComputedStyle(header.querySelector('h1')).color);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let hasHeaderTextColor = false;
    for (let i = 0; i < pixels.length; i += 4) {
      if (headerText.every((component, index) => component === pixels[i + index]) && pixels[i + 3] === 255) {
        hasHeaderTextColor = true;
        break;
      }
    }

    return { width: image.naturalWidth, height: image.naturalHeight, background, headerBackground, hasHeaderTextColor };
  });
  expect(icon.width).toBeGreaterThan(0);
  expect(icon.height).toBeGreaterThan(0);
  expect(icon.background).toEqual(icon.headerBackground);
  expect(icon.hasHeaderTextColor).toBe(true);
});

test('shows the last updated date as relative time with an exact tooltip', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-03-17T09:00:00Z'));
  await loadSite(page);

  const lastUpdated = page.locator('#last-updated');
  await expect(lastUpdated).toHaveText('2 days ago');
  const expectedTooltip = await page.evaluate(() => {
    const d = new Date('2026-03-15T09:00:00Z');
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const pad = n => String(n).padStart(2, '0');
    return `${pad(d.getDate())}-${months[d.getMonth()]}-${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  });
  await expect(lastUpdated).toHaveAttribute('title', expectedTooltip);
  await expect(lastUpdated).toHaveAttribute('title', /^\d{2}-[A-Z][a-z]{2}-\d{4} \d{2}:\d{2}$/);
  await expect(lastUpdated).toHaveAttribute('datetime', '2026-03-15T09:00:00.000Z');
});

for (const [label, viewport] of [
  ['desktop', DESKTOP_VIEWPORT],
  ['narrow mobile', { width: 320, height: 800 }],
]) {
  test(`shows an accessible repository link in the ${label} header`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await loadSite(page);

    const header = page.locator('header');
    const heading = header.locator('h1');
    const subtitle = header.locator('.subtitle');
    const link = header.getByRole('link', { name: 'View repository on GitHub' });
    const logo = link.locator('svg');

    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute(
      'href',
      'https://github.com/FokkoVeegens/github-copilot-ide-features',
    );
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(logo).toBeVisible();
    await expect(heading).toHaveCSS('color', 'rgb(255, 255, 255)');
    await expect(subtitle).toHaveCSS('color', 'rgb(255, 255, 255)');
    await expect(logo.locator('path')).toHaveCSS('fill', 'rgb(255, 255, 255)');

    const background = await header.evaluate(element =>
      getComputedStyle(element).backgroundColor.match(/\d+/g).map(Number),
    );
    expect(background[2]).toBeGreaterThan(background[0]);
    expect(background[2]).toBeGreaterThan(background[1]);

    const headingBox = await heading.boundingBox();
    const linkBox = await link.boundingBox();
    expect(linkBox.width).toBeGreaterThanOrEqual(44);
    expect(linkBox.height).toBeGreaterThanOrEqual(44);
    expect(linkBox.x).toBeGreaterThanOrEqual(headingBox.x + headingBox.width);
    expect(linkBox.x + linkBox.width).toBeLessThanOrEqual(viewport.width);
    expect(Math.abs(linkBox.y - headingBox.y)).toBeLessThanOrEqual(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      viewport.width,
    );

    await page.keyboard.press('Tab');
    await expect(link).toBeFocused();
    await expect(link).not.toHaveCSS('outline-style', 'none');
    await expectNoAccessibilityViolations(page, 'header');
  });
}

test('whole-word search excludes substring-only IDEs and highlights only whole matches', async ({ page }) => {
  const index = [
    { ...SEARCH_INDEX[0], snippet: 'Fusion is available despite earlier confusion.' },
    { ...SEARCH_INDEX[3], snippet: 'A fix for confusion is now available.' },
    { ...SEARCH_INDEX[4], snippet: 'Fusion-powered features are now available.' },
  ];
  await page.route('**/search-index.json', route => route.fulfill({ json: index }));
  await page.route('**/meta.json', route => route.fulfill({ json: { generated_at: '2026-03-15T09:00:00Z' } }));
  await page.goto('/index.html');
  await expect(page.locator('#hint')).toBeVisible();
  await expect(page.locator('#hint')).toContainText('whole word or exact phrase (at least 3 characters)');
  await search(page, 'fusion');

  for (const launchOnly of [true, false]) {
    if (!launchOnly) await page.locator('#launch-only-filter').uncheck();
    const table = page.locator('.table-wrapper');
    await expect(table.locator('.snippet-match')).toHaveText(['Fusion', 'Fusion']);
    await expect(table).toContainText('confusion');
    await expect(table).not.toContainText('A fix for confusion');
    await expect(table).toContainText('CLI');
    await expect(page.locator('.mobile-results .snippet-match')).toHaveText(['Fusion', 'Fusion']);
  }
});

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

  test('has no detectable accessibility violations in the mobile results', async ({ page }) => {
    await search(page, 'agent mode', { launchOnly: false });

    await expectNoAccessibilityViolations(page, '#results');
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
    await search(page, 'agent mode', { launchOnly: false });

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

    // All matching releases remain visible alongside the N/A group.
    await expect(page.locator('.mobile-ide-group:not(.mobile-ide-group-na)')).toHaveCount(2);
    await expect(page.locator('.version-badge:visible')).toHaveCount(4);
  });

  test('keeps mobile description links visually identifiable without hover', async ({ page }) => {
    await search(page, 'agent mode', { launchOnly: false });

    const descriptionLink = page.locator('.mobile-release-card .desc-cell a').first();
    const styles = await descriptionLink.evaluate(element => {
      const computed = window.getComputedStyle(element);
      return {
        color: computed.color,
        parentColor: window.getComputedStyle(element.parentElement).color,
        textDecorationLine: computed.textDecorationLine,
      };
    });

    expect(
      styles.textDecorationLine.includes('underline') || styles.color !== styles.parentColor,
    ).toBe(true);
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

test('rejects encoded paths outside the site root', async ({ request }) => {
  const response = await request.get('/%2e%2e%2fsite-private/file');

  expect(response.status()).toBe(403);
});

test('returns a bad request for malformed URI encoding', async ({ request }) => {
  const response = await request.get('/%');

  expect(response.status()).toBe(400);
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

  test('has no detectable accessibility violations in the desktop results', async ({ page }) => {
    await loadSite(page);
    await search(page, 'agent mode', { launchOnly: false });

    await expectNoAccessibilityViolations(page, '#results');
  });
});
