const API = localStorage.getItem('phoenix_api') || 'http://localhost:8000';
const $ = (selector) => document.querySelector(selector);
const safe = (value, fallback = '—') => value === undefined || value === null || value === '' ? fallback : value;
const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;

function log(message, level = 'INFO') {
  const node = $('#log');
  const line = `[${new Date().toLocaleTimeString()}] [${level}] ${message}`;
  node.textContent = `${line}\n${node.textContent}`.slice(0, 9000);
}

async function get(path) {
  const response = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function setText(selector, value) {
  const node = $(selector);
  if (node) node.textContent = safe(value);
}

function renderWatchlist(payload) {
  const root = $('#watchlist');
  const items = payload.items || payload.watchlist || payload || [];
  const rows = Array.isArray(items) ? items.slice(0, 10) : [];
  setText('#activeMarkets', rows.length);
  if (!rows.length) return;
  root.innerHTML = '<div class="watch-row header"><span>MARKET</span><span>REGIME</span><span>BIAS</span><span>OPPORTUNITY</span><span>RISK</span></div>' + rows.map((item) => {
    const opportunity = Math.round(Number(item.opportunity_score ?? item.opportunity ?? 0) * (Number(item.opportunity_score ?? item.opportunity ?? 0) <= 1 ? 100 : 1));
    const risk = Math.round(Number(item.risk_score ?? item.risk ?? 0) * (Number(item.risk_score ?? item.risk ?? 0) <= 1 ? 100 : 1));
    return `<div class="watch-row"><b>${safe(item.symbol, 'UNKNOWN')}</b><span>${safe(item.regime, 'unknown').toUpperCase()}</span><em>${safe(item.bias, 'neutral').toUpperCase()}</em><span><div class="bar"><i style="width:${Math.min(opportunity, 100)}%"></i></div></span><span>${risk}%</span></div>`;
  }).join('');
  const lead = rows[0];
  setText('#marketRegime', safe(lead.regime, 'SCANNING').toUpperCase());
  setText('#marketBias', `${safe(lead.symbol, 'MARKET')} · ${safe(lead.bias, 'neutral').toUpperCase()} bias`);
}

function renderTradeAnalysis(item) {
  if (!item) return;
  const confidence = Number(item.confidence || 0);
  setText('#tradeVerdict', safe(item.verdict, 'NO SETUP').toUpperCase());
  setText('#tradeConfidence', `${percent(confidence)} confidence`);
  setText('#analystSymbol', safe(item.symbol, 'No active thesis'));
  setText('#analystVerdict', safe(item.verdict, 'WAITING').toUpperCase());
  setText('#analystConfidence', percent(confidence));
  $('#confidenceRing').style.setProperty('--value', percent(confidence));
  setText('#analystDirection', safe(item.direction || item.thesis, '—').toUpperCase());
  const zone = item.entry_zone || item.entry || null;
  setText('#analystEntry', Array.isArray(zone) ? zone.join(' – ') : safe(zone));
  setText('#analystInvalidation', item.invalidation ?? item.invalidation_level);
  setText('#analystRR', item.risk_reward ?? item.first_target_rr);
}

function renderOrderflow(item) {
  if (!item) return;
  setText('#orderflowSignal', safe(item.signal, 'NEUTRAL').toUpperCase());
  setText('#orderflowQuality', `Quality ${percent(item.data_quality)} · Confidence ${percent(item.confidence)}`);
}

function renderResearch(brief, status) {
  setText('#researchEvents', status?.total_events || 0);
  if (!brief) return;
  setText('#researchHeadline', brief.headline);
  setText('#researchSummary', brief.summary);
  setText('#researchConfidence', `${percent(brief.confidence)} CONF.`);
  setText('#opportunityCount', brief.opportunities?.length || 0);
  setText('#riskCount', brief.risks?.length || 0);
  setText('#contradictionCount', brief.contradictions?.length || 0);
  $('#researchEntities').innerHTML = (brief.key_entities || []).slice(0, 8).map((entity) => `<span>${entity}</span>`).join('');
}

function renderCEOProfile(profile) {
  const salutation = profile.preferred_salutation || 'MASTER Brano';
  const heading = $('.hero-copy h2');
  if (heading) heading.innerHTML = `Welcome, ${salutation}.<br />Every mission prioritized.`;
  setText('#voiceStatus', `Ready for ${salutation}. Wake name: ${profile.assistant_name || 'PHOENIX'}`);
  log(`Personal AI CEO profile loaded for ${salutation}`, 'CEO');
}

function renderCEOBriefing(briefing) {
  if (!briefing) return;
  const focus = briefing.daily_focus || 'No critical action required';
  setText('#missionStatus', `CEO · ${briefing.top_priorities?.length || 0} PRIORITIES`);
  log(`${briefing.salutation}: daily focus — ${focus}`, 'CEO');
  (briefing.risks || []).slice(0, 3).forEach((risk) => log(`Executive risk: ${risk}`, 'RISK'));
  (briefing.approvals || []).slice(0, 3).forEach((approval) => log(`Approval required: ${approval}`, 'CONTROL'));
}

function renderRuntime(report) {
  const queued = report.queued || 0;
  const active = report.active || 0;
  const completed = report.completed || 0;
  const blocked = (report.failed || 0) + (report.dead_letter || 0);
  const total = queued + active + completed + blocked + (report.waiting_review || 0) + (report.waiting_approval || 0);
  const progress = total ? completed / total : 0;
  setText('#missionsQueued', queued);
  setText('#missionsActive', active);
  setText('#missionsCompleted', completed);
  setText('#missionsBlocked', blocked);
  setText('#missionProgress', percent(progress));
  $('#missionProgressBar').style.width = percent(progress);
  setText('#missionStatus', blocked ? 'ATTENTION' : active ? 'EXECUTING' : 'MONITORING');
}

function renderApprovals(payload) {
  const items = payload.items || payload.approvals || [];
  const pending = items.filter((item) => !item.status || ['pending', 'requested', 'waiting'].includes(String(item.status).toLowerCase()));
  setText('#pendingApprovals', pending.length);
  setText('#approvalBadge', `${pending.length} PENDING`);
  const root = $('#approvalList');
  if (!pending.length) {
    root.innerHTML = '<div class="empty-state">No pending approvals detected.</div>';
    return;
  }
  root.innerHTML = pending.slice(0, 4).map((item) => `<div class="approval-item"><div><b>${safe(item.title || item.action, 'Approval request')}</b><small>${safe(item.reason || item.description, 'Human review required')}</small></div><button data-approval="${safe(item.id, '')}">REVIEW</button></div>`).join('');
  root.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => log(`Approval ${button.dataset.approval || ''} opened for human review — no automatic action`, 'CONTROL')));
}

async function refresh() {
  $('#refreshButton').disabled = true;
  const services = [
    ['/health', (data) => setText('#coreStatus', data.status?.toUpperCase() || 'ONLINE')],
    ['/v1/personal-ceo/profile', renderCEOProfile],
    ['/v1/personal-ceo/briefings/latest', renderCEOBriefing],
    ['/v1/market-intelligence/watchlist', renderWatchlist],
    ['/v1/trade-analyst/analyses', (data) => renderTradeAnalysis((data.items || [])[0])],
    ['/v1/orderflow/snapshots', (data) => renderOrderflow((data.items || [])[0])],
    ['/v1/research-network/status', (data) => renderResearch(null, data)],
    ['/v1/research-network/brief', (data) => renderResearch(data, null)],
    ['/v1/company-runtime/report', renderRuntime],
    ['/v1/orchestrator/status', (data) => setText('#agentCount', `${data.available_agents || data.active_agents || 0} AVAILABLE`)],
    ['/v1/approvals', renderApprovals],
    ['/v1/voice/status', (data) => {
      setText('#assistantName', data.assistant_name || 'PHOENIX');
    }]
  ];
  let connected = 0;
  for (const [path, apply] of services) {
    try {
      const data = await get(path);
      apply(data);
      connected += 1;
    } catch (error) {
      if (path !== '/v1/personal-ceo/briefings/latest') log(`Service unavailable: ${path}`, 'WAIT');
    }
  }
  setText('#connectedServices', `${connected}/${services.length}`);
  setText('#systemRisk', connected >= Math.ceil(services.length * 0.7) ? 'CONTROLLED' : 'DEGRADED');
  log(`Intelligence refresh complete: ${connected}/${services.length} services connected`, 'SYNC');
  $('#refreshButton').disabled = false;
}

function updateClock() {
  setText('#clock', new Date().toLocaleTimeString([], { hour12: false }));
}

$('#refreshButton').addEventListener('click', refresh);
$('#voiceButton').addEventListener('click', () => {
  const active = document.body.classList.toggle('listening');
  setText('#voiceButton', active ? 'VOICE LINK ACTIVE' : 'ACTIVATE VOICE LINK');
  setText('#voiceBadge', active ? 'LISTENING' : 'STANDBY');
  setText('#voiceStatus', active ? 'Listening for PHOENIX commands from MASTER Brano…' : 'Voice link paused.');
  log(active ? 'Voice link activated for MASTER Brano' : 'Voice link paused', 'VOICE');
});
$('#focusButton').addEventListener('click', () => {
  const active = document.body.classList.toggle('focus');
  setText('#focusButton', active ? 'EXIT FOCUS MODE' : 'ENTER FOCUS MODE');
  log(active ? 'Executive focus mode enabled' : 'Full command view restored', 'UI');
});

setInterval(updateClock, 1000);
setInterval(refresh, 60000);
updateClock();
refresh();
