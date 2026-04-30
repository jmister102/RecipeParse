// ── Auth state ────────────────────────────────────────────

let authToken = localStorage.getItem('recipes_token');
let currentUser = null;

// ── App state ─────────────────────────────────────────────

let allRecipes = [];
let filteredRecipes = [];
let starFilterActive = false;

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
const statsBar           = document.getElementById('stats-bar');
const starredFilterBtn   = document.getElementById('starred-filter-btn');

const detailOverlay = document.getElementById('detail-overlay');
const detailContent = document.getElementById('detail-content');
const detailClose   = document.getElementById('detail-close');

const addOverlay    = document.getElementById('add-overlay');
const addClose      = document.getElementById('add-close');
const addUrlInput   = document.getElementById('add-url-input');
const addSubmitBtn  = document.getElementById('add-submit-btn');
const addStatus     = document.getElementById('add-status');
const addTabBtns     = document.querySelectorAll('.add-tab');
const addUrlPanel    = document.getElementById('add-url-panel');
const addPhotoPanel  = document.getElementById('add-photo-panel');
const addManualPanel = document.getElementById('add-manual-panel');
const manualForm     = document.getElementById('manual-form');

const photoDropzone   = document.getElementById('photo-dropzone');
const photoFileInput  = document.getElementById('photo-file-input');
const photoSubmitBtn  = document.getElementById('photo-submit-btn');
const photoDropInner  = document.getElementById('photo-dropzone-inner');

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
  const starLabel = recipe.starred ? 'Remove from favorites' : 'Add to favorites';
  return `
    <article class="recipe-card" data-id="${recipe.id}" role="button" tabindex="0">
      ${img}
      <button class="card-delete" data-id="${recipe.id}" aria-label="Remove recipe" title="Remove recipe">✕</button>
      <button class="card-star${recipe.starred ? ' starred' : ''}" data-id="${recipe.id}" aria-label="${starLabel}" title="${starLabel}">${recipe.starred ? '★' : '☆'}</button>
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
    card.querySelector('.card-star').addEventListener('click', async e => {
      e.stopPropagation();
      const btn = e.currentTarget;
      const recipe = allRecipes.find(rc => rc.id === r.id);
      if (!recipe) return;
      const newStarred = !recipe.starred;
      try {
        await fetchJson(`api/recipes/${r.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ starred: newStarred }),
        });
        recipe.starred = newStarred;
        btn.className = `card-star${newStarred ? ' starred' : ''}`;
        btn.textContent = newStarred ? '★' : '☆';
        const label = newStarred ? 'Remove from favorites' : 'Add to favorites';
        btn.setAttribute('aria-label', label);
        btn.setAttribute('title', label);
      } catch (err) {
        alert('Could not update favorite: ' + err.message);
      }
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
    const matchStar = !starFilterActive || r.starred;
    return matchQ && matchCat && matchStar;
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

    const existingCats = Array.from(categoryFilter.options)
      .filter(o => o.value).map(o => o.value);
    if (r.category && !existingCats.includes(r.category)) existingCats.push(r.category);
    const catOptions = `<option value="">No category</option>` +
      existingCats.map(c => `<option value="${esc(c)}"${c === r.category ? ' selected' : ''}>${esc(c)}</option>`).join('') +
      `<option value="__new__">+ New category…</option>`;
    const catDisplayHtml = r.category
      ? `<span class="badge">${esc(r.category)}</span>`
      : `<span class="no-category">No category</span>`;

    detailContent.innerHTML = `
      ${heroImg}
      <div class="detail-body">
        <div class="detail-title-row">
          <h2 class="detail-title">${esc(r.title || 'Untitled Recipe')}</h2>
          <button class="detail-star${r.starred ? ' starred' : ''}" id="detail-star">${r.starred ? '★ Favorited' : '☆ Favorite'}</button>
        </div>
        <div class="detail-meta">
          <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.source_site || r.url)} ↗</a>
          <span class="category-edit-wrap">
            <span id="category-display">${catDisplayHtml}</span>
            <button class="edit-category-btn" id="edit-category-btn" aria-label="Edit category" title="Edit category">✎</button>
          </span>
          <span class="category-editor" id="category-editor" hidden>
            <select id="category-select">${catOptions}</select>
            <input type="text" id="new-category-input" placeholder="Category name…" hidden>
            <button class="btn-primary btn-sm" id="save-category-btn">Save</button>
            <button class="btn-ghost btn-sm" id="cancel-category-btn">Cancel</button>
          </span>
          <span>${cookMeta} ${yieldMeta}</span>
        </div>
        ${noDataNotice}
        ${hasFull ? `<div class="detail-columns">
          <div class="detail-section"><h3>Ingredients</h3>${ingredientsHtml || '<p style="color:var(--text-muted);font-size:.875rem">Not available</p>'}</div>
          <div class="detail-section"><h3>Instructions</h3>${instructionsHtml || '<p style="color:var(--text-muted);font-size:.875rem">Not available</p>'}</div>
        </div>` : ''}
        <div class="notes-section">
          <h3>My Notes</h3>
          <textarea class="notes-textarea" id="notes-textarea" placeholder="Add your notes, substitutions, tips…">${esc(r.notes || '')}</textarea>
          <span class="notes-status" id="notes-status"></span>
        </div>
      </div>`;

    // ── Star toggle ──
    const detailStar = document.getElementById('detail-star');
    detailStar.addEventListener('click', async () => {
      const newStarred = !r.starred;
      try {
        await fetchJson(`api/recipes/${id}`, {
          method: 'PATCH',
          body: JSON.stringify({ starred: newStarred }),
        });
        r.starred = newStarred;
        detailStar.className = `detail-star${newStarred ? ' starred' : ''}`;
        detailStar.textContent = newStarred ? '★ Favorited' : '☆ Favorite';
        const recipeInAll = allRecipes.find(rc => rc.id === id);
        if (recipeInAll) recipeInAll.starred = newStarred;
        const cardEl = gridContainer.querySelector(`[data-id="${id}"]`);
        if (cardEl) {
          const btn = cardEl.querySelector('.card-star');
          if (btn) {
            btn.className = `card-star${newStarred ? ' starred' : ''}`;
            btn.textContent = newStarred ? '★' : '☆';
            const label = newStarred ? 'Remove from favorites' : 'Add to favorites';
            btn.setAttribute('aria-label', label);
            btn.setAttribute('title', label);
          }
        }
      } catch (err) {
        alert('Could not update favorite: ' + err.message);
      }
    });

    // ── Category editor ──
    const categoryDisplayEl = document.getElementById('category-display');
    const categoryEditorEl  = document.getElementById('category-editor');
    const editCategoryBtn   = document.getElementById('edit-category-btn');
    const categorySelect    = document.getElementById('category-select');
    const newCategoryInput  = document.getElementById('new-category-input');
    const saveCategoryBtn   = document.getElementById('save-category-btn');
    const cancelCategoryBtn = document.getElementById('cancel-category-btn');

    editCategoryBtn.addEventListener('click', () => {
      categoryDisplayEl.hidden = true;
      editCategoryBtn.hidden   = true;
      categoryEditorEl.hidden  = false;
    });
    categorySelect.addEventListener('change', () => {
      newCategoryInput.hidden = categorySelect.value !== '__new__';
      if (!newCategoryInput.hidden) newCategoryInput.focus();
    });
    cancelCategoryBtn.addEventListener('click', () => {
      categoryDisplayEl.hidden = false;
      editCategoryBtn.hidden   = false;
      categoryEditorEl.hidden  = true;
    });
    saveCategoryBtn.addEventListener('click', async () => {
      const newCat = categorySelect.value === '__new__'
        ? newCategoryInput.value.trim()
        : categorySelect.value;
      try {
        await fetchJson(`api/recipes/${id}`, {
          method: 'PATCH',
          body: JSON.stringify({ category: newCat }),
        });
        r.category = newCat || null;
        const recipeInAll = allRecipes.find(rc => rc.id === id);
        if (recipeInAll) recipeInAll.category = newCat || null;
        if (newCat && !Array.from(categoryFilter.options).some(o => o.value === newCat)) {
          const opt = document.createElement('option');
          opt.value = newCat; opt.textContent = newCat;
          categoryFilter.appendChild(opt);
        }
        categoryDisplayEl.innerHTML = newCat
          ? `<span class="badge">${esc(newCat)}</span>`
          : `<span class="no-category">No category</span>`;
        categoryDisplayEl.hidden = false;
        editCategoryBtn.hidden   = false;
        categoryEditorEl.hidden  = true;
        const cardEl = gridContainer.querySelector(`[data-id="${id}"]`);
        if (cardEl) {
          const metaEl  = cardEl.querySelector('.card-meta');
          const badgeEl = metaEl.querySelector('.badge');
          if (newCat) {
            if (badgeEl) badgeEl.textContent = newCat;
            else metaEl.insertAdjacentHTML('beforeend', `<span class="badge">${esc(newCat)}</span>`);
          } else if (badgeEl) {
            badgeEl.remove();
          }
        }
      } catch (err) {
        alert('Could not update category: ' + err.message);
      }
    });

    // ── Notes ──
    const textarea = document.getElementById('notes-textarea');
    const notesStatus = document.getElementById('notes-status');
    let saveTimer = null;
    textarea.addEventListener('input', () => {
      notesStatus.textContent = '';
      clearTimeout(saveTimer);
      saveTimer = setTimeout(async () => {
        try {
          await fetchJson(`api/recipes/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ notes: textarea.value }),
          });
          notesStatus.textContent = 'Saved ✓';
          setTimeout(() => { notesStatus.textContent = ''; }, 2000);
        } catch {
          notesStatus.textContent = 'Save failed';
        }
      }, 800);
    });
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

function resetPhotoPanel() {
  photoFileInput.value = '';
  photoSubmitBtn.disabled = true;
  photoDropzone.classList.remove('has-image', 'drag-over');
  photoDropInner.innerHTML = `
    <span class="photo-dropzone-icon">📷</span>
    <span class="photo-dropzone-text">Click to choose a photo<br><small>or drag &amp; drop here</small></span>`;
  photoDropInner.style.display = '';
  // Remove any preview image
  const prev = photoDropzone.querySelector('.photo-preview');
  if (prev) prev.remove();
}

function openAdd() {
  addOverlay.hidden = false;
  addUrlInput.value = '';
  addStatus.textContent = '';
  addStatus.className = '';
  manualForm.reset();
  resetPhotoPanel();
  // always open on URL tab
  addTabBtns.forEach(t => t.classList.toggle('active', t.dataset.tab === 'url'));
  addUrlPanel.hidden  = false;
  addPhotoPanel.hidden = true;
  addManualPanel.hidden = true;
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

// Add modal tabs
addTabBtns.forEach(tab => {
  tab.addEventListener('click', () => {
    addTabBtns.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    addUrlPanel.hidden   = tab.dataset.tab !== 'url';
    addPhotoPanel.hidden  = tab.dataset.tab !== 'photo';
    addManualPanel.hidden = tab.dataset.tab !== 'manual';
    addStatus.textContent = '';
    addStatus.className = '';
  });
});

// Manual entry submit
manualForm.addEventListener('submit', async e => {
  e.preventDefault();
  const title = document.getElementById('manual-title').value.trim();
  if (!title) return;

  const ingredients = document.getElementById('manual-ingredients').value
    .split('\n').map(s => s.trim()).filter(Boolean);
  const instructions = document.getElementById('manual-instructions').value
    .split('\n').map(s => s.trim()).filter(Boolean);

  const btn = manualForm.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = 'Adding…';
  addStatus.textContent = '';
  addStatus.className = '';

  try {
    const recipe = await fetchJson('api/recipes/manual', {
      method: 'POST',
      body: JSON.stringify({
        title,
        category: document.getElementById('manual-category').value.trim(),
        cook_time: document.getElementById('manual-cook-time').value.trim(),
        yields: document.getElementById('manual-yields').value.trim(),
        image_url: document.getElementById('manual-image-url').value.trim(),
        ingredients,
        instructions,
      }),
    });
    addStatus.innerHTML = `✓ Added: <strong>${esc(recipe.title)}</strong>`;
    addStatus.className = 'success';
    if (recipe.category && !Array.from(categoryFilter.options).some(o => o.value === recipe.category)) {
      const opt = document.createElement('option');
      opt.value = recipe.category; opt.textContent = recipe.category;
      categoryFilter.appendChild(opt);
    }
    allRecipes.unshift(recipe);
    applyFilters();
    setTimeout(() => { closeAdd(); openDetail(recipe.id); }, 1200);
  } catch (err) {
    addStatus.textContent = '✗ ' + err.message;
    addStatus.className = 'error';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Add Recipe';
  }
});

// ── Photo OCR ─────────────────────────────────────────────

function setPhotoPreview(file) {
  const url = URL.createObjectURL(file);
  // Replace dropzone inner with preview image
  photoDropInner.style.display = 'none';
  let img = photoDropzone.querySelector('.photo-preview');
  if (!img) {
    img = document.createElement('img');
    img.className = 'photo-preview';
    img.alt = '';
    photoDropzone.appendChild(img);
  }
  img.src = url;
  photoDropzone.classList.add('has-image');
  photoSubmitBtn.disabled = false;
}

photoDropzone.addEventListener('click', () => photoFileInput.click());
photoDropzone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') photoFileInput.click(); });

photoFileInput.addEventListener('change', () => {
  const file = photoFileInput.files[0];
  if (file) setPhotoPreview(file);
});

// Drag & drop
photoDropzone.addEventListener('dragover', e => { e.preventDefault(); photoDropzone.classList.add('drag-over'); });
photoDropzone.addEventListener('dragleave', () => photoDropzone.classList.remove('drag-over'));
photoDropzone.addEventListener('drop', e => {
  e.preventDefault();
  photoDropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) {
    setPhotoPreview(file);
  }
});

photoSubmitBtn.addEventListener('click', async () => {
  const file = photoFileInput.files[0] || (() => {
    // File may have come from drag & drop — grab from preview src isn't possible,
    // so we rely on the file input. If empty, no-op.
    return null;
  })();
  if (!file) return;

  photoSubmitBtn.disabled = true;
  addStatus.innerHTML = '<span class="spinner"></span> Extracting recipe…';
  addStatus.className = '';

  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('api/recipes/ocr', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: form,
    });
    const recipe = await res.json();
    if (!res.ok) throw new Error(recipe.detail || `HTTP ${res.status}`);

    addStatus.innerHTML = `✓ Extracted: <strong>${esc(recipe.title || 'Recipe')}</strong>`;
    addStatus.className = 'success';
    allRecipes.unshift(recipe);
    applyFilters();
    await loadCategories();
    setTimeout(() => { closeAdd(); openDetail(recipe.id); }, 1200);
  } catch (err) {
    addStatus.textContent = '✗ ' + err.message;
    addStatus.className = 'error';
    photoSubmitBtn.disabled = false;
  }
});

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
starredFilterBtn.addEventListener('click', () => {
  starFilterActive = !starFilterActive;
  starredFilterBtn.classList.toggle('active', starFilterActive);
  starredFilterBtn.setAttribute('aria-pressed', starFilterActive);
  starredFilterBtn.textContent = starFilterActive ? '★ Starred' : '☆ Starred';
  applyFilters();
});

// ── Init ──────────────────────────────────────────────────

if (authToken) {
  const savedUser = localStorage.getItem('recipes_user') || '';
  showApp(savedUser);
} else {
  showAuth();
}
