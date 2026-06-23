/**
 * ConsolePanel — Interactive command console.
 *
 * Features:
 * - Input field at the bottom with prompt
 * - Output area showing command results, errors, and system messages
 * - Command history navigation (up/down arrow)
 * - Submit sends a command to the server via client.call()
 * - Color-coded output: info (white), output (blue), error (red),
 *   warning (yellow), success (green), system (gray italic)
 */

export class ConsolePanel {
  /**
   * @param {HTMLElement} container - The #console-panel element.
   * @param {import('../client.js').RpcClient} client
   * @param {import('../store.js').CadStore} store
   */
  constructor(container, client, store) {
    this.container = container;
    this.client = client;
    this.store = store;

    /** @type {string[]} Command history (most recent last) */
    this.history = [];
    /** @type {number} Current history index (-1 means new input) */
    this.historyIndex = -1;
    /** @type {number} Maximum history entries */
    this.maxHistory = 200;

    this._build();
  }

  // ── Build ─────────────────────────────────────────────────────────

  _build() {
    this.container.innerHTML = '';

    // Output area
    this._outputEl = document.createElement('div');
    this._outputEl.id = 'console-output';
    this.container.appendChild(this._outputEl);

    // Input row
    const inputRow = document.createElement('div');
    inputRow.id = 'console-input-row';

    const prompt = document.createElement('span');
    prompt.id = 'console-prompt';
    prompt.textContent = '❯';
    inputRow.appendChild(prompt);

    this._inputEl = document.createElement('input');
    this._inputEl.id = 'console-input';
    this._inputEl.type = 'text';
    this._inputEl.placeholder = 'Enter command (e.g. create_box)';
    inputRow.appendChild(this._inputEl);

    this.container.appendChild(inputRow);

    // Focus input on click anywhere in the panel
    this.container.addEventListener('click', () => {
      this._inputEl.focus();
    });

    // Bind input events
    this._inputEl.addEventListener('keydown', (e) => this._onKeyDown(e));
    this._inputEl.addEventListener('blur', () => {
      // Small delay to allow click-to-focus on the panel
      setTimeout(() => this._inputEl.focus(), 10);
    });

    // Welcome message
    this.appendOutput('Fiona CAD Console v0.1.0', 'system');
    this.appendOutput('Type a command name and arguments, or "help" for commands.', 'system');
  }

  // ── Output ────────────────────────────────────────────────────────

  /**
   * Append a line to the output area.
   * @param {string} text - The line text.
   * @param {'info'|'output'|'error'|'warning'|'success'|'system'} type - Style class.
   */
  appendOutput(text, type = 'info') {
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    line.textContent = text;
    this._outputEl.appendChild(line);

    // Auto-scroll to bottom
    this._outputEl.scrollTop = this._outputEl.scrollHeight;

    // Limit output lines (prevent memory leak)
    while (this._outputEl.children.length > 500) {
      this._outputEl.removeChild(this._outputEl.firstChild);
    }
  }

  /**
   * Append multiple lines.
   * @param {string} text
   * @param {'info'|'output'|'error'|'warning'|'success'|'system'} type
   */
  appendMultiline(text, type = 'info') {
    const lines = text.split('\n');
    for (const line of lines) {
      this.appendOutput(line, type);
    }
  }

  // ── Input ─────────────────────────────────────────────────────────

  _onKeyDown(event) {
    const input = this._inputEl;

    if (event.key === 'Enter') {
      event.preventDefault();
      const text = input.value.trim();
      if (text) {
        this._executeInput(text);
      }
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (this.history.length === 0) return;
      if (this.historyIndex === -1) {
        // Save current draft
        this._draft = input.value;
        this.historyIndex = this.history.length - 1;
      } else if (this.historyIndex > 0) {
        this.historyIndex--;
      }
      input.value = this.history[this.historyIndex];
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (this.historyIndex === -1) return;
      if (this.historyIndex < this.history.length - 1) {
        this.historyIndex++;
        input.value = this.history[this.historyIndex];
      } else {
        // Back to draft
        this.historyIndex = -1;
        input.value = this._draft || '';
      }
      return;
    }

    if (event.key === 'l' && event.ctrlKey) {
      event.preventDefault();
      this.clearOutput();
    }
  }

  async _executeInput(text) {
    // Add to history
    this.history.push(text);
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    }
    this.historyIndex = -1;

    // Echo
    this.appendOutput(`❯ ${text}`, 'info');

    // Clear input
    this._inputEl.value = '';
    this._draft = '';

    // Parse: first word is command, rest is JSON kwargs
    const parts = text.split(' ');
    const commandName = parts[0];
    let kwargs = {};

    if (parts.length > 1) {
      try {
        kwargs = JSON.parse(parts.slice(1).join(' '));
      } catch {
        // Treat remaining words as positional string args
        kwargs = { args: parts.slice(1) };
      }
    }

    // Handle built-in commands
    if (commandName === 'help') {
      this._showHelp();
      return;
    }
    if (commandName === 'clear') {
      this.clearOutput();
      return;
    }
    if (commandName === 'documents') {
      this._listDocuments();
      return;
    }
    if (commandName === 'tree') {
      this._showTree();
      return;
    }

    // Send to server via RPC
    try {
      // Support both "command.name" and "namespace.name" patterns
      const method = commandName.includes('.') ? commandName : `command.execute`;
      const params = commandName.includes('.')
        ? { ...kwargs }
        : { doc_id: this.store.docId, name: commandName, kwargs };

      const result = await this.client.call(method, params);
      const output = typeof result === 'string'
        ? result
        : JSON.stringify(result, null, 2);
      this.appendMultiline(output, 'output');
    } catch (err) {
      this.appendOutput(`Error: ${err.message}`, 'error');
    }
  }

  // ── Built-in Commands ─────────────────────────────────────────────

  _showHelp() {
    this.appendOutput('Available commands:', 'system');
    this.appendOutput('  help              - Show this help', 'system');
    this.appendOutput('  clear             - Clear console output', 'system');
    this.appendOutput('  documents         - List open documents', 'system');
    this.appendOutput('  tree              - Show object tree', 'system');
    this.appendOutput('  create_box        - Create a box', 'system');
    this.appendOutput('  create_cylinder   - Create a cylinder', 'system');
    this.appendOutput('  create_sphere     - Create a sphere', 'system');
    this.appendOutput('  create_cone       - Create a cone', 'system');
    this.appendOutput('  create_torus      - Create a torus', 'system');
    this.appendOutput('  command.execute   - Execute any command', 'system');
    this.appendOutput('', 'system');
    this.appendOutput('  Examples:', 'system');
    this.appendOutput('    create_box', 'system');
    this.appendOutput('    create_cylinder {"radius": 15, "height": 30}', 'system');
    this.appendOutput('    command.execute {"doc_id": "...", "name": "recompute"}', 'system');
  }

  _listDocuments() {
    if (this.store.docId) {
      this.appendOutput(`Active document: ${this.store.docId}`, 'info');
      if (this.store.document) {
        this.appendOutput(`  Name: ${this.store.document.name}`, 'info');
        this.appendOutput(`  Objects: ${this.store.objectCount}`, 'info');
      }
    } else {
      this.appendOutput('No active document', 'info');
    }
  }

  _showTree() {
    const objects = this.store.objects;
    if (objects.length === 0) {
      this.appendOutput('No objects in document', 'info');
      return;
    }
    for (const obj of objects) {
      this.appendOutput(`  ${obj.uid.slice(0, 8)}  ${obj.type}  "${obj.name}"`, 'info');
    }
  }

  // ── Utility ───────────────────────────────────────────────────────

  /** Clear all output. */
  clearOutput() {
    this._outputEl.innerHTML = '';
  }

  /**
   * Focus the input field.
   */
  focus() {
    this._inputEl.focus();
  }
}
