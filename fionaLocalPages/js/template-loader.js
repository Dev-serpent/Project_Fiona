/* ==========================================================================
   template-loader.js — Fetch & Cache HTML Templates
   ==========================================================================
   Loads HTML page templates from the /templates/ directory, caches them
   in-memory, and provides a simple {{variable}} interpolation helper.
   This separates HTML structure from JS behavior so templates render as
   real HTML instead of being embedded in JS template literals.

   Usage:
     import { loadTemplate } from '../js/template-loader.js';

     async function mount(container) {
       const html = await loadTemplate('dashboard', {
         pageTitle: 'Dashboard',
         agentCount: 3,
       });
       container.innerHTML = html;
       // ... bind events
     }

   Template files:
     Each template is a plain .html file under fionaLocalPages/templates/
     with {{variable}} placeholders for dynamic content.
   ========================================================================== */

const _cache = new Map();
const _templateDir = 'templates';  // relative to the SPA base URL

/**
 * Fetch and optionally interpolate an HTML template.
 *
 * @param {string} name - Template filename without .html (e.g. 'dashboard')
 * @param {Object} [data] - Key/value pairs for {{variable}} interpolation
 * @param {Object} [opts]
 * @param {boolean} [opts.force=false] - Bypass cache
 * @returns {Promise<string>} The template HTML
 */
export async function loadTemplate(name, data = {}, opts = {}) {
  const cacheKey = name;
  if (!opts.force && _cache.has(cacheKey)) {
    return _interpolate(_cache.get(cacheKey), data);
  }

  const url = `${_templateDir}/${name}.html`;
  const resp = await fetch(url);

  if (!resp.ok) {
    throw new Error(`Failed to load template "${name}": ${resp.status} ${resp.statusText}`);
  }

  const html = await resp.text();
  _cache.set(cacheKey, html);
  return _interpolate(html, data);
}

/**
 * Clear all cached templates (useful during development).
 */
export function clearTemplateCache() {
  _cache.clear();
}

/**
 * Simple {{variable}} interpolation.
 * Also supports {{#if condition}}...{{/if}} blocks and
 * {{#each items}}...{{/each}} loops.
 *
 * @param {string} html - Template HTML with {{placeholders}}
 * @param {Object} data - Key/value pairs
 * @returns {string}
 * @private
 */
function _interpolate(html, data) {
  let result = html;

  // Replace {{variable}} placeholders (escaping HTML entities)
  result = result.replace(/\{\{escape\s+(\w+)\}\}/g, (_, key) => {
    const val = data[key];
    if (val == null) return '';
    return _escapeHtml(String(val));
  });

  // Replace {{{variable}}} placeholders (raw — for SVG icons / trusted HTML)
  result = result.replace(/\{\{\{(\w+)\}\}\}/g, (_, key) => {
    const val = data[key];
    if (val == null) return '';
    return String(val);
  });

  // Replace {{variable}} placeholders (auto-detect: escape by default)
  result = result.replace(/\{\{(\w+)\}\}/g, (_, key) => {
    const val = data[key];
    if (val == null) return '';
    // If the value is an object with __isRawHtml (from html.raw), use raw
    if (val && typeof val === 'object' && val.__isRawHtml) {
      return val.html;
    }
    return _escapeHtml(String(val));
  });

  // Basic {{#if key}}...{{/if}} blocks
  result = result.replace(/\{\{#if\s+(\w+)\}\}([\s\S]*?)\{\{\/if\}\}/g, (_, key, content) => {
    if (data[key]) {
      // Recursively interpolate the content
      return _interpolate(content, data);
    }
    return '';
  });

  // Basic {{#unless key}}...{{/unless}} blocks (inverse of if)
  result = result.replace(/\{\{#unless\s+(\w+)\}\}([\s\S]*?)\{\{\/unless\}\}/g, (_, key, content) => {
    if (!data[key]) {
      return _interpolate(content, data);
    }
    return '';
  });

  // Basic {{#each items}}...{{/each}} blocks — items must be an array
  // Each item is available as {{this}}, and item properties as {{propName}}
  result = result.replace(/\{\{#each\s+(\w+)\}\}([\s\S]*?)\{\{\/each\}\}/g, (_, key, template) => {
    const items = data[key];
    if (!Array.isArray(items) || items.length === 0) return '';
    return items.map((item) => {
      // item can be a string or object
      if (typeof item === 'string' || typeof item === 'number') {
        return _interpolate(template, { ...data, this: item });
      }
      return _interpolate(template, { ...data, ...item, this: item });
    }).join('');
  });

  return result;
}

/**
 * Escape HTML entities in a string.
 * @param {string} str
 * @returns {string}
 * @private
 */
function _escapeHtml(str) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

export default { loadTemplate, clearTemplateCache };
