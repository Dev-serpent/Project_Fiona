import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';

function esc(str) {
  if (str == null) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

export function createPlaceholderPage({
  title,
  subtitle,
  icon = 'info',
  description,
  items = [],
  actions = [],
}) {
  let container = null;

  function render(routeInfo = {}) {
    const routePath = routeInfo?.path ? esc(routeInfo.path) : '';
    const itemHtml = items.length
      ? `<ul class="c-list" style="margin-top: var(--space-4);">
          ${items.map((item) => `
            <li class="c-list__item" style="padding: var(--space-3) var(--space-4);">
              <div style="font-weight: var(--font-weight-medium); color: var(--text-primary);">${esc(item.title)}</div>
              ${item.detail ? `<div style="margin-top: 4px; color: var(--text-muted); font-size: var(--font-size-sm);">${esc(item.detail)}</div>` : ''}
            </li>
          `).join('')}
        </ul>`
      : '';

    const actionHtml = actions.length
      ? `<div style="display: flex; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-4);">
          ${actions.map((action) => `
            <button class="c-btn c-btn--sm" data-action="${esc(action.action)}">
              <span class="c-btn__icon">${ICONS[action.icon] || ICONS.info}</span>
              ${esc(action.label)}
            </button>
          `).join('')}
        </div>`
      : '';

    return html`
      <div class="c-card" style="max-width: 960px; margin: 0 auto;">
        <div class="c-card__body" style="padding: var(--space-6);">
          <div style="display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4);">
            <div style="width: 44px; height: 44px; display: grid; place-items: center; border-radius: var(--radius-lg); background: var(--accent-muted); color: var(--accent);">
              ${ICONS[icon] || ICONS.info}
            </div>
            <div>
              <h2 style="margin: 0; font-size: var(--font-size-xl); color: var(--text-primary);">${esc(title)}</h2>
              <div style="color: var(--text-muted); font-size: var(--font-size-sm);">${esc(subtitle)}</div>
            </div>
          </div>

          <p style="margin: 0; color: var(--text-secondary); line-height: var(--line-height-relaxed);">
            ${esc(description)}
          </p>

          ${routePath ? `<div style="margin-top: var(--space-3); color: var(--text-muted); font-size: var(--font-size-xs);">Route: <code>${routePath}</code></div>` : ''}

          ${itemHtml ? html.raw(itemHtml) : ''}
          ${actionHtml ? html.raw(actionHtml) : ''}
        </div>
      </div>
    `;
  }

  function mount(_container) {
    container = _container;
    if (!container) return;

    container.querySelectorAll('[data-action]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        const action = button.getAttribute('data-action');
        if (action === 'open-settings') {
          window.fiona?.router?.navigate('/settings');
        } else if (action === 'open-dashboard') {
          window.fiona?.router?.navigate('/');
        } else if (action === 'open-config') {
          window.fiona?.router?.navigate('/config');
        } else if (action === 'open-terminal') {
          window.fiona?.router?.navigate('/terminal');
        }
      });
    });
  }

  function destroy() {
    container = null;
  }

  return { render, mount, destroy };
}
