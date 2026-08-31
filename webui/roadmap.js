// Optional roadmap controls kept separate from the legacy-compatible renderer.
(function () {
  const previousEvent = window.__appEvent;
  window.__appEvent = event => {
    previousEvent?.(event);
    if (event?.event !== 'destination_import_requested') return;
    page = 'servers';
    render();
    setTimeout(() => {
      const input = document.querySelector('#destinationInput');
      if (input) input.value = event.data?.raw || '';
      window.toast?.('Destination received. Preview it before importing.');
    }, 0);
  };
  function enhance() {
    const start = document.querySelector('#start');
    if (!start || document.querySelector('#watch')) return;
    const watch = document.createElement('button');
    watch.id = 'watch'; watch.className = 'button'; watch.textContent = 'Watch for a slot';
    watch.disabled = start.disabled;
    start.parentElement.insertBefore(watch, start.nextSibling);
    watch.addEventListener('click', async () => {
      const type = document.querySelector('#targetType')?.value || 'server';
      const id = document.querySelector('#targetSelect')?.value;
      if (!id) return;
      const result = await window.call('start_watch', id, type);
      if (result?.ok) window.toast('Watching for an available slot. SCP:SL will not be focused until one is found.');
    });
  }
  function addRoadmapTools() {
    if (document.querySelector('h1')?.textContent === 'Text Packs' && !document.querySelector('#packUpdateTools')) {
      const panel = document.createElement('section'); panel.className = 'panel'; panel.id = 'packUpdateTools';
      panel.innerHTML = '<div class="section-heading"><h2>Pack updates</h2><p>Updates are checked and installed only when you request them. Existing files are backed up first.</p></div><button class="button" id="checkPackUpdates">Check for updates</button><div id="packUpdateResults" role="status"></div>';
      document.querySelector('.layout')?.appendChild(panel);
      $('#checkPackUpdates').onclick = async () => { const result = await window.call('check_translation_updates'); const items = result?.updates || []; $('#packUpdateResults').innerHTML = items.length ? items.map(item => `<div class="table-item"><span><strong>${esc(item.name || 'Pack update available')}</strong><small>${esc(item.revision || '')}</small></span><button class="button" data-pack-update="${esc(item.id)}">Install update</button></div>`).join('') : '<p class="technical-note">No user-initiated updates are available.</p>'; document.querySelectorAll('[data-pack-update]').forEach(button => button.onclick = async () => { const updated = await window.call('update_translation_pack', button.dataset.packUpdate); if (updated?.ok) { window.toast('Translation pack updated and backed up.'); render(); } else window.toast(updated?.error || 'Pack update failed'); }); };
    }
    if (document.querySelector('.settings-page') && !document.querySelector('#roadmapSettings')) {
      const panel = document.createElement('section');
      panel.className = 'settings-section panel'; panel.id = 'roadmapSettings';
      panel.innerHTML = '<div class="section-heading"><h2>Background services</h2><p>Optional tools run locally and stay disabled until you enable them.</p></div>' +
        '<div class="setting-row" id="backgroundMonitor"><div><strong>Background server monitoring</strong><small>Check enabled servers periodically and build local history.</small></div><button class="button" id="toggleMonitor">Start monitoring</button></div>' +
        '<div class="setting-row" id="discordPresence"><div><strong>Discord Rich Presence</strong><small>Optional and local. Discord never affects app startup, watching, or joining.</small></div><label class="toggle-row"><span>Enable</span><input type="checkbox" id="toggleDiscord"></label></div>' +
        '<div class="setting-row" id="discordApplication"><div><strong>Discord application</strong><small>Paste your public Application ID and upload the purple S mark as <code>scpsl-autojoin-s</code>. Never paste a client secret or bot token.</small><div class="actions"><input class="input" id="discordApplicationId" inputmode="numeric" placeholder="Discord Application ID"><button class="button" id="saveDiscordApplicationId">Save ID</button></div><small id="discordApplicationStatus" role="status">Checking Discord status…</small></div></div>' +
        '<div class="setting-row" id="discordPlayerSharing"><div><strong>Share player counts</strong><small>Also enable “Share this destination” in its server profile. Names and Join requests stay private until then.</small></div><label class="toggle-row"><span>Share</span><input type="checkbox" id="toggleDiscordPlayers"></label></div>';
      document.querySelector('.settings-page').appendChild(panel);
      $('#toggleMonitor').onclick = async () => { const result = await window.call('start_background_monitor'); if (!result?.ok) window.toast(result?.error || 'Monitoring could not start'); else { $('#toggleMonitor').textContent = 'Monitoring active'; $('#toggleMonitor').disabled = true; } };
      $('#toggleDiscord').onchange = async event => { const result = await window.call('set_discord_enabled', event.target.checked); if (!result?.ok) event.target.checked = !event.target.checked; };
      $('#discordApplicationId').value = state.settings?.discord_application_id || '';
      $('#saveDiscordApplicationId').onclick = async () => { const result = await window.call('set_discord_application_id', $('#discordApplicationId').value.trim()); $('#discordApplicationStatus').textContent = result?.ok ? (result.configured ? 'Discord application saved. Restart Discord if it is already open.' : 'Discord application ID cleared.') : (result?.error || 'Could not save Discord application ID.'); };
      window.call('get_discord_status').then(status => { const host = $('#discordApplicationStatus'); if (!host) return; host.textContent = !status?.enabled ? 'Discord presence is off.' : !status?.configured ? 'Add a public Application ID to enable Rich Presence.' : status?.connected ? 'Discord Rich Presence connected.' : 'Discord is not running or unavailable. The app will continue normally.'; });
      $('#toggleDiscordPlayers').checked = !!state.settings?.discord_share_players;
      $('#toggleDiscordPlayers').onchange = async event => { const result = await window.call('save_setting', 'discord_share_players', event.target.checked); if (!result?.settings) event.target.checked = !event.target.checked; else state.settings = result.settings; };
    }
    if (document.querySelector('.servers-page') && !document.querySelector('#destinationTools')) {
      let importPreviewReady = false;
      const panel = document.createElement('section'); panel.className = 'panel destination-tools'; panel.id = 'destinationTools';
      panel.innerHTML = '<div class="section-heading"><h2>Share destinations</h2><p>Paste a scpsl-autojoin link or JSON bundle. Review it before importing.</p></div><textarea class="input" id="destinationInput" rows="3" placeholder="Paste destination link or JSON"></textarea><div class="actions"><button class="button" id="previewDestination">Preview import</button><button class="button primary" id="importDestination">Import destination</button></div><small id="destinationPreview" role="status"></small>';
      document.querySelector('.servers-page').appendChild(panel);
      $('#previewDestination').onclick = async () => { importPreviewReady = false; const result = await window.call('preview_destination', $('#destinationInput').value.trim()); importPreviewReady = !!result?.ok; $('#destinationPreview').textContent = result?.ok ? `${result.destination.name}: ${result.destination.servers.length} server(s)` : (result?.error || 'Invalid destination'); };
      $('#importDestination').onclick = async () => { if (!importPreviewReady) { $('#destinationPreview').textContent = 'Preview the destination before importing.'; return; } const result = await window.call('import_destination_link', $('#destinationInput').value.trim()); if (result?.ok) { window.toast('Destination imported'); if (typeof window.render === 'function') window.render(); } else window.toast(result?.error || 'Import failed'); };
    }
  }
  document.addEventListener('DOMContentLoaded', () => setTimeout(() => { enhance(); addRoadmapTools(); }, 250));
  const content = document.querySelector('#content');
  if (content) new MutationObserver(() => addRoadmapTools()).observe(content, {childList: true});
  setInterval(() => { enhance(); addRoadmapTools(); }, 250);
})();

(function () {
  function installDestinationExport() {
    const host = document.querySelector('#destinationTools');
    if (!host || document.querySelector('#exportDestinationLink')) return;
    const controls = document.createElement('div');
    controls.className = 'actions destination-export';
    controls.innerHTML = '<input class="input" id="destinationExportName" placeholder="Share name" aria-label="Share name"><button class="button" id="exportDestinationLink">Copy share link</button><small id="destinationExportStatus" class="technical-note" role="status"></small>';
    host.appendChild(controls);
    $('#exportDestinationLink').onclick = async () => {
      const name = $('#destinationExportName').value.trim() || 'Shared destination';
      const result = await window.call('export_destination_link', name, state.servers.map(s => s.id));
      if (!result?.ok) { $('#destinationExportStatus').textContent = result?.error || 'Could not create share link.'; return; }
      try { await navigator.clipboard.writeText(result.link); $('#destinationExportStatus').textContent = 'Share link copied. It contains destinations only.'; }
      catch (_) { $('#destinationExportStatus').textContent = result.link; }
    };
  }
  document.addEventListener('DOMContentLoaded', () => setTimeout(installDestinationExport, 350));
  const content = document.querySelector('#content');
  if (content) new MutationObserver(() => setTimeout(installDestinationExport, 0)).observe(content, { childList: true });
})();

// Add the per-group loop override to the policy editor without changing the
// older renderer's markup contract.
(function () {
  function installGroupLoopControl() {
    const policy = document.querySelector('.group-policy');
    if (!policy || document.querySelector('#groupLoopOverride')) return;
    const row = document.createElement('label');
    row.className = 'toggle-row';
    row.innerHTML = '<span><strong>Loop after the final server</strong><small>Keep cycling this group until you stop it.</small></span><input type="checkbox" id="groupLoopOverride">';
    policy.insertBefore(row, policy.querySelector('#saveGroupPolicy'));
    const group = state.groups.find(item => item.id === mainGroupId);
    row.querySelector('input').checked = group?.policy?.loop === true;
  }
  document.addEventListener('DOMContentLoaded', () => setTimeout(installGroupLoopControl, 350));
  const content = document.querySelector('#content');
  if (content) new MutationObserver(() => setTimeout(installGroupLoopControl, 0)).observe(content, { childList: true });
  document.addEventListener('click', async event => {
    const button = event.target.closest?.('#saveGroupPolicy');
    if (!button || !document.querySelector('#groupLoopOverride')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const result = await window.call('save_group_policy', mainGroupId, { strategy: $('#groupStrategy').value, minimum_players: Number($('#groupMinPlayers').value), maximum_fill_percent: Number($('#groupMaxFill').value), loop: $('#groupLoopOverride').checked });
    if (result?.ok) { const group = state.groups.find(item => item.id === mainGroupId); if (group) group.policy = result.group.policy; window.toast('Group policy saved'); } else window.toast(result?.error || 'Could not save group policy');
  }, true);
})();

// Per-server overrides belong with the saved destination, not buried in the
// global settings page. Keep this additive so older stores remain readable.
(function () {
  function installServerProfileEditor() {
    if (!document.querySelector('.servers-page') || document.querySelector('#serverProfileEditor')) return;
    const host = document.querySelector('.servers-page .saved-servers-panel');
    if (!host || !state.servers?.length) return;
    const panel = document.createElement('section');
    panel.className = 'panel server-profile-editor';
    panel.id = 'serverProfileEditor';
    panel.innerHTML = '<div class="section-heading"><h2>Server profile</h2><p>Optional overrides apply only when this destination is joined or monitored.</p></div>' +
      '<label class="field"><span>SERVER</span><select class="input" id="profileServer">' + state.servers.map(s => '<option value="' + esc(s.id) + '">' + esc(s.name) + '</option>').join('') + '</select></label>' +
      '<div class="settings-grid compact-grid"><label class="field"><span>RETRY SECONDS</span><input class="input" id="profileRetry" type="number" min="0" placeholder="Global"></label><label class="field"><span>ATTEMPT TIMEOUT</span><input class="input" id="profileTimeout" type="number" min="1" placeholder="Global"></label></div>' +
      '<label class="toggle-row"><span><strong>Monitor in background</strong><small>Include this server in the optional local history sweep.</small></span><input type="checkbox" id="profileMonitoring"></label>' +
      '<label class="toggle-row"><span><strong>Mute while joining</strong><small>Restore the previous game audio state when finished.</small></span><input type="checkbox" id="profileMute"></label>' +
      '<label class="toggle-row"><span><strong>Share this destination on Discord</strong><small>Shares its display name. A friend’s Join request opens an import preview only; it never joins automatically.</small></span><input type="checkbox" id="profilePresence"></label>' +
      '<div class="settings-grid compact-grid"><label class="field"><span>COMPANION URL</span><input class="input" id="profileCompanionUrl" placeholder="http://127.0.0.1:8787"></label><label class="field"><span>COMPANION TOKEN</span><input class="input" id="profileCompanionToken" type="password" placeholder="Stored securely on this PC"></label></div>' +
      '<small class="technical-note">Optional owner-operated LabAPI companion. Remote connections must use HTTPS; the token is never shown in the server list or shared presence.</small>' +
      '<button class="button primary" id="saveServerProfile">Save server profile</button><small id="serverProfileStatus" class="technical-note" role="status"></small>';
    host.appendChild(panel);
    const selected = () => state.servers.find(s => s.id === $('#profileServer').value) || state.servers[0];
    const load = () => { const s = selected(), join = s?.join_profile || {}, monitoring = s?.monitoring || {}; $('#profileRetry').value = join.retry_interval_s ?? ''; $('#profileTimeout').value = join.attempt_timeout_s ?? ''; $('#profileMonitoring').checked = !!monitoring.enabled; $('#profileMute').checked = join.mute_game_audio === true; $('#profilePresence').checked = !!s?.share_presence; $('#profileCompanionUrl').value = s?.companion_url || ''; $('#profileCompanionToken').value = ''; };
    $('#profileServer').onchange = load;
    $('#saveServerProfile').onclick = async () => { const s = selected(); if (!s) return; const value = { monitoring: { enabled: $('#profileMonitoring').checked }, join_profile: { retry_interval_s: $('#profileRetry').value === '' ? null : Number($('#profileRetry').value), attempt_timeout_s: $('#profileTimeout').value === '' ? null : Number($('#profileTimeout').value), mute_game_audio: $('#profileMute').checked, notifications_enabled: null }, share_presence: $('#profilePresence').checked, companion_url: $('#profileCompanionUrl').value.trim() || null }; const token = $('#profileCompanionToken').value.trim(); if (token) value.companion_token = token; const result = await window.call('save_server_profile', s.id, value); if (result?.ok) { Object.assign(s, result.server); $('#profileCompanionToken').value = ''; $('#serverProfileStatus').textContent = 'Profile saved locally. Companion token is protected by Windows.'; } else $('#serverProfileStatus').textContent = result?.error || 'Could not save profile.'; };
    load();
  }
  document.addEventListener('DOMContentLoaded', () => setTimeout(installServerProfileEditor, 300));
  const content = document.querySelector('#content');
  if (content) new MutationObserver(() => setTimeout(installServerProfileEditor, 0)).observe(content, { childList: true });
})();
