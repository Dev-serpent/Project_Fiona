/**
 * flask-shared.js — Minimal shared JS for the Flask-rendered frontend.
 * Replaces the SPA app.js, router.js, state.js, api.js, template-loader.js
 *
 * This file provides:
 *  - Clock update in status bar
 *  - Connection indicator polling
 *  - Sidebar section toggle
 *  - Breadcrumb sync
 */

(function () {
  'use strict';

  /* ── Clock ─────────────────────────────────────────────────────────── */
  function updateClock() {
    const el = document.getElementById('status-clock');
    if (!el) return;
    const now = new Date();
    const h = now.getHours();
    const m = String(now.getMinutes()).padStart(2, '0');
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    el.textContent = h12 + ':' + m + ' ' + ampm;
  }
  updateClock();
  setInterval(updateClock, 10000);

  /* ── Connection Indicator ──────────────────────────────────────────── */
  function checkConnection() {
    const el = document.getElementById('connection-indicator');
    if (!el) return;
    fetch('/api/v1/health')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.ok) {
          el.className = 'connection-indicator connection-indicator--connected';
          el.querySelector('.connection-indicator__label').textContent = 'Connected';
        } else {
          el.className = 'connection-indicator connection-indicator--disconnected';
          el.querySelector('.connection-indicator__label').textContent = 'Disconnected';
        }
      })
      .catch(function () {
        el.className = 'connection-indicator connection-indicator--disconnected';
        el.querySelector('.connection-indicator__label').textContent = 'Disconnected';
      });
  }
  checkConnection();
  setInterval(checkConnection, 15000);

  /* ── Sidebar Section Toggle ────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    var target = e.target.closest('[data-action="toggle-section"]');
    if (!target) return;
    var sectionId = target.dataset.sectionId;
    var content = target.nextElementSibling;
    if (content) {
      var expanded = target.getAttribute('aria-expanded') === 'true';
      target.setAttribute('aria-expanded', String(!expanded));
      content.style.display = expanded ? 'none' : '';
    }
  });

  /* ── Active nav-item highlight ─────────────────────────────────────── */
  var navItems = document.querySelectorAll('.nav-item');
  var currentPath = window.location.pathname;
  navItems.forEach(function (item) {
    var href = item.getAttribute('href');
    if (href === currentPath) {
      item.classList.add('nav-item--active');
    }
  });

})();
