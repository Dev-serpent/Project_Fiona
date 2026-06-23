/* ==========================================================================
   DataTable.js — Sortable, Filterable Data Table
   ==========================================================================
   Creates a feature-rich data table with column sorting, text filtering,
   row selection (single/multi), pagination, and CSV export.

   Usage:
     import { createDataTable } from './DataTable.js';

     const table = createDataTable('#my-table', [
       { key: 'name', label: 'Name', sortable: true, filterable: true },
       { key: 'age',  label: 'Age',  sortable: true },
       { key: 'role', label: 'Role', render: (val) => `<span class="c-badge">${val}</span>` },
     ], [
       { name: 'Alice', age: 30, role: 'Admin' },
       { name: 'Bob',   age: 25, role: 'User' },
     ], {
       pageSize: 20,
       selectable: 'single',
     });

     table.onSelection((rows) => console.log('Selected:', rows));
     table.exportCSV();
     table.destroy();
   ========================================================================== */

import { html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  wrapper: 'c-table-wrapper',
  table: 'c-table',
  thSortable: 'th--sortable',
  thSorted: 'th--sorted',
  trSelected: 'tr--selected',
  trClickable: 'tr--clickable',
};

/**
 * @typedef {Object} ColumnDef
 * @property {string} key - Data key
 * @property {string} label - Column header label
 * @property {boolean} [sortable=false] - Enable click-to-sort
 * @property {boolean} [filterable=false] - Show filter input
 * @property {number} [width] - Column width (px or %)
 * @property {Function} [render] - Custom cell renderer: (value, row) => HTML string
 */

/**
 * Create a data table.
 *
 * @param {string|Element} container - Container element
 * @param {ColumnDef[]} columns - Column definitions
 * @param {Array<Object>} data - Array of row data objects
 * @param {Object} [options]
 * @param {number} [options.pageSize=50] - Rows per page (0 = no pagination)
 * @param {'none'|'single'|'multi'} [options.selectable='none'] - Row selection mode
 * @param {string} [options.defaultSortKey] - Default sort column
 * @param {'asc'|'desc'} [options.defaultSortDir='asc'] - Default sort direction
 * @param {Function} [options.onRowClick] - (row, index) => void
 * @returns {DataTableAPI}
 */
export function createDataTable(container, columns, data, options = {}) {
  /** @type {Element} */
  let _container = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (!_container) {
    console.error('[DataTable] Container not found:', container);
    return null;
  }

  /** @type {ColumnDef[]} */
  let _columns = [...columns];

  /** @type {Array<Object>} */
  let _data = [...data];

  /** @type {Object} */
  const _opts = {
    pageSize: options.pageSize != null ? options.pageSize : 50,
    selectable: options.selectable || 'none',
    defaultSortKey: options.defaultSortKey || null,
    defaultSortDir: options.defaultSortDir || 'asc',
    onRowClick: options.onRowClick || null,
  };

  /** @type {{ key: string, dir: 'asc'|'desc'|null }} */
  let _sort = { key: _opts.defaultSortKey, dir: _opts.defaultSortDir || 'asc' };

  /** @type {Object<string, string>} Column filter values */
  let _filters = {};

  /** @type {Set<number>} Selected row indices */
  let _selected = new Set();

  /** @type {number} Current page (0-indexed) */
  let _page = 0;

  /** @type {Function|null} */
  let _selectionCallback = null;

  let _destroyed = false;

  /**
   * Conditionally build a className string.
   * @param {...*} args
   * @returns {string}
   */
  function classNames(...args) {
    const classes = [];
    for (const arg of args) {
      if (!arg) continue;
      if (typeof arg === 'string') {
        classes.push(arg);
      } else if (Array.isArray(arg)) {
        classes.push(classNames(...arg));
      } else if (typeof arg === 'object') {
        for (const [key, value] of Object.entries(arg)) {
          if (value) classes.push(key);
        }
      }
    }
    return classes.join(' ');
  }

  /* ── Data processing ─────────────────────────────────────────────────── */

  /**
   * Get filtered, sorted data.
   * @returns {Array<{index: number, row: Object}>}
   * @private
   */
  function _getProcessedData() {
    let filtered = _data.map((row, idx) => ({ index: idx, row }));

    // Apply filters
    for (const [key, value] of Object.entries(_filters)) {
      if (!value || !value.trim()) continue;
      const q = value.toLowerCase().trim();
      filtered = filtered.filter(({ row }) => {
        const cell = String(row[key] || '').toLowerCase();
        return cell.includes(q);
      });
    }

    // Apply sorting
    if (_sort.key && _sort.dir) {
      const { key, dir } = _sort;
      filtered.sort((a, b) => {
        const va = a.row[key];
        const vb = b.row[key];
        let cmp = 0;
        if (typeof va === 'number' && typeof vb === 'number') {
          cmp = va - vb;
        } else {
          cmp = String(va).localeCompare(String(vb));
        }
        return dir === 'desc' ? -cmp : cmp;
      });
    }

    return filtered;
  }

  /**
   * Get the paginated subset of data.
   * @param {Array} processed
   * @returns {{ rows: Array, totalPages: number, totalRows: number }}
   * @private
   */
  function _getPageData(processed) {
    const totalRows = processed.length;
    const pageSize = _opts.pageSize;
    const totalPages = pageSize > 0 ? Math.ceil(totalRows / pageSize) : 1;

    if (pageSize > 0) {
      const start = _page * pageSize;
      const rows = processed.slice(start, start + pageSize);
      return { rows, totalPages, totalRows };
    }

    return { rows: processed, totalPages: 1, totalRows };
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  function _render() {
    if (_destroyed) return;

    const processed = _getProcessedData();
    const { rows, totalPages, totalRows } = _getPageData(processed);

    // Ensure page is valid
    if (_page >= totalPages) _page = Math.max(0, totalPages - 1);

    // Selected set should only contain valid indices in original data
    _selected = new Set(Array.from(_selected).filter((idx) => idx < _data.length));

    const allSelected = _opts.selectable === 'multi'
      && rows.every((r) => _selected.has(r.index));

    _container.innerHTML = html`
      <div class="${CSS.wrapper}">
        <table class="${CSS.table}">
          <thead>
            <tr>
              ${_opts.selectable === 'multi' ? html`
                <th style="width: 40px;">
                  <label class="c-checkbox" style="justify-content: center;">
                    <input type="checkbox" class="c-checkbox__input"
                           data-select-all ${allSelected ? 'checked' : ''} />
                    <span class="c-checkbox__visual"></span>
                  </label>
                </th>
              ` : ''}
              ${_opts.selectable === 'single' ? html`
                <th style="width: 40px;"></th>
              ` : ''}
              ${_columns.map((col) => html`
                <th class="${classNames(col.sortable ? CSS.thSortable : '',
                                           _sort.key === col.key ? CSS.thSorted : '')}"
                    style="${col.width ? `width: ${typeof col.width === 'number' ? col.width + 'px' : col.width}` : ''}"
                    data-column-key="${col.key}"
                    data-sortable="${col.sortable ? 'true' : 'false'}">
                  <div style="display: flex; align-items: center; gap: 4px;">
                    <span>${col.label}</span>
                    ${_sort.key === col.key ? html`
                      <span style="font-size: 10px;">
                        ${_sort.dir === 'asc' ? ICONS.arrowUp : ICONS.arrowDown}
                      </span>
                    ` : ''}
                  </div>
                  ${col.filterable ? html`
                    <div style="margin-top: 4px;">
                      <input type="text" class="c-input c-input--sm"
                             data-filter-key="${col.key}"
                             placeholder="Filter…"
                             value="${_filters[col.key] || ''}"
                             style="width: 100%; height: 24px; font-size: 11px; padding: 0 6px;" />
                    </div>
                  ` : ''}
                </th>
              `)}
            </tr>
          </thead>
          <tbody>
            ${rows.length === 0 ? html`
              <tr>
                <td colspan="${_columns.length + (_opts.selectable !== 'none' ? 1 : 0)}"
                    style="text-align: center; padding: 40px 16px; color: var(--text-muted);">
                  No data found.
                </td>
              </tr>
            ` : rows.map(({ index, row }) => {
              const isSelected = _selected.has(index);
              return html`
                <tr class="${classNames(isSelected ? CSS.trSelected : '',
                                            _opts.onRowClick ? CSS.trClickable : '')}"
                    data-row-index="${index}">
                  ${_opts.selectable === 'multi' ? html`
                    <td>
                      <label class="c-checkbox" style="justify-content: center;">
                        <input type="checkbox" class="c-checkbox__input"
                               data-select-row="${index}"
                               ${isSelected ? 'checked' : ''} />
                        <span class="c-checkbox__visual"></span>
                      </label>
                    </td>
                  ` : ''}
                  ${_opts.selectable === 'single' ? html`
                    <td>
                      <label class="c-radio" style="justify-content: center;">
                        <input type="radio" class="c-radio__input"
                               name="row-select"
                               data-select-row="${index}"
                               ${isSelected ? 'checked' : ''} />
                        <span class="c-radio__visual"></span>
                      </label>
                    </td>
                  ` : ''}
                  ${_columns.map((col) => {
                    const value = row[col.key];
                    const display = col.render ? col.render(value, row) : String(value != null ? value : '');
                    return html`<td>${html.raw(display)}</td>`;
                  })}
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>

      ${_opts.pageSize > 0 ? html`
        <div style="display: flex; align-items: center; justify-content: space-between;
                    padding: 8px 12px; border-top: 1px solid var(--border-subtle);
                    font-size: var(--font-size-xs); color: var(--text-muted);">
          <span>${totalRows} row${totalRows !== 1 ? 's' : ''}</span>
          <div style="display: flex; align-items: center; gap: 8px;">
            <button class="c-btn c-btn--sm c-btn--icon" data-page="first"
                    ${_page === 0 ? 'disabled' : ''} title="First page">
              ${ICONS.chevronLeft}${ICONS.chevronLeft}
            </button>
            <button class="c-btn c-btn--sm c-btn--icon" data-page="prev"
                    ${_page === 0 ? 'disabled' : ''} title="Previous page">
              ${ICONS.chevronLeft}
            </button>
            <span>Page ${_page + 1} of ${totalPages}</span>
            <button class="c-btn c-btn--sm c-btn--icon" data-page="next"
                    ${_page >= totalPages - 1 ? 'disabled' : ''} title="Next page">
              ${ICONS.chevronRight}
            </button>
            <button class="c-btn c-btn--sm c-btn--icon" data-page="last"
                    ${_page >= totalPages - 1 ? 'disabled' : ''} title="Last page">
              ${ICONS.chevronRight}${ICONS.chevronRight}
            </button>
            <button class="c-btn c-btn--sm c-btn--icon" data-action="export-csv"
                    title="Export CSV" style="margin-left: 8px;">
              ${ICONS.download}
            </button>
          </div>
        </div>
      ` : ''}
    `;

    _bindEvents();
  }

  /* ── Events ──────────────────────────────────────────────────────────── */

  function _bindEvents() {
    // Column header sorting
    _container.querySelectorAll('[data-column-key][data-sortable="true"]').forEach((th) => {
      th.addEventListener('click', (e) => {
        // Ignore clicks on filter inputs
        if (e.target.tagName === 'INPUT') return;
        const key = th.dataset.columnKey;
        _toggleSort(key);
      });
    });

    // Filter inputs (debounced)
    _container.querySelectorAll('[data-filter-key]').forEach((input) => {
      let timer;
      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          _filters[input.dataset.filterKey] = input.value;
          _page = 0;
          _render();
        }, 200);
      });
    });

    // Pagination
    _container.querySelectorAll('[data-page]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.page;
        const processed = _getProcessedData();
        const { totalPages } = _getPageData(processed);

        switch (action) {
          case 'first': _page = 0; break;
          case 'prev':  _page = Math.max(0, _page - 1); break;
          case 'next':  _page = Math.min(totalPages - 1, _page + 1); break;
          case 'last':  _page = totalPages - 1; break;
        }
        _render();
      });
    });

    // Row selection - multi
    if (_opts.selectable === 'multi') {
      _container.querySelectorAll('[data-select-row]').forEach((cb) => {
        cb.addEventListener('change', () => {
          const idx = parseInt(cb.dataset.selectRow, 10);
          if (cb.checked) _selected.add(idx);
          else _selected.delete(idx);
          _notifySelection();
          _renderSelectedState();
        });
      });

      // Select all
      const selectAll = _container.querySelector('[data-select-all]');
      if (selectAll) {
        selectAll.addEventListener('change', () => {
          const processed = _getProcessedData();
          const { rows } = _getPageData(processed);
          if (selectAll.checked) {
            rows.forEach((r) => _selected.add(r.index));
          } else {
            rows.forEach((r) => _selected.delete(r.index));
          }
          _notifySelection();
          _render();
        });
      }
    }

    // Row selection - single
    if (_opts.selectable === 'single') {
      _container.querySelectorAll('[data-select-row]').forEach((radio) => {
        radio.addEventListener('change', () => {
          if (!radio.checked) return;
          _selected.clear();
          const idx = parseInt(radio.dataset.selectRow, 10);
          _selected.add(idx);
          _notifySelection();
          _renderSelectedState();
        });
      });
    }

    // Row click
    if (_opts.onRowClick) {
      _container.querySelectorAll('[data-row-index]').forEach((tr) => {
        tr.addEventListener('click', (e) => {
          // Don't fire if clicking on checkbox/radio
          if (e.target.closest('.c-checkbox, .c-radio, input')) return;
          const idx = parseInt(tr.dataset.rowIndex, 10);
          _opts.onRowClick(_data[idx], idx);
        });
      });
    }

    // CSV export
    _container.querySelector('[data-action="export-csv"]')?.addEventListener('click', exportCSV);
  }

  /**
   * Update only the selected visual state without full re-render.
   * @private
   */
  function _renderSelectedState() {
    _container.querySelectorAll('[data-row-index]').forEach((tr) => {
      const idx = parseInt(tr.dataset.rowIndex, 10);
      tr.classList.toggle(CSS.trSelected, _selected.has(idx));

      const cb = tr.querySelector('[data-select-row]');
      if (cb) cb.checked = _selected.has(idx);
    });
  }

  /**
   * Toggle sort for a column.
   * @param {string} key
   * @private
   */
  function _toggleSort(key) {
    if (_sort.key === key) {
      // Cycle: asc -> desc -> null
      if (_sort.dir === 'asc') _sort.dir = 'desc';
      else if (_sort.dir === 'desc') { _sort.dir = null; _sort.key = null; }
    } else {
      _sort.key = key;
      _sort.dir = 'asc';
    }
    _page = 0;
    _render();
  }

  /**
   * Notify selection callback.
   * @private
   */
  function _notifySelection() {
    if (_selectionCallback) {
      const selectedRows = Array.from(_selected).map((idx) => _data[idx]);
      _selectionCallback(selectedRows);
    }
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Update the table data.
   * @param {Array<Object>} newData
   * @param {boolean} [resetPage=true]
   */
  function setData(newData, resetPage = true) {
    if (_destroyed) return;
    _data = [...newData];
    _selected.clear();
    if (resetPage) _page = 0;
    _render();
  }

  /**
   * Update columns.
   * @param {ColumnDef[]} newColumns
   */
  function setColumns(newColumns) {
    if (_destroyed) return;
    _columns = [...newColumns];
    _render();
  }

  /**
   * Get selected rows.
   * @returns {Array<Object>}
   */
  function getSelected() {
    return Array.from(_selected).map((idx) => _data[idx]);
  }

  /**
   * Register a selection change callback.
   * @param {Function} callback - (selectedRows) => void
   */
  function onSelection(callback) {
    _selectionCallback = callback;
  }

  /**
   * Export current (filtered) data to CSV file.
   */
  function exportCSV() {
    const processed = _getProcessedData();
    const headers = _columns.map((c) => c.label);
    const rows = processed.map(({ row }) =>
      _columns.map((c) => {
        const val = row[c.key];
        const str = val != null ? String(val) : '';
        // Escape CSV
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',')
    );

    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'export.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  /**
   * Refresh the table rendering (e.g., after external data change).
   */
  function refresh() {
    if (_destroyed) return;
    _render();
  }

  /**
   * Remove the table from the DOM.
   */
  function destroy() {
    _destroyed = true;
    _container.innerHTML = '';
    _data = [];
    _columns = [];
    _selected.clear();
    _selectionCallback = null;
  }

  // Initial render
  _render();

  return {
    setData,
    setColumns,
    getSelected,
    onSelection,
    exportCSV,
    refresh,
    destroy,
  };
}

/**
 * @typedef {Object} DataTableAPI
 * @property {(newData: Array<Object>, resetPage?: boolean) => void} setData
 * @property {(newColumns: ColumnDef[]) => void} setColumns
 * @property {() => Array<Object>} getSelected
 * @property {(callback: Function) => void} onSelection
 * @property {() => void} exportCSV
 * @property {() => void} refresh
 * @property {() => void} destroy
 */

export default createDataTable;
