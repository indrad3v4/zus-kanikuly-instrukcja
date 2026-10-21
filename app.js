/* Каникулы składkowe – level engine. State: path + checks, persisted locally. */
(function () {
  'use strict';
  var LEVELS = window.LEVELS || [];
  var KEY = 'zus-wakacje-v1';
  var S = { path: null, checks: {}, i: 0 };
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var d = JSON.parse(raw);
        if (d && (d.path === 'a' || d.path === 'b' || d.path === null)) S = d;
        if (!S.checks) S.checks = {};
      }
    } catch (e) {}
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
  }

  function visible() {
    return LEVELS.filter(function (l) { return l.path === 'all' || l.path === S.path; });
  }
  function total() { return visible().length; }
  function current() { return visible()[S.i]; }

  function track(name, extra) {
    if (window.umami && window.umami.track) {
      try { window.umami.track(name, Object.assign({ path: S.path || 'intro', level: S.i + 1 }, extra || {})); } catch (e) {}
    }
  }

  function toast(msg) {
    var t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove('on'); }, 1600);
  }

  function paint() {
    var body = $('#intro'), stage = $('#stage'), fin = $('#final');
    var list = visible(), cur = current();
    var introOpen = !S.path;

    body.style.display = introOpen ? '' : 'none';
    fin.classList.toggle('on', !!S.finished);
    stage.style.display = (introOpen || S.finished) ? 'none' : '';

    // header
    var doneCount = list.filter(function (l) { return isDone(l); }).length;
    var pct = list.length ? Math.round(doneCount / list.length * 100) : 0;
    $('#barFill').style.width = pct + '%';
    $('#counter').textContent = introOpen ? 'Начало' :
      (S.finished ? 'Готово · ' + doneCount + ' из ' + list.length : 'Уровень ' + (S.i + 1) + ' / ' + list.length);
    var sb = $('#startBtn');
    if (sb) { sb.disabled = introOpen; sb.setAttribute('aria-disabled', String(introOpen)); }

    if (introOpen || S.finished || !cur) return;

    // one card visible
    $$('.lvl').forEach(function (n) { n.classList.remove('on'); });
    var node = document.getElementById('lvl-' + cur.id);
    if (node) node.classList.add('on');

    var arr = S.checks[cur.id] || (S.checks[cur.id] = []);
    for (var k = 0; k < cur.checks.length; k++) {
      var inp = node.querySelector('input[data-k="' + k + '"]');
      if (inp) inp.checked = !!arr[k];
    }
    updateNav(node, cur);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function isDone(l) {
    var a = S.checks[l.id] || [];
    return l.checks.every(function (_, k) { return !!a[k]; });
  }

  function updateNav(node, cur) {
    var arr = S.checks[cur.id] || [];
    var n = arr.filter(Boolean).length;
    var hint = node.querySelector('.hint');
    if (hint) hint.textContent = n >= cur.checks.length ? 'всё отмечено' : n + ' из ' + cur.checks.length;
    var next = node.querySelector('.btn.primary');
    if (next) next.textContent = (S.i >= total() - 1) ? 'Забрать UPO' : 'Дальше';
    var back = node.querySelector('.btn.ghost');
    if (back) back.style.visibility = S.i === 0 ? 'hidden' : '';
  }

  function choose(path) {
    S.path = path; S.i = 0; S.finished = false; S.checks = {};
    $$('.fork button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.path === path)); });
    save(); paint(); track('path', { chosen: path });
  }

  function go(delta) {
    var list = visible();
    if (delta > 0 && S.i >= list.length - 1) { finish(); return; }
    S.i = Math.max(0, Math.min(list.length - 1, S.i + delta));
    save(); paint(); track('level', { dir: delta });
  }

  function finish() {
    var list = visible();
    var doneCount = list.filter(isDone).length;
    S.finished = true; save(); paint();
    $('#finalStat').textContent = doneCount + ' из ' + list.length + ' уровней закрыто';
    track('finish', { done: doneCount });
  }

  // wire up
  function init() {
    load();
    // level markup injected statically by build.py
    $$('.fork button').forEach(function (b) {
      b.addEventListener('click', function () { choose(b.dataset.path); });
    });
    var startBtn = $('#startBtn');
    if (startBtn) startBtn.addEventListener('click', function () {
      if (!S.path) { toast('Сначала выберите свой случай'); return; }
      S.finished = false; S.i = 0; save(); paint(); track('start');
    });

    document.addEventListener('change', function (e) {
      var inp = e.target.closest && e.target.closest('input[data-k]');
      if (!inp) return;
      var card = inp.closest('.lvl');
      var id = card.getAttribute('data-id');
      var k = +inp.dataset.k;
      var arr = S.checks[id] || (S.checks[id] = []);
      arr[k] = inp.checked; save();
      updateNav(card, LEVELS.filter(function (l) { return l.id === id; })[0]);
      var list = visible();
      $('#barFill').style.width = Math.round(list.filter(isDone).length / list.length * 100) + '%';
      if (inp.checked && isDone(LEVELS.filter(function (l) { return l.id === id; })[0])) {
        toast('Уровень закрыт');
        track('level_done', { id: id });
      }
    });

    document.addEventListener('click', function (e) {
      var b = e.target.closest('[data-act]');
      if (b) {
        var act = b.dataset.act;
        if (act === 'next') go(1);
        else if (act === 'prev') go(-1);
        else if (act === 'finish') finish();
        else if (act === 'reset') {
          S = { path: null, checks: {}, i: 0 };
          save(); $$('.fork button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
          paint(); track('reset');
        } else if (act === 'shot') {
          var lb = $('#lb'); $('#lbImg').src = b.dataset.src; lb.classList.add('on'); lb.focus();
        }
        return;
      }
      if (e.target.id === 'lb' || e.target.closest('#lb')) {
        var im = $('#lbImg');
        if (e.target === im) { im.classList.toggle('zoom'); return; }
        $('#lb').classList.remove('on'); im.classList.remove('zoom');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') $('#lb').classList.remove('on');
      if (e.target.matches('input,textarea,button,a')) return;
      if (e.key === 'ArrowRight') go(1);
      if (e.key === 'ArrowLeft') go(-1);
    });

    paint();
    if (location.hash) {
      var id = location.hash.slice(1);
      var idx = visible().findIndex(function (l) { return l.id === id; });
      if (idx > -1) { S.i = idx; paint(); }
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
