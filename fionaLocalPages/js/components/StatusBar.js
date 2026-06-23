/* ==========================================================================
   StatusBar.js — Bottom Application Status Bar
   ==========================================================================
   Display-only status bar showing current page name, mode indicator,
   operation progress (hidden when idle), connection indicator with
   green/red dot, notification count, and a live clock.

   Usage:
     import { StatusBar } from './StatusBar.js';

     const statusBar = new StatusBar({
       container: '#status-bar',
       store,
       router,
     });
     statusBar.attach();
   ========================================================================== */

import { BaseComponent, html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  statusBar: 'status-bar',
  left: 'status-bar__left',
  center: 'status-bar__center',
  right: 'status-bar__right',
  item: 'status-bar__item',
  itemInteractive: 'status-bar__item--interactive',
  separator: 'status-bar__separator',
  icon: 'status-bar__icon',
};

/**
 * @typedef {'disconnected'|'connecting'|'connected'|'error'} ConnectionStatus
 */

export class StatusBar extends BaseComponent {
  /**
   * @param {Object} options
   * @param {string|Element} options.container - Mount container
   * @param {Object} options.store - Global state store
   * @param {Object} [options.router] - Router instance for page name
   * @param {Object} [options.props]
   * @param {string} [options.props.mode='default'] - Mode indicator text
   */
  constructor(options = {}) {
    super(options);

    this._state = {
      pageName: '',
      mode: this._props.mode || 'default',
      connectionStatus: 'disconnected',
      notificationCount: 0,
      clock: '',
      taskActive: false,
      taskLabel: '',
      taskProgress: 0,
    };

    /** @type {number} Interval ID for the clock */
    this._clockInterval = null;
  }

  /**
   * Subscribe to store and start clock on mount.
   */
  mount() {
    if (this._store) {
      // Page name via router changes
      if (this._router) {
        this._unsubRoute = this._router.onChange((route) => {
          this.setState({ pageName: route?.title || route?.name || '' });
        });
      }

      // Connection status
      this._unsubConn = this._store.subscribe('system.status', (status) => {
        this.setState({ connectionStatus: status || 'disconnected' });
      });

      // Notification count
      this._unsubNotif = this._store.subscribe('notifications.unreadCount', (count) => {
        this.setState({ notificationCount: count || 0 });
      });

      // Task progress (from store path tasks.active)
      this._unsubTask = this._store.subscribe('tasks.active', (task) => {
        if (task) {
          this.setState({
            taskActive: true,
            taskLabel: task.label || '',
            taskProgress: task.progress || 0,
          });
        } else {
          this.setState({
            taskActive: false,
            taskLabel: '',
            taskProgress: 0,
          });
        }
      });

      // Initial sync of connection status
      const initialStatus = this._store.get('system.status');
      if (initialStatus) {
        this.setState({ connectionStatus: initialStatus });
      }

      const initialCount = this._store.get('notifications.unreadCount');
      if (initialCount != null) {
        this.setState({ notificationCount: initialCount });
      }
    }

    // Start clock
    this._updateClock();
    this._clockInterval = setInterval(() => this._updateClock(), 30000);
    this.addCleanup(() => {
      if (this._clockInterval) {
        clearInterval(this._clockInterval);
      }
    });
  }

  /**
   * Update the clock display.
   * @private
   */
  _updateClock() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    this.setState({ clock: `${displayHours}:${minutes} ${ampm}` }, true);
  }

  /**
   * Render the status bar.
   * @returns {string}
   */
  render() {
    const { pageName, mode, connectionStatus, notificationCount, clock,
            taskActive, taskLabel, taskProgress } = this._state;

    const connColor = connectionStatus === 'connected' ? 'var(--success)' : 'var(--danger)';
    const connDot =
      connectionStatus === 'connected'
        ? ICONS.check
        : ICONS.close;

    return html`
      <div class="${CSS.statusBar}">
        <!-- Left section: page name, mode -->
        <div class="${CSS.left}">
          <span class="${CSS.item}">
            ${pageName || 'Dashboard'}
          </span>
          <span class="${CSS.separator}"></span>
          <span class="${CSS.item}">
            Mode: ${mode}
          </span>
        </div>

        <!-- Center section: operation progress -->
        <div class="${CSS.center}">
          ${taskActive ? html`
            <span class="${CSS.item}">
              <span class="${CSS.icon}">${ICONS.activity}</span>
              ${taskLabel}
            </span>
            <span class="c-progress c-progress--sm" style="width: 80px;">
              <span class="c-progress__bar" style="width: ${taskProgress}%;"></span>
            </span>
          ` : ''}
        </div>

        <!-- Right section: connection, notifications, clock -->
        <div class="${CSS.right}">
          <!-- Connection -->
          <span class="${CSS.item} ${CSS.itemInteractive}"
                title="Connection: ${connectionStatus}">
            <span class="${CSS.icon}" style="color: ${connColor};">${connDot}</span>
            <span id="status-connection">${connectionStatus}</span>
          </span>

          <!-- Notification count -->
          ${notificationCount > 0 ? html`
            <span class="${CSS.separator}"></span>
            <span class="${CSS.item} ${CSS.itemInteractive}"
                  data-action="open-notifications"
                  title="Notifications">
              <span class="${CSS.icon}">${ICONS.bell}</span>
              <span id="status-notification-count"
                    class="c-badge c-badge--danger"
                    style="padding: 0 5px; min-width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 10px;">
                ${notificationCount > 99 ? '99+' : notificationCount}
              </span>
            </span>
          ` : ''}

          <span class="${CSS.separator}"></span>

          <!-- Clock -->
          <span class="${CSS.item}" id="status-clock">
            <span class="${CSS.icon}">${ICONS.clock}</span>
            ${clock}
          </span>
        </div>
      </div>
    `;
  }

  /**
   * Clean up subscriptions on destroy.
   */
  destroy() {
    if (this._unsubRoute) this._unsubRoute();
    if (this._unsubConn) this._unsubConn();
    if (this._unsubNotif) this._unsubNotif();
    if (this._unsubTask) this._unsubTask();
    super.destroy();
  }
}

export default StatusBar;
