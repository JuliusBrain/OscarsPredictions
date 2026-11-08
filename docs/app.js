(function () {
  var ACCENTS = { gold: ['#D4AF37', '#7A5C12'], champagne: ['#E8D8A8', '#8A6D3B'], rose: ['#E5677B', '#A3263E'] };
  var PEOPLE_CATS = ['Directing', 'Actor', 'Actress', 'Supporting Actor', 'Supporting Actress'];
  var state = { theme: 'mid', accent: 'gold', mode: 'predicted', tab: 'films', cat: 'All', filter: 'all' };
  var watched = {};
  try { JSON.parse(localStorage.getItem('watched') || '[]').forEach(function (f) { watched[f] = 1; }); } catch (e) {}
  function saveWatched() { store('watched', JSON.stringify(Object.keys(watched))); }
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
    root.style.setProperty('--accent', ACCENTS[state.accent][state.theme === 'light' ? 1 : 0]);
    ['theme', 'accent', 'mode', 'tab', 'filter'].forEach(function (f) {
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
    var seenCount = list.filter(function (f) { return watched[f.name]; }).length;
    document.getElementById('progress').textContent = seenCount + ' of ' + list.length + ' watched · ' + (list.length - seenCount) + ' left to watch';
    var shown = list.filter(function (f) {
      return state.filter === 'all' || (state.filter === 'seen') === !!watched[f.name];
    });
    var box = document.getElementById('filmlist');
    box.textContent = '';
    if (!shown.length) box.appendChild(el('div', 'none', state.filter === 'seen' ? 'No films marked as watched yet.' : 'Nothing left to watch. You have seen everything on the list.'));
    shown.forEach(function (f) {
      var wins = f.noms.filter(function (n) { return n.winner; }).length;
      var row = el('div', 'filmrow' + (watched[f.name] ? ' seen' : '')), name = el('div', 'filmname');
      name.appendChild(el('b', '', f.name));
      name.appendChild(el('span', '', f.studio + ' · ' + f.noms.length + (f.noms.length === 1 ? ' nomination' : ' nominations') + (wins ? ' · ' + wins + ' predicted ' + (wins === 1 ? 'win' : 'wins') : '')));
      var lab = el('label', 'watch'), cb = el('input');
      cb.type = 'checkbox'; cb.checked = !!watched[f.name]; cb.setAttribute('data-film', f.name);
      cb.onchange = function () {
        if (cb.checked) watched[f.name] = 1; else delete watched[f.name];
        saveWatched(); render();
        var again = document.querySelector('input[data-film]');
        document.querySelectorAll('input[data-film]').forEach(function (i) { if (i.getAttribute('data-film') === f.name) again = i; });
        if (again && again.getAttribute('data-film') === f.name) again.focus();
      };
      lab.appendChild(cb); lab.appendChild(document.createTextNode('Watched'));
      name.appendChild(lab);
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
        if (watched[e.film]) li.appendChild(el('span', 'seen-tag', 'Watched'));
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
          info.appendChild(el('div', 'film2', e.film + (watched[e.film] ? ' · Watched' : '')));
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

  [['theme', 'theme'], ['accent', 'accent'], ['mode', 'mode'], ['tab', 'tab'], ['filter', 'filter']].forEach(function (p) {
    document.querySelectorAll('[data-' + p[0] + '-btn]').forEach(function (b) {
      b.onclick = function () {
        state[p[1]] = b.getAttribute('data-' + p[0] + '-btn');
        if (p[1] === 'theme' || p[1] === 'accent') store(p[1], state[p[1]]);
        render();
      };
    });
  });
  state.theme = ['dark', 'mid', 'light'].indexOf(store('theme')) >= 0 ? store('theme') : 'mid';
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
