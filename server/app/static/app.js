async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
}

async function initCharts() {
    const statusEl = document.getElementById('chart-status');
    const throughputEl = document.getElementById('chart-throughput');
    if (!statusEl && !throughputEl) return;

    try {
        if (statusEl) {
            const rows = await fetchJSON('/api/dashboard');
            const labels = rows.map((r) => r.topic_name);
            new Chart(statusEl, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        { label: 'pending', data: rows.map((r) => r.pending), backgroundColor: '#94a3b8' },
                        { label: 'claimed', data: rows.map((r) => r.claimed), backgroundColor: '#f59e0b' },
                        { label: 'delivered', data: rows.map((r) => r.delivered), backgroundColor: '#22c55e' },
                        { label: 'dead', data: rows.map((r) => r.dead), backgroundColor: '#ef4444' },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { x: { stacked: true }, y: { stacked: true } },
                },
            });
        }

        if (throughputEl) {
            const rows = await fetchJSON('/api/throughput');
            const minutes = [...new Set(rows.map((r) => r.minute_ts))].sort();
            const topics = [...new Set(rows.map((r) => r.topic_name))].sort();
            const palette = ['#2563eb', '#16a34a', '#f59e0b', '#a855f7', '#ef4444'];
            new Chart(throughputEl, {
                type: 'line',
                data: {
                    labels: minutes.map((m) => m.slice(11, 16)),
                    datasets: topics.map((t, i) => ({
                        label: t,
                        borderColor: palette[i % palette.length],
                        backgroundColor: palette[i % palette.length],
                        pointRadius: 0,
                        tension: 0.3,
                        data: minutes.map(
                            (m) => rows.find((r) => r.topic_name === t && r.minute_ts === m)?.messages ?? 0
                        ),
                    })),
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: { y: { beginAtZero: true } },
                },
            });
        }
    } catch (e) {
        console.error('chart init failed', e);
    }
}

document.addEventListener('alpine:init', () => {
    Alpine.data('playground', () => ({
        mode: document.body.dataset.mode || 'app',
        topics: [],
        groups: [],
        pTopic: '',
        pKey: '',
        pPayload: '{\n  "event": "created",\n  "order_id": 1\n}',
        pResult: null,
        pError: null,
        cTopic: '',
        cGroup: '',
        cBatch: 10,
        claimed: [],
        cError: null,
        cInfo: null,

        async init() {
            try {
                if (this.mode === 'app') {
                    const me = await fetchJSON('/api/me');
                    this.topics = me.accessible_topics;
                    this.groups = await fetchJSON('/api/my-groups');
                }
            } catch (e) {
                console.error('playground init failed', e);
            }
        },

        get produceTopics() {
            return this.topics.filter((t) => t.access_type === 'produce');
        },
        get consumeTopics() {
            return this.topics.filter((t) => t.access_type === 'consume');
        },

        async produce() {
            this.pError = null;
            this.pResult = null;
            let payload;
            try {
                payload = JSON.parse(this.pPayload);
            } catch (e) {
                this.pError = 'payload is not valid JSON';
                return;
            }
            try {
                const res = await fetch('/api/produce', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic: this.pTopic,
                        key: this.pKey || null,
                        payload,
                        seq: Date.now(),
                    }),
                });
                const body = await res.json();
                if (!res.ok) {
                    this.pError = body.message || body.detail || 'produce failed';
                } else {
                    this.pResult = body;
                }
            } catch (e) {
                this.pError = 'request failed: ' + e.message;
            }
        },

        async consume() {
            this.cError = null;
            this.cInfo = null;
            try {
                const res = await fetch('/api/consume', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        group: this.cGroup,
                        topic: this.cTopic,
                        batch: Number(this.cBatch) || 10,
                        visibility_timeout_s: 120,
                    }),
                });
                const body = await res.json();
                if (!res.ok) {
                    this.cError = body.message || body.detail || 'consume failed';
                } else {
                    this.claimed = body.messages;
                    if (!this.claimed.length) this.cInfo = 'no pending messages right now';
                }
            } catch (e) {
                this.cError = 'request failed: ' + e.message;
            }
        },

        async ackOne(m) {
            await this._settle('/api/ack', [m.location], 'acknowledged');
            this.claimed = this.claimed.filter((x) => x !== m);
        },

        async nackOne(m) {
            await this._settle('/api/nack', [m.location], 'nacked');
            this.claimed = this.claimed.filter((x) => x !== m);
        },

        async ackAll() {
            const locs = this.claimed.map((m) => m.location);
            await this._settle('/api/ack', locs, `acknowledged ${locs.length}`);
            this.claimed = [];
        },

        async _settle(url, locations, verb) {
            this.cError = null;
            this.cInfo = null;
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ group: this.cGroup, locations, reason: 'playground nack' }),
                });
                const body = await res.json();
                if (!res.ok) {
                    this.cError = body.message || body.detail || 'failed';
                } else {
                    this.cInfo = verb;
                }
            } catch (e) {
                this.cError = 'request failed: ' + e.message;
            }
        },
    }));
});

document.addEventListener('DOMContentLoaded', initCharts);
