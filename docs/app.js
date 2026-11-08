(function () {
  var REPO = 'JuliusBrain/OscarsPredictions', WPATH = 'docs/data/watched.json';
  var THEMES = ['deco', 'midnight', 'program'];
  var PEOPLE_CATS = ['Directing', 'Actor', 'Actress', 'Supporting Actor', 'Supporting Actress'];
  var state = { theme: 'midnight', mode: 'predicted', tab: 'films', cat: 'All', filter: 'all' };
  var filmweb = {}, availability = { films: {}, tmdb_enabled: false };
  var data = null, registry = null, official = null, changes = { entries: {}, dropped: [] };
  var watched = {}, ops = [], remoteSha = null, saveTimer = null, saving = false, syncMsg = '';

  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {}
    return null;
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  function slug(name) { return name.normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }
  function today() { return new Date().toISOString().slice(0, 10); }
  function status(cat, film) { return changes.entries[cat + '|' + film] || 'same'; }
  function marker(st) {
    if (st === 'new') return el('b', 'chg new', 'NEW');
    if (st === 'winner_gained') return el('b', 'chg up', 'WINNER');
    if (st === 'winner_lost') return el('b', 'chg down', 'NOT WINNER');
    return null;
  }
  function showError(msg) {
    var m = document.getElementById('meta');
    if (m) m.textContent = 'Something went wrong (' + msg + '). Try a hard refresh.';
    if (window.console) console.error(msg);
  }

  /* ---------- watched data + GitHub sync ---------- */
  function token() { return store('ghtoken'); }
  function applyOps(map, list) {
    var out = JSON.parse(JSON.stringify(map));
    list.forEach(function (o) { if (o.on) out[o.id] = { at: o.at }; else delete out[o.id]; });
    return out;
  }
  function persistLocal() { store('watched_ops', JSON.stringify(ops)); store('watched_cache', JSON.stringify(watched)); }
  function setSync(msg) { syncMsg = msg; var s = document.getElementById('syncstate'); if (s) s.textContent = msg; }
  function setWatched(id, on) {
    ops.push({ id: id, on: on, at: today() });
    watched = applyOps(watched, [ops[ops.length - 1]]);
    persistLocal();
    if (!token()) { setSync('Saved in this browser only. Add a token under Sync settings to save to GitHub.'); return; }
    setSync('Saving to GitHub…');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(flush, 800);
  }
  function api(method, path, body) {
    return fetch('https://api.github.com' + path, {
      method: method, cache: 'no-store', body: body ? JSON.stringify(body) : undefined,
      headers: { 'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer ' + token(), 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' }
    });
  }
  function b64decode(s) { var bin = atob(s.replace(/\n/g, '')), a = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i); return new TextDecoder().decode(a); }
  function b64encode(s) { var a = new TextEncoder().encode(s), bin = ''; for (var i = 0; i < a.length; i++) bin += String.fromCharCode(a[i]); return btoa(bin); }
  function loadRemote() {
    return api('GET', '/repos/' + REPO + '/contents/' + WPATH + '?ref=main').then(function (r) {
      if (r.status === 404) { remoteSha = null; return {}; }
      if (!r.ok) throw { status: r.status };
      return r.json().then(function (j) { remoteSha = j.sha; return (JSON.parse(b64decode(j.content)).films) || {}; });
    });
  }
  function flush(retry) {
    if (saving || !ops.length || !token()) return Promise.resolve();
    saving = true;
    var sent = ops.length;
    return loadRemote().then(function (remote) {
      var merged = applyOps(remote, ops.slice(0, sent));
      var body = JSON.stringify({ updated: new Date().toISOString(), films: sortKeys(merged) }, null, 1) + '\n';
      var payload = { message: 'Update watched films', content: b64encode(body), branch: 'main' };
      if (remoteSha) payload.sha = remoteSha;
      return api('PUT', '/repos/' + REPO + '/contents/' + WPATH, payload).then(function (r) {
        if (r.status === 409 || r.status === 422) { saving = false; if (!retry) return flush(true); throw { status: r.status }; }
        if (!r.ok) throw { status: r.status };
        ops = ops.slice(sent); watched = applyOps(merged, ops); persistLocal();
        saving = false; setSync(ops.length ? 'Saving to GitHub…' : 'Saved to GitHub'); render();
        if (ops.length) return flush();
      });
    }).catch(function (e) {
      saving = false;
      var st = e && e.status;
      setSync(st === 401 || st === 403 ? 'GitHub rejected the token (needs Contents: Read and write on this repo). Changes are kept in this browser.'
        : 'Could not save to GitHub (' + (st || 'network') + '). Changes are kept in this browser and will retry on next change.');
    });
  }
  function sortKeys(o) { var r = {}; Object.keys(o).sort().forEach(function (k) { r[k] = o[k]; }); return r; }

  function loadWatched() {
    try { ops = JSON.parse(store('watched_ops') || '[]'); } catch (e) { ops = []; }
    try { JSON.parse(store('watched') || '[]').forEach(function (n) { ops.push({ id: slug(n), on: true, at: today() }); }); } catch (e) {}
    if (store('watched') !== null) { store('watched', null); persistLocal(); }
    return fetch('data/watched.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : { films: {} }; })
      .catch(function () { return { films: {} }; })
      .then(function (j) {
        watched = applyOps(j.films || {}, ops);
        if (!token()) { if (ops.length) setSync('Saved in this browser only. Add a token under Sync settings to save to GitHub.'); return; }
        return loadRemote().then(function (remote) {
          watched = applyOps(remote, ops); persistLocal();
          setSync(ops.length ? 'Saving to GitHub…' : 'Synced with GitHub');
          if (ops.length) flush();
        }).catch(function (e) {
          setSync(e && (e.status === 401 || e.status === 403) ? 'GitHub rejected the token. Check Sync settings.' : 'Could not reach GitHub. Showing the last saved list.');
        });
      });
  }

  /* ---------- theme ---------- */
  function applyTheme() {
    var root = document.documentElement;
    root.setAttribute('data-theme', state.theme);
    ['theme', 'mode', 'tab', 'filter'].forEach(function (f) {
      document.querySelectorAll('[data-' + f + '-btn]').forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-' + f + '-btn') === state[f]);
      });
    });
  }

  /* ---------- Poland: dates and where to watch ---------- */
  function fmt(iso) { return new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); }
  function mon(iso) { return new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }); }
  function monRange(a, b) {
    var x = new Date(a + 'T00:00:00'), y = new Date(b + 'T00:00:00');
    if (mon(a) === mon(b)) return mon(a);
    if (x.getFullYear() === y.getFullYear()) return x.toLocaleDateString('en-GB', { month: 'short' }) + '–' + mon(b);
    return mon(a) + '–' + mon(b);
  }
  function daysBetween(a, b) { return Math.round((Date.parse(a) - Date.parse(b)) / 864e5); }
  function line(cls, text) { return el('span', cls, text); }

  function relDays(iso) {
    var d = daysBetween(iso, today());
    if (d === 0) return 'today';
    var n = Math.abs(d), t = n >= 90 ? Math.round(n / 30) + ' months' : n + (n === 1 ? ' day' : ' days');
    return d > 0 ? 'in ' + t : t + ' ago';
  }
  function cell(label, cls) {
    var c = el('div', 'pcell' + (cls ? ' ' + cls : ''));
    c.appendChild(el('span', 'plabel', label));
    return c;
  }
  function dateCell(label, iso, year, missing) {
    var c = cell(label);
    if (iso) { c.appendChild(el('span', 'pval', fmt(iso))); c.appendChild(el('span', 'psub', relDays(iso))); }
    else if (year) { c.appendChild(el('span', 'pval', String(year))); c.appendChild(el('span', 'psub', 'exact date not set')); }
    else { c.appendChild(el('span', 'pval pnone', '—')); c.appendChild(el('span', 'psub', missing)); }
    return c;
  }

  function availBlock(f) {
    var panel = el('div', 'poland'), fw = filmweb[f.id], av = (availability.films || {})[f.id] || {}, now = today();
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', 'Release dates and availability in Poland');

    var c1 = dateCell('World premiere', fw && fw.world_premiere, fw && fw.world_premiere_year, 'not found on Filmweb');
    var c2 = dateCell('Polish cinemas', fw && fw.pl_cinema, null, 'no date announced');
    if (fw && fw.url) {
      var a = el('a', '', 'Filmweb ↗'); a.href = fw.url; a.target = '_blank'; a.rel = 'noopener';
      var sub = c2.querySelector('.psub'); sub.appendChild(document.createTextNode(' · ')); sub.appendChild(a);
    }
    panel.appendChild(c1); panel.appendChild(c2);

    var p = av.providers || {}, stream = p.flatrate || [], rentbuy = (p.rent || []).concat((p.buy || []).filter(function (x) { return (p.rent || []).indexOf(x) < 0; })), free = (p.free || []).concat(p.ads || []);
    var any = stream.length || rentbuy.length || free.length;
    var out = fw && fw.pl_cinema && fw.pl_cinema > now;
    var inCinemas = fw && fw.pl_cinema && !out && daysBetween(now, fw.pl_cinema) <= 90;

    var w = cell('Watch in Poland', 'pwatch'), pill, note = '';
    if (any) pill = [stream.length ? 'Streaming' : rentbuy.length ? 'Rent / buy' : 'Free', 'ok'];
    else if (out) { pill = ['Not out yet', 'wait']; note = 'Opens in Polish cinemas ' + fmt(fw.pl_cinema); }
    else if (fw && !fw.pl_cinema) { pill = ['No Polish release yet', 'no']; note = 'Not announced on Filmweb'; }
    else if (!availability.tmdb_enabled || !av.checked) { pill = ['Not checked', 'no']; note = 'Streaming data unavailable'; }
    else if (inCinemas) { pill = ['In cinemas only', 'wait']; note = 'Not on any streaming or VOD service yet'; }
    else { pill = ['Not available yet', 'no']; note = 'Not on any Polish streaming or VOD service'; }
    w.appendChild(el('span', 'pstatus ' + pill[1], pill[0]));
    if (any) {
      [['Stream', stream], ['Rent / buy', rentbuy], ['Free', free]].forEach(function (g) {
        if (!g[1].length) return;
        var row = el('span', 'pgroup'); row.appendChild(el('b', '', g[0])); row.appendChild(document.createTextNode(g[1].join(' · ')));
        w.appendChild(row);
      });
    } else if (note) w.appendChild(el('span', 'psub', note));
    panel.appendChild(w);

    var e = av.estimate;
    if (!any && e) {
      var est = cell('Likely available · estimate', 'pest');
      est.title = e.basis;
      var late = e.rent_buy[1] < now && e.streaming[1] < now;
      function kv(k, v) { var r = el('span', 'pkv'); r.appendChild(el('span', '', k)); r.appendChild(el('b', '', v)); est.appendChild(r); }
      if (late) kv('Status', 'past the usual windows');
      else {
        kv('Rent / buy', e.rent_buy[1] < now ? 'should be out' : monRange(e.rent_buy[0], e.rent_buy[1]));
        kv('Streaming', e.streaming[1] < now ? 'window passed' : monRange(e.streaming[0], e.streaming[1]));
      }
      panel.appendChild(est);
    }
    return panel;
  }

  /* ---------- views ---------- */
  function filmChips(f) {
    var chips = el('div', 'noms');
    Object.keys(f.categories).map(function (cat) { return { cat: cat, c: f.categories[cat] }; })
      .sort(function (a, b) { return (b.c.active - a.c.active) || ((b.c.winner ? 1 : 0) - (a.c.winner ? 1 : 0)) || a.cat.localeCompare(b.cat); })
      .forEach(function (n) {
        var cls = 'nom' + (n.c.active ? (n.c.winner ? ' win' : '') : ' gone');
        var chip = el('span', cls, n.cat);
        var label = n.cat + (n.c.official ? ', officially nominated' : n.c.active ? (n.c.winner ? ', predicted winner' : ', predicted nominee') : ', no longer on Variety list since ' + n.c.last_seen);
        chip.setAttribute('aria-label', label);
        if (!n.c.active) chip.title = 'Dropped from Variety’s list (last seen ' + n.c.last_seen + ')';
        if (n.c.official) { chip.appendChild(document.createTextNode(' ')); chip.appendChild(el('b', 'ok', 'NOMINATED')); }
        var m = n.c.active ? marker(status(n.cat, f.name)) : null;
        if (m) { chip.appendChild(document.createTextNode(' ')); chip.appendChild(m); }
        chips.appendChild(chip);
      });
    return chips;
  }

  function filmRow(f) {
    var seen = !!watched[f.id];
    var row = el('div', 'filmrow' + (seen ? ' seen' : '')), name = el('div', 'filmname');
    name.appendChild(el('b', '', f.name));
    var cats = Object.keys(f.categories), act = cats.filter(function (c) { return f.categories[c].active; });
    var wins = act.filter(function (c) { return f.categories[c].winner; }).length;
    var noms = act.reduce(function (s, c) { return s + (f.categories[c].entries || 1); }, 0);
    var line = f.studio + ' · ' + (f.active ? noms + (noms === 1 ? ' nomination' : ' nominations') + (wins ? ' · ' + wins + ' predicted ' + (wins === 1 ? 'win' : 'wins') : '') : 'Dropped from Variety’s list (last seen ' + f.last_seen + ')');
    name.appendChild(el('span', '', line));
    var lab = el('label', 'watch'), cb = el('input');
    cb.type = 'checkbox'; cb.checked = seen; cb.setAttribute('data-film', f.id);
    cb.onchange = function () {
      setWatched(f.id, cb.checked); render();
      document.querySelectorAll('input[data-film]').forEach(function (i) { if (i.getAttribute('data-film') === f.id) i.focus(); });
    };
    lab.appendChild(cb); lab.appendChild(document.createTextNode(seen && watched[f.id].at ? 'Watched · ' + watched[f.id].at : 'Watched'));
    name.appendChild(lab);
    row.appendChild(name); row.appendChild(filmChips(f)); row.appendChild(availBlock(f));
    return row;
  }

  function renderFilms() {
    var all = Object.keys(registry.films).map(function (k) { return registry.films[k]; });
    var active = all.filter(function (f) { return f.active; }), gone = all.filter(function (f) { return !f.active; });
    function n(f) { return Object.keys(f.categories).reduce(function (s, c) { return s + (f.categories[c].active ? (f.categories[c].entries || 1) : 0); }, 0); }
    active.sort(function (a, b) { return n(b) - n(a) || a.name.localeCompare(b.name); });
    gone.sort(function (a, b) { return (b.nominated.length - a.nominated.length) || b.last_seen.localeCompare(a.last_seen) || a.name.localeCompare(b.name); });
    var seenCount = active.filter(function (f) { return watched[f.id]; }).length;
    document.getElementById('progress').textContent = seenCount + ' of ' + active.length + ' watched · ' + (active.length - seenCount) + ' left to watch';
    function keep(f) { return state.filter === 'all' || (state.filter === 'seen') === !!watched[f.id]; }
    var box = document.getElementById('filmlist');
    box.textContent = '';
    var shown = active.filter(keep);
    if (!shown.length) box.appendChild(el('div', 'none', state.filter === 'seen' ? 'No films marked as watched yet.' : 'Nothing left to watch. You have seen everything on the list.'));
    shown.forEach(function (f) { box.appendChild(filmRow(f)); });
    var d = document.getElementById('dropped');
    d.textContent = '';
    var g = gone.filter(keep);
    if (g.length) {
      d.appendChild(el('h3', 'sechead', 'No longer on Variety’s list'));
      d.appendChild(el('p', 'dropnote', 'Kept for the record. If a film is officially nominated later, it is tagged NOMINATED.'));
      var list = el('div', 'filmlist');
      g.forEach(function (f) { list.appendChild(filmRow(f)); });
      d.appendChild(list);
    }
  }

  function catCards(source, box) {
    box.textContent = '';
    Object.keys(source.categories).forEach(function (cat) {
      var card = el('div', 'catcard'), ul = el('ul');
      card.appendChild(el('h3', '', cat));
      source.categories[cat].forEach(function (e) {
        var li = el('li'), t = el('span'), strong = el('b', '', e.song ? e.song : e.film);
        t.appendChild(strong);
        if (e.winner) t.appendChild(el('span', 'tag', 'Winner'));
        var m = source === data ? marker(status(cat, e.film)) : null;
        if (m && !e.winner) { t.appendChild(document.createTextNode(' ')); t.appendChild(m); }
        li.appendChild(t);
        var who = (e.song ? e.film + ' · ' : '') + (e.people.length && PEOPLE_CATS.indexOf(cat) >= 0 ? e.people.join(', ') + ' · ' : '') + e.studio + (e.country ? ' · ' + e.country : '');
        li.appendChild(el('span', 'who', who));
        if (watched[slug(e.film)]) li.appendChild(el('span', 'seen-tag', 'Watched'));
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
          info.appendChild(el('div', 'film2', e.film + (watched[slug(e.film)] ? ' · Watched' : '')));
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
    document.getElementById('nomempty').hidden = !!official;
    if (data && registry) {
      [renderFilms, function renderCats() { catCards(data, document.getElementById('catlist')); }, renderPeople,
        function renderOfficial() { if (official) catCards(official, document.getElementById('nomlist')); }].forEach(function (fn) {
        try { fn(); } catch (e) { showError(fn.name + ': ' + e.message); }
      });
    }
  }

  [['theme', 'theme'], ['mode', 'mode'], ['tab', 'tab'], ['filter', 'filter']].forEach(function (p) {
    document.querySelectorAll('[data-' + p[0] + '-btn]').forEach(function (b) {
      b.onclick = function () {
        state[p[1]] = b.getAttribute('data-' + p[0] + '-btn');
        if (p[1] === 'tab') state.mode = 'predicted';
        if (p[1] === 'theme') store('theme', state.theme);
        render();
      };
    });
  });
  document.getElementById('tokensave').onclick = function () {
    var v = document.getElementById('token').value.trim();
    if (!v) { setSync('Paste a token first.'); return; }
    store('ghtoken', v); document.getElementById('token').value = '';
    setSync('Token saved in this browser. Checking GitHub…');
    loadWatched().then(render);
  };
  document.getElementById('tokenclear').onclick = function () {
    store('ghtoken', null); setSync('Token removed. Marks are kept in this browser only.');
  };
  state.theme = THEMES.indexOf(store('theme')) >= 0 ? store('theme') : 'midnight';
  render();

  function getJson(url, optional) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) { if (optional) return null; throw new Error(url + ' HTTP ' + r.status); }
      return r.json();
    });
  }
  Promise.all([getJson('data/latest.json'), getJson('data/changes.json'), getJson('data/films.json'), getJson('data/official.json', true), getJson('data/filmweb.json', true), getJson('data/availability.json', true)]).then(function (j) {
    data = j[0]; changes = j[1]; registry = j[2]; official = j[3];
    filmweb = j[4] || {}; availability = j[5] || { films: {}, tmdb_enabled: false };
    var m = 'Captured ' + data.date + ' · Source: Variety';
    m += changes.from ? ' · Changes vs ' + changes.from : ' · Changes will appear after the next snapshot';
    document.getElementById('meta').textContent = m;
    return loadWatched();
  }).then(render).catch(function (e) {
    showError('data: ' + e.message + '. Open the site via its https URL, not as a local file');
  });
})();
