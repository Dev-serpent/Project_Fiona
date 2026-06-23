/**
 * AgentConsole — Human-in-the-loop approval panel.
 * 
 * Shows agent plans awaiting human approval and execution history.
 * Uses server-sent WebSocket events for real-time updates, with
 * an initial RPC fetch to populate on load.
 */
export class AgentConsole {
    /**
     * @param {HTMLElement} container - The DOM element to render into
     * @param {import('../client.js').RpcClient} client - JSON-RPC WebSocket client
     * @param {import('../store.js').CadStore} store - Application state store
     */
    constructor(container, client, store) {
        this.container = container;
        this.client = client;
        this.store = store;
        this._pendingPlans = [];
        this._allPlans = [];
        this._activeTab = 'pending'; // 'pending' or 'history'
        this._unsubscribe = []; // Track client.on() cleanup

        this._render();
        this._fetchPlans();          // Initial load
        this._subscribeEvents();     // Real-time updates via WebSocket
    }

    /** Render the full panel UI */
    _render() {
        this.container.innerHTML = `
            <div class="agent-console">
                <div class="agent-header">
                    <h2>🤖 Agent Supervisor</h2>
                    <div class="agent-tabs">
                        <button class="agent-tab active" data-tab="pending">
                            Pending Plans <span class="badge" id="pending-count">0</span>
                        </button>
                        <button class="agent-tab" data-tab="history">History</button>
                    </div>
                </div>
                <div class="agent-content" id="agent-content">
                    ${this._renderPendingView([])}
                </div>
            </div>
        `;

        // Tab switching
        this.container.querySelectorAll('.agent-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this._activeTab = tab.dataset.tab;
                this.container.querySelectorAll('.agent-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this._refreshView();
            });
        });
    }

    /** Render the pending plans list */
    _renderPendingView(plans) {
        if (plans.length === 0) {
            return `<div class="agent-empty">No plans awaiting approval. The agent is idle.</div>`;
        }
        return plans.map(plan => this._renderPlanCard(plan)).join('');
    }

    /** Render a single plan card */
    _renderPlanCard(plan) {
        const stepsHtml = (plan.steps || []).map((step, i) => `
            <div class="plan-step">
                <div class="step-number">${i + 1}</div>
                <div class="step-content">
                    <div class="step-action">
                        <span class="risk-badge risk-${step.risk}">${step.risk}</span>
                        <code>${step.action}</code>
                        <span class="step-params">${JSON.stringify(step.params || {})}</span>
                    </div>
                    <div class="step-reasoning">${this._escapeHtml(step.reasoning || '')}</div>
                </div>
            </div>
        `).join('');

        const statusIcon = this._statusIcon(plan.status);

        return `
            <div class="plan-card ${plan.status}" data-plan-id="${plan.plan_id}">
                <div class="plan-header">
                    <span class="plan-status-icon">${statusIcon}</span>
                    <span class="plan-status-label">${plan.status}</span>
                    <span class="plan-time">${this._formatTime(plan.created_at)}</span>
                </div>
                <div class="plan-goal">${this._escapeHtml(plan.goal)}</div>
                <div class="plan-steps">${stepsHtml}</div>
                ${plan.decision_reason ? `<div class="plan-reason">Reason: ${this._escapeHtml(plan.decision_reason)}</div>` : ''}
                ${plan.result_summary ? `<div class="plan-result">${this._escapeHtml(plan.result_summary)}</div>` : ''}
                ${plan.status === 'pending' ? `
                    <div class="plan-actions">
                        <button class="btn-approve" onclick="window.__approvePlan('${plan.plan_id}')">✅ Approve</button>
                        <button class="btn-deny" onclick="window.__denyPlan('${plan.plan_id}')">❌ Deny</button>
                    </div>
                ` : ''}
            </div>
        `;
    }

    /** Render the history view */
    _renderHistoryView(plans) {
        if (plans.length === 0) {
            return `<div class="agent-empty">No plan history yet.</div>`;
        }
        return plans.map(plan => this._renderPlanCard(plan)).join('');
    }

    /** Fetch plans from server (initial load only) */
    async _fetchPlans() {
        try {
            const [pendingRes, historyRes] = await Promise.all([
                this.client.call('approval.pending', {}),
                this.client.call('approval.list', {}),
            ]);
            this._pendingPlans = pendingRes.plans || [];
            this._allPlans = historyRes.plans || [];
            this._refreshView();
        } catch (err) {
            console.warn('Failed to fetch approval plans:', err);
        }
    }

    /** Subscribe to server-sent WebSocket events for real-time updates */
    _subscribeEvents() {
        // Plan status changed (approved, denied, completed, etc.)
        const unsubPlan = this.client.on('plan_updated', (payload) => {
            this._handlePlanUpdated(payload);
        });
        this._unsubscribe.push(unsubPlan);

        // Plan was approved
        const unsubApproved = this.client.on('plan_approved', (payload) => {
            if (payload && payload.plan_id) {
                this._updateSinglePlan(payload.plan_id);
            }
        });
        this._unsubscribe.push(unsubApproved);

        // Plan was denied
        const unsubDenied = this.client.on('plan_denied', (payload) => {
            if (payload && payload.plan_id) {
                this._updateSinglePlan(payload.plan_id);
            }
        });
        this._unsubscribe.push(unsubDenied);

        // Agent thinking update (streaming thought)
        const unsubThinking = this.client.on('agent_thinking', (payload) => {
            this._handleAgentThinking(payload);
        });
        this._unsubscribe.push(unsubThinking);
    }

    /** Handle a plan_updated event from the server */
    _handlePlanUpdated(payload) {
        if (!payload) return;
        // payload may be a full plan dict or have a nested plan
        const plan = payload.plan || payload;
        if (!plan.plan_id) return;

        const planId = plan.plan_id;
        const status = plan.status || '';

        // Refresh the specific plan in our lists
        this._upsertPlan(this._pendingPlans, plan);
        this._upsertPlan(this._allPlans, plan);

        // If status changed from pending, remove from pending list
        if (status !== 'pending' && status !== '') {
            this._pendingPlans = this._pendingPlans.filter(p => p.plan_id !== planId);
        }

        this._refreshView();
    }

    /** Fetch a single plan and update local state */
    async _updateSinglePlan(planId) {
        try {
            // Re-fetch to get the full updated state
            const [pendingRes, historyRes] = await Promise.all([
                this.client.call('approval.pending', {}),
                this.client.call('approval.list', {}),
            ]);
            this._pendingPlans = pendingRes.plans || [];
            this._allPlans = historyRes.plans || [];
            this._refreshView();
        } catch (err) {
            console.warn('Failed to refresh plan:', err);
        }
    }

    /** Handle streaming agent thinking */
    _handleAgentThinking(payload) {
        if (!payload) return;
        const thought = payload.thought || payload.message || '';
        if (!thought) return;

        // Find or create the thinking display
        let thinkingEl = this.container.querySelector('.agent-thinking');
        if (!thinkingEl) {
            const content = this.container.querySelector('#agent-content');
            if (content) {
                const div = document.createElement('div');
                div.className = 'agent-thinking';
                div.innerHTML = '<h3>🧠 Agent Thinking</h3><div class="thinking-text"></div>';
                content.insertBefore(div, content.firstChild);
                thinkingEl = div;
            }
        }

        if (thinkingEl) {
            const textEl = thinkingEl.querySelector('.thinking-text');
            if (textEl) {
                textEl.textContent = thought;
            }
            // Make sure the pending tab is active if we're seeing thinking
            if (this._activeTab !== 'pending') {
                this._activeTab = 'pending';
                // Update tab UI
                this.container.querySelectorAll('.agent-tab').forEach(t => {
                    t.classList.toggle('active', t.dataset.tab === 'pending');
                });
            }
        }
    }

    /** Insert or update a plan in the given list */
    _upsertPlan(list, plan) {
        const idx = list.findIndex(p => p.plan_id === plan.plan_id);
        if (idx >= 0) {
            list[idx] = plan;
        } else {
            list.push(plan);
        }
    }

    /** Refresh the visible view based on active tab */
    _refreshView() {
        const content = this.container.querySelector('#agent-content');
        if (!content) return;

        const pendingCount = this._pendingPlans.length;
        const badge = this.container.querySelector('#pending-count');
        if (badge) badge.textContent = pendingCount;

        if (this._activeTab === 'pending') {
            content.innerHTML = this._renderPendingView(this._pendingPlans);
        } else {
            content.innerHTML = this._renderHistoryView(this._allPlans);
        }

        // Re-register global approval handlers
        // (The WebSocket event subscription handles updating the view)
        window.__approvePlan = async (planId) => {
            try {
                const result = await this.client.call('approval.approve', { plan_id: planId });
                if (!result.ok) {
                    console.warn('Approve returned not ok:', result);
                }
                // View updates automatically via plan_updated/plan_approved event
            } catch (err) {
                console.error('Approve failed:', err);
            }
        };

        window.__denyPlan = async (planId) => {
            const reason = prompt('Reason for denial (optional):');
            try {
                const result = await this.client.call('approval.deny', { plan_id: planId, reason: reason || '' });
                if (!result.ok) {
                    console.warn('Deny returned not ok:', result);
                }
                // View updates automatically via plan_updated/plan_denied event
            } catch (err) {
                console.error('Deny failed:', err);
            }
        };
    }

    // ── Helpers ──

    _statusIcon(status) {
        const icons = {
            pending: '⏳',
            approved: '✅',
            denied: '❌',
            executing: '🔄',
            completed: '✅',
            failed: '❌',
            cancelled: '🚫',
        };
        return icons[status] || '❓';
    }

    _formatTime(ts) {
        if (!ts) return '';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString();
    }

    _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /** Clean up event subscriptions on destroy */
    destroy() {
        for (const unsub of this._unsubscribe) {
            try { unsub(); } catch (e) { /* ignore */ }
        }
        this._unsubscribe = [];
    }
}
