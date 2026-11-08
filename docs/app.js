(function () {
  var ACCENTS = { gold: ['#D4AF37', '#7A5C12'], champagne: ['#E8D8A8', '#8A6D3B'], rose: ['#E5677B', '#A3263E'] };
  var ACTING = ['Actor', 'Actress', 'Supp. Actor', 'Supp. Actress'];
  var state = { theme: 'dark', accent: 'gold', mode: 'predicted', tab: 'films', cat: 'All' };
  var data = null, changes = { entries: {}, dropped: [] };

  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function badge(rank) { return el('i', 'badge ' + (rank === 1 ? 'r1' : rank === 2 ? 'r2' : 'r3'), String(rank)); }
  function chg(c) {
    if (!c || c.status === 'same') return null;
    if (c.status === 'new') return el('b', 'chg new', 'NEW');
    return el('b', 'chg ' + c.status, (c.status === 'up' ? '▲' : '▼') + c.delta);
  }
  function key(cat, film) { return cat + '|' + film; }

  function applyTheme() {
    var root = document.documentElement;
    root.setAttribute('data-theme', state.theme);
    root.style.setProperty('--accent', ACCENTS[state.accent][state.theme === 'dark' ? 0 : 1]);
    document.querySelectorAll('[data-theme-btn]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.themeBtn === state.theme); });
    document.querySelectorAll('[data-accent-btn]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.accentBtn === state.accent); });
    document.querySelectorAll('[data-mode-btn]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.modeBtn === state.mode); });
    document.querySelectorAll('[data-tab-btn]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.tabBtn === state.tab); });
  }

  function renderGrid() {
    var cats = Object.keys(data.categories), films = {};
    cats.forEach(function (c) {
      data.categories[c].forEach(function (e) { (films[e.film] = films[e.film] || {})[c] = e.rank; });
    });
    var names = Object.keys(films).sort(function (a, b) {
      return Math.min.apply(null, Object.values(films[a])) - Math.min.apply(null, Object.values(films[b]));
    });
    var grid = document.getElementById('grid');
    grid.textContent = '';
    grid.style.setProperty('--cols', cats.length);
    var hdr = el('div', 'row hdr');
    hdr.appendChild(el('div', 'hcell', 'Film'));
    cats.forEach(function (c) { hdr.appendChild(el('div', 'hcell', c)); });
    grid.appendChild(hdr);
    names.forEach(function (f) {
      var row = el('div', 'row');
      var cell0 = el('div', 'film'); cell0.appendChild(el('b', '', f)); row.appendChild(cell0);
      cats.forEach(function (c) {
        var cell = el('div', 'cell'), r = films[f][c];
        if (r) {
          cell.appendChild(badge(r));
          var b = chg(changes.entries[key(c, f)]);
          if (b) cell.appendChild(b);
        }
        row.appendChild(cell);
      });
      grid.appendChild(row);
    });
    var d = document.getElementById('dropped');
    d.textContent = '';
    if (changes.dropped.length) {
      var box = el('div', 'dropped');
      box.appendChild(el('h3', '', 'Dropped since ' + changes.from));
      box.appendChild(el('span', '', changes.dropped.map(function (x) { return x.film + ' (' + x.category + ')'; }).join(', ')));
      d.appendChild(box);
    }
  }

  function renderPeople() {
    var chips = document.getElementById('chips'), cards = document.getElementById('cards');
    chips.textContent = ''; cards.textContent = '';
    ['All'].concat(ACTING).forEach(function (name) {
      var b = el('button', 'chip', name);
      b.setAttribute('aria-pressed', state.cat === name);
      b.onclick = function () { state.cat = name; renderPeople(); };
      chips.appendChild(b);
    });
    ACTING.forEach(function (c) {
      if (state.cat !== 'All' && state.cat !== c) return;
      (data.categories[c] || []).forEach(function (e) {
        e.people.forEach(function (p) {
          var card = el('article', 'card'), top = el('div', 'top'), info = el('div');
          info.appendChild(el('div', 'name', p));
          info.appendChild(el('div', 'film2', e.film));
          top.appendChild(info); top.appendChild(badge(e.rank));
          card.appendChild(top);
          var foot = el('div', 'cat', c);
          var b = chg(changes.entries[key(c, e.film)]);
          if (b) { foot.appendChild(document.createTextNode(' ')); foot.appendChild(b); }
          card.appendChild(foot);
          cards.appendChild(card);
        });
      });
    });
  }

  function render() {
    applyTheme();
    var predicted = state.mode === 'predicted';
    document.getElementById('nominees').hidden = predicted;
    document.getElementById('films').hidden = !(predicted && state.tab === 'films');
    document.getElementById('people').hidden = !(predicted && state.tab === 'people');
    if (data) { renderGrid(); renderPeople(); }
  }

  function wire(attr, field) {
    document.querySelectorAll('[' + attr + ']').forEach(function (b) {
      b.onclick = function () { state[field] = b.getAttribute(attr); if (field === 'theme' || field === 'accent') store(field, state[field]); render(); };
    });
  }
  wire('data-theme-btn', 'theme'); wire('data-accent-btn', 'accent');
  wire('data-mode-btn', 'mode'); wire('data-tab-btn', 'tab');
  state.theme = store('theme') || (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  state.accent = ACCENTS[store('accent')] ? store('accent') : 'gold';
  render();

  Promise.all([fetch('data/latest.json'), fetch('data/changes.json')]).then(function (rs) {
    return Promise.all(rs.map(function (r) { return r.json(); }));
  }).then(function (j) {
    data = j[0]; changes = j[1];
    var m = 'Updated ' + data.date + ' · Source: ' + data.source;
    if (changes.from) m += ' · Changes vs ' + changes.from;
    document.getElementById('meta').textContent = m;
    render();
  }).catch(function () {
    document.getElementById('meta').textContent = 'Could not load data.';
  });
})();
