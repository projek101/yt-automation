// main.js - Frontend JavaScript for CLIPPER Dashboard

const API_BASE = ''; // Same origin

// Helper function for fetch
async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
}

// Refresh status display
async function refreshStatus() {
    try {
        const data = await fetchJSON('/status');
        
        // Update counts
        document.getElementById('pending-count').textContent = data.pending || 0;
        document.getElementById('in-progress-count').textContent = data.in_progress || 0;
        document.getElementById('done-count').textContent = data.done || 0;
        document.getElementById('failed-count').textContent = data.failed || 0;
        document.getElementById('total-count').textContent = data.total || 0;
        
        // Show next link
        const nextLinkEl = document.getElementById('next-link');
        if (data.next_link) {
            nextLinkEl.innerHTML = `<strong>Next:</strong> ${data.next_link.title || 'Untitled'}<br><small>${data.next_link.link}</small>`;
        } else {
            nextLinkEl.textContent = data.pending > 0 ? '' : 'No pending links';
        }
        
    } catch (e) {
        console.error('Status error:', e);
    }
}

// Refresh logs display
async function refreshLogs() {
    try {
        const data = await fetchJSON('/logs?lines=100');
        document.getElementById('log-output').textContent = data.logs || '(empty)';
        // Auto-scroll to bottom
        const logOutput = document.getElementById('log-output');
        logOutput.scrollTop = logOutput.scrollHeight;
    } catch (e) {
        document.getElementById('log-output').textContent = 'Error loading logs: ' + e.message;
    }
}

// Sync with GitHub
async function syncNow() {
    try {
        const data = await fetchJSON('/sync', { method: 'POST' });
        alert(`Sync complete!\nAdded: ${data.added} links\nTotal: ${data.total}`);
        refreshStatus();
    } catch (e) {
        alert('Sync failed: ' + e.message);
    }
}

// Start job
async function startJob() {
    try {
        const data = await fetchJSON('/start-job', { method: 'POST' });
        alert(`Job started (PID: ${data.pid})`);
        refreshStatus();
    } catch (e) {
        alert('Start job failed: ' + e.message);
    }
}

// Stop job
async function stopJob() {
    try {
        const data = await fetchJSON('/stop-job', { method: 'POST' });
        alert('Stop signal sent');
    } catch (e) {
        alert('Stop failed: ' + e.message);
    }
}

// Reset all statuses
async function resetStatus() {
    if (!confirm('Reset all statuses to 0? This will mark all videos as pending again.')) {
        return;
    }
    try {
        const data = await fetchJSON('/reset', { method: 'POST' });
        alert('All statuses reset to 0');
        refreshStatus();
    } catch (e) {
        alert('Reset failed: ' + e.message);
    }
}

// Initial load and auto-refresh
document.addEventListener('DOMContentLoaded', () => {
    refreshStatus();
    refreshLogs();
    
    // Auto-refresh every 10 seconds
    setInterval(refreshStatus, 10000);
    setInterval(refreshLogs, 10000);
});
