/* ==========================================================================
   devtools.js — Developer Tools for Fiona Debugging
   ==========================================================================
   Tabbed developer utilities: State Inspector, API Playground, Console
   (JS eval), and Event Log.  All features are client-side except the
   API Playground which sends requests to the backend.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const TABS = [
  { id: 'state-inspector', label: 'State Inspector', icon: 'search' },
  { id: 'api-playground',   label: 'API Playground',  icon: 'globe' },
  { id: 'console',          label: 'Console',         icon: 'terminal' },
  { id: 'event-log',        label: 'Event Log',       icon: 'activity' },
];

const API_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: false,

  // Tab
  activeTab: 'state-inspector',

  // State Inspector
  stateSearch: '',
  stateNamespace: '',

  // API Playground
  apiMethod: 'GET',
  apiUrl: '/api/v1/',
  apiBody: '',
  apiHeaders: [{ key: 'Content-Type', value: 'application/json' }],
  apiResponse: null,
  apiResponseTime: null,
  apiResponseStatus: null,
  apiSending: false,

  // Console
  consoleInput: '',
  consoleHistory: [],
  consoleHistoryIndex: -1,
  consoleOutput: [],   // { type, text, timestamp }

  // Event Log
  eventLog: [],         // { type, data, timestamp }
  eventFilter: '',
  wsUnsub: null,
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function getStore() {
  return window.fiona?.store;
}

function esc(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function formatTimestamp(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  const s = date.getSeconds().toString().padStart(2, '0');
  const ms = date.getMilliseconds().toString().padStart(3, '0');
  return `${h}:${m}:${s}.${ms}`;
}

function syntaxHighlight(json) {
  if (typeof json !== 'string') {
    json = JSON.stringify(json, null, 2);
  }
  json = esc(json);
  // Simple JSON syntax highlighting
  json = json.replace(
    /("(?:[^"\\]|\\.)*")\s*:/g,
    '<span style="color: var(--info);">$1</span>:',
  );
  json = json.replace(
    /"((?:[^"\\]|\\.)*)"/g,
    '<span style="color: var(--accent);">"$1"</span>',
  );
  json = json.replace(
    /\b(true|false|null)\b/g,
    '<span style="color: var(--warning);">$1</span>',
  );
  json = json.replace(
    /\b(-?\d+\.?\d*(?:e[+-]?\d+)?)\b/g,
    '<span style="color: var(--success);">$1</span>',
  );
  return json;
}

/* ── Render ─────────────────────────────────────────────────────────────── */

function renderPage(container) {
  if (_state.destroyed) return;
  _state.container = container;

  container.innerHTML = html`
    <!-- Page Header -->
    <div style="margin-bottom: var(--space-4);">
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <div>
          <h1 style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); margin: 0;">
            Developer Tools
          </h1>
          <p style="font-size: var(--font-size-sm); color: var(--text-muted); margin: 2px 0 0 0;">
            Debugging, inspection, and testing utilities
          </p>
        </div>
      </div>
    </div>

    <!-- Tab Bar -->
    <div class="c-tabs" style="margin-bottom: var(--space-4);">
      ${html.raw(TABS.map((tab) => html`
        <div class="c-tab ${tab.id === _state.activeTab ? 'c-tab--active' : ''}"
             data-action="switch-tab" data-tab="${tab.id}"
             style="cursor: pointer;">
          <span class="c-tab__icon">${ICONS[tab.icon] || ICONS.gear}</span>
          <span>${esc(tab.label)}</span>
        </div>
      `).join(''))}
    </div>

    <!-- Tab Content -->
    <div style="min-height: 400px;">
      ${_state.activeTab === 'state-inspector' ? renderStateInspector() : ''}
      ${_state.activeTab === 'api-playground' ? renderApiPlayground() : ''}
      ${_state.activeTab === 'console' ? renderConsole() : ''}
      ${_state.activeTab === 'event-log' ? renderEventLog() : ''}
    </div>
  `;

  mountHandlers(container);
}

/* ── Tab: State Inspector ───────────────────────────────────────────────── */

function renderStateInspector() {
  const store = getStore();
  const state = store?.getState ? store.getState() : store?.state || {};

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">Application State</span>
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <div class="c-input-wrapper" style="width: 180px;">
            <span class="c-input-wrapper__icon c-input-wrapper__icon--left">${ICONS.search}</span>
            <input type="text" class="c-input c-input--sm" id="devtools-state-search"
                   placeholder="Search state…"
                   value="${esc(_state.stateSearch)}"
                   style="padding-left: 32px; font-size: var(--font-size-xs);">
          </div>
          <input type="text" class="c-input c-input--sm" id="devtools-state-namespace"
                 placeholder="Filter namespace…"
                 value="${esc(_state.stateNamespace)}"
                 style="width: 140px; font-size: var(--font-size-xs);">
          <button class="c-btn c-btn--sm c-btn--ghost" id="devtools-copy-state" title="Copy state JSON">
            <span class="c-btn__icon">${ICONS.copy}</span>
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost c-btn--danger" id="devtools-reset-state" title="Reset state">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body" style="padding: 0; max-height: 600px; overflow: auto;">
        <pre id="devtools-state-tree"
             style="margin: 0; padding: var(--space-4); font-family: var(--font-mono);
                    font-size: var(--font-size-xs); line-height: 1.6;
                    color: var(--text-primary); white-space: pre-wrap; word-break: break-all;
                    overflow-x: auto;">
${syntaxHighlight(JSON.stringify(filterState(state), null, 2))}
        </pre>
      </div>
    </div>
  `;
}

function filterState(state) {
  let obj = state;

  // Namespace filter
  if (_state.stateNamespace) {
    const parts = _state.stateNamespace.split('.');
    for (const part of parts) {
      if (obj && typeof obj === 'object' && part in obj) {
        obj = obj[part];
      } else {
        return { error: `Namespace "${_state.stateNamespace}" not found` };
      }
    }
    // Wrap in object for display
    obj = { [`${_state.stateNamespace}`]: obj };
  }

  // Search filter — show only matching keys if search is active
  if (_state.stateSearch) {
    const q = _state.stateSearch.toLowerCase();
    const filterObj = (o, path = '') => {
      if (typeof o !== 'object' || o === null) return null;
      const result = {};
      let matched = false;
      for (const [key, value] of Object.entries(o)) {
        const fullPath = path ? `${path}.${key}` : key;
        if (key.toLowerCase().includes(q) || fullPath.toLowerCase().includes(q)) {
          result[key] = value;
          matched = true;
        } else if (typeof value === 'object' && value !== null) {
          const nested = filterObj(value, fullPath);
          if (nested && Object.keys(nested).length > 0) {
            result[key] = nested;
            matched = true;
          }
        }
      }
      return matched ? result : null;
    };
    const filtered = filterObj(obj);
    return filtered || { notice: 'No matching keys found.' };
  }

  return obj;
}

/* ── Tab: API Playground ────────────────────────────────────────────────── */

function renderApiPlayground() {
  return html`
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4);">
      <!-- Request Panel -->
      <div class="c-card">
        <div class="c-card__header">
          <span class="c-card__title">Request</span>
        </div>
        <div class="c-card__body">
          <!-- Method + URL -->
          <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-3);">
            <select class="c-select c-select--sm" id="devtools-api-method"
                    style="width: auto; min-width: 100px; flex-shrink: 0;">
              ${html.raw(API_METHODS.map((m) => html`
                <option value="${m}" ${m === _state.apiMethod ? 'selected' : ''}>${m}</option>
              `).join(''))}
            </select>
            <input type="text" class="c-input c-input--sm" id="devtools-api-url"
                   placeholder="/api/v1/endpoint"
                   value="${esc(_state.apiUrl)}"
                   style="flex: 1; font-family: var(--font-mono); font-size: var(--font-size-xs);">
            <button class="c-btn c-btn--primary c-btn--sm" id="devtools-api-send"
                    ${_state.apiSending ? 'disabled' : ''}
                    style="${_state.apiSending ? 'opacity: 0.6;' : ''}">
              <span class="c-btn__icon">${_state.apiSending ? ICONS.refresh : ICONS.play}</span>
              ${_state.apiSending ? 'Sending…' : 'Send'}
            </button>
          </div>

          <!-- Headers -->
          <div style="margin-bottom: var(--space-3);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-1);">
              <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Headers</span>
              <button class="c-btn c-btn--sm c-btn--ghost" id="devtools-add-header" style="padding: 0 6px;">
                <span class="c-btn__icon">${ICONS.plus}</span>
              </button>
            </div>
            <div id="devtools-headers-list">
              ${html.raw((_state.apiHeaders.length > 0 ? _state.apiHeaders : [{ key: '', value: '' }]).map((h, i) => html`
                <div style="display: flex; gap: var(--space-2); margin-bottom: 4px;">
                  <input type="text" class="c-input c-input--sm" data-header-key="${i}"
                         placeholder="Key" value="${esc(h.key)}"
                         style="flex: 1; font-size: var(--font-size-xxs); font-family: var(--font-mono);">
                  <input type="text" class="c-input c-input--sm" data-header-value="${i}"
                         placeholder="Value" value="${esc(h.value)}"
                         style="flex: 1; font-size: var(--font-size-xxs); font-family: var(--font-mono);">
                  <button class="c-btn c-btn--sm c-btn--ghost" data-action="remove-header" data-index="${i}"
                          style="padding: 2px 6px; color: var(--danger);">
                    <span class="c-btn__icon">${ICONS.trash}</span>
                  </button>
                </div>
              `).join('')))}
            </div>
          </div>

          <!-- Body -->
          <div style="margin-bottom: var(--space-2);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-1);">
              <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                Request Body (${_state.apiMethod === 'GET' || _state.apiMethod === 'DELETE' ? 'ignored for ' + _state.apiMethod : ''})
              </span>
            </div>
            <textarea class="c-textarea" id="devtools-api-body"
                      placeholder='{"key": "value"}'
                      ${_state.apiMethod === 'GET' || _state.apiMethod === 'DELETE' ? 'disabled' : ''}
                      style="min-height: 120px; font-family: var(--font-mono); font-size: var(--font-size-xs);">${esc(_state.apiBody)}</textarea>
          </div>
        </div>
      </div>

      <!-- Response Panel -->
      <div class="c-card">
        <div class="c-card__header">
          <span class="c-card__title">Response</span>
          <div style="display: flex; align-items: center; gap: var(--space-2);">
            ${_state.apiResponseStatus ? html`
              <span class="c-badge c-badge--${_state.apiResponseStatus < 300 ? 'success' : _state.apiResponseStatus < 500 ? 'warning' : 'danger'}"
                    style="font-family: var(--font-mono);">
                ${_state.apiResponseStatus}
              </span>
            ` : ''}
            ${_state.apiResponseTime != null ? html`
              <span style="font-size: var(--font-size-xs); color: var(--text-muted); font-variant-numeric: tabular-nums;">
                ${_state.apiResponseTime}ms
              </span>
            ` : ''}
            <button class="c-btn c-btn--sm c-btn--ghost" id="devtools-copy-response" title="Copy response">
              <span class="c-btn__icon">${ICONS.copy}</span>
            </button>
          </div>
        </div>
        <div class="c-card__body" style="padding: 0; max-height: 500px; overflow: auto;">
          <pre id="devtools-response-body"
               style="margin: 0; padding: var(--space-4); font-family: var(--font-mono);
                      font-size: var(--font-size-xs); line-height: 1.6;
                      color: var(--text-primary); white-space: pre-wrap; word-break: break-all;
                      overflow-x: auto;">
${_state.apiResponse != null ? syntaxHighlight(_state.apiResponse) : 'Send a request to see the response here.'}
          </pre>
        </div>
      </div>
    </div>
  `;
}

/* ── Tab: Console ───────────────────────────────────────────────────────── */

function renderConsole() {
  return html`
    <div class="c-card" style="display: flex; flex-direction: column;">
      <div class="c-card__header">
        <span class="c-card__title">JavaScript Console</span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="devtools-console-clear">
          <span class="c-btn__icon">${ICONS.trash}</span>
          Clear
        </button>
      </div>
      <div class="c-card__body" style="padding: 0; flex: 1; display: flex; flex-direction: column;">
        <!-- Output -->
        <div id="devtools-console-output"
             style="flex: 1; min-height: 300px; max-height: 450px; overflow-y: auto;
                    padding: var(--space-3); background: var(--bg-tertiary);
                    font-family: var(--font-mono); font-size: var(--font-size-xs);
                    line-height: 1.5;">
          ${_state.consoleOutput.length === 0 ? html`
            <div style="color: var(--text-muted); padding: var(--space-4); text-align: center;">
              Console output will appear here. Type JavaScript below to execute.
            </div>
          ` : html.raw(_state.consoleOutput.map((entry) => {
            const ts = entry.timestamp ? formatTimestamp(new Date(entry.timestamp)) : '';
            return html`
              <div style="margin-bottom: 2px; padding: 2px 0; border-bottom: 1px solid var(--border-subtle);">
                <span style="color: var(--text-muted); font-size: 9px; margin-right: 6px;">${esc(ts)}</span>
                <span style="color: ${entry.type === 'error' ? 'var(--danger)' : entry.type === 'warn' ? 'var(--warning)' : entry.type === 'result' ? 'var(--success)' : 'var(--text-primary)'}">
                  ${entry.type === 'input' ? '› ' : entry.type === 'error' ? '✗ ' : entry.type === 'result' ? '← ' : ''}
                  ${esc(entry.text)}
                </span>
              </div>
            `;
          }).join(''))}
          <div id="devtools-console-scroll-anchor"></div>
        </div>

        <!-- Input -->
        <div style="display: flex; align-items: center; gap: var(--space-2); padding: var(--space-3);
                    border-top: 1px solid var(--border); background: var(--surface);">
          <span style="color: var(--accent); font-family: var(--font-mono); font-size: var(--font-size-sm);">›</span>
          <input type="text" id="devtools-console-input"
                 placeholder="Type JavaScript and press Enter…"
                 value="${esc(_state.consoleInput)}"
                 style="flex: 1; border: none; background: transparent; outline: none;
                        font-family: var(--font-mono); font-size: var(--font-size-sm);
                        color: var(--text-primary);">
        </div>
      </div>
    </div>
  `;
}

/* ── Tab: Event Log ─────────────────────────────────────────────────────── */

function renderEventLog() {
  const filtered = _state.eventFilter
    ? _state.eventLog.filter((e) => e.type.toLowerCase().includes(_state.eventFilter.toLowerCase()))
    : _state.eventLog;

  return html`
    <div class="c-card" style="display: flex; flex-direction: column;">
      <div class="c-card__header">
        <span class="c-card__title">WebSocket Event Log</span>
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <div class="c-input-wrapper" style="width: 160px;">
            <span class="c-input-wrapper__icon c-input-wrapper__icon--left">${ICONS.search}</span>
            <input type="text" class="c-input c-input--sm" id="devtools-event-filter"
                   placeholder="Filter by type…"
                   value="${esc(_state.eventFilter)}"
                   style="padding-left: 32px; font-size: var(--font-size-xs);">
          </div>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted);">
            ${filtered.length} events
          </span>
          <button class="c-btn c-btn--sm c-btn--ghost" id="devtools-event-clear">
            <span class="c-btn__icon">${ICONS.trash}</span>
            Clear
          </button>
        </div>
      </div>
      <div class="c-card__body" style="padding: 0; max-height: 550px; overflow-y: auto;">
        ${filtered.length === 0 ? html`
          <div style="padding: var(--space-6); text-align: center; color: var(--text-muted); font-size: var(--font-size-sm);">
            ${_state.eventFilter ? 'No events match the filter.' : 'No WebSocket events received yet. Events will appear here in real-time.'}
          </div>
        ` : html.raw(filtered.map((entry, i) => {
          const ts = entry.timestamp ? formatTimestamp(new Date(entry.timestamp)) : '';
          const isExpanded = _state.expandedEventIdx === i;
          return html`
            <div style="padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-subtle);
                        cursor: pointer; transition: background var(--transition-fast);"
                 data-action="toggle-event" data-event-idx="${i}">
              <div style="display: flex; align-items: center; gap: var(--space-2);">
                <span style="font-size: 9px; color: var(--text-muted); font-family: var(--font-mono); flex-shrink: 0;">
                  ${esc(ts)}
                </span>
                <span class="c-badge c-badge--default" style="font-size: 9px; font-family: var(--font-mono); flex-shrink: 0;">
                  ${esc(entry.type)}
                </span>
                <span style="font-size: var(--font-size-xs); color: var(--text-muted); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  ${esc(typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data).slice(0, 120))}
                </span>
                <span style="color: var(--text-muted); flex-shrink: 0;">${isExpanded ? ICONS.chevronUp : ICONS.chevronDown}</span>
              </div>
              ${isExpanded ? html`
                <pre style="margin-top: var(--space-2); padding: var(--space-2); background: var(--bg-tertiary);
                            border-radius: var(--radius-sm); font-size: var(--font-size-xxs);
                            font-family: var(--font-mono); overflow-x: auto;
                            color: var(--text-secondary); white-space: pre-wrap; word-break: break-all;">
${esc(JSON.stringify(entry.data, null, 2))}
                </pre>
              ` : ''}
            </div>
          `;
        }).join(''))}
      </div>
      ${_state.eventLog.length > 0 ? html`
        <div class="c-card__footer" style="justify-content: flex-start; gap: var(--space-2);">
          <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
            ${_state.eventLog.length === 1 ? '1 event' : `${_state.eventLog.length} events`} logged
            ${_state.wsUnsub ? '· Listening for events' : '· Not connected'}
          </span>
        </div>
      ` : ''}
    </div>
  `;
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // ── Tab switching ──
  container.querySelectorAll('[data-action="switch-tab"]').forEach((el) => {
    el.addEventListener('click', () => {
      _state.activeTab = el.dataset.tab;
      if (_state.container) renderPage(_state.container);
    });
  });

  // ── State Inspector ──
  const stateSearch = container.querySelector('#devtools-state-search');
  if (stateSearch) {
    stateSearch.addEventListener('input', (e) => {
      _state.stateSearch = e.target.value;
      refreshStateInspector();
    });
  }

  const stateNs = container.querySelector('#devtools-state-namespace');
  if (stateNs) {
    stateNs.addEventListener('input', (e) => {
      _state.stateNamespace = e.target.value;
      refreshStateInspector();
    });
  }

  container.querySelector('#devtools-copy-state')?.addEventListener('click', () => {
    const store = getStore();
    const state = store?.getState ? store.getState() : store?.state || {};
    navigator.clipboard.writeText(JSON.stringify(state, null, 2))
      .then(() => showToast('success', 'State copied to clipboard.'))
      .catch(() => showToast('error', 'Failed to copy state.'));
  });

  container.querySelector('#devtools-reset-state')?.addEventListener('click', () => {
    if (confirm('Reset application state? This will reload the page.')) {
      const store = getStore();
      if (store?.reset) {
        store.reset();
        showToast('info', 'State has been reset.');
        refreshStateInspector();
      } else {
        showToast('error', 'State reset is not supported by the current store.');
      }
    }
  });

  // ── API Playground ──
  const methodSelect = container.querySelector('#devtools-api-method');
  if (methodSelect) {
    methodSelect.addEventListener('change', (e) => {
      _state.apiMethod = e.target.value;
      // Re-render to disable body for GET/DELETE
      if (_state.container) renderPage(_state.container);
    });
  }

  const apiUrl = container.querySelector('#devtools-api-url');
  if (apiUrl) {
    apiUrl.addEventListener('change', (e) => { _state.apiUrl = e.target.value; });
    apiUrl.addEventListener('input', (e) => { _state.apiUrl = e.target.value; });
  }

  // Headers management
  container.querySelector('#devtools-add-header')?.addEventListener('click', () => {
    _state.apiHeaders.push({ key: '', value: '' });
    if (_state.container) renderPage(_state.container);
  });

  container.querySelectorAll('[data-action="remove-header"]').forEach((el) => {
    el.addEventListener('click', () => {
      const idx = parseInt(el.dataset.index, 10);
      if (!isNaN(idx) && idx >= 0 && idx < _state.apiHeaders.length) {
        _state.apiHeaders.splice(idx, 1);
        if (_state.container) renderPage(_state.container);
      }
    });
  });

  // Live header inputs
  container.querySelectorAll('[data-header-key]').forEach((el) => {
    el.addEventListener('input', (e) => {
      const idx = parseInt(e.target.dataset.headerKey, 10);
      _state.apiHeaders[idx] = _state.apiHeaders[idx] || { key: '', value: '' };
      _state.apiHeaders[idx].key = e.target.value;
    });
  });
  container.querySelectorAll('[data-header-value]').forEach((el) => {
    el.addEventListener('input', (e) => {
      const idx = parseInt(e.target.dataset.headerValue, 10);
      _state.apiHeaders[idx] = _state.apiHeaders[idx] || { key: '', value: '' };
      _state.apiHeaders[idx].value = e.target.value;
    });
  });

  const apiBody = container.querySelector('#devtools-api-body');
  if (apiBody) {
    apiBody.addEventListener('input', (e) => { _state.apiBody = e.target.value; });
    apiBody.addEventListener('change', (e) => { _state.apiBody = e.target.value; });
  }

  container.querySelector('#devtools-api-send')?.addEventListener('click', sendApiRequest);

  // Enter in URL field triggers send
  if (apiUrl) {
    apiUrl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendApiRequest();
    });
  }

  container.querySelector('#devtools-copy-response')?.addEventListener('click', () => {
    if (_state.apiResponse != null) {
      const text = typeof _state.apiResponse === 'string'
        ? _state.apiResponse
        : JSON.stringify(_state.apiResponse, null, 2);
      navigator.clipboard.writeText(text)
        .then(() => showToast('success', 'Response copied.'))
        .catch(() => showToast('error', 'Failed to copy.'));
    }
  });

  // ── Console ──
  const consoleInput = container.querySelector('#devtools-console-input');
  if (consoleInput) {
    consoleInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        executeConsoleInput();
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        navigateConsoleHistory(-1);
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        navigateConsoleHistory(1);
      }
    });
    consoleInput.addEventListener('input', (e) => {
      _state.consoleInput = e.target.value;
    });
  }

  container.querySelector('#devtools-console-clear')?.addEventListener('click', () => {
    _state.consoleOutput = [];
    if (_state.container) renderPage(_state.container);
  });

  // ── Event Log ──
  const eventFilter = container.querySelector('#devtools-event-filter');
  if (eventFilter) {
    eventFilter.addEventListener('input', (e) => {
      _state.eventFilter = e.target.value;
      if (_state.container) renderPage(_state.container);
    });
  }

  container.querySelector('#devtools-event-clear')?.addEventListener('click', () => {
    _state.eventLog = [];
    if (_state.container) renderPage(_state.container);
  });

  container.querySelectorAll('[data-action="toggle-event"]').forEach((el) => {
    el.addEventListener('click', () => {
      const idx = parseInt(el.dataset.eventIdx, 10);
      _state.expandedEventIdx = _state.expandedEventIdx === idx ? -1 : idx;
      if (_state.container) renderPage(_state.container);
    });
  });

  // Scroll console output to bottom
  const output = container.querySelector('#devtools-console-output');
  if (output) {
    output.scrollTop = output.scrollHeight;
  }
}

/* ── State Inspector Refresh ────────────────────────────────────────────── */

function refreshStateInspector() {
  const el = _state.container?.querySelector('#devtools-state-tree');
  if (!el) return;
  const store = getStore();
  const state = store?.getState ? store.getState() : store?.state || {};
  el.innerHTML = syntaxHighlight(JSON.stringify(filterState(state), null, 2));
}

/* ── API Playground: Send Request ───────────────────────────────────────── */

async function sendApiRequest() {
  const api = getApi();
  if (!api || _state.apiSending) return;

  _state.apiSending = true;
  _state.apiResponse = null;
  _state.apiResponseStatus = null;
  _state.apiResponseTime = null;
  if (_state.container) renderPage(_state.container);

  try {
    // Build headers object from array
    const headers = {};
    for (const h of _state.apiHeaders) {
      if (h.key && h.key.trim()) {
        headers[h.key.trim()] = h.value;
      }
    }

    const t0 = performance.now();
    let body;
    if (_state.apiBody && (_state.apiMethod === 'POST' || _state.apiMethod === 'PUT' || _state.apiMethod === 'PATCH')) {
      try {
        body = JSON.parse(_state.apiBody);
      } catch {
        body = _state.apiBody; // Send as raw string if not valid JSON
      }
    }

    // Use the raw fetch through the API or direct
    let response;
    try {
      response = await api.request(_state.apiMethod, _state.apiUrl, body, { headers });
    } catch (fetchErr) {
      // Fallback to raw fetch
      const fetchOptions = {
        method: _state.apiMethod,
        headers: { ...headers },
      };
      if (body && (_state.apiMethod === 'POST' || _state.apiMethod === 'PUT' || _state.apiMethod === 'PATCH')) {
        fetchOptions.body = JSON.stringify(body);
      }
      const baseUrl = api.baseUrl || '';
      const url = _state.apiUrl.startsWith('http') ? _state.apiUrl : `${baseUrl}${_state.apiUrl}`;
      const rawRes = await fetch(url, fetchOptions);
      const rawData = await rawRes.json();
      response = {
        status: rawRes.status,
        data: rawData,
        headers: Object.fromEntries(rawRes.headers.entries()),
      };
    }

    const ms = Math.round(performance.now() - t0);
    _state.apiResponseTime = ms;
    _state.apiResponseStatus = response.status || response.statusCode || 200;
    _state.apiResponse = response.data ?? response.body ?? response;
  } catch (err) {
    _state.apiResponseStatus = 0;
    _state.apiResponseTime = null;
    _state.apiResponse = { error: err.message || 'Request failed' };
  }

  _state.apiSending = false;
  if (!_state.destroyed && _state.container) {
    renderPage(_state.container);
  }
}

/* ── Console: Execute JS ────────────────────────────────────────────────── */

function executeConsoleInput() {
  const input = _state.consoleInput;
  if (!input || !input.trim()) return;

  // Add to history
  _state.consoleHistory.push(input);
  _state.consoleHistoryIndex = _state.consoleHistory.length;

  // Add input to output
  _state.consoleOutput.push({
    type: 'input',
    text: input,
    timestamp: Date.now(),
  });

  _state.consoleInput = '';
  if (_state.container) renderPage(_state.container);

  // Execute in setTimeout to let the DOM update
  setTimeout(() => {
    try {
      // Use indirect eval for global scope
      const result = (0, eval)(input);

      // Handle promises
      if (result && typeof result.then === 'function') {
        _state.consoleOutput.push({
          type: 'info',
          text: 'Promise { <pending> }',
          timestamp: Date.now(),
        });
        result
          .then((val) => {
            _state.consoleOutput.push({
              type: 'result',
              text: formatConsoleValue(val),
              timestamp: Date.now(),
            });
            if (_state.container) renderPage(_state.container);
          })
          .catch((err) => {
            _state.consoleOutput.push({
              type: 'error',
              text: `Promise rejected: ${err.message || err}`,
              timestamp: Date.now(),
            });
            if (_state.container) renderPage(_state.container);
          });
      } else {
        _state.consoleOutput.push({
          type: 'result',
          text: formatConsoleValue(result),
          timestamp: Date.now(),
        });
      }
    } catch (err) {
      _state.consoleOutput.push({
        type: 'error',
        text: err.message || String(err),
        timestamp: Date.now(),
      });
    }

    if (_state.container) renderPage(_state.container);
  }, 50);
}

function formatConsoleValue(val) {
  if (val === null) return 'null';
  if (val === undefined) return 'undefined';
  if (typeof val === 'string') return val;
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (Array.isArray(val)) return `Array(${val.length}) ${JSON.stringify(val)}`;
  if (typeof val === 'function') return `ƒ ${val.name || 'anonymous'}()`;
  if (typeof val === 'object') {
    try {
      return JSON.stringify(val, null, 2);
    } catch {
      return String(val);
    }
  }
  return String(val);
}

function navigateConsoleHistory(direction) {
  const history = _state.consoleHistory;
  if (history.length === 0) return;

  _state.consoleHistoryIndex += direction;
  if (_state.consoleHistoryIndex < 0) _state.consoleHistoryIndex = 0;
  if (_state.consoleHistoryIndex >= history.length) {
    _state.consoleHistoryIndex = history.length;
    _state.consoleInput = '';
  } else {
    _state.consoleInput = history[_state.consoleHistoryIndex] || '';
  }

  const inputEl = _state.container?.querySelector('#devtools-console-input');
  if (inputEl) {
    inputEl.value = _state.consoleInput;
    // Move cursor to end
    setTimeout(() => {
      inputEl.selectionStart = inputEl.selectionEnd = inputEl.value.length;
    }, 0);
  }
}

/* ── WebSocket Event Log ────────────────────────────────────────────────── */

function initEventLog() {
  const fiona = window.fiona;
  if (!fiona?.api?.on) return;

  // Listen for all WebSocket events
  _state.wsUnsub = fiona.api.on('*', (eventType, data) => {
    if (_state.destroyed) return;
    _state.eventLog.push({
      type: eventType || 'unknown',
      data: data ?? {},
      timestamp: Date.now(),
    });
    // Keep last 200 events
    if (_state.eventLog.length > 200) {
      _state.eventLog.splice(0, _state.eventLog.length - 200);
    }
    // Update the event log panel if visible
    if (_state.activeTab === 'event-log' && _state.container) {
      renderPage(_state.container);
    }
  });
}

/* ── Toast ───────────────────────────────────────────────────────────────── */

function showToast(type, message) {
  const toast = document.createElement('div');
  toast.className = `c-toast c-toast--${type || 'info'} animate-slide-right`;
  toast.style.cssText = 'position: fixed; bottom: 60px; right: 20px; z-index: 9999; max-width: 360px;';
  toast.innerHTML = `
    <div class="c-toast__icon">${ICONS[type === 'success' ? 'check' : type === 'error' ? 'error' : 'info']}</div>
    <div class="c-toast__content"><div class="c-toast__message">${esc(message)}</div></div>
    <button class="c-toast__dismiss" data-toast-dismiss style="flex-shrink:0;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  `;
  document.body.appendChild(toast);
  toast.querySelector('[data-toast-dismiss]')?.addEventListener('click', () => toast.remove());
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.2s';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = false;
  _state.container = container;

  renderPage(container);
  initEventLog();
}

export function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container) {
    renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;

  if (_state.wsUnsub) {
    _state.wsUnsub();
    _state.wsUnsub = null;
  }

  _state.container = null;
  _state.consoleOutput = [];
  _state.consoleHistory = [];
  _state.eventLog = [];
  _state.apiResponse = null;
  _state.expandedEventIdx = -1;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="devtools-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#devtools-root') || container;
      try {
        const templateHtml = await loadTemplate('devtools', {
          loading: true,
        });
        root.innerHTML = templateHtml;
      } catch (err) {
        console.error('[DevTools] Failed to load template:', err);
      }
      render(root);
    },
    destroy,
  };
}
