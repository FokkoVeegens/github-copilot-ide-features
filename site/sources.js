/**
 * Renders collected release dates and monthly history from meta.json.
 */
import { formatDate, formatRelativeDate, parseReleaseDate } from './search.js';

export function buildReleaseTimeline(histories, now = new Date()) {
  const counts = Object.values(histories).flatMap(history => Object.entries(history.months));
  const end = now.getUTCFullYear() * 12 + now.getUTCMonth();
  const months = Array.from({ length: 6 }, (_, index) => {
    const monthIndex = end - 5 + index;
    return `${Math.floor(monthIndex / 12)}-${String(monthIndex % 12 + 1).padStart(2, '0')}`;
  });
  const monthSet = new Set(months);
  return {
    months,
    maximum: Math.max(1, ...counts
      .filter(([month]) => monthSet.has(month))
      .map(([, count]) => count)),
  };
}

function monthLabel(month) {
  return new Date(`${month}-01T00:00:00Z`).toLocaleDateString('en-GB', {
    month: 'short', year: 'numeric', timeZone: 'UTC',
  });
}

function svgElement(name, attributes) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

function renderReleaseHistory(root, histories) {
  if (!histories) return;
  const { months, maximum } = buildReleaseTimeline(histories);
  for (const cell of root.querySelectorAll('[data-release-history]')) {
    const history = histories[cell.dataset.releaseHistory];
    if (!history) continue;
    const total = months.reduce((sum, month) => sum + (history.months[month] || 0), 0);
    const figure = document.createElement('figure');
    const caption = document.createElement('figcaption');
    caption.textContent = `${total} ${total === 1 ? 'release' : 'releases'} in this period`;
    figure.append(caption);

    if (months.length) {
      const name = cell.closest('tr').querySelector('th').textContent;
      const range = `${monthLabel(months[0])} to ${monthLabel(months.at(-1))}`;
      const monthlyCounts = months.map(month =>
        `${monthLabel(month)}: ${history.months[month] || 0} releases`,
      ).join('; ');
      const plot = document.createElement('div');
      plot.className = 'release-history-plot';
      const svg = svgElement('svg', {
        viewBox: '0 0 360 112', role: 'img',
        'aria-label': `${name}: releases per month, ${range}. Scale: 0 to ${maximum} releases. ${monthlyCounts}.`,
      });
      plot.append(svg);
      for (const [value, y] of [[maximum, 34], [0, 98]]) {
        const label = svgElement('text', { x: 24, y: y + 4, 'text-anchor': 'end' });
        label.textContent = value;
        svg.append(label, svgElement('line', { x1: 30, x2: 360, y1: y, y2: y }));
      }
      const step = 330 / months.length;
      const monthLabels = document.createElement('div');
      monthLabels.className = 'release-history-months';
      monthLabels.setAttribute('aria-hidden', 'true');
      for (const [index, month] of months.entries()) {
        const count = history.months[month] || 0;
        const height = count / maximum * 64;
        const x = 30 + index * step;
        const column = svgElement('g', { class: 'release-history-month' });
        const title = svgElement('title', {});
        title.textContent = `${monthLabel(month)}: ${count} releases`;
        column.append(title, svgElement('rect', {
          class: 'release-history-hit-area',
          x, y: 0, width: step, height: 112,
        }));
        if (count) {
          column.append(svgElement('rect', {
            class: 'release-history-bar',
            x: x + step * 0.1, y: 98 - height,
            width: step * 0.8, height,
          }));
        }
        svg.append(column);

        const countLabel = document.createElement('span');
        countLabel.className = 'release-history-count';
        countLabel.setAttribute('aria-hidden', 'true');
        countLabel.textContent = count;
        countLabel.style.left = `${(x + step / 2) / 360 * 100}%`;
        countLabel.style.bottom = `${(14 + height) / 112 * 100}%`;
        plot.append(countLabel);

        const label = document.createElement('span');
        label.textContent = monthLabel(month).split(' ')[0];
        monthLabels.append(label);
      }
      const axis = document.createElement('div');
      axis.className = 'release-history-axis';
      for (const month of [months[0], months.at(-1)]) {
        const label = document.createElement('span');
        label.textContent = monthLabel(month);
        axis.append(label);
      }
      figure.append(plot, monthLabels, axis);
    }
    cell.replaceChildren(figure);
  }
}

function renderLastUpdated(root, ideLastUpdated, now = new Date()) {
  for (const cell of root.querySelectorAll('[data-last-updated]')) {
    const value = ideLastUpdated?.[cell.dataset.lastUpdated];
    const date = parseReleaseDate(value);
    if (!date) continue;

    const time = document.createElement('time');
    time.dateTime = value;
    time.title = formatDate(date);
    time.textContent = formatRelativeDate(date, now);
    cell.replaceChildren(time);
  }
}

async function init() {
  try {
    const response = await fetch('./meta.json');
    if (!response.ok) throw new Error(`Metadata request failed: ${response.status}`);
    const meta = await response.json();
    renderLastUpdated(document, meta.ide_last_updated);
    renderReleaseHistory(document, meta.ide_release_history);
  } catch (error) {
    console.error('Failed to load source metadata:', error);
  }
}

if (typeof document !== 'undefined') init();
