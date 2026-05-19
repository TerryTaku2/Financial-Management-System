// ── Config ──────────────────────────────────────────────────────────────
// Uses window.location.origin so the app works on localhost AND any deployed host
// (Render, Fly.io, PythonAnywhere, etc.) without code changes.
const API = window.location.origin;

// ── Auth ────────────────────────────────────────────────────────────────
function getToken() { return localStorage.getItem('fms_token'); }
function getUser()  { return JSON.parse(localStorage.getItem('fms_user') || 'null'); }
function setAuth(token, user) {
  localStorage.setItem('fms_token', token);
  localStorage.setItem('fms_user', JSON.stringify(user));
}
function clearAuth() {
  localStorage.removeItem('fms_token');
  localStorage.removeItem('fms_user');
}
function requireAuth() {
  if (!getToken()) { window.location.href = '/static/pages/login.html'; }
}
function logout() {
  clearAuth();
  window.location.href = '/static/pages/login.html';
}

// ── API Helper ───────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401) { logout(); return; }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

async function apiPost(path, body) {
  return apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
}
async function apiPatch(path, body = {}) {
  return apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) });
}
async function apiPut(path, body = {}) {
  return apiFetch(path, { method: 'PUT', body: JSON.stringify(body) });
}
async function apiDelete(path) {
  return apiFetch(path, { method: 'DELETE' });
}

// Download a file export from the API
async function downloadExport(url, filename) {
  const token = getToken();
  try {
    const res = await fetch(API + url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Export failed' }));
      throw new Error(err.detail || 'Export failed');
    }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  } catch(e) { toast(e.message, 'error'); }
}

// Upload a file to an import endpoint
async function uploadImport(url, file) {
  const token = getToken();
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(API + url, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: fd
  });
  if (res.status === 401) { logout(); return; }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

// Confirm-then-delete helper
async function confirmDelete(message, onConfirm) {
  if (confirm(message)) { await onConfirm(); }
}

// ── Cross-page navigation ─────────────────────────────────────────────────────
function getUrlParams() {
  return Object.fromEntries(new URLSearchParams(window.location.search));
}
function navigateTo(href, params = {}) {
  const clean = Object.fromEntries(Object.entries(params).filter(([,v]) => v != null && v !== ''));
  const qs = new URLSearchParams(clean).toString();
  window.location.href = `/static/pages/${href}${qs ? '?' + qs : ''}`;
}
function pageUrl(href, params = {}) {
  const clean = Object.fromEntries(Object.entries(params).filter(([,v]) => v != null && v !== ''));
  const qs = new URLSearchParams(clean).toString();
  return `/static/pages/${href}${qs ? '?' + qs : ''}`;
}

// ── Toast ────────────────────────────────────────────────────────────────
function toast(msg, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const iconSpan = document.createElement('span');
  iconSpan.className = 'toast-icon';
  iconSpan.textContent = icons[type] || 'ℹ️';
  const msgSpan = document.createElement('span');
  msgSpan.className = 'toast-msg';
  msgSpan.textContent = msg;
  t.appendChild(iconSpan);
  t.appendChild(msgSpan);
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Sidebar ──────────────────────────────────────────────────────────────
function buildSidebar(activePage) {
  const user = getUser();
  const role = user?.role || '';
  const navItems = [
    { label: 'Dashboard',        icon: '▪', page: 'dashboard',    href: 'dashboard.html',    roles: [] },
    { label: 'Ratepayers',       icon: '▪', page: 'ratepayers',   href: 'ratepayers.html',   roles: [] },
    { label: 'Invoices',         icon: '▪', page: 'invoices',     href: 'invoices.html',     roles: [] },
    { label: 'Billing',          icon: '▪', page: 'billing',      href: 'billing.html',      roles: [] },
    { label: 'Payments',         icon: '▪', page: 'payments',     href: 'payments.html',     roles: [] },
    { label: 'Expenditure',      icon: '▪', page: 'expenditures', href: 'expenditures.html', roles: [] },
    { label: 'Budget',           icon: '▪', page: 'budget',       href: 'budget.html',       roles: [] },
    { label: 'Leakage Monitor',  icon: '▪', page: 'leakage',      href: 'leakage.html',      roles: [] },
    { label: 'Reconciliation',    icon: '▪', page: 'reconciliation', href: 'reconciliation.html', roles: [] },
    { label: 'Audit Trail',      icon: '▪', page: 'audit',        href: 'audit.html',        roles: ['admin','auditor'] },
    { label: 'Management Report', icon: '▪', page: 'management_report', href: 'management_report.html', roles: ['admin','auditor','accountant','budget_officer'] },
    { label: 'Reports',          icon: '▪', page: 'reports',      href: 'reports.html',      roles: ['admin','auditor','accountant','budget_officer'] },
    { label: 'Aging Analysis',   icon: '▪', page: 'aging',        href: 'aging.html',        roles: [] },
    { label: 'Chart Generator',  icon: '▪', page: 'charts',       href: 'charts.html',       roles: [] },
    { label: 'User Management',  icon: '▪', page: 'users',        href: 'users.html',        roles: ['admin'] },
  ];

  const allowed = navItems.filter(n => n.roles.length === 0 || n.roles.includes(role));
  const navHTML = `
    <div class="nav-section-label">Main Menu</div>
    ${allowed.map(n => `
      <a class="nav-item ${activePage === n.page ? 'active' : ''}" href="/static/pages/${n.href}">
        <span class="nav-icon">${n.icon}</span>
        <span>${n.label}</span>
      </a>`).join('')}
  `;

  const initials = (user?.full_name||'U').split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
  const sidebar = document.getElementById('sidebar');
  if (sidebar) {
    sidebar.innerHTML = `
      <div class="sidebar-logo">
        <div class="logo-badge">
          <img src="/static/images/crest.png" alt="City of Harare Crest" style="width:44px;height:44px;object-fit:contain;">
          <div>
            <div class="logo-text">City of Harare</div>
            <div class="logo-sub">FMS v1.0</div>
          </div>
        </div>
      </div>
      <nav class="sidebar-nav">${navHTML}</nav>
      <div class="sidebar-footer">
        <div class="user-chip">
          <div class="user-avatar">${initials}</div>
          <div class="user-info">
            <div class="user-name">${user?.full_name || 'User'}</div>
            <div class="user-role">${(user?.role||'').replace('_',' ')}</div>
          </div>
          <button class="logout-btn" onclick="logout()" title="Logout">⏏</button>
        </div>
        <button class="change-pwd-btn" onclick="openModal('changePwdModal')" title="Change Password">Change Password</button>
      </div>`;
    // Inject the change-password modal once into the page
    if (!document.getElementById('changePwdModal')) {
      const modalHtml = `
        <div class="modal-overlay" id="changePwdModal">
          <div class="modal" style="max-width:400px">
            <div class="modal-header">
              <span class="modal-title">Change Password</span>
              <button class="modal-close" onclick="closeModal('changePwdModal')">✕</button>
            </div>
            <div class="modal-body">
              <div class="form-group">
                <label class="form-label">Current Password</label>
                <input class="form-input" type="password" id="cpCurrent" placeholder="Enter current password">
              </div>
              <div class="form-group">
                <label class="form-label">New Password</label>
                <input class="form-input" type="password" id="cpNew" placeholder="At least 8 characters">
              </div>
              <div class="form-group">
                <label class="form-label">Confirm New Password</label>
                <input class="form-input" type="password" id="cpConfirm" placeholder="Repeat new password">
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-secondary" onclick="closeModal('changePwdModal')">Cancel</button>
              <button class="btn btn-primary" onclick="submitChangePassword()">Update Password</button>
            </div>
          </div>
        </div>`;
      document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
  }
}

// ── Modal Helpers ────────────────────────────────────────────────────────
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('open');
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('open');
}

// ── Format Helpers ───────────────────────────────────────────────────────
function fmtMoney(v) {
  return '$' + Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' });
}
function badge(val, map) {
  const cls = map[val] || 'none';
  return `<span class="badge badge-${cls}">${val || '—'}</span>`;
}
function statusBadge(s) {
  const m = { paid:'paid', pending:'pending', overdue:'overdue', disputed:'disputed', waived:'waived' };
  return badge(s, m);
}
function anomalyBadge(f) {
  const m = { none:'none', low:'low', medium:'medium', high:'danger' };
  return badge(f, m);
}

// ── Pagination ────────────────────────────────────────────────────────────
function renderPagination(containerId, total, limit, currentPage, onPage) {
  const totalPages = Math.ceil(total / limit);
  const el = document.getElementById(containerId);
  if (!el || totalPages <= 1) { if (el) el.innerHTML = ''; return; }
  let html = `<span class="page-info">${total} records</span>`;
  html += `<button class="page-btn" onclick="(${onPage})(${currentPage-1})" ${currentPage<=1?'disabled':''}>‹</button>`;
  for (let i = 1; i <= Math.min(totalPages, 7); i++) {
    html += `<button class="page-btn ${i===currentPage?'active':''}" onclick="(${onPage})(${i})">${i}</button>`;
  }
  html += `<button class="page-btn" onclick="(${onPage})(${currentPage+1})" ${currentPage>=totalPages?'disabled':''}>›</button>`;
  el.innerHTML = html;
}

// ── Change Password ───────────────────────────────────────────────────────────
async function submitChangePassword() {
  const current = document.getElementById('cpCurrent').value.trim();
  const newPwd  = document.getElementById('cpNew').value.trim();
  const confirm = document.getElementById('cpConfirm').value.trim();
  if (!current || !newPwd || !confirm) { toast('All fields are required', 'warning'); return; }
  if (newPwd.length < 8) { toast('New password must be at least 8 characters', 'warning'); return; }
  if (newPwd !== confirm) { toast('New passwords do not match', 'error'); return; }
  try {
    await apiPatch('/api/auth/change-password', { current_password: current, new_password: newPwd });
    toast('Password changed successfully', 'success');
    closeModal('changePwdModal');
    document.getElementById('cpCurrent').value = '';
    document.getElementById('cpNew').value = '';
    document.getElementById('cpConfirm').value = '';
  } catch(e) { toast(e.message, 'error'); }
}

// ── PDF Export ────────────────────────────────────────────────────────────────
// Loads jsPDF + autoTable from CDN on first use, then generates a PDF from
// the provided columns/rows data with a City of Harare branded header.
let _jspdfLoaded = false;
let _crestDataURL = null;
async function _loadCrest() {
  if (_crestDataURL) return _crestDataURL;
  return new Promise(resolve => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      c.getContext('2d').drawImage(img, 0, 0);
      _crestDataURL = c.toDataURL('image/png');
      resolve(_crestDataURL);
    };
    img.onerror = () => resolve(null);
    img.src = '/static/images/crest.png';
  });
}
async function _loadJsPDF() {
  if (_jspdfLoaded) return;
  await new Promise((res, rej) => {
    const s1 = document.createElement('script');
    s1.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
    s1.onload = () => {
      const s2 = document.createElement('script');
      s2.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js';
      s2.onload = () => { _jspdfLoaded = true; res(); };
      s2.onerror = rej;
      document.head.appendChild(s2);
    };
    s1.onerror = rej;
    document.head.appendChild(s1);
  });
}

/**
 * Export structured data as a branded PDF.
 * @param {string} pageTitle  - e.g. "Invoice Register"
 * @param {string[]} columns  - Column header array
 * @param {Array[]} rows      - 2-D array of row values
 * @param {string} filename   - e.g. "invoices.pdf"
 * @param {string} [subtitle] - Optional subtitle / filter description
 */
async function exportPDF(pageTitle, columns, rows, filename, subtitle) {
  try {
    await _loadJsPDF();
    const [, crest] = await Promise.all([Promise.resolve(), _loadCrest()]);
    const { jsPDF } = window.jspdf;
    const orientation = columns.length > 7 ? 'landscape' : 'portrait';
    const doc = new jsPDF({ orientation, unit: 'mm', format: 'a4' });
    const pageW = doc.internal.pageSize.getWidth();

    // ── Header band ───────────────────────────────────────────────────────────
    doc.setFillColor(31, 56, 100);
    doc.rect(0, 0, pageW, 24, 'F');
    // Crest logo (left side of header)
    if (crest) doc.addImage(crest, 'PNG', 5, 2, 20, 20);
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(13);
    doc.setFont('helvetica', 'bold');
    doc.text('City of Harare — Financial Management System', pageW / 2, 10, { align: 'center' });
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.text(pageTitle, pageW / 2, 18, { align: 'center' });

    // ── Meta line ─────────────────────────────────────────────────────────────
    doc.setTextColor(80, 80, 80);
    doc.setFontSize(8);
    const genLine = `Generated: ${new Date().toLocaleString('en-GB')}${subtitle ? '   |   ' + subtitle : ''}`;
    doc.text(genLine, 14, 30);

    // ── Table ─────────────────────────────────────────────────────────────────
    doc.autoTable({
      head: [columns],
      body: rows.map(r => r.map(v => (v === null || v === undefined) ? '' : String(v))),
      startY: 34,
      styles: { fontSize: 7.5, cellPadding: 1.8, overflow: 'linebreak' },
      headStyles: {
        fillColor: [46, 95, 163], textColor: 255,
        fontStyle: 'bold', halign: 'center'
      },
      alternateRowStyles: { fillColor: [242, 246, 252] },
      margin: { left: 14, right: 14 },
      didDrawPage: (data) => {
        // Footer on each page
        const pg = doc.internal.getCurrentPageInfo().pageNumber;
        const total = doc.internal.getNumberOfPages();
        doc.setFontSize(7);
        doc.setTextColor(150);
        doc.text(`Page ${pg} of ${total}`, pageW - 14, doc.internal.pageSize.getHeight() - 6, { align: 'right' });
        doc.text('City of Harare FMS — Confidential', 14, doc.internal.pageSize.getHeight() - 6);
      }
    });

    doc.save(filename || 'export.pdf');
  } catch(e) {
    toast('PDF export failed: ' + e.message, 'error');
  }
}

/**
 * Extract data from an HTML table and export as PDF.
 * @param {string} pageTitle - Report title
 * @param {string} tableSelector - CSS selector or element ID of the <table>
 * @param {string} filename  - Output filename
 * @param {string} [subtitle]
 */
function exportTablePDF(pageTitle, tableSelector, filename, subtitle) {
  const table = typeof tableSelector === 'string'
    ? (document.getElementById(tableSelector) || document.querySelector(tableSelector))
    : tableSelector;
  if (!table) { toast('Table not found', 'error'); return; }

  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  const columns = thead
    ? Array.from(thead.querySelectorAll('th')).map(th => th.textContent.trim()).filter(h => h && h !== 'Actions')
    : [];
  const actionColIdx = thead
    ? Array.from(thead.querySelectorAll('th')).findIndex(th => th.textContent.trim() === 'Actions')
    : -1;

  const rows = tbody ? Array.from(tbody.querySelectorAll('tr')).map(tr => {
    const cells = Array.from(tr.querySelectorAll('td'));
    return cells
      .filter((_, i) => i !== actionColIdx)
      .map(td => td.textContent.trim());
  }).filter(r => r.length > 0 && r.some(c => c)) : [];

  if (rows.length === 0) { toast('No data to export', 'warning'); return; }
  exportPDF(pageTitle, columns, rows, filename, subtitle);
}

// ── Chart Export Utilities ────────────────────────────────────────────────────

/**
 * Download a Chart.js canvas as a PNG image.
 * @param {string} canvasId - ID of the <canvas> element
 * @param {string} [filename]
 */
function downloadChartAsPNG(canvasId, filename) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) { toast('Chart not found', 'error'); return; }
  // Render on white background (canvas is typically transparent)
  const offscreen = document.createElement('canvas');
  offscreen.width  = canvas.width;
  offscreen.height = canvas.height;
  const ctx = offscreen.getContext('2d');
  ctx.fillStyle = '#1a2133'; // dark background to match app theme
  ctx.fillRect(0, 0, offscreen.width, offscreen.height);
  ctx.drawImage(canvas, 0, 0);
  const a = document.createElement('a');
  a.href = offscreen.toDataURL('image/png');
  a.download = filename || 'chart.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Export a Chart.js canvas as a branded PDF.
 * @param {string} canvasId - ID of the <canvas> element
 * @param {string} chartTitle - Title for the PDF header
 * @param {string} [filename]
 * @param {string} [subtitle]
 */
async function exportChartAsPDF(canvasId, chartTitle, filename, subtitle) {
  try {
    await _loadJsPDF();
    const [canvas, crest] = await Promise.all([
      Promise.resolve(document.getElementById(canvasId)),
      _loadCrest()
    ]);
    if (!canvas) { toast('Chart not found', 'error'); return; }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const pageW = doc.internal.pageSize.getWidth();
    const pageH = doc.internal.pageSize.getHeight();

    // Header band
    doc.setFillColor(31, 56, 100);
    doc.rect(0, 0, pageW, 24, 'F');
    if (crest) doc.addImage(crest, 'PNG', 5, 2, 20, 20);
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(13); doc.setFont('helvetica', 'bold');
    doc.text('City of Harare — Financial Management System', pageW / 2, 10, { align: 'center' });
    doc.setFontSize(10); doc.setFont('helvetica', 'normal');
    doc.text(chartTitle, pageW / 2, 18, { align: 'center' });

    // Meta line
    doc.setTextColor(80, 80, 80); doc.setFontSize(8);
    const meta = `Generated: ${new Date().toLocaleString('en-GB')}${subtitle ? '   |   ' + subtitle : ''}`;
    doc.text(meta, 14, 29);

    // Chart image (white bg for PDF)
    const offscreen = document.createElement('canvas');
    offscreen.width = canvas.width; offscreen.height = canvas.height;
    const ctx = offscreen.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, offscreen.width, offscreen.height);
    ctx.drawImage(canvas, 0, 0);
    const imgData = offscreen.toDataURL('image/png');
    const availH = pageH - 42;
    const imgW   = pageW - 28;
    const imgH   = Math.min((canvas.height / canvas.width) * imgW, availH);
    doc.addImage(imgData, 'PNG', 14, 33, imgW, imgH);

    // Footer
    doc.setFontSize(7); doc.setTextColor(150);
    doc.text(`Page 1 of 1`, pageW - 14, pageH - 6, { align: 'right' });
    doc.text('City of Harare FMS — Confidential', 14, pageH - 6);

    doc.save(filename || 'chart.pdf');
  } catch(e) { toast('Chart PDF failed: ' + e.message, 'error'); }
}

// ── Session Timeout ───────────────────────────────────────────────────────────
// Decode JWT expiry and redirect to login before the token expires, giving
// the user a 60-second warning rather than a silent API failure.
(function initSessionTimeout() {
  const token = getToken();
  if (!token) return;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const expiresAt = payload.exp * 1000; // convert seconds → ms
    const now = Date.now();
    const msLeft = expiresAt - now;
    if (msLeft <= 0) { logout(); return; }
    // Warn 60 seconds before expiry
    const warnAt = msLeft - 60000;
    if (warnAt > 0) {
      setTimeout(() => {
        toast('Your session will expire in 60 seconds. Save your work and log in again.', 'warning');
      }, warnAt);
    }
    // Auto-logout at expiry
    setTimeout(() => {
      toast('Session expired. Redirecting to login...', 'error');
      setTimeout(logout, 2000);
    }, msLeft);
  } catch(e) { /* malformed token — will fail on next API call */ }
})();

// ═══════════════════════════════════════════════════════════════════════════════
// AI CHAT WIDGET — disabled; Claude API available at /api/ai/* endpoints
// ═══════════════════════════════════════════════════════════════════════════════
/*
(function initAIChat() {
  function _boot() {
    if (!getToken()) return;
    _buildAIWidget();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _boot);
  } else {
    _boot();
  }

  function _buildAIWidget() {

  const SUGGESTIONS = [
    "What is our current collection rate?",
    "Show me the top 5 overdue accounts",
    "Which revenue category has the lowest collection rate?",
    "Summarise the active leakage alerts",
    "Which departments are over budget?",
    "Show unreconciled payments",
    "What is the monthly revenue trend?",
    "Find anomaly-flagged invoices",
  ];

  // ── Inject styles ──────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
  #ai-fab {
    position:fixed;bottom:28px;right:28px;z-index:9000;
    width:56px;height:56px;border-radius:50%;
    background:linear-gradient(135deg,#4a9eff,#7c5cff);
    border:none;cursor:pointer;box-shadow:0 6px 24px rgba(74,158,255,.4);
    display:flex;align-items:center;justify-content:center;
    transition:transform .2s,box-shadow .2s;
  }
  #ai-fab:hover { transform:scale(1.08); box-shadow:0 10px 32px rgba(74,158,255,.5); }
  #ai-fab svg { pointer-events:none; }
  #ai-fab .ai-badge {
    position:absolute;top:-4px;right:-4px;
    width:18px;height:18px;border-radius:50%;
    background:#2ecc71;border:2px solid #07091a;
    font-size:9px;font-weight:700;color:#fff;
    display:flex;align-items:center;justify-content:center;
  }
  #ai-fab .ai-badge.offline { background:#e74c3c; }

  #ai-panel {
    position:fixed;bottom:96px;right:28px;z-index:9000;
    width:380px;max-width:calc(100vw - 40px);
    background:#0d1128;
    border:1px solid rgba(255,255,255,.1);
    border-radius:20px;
    box-shadow:0 24px 80px rgba(0,0,0,.6);
    display:flex;flex-direction:column;
    overflow:hidden;
    transform:translateY(20px) scale(.96);opacity:0;pointer-events:none;
    transition:transform .25s cubic-bezier(.16,1,.3,1),opacity .25s;
    max-height:calc(100vh - 140px);
  }
  #ai-panel.open { transform:translateY(0) scale(1);opacity:1;pointer-events:all; }

  #ai-panel-header {
    display:flex;align-items:center;gap:10px;
    padding:14px 16px;
    background:linear-gradient(135deg,rgba(74,158,255,.12),rgba(124,92,255,.08));
    border-bottom:1px solid rgba(255,255,255,.07);
    flex-shrink:0;
  }
  #ai-panel-header .ai-avatar {
    width:36px;height:36px;border-radius:50%;flex-shrink:0;
    background:linear-gradient(135deg,#4a9eff,#7c5cff);
    display:flex;align-items:center;justify-content:center;font-size:17px;
  }
  #ai-panel-header .ai-title { font-weight:700;font-size:14px;color:#eef0f8; }
  #ai-panel-header .ai-sub { font-size:10.5px;color:#5e6888; margin-top:1px; }
  #ai-panel-header .ai-close {
    margin-left:auto;background:none;border:none;cursor:pointer;
    color:#5e6888;padding:6px;border-radius:8px;display:flex;
    transition:color .2s,background .2s;
  }
  #ai-panel-header .ai-close:hover { color:#eef0f8;background:rgba(255,255,255,.07); }

  #ai-messages {
    flex:1;overflow-y:auto;padding:14px;
    display:flex;flex-direction:column;gap:10px;
    min-height:200px;
    scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.1) transparent;
  }
  #ai-messages::-webkit-scrollbar { width:4px; }
  #ai-messages::-webkit-scrollbar-thumb { background:rgba(255,255,255,.1);border-radius:2px; }

  .ai-msg { display:flex;gap:8px;animation:aiMsgIn .25s cubic-bezier(.16,1,.3,1); }
  @keyframes aiMsgIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
  .ai-msg.user { flex-direction:row-reverse; }

  .ai-bubble {
    max-width:85%;padding:10px 13px;border-radius:14px;font-size:13px;line-height:1.65;
    word-break:break-word;
  }
  .ai-msg.assistant .ai-bubble {
    background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.07);
    color:#d0d6e8;border-top-left-radius:4px;
  }
  .ai-msg.user .ai-bubble {
    background:linear-gradient(135deg,rgba(74,158,255,.25),rgba(124,92,255,.2));
    border:1px solid rgba(74,158,255,.3);color:#eef0f8;border-top-right-radius:4px;
  }
  .ai-bubble strong { color:#eef0f8; }
  .ai-bubble ul { padding-left:16px;margin:6px 0; }
  .ai-bubble li { margin-bottom:3px; }
  .ai-bubble code {
    background:rgba(255,255,255,.08);padding:1px 5px;border-radius:4px;
    font-family:'DM Mono',monospace;font-size:11.5px;
  }

  .ai-typing {
    display:flex;align-items:center;gap:4px;padding:10px 13px;
    background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);
    border-radius:14px;border-top-left-radius:4px;width:fit-content;
  }
  .ai-typing span {
    width:6px;height:6px;border-radius:50%;background:#4a9eff;
    animation:aiDot 1.2s ease-in-out infinite;
  }
  .ai-typing span:nth-child(2){animation-delay:.2s}
  .ai-typing span:nth-child(3){animation-delay:.4s}
  @keyframes aiDot{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1)}}

  #ai-suggestions {
    padding:10px 14px 4px;
    display:flex;flex-wrap:wrap;gap:6px;
    flex-shrink:0;
  }
  .ai-suggestion {
    background:rgba(74,158,255,.08);border:1px solid rgba(74,158,255,.2);
    color:#74b8ff;font-size:11px;padding:5px 10px;border-radius:20px;
    cursor:pointer;transition:all .18s;white-space:nowrap;
  }
  .ai-suggestion:hover { background:rgba(74,158,255,.18);border-color:rgba(74,158,255,.4); }

  #ai-input-row {
    display:flex;align-items:flex-end;gap:8px;
    padding:10px 14px 14px;
    border-top:1px solid rgba(255,255,255,.07);
    flex-shrink:0;
  }
  #ai-input {
    flex:1;background:rgba(255,255,255,.05);
    border:1.5px solid rgba(255,255,255,.1);border-radius:12px;
    color:#eef0f8;font-family:'DM Sans',sans-serif;font-size:13px;
    padding:10px 12px;outline:none;resize:none;
    max-height:100px;min-height:40px;line-height:1.5;
    transition:border-color .2s;
    scrollbar-width:thin;
  }
  #ai-input:focus { border-color:#4a9eff; }
  #ai-input::placeholder { color:#5e6888; }
  #ai-send {
    width:38px;height:38px;flex-shrink:0;border-radius:10px;
    background:linear-gradient(135deg,#4a9eff,#7c5cff);
    border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;
    transition:transform .15s,opacity .15s;
  }
  #ai-send:hover:not(:disabled) { transform:scale(1.08); }
  #ai-send:disabled { opacity:.45;cursor:not-allowed; }
  #ai-send svg { pointer-events:none; }

  #ai-clear {
    width:100%;background:none;border:none;cursor:pointer;
    color:#5e6888;font-size:11px;padding:4px 0 2px;
    text-align:center;transition:color .2s;
  }
  #ai-clear:hover { color:#9aa2be; }

  @media(max-width:480px){
    #ai-panel { right:14px;bottom:90px;width:calc(100vw - 28px); }
    #ai-fab { bottom:18px;right:18px; }
  }
  `;
  document.head.appendChild(style);

  // ── Build DOM ──────────────────────────────────────────────────────────────
  const fab = document.createElement('button');
  fab.id = 'ai-fab';
  fab.title = 'AI Financial Assistant';
  fab.innerHTML = `
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
      <path d="M12 2a7 7 0 0 1 7 7c0 3-1.6 5.5-4 6.7V17a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.3C6.6 14.5 5 12 5 9a7 7 0 0 1 7-7z"/>
      <path d="M9 21h6M10 17v1M14 17v1"/>
    </svg>
    <div class="ai-badge" id="aiBadge">✓</div>`;

  const panel = document.createElement('div');
  panel.id = 'ai-panel';
  panel.innerHTML = `
    <div id="ai-panel-header">
      <div class="ai-avatar">🤖</div>
      <div>
        <div class="ai-title">FMS AI Assistant</div>
        <div class="ai-sub">Powered by Claude · Live financial data</div>
      </div>
      <button class="ai-close" id="aiClose" title="Close">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
    <div id="ai-messages"></div>
    <div id="ai-suggestions"></div>
    <div id="ai-input-row">
      <textarea id="ai-input" placeholder="Ask about revenue, leakage, debtors…" rows="1"></textarea>
      <button id="ai-send" title="Send">
        <svg width="17" height="17" fill="none" stroke="#fff" stroke-width="2.2" viewBox="0 0 24 24">
          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
    <button id="ai-clear">Clear conversation</button>`;

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  // ── State ──────────────────────────────────────────────────────────────────
  let open = false;
  let loading = false;
  let history = [];         // [{role, content}]
  let aiReady = false;

  // ── Check AI status ────────────────────────────────────────────────────────
  apiFetch('/api/ai/status').then(s => {
    aiReady = s?.available;
    const badge = document.getElementById('aiBadge');
    if (!aiReady) {
      badge.textContent = '!';
      badge.classList.add('offline');
    }
  }).catch(() => {});

  // ── Toggle panel ───────────────────────────────────────────────────────────
  function togglePanel() {
    open = !open;
    panel.classList.toggle('open', open);
    if (open) {
      if (history.length === 0) showWelcome();
      setTimeout(() => document.getElementById('ai-input')?.focus(), 150);
    }
  }

  fab.addEventListener('click', togglePanel);
  document.getElementById('aiClose').addEventListener('click', () => {
    open = false; panel.classList.remove('open');
  });

  // ── Welcome message ────────────────────────────────────────────────────────
  function showWelcome() {
    const user = getUser();
    appendMessage('assistant',
      `Hello${user?.full_name ? ', ' + user.full_name.split(' ')[0] : ''}! I'm your FMS AI assistant — I have live access to the City of Harare financial database.\n\nYou can ask me anything about revenue, collections, overdue accounts, budgets, or leakage risks. Try one of the suggestions below, or type your own question.`
    );
    renderSuggestions(SUGGESTIONS.slice(0, 4));
  }

  // ── Render suggestions ────────────────────────────────────────────────────
  function renderSuggestions(list) {
    const el = document.getElementById('ai-suggestions');
    el.innerHTML = ''; // Clear existing
    list.forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'ai-suggestion';
      btn.textContent = s;
      btn.onclick = () => aiAsk(s);
      el.appendChild(btn);
    });
  }

  // ── Append message ────────────────────────────────────────────────────────
  function appendMessage(role, content) {
    const msgs = document.getElementById('ai-messages');
    const div = document.createElement('div');
    div.className = `ai-msg ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'ai-bubble';
    bubble.innerHTML = formatAIResponse(content);
    div.appendChild(bubble);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function formatAIResponse(text) {
    let s = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    s = s.replace(/[*][*](.+?)[*][*]/g, '<strong>$1</strong>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/^•\s(.+)$/gm, '<li>$1</li>');
    s = s.replace(/^-\s(.+)$/gm, '<li>$1</li>');
    s = s.replace(/\n{2,}/g, '<br><br>');
    s = s.replace(/\n/g, '<br>');
    return s;
  }

  // ── Typing indicator ──────────────────────────────────────────────────────
  function showTyping() {
    const msgs = document.getElementById('ai-messages');
    const div = document.createElement('div');
    div.className = 'ai-msg assistant';
    div.id = 'ai-typing-msg';
    div.innerHTML = `<div class="ai-typing"><span></span><span></span><span></span></div>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }
  function hideTyping() {
    document.getElementById('ai-typing-msg')?.remove();
  }

  // ── Send message ──────────────────────────────────────────────────────────
  window.aiAsk = async function(text) {
    if (!text?.trim() || loading) return;
    if (!aiReady) {
      appendMessage('assistant', '⚠️ The AI assistant is not available in this version.');
      return;
    }

    const inputEl = document.getElementById('ai-input');
    const sendBtn = document.getElementById('ai-send');
    const sugEl   = document.getElementById('ai-suggestions');

    appendMessage('user', text);
    history.push({ role: 'user', content: text });
    if (inputEl) inputEl.value = '';
    sugEl.innerHTML = '';
    loading = true;
    sendBtn.disabled = true;

    showTyping();
    try {
      const res = await apiFetch('/api/ai/chat', {
        method: 'POST',
        body: JSON.stringify({ messages: history })
      });
      hideTyping();
      const reply = res?.response || 'No response received.';
      appendMessage('assistant', reply);
      history.push({ role: 'assistant', content: reply });

      // Show follow-up suggestions
      renderSuggestions(SUGGESTIONS.filter(s => s !== text).slice(0, 3));
    } catch(e) {
      hideTyping();
      appendMessage('assistant', `⚠️ Error: ${e.message}`);
    }
    loading = false;
    sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
  };

  // ── Input handlers ────────────────────────────────────────────────────────
  const inputEl = document.getElementById('ai-input');
  const sendBtn = document.getElementById('ai-send');

  sendBtn.addEventListener('click', () => aiAsk(inputEl.value.trim()));
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); aiAsk(inputEl.value.trim()); }
  });
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
  });

  document.getElementById('ai-clear').addEventListener('click', () => {
    history = [];
    document.getElementById('ai-messages').innerHTML = '';
    document.getElementById('ai-suggestions').innerHTML = '';
    showWelcome();
  });
  } // end _buildAIWidget
})();
*/
