/* ==========================================================================
   browser.js — Browser Automation Page
   ==========================================================================
   Control panel for Fiona's Playwright-based browser automation.
   Features browser lifecycle management, URL navigation, element
   interaction, console log capture, screenshot gallery, and multi-
   session (tab) management.

   Exports: { render(routeInfo), mount(container), destroy() }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── API Helper ─────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api || window.__fiona?.api;
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 3000;
const DEFAULT_URL = 'https://www.google.com';
const NAVIGATE_TIMEOUT = 30000;
const MAX_CONSOLE_LINES = 500;
const MAX_SCREENSHOTS = 50;

/* ── Page State ─────────────────────────────────────────────────────────── */

let _container = null;
let _isDestroyed = false;

const _state = {
  // Browser status
  browserStatus: 'stopped', // 'stopped' | 'starting' | 'running' | 'error'
  statusMessage: '',
  browserError: '',

  // Navigation
  currentUrl: DEFAULT_URL,
  pageTitle: '',
  pageStatusCode: null,
  loadTimeMs: null,
  isLoading: false,
  urlHistory: [],
  historyIndex: -1,

  // Active tab
  activeTab: 'view', // 'view' | 'console' | 'screenshots' | 'sessions'

  // Console messages
  consoleMessages: [], // { text, level, timestamp }
  consoleFilter: 'all', // 'all' | 'log' | 'info' | 'warn' | 'error'

  // Screenshots
  screenshots: [], // { id, dataUrl, timestamp, url, fullPage }

  // Sessions / tabs
  sessions: [], // { id, title, url, isActive }
  activeSessionId: null,
  sessionCounter: 0,

  // Element interaction
  elementSelector: '',
  elementActionResult: '',

  // Polling
  pollTimer: null,

  // Loading states for operations
  operationLoading: {
    start: false,
    stop: false,
    navigate: false,
    click: false,
    screenshot: false,
  },
};

let _unbindFns = [];

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function _escapeHtml(str) {
  if (str == null) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function _generateId() {
  return `browser-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function _formatTimestamp(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  const s = date.getSeconds().toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function _formatTimestampFull(date) {
  const d = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return `${d} ${_formatTimestamp(date)}`;
}

function _formatDuration(ms) {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

function _getStatusColor(status) {
  switch (status) {
    case 'running': return 'var(--success)';
    case 'starting': return 'var(--warning)';
    case 'error': return 'var(--danger)';
    default: return 'var(--text-muted)';
  }
}

function _getStatusLabel(status) {
  switch (status) {
    case 'running': return 'Running';
    case 'starting': return 'Starting…';
    case 'error': return 'Error';
    default: return 'Stopped';
  }
}

/* ── API Calls ───────────────────────────────────────────────────────────── */

async function _apiStartBrowser() {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/start');
  return res?.data || res;
}

async function _apiStopBrowser() {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/stop');
  return res?.data || res;
}

async function _apiGetStatus() {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.get('/api/v1/browser/status');
  return res?.data || res;
}

async function _apiNavigate(url, timeout) {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/navigate', { url, timeout: timeout || NAVIGATE_TIMEOUT });
  return res?.data || res;
}

async function _apiClick(selector, timeout) {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/click', { selector, timeout: timeout || 5000 });
  return res?.data || res;
}

async function _apiTypeText(selector, text, timeout) {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/type', { selector, text, timeout: timeout || 5000 });
  return res?.data || res;
}

async function _apiGetText(selector, timeout) {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/get_text', { selector, timeout: timeout || 5000 });
  return res?.data || res;
}

async function _apiScreenshot(fullPage) {
  const api = getApi();
  if (!api) throw new Error('API client not available');
  const res = await api.post('/api/v1/browser/screenshot', { full_page: !!fullPage });
  return res?.data || res;
}

/* ── Status Polling ──────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  _state.pollTimer = setInterval(pollStatus, POLL_INTERVAL);
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
}

async function pollStatus() {
  if (_isDestroyed) return;

  try {
    const status = await _apiGetStatus();
    if (_isDestroyed) return;

    // Update browser status from response
    if (status.status) {
      const wasStarting = _state.browserStatus === 'starting';
      _state.browserStatus = status.status;

      // If we were starting and now running, update the UI
      if (wasStarting && status.status === 'running') {
        renderUI();
      }
    }

    if (status.url) _state.currentUrl = status.url;
    if (status.title) _state.pageTitle = status.title;
    if (status.status_code != null) _state.pageStatusCode = status.status_code;
    if (status.load_time_ms != null) _state.loadTimeMs = status.load_time_ms;

    // Sync sessions from backend if available
    if (status.sessions && Array.isArray(status.sessions)) {
      _state.sessions = status.sessions.map((s) => ({
        id: s.id || _generateId(),
        title: s.title || 'New Tab',
        url: s.url || '',
        isActive: s.isActive || false,
      }));
      const activeSession = _state.sessions.find((s) => s.isActive);
      if (activeSession) _state.activeSessionId = activeSession.id;
    }

    // Capture console messages if backend provides them
    if (status.console_messages && Array.isArray(status.console_messages)) {
      for (const msg of status.console_messages) {
        addConsoleMessage(msg.text || msg.message || '', msg.level || 'log');
      }
    }

    renderUI();

    // Stop polling if browser stopped
    if (status.status === 'stopped' || status.status === 'error') {
      stopPolling();
    }
  } catch (err) {
    if (_isDestroyed) return;
    // Silently handle poll errors — browser might have been stopped externally
    console.warn('[Browser] Status poll failed:', err);
  }
}

/* ── Console Message Management ──────────────────────────────────────────── */

function addConsoleMessage(text, level) {
  level = level || 'log';
  _state.consoleMessages.push({
    text: String(text),
    level,
    timestamp: Date.now(),
  });
  // Trim if too long
  if (_state.consoleMessages.length > MAX_CONSOLE_LINES) {
    _state.consoleMessages = _state.consoleMessages.slice(-MAX_CONSOLE_LINES);
  }
}

function clearConsole() {
  _state.consoleMessages = [];
  renderConsoleTab();
}

/* ── Screenshot Management ───────────────────────────────────────────────── */

function addScreenshot(dataUrl, fullPage) {
  _state.screenshots.unshift({
    id: _generateId(),
    dataUrl,
    timestamp: Date.now(),
    url: _state.currentUrl,
    fullPage: !!fullPage,
  });
  if (_state.screenshots.length > MAX_SCREENSHOTS) {
    _state.screenshots = _state.screenshots.slice(0, MAX_SCREENSHOTS);
  }
}

/* ── Session / Tab Management ────────────────────────────────────────────── */

function createSession(title) {
  const id = _generateId();
  const session = {
    id,
    title: title || 'New Tab',
    url: _state.currentUrl,
    isActive: false,
  };
  _state.sessions.push(session);
  return session;
}

function switchSession(sessionId) {
  _state.sessions.forEach((s) => { s.isActive = s.id === sessionId; });
  _state.activeSessionId = sessionId;
  renderSessionsTab();
  updateSessionDisplay();
}

function closeSession(sessionId) {
  if (_state.sessions.length <= 1) return; // Keep at least one
  const idx = _state.sessions.findIndex((s) => s.id === sessionId);
  if (idx === -1) return;
  _state.sessions.splice(idx, 1);

  if (_state.activeSessionId === sessionId) {
    const newIdx = Math.min(idx, _state.sessions.length - 1);
    _state.activeSessionId = _state.sessions[newIdx].id;
    _state.sessions[newIdx].isActive = true;
  }
  renderSessionsTab();
  updateSessionDisplay();
}

function updateSessionDisplay() {
  const active = _state.sessions.find((s) => s.id === _state.activeSessionId);
  if (active) {
    active.url = _state.currentUrl;
    active.title = _state.pageTitle || 'New Tab';
  }
}

/* ── Navigation History ──────────────────────────────────────────────────── */

function pushHistory(url) {
  // Remove any forward history
  if (_state.historyIndex < _state.urlHistory.length - 1) {
    _state.urlHistory = _state.urlHistory.slice(0, _state.historyIndex + 1);
  }
  _state.urlHistory.push(url);
  _state.historyIndex = _state.urlHistory.length - 1;
}

function canGoBack() {
  return _state.historyIndex > 0;
}

function canGoForward() {
  return _state.historyIndex < _state.urlHistory.length - 1;
}

function goBack() {
  if (!canGoBack()) return;
  _state.historyIndex--;
  const url = _state.urlHistory[_state.historyIndex];
  if (url) navigateTo(url, false);
}

function goForward() {
  if (!canGoForward()) return;
  _state.historyIndex++;
  const url = _state.urlHistory[_state.historyIndex];
  if (url) navigateTo(url, false);
}

/* ── Browser Actions ─────────────────────────────────────────────────────── */

async function startBrowser() {
  if (_state.operationLoading.start) return;
  _state.operationLoading.start = true;
  _state.browserStatus = 'starting';
  _state.browserError = '';
  renderUI();

  try {
    await _apiStartBrowser();
    _state.browserStatus = 'running';
    _state.statusMessage = 'Browser started';
    startPolling();
  } catch (err) {
    _state.browserStatus = 'error';
    _state.browserError = err.message || 'Failed to start browser';
    _state.statusMessage = '';
    console.error('[Browser] Start failed:', err);
  } finally {
    _state.operationLoading.start = false;
    renderUI();
  }
}

async function stopBrowser() {
  if (_state.operationLoading.stop) return;
  _state.operationLoading.stop = true;
  renderUI();

  try {
    await _apiStopBrowser();
    _state.browserStatus = 'stopped';
    _state.statusMessage = 'Browser stopped';
    stopPolling();
  } catch (err) {
    _state.browserError = err.message || 'Failed to stop browser';
    console.error('[Browser] Stop failed:', err);
  } finally {
    _state.operationLoading.stop = false;
    renderUI();
  }
}

async function navigateTo(url, recordHistory = true) {
  if (!url || !url.trim() || _state.operationLoading.navigate) return;

  // Auto-add protocol if missing
  let normalizedUrl = url.trim();
  if (!/^https?:\/\//i.test(normalizedUrl)) {
    normalizedUrl = 'https://' + normalizedUrl;
  }

  _state.operationLoading.navigate = true;
  _state.isLoading = true;
  _state.loadTimeMs = null;
  _state.pageStatusCode = null;
  _state.elementActionResult = '';
  renderUI();

  try {
    const result = await _apiNavigate(normalizedUrl);
    _state.currentUrl = normalizedUrl;

    if (recordHistory) {
      pushHistory(normalizedUrl);
    }

    _state.pageTitle = result?.title || result?.page_title || '';
    _state.pageStatusCode = result?.status_code || result?.status || null;
    _state.loadTimeMs = result?.load_time_ms || result?.duration_ms || null;
    _state.statusMessage = _state.loadTimeMs
      ? `Page loaded in ${_formatDuration(_state.loadTimeMs)}`
      : 'Page loaded';
    _state.pageTitle = result?.title || result?.page_title || '';

    updateSessionDisplay();
  } catch (err) {
    _state.browserError = err.message || 'Navigation failed';
    _state.statusMessage = '';
    _state.pageStatusCode = err.status || 0;
    console.error('[Browser] Navigate failed:', err);
  } finally {
    _state.operationLoading.navigate = false;
    _state.isLoading = false;
    renderUI();
  }
}

function refreshPage() {
  navigateTo(_state.currentUrl, false);
}

async function takeScreenshot(fullPage) {
  if (_state.operationLoading.screenshot) return;
  _state.operationLoading.screenshot = true;
  renderUI();

  try {
    const result = await _apiScreenshot(fullPage);
    // Backend returns screenshot_base64 (raw base64), construct data URL
    const raw = result?.screenshot_base64 || result?.data_url || result?.screenshot_data || result?.data || '';
    const dataUrl = raw.startsWith('data:') ? raw : raw ? `data:image/png;base64,${raw}` : '';
    if (dataUrl) {
      addScreenshot(dataUrl, fullPage);
      if (_state.activeTab === 'screenshots') {
        renderScreenshotsTab();
      }
      _state.statusMessage = 'Screenshot captured';
    } else {
      _state.browserError = 'No screenshot data returned';
    }
  } catch (err) {
    _state.browserError = err.message || 'Screenshot failed';
    console.error('[Browser] Screenshot failed:', err);
  } finally {
    _state.operationLoading.screenshot = false;
    renderUI();
  }
}

async function clickElement(selector) {
  if (!selector || !selector.trim() || _state.operationLoading.click) return;
  _state.operationLoading.click = true;
  _state.elementActionResult = '';
  renderUI();

  try {
    const result = await _apiClick(selector.trim());
    _state.elementActionResult = 'Clicked: ' + (result?.result || 'OK');
  } catch (err) {
    _state.elementActionResult = 'Error: ' + (err.message || 'Click failed');
    console.error('[Browser] Click failed:', err);
  } finally {
    _state.operationLoading.click = false;
    renderUI();
  }
}

async function typeText(selector, text) {
  if (!selector || !selector.trim() || !text || _state.operationLoading.click) return;
  _state.operationLoading.click = true;
  _state.elementActionResult = '';
  renderUI();

  try {
    const result = await _apiTypeText(selector.trim(), text);
    _state.elementActionResult = 'Typed: ' + (result?.result || 'OK');
  } catch (err) {
    _state.elementActionResult = 'Error: ' + (err.message || 'Type failed');
    console.error('[Browser] Type failed:', err);
  } finally {
    _state.operationLoading.click = false;
    renderUI();
  }
}

async function getElementText(selector) {
  if (!selector || !selector.trim() || _state.operationLoading.click) return;
  _state.operationLoading.click = true;
  _state.elementActionResult = '';
  renderUI();

  try {
    const result = await _apiGetText(selector.trim());
    const text = result?.text || result?.result || '(empty)';
    _state.elementActionResult = 'Text: ' + text;
  } catch (err) {
    _state.elementActionResult = 'Error: ' + (err.message || 'Get text failed');
    console.error('[Browser] Get text failed:', err);
  } finally {
    _state.operationLoading.click = false;
    renderUI();
  }
}

/* ── Tab Rendering ────────────────────────────────────────────────────────── */

function renderTabButtons() {
  const tabBar = _container?.querySelector('#browser-tab-bar');
  if (!tabBar) return;

  const tabs = [
    { id: 'view', label: 'Browser View', icon: ICONS.globe },
    { id: 'console', label: 'Console', icon: ICONS.terminal },
    { id: 'screenshots', label: 'Screenshots', icon: ICONS.eye },
    { id: 'sessions', label: 'Sessions', icon: ICONS.moreHorizontal },
  ];

  tabBar.innerHTML = tabs.map((tab) => {
    const isActive = _state.activeTab === tab.id;
    const iconHtml = tab.icon.html;
    const count = tab.id === 'console'
      ? _state.consoleMessages.length
      : tab.id === 'screenshots'
        ? _state.screenshots.length
        : tab.id === 'sessions'
          ? _state.sessions.length
          : null;
    const countHtml = count != null ? `<span class="c-tab__count">${count}</span>` : '';
    return `
      <button class="c-tab ${isActive ? 'c-tab--active' : ''}"
              data-browser-tab="${tab.id}"
              role="tab"
              aria-selected="${isActive ? 'true' : 'false'}">
        <span class="c-tab__icon">${iconHtml}</span>
        <span>${tab.label}</span>
        ${countHtml}
      </button>
    `;
  }).join('');
}

function renderBrowserViewTab() {
  const content = _container?.querySelector('#browser-tab-content');
  if (!content) return;

  const isRunning = _state.browserStatus === 'running';
  const isLoading = _state.isLoading;
  const screenshotData = _state.screenshots.length > 0
    ? _state.screenshots[0].dataUrl
    : null;
  const globeHtml = ICONS.globe.html;

  let viewportHtml;
  if (isLoading) {
    viewportHtml = `
      <div class="browser-loading">
        <span class="c-spinner c-spinner--lg c-spinner--accent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4"
                    stroke-dashoffset="10"/>
          </svg>
        </span>
        <span>Loading…</span>
      </div>
    `;
  } else if (isRunning && screenshotData) {
    viewportHtml = `
      <div class="browser-screenshot-container">
        <img src="${_escapeHtml(screenshotData)}"
             alt="Page screenshot"
             class="browser-screenshot"
             id="browser-screenshot-img" />
      </div>
    `;
  } else if (isRunning) {
    viewportHtml = `
      <div class="browser-viewport-placeholder">
        <div class="browser-viewport-placeholder__icon">
          ${globeHtml}
        </div>
        <div class="browser-viewport-placeholder__text">
          Navigate to a URL to see the page content
        </div>
      </div>
    `;
  } else {
    viewportHtml = `
      <div class="browser-viewport-placeholder">
        <div class="browser-viewport-placeholder__icon" style="opacity: 0.3;">
          ${globeHtml}
        </div>
        <div class="browser-viewport-placeholder__text">
          Start the browser to begin
        </div>
      </div>
    `;
  }

  content.innerHTML = `
    <!-- Browser Viewport -->
    <div class="browser-viewport">
      ${viewportHtml}
    </div>

    <!-- Page Info Bar -->
    <div class="browser-page-info">
      <div class="browser-page-info__item" title="${_escapeHtml(_state.pageTitle)}">
        <span class="browser-page-info__label">Title:</span>
        <span class="browser-page-info__value">${_escapeHtml(_state.pageTitle || '—')}</span>
      </div>
      <div class="browser-page-info__item" title="${_escapeHtml(_state.currentUrl)}">
        <span class="browser-page-info__label">URL:</span>
        <span class="browser-page-info__value browser-page-info__value--url">${_escapeHtml(_state.currentUrl)}</span>
      </div>
      <div class="browser-page-info__item">
        <span class="browser-page-info__label">Status:</span>
        <span class="browser-page-info__value ${
          _state.pageStatusCode != null && _state.pageStatusCode >= 400
            ? 'browser-page-info__value--error'
            : _state.pageStatusCode != null
              ? 'browser-page-info__value--success'
              : ''
        }">${_state.pageStatusCode != null ? _state.pageStatusCode : '—'}</span>
      </div>
      ${_state.loadTimeMs != null ? `
        <div class="browser-page-info__item">
          <span class="browser-page-info__label">Load time:</span>
          <span class="browser-page-info__value">${_formatDuration(_state.loadTimeMs)}</span>
        </div>
      ` : ''}
    </div>

    <!-- Element Interaction -->
    <div class="browser-element-interaction">
      <div class="browser-element-interaction__row">
        <input type="text" class="c-input c-input--sm browser-selector-input"
               id="browser-selector-input"
               placeholder="CSS selector (e.g. #myButton, .class)"
               value="${_escapeHtml(_state.elementSelector)}" />
        <button class="c-btn c-btn--sm" id="browser-btn-click"
                ${isRunning && !_state.operationLoading.click ? '' : 'disabled'}>
          <span class="c-btn__icon">${ICONS.play.html}</span>
          Click
        </button>
        <button class="c-btn c-btn--sm" id="browser-btn-type"
                ${isRunning && !_state.operationLoading.click ? '' : 'disabled'}>
          <span class="c-btn__icon">${ICONS.edit.html}</span>
          Type
        </button>
        <button class="c-btn c-btn--sm" id="browser-btn-gettext"
                ${isRunning && !_state.operationLoading.click ? '' : 'disabled'}>
          <span class="c-btn__icon">${ICONS.fileText.html}</span>
          Get Text
        </button>
      </div>
      <div class="browser-element-interaction__input-row" id="browser-type-row" style="display: none;">
        <input type="text" class="c-input c-input--sm"
               id="browser-type-text"
               placeholder="Text to type…" />
        <button class="c-btn c-btn--sm c-btn--primary" id="browser-btn-type-send">
          Type
        </button>
      </div>
      ${_state.elementActionResult ? `
        <div class="browser-element-action-result">
          ${_escapeHtml(_state.elementActionResult)}
        </div>
      ` : ''}
    </div>
  `;
}

function renderConsoleTab() {
  const content = _container?.querySelector('#browser-tab-content');
  if (!content) return;

  const messages = _state.consoleFilter === 'all'
    ? _state.consoleMessages
    : _state.consoleMessages.filter((m) => m.level === _state.consoleFilter);

  const filterOptions = ['all', 'log', 'info', 'warn', 'error'];

  content.innerHTML = `
    <!-- Console Toolbar -->
    <div class="browser-console-toolbar">
      <div class="browser-console-filters">
        ${filterOptions.map((level) => `
          <button class="c-btn c-btn--sm ${_state.consoleFilter === level ? 'c-btn--primary' : 'c-btn--ghost'}"
                  data-console-filter="${level}">
            ${level.charAt(0).toUpperCase() + level.slice(1)}
          </button>
        `).join('')}
      </div>
      <div class="browser-console-actions">
        <button class="c-btn c-btn--sm c-btn--ghost" id="browser-console-clear"
                title="Clear console">
          <span class="c-btn__icon">${ICONS.trash.html}</span>
          Clear
        </button>
      </div>
    </div>

    <!-- Console Messages -->
    <div class="browser-console-messages">
      ${messages.length === 0 ? `
        <div class="browser-console-empty">
          ${_state.consoleMessages.length === 0
            ? 'No console messages yet.'
            : 'No messages match the current filter.'}
        </div>
      ` : messages.map((msg) => {
        const levelColors = {
          log: 'var(--text-secondary)',
          info: 'var(--info)',
          warn: 'var(--warning)',
          error: 'var(--danger)',
        };
        const levelLabels = {
          log: 'LOG',
          info: 'INFO',
          warn: 'WARN',
          error: 'ERROR',
        };
        return `
          <div class="browser-console-message browser-console-message--${_escapeHtml(msg.level)}">
            <span class="browser-console-message__level"
                  style="color: ${levelColors[msg.level] || 'var(--text-muted)'};">
              ${levelLabels[msg.level] || 'LOG'}
            </span>
            <span class="browser-console-message__text">${_escapeHtml(msg.text)}</span>
            <span class="browser-console-message__time">${_formatTimestamp(new Date(msg.timestamp))}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderScreenshotsTab() {
  const content = _container?.querySelector('#browser-tab-content');
  if (!content) return;

  const screenshots = _state.screenshots;

  content.innerHTML = `
    <div class="browser-screenshots-toolbar">
      <span class="browser-screenshots-count">${screenshots.length} screenshot${screenshots.length !== 1 ? 's' : ''}</span>
      <button class="c-btn c-btn--sm c-btn--primary" id="browser-screenshot-btn-full"
              ${_state.browserStatus === 'running' && !_state.operationLoading.screenshot ? '' : 'disabled'}>
        <span class="c-btn__icon">${ICONS.eye.html}</span>
        Full Page Screenshot
      </button>
      <button class="c-btn c-btn--sm" id="browser-screenshot-btn-viewport"
              ${_state.browserStatus === 'running' && !_state.operationLoading.screenshot ? '' : 'disabled'}>
        <span class="c-btn__icon">${ICONS.eye.html}</span>
        Viewport Screenshot
      </button>
    </div>

    <div class="browser-screenshots-grid" id="browser-screenshots-grid">
      ${screenshots.length === 0 ? `
        <div class="browser-screenshots-empty">
          No screenshots captured yet. Navigate to a page and take a screenshot.
        </div>
      ` : screenshots.map((shot) => `
        <div class="browser-screenshot-card" data-shot-id="${_escapeHtml(shot.id)}">
          <div class="browser-screenshot-card__preview">
            <img src="${_escapeHtml(shot.dataUrl)}"
                 alt="Screenshot from ${_formatTimestampFull(new Date(shot.timestamp))}"
                 loading="lazy" />
          </div>
          <div class="browser-screenshot-card__info">
            <div class="browser-screenshot-card__url" title="${_escapeHtml(shot.url)}">
              ${_escapeHtml(shot.url)}
            </div>
            <div class="browser-screenshot-card__meta">
              <span>${_formatTimestampFull(new Date(shot.timestamp))}</span>
              ${shot.fullPage ? '<span class="c-badge c-badge--info">Full</span>' : ''}
            </div>
          </div>
          <div class="browser-screenshot-card__actions">
            <button class="c-btn c-btn--sm c-btn--ghost browser-screenshot-view-btn"
                    data-shot-id="${_escapeHtml(shot.id)}"
                    title="View full size">
              ${ICONS.maximize.html}
            </button>
            <button class="c-btn c-btn--sm c-btn--ghost browser-screenshot-download-btn"
                    data-shot-id="${_escapeHtml(shot.id)}"
                    title="Download screenshot">
              ${ICONS.download.html}
            </button>
            <button class="c-btn c-btn--sm c-btn--ghost browser-screenshot-delete-btn"
                    data-shot-id="${_escapeHtml(shot.id)}"
                    title="Delete screenshot">
              ${ICONS.trash.html}
            </button>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderSessionsTab() {
  const content = _container?.querySelector('#browser-tab-content');
  if (!content) return;

  const plusHtml = ICONS.plus.html;
  const chevronRightHtml = ICONS.chevronRight.html;
  const closeHtml = ICONS.close.html;

  let listHtml;
  if (_state.sessions.length === 0) {
    listHtml = `
      <div class="browser-sessions-empty">
        No browser sessions. Start the browser and create a new session.
      </div>
    `;
  } else {
    listHtml = _state.sessions.map((session) => {
      const isActive = session.id === _state.activeSessionId;
      const activeBadge = isActive ? '<span class="c-badge c-badge--accent" style="margin-left: 8px; font-size: 9px;">Active</span>' : '';
      const switchBtn = !isActive ? `
        <button class="c-btn c-btn--sm c-btn--ghost browser-session-switch-btn"
                data-session-id="${_escapeHtml(session.id)}"
                title="Switch to this session">
          ${chevronRightHtml}
        </button>
      ` : '';
      return `
        <div class="browser-session-item ${isActive ? 'browser-session-item--active' : ''}"
             data-session-id="${_escapeHtml(session.id)}">
          <div class="browser-session-item__info">
            <div class="browser-session-item__title">
              ${_escapeHtml(session.title)}
              ${activeBadge}
            </div>
            <div class="browser-session-item__url">${_escapeHtml(session.url || '—')}</div>
          </div>
          <div class="browser-session-item__actions">
            ${switchBtn}
            <button class="c-btn c-btn--sm c-btn--ghost browser-session-close-btn"
                    data-session-id="${_escapeHtml(session.id)}"
                    title="Close session"
                    ${_state.sessions.length <= 1 ? 'disabled' : ''}>
              ${closeHtml}
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  content.innerHTML = `
    <div class="browser-sessions-toolbar">
      <button class="c-btn c-btn--sm c-btn--primary" id="browser-session-new-btn">
        <span class="c-btn__icon">${plusHtml}</span>
        New Session
      </button>
    </div>

    <div class="browser-sessions-list">
      ${listHtml}
    </div>
  `;
}

/* ── Full UI Render ───────────────────────────────────────────────────────── */

function renderUI() {
  if (_isDestroyed || !_container) return;

  // Update status indicator
  const statusDot = _container.querySelector('#browser-status-dot');
  const statusLabel = _container.querySelector('#browser-status-label');
  if (statusDot) {
    statusDot.style.background = _getStatusColor(_state.browserStatus);
    if (_state.browserStatus === 'starting') {
      statusDot.style.animation = 'pulseSoft 1s ease-in-out infinite';
    } else {
      statusDot.style.animation = '';
    }
  }
  if (statusLabel) {
    statusLabel.textContent = _getStatusLabel(_state.browserStatus);
  }

  // Update start/stop button
  const startStopBtn = _container.querySelector('#browser-start-stop-btn');
  if (startStopBtn) {
    const isRunning = _state.browserStatus === 'running';
    const isLoading = _state.operationLoading.start || _state.operationLoading.stop;
    const refreshHtml = ICONS.refresh.html;
    const closeHtml = ICONS.close.html;
    const playHtml = ICONS.play.html;
    let btnContent;
    if (isLoading) {
      const actionText = isRunning ? 'Stopping…' : 'Starting…';
      btnContent = `<span class="c-spinner c-spinner--sm">${refreshHtml}</span> ${actionText}`;
    } else if (isRunning) {
      btnContent = `${closeHtml} Stop Browser`;
    } else {
      btnContent = `${playHtml} Start Browser`;
    }
    startStopBtn.innerHTML = btnContent;
    startStopBtn.className = `c-btn c-btn--sm ${isRunning ? 'c-btn--danger-solid' : 'c-btn--primary'}`;
    startStopBtn.disabled = isLoading || _state.browserStatus === 'starting';
  }

  // Update navigation toolbar
  const urlInput = _container.querySelector('#browser-url-input');
  if (urlInput) {
    urlInput.value = _state.currentUrl;
    urlInput.disabled = _state.browserStatus !== 'running' || _state.isLoading;
  }

  const goBtn = _container.querySelector('#browser-go-btn');
  if (goBtn) {
    goBtn.disabled = _state.browserStatus !== 'running' || _state.isLoading || _state.operationLoading.navigate;
    goBtn.innerHTML = _state.operationLoading.navigate
      ? `<span class="c-spinner c-spinner--sm">${ICONS.refresh.html}</span>`
      : `${ICONS.chevronRight.html}`;
  }

  const backBtn = _container.querySelector('#browser-back-btn');
  if (backBtn) backBtn.disabled = !canGoBack() || _state.isLoading;

  const forwardBtn = _container.querySelector('#browser-forward-btn');
  if (forwardBtn) forwardBtn.disabled = !canGoForward() || _state.isLoading;

  const refreshBtn = _container.querySelector('#browser-refresh-btn');
  if (refreshBtn) refreshBtn.disabled = _state.browserStatus !== 'running' || _state.isLoading;

  const screenshotBtn = _container.querySelector('#browser-screenshot-btn');
  if (screenshotBtn) {
    screenshotBtn.disabled = _state.browserStatus !== 'running' || _state.operationLoading.screenshot;
  }

  // Status text
  const statusText = _container.querySelector('#browser-status-text');
  if (statusText) {
    if (_state.isLoading) {
      statusText.textContent = 'Loading…';
      statusText.style.color = 'var(--text-muted)';
    } else if (_state.statusMessage) {
      statusText.textContent = _state.statusMessage;
      statusText.style.color = 'var(--success)';
    } else if (_state.browserError) {
      statusText.textContent = _state.browserError;
      statusText.style.color = 'var(--danger)';
    } else if (_state.browserStatus === 'running') {
      statusText.textContent = 'Ready';
      statusText.style.color = 'var(--text-muted)';
    } else if (_state.browserStatus === 'stopped') {
      statusText.textContent = 'Browser stopped';
      statusText.style.color = 'var(--text-muted)';
    } else {
      statusText.textContent = '';
    }
  }

  // Error banner
  const errorBanner = _container.querySelector('#browser-error-banner');
  if (errorBanner) {
    if (_state.browserError && !_state.statusMessage && !_state.isLoading) {
      errorBanner.style.display = 'flex';
      errorBanner.innerHTML = `
        <span class="c-alert__icon">${ICONS.error.html}</span>
        <span class="c-alert__content">${_escapeHtml(_state.browserError)}</span>
        <button class="c-alert__dismiss" id="browser-error-dismiss">${ICONS.close.html}</button>
      `;
      errorBanner.querySelector('#browser-error-dismiss')?.addEventListener('click', () => {
        _state.browserError = '';
        errorBanner.style.display = 'none';
      });
    } else {
      errorBanner.style.display = 'none';
    }
  }

  // Tab bar
  renderTabButtons();

  // Active tab content
  switch (_state.activeTab) {
    case 'view':
      renderBrowserViewTab();
      break;
    case 'console':
      renderConsoleTab();
      break;
    case 'screenshots':
      renderScreenshotsTab();
      break;
    case 'sessions':
      renderSessionsTab();
      break;
    default:
      renderBrowserViewTab();
  }
}

/* ── Event Binding ────────────────────────────────────────────────────────── */

function bindEvents() {
  if (!_container) return;

  const on = (selector, event, handler) => {
    const el = _container.querySelector(selector);
    if (el) {
      el.addEventListener(event, handler);
      _unbindFns.push(() => el.removeEventListener(event, handler));
    }
  };

  // Start/Stop browser
  on('#browser-start-stop-btn', 'click', () => {
    if (_state.browserStatus === 'running') {
      stopBrowser();
    } else {
      startBrowser();
    }
  });

  // URL input: Enter to navigate
  const urlInput = _container.querySelector('#browser-url-input');
  if (urlInput) {
    const handleUrlKeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        navigateTo(urlInput.value);
      }
    };
    urlInput.addEventListener('keydown', handleUrlKeydown);
    _unbindFns.push(() => urlInput.removeEventListener('keydown', handleUrlKeydown));
  }

  // Go button
  on('#browser-go-btn', 'click', () => {
    const input = _container.querySelector('#browser-url-input');
    if (input) navigateTo(input.value);
  });

  // Back/Forward
  on('#browser-back-btn', 'click', goBack);
  on('#browser-forward-btn', 'click', goForward);

  // Refresh
  on('#browser-refresh-btn', 'click', refreshPage);

  // Screenshot button in toolbar
  on('#browser-screenshot-btn', 'click', () => takeScreenshot(false));

  // Tab switching (delegated)
  const tabBar = _container.querySelector('#browser-tab-bar');
  if (tabBar) {
    const handleTabClick = (e) => {
      const tabBtn = e.target.closest('[data-browser-tab]');
      if (tabBtn) {
        const tabId = tabBtn.dataset.browserTab;
        if (tabId && tabId !== _state.activeTab) {
          _state.activeTab = tabId;
          renderUI();
        }
      }
    };
    tabBar.addEventListener('click', handleTabClick);
    _unbindFns.push(() => tabBar.removeEventListener('click', handleTabClick));
  }

  // Element interaction: Click
  on('#browser-btn-click', 'click', () => {
    const input = _container.querySelector('#browser-selector-input');
    if (input) {
      _state.elementSelector = input.value;
      clickElement(input.value);
    }
  });

  // Element interaction: Type - show text input
  on('#browser-btn-type', 'click', () => {
    const typeRow = _container.querySelector('#browser-type-row');
    if (typeRow) {
      typeRow.style.display = typeRow.style.display === 'none' ? 'flex' : 'none';
      if (typeRow.style.display === 'flex') {
        const textInput = typeRow.querySelector('#browser-type-text');
        if (textInput) textInput.focus();
      }
    }
  });

  // Element interaction: Type - send
  on('#browser-btn-type-send', 'click', () => {
    const selectorInput = _container.querySelector('#browser-selector-input');
    const textInput = _container.querySelector('#browser-type-text');
    if (selectorInput && textInput && selectorInput.value.trim() && textInput.value) {
      _state.elementSelector = selectorInput.value;
      typeText(selectorInput.value, textInput.value);
      textInput.value = '';
    }
  });

  // Element interaction: Get text
  on('#browser-btn-gettext', 'click', () => {
    const input = _container.querySelector('#browser-selector-input');
    if (input && input.value.trim()) {
      _state.elementSelector = input.value;
      getElementText(input.value);
    }
  });

  // Console: filter buttons (delegated)
  const consoleArea = _container.querySelector('#browser-tab-content');
  // We use a delegated listener on the container for dynamic filter buttons
  const handleConsoleFilter = (e) => {
    const filterBtn = e.target.closest('[data-console-filter]');
    if (filterBtn) {
      _state.consoleFilter = filterBtn.dataset.consoleFilter;
      renderConsoleTab();
    }
  };
  _container.addEventListener('click', handleConsoleFilter);
  _unbindFns.push(() => _container.removeEventListener('click', handleConsoleFilter));

  // Console: clear
  on('#browser-console-clear', 'click', clearConsole);

  // Screenshots: full page
  on('#browser-screenshot-btn-full', 'click', () => takeScreenshot(true));

  // Screenshots: viewport
  on('#browser-screenshot-btn-viewport', 'click', () => takeScreenshot(false));

  // Screenshots gallery: view, download, delete (delegated)
  const handleScreenshotAction = (e) => {
    const viewBtn = e.target.closest('.browser-screenshot-view-btn');
    const downloadBtn = e.target.closest('.browser-screenshot-download-btn');
    const deleteBtn = e.target.closest('.browser-screenshot-delete-btn');

    if (viewBtn) {
      const shotId = viewBtn.dataset.shotId;
      const shot = _state.screenshots.find((s) => s.id === shotId);
      if (shot) viewScreenshotFull(shot);
    }

    if (downloadBtn) {
      const shotId = downloadBtn.dataset.shotId;
      const shot = _state.screenshots.find((s) => s.id === shotId);
      if (shot) downloadScreenshot(shot);
    }

    if (deleteBtn) {
      const shotId = deleteBtn.dataset.shotId;
      _state.screenshots = _state.screenshots.filter((s) => s.id !== shotId);
      renderScreenshotsTab();
      renderTabButtons();
    }
  };
  _container.addEventListener('click', handleScreenshotAction);
  _unbindFns.push(() => _container.removeEventListener('click', handleScreenshotAction));

  // Sessions: new
  on('#browser-session-new-btn', 'click', () => {
    if (_state.browserStatus !== 'running') return;
    createSession();
    switchSession(_state.sessions[_state.sessions.length - 1].id);
  });

  // Sessions: switch/close (delegated)
  const handleSessionAction = (e) => {
    const switchBtn = e.target.closest('.browser-session-switch-btn');
    const closeBtn = e.target.closest('.browser-session-close-btn');

    if (switchBtn) {
      const sessionId = switchBtn.dataset.sessionId;
      if (sessionId) switchSession(sessionId);
    }

    if (closeBtn) {
      const sessionId = closeBtn.dataset.sessionId;
      if (sessionId) closeSession(sessionId);
    }
  };
  _container.addEventListener('click', handleSessionAction);
  _unbindFns.push(() => _container.removeEventListener('click', handleSessionAction));

  // Type text input: Enter to send
  const typeRow = _container.querySelector('#browser-type-row');
  if (typeRow) {
    const typeTextInput = typeRow.querySelector('#browser-type-text');
    if (typeTextInput) {
      const handleTypeKeydown = (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const sendBtn = _container.querySelector('#browser-btn-type-send');
          if (sendBtn) sendBtn.click();
        }
      };
      typeTextInput.addEventListener('keydown', handleTypeKeydown);
      _unbindFns.push(() => typeTextInput.removeEventListener('keydown', handleTypeKeydown));
    }
  }
}

function unbindEvents() {
  _unbindFns.forEach((fn) => fn());
  _unbindFns = [];
}

/* ── Screenshot Viewer ────────────────────────────────────────────────────── */

function viewScreenshotFull(shot) {
  // Create a modal overlay for viewing the full screenshot
  const backdrop = document.createElement('div');
  backdrop.className = 'c-modal-backdrop';
  backdrop.style.cursor = 'zoom-out';

  const img = document.createElement('img');
  img.src = shot.dataUrl;
  img.style.maxWidth = '90vw';
  img.style.maxHeight = '90vh';
  img.style.borderRadius = 'var(--radius-lg)';
  img.style.boxShadow = 'var(--shadow-xl)';
  img.style.objectFit = 'contain';
  img.style.cursor = 'default';

  const container = document.createElement('div');
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'center';
  container.style.gap = 'var(--space-4)';

  const info = document.createElement('div');
  info.style.cssText = 'display:flex;align-items:center;gap:var(--space-4);padding:var(--space-3)var(--space-5);background:var(--glass-bg-strong);backdrop-filter:blur(var(--glass-blur));border-radius:var(--radius-lg);border:1px solid var(--glass-border-strong);font-size:var(--font-size-sm);color:var(--text-secondary);';
  info.innerHTML = `
    <span>${_escapeHtml(shot.url)}</span>
    <span>·</span>
    <span>${_formatTimestampFull(new Date(shot.timestamp))}</span>
    ${shot.fullPage ? '<span class="c-badge c-badge--info">Full Page</span>' : ''}
  `;

  container.appendChild(img);
  container.appendChild(info);
  backdrop.appendChild(container);

  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) {
      backdrop.classList.add('c-modal-backdrop--exiting');
      setTimeout(() => backdrop.remove(), 200);
    }
  });

  document.body.appendChild(backdrop);
}

function downloadScreenshot(shot) {
  const link = document.createElement('a');
  link.href = shot.dataUrl;
  const filename = `screenshot-${new Date(shot.timestamp).toISOString().slice(0, 19).replace(/[:-]/g, '')}.png`;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/* ── Page Lifecycle ───────────────────────────────────────────────────────── */

/**
 * Render the browser page HTML into the given container.
 * Called by the router with routeInfo.
 * @param {Object} routeInfo - Route info from router
 * @returns {string} HTML string
 */
function render(routeInfo) {
  // Reset state
  _state.browserStatus = 'stopped';
  _state.statusMessage = '';
  _state.browserError = '';
  _state.currentUrl = DEFAULT_URL;
  _state.pageTitle = '';
  _state.pageStatusCode = null;
  _state.loadTimeMs = null;
  _state.isLoading = false;
  _state.urlHistory = [];
  _state.historyIndex = -1;
  _state.activeTab = 'view';
  _state.consoleMessages = [];
  _state.consoleFilter = 'all';
  _state.screenshots = [];
  _state.sessions = [];
  _state.activeSessionId = null;
  _state.sessionCounter = 0;
  _state.elementSelector = '';
  _state.elementActionResult = '';
  _state.operationLoading = {
    start: false,
    stop: false,
    navigate: false,
    click: false,
    screenshot: false,
  };

  // Create a default session
  createSession('Default');
  _state.activeSessionId = _state.sessions[0]?.id || null;

  // Return mount point; template loaded by mount()
  return '<div id="browser-root"></div>';
}

/**
 * Mount the browser page — called after HTML is inserted into the DOM.
 * Binds event listeners and populates initial state.
 * @param {Element} container - The page container element
 */
async function mount(container) {
  _container = container;
  _isDestroyed = false;

  // Load and inject the HTML template
  try {
    const rootEl = container.querySelector('#browser-root') || container;
    const templateHtml = await loadTemplate('browser', {
      defaultUrl: DEFAULT_URL,
      playIcon: ICONS.play.html,
    });
    rootEl.innerHTML = templateHtml;
  } catch (err) {
    console.error('[Browser] Failed to load template:', err);
  }

  // Render initial UI
  renderUI();

  // Bind events
  bindEvents();

  // Check if browser is already running (from previous session)
  checkInitialStatus();
}

async function checkInitialStatus() {
  try {
    const status = await _apiGetStatus();
    if (_isDestroyed) return;

    if (status.status === 'running') {
      _state.browserStatus = 'running';
      if (status.url) _state.currentUrl = status.url;
      if (status.title) _state.pageTitle = status.title;
      renderUI();
      startPolling();
    }
  } catch {
    // Browser not running — that's fine
  }
}

/**
 * Destroy the browser page — clean up all event listeners and state.
 */
function destroy() {
  _isDestroyed = true;
  stopPolling();
  unbindEvents();
  _container = null;

  // Reset state
  _state.browserStatus = 'stopped';
  _state.urlHistory = [];
  _state.historyIndex = -1;
  _state.consoleMessages = [];
  _state.screenshots = [];
  _state.sessions = [];
}

/* ── Exports ─────────────────────────────────────────────────────────────── */

export default {
  render,
  mount,
  destroy,
};
