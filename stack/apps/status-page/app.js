// Configuration
// Use Nginx proxy to avoid CORS issues
const STATUS_API_URL = '/api/status';

// Uptime periods to display
const UPTIME_PERIODS = [
    { label: '90d', days: 90 },
    { label: '30d', days: 30 },
    { label: '7d', days: 7 },
    { label: '24h', hours: 24 },
    { label: '1h', hours: 1 }
];

// Fetch monitors from the API
async function fetchMonitors() {
    try {
        const cacheBuster = Date.now();
        const response = await fetch(`${STATUS_API_URL}/monitors?t=${cacheBuster}`, {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching monitors:', error);
        return null;
    }
}

// Fetch heartbeats from the API
async function fetchHeartbeats() {
    try {
        const cacheBuster = Date.now();
        const response = await fetch(`${STATUS_API_URL}/history?window=90d&t=${cacheBuster}`, {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching heartbeats:', error);
        return null;
    }
}

async function fetchMaintenance() {
    try {
        const cacheBuster = Date.now();
        const response = await fetch(`${STATUS_API_URL}/maintenance?t=${cacheBuster}`, {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching maintenance:', error);
        return null;
    }
}

// Normalize heartbeat time to milliseconds
function toTimeMs(value) {
    if (typeof value === 'number') {
        return value < 1e12 ? value * 1000 : value;
    }
    return new Date(value).getTime();
}

// Calculate uptime for a given period
function calculateUptimeForPeriod(heartbeats, period, maintenanceRanges) {
    if (!heartbeats || heartbeats.length === 0) {
        return { uptime: 0, segments: [], hasData: false };
    }

    // Define the number of segments and their duration based on the period
    let periodMs;
    let segmentDuration;
    let totalSegments;

    if (period.hours === 1) {
        // 1 hour = 30 segments of 2 minutes
        periodMs = 60 * 60 * 1000;
        // 2 minutes
        segmentDuration = 2 * 60 * 1000;
        totalSegments = 30;
    } else if (period.hours === 24) {
        // 24 hours = 48 segments of 30 minutes
        periodMs = 24 * 60 * 60 * 1000;
        // 30 minutes
        segmentDuration = 30 * 60 * 1000;
        totalSegments = 48;
    } else if (period.days === 7) {
        // 7 days = 28 segments of 6 hours
        periodMs = 7 * 24 * 60 * 60 * 1000;
        // 6 hours
        segmentDuration = 6 * 60 * 60 * 1000;
        totalSegments = 28;
    } else if (period.days === 30) {
        // 30 days = 30 segments of 1 day
        periodMs = 30 * 24 * 60 * 60 * 1000;
        // 1 day
        segmentDuration = 24 * 60 * 60 * 1000;
        totalSegments = 30;
    } else if (period.days === 90) {
        // 90 days = 90 segments of 1 day
        periodMs = 90 * 24 * 60 * 60 * 1000;
        // 1 day
        segmentDuration = 24 * 60 * 60 * 1000;
        totalSegments = 90;
    }

    // Use Date.now() for a real time window
    const now = Date.now();
    const cutoffTime = now - periodMs;

    // Filter heartbeats within the period
    const relevantHeartbeats = heartbeats.filter(hb => {
        const time = toTimeMs(hb.time);
        return time >= cutoffTime && time <= now;
    });

    if (relevantHeartbeats.length === 0) {
        const segments = [];
        for (let i = 0; i < totalSegments; i++) {
            const segmentEnd = now - (i * segmentDuration);
            const segmentStart = segmentEnd - segmentDuration;
            segments.unshift({
                status: 'unknown',
                width: 100 / totalSegments,
                startTime: new Date(segmentStart),
                endTime: new Date(segmentEnd),
                uptime: '0.0',
                heartbeatCount: 0
            });
        }
        return { uptime: 0, segments, hasData: false };
    }

    // Calculate data coverage
    relevantHeartbeats.sort((a, b) => toTimeMs(a.time) - toTimeMs(b.time));
    const oldestHeartbeat = toTimeMs(relevantHeartbeats[0].time);
    const newestHeartbeat = toTimeMs(relevantHeartbeats[relevantHeartbeats.length - 1].time);
    const actualDataSpan = newestHeartbeat - oldestHeartbeat;
    const dataCoverage = actualDataSpan / periodMs * 100;
    const hasEnoughData = dataCoverage >= 10;

    // Create fixed time segments
    const segments = [];

    for (let i = 0; i < totalSegments; i++) {
        // Calculate segment time boundaries (from most recent to oldest)
        const segmentEnd = now - (i * segmentDuration);
        const segmentStart = segmentEnd - segmentDuration;

        // Find all heartbeats in this segment
        const segmentHeartbeats = relevantHeartbeats.filter(hb => {
            const time = toTimeMs(hb.time);
            return time >= segmentStart && time < segmentEnd;
        });

        let status;
        let segmentUptime = 0;
        const maintenanceOverlap = (maintenanceRanges || []).some(range => {
            return segmentStart < range.end && segmentEnd > range.start;
        });

        if (maintenanceOverlap) {
            status = 'maintenance';
        } else if (segmentHeartbeats.length === 0) {
            status = 'unknown';
        } else {
            // Calculate segment uptime
            const upInSegment = segmentHeartbeats.filter(hb => hb.status === 1).length;
            segmentUptime = (upInSegment / segmentHeartbeats.length) * 100;

            // Determine status
            if (segmentUptime >= 100) {
                // Green: 100%
                status = 'up';
            } else if (segmentUptime >= 50) {
                // Yellow: 50-99%
                status = 'degraded';
            } else {
                // Red: <50%
                status = 'down';
            }
        }

        const startTime = new Date(segmentStart);
        const endTime = new Date(segmentEnd);

        // Most recent on left, oldest on right
        segments.unshift({
            status,
            width: 100 / totalSegments,
            startTime,
            endTime,
            uptime: segmentUptime.toFixed(1),
            heartbeatCount: segmentHeartbeats.length
        });
    }

    // Calculate overall uptime (maintenance counts as up)
    let uptime = 0;
    let consideredSegments = 0;
    segments.forEach(seg => {
        if (seg.status === 'unknown') {
            return;
        }
        consideredSegments += 1;
        uptime += Number.parseFloat(seg.uptime);
    });

    const uptimeValue = consideredSegments > 0 ? (uptime / consideredSegments) : 0;

    return { uptime: uptimeValue.toFixed(2), segments, hasData: hasEnoughData };
}

// Determine overall status
function determineOverallStatus(monitors) {
    if (!monitors || monitors.length === 0) {
        return { status: 'loading', text: 'Loading...', icon: '⏳' };
    }

    const allUp = monitors.every(m => m.active);
    const someDown = monitors.some(m => !m.active);

    if (allUp) {
        return { status: 'operational', text: 'All Systems Operational', icon: '✓' };
    } else if (someDown) {
        const downCount = monitors.filter(m => !m.active).length;
        return { status: 'down', text: `${downCount} Service${downCount > 1 ? 's' : ''} Down`, icon: '✗' };
    } else {
        return { status: 'degraded', text: 'Degraded Performance', icon: '!' };
    }
}

// Create HTML for a monitor
function createMonitorCard(monitor, maintenanceActive, maintenanceRanges) {
    const card = document.createElement('div');
    card.className = 'monitor-card';

    let statusClass;
    let statusText;

    if (maintenanceActive) {
        statusClass = 'maintenance';
        statusText = 'Maintenance in progress';
    } else if (monitor.active) {
        statusClass = 'up';
        statusText = 'Currently Operational';
    } else {
        statusClass = 'down';
        statusText = 'Currently Down';
    }

    // Always display all periods, even without data
    const periodsToShow = UPTIME_PERIODS;

    let timelinesHTML = '';

    periodsToShow.forEach(period => {
        const { uptime, segments, hasData } = calculateUptimeForPeriod(monitor.heartbeats, period, maintenanceRanges);

        // Green if 100%, yellow if >= 90%, red if < 90%
        let uptimeClass;
        if (!hasData) {
            uptimeClass = 'muted';
        } else if (uptime >= 99.9) {
            uptimeClass = 'high';
        } else if (uptime >= 90) {
            uptimeClass = 'medium';
        } else {
            uptimeClass = 'low';
        }

        const uptimeText = hasData ? `${uptime}%` : '—';

        const segmentsHTML = segments.map(seg => {
            // Format dates for tooltip (Paris time)
            const startStr = seg.startTime.toLocaleString('fr-FR', {
                timeZone: 'Europe/Paris',
                day: '2-digit',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            });
            const endStr = seg.endTime.toLocaleString('fr-FR', {
                timeZone: 'Europe/Paris',
                hour: '2-digit',
                minute: '2-digit'
            });

            let tooltipText;
            if (seg.status === 'unknown') {
                tooltipText = `${startStr} - ${endStr}\nNo data`;
            } else {
                tooltipText = `${startStr} - ${endStr}\nUptime: ${seg.uptime}%\n(${seg.heartbeatCount} checks)`;
            }

            return `<div class="timeline-segment ${seg.status}" style="width: ${seg.width}%" data-tooltip="${tooltipText}"></div>`;
        }).join('');

        timelinesHTML += `
            <div class="timeline-row">
                <div class="timeline-label">${period.label}</div>
                <div class="timeline-bar">${segmentsHTML}</div>
                <div class="timeline-uptime ${uptimeClass}">${uptimeText}</div>
            </div>
        `;
    });

    card.innerHTML = `
        <div class="monitor-header">
            <div class="monitor-name">
                <span>${monitor.active ? '🟢' : '🔴'}</span>
                <span>${monitor.name}</span>
            </div>
            <div class="monitor-status ${statusClass}">${statusText}</div>
        </div>
        <div class="timeline">
            ${timelinesHTML}
        </div>
    `;

    return card;
}

function renderMaintenance(maintenanceData) {
    const activeContainer = document.getElementById('maintenance-container');
    const historyContainer = document.getElementById('maintenance-history-container');
    if (!activeContainer || !historyContainer) return;

    activeContainer.innerHTML = '';
    historyContainer.innerHTML = '';
    if (!maintenanceData) {
        return { hasActive: false };
    }

    const activeItems = (maintenanceData.active || []).filter(Boolean);
    const inactiveItems = (maintenanceData.history || []).filter(Boolean);

    if (activeItems.length > 0) {
        activeItems.forEach(item => {
            const card = document.createElement('div');
            card.className = 'maintenance-card active';
            const startedAt = item.started_at ? new Date(item.started_at).toLocaleString('en-GB', {
                timeZone: 'Europe/Paris',
                dateStyle: 'medium',
                timeStyle: 'short'
            }) : null;
            card.innerHTML = `
                <div class="maintenance-header">⚠️ Maintenance in progress</div>
                <div class="maintenance-title">${item.title || 'Scheduled maintenance'}</div>
                ${startedAt ? `<div class="maintenance-meta">Started ${startedAt} (Paris)</div>` : ''}
                <div class="maintenance-description">${item.description || ''}</div>
            `;
            activeContainer.appendChild(card);
        });
    }

    if (inactiveItems.length > 0) {
        const title = document.createElement('div');
        title.className = 'maintenance-history-title';
        title.textContent = 'Maintenance history';
        historyContainer.appendChild(title);

        inactiveItems.forEach(item => {
            const card = document.createElement('div');
            card.className = 'maintenance-card history';
            const statusText = item.status ? item.status.replaceAll('-', ' ') : 'completed';
            const startedAt = item.started_at ? new Date(item.started_at).toLocaleString('en-GB', {
                timeZone: 'Europe/Paris',
                dateStyle: 'medium',
                timeStyle: 'short'
            }) : null;
            const endedAt = item.ended_at ? new Date(item.ended_at).toLocaleString('en-GB', {
                timeZone: 'Europe/Paris',
                dateStyle: 'medium',
                timeStyle: 'short'
            }) : null;

            let rangeText = '';
            if (startedAt && endedAt) {
                rangeText = `Started ${startedAt} • Ended ${endedAt} (Paris)`;
            } else if (startedAt) {
                rangeText = `Started ${startedAt} (Paris)`;
            } else if (endedAt) {
                rangeText = `Ended ${endedAt} (Paris)`;
            }

            card.innerHTML = `
                <div class="maintenance-row">
                    <div class="maintenance-title">${item.title || 'Scheduled maintenance'}</div>
                    <div class="maintenance-status">${statusText}</div>
                </div>
                ${rangeText ? `<div class="maintenance-meta">${rangeText}</div>` : ''}
                <div class="maintenance-description">${item.description || ''}</div>
            `;
            historyContainer.appendChild(card);
        });
    }

    return { hasActive: activeItems.length > 0 };
}

// Update the page
async function updateStatus() {
    // Fetch monitors and heartbeats in parallel
    const [monitorsData, heartbeatsData, maintenanceData] = await Promise.all([
        fetchMonitors(),
        fetchHeartbeats(),
        fetchMaintenance()
    ]);

    if (!monitorsData || !monitorsData.monitors) {
        console.error('Invalid monitors data structure from API');
        return;
    }

    if (!heartbeatsData || !heartbeatsData.points) {
        console.error('Invalid heartbeats data structure from API');
        return;
    }

    const maintenanceState = renderMaintenance(maintenanceData);
    const maintenanceRanges = [];

    if (maintenanceData) {
        const maintenanceItems = (maintenanceData.active || []).concat(maintenanceData.history || []);
        maintenanceItems.forEach(item => {
            if (!item || !item.started_at) {
                return;
            }
            const start = toTimeMs(item.started_at);
            const end = item.ended_at ? toTimeMs(item.ended_at) : Date.now();
            if (Number.isFinite(start) && Number.isFinite(end) && end >= start) {
                maintenanceRanges.push({ start, end });
            }
        });
    }

    const monitors = monitorsData.monitors.map(m => ({ ...m })).map(m => {
        if (m.id === 'live-bot') {
            return { ...m, name: 'Bot (Live API)' };
        }
        return m;
    });

    const heartbeatsByMonitor = {};
    heartbeatsData.points.forEach(point => {
        const ts = point.timestamp_ms;
        (point.checks || []).forEach(check => {
            if (!heartbeatsByMonitor[check.id]) {
                heartbeatsByMonitor[check.id] = [];
            }
            heartbeatsByMonitor[check.id].push({
                time: ts,
                status: check.up ? 1 : 0
            });
        });
    });

    // Add heartbeats to each monitor
    monitors.forEach(monitor => {
        monitor.heartbeats = heartbeatsByMonitor[monitor.id] || [];

        // Determine current status based on last heartbeat
        if (monitor.heartbeats.length > 0) {
            const lastHeartbeat = monitor.heartbeats[monitor.heartbeats.length - 1];
            monitor.active = lastHeartbeat.status === 1;
        } else {
            monitor.active = false;
        }
    });

    // Update overall status
    const overallStatus = determineOverallStatus(monitors);
    const statusBadge = document.getElementById('overall-status');
    if (maintenanceState.hasActive) {
        statusBadge.className = 'status-badge plain maintenance-text';
        statusBadge.innerHTML = `<span class="status-text">Maintenance in progress</span>`;
    } else if (overallStatus.status === 'operational') {
        statusBadge.className = 'status-badge plain';
        statusBadge.innerHTML = `<span class="status-text">${overallStatus.text}</span>`;
    } else {
        statusBadge.className = `status-badge ${overallStatus.status}`;
        statusBadge.innerHTML = `<span class="status-text">${overallStatus.text}</span>`;
    }

    const monitorOrder = ['live-bot', 'public-api', 'db'];
    monitors.sort((a, b) => {
        const ai = monitorOrder.indexOf(a.id);
        const bi = monitorOrder.indexOf(b.id);
        const aRank = ai === -1 ? Number.MAX_SAFE_INTEGER : ai;
        const bRank = bi === -1 ? Number.MAX_SAFE_INTEGER : bi;
        if (aRank !== bRank) {
            return aRank - bRank;
        }
        return a.name.localeCompare(b.name);
    });

    // Display monitors
    const container = document.getElementById('monitors-container');
    container.innerHTML = '';

    if (monitors.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">No monitors configured</p>';
        return;
    }

    monitors.forEach(monitor => {
        const card = createMonitorCard(monitor, maintenanceState.hasActive, maintenanceRanges);
        container.appendChild(card);
    });

    // Update timestamp (Paris time)
    const lastUpdate = document.getElementById('last-update');
    lastUpdate.textContent = new Date().toLocaleString('fr-FR', {
        timeZone: 'Europe/Paris',
        dateStyle: 'short',
        timeStyle: 'medium'
    });
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            updateStatus();
        });
    }

    // Load data immediately
    updateStatus();

    // Refresh every 10 seconds
    setInterval(updateStatus, 10000);
});
