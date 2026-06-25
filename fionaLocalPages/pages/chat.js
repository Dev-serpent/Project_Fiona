/* ==========================================================================
   chat.js — AI Chat Page
   ==========================================================================
   Full AI chat interface for communicating with Fiona's agent (Ollama
   backend).  Features streaming token-by-token responses, session
   management, markdown rendering, configurable model/temperature/
   max-tokens settings, and WebSocket-based real-time communication.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const STORE_KEY = 'chat';
const DEFAULT_MODEL = 'llama3.2';
const DEFAULT_TEMPERATURE = 0.3;
const DEFAULT_MAX_TOKENS = 2048;
const WS_EVENT_STREAM = 'agent:stream';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,

  // Sessions
  sessions: [],
  activeSessionId: null,

  // Current session messages
  messages: [],

  // Streaming
  isStreaming: false,
  streamBuffer: '',
  streamMessageId: null,

  // UI
  sidebarOpen: true,
  error: null,

  // Config
  model: DEFAULT_MODEL,
  temperature: DEFAULT_TEMPERATURE,
  maxTokens: DEFAULT_MAX_TOKENS,
  systemPrompt: 'You are Fiona, a helpful AI assistant.',

  // WebSocket
  wsUnsub: null,
  wsMessageUnsub: null,

  // Refs
  messageListEl: null,
  inputEl: null,
  autoScroll: true,
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

function generateId() {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function generateSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

function formatTime(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}

function truncate(str, len = 60) {
  if (!str) return 'Empty chat';
  return str.length > len ? str.slice(0, len) + '…' : str;
}

/* ── Markdown Rendering ─────────────────────────────────────────────────── */

/**
 * Render markdown text to safe HTML.
 * Handles: **bold**, *italic*, `inline code`, ```code blocks```,
 * - lists, [links](url), and paragraphs.
 * @param {string} text
 * @returns {string} Safe HTML
 */
function renderMarkdown(text) {
  if (!text) return '';

  let result = esc(text);

  // Code blocks (```...```) — must be done before inline code
  result = result.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const highlighted = highlightSyntax(code, lang);
    return `<pre><code class="lang-${esc(lang || '')}">${highlighted}</code></pre>`;
  });

  // Inline code (`...`)
  result = result.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold (**...**)
  result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic (*...*)
  result = result.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Links [text](url)
  result = result.replace(/\[([^\]]+)]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Unordered list items (- ...)
  const lines = result.split('\n');
  let inList = false;
  const outLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^-\s+(.*)/);
    if (listMatch) {
      if (!inList) {
        outLines.push('<ul>');
        inList = true;
      }
      outLines.push(`<li>${listMatch[1]}</li>`);
    } else {
      if (inList) {
        outLines.push('</ul>');
        inList = false;
      }
      if (line.trim() === '') {
        outLines.push('<br>');
      } else if (
        !line.startsWith('<pre') &&
        !line.startsWith('<ul') &&
        !line.startsWith('<li') &&
        !line.startsWith('</')
      ) {
        outLines.push(`<p>${line}</p>`);
      } else {
        outLines.push(line);
      }
    }
  }
  if (inList) outLines.push('</ul>');

  return outLines.join('\n');
}

/**
 * Simple syntax highlighting for code blocks.
 * Wraps common keywords in <span> elements with color classes.
 * @param {string} code
 * @param {string} _lang
 * @returns {string} HTML with syntax spans
 */
function highlightSyntax(code, _lang) {
  const keywords = [
    'function', 'const', 'let', 'var', 'if', 'else', 'for', 'while',
    'do', 'switch', 'case', 'break', 'continue', 'return', 'throw',
    'try', 'catch', 'finally', 'new', 'delete', 'typeof', 'instanceof',
    'class', 'extends', 'super', 'import', 'export', 'default', 'from',
    'async', 'await', 'yield', 'of', 'in', 'this', 'true', 'false',
    'null', 'undefined', 'def', 'return', 'if', 'elif', 'else', 'for',
    'while', 'import', 'from', 'class', 'with', 'as', 'pass', 'raise',
    'except', 'finally', 'lambda', 'yield', 'global', 'nonlocal',
  ];

  // Escape first
  let result = esc(code);

  // String literals (single and double quoted)
  result = result.replace(/(["'`])(?:(?!\1|\\).|\\.)*\1/g,
    '<span style="color: var(--success);">$&</span>');

  // Comments (// and #)
  result = result.replace(/(\/\/.*$|#.*$)/gm,
    '<span style="color: var(--text-muted);">$&</span>');

  // Numbers
  result = result.replace(/\b(\d+\.?\d*)\b/g,
    '<span style="color: var(--warning);">$1</span>');

  // Keywords
  for (const kw of keywords) {
    const regex = new RegExp(`\\b${kw}\\b`, 'g');
    result = result.replace(regex,
      `<span style="color: var(--accent); font-weight: var(--font-weight-medium);">${kw}</span>`);
  }

  return result;
}

/* ── State Persistence ──────────────────────────────────────────────────── */

function loadState() {
  try {
    const stored = localStorage.getItem('fiona_chat_state');
    if (stored) {
      const parsed = JSON.parse(stored);
      _state.sessions = parsed.sessions || [];
      _state.activeSessionId = parsed.activeSessionId || null;
      _state.model = parsed.model || DEFAULT_MODEL;
      _state.temperature = parsed.temperature ?? DEFAULT_TEMPERATURE;
      _state.maxTokens = parsed.maxTokens ?? DEFAULT_MAX_TOKENS;
      _state.systemPrompt = parsed.systemPrompt || 'You are Fiona, a helpful AI assistant.';

      // Load active session messages
      if (_state.activeSessionId) {
        const active = _state.sessions.find((s) => s.id === _state.activeSessionId);
        _state.messages = active?.messages || [];
      }
    }
  } catch (e) {
    console.warn('[chat] Failed to load state from localStorage:', e);
  }
}

function saveState() {
  try {
    const data = {
      sessions: _state.sessions.map((s) => ({
        ...s,
        messages: s.messages,
      })),
      activeSessionId: _state.activeSessionId,
      model: _state.model,
      temperature: _state.temperature,
      maxTokens: _state.maxTokens,
      systemPrompt: _state.systemPrompt,
    };
    localStorage.setItem('fiona_chat_state', JSON.stringify(data));
  } catch (e) {
    console.warn('[chat] Failed to save state to localStorage:', e);
  }
}

/* ── Session Management ─────────────────────────────────────────────────── */

function createNewSession() {
  const id = generateSessionId();
  const session = {
    id,
    title: 'New Chat',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
    model: _state.model,
  };

  _state.sessions.unshift(session);
  _state.activeSessionId = id;
  _state.messages = [];
  saveState();
  renderChatUI();
}

function switchSession(sessionId) {
  if (_state.isStreaming) return;

  // Save current session messages
  const current = _state.sessions.find((s) => s.id === _state.activeSessionId);
  if (current) {
    current.messages = _state.messages;
    current.updatedAt = Date.now();
  }

  _state.activeSessionId = sessionId;
  const next = _state.sessions.find((s) => s.id === sessionId);
  _state.messages = next?.messages || [];

  saveState();
  renderChatUI();
  scrollToBottom();
}

function deleteSession(sessionId) {
  if (_state.isStreaming) return;

  _state.sessions = _state.sessions.filter((s) => s.id !== sessionId);

  if (_state.activeSessionId === sessionId) {
    if (_state.sessions.length > 0) {
      _state.activeSessionId = _state.sessions[0].id;
      _state.messages = _state.sessions[0].messages;
    } else {
      _state.activeSessionId = null;
      _state.messages = [];
    }
  }

  saveState();
  renderChatUI();
}

function updateSessionTitle(sessionId, content) {
  const session = _state.sessions.find((s) => s.id === sessionId);
  if (session) {
    const title = truncate(content.replace(/[*`#]/g, '').trim(), 60);
    if (title && session.title === 'New Chat') {
      session.title = title;
      session.updatedAt = Date.now();
      saveState();
    }
  }
}

/* ── Messages ───────────────────────────────────────────────────────────── */

function addMessage(role, content) {
  const msg = {
    id: generateId(),
    role,
    content,
    timestamp: Date.now(),
  };
  _state.messages.push(msg);

  // Also add to session
  const session = _state.sessions.find((s) => s.id === _state.activeSessionId);
  if (session) {
    session.messages = _state.messages;
    session.updatedAt = Date.now();
    updateSessionTitle(_state.activeSessionId, content);
  }

  saveState();
  return msg;
}

function updateLastMessage(content) {
  if (_state.messages.length === 0) return;
  const last = _state.messages[_state.messages.length - 1];
  last.content = content;

  const session = _state.sessions.find((s) => s.id === _state.activeSessionId);
  if (session) {
    session.messages = _state.messages;
  }

  saveState();
}

function retryLastMessage() {
  if (_state.isStreaming) return;
  // Find the last user message
  let lastUserIdx = -1;
  for (let i = _state.messages.length - 1; i >= 0; i--) {
    if (_state.messages[i].role === 'user') {
      lastUserIdx = i;
      break;
    }
  }
  if (lastUserIdx < 0) return;

  // Remove messages after (and including) the last assistant response
  if (lastUserIdx + 1 < _state.messages.length) {
    _state.messages = _state.messages.slice(0, lastUserIdx + 1);
  }

  const prompt = _state.messages[lastUserIdx].content;
  saveState();
  renderMessages();
  sendPrompt(prompt);
}

/* ── API Calls ──────────────────────────────────────────────────────────── */

function getWsUrl() {
  const base = getApi()?._getBaseURL?.() || 'http://localhost:8765';
  return base.replace(/^http/, 'ws') + '/ws';
}

async function checkAgentHealth() {
  const api = getApi();
  if (!api) return false;
  try {
    const res = await api.get('/api/v1/agent/status');
    return res?.data?.connected === true;
  } catch {
    return false;
  }
}

async function sendPrompt(prompt) {
  if (!prompt || !prompt.trim() || _state.isStreaming) return;

  // Ensure we have an active session
  if (!_state.activeSessionId) {
    createNewSession();
  }

  const api = getApi();
  if (!api) {
    _state.error = 'API client not available.';
    renderChatUI();
    return;
  }

  // Check agent health first
  const healthy = await checkAgentHealth();
  if (!healthy) {
    _state.error = 'Agent (Ollama) is not responding. Check that Ollama is running.';
    renderChatUI();
    return;
  }
  _state.error = null;

  // Add user message
  addMessage('user', prompt.trim());

  // Add placeholder assistant message
  const assistantMsg = addMessage('assistant', '');

  _state.isStreaming = true;
  _state.streamBuffer = '';
  _state.streamMessageId = assistantMsg.id;

  renderChatUI();

  // Try WebSocket streaming first, fall back to REST
  const wsUsed = await tryStreamViaWebSocket(prompt);

  if (!wsUsed) {
    await sendViaRest(prompt);
  }
}

async function tryStreamViaWebSocket(prompt) {
  const api = getApi();
  if (!api) return false;

  try {
    const ws = api.connect(getWsUrl(), { autoReconnect: false });
    if (!ws.connected) {
      // Wait briefly for connection
      await new Promise((resolve) => {
        const unsub = ws.on('open', () => {
          unsub();
          resolve();
        });
        setTimeout(resolve, 2000);
      });
    }

    if (!ws.connected) return false;

    // ── Stream state ──
    let streamComplete = false;
    let streamError = null;
    let receivedFirstToken = false;
    const REQ_ID = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    // ── Listen for stream data, errors, and RPC responses ──
    const unsubMessage = ws.on('message', (data) => {
      if (_state.destroyed) return;
      if (!data || typeof data !== 'object') return;

      // Track that we got some response (even error means server processed it)
      if (data.id === REQ_ID) receivedFirstToken = true;

      // Check for JSON-RPC error response
      if (data.id === REQ_ID && data.error) {
        streamError = data.error.message || 'Request rejected by server';
        streamComplete = true;
        return;
      }

      // Check for agent:stream event (WebSocket notification broadcast)
      if (data.event === WS_EVENT_STREAM) {
        const params = data.params || {};
        const token = params.token || params.text || params.content || '';
        receivedFirstToken = true;

        if (token) {
          _state.streamBuffer += token;
          updateLastMessage(_state.streamBuffer);
          renderMessages();
          scrollToBottom();
        }

        if (params.done) {
          streamComplete = true;
          if (params.final) {
            updateLastMessage(params.final);
            _state.streamBuffer = params.final;
          }
        }
        return;
      }

      // Check for JSON-RPC style method notification
      if (data.method === WS_EVENT_STREAM) {
        const params = data.params || {};
        const token = params.token || params.text || params.content || '';
        receivedFirstToken = true;

        if (token) {
          _state.streamBuffer += token;
          updateLastMessage(_state.streamBuffer);
          renderMessages();
          scrollToBottom();
        }

        if (params.done || params.final) {
          streamComplete = true;
          if (params.final) {
            updateLastMessage(params.final);
            _state.streamBuffer = params.final;
          }
        }
        return;
      }

      // Check for agent:error event
      if (data.event === 'agent:error' || data.method === 'agent:error') {
        receivedFirstToken = true;
        streamError = data.params?.message || 'Stream error';
        streamComplete = true;
      }
    });

    // ── Send the request with an id for error detection ──
    api.send('agent:ask', {
      prompt,
      model: _state.model,
      temperature: _state.temperature,
      max_tokens: _state.maxTokens,
      system: _state.systemPrompt,
      session_id: _state.activeSessionId,
    }, REQ_ID);

    // ── Two-stage wait: short deadline for first token, then extend ──
    await new Promise((resolve) => {
      const FIRST_TOKEN_TIMEOUT = 5000; // wait 5s for first token or error
      const STREAM_TIMEOUT = 60000;     // then up to 60s for completion

      let firstTimer = setTimeout(() => {
        clearInterval(poll);
        resolve();
      }, FIRST_TOKEN_TIMEOUT);

      let streamTimer = null;

      const poll = setInterval(() => {
        if (streamComplete || streamError || _state.destroyed) {
          clearInterval(poll);
          clearTimeout(firstTimer);
          if (streamTimer) clearTimeout(streamTimer);
          resolve();
        }
        // Once we get a first response, switch to longer timeout
        if (receivedFirstToken && firstTimer) {
          clearTimeout(firstTimer);
          firstTimer = null;
          streamTimer = setTimeout(() => {
            clearInterval(poll);
            resolve();
          }, STREAM_TIMEOUT);
        }
      }, 100);
    });

    unsubMessage();

    // ── Handle failure modes ──

    // If we connected but got no response at all (method not supported), fall back
    if (!receivedFirstToken && !streamComplete && !streamError) {
      console.log('[chat] WS request got no response — falling back to REST');
      // Keep isStreaming=true so the typing indicator persists during REST call
      return false;
    }

    // If the server doesn't support this method via WebSocket, fall back to REST
    if (streamError && (
      streamError.includes('Method not found') ||
      streamError.includes('not supported') ||
      streamError.includes('unrecognized')
    )) {
      console.log('[chat] WS method not supported — falling back to REST');
      // Keep isStreaming=true so the typing indicator persists during REST call
      return false;
    }

    if (streamError) {
      _state.error = streamError;
      renderChatUI();
      _state.isStreaming = false;
      // Don't fall back to REST on explicit error — the backend processed the
      // request and gave us a real error; retrying with REST is unlikely to help.
      return true;
    }

    _state.isStreaming = false;

    // Ensure the assistant message has content
    if (_state.streamBuffer && _state.messages.length > 0) {
      const lastMsg = _state.messages[_state.messages.length - 1];
      if (!lastMsg.content || lastMsg.content !== _state.streamBuffer) {
        updateLastMessage(_state.streamBuffer || '*(no response)*');
      }
    }

    renderMessages();
    saveState();
    return true;
  } catch (err) {
    console.warn('[chat] WebSocket streaming failed:', err);
    return false;
  }
}

async function sendViaRest(prompt) {
  const api = getApi();
  if (!api) return;

  try {
    const result = await api.post('/api/v1/agent/ask', {
      prompt,
      model: _state.model,
      temperature: _state.temperature,
      max_tokens: _state.maxTokens,
      system: _state.systemPrompt,
    });

    const response = result?.data?.response || result?.response || '*(no response)*';

    _state.streamBuffer = response;
    updateLastMessage(response);
    _state.isStreaming = false;
    renderMessages();
    scrollToBottom();
    saveState();
  } catch (err) {
    console.error('[chat] REST request failed:', err);
    _state.isStreaming = false;
    _state.error = err.message || 'Failed to send message.';
    renderChatUI();
  }
}

/* ── Message Rendering ──────────────────────────────────────────────────── */

function renderMessages() {
  const el = _state.messageListEl;
  if (!el) return;

  const messages = _state.messages;

  if (messages.length === 0) {
    el.innerHTML = `
      <div class="empty-state" style="padding: var(--space-16) var(--space-6);">
        <div class="empty-state__icon" style="opacity: 0.3;">
          ${ICONS.message.html}
        </div>
        <div class="empty-state__title">Start a Conversation</div>
        <div class="empty-state__description">
          Send a message to begin chatting with Fiona's AI agent.
        </div>
      </div>
    `;
    return;
  }

  el.innerHTML = messages.map((msg, idx) => {
    const isUser = msg.role === 'user';
    const isLast = idx === messages.length - 1;
    const isStreaming = isLast && _state.isStreaming && msg.role === 'assistant';
    const displayContent = isStreaming && _state.streamBuffer
      ? _state.streamBuffer
      : msg.content;
    const isEmpty = !displayContent && isStreaming;

    return `
      <div class="chat-message ${isUser ? 'chat-message--user' : 'chat-message--agent'}"
           data-message-id="${esc(msg.id)}"
           style="display: flex; gap: var(--space-3); padding: var(--space-4) var(--space-5);
                  ${isUser ? 'flex-direction: row-reverse;' : ''}">
        <!-- Avatar -->
        <div class="c-avatar ${isUser ? '' : 'c-avatar--accent'}"
             style="flex-shrink: 0; width: 32px; height: 32px;">
          ${isUser ? esc((getStore()?.get('app')?.username || 'U')[0]) : 'F'}
        </div>

        <!-- Content -->
        <div style="flex: 1; min-width: 0; max-width: 75%;">
          <!-- Header -->
          <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1); ${isUser ? 'justify-content: flex-end;' : ''}">
            <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); color: var(--text-secondary);">
              ${isUser ? 'You' : 'Fiona'}
            </span>
            <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">${formatTime(new Date(msg.timestamp))}</span>
            ${!isUser && !isStreaming ? `
              <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost chat-copy-btn"
                      data-copy-msg="${esc(msg.id)}"
                      title="Copy message"
                      style="opacity: 0; margin-left: auto; width: 24px; height: 24px;">
                ${ICONS.copy.html}
              </button>
            ` : ''}
          </div>

          <!-- Body -->
          <div class="chat-message__content"
               style="font-size: var(--font-size-sm); line-height: var(--line-height-relaxed); color: var(--text-primary);
                      ${isUser ? 'background: var(--accent-muted); padding: var(--space-3) var(--space-4); border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);' : ''}">
            ${isEmpty ? '<span class="chat-typing">▊</span>' : html.raw(renderMarkdown(displayContent || ''))}
            ${isStreaming && _state.streamBuffer ? '<span class="chat-typing" style="animation: pulseSoft 1s infinite;">▊</span>' : ''}
          </div>

          <!-- Retry button for failed messages -->
          ${isLast && msg.role === 'assistant' && !_state.isStreaming && !msg.content ? `
            <div style="margin-top: var(--space-2); display: flex; gap: var(--space-2);">
              <button class="c-btn c-btn--sm c-btn--ghost chat-retry-btn" data-retry>
                <span class="c-btn__icon">${ICONS.refresh.html}</span>
                Retry
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');

  // Hide copy buttons initially, show on hover
  el.querySelectorAll('.chat-message').forEach((msgEl) => {
    msgEl.addEventListener('mouseenter', () => {
      const btn = msgEl.querySelector('.chat-copy-btn');
      if (btn) btn.style.opacity = '1';
    });
    msgEl.addEventListener('mouseleave', () => {
      const btn = msgEl.querySelector('.chat-copy-btn');
      if (btn) btn.style.opacity = '0';
    });
  });

  // Copy buttons
  el.querySelectorAll('.chat-copy-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const msgId = btn.dataset.copyMsg;
      const msg = _state.messages.find((m) => m.id === msgId);
      if (msg?.content) {
        navigator.clipboard.writeText(msg.content).catch(() => {});
        btn.title = 'Copied!';
        setTimeout(() => { btn.title = 'Copy message'; }, 2000);
      }
    });
  });

  // Retry buttons
  el.querySelectorAll('.chat-retry-btn').forEach((btn) => {
    btn.addEventListener('click', () => retryLastMessage());
  });
}

function scrollToBottom() {
  if (!_state.autoScroll) return;
  const el = _state.messageListEl;
  if (el) {
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }
}

/* ── Sidebar Rendering ──────────────────────────────────────────────────── */

function renderSidebar() {
  const sidebarEl = _state.container?.querySelector('#chat-sidebar');
  if (!sidebarEl) return;

  const sessions = _state.sessions;

  sidebarEl.innerHTML = html`
    <div style="padding: var(--space-3); border-bottom: 1px solid var(--border-subtle);">
      <button class="c-btn c-btn--primary c-btn--full c-btn--sm" id="chat-new-session-btn">
        <span class="c-btn__icon">${ICONS.plus}</span>
        New Chat
      </button>
    </div>

    <div style="flex: 1; overflow-y: auto; padding: var(--space-2);">
      ${sessions.length === 0 ? `
        <div style="text-align: center; padding: var(--space-6); color: var(--text-muted); font-size: var(--font-size-xs);">
          No conversations yet.
        </div>
      ` : html.raw(sessions.map((s) => {
        const isActive = s.id === _state.activeSessionId;
        return `
          <div class="c-list__item ${isActive ? 'c-list__item--active' : ''}"
               data-session-id="${esc(s.id)}"
               style="cursor: pointer; display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); font-size: var(--font-size-sm);">
            <span style="flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${esc(s.title || 'New Chat')}
            </span>
            <span style="font-size: var(--font-size-xxs); color: var(--text-muted); flex-shrink: 0;">
              ${formatTime(new Date(s.updatedAt || s.createdAt))}
            </span>
            <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost chat-delete-session-btn"
                    data-session-id="${esc(s.id)}"
                    title="Delete conversation"
                    style="width: 22px; height: 22px; opacity: 0.5; flex-shrink: 0;">
              ${ICONS.trash}
            </button>
          </div>
        `;
      }).join(''))}
    </div>
  `;

  // New session button
  sidebarEl.querySelector('#chat-new-session-btn')?.addEventListener('click', () => {
    createNewSession();
  });

  // Session click to switch
  sidebarEl.querySelectorAll('[data-session-id]').forEach((el) => {
    el.addEventListener('click', (e) => {
      // Ignore if delete button was clicked
      if (e.target.closest('.chat-delete-session-btn')) return;
      const sid = el.dataset.sessionId;
      if (sid) switchSession(sid);
    });
  });

  // Delete session buttons
  sidebarEl.querySelectorAll('.chat-delete-session-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sid = btn.dataset.sessionId;
      if (sid) deleteSession(sid);
    });
  });
}

/* ── Full UI Render ─────────────────────────────────────────────────────── */

function renderChatUI() {
  if (_state.destroyed || !_state.container) return;

  // Render the sidebar
  renderSidebar();

  // Render messages
  renderMessages();

  // Update header
  updateHeader();

  // Update input area (streaming state)
  updateInputState();

  // Update error display
  updateError();
}

function updateHeader() {
  const headerEl = _state.container?.querySelector('#chat-header');
  if (!headerEl) return;

  const session = _state.sessions.find((s) => s.id === _state.activeSessionId);
  const title = session?.title || 'AI Chat';

  headerEl.innerHTML = `
    <div style="display: flex; align-items: center; gap: var(--space-3);">
      <button class="c-btn c-btn--icon c-btn--ghost" id="chat-toggle-sidebar" title="Toggle session list">
        ${ICONS.chevronLeft}
      </button>
      <div>
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary);">${esc(title)}</div>
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted);">
          ${_state.model} · ${_state.isStreaming ? 'Generating…' : `${_state.messages.length} messages`}
        </div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: var(--space-2);">
      ${_state.isStreaming ? `
        <button class="c-btn c-btn--sm c-btn--ghost" id="chat-stop-btn" style="color: var(--danger);">
          <span class="c-btn__icon">${ICONS.close}</span>
          Stop
        </button>
      ` : ''}
      <button class="c-btn c-btn--icon c-btn--ghost" id="chat-clear-btn" title="Clear chat">
        ${ICONS.trash}
      </button>
    </div>
  `;

  headerEl.querySelector('#chat-toggle-sidebar')?.addEventListener('click', () => {
    _state.sidebarOpen = !_state.sidebarOpen;
    const sidebar = _state.container?.querySelector('#chat-sidebar');
    if (sidebar) sidebar.style.display = _state.sidebarOpen ? 'flex' : 'none';
  });

  headerEl.querySelector('#chat-clear-btn')?.addEventListener('click', () => {
    if (_state.isStreaming) return;
    _state.messages = [];
    const session = _state.sessions.find((s) => s.id === _state.activeSessionId);
    if (session) {
      session.messages = [];
      session.title = 'New Chat';
    }
    saveState();
    renderChatUI();
  });

  headerEl.querySelector('#chat-stop-btn')?.addEventListener('click', () => {
    // Stop streaming - set flag and finalize
    _state.isStreaming = false;
    if (!_state.streamBuffer) {
      updateLastMessage('*(stopped)*');
    }
    renderChatUI();
  });
}

function updateInputState() {
  const inputEl = _state.container?.querySelector('#chat-input');
  const sendBtn = _state.container?.querySelector('#chat-send-btn');
  const inputWrapper = _state.container?.querySelector('#chat-input-wrapper');

  if (inputEl) inputEl.disabled = _state.isStreaming;
  if (sendBtn) {
    sendBtn.disabled = _state.isStreaming;
    sendBtn.innerHTML = _state.isStreaming
      ? `<span class="c-spinner c-spinner--sm">${ICONS.refresh}</span>`
      : `<span class="c-btn__icon">${ICONS.check}</span>`;
  }
  if (inputWrapper) {
    inputWrapper.style.opacity = _state.isStreaming ? '0.6' : '1';
  }
}

function updateError() {
  const errorEl = _state.container?.querySelector('#chat-error');
  if (!errorEl) return;

  if (_state.error) {
    errorEl.style.display = 'flex';
    errorEl.innerHTML = `
      <div class="c-alert c-alert--danger" style="margin: var(--space-3) var(--space-5);">
        <span class="c-alert__icon">${ICONS.error}</span>
        <span class="c-alert__content">${esc(_state.error)}</span>
        <button class="c-alert__dismiss" id="chat-error-dismiss">${ICONS.close}</button>
      </div>
    `;
    errorEl.querySelector('#chat-error-dismiss')?.addEventListener('click', () => {
      _state.error = null;
      errorEl.style.display = 'none';
    });
  } else {
    errorEl.style.display = 'none';
  }
}

/* ── Full Page Render ───────────────────────────────────────────────────── */

/**
 * Render the full chat page into the container.
 * @param {Element} container
 */
async function renderFullPage(container) {
  _state.container = container;

  const data = {
    sendIcon: ICONS.check.html,
  };

  container.innerHTML = await loadTemplate('chat', data);

  // Apply sidebar visibility
  const sidebarEl = container.querySelector('#chat-sidebar');
  if (sidebarEl) {
    sidebarEl.style.display = _state.sidebarOpen ? 'flex' : 'none';
  }

  // Apply settings values from state
  const modelSelect = container.querySelector('#chat-model-select');
  if (modelSelect) {
    for (const opt of modelSelect.options) {
      if (opt.value === _state.model) {
        opt.selected = true;
        break;
      }
    }
  }
  const tempSlider = container.querySelector('#chat-temp-slider');
  if (tempSlider) tempSlider.value = String(_state.temperature);
  const tempValue = container.querySelector('#chat-temp-value');
  if (tempValue) tempValue.textContent = String(_state.temperature);
  const maxTokens = container.querySelector('#chat-max-tokens');
  if (maxTokens) maxTokens.value = String(_state.maxTokens);

  // Apply input streaming state
  const inputEl = container.querySelector('#chat-input');
  if (inputEl) {
    inputEl.placeholder = _state.isStreaming
      ? 'Waiting for response…'
      : 'Type a message… (Enter to send, Shift+Enter for newline)';
    if (_state.isStreaming) inputEl.setAttribute('disabled', '');
    else inputEl.removeAttribute('disabled');
  }

  // Store refs
  _state.messageListEl = container.querySelector('#chat-messages');

  // Update sidebar, header, messages
  renderSidebar();
  renderMessages();
  updateHeader();
  updateInputState();
  updateError();

  // Bind events
  bindInputEvents(container);
  bindSettingsEvents(container);

  // Scroll to bottom
  setTimeout(scrollToBottom, 50);
}

/* ── Event Binding ───────────────────────────────────────────────────────── */

function bindInputEvents(container) {
  const inputEl = container.querySelector('#chat-input');
  const sendBtn = container.querySelector('#chat-send-btn');
  _state.inputEl = inputEl;

  if (!inputEl || !sendBtn) return;

  // Auto-resize textarea
  function autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
  }
  inputEl.addEventListener('input', autoResize);

  // Send on Enter (Shift+Enter for newline)
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendCurrentMessage();
    }
  });

  sendBtn.addEventListener('click', () => sendCurrentMessage());

  function sendCurrentMessage() {
    if (_state.isStreaming) return;
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendPrompt(text);
  }
}

function bindSettingsEvents(container) {
  // Model selector
  const modelSelect = container.querySelector('#chat-model-select');
  if (modelSelect) {
    modelSelect.addEventListener('change', () => {
      _state.model = modelSelect.value;
      saveState();
      updateHeader();
    });
  }

  // Temperature slider
  const tempSlider = container.querySelector('#chat-temp-slider');
  const tempValue = container.querySelector('#chat-temp-value');
  if (tempSlider && tempValue) {
    tempSlider.addEventListener('input', () => {
      _state.temperature = parseFloat(tempSlider.value);
      tempValue.textContent = _state.temperature.toFixed(1);
      saveState();
    });
  }

  // Max tokens
  const maxTokens = container.querySelector('#chat-max-tokens');
  if (maxTokens) {
    maxTokens.addEventListener('change', () => {
      _state.maxTokens = parseInt(maxTokens.value, 10) || DEFAULT_MAX_TOKENS;
      saveState();
    });
  }

  // Auto-scroll toggle
  const autoScrollCheck = container.querySelector('#chat-auto-scroll');
  if (autoScrollCheck) {
    autoScrollCheck.addEventListener('change', () => {
      _state.autoScroll = autoScrollCheck.checked;
    });
  }
}

/* ── Dynamic CSS Loading ─────────────────────────────────────────────────── */

/** @type {boolean} Whether chat.css has been loaded */
let _cssLoaded = false;

/**
 * Load chat-specific CSS dynamically (only once).
 * Falls back silently if the file is unavailable.
 */
function _loadChatCSS() {
  if (_cssLoaded) return;
  _cssLoaded = true;

  // Check if already in document (e.g. loaded via index.html)
  if (document.querySelector('link[href*="chat.css"]')) return;

  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'pages/chat.css';
  link.onerror = () => { _cssLoaded = false; }; // allow retry on next mount
  document.head.appendChild(link);
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Full render — called by the router or from mount().
 * @param {Element} container
 */
export function render() {
  return '<div id="chat-root"></div>';
}

export async function mount(container) {
  _state.destroyed = false;
  _state.container = container;

  // Load page-specific CSS (no-op if already loaded or loaded via index.html)
  _loadChatCSS();

  // Load persisted state
  loadState();

  // Ensure at least one session exists
  if (_state.sessions.length === 0) {
    createNewSession();
  }

  await renderFullPage(container);
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;

  // Save state before cleanup
  saveState();

  // Clean up WebSocket listeners
  if (_state.wsUnsub) { _state.wsUnsub(); _state.wsUnsub = null; }
  if (_state.wsMessageUnsub) { _state.wsMessageUnsub(); _state.wsMessageUnsub = null; }

  _state.container = null;
  _state.messageListEl = null;
  _state.inputEl = null;
  _state.isStreaming = false;
  _state.streamBuffer = '';
}

/* ── Router-compatible default export ────────────────────────────────────── */

/**
 * Factory function for the SPA router.
 * @param {Object} _routeInfo
 * @returns {{ render: Function, mount: Function, destroy: Function }}
 */
export default function createPage(_routeInfo) {
  return {
    render,
    async mount(container) {
      const root = container.querySelector('#chat-root') || container;
      _state.destroyed = false;
      _state.container = root;

      // Load page-specific CSS
      _loadChatCSS();

      // Load persisted state
      loadState();

      // Ensure at least one session exists
      if (_state.sessions.length === 0) {
        createNewSession();
      }

      await renderFullPage(root);
    },
    destroy,
  };
}
