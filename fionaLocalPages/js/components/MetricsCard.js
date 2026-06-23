/* ==========================================================================
   MetricsCard.js — Animated Metrics Display Card
   ==========================================================================
   Displays a single metric value with animated counter, trend indicator,
   sparkline mini-chart (canvas-based), and configurable variants
   (default, compact, detailed).

   Usage:
     import { MetricsCard } from './MetricsCard.js';

     const card = new MetricsCard({
       container: '#cpu-card',
       props: {
         title: 'CPU Usage',
         value: 45.2,
         unit: '%',
         icon: 'activity',
         trend: 'up',
         delta: '+5.2%',
         sparklineData: [30, 42, 38, 45, 41, 39, 45.2],
         color: 'var(--accent)',
         variant: 'default',
       },
     });
     card.attach();

     // Update value (animates counter)
     card.updateValue(52.8);
   ========================================================================== */

import { BaseComponent, html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/**
 * @typedef {'default'|'compact'|'detailed'} MetricVariant
 * @typedef {'up'|'down'|'neutral'} TrendDirection
 */

export class MetricsCard extends BaseComponent {
  /**
   * @param {Object} options
   * @param {string|Element} options.container
   * @param {Object} options.props
   * @param {string} options.props.title - Metric label
   * @param {number} options.props.value - Current value
   * @param {string} [options.props.unit] - Unit suffix (e.g. '%', 'ms')
   * @param {string} [options.props.icon] - Icon key from ICONS
   * @param {TrendDirection} [options.props.trend='neutral'] - Trend direction
   * @param {string} [options.props.delta] - Change text (e.g. '+5.2%')
   * @param {number[]} [options.props.sparklineData] - Data points for mini chart
   * @param {string} [options.props.color='var(--accent)'] - Accent color
   * @param {MetricVariant} [options.props.variant='default']
   */
  constructor(options = {}) {
    super(options);

    this._state = {
      displayValue: this._props.value || 0,
      previousValue: 0,
    };

    /** @type {number|null} */
    this._animFrame = null;

    /** @type {number} Animation duration in ms */
    this._animDuration = 800;
  }

  /**
   * Set up canvas sparkline on mount.
   */
  mount() {
    if (this._props.sparklineData && this._props.sparklineData.length > 0) {
      this._drawSparkline();
    }
  }

  /**
   * Update the displayed value with counter animation.
   * @param {number} newValue
   * @param {boolean} [animate=true]
   */
  updateValue(newValue, animate = true) {
    this.setState({ previousValue: this._props.value || 0 });
    this._props = { ...this._props, value: newValue };

    if (animate && this._isMounted) {
      this._animateCounter(this._state.previousValue, newValue);
    } else {
      this.setState({ displayValue: newValue });
    }

    // Redraw sparkline if data was updated
    if (this._props.sparklineData && this._isMounted) {
      requestAnimationFrame(() => this._drawSparkline());
    }
  }

  /**
   * Animate the counter from start to end.
   * @param {number} start
   * @param {number} end
   * @private
   */
  _animateCounter(start, end) {
    if (this._animFrame) {
      cancelAnimationFrame(this._animFrame);
    }

    const startTime = performance.now();
    const diff = end - start;

    const step = (timestamp) => {
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / this._animDuration, 1);

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + diff * eased;

      this.setState({ displayValue: current }, true);
      // Update the displayed value in DOM directly for performance
      const valueEl = this.element?.querySelector('[data-metric-value]');
      if (valueEl) {
        valueEl.textContent = this._formatValue(current);
      }

      if (progress < 1) {
        this._animFrame = requestAnimationFrame(step);
      } else {
        this.setState({ displayValue: end }, true);
        this._animFrame = null;
      }
    };

    this._animFrame = requestAnimationFrame(step);
  }

  /**
   * Draw the sparkline chart on a canvas.
   * @private
   */
  _drawSparkline() {
    const canvas = this.element?.querySelector('[data-sparkline]');
    if (!canvas) return;

    const data = this._props.sparklineData;
    if (!data || data.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const color = this._props.color || 'var(--accent)';
    const pad = 2;

    ctx.clearRect(0, 0, w, h);

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // Draw the line
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    data.forEach((val, i) => {
      const x = pad + (i / (data.length - 1)) * (w - pad * 2);
      const y = h - pad - ((val - min) / range) * (h - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill gradient underneath
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, color.replace(')', ', 0.2)').replace(/[^,]+$/, '0.2)'));
    gradient.addColorStop(1, 'transparent');

    ctx.beginPath();
    const lastIdx = data.length - 1;
    ctx.moveTo(pad + (lastIdx / (data.length - 1)) * (w - pad * 2), h - pad);
    data.forEach((val, i) => {
      const x = pad + (i / (data.length - 1)) * (w - pad * 2);
      const y = h - pad - ((val - min) / range) * (h - pad * 2);
      ctx.lineTo(x, y);
    });
    ctx.lineTo(pad, h - pad);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
  }

  /**
   * Format a value for display.
   * @param {number} value
   * @returns {string}
   * @private
   */
  _formatValue(value) {
    if (Number.isInteger(value)) return String(value);
    // Show appropriate decimal places
    if (Math.abs(value) < 10) return value.toFixed(1);
    if (Math.abs(value) < 1000) return value.toFixed(0);
    return value.toFixed(0);
  }

  /**
   * Render the metrics card.
   * @returns {string}
   */
  render() {
    const { title, unit, icon, trend, delta, sparklineData, color, variant } = this._props;
    const { displayValue } = this._state;
    const v = variant || 'default';

    const trendIcon = trend === 'up' ? ICONS.trendingUp
      : trend === 'down' ? ICONS.trendingDown
      : '';

    const trendClass = trend === 'up' ? 'c-metric__change--positive'
      : trend === 'down' ? 'c-metric__change--negative'
      : '';

    if (v === 'compact') {
      return html`
        <div class="c-card" style="padding: var(--space-3); display: flex; align-items: center; gap: var(--space-3);">
          ${icon ? html`
            <div style="width: 32px; height: 32px; border-radius: var(--radius-md);
                        background: ${color}20; display: flex; align-items: center;
                        justify-content: center; flex-shrink: 0; color: ${color};">
              ${ICONS[icon]}
            </div>
          ` : ''}
          <div style="flex: 1; min-width: 0;">
            <div style="font-size: var(--font-size-xs); color: var(--text-muted);">${title}</div>
            <div style="display: flex; align-items: baseline; gap: 4px;">
              <span style="font-size: var(--font-size-lg); font-weight: var(--font-weight-bold);
                           color: var(--text-primary); font-variant-numeric: tabular-nums;"
                    data-metric-value>${this._formatValue(displayValue)}</span>
              ${unit ? html`<span style="font-size: var(--font-size-xs); color: var(--text-muted);">${unit}</span>` : ''}
            </div>
          </div>
          ${delta ? html`
            <div style="display: flex; align-items: center; gap: 2px; font-size: var(--font-size-xs); ${trendClass}">
              ${trendIcon} ${delta}
            </div>
          ` : ''}
        </div>
      `;
    }

    if (v === 'detailed') {
      return html`
        <div class="c-card">
          <div class="c-card__header">
            <div style="display: flex; align-items: center; gap: var(--space-2);">
              ${icon ? html`<span style="color: ${color};">${ICONS[icon]}</span>` : ''}
              <span class="c-card__title">${title}</span>
            </div>
            ${delta ? html`
              <div style="display: flex; align-items: center; gap: 2px; font-size: var(--font-size-sm); ${trendClass}">
                ${trendIcon} ${delta}
              </div>
            ` : ''}
          </div>
          <div class="c-card__body">
            <div style="display: flex; align-items: baseline; gap: 4px; margin-bottom: var(--space-3);">
              <span class="c-metric__value" data-metric-value
                    style="font-size: var(--font-size-xxl); color: ${color};">${this._formatValue(displayValue)}</span>
              ${unit ? html`<span style="font-size: var(--font-size-md); color: var(--text-muted);">${unit}</span>` : ''}
            </div>
            ${sparklineData && sparklineData.length > 0 ? html`
              <canvas data-sparkline
                      style="width: 100%; height: 48px; border-radius: var(--radius-sm);"></canvas>
            ` : ''}
          </div>
        </div>
      `;
    }

    // Default variant
    return html`
      <div class="c-card">
        <div class="c-card__body" style="display: flex; flex-direction: column; gap: var(--space-2);">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: var(--space-2);">
              ${icon ? html`
                <div style="width: 28px; height: 28px; border-radius: var(--radius-md);
                            background: ${color}20; display: flex; align-items: center;
                            justify-content: center; color: ${color};">
                  ${ICONS[icon]}
                </div>
              ` : ''}
              <span style="font-size: var(--font-size-xs); color: var(--text-muted);
                          text-transform: uppercase; letter-spacing: 0.05em;">
                ${title}
              </span>
            </div>
            ${delta ? html`
              <div style="display: flex; align-items: center; gap: 2px; font-size: var(--font-size-xs); ${trendClass}">
                ${trendIcon}
                <span>${delta}</span>
              </div>
            ` : ''}
          </div>

          <div style="display: flex; align-items: baseline; gap: 4px;">
            <span style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold);
                         color: var(--text-primary); font-variant-numeric: tabular-nums;"
                  data-metric-value>${this._formatValue(displayValue)}</span>
            ${unit ? html`<span style="font-size: var(--font-size-sm); color: var(--text-muted);">${unit}</span>` : ''}
          </div>

          ${sparklineData && sparklineData.length > 0 ? html`
            <canvas data-sparkline
                    style="width: 100%; height: 32px; margin-top: var(--space-1); border-radius: var(--radius-sm);"></canvas>
          ` : ''}
        </div>
      </div>
    `;
  }

  /**
   * Clean up on destroy.
   */
  destroy() {
    if (this._animFrame) {
      cancelAnimationFrame(this._animFrame);
      this._animFrame = null;
    }
    super.destroy();
  }
}

export default MetricsCard;
