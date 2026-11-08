(function () {
  var REPO = 'JuliusBrain/OscarsPredictions', WPATH = 'docs/data/watched.json';
  var THEMES = ['deco', 'midnight', 'program'];
  var LANGS = ['en', 'pl'];
  var TABS = ['films', 'cal', 'cats', 'people'];
  var PEOPLE_CATS = ['Directing', 'Actor', 'Actress', 'Supporting Actor', 'Supporting Actress'];
  var state = { lang: 'en', theme: 'midnight', mode: 'predicted', tab: 'films', cat: 'All', filter: 'all', cal: null };
  var filmweb = {}, availability = { films: {}, tmdb_enabled: false };
  var data = null, registry = null, official = null, changes = { entries: {}, dropped: [] };
  var watched = {}, ops = [], remoteSha = null, saveTimer = null, saving = false;
  var syncState = null, metaError = null;

  /* ---------- helpers ---------- */
  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {}
    return null;
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  function slug(name) { return name.normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function isoOf(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function today() { return isoOf(new Date()); }
  function daysBetween(a, b) { return Math.round((Date.parse(a) - Date.parse(b)) / 864e5); }
  function status(cat, film) { return changes.entries[cat + '|' + film] || 'same'; }

  /* ---------- language ---------- */
  function t(key, v) {
    var s = (window.I18N[state.lang] || {})[key];
    if (s === undefined) s = window.I18N.en[key];
    if (s === undefined) s = key;
    return v ? s.replace(/\{(\w+)\}/g, function (m, k) { return v[k] !== undefined ? v[k] : m; }) : s;
  }
  function pluralForm(n) {
    if (state.lang === 'pl') {
      if (n === 1) return 'one';
      var a = n % 10, b = n % 100;
      return (a >= 2 && a <= 4 && !(b >= 12 && b <= 14)) ? 'few' : 'many';
    }
    return n === 1 ? 'one' : 'many';
  }
  function tn(base, n, v) { v = v || {}; v.n = n; return t(base + '.' + pluralForm(n), v); }
  function locale() { return state.lang === 'pl' ? 'pl-PL' : 'en-GB'; }
  function cl(cat) { var k = 'cat.' + cat, s = t(k); return s === k ? cat : s; }
  function ftitle(name) {
    var w = filmweb[slug(name)];
    return state.lang === 'pl' && w && w.title_pl ? w.title_pl : name;
  }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.title = t('title');
    document.querySelectorAll('[data-i18n]').forEach(function (n) { n.textContent = t(n.getAttribute('data-i18n')); });
    document.querySelectorAll('[data-i18n-html]').forEach(function (n) { n.innerHTML = t(n.getAttribute('data-i18n-html')); });
    document.querySelectorAll('[data-i18n-aria]').forEach(function (n) { n.setAttribute('aria-label', t(n.getAttribute('data-i18n-aria'))); });
    showSync();
  }

  function marker(st) {
    if (st === 'new') return el('b', 'chg new', t('badge.new'));
    if (st === 'winner_gained') return el('b', 'chg up', t('badge.winner'));
    if (st === 'winner_lost') return el('b', 'chg down', t('badge.notwinner'));
    return null;
  }
  function showError(key, vars) {
    metaError = { key: key, vars: vars };
    renderMeta();
    if (window.console) console.error(key, vars);
  }
  function renderMeta() {
    var m = document.getElementById('meta');
    if (!m) return;
    if (metaError) { m.textContent = t(metaError.key, metaError.vars); return; }
    if (!data) { m.textContent = ''; return; }
    m.textContent = t('meta.captured', { date: data.date }) + (changes.from ? t('meta.changes', { date: changes.from }) : t('meta.nochanges'));
  }

  /* ---------- watched data + GitHub sync ---------- */
  function token() { return store('ghtoken'); }
  function applyOps(map, list) {
    var out = JSON.parse(JSON.stringify(map));
    list.forEach(function (o) { if (o.on) out[o.id] = { at: o.at }; else delete out[o.id]; });
    return out;
  }
  function persistLocal() { store('watched_ops', JSON.stringify(ops)); store('watched_cache', JSON.stringify(watched)); }
  function showSync() { var s = document.getElementById('syncstate'); if (s) s.textContent = syncState ? t(syncState.key, syncState.vars) : ''; }
  function setSync(key, vars) { syncState = key ? { key: key, vars: vars } : null; showSync(); }
  function setWatched(id, on) {
    ops.push({ id: id, on: on, at: today() });
    watched = applyOps(watched, [ops[ops.length - 1]]);
    persistLocal();
    if (!token()) { setSync('sync.local'); return; }
    setSync('sync.saving');
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
        saving = false; setSync(ops.length ? 'sync.saving' : 'sync.saved'); render();
        if (ops.length) return flush();
      });
    }).catch(function (e) {
      saving = false;
      var st = e && e.status;
      if (st === 401 || st === 403) setSync('sync.rejectedFull');
      else setSync('sync.failed', { code: st || 'network' });
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
        if (!token()) { if (ops.length) setSync('sync.local'); return; }
        return loadRemote().then(function (remote) {
          watched = applyOps(remote, ops); persistLocal();
          setSync(ops.length ? 'sync.saving' : 'sync.synced');
          if (ops.length) flush();
        }).catch(function (e) {
          setSync(e && (e.status === 401 || e.status === 403) ? 'sync.rejected' : 'sync.unreachable');
        });
      });
  }

  /* ---------- theme ---------- */
  function applyState() {
    document.documentElement.setAttribute('data-theme', state.theme);
    ['lang', 'theme', 'mode', 'tab', 'filter'].forEach(function (f) {
      document.querySelectorAll('[data-' + f + '-btn]').forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-' + f + '-btn') === state[f]);
      });
    });
  }

  /* ---------- Poland: dates and where to watch ---------- */
  function fmt(iso) { return new Date(iso + 'T00:00:00').toLocaleDateString(locale(), { day: 'numeric', month: 'short', year: 'numeric' }); }
  function mon(iso) { return new Date(iso + 'T00:00:00').toLocaleDateString(locale(), { month: 'short', year: 'numeric' }); }
  function monRange(a, b) {
    var x = new Date(a + 'T00:00:00'), y = new Date(b + 'T00:00:00');
    if (mon(a) === mon(b)) return mon(a);
    if (x.getFullYear() === y.getFullYear()) return x.toLocaleDateString(locale(), { month: 'short' }) + '–' + mon(b);
    return mon(a) + '–' + mon(b);
  }
  function relDays(iso) {
    var d = daysBetween(iso, today());
    if (d === 0) return t('rel.today');
    var n = Math.abs(d), span = n >= 90 ? tn('unit.month', Math.round(n / 30)) : tn('unit.day', n);
    return t(d > 0 ? 'rel.in' : 'rel.ago', { t: span });
  }
  function cell(label, cls) {
    var c = el('div', 'pcell' + (cls ? ' ' + cls : ''));
    c.appendChild(el('span', 'plabel', label));
    return c;
  }
  function dateCell(label, iso, year, missingKey) {
    var c = cell(label);
    if (iso) { c.appendChild(el('span', 'pval', fmt(iso))); c.appendChild(el('span', 'psub', relDays(iso))); }
    else if (year) { c.appendChild(el('span', 'pval', String(year))); c.appendChild(el('span', 'psub', t('av.exactNot'))); }
    else { c.appendChild(el('span', 'pval pnone', '—')); c.appendChild(el('span', 'psub', t(missingKey))); }
    return c;
  }

  /* One place decides what to tell the user about where a film can be watched. */
  function watchStatus(f) {
    var fw = filmweb[f.id], av = (availability.films || {})[f.id] || {}, now = today();
    var p = av.providers || {}, stream = p.flatrate || [];
    var rentbuy = (p.rent || []).concat((p.buy || []).filter(function (x) { return (p.rent || []).indexOf(x) < 0; }));
    var free = (p.free || []).concat(p.ads || []);
    var any = stream.length || rentbuy.length || free.length;
    var out = fw && fw.pl_cinema && fw.pl_cinema > now;
    var inCinemas = fw && fw.pl_cinema && !out && daysBetween(now, fw.pl_cinema) <= 90;
    var pill, note = '';
    if (any) pill = [stream.length ? 'av.pill.streaming' : rentbuy.length ? 'av.pill.rentbuy' : 'av.pill.free', 'ok'];
    else if (out) { pill = ['av.pill.notout', 'wait']; note = t('av.note.opens', { date: fmt(fw.pl_cinema) }); }
    else if (fw && !fw.pl_cinema) { pill = ['av.pill.nopl', 'no']; note = t('av.note.notann'); }
    else if (!availability.tmdb_enabled || !av.checked) { pill = ['av.pill.notchecked', 'no']; note = t('av.note.nodata'); }
    else if (inCinemas) { pill = ['av.pill.cinemas', 'wait']; note = t('av.note.cinemasonly'); }
    else { pill = ['av.pill.none', 'no']; note = t('av.note.none'); }
    return { pill: pill, note: note, any: any, groups: [['av.g.stream', stream], ['av.g.rentbuy', rentbuy], ['av.g.free', free]], av: av };
  }

  function basisText(e) {
    if (e.basis_kind === 'digital' && e.hint) return t('av.basis.digital', { date: fmt(e.hint.date), country: e.hint.country });
    if (e.basis_kind === 'typical') return t('av.basis.typical');
    return e.basis;
  }

  function availBlock(f) {
    var panel = el('div', 'poland'), fw = filmweb[f.id], now = today(), ws = watchStatus(f);
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', t('av.group'));

    var c1 = dateCell(t('av.world'), fw && fw.world_premiere, fw && fw.world_premiere_year, 'av.notfound');
    var c2 = dateCell(t('av.pl'), fw && fw.pl_cinema, null, 'av.nodate');
    if (fw && fw.url) {
      var a = el('a', '', 'Filmweb ↗'); a.href = fw.url; a.target = '_blank'; a.rel = 'noopener';
      var sub = c2.querySelector('.psub'); sub.appendChild(document.createTextNode(' · ')); sub.appendChild(a);
    }
    panel.appendChild(c1); panel.appendChild(c2);

    var w = cell(t('av.watch'), 'pwatch');
    w.appendChild(el('span', 'pstatus ' + ws.pill[1], t(ws.pill[0])));
    if (ws.any) {
      ws.groups.forEach(function (g) {
        if (!g[1].length) return;
        var row = el('span', 'pgroup'); row.appendChild(el('b', '', t(g[0]))); row.appendChild(document.createTextNode(g[1].join(' · ')));
        w.appendChild(row);
      });
    } else if (ws.note) w.appendChild(el('span', 'psub', ws.note));
    panel.appendChild(w);

    var e = ws.av.estimate;
    if (!ws.any && e) {
      var est = cell(t('av.est'), 'pest');
      est.title = basisText(e);
      var late = e.rent_buy[1] < now && e.streaming[1] < now;
      var kv = function (k, v) { var r = el('span', 'pkv'); r.appendChild(el('span', '', k)); r.appendChild(el('b', '', v)); est.appendChild(r); };
      if (late) kv(t('av.est.status'), t('av.est.late'));
      else {
        kv(t('av.est.rb'), e.rent_buy[1] < now ? t('av.est.out') : monRange(e.rent_buy[0], e.rent_buy[1]));
        kv(t('av.est.stream'), e.streaming[1] < now ? t('av.est.passed') : monRange(e.streaming[0], e.streaming[1]));
      }
      panel.appendChild(est);
    }
    return panel;
  }

  /* ---------- films ---------- */
  function nomCount(f) {
    return Object.keys(f.categories).reduce(function (s, c) { return s + (f.categories[c].active ? (f.categories[c].entries || 1) : 0); }, 0);
  }
  function winCount(f) {
    return Object.keys(f.categories).filter(function (c) { return f.categories[c].active && f.categories[c].winner; }).length;
  }
  function filmChips(f) {
    var chips = el('div', 'noms');
    Object.keys(f.categories).map(function (cat) { return { cat: cat, c: f.categories[cat] }; })
      .sort(function (a, b) { return (b.c.active - a.c.active) || ((b.c.winner ? 1 : 0) - (a.c.winner ? 1 : 0)) || cl(a.cat).localeCompare(cl(b.cat), locale()); })
      .forEach(function (n) {
        var cls = 'nom' + (n.c.active ? (n.c.winner ? ' win' : '') : ' gone');
        var chip = el('span', cls, cl(n.cat));
        var v = { cat: cl(n.cat), date: n.c.last_seen };
        chip.setAttribute('aria-label', t(n.c.official ? 'chip.official' : n.c.active ? (n.c.winner ? 'chip.winner' : 'chip.nominee') : 'chip.gone', v));
        if (!n.c.active) chip.title = t('chip.goneTitle', v);
        if (n.c.official) { chip.appendChild(document.createTextNode(' ')); chip.appendChild(el('b', 'ok', t('badge.nominated'))); }
        var m = n.c.active ? marker(status(n.cat, f.name)) : null;
        if (m) { chip.appendChild(document.createTextNode(' ')); chip.appendChild(m); }
        chips.appendChild(chip);
      });
    return chips;
  }

  function focusFilm(id) {
    var box = Array.prototype.filter.call(document.querySelectorAll('input[data-film]'), function (i) { return i.getAttribute('data-film') === id && i.offsetParent !== null; })[0];
    if (box) box.focus();
  }
  function watchLabel(f) {
    var seen = !!watched[f.id], lab = el('label', 'watch'), cb = el('input');
    cb.type = 'checkbox'; cb.checked = seen; cb.setAttribute('data-film', f.id);
    cb.onchange = function () { setWatched(f.id, cb.checked); render(); focusFilm(f.id); };
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(seen && watched[f.id].at ? t('film.watchedOn', { date: watched[f.id].at }) : t('film.watched')));
    return lab;
  }

  function filmRow(f) {
    var seen = !!watched[f.id];
    var row = el('div', 'filmrow' + (seen ? ' seen' : '')), name = el('div', 'filmname');
    name.appendChild(el('b', '', ftitle(f.name)));
    if (state.lang === 'pl' && ftitle(f.name) !== f.name) name.appendChild(el('span', 'filmorig', t('film.original', { title: f.name })));
    var wins = winCount(f), noms = nomCount(f);
    var line = f.studio + ' · ' + (f.active ? tn('film.nom', noms) + (wins ? ' · ' + tn('film.win', wins) : '') : t('film.dropped', { date: f.last_seen }));
    name.appendChild(el('span', '', line));
    name.appendChild(watchLabel(f));
    row.appendChild(name); row.appendChild(filmChips(f)); row.appendChild(availBlock(f));
    return row;
  }

  function renderFilms() {
    var all = Object.keys(registry.films).map(function (k) { return registry.films[k]; });
    var active = all.filter(function (f) { return f.active; }), gone = all.filter(function (f) { return !f.active; });
    active.sort(function (a, b) { return nomCount(b) - nomCount(a) || ftitle(a.name).localeCompare(ftitle(b.name), locale()); });
    gone.sort(function (a, b) { return (b.nominated.length - a.nominated.length) || b.last_seen.localeCompare(a.last_seen) || a.name.localeCompare(b.name); });
    var seenCount = active.filter(function (f) { return watched[f.id]; }).length;
    document.getElementById('progress').textContent = t('progress', { seen: seenCount, total: active.length, left: active.length - seenCount });
    function keep(f) { return state.filter === 'all' || (state.filter === 'seen') === !!watched[f.id]; }
    var box = document.getElementById('filmlist');
    box.textContent = '';
    var shown = active.filter(keep);
    if (!shown.length) box.appendChild(el('div', 'none', t(state.filter === 'seen' ? 'films.noneSeen' : 'films.noneLeft')));
    shown.forEach(function (f) { box.appendChild(filmRow(f)); });
    var d = document.getElementById('dropped');
    d.textContent = '';
    var g = gone.filter(keep);
    if (g.length) {
      d.appendChild(el('h3', 'sechead', t('dropped.title')));
      d.appendChild(el('p', 'dropnote', t('dropped.note')));
      var list = el('div', 'filmlist');
      g.forEach(function (f) { list.appendChild(filmRow(f)); });
      d.appendChild(list);
    }
  }

  /* ---------- calendar of Polish premieres ---------- */
  function agRow(item) {
    var f = item.f, seen = !!watched[f.id], row = el('div', 'agrow' + (seen ? ' seen' : ''));
    var dt = el('div', 'agdate');
    if (item.date) {
      var d = new Date(item.date + 'T00:00:00');
      dt.appendChild(el('b', '', String(d.getDate())));
      dt.appendChild(el('span', '', d.toLocaleDateString(locale(), { month: 'short' })));
      dt.appendChild(el('small', '', d.toLocaleDateString(locale(), { weekday: 'short' })));
    } else dt.appendChild(el('b', 'pnone', '—'));
    var info = el('div', 'aginfo');
    info.appendChild(el('b', '', ftitle(f.name)));
    var wins = winCount(f);
    info.appendChild(el('span', '', f.studio + ' · ' + tn('film.nom', nomCount(f)) + (wins ? ' · ' + tn('film.win', wins) : '')));
    if (item.date) info.appendChild(el('span', 'agrel', relDays(item.date)));
    var side = el('div', 'agside');
    side.appendChild(watchLabel(f));
    var ws = watchStatus(f);
    side.appendChild(el('span', 'pstatus ' + ws.pill[1], t(ws.pill[0])));
    row.appendChild(dt); row.appendChild(info); row.appendChild(side);
    return row;
  }

  function monthLabel(y, m) { return cap(new Date(y, m, 1).toLocaleDateString(locale(), { month: 'long', year: 'numeric' })); }

  function renderCalendar() {
    var box = document.getElementById('calendar');
    box.textContent = '';
    var items = Object.keys(registry.films).map(function (k) { return registry.films[k]; })
      .filter(function (f) { return f.active; })
      .map(function (f) { var w = filmweb[f.id]; return { f: f, date: w && w.pl_cinema ? w.pl_cinema : null }; });
    var dated = items.filter(function (i) { return i.date; }), undated = items.filter(function (i) { return !i.date; });
    var now = today();
    function byDate(a, b) { return a.date.localeCompare(b.date) || ftitle(a.f.name).localeCompare(ftitle(b.f.name), locale()); }
    dated.sort(byDate);
    var upcoming = dated.filter(function (i) { return i.date >= now; }), past = dated.filter(function (i) { return i.date < now; }).reverse();
    if (!state.cal) { var d0 = new Date(); state.cal = { y: d0.getFullYear(), m: d0.getMonth() }; }
    var y = state.cal.y, m = state.cal.m;

    function go(name, y2, m2) {
      var dd = new Date(y2, m2, 1); state.cal = { y: dd.getFullYear(), m: dd.getMonth() };
      renderCalendar();
      var b = box.querySelector('[data-cal="' + name + '"]'); if (b) b.focus();
    }
    var nav = el('div', 'calnav');
    nav.appendChild(el('h2', 'caltitle', monthLabel(y, m)));
    nav.lastChild.setAttribute('aria-live', 'polite');
    var btns = el('div', 'calbtns');
    var prev = el('button', 'calbtn', '‹'); prev.setAttribute('aria-label', t('cal.prev')); prev.setAttribute('data-cal', 'prev');
    prev.onclick = function () { go('prev', y, m - 1); };
    var next = el('button', 'calbtn', '›'); next.setAttribute('aria-label', t('cal.next')); next.setAttribute('data-cal', 'next');
    next.onclick = function () { go('next', y, m + 1); };
    var tod = el('button', 'calbtn wide', t('cal.today')); tod.setAttribute('data-cal', 'today');
    tod.onclick = function () { var n = new Date(); go('today', n.getFullYear(), n.getMonth()); };
    btns.appendChild(prev); btns.appendChild(tod); btns.appendChild(next);
    if (upcoming.length) {
      var np = el('button', 'calbtn wide', t('cal.nextPremiere')); np.setAttribute('data-cal', 'np');
      np.onclick = function () { var dd = new Date(upcoming[0].date + 'T00:00:00'); go('np', dd.getFullYear(), dd.getMonth()); };
      btns.appendChild(np);
    }
    nav.appendChild(btns);
    box.appendChild(nav);

    var byDay = {};
    dated.forEach(function (i) { (byDay[i.date] = byDay[i.date] || []).push(i); });
    var grid = el('div', 'calgrid');
    grid.setAttribute('role', 'group'); grid.setAttribute('aria-label', monthLabel(y, m));
    for (var w = 0; w < 7; w++) grid.appendChild(el('div', 'calhead', new Date(2024, 0, 1 + w).toLocaleDateString(locale(), { weekday: 'short' })));
    var first = new Date(y, m, 1), lead = (first.getDay() + 6) % 7, dim = new Date(y, m + 1, 0).getDate();
    var total = Math.ceil((lead + dim) / 7) * 7;
    for (var i = 0; i < total; i++) {
      var day = i - lead + 1, dd2 = new Date(y, m, day), iso = isoOf(dd2), out = day < 1 || day > dim;
      var cellEl = el('div', 'calday' + (out ? ' out' : '') + (iso === now ? ' today' : '') + (iso < now ? ' past' : '') + (byDay[iso] ? ' has' : ''));
      cellEl.appendChild(el('span', 'calnum', String(dd2.getDate())));
      var list = byDay[iso] || [];
      list.slice(0, 3).forEach(function (it) {
        var wch = !!watched[it.f.id];
        var chip = el('span', 'calchip' + (wch ? ' seen' : ''), (wch ? '✓ ' : '') + ftitle(it.f.name));
        chip.title = ftitle(it.f.name) + ' · ' + it.f.studio;
        cellEl.appendChild(chip);
      });
      if (list.length > 3) cellEl.appendChild(el('span', 'calmore', t('cal.more', { n: list.length - 3 })));
      if (list.length) {
        var cnt = el('span', 'calcount', String(list.length));
        cnt.setAttribute('aria-label', tn('cal.count', list.length));
        cellEl.appendChild(cnt);
      }
      grid.appendChild(cellEl);
    }
    box.appendChild(grid);

    box.appendChild(el('h3', 'sechead', t('cal.upcoming')));
    if (!upcoming.length) box.appendChild(el('div', 'none', t('cal.upcomingNone')));
    var cur = '';
    upcoming.forEach(function (it) {
      var key = it.date.slice(0, 7);
      if (key !== cur) { cur = key; var p = it.date.split('-'); box.appendChild(el('h4', 'agmonth', monthLabel(+p[0], +p[1] - 1))); }
      box.appendChild(agRow(it));
    });
    function fold(titleKey, arr) {
      if (!arr.length) return;
      var det = el('details', 'calfold'), sum = el('summary', '', t(titleKey, { n: arr.length }));
      det.appendChild(sum);
      arr.forEach(function (it) { det.appendChild(agRow(it)); });
      box.appendChild(det);
    }
    fold('cal.past', past);
    fold('cal.undated', undated);
    box.appendChild(el('p', 'credits', t('cal.source')));
  }

  /* ---------- categories and people ---------- */
  function catCards(source, box) {
    box.textContent = '';
    Object.keys(source.categories).forEach(function (cat) {
      var card = el('div', 'catcard'), ul = el('ul');
      var ids = {}; source.categories[cat].forEach(function (e) { ids[slug(e.film)] = 1; });
      var all = Object.keys(ids), seen = all.filter(function (id) { return watched[id]; }).length;
      var head = el('div', 'cathead');
      head.appendChild(el('h3', '', cl(cat)));
      head.appendChild(el('span', 'catprog' + (seen === all.length ? ' done' : ''), tn('catprog', all.length, { seen: seen, total: all.length })));
      card.appendChild(head);
      var bar = el('div', 'catbar'), fill = el('i');
      fill.style.width = Math.round(seen / all.length * 100) + '%';
      bar.setAttribute('aria-hidden', 'true'); bar.appendChild(fill);
      card.appendChild(bar);
      source.categories[cat].forEach(function (e) {
        var li = el('li'), tt = el('span'), strong = el('b', '', e.song ? e.song : ftitle(e.film));
        tt.appendChild(strong);
        if (e.winner) tt.appendChild(el('span', 'tag', t('tag.winner')));
        var m = source === data ? marker(status(cat, e.film)) : null;
        if (m && !e.winner) { tt.appendChild(document.createTextNode(' ')); tt.appendChild(m); }
        li.appendChild(tt);
        var who = (e.song ? ftitle(e.film) + ' · ' : '') + (e.people.length && PEOPLE_CATS.indexOf(cat) >= 0 ? e.people.join(', ') + ' · ' : '') + e.studio + (e.country ? ' · ' + e.country : '');
        li.appendChild(el('span', 'who', who));
        if (watched[slug(e.film)]) li.appendChild(el('span', 'seen-tag', t('tag.watched')));
        ul.appendChild(li);
      });
      card.appendChild(ul); box.appendChild(card);
    });
  }

  function renderPeople() {
    var chips = document.getElementById('chips'), cards = document.getElementById('cards');
    chips.textContent = ''; cards.textContent = '';
    ['All'].concat(PEOPLE_CATS).forEach(function (name) {
      var b = el('button', 'chip', name === 'All' ? t('people.all') : cl(name));
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
          info.appendChild(el('div', 'film2', ftitle(e.film) + (watched[slug(e.film)] ? ' · ' + t('tag.watched') : '')));
          top.appendChild(info);
          if (e.winner) top.appendChild(el('span', 'tag', t('tag.winner')));
          card.appendChild(top);
          var foot = el('div', 'cat', cl(c)), m = marker(status(c, e.film));
          if (m) { foot.appendChild(document.createTextNode(' ')); foot.appendChild(m); }
          card.appendChild(foot); cards.appendChild(card);
        });
      });
    });
  }

  function render() {
    applyState();
    var predicted = state.mode === 'predicted';
    document.getElementById('nominees').hidden = predicted;
    TABS.forEach(function (tab) { document.getElementById(tab).hidden = !(predicted && state.tab === tab); });
    document.getElementById('nomempty').hidden = !!official;
    renderMeta();
    if (data && registry) {
      [renderFilms, renderCalendar, function renderCats() { catCards(data, document.getElementById('catlist')); }, renderPeople,
        function renderOfficial() { if (official) catCards(official, document.getElementById('nomlist')); }].forEach(function (fn) {
        try { fn(); } catch (e) { showError('err.generic', { msg: (fn.name || 'render') + ': ' + e.message }); }
      });
    }
  }

  /* ---------- wiring ---------- */
  [['lang', 'lang'], ['theme', 'theme'], ['mode', 'mode'], ['tab', 'tab'], ['filter', 'filter']].forEach(function (p) {
    document.querySelectorAll('[data-' + p[0] + '-btn]').forEach(function (b) {
      b.onclick = function () {
        state[p[1]] = b.getAttribute('data-' + p[0] + '-btn');
        if (p[1] === 'tab') state.mode = 'predicted';
        if (p[1] === 'theme') store('theme', state.theme);
        if (p[1] === 'lang') { store('lang', state.lang); applyI18n(); }
        render();
      };
    });
  });
  document.getElementById('tokensave').onclick = function () {
    var v = document.getElementById('token').value.trim();
    if (!v) { setSync('sync.pasteFirst'); return; }
    store('ghtoken', v); document.getElementById('token').value = '';
    setSync('sync.tokenSaved');
    loadWatched().then(render);
  };
  document.getElementById('tokenclear').onclick = function () {
    store('ghtoken', null); setSync('sync.tokenRemoved');
  };

  var savedLang = store('lang');
  state.lang = LANGS.indexOf(savedLang) >= 0 ? savedLang : ((navigator.language || 'en').toLowerCase().indexOf('pl') === 0 ? 'pl' : 'en');
  state.theme = THEMES.indexOf(store('theme')) >= 0 ? store('theme') : 'midnight';
  applyI18n();
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
    return loadWatched();
  }).then(render).catch(function (e) {
    showError('err.data', { msg: e.message });
  });
})();
