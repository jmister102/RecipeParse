// ── Auth state ────────────────────────────────────────────

let authToken = localStorage.getItem('recipes_token');
let currentUser = null;

// ── App state ─────────────────────────────────────────────

let allRecipes = [];
let filteredRecipes = [];

// ── DOM refs ──────────────────────────────────────────────

const authView   = document.getElementById('auth-view');
const appView    = document.getElementById('app-view');
const userLabel  = document.getElementById('user-label');
const logoutBtn  = document.getElementById('logout-btn');

const searchInput    = document.getElementById('search-input');
const categoryFilter = document.getElementById('category-filter');
const sortSelect     = document.getElementById('sort-select');
const addBtn         = document.getElementById('add-btn');
const gridContainer  = document.getElementById('grid-container');
const loading        = document.getElementById('loading');
const emptyState     = document.getElementById('empty-state');
const statsBar       = document.getElementById('stats-bar');

const detailOverlay = document.getElementById('detail-overlay');
const detailContent = document.getElementById('detail-content');
const detailClose   = document.getElementById('detail-close');

const addOverlay    = document.getElementById('add-overlay');
const addClose      = document.getElementById('add-close');
const addUrlInput   = document.getElementById('add-url-input');
const addSubmitBtn  = document.getElementById('add-submit-btn');
const addStatus     = document.getElementById('add-status');

// Auth form elements
const authTabs      = document.querySelectorAll('.auth-tab');
const loginForm     = document.getElementById('login-form');
const registerForm  = document.getElementById('register-form');
const loginError    = document.getElementById('login-error');
const registerError = document.getElementById('register-error');

// ── API ───────────────────────────────────────────────────

async function fetchJson(url, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const res = await fetch(url, { ...opts, headers });
  const data = await res.json();
  if (res.status === 401) {
    logout();
    throw new Error('Session expired — please sign in again');
  }
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// ── Auth ──────────────────────────────────────────────────

function showAuth() {
  authView.hidden = false;
  appView.hidden  = true;
}

function showApp(username) {
  authView.hidden = false; // stays in DOM but hidden
  authView.hidden = true;
  appView.hidden  = false;
  userLabel.textContent = username;
  loadCategories();
  loadRecipes();
}

function logout() {
  localStorage.removeItem('recipes_token');
  localStorage.removeItem('recipes_user');
  authToken   = null;
  currentUser = null;
  allRecipes  = [];
  categoryFilter.innerHTML = '<option value="">All categories</option>';
  showAuth();
}

logoutBtn.addEventListener('click', logout);

// Auth tabs
authTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    authTabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    loginForm.hidden    = target !== 'login';
    registerForm.hidden = target !== 'register';
    loginError.textContent    = '';
    registerError.textContent = '';
  });
});

// Login
loginForm.addEventListener('submit', async e => {
  e.preventDefault();
  loginError.textContent = '';
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const btn = loginForm.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = 'Signing in…';
  try {
    const data = await fetch('api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const json = await data.json();
    if (!data.ok) throw new Error(json.detail || 'Login failed');
    authToken = json.token;
    localStorage.setItem('recipes_token', authToken);
    localStorage.setItem('recipes_user', json.username);
    showApp(json.username);
  } catch (err) {
    loginError.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in';
  }
});

// Register
registerForm.addEventListener('submit', async e => {
  e.preventDefault();
  registerError.textContent = '';
  const username = document.getElementById('reg-username').value.trim();
  const email    = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const btn = registerForm.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = 'Creating account…';
  try {
    const data = await fetch('api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });
    const json = await data.json();
    if (!data.ok) throw new Error(json.detail || 'Registration failed');
    authToken = json.token;
    localStorage.setItem('recipes_token', authToken);
    localStorage.setItem('recipes_user', json.username);
    showApp(json.username);
  } catch (err) {
    registerError.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create account';
  }
});

// ── Render helpers ────────────────────────────────────────

function esc(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function statusDot(status) {
  return `<span class="status-dot status-${status}" title="${status}"></span>`;
}

function placeholder() {
  const d = document.createElement('div');
  d.className = 'card-img-placeholder';
  d.textContent = '🍽️';
  return d;
}

function cardHtml(recipe) {
  const img = recipe.image_url
    ? `<img class="card-img" src="${esc(recipe.image_url)}" alt="" loading="lazy" onerror="this.replaceWith(placeholder())">`
    : `<div class="card-img-placeholder">🍽️</div>`;
  const badge = recipe.category
    ? `<span class="badge">${esc(recipe.category)}</span>` : '';
  return `
    <article class="recipe-card" data-id="${recipe.id}" role="button" tabindex="0">
      ${img}
      <button class="card-delete" data-id="${recipe.id}" aria-label="Remove recipe" title="Remove recipe">✕</button>
      <div class="card-body">
        <div class="card-title">${esc(recipe.title || 'Untitled Recipe')}</div>
        <div class="card-meta">
          ${statusDot(recipe.scrape_status || 'pending')}
          <span>${esc(recipe.source_site || '')}</span>
          ${badge}
        </div>
      </div>
    </article>`;
}

// ── Grid ──────────────────────────────────────────────────

function renderGrid(recipes) {
  gridContainer.querySelectorAll('.recipe-card').forEach(el => el.remove());
  emptyState.hidden = recipes.length > 0;
  recipes.forEach(r => {
    const tmp = document.createElement('div');
    tmp.innerHTML = cardHtml(r);
    const card = tmp.firstElementChild;
    card.addEventListener('click', e => {
      if (e.target.closest('.card-delete')) return;
      openDetail(r.id);
    });
    card.addEventListener('keydown', e => { if (e.key === 'Enter') openDetail(r.id); });
    card.querySelector('.card-delete').addEventListener('click', e => {
      e.stopPropagation();
      deleteRecipe(r.id, r.title, card);
    });
    gridContainer.appendChild(card);
  });
}

function applyFilters() {
  const q   = searchInput.value.trim().toLowerCase();
  const cat = categoryFilter.value;
  const sort = sortSelect.value;
  filteredRecipes = allRecipes.filter(r => {
    const matchQ = !q
      || (r.title || '').toLowerCase().includes(q)
      || (r.description || '').toLowerCase().includes(q)
      || (r.source_site || '').toLowerCase().includes(q);
    const matchCat = !cat || r.category === cat;
    return matchQ && matchCat;
  });
  filteredRecipes.sort((a, b) => {
    if (sort === 'title') return (a.title || '').localeCompare(b.title || '');
    const da = a.date_added || '';
    const db = b.date_added || '';
    return sort === 'date-asc' ? da.localeCompare(db) : db.localeCompare(da);
  });
  renderGrid(filteredRecipes);
  statsBar.textContent = filteredRecipes.length === allRecipes.length
    ? `${allRecipes.length} recipe${allRecipes.length !== 1 ? 's' : ''}`
    : `${filteredRecipes.length} of ${allRecipes.length} recipes`;
}

async function deleteRecipe(id, title, cardEl) {
  if (!confirm(`Remove "${title || 'this recipe'}" from your collection?`)) return;
  try {
    await fetchJson(`api/recipes/${id}`, { method: 'DELETE' });
    allRecipes = allRecipes.filter(r => r.id !== id);
    cardEl.remove();
    filteredRecipes = filteredRecipes.filter(r => r.id !== id);
    emptyState.hidden = filteredRecipes.length > 0;
    statsBar.textContent = filteredRecipes.length === allRecipes.length
      ? `${allRecipes.length} recipe${allRecipes.length !== 1 ? 's' : ''}`
      : `${filteredRecipes.length} of ${allRecipes.length} recipes`;
  } catch (err) {
    alert('Could not remove recipe: ' + err.message);
  }
}

// ── Load data ─────────────────────────────────────────────

async function loadRecipes() {
  loading.hidden = false;
  try {
    allRecipes = await fetchJson('api/recipes');
    loading.hidden = true;
    applyFilters();
  } catch (err) {
    loading.textContent = 'Failed to load recipes: ' + err.message;
  }
}

async function loadCategories() {
  try {
    const cats = await fetchJson('api/categories');
    categoryFilter.innerHTML = '<option value="">All categories</option>';
    cats.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat; opt.textContent = cat;
      categoryFilter.appendChild(opt);
    });
  } catch (_) {}
}

// ── Detail modal ──────────────────────────────────────────

async function openDetail(id) {
  detailContent.innerHTML = '<div class="loading" style="padding:60px">Loading…</div>';
  detailOverlay.hidden = false;
  document.body.style.overflow = 'hidden';
  try {
    const r = await fetchJson(`api/recipes/${id}`);
    const hasFull = r.ingredients.length > 0 || r.instructions.length > 0;
    const heroImg = r.image_url
      ? `<img class="detail-hero" src="${esc(r.image_url)}" alt="" onerror="this.remove()">` : '';
    const cookMeta  = r.cook_time ? `· ${esc(r.cook_time)}` : '';
    const yieldMeta = r.yields   ? `· Serves ${esc(r.yields)}` : '';
    const ingredientsHtml  = r.ingredients.length > 0
      ? `<ul class="ingredients-list">${r.ingredients.map(i => `<li>${esc(i)}</li>`).join('')}</ul>` : '';
    const instructionsHtml = r.instructions.length > 0
      ? `<ol class="instructions-list">${r.instructions.map(s => `<li>${esc(s)}</li>`).join('')}</ol>` : '';
    const noDataNotice = !hasFull
      ? `<div class="no-data-notice">Recipe details couldn't be extracted automatically.
           <a href="${esc(r.url)}" target="_blank" rel="noopener">Open original recipe ↗</a></div>` : '';
    detailContent.innerHTML = `
      ${heroImg}
      <div class="detail-body">
        <h2 class="detail-title">${esc(r.title || 'Untitled Recipe')}</h2>
        <div class="detail-meta">
          <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.source_site || r.url)} ↗</a>
          ${r.category ? `<span class="badge">${esc(r.category)}</span>` : ''}
          <span>${cookMeta} ${yieldMeta}</span>
        </div>
        ${noDataNotice}
        ${hasFull ? `<div class="detail-columns">
          <div class="detail-section"><h3>Ingredients</h3>${ingredientsHtml || '<p style="color:var(--text-muted);font-size:.875rem">Not available</p>'}</div>
          <div class="detail-section"><h3>Instructions</h3>${instructionsHtml || '<p style="color:var(--text-muted);font-size:.875rem">Not available</p>'}</div>
        </div>` : ''}
      </div>`;
  } catch (err) {
    detailContent.innerHTML = `<div class="detail-body"><p style="color:var(--danger)">Error: ${esc(err.message)}</p></div>`;
  }
}

function closeDetail() {
  detailOverlay.hidden = true;
  document.body.style.overflow = '';
}

detailClose.addEventListener('click', closeDetail);
detailOverlay.addEventListener('click', e => { if (e.target === detailOverlay) closeDetail(); });

// ── Add recipe ────────────────────────────────────────────

function openAdd() {
  addOverlay.hidden = false;
  addUrlInput.value = '';
  addStatus.textContent = '';
  addStatus.className = '';
  document.body.style.overflow = 'hidden';
  addUrlInput.focus();
}

function closeAdd() {
  addOverlay.hidden = true;
  document.body.style.overflow = '';
}

addBtn.addEventListener('click', openAdd);
addClose.addEventListener('click', closeAdd);
addOverlay.addEventListener('click', e => { if (e.target === addOverlay) closeAdd(); });
addSubmitBtn.addEventListener('click', submitAdd);
addUrlInput.addEventListener('keydown', e => { if (e.key === 'Enter') submitAdd(); });

async function submitAdd() {
  const url = addUrlInput.value.trim();
  if (!url) { addStatus.textContent = 'Please enter a URL.'; addStatus.className = 'error'; return; }
  addSubmitBtn.disabled = true;
  addStatus.innerHTML = '<span class="spinner"></span> Scraping recipe…';
  addStatus.className = '';
  try {
    const recipe = await fetchJson('api/recipes', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
    addStatus.innerHTML = `✓ Added: <strong>${esc(recipe.title || 'Recipe')}</strong>`;
    addStatus.className = 'success';
    if (recipe.category && !Array.from(categoryFilter.options).some(o => o.value === recipe.category)) {
      const opt = document.createElement('option');
      opt.value = recipe.category; opt.textContent = recipe.category;
      categoryFilter.appendChild(opt);
    }
    const card = {
      id: recipe.id, url: recipe.url, title: recipe.title,
      image_url: recipe.image_url, source_site: recipe.source_site,
      category: recipe.category, scrape_status: recipe.scrape_status,
      description: recipe.description, cook_time: recipe.cook_time, yields: recipe.yields,
    };
    allRecipes.unshift(card);
    applyFilters();
    setTimeout(() => { closeAdd(); openDetail(recipe.id); }, 1200);
  } catch (err) {
    const msg = err.message.includes('already') ? 'This recipe is already in your collection.' : err.message;
    addStatus.textContent = '✗ ' + msg;
    addStatus.className = 'error';
  } finally {
    addSubmitBtn.disabled = false;
  }
}

// ── Keyboard ──────────────────────────────────────────────

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (!detailOverlay.hidden) closeDetail();
    else if (!addOverlay.hidden) closeAdd();
  }
});

// ── Event wiring ──────────────────────────────────────────

searchInput.addEventListener('input', applyFilters);
categoryFilter.addEventListener('change', applyFilters);
sortSelect.addEventListener('change', applyFilters);

// ── Init ──────────────────────────────────────────────────

if (authToken) {
  const savedUser = localStorage.getItem('recipes_user') || '';
  showApp(savedUser);
} else {
  showAuth();
}
