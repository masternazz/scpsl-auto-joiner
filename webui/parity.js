/* Feature-parity controls kept separate from the compact legacy renderer. */
(function () {
  const $ = (s, root = document) => root.querySelector(s);
  const escValue = value => String(value ?? '');

  function applyStoredTheme() {
    const preset = state.theme?.preset || 'violet';
    document.documentElement.classList.toggle('light-mode', preset.startsWith('light'));
    document.documentElement.classList.toggle('light-warm', preset === 'light-warm');
    document.documentElement.classList.toggle('light-slate', preset === 'light-slate');
    const colors = { violet: '#b186ff', amber: '#e0a458', slate: '#71b7d8', light: '#6941c6', 'light-warm': '#8a5a24', 'light-slate': '#216b89' };
    document.documentElement.style.setProperty('--accent', colors[preset] || colors.violet);
    let custom = document.querySelector('#storedCustomTheme');
    if (custom) custom.remove();
    const css = state.theme?.custom?.compiled;
    if (css) {
      custom = document.createElement('style');
      custom.id = 'storedCustomTheme';
      custom.textContent = css;
      document.head.appendChild(custom);
    }
  }

  function form(title, fields, submit) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = '<section class="confirm-modal form-modal" role="dialog" aria-modal="true"><div class="modal-kicker">EDIT LOCAL DATA</div><h2></h2><form><div class="form-fields"></div><div class="modal-actions"><button type="button" class="button" data-form-cancel>Cancel</button><button type="submit" class="button primary">Save</button></div></form></section>';
    $('h2', backdrop).textContent = title;
    const fieldsRoot = $('.form-fields', backdrop);
    fields.forEach(field => {
      const label = document.createElement('label');
      label.className = 'field';
      label.innerHTML = '<span class="field-label"></span><input class="input">';
      $('.field-label', label).textContent = field.label;
      const input = $('input', label);
      input.name = field.name;
      input.value = escValue(field.value);
      input.type = field.type || 'text';
      input.required = field.required !== false;
      fieldsRoot.appendChild(label);
    });
    const close = () => backdrop.remove();
    $('[data-form-cancel]', backdrop).onclick = close;
    backdrop.onclick = event => { if (event.target === backdrop) close(); };
    $('form', backdrop).onsubmit = async event => {
      event.preventDefault();
      const values = Object.fromEntries([...new FormData(event.currentTarget).entries()]);
      const result = await submit(values);
      if (result !== false) close();
    };
    document.body.appendChild(backdrop);
    $('input', backdrop)?.focus();
  }

  function addServer() {
    form('Add saved server', [
      { name: 'name', label: 'Display name' },
      { name: 'endpoint', label: 'IP or hostname:port', value: '' }
    ], async values => {
      const split = values.endpoint.trim().lastIndexOf(':');
      if (split <= 0) { toast('Enter an endpoint such as 127.0.0.1:7777'); return false; }
      const result = await call('save_server', values.name.trim(), values.endpoint.slice(0, split).trim(), Number(values.endpoint.slice(split + 1)));
      if (!result?.ok) { toast(result?.error || 'Could not save the server'); return false; }
      state.servers = [...state.servers, result.server];
      selected = result.server.id;
      render();
    });
  }

  function renameServer(id) {
    const server = state.servers.find(item => item.id === id);
    if (!server) return;
    form('Rename saved server', [{ name: 'name', label: 'Display name', value: server.name }], async values => {
      const result = await call('rename_server', id, values.name.trim());
      if (!result?.ok) { toast(result?.error || 'Could not rename the server'); return false; }
      state.servers = state.servers.map(item => item.id === id ? result.server : item);
      render();
    });
  }

  function groupEditor() {
    const host = $('.layout > section:nth-child(2)');
    if (!host || $('#groupEditor', host)) return;
    const editor = document.createElement('div');
    editor.id = 'groupEditor';
    editor.className = 'group-editor';
    editor.innerHTML = '<div class="label">GROUP EDITOR</div><h2>Build an ordered retry group</h2><p>Choose servers and arrange the exact order used for retries.</p><div class="field"><label for="groupSelect">GROUP</label><select class="input" id="groupSelect"><option value="">New group</option></select></div><div class="field"><label for="groupName">GROUP NAME</label><input class="input" id="groupName" placeholder="My retry group"></div><div class="group-members" id="groupMembers"></div><div class="actions"><button class="button" id="newGroup">New group</button><button class="button primary" id="saveGroup">Save group</button><button class="button" id="startGroup">Start group</button></div>';
    host.appendChild(editor);
    const select = $('#groupSelect', editor), name = $('#groupName', editor), members = $('#groupMembers', editor);
    state.groups.forEach(group => { const option = new Option(group.name, group.id); select.add(option); });
    const selectedGroup = () => state.groups.find(group => group.id === select.value);
    const draw = () => {
      const group = selectedGroup();
      name.value = group?.name || '';
      const ids = group?.server_ids || [];
      members.innerHTML = state.servers.map(server => '<label class="member-row"><input type="checkbox" data-member="'+esc(server.id)+'" '+(ids.includes(server.id) ? 'checked' : '')+'><span>'+esc(server.name)+'</span><small>'+esc(server.ip)+':'+server.port+'</small></label>').join('') || '<div class="empty">Add servers first.</div>';
    };
    select.onchange = draw;
    $('#newGroup', editor).onclick = () => { select.value = ''; draw(); name.focus(); };
    $('#saveGroup', editor).onclick = async () => {
      const ids = [...members.querySelectorAll('[data-member]:checked')].map(input => input.dataset.member);
      const result = await call('save_group', name.value.trim(), ids, select.value || null);
      if (!result?.ok) { toast(result?.error || 'Add a name and at least one server'); return; }
      state.groups = select.value ? state.groups.map(group => group.id === result.group.id ? result.group : group) : [...state.groups, result.group];
      toast('Server group saved'); render();
    };
    $('#startGroup', editor).onclick = async () => {
      if (!select.value) { toast('Choose or save a group first'); return; }
      const result = await call('start_join', select.value, 'group');
      if (result?.ok) { addLog('Group auto-join started.'); page = 'join'; render(); }
    };
    draw();
  }

  function addStorageControls() {
    const panel = $('.settings .panel');
    if (!panel || $('#storageTools')) return;
    const row = document.createElement('div'); row.className = 'setting-row'; row.id = 'storageTools';
    row.innerHTML = '<div><strong>Local data</strong><small>Export a backup or reset only this app’s saved servers, groups, settings, and calibration.</small></div><div class="actions"><button class="button" id="exportData">Export data</button><button class="button danger" id="resetData">Reset app data</button></div>';
    panel.appendChild(row);
    $('#exportData').onclick = async () => { const result = await call('export_local_data'); toast(result?.ok ? 'Local data exported to AppData' : (result?.error || 'Export failed')); };
    $('#resetData').onclick = async () => { if (!await ask('Reset saved servers, groups, settings, and calibration? Translation packs and built-in files are not removed.', { title: 'Reset app data', confirmText: 'Reset', danger: true })) return; const result = await call('reset_local_storage'); if (result?.ok) { state.servers = result.servers; state.groups = result.groups; state.settings = result.settings; state.calibration = result.calibration; selected = null; render(); toast('App data reset'); } };
  }

  function addPackActions() {
    const panel = page === 'packs' ? $('.layout > section') : null;
    if (!panel || $('#packLinkTools')) return;
    const tools = document.createElement('div'); tools.className = 'field'; tools.id = 'packLinkTools';
    tools.innerHTML = '<label for="packLink">INSTALL FROM LINK</label><div class="actions"><input class="input" id="packLink" placeholder="GitHub repository or direct ZIP URL"><button class="button" id="installPackLink">Install link</button></div>';
    panel.appendChild(tools);
    $('#installPackLink').onclick = async () => { const url = $('#packLink').value.trim(); if (!url) return; const result = await call('install_translation_link', url); if (result?.ok) { state.packs = result.packs; toast('Translation pack installed'); render(); } else toast(result?.error || 'Could not install pack'); };
    document.querySelectorAll('[data-pack-delete]').forEach(button => {
      const row = button.closest('.table-item');
      if (!row || row.querySelector('[data-pack-open]')) return;
      const id = button.dataset.packDelete;
      row.insertAdjacentHTML('beforeend', '<button class="button" data-pack-open="'+esc(id)+'">Open folder</button><button class="button" data-pack-restore="'+esc(id)+'">Restore backup</button>');
    });
  }

  function addRememberControl() {
    const panel = page === 'servers' ? $('.layout > section') : null;
    if (!panel || $('#rememberServer', panel)) return;
    const button = document.createElement('button');
    button.className = 'button';
    button.id = 'rememberServer';
    button.textContent = 'Remember current connection';
    button.title = 'Watch Player.log for the next connection, then suggest its server name';
    panel.querySelector('.actions')?.appendChild(button);
    button.onclick = async () => {
      const result = await call('start_remember');
      if (result?.ok) toast('Watching SCP:SL. Join normally, then the endpoint will appear here.');
      else toast(result?.error || 'Could not start connection detection');
    };
  }

  function showDetectedServer(data) {
    const endpoint = `${data.ip}:${data.port}`;
    form('Save detected server', [
      { name: 'name', label: 'Display name', value: data.name || endpoint },
      { name: 'endpoint', label: 'Detected endpoint', value: endpoint }
    ], async values => {
      const split = values.endpoint.trim().lastIndexOf(':');
      if (split <= 0) { toast('Enter an endpoint such as 127.0.0.1:7777'); return false; }
      const result = await call('remember_server', values.name.trim(), values.endpoint.slice(0, split).trim(), Number(values.endpoint.slice(split + 1)));
      if (!result?.ok) { toast(result?.error || 'Could not save the server'); return false; }
      state.servers = [...state.servers.filter(item => item.id !== result.server.id), result.server];
      selected = result.server.id;
      render();
    });
  }

  function addGroup() {
    form('Create server group', [{ name: 'name', label: 'Group name', value: '' }], async values => {
      const ids = state.servers.map(server => server.id);
      const result = await call('save_group', values.name.trim(), ids);
      if (!result?.ok) { toast(result?.error || 'Could not create the group'); return false; }
      state.groups = [...state.groups, result.group];
      render();
    });
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest?.('#addServer,[data-rename]');
    if (button) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (button.id === 'addServer') addServer(); else renameServer(button.dataset.rename);
      return;
    }
    const addGroupButton = event.target.closest?.('#addGroup');
    if (addGroupButton) {
      event.preventDefault(); event.stopImmediatePropagation(); addGroup(); return;
    }
    const deleteServer = event.target.closest?.('[data-delete]');
    if (deleteServer) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (await ask('Delete this saved server? This cannot be undone.', { title: 'Delete saved server', confirmText: 'Delete', danger: true })) {
        const result = await call('delete_server', deleteServer.dataset.delete);
        if (result?.ok) { state.servers = state.servers.filter(item => item.id !== deleteServer.dataset.delete); render(); }
      }
      return;
    }
    const deleteGroup = event.target.closest?.('[data-group-delete]');
    if (deleteGroup) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (await ask('Delete this retry group?', { title: 'Delete group', confirmText: 'Delete', danger: true })) {
        const result = await call('delete_group', deleteGroup.dataset.groupDelete);
        if (result?.deleted) { state.groups = state.groups.filter(item => item.id !== deleteGroup.dataset.groupDelete); render(); }
      }
      return;
    }
    const deletePack = event.target.closest?.('[data-pack-delete]');
    if (deletePack) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (await ask('Delete this installed translation pack?', { title: 'Delete translation pack', confirmText: 'Delete', danger: true })) {
        const result = await call('delete_translation_pack', deletePack.dataset.packDelete);
        if (result?.ok) { state.packs = result.packs; render(); }
      }
      return;
    }
    const open = event.target.closest?.('[data-pack-open]');
    if (open) { event.preventDefault(); call('open_translation_folder', open.dataset.packOpen); return; }
    const restore = event.target.closest?.('[data-pack-restore]');
    if (restore) { event.preventDefault(); call('restore_translation_backup', restore.dataset.packRestore).then(result => { if (result?.ok) { state.packs = result.packs; render(); } }); }
  }, true);

  let installed = false;
  function installParityRender() {
    if (installed) return;
    installed = true;
    const oldRender = render;
    render = () => { oldRender(); applyStoredTheme(); if (page === 'servers') { groupEditor(); addRememberControl(); } if (page === 'settings') addStorageControls(); if (page === 'packs') addPackActions(); };
    const oldEvent = window.__appEvent;
    window.__appEvent = event => {
      oldEvent?.(event);
      if (event?.event === 'server_detected') showDetectedServer(event.data || {});
    };
  }
  installParityRender();
  // With an already-available bridge, boot can finish before the next script
  // tag is evaluated. Re-render once in that case so parity controls and the
  // persisted theme are applied to the actual loaded state.
  if (state.version) render();
  document.addEventListener('DOMContentLoaded', installParityRender);
})();
