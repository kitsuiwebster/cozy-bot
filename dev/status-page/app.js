// Configuration
// Use Nginx proxy to avoid CORS issues
const STATUS_API_URL = '/api/public/status';

// Périodes d'uptime à afficher
const UPTIME_PERIODS = [
    { label: '90d', days: 90 },
    { label: '30d', days: 30 },
    { label: '7d', days: 7 },
    { label: '24h', hours: 24 },
    { label: '1h', hours: 1 }
];

// Récupérer les monitors depuis l'API Kuma
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

// Récupérer les heartbeats depuis l'API Kuma
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

// Normalize heartbeat time to milliseconds
function toTimeMs(value) {
    if (typeof value === 'number') {
        return value < 1e12 ? value * 1000 : value;
    }
    return new Date(value).getTime();
}

// Calculer l'uptime pour une période donnée
function calculateUptimeForPeriod(heartbeats, period) {
    if (!heartbeats || heartbeats.length === 0) {
        return { uptime: 0, segments: [], hasData: false };
    }

    // Définir le nombre de segments et leur durée selon la période
    let periodMs;
    let segmentDuration;
    let totalSegments;

    if (period.hours === 1) {
        // 1 heure = 30 segments de 2 minutes
        periodMs = 60 * 60 * 1000;
        segmentDuration = 2 * 60 * 1000; // 2 minutes
        totalSegments = 30;
    } else if (period.hours === 24) {
        // 24 heures = 48 segments de 30 minutes
        periodMs = 24 * 60 * 60 * 1000;
        segmentDuration = 30 * 60 * 1000; // 30 minutes
        totalSegments = 48;
    } else if (period.days === 7) {
        // 7 jours = 28 segments de 6 heures
        periodMs = 7 * 24 * 60 * 60 * 1000;
        segmentDuration = 6 * 60 * 60 * 1000; // 6 heures
        totalSegments = 28;
    } else if (period.days === 30) {
        // 30 jours = 30 segments de 1 jour
        periodMs = 30 * 24 * 60 * 60 * 1000;
        segmentDuration = 24 * 60 * 60 * 1000; // 1 jour
        totalSegments = 30;
    } else if (period.days === 90) {
        // 90 jours = 90 segments de 1 jour
        periodMs = 90 * 24 * 60 * 60 * 1000;
        segmentDuration = 24 * 60 * 60 * 1000; // 1 jour
        totalSegments = 90;
    }

    // Utiliser Date.now() pour avoir une vraie fenêtre temporelle
    const now = Date.now();
    const cutoffTime = now - periodMs;

    // Filtrer les heartbeats dans la période
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

    // Calculer la couverture de données
    relevantHeartbeats.sort((a, b) => toTimeMs(a.time) - toTimeMs(b.time));
    const oldestHeartbeat = toTimeMs(relevantHeartbeats[0].time);
    const newestHeartbeat = toTimeMs(relevantHeartbeats[relevantHeartbeats.length - 1].time);
    const actualDataSpan = newestHeartbeat - oldestHeartbeat;
    const dataCoverage = actualDataSpan / periodMs * 100;
    const hasEnoughData = dataCoverage >= 10;

    // Calculer l'uptime global
    const upCount = relevantHeartbeats.filter(hb => hb.status === 1).length;
    const uptime = (upCount / relevantHeartbeats.length) * 100;

    // Créer des segments de TEMPS FIXES
    const segments = [];

    for (let i = 0; i < totalSegments; i++) {
        // Calculer les bornes temporelles du segment (du plus récent au plus ancien)
        const segmentEnd = now - (i * segmentDuration);
        const segmentStart = segmentEnd - segmentDuration;

        // Trouver tous les heartbeats dans ce segment
        const segmentHeartbeats = relevantHeartbeats.filter(hb => {
            const time = toTimeMs(hb.time);
            return time >= segmentStart && time < segmentEnd;
        });

        let status;
        let segmentUptime = 0;

        if (segmentHeartbeats.length === 0) {
            // Pas de données pour ce segment
            status = 'unknown';
        } else {
            // Calculer l'uptime du segment
            const upInSegment = segmentHeartbeats.filter(hb => hb.status === 1).length;
            segmentUptime = (upInSegment / segmentHeartbeats.length) * 100;

            // Déterminer le statut
            if (segmentUptime >= 100) {
                status = 'up'; // Vert: 100%
            } else if (segmentUptime >= 50) {
                status = 'degraded'; // Jaune: 50-99%
            } else {
                status = 'down'; // Rouge: <50%
            }
        }

        const startTime = new Date(segmentStart);
        const endTime = new Date(segmentEnd);

        segments.unshift({ // Plus récent à gauche, plus ancien à droite
            status,
            width: 100 / totalSegments,
            startTime,
            endTime,
            uptime: segmentUptime.toFixed(1),
            heartbeatCount: segmentHeartbeats.length
        });
    }

    return { uptime: uptime.toFixed(2), segments, hasData: hasEnoughData };
}

// Déterminer le statut global
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

// Créer l'HTML pour un monitor
function createMonitorCard(monitor) {
    const card = document.createElement('div');
    card.className = 'monitor-card';

    const statusClass = monitor.active ? 'up' : 'down';
    const statusText = monitor.active ? '✓ Currently Operational' : '✗ Currently Down';

    // Afficher toujours toutes les périodes, même sans données
    var periodsToShow = UPTIME_PERIODS;

    let timelinesHTML = '';

    periodsToShow.forEach(period => {
        const { uptime, segments, hasData } = calculateUptimeForPeriod(monitor.heartbeats, period);

        // Vert si 100%, jaune si >= 90%, rouge si < 90%
        const uptimeClass = hasData
            ? (uptime >= 99.9 ? 'high' : uptime >= 90 ? 'medium' : 'low')
            : 'muted';
        const uptimeText = hasData ? `${uptime}%` : '—';

        const segmentsHTML = segments.map(seg => {
            // Formater les dates pour le tooltip (heure de Paris)
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

// Mettre à jour la page
async function updateStatus() {
    // Récupérer les monitors et les heartbeats en parallèle
    const [monitorsData, heartbeatsData] = await Promise.all([
        fetchMonitors(),
        fetchHeartbeats()
    ]);

    if (!monitorsData || !monitorsData.monitors) {
        console.error('Invalid monitors data structure from API');
        return;
    }

    if (!heartbeatsData || !heartbeatsData.points) {
        console.error('Invalid heartbeats data structure from API');
        return;
    }

    const monitors = monitorsData.monitors.map(m => ({ ...m }));

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

    // Ajouter les heartbeats à chaque monitor
    monitors.forEach(monitor => {
        monitor.heartbeats = heartbeatsByMonitor[monitor.id] || [];

        // Déterminer le statut actuel basé sur le dernier heartbeat
        if (monitor.heartbeats.length > 0) {
            const lastHeartbeat = monitor.heartbeats[monitor.heartbeats.length - 1];
            monitor.active = lastHeartbeat.status === 1;
        } else {
            monitor.active = false;
        }
    });

    // Mettre à jour le statut global
    const overallStatus = determineOverallStatus(monitors);
    const statusBadge = document.getElementById('overall-status');
    if (overallStatus.status === 'operational') {
        statusBadge.className = 'status-badge plain';
        statusBadge.innerHTML = `<span class="status-text">${overallStatus.text}</span>`;
    } else {
        statusBadge.className = `status-badge ${overallStatus.status}`;
        statusBadge.innerHTML = `<span class="status-text">${overallStatus.text}</span>`;
    }

    // Afficher les monitors
    const container = document.getElementById('monitors-container');
    container.innerHTML = '';

    if (monitors.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">No monitors configured</p>';
        return;
    }

    monitors.forEach(monitor => {
        const card = createMonitorCard(monitor);
        container.appendChild(card);
    });

    // Mettre à jour le timestamp (heure de Paris)
    const lastUpdate = document.getElementById('last-update');
    lastUpdate.textContent = new Date().toLocaleString('fr-FR', {
        timeZone: 'Europe/Paris',
        dateStyle: 'short',
        timeStyle: 'medium'
    });
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            updateStatus();
        });
    }

    // Charger les données immédiatement
    updateStatus();

    // Rafraîchir toutes les 10 secondes
    setInterval(updateStatus, 10000);
});
