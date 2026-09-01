/* Progressive UI for the local-first product expansion.  It intentionally
   augments the stable renderer instead of making feature modules responsible
   for the connection UI. */
(() => {
  const call = (...args) => window.pywebview?.api?.[args[0]]?.(...args.slice(1));
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  let setup = null, decisions = [], map = null, recovery = [], setupServerId = null;
  const panel = (title, body, className='expansion-panel') => `<section class="panel ${className}"><div class="feed-head"><span>${title}</span></div>${body}</section>`;

  async function refreshData(view) {
    const requests = [call('get_join_explanations'), call('get_recovery_actions')];
    if (view === 'diagnostics') requests.push(call('run_setup_check', setupServerId), call('calibration_target_map'));
    const [why, recoveryResult, checks, targets] = await Promise.all(requests);
    decisions = why?.items || []; recovery = recoveryResult?.actions || [];
    if (checks) setup = checks.checks || [];
    if (targets) map = targets.targets || [];
  }
  function injectJoin() {
    const page = document.querySelector('.join-page');
    if (!page || page.querySelector('#whyJoinPanel')) return;
    const content = decisions.slice(0, 4).map(item => `<article><strong>${esc(item.title)}</strong><span>${esc(item.next_action)}</span></article>`).join('') || '<p>No failed or pending decisions yet. Start Watch Mode or Auto-Join to see the reasoning here.</p>';
    page.insertAdjacentHTML('beforeend', panel('WHY DIDN’T IT JOIN?', `<div id="whyJoinPanel" class="decision-list">${content}</div><div class="actions"><button class="button" id="refreshWhyJoin">Refresh explanation</button>${recovery.map(action=>`<button class="button ${action.id==='retry'?'primary':''}" data-recovery="${action.id}">${esc(action.label)}</button>`).join('')}</div>`));
    document.querySelector('#refreshWhyJoin')?.addEventListener('click', async () => { await refreshData(); document.querySelector('#whyJoinPanel').innerHTML = decisions.slice(0,4).map(item=>`<article><strong>${esc(item.title)}</strong><span>${esc(item.next_action)}</span></article>`).join('') || '<p>No decisions yet.</p>'; });
    document.querySelectorAll('[data-recovery]').forEach(button=>button.addEventListener('click',async()=>{const action=button.dataset.recovery;if(action==='diagnostics'){page.dataset.pendingRecovery='diagnostics';document.querySelector('[data-go="diagnostics"]')?.click();return}const choices=selectedTarget.type==='group'?state.groups:state.servers,id=selectedTarget.id||choices[0]?.id;if(!id)return toast('Choose a destination first.');if(action==='retry'&&!await ask('Retry now? This may briefly focus SCP:SL for the Direct Connect steps.',{title:'Retry safely',confirmText:'Retry'}))return;const result=await call('recover_connection',id,selectedTarget.type,action);toast(result?.ok?'Recovery action started.':(result?.error||'Recovery could not start.'))}));
  }
  function injectDiagnostics() {
    const page = document.querySelector('.diagnostics-page');
    if (!page || page.querySelector('#setupCheckPanel')) return;
    const checks = setup.map(item => `<article class="${item.ok ? 'pass' : 'attention'}"><strong>${esc(item.label)}</strong><span>${esc(item.detail)}</span></article>`).join('');
    const targets = map.map(item => `<div class="target-map-item ${item.captured ? 'captured' : ''}" style="--x:${item.relative?.[0] ?? .5};--y:${item.relative?.[1] ?? .5}" title="${esc(item.id)}"><i></i><span>${esc(item.id.replace('_',' '))}</span></div>`).join('');
    const querySelect = `<label class="field"><span>OPTIONAL A2S CHECK</span><select class="input" id="setupServer"><option value="">Do not query a server</option>${(state.servers||[]).map(server=>`<option value="${esc(server.id)}" ${server.id===setupServerId?'selected':''}>${esc(server.name)}</option>`).join('')}</select></label>`;
    page.insertAdjacentHTML('beforeend', `<div class="expansion-grid"><section class="panel" id="setupCheckPanel"><div class="feed-head"><span>TEST MY SETUP</span></div>${querySelect}<div class="setup-checks">${checks}</div><button class="button" id="rerunSetup">Run checks again</button></section><section class="panel"><div class="feed-head"><span>CLIENT-RELATIVE TARGET MAP</span></div><div class="target-map">${targets}</div><small class="technical-note">Dots show saved targets relative to the detected game client. Open the technical preview above for exact coordinates.</small></section></div>`);
    document.querySelector('#rerunSetup')?.addEventListener('click', async () => { setupServerId=document.querySelector('#setupServer').value||null; await refreshData('diagnostics'); document.querySelector('#setupCheckPanel .setup-checks').innerHTML = setup.map(item => `<article class="${item.ok?'pass':'attention'}"><strong>${esc(item.label)}</strong><span>${esc(item.detail)}</span></article>`).join(''); });
  }
  function injectSettings() {
    const page = document.querySelector('.settings-page');
    if (!page || page.querySelector('#safeBackupPanel')) return;
    page.insertAdjacentHTML('beforeend', panel('SAFE BACKUP, ALERTS, AND ACCESSIBILITY', `<div class="settings-list"><label class="toggle-row"><span><strong>Slot notification sound</strong><small>Optional sound when Watch Mode confirms a slot.</small></span><input type="checkbox" data-product-setting="notification_sound"></label><label class="toggle-row"><span><strong>Actionable slot alerts</strong><small>Show Join now, Keep watching, and Mute game and join actions. Watch Mode waits for your choice.</small></span><input type="checkbox" data-product-setting="slot_alert_actions"></label><label class="toggle-row"><span><strong>Quiet notifications</strong><small>Show slot alerts without a sound.</small></span><input type="checkbox" data-product-setting="quiet_notifications"></label><label class="toggle-row"><span><strong>Compact server cards</strong><small>Use a denser layout in the Servers page.</small></span><input type="checkbox" data-product-setting="compact_mode"></label><label class="toggle-row"><span><strong>High contrast</strong><small>Strengthen lines and status differences.</small></span><input type="checkbox" data-product-setting="high_contrast"></label><label class="toggle-row"><span><strong>Larger text</strong><small>Increase reading size across the app.</small></span><input type="checkbox" data-product-setting="large_text"></label></div><div class="maintenance-actions"><button class="button primary" id="createSafeBackup">Create safe backup</button><button class="button" id="restoreSafeBackup">Restore a backup</button><button class="button" id="createSupportBundle">Create support bundle</button><button class="button" id="registerDestinationLinks">Register share-link actions</button></div><small class="technical-note">Installed copies register share links automatically. Portable users can opt in here. Backups never include Discord or companion credentials.</small>`, 'expansion-panel safe-backup-panel',));
    const currentState = state || {};
    document.querySelectorAll('[data-product-setting]').forEach(input => { input.checked = !!currentState.settings?.[input.dataset.productSetting]; input.addEventListener('change', async () => { const result = await call('save_setting', input.dataset.productSetting, input.checked); if (!result?.ok) input.checked = !input.checked; else { state.settings={...state.settings,...result.settings}; document.documentElement.classList.toggle(input.dataset.productSetting.replace('_','-'), input.checked); } }); });
    document.querySelector('#createSafeBackup')?.addEventListener('click', async () => { const result = await call('create_backup'); window.toast?.(result?.ok ? 'Safe backup created in AppData.' : result?.error || 'Backup failed.'); });
    document.querySelector('#restoreSafeBackup')?.addEventListener('click', async () => { const pick = await call('pick_backup_source'); if (!pick?.path) return; const preview=await call('preview_backup',pick.path); if (!preview?.ok) return toast(preview?.error || 'Invalid backup.'); if (!await ask(`Restore ${preview.summary.servers} servers and ${preview.summary.groups} groups? A safety backup will be created first.`,{title:'Restore safe backup',confirmText:'Restore',danger:true})) return; const result=await call('restore_backup',pick.path); toast(result?.ok ? 'Backup restored. Restarting the page state.' : result?.error || 'Restore failed.'); if(result?.ok) location.reload(); });
    document.querySelector('#createSupportBundle')?.addEventListener('click', async () => { const result=await call('create_support_bundle'); window.toast?.(result?.ok ? 'Sanitized support bundle created in AppData.' : result?.error || 'Could not create bundle.'); });
    document.querySelector('#registerDestinationLinks')?.addEventListener('click', async () => { const result=await call('register_destination_protocol'); window.toast?.(result?.ok ? 'Share-link actions are registered for this Windows user.' : result?.error || 'Could not register share-link actions.'); });
  }
  function injectServers() {
    const page = document.querySelector('.servers-page');
    if (!page || page.querySelector('#organizationPanel')) return;
    page.insertAdjacentHTML('beforeend', panel('PRIVATE ORGANIZATION', `<p class="technical-note">Tags, collections, notes, and local history never enter shared links or Discord.</p><div class="organization-actions"><input class="input" id="newCollection" placeholder="New collection name"><button class="button" id="saveCollection">Save collection</button></div><div id="collectionStatus" class="technical-note"></div>`));
    document.querySelector('#saveCollection')?.addEventListener('click', async () => { const input=document.querySelector('#newCollection'),result=await call('save_collection',input.value); document.querySelector('#collectionStatus').textContent=result?.ok?`Saved collection: ${input.value}`:(result?.error||'Could not save collection'); if(result?.ok) input.value=''; });
  }
  window.productExpansionRender = () => requestAnimationFrame(async () => { await refreshData(window.__currentPage || 'join'); injectJoin(); injectDiagnostics(); injectSettings(); injectServers(); });
  const eventHandler=window.__appEvent;
  window.__appEvent = event => { eventHandler?.(event); if (event?.event === 'join_decision') { decisions=[event.data,...decisions].slice(0,100); const node=document.querySelector('#whyJoinPanel'); if(node) node.innerHTML=decisions.slice(0,4).map(item=>`<article><strong>${esc(item.title)}</strong><span>${esc(item.next_action)}</span></article>`).join(''); } };
})();
