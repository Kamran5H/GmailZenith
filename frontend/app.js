/**
 * Gmail Zenith Pro — Frontend Application Logic
 * Fast asynchronous API communication, live stats charts, batch actions,
 * interactive dry-run preview, and GitHub notification triage.
 */

class GmailZenithApp {
  constructor() {
    this.state = {
      authenticated: false,
      profile: null,
      stats: null,
      topSenders: [],
      githubData: null,
      activeGhCategory: 'all',
      filterResults: [],
      selectedMessageIds: new Set(),
      pendingCleanQuery: null,
      pendingCleanPreset: null,
      logEntriesCount: 1,
    };

    this.initElements();
    this.initEventListeners();
    this.checkAuthStatus();
  }

  initElements() {
    // Navigation
    this.navButtons = document.querySelectorAll('.nav-item');
    this.tabPanels = document.querySelectorAll('.tab-panel');
    this.pageTitle = document.getElementById('page-title');
    this.pageSubtitle = document.getElementById('page-subtitle');

    // Status
    this.statusDot = document.getElementById('status-dot');
    this.statusTitle = document.getElementById('status-title');
    this.statusEmail = document.getElementById('status-email');
    this.btnQuickAuth = document.getElementById('btn-quick-auth');

    // Stats
    this.statInboxTotal = document.getElementById('stat-inbox-total');
    this.statUnreadTotal = document.getElementById('stat-unread-total');
    this.statPromotions = document.getElementById('stat-promotions');
    this.statSocialUpdates = document.getElementById('stat-social-updates');
    this.statGithubCount = document.getElementById('stat-github-count');
    this.badgeInbox = document.getElementById('badge-inbox');
    this.badgeGithub = document.getElementById('badge-github');
    this.clutterPercentBadge = document.getElementById('clutter-percent-badge');
    this.multiProgress = document.getElementById('multi-progress');
    this.storageLargeCount = document.getElementById('storage-large-count');

    // GitHub Triage
    this.githubFeed = document.getElementById('github-feed-container');
    this.ghTabButtons = document.querySelectorAll('.gh-tab-btn');

    // Filter
    this.filterQueryInput = document.getElementById('filter-query-input');
    this.filterTableBody = document.getElementById('filter-table-body');
    this.selectAllCheckbox = document.getElementById('select-all-results');
    this.resultsCountLabel = document.getElementById('results-count-label');

    // Quick Search Top Bar
    this.quickSearchInput = document.getElementById('quick-search-input');
    this.btnQuickSearch = document.getElementById('btn-quick-search');

    // Modal
    this.dryRunModal = document.getElementById('dry-run-modal');
    this.modalTitle = document.getElementById('modal-title');
    this.modalDesc = document.getElementById('modal-desc');
    this.modalMatchedCount = document.getElementById('modal-matched-count');
    this.modalStorageReclaimed = document.getElementById('modal-storage-reclaimed');
    this.modalPreviewList = document.getElementById('modal-preview-list');

    // Terminal
    this.logConsoleDrawer = document.querySelector('.log-console-drawer');
    this.logConsoleBody = document.getElementById('log-console-body');
    this.logCount = document.getElementById('log-count');

    // Setup
    this.dropzone = document.getElementById('dropzone');
    this.credentialsFileInput = document.getElementById('credentials-file-input');
  }

  initEventListeners() {
    // Tab switching
    this.navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.getAttribute('data-tab');
        this.switchTab(tab);
      });
    });

    // Refresh button
    const btnRefresh = document.getElementById('btn-refresh-stats');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => this.refreshAllData(true));
    }

    // Top Quick Search
    if (this.btnQuickSearch && this.quickSearchInput) {
      this.btnQuickSearch.addEventListener('click', () => {
        const q = this.quickSearchInput.value.trim();
        if (q) {
          this.switchTab('filter');
          this.filterQueryInput.value = q;
          this.executeFilterSearch();
        }
      });
      this.quickSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this.btnQuickSearch.click();
        }
      });
    }

    // Filter Query input enter key
    if (this.filterQueryInput) {
      this.filterQueryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this.executeFilterSearch();
        }
      });
    }

    // GitHub Sub-tabs
    this.ghTabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        this.ghTabButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.state.activeGhCategory = btn.getAttribute('data-ghcat');
        this.renderGitHubFeed();
      });
    });

    // File Dropzone
    if (this.dropzone && this.credentialsFileInput) {
      this.dropzone.addEventListener('click', () => this.credentialsFileInput.click());
      this.dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        this.dropzone.style.borderColor = 'var(--accent-blue)';
      });
      this.dropzone.addEventListener('dragleave', () => {
        this.dropzone.style.borderColor = 'var(--border-subtle)';
      });
      this.dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        this.dropzone.style.borderColor = 'var(--border-subtle)';
        if (e.dataTransfer.files.length) {
          this.uploadCredentialsFile(e.dataTransfer.files[0]);
        }
      });
      this.credentialsFileInput.addEventListener('change', () => {
        if (this.credentialsFileInput.files.length) {
          this.uploadCredentialsFile(this.credentialsFileInput.files[0]);
        }
      });
    }
  }

  // --- TAB NAVIGATION ---
  switchTab(tabId) {
    this.navButtons.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });

    this.tabPanels.forEach(panel => {
      panel.classList.toggle('active', panel.id === `tab-${tabId}`);
    });

    const titles = {
      overview: ['Inbox Overview & Analytics', 'Real-time scan, clutter analytics, and fast triage engine'],
      cleaners: ['1-Click Power Cleaners', 'Safely delete marketing, social, updates, and heavy files with 1-click'],
      github: ['GitHub Triage Center', 'Pull requests, issues, failed workflows, and security alerts'],
      filter: ['Universal Smart Filter', 'Custom Gmail query search, dry-run simulation, and batch actions'],
      setup: ['Connection & Google OAuth', 'Manage official Google Cloud credentials and OAuth authentication'],
    };

    if (titles[tabId]) {
      this.pageTitle.textContent = titles[tabId][0];
      this.pageSubtitle.textContent = titles[tabId][1];
    }

    if (tabId === 'github' && (!this.state.githubData || !this.state.githubData.all.length)) {
      this.loadGitHubTriage();
    }
  }

  // --- LOGGING & TERMINAL ---
  log(message, type = 'info') {
    const timeStr = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">[${timeStr}]</span> <span class="log-tag ${type}">[${type.toUpperCase()}]</span> ${message}`;
    this.logConsoleBody.appendChild(entry);
    this.logConsoleBody.scrollTop = this.logConsoleBody.scrollHeight;

    this.state.logEntriesCount++;
    if (this.logCount) {
      this.logCount.textContent = `${this.state.logEntriesCount} events`;
    }
  }

  toggleLogConsole() {
    this.logConsoleDrawer.classList.toggle('collapsed');
  }

  // --- TOAST NOTIFICATIONS ---
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- AUTH STATUS CHECKER ---
  async checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status');
      const data = await res.json();
      this.state.authenticated = data.authenticated;
      this.state.profile = data.profile;

      if (data.authenticated && data.profile) {
        this.statusDot.classList.add('online');
        this.statusTitle.textContent = 'Connected (Google OAuth)';
        this.statusEmail.textContent = data.profile.email;
        this.log(`Authenticated as ${data.profile.email}`, 'success');
        this.refreshAllData();
      } else {
        this.statusDot.classList.remove('online');
        this.statusTitle.textContent = data.hasCredentials ? 'Needs Authentication' : 'Setup Required';
        this.statusEmail.textContent = data.hasCredentials ? 'Click to login' : 'Upload credentials.json';
        this.log('Waiting for Google OAuth authentication...', 'warn');
      }
    } catch (e) {
      this.statusTitle.textContent = 'Backend Offline';
      this.statusEmail.textContent = 'Checking localhost:8765...';
      this.log(`Failed to connect to backend: ${e}`, 'danger');
    }
  }

  // --- REFRESH ALL DATA ---
  async refreshAllData(showToasts = false) {
    if (!this.state.authenticated) {
      this.checkAuthStatus();
      return;
    }

    this.log('Initiating inbox scan & analytics refresh...', 'info');
    try {
      await Promise.all([
        this.loadInboxStats(),
        this.loadTopSenders(),
      ]);
      if (showToasts) this.showToast('Inbox analytics refreshed successfully!', 'success');
      this.log('Inbox analytics updated successfully.', 'success');
    } catch (e) {
      this.log(`Error updating stats: ${e.message}`, 'danger');
    }
  }

  // --- LOAD INBOX STATS ---
  async loadInboxStats() {
    try {
      const res = await fetch('/api/stats/inbox');
      if (!res.ok) return;
      const data = await res.json();
      this.state.stats = data;

      const counts = data.counts || {};
      const totalInbox = counts.inbox || 0;
      const unread = counts.unread || 0;
      const promotions = counts.promotions || 0;
      const social = counts.social || 0;
      const updates = counts.updates || 0;
      const spam = counts.spam || 0;
      const github = counts.github || 0;
      const largeFiles = counts.largeFiles || 0;

      // Update UI cards
      this.statInboxTotal.textContent = totalInbox.toLocaleString();
      this.statUnreadTotal.textContent = `${unread.toLocaleString()} unread`;
      this.statPromotions.textContent = promotions.toLocaleString();
      this.statSocialUpdates.textContent = (social + updates).toLocaleString();
      this.statGithubCount.textContent = github.toLocaleString();
      this.storageLargeCount.textContent = largeFiles.toLocaleString();

      this.badgeInbox.textContent = totalInbox > 999 ? '999+' : totalInbox;
      this.badgeGithub.textContent = github;

      // Clutter metrics
      const totalClutter = promotions + social + updates + spam;
      const clutterPercent = totalInbox > 0 ? Math.min(100, Math.round((totalClutter / totalInbox) * 100)) : 0;
      this.clutterPercentBadge.textContent = `${clutterPercent}% Clutter`;

      // Legend
      document.getElementById('leg-promotions').textContent = promotions.toLocaleString();
      document.getElementById('leg-social').textContent = social.toLocaleString();
      document.getElementById('leg-updates').textContent = updates.toLocaleString();
      document.getElementById('leg-spam').textContent = spam.toLocaleString();

      // Multi-progress bar widths
      const denom = Math.max(1, promotions + social + updates + totalInbox);
      const pProm = (promotions / denom) * 100;
      const pSoc = (social / denom) * 100;
      const pUpd = (updates / denom) * 100;
      const pOther = Math.max(5, 100 - (pProm + pSoc + pUpd));

      this.multiProgress.innerHTML = `
        <div class="bar-seg seg-promotions" style="width: ${pProm}%" title="Promotions: ${promotions}"></div>
        <div class="bar-seg seg-social" style="width: ${pSoc}%" title="Social: ${social}"></div>
        <div class="bar-seg seg-updates" style="width: ${pUpd}%" title="Updates: ${updates}"></div>
        <div class="bar-seg seg-other" style="width: ${pOther}%" title="Other"></div>
      `;
    } catch (e) {
      console.error(e);
    }
  }

  // --- LOAD TOP SENDERS ---
  async loadTopSenders() {
    const tbody = document.getElementById('senders-table-body');
    try {
      const res = await fetch('/api/stats/top-senders?limit=80');
      if (!res.ok) return;
      const data = await res.json();
      const senders = data.senders || [];
      this.state.topSenders = senders;

      if (!senders.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No senders analyzed yet.</td></tr>`;
        return;
      }

      const maxCount = Math.max(...senders.map(s => s.count), 1);

      tbody.innerHTML = senders.map(s => {
        const pct = Math.round((s.count / maxCount) * 100);
        return `
          <tr>
            <td>
              <div class="sender-tag">${this.escapeHtml(s.name)}</div>
              <div class="sender-email-small">${this.escapeHtml(s.email)}</div>
            </td>
            <td><b>${s.count}</b> emails</td>
            <td>
              <div class="impact-mini-bar">
                <div class="impact-mini-fill" style="width: ${pct}%"></div>
              </div>
            </td>
            <td class="text-right">
              <button class="btn btn-sm btn-secondary" onclick="app.previewClean('from:${this.escapeHtml(s.email || s.name)}', 'All mail from ${this.escapeHtml(s.name)}')">
                Preview Clean
              </button>
            </td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Failed to load top senders.</td></tr>`;
    }
  }

  // --- 1-CLICK QUICK CLEAN ---
  async quickClean(presetName) {
    if (!this.state.authenticated) {
      this.showToast('Please connect your Google Account first.', 'danger');
      this.switchTab('setup');
      return;
    }

    const presetDescriptions = {
      promotions: 'Promotional & Marketing Emails',
      social: 'Social Media Notifications',
      updates: 'Automated Updates & Newsletters',
      spam: 'Spam Box Emails',
      large_files: 'Large Attachments (>10MB)',
      older_than_1y: 'Emails Older Than 1 Year',
    };

    const label = presetDescriptions[presetName] || presetName;
    if (!confirm(`Are you sure you want to clean ${label}? They will be safely moved to your Gmail Trash (recoverable for 30 days).`)) {
      return;
    }

    this.log(`Executing 1-Click Clean for [${presetName}]...`, 'info');
    try {
      const res = await fetch('/api/clean/preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset: presetName, max_items: 100 }),
      });

      const data = await res.json();
      if (data.success) {
        this.log(`Successfully moved ${data.count} ${label} to Trash!`, 'success');
        this.showToast(`Cleaned ${data.count} emails!`, 'success');
        this.refreshAllData();
      } else {
        this.log(`Clean failed: ${data.error}`, 'danger');
        this.showToast(`Error: ${data.error}`, 'danger');
      }
    } catch (e) {
      this.log(`Request error: ${e.message}`, 'danger');
    }
  }

  // --- DRY RUN & SIMULATION PREVIEW ---
  async previewClean(query, title = 'Custom Clean Preview') {
    if (!this.state.authenticated) {
      this.showToast('Please connect your Google Account first.', 'danger');
      this.switchTab('setup');
      return;
    }

    this.state.pendingCleanQuery = query;
    this.modalTitle.textContent = `Preview: ${title}`;
    this.modalDesc.textContent = `Query: "${query}". Review the matched emails before proceeding:`;
    this.modalMatchedCount.textContent = 'Scanning...';
    this.modalStorageReclaimed.textContent = '-- MB';
    this.modalPreviewList.innerHTML = `<div class="text-center text-muted p-4">Scanning inbox with Gmail API...</div>`;
    this.dryRunModal.classList.add('active');

    try {
      const res = await fetch('/api/clean/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, max_scan: 50 }),
      });

      const data = await res.json();
      this.modalMatchedCount.textContent = (data.matchedCount || 0).toLocaleString();
      this.modalStorageReclaimed.textContent = data.estimatedSizeFormatted || '0 MB';

      const sample = data.sample || [];
      if (!sample.length) {
        this.modalPreviewList.innerHTML = `<div class="text-center text-muted p-4">No matching emails found for this query.</div>`;
      } else {
        this.modalPreviewList.innerHTML = sample.map(m => `
          <div class="preview-item-row">
            <div style="font-weight: 700;">${this.escapeHtml(m.senderName)} <span style="font-size:0.75rem; color:var(--text-muted); font-weight:normal;">(${this.escapeHtml(m.date)})</span></div>
            <div style="color:var(--text-primary); margin-top:2px;">${this.escapeHtml(m.subject)}</div>
            <div style="color:var(--text-muted); font-size:0.75rem;">${this.escapeHtml(m.snippet)}</div>
          </div>
        `).join('');
      }
    } catch (e) {
      this.modalPreviewList.innerHTML = `<div class="text-center text-rose p-4">Error scanning: ${e.message}</div>`;
    }
  }

  closeModal() {
    this.dryRunModal.classList.remove('active');
    this.state.pendingCleanQuery = null;
  }

  async executeConfirmedClean() {
    if (!this.state.pendingCleanQuery) return;
    const query = this.state.pendingCleanQuery;
    this.closeModal();

    this.log(`Executing batch trash for query: "${query}"...`, 'info');
    try {
      // First search for IDs matching query
      const searchRes = await fetch(`/api/search?q=${encodeURIComponent(query)}&max_results=100`);
      const searchData = await searchRes.json();
      const ids = (searchData.messages || []).map(m => m.id);

      if (!ids.length) {
        this.showToast('No matching emails found to trash.', 'info');
        return;
      }

      const trashRes = await fetch('/api/batch/trash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: ids }),
      });

      const trashData = await trashRes.json();
      if (trashData.success) {
        this.log(`Moved ${trashData.count} emails to Trash!`, 'success');
        this.showToast(`Cleaned ${trashData.count} emails to Trash!`, 'success');
        this.refreshAllData();
      } else {
        this.showToast(`Error: ${trashData.error}`, 'danger');
      }
    } catch (e) {
      this.log(`Batch execution error: ${e.message}`, 'danger');
    }
  }

  // --- GITHUB TRIAGE CENTER ---
  async loadGitHubTriage() {
    if (!this.state.authenticated) return;
    this.githubFeed.innerHTML = `<div class="feed-empty-state"><p>Scanning GitHub notifications...</p></div>`;

    try {
      const res = await fetch('/api/github/triage?max_results=60');
      const data = await res.json();
      this.state.githubData = data;

      const catCounts = {
        all: data.total || 0,
        pr: (data.categorized.pull_requests || []).length,
        issues: (data.categorized.issues || []).length,
        ci: (data.categorized.ci_cd || []).length,
        sec: (data.categorized.security || []).length,
        rel: (data.categorized.releases || []).length,
      };

      document.getElementById('gh-count-all').textContent = catCounts.all;
      document.getElementById('gh-count-pr').textContent = catCounts.pr;
      document.getElementById('gh-count-issues').textContent = catCounts.issues;
      document.getElementById('gh-count-ci').textContent = catCounts.ci;
      document.getElementById('gh-count-sec').textContent = catCounts.sec;
      document.getElementById('gh-count-rel').textContent = catCounts.rel;

      this.renderGitHubFeed();
    } catch (e) {
      this.githubFeed.innerHTML = `<div class="feed-empty-state"><p class="text-rose">Error loading GitHub emails: ${e.message}</p></div>`;
    }
  }

  renderGitHubFeed() {
    if (!this.state.githubData) return;

    const cat = this.state.activeGhCategory;
    const items = cat === 'all' ? this.state.githubData.all : (this.state.githubData.categorized[cat] || []);

    if (!items.length) {
      this.githubFeed.innerHTML = `
        <div class="feed-empty-state">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="20 6 9 17 4 12"/></svg>
          <p>Zero unhandled notifications in this category. You are all caught up!</p>
        </div>
      `;
      return;
    }

    const badgeClassMap = {
      pull_requests: 'badge-pr',
      issues: 'badge-issue',
      ci_cd: 'badge-ci',
      security: 'badge-sec',
      releases: 'badge-rel',
      general: 'badge-pr',
    };

    this.githubFeed.innerHTML = items.map(item => {
      const meta = item.githubMeta || {};
      const isUnread = item.labelIds && item.labelIds.includes('UNREAD');
      const bClass = badgeClassMap[meta.category] || 'badge-pr';

      return `
        <div class="gh-item-card ${isUnread ? 'is-unread' : ''}" id="gh-card-${item.id}">
          <div class="gh-badge-tag ${bClass}">
            <span>${meta.badge || 'GitHub'}</span>
          </div>

          <div class="gh-content-col">
            <div class="gh-subject">${this.escapeHtml(item.subject)}</div>
            <div class="gh-snippet">${this.escapeHtml(item.snippet)}</div>
            <div class="gh-meta-row">
              <span>📅 ${this.escapeHtml(item.date)}</span>
              ${meta.repo ? `<span>📦 <b>${this.escapeHtml(meta.repo)}</b></span>` : ''}
              ${item.hasAttachment ? `<span>📎 Attachment</span>` : ''}
            </div>
          </div>

          <div class="gh-actions-col">
            <a href="${this.escapeHtml(meta.url || 'https://github.com/notifications')}" target="_blank" class="btn btn-sm btn-secondary" title="Open on GitHub">
              Open Thread ↗
            </a>
            <button class="btn btn-sm btn-secondary" onclick="app.actionMessage('${item.id}', 'read')" title="Mark as Read">
              ✓
            </button>
            <button class="btn btn-sm btn-rose" onclick="app.actionMessage('${item.id}', 'trash')" title="Move to Trash">
              🗑️
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  async markAllGitHubRead() {
    if (!this.state.githubData || !this.state.githubData.all.length) return;
    const ids = this.state.githubData.all.map(m => m.id);

    try {
      await fetch('/api/batch/labels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: ids, remove_labels: ['UNREAD'] }),
      });
      this.showToast('Marked all GitHub notifications as read!', 'success');
      this.log('Marked all current GitHub notifications as read.', 'success');
      this.loadGitHubTriage();
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  async actionMessage(messageId, action) {
    try {
      if (action === 'trash') {
        await fetch('/api/batch/trash', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message_ids: [messageId] }),
        });
        const el = document.getElementById(`gh-card-${messageId}`);
        if (el) el.remove();
        this.showToast('Moved to Trash.', 'info');
      } else if (action === 'read') {
        await fetch('/api/batch/labels', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message_ids: [messageId], remove_labels: ['UNREAD'] }),
        });
        const el = document.getElementById(`gh-card-${messageId}`);
        if (el) el.classList.remove('is-unread');
        this.showToast('Marked as read.', 'info');
      }
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  // --- UNIVERSAL FILTER & SMART SEARCH ---
  setFilterQuery(query) {
    this.filterQueryInput.value = query;
    this.executeFilterSearch();
  }

  async executeFilterSearch() {
    if (!this.state.authenticated) {
      this.showToast('Please connect your Google Account first.', 'danger');
      return;
    }

    const query = this.filterQueryInput.value.trim() || 'in:inbox';
    this.filterTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Searching Gmail for "${this.escapeHtml(query)}"...</td></tr>`;
    this.state.selectedMessageIds.clear();
    this.updateSelectedCountUI();

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&max_results=50`);
      const data = await res.json();
      const messages = data.messages || [];
      this.state.filterResults = messages;

      if (!messages.length) {
        this.filterTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No matching emails found for query.</td></tr>`;
        return;
      }

      this.filterTableBody.innerHTML = messages.map(m => `
        <tr>
          <td>
            <input type="checkbox" class="result-row-check" value="${m.id}" onchange="app.toggleMessageSelect('${m.id}', this.checked)">
          </td>
          <td>
            <div class="sender-tag">${this.escapeHtml(m.senderName)}</div>
            <div class="sender-email-small">${this.escapeHtml(m.senderEmail)}</div>
          </td>
          <td>
            <div style="font-weight: 700; color: var(--text-primary);">${this.escapeHtml(m.subject)}</div>
            <div style="color: var(--text-muted); font-size: 0.78rem; max-width: 480px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              ${this.escapeHtml(m.snippet)}
            </div>
          </td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">${this.escapeHtml(m.date)}</td>
          <td style="font-size: 0.8rem; color: var(--text-secondary);">${m.sizeEstimate ? Math.round(m.sizeEstimate / 1024) + ' KB' : '--'}</td>
          <td class="text-right">
            <button class="btn btn-sm btn-rose" onclick="app.trashSingleMessage('${m.id}')" title="Move to Trash">🗑️</button>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      this.filterTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-rose">Search error: ${e.message}</td></tr>`;
    }
  }

  toggleMessageSelect(id, checked) {
    if (checked) {
      this.state.selectedMessageIds.add(id);
    } else {
      this.state.selectedMessageIds.delete(id);
    }
    this.updateSelectedCountUI();
  }

  toggleSelectAll(checkbox) {
    const checks = document.querySelectorAll('.result-row-check');
    checks.forEach(c => {
      c.checked = checkbox.checked;
      if (checkbox.checked) {
        this.state.selectedMessageIds.add(c.value);
      } else {
        this.state.selectedMessageIds.delete(c.value);
      }
    });
    this.updateSelectedCountUI();
  }

  updateSelectedCountUI() {
    const count = this.state.selectedMessageIds.size;
    this.resultsCountLabel.textContent = `${count} items selected`;
  }

  async trashSingleMessage(id) {
    try {
      await fetch('/api/batch/trash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: [id] }),
      });
      this.showToast('Moved to Trash.', 'info');
      this.executeFilterSearch();
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  async batchTrashSelected() {
    const ids = Array.from(this.state.selectedMessageIds);
    if (!ids.length) {
      this.showToast('Please select one or more emails first.', 'warn');
      return;
    }

    try {
      const res = await fetch('/api/batch/trash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: ids }),
      });
      const data = await res.json();
      this.showToast(`Moved ${data.count} emails to Trash!`, 'success');
      this.log(`Batch moved ${data.count} selected emails to Trash.`, 'success');
      this.executeFilterSearch();
      this.loadInboxStats();
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  async batchMarkRead() {
    const ids = Array.from(this.state.selectedMessageIds);
    if (!ids.length) {
      this.showToast('Please select one or more emails first.', 'warn');
      return;
    }

    try {
      await fetch('/api/batch/labels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: ids, remove_labels: ['UNREAD'] }),
      });
      this.showToast(`Marked ${ids.length} emails as read!`, 'success');
      this.executeFilterSearch();
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  async batchArchive() {
    const ids = Array.from(this.state.selectedMessageIds);
    if (!ids.length) {
      this.showToast('Please select one or more emails first.', 'warn');
      return;
    }

    try {
      await fetch('/api/batch/labels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: ids, remove_labels: ['INBOX'] }),
      });
      this.showToast(`Archived ${ids.length} emails!`, 'success');
      this.executeFilterSearch();
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  // --- GOOGLE OAUTH SETUP & UPLOAD ---
  async uploadCredentialsFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    this.log(`Uploading OAuth credentials file (${file.name})...`, 'info');
    try {
      const res = await fetch('/api/auth/upload-credentials', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('credentials.json saved successfully! Click Authorize to connect.', 'success');
        this.log('credentials.json uploaded successfully.', 'success');
        this.checkAuthStatus();
      } else {
        this.showToast(`Error: ${data.detail || 'Upload failed'}`, 'danger');
      }
    } catch (e) {
      this.showToast(`Error uploading: ${e.message}`, 'danger');
    }
  }

  async launchOAuthLogin() {
    this.log('Fetching Google OAuth authorization URL...', 'info');
    this.showToast('Preparing Google sign-in...', 'info');

    try {
      const res = await fetch('/api/auth/url');
      const data = await res.json();
      if (!data.success || !data.auth_url) {
        throw new Error(data.detail || 'Failed to generate auth URL');
      }

      this.log('Opening official Google Account authorization screen...', 'info');
      
      // Listen for callback postMessage
      window.addEventListener('message', (event) => {
        if (event.data === 'oauth_complete') {
          this.log('OAuth authorization confirmed by callback!', 'success');
          this.showToast('Google Account authorized successfully!', 'success');
          this.checkAuthStatus();
        }
      }, { once: true });

      // Open Google sign in in popup window or tab
      const authWindow = window.open(
        data.auth_url,
        'GoogleAuthPopup',
        'width=600,height=720,menubar=no,toolbar=no,location=no,status=no'
      );

      if (!authWindow || authWindow.closed || typeof authWindow.closed === 'undefined') {
        // If popup was blocked by browser, redirect current tab
        this.showToast('Redirecting to Google sign-in...', 'info');
        window.location.href = data.auth_url;
      } else {
        // Poll status in background until connected
        let pollCount = 0;
        const interval = setInterval(async () => {
          pollCount++;
          if (pollCount > 60) {
            clearInterval(interval);
            return;
          }
          try {
            const statusRes = await fetch('/api/auth/status');
            const statusData = await statusRes.json();
            if (statusData.authenticated) {
              clearInterval(interval);
              this.log(`Authentication verified for ${statusData.profile?.email}`, 'success');
              this.showToast('Connected to Google Account!', 'success');
              this.checkAuthStatus();
            }
          } catch (e) {}
        }, 2000);
      }
    } catch (e) {
      this.showToast(`Login failed: ${e.message}`, 'danger');
      this.log(`OAuth URL error: ${e.message}`, 'danger');
    }
  }

  async logoutAccount() {
    if (!confirm('Are you sure you want to disconnect your Google Account and clear saved tokens?')) return;
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      this.showToast('Logged out successfully.', 'info');
      this.log('Logged out of Google Account.', 'warn');
      this.checkAuthStatus();
    } catch (e) {
      this.showToast(`Error: ${e.message}`, 'danger');
    }
  }

  // --- UTILITIES ---
  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Global App Instance
let app;
document.addEventListener('DOMContentLoaded', () => {
  app = new GmailZenithApp();
});
