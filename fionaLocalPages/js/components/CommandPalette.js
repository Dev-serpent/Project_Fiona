/* ==========================================================================
   CommandPalette.js — Command Palette (Raycast/Spotlight-Style)
   ==========================================================================
   Global command palette triggered by Cmd+K or / key.  Fuzzy search
   across commands grouped by category, keyboard navigation (Arrow
   Up/Down, Enter, Escape), recent actions when input is empty, and
   async command execution support.

   Usage:
     import { commandPalette } from './CommandPalette.js';

     commandPalette.registerCommands('Pages', [
       { id: 'go-dashboard', label: 'Go to Dashboard', icon: 'dashboard',
         execute: () => router.navigate('/') },
     ]);
     commandPalette.open();
   ========================================================================== */

import { BaseComponent, html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  palette: 'c-command-palette',
  dialog: 'c-command-palette__dialog',
  inputWrapper: 'c-command-palette__input-wrapper',
  icon: 'c-command-palette__icon',
  input: 'c-command-palette__input',
  results: 'c-command-palette__results',
  groupLabel: 'c-command-palette__group-label',
  result: 'c-command-palette__result',
  resultSelected: 'c-command-palette__result--selected',
  resultIcon: 'c-command-palette__result-icon',
  resultLabel: 'c-command-palette__result-label',
  resultDescription: 'c-command-palette__result-description',
  resultShortcut: 'c-command-palette__result-shortcut',
  empty: 'c-command-palette__empty',
  emptyIcon: 'c-command-palette__empty-icon',
  footer: 'c-command-palette__footer',
  footerHint: 'c-command-palette__footer-hint',
};

/* ── Simple fuzzy search ───────────────────────────────────────────────── */

/**
 * Simple fuzzy match: returns true if all chars of `query` appear in
 * order within `text`.
 * @param {string} query
 * @param {string} text
 * @returns {boolean}
 */
function fuzzyMatch(query, text) {
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  let qi = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++;
  }
  return qi === q.length;
}

/**
 * Calculate a simple relevance score for sorting results.
 * Exact prefix matches rank highest.
 * @param {string} query
 * @param {string} label
 * @param {string} [description]
 * @returns {number}
 */
function fuzzyScore(query, label, description) {
  const q = query.toLowerCase();
  const l = label.toLowerCase();
  let score = 0;

  // Exact match on label
  if (l === q) score += 100;
  // Label starts with query
  else if (l.startsWith(q)) score += 80;
  // Label contains query as word
  else if (l.includes(' ' + q) || l.includes('-' + q) || l.includes('_' + q)) score += 60;
  // Label contains query
  else if (l.includes(q)) score += 40;

  // Bonus for description match
  if (description) {
    const d = description.toLowerCase();
    if (d.startsWith(q)) score += 20;
    else if (d.includes(q)) score += 10;
  }

  // Shorter labels rank higher
  score += Math.max(0, 20 - l.length);

  return score;
}

/**
 * @typedef {Object} CommandDef
 * @property {string} id - Unique command ID
 * @property {string} label - Display label
 * @property {string} [description] - Description text
 * @property {string} [icon] - Icon key from ICONS
 * @property {string} [shortcut] - Keyboard shortcut hint
 * @property {string} [category] - Group category
 * @property {Function|Function} execute - Sync or async command handler
 * @property {boolean} [recent=false] - Whether this is a recent action
 */

/**
 * Create a command palette system.
 *
 * @param {string|Element} [container] - Container element. If not
 *        provided, uses or creates '#command-palette-container'.
 * @param {Object} [options]
 * @param {Function} [options.onClose] - Called when palette closes
 * @returns {CommandPaletteSystem}
 */
export function createCommandPalette(container, options = {}) {
  /** @type {Element} */
  let _container;

  /** @type {boolean} */
  let _isOpen = false;

  /** @type {CommandDef[]} All registered commands */
  let _commands = [];

  /** @type {string[]} Recent command IDs (most recent first) */
  let _recentIds = [];

  /** @type {number} Max recent items */
  const MAX_RECENT = 5;

  /* ── Resolve Container ───────────────────────────────────────────────── */

  function _resolveContainer() {
    if (_container) return _container;

    if (container) {
      _container = typeof container === 'string'
        ? document.querySelector(container)
        : container;
    }

    if (!_container) {
      _container = document.getElementById('command-palette-container');
    }

    if (!_container) {
      _container = document.createElement('div');
      _container.id = 'command-palette-container';
      document.body.appendChild(_container);
    }

    return _container;
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  /**
   * Render the palette with the given query.
   * @param {string} query
   * @private
   */
  function _render(query = '') {
    const el = _resolveContainer();
    if (!_isOpen) {
      el.style.display = 'none';
      el.innerHTML = '';
      return;
    }

    const results = _getFilteredResults(query);
    const grouped = _groupResults(results);

    el.style.display = 'flex';
    el.className = CSS.palette;

    el.innerHTML = html`
      <div class="${CSS.dialog}">
        <div class="${CSS.inputWrapper}">
          <span class="${CSS.icon}">${ICONS.search}</span>
          <input class="${CSS.input}"
                 type="text"
                 id="cmd-palette-input"
                 placeholder="Search commands and pages…"
                 autocomplete="off"
                 autocorrect="off"
                 spellcheck="false"
                 value="${query}" />
        </div>

        <div class="${CSS.results}" id="cmd-palette-results">
          ${grouped.length === 0 ? html`
            <div class="${CSS.empty}">
              <div class="${CSS.emptyIcon}">${ICONS.search}</div>
              <span>No results for "${query}"</span>
            </div>
          ` : grouped.map((g) => html`
            <div data-group="${g.category}">
              <div class="${CSS.groupLabel}">${g.category}</div>
              ${g.items.map((item, idx) => html`
                <div class="${CSS.result} ${idx === 0 ? CSS.resultSelected : ''}"
                     data-command-id="${item.id}"
                     role="option"
                     aria-selected="${idx === 0 ? 'true' : 'false'}">
                  <span class="${CSS.resultIcon}">${ICONS[item.icon] || ICONS.bolt}</span>
                  <span class="${CSS.resultLabel}">${item.label}</span>
                  ${item.description ? html`<span class="${CSS.resultDescription}">${item.description}</span>` : ''}
                  ${item.shortcut ? html`<span class="${CSS.resultShortcut}"><kbd>${item.shortcut}</kbd></span>` : ''}
                </div>
              `)}
            </div>
          `)}
        </div>

        <div class="${CSS.footer}">
          <span>${results.length} result${results.length !== 1 ? 's' : ''}</span>
          <div class="${CSS.footerHint}">
            <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
            <span><kbd>↵</kbd> select</span>
            <span><kbd>Esc</kbd> close</span>
          </div>
        </div>
      </div>
    `;

    // Focus input
    const input = el.querySelector(`.${CSS.input}`);
    if (input) {
      // Place cursor at end
      requestAnimationFrame(() => {
        input.focus();
        const len = input.value.length;
        input.setSelectionRange(len, len);
      });
    }

    // Bind events
    _bindEvents(el);
  }

  /**
   * Get filtered results sorted by relevance.
   * @param {string} query
   * @returns {CommandDef[]}
   * @private
   */
  function _getFilteredResults(query) {
    const trimmed = query.trim();

    if (!trimmed) {
      // Show recent actions when input is empty
      const recentCmds = _recentIds
        .map((id) => _commands.find((c) => c.id === id))
        .filter(Boolean);
      // Remaining commands sorted by category
      const otherCmds = _commands.filter((c) => !_recentIds.includes(c.id));
      return [...recentCmds, ...otherCmds];
    }

    // Fuzzy filter
    const scored = [];
    for (const cmd of _commands) {
      if (fuzzyMatch(trimmed, cmd.label) || (cmd.description && fuzzyMatch(trimmed, cmd.description))) {
        const score = fuzzyScore(trimmed, cmd.label, cmd.description);
        scored.push({ cmd, score });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.map((s) => s.cmd);
  }

  /**
   * Group results by category.
   * @param {CommandDef[]} results
   * @returns {Array<{category: string, items: CommandDef[]}>}
   * @private
   */
  function _groupResults(results) {
    const groups = new Map();
    for (const cmd of results) {
      const cat = cmd.category || 'Commands';
      if (!groups.has(cat)) groups.set(cat, []);
      groups.get(cat).push(cmd);
    }
    return Array.from(groups.entries()).map(([category, items]) => ({
      category,
      items,
    }));
  }

  /**
   * Bind keyboard and click events on the rendered palette.
   * @param {Element} el
   * @private
   */
  function _bindEvents(el) {
    const input = el.querySelector(`.${CSS.input}`);
    const resultsEl = el.querySelector(`.${CSS.results}`);

    if (!input || !resultsEl) return;

    // Input handler
    const onInput = () => {
      _render(input.value);
    };
    input.addEventListener('input', onInput);

    // Clean up previous listeners via data attributes
    // (we re-bind each render, so we need to clean up)
    // We'll use a single keydown handler on the dialog level

    const keyHandler = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        _moveSelection(1);
        return;
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        _moveSelection(-1);
        return;
      }

      if (e.key === 'Enter') {
        e.preventDefault();
        _activateSelected();
        return;
      }
    };

    el.addEventListener('keydown', keyHandler);

    // Click on result items
    const clickHandler = (e) => {
      const result = e.target.closest(`.${CSS.result}`);
      if (result) {
        const id = result.dataset.commandId;
        _executeCommand(id);
      }
    };
    resultsEl.addEventListener('click', clickHandler);

    // Click on backdrop to close
    el.addEventListener('click', (e) => {
      if (e.target === el) {
        close();
      }
    });

    // Store references for cleanup (they persist across re-renders on the el)
    el._cleanup = () => {
      input.removeEventListener('input', onInput);
      el.removeEventListener('keydown', keyHandler);
      resultsEl.removeEventListener('click', clickHandler);
    };
  }

  /**
   * Move the selection highlight by `delta` steps.
   * @param {number} delta
   * @private
   */
  function _moveSelection(delta) {
    const results = _resolveContainer().querySelectorAll(`.${CSS.result}`);
    const currentIdx = Array.from(results).findIndex(
      (r) => r.classList.contains(CSS.resultSelected)
    );

    let nextIdx = currentIdx + delta;
    if (nextIdx < 0) nextIdx = results.length - 1;
    if (nextIdx >= results.length) nextIdx = 0;

    results.forEach((r, i) => {
      r.classList.toggle(CSS.resultSelected, i === nextIdx);
      r.setAttribute('aria-selected', i === nextIdx ? 'true' : 'false');
    });

    // Scroll into view
    if (results[nextIdx]) {
      results[nextIdx].scrollIntoView({ block: 'nearest' });
    }
  }

  /**
   * Activate the currently selected command.
   * @private
   */
  function _activateSelected() {
    const selected = _resolveContainer().querySelector(`.${CSS.resultSelected}`);
    if (selected) {
      const id = selected.dataset.commandId;
      _executeCommand(id);
    }
  }

  /**
   * Execute a command by ID.
   * @param {string} id
   * @private
   */
  async function _executeCommand(id) {
    const cmd = _commands.find((c) => c.id === id);
    if (!cmd) return;

    // Track recent
    _recentIds = [id, ..._recentIds.filter((rid) => rid !== id)].slice(0, MAX_RECENT);

    // Close palette
    close();

    // Execute
    try {
      await cmd.execute();
    } catch (err) {
      console.error(`[CommandPalette] Error executing "${id}":`, err);
    }
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Open the command palette.
   */
  function open() {
    if (_isOpen) return;
    _isOpen = true;
    _render('');
  }

  /**
   * Close the command palette.
   */
  function close() {
    if (!_isOpen) return;
    _isOpen = false;
    _render('');
    if (options.onClose) options.onClose();
  }

  /**
   * Toggle the command palette open/closed.
   */
  function toggle() {
    if (_isOpen) close();
    else open();
  }

  /**
   * Check if the palette is open.
   * @returns {boolean}
   */
  function isOpen() {
    return _isOpen;
  }

  /**
   * Register a set of commands.
   *
   * @param {string} category - Group category name
   * @param {CommandDef[]} commands - Array of command definitions
   */
  function registerCommands(category, commands) {
    for (const cmd of commands) {
      cmd.category = category;
      // Remove existing command with same ID
      _commands = _commands.filter((c) => c.id !== cmd.id);
      _commands.push(cmd);
    }
  }

  /**
   * Register a single command.
   *
   * @param {CommandDef} command
   */
  function registerCommand(command) {
    _commands = _commands.filter((c) => c.id !== command.id);
    _commands.push(command);
  }

  /**
   * Remove a command by ID.
   * @param {string} id
   */
  function unregisterCommand(id) {
    _commands = _commands.filter((c) => c.id !== id);
    _recentIds = _recentIds.filter((rid) => rid !== id);
  }

  /**
   * Get all registered commands.
   * @returns {CommandDef[]}
   */
  function getCommands() {
    return [..._commands];
  }

  /**
   * Set up the global keyboard listeners (Cmd+K, /).
   * Should be called once during app init.
   */
  function initGlobalShortcut() {
    document.addEventListener('keydown', (e) => {
      // Skip if user is typing in an input
      const tag = e.target?.tagName?.toLowerCase();
      const isInput = tag === 'input' || tag === 'textarea' || e.target?.isContentEditable;

      // Cmd+K or Ctrl+K
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggle();
        return;
      }

      // / key to open (when not in an input)
      if (e.key === '/' && !isInput && !_isOpen) {
        e.preventDefault();
        open();
        return;
      }
    });
  }

  // Initialize
  _resolveContainer();

  return {
    open,
    close,
    toggle,
    isOpen,
    registerCommands,
    registerCommand,
    unregisterCommand,
    getCommands,
    initGlobalShortcut,
  };
}

/**
 * @typedef {Object} CommandPaletteSystem
 * @property {() => void} open
 * @property {() => void} close
 * @property {() => void} toggle
 * @property {() => boolean} isOpen
 * @property {(category: string, commands: CommandDef[]) => void} registerCommands
 * @property {(command: CommandDef) => void} registerCommand
 * @property {(id: string) => void} unregisterCommand
 * @property {() => CommandDef[]} getCommands
 * @property {() => void} initGlobalShortcut
 */

/**
 * Singleton command palette instance.
 *
 * Import and use directly:
 *   import { commandPalette } from './CommandPalette.js';
 *   commandPalette.registerCommands('Actions', [...]);
 *   commandPalette.open();
 *
 * @type {CommandPaletteSystem}
 */
export const commandPalette = createCommandPalette();

export default commandPalette;
