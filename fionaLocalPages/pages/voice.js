/* ==========================================================================
   voice.js — Voice Command Page
   ==========================================================================
   Provides an interface for parsing text-based voice commands and
   transcribing uploaded or recorded audio.  Uses the backend APIs:
     POST /api/v1/voice/parse    — parse a natural-language phrase
     POST /api/v1/voice/transcribe — transcribe base64 WAV audio
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const HISTORY_MAX = 20;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,

  // Parse section
  parsePhrase: '',
  parseLoading: false,
  parseResult: null,       // { ok, data } from API or null
  parseError: null,        // string or null
  parseHistory: [],        // array of { phrase, result, error, timestamp }

  // Transcribe section
  transcribeLoading: false,
  transcribeResult: null,  // { ok, data } from API or null
  transcribeError: null,   // string or null

  // Recording state
  isRecording: false,
  mediaRecorder: null,
  audioChunks: [],
  recordingStream: null,
  recordedBlob: null,      // latest recording blob
  mediaRecorderAvailable: true,

  // File state
  selectedFile: null,      // File object or null
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function esc(str) {
  if (str == null) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function formatTime(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  const s = date.getSeconds().toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

/* ── MediaRecorder Detection ────────────────────────────────────────────── */

function checkMediaRecorderSupport() {
  return !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
}

/* ── API Calls ──────────────────────────────────────────────────────────── */

/**
 * POST /api/v1/voice/parse
 * @param {string} phrase
 */
async function callParseApi(phrase) {
  const api = getApi();
  if (!api) throw new Error('API client not available.');

  const res = await api.post('/api/v1/voice/parse', { phrase });
  if (!res || !res.ok) {
    throw new Error(res?.data?.message || res?.data?.error || 'Parse request failed');
  }
  return res; // { ok: true, data: { matched, text, command?, confidence?, params? } }
}

/**
 * POST /api/v1/voice/transcribe
 * @param {string} audioData - base64-encoded WAV
 */
async function callTranscribeApi(audioData) {
  const api = getApi();
  if (!api) throw new Error('API client not available.');

  const res = await api.post('/api/v1/voice/transcribe', { audio_data: audioData });
  if (!res || !res.ok) {
    throw new Error(res?.data?.message || res?.data?.error || 'Transcribe request failed');
  }
  return res; // { ok: true, data: { text } }
}

/* ── Parse Logic ────────────────────────────────────────────────────────── */

async function handleParse() {
  const phrase = _state.parsePhrase.trim();
  if (!phrase) return;

  _state.parseLoading = true;
  _state.parseResult = null;
  _state.parseError = null;
  if (_state.container) await renderContent();

  try {
    const result = await callParseApi(phrase);
    _state.parseResult = result;

    // Add to history
    _state.parseHistory.unshift({
      phrase,
      result,
      error: null,
      timestamp: Date.now(),
    });
    if (_state.parseHistory.length > HISTORY_MAX) {
      _state.parseHistory.length = HISTORY_MAX;
    }
  } catch (err) {
    _state.parseError = err.message || 'Parse failed';
    _state.parseResult = null;

    _state.parseHistory.unshift({
      phrase,
      result: null,
      error: _state.parseError,
      timestamp: Date.now(),
    });
    if (_state.parseHistory.length > HISTORY_MAX) {
      _state.parseHistory.length = HISTORY_MAX;
    }
  } finally {
    _state.parseLoading = false;
    if (_state.container) await renderContent();
  }
}

/* ── Transcribe Logic ───────────────────────────────────────────────────── */

async function handleTranscribe(audioData) {
  _state.transcribeLoading = true;
  _state.transcribeResult = null;
  _state.transcribeError = null;
  if (_state.container) await renderContent();

  try {
    const result = await callTranscribeApi(audioData);
    _state.transcribeResult = result;
  } catch (err) {
    _state.transcribeError = err.message || 'Transcription failed';
  } finally {
    _state.transcribeLoading = false;
    if (_state.container) await renderContent();
  }
}

function handleFileSelect(file) {
  if (!file) return;
  _state.selectedFile = file;
  _state.recordedBlob = null;

  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target.result.split(',')[1]; // remove data URL prefix
    handleTranscribe(base64);
  };
  reader.onerror = () => {
    _state.transcribeError = 'Failed to read audio file.';
    _state.container && renderContent();
  };
  reader.readAsDataURL(file);
}

function handleRecordedBlob(blob) {
  _state.recordedBlob = blob;
  _state.selectedFile = null;

  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target.result.split(',')[1];
    handleTranscribe(base64);
  };
  reader.onerror = () => {
    _state.transcribeError = 'Failed to process recording.';
    _state.container && renderContent();
  };
  reader.readAsDataURL(blob);
}

/* ── Recording ──────────────────────────────────────────────────────────── */

async function startRecording() {
  if (_state.isRecording) return;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    _state.recordingStream = stream;

    // Determine preferred audio MIME type
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/wav';

    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
    _state.mediaRecorder = recorder;
    _state.audioChunks = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        _state.audioChunks.push(e.data);
      }
    };

    recorder.onstop = () => {
      // Stop all tracks
      if (_state.recordingStream) {
        _state.recordingStream.getTracks().forEach((t) => t.stop());
        _state.recordingStream = null;
      }

      const blob = new Blob(_state.audioChunks, { type: mimeType || 'audio/webm' });
      _state.audioChunks = [];
      _state.isRecording = false;
      _state.mediaRecorder = null;

      _state.container && renderContent();

      if (blob.size > 0) {
        handleRecordedBlob(blob);
      }
    };

    recorder.onerror = () => {
      stopRecording();
      _state.transcribeError = 'Recording error occurred.';
      _state.container && renderContent();
    };

    recorder.start(250); // collect data every 250ms
    _state.isRecording = true;
    _state.container && renderContent();
  } catch (err) {
    let msg = 'Microphone access denied or unavailable.';
    if (err.name === 'NotAllowedError') {
      msg = 'Microphone permission denied. Please allow microphone access and try again.';
    } else if (err.name === 'NotFoundError') {
      msg = 'No microphone found. Please connect a microphone and try again.';
    }
    _state.transcribeError = msg;
    _state.container && renderContent();
  }
}

function stopRecording() {
  if (_state.mediaRecorder && _state.mediaRecorder.state !== 'inactive') {
    _state.mediaRecorder.stop();
  }
  if (_state.recordingStream) {
    _state.recordingStream.getTracks().forEach((t) => t.stop());
    _state.recordingStream = null;
  }
  _state.isRecording = false;
  _state.mediaRecorder = null;
  _state.container && renderContent();
}

/* ── Render ─────────────────────────────────────────────────────────────── */

async function renderContent() {
  if (_state.destroyed || !_state.container) return;

  const parseResultHTML = renderParseResult();
  const parseHistoryHTML = renderParseHistory();
  const transcribeCardHTML = renderTranscribeCard();
  const historyListHTML = renderHistoryList();

  const data = {
    parsePhrase: esc(_state.parsePhrase),
    parseDisabled: _state.parseLoading || !_state.parsePhrase.trim(),
    parseBtnIcon: _state.parseLoading ? '<span class="c-spinner c-spinner--sm">' + ICONS.refresh.html + '</span>' : ICONS.bolt.html,
    parseBtnText: _state.parseLoading ? 'Parsing&hellip;' : 'Parse',
    parseResultHTML,
    parseHistoryHTML,
    transcribeCardHTML,
    historyListHTML,
  };

  _state.container.innerHTML = await loadTemplate('voice', data);
  mountEvents();
}

/* ── Parse Result Renderer ──────────────────────────────────────────────── */

function renderParseResult() {
  if (_state.parseLoading) {
    return html`
      <div style="padding: var(--space-4); text-align: center; color: var(--text-muted); font-size: var(--font-size-sm);">
        <span class="c-spinner" style="display: inline-flex; margin-bottom: var(--space-2);">${ICONS.refresh}</span>
        <div>Parsing phrase…</div>
      </div>
    `;
  }

  if (_state.parseError) {
    return html`
      <div class="c-alert c-alert--danger" style="margin-top: var(--space-2);">
        <span class="c-alert__icon">${ICONS.error}</span>
        <span class="c-alert__content">${esc(_state.parseError)}</span>
      </div>
    `;
  }

  if (!_state.parseResult) {
    return html`
      <div style="padding: var(--space-4); text-align: center; color: var(--text-muted); font-size: var(--font-size-sm);">
        <div style="opacity: 0.4; margin-bottom: var(--space-2);">${ICONS.bolt}</div>
        <div>Type a phrase above and click Parse to see results.</div>
      </div>
    `;
  }

  const data = _state.parseResult.data || {};
  const matched = data.matched === true;
  const resultIcon = matched ? ICONS['check-circle'] : ICONS.warning;
  const resultColor = matched ? 'var(--success)' : 'var(--warning)';
  const resultBg = matched ? 'var(--success-muted)' : 'var(--warning-muted)';
  const resultLabel = matched ? 'Command Matched' : 'No Match';

  return html`
    <!-- Result indicator -->
    <div style="display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3); border-radius: var(--radius-md); background: ${resultBg}; margin-bottom: var(--space-3);">
      <div style="color: ${resultColor}; width: 20px; height: 20px; flex-shrink: 0; margin-top: 1px;">
        ${resultIcon}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: ${resultColor};">
          ${resultLabel}
        </div>
        <div style="font-size: var(--font-size-sm); color: var(--text-primary); margin-top: var(--space-1);">
          "${esc(data.text || _state.parseResult.data?.phrase || '')}"
        </div>
        ${matched ? html`
          <div style="margin-top: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--font-size-sm);">
            ${data.command ? html`
              <div>
                <span style="color: var(--text-muted);">Command:</span>
                <span style="color: var(--text-primary); font-weight: var(--font-weight-medium); margin-left: var(--space-1);">${esc(data.command)}</span>
              </div>
            ` : ''}
            ${data.confidence != null ? html`
              <div>
                <span style="color: var(--text-muted);">Confidence:</span>
                <span style="color: var(--text-primary); font-weight: var(--font-weight-medium); margin-left: var(--space-1);">${(data.confidence * 100).toFixed(1)}%</span>
              </div>
            ` : ''}
            ${data.params && Object.keys(data.params).length > 0 ? html`
              <div>
                <span style="color: var(--text-muted);">Parameters:</span>
                <span style="color: var(--text-primary); margin-left: var(--space-1); font-family: var(--font-mono); font-size: var(--font-size-xs);">${esc(JSON.stringify(data.params))}</span>
              </div>
            ` : ''}
          </div>
        ` : ''}
      </div>
    </div>

    <!-- Full JSON response (collapsible) -->
    <details style="font-size: var(--font-size-xs);">
      <summary style="cursor: pointer; color: var(--text-muted); user-select: none; padding: var(--space-1) 0;">
        Full Response
      </summary>
      <pre style="margin-top: var(--space-2); padding: var(--space-3); font-size: var(--font-size-xs); max-height: 200px; overflow: auto; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md);">${esc(JSON.stringify(_state.parseResult.data, null, 2))}</pre>
    </details>
  `;
}

/* ── Parse History Renderer (inside the parse card) ──────────────────────── */

function renderParseHistory() {
  if (_state.parseHistory.length === 0) return '';

  const items = _state.parseHistory.slice(0, 5); // show last 5

  return html`
    <div style="margin-top: var(--space-3); border-top: 1px solid var(--border-subtle); padding-top: var(--space-3);">
      <div style="font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-2);">
        Recent Parses
      </div>
      <div style="display: flex; flex-direction: column; gap: 2px;">
        ${items.map((item) => {
          const matched = item.result?.data?.matched === true;
          const icon = matched ? ICONS['check-circle'] : item.error ? ICONS.error : ICONS.warning;
          const color = matched ? 'var(--success)' : item.error ? 'var(--danger)' : 'var(--warning)';
          return html`
            <div style="display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); border-radius: var(--radius-sm); font-size: var(--font-size-xs);">
              <span style="color: ${color}; width: 14px; height: 14px; flex-shrink: 0;">${icon}</span>
              <span style="color: var(--text-primary); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${esc(item.phrase)}</span>
              <span style="color: var(--text-muted); flex-shrink: 0;">${formatTime(new Date(item.timestamp))}</span>
            </div>
          `;
        })}
      </div>
    </div>
  `;
}

/* ── Transcribe Card Renderer ───────────────────────────────────────────── */

function renderTranscribeCard() {
  // Check MediaRecorder support
  const recorderSupported = checkMediaRecorderSupport();

  return html`
    <!-- File upload -->
    <div style="margin-bottom: var(--space-3);">
      <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-bottom: var(--space-2);">
        Upload Audio File
      </div>
      <div style="display: flex; gap: var(--space-2); align-items: center;">
        <label class="c-btn c-btn--secondary" id="voice-file-label" style="cursor: pointer;">
          <span class="c-btn__icon">${ICONS.upload}</span>
          ${_state.selectedFile ? esc(_state.selectedFile.name) : 'Choose WAV File'}
          <input type="file"
                 id="voice-file-input"
                 accept=".wav,audio/wav"
                 style="display: none;">
        </label>
        ${_state.selectedFile ? html`
          <button class="c-btn c-btn--ghost c-btn--sm" id="voice-file-clear" title="Clear file">
            <span class="c-btn__icon">${ICONS.close}</span>
          </button>
        ` : ''}
      </div>
      <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: var(--space-1);">
        Supported: .wav files
      </div>
    </div>

    <!-- Divider with OR -->
    <div style="display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3);">
      <span style="flex: 1; height: 1px; background: var(--border-subtle);"></span>
      <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">or</span>
      <span style="flex: 1; height: 1px; background: var(--border-subtle);"></span>
    </div>

    <!-- Record button -->
    ${recorderSupported ? html`
      <div style="margin-bottom: var(--space-3);">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-bottom: var(--space-2);">
          Record from Microphone
        </div>
        <div style="display: flex; gap: var(--space-2); align-items: center;">
          <button class="c-btn ${_state.isRecording ? 'c-btn--danger-solid' : 'c-btn--secondary'}"
                  id="voice-record-btn"
                  ?disabled="${_state.transcribeLoading}">
            <span class="c-btn__icon">
              ${_state.isRecording ? ICONS.close : ICONS.mic || html.raw(ICONS.playCircle.html)}
            </span>
            ${_state.isRecording ? 'Stop Recording' : 'Record'}
          </button>
          ${_state.isRecording ? html`
            <span style="display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--danger);">
              <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--danger); animation: pulseSoft 1s infinite;"></span>
              Recording…
            </span>
          ` : ''}
          ${_state.recordedBlob && !_state.isRecording ? html`
            <span style="font-size: var(--font-size-xs); color: var(--text-muted);">
              Recorded ${(_state.recordedBlob.size / 1024).toFixed(0)} KB
            </span>
          ` : ''}
        </div>
      </div>
    ` : html`
      <div style="padding: var(--space-3); border-radius: var(--radius-md); background: var(--warning-muted); border: 1px solid rgba(234, 179, 8, 0.2); margin-bottom: var(--space-3);">
        <div style="display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); color: var(--warning);">
          <span style="width: 16px; height: 16px; flex-shrink: 0;">${ICONS.info}</span>
          <span>MediaRecorder is not available in this browser. File upload is the only option.</span>
        </div>
      </div>
    `}

    <!-- Transcribe result -->
    ${renderTranscribeResult()}
  `;
}

/* ── Transcribe Result Renderer ─────────────────────────────────────────── */

function renderTranscribeResult() {
  if (_state.transcribeLoading) {
    return html`
      <div style="padding: var(--space-3); text-align: center; color: var(--text-muted); font-size: var(--font-size-sm); border-top: 1px solid var(--border-subtle); padding-top: var(--space-3);">
        <span class="c-spinner" style="display: inline-flex; margin-bottom: var(--space-2);">${ICONS.refresh}</span>
        <div>Transcribing audio…</div>
      </div>
    `;
  }

  if (_state.transcribeError) {
    return html`
      <div style="border-top: 1px solid var(--border-subtle); padding-top: var(--space-3);">
        <div class="c-alert c-alert--danger">
          <span class="c-alert__icon">${ICONS.error}</span>
          <span class="c-alert__content">${esc(_state.transcribeError)}</span>
        </div>
      </div>
    `;
  }

  if (!_state.transcribeResult) {
    return '';
  }

  const text = _state.transcribeResult.data?.text || '';

  return html`
    <div style="border-top: 1px solid var(--border-subtle); padding-top: var(--space-3);">
      <div style="font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-2);">
        Transcription Result
      </div>
      <div style="display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3); border-radius: var(--radius-md); background: var(--success-muted);">
        <div style="color: var(--success); width: 20px; height: 20px; flex-shrink: 0; margin-top: 1px;">
          ${ICONS['check-circle']}
        </div>
        <div style="flex: 1; min-width: 0;">
          <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--success);">
            Transcribed
          </div>
          <div style="font-size: var(--font-size-sm); color: var(--text-primary); margin-top: var(--space-1); font-style: italic;">
            "${esc(text)}"
          </div>
        </div>
      </div>
      <!-- Full response details -->
      <details style="font-size: var(--font-size-xs); margin-top: var(--space-2);">
        <summary style="cursor: pointer; color: var(--text-muted); user-select: none; padding: var(--space-1) 0;">
          Full Response
        </summary>
        <pre style="margin-top: var(--space-2); padding: var(--space-3); font-size: var(--font-size-xs); max-height: 200px; overflow: auto; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md);">${esc(JSON.stringify(_state.transcribeResult.data, null, 2))}</pre>
      </details>
    </div>
  `;
}

/* ── History List (Bottom Section) ──────────────────────────────────────── */

function renderHistoryList() {
  if (_state.parseHistory.length === 0) {
    return html`
      <div class="c-card">
        <div class="c-card__header">
          <span class="c-card__title">Parse History</span>
        </div>
        <div class="c-card__body" style="text-align: center; padding: var(--space-8); color: var(--text-muted); font-size: var(--font-size-sm);">
          No parse history yet. Type a phrase and click Parse.
        </div>
      </div>
    `;
  }

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">Parse History</span>
        <button class="c-btn c-btn--ghost c-btn--sm" id="voice-clear-history" title="Clear history">
          <span class="c-btn__icon">${ICONS.trash}</span>
          Clear
        </button>
      </div>
      <div class="c-card__body" style="padding: var(--space-2); max-height: 400px; overflow-y: auto;">
        ${_state.parseHistory.map((item) => {
          const data = item.result?.data || {};
          const matched = data.matched === true;
          const icon = matched ? ICONS['check-circle'] : item.error ? ICONS.error : ICONS.warning;
          const color = matched ? 'var(--success)' : item.error ? 'var(--danger)' : 'var(--warning)';
          return html`
            <div style="display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3) var(--space-2); border-bottom: 1px solid var(--border-subtle);">
              <div style="color: ${color}; width: 18px; height: 18px; flex-shrink: 0; margin-top: 1px;">
                ${icon}
              </div>
              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; align-items: center; gap: var(--space-2);">
                  <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">${esc(item.phrase)}</span>
                  ${matched ? html`<span class="c-badge c-badge--success">Matched</span>` : item.error ? html`<span class="c-badge c-badge--danger">Error</span>` : html`<span class="c-badge c-badge--warning">No Match</span>`}
                </div>
                <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 2px;">
                  ${formatTime(new Date(item.timestamp))}
                  ${matched && data.command ? html`· Command: ${esc(data.command)}` : ''}
                  ${matched && data.confidence != null ? html`· ${(data.confidence * 100).toFixed(0)}%` : ''}
                  ${item.error ? html`· ${esc(item.error)}` : ''}
                </div>
              </div>
            </div>
          `;
        })}
      </div>
    </div>
  `;
}

/* ── Event Binding ──────────────────────────────────────────────────────── */

function mountEvents() {
  if (!_state.container) return;
  const c = _state.container;

  // ── Parse Input ────────────────────────────────────────────────────────
  const parseInput = c.querySelector('#voice-parse-input');
  const parseBtn = c.querySelector('#voice-parse-btn');

  if (parseInput) {
    parseInput.addEventListener('input', (e) => {
      _state.parsePhrase = e.target.value;
      // Update button disabled state
      if (parseBtn) {
        parseBtn.disabled = !_state.parsePhrase.trim() || _state.parseLoading;
      }
    });

    parseInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && _state.parsePhrase.trim() && !_state.parseLoading) {
        e.preventDefault();
        handleParse();
      }
    });
  }

  if (parseBtn) {
    parseBtn.addEventListener('click', () => handleParse());
  }

  // ── File Upload ────────────────────────────────────────────────────────
  const fileInput = c.querySelector('#voice-file-input');
  const fileClear = c.querySelector('#voice-file-clear');

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFileSelect(file);
      }
    });
  }

  if (fileClear) {
    fileClear.addEventListener('click', () => {
      _state.selectedFile = null;
      if (fileInput) fileInput.value = '';
      renderContent();
    });
  }

  // ── Recording ──────────────────────────────────────────────────────────
  const recordBtn = c.querySelector('#voice-record-btn');
  if (recordBtn) {
    recordBtn.addEventListener('click', () => {
      if (_state.isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    });
  }

  // ── Clear History ──────────────────────────────────────────────────────
  const clearHistoryBtn = c.querySelector('#voice-clear-history');
  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', () => {
      _state.parseHistory = [];
      renderContent();
    });
  }
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

/**
 * Full render — called from the router or from mount().
 * @param {Element} container
 */
export async function render(container) {
  _state.destroyed = false;
  _state.container = container;
  _state.mediaRecorderAvailable = checkMediaRecorderSupport();

  await renderContent();
}

/**
 * Cleanup — called when navigating away.
 * Stops any active recording and releases mic.
 */
export function destroy() {
  _state.destroyed = true;

  // Stop any active recording
  if (_state.isRecording) {
    if (_state.mediaRecorder && _state.mediaRecorder.state !== 'inactive') {
      try { _state.mediaRecorder.stop(); } catch (e) { /* ignore */ }
    }
    if (_state.recordingStream) {
      try { _state.recordingStream.getTracks().forEach((t) => t.stop()); } catch (e) { /* ignore */ }
    }
  }

  _state.mediaRecorder = null;
  _state.recordingStream = null;
  _state.audioChunks = [];
  _state.isRecording = false;
  _state.container = null;
}

/* ── Router-compatible default export ────────────────────────────────────── */

/**
 * Factory function for the SPA router.
 * @param {Object} _routeInfo
 * @returns {{ render: Function, mount: Function, destroy: Function }}
 */
export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="voice-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#voice-root') || container;
      await render(root);
    },
    destroy,
  };
}
