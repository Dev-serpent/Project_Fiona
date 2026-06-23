/* ==========================================================================
   LoadingSkeleton.js — Skeleton Loading Placeholders
   ==========================================================================
   Provides skeleton placeholder HTML generators for various content
   shapes (card, text, circle, rect, table-row, chart) with pulse
   animation via CSS.  Also includes a group helper for composing
   complex page-level loading states.

   Usage:
     import {
       skeletonText,
       skeletonCard,
       skeletonCircle,
       skeletonRect,
       skeletonTableRow,
       skeletonChart,
       skeletonGroup,
     } from './LoadingSkeleton.js';

     container.innerHTML = skeletonGroup([
       skeletonCard(),
       skeletonText({ lines: 3 }),
       skeletonTableRow({ columns: 4 }),
     ]);
   ========================================================================== */

import { html } from './BaseComponent.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  skeleton: 'c-skeleton',
  text: 'c-skeleton--text',
  heading: 'c-skeleton--heading',
  circle: 'c-skeleton--circle',
  rect: 'c-skeleton--rect',
  card: 'c-skeleton--card',
  avatar: 'c-skeleton--avatar',
  badge: 'c-skeleton--badge',
  button: 'c-skeleton--button',
  group: 'c-skeleton-group',
  groupRow: 'c-skeleton-group--row',
};

/**
 * @typedef {Object} SkeletonOptions
 * @property {number|string} [width] - CSS width value
 * @property {number|string} [height] - CSS height value
 * @property {string} [className] - Additional CSS classes
 * @property {string} [style] - Inline styles
 */

/* ── Individual Skeleton Helpers ───────────────────────────────────────── */

/**
 * Generate a text line skeleton.
 * @param {SkeletonOptions & { lines?: number }} [options]
 * @returns {string} HTML string
 */
export function skeletonText(options = {}) {
  const lines = options.lines || 1;
  const width = options.width || '100%';
  const extraClass = options.className || '';
  const extraStyle = options.style || '';

  return Array.from({ length: lines }, (_, i) => {
    const isLast = i === lines - 1 && lines > 1;
    return html`
      <div class="${CSS.skeleton} ${CSS.text} ${extraClass}"
           style="width: ${isLast ? '60%' : width}; ${extraStyle}"></div>
    `;
  }).join('');
}

/**
 * Generate a heading skeleton.
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonHeading(options = {}) {
  const width = options.width || '40%';
  return html`
    <div class="${CSS.skeleton} ${CSS.heading}"
         style="width: ${width}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate a circle skeleton (avatar or icon).
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonCircle(options = {}) {
  const size = options.width || options.height || '36px';
  return html`
    <div class="${CSS.skeleton} ${CSS.circle} ${options.className || ''}"
         style="width: ${size}; height: ${size}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate a rectangle skeleton.
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonRect(options = {}) {
  const width = options.width || '100%';
  const height = options.height || '80px';
  return html`
    <div class="${CSS.skeleton} ${CSS.rect} ${options.className || ''}"
         style="width: ${width}; height: ${height}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate a card skeleton.
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonCard(options = {}) {
  const width = options.width || '100%';
  const height = options.height || '120px';
  return html`
    <div class="${CSS.skeleton} ${CSS.card} ${options.className || ''}"
         style="width: ${width}; height: ${height}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate an avatar skeleton (smaller circle).
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonAvatar(options = {}) {
  const size = options.width || options.height || '32px';
  return html`
    <div class="${CSS.skeleton} ${CSS.avatar} ${options.className || ''}"
         style="width: ${size}; height: ${size}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate a badge skeleton.
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonBadge(options = {}) {
  const width = options.width || '60px';
  const height = options.height || '20px';
  return html`
    <div class="${CSS.skeleton} ${CSS.badge} ${options.className || ''}"
         style="width: ${width}; height: ${height}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate a button skeleton.
 * @param {SkeletonOptions} [options]
 * @returns {string}
 */
export function skeletonButton(options = {}) {
  const width = options.width || '80px';
  const height = options.height || '32px';
  return html`
    <div class="${CSS.skeleton} ${CSS.button} ${options.className || ''}"
         style="width: ${width}; height: ${height}; ${options.style || ''}"></div>
  `;
}

/**
 * Generate a table row skeleton.
 * @param {Object} [options]
 * @param {number} [options.columns=4] - Number of columns
 * @param {number|string} [options.height='28px'] - Row height
 * @returns {string}
 */
export function skeletonTableRow(options = {}) {
  const cols = options.columns || 4;
  const height = options.height || '28px';
  const rows = options.rows || 1;

  const row = html`
    <div style="display: flex; gap: var(--space-3); padding: var(--space-3) 0;
                border-bottom: 1px solid var(--border-subtle);">
      ${Array.from({ length: cols }, (_, i) => html`
        <div class="${CSS.skeleton} ${CSS.text}"
             style="flex: ${i === 0 ? '2' : '1'}; height: ${height};"></div>
      `)}
    </div>
  `;

  return Array.from({ length: rows }, () => row).join('');
}

/**
 * Generate a chart skeleton (bar or line chart placeholder).
 * @param {Object} [options]
 * @param {number} [options.bars=8] - Number of bar placeholders
 * @param {number|string} [options.height='120px']
 * @returns {string}
 */
export function skeletonChart(options = {}) {
  const bars = options.bars || 8;
  const height = options.height || '120px';

  const barHeights = [];
  for (let i = 0; i < bars; i++) {
    barHeights.push(30 + Math.random() * 70);
  }

  return html`
    <div style="display: flex; align-items: flex-end; gap: 4px; height: ${height};
                padding: var(--space-3) 0;">
      ${barHeights.map((h) => html`
        <div class="${CSS.skeleton}"
             style="flex: 1; height: ${h}%; border-radius: var(--radius-sm) var(--radius-sm) 0 0;"></div>
      `)}
    </div>
  `;
}

/* ── Group Helper ──────────────────────────────────────────────────────── */

/**
 * Wrap multiple skeleton items in a group container.
 * @param {string|string[]} children - Skeleton HTML string(s)
 * @param {Object} [options]
 * @param {'column'|'row'} [options.direction='column']
 * @param {string} [options.className]
 * @returns {string}
 */
export function skeletonGroup(children, options = {}) {
  const items = Array.isArray(children) ? children.join('') : children;
  const directionClass = options.direction === 'row' ? CSS.groupRow : '';

  return html`
    <div class="${CSS.group} ${directionClass} ${options.className || ''}">
      ${html.raw(items)}
    </div>
  `;
}

/* ── Pre-built page layouts ────────────────────────────────────────────── */

/**
 * Generate a loading skeleton for the dashboard page.
 * @returns {string}
 */
export function dashboardSkeleton() {
  return html`
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-4);">
      ${Array.from({ length: 4 }, () => skeletonCard({ height: '140px' }))}
    </div>
    <div style="margin-top: var(--space-6);">
      ${skeletonHeading()}
      ${skeletonTableRow({ columns: 5, rows: 5 })}
    </div>
  `;
}

/**
 * Generate a loading skeleton for a list page.
 * @returns {string}
 */
export function listPageSkeleton() {
  return html`
    <div style="display: flex; justify-content: space-between; margin-bottom: var(--space-4);">
      ${skeletonHeading({ width: '200px' })}
      ${skeletonButton({ width: '100px' })}
    </div>
    ${skeletonTableRow({ columns: 4, rows: 8 })}
  `;
}

/**
 * Generate a loading skeleton for the chat page.
 * @returns {string}
 */
export function chatSkeleton() {
  return html`
    <div style="display: flex; flex-direction: column; gap: var(--space-4); padding: var(--space-4);">
      ${Array.from({ length: 4 }, (_, i) => html`
        <div style="display: flex; gap: var(--space-3); ${i % 2 === 0 ? '' : 'flex-direction: row-reverse;'}">
          ${skeletonAvatar()}
          <div style="flex: 1; ${i % 2 === 0 ? '' : 'display: flex; flex-direction: column; align-items: flex-end;'}">
            ${skeletonText({ lines: 2, width: '60%' })}
          </div>
        </div>
      `)}
    </div>
  `;
}
