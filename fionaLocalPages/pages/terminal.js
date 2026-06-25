/* ==========================================================================
   terminal.js — Terminal Emulator Page
   ==========================================================================
   Full-page terminal emulator with tabbed sessions, ANSI color rendering,
   command history, and shell command execution via the Fiona backend API.

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

const PROMPT_BASE = 'user@fiona';
const INITIAL_DIR = '~';
const MAX_OUTPUT_HEIGHT = 10000; // max lines in output buffer



/* ── ANSI Color Rendering ───────────────────────────────────────────────── */

/**
 * Convert a string containing ANSI escape codes to HTML with styled spans.
 * Supports foreground colors (30-37, 90-97), bold (1), dim (2), reset (0).
 *
 * @param {string} text - Raw text with ANSI escape sequences
 * @returns {string} HTML string with inline styles
 */
function renderAnsi(text) {
  if (!text) return '';

  const ansiStyles = {
    // Reset
    0: () => ({ bold: false, dim: false, color: null }),
    // Bold
    1: (s) => ({ ...s, bold: true }),
    // Dim / faint
    2: (s) => ({ ...s, dim: true }),
    // Italic
    3: (s) => ({ ...s, italic: true }),
    // Underline
    4: (s) => ({ ...s, underline: true }),
    // Slow blink
    5: (s) => ({ ...s }),
    // Fast blink
    6: (s) => ({ ...s }),
    // Inverse
    7: (s) => ({ ...s, inverse: true }),
    // Standard foreground colors 30-37
    30: (s) => ({ ...s, color: 'var(--terminal-gray)' }),
    31: (s) => ({ ...s, color: 'var(--terminal-red)' }),
    32: (s) => ({ ...s, color: 'var(--terminal-green)' }),
    33: (s) => ({ ...s, color: 'var(--terminal-yellow)' }),
    34: (s) => ({ ...s, color: 'var(--terminal-blue)' }),
    35: (s) => ({ ...s, color: 'var(--terminal-magenta)' }),
    36: (s) => ({ ...s, color: 'var(--terminal-cyan)' }),
    37: (s) => ({ ...s, color: 'var(--terminal-white)' }),
    // Bright foreground colors 90-97
    90: (s) => ({ ...s, color: '#808080' }),
    91: (s) => ({ ...s, color: '#ff6b6b' }),
    92: (s) => ({ ...s, color: '#69db7c' }),
    93: (s) => ({ ...s, color: '#ffd43b' }),
    94: (s) => ({ ...s, color: '#74c0fc' }),
    95: (s) => ({ ...s, color: '#da77f2' }),
    96: (s) => ({ ...s, color: '#66d9e8' }),
    97: (s) => ({ ...s, color: '#ffffff' }),
    // Background colors 40-47
    40: (s) => ({ ...s, bgColor: '#1a1a1a' }),
    41: (s) => ({ ...s, bgColor: '#cc0000' }),
    42: (s) => ({ ...s, bgColor: '#00aa00' }),
    43: (s) => ({ ...s, bgColor: '#aaaa00' }),
    44: (s) => ({ ...s, bgColor: '#0000cc' }),
    45: (s) => ({ ...s, bgColor: '#cc00cc' }),
    46: (s) => ({ ...s, bgColor: '#00cccc' }),
    47: (s) => ({ ...s, bgColor: '#cccccc' }),
  };

  // Split on ANSI escape sequences: ESC[<params>m
  const parts = text.split(/(\x1b\[[\d;]*m)/);
  const fragments = [];
  let currentStyle = { bold: false, dim: false, color: null, bgColor: null, italic: false, underline: false, inverse: false };

  for (const part of parts) {
    const ansiMatch = part.match(/^\x1b\[([\d;]*)m$/);
    if (ansiMatch) {
      // Parse and apply ANSI codes
      const codes = ansiMatch[1] ? ansiMatch[1].split(';') : ['0'];
      for (const codeStr of codes) {
        const code = parseInt(codeStr, 10);
        const styleFn = ansiStyles[code];
        if (styleFn) {
          currentStyle = styleFn(currentStyle);
        } else if (code >= 30 && code <= 37) {
          currentStyle.color = `var(--terminal-${['black','red','green','yellow','blue','magenta','cyan','white'][code - 30]})`;
        }
      }
    } else if (part) {
      // Regular text — build a span with inline styles
      const escaped = _escapeHtml(part);
      const styles = [];

      if (currentStyle.color) styles.push(`color: ${currentStyle.color}`);
      if (currentStyle.bgColor) styles.push(`background: ${currentStyle.bgColor}`);
      if (currentStyle.bold) styles.push('font-weight: 700');
      if (currentStyle.dim) styles.push('opacity: 0.7');
      if (currentStyle.italic) styles.push('font-style: italic');
      if (currentStyle.underline) styles.push('text-decoration: underline');
      if (currentStyle.inverse) {
        styles.push('background: var(--text-primary)');
        styles.push('color: var(--bg-primary)');
      }

      if (styles.length > 0) {
        fragments.push(`<span style="${styles.join(';')}">${escaped}</span>`);
      } else {
        fragments.push(escaped);
      }
    }
  }

  return fragments.join('');
}

/**
 * Escape HTML special characters.
 * @param {string} str
 * @returns {string}
 */
function _escapeHtml(str) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

/* ── Format duration ────────────────────────────────────────────────────── */

function formatDuration(ms) {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

/* ── Terminal Session ───────────────────────────────────────────────────── */

class TerminalSession {
  constructor(id) {
    this.id = id;
    this.output = [];         // Array of { text, type: 'stdout'|'stderr'|'system'|'prompt' }
    this.commandHistory = [];
    this.historyIndex = -1;
    this.currentDir = INITIAL_DIR;
    this.isLoading = false;
    this.cwd = INITIAL_DIR;
  }

  addOutput(text, type = 'stdout') {
    this.output.push({ text, type });
    // Trim if too long
    if (this.output.length > MAX_OUTPUT_HEIGHT) {
      this.output = this.output.slice(-MAX_OUTPUT_HEIGHT);
    }
  }

  addPrompt(dir) {
    this.addOutput(`${PROMPT_BASE}:${dir || this.cwd}$ `, 'prompt');
  }

  addCommand(command) {
    this.commandHistory.push(command);
    this.historyIndex = this.commandHistory.length;
  }

  getPrevHistory() {
    if (this.commandHistory.length === 0) return null;
    this.historyIndex = Math.max(0, Math.min(this.historyIndex - 1, this.commandHistory.length - 1));
    return this.commandHistory[this.historyIndex];
  }

  getNextHistory() {
    if (this.commandHistory.length === 0) return null;
    this.historyIndex = Math.min(this.historyIndex + 1, this.commandHistory.length);
    if (this.historyIndex >= this.commandHistory.length) {
      return '';
    }
    return this.commandHistory[this.historyIndex];
  }

  /**
   * Try to extract the working directory from command output.
   */
  updateDirFromOutput(stdout, stderr) {
    // If command was 'pwd', the stdout contains the directory
    // If command had 'cd', we track it
    const combined = stdout + stderr;
    // Simple heuristic: look for path patterns in output
    const pathMatch = combined.match(/^(\/[^\s]+)$/m);
    if (pathMatch) {
      this.cwd = pathMatch[1];
    }
  }
}

/* ── Page State ─────────────────────────────────────────────────────────── */

let _container = null;
let _sessions = [];
let _activeSessionId = 0;
let _sessionCounter = 0;
let _inputEl = null;
let _outputEl = null;
let _tabsEl = null;
let _clearBtn = null;
let _copyBtn = null;
let _helpBtn = null;
let _resizeHandler = null;
let _popstateHandler = null;
let _isDestroyed = false;

/* ── Create a new session ───────────────────────────────────────────────── */

function createSession() {
  const id = ++_sessionCounter;
  const session = new TerminalSession(id);
  session.addOutput(`Fiona Terminal v0.2.0 — Shell commands on the Fiona host`, 'system');
  session.addOutput(`Type 'help' or press ? for command reference. Press ↑/↓ for history, Tab for autocomplete.\n`, 'system');
  session.addPrompt(session.cwd);
  _sessions.push(session);
  if (_sessions.length === 1) {
    _activeSessionId = id;
  }
  return session;
}

/* ── Get current session ────────────────────────────────────────────────── */

function getActiveSession() {
  return _sessions.find((s) => s.id === _activeSessionId) || _sessions[0];
}

/* ── Render Functions ────────────────────────────────────────────────────── */

function renderTabs() {
  if (!_tabsEl) return;

  _tabsEl.innerHTML = _sessions.map((session) => {
    const isActive = session.id === _activeSessionId;
    return html`
      <div class="terminal-tab ${isActive ? 'terminal-tab--active' : ''}"
           data-tab-id="${session.id}"
           role="tab"
           aria-selected="${isActive ? 'true' : 'false'}">
        <span class="terminal-tab__label">Terminal ${session.id}</span>
        ${_sessions.length > 1 ? html`
          <button class="terminal-tab__close" data-tab-close="${session.id}"
                  title="Close terminal" aria-label="Close terminal ${session.id}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" width="12" height="12"
                 stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        ` : ''}
        ${session.isLoading ? html`
          <span class="c-spinner c-spinner--sm" style="margin-left: 4px;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4"
                      stroke-dashoffset="10"/>
            </svg>
          </span>
        ` : ''}
      </div>
    `;
  }).join('');

  // Add the new tab button
  const newTabBtn = document.createElement('button');
  newTabBtn.className = 'terminal-tab terminal-tab--new';
  newTabBtn.setAttribute('data-action', 'new-tab');
  newTabBtn.setAttribute('title', 'New terminal tab');
  newTabBtn.setAttribute('aria-label', 'New terminal tab');
  newTabBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="2" width="14" height="14"
         stroke-linecap="round" stroke-linejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"/>
      <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  `;
  _tabsEl.appendChild(newTabBtn);
}

function renderOutput() {
  if (!_outputEl) return;

  const session = getActiveSession();
  if (!session) {
    _outputEl.innerHTML = '';
    return;
  }

  _outputEl.innerHTML = session.output.map((line) => {
    if (line.type === 'prompt') {
      return html`<div class="terminal-line terminal-line--prompt">${html.raw(renderAnsi(line.text))}</div>`;
    } else if (line.type === 'stdout') {
      return html`<div class="terminal-line terminal-line--stdout">${html.raw(renderAnsi(line.text))}</div>`;
    } else if (line.type === 'stderr') {
      return html`<div class="terminal-line terminal-line--stderr">${html.raw(renderAnsi(line.text))}</div>`;
    } else if (line.type === 'system') {
      return html`<div class="terminal-line terminal-line--system">${html.raw(renderAnsi(line.text))}</div>`;
    }
    return html`<div class="terminal-line">${html.raw(renderAnsi(line.text))}</div>`;
  }).join('');

  // Scroll to bottom
  _outputEl.scrollTop = _outputEl.scrollHeight;
}

function updateInputPrompt() {
  const session = getActiveSession();
  const promptEl = _container?.querySelector('.terminal-prompt');
  if (promptEl && session) {
    promptEl.textContent = `${PROMPT_BASE}:${session.cwd}$ `;
  }
}

/* ── Execute Command ────────────────────────────────────────────────────── */

async function executeCommand(command) {
  const session = getActiveSession();
  if (!session || !command.trim() || session.isLoading) return;

  const trimmed = command.trim();

  const api = getApi();
  if (!api) {
    session.addOutput('Error: API client not available', 'stderr');
    renderOutput();
    return;
  }

  // Add command to history
  session.addCommand(trimmed);

  // Show command in output
  session.addOutput(`${PROMPT_BASE}:${session.cwd}$ ${command}`, 'stdout');

  // Set loading
  session.isLoading = true;
  renderTabs();

  try {
    const result = await api.post('/api/v1/terminal/exec', {
      command: trimmed,
    });

    // Handle response
    const data = result.data || result;

    // Built-in: clear terminal
    if (data.action === 'clear') {
      session.output = [];
      session.addPrompt(session.cwd);
      renderOutput();
      return;
    }

    if (data.stdout) {
      session.addOutput(data.stdout, 'stdout');
    }
    if (data.stderr) {
      session.addOutput(data.stderr, 'stderr');
    }

    // Show return code if non-zero
    if (data.returncode !== undefined && data.returncode !== 0) {
      session.addOutput(`\nProcess exited with code ${data.returncode}`, 'system');
    }

    // Show duration
    if (data.duration_ms) {
      session.addOutput(`[Completed in ${formatDuration(data.duration_ms)}]`, 'system');
    }

    // Track cwd changes
    if (trimmed.startsWith('cd ')) {
      const dirArg = trimmed.slice(3).trim();
      if (dirArg.startsWith('/')) {
        session.cwd = dirArg;
      } else if (dirArg === '..') {
        const parts = session.cwd.split('/').filter(Boolean);
        parts.pop();
        session.cwd = parts.length > 0 ? '/' + parts.join('/') : '/';
      } else if (dirArg === '~' || dirArg === '') {
        session.cwd = INITIAL_DIR;
      } else {
        const base = session.cwd === INITIAL_DIR ? '/home' : session.cwd;
        session.cwd = base.replace(/\/$/, '') + '/' + dirArg;
      }
      // Verify with pwd
      try {
        const pwdResult = await api.post('/api/v1/terminal/exec', { command: 'pwd' });
        const pwdData = pwdResult.data || pwdResult;
        if (pwdData.stdout) {
          const actualDir = pwdData.stdout.trim();
          if (actualDir) session.cwd = actualDir;
        }
      } catch { /* silent */ }
    }

    if (trimmed === 'pwd') {
      const pwdData = data.stdout?.trim();
      if (pwdData && pwdData.startsWith('/')) {
        session.cwd = pwdData;
      }
    }

  } catch (err) {
    const msg = err.message || 'Unknown error';
    if (err.name === 'NetworkError' || err.name === 'ApiError') {
      session.addOutput(`Error: ${msg}`, 'stderr');
      if (err.status === 403) {
        session.addOutput('This command was blocked by shell safety restrictions.', 'stderr');
      }
    } else {
      session.addOutput(`Error: ${msg}`, 'stderr');
    }
    console.error('[Terminal] Command failed:', err);
  } finally {
    session.isLoading = false;
    renderTabs();
    renderOutput();
    updateInputPrompt();
  }
}

/* ── Event Handling ─────────────────────────────────────────────────────── */

function handleInputKeydown(e) {
  const session = getActiveSession();
  if (!session) return;

  if (e.key === 'Enter') {
    e.preventDefault();
    const command = _inputEl.value;
    _inputEl.value = '';
    executeCommand(command);
    return;
  }

  if (e.key === 'ArrowUp') {
    e.preventDefault();
    const prev = session.getPrevHistory();
    if (prev !== null) {
      _inputEl.value = prev;
      // Move cursor to end
      setTimeout(() => {
        _inputEl.selectionStart = _inputEl.selectionEnd = _inputEl.value.length;
      }, 0);
    }
    return;
  }

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    const next = session.getNextHistory();
    _inputEl.value = next !== null ? next : '';
    return;
  }

  if (e.key === 'l' && e.ctrlKey) {
    e.preventDefault();
    clearTerminal();
    return;
  }

  // Tab autocomplete — queries the Python backend
  if (e.key === 'Tab') {
    e.preventDefault();
    const partial = _inputEl.value.trim();
    if (!partial) return;
    const api = getApi();
    if (!api) return;
    api.post('/api/v1/terminal/autocomplete', { partial })
      .then((result) => {
        const data = result.data || result;
        const matches = data.matches || [];
        if (matches.length === 0) return;
        const session = getActiveSession();
        if (session) {
          session.addOutput(`\x1b[2m⤷ ${matches.join(', ')}\x1b[0m`, 'system');
          renderOutput();
        }
        _inputEl.value = matches[0] + ' ';
        setTimeout(() => {
          _inputEl.selectionStart = _inputEl.selectionEnd = _inputEl.value.length;
        }, 0);
      })
      .catch(() => { /* autocomplete silently fails */ });
    return;
  }
}

function handleTabClick(e) {
  const tabEl = e.target.closest('[data-tab-id]');
  if (tabEl) {
    const id = parseInt(tabEl.dataset.tabId, 10);
    if (!isNaN(id) && id !== _activeSessionId) {
      switchTab(id);
    }
    return;
  }

  // Close button
  const closeBtn = e.target.closest('[data-tab-close]');
  if (closeBtn) {
    e.stopPropagation();
    const id = parseInt(closeBtn.dataset.tabClose, 10);
    if (!isNaN(id)) {
      closeTab(id);
    }
    return;
  }

  // New tab button
  const newBtn = e.target.closest('[data-action="new-tab"]');
  if (newBtn) {
    e.preventDefault();
    createSession();
    _activeSessionId = _sessions[_sessions.length - 1].id;
    renderTabs();
    renderOutput();
    updateInputPrompt();
    _focusInput();
    return;
  }
}

function switchTab(id) {
  _activeSessionId = id;
  renderTabs();
  renderOutput();
  updateInputPrompt();
  _focusInput();
}

function closeTab(id) {
  if (_sessions.length <= 1) return; // Keep at least one tab

  const idx = _sessions.findIndex((s) => s.id === id);
  if (idx === -1) return;

  _sessions.splice(idx, 1);

  // If active tab was closed, pick nearest
  if (_activeSessionId === id) {
    const newIdx = Math.min(idx, _sessions.length - 1);
    _activeSessionId = _sessions[newIdx].id;
  }

  renderTabs();
  renderOutput();
  updateInputPrompt();
  _focusInput();
}

function clearTerminal() {
  const session = getActiveSession();
  if (!session) return;
  session.output = [];
  session.addPrompt(session.cwd);
  renderOutput();
}

function copyOutput() {
  const session = getActiveSession();
  if (!session) return;

  const text = session.output
    .filter((l) => l.type === 'stdout' || l.type === 'stderr')
    .map((l) => l.text)
    .join('\n');

  if (!text) return;

  navigator.clipboard.writeText(text).catch(() => {
    // Fallback
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  });
}

function _focusInput() {
  if (_inputEl) {
    _inputEl.focus();
  }
}

/* ── Event Delegation ───────────────────────────────────────────────────── */

function bindEvents() {
  if (!_container) return;

  // Tab bar clicks (delegated)
  const tabBar = _container.querySelector('.terminal-tabs');
  if (tabBar) {
    tabBar.addEventListener('click', handleTabClick);
  }

  // Input keydown
  if (_inputEl) {
    _inputEl.addEventListener('keydown', handleInputKeydown);
  }

  // Clear button
  if (_clearBtn) {
    _clearBtn.addEventListener('click', clearTerminal);
  }

  // Copy button
  if (_copyBtn) {
    _copyBtn.addEventListener('click', copyOutput);
  }

  // Help button — sends "help" to the backend
  if (_helpBtn) {
    _helpBtn._listener = () => {
      executeCommand('help');
    };
    _helpBtn.addEventListener('click', _helpBtn._listener);
  }

  // Click anywhere in output to focus input
  if (_outputEl) {
    _outputEl.addEventListener('click', _focusInput);
  }

  // Resize handler
  _resizeHandler = () => {
    if (_outputEl) {
      _outputEl.scrollTop = _outputEl.scrollHeight;
    }
  };
  window.addEventListener('resize', _resizeHandler);
}

/* ── Cleanup Events ─────────────────────────────────────────────────────── */

function unbindEvents() {
  if (!_container) return;

  const tabBar = _container.querySelector('.terminal-tabs');
  if (tabBar) {
    tabBar.removeEventListener('click', handleTabClick);
  }

  if (_inputEl) {
    _inputEl.removeEventListener('keydown', handleInputKeydown);
  }

  if (_clearBtn) {
    _clearBtn.removeEventListener('click', clearTerminal);
  }

  if (_copyBtn) {
    _copyBtn.removeEventListener('click', copyOutput);
  }

  if (_helpBtn && _helpBtn._listener) {
    _helpBtn.removeEventListener('click', _helpBtn._listener);
    _helpBtn._listener = null;
  }

  if (_outputEl) {
    _outputEl.removeEventListener('click', _focusInput);
  }

  if (_resizeHandler) {
    window.removeEventListener('resize', _resizeHandler);
    _resizeHandler = null;
  }
}

/* ── Page Lifecycle ─────────────────────────────────────────────────────── */

/**
 * Render the terminal page — returns a mount point for the SPA router.
 * @param {Object} _routeInfo - Route info from router (unused)
 * @returns {string} HTML placeholder
 */
function render(_routeInfo) {
  return '<div id="terminal-root"></div>';
}

/**
 * Mount the terminal page — called after HTML is inserted into the DOM.
 * Loads the HTML template, initializes sessions, and binds events.
 * @param {Element} container - The page container element
 */
async function mount(container) {
  _container = container;
  _isDestroyed = false;

  // Reset state
  _sessions = [];
  _sessionCounter = 0;
  _activeSessionId = 0;

  // Load the template
  try {
    const rootEl = container.querySelector('#terminal-root') || container;
    const data = {
      initialPrompt: `${PROMPT_BASE}:${INITIAL_DIR}$ `,
    };
    rootEl.innerHTML = await loadTemplate('terminal', data);
  } catch (err) {
    console.error('[Terminal] Failed to load template:', err);
  }

  // Cache DOM references
  _tabsEl = container.querySelector('#terminal-tabs');
  _outputEl = container.querySelector('#terminal-output');
  _inputEl = container.querySelector('#terminal-input');
  _clearBtn = container.querySelector('#terminal-clear-btn');
  _copyBtn = container.querySelector('#terminal-copy-btn');
  _helpBtn = container.querySelector('#terminal-help-btn');

  // Create initial session
  createSession();

  // Render initial state
  renderTabs();
  renderOutput();
  updateInputPrompt();

  // Bind events
  bindEvents();

  // Focus input
  _focusInput();
}

/**
 * Destroy the terminal page — clean up all event listeners and state.
 */
function destroy() {
  _isDestroyed = true;
  unbindEvents();
  _container = null;
  _sessions = [];
  _inputEl = null;
  _outputEl = null;
  _tabsEl = null;
  _clearBtn = null;
  _copyBtn = null;
  _helpBtn = null;
  _resizeHandler = null;
}

/* ── Exports ─────────────────────────────────────────────────────────────── */

export default {
  render,
  mount,
  destroy,
};
