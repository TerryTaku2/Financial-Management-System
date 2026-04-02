// ── Config ──────────────────────────────────────────────────────────────
const API = 'http://localhost:8000';

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
  t.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ️'}</span><span class="toast-msg">${msg}</span>`;
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Sidebar ──────────────────────────────────────────────────────────────
function buildSidebar(activePage) {
  const user = getUser();
  const role = user?.role || '';
  const navItems = [
    { label: 'Dashboard',        icon: '📊', page: 'dashboard',    href: 'dashboard.html',    roles: [] },
    { label: 'Ratepayers',       icon: '👤', page: 'ratepayers',   href: 'ratepayers.html',   roles: [] },
    { label: 'Invoices',         icon: '🧾', page: 'invoices',     href: 'invoices.html',     roles: [] },
    { label: 'Payments',         icon: '💳', page: 'payments',     href: 'payments.html',     roles: [] },
    { label: 'Expenditure',      icon: '💸', page: 'expenditures', href: 'expenditures.html', roles: [] },
    { label: 'Budget',           icon: '📁', page: 'budget',       href: 'budget.html',       roles: [] },
    { label: 'Leakage Monitor',  icon: '🔍', page: 'leakage',      href: 'leakage.html',      roles: [] },
    { label: 'Audit Trail',      icon: '📋', page: 'audit',        href: 'audit.html',        roles: ['admin','auditor'] },
    { label: 'Reports',          icon: '📈', page: 'reports',      href: 'reports.html',      roles: ['admin','auditor','accountant','budget_officer'] },
    { label: 'Aging Analysis',   icon: '⏳', page: 'aging',        href: 'aging.html',        roles: [] },
    { label: 'User Management',  icon: '👥', page: 'users',        href: 'users.html',        roles: ['admin'] },
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
          <div class="logo-icon">🏛️</div>
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
      </div>`;
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
