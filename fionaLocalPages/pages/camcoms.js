/* ==========================================================================
   camcoms.js — CamComs Management Page
   ==========================================================================
   Displays service status, identity fingerprint, configuration editor,
   audit log viewer, service controls, trust management, and key management.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 10000;
const STORAGE_KEY = 'fiona_camcoms_auto_refresh';
const TAB_STORAGE_KEY = 'fiona_camcoms_active_tab';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  status: null,           // { ready, error, config_exists, ... }
  identity: null,         // { fingerprint, error }
  autoRefresh: false,
  pollTimer: null,
  copyFeedback: false,

  // Tab state
  activeTab: 'config',

  // Configuration
  config: null,
  configLoading: false,
  configLoadError: '',

  // Audit Log
  logs: [],
  logsLoading: false,
  logsError: '',

  // Trust Management
  trustedSenders: [],
  trustLoading: false,
  trustError: '',

  // Pairing
  pairingStatus: null,
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function esc(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function persistAutoRefresh(value) {
  try {
    if (value) {
      localStorage.setItem(STORAGE_KEY, '1');
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch { /* ignore */ }
}

function loadAutoRefreshPreference() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function persistActiveTab(tabId) {
  try {
    localStorage.setItem(TAB_STORAGE_KEY, tabId);
  } catch { /* ignore */ }
}

function loadActiveTabPreference() {
  try {
    return localStorage.getItem(TAB_STORAGE_KEY) || 'config';
  } catch {
    return 'config';
  }
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts * 1000);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return String(ts);
  }
}

function getEventTypeColor(type) {
  if (!type) return 'var(--text-muted)';
  const t = type.toLowerCase();
  if (t.includes('error') || t.includes('fail')) return 'var(--danger)';
  if (t.includes('warn')) return 'var(--warning)';
  if (t.includes('pair') || t.includes('trust')) return 'var(--accent)';
  if (t.includes('start') || t.includes('stop') || t.includes('restart')) return 'var(--info, #3b82f6)';
  return 'var(--text-muted)';
}

function getEventSummary(event) {
  // Build a human-readable summary from the event dict
  const type = event.event || event.type || event.event_type || 'unknown';
  const parts = [type];
  if (event.device_id) parts.push(`device=${event.device_id}`);
  if (event.sender) parts.push(`sender=${event.sender}`);
  if (event.recipient) parts.push(`recipient=${event.recipient}`);
  if (event.message_type) parts.push(`type=${event.message_type}`);
  if (event.action) parts.push(`action=${event.action}`);
  if (event.detail || event.message) {
    parts.push(`— ${(event.detail || event.message).slice(0, 80)}`);
  }
  return parts.join(' ');
}

/* ── Dynamic Table Renderers ─────────────────────────────────────────────── */

function renderLogsTable(container) {
  const tbody = container.querySelector('#camcoms-logs-tbody');
  const empty = container.querySelector('#camcoms-logs-empty');
  const msg = container.querySelector('#camcoms-logs-message');
  if (!tbody) return;

  const entries = (_state.logs || []).map((event) => {
    const ts = event.timestamp || 0;
    const eventType = event.event || event.type || event.event_type || 'event';
    return {
      formattedTime: formatTimestamp(ts),
      eventType: esc(eventType),
      typeColor: getEventTypeColor(eventType),
      summary: esc(getEventSummary(event)),
    };
  });

  if (entries.length === 0) {
    tbody.innerHTML = '';
    if (empty) { empty.style.display = 'flex'; }
    if (msg) { msg.textContent = _state.logsError || 'No audit log entries found.'; }
    return;
  }

  if (empty) empty.style.display = 'none';

  tbody.innerHTML = entries.map((e) => `
    <tr style="border-bottom: 1px solid var(--border-light, var(--border));">
      <td style="padding: var(--space-2) var(--space-1); white-space: nowrap; font-family: var(--font-mono, monospace); color: var(--text-muted);">${e.formattedTime}</td>
      <td style="padding: var(--space-2) var(--space-1);">
        <span style="display: inline-block; padding: 1px 6px; border-radius: var(--radius-sm, 3px);
                     background: ${e.typeColor}18; color: ${e.typeColor}; font-size: var(--font-size-xxs, 10px);
                     font-weight: var(--font-weight-medium); text-transform: uppercase;">
          ${e.eventType}
        </span>
      </td>
      <td style="padding: var(--space-2) var(--space-1); color: var(--text-primary); word-break: break-word;">${e.summary}</td>
    </tr>
  `).join('');
}

function renderTrustTable(container) {
  const tbody = container.querySelector('#camcoms-trust-tbody');
  const empty = container.querySelector('#camcoms-trust-empty');
  const msg = container.querySelector('#camcoms-trust-message');
  if (!tbody) return;

  const now = Math.floor(Date.now() / 1000);
  const senders = (_state.trustedSenders || []).map((s) => {
    const bundle = s.bundle || {};
    const expiresAt = s.expires_at;
    return {
      deviceId: esc(bundle.device_id || 'unknown'),
      addedTime: formatTimestamp(s.added_at),
      expiresTime: expiresAt ? formatTimestamp(expiresAt) : 'Never',
      isExpired: expiresAt ? now > expiresAt : false,
    };
  });

  if (senders.length === 0) {
    tbody.innerHTML = '';
    if (empty) { empty.style.display = 'flex'; }
    if (msg) { msg.textContent = _state.trustError || 'No trusted senders configured.'; }
    return;
  }

  if (empty) empty.style.display = 'none';

  tbody.innerHTML = senders.map((s) => `
    <tr style="border-bottom: 1px solid var(--border-light, var(--border));">
      <td style="padding: var(--space-2) var(--space-1); font-family: var(--font-mono, monospace); color: var(--text-primary);">${s.deviceId}</td>
      <td style="padding: var(--space-2) var(--space-1); color: var(--text-muted); white-space: nowrap;">${s.addedTime}</td>
      <td style="padding: var(--space-2) var(--space-1); color: ${s.isExpired ? 'var(--danger)' : 'var(--text-muted)'}; white-space: nowrap;">
        ${s.expiresTime}
      </td>
      <td style="padding: var(--space-2) var(--space-1);">
        <button class="c-btn c-btn--sm c-btn--ghost c-btn--danger" data-trust-remove="${s.deviceId}" title="Remove trusted sender">
          <span class="c-btn__icon">${ICONS.trash}</span>
        </button>
      </td>
    </tr>
  `).join('');
}


/* ── Tab System ─────────────────────────────────────────────────────────── */

function switchTab(tabId) {
  if (_state.destroyed) return;
  _state.activeTab = tabId;
  persistActiveTab(tabId);

  // Update tab button active states
  const container = _state.container;
  if (!container) return;

  container.querySelectorAll('[data-camcoms-tab]').forEach((btn) => {
    btn.classList.toggle('c-tab--active', btn.dataset.camcomsTab === tabId);
  });

  // Show/hide tab content
  ['config', 'logs', 'service', 'trust', 'keys'].forEach((id) => {
    const el = container.querySelector(`#camcoms-tab-${id}`);
    if (el) {
      el.style.display = id === tabId ? 'block' : 'none';
    }
  });

  // Lazy-load data when tab becomes active
  if (tabId === 'logs' && !_state.logsLoading && _state.logs.length === 0) {
    fetchLogs();
  }
  if (tabId === 'trust' && !_state.trustLoading && _state.trustedSenders.length === 0) {
    fetchTrustedSenders();
  }
  if (tabId === 'config' && !_state.configLoading && _state.config === null) {
    fetchConfig();
  }
}

/* ── Render ─────────────────────────────────────────────────────────────── */

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

  const activeTab = _state.activeTab;

  // Config data
  const configData = _state.config || {};
  const configAvailable = !!_state.config && !_state.configLoadError;

  const data = {
    // Existing icons
    autoRefresh: _state.autoRefresh,
    refreshIcon: ICONS.refresh.html,
    eyeIcon: ICONS.eye.html,
    lockIcon: ICONS.lock.html,
    checkCircleIcon: ICONS['check-circle'].html,
    errorIcon: ICONS.error.html,
    copyIcon: ICONS.copy.html,
    checkIcon: ICONS.check.html,
    warningIcon: ICONS.warning.html,
    helpIcon: ICONS.help.html,

    // New icons (using existing icon names from _icons.js)
    settingsIcon: ICONS.gear.html,
    listIcon: ICONS.clock.html,
    playIcon: ICONS.play.html,
    closeIcon: ICONS.close.html,
    shieldIcon: ICONS.lock.html,
    plusIcon: ICONS.plus.html,
    trashIcon: ICONS.trash.html,
    keyIcon: ICONS.lock.html,

    // Existing status/identity
    statusReady: _state.status?.ready === true,
    hasStatusError: !!_state.status?.error,
    statusErrorText: esc(_state.status?.error || ''),
    configExists: _state.status?.config_exists === true,
    hasConfigPath: !!_state.status?.config_path,
    configPath: esc(_state.status?.config_path || ''),
    hasDevice: !!_state.status?.device,
    device: esc(_state.status?.device || ''),
    hasFingerprint: !!_state.identity?.fingerprint,
    fingerprint: esc(_state.identity?.fingerprint || ''),
    hasIdentityError: !!_state.identity?.error,
    identityError: esc(_state.identity?.error || ''),
    copyFeedback: _state.copyFeedback,

    // Tab active states
    isConfigTabActive: activeTab === 'config',
    isLogsTabActive: activeTab === 'logs',
    isServiceTabActive: activeTab === 'service',
    isTrustTabActive: activeTab === 'trust',
    isKeysTabActive: activeTab === 'keys',

    // Config section
    configAvailable,
    configError: esc(_state.configLoadError || ''),
    configHost: esc(configData.receiver_host || '0.0.0.0'),
    configPort: String(configData.receiver_port || 8080),
    configKeyPath: esc(configData.host_private_path || ''),
    configTrustedDir: esc(configData.trusted_dir || ''),
    configAuditPath: esc(configData.audit_log_path || ''),
    configExecuteActions: !!configData.execute_remote_actions,
    configAllowedActions: esc((configData.allowed_remote_actions || []).join(', ')),

    // Logs section (message for empty state, logs populated by JS)
    logError: esc(_state.logsError || ''),

    // Trust section (message for empty state, trust populated by JS)
    trustError: esc(_state.trustError || ''),
  };

  container.innerHTML = await loadTemplate('camcoms', data);
  renderLogsTable(container);
  renderTrustTable(container);
  mountHandlers(container);
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '180px' })}
        ${skeletonText({ width: '240px' })}
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: var(--space-4);">
        ${skeletonCard({ height: '280px' })}
        ${skeletonCard({ height: '280px' })}
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
        ${esc(_state.errorMessage || 'Unable to reach the CamComs backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="camcoms-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#camcoms-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // ── Existing: Refresh button ──────────────────────────────────────────
  container.querySelector('#camcoms-refresh-btn')?.addEventListener('click', () => {
    loadData();
  });

  // ── Existing: Auto-refresh toggle ────────────────────────────────────
  const autoToggle = container.querySelector('#camcoms-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', () => {
      _state.autoRefresh = autoToggle.checked;
      persistAutoRefresh(_state.autoRefresh);
      if (_state.autoRefresh) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }

  // ── Existing: Copy fingerprint button ────────────────────────────────
  container.querySelector('#camcoms-copy-btn')?.addEventListener('click', async () => {
    const fingerprint = _state.identity?.fingerprint;
    if (!fingerprint) return;

    try {
      await navigator.clipboard.writeText(fingerprint);
      showCopyFeedback(container);
    } catch (err) {
      console.warn('[camcoms] Copy failed:', err);
    }
  });

  // ── Tab switching ────────────────────────────────────────────────────
  container.querySelectorAll('[data-camcoms-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tabId = btn.dataset.camcomsTab;
      if (tabId && tabId !== _state.activeTab) {
        switchTab(tabId);
      }
    });
  });

  // ── Configuration: Save ──────────────────────────────────────────────
  container.querySelector('#camcoms-config-save-btn')?.addEventListener('click', () => {
    saveConfig();
  });

  // ── Configuration: Init default ──────────────────────────────────────
  container.querySelector('#camcoms-config-init-btn')?.addEventListener('click', () => {
    initDefaultConfig();
  });

  // ── Logs: Refresh ────────────────────────────────────────────────────
  container.querySelector('#camcoms-logs-refresh-btn')?.addEventListener('click', () => {
    fetchLogs();
  });

  // ── Service: Start ───────────────────────────────────────────────────
  container.querySelector('#camcoms-service-start-btn')?.addEventListener('click', () => {
    serviceAction('start');
  });

  // ── Service: Stop ────────────────────────────────────────────────────
  container.querySelector('#camcoms-service-stop-btn')?.addEventListener('click', () => {
    serviceAction('stop');
  });

  // ── Service: Restart ─────────────────────────────────────────────────
  container.querySelector('#camcoms-service-restart-btn')?.addEventListener('click', () => {
    serviceAction('restart');
  });

  // ── Trust: Remove buttons ────────────────────────────────────────────
  container.querySelectorAll('[data-trust-remove]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const deviceId = btn.dataset.trustRemove;
      if (deviceId) removeTrustedSender(deviceId);
    });
  });

  // ── Trust: Add button ────────────────────────────────────────────────
  container.querySelector('#camcoms-trust-add-btn')?.addEventListener('click', () => {
    addTrustedSender();
  });

  // ── Keys: Generate ───────────────────────────────────────────────────
  container.querySelector('#camcoms-keygen-btn')?.addEventListener('click', () => {
    generateKeys();
  });

  // ── Keys: Copy public key ────────────────────────────────────────────
  container.querySelector('#camcoms-copy-pubkey-btn')?.addEventListener('click', async () => {
    await copyPublicKey(container);
  });
}

/* ── Copy Feedback Helper ───────────────────────────────────────────────── */

async function showCopyFeedback(container) {
  _state.copyFeedback = true;
  const btn = container.querySelector('#camcoms-copy-btn');
  if (btn) {
    btn.querySelector('span:last-child').textContent = 'Copied!';
    const iconSpan = btn.querySelector('span:first-child');
    if (iconSpan) iconSpan.innerHTML = ICONS.check.html || ICONS.check;
  }
  setTimeout(() => {
    if (_state.destroyed) return;
    _state.copyFeedback = false;
    const btn2 = container.querySelector('#camcoms-copy-btn');
    if (btn2) {
      btn2.querySelector('span:last-child').textContent = 'Copy';
      const iconSpan2 = btn2.querySelector('span:first-child');
      if (iconSpan2) iconSpan2.innerHTML = ICONS.copy.html || ICONS.copy;
    }
  }, 2000);
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
  await fetchData(true);
}

/* ── Data Loading (Status + Identity) ──────────────────────────────────── */

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
    const [statusRes, identityRes] = await Promise.allSettled([
      api.get('/api/v1/camcoms/status'),
      api.get('/api/v1/camcoms/identity'),
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
        _state.errorMessage = statusRes.reason?.message || 'Failed to fetch CamComs status.';
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
        _state.errorMessage = identityRes.reason?.message || 'Failed to fetch CamComs identity.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
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
      console.error('[camcoms] Failed to load data:', err);
      _state.error = true;
      _state.errorMessage = err.message || 'Unexpected error fetching CamComs data.';
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

  // Lazy-load data for the initially active tab
  if (!_state.destroyed) {
    const tab = _state.activeTab;
    if (tab === 'config') fetchConfig();
    else if (tab === 'logs') fetchLogs();
    else if (tab === 'trust') fetchTrustedSenders();
  }

  if (_state.autoRefresh && !_state.destroyed) {
    startPolling();
  }
}

/* ── Section Data Fetchers ──────────────────────────────────────────────── */

async function fetchConfig() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  _state.configLoading = true;
  _state.configLoadError = '';

  try {
    const res = await api.get('/api/v1/camcoms/config');
    if (_state.destroyed) return;
    const data = res?.data || {};
    if (data.available === false) {
      _state.config = null;
      _state.configLoadError = data.error || 'Config not available';
    } else {
      _state.config = data;
    }
  } catch (err) {
    console.error('[camcoms] Failed to load config:', err);
    _state.config = null;
    _state.configLoadError = err.message || 'Failed to load config';
  } finally {
    _state.configLoading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
}

async function fetchLogs() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  _state.logsLoading = true;
  _state.logsError = '';

  try {
    const res = await api.get('/api/v1/camcoms/logs?limit=50');
    if (_state.destroyed) return;
    _state.logs = res?.data || [];
  } catch (err) {
    console.error('[camcoms] Failed to load logs:', err);
    _state.logs = [];
    _state.logsError = err.message || 'Failed to load logs';
  } finally {
    _state.logsLoading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
}

async function fetchTrustedSenders() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  _state.trustLoading = true;
  _state.trustError = '';

  try {
    const res = await api.get('/api/v1/camcoms/trusted');
    if (_state.destroyed) return;
    const data = res?.data || {};
    _state.trustedSenders = data.senders || [];
  } catch (err) {
    console.error('[camcoms] Failed to load trusted senders:', err);
    _state.trustedSenders = [];
    _state.trustError = err.message || 'Failed to load trusted senders';
  } finally {
    _state.trustLoading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
}

/* ── Action Handlers ────────────────────────────────────────────────────── */

async function saveConfig() {
  const container = _state.container;
  if (!container) return;

  const feedback = container.querySelector('#camcoms-config-feedback');
  if (feedback) feedback.style.display = 'none';

  const api = getApi();
  if (!api) {
    if (feedback) { feedback.textContent = 'API not available'; feedback.style.display = 'block'; feedback.style.color = 'var(--danger)'; }
    return;
  }

  // Collect form values
  const host = container.querySelector('#camcoms-config-host')?.value || '0.0.0.0';
  const portStr = container.querySelector('#camcoms-config-port')?.value || '8080';
  const hostPrivatePath = container.querySelector('#camcoms-config-key-path')?.value || '';
  const trustedDir = container.querySelector('#camcoms-config-trusted-dir')?.value || '';
  const auditPath = container.querySelector('#camcoms-config-audit-path')?.value || '';
  const executeActions = container.querySelector('#camcoms-config-execute-actions')?.value === 'true';
  const allowedActionsStr = container.querySelector('#camcoms-config-allowed-actions')?.value || '';

  const configUpdate = {
    receiver_host: host,
    receiver_port: parseInt(portStr, 10) || 8080,
    host_private_path: hostPrivatePath,
    trusted_dir: trustedDir,
    audit_log_path: auditPath,
    execute_remote_actions: executeActions,
    allowed_remote_actions: allowedActionsStr.split(',').map((s) => s.trim()).filter(Boolean),
  };

  try {
    const res = await api.post('/api/v1/camcoms/config', configUpdate);
    if (_state.destroyed) return;
    _state.config = res?.data || configUpdate;
    if (feedback) {
      feedback.textContent = 'Configuration saved successfully';
      feedback.style.display = 'block';
      feedback.style.color = 'var(--success)';
      setTimeout(() => { feedback.style.display = 'none'; }, 3000);
    }
  } catch (err) {
    console.error('[camcoms] Failed to save config:', err);
    if (feedback) {
      feedback.textContent = `Failed to save: ${err.message || 'Unknown error'}`;
      feedback.style.display = 'block';
      feedback.style.color = 'var(--danger)';
    }
  }
}

async function initDefaultConfig() {
  const container = _state.container;
  if (!container) return;

  // Create a minimal default config
  const defaultConfig = {
    receiver_host: '0.0.0.0',
    receiver_port: 8080,
    execute_remote_actions: false,
    allowed_remote_actions: ['press', 'click', 'move', 'launch_binding', 'text', 'macro'],
  };

  const api = getApi();
  if (!api) return;

  try {
    await api.post('/api/v1/camcoms/config', defaultConfig);
    await fetchConfig();
  } catch (err) {
    console.error('[camcoms] Failed to init default config:', err);
  }
}

async function serviceAction(action) {
  const container = _state.container;
  if (!container) return;

  const feedback = container.querySelector('#camcoms-service-feedback');
  if (feedback) feedback.textContent = `${action}ing service...`;

  const api = getApi();
  if (!api) {
    if (feedback) feedback.textContent = 'API not available';
    return;
  }

  try {
    const res = await api.post(`/api/v1/camcoms/${action}`);
    if (_state.destroyed) return;
    if (feedback) {
      const stdout = res?.data?.stdout || '';
      feedback.textContent = `Service ${action} completed. ${stdout}`;
      feedback.style.color = 'var(--success)';
      setTimeout(() => {
        if (!_state.destroyed && feedback) {
          feedback.textContent = '';
          feedback.style.color = '';
        }
      }, 5000);
    }
  } catch (err) {
    console.error(`[camcoms] Failed to ${action} service:`, err);
    if (feedback) {
      feedback.textContent = `Failed to ${action}: ${err.message || 'Unknown error'}`;
      feedback.style.color = 'var(--danger)';
    }
  }
}

async function removeTrustedSender(deviceId) {
  const container = _state.container;
  if (!container) return;

  const feedback = container.querySelector('#camcoms-trust-feedback');
  if (feedback) feedback.textContent = '';

  const api = getApi();
  if (!api) return;

  try {
    await api.post('/api/v1/camcoms/trust/remove', { device_id: deviceId });
    // Refresh the list
    await fetchTrustedSenders();
    if (feedback) {
      feedback.textContent = `Removed ${deviceId}`;
      feedback.style.color = 'var(--success)';
      setTimeout(() => { feedback.textContent = ''; }, 3000);
    }
  } catch (err) {
    console.error('[camcoms] Failed to remove trusted sender:', err);
    if (feedback) {
      feedback.textContent = `Failed to remove: ${err.message || 'Unknown error'}`;
      feedback.style.color = 'var(--danger)';
    }
  }
}

async function addTrustedSender() {
  const container = _state.container;
  if (!container) return;

  const feedback = container.querySelector('#camcoms-trust-feedback');
  if (feedback) feedback.textContent = '';

  const input = container.querySelector('#camcoms-trust-key-input');
  const expiryInput = container.querySelector('#camcoms-trust-expiry');

  if (!input) return;

  let publicKeyJson;
  try {
    publicKeyJson = JSON.parse(input.value);
  } catch {
    if (feedback) {
      feedback.textContent = 'Invalid JSON in public key field';
      feedback.style.color = 'var(--danger)';
    }
    return;
  }

  if (!publicKeyJson.device_id || !publicKeyJson.encryption_public_key || !publicKeyJson.signing_public_key) {
    if (feedback) {
      feedback.textContent = 'Public key must include device_id, encryption_public_key, and signing_public_key';
      feedback.style.color = 'var(--danger)';
    }
    return;
  }

  const api = getApi();
  if (!api) return;

  const body = { public_key: publicKeyJson };
  const expiryDays = parseInt(expiryInput?.value || '0', 10);
  if (expiryDays > 0) {
    body.expires_in_days = expiryDays;
  }

  try {
    await api.post('/api/v1/camcoms/trust/add', body);
    input.value = '';
    if (expiryInput) expiryInput.value = '0';
    await fetchTrustedSenders();
    if (feedback) {
      feedback.textContent = `Added trusted sender: ${publicKeyJson.device_id}`;
      feedback.style.color = 'var(--success)';
      setTimeout(() => { feedback.textContent = ''; }, 3000);
    }
  } catch (err) {
    console.error('[camcoms] Failed to add trusted sender:', err);
    if (feedback) {
      feedback.textContent = `Failed to add: ${err.message || 'Unknown error'}`;
      feedback.style.color = 'var(--danger)';
    }
  }
}

async function generateKeys() {
  const container = _state.container;
  if (!container) return;

  const feedback = container.querySelector('#camcoms-keygen-feedback');
  if (feedback) feedback.textContent = '';

  const deviceIdInput = container.querySelector('#camcoms-keygen-device-id');
  const deviceId = deviceIdInput?.value || 'host';

  // Confirm with the user
  if (!confirm('WARNING: Generating new keys will invalidate all existing trusted sender relationships.\n\nAll paired devices will need to re-pair using the new public key.\n\nAre you sure you want to continue?')) {
    return;
  }

  const api = getApi();
  if (!api) {
    if (feedback) feedback.textContent = 'API not available';
    return;
  }

  try {
    const res = await api.post('/api/v1/camcoms/keygen', {
      device_id: deviceId,
      confirmed: true,
    });
    if (_state.destroyed) return;
    const data = res?.data || {};
    if (feedback) {
      feedback.innerHTML = `Keys generated. New fingerprint: <code style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 3px; word-break: break-all;">${esc(data.new_fingerprint || '')}</code>`;
      feedback.style.color = 'var(--text-primary)';
    }
    // Refresh identity display
    await fetchData(true);
  } catch (err) {
    console.error('[camcoms] Key generation failed:', err);
    if (feedback) {
      feedback.textContent = `Key generation failed: ${err.message || 'Unknown error'}`;
      feedback.style.color = 'var(--danger)';
    }
  }
}

async function copyPublicKey(container) {
  const api = getApi();
  if (!api) return;

  // Try to load the public key bundle from the identity endpoint
  try {
    const res = await api.get('/api/v1/camcoms/identity');
    const fingerprint = res?.data?.fingerprint;
    if (fingerprint && fingerprint !== '(unavailable)' && fingerprint !== '(no identity)') {
      await navigator.clipboard.writeText(fingerprint);

      // Show brief feedback on the button
      const btn = container.querySelector('#camcoms-copy-pubkey-btn');
      if (btn) {
        const origText = btn.innerHTML;
        btn.innerHTML = '<span style="color: var(--success);">Copied!</span>';
        setTimeout(() => { btn.innerHTML = origText; }, 2000);
      }
      return;
    }
  } catch (err) {
    console.warn('[camcoms] Copy public key failed:', err);
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
  _state.activeTab = loadActiveTabPreference();

  // Reset section data on fresh render
  _state.config = null;
  _state.configLoadError = '';
  _state.logs = [];
  _state.logsError = '';
  _state.trustedSenders = [];
  _state.trustError = '';

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
  _state.copyFeedback = false;
  _state.config = null;
  _state.logs = [];
  _state.trustedSenders = [];
  _state.pairingStatus = null;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="camcoms-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#camcoms-root') || container;
      render(root);
    },
    destroy,
  };
}
