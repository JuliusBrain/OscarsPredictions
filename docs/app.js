(function () {
  var ACCENTS = { gold: ['#D4AF37', '#7A5C12'], champagne: ['#E8D8A8', '#8A6D3B'], rose: ['#E5677B', '#A3263E'] };
  var PEOPLE_CATS = ['Directing', 'Actor', 'Actress', 'Supporting Actor', 'Supporting Actress'];
  var state = { theme: 'dark', accent: 'gold', mode: 'predicted', tab: 'films', cat: 'All' };
  var data = null, changes = { entries: {}, dropped: [] };

  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function status(cat, film) { return changes.entries[cat + '|' + film] || 'same'; }
  function marker(st) {
    if (st === 'new') return el('b', 'chg new', 'NEW');
    if (st === 'winner_gained') return el('b', 'chg up', 'WINNER');
    if (st === 'winner_lost') return el('b', 'chg down', 'NOT WINNER');
    return null;
  }

  function applyTheme() {
    var root = document.documentElement;
    root.setAttribute('data-theme', state.theme);
    root.style.setProperty('--accent', ACCENTS[state.accent][state.theme === 'dark' ? 0 : 1]);
    ['theme', 'accent', 'mode', 'tab'].forEach(function (f) {
      document.querySelectorAll('[data-' + f + '-btn]').forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-' + f + '-btn') === state[f]);
      });
    });
  }

  function renderFilms() {
    var films = {};
    Object.keys(data.categories).forEach(function (cat) {
      data.categories[cat].forEach(function (e) {
        var f = films[e.film] || (films[e.film] = { name: e.film, studio: e.studio, noms: [] });
        f.noms.push({ cat: cat, winner: e.winner });
      });
    });
    var list = Object.keys(films).map(function (k) { return films[k]; }).sort(function (a, b) {
      return b.noms.length - a.noms.length || a.name.localeCompare(b.name);
    });
    var box = document.getElementById('filmlist');
    box.textContent = '';
    list.forEach(function (f) {
      var wins = f.noms.filter(function (n) { return n.winner; }).length;
      var row = el('div', 'filmrow'), name = el('div', 'filmname');
      name.appendChild(el('b', '', f.name));
      name.appendChild(el('span', '', f.studio + ' · ' + f.noms.length + (f.noms.length === 1 ? ' nomination' : ' nominations') + (wins ? ' · ' + wins + ' predicted ' + (wins === 1 ? 'win' : 'wins') : '')));
      var chips = el('div', 'noms');
      f.noms.sort(function (a, b) { return (b.winner - a.winner); }).forEach(function (n) {
        var c = el('span', 'nom' + (n.winner ? ' win' : ''), n.cat);
        c.setAttribute('aria-label', n.cat + (n.winner ? ', predicted winner' : ', predicted nominee'));
        var m = marker(status(n.cat, f.name));
        if (m) { c.appendChild(document.createTextNode(' ')); c.appendChild(m); }
        chips.appendChild(c);
      });
      row.appendChild(name); row.appendChild(chips); box.appendChild(row);
    });
    var d = document.getElementById('dropped');
    d.textContent = '';
    if (changes.dropped.length) {
      var b = el('div', 'dropped');
      b.appendChild(el('h3', '', 'Dropped since ' + changes.from));
      b.appendChild(el('span', '', changes.dropped.map(function (x) { return x.film + ' (' + x.category + ')'; }).join(', ')));
      d.appendChild(b);
    }
  }

  function renderCats() {
    var box = document.getElementById('catlist');
    box.textContent = '';
    Object.keys(data.categories).forEach(function (cat) {
      var card = el('div', 'catcard'), ul = el('ul');
      card.appendChild(el('h3', '', cat));
      data.categories[cat].forEach(function (e) {
        var li = el('li'), t = el('span', '', ''), strong = el('b', '', e.song ? e.song : e.film);
        t.appendChild(strong);
        if (e.winner) t.appendChild(el('span', 'tag', 'Winner'));
        var m = marker(status(cat, e.film));
        if (m && !e.winner) { t.appendChild(document.createTextNode(' ')); t.appendChild(m); }
        li.appendChild(t);
        var who = (e.song ? e.film + ' · ' : '') + (e.people.length && PEOPLE_CATS.indexOf(cat) >= 0 ? e.people.join(', ') + ' · ' : '') + e.studio + (e.country ? ' · ' + e.country : '');
        li.appendChild(el('span', 'who', who));
        ul.appendChild(li);
      });
      card.appendChild(ul); box.appendChild(card);
    });
  }

  function renderPeople() {
    var chips = document.getElementById('chips'), cards = document.getElementById('cards');
    chips.textContent = ''; cards.textContent = '';
    ['All'].concat(PEOPLE_CATS).forEach(function (name) {
      var b = el('button', 'chip', name);
      b.setAttribute('aria-pressed', state.cat === name);
      b.onclick = function () { state.cat = name; renderPeople(); };
      chips.appendChild(b);
    });
    PEOPLE_CATS.forEach(function (c) {
      if (state.cat !== 'All' && state.cat !== c) return;
      (data.categories[c] || []).forEach(function (e) {
        e.people.forEach(function (p) {
          var card = el('article', 'card'), top = el('div', 'top'), info = el('div');
          info.appendChild(el('div', 'name', p));
          info.appendChild(el('div', 'film2', e.film));
          top.appendChild(info);
          if (e.winner) top.appendChild(el('span', 'tag', 'Winner'));
          card.appendChild(top);
          var foot = el('div', 'cat', c), m = marker(status(c, e.film));
          if (m) { foot.appendChild(document.createTextNode(' ')); foot.appendChild(m); }
          card.appendChild(foot); cards.appendChild(card);
        });
      });
    });
  }

  function render() {
    applyTheme();
    var predicted = state.mode === 'predicted';
    document.getElementById('nominees').hidden = predicted;
    ['films', 'cats', 'people'].forEach(function (t) {
      document.getElementById(t).hidden = !(predicted && state.tab === t);
    });
    if (data) { renderFilms(); renderCats(); renderPeople(); }
  }

  [['theme', 'theme'], ['accent', 'accent'], ['mode', 'mode'], ['tab', 'tab']].forEach(function (p) {
    document.querySelectorAll('[data-' + p[0] + '-btn]').forEach(function (b) {
      b.onclick = function () {
        state[p[1]] = b.getAttribute('data-' + p[0] + '-btn');
        if (p[1] === 'theme' || p[1] === 'accent') store(p[1], state[p[1]]);
        render();
      };
    });
  });
  state.theme = store('theme') || (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  state.accent = ACCENTS[store('accent')] ? store('accent') : 'gold';
  render();

  Promise.all([fetch('data/latest.json'), fetch('data/changes.json')]).then(function (rs) {
    return Promise.all(rs.map(function (r) { return r.json(); }));
  }).then(function (j) {
    data = j[0]; changes = j[1];
    var m = 'Captured ' + data.date + ' · Source: Variety';
    m += changes.from ? ' · Changes vs ' + changes.from : ' · Changes will appear after the next snapshot';
    document.getElementById('meta').textContent = m;
    render();
  }).catch(function () {
    document.getElementById('meta').textContent = 'Could not load data.';
  });
})();
