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

const UMAMI_SCRIPT_URL = 'https://cloud.umami.is/script.js';

// Never contact the analytics service from tests; this also simulates visitors
// whose browser blocks the analytics script.
test.beforeEach(async ({ page }) => {
  await page.route('https://cloud.umami.is/**', route => route.abort());
});

async function loadSite(page, index = SEARCH_INDEX) {
  await page.route('**/search-index.json', route => route.fulfill({ json: index }));
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

test('configures Umami to track only the production domain and keeps search working when blocked', async ({ page }) => {
  const analyticsRequests = [];
  page.on('request', request => {
    if (request.url().startsWith('https://cloud.umami.is/')) analyticsRequests.push(request.url());
  });

  await loadSite(page);

  const analytics = page.locator(`script[src="${UMAMI_SCRIPT_URL}"]`);
  await expect(analytics).toHaveCount(1);
  await expect(analytics).toHaveAttribute('data-website-id', 'cc73becd-edb9-4960-bc37-705935831da4');
  await expect(analytics).toHaveAttribute('data-domains', 'fokkoveegens.github.io');
  expect(await analytics.evaluate(script => script.defer)).toBe(true);
  expect(analyticsRequests).toEqual([UMAMI_SCRIPT_URL]);

  await search(page, 'agent mode');
});

test('tracks search terms after typing pauses without changing the searched phrase', async ({ page }) => {
  await page.addInitScript(() => {
    window.umami = {
      track: (name, data) => {
        window.trackedUmamiEvents ??= [];
        window.trackedUmamiEvents.push({ name, data });
      },
    };
  });
  await loadSite(page);

  await page.locator('#search-input').fill('ab');
  await page.waitForTimeout(1100);
  expect(await page.evaluate(() => window.trackedUmamiEvents ?? [])).toEqual([]);

  await page.locator('#search-input').fill('  AGENT MODE  ');
  await expect(page.locator('#results .summary-section')).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.trackedUmamiEvents ?? [])).toHaveLength(1);

  const [event] = await page.evaluate(() => window.trackedUmamiEvents);
  expect(event.name).toBe('search');
  expect(event.data).toMatchObject({
    query: 'AGENT MODE',
    launch_only: true,
  });
  expect(event.data.result_count).toBeGreaterThan(0);

  await page.locator('#search-input').fill(' Agent   Mode ');
  await expect(page.locator('#results')).toHaveText('No matching features found.');
  await expect.poll(() => page.evaluate(() => window.trackedUmamiEvents)).toHaveLength(2);
  const secondEvent = await page.evaluate(() => window.trackedUmamiEvents[1]);
  expect(secondEvent.data).toEqual({ query: 'Agent   Mode', result_count: 0, launch_only: true });
});

test('search event counts deduplicated and capped visible release rows', async ({ page }) => {
  await page.addInitScript(() => {
    window.umami = {
      track: (name, data) => {
        window.trackedUmamiEvents ??= [];
        window.trackedUmamiEvents.push({ name, data });
      },
    };
  });
  const releases = Array.from({ length: 22 }, (_, i) => ({
    ...SEARCH_INDEX[0],
    version: `1.${i}.0`,
  }));
  await loadSite(page, [...releases, releases[0], SEARCH_INDEX[3], SEARCH_INDEX[3]]);
  await search(page, 'agent mode', { launchOnly: false });
  await expect(page.locator('.rows-table .version-link')).toHaveCount(21);
  await expect.poll(() => page.evaluate(() => window.trackedUmamiEvents ?? [])).toHaveLength(1);
  const [event] = await page.evaluate(() => window.trackedUmamiEvents);
  expect(event.data).toEqual({ query: 'agent mode', result_count: 21, launch_only: false });
});

test('privacy page is linked from the footer and lets visitors opt out of analytics', async ({ page }) => {
  await loadSite(page);
  await page.locator('footer a', { hasText: 'Privacy' }).click();
  await expect(page).toHaveURL(/\/privacy\.html$/);
  await expect(page.locator('h1')).toHaveText('Privacy');
  await expect(page.locator(`script[src="${UMAMI_SCRIPT_URL}"]`)).toHaveCount(0);
  await expect(page.locator('article')).toContainText('the search term');

  const toggle = page.locator('#analytics-toggle');
  const status = page.locator('#analytics-status');
  await expect(toggle).toHaveText('Stop counting my visits');
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');

  await toggle.click();
  await expect(toggle).toHaveText('Allow visit counting');
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await expect(status).toHaveText('Your visits are not counted in this browser.');
  expect(await page.evaluate(() => localStorage.getItem('umami.disabled'))).toBe('1');

  await page.reload();
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await toggle.click();
  expect(await page.evaluate(() => localStorage.getItem('umami.disabled'))).toBeNull();
  await expect(status).toHaveText('Your visits are counted anonymously.');

  await expectNoAccessibilityViolations(page, 'body');
});

test('opt-out button maintains readable contrast while hovering and unhovering', async ({ page }) => {
  await page.goto('/privacy.html');
  const toggle = page.locator('#analytics-toggle');
  await expect(toggle).toBeVisible();
  await page.mouse.move(0, 0);

  async function sampleContrastDuring(action) {
    await page.evaluate(() => {
      const button = document.getElementById('analytics-toggle');
      const luminance = color => {
        const channels = color.match(/[\d.]+/g).slice(0, 3).map(Number);
        const linear = channels.map(value => {
          const s = value / 255;
          return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
      };
      window.contrastSamples = new Promise(resolve => {
        const samples = [];
        const start = performance.now();
        function sample() {
          const style = getComputedStyle(button);
          const foreground = luminance(style.color);
          const background = luminance(style.backgroundColor);
          samples.push((Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05));
          if (performance.now() - start < 350) requestAnimationFrame(sample);
          else resolve(samples);
        }
        requestAnimationFrame(sample);
      });
    });
    await action();
    return page.evaluate(() => window.contrastSamples);
  }

  for (const action of [() => toggle.hover(), () => page.mouse.move(0, 0)]) {
    const samples = await sampleContrastDuring(action);
    expect(samples.length).toBeGreaterThan(1);
    expect(Math.min(...samples)).toBeGreaterThanOrEqual(4.5);
  }
});

for (const initiallyDisabled of [false, true]) {
  test(`reports an opt-out storage failure when tracking is ${initiallyDisabled ? 'disabled' : 'enabled'}`, async ({ page }) => {
    await page.addInitScript((disabled) => {
      if (disabled) localStorage.setItem('umami.disabled', '1');
      const method = disabled ? 'removeItem' : 'setItem';
      const original = Storage.prototype[method];
      Storage.prototype[method] = function (key, ...args) {
        if (key === 'umami.disabled') throw new DOMException('Storage unavailable', 'QuotaExceededError');
        return original.call(this, key, ...args);
      };
    }, initiallyDisabled);

    const errors = [];
    page.on('pageerror', error => errors.push(error));
    await page.goto('/privacy.html');
    const toggle = page.locator('#analytics-toggle');
    await expect(toggle).toHaveAttribute('aria-pressed', String(initiallyDisabled));
    await toggle.click();
    await expect(page.locator('#analytics-status')).toHaveText('Your choice could not be saved. Try again or use a content blocker.');
    await expect(toggle).toHaveAttribute('aria-pressed', String(initiallyDisabled));
    expect(await page.evaluate(() => localStorage.getItem('umami.disabled'))).toBe(initiallyDisabled ? '1' : null);
    expect(errors).toEqual([]);
  });
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
  test(`makes collection sources discoverable and readable on ${label}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await loadSite(page);

    const sourceLink = page.locator('.disclaimer').getByRole('link', {
      name: 'the data on this site',
      exact: true,
    });
    await expect(sourceLink).toHaveAttribute('href', './sources.html');
    await expect(page.locator('.source-intro')).toHaveCount(0);
    await search(page, 'agent mode');
    await expect(sourceLink).toBeVisible();
    await page.locator('#search-input').fill('no matching feature');
    await expect(page.locator('#results')).toHaveText('No matching features found.');
    await expect(sourceLink).toBeVisible();
    await sourceLink.focus();
    await expect(sourceLink).not.toHaveCSS('outline-style', 'none');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/sources\.html$/);

    const sources = page.getByRole('region', {
      name: 'Official release notes and feature documentation',
      exact: true,
    });
    await expect(page.locator('h1')).toHaveText('Data sources');
    await expect(
      sources.getByRole('heading', {
        name: 'Official release notes and feature documentation',
      }),
    ).toBeInViewport();
    await expect(sources.locator('tbody th')).toHaveText([
      'VS Code', 'GitHub Copilot CLI', 'Visual Studio 2022', 'Visual Studio 2026',
      'JetBrains', 'Xcode', 'Eclipse', 'Vim/Neovim', 'SQL Server Management Studio',
    ]);
    expect(await sources.getByRole('link').evaluateAll(links => links.map(link => ({
      href: link.href, target: link.target, rel: link.rel,
    })))).toEqual([
      'https://code.visualstudio.com/updates',
      'https://github.com/github/copilot-cli/releases',
      'https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-history',
      'https://learn.microsoft.com/en-us/visualstudio/releases/2026/release-notes',
      'https://plugins.jetbrains.com/plugin/17718-github-copilot/versions',
      'https://docs.github.com/en/copilot/reference/copilot-feature-matrix?tool=xcode',
      'https://github.com/github/CopilotForXcode/blob/main/CHANGELOG.md',
      'https://github.com/microsoft/copilot-for-eclipse/releases',
      'https://docs.github.com/en/copilot/reference/copilot-feature-matrix?tool=vimneovim',
      'https://learn.microsoft.com/en-us/ssms/release-notes-22',
      'https://learn.microsoft.com/en-us/ssms/release-notes-21',
    ].map(href => ({ href, target: '_blank', rel: 'noopener noreferrer' })));
    await expectNoAccessibilityViolations(page, 'main');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      viewport.width,
    );

    await expect(
      page.locator('footer').getByRole('link', { name: 'Feature search' }),
    ).toHaveAttribute('href', './index.html');
    await expect(page.locator('footer').getByRole('link', { name: 'Privacy' })).toHaveAttribute(
      'href',
      './privacy.html',
    );
  });

  test(`links to data sources beside Privacy in the ${label} search footer`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await loadSite(page);
    const footerLinks = page.locator('footer a');
    await expect(footerLinks).toHaveText(['Data sources', 'Privacy']);
    await expect(footerLinks.nth(0)).toHaveAttribute('href', './sources.html');
    await footerLinks.nth(0).click();
    await expect(page).toHaveURL(/\/sources\.html$/);
    await expect(page.locator('h1')).toHaveText('Data sources');
  });

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

test('keeps the source page reachable without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.route('https://cloud.umami.is/**', route => route.abort());
  try {
    await page.goto('/index.html');
    await page.getByRole('link', { name: 'the data on this site', exact: true }).click();
    await expect(page).toHaveURL(/\/sources\.html$/);
    const sources = page.getByRole('region', {
      name: 'Official release notes and feature documentation',
      exact: true,
    });
    await expect(sources).toBeVisible();
    await expect(sources.getByRole('link')).toHaveCount(11);
    await expect(sources.locator('[data-last-updated]')).toHaveText(Array(9).fill('Not available'));
  } finally {
    await context.close();
  }
});

for (const [label, viewport] of [
  ['desktop', DESKTOP_VIEWPORT],
  ['narrow mobile', { width: 320, height: 800 }],
]) {
  test(`shows each IDE's newest collected release date on the ${label} sources page`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.clock.setFixedTime(new Date(2026, 4, 20, 0, 30));
    await page.route('**/meta.json', route => route.fulfill({
      json: {
        generated_at: '2026-05-20T00:00:00Z',
        ide_last_updated: {
          'vs-code': '2026-05-20',
          'copilot-cli': '2026-05-19',
          'visual-studio-2022': '2026-05-13',
          'visual-studio-2026': '2026-05-01',
          jetbrains: '2026-03-01',
          xcode: '2026-05-18',
          eclipse: '2024-01-01',
          'vim-neovim': null,
          'sql-server-management-studio': 'not-a-date',
        },
      },
    }));
    await page.goto('/sources.html');

    const table = page.locator('.sources-table');
    if (viewport === DESKTOP_VIEWPORT) {
      await expect(table.locator('thead th')).toHaveText([
        'IDE', 'Source', 'Last updated', 'Releases per month',
      ]);
    }
    const cells = table.locator('[data-last-updated]');
    await expect(cells).toContainText([
      'today', '1 day ago', '7 days ago', 'more than a week ago', 'more than a month ago',
      '2 days ago', 'more than a year ago', 'Not available', 'Not available',
    ]);

    const xcode = page.getByRole('row', { name: /^Xcode/ }).locator('time');
    await expect(xcode).toHaveAttribute('datetime', '2026-05-18');
    await expect(xcode).toHaveAttribute('title', '18-May-2026');
    await expect(table.locator('time')).toHaveCount(7);
    for (const title of await table.locator('time').evaluateAll(els => els.map(el => el.title))) {
      expect(title).toMatch(/^\d{2}-[A-Z][a-z]{2}-\d{4}$/);
    }

    await expectNoAccessibilityViolations(page, 'main');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      viewport.width,
    );
  });
}

for (const width of [1280, 768, 320]) {
  test(`shows separate release charts with identical axes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const ids = [
      'vs-code', 'copilot-cli', 'visual-studio-2022', 'visual-studio-2026',
      'jetbrains', 'xcode', 'eclipse', 'vim-neovim', 'sql-server-management-studio',
    ];
    const histories = Object.fromEntries(ids.map(id => [id, { months: {}, undated: 0 }]));
    histories['vs-code'] = { months: { '2025-12': 2, '2026-02': 1 }, undated: 3 };
    histories['copilot-cli'] = { months: { '2026-02': 65 }, undated: 0 };
    await page.route('**/meta.json', route => route.fulfill({
      json: { ide_release_history: histories },
    }));
    await page.clock.setFixedTime(new Date('2026-03-20T12:00:00Z'));
    await page.goto('/sources.html');

    const charts = page.locator('.release-history svg');
    await expect(charts).toHaveCount(9);
    for (const chart of await charts.all()) {
      await expect(chart).toBeVisible();
      await expect(chart).toHaveAttribute('aria-label', /Oct 2025 to Mar 2026\. Scale: 0 to 65/);
    }
    const first = page.locator('[data-release-history="vs-code"]');
    const second = page.locator('[data-release-history="copilot-cli"]');
    await expect(first.locator('figcaption')).toHaveText('3 releases in this period');
    await expect(first.locator('.release-history-axis')).toHaveText('Oct 2025Mar 2026');
    const firstBars = first.locator('.release-history-bar');
    await expect(firstBars).toHaveCount(2);
    await expect(firstBars.nth(1)).toHaveAttribute(
      'x', await second.locator('.release-history-bar').getAttribute('x'),
    );
    expect(Number(await firstBars.nth(0).getAttribute('height'))).toBeCloseTo(2 / 65 * 64);
    await expect(second.locator('.release-history-bar')).toHaveAttribute('height', '64');

    await expect(first.locator('.release-history-count')).toHaveText(['0', '0', '2', '0', '1', '0']);
    await expect(first.locator('.release-history-months span')).toHaveText([
      'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar',
    ]);
    for (const count of await first.locator('.release-history-count').all()) {
      await expect(count).toBeVisible();
      expect(await count.evaluate(el => parseFloat(getComputedStyle(el).fontSize)))
        .toBeGreaterThanOrEqual(14);
    }

    for (const index of [0, 2, 4]) {
      const column = first.locator('.release-history-month').nth(index);
      const hitArea = column.locator('.release-history-hit-area');
      const hitBox = await hitArea.boundingBox();
      expect(hitBox.height).toBeGreaterThanOrEqual(40);
      await hitArea.hover({ position: { x: hitBox.width / 2, y: hitBox.height / 4 } });
      await expect(hitArea).toHaveCSS('fill', 'rgba(3, 102, 214, 0.08)');
      await expect(column.locator('title')).toHaveText(
        { 0: 'Oct 2025: 0 releases', 2: 'Dec 2025: 2 releases', 4: 'Feb 2026: 1 release' }[index],
      );
    }
    await expect(page.getByText('Monthly counts', { exact: true })).toHaveCount(0);
    await expect(first.getByRole('img')).toHaveAccessibleName(
      'VS Code: releases per month, Oct 2025 to Mar 2026. Scale: 0 to 65 releases. ' +
      'Oct 2025: 0 releases; Nov 2025: 0 releases; Dec 2025: 2 releases; ' +
      'Jan 2026: 0 releases; Feb 2026: 1 release; Mar 2026: 0 releases.',
    );
    await expectNoAccessibilityViolations(page, 'main');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test('source charts ignore undated counts and handle unavailable metadata', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-03-20T12:00:00Z'));
  await page.route('**/meta.json', route => route.fulfill({
    json: { ide_release_history: {
      'vs-code': { months: {}, undated: 2 },
      'xcode': { months: { '2026-03': 1 } },
    } },
  }));
  await page.goto('/sources.html');
  const first = page.locator('[data-release-history="vs-code"]');
  await expect(first.locator('figcaption')).toHaveText('0 releases in this period');
  await expect(page.locator('[data-release-history="xcode"] figcaption')).toHaveText(
    '1 release in this period',
  );
  await expect(page.locator('[data-release-history="xcode"]').getByRole('img')).toHaveAccessibleName(
    /Scale: 0 to 1 release\..*Mar 2026: 1 release\./,
  );
  await expect(first).not.toContainText('without a known date');
  await expect(first.locator('svg')).toHaveCount(1);
  await expect(page.locator('[data-release-history="copilot-cli"]')).toHaveText(
    'Release history unavailable.',
  );
  await page.route('**/meta.json', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.reload();
  await expect(first).toHaveText('Release history unavailable.');
});

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
