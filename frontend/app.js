/**
 * Gmail Zenith — dashboard logic.
 * All dynamic content is escaped and wired through data-action attributes
 * (no inline handlers), so email content can never execute as script.
 */
(() => {
  'use strict';

  // ---------------------------------------------------------------- helpers
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (n) => (typeof n === 'number' ? n.toLocaleString() : '—');
  const plural = (n, word) => `${num(n)} ${word}${n === 1 ? '' : 's'}`;

  function fmtSize(bytes) {
    if (!bytes) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return `${bytes.toFixed(i ? 1 : 0)} ${units[i]}`;
  }

  function fmtDate(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    const opts = d.getFullYear() === now.getFullYear()
      ? { month: 'short', day: 'numeric' }
      : { year: 'numeric', month: 'short', day: 'numeric' };
    return d.toLocaleDateString([], opts);
  }

  async function api(path, { method = 'GET', body, form } = {}) {
    const opts = { method, headers: {} };
    if (form) {
      opts.body = form;
    } else if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    let data = {};
    try { data = await res.json(); } catch (_) { /* empty body */ }
    if (!res.ok) {
      let msg = data.detail || res.statusText || 'Request failed';
      if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join('; ');
      const err = new Error(msg);
      err.status = res.status;
      if (res.status === 401) onSignedOut();
      throw err;
    }
    return data;
  }

  const ICON = {
    open: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>',
    read: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
    archive: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>',
    trash: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    search: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
    unsub: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.9 17.9 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><path d="m2 2 20 20"/></svg>',
  };

  const ACTION_WORDS = {
    trash: { verb: 'Move to Trash', done: 'moved to Trash' },
    archive: { verb: 'Archive', done: 'archived' },
    read: { verb: 'Mark as read', done: 'marked as read' },
  };

  const TAB_TITLES = {
    overview: ['Overview', 'Exact inbox counts, clutter breakdown and top senders'],
    cleaners: ['Cleaners', 'One-click cleanups with a preview first — and undo after'],
    search: ['Search & Bulk', 'Any Gmail search, then act on selected or all matching emails'],
    github: ['GitHub', 'Pull requests, issues, CI runs and security alerts in your inbox'],
    autoclean: ['Auto-Clean', 'Rules that keep your inbox clean on a schedule'],
    setup: ['Setup', 'Connect your Gmail account securely with Google OAuth'],
  };

  const BREAKDOWN = [
    { key: 'primary', label: 'Primary', cls: 'other', query: 'in:inbox category:primary' },
    { key: 'promotions', label: 'Promotions', cls: 'promotions', query: 'in:inbox category:promotions' },
    { key: 'social', label: 'Social', cls: 'social', query: 'in:inbox category:social' },
    { key: 'updates', label: 'Updates', cls: 'updates', query: 'in:inbox category:updates' },
    { key: 'forums', label: 'Forums', cls: 'forums', query: 'in:inbox category:forums' },
  ];

  // ------------------------------------------------------------------ state
  const state = {
    auth: null,
    tab: 'overview',
    loaded: {},
    search: { query: '', items: [], next: null, selected: new Set(), estimate: 0 },
    github: { data: null, cat: 'all' },
    ac: null,
    modal: null,
    logCount: 0,
  };

  // ------------------------------------------------------------ log & toast
  function log(message, type = 'info') {
    const row = document.createElement('div');
    row.className = 'log-entry';
    row.innerHTML = `<span class="log-time">${esc(new Date().toLocaleTimeString())}</span> `
      + `<span class="log-tag ${esc(type)}">${esc(type.toUpperCase())}</span> ${esc(message)}`;
    const body = $('log-body');
    body.appendChild(row);
    while (body.children.length > 200) body.firstChild.remove();
    body.scrollTop = body.scrollHeight;
    state.logCount++;
    $('log-count').textContent = plural(state.logCount, 'event');
  }

  function toast(message, type = 'info', { undo, duration = 5000 } = {}) {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span>${esc(message)}</span>`;
    if (undo) {
      const btn = document.createElement('button');
      btn.className = 'toast-btn';
      btn.textContent = 'Undo';
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        dismiss();
        await undo();
      });
      el.appendChild(btn);
      duration = 12000;
    }
    const dismiss = () => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 250);
    };
    $('toast-container').appendChild(el);
    setTimeout(dismiss, duration);
  }

  function fail(context, err) {
    if (err.status === 401) return; // handled by onSignedOut
    toast(`${context}: ${err.message}`, 'danger', { duration: 7000 });
    log(`${context}: ${err.message}`, 'danger');
  }

  function setBusy(el, busy) {
    if (!el) return;
    el.disabled = busy;
    el.classList.toggle('is-loading', busy);
  }

  // ---------------------------------------------------------------- actions
  async function runOnIds(ids, action, { silent = false } = {}) {
    const res = await api('/api/actions/ids', { method: 'POST', body: { message_ids: ids, action } });
    const msg = `${plural(res.count, 'email')} ${ACTION_WORDS[action].done}`;
    log(msg, 'success');
    if (!silent) toast(msg, 'success', { undo: res.undo.length ? () => undo(res.undo) : null });
    return res;
  }

  async function undo(ops) {
    try {
      const res = await api('/api/actions/undo', { method: 'POST', body: { ops } });
      toast(`Undone — ${plural(res.count, 'email')} restored`, 'info');
      log(`Undo restored ${res.count} email(s).`, 'info');
      afterChange();
      refreshCurrent(true);
    } catch (e) { fail('Undo failed', e); }
  }

  function afterChange() {
    state.loaded = { [state.tab]: state.loaded[state.tab] };
    loadStats();
  }

  // ------------------------------------------------------------- navigation
  function switchTab(tab) {
    if (!TAB_TITLES[tab]) return;
    state.tab = tab;
    document.querySelectorAll('.nav-item').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${tab}`));
    $('page-title').textContent = TAB_TITLES[tab][0];
    $('page-subtitle').textContent = TAB_TITLES[tab][1];
    try { localStorage.setItem('zenith.tab', tab); } catch (_) { /* storage unavailable */ }
    refreshCurrent(false);
  }

  function refreshCurrent(force) {
    const tab = state.tab;
    if (tab === 'setup') return renderSetup();
    if (tab === 'autoclean') return loadAutoClean(force);
    if (!state.auth?.authenticated) return;
    if (!force && state.loaded[tab]) return;
    state.loaded[tab] = true;
    if (tab === 'overview') { loadStats(); loadSenders(); }
    if (tab === 'cleaners') loadPresets();
    if (tab === 'github') loadGitHub();
    if (tab === 'search') runSearch(state.search.query || $('search-input').value || 'in:inbox');
  }

  // ------------------------------------------------------------------- auth
  async function checkAuth() {
    try {
      state.auth = await api('/api/auth/status');
    } catch (e) {
      $('status-title').textContent = 'Server offline';
      $('status-email').textContent = 'Start run_gmail_zenith.bat';
      log(`Cannot reach the local server: ${e.message}`, 'danger');
      return;
    }
    const a = state.auth;
    $('status-dot').classList.toggle('online', a.authenticated);
    $('connect-banner').hidden = a.authenticated;
    if (a.authenticated) {
      $('status-title').textContent = 'Connected';
      $('status-email').textContent = a.profile?.email || '';
      log(`Connected as ${a.profile?.email}`, 'success');
      loadStats();
    } else {
      $('status-title').textContent = a.hasCredentials ? 'Not signed in' : 'Setup needed';
      $('status-email').textContent = a.hasCredentials ? 'Click to connect' : 'Upload credentials.json';
    }
    renderSetup();
    refreshCurrent(true);
  }

  function onSignedOut() {
    if (state.auth) state.auth.authenticated = false;
    $('status-dot').classList.remove('online');
    $('status-title').textContent = 'Not signed in';
    $('status-email').textContent = 'Click to connect';
    $('connect-banner').hidden = false;
  }

  function renderSetup() {
    const a = state.auth || {};
    $('redirect-uri').textContent = a.redirectUri || `${location.origin}/oauth2callback`;
    const rows = [
      [a.hasCredentials, 'OAuth client', a.hasCredentials
        ? `credentials.json found (${a.clientType === 'web' ? 'Web application' : 'Desktop app'} client)`
        : 'Upload credentials.json (step 2)'],
      [a.authenticated, 'Gmail account', a.authenticated ? a.profile?.email : 'Not connected yet (step 3)'],
    ];
    $('setup-status').innerHTML = rows.map(([ok, title, text]) => `
      <div class="status-row ${ok ? 'ok' : ''}">
        <span class="status-check">${ok ? '✓' : '•'}</span>
        <div><b>${esc(title)}</b><span>${esc(text)}</span></div>
      </div>`).join('')
      + (a.authenticated && a.profile ? `<div class="status-row ok"><span class="status-check">✓</span>
        <div><b>Mailbox</b><span>${num(a.profile.messagesTotal)} messages · ${num(a.profile.threadsTotal)} threads</span></div></div>` : '');
    $('btn-connect').disabled = !a.hasCredentials;
    $('btn-connect').lastChild.textContent = a.authenticated ? ' Reconnect / switch account' : ' Connect Gmail';
    $('btn-logout').hidden = !a.authenticated;
    $('setup-guide').open = !a.authenticated;
  }

  async function uploadCredentials(file) {
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      await api('/api/auth/upload-credentials', { method: 'POST', form });
      toast('credentials.json saved — now click Connect Gmail.', 'success');
      log(`Saved OAuth client from ${file.name}.`, 'success');
      await checkAuth();
    } catch (e) { fail('Upload failed', e); }
  }

  async function connect() {
    try {
      const { auth_url: url } = await api('/api/auth/url');
      log('Opening Google sign-in…');
      const popup = window.open(url, 'zenith-google-auth', 'width=560,height=720');
      if (!popup) { location.href = url; return; }
      const started = Date.now();
      const timer = setInterval(async () => {
        if (Date.now() - started > 5 * 60 * 1000) return clearInterval(timer);
        if (popup.closed) {
          clearInterval(timer);
          await checkAuth();
          if (state.auth?.authenticated) toast('Gmail connected!', 'success');
        }
      }, 1000);
    } catch (e) { fail('Sign-in failed', e); }
  }

  window.addEventListener('message', (e) => {
    if (e.origin === location.origin && e.data === 'oauth_complete') {
      checkAuth().then(() => toast('Gmail connected!', 'success'));
    }
  });

  async function logout() {
    if (!confirm('Disconnect this Gmail account? The saved token on this computer will be deleted.')) return;
    try {
      await api('/api/auth/logout', { method: 'POST' });
      toast('Disconnected.', 'info');
      state.loaded = {};
      await checkAuth();
    } catch (e) { fail('Logout failed', e); }
  }

  // --------------------------------------------------------------- overview
  let statsInFlight = null;
  function loadStats() {
    if (!state.auth?.authenticated) return Promise.resolve();
    if (!statsInFlight) statsInFlight = fetchStats().finally(() => { statsInFlight = null; });
    return statsInFlight;
  }

  async function fetchStats() {
    const btn = $('btn-refresh');
    setBusy(btn, true);
    try {
      const { counts: c } = await api('/api/stats/inbox');
      const clutter = c.promotions + c.social + c.updates + c.forums;
      const pct = c.inbox ? Math.round((clutter / c.inbox) * 100) : 0;
      $('stat-inbox').textContent = num(c.inbox);
      $('stat-unread').textContent = `${num(c.unread)} unread`;
      $('stat-clutter').textContent = num(clutter);
      $('stat-clutter-pct').textContent = `${pct}% of inbox`;
      $('stat-large').textContent = num(c.largeFiles);
      $('stat-github').textContent = num(c.github);
      $('spam-pill').textContent = `Spam: ${num(c.spam)} · Trash: ${num(c.trash)}`;
      setBadge('badge-inbox', c.inbox > 999 ? '999+' : c.inbox);
      setBadge('badge-clutter', clutter > 999 ? '999+' : clutter);
      setBadge('badge-github', c.github);

      const total = Math.max(1, BREAKDOWN.reduce((s, b) => s + (c[b.key] || 0), 0));
      $('breakdown-bar').innerHTML = BREAKDOWN.map((b) => {
        const w = ((c[b.key] || 0) / total) * 100;
        return w ? `<div class="bar-seg seg-${b.cls}" style="width:${w}%" title="${esc(b.label)}: ${num(c[b.key])}"></div>` : '';
      }).join('');
      $('breakdown-legend').innerHTML = BREAKDOWN.map((b) => `
        <button class="legend-item" data-action="search" data-query="${esc(b.query)}">
          <span class="dot dot-${b.cls}"></span>${esc(b.label)}
          <b>${num(c[b.key])}</b><small>${Math.round(((c[b.key] || 0) / total) * 100)}%</small>
        </button>`).join('');
    } catch (e) {
      fail('Could not load inbox counts', e);
    } finally {
      setBusy(btn, false);
    }
  }

  function setBadge(id, value) {
    const el = $(id);
    el.hidden = !value;
    el.textContent = value;
  }

  async function loadSenders() {
    if (!state.auth?.authenticated) return;
    const body = $('senders-body');
    body.innerHTML = `<tr><td colspan="5" class="empty-cell"><span class="spinner"></span> Analysing your latest inbox emails…</td></tr>`;
    try {
      const { senders, scanned } = await api('/api/stats/top-senders?limit=300');
      $('senders-desc').textContent = `Who fills your inbox the most, based on your latest ${num(scanned)} inbox emails`;
      if (!senders.length) {
        body.innerHTML = `<tr><td colspan="5" class="empty-cell">Your inbox is empty. Nice!</td></tr>`;
        return;
      }
      const max = Math.max(...senders.map((s) => s.count));
      body.innerHTML = senders.map((s) => {
        const q = s.email ? `from:${s.email}` : `from:"${s.name}"`;
        const canUnsub = s.unsubscribe && (s.unsubscribe.url || s.unsubscribe.mailto);
        return `<tr>
          <td class="col-sender">
            <div class="sender-tag">${esc(s.name)}</div>
            <div class="sender-email-small">${esc(s.email)}</div>
          </td>
          <td class="col-count">
            <div class="count-cell"><b>${num(s.count)}</b>
              <div class="impact-mini-bar"><div class="impact-mini-fill" style="width:${Math.round((s.count / max) * 100)}%"></div></div>
            </div>
          </td>
          <td class="hide-sm">${num(s.unread)}</td>
          <td class="hide-sm">${esc(s.size)}</td>
          <td class="text-right nowrap col-actions">
            <button class="icon-btn" title="Show all emails from this sender" data-action="search" data-query="${esc(q)}">${ICON.search}</button>
            ${canUnsub ? `<button class="icon-btn" title="Unsubscribe" data-action="unsubscribe" data-id="${esc(s.sampleId)}" data-name="${esc(s.name)}">${ICON.unsub}</button>` : ''}
            <button class="btn btn-sm btn-rose" data-action="preview" data-query="${esc(q)}" data-title="All email from ${esc(s.name)}">Clean</button>
          </td>
        </tr>`;
      }).join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="empty-cell">Could not analyse senders: ${esc(e.message)}</td></tr>`;
    }
  }

  async function unsubscribe(id, name) {
    if (!confirm(`Unsubscribe from ${name}?`)) return;
    try {
      const res = await api('/api/unsubscribe', { method: 'POST', body: { message_id: id } });
      if (res.success) {
        toast(`Unsubscribed from ${name}.`, 'success');
        log(`One-click unsubscribe from ${name} succeeded.`, 'success');
      } else if (res.url) {
        window.open(res.url, '_blank', 'noopener');
        toast(`Opened ${name}'s unsubscribe page — finish there.`, 'info', { duration: 7000 });
      } else if (res.mailto) {
        location.href = res.mailto;
        toast(`Opened an unsubscribe email to ${name} — just send it.`, 'info', { duration: 7000 });
      }
    } catch (e) { fail('Unsubscribe failed', e); }
  }

  // --------------------------------------------------------------- cleaners
  async function loadPresets() {
    const grid = $('cleaners-grid');
    if (!grid.children.length) {
      grid.innerHTML = `<div class="feed-empty-state"><span class="spinner"></span> Counting matching emails…</div>`;
    }
    try {
      const { presets } = await api('/api/presets?counts=true');
      grid.innerHTML = presets.map((p) => `
        <div class="glass-card cleaner-card accent-${esc(p.color)}">
          <div class="cleaner-top">
            <h3>${esc(p.title)}</h3>
            <span class="cleaner-count ${p.count ? '' : 'zero'}">${p.count ? num(p.count) + (p.capped ? '+' : '') : 'Clean'}</span>
          </div>
          <p>${esc(p.description)}</p>
          <code class="cleaner-query">${esc(p.query)}</code>
          <div class="cleaner-buttons">
            <button class="btn btn-secondary btn-sm" data-action="search" data-query="${esc(p.query)}">View</button>
            <button class="btn btn-rose btn-sm" data-action="preview" data-query="${esc(p.query)}" data-title="${esc(p.title)}" ${p.count ? '' : 'disabled'}>Review &amp; clean</button>
          </div>
        </div>`).join('');
    } catch (e) {
      grid.innerHTML = `<div class="feed-empty-state">Could not load cleaners: ${esc(e.message)}</div>`;
    }
  }

  // ------------------------------------------------------------------ modal
  async function openPreview(query, title, action = 'trash') {
    if (!state.auth?.authenticated) { switchTab('setup'); return toast('Connect Gmail first.', 'warn'); }
    state.modal = { query, title, count: 0 };
    $('modal-title').textContent = title || 'Review before cleaning';
    $('modal-query').textContent = `${query}  ·  starred excluded`;
    $('modal-count').textContent = '…';
    $('modal-size').textContent = '…';
    $('modal-action').value = action;
    $('modal-list').innerHTML = `<div class="empty-cell"><span class="spinner"></span> Counting matches…</div>`;
    $('modal-confirm').disabled = true;
    updateModalNote();
    $('preview-modal').classList.add('active');
    try {
      const p = await api('/api/actions/preview', { method: 'POST', body: { query } });
      if (!state.modal || state.modal.query !== query) return;
      state.modal.count = p.count;
      state.modal.capped = p.capped;
      $('modal-count').textContent = num(p.count) + (p.capped ? '+' : '');
      $('modal-size').textContent = p.count ? `≈ ${p.estimatedSize}` : '—';
      $('modal-list').innerHTML = p.sample.length ? p.sample.map((m) => `
        <div class="preview-item-row">
          <div class="pi-top"><b>${esc(m.senderName)}</b><span>${esc(fmtDate(m.timestamp))}</span></div>
          <div class="pi-subject">${esc(m.subject)}</div>
          <div class="pi-snippet">${esc(m.snippet)}</div>
        </div>`).join('')
        + (p.count > p.sample.length ? `<div class="pi-more">…and ${num(p.count - p.sample.length)} more</div>` : '')
        : `<div class="empty-cell">Nothing matches — all clean!</div>`;
      $('modal-confirm').disabled = !p.count;
      updateModalNote();
    } catch (e) {
      $('modal-list').innerHTML = `<div class="empty-cell text-rose">${esc(e.message)}</div>`;
    }
  }

  function updateModalNote() {
    const action = $('modal-action').value;
    const m = state.modal || {};
    const n = m.count || 0;
    const words = ACTION_WORDS[action];
    const capNote = n >= 5000 || m.capped ? ' Up to 5,000 per run — run it again for the rest.' : '';
    const notes = {
      trash: 'Trash is kept for 30 days, and you can undo right after.',
      archive: 'Emails leave the inbox but stay searchable in All Mail.',
      read: 'Only unread emails are changed.',
    };
    $('modal-note').textContent = notes[action] + capNote;
    $('modal-confirm').textContent = n ? `${words.verb} (${num(Math.min(n, 5000))})` : words.verb;
    $('modal-confirm').className = `btn ${action === 'trash' ? 'btn-rose' : 'btn-primary'}`;
    $('modal-confirm').disabled = !n;
  }

  function closeModal() {
    $('preview-modal').classList.remove('active');
    state.modal = null;
  }

  async function confirmModal() {
    if (!state.modal) return;
    const { query } = state.modal;
    const action = $('modal-action').value;
    const btn = $('modal-confirm');
    setBusy(btn, true);
    btn.textContent = 'Working…';
    try {
      const res = await api('/api/actions/query', { method: 'POST', body: { query, action } });
      closeModal();
      const msg = `${plural(res.count, 'email')} ${ACTION_WORDS[action].done}` + (res.more ? ' (more remain — run again)' : '');
      log(`${msg} · ${res.query}`, 'success');
      toast(msg, 'success', { undo: res.undo.length ? () => undo(res.undo) : null });
      afterChange();
      refreshCurrent(true);
    } catch (e) {
      fail('Action failed', e);
    } finally {
      setBusy(btn, false);
      if (state.modal) updateModalNote();
    }
  }

  // ----------------------------------------------------------------- search
  async function runSearch(query, { append = false } = {}) {
    query = (query || '').trim() || 'in:inbox';
    if (state.tab !== 'search') {
      state.search.query = query;
      $('search-input').value = query;
      state.loaded.search = false;
      switchTab('search');
      return;
    }
    if (!state.auth?.authenticated) return toast('Connect Gmail first.', 'warn');
    const s = state.search;
    const body = $('search-body');
    $('search-input').value = query;
    if (!append) {
      Object.assign(s, { query, items: [], next: null });
      s.selected.clear();
      body.innerHTML = `<tr><td colspan="6" class="empty-cell"><span class="spinner"></span> Searching…</td></tr>`;
    }
    state.loaded.search = true;
    try {
      const params = new URLSearchParams({ q: query, max_results: '50' });
      if (append && s.next) params.set('page_token', s.next);
      const data = await api(`/api/search?${params}`);
      if (s.query !== query) return;
      s.items = append ? s.items.concat(data.messages) : data.messages;
      s.next = data.nextPageToken;
      s.estimate = data.resultSizeEstimate;
      renderSearch();
    } catch (e) {
      body.innerHTML = `<tr><td colspan="6" class="empty-cell text-rose">${esc(e.message)}</td></tr>`;
    }
  }

  function renderSearch() {
    const s = state.search;
    const body = $('search-body');
    if (!s.items.length) {
      body.innerHTML = `<tr><td colspan="6" class="empty-cell">No emails match <code>${esc(s.query)}</code>.</td></tr>`;
    } else {
      body.innerHTML = s.items.map((m) => `
        <tr class="${m.unread ? 'is-unread' : ''}" data-id="${esc(m.id)}">
          <td class="col-check"><input type="checkbox" class="row-check" value="${esc(m.id)}" ${s.selected.has(m.id) ? 'checked' : ''} aria-label="Select"></td>
          <td class="col-sender">
            <div class="sender-tag">${m.starred ? '<span class="star" title="Starred">★</span>' : ''}${esc(m.senderName)}</div>
            <div class="sender-email-small">${esc(m.senderEmail)}</div>
          </td>
          <td class="col-subject">
            <div class="subject-line">${esc(m.subject)}</div>
            <div class="snippet-line">${esc(m.snippet)}</div>
          </td>
          <td class="hide-sm nowrap text-muted" title="${esc(m.date)}">${esc(fmtDate(m.timestamp))}</td>
          <td class="hide-sm nowrap text-muted">${fmtSize(m.sizeEstimate)}</td>
          <td class="text-right nowrap col-actions">
            <a class="icon-btn" href="${esc(m.gmailUrl)}" target="_blank" rel="noopener" title="Open in Gmail">${ICON.open}</a>
            ${m.unread ? `<button class="icon-btn" title="Mark read" data-action="row" data-op="read" data-id="${esc(m.id)}">${ICON.read}</button>` : ''}
            ${m.labelIds.includes('INBOX') ? `<button class="icon-btn" title="Archive" data-action="row" data-op="archive" data-id="${esc(m.id)}">${ICON.archive}</button>` : ''}
            ${m.labelIds.includes('TRASH') ? '' : `<button class="icon-btn danger" title="Move to Trash" data-action="row" data-op="trash" data-id="${esc(m.id)}">${ICON.trash}</button>`}
          </td>
        </tr>`).join('');
    }
    $('load-more-row').hidden = !s.next;
    updateSelection();
  }

  function updateSelection() {
    const s = state.search;
    const n = s.selected.size;
    const shown = s.items.length;
    $('results-count-label').textContent = n
      ? `${plural(n, 'email')} selected`
      : shown ? `Showing ${num(shown)}${s.next ? ` of ~${num(s.estimate)}` : ''}` : 'No results';
    $('select-all').checked = shown > 0 && n === shown;
    $('select-all').indeterminate = n > 0 && n < shown;
    document.querySelectorAll('[data-action="bulk-selected"]').forEach((b) => { b.disabled = !n; });
    $('btn-all-matching').disabled = !shown;
  }

  async function bulkSelected(op, btn) {
    const ids = [...state.search.selected];
    if (!ids.length) return;
    setBusy(btn, true);
    try {
      await runOnIds(ids, op);
      applyLocal(ids, op);
      afterChange();
    } catch (e) { fail('Action failed', e); } finally { setBusy(btn, false); }
  }

  async function rowAction(id, op, btn) {
    setBusy(btn, true);
    try {
      await runOnIds([id], op);
      applyLocal([id], op);
      afterChange();
    } catch (e) { fail('Action failed', e); setBusy(btn, false); }
  }

  /** Reflect an action in the loaded results without re-querying Gmail. */
  function applyLocal(ids, op) {
    const s = state.search;
    const set = new Set(ids);
    if (op === 'read') {
      s.items.forEach((m) => { if (set.has(m.id)) { m.unread = false; m.labelIds = m.labelIds.filter((l) => l !== 'UNREAD'); } });
    } else {
      const q = s.query.toLowerCase();
      const stillMatches = op === 'archive' && !/in:inbox|is:inbox/.test(q);
      if (stillMatches) {
        s.items.forEach((m) => { if (set.has(m.id)) m.labelIds = m.labelIds.filter((l) => l !== 'INBOX'); });
      } else {
        s.items = s.items.filter((m) => !set.has(m.id));
      }
    }
    ids.forEach((id) => s.selected.delete(id));
    renderSearch();
    // Keep the GitHub view in sync too.
    const g = state.github.data;
    if (g && op !== 'read') {
      g.all = g.all.filter((m) => !set.has(m.id));
      Object.keys(g.categorized).forEach((k) => { g.categorized[k] = g.categorized[k].filter((m) => !set.has(m.id)); });
      renderGitHub();
    }
  }

  // ----------------------------------------------------------------- github
  async function loadGitHub() {
    const feed = $('github-feed');
    feed.innerHTML = `<div class="feed-empty-state"><span class="spinner"></span> Loading GitHub notifications…</div>`;
    try {
      state.github.data = await api('/api/github/triage?max_results=100');
      renderGitHub();
    } catch (e) {
      feed.innerHTML = `<div class="feed-empty-state text-rose">${esc(e.message)}</div>`;
    }
  }

  function ghItems() {
    const g = state.github.data;
    if (!g) return [];
    return state.github.cat === 'all' ? g.all : (g.categorized[state.github.cat] || []);
  }

  function renderGitHub() {
    const g = state.github.data;
    if (!g) return;
    document.querySelectorAll('.gh-tab-btn').forEach((b) => {
      const cat = b.dataset.ghcat;
      b.querySelector('span').textContent = cat === 'all' ? g.all.length : (g.categorized[cat] || []).length;
      b.classList.toggle('active', cat === state.github.cat);
    });
    const items = ghItems();
    if (!items.length) {
      $('github-feed').innerHTML = `<div class="feed-empty-state"><span class="big-check">✓</span>Nothing here — you're all caught up.</div>`;
      return;
    }
    $('github-feed').innerHTML = items.map((m) => {
      const meta = m.githubMeta || {};
      return `<div class="gh-item-card ${m.unread ? 'is-unread' : ''}">
        <span class="gh-badge-tag badge-${esc(meta.category)}">${esc(meta.badge)}</span>
        <div class="gh-content-col">
          <a class="gh-subject" href="${esc(meta.url)}" target="_blank" rel="noopener">${esc(m.subject)}</a>
          <div class="gh-snippet">${esc(m.snippet)}</div>
          <div class="gh-meta-row">
            <span>${esc(fmtDate(m.timestamp))}</span>
            ${meta.repo ? `<span class="gh-repo">${esc(meta.repo)}</span>` : ''}
            ${meta.reason ? `<span class="gh-reason">${esc(meta.reason.replace(/_/g, ' '))}</span>` : ''}
          </div>
        </div>
        <div class="gh-actions-col">
          <a class="icon-btn" href="${esc(meta.url)}" target="_blank" rel="noopener" title="Open on GitHub">${ICON.open}</a>
          ${m.unread ? `<button class="icon-btn" title="Mark read" data-action="gh-row" data-op="read" data-id="${esc(m.id)}">${ICON.read}</button>` : ''}
          <button class="icon-btn" title="Archive" data-action="gh-row" data-op="archive" data-id="${esc(m.id)}">${ICON.archive}</button>
          <button class="icon-btn danger" title="Move to Trash" data-action="gh-row" data-op="trash" data-id="${esc(m.id)}">${ICON.trash}</button>
        </div>
      </div>`;
    }).join('') + (g.more ? `<div class="feed-footnote">Showing the latest 100. Archive these to see older ones.</div>` : '');
  }

  async function ghAction(ids, op, btn) {
    if (!ids.length) return toast('Nothing to update in this view.', 'info');
    setBusy(btn, true);
    try {
      await runOnIds(ids, op);
      const set = new Set(ids);
      const g = state.github.data;
      if (op === 'read') {
        g.all.forEach((m) => { if (set.has(m.id)) m.unread = false; });
      } else {
        g.all = g.all.filter((m) => !set.has(m.id));
        Object.keys(g.categorized).forEach((k) => { g.categorized[k] = g.categorized[k].filter((m) => !set.has(m.id)); });
      }
      renderGitHub();
      afterChange();
    } catch (e) { fail('Action failed', e); } finally { setBusy(btn, false); }
  }

  // ------------------------------------------------------------- auto-clean
  async function loadAutoClean(force) {
    try {
      if (force || !state.ac) state.ac = await api('/api/sync/config');
      renderAutoClean();
      loadHistory();
      pollSyncStatus();
    } catch (e) { fail('Could not load Auto-Clean settings', e); }
  }

  function renderAutoClean() {
    const c = state.ac;
    $('ac-enabled').checked = c.enabled;
    $('ac-interval').value = c.interval_minutes;
    $('ac-max').value = c.max_per_rule;
    $('badge-auto').hidden = !c.enabled;
    $('rules-body').innerHTML = c.rules.length ? c.rules.map((r, i) => `
      <tr data-index="${i}">
        <td class="col-check"><input type="checkbox" data-field="enabled" ${r.enabled ? 'checked' : ''} aria-label="Enabled"></td>
        <td><input class="cell-input" data-field="name" value="${esc(r.name)}" placeholder="Rule name"></td>
        <td><input class="cell-input mono" data-field="query" value="${esc(r.query)}" placeholder="e.g. from:news@shop.com"></td>
        <td>
          <select class="cell-input" data-field="action">
            ${['trash', 'archive', 'read'].map((a) => `<option value="${a}" ${r.action === a ? 'selected' : ''}>${esc(ACTION_WORDS[a].verb)}</option>`).join('')}
          </select>
        </td>
        <td class="text-right nowrap">
          <button class="icon-btn" title="Preview matches" data-action="ac-preview" data-index="${i}">${ICON.search}</button>
          <button class="icon-btn danger" title="Delete rule" data-action="ac-remove" data-index="${i}">${ICON.trash}</button>
        </td>
      </tr>`).join('') : `<tr><td colspan="5" class="empty-cell">No rules yet — add one.</td></tr>`;
  }

  function readAutoCleanForm() {
    const c = state.ac;
    c.enabled = $('ac-enabled').checked;
    c.interval_minutes = Number($('ac-interval').value);
    c.max_per_rule = Number($('ac-max').value);
    document.querySelectorAll('#rules-body tr[data-index]').forEach((tr) => {
      const r = c.rules[Number(tr.dataset.index)];
      tr.querySelectorAll('[data-field]').forEach((f) => {
        r[f.dataset.field] = f.type === 'checkbox' ? f.checked : f.value.trim();
      });
    });
    return c;
  }

  async function saveAutoClean(btn) {
    setBusy(btn, true);
    try {
      const res = await api('/api/sync/config', { method: 'POST', body: readAutoCleanForm() });
      state.ac = res.config;
      renderAutoClean();
      toast('Auto-Clean settings saved.', 'success');
      log('Auto-Clean settings saved.', 'success');
    } catch (e) { fail('Could not save', e); } finally { setBusy(btn, false); }
  }

  async function loadHistory() {
    try {
      const rows = await api('/api/sync/history');
      $('history-body').innerHTML = rows.length ? rows.slice(0, 30).map((h) => {
        const details = Object.entries(h.details || {}).filter(([, n]) => n).map(([k, n]) => `${k}: ${n}`);
        const errs = Object.entries(h.errors || {}).map(([k, v]) => `${k}: ${v}`);
        return `<tr>
          <td class="nowrap">${esc(h.timestamp)}</td>
          <td><b>${num(h.totalCleaned)}</b></td>
          <td class="hide-sm">${esc(h.durationSeconds)}s</td>
          <td class="hide-sm">${num(h.inboxMessagesRemaining)}</td>
          <td class="details-cell">${details.length ? esc(details.join(' · ')) : '<span class="text-muted">Nothing to clean</span>'}
            ${errs.length ? `<div class="text-rose">${esc(errs.join(' · '))}</div>` : ''}</td>
        </tr>`;
      }).join('') : `<tr><td colspan="5" class="empty-cell">No runs yet.</td></tr>`;
    } catch (e) { /* history is optional */ }
  }

  let statusTimer = null;
  async function pollSyncStatus() {
    clearTimeout(statusTimer);
    try {
      const st = await api('/api/sync/status');
      const el = $('ac-status');
      el.textContent = st.running ? `Running since ${st.startedAt}…` : 'Idle';
      el.classList.toggle('running', st.running);
      setBusy(document.querySelector('[data-action="ac-run"]'), st.running);
      if (st.running) {
        statusTimer = setTimeout(pollSyncStatus, 2000);
      } else if (state.acWasRunning) {
        state.acWasRunning = false;
        loadHistory();
        afterChange();
        toast('Auto-Clean run finished — see History.', 'success');
      }
      state.acWasRunning = st.running || false;
    } catch (_) { /* ignore */ }
  }

  async function runAutoCleanNow(btn) {
    if (!confirm('Run all enabled rules now? Matching emails will be processed immediately.')) return;
    setBusy(btn, true);
    try {
      await api('/api/sync/run-now', { method: 'POST' });
      log('Auto-Clean run started.', 'info');
      state.acWasRunning = true;
      pollSyncStatus();
    } catch (e) { fail('Could not start', e); setBusy(btn, false); }
  }

  // ------------------------------------------------------------ click hub
  const handlers = {
    'tab': (el) => switchTab(el.dataset.tab),
    'go-setup': () => switchTab('setup'),
    'search': (el) => runSearch(el.dataset.query),
    'preview': (el) => openPreview(el.dataset.query, el.dataset.title),
    'reload-senders': () => loadSenders(),
    'unsubscribe': (el) => unsubscribe(el.dataset.id, el.dataset.name),
    'bulk-selected': (el) => bulkSelected(el.dataset.op, el),
    'all-matching': () => openPreview(state.search.query, 'All matching emails'),
    'load-more': (el) => { setBusy(el, true); runSearch(state.search.query, { append: true }).finally(() => setBusy(el, false)); },
    'row': (el) => rowAction(el.dataset.id, el.dataset.op, el),
    'gh-refresh': () => loadGitHub(),
    'gh-row': (el) => ghAction([el.dataset.id], el.dataset.op, el),
    'gh-bulk': (el) => {
      const items = ghItems().filter((m) => el.dataset.op !== 'read' || m.unread);
      if (el.dataset.op === 'archive' && items.length && !confirm(`Archive ${plural(items.length, 'notification')} shown?`)) return;
      ghAction(items.map((m) => m.id), el.dataset.op, el);
    },
    'ac-run': (el) => runAutoCleanNow(el),
    'ac-save': (el) => saveAutoClean(el),
    'ac-history': () => loadHistory(),
    'ac-add': () => {
      readAutoCleanForm();
      state.ac.rules.push({ name: '', query: '', action: 'trash', enabled: true });
      renderAutoClean();
      const inputs = document.querySelectorAll('#rules-body [data-field="name"]');
      inputs[inputs.length - 1]?.focus();
    },
    'ac-remove': (el) => {
      readAutoCleanForm();
      state.ac.rules.splice(Number(el.dataset.index), 1);
      renderAutoClean();
      toast('Rule removed — click Save changes to keep it that way.', 'info');
    },
    'ac-preview': (el) => {
      readAutoCleanForm();
      const r = state.ac.rules[Number(el.dataset.index)];
      if (!r.query) return toast('Enter a Gmail search for this rule first.', 'warn');
      openPreview(r.query, r.name || 'Rule preview', r.action);
    },
    'copy-redirect': (el) => {
      navigator.clipboard?.writeText(el.textContent).then(() => toast('Redirect URI copied.', 'success'));
    },
    'connect': () => connect(),
    'logout': () => logout(),
    'toggle-log': () => $('log-drawer').classList.toggle('collapsed'),
    'close-modal': () => closeModal(),
    'confirm-modal': () => confirmModal(),
  };

  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el || el.disabled) return;
    const fn = handlers[el.dataset.action];
    if (fn) { e.preventDefault(); fn(el, e); }
  });

  // ------------------------------------------------------------ other events
  document.querySelectorAll('.nav-item').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)));
  document.querySelectorAll('.gh-tab-btn').forEach((b) => b.addEventListener('click', () => {
    state.github.cat = b.dataset.ghcat;
    renderGitHub();
  }));

  $('btn-refresh').addEventListener('click', () => {
    state.loaded = {};
    if (state.auth?.authenticated && state.tab !== 'overview') loadStats();
    refreshCurrent(true);
  });

  $('quick-search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = $('quick-search-input').value.trim();
    if (q) runSearch(q);
  });

  $('search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    runSearch($('search-input').value);
  });

  $('search-body').addEventListener('change', (e) => {
    if (!e.target.classList.contains('row-check')) return;
    const s = state.search.selected;
    e.target.checked ? s.add(e.target.value) : s.delete(e.target.value);
    updateSelection();
  });

  $('select-all').addEventListener('change', (e) => {
    const s = state.search.selected;
    state.search.items.forEach((m) => (e.target.checked ? s.add(m.id) : s.delete(m.id)));
    document.querySelectorAll('.row-check').forEach((c) => { c.checked = e.target.checked; });
    updateSelection();
  });

  $('modal-action').addEventListener('change', updateModalNote);
  $('preview-modal').addEventListener('click', (e) => { if (e.target.id === 'preview-modal') closeModal(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.modal) closeModal();
    if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault();
      $('quick-search-input').focus();
    }
  });

  const dz = $('dropzone');
  const fileInput = $('credentials-input');
  dz.addEventListener('click', () => fileInput.click());
  dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dragging'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dragging'));
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.classList.remove('dragging');
    uploadCredentials(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { uploadCredentials(fileInput.files[0]); fileInput.value = ''; });

  // ------------------------------------------------------------------ start
  log('Gmail Zenith ready.');
  let initialTab = 'overview';
  try { initialTab = localStorage.getItem('zenith.tab') || 'overview'; } catch (_) { /* storage unavailable */ }
  switchTab(TAB_TITLES[initialTab] ? initialTab : 'overview');
  checkAuth().then(() => {
    if (state.auth && !state.auth.authenticated && !state.auth.hasCredentials) switchTab('setup');
  });
})();
