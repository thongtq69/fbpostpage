let currentTab = 'dashboard';
let logInterval = null;

async function switchTab(tabId) {
    document.querySelectorAll('.animate-fade').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    document.getElementById(`tab-${tabId}`).style.display = 'block';
    event.currentTarget.classList.add('active');

    const titles = {
        'dashboard': 'Tổng quan',
        'config': 'Cấu hình hệ thống',
        'logs': 'Nhật ký chi tiết'
    };
    document.getElementById('page-title').innerText = titles[tabId];
    currentTab = tabId;

    if (tabId === 'config') {
        loadConfig();
    }
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        document.getElementById('cfg-email').value = config.email || '';
        document.getElementById('cfg-password').value = config.password || '';
        document.getElementById('cfg-group-urls').value = (config.group_urls || []).join('\n') || config.group_url || '';
        document.getElementById('cfg-page-url').value = config.page_url || '';
        document.getElementById('cfg-content').value = config.post_content || '';

        // Intervals
        document.getElementById('cfg-between-min').value = config.between_groups_min || 60;
        document.getElementById('cfg-between-max').value = config.between_groups_max || 180;

        // Convert seconds to minutes for UI
        document.getElementById('cfg-loop-min').value = Math.floor((config.loop_rest_min || 3600) / 60);
        document.getElementById('cfg-loop-max').value = Math.floor((config.loop_rest_max || 7200) / 60);

    } catch (err) {
        console.error('Failed to load config', err);
    }
}

async function saveConfig(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const data = Object.from_iterable(formData.entries());

    // Convert strings to arrays/numbers
    data.group_urls = data.group_urls.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    data.between_groups_min = parseInt(data.between_groups_min) || 60;
    data.between_groups_max = parseInt(data.between_groups_max) || 180;

    // Minutes to Seconds
    data.loop_rest_min = (parseInt(data.loop_rest_min) || 60) * 60;
    data.loop_rest_max = (parseInt(data.loop_rest_max) || 120) * 60;

    data.min_delay = 1; // Legacy defaults
    data.max_delay = 3;

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (response.ok) {
            alert('Cấu hình đã được lưu!');
        }
    } catch (err) {
        alert('Lỗi khi lưu cấu hình');
    }
}

// Fixed Object.from_iterable for compatibility
if (!Object.from_iterable) {
    Object.from_iterable = function (iter) {
        const obj = {};
        for (const [k, v] of iter) {
            obj[k] = v;
        }
        return obj;
    };
}

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        const badge = document.getElementById('bot-status-badge');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const connBadge = document.getElementById('connection-status');

        connBadge.className = 'status-badge status-online';
        connBadge.innerText = 'Đã kết nối';

        if (data.running) {
            badge.className = 'status-badge status-online';
            badge.innerText = 'Đang chạy';
            startBtn.style.display = 'none';
            stopBtn.style.display = 'flex';
        } else {
            badge.className = 'status-badge status-offline';
            badge.innerText = 'Dừng';
            startBtn.style.display = 'flex';
            stopBtn.style.display = 'none';
        }

        document.getElementById('img-count').innerText = data.image_count || 0;
    } catch (err) {
        document.getElementById('connection-status').className = 'status-badge status-offline';
        document.getElementById('connection-status').innerText = 'Mất kết nối';
    }
}

async function toggleBot() {
    const isStarting = document.getElementById('start-btn').style.display !== 'none';
    const endpoint = isStarting ? '/api/start' : '/api/stop';

    try {
        await fetch(endpoint, { method: 'POST' });
        setTimeout(updateStatus, 1000);
    } catch (err) {
        alert('Lỗi khi điều khiển Bot');
    }
}

async function fetchLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();
        const viewer = document.getElementById('log-viewer');

        // Only update if changes
        if (viewer.dataset.lastLog !== data.logs) {
            viewer.innerHTML = data.logs.split('\n').map(line => {
                let type = 'info';
                if (line.includes('ERROR')) type = 'error';
                if (line.includes('WARNING')) type = 'warning';

                // Colorize timestamp
                const parts = line.split(' - ');
                if (parts.length >= 3) {
                    return `<div class="log-entry"><span class="log-timestamp">${parts[0]}</span><span class="log-${type}">${parts[1]}</span> - ${parts.slice(2).join(' - ')}</div>`;
                }
                return `<div class="log-entry ${type}">${line}</div>`;
            }).join('');

            viewer.dataset.lastLog = data.logs;
            viewer.scrollTop = viewer.scrollHeight;
        }
    } catch (err) {
        console.error('Failed to fetch logs');
    }
}

// Initialization
setInterval(updateStatus, 3000);
setInterval(fetchLogs, 2000);
updateStatus();
fetchLogs();
