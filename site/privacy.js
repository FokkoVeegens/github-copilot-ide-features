/**
 * Opt-out toggle for Umami analytics on the privacy page.
 * Umami's tracker skips all tracking while localStorage['umami.disabled'] is set.
 */
const STORAGE_KEY = 'umami.disabled';

function isDisabled() {
  return localStorage.getItem(STORAGE_KEY) !== null;
}

function render(button, status, disabled) {
  button.textContent = disabled ? 'Allow visit counting' : 'Stop counting my visits';
  button.setAttribute('aria-pressed', String(disabled));
  status.textContent = disabled
    ? 'Your visits are not counted in this browser.'
    : 'Your visits are counted anonymously.';
}

function init() {
  const button = document.getElementById('analytics-toggle');
  const status = document.getElementById('analytics-status');

  try {
    render(button, status, isDisabled());
  } catch {
    status.textContent = 'Your browser blocks local storage, so this setting cannot be saved. Use a content blocker instead.';
    return;
  }

  button.hidden = false;
  button.addEventListener('click', () => {
    try {
      const disabled = isDisabled();
      if (disabled) {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, '1');
      }
      render(button, status, !disabled);
    } catch {
      status.textContent = 'Your choice could not be saved. Try again or use a content blocker.';
    }
  });
}

init();
