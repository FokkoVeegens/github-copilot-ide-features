/**
 * Fills the "Last updated" column on the data sources page with the newest
 * collected release date per IDE from meta.json.
 */
import { formatDate, formatRelativeDate, parseReleaseDate } from './search.js';

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
    if (!response.ok) return;
    const meta = await response.json();
    renderLastUpdated(document, meta.ide_last_updated);
  } catch (error) {
    console.error('Failed to load source update dates:', error);
  }
}

init();
