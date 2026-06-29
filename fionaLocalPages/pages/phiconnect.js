/* ==========================================================================
   phiconnect.js — PhiConnect Secure Messaging Page
   ==========================================================================
   Full PhiConnect UI: service status & identity display, tab-based
   navigation for Messages, Contacts, Trust, and Configuration.  Messages
   tab includes compose/send form, search/filter, auto-refresh polling.
   Contacts tab shows trusted peers with add/remove.  Trust tab shows
   trusted keys with revoke.  Config tab exposes settings and key mgmt.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { toast } from '../js/components/Toast.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 10000;
const MESSAGE_POLL_SECONDS = 180;
const STORAGE_KEY = 'fiona_phiconnect_auto_refresh';

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function esc(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function timeAgo(timestamp) {
  // timestamp may be in seconds (from backend) or ms; normalize
  let ts = Number(timestamp);
  if (!ts) return '';
  // If it looks like seconds (before 3000-01-01), multiply
  if (ts < 100000000000) ts *= 1000;
  const now = Date.now();
  const diff = now - ts;
  const sec = Math.floor(diff / 1000);
  if (sec < 0) return 'just now';
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  let t = Number(ts);
  if (t < 100000000000) t *= 1000;
  return new Date(t).toLocaleString();
}

function persistAutoRefresh(value) {
  try {
    if (value) localStorage.setItem(STORAGE_KEY, '1');
    else localStorage.removeItem(STORAGE_KEY);
  } catch { /* ignore */ }
}

function loadAutoRefreshPreference() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

/* ── Simple inline SVG icons (not in ICONS) ───────────────────────────── */

const CONTACTS_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';

const SHIELD_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  status: null,            // { ready, port, config_dir, identity_exists, trusted_peers }
  identity: null,          // { device_id, public_bundle, fingerprint }
  messages: [],            // [{ sender, body, timestamp, ... }]
  autoRefresh: false,
  pollTimer: null,
  copyFeedback: false,
  sending: false,
  activeTab: 'messages',   // 'messages' | 'contacts' | 'trust' | 'config'
  peers: [],               // contacts/peers list
  trustedKeys: [],         // trusted keys list
  configData: null,        // { config: {...}, identity: {...} }
  messageSearch: '',       // current search string
  peerFilter: '',          // filter messages by sender
};

/* ── Modal helpers ─────────────────────────────────────────────────────── */

function showModal(htmlContent) {
  const overlay = document.getElementById('phc-modal-overlay');
  const body = document.getElementById('phc-modal-body');
  if (!overlay || !body) return;
  body.innerHTML = htmlContent;
  overlay.style.display = 'flex';

  // Close on overlay click
  overlay.onclick = (e) => {
    if (e.target === overlay) hideModal();
  };

  // Close on Escape
  const handler = (e) => {
    if (e.key === 'Escape') {
      hideModal();
      document.removeEventListener('keydown', handler);
    }
  };
  document.addEventListener('keydown', handler);
}

function hideModal() {
  const overlay = document.getElementById('phc-modal-overlay');
  if (overlay) overlay.style.display = 'none';
}

/* ── Tab Active Styles ─────────────────────────────────────────────────── */

function updateTabStyles(container) {
  const tabs = container.querySelectorAll('.phc-tab');
  tabs.forEach((btn) => {
    const tab = btn.getAttribute('data-tab');
    const isActive = tab === _state.activeTab;
    btn.className = `phc-tab c-btn c-btn--sm ${isActive ? 'c-btn--primary' : 'c-btn--ghost'}`;
    btn.style.borderBottom = isActive ? '2px solid var(--accent)' : '2px solid transparent';
  });
}

/* ── Render: Individual Tab Content ───────────────────────────────────── */

function renderMessagesTabHTML() {
  const messages = Array.isArray(_state.messages) ? _state.messages : [];
  const searchTerm = _state.messageSearch.toLowerCase().trim();

  // Apply search filter (client-side for responsiveness)
  let filtered = messages;
  if (searchTerm) {
    filtered = filtered.filter((m) =>
      (m.body || '').toLowerCase().includes(searchTerm) ||
      (m.sender || '').toLowerCase().includes(searchTerm)
    );
  }

  // Group by sender (message threading)
  const groups = {};
  filtered.forEach((msg) => {
    const sender = msg.sender || 'unknown';
    if (!groups[sender]) groups[sender] = [];
    groups[sender].push(msg);
  });

  let messagesHTML = '';
  const groupKeys = Object.keys(groups);
  if (groupKeys.length === 0) {
    messagesHTML = `
      <div style="text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-muted);">
        <div style="width: 40px; height: 40px; margin: 0 auto var(--space-3); display: flex; align-items: center; justify-content: center; color: var(--text-muted); opacity: 0.4;">
          ${ICONS.message.html}
        </div>
        <div style="font-size: var(--font-size-sm);">${searchTerm ? 'No messages match your search.' : 'No recent messages'}</div>
        <div style="font-size: var(--font-size-xs); margin-top: var(--space-1);">
          Messages from the last ${MESSAGE_POLL_SECONDS / 60} minutes appear here.
        </div>
      </div>
    `;
  } else {
    groupKeys.forEach((sender) => {
      const msgs = groups[sender];
      messagesHTML += `
        <div class="phc-message-group" style="margin-bottom: var(--space-3);">
          <div style="padding: var(--space-1) var(--space-3); font-size: var(--font-size-xxs); color: var(--text-muted); background: var(--bg-tertiary); border-radius: var(--radius-sm) var(--radius-sm) 0 0; font-family: var(--font-mono); display: flex; align-items: center; justify-content: space-between;">
            <span>${esc(sender)}</span>
            <span>${msgs.length} message${msgs.length !== 1 ? 's' : ''}</span>
          </div>
          ${msgs.map((msg) => `
            <div class="phc-message" style="padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-subtle);">
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
                  ${formatTimestamp(msg.timestamp)}
                </span>
                <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
                  ${timeAgo(msg.timestamp)}
                </span>
              </div>
              <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: pre-wrap; word-break: break-word; line-height: 1.5; margin-top: var(--space-1);">
                ${esc(msg.body || '')}
              </div>
              ${msg.ok === false ? `<div style="font-size: var(--font-size-xxs); color: var(--danger); margin-top: 2px;">Send failed</div>` : ''}
            </div>
          `).join('')}
        </div>
      `;
    });
  }

  const msgCount = filtered.length;

  return `
    <!-- Message Search -->
    <div class="c-card" style="margin-bottom: var(--space-4);">
      <div class="c-card__body" style="padding: var(--space-3);">
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); flex-shrink: 0;">
            ${ICONS.search.html}
          </span>
          <input type="text" id="phc-msg-search" class="c-input" placeholder="Search messages by body or sender..."
                 value="${esc(_state.messageSearch)}"
                 style="font-size: var(--font-size-xs); padding: 4px 8px; flex: 1;">
          <span style="font-size: var(--font-size-xxs); color: var(--text-muted); white-space: nowrap;">
            ${msgCount}/${messages.length}
          </span>
        </div>
      </div>
    </div>

    <!-- Messages List -->
    <div class="c-card" style="display: flex; flex-direction: column;">
      <div class="c-card__header">
        <span style="display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">${ICONS.message.html}</span>
          <span class="c-card__title">Messages</span>
        </span>
        ${msgCount > 0 ? `<span class="c-badge c-badge--default" id="phc-msg-count">${msgCount}</span>` : ''}
      </div>
      <div class="c-card__body" style="padding: 0; flex: 1; max-height: 400px; overflow-y: auto;" id="phc-messages-list">
        ${messagesHTML}
      </div>
    </div>

    <!-- Send Message -->
    <div class="c-card" style="margin-top: var(--space-4);">
      <div class="c-card__body" style="padding: var(--space-4);">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">${ICONS.arrowUp.html}</span>
          Send Message
        </div>
        <form id="phc-send-form">
          <div style="display: flex; flex-direction: column; gap: var(--space-3);">
            <textarea id="phc-msg-body" class="c-input" rows="3"
                      placeholder="Type your message here\u2026"
                      style="resize: vertical; min-height: 60px; width: 100%;"
                      required></textarea>
            <div style="display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;">
              <input id="phc-msg-host" class="c-input" type="text"
                     placeholder="Host (optional)" style="flex: 0 1 220px;">
              <button type="submit" class="c-btn c-btn--primary" id="phc-send-btn"
                      ${_state.sending ? 'disabled' : ''}
                      style="display: flex; align-items: center; gap: var(--space-2);">
                ${_state.sending
                  ? '<span class="c-spinner c-spinner--sm" style="width: 16px; height: 16px;"></span> Sending\u2026'
                  : `<span style="width: 16px; height: 16px; display: flex; align-items: center; justify-content: center;">${ICONS.chevronRight.html}</span> Send`
                }
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  `;
}

function renderContactsTabHTML() {
  const peers = Array.isArray(_state.peers) ? _state.peers : [];
  const trustedCount = peers.length;

  let listHTML;
  if (peers.length === 0) {
    listHTML = `
      <div style="text-align: center; padding: var(--space-6) var(--space-4); color: var(--text-muted);">
        <div style="font-size: var(--font-size-sm);">No contacts yet</div>
        <div style="font-size: var(--font-size-xs); margin-top: var(--space-1);">
          Add a contact by pasting their public key below.
        </div>
      </div>
    `;
  } else {
    listHTML = peers.map((p) => `
      <div class="phc-contact" style="padding: var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); margin-bottom: var(--space-2); display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);">
        <div style="min-width: 0; flex: 1;">
          <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); font-family: var(--font-mono); word-break: break-all;">
            ${esc(p.device_id || 'unknown')}
          </div>
          <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-top: 2px;">
            ${p.truncated_fingerprint ? `<span style="font-size: var(--font-size-xxs); color: var(--text-muted); font-family: var(--font-mono);">${esc(p.truncated_fingerprint)}</span>` : ''}
            <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
              ${p.last_seen ? `Last seen: ${timeAgo(p.last_seen)}` : 'Never seen'}
            </span>
            <span style="font-size: var(--font-size-xxs); padding: 1px 6px; border-radius: var(--radius-sm); background: var(--bg-tertiary); color: var(--text-muted);">
              ${p.trust_status || 'trusted'}
            </span>
            ${p.is_expired ? `<span style="font-size: var(--font-size-xxs); color: var(--danger);">expired</span>` : ''}
          </div>
        </div>
        <button class="c-btn c-btn--sm c-btn--ghost phc-remove-peer-btn" data-device-id="${esc(p.device_id)}"
                style="flex-shrink: 0; color: var(--danger);" title="Remove contact">
          <span style="width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;">${ICONS.trash.html}</span>
        </button>
      </div>
    `).join('');
  }

  return `
    <!-- Add Contact -->
    <div class="c-card" style="margin-bottom: var(--space-4);">
      <div class="c-card__body" style="padding: var(--space-4);">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">${ICONS.plus.html}</span>
          Add Contact
        </div>
        <div style="display: flex; flex-direction: column; gap: var(--space-2);">
          <textarea id="phc-peer-json" class="c-input" rows="4"
                    placeholder="Paste the peer&#39;s public key JSON here... (from their fiona.public.json or exported key)"
                    style="font-family: var(--font-mono); font-size: var(--font-size-xxs); resize: vertical; width: 100%;"></textarea>
          <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
            <button class="c-btn c-btn--primary c-btn--sm" id="phc-peer-add-btn">
              <span style="width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;">${ICONS.plus.html}</span>
              Add Contact
            </button>
            <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
              Or drop a <code>.public.json</code> file
            </span>
            <input type="file" id="phc-peer-file-input" accept=".json" style="display: none;">
            <button class="c-btn c-btn--sm c-btn--ghost" id="phc-peer-file-btn" title="Upload public key file">
              <span style="width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;">${ICONS.upload.html}</span>
              Upload File
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Contacts List -->
    <div class="c-card" style="display: flex; flex-direction: column;">
      <div class="c-card__header">
        <span style="display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">
            ${CONTACTS_ICON}
          </span>
          <span class="c-card__title">Known Peers (${trustedCount})</span>
        </span>
      </div>
      <div class="c-card__body" style="padding: var(--space-3);" id="phc-peers-list">
        ${listHTML}
      </div>
    </div>
  `;
}

function renderTrustTabHTML() {
  const keys = Array.isArray(_state.trustedKeys) ? _state.trustedKeys : [];

  let listHTML;
  if (keys.length === 0) {
    listHTML = `
      <div style="text-align: center; padding: var(--space-6) var(--space-4); color: var(--text-muted);">
        <div style="font-size: var(--font-size-sm);">No trusted keys</div>
        <div style="font-size: var(--font-size-xs); margin-top: var(--space-1);">
          Trusted public keys from your contacts appear here.
        </div>
      </div>
    `;
  } else {
    listHTML = keys.map((k) => `
      <div class="phc-trusted-key" style="padding: var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); margin-bottom: var(--space-2);">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-2);">
          <div style="min-width: 0; flex: 1;">
            <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); font-family: var(--font-mono); word-break: break-all;">
              ${esc(k.device_id || 'unknown')}
            </div>
            <div style="margin-top: var(--space-1); background: var(--bg-tertiary); border-radius: var(--radius-sm); padding: var(--space-2); font-family: var(--font-mono); font-size: var(--font-size-xxs); color: var(--text-secondary); word-break: break-all; line-height: 1.6;">
              ${esc(k.fingerprint)}
            </div>
            <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-1);">
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">Added: ${formatTimestamp(k.added_at)}</span>
              ${k.expires_at ? `<span style="font-size: var(--font-size-xxs); color: var(--text-muted);">Expires: ${formatTimestamp(k.expires_at)}</span>` : ''}
              ${k.is_expired ? `<span style="font-size: var(--font-size-xxs); color: var(--danger); font-weight: var(--font-weight-medium);">EXPIRED</span>` : '<span style="font-size: var(--font-size-xxs); color: var(--success);">Active</span>'}
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: var(--space-1); flex-shrink: 0;">
            <button class="c-btn c-btn--xs c-btn--ghost phc-copy-trust-fp-btn" data-fingerprint="${esc(k.fingerprint)}"
                    title="Copy fingerprint" style="font-size: var(--font-size-xxs);">
              <span style="width: 12px; height: 12px; display: flex; align-items: center; justify-content: center;">${ICONS.copy.html}</span>
            </button>
            <button class="c-btn c-btn--xs c-btn--ghost phc-revoke-trust-btn" data-device-id="${esc(k.device_id)}"
                    title="Revoke trust" style="color: var(--danger); font-size: var(--font-size-xxs);">
              <span style="width: 12px; height: 12px; display: flex; align-items: center; justify-content: center;">${ICONS.trash.html}</span>
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }

  return `
    <!-- Verification Instructions -->
    <div class="c-card" style="margin-bottom: var(--space-4); border-left: 3px solid var(--accent);">
      <div class="c-card__body" style="padding: var(--space-3);">
        <div style="display: flex; align-items: flex-start; gap: var(--space-2);">
          <span style="width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; color: var(--accent); flex-shrink: 0; margin-top: 2px;">${SHIELD_ICON}</span>
          <div>
            <div style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-primary);">Out-of-Band Verification</div>
            <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 2px; line-height: 1.5;">
              To verify a peer's identity, compare their device fingerprint over a secure
              side-channel (phone call, in-person, or another messaging app).
              If the fingerprints match, the connection is secure and end-to-end encrypted.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Trusted Keys List -->
    <div class="c-card" style="display: flex; flex-direction: column;">
      <div class="c-card__header">
        <span style="display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">${ICONS.lock.html}</span>
          <span class="c-card__title">Trusted Keys (${keys.length})</span>
        </span>
      </div>
      <div class="c-card__body" style="padding: var(--space-3);" id="phc-trust-list">
        ${listHTML}
      </div>
    </div>
  `;
}

function renderConfigTabHTML() {
  const config = _state.configData?.config || {};
  const identity = _state.configData?.identity || _state.identity || {};
  const fingerprint = identity.fingerprint || _state.identity?.fingerprint || '';
  const deviceId = identity.device_id || _state.identity?.device_id || '';

  const listenPort = config.listen_port || '';
  const listenHost = config.listen_host || '';
  const peerHost = config.peer_host || '';
  const peerPort = config.peer_port || '';
  const autoStart = config.auto_start || false;
  const logLevel = config.log_level || 'INFO';

  return `
    <!-- Connection Settings -->
    <div class="c-card" style="margin-bottom: var(--space-4);">
      <div class="c-card__body" style="padding: var(--space-4);">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">${ICONS.gear.html}</span>
          Connection Settings
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3);">
          <div>
            <label style="font-size: var(--font-size-xxs); color: var(--text-muted); display: block; margin-bottom: 2px;">Listen Host</label>
            <input type="text" id="phc-cfg-listen-host" class="c-input" value="${esc(listenHost)}"
                   style="font-size: var(--font-size-xs); padding: 4px 8px; width: 100%;">
          </div>
          <div>
            <label style="font-size: var(--font-size-xxs); color: var(--text-muted); display: block; margin-bottom: 2px;">Listen Port</label>
            <input type="number" id="phc-cfg-listen-port" class="c-input" value="${esc(String(listenPort))}"
                   min="1" max="65535"
                   style="font-size: var(--font-size-xs); padding: 4px 8px; width: 100%;">
          </div>
          <div>
            <label style="font-size: var(--font-size-xxs); color: var(--text-muted); display: block; margin-bottom: 2px;">Peer Host</label>
            <input type="text" id="phc-cfg-peer-host" class="c-input" value="${esc(peerHost)}"
                   style="font-size: var(--font-size-xs); padding: 4px 8px; width: 100%;">
          </div>
          <div>
            <label style="font-size: var(--font-size-xxs); color: var(--text-muted); display: block; margin-bottom: 2px;">Peer Port</label>
            <input type="number" id="phc-cfg-peer-port" class="c-input" value="${esc(String(peerPort))}"
                   min="1" max="65535"
                   style="font-size: var(--font-size-xs); padding: 4px 8px; width: 100%;">
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-3); flex-wrap: wrap;">
          <label style="display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-muted); cursor: pointer;">
            <input type="checkbox" id="phc-cfg-auto-start" ${autoStart ? 'checked' : ''}
                   style="accent-color: var(--accent); cursor: pointer;">
            Auto-start receiver on boot
          </label>
          <div>
            <label style="font-size: var(--font-size-xxs); color: var(--text-muted); display: block; margin-bottom: 2px;">Log Level</label>
            <select id="phc-cfg-log-level" class="c-input" style="font-size: var(--font-size-xs); padding: 4px 8px;">
              <option value="DEBUG" ${logLevel === 'DEBUG' ? 'selected' : ''}>DEBUG</option>
              <option value="INFO" ${logLevel === 'INFO' ? 'selected' : ''}>INFO</option>
              <option value="WARNING" ${logLevel === 'WARNING' ? 'selected' : ''}>WARNING</option>
              <option value="ERROR" ${logLevel === 'ERROR' ? 'selected' : ''}>ERROR</option>
            </select>
          </div>
        </div>

        <div style="margin-top: var(--space-3);">
          <button class="c-btn c-btn--primary c-btn--sm" id="phc-cfg-save-btn">
            <span style="width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;">${ICONS.check.html}</span>
            Save Settings
          </button>
          <span id="phc-cfg-save-msg" style="font-size: var(--font-size-xxs); color: var(--success); margin-left: var(--space-2); display: none;">Saved!</span>
        </div>
      </div>
    </div>

    <!-- Key Management -->
    <div class="c-card" style="margin-bottom: var(--space-4);">
      <div class="c-card__body" style="padding: var(--space-4);">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-3); display: flex; align-items: center; gap: var(--space-2);">
          <span style="width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; color: var(--accent);">${ICONS.lock.html}</span>
          Key Management
        </div>
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-bottom: var(--space-2);">
          Device ID: <span style="font-family: var(--font-mono);">${esc(deviceId)}</span>
        </div>
        ${fingerprint ? `
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-bottom: var(--space-2);">
          Fingerprint:
        </div>
        <pre class="code-block" style="background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-2); font-family: var(--font-mono); font-size: var(--font-size-xxs); color: var(--text-primary); overflow-x: auto; white-space: pre-wrap; word-break: break-all; line-height: 1.6; margin: 0 0 var(--space-2) 0;">${esc(fingerprint)}</pre>
        ` : ''}
        <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
          <button class="c-btn c-btn--sm c-btn--ghost" id="phc-cfg-copy-pubkey" title="Copy public key JSON">
            <span style="width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;">${ICONS.copy.html}</span>
            Copy Public Key
          </button>
          <button class="c-btn c-btn--sm c-btn--danger" id="phc-cfg-regenerate-keys"
                  style="color: var(--danger); border-color: var(--danger);">
            <span style="width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;">${ICONS.refresh.html}</span>
            Regenerate Keys
          </button>
        </div>
      </div>
    </div>
  `;
}

/* ─── Render: Full Page ───────────────────────────────────────────────── */

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '180px' })}
        ${skeletonText({ width: '240px' })}
      </div>
      ${skeletonCard({ height: '60px' })}
      <div style="margin-top: var(--space-3);">
        ${skeletonCard({ height: '400px' })}
      </div>
    </div>
  `;
}

function renderError(container) {
  container.innerHTML = html`
    <div class="empty-state" style="margin-top: 10vh;">
      <div class="empty-state__icon" style="color: var(--danger);">
        ${ICONS.error}
      </div>
      <div class="empty-state__title">Connection Error</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to reach the PhiConnect backend. The service may not be running.')}
      </div>
      <button class="c-btn c-btn--primary" id="phc-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#phc-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

async function renderPage(container) {
  if (_state.destroyed) return;
  _state.container = container;

  if (_state.loading) {
    renderSkeletons(container);
    return;
  }

  if (_state.error) {
    renderError(container);
    return;
  }

  const statusReady = _state.status?.ready === true;
  const port = _state.status?.port;
  const configDir = _state.status?.config_dir;
  const fingerprint = _state.identity?.fingerprint;
  const deviceId = _state.identity?.device_id;
  const peersCount = Array.isArray(_state.peers) ? _state.peers.length : 0;
  const messages = Array.isArray(_state.messages) ? _state.messages : [];

  // Render active tab content
  let tabContent = '';
  switch (_state.activeTab) {
    case 'messages':
      tabContent = renderMessagesTabHTML();
      break;
    case 'contacts':
      tabContent = renderContactsTabHTML();
      break;
    case 'trust':
      tabContent = renderTrustTabHTML();
      break;
    case 'config':
      tabContent = renderConfigTabHTML();
      break;
  }

  const data = {
    refreshIcon: ICONS.refresh.html,
    messageIcon: ICONS.message.html,
    contactsIcon: CONTACTS_ICON,
    trustIcon: SHIELD_ICON,
    configIcon: ICONS.gear.html,
    copyIcon: ICONS.copy.html,
    autoRefresh: _state.autoRefresh,
    statusReady,
    hasPort: port != null,
    port: esc(String(port ?? '')),
    hasConfigDir: !!configDir,
    configDir: esc(configDir || ''),
    hasDeviceId: !!deviceId,
    deviceId: esc(deviceId || ''),
    hasFingerprint: !!fingerprint,
    fingerprint: esc(fingerprint || ''),
    copyFeedback: _state.copyFeedback,
    hasMessages: messages.length > 0,
    messagesCount: messages.length,
    hasPeers: peersCount > 0,
    peersCount,
    tabContent,
  };

  container.innerHTML = await loadTemplate('phiconnect', data);
  updateTabStyles(container);
  mountHandlers(container);
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // ── Top-level controls ──

  // Tab switching
  container.querySelectorAll('.phc-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');
      if (tab && tab !== _state.activeTab) {
        switchTab(container, tab);
      }
    });
  });

  // Refresh button
  container.querySelector('#phc-refresh-btn')?.addEventListener('click', () => {
    loadData();
  });

  // Auto-refresh toggle
  const autoToggle = container.querySelector('#phc-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', () => {
      _state.autoRefresh = autoToggle.checked;
      persistAutoRefresh(_state.autoRefresh);
      if (_state.autoRefresh) startPolling();
      else stopPolling();
    });
  }

  // Copy fingerprint button (in status bar)
  container.querySelector('#phc-copy-fp-btn')?.addEventListener('click', async () => {
    const fp = _state.identity?.fingerprint;
    if (!fp) return;
    try {
      await navigator.clipboard.writeText(fp);
      _state.copyFeedback = true;
      const btn = container.querySelector('#phc-copy-fp-btn');
      if (btn) {
        btn.innerHTML = `<span style="width: 12px; height: 12px; display: flex; align-items: center; justify-content: center;">${ICONS.check.html}</span> Copied!`;
      }
      setTimeout(() => {
        if (_state.destroyed) return;
        _state.copyFeedback = false;
        const btn2 = container.querySelector('#phc-copy-fp-btn');
        if (btn2) {
          btn2.innerHTML = `<span style="width: 12px; height: 12px; display: flex; align-items: center; justify-content: center;">${ICONS.copy.html}</span> Copy`;
        }
      }, 2000);
    } catch (err) {
      console.warn('[phiconnect] Copy failed:', err);
    }
  });

  // Mount tab-specific handlers
  mountActiveTabHandlers(container);
}

function mountActiveTabHandlers(container) {
  switch (_state.activeTab) {
    case 'messages':
      mountMessagesHandlers(container);
      break;
    case 'contacts':
      mountContactsHandlers(container);
      break;
    case 'trust':
      mountTrustHandlers(container);
      break;
    case 'config':
      mountConfigHandlers(container);
      break;
  }
}

/* ── Messages Tab Handlers ──────────────────────────────────────────────── */

function mountMessagesHandlers(container) {
  // Send message form
  const sendForm = container.querySelector('#phc-send-form');
  if (sendForm) {
    sendForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (_state.sending) return;

      const bodyEl = container.querySelector('#phc-msg-body');
      const hostEl = container.querySelector('#phc-msg-host');
      if (!bodyEl) return;

      const body = bodyEl.value.trim();
      if (!body) return;

      const host = hostEl ? hostEl.value.trim() : '';

      _state.sending = true;
      updateSendButtonSending(container);

      try {
        const api = getApi();
        if (!api) throw new Error('API not available');

        const payload = { body };
        if (host) {
          const parts = host.split(':');
          payload.host = parts[0];
          if (parts[1]) payload.port = parseInt(parts[1], 10);
        }

        const result = await api.post('/api/v1/phiconnect/send', payload);
        if (!result || !result.ok) {
          throw new Error(result?.data?.error || result?.data?.message || 'Send failed');
        }

        bodyEl.value = '';
        if (hostEl) hostEl.value = '';

        toast.showToast('success', 'Message Sent', 'Your message was sent successfully.');

        await refreshMessagesOnly();
      } catch (err) {
        console.error('[phiconnect] Send failed:', err);
        toast.showToast('error', 'Send Failed', err.message || 'Could not send message.');
      } finally {
        _state.sending = false;
        updateSendButtonIdle(container);
      }
    });
  }

  // Message search
  const searchInput = container.querySelector('#phc-msg-search');
  if (searchInput) {
    // Debounced search
    let searchTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        _state.messageSearch = searchInput.value;
        refreshActiveTab(container);
      }, 250);
    });
  }
}

function updateSendButtonSending(container) {
  const btn = container.querySelector('#phc-send-btn');
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = html`
    <span class="c-spinner c-spinner--sm" style="width: 16px; height: 16px;"></span>
    Sending\u2026
  `;
}

function updateSendButtonIdle(container) {
  const btn = container.querySelector('#phc-send-btn');
  if (!btn) return;
  btn.disabled = false;
  btn.innerHTML = html`
    <span style="width: 16px; height: 16px; display: flex; align-items: center; justify-content: center;">
      ${ICONS.chevronRight}
    </span>
    Send
  `;
}

/* ── Contacts Tab Handlers ──────────────────────────────────────────────── */

function mountContactsHandlers(container) {
  // Add peer from textarea
  const addBtn = container.querySelector('#phc-peer-add-btn');
  const textarea = container.querySelector('#phc-peer-json');
  if (addBtn && textarea) {
    addBtn.addEventListener('click', async () => {
      const jsonStr = textarea.value.trim();
      if (!jsonStr) {
        toast.showToast('warning', 'Input Required', 'Paste the peer\'s public key JSON first.');
        return;
      }

      let bundle;
      try {
        bundle = JSON.parse(jsonStr);
      } catch {
        toast.showToast('error', 'Invalid JSON', 'Could not parse the public key JSON.');
        return;
      }

      try {
        const api = getApi();
        if (!api) throw new Error('API not available');

        const result = await api.post('/api/v1/phiconnect/peers/add', {
          public_bundle: bundle,
        });

        if (!result || !result.ok) {
          throw new Error(result?.data?.error || 'Failed to add peer');
        }

        toast.showToast('success', 'Contact Added', `Peer ${result.data.device_id || ''} has been added.`);
        textarea.value = '';
        // Refresh data
        await fetchPeersAndTrust();
        refreshActiveTab(container);
      } catch (err) {
        console.error('[phiconnect] Add peer failed:', err);
        toast.showToast('error', 'Add Failed', err.message || 'Could not add contact.');
      }
    });
  }

  // Upload file button
  const fileBtn = container.querySelector('#phc-peer-file-btn');
  const fileInput = container.querySelector('#phc-peer-file-input');
  if (fileBtn && fileInput) {
    fileBtn.addEventListener('click', () => {
      fileInput.click();
    });
    fileInput.addEventListener('change', () => {
      const file = fileInput.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result;
        if (text && textarea) {
          textarea.value = text;
        }
        fileInput.value = '';
        // Trigger add
        addBtn?.click();
      };
      reader.readAsText(file);
    });
  }

  // Remove peer buttons
  container.querySelectorAll('.phc-remove-peer-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const deviceId = btn.getAttribute('data-device-id');
      if (!deviceId) return;
      showConfirmModal(
        'Remove Contact',
        `Remove contact "${deviceId}"? This will revoke trust for this peer.`,
        async () => {
          try {
            const api = getApi();
            if (!api) throw new Error('API not available');
            const result = await api.delete(`/api/v1/phiconnect/peers/remove?device_id=${encodeURIComponent(deviceId)}`);
            if (!result || !result.ok) {
              throw new Error(result?.data?.error || 'Failed to remove peer');
            }
            toast.showToast('success', 'Contact Removed', deviceId);
            await fetchPeersAndTrust();
            refreshActiveTab(container);
          } catch (err) {
            console.error('[phiconnect] Remove peer failed:', err);
            toast.showToast('error', 'Remove Failed', err.message);
          }
        }
      );
    });
  });
}

/* ── Trust Tab Handlers ─────────────────────────────────────────────────── */

function mountTrustHandlers(container) {
  // Copy fingerprint buttons
  container.querySelectorAll('.phc-copy-trust-fp-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const fp = btn.getAttribute('data-fingerprint');
      if (!fp) return;
      try {
        await navigator.clipboard.writeText(fp);
        toast.showToast('success', 'Copied', 'Fingerprint copied to clipboard.');
      } catch (err) {
        console.warn('[phiconnect] Copy failed:', err);
      }
    });
  });

  // Revoke trust buttons
  container.querySelectorAll('.phc-revoke-trust-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const deviceId = btn.getAttribute('data-device-id');
      if (!deviceId) return;
      showConfirmModal(
        'Revoke Trust',
        `Are you sure you want to revoke trust for "${deviceId}"? You will no longer be able to communicate with this peer until you re-add their key.`,
        async () => {
          try {
            const api = getApi();
            if (!api) throw new Error('API not available');
            const result = await api.post('/api/v1/phiconnect/trust/revoke', { device_id: deviceId });
            if (!result || !result.ok) {
              throw new Error(result?.data?.error || 'Failed to revoke trust');
            }
            toast.showToast('success', 'Trust Revoked', `Trust revoked for ${deviceId}`);
            await fetchPeersAndTrust();
            refreshActiveTab(container);
          } catch (err) {
            console.error('[phiconnect] Revoke trust failed:', err);
            toast.showToast('error', 'Revoke Failed', err.message);
          }
        }
      );
    });
  });
}

/* ── Config Tab Handlers ────────────────────────────────────────────────── */

function mountConfigHandlers(container) {
  // Save settings
  const saveBtn = container.querySelector('#phc-cfg-save-btn');
  const saveMsg = container.querySelector('#phc-cfg-save-msg');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const listenHost = container.querySelector('#phc-cfg-listen-host')?.value?.trim() || '0.0.0.0';
      const listenPort = parseInt(container.querySelector('#phc-cfg-listen-port')?.value || '5000', 10);
      const peerHost = container.querySelector('#phc-cfg-peer-host')?.value?.trim() || '127.0.0.1';
      const peerPort = parseInt(container.querySelector('#phc-cfg-peer-port')?.value || '5000', 10);
      const autoStart = container.querySelector('#phc-cfg-auto-start')?.checked || false;
      const logLevel = container.querySelector('#phc-cfg-log-level')?.value || 'INFO';

      // Validate
      if (listenPort < 1 || listenPort > 65535 || peerPort < 1 || peerPort > 65535) {
        toast.showToast('error', 'Invalid Port', 'Port must be between 1 and 65535.');
        return;
      }

      try {
        const api = getApi();
        if (!api) throw new Error('API not available');

        const result = await api.post('/api/v1/phiconnect/config', {
          listen_host: listenHost,
          listen_port: listenPort,
          peer_host: peerHost,
          peer_port: peerPort,
          auto_start: autoStart,
          log_level: logLevel,
        });

        if (!result || !result.ok) {
          throw new Error(result?.data?.error || 'Failed to save config');
        }

        if (saveMsg) {
          saveMsg.style.display = 'inline';
          setTimeout(() => { if (saveMsg) saveMsg.style.display = 'none'; }, 3000);
        }
        toast.showToast('success', 'Settings Saved', 'Configuration updated.');
        _state.configData = result.data;
      } catch (err) {
        console.error('[phiconnect] Save config failed:', err);
        toast.showToast('error', 'Save Failed', err.message);
      }
    });
  }

  // Copy public key
  const copyPubKeyBtn = container.querySelector('#phc-cfg-copy-pubkey');
  if (copyPubKeyBtn) {
    copyPubKeyBtn.addEventListener('click', async () => {
      const bundle = _state.identity?.public_bundle || _state.configData?.identity?.public_bundle;
      if (!bundle) {
        toast.showToast('warning', 'No Key', 'No public key available yet.');
        return;
      }
      try {
        await navigator.clipboard.writeText(JSON.stringify(bundle, null, 2));
        toast.showToast('success', 'Copied', 'Public key JSON copied to clipboard.');
      } catch (err) {
        console.warn('[phiconnect] Copy public key failed:', err);
      }
    });
  }

  // Regenerate keys
  const regenBtn = container.querySelector('#phc-cfg-regenerate-keys');
  if (regenBtn) {
    regenBtn.addEventListener('click', () => {
      showConfirmModal(
        'Regenerate Keys',
        'WARNING: This will invalidate existing trust relationships and make previously encrypted messages undecryptable. Are you sure you want to continue?',
        async () => {
          try {
            const api = getApi();
            if (!api) throw new Error('API not available');
            const result = await api.post('/api/v1/phiconnect/keys/regenerate');
            if (!result || !result.ok) {
              throw new Error(result?.data?.error || 'Failed to regenerate keys');
            }
            toast.showToast('success', 'Keys Regenerated', 'New identity keys have been generated. Previous trust relationships are invalidated.');
            _state.identity = result.data;
            _state.configData = null;
            await loadData();
          } catch (err) {
            console.error('[phiconnect] Regenerate keys failed:', err);
            toast.showToast('error', 'Regenerate Failed', err.message);
          }
        }
      );
    });
  }
}

/* ── Modal: Confirm Dialog ──────────────────────────────────────────────── */

function showConfirmModal(title, message, onConfirm) {
  showModal(`
    <div style="margin-bottom: var(--space-4);">
      <h3 style="margin: 0 0 var(--space-2); font-size: var(--font-size-md);">${esc(title)}</h3>
      <p style="margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5;">${esc(message)}</p>
    </div>
    <div style="display: flex; justify-content: flex-end; gap: var(--space-2);">
      <button class="c-btn c-btn--sm" id="phc-modal-cancel">Cancel</button>
      <button class="c-btn c-btn--sm c-btn--danger" id="phc-modal-confirm" style="color: var(--danger); border-color: var(--danger);">Confirm</button>
    </div>
  `);

  document.getElementById('phc-modal-cancel')?.addEventListener('click', hideModal);
  document.getElementById('phc-modal-confirm')?.addEventListener('click', () => {
    hideModal();
    if (onConfirm) onConfirm();
  });
}

/* ── Tab Switching ──────────────────────────────────────────────────────── */

function switchTab(container, tab) {
  _state.activeTab = tab;

  // If switching to messages, fetch fresh messages
  if (tab === 'messages') {
    refreshMessagesOnly();
  }

  // For contacts/trust/config, re-fetch data if stale
  if (tab === 'contacts' || tab === 'trust') {
    fetchPeersAndTrust().then(() => {
      refreshActiveTab(container);
    });
    return;
  }

  if (tab === 'config') {
    fetchConfig().then(() => {
      refreshActiveTab(container);
    });
    return;
  }

  refreshActiveTab(container);
}

function refreshActiveTab(container) {
  const tabContentEl = container.querySelector('#phc-tab-content');
  if (!tabContentEl) return;

  switch (_state.activeTab) {
    case 'messages':
      tabContentEl.innerHTML = renderMessagesTabHTML();
      break;
    case 'contacts':
      tabContentEl.innerHTML = renderContactsTabHTML();
      break;
    case 'trust':
      tabContentEl.innerHTML = renderTrustTabHTML();
      break;
    case 'config':
      tabContentEl.innerHTML = renderConfigTabHTML();
      break;
  }

  updateTabStyles(container);
  mountActiveTabHandlers(container);
}

/* ── Messages List Incremental Update ────────────────────────────────────── */

function updateMessagesList(container) {
  // Only update if messages tab is active and no search is active
  if (_state.activeTab !== 'messages') return;

  const listEl = container.querySelector('#phc-messages-list');
  const badgeEl = container.querySelector('#phc-msg-count');
  const messages = Array.isArray(_state.messages) ? _state.messages : [];
  const searchTerm = _state.messageSearch.toLowerCase().trim();

  let filtered = messages;
  if (searchTerm) {
    filtered = filtered.filter((m) =>
      (m.body || '').toLowerCase().includes(searchTerm) ||
      (m.sender || '').toLowerCase().includes(searchTerm)
    );
  }

  if (!listEl) return;

  const groupKeys = [...new Set(filtered.map((m) => m.sender || 'unknown'))];

  if (filtered.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-muted);">
        <div style="width: 40px; height: 40px; margin: 0 auto var(--space-3); display: flex; align-items: center; justify-content: center; color: var(--text-muted); opacity: 0.4;">
          ${ICONS.message.html}
        </div>
        <div style="font-size: var(--font-size-sm);">${searchTerm ? 'No messages match your search.' : 'No recent messages'}</div>
        <div style="font-size: var(--font-size-xs); margin-top: var(--space-1);">
          Messages from the last ${MESSAGE_POLL_SECONDS / 60} minutes will appear here.
        </div>
      </div>
    `;
    if (badgeEl) badgeEl.textContent = '0';
    return;
  }

  let htmlStr = '';
  groupKeys.forEach((sender) => {
    const msgs = filtered.filter((m) => (m.sender || 'unknown') === sender);
    htmlStr += `
      <div class="phc-message-group" style="margin-bottom: var(--space-3);">
        <div style="padding: var(--space-1) var(--space-3); font-size: var(--font-size-xxs); color: var(--text-muted); background: var(--bg-tertiary); border-radius: var(--radius-sm) var(--radius-sm) 0 0; font-family: var(--font-mono); display: flex; align-items: center; justify-content: space-between;">
          <span>${esc(sender)}</span>
          <span>${msgs.length} msg${msgs.length !== 1 ? 's' : ''}</span>
        </div>
        ${msgs.map((msg) => `
          <div class="phc-message" style="padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-subtle);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">${formatTimestamp(msg.timestamp)}</span>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">${timeAgo(msg.timestamp)}</span>
            </div>
            <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: pre-wrap; word-break: break-word; line-height: 1.5; margin-top: var(--space-1);">
              ${esc(msg.body || '')}
            </div>
            ${msg.ok === false ? `<div style="font-size: var(--font-size-xxs); color: var(--danger); margin-top: 2px;">Send failed</div>` : ''}
          </div>
        `).join('')}
      </div>
    `;
  });

  listEl.innerHTML = htmlStr;
  if (badgeEl) badgeEl.textContent = String(filtered.length);
}

/* ── Polling ────────────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  _state.pollTimer = setInterval(silentPoll, POLL_INTERVAL);
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
}

async function silentPoll() {
  if (_state.destroyed || !_state.autoRefresh) return;
  await refreshMessagesOnly();
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function refreshMessagesOnly() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const res = await api.get(`/api/v1/phiconnect/messages?seconds=${MESSAGE_POLL_SECONDS}`);
    if (_state.destroyed) return;

    if (res && res.ok) {
      _state.messages = Array.isArray(res.data) ? res.data : [];
      if (!_state.destroyed && _state.container && !_state.loading) {
        updateMessagesList(_state.container);
      }
    }
  } catch (err) {
    // Silently fail during poll
  }
}

async function fetchPeersAndTrust() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const [peersRes, trustRes] = await Promise.allSettled([
      api.get('/api/v1/phiconnect/peers'),
      api.get('/api/v1/phiconnect/trust/list'),
    ]);

    if (_state.destroyed) return;

    if (peersRes.status === 'fulfilled' && peersRes.value?.ok) {
      _state.peers = Array.isArray(peersRes.value.data) ? peersRes.value.data : [];
    }
    if (trustRes.status === 'fulfilled' && trustRes.value?.ok) {
      _state.trustedKeys = Array.isArray(trustRes.value.data) ? trustRes.value.data : [];
    }
  } catch (err) {
    // Silently fail
  }
}

async function fetchConfig() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const res = await api.get('/api/v1/phiconnect/config');
    if (_state.destroyed) return;
    if (res && res.ok) {
      _state.configData = res.data;
    }
  } catch (err) {
    // Silently fail
  }
}

/**
 * Full data fetch — status, identity, messages, peers, trust, config.
 * Used on initial load and manual refresh.
 */
async function fetchData(silent) {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    if (!silent) {
      _state.error = true;
      _state.errorMessage = 'API client not available.';
      _state.loading = false;
      if (_state.container) await renderPage(_state.container);
    }
    return;
  }

  try {
    const [statusRes, identityRes, messagesRes, peersRes, trustRes, configRes] = await Promise.allSettled([
      api.get('/api/v1/phiconnect/status'),
      api.get('/api/v1/phiconnect/identity'),
      api.get(`/api/v1/phiconnect/messages?seconds=${MESSAGE_POLL_SECONDS}`),
      api.get('/api/v1/phiconnect/peers'),
      api.get('/api/v1/phiconnect/trust/list'),
      api.get('/api/v1/phiconnect/config'),
    ]);

    if (_state.destroyed) return;

    let changed = false;

    if (statusRes.status === 'fulfilled') {
      const data = statusRes.value?.data || {};
      _state.status = data;
      changed = true;
    } else {
      if (!silent) {
        _state.error = true;
        _state.errorMessage = statusRes.reason?.message || 'Failed to fetch PhiConnect status.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
    }

    if (identityRes.status === 'fulfilled') {
      const data = identityRes.value?.data || {};
      _state.identity = data;
      changed = true;
    } else {
      if (!silent) {
        _state.error = true;
        _state.errorMessage = identityRes.reason?.message || 'Failed to fetch PhiConnect identity.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
    }

    if (messagesRes.status === 'fulfilled') {
      const data = messagesRes.value?.data;
      _state.messages = Array.isArray(data) ? data : [];
      changed = true;
    } else {
      if (!silent) {
        _state.error = true;
        _state.errorMessage = messagesRes.reason?.message || 'Failed to fetch messages.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
    }

    // Non-critical fetches — don't error the whole page
    if (peersRes.status === 'fulfilled' && peersRes.value?.ok) {
      _state.peers = Array.isArray(peersRes.value.data) ? peersRes.value.data : [];
    }
    if (trustRes.status === 'fulfilled' && trustRes.value?.ok) {
      _state.trustedKeys = Array.isArray(trustRes.value.data) ? trustRes.value.data : [];
    }
    if (configRes.status === 'fulfilled' && configRes.value?.ok) {
      _state.configData = configRes.value.data;
    }

    if (changed) {
      _state.error = false;
      _state.loading = false;
      if (!_state.destroyed && _state.container) {
        await renderPage(_state.container);
      }
    }
  } catch (err) {
    if (!silent) {
      console.error('[phiconnect] Failed to load data:', err);
      _state.error = true;
      _state.errorMessage = err.message || 'Unexpected error fetching PhiConnect data.';
      _state.loading = false;
      if (!_state.destroyed && _state.container) {
        await renderPage(_state.container);
      }
    }
  }
}

async function loadData() {
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';

  if (_state.container) renderSkeletons(_state.container);

  await fetchData(false);

  if (_state.autoRefresh && !_state.destroyed) {
    startPolling();
  }
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;
  _state.copyFeedback = false;
  _state.autoRefresh = loadAutoRefreshPreference();
  _state.activeTab = 'messages';
  _state.messageSearch = '';
  _state.peers = [];
  _state.trustedKeys = [];
  _state.configData = null;

  renderSkeletons(container);
  loadData();
}

export async function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container) {
    await renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  stopPolling();
  _state.container = null;
  _state.status = null;
  _state.identity = null;
  _state.messages = [];
  _state.peers = [];
  _state.trustedKeys = [];
  _state.configData = null;
  _state.copyFeedback = false;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="phiconnect-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#phiconnect-root') || container;
      render(root);
    },
    destroy,
  };
}
