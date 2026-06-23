/* ==========================================================================
   ActivityTimeline.js — Chronological Activity Feed
   ==========================================================================
   Displays a chronological list of events grouped by date, with
   per-event-type icons, relative timestamps, expandable details,
   infinite scroll / "Load more" button, and optional type-based
   filtering.

   Usage:
     import { createActivityTimeline } from './ActivityTimeline.js';

     const timeline = createActivityTimeline('#activity-feed', {
       loadEvents: async (offset, limit) => {
         const res = await api.get('/api/events?offset=' + offset + '&limit=' + limit);
         return res.events;
       },
       pageSize: 20,
     });

     timeline.loadMore();
     timeline.setFilter('error');
     timeline.destroy();
   ========================================================================== */

import { html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── Relative time formatting ──────────────────────────────────────────── */

/**
 * Format a timestamp as a relative time string.
 * @param {string|number|Date} timestamp
 * @returns {string}
 */
function timeAgo(timestamp) {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;

  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;

  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;

  const years = Math.floor(days / 365);
  return `${years}y ago`;
}

/**
 * Extract a date label (e.g. "Today", "Yesterday", "Monday", "Jun 22").
 * @param {string|number|Date} timestamp
 * @returns {string}
 */
function dateLabel(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (target.getTime() === today.getTime()) return 'Today';
  if (target.getTime() === yesterday.getTime()) return 'Yesterday';

  const diff = (today.getTime() - target.getTime()) / 86400000;
  if (diff < 7) {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    return days[date.getDay()];
  }

  const month = date.toLocaleString('default', { month: 'short' });
  const day = date.getDate();
  const year = date.getFullYear() !== now.getFullYear() ? ` ${date.getFullYear()}` : '';
  return `${month} ${day}${year}`;
}

/**
 * Get an icon for an event type.
 * @param {string} type
 * @returns {string}
 */
function getEventIcon(type) {
  switch (type) {
    case 'message':   return ICONS.message;
    case 'bot':       return ICONS.bot;
    case 'error':     return ICONS.error;
    case 'warning':   return ICONS.warning;
    case 'success':   return ICONS.success;
    case 'info':      return ICONS.info;
    case 'file':      return ICONS.file;
    case 'folder':    return ICONS.folder;
    case 'terminal':  return ICONS.terminal;
    case 'gear':      return ICONS.gear;
    case 'bolt':      return ICONS.bolt;
    case 'activity':  return ICONS.activity;
    default:          return ICONS.activity;
  }
}

/**
 * @typedef {Object} TimelineEvent
 * @property {string} id - Unique event ID
 * @property {string} type - Event type (determines icon)
 * @property {string} title - Event title
 * @property {string} [description] - Event description
 * @property {string|number|Date} timestamp - ISO date string or ms
 * @property {Object} [details] - Expandable detail data (rendered as JSON)
 * @property {boolean} [important=false] - Highlight the event
 */

/**
 * Create an activity timeline.
 *
 * @param {string|Element} container - Container element
 * @param {Object} callbacks
 * @param {Function} callbacks.loadEvents - async (offset, limit) => TimelineEvent[]
 * @param {Object} [options]
 * @param {number} [options.pageSize=20] - Events to load per batch
 * @param {string[]} [options.types] - Available event types for filtering
 * @returns {ActivityTimelineAPI}
 */
export function createActivityTimeline(container, callbacks, options = {}) {
  /** @type {Element} */
  let _container = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (!_container) {
    console.error('[ActivityTimeline] Container not found:', container);
    return null;
  }

  const _loadEvents = callbacks.loadEvents || (async () => []);
  const _pageSize = options.pageSize || 20;
  const _eventTypes = options.types || [];

  /** @type {TimelineEvent[]} */
  let _events = [];

  /** @type {boolean} */
  let _loading = false;

  /** @type {boolean} */
  let _hasMore = true;

  /** @type {number} */
  let _offset = 0;

  /** @type {string|null} Active type filter */
  let _activeFilter = null;

  /** @type {Set<string>} IDs of expanded events */
  let _expandedIds = new Set();

  /** @type {boolean} */
  let _destroyed = false;

  /* ── Data Loading ────────────────────────────────────────────────────── */

  /**
   * Load the next page of events.
   * @returns {Promise<void>}
   * @private
   */
  async function _loadPage() {
    if (_loading || !_hasMore || _destroyed) return;
    _loading = true;
    _showLoader(true);

    try {
      const newEvents = await _loadEvents(_offset, _pageSize);
      if (!newEvents || newEvents.length === 0) {
        _hasMore = false;
      } else {
        _events = [..._events, ...newEvents];
        _offset += newEvents.length;
        if (newEvents.length < _pageSize) {
          _hasMore = false;
        }
      }
    } catch (err) {
      console.error('[ActivityTimeline] Error loading events:', err);
    } finally {
      _loading = false;
      _showLoader(false);
      _render();
    }
  }

  /**
   * Show/hide the loading indicator.
   * @param {boolean} show
   * @private
   */
  function _showLoader(show) {
    const loader = _container.querySelector('#timeline-loader');
    if (loader) {
      loader.style.display = show ? 'flex' : 'none';
    }
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  function _render() {
    if (_destroyed) return;

    const filtered = _activeFilter
      ? _events.filter((e) => e.type === _activeFilter)
      : _events;

    // Group by date
    const groups = _groupByDate(filtered);

    _container.innerHTML = html`
      <!-- Filters -->
      ${_eventTypes.length > 0 ? html`
        <div style="display: flex; gap: var(--space-1); padding: var(--space-3) var(--space-4);
                     border-bottom: 1px solid var(--border-subtle); flex-wrap: wrap;">
          <button class="c-btn c-btn--sm ${_activeFilter === null ? 'c-btn--primary' : 'c-btn--ghost'}"
                  data-filter-all>All</button>
          ${_eventTypes.map((type) => html`
            <button class="c-btn c-btn--sm ${_activeFilter === type ? 'c-btn--primary' : 'c-btn--ghost'}"
                    data-filter-type="${type}">${type}</button>
          `)}
        </div>
      ` : ''}

      <!-- Timeline -->
      <div style="padding: var(--space-3); overflow-y: auto;">
        ${groups.length === 0 ? html`
          <div style="text-align: center; padding: 40px 16px; color: var(--text-muted); font-size: 13px;">
            No activity yet.
          </div>
        ` : groups.map(({ date, events }) => html`
          <div style="margin-bottom: var(--space-4);">
            <div style="font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold);
                        color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;
                        padding: var(--space-2) var(--space-2); margin-bottom: var(--space-1);">
              ${date}
            </div>
            <div style="position: relative; padding-left: 24px;">
              <!-- Vertical line -->
              <div style="position: absolute; left: 8px; top: 0; bottom: 0; width: 1px;
                          background: var(--border-subtle);"></div>
              ${events.map((event) => _renderEvent(event))}
            </div>
          </div>
        `)}
      </div>

      <!-- Load more -->
      ${_hasMore ? html`
        <div style="padding: var(--space-3); text-align: center; border-top: 1px solid var(--border-subtle);">
          <button class="c-btn c-btn--ghost c-btn--sm" id="timeline-load-more"
                  ${_loading ? 'disabled' : ''}>
            ${_loading ? 'Loading…' : 'Load more'}
          </button>
        </div>
      ` : ''}

      <!-- Loader (inline) -->
      <div id="timeline-loader" style="display: none; padding: var(--space-3); justify-content: center;">
        <span class="c-spinner c-spinner--sm c-spinner--accent">${ICONS.refresh}</span>
      </div>
    `;

    _bindEvents();
  }

  /**
   * Render a single timeline event.
   * @param {TimelineEvent} event
   * @returns {string}
   * @private
   */
  function _renderEvent(event) {
    const isExpanded = _expandedIds.has(event.id);
    const icon = getEventIcon(event.type);
    const time = timeAgo(event.timestamp);

    return html`
      <div style="position: relative; padding: var(--space-2) var(--space-2) var(--space-3) var(--space-3);
                  margin-left: 0; transition: background var(--transition-fast); border-radius: var(--radius-md);
                  ${event.important ? 'background: var(--accent-muted);' : ''}"
           data-event-id="${event.id}">
        <!-- Dot on the timeline -->
        <div style="position: absolute; left: -20px; top: 12px; width: 10px; height: 10px;
                    border-radius: var(--radius-full); background: var(--bg-secondary);
                    border: 2px solid var(--text-muted); z-index: 1;
                    display: flex; align-items: center; justify-content: center;">
        </div>

        <div style="display: flex; align-items: flex-start; gap: var(--space-2);">
          <!-- Icon -->
          <div style="width: 20px; height: 20px; display: flex; align-items: center;
                      justify-content: center; flex-shrink: 0; color: var(--text-muted); margin-top: 1px;">
            ${icon}
          </div>

          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
              <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium);
                           color: var(--text-primary);">${event.title}</span>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">${time}</span>
            </div>

            ${event.description ? html`
              <div style="font-size: var(--font-size-xs); color: var(--text-secondary);
                          margin-top: 2px; line-height: var(--line-height-normal);">
                ${event.description}
              </div>
            ` : ''}

            ${event.details ? html`
              <div style="margin-top: var(--space-1);">
                <button class="c-btn c-btn--sm c-btn--ghost"
                        data-toggle-details="${event.id}"
                        style="font-size: var(--font-size-xxs); padding: 2px 8px;">
                  ${isExpanded ? 'Hide details' : 'Show details'}
                </button>
                ${isExpanded ? html`
                  <pre style="margin-top: var(--space-2); padding: var(--space-2); background: var(--surface);
                              border: 1px solid var(--border); border-radius: var(--radius-sm);
                              font-size: var(--font-size-xxs); overflow-x: auto;
                              max-height: 200px;">
                    ${JSON.stringify(event.details, null, 2)}
                  </pre>
                ` : ''}
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Group events by date label.
   * @param {TimelineEvent[]} events
   * @returns {Array<{date: string, events: TimelineEvent[]}>}
   * @private
   */
  function _groupByDate(events) {
    const groups = new Map();
    for (const event of events) {
      const label = dateLabel(event.timestamp);
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(event);
    }
    return Array.from(groups.entries()).map(([date, evts]) => ({ date, events: evts }));
  }

  /* ── Events ──────────────────────────────────────────────────────────── */

  function _bindEvents() {
    // Load more
    const loadMoreBtn = _container.querySelector('#timeline-load-more');
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', () => _loadPage());
    }

    // Toggle details
    _container.querySelectorAll('[data-toggle-details]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.toggleDetails;
        if (_expandedIds.has(id)) _expandedIds.delete(id);
        else _expandedIds.add(id);
        _render();
      });
    });

    // Filter buttons
    _container.querySelectorAll('[data-filter-all]').forEach((btn) => {
      btn.addEventListener('click', () => {
        _activeFilter = null;
        _render();
      });
    });

    _container.querySelectorAll('[data-filter-type]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.filterType;
        _activeFilter = _activeFilter === type ? null : type;
        _render();
      });
    });
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Load the initial batch of events.
   */
  async function loadMore() {
    await _loadPage();
  }

  /**
   * Set an active type filter.
   * @param {string|null} type - Event type, or null to clear filter
   */
  function setFilter(type) {
    _activeFilter = type || null;
    _render();
  }

  /**
   * Get the current filter.
   * @returns {string|null}
   */
  function getFilter() {
    return _activeFilter;
  }

  /**
   * Add a single event to the top of the timeline.
   * @param {TimelineEvent} event
   */
  function addEvent(event) {
    if (_destroyed) return;
    _events = [event, ..._events];
    _offset++;
    _render();
  }

  /**
   * Clear all events and reload.
   */
  async function refresh() {
    if (_destroyed) return;
    _events = [];
    _offset = 0;
    _hasMore = true;
    await _loadPage();
  }

  /**
   * Get the current number of loaded events.
   * @returns {number}
   */
  function count() {
    return _events.length;
  }

  /**
   * Remove the timeline from the DOM.
   */
  function destroy() {
    _destroyed = true;
    _container.innerHTML = '';
    _events = [];
    _expandedIds.clear();
  }

  // Initial load
  _loadPage();

  return {
    loadMore,
    setFilter,
    getFilter,
    addEvent,
    refresh,
    count,
    destroy,
  };
}

/**
 * @typedef {Object} ActivityTimelineAPI
 * @property {() => Promise<void>} loadMore
 * @property {(type: string|null) => void} setFilter
 * @property {() => string|null} getFilter
 * @property {(event: TimelineEvent) => void} addEvent
 * @property {() => Promise<void>} refresh
 * @property {() => number} count
 * @property {() => void} destroy
 */

export default createActivityTimeline;
