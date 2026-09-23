/*
 bulk_extract.js  (paste into the javascript_tool, action "javascript_exec")

 Run it while a Chrome tab sits on the DETAIL-page domain of a careers site, so every
 fetch() is same-origin. It defines window.__ij with helpers that:
   start(ids)        fetch every posting in the background and parse its fields
   status()          progress (poll this; never sleep inside a call for more than ~10 s)
   groups()          collapse postings whose qualification text is the same across cities
   stage1()          compact DATES / EDU sentences per posting, to filter fast
   scan(regex)       which postings mention a pattern (2028, sophomore, phoenix, ...)
   years()           every years/months-of-experience mention, marked [>1y] when over one year
   detail(ids, lbl)  full text of chosen fields for chosen postings
   show(text)        write text into the page body so get_page_text can return it in full

 Full posting URLs cannot be printed through javascript_tool (output containing query strings is
 blocked); build them from the address pattern of an opened posting.

 Edit CONFIG for the site first. The IBM values below are the ones that worked in Sept 2026
. For a site with no label/value blocks the whole page text is kept
 in f._full, so the same helpers still work with looser results.

 Why the extra machinery: javascript_tool output is cut at roughly 800 characters and is blocked
 when it looks like a URL with a query string or a cookie, and a call times out after 45 s.
 The fetches keep running after a call times out, so start them, then poll.
*/
(() => {
  const CONFIG = {
    // Same-origin path that returns one posting's HTML for an id.
    urlFor: id => `/en_US/careers/JobDetail?jobId=${id}&source=WEB_Search_NA`,
    // Label/value blocks that hold the description and metadata.
    fieldSel: '.article__content__view__field',
    labelSel: '.article__content__view__field__label',
    valueSel: '.article__content__view__field__value',
    // Turn document.title into a clean job title.
    cleanTitle: t => t.replace(/( - \d+)? - IBM$/, '').trim(),
    // Labels whose text decides "same posting, different city" for groups().
    signatureLabels: ['Required education', 'Preferred education',
      'Required technical and professional expertise',
      'Preferred technical and professional experience'],
    // Metadata labels (not description); skipped by stage1() and scan().
    metaLabels: /^(Job Title|Date posted|Job ID|City|State|Country|Work arrangement|Area of work|Employment type|Contract type|Projected|Position type|Travel|Company|Shift|Is this)/,
    // 4 workers was about 1.5 s per request each on IBM; more did not help.
    workers: 4,
  };

  // Sentences that state a term or dates, and sentences that state eligibility or a hard filter.
  const DATE_RE = /(program dates|internship dates|dates are|weeks|summer|fall|spring|winter|start date|duration|semester|quarter|may (to|-|through)|june|july|august)/i;
  const EDU_RE = /(graduat|pursuing|enrolled|freshman|sophomore|junior|senior|rising|class of|expected|undergraduate|bachelor|master|ph\.?d|mba|academic|first[- ]year|underclass|sponsorship|citizen|clearance|gpa)/i;

  const J = {};                       // id -> { title, f: {label: text}, status } or { err }
  const queue = [];
  let total = 0;

  const h2t = html => html
    .replace(/<\s*br\s*\/?>/gi, '\n').replace(/<\/(p|div|ul|ol|h\d|tr)>/gi, '\n')
    .replace(/<li[^>]*>/gi, '- ').replace(/<\/li>/gi, '\n').replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&#39;|&rsquo;|&lsquo;/g, "'").replace(/&quot;|&ldquo;|&rdquo;/g, '"')
    .replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
  const agg = s => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const firstMatch = (f, re) => { const k = Object.keys(f).find(k => re.test(k)); return k ? f[k].replace(/\s+/g, ' ') : ''; };
  const body = f => Object.entries(f).filter(([k]) => !CONFIG.metaLabels.test(k));
  const meta = id => { const f = (J[id] && J[id].f) || {}; return [firstMatch(f, /^(City|Location)/i), firstMatch(f, /^Work arrangement/i)].filter(Boolean).join(' | '); };

  async function getOne(id) {
    try {
      const r = await fetch(CONFIG.urlFor(id), { credentials: 'same-origin' });
      const html = await r.text();
      const d = new DOMParser().parseFromString(html, 'text/html');
      const f = {};
      d.querySelectorAll(CONFIG.fieldSel).forEach(el => {
        const l = el.querySelector(CONFIG.labelSel), v = el.querySelector(CONFIG.valueSel);
        const label = l ? l.textContent.trim() : '';
        if (label && v) f[label] = h2t(v.innerHTML);
      });
      if (!Object.keys(f).length) f._full = h2t((d.querySelector('main, article') || d.body).innerHTML);
      J[id] = { title: CONFIG.cleanTitle(d.title || ''), f, status: r.status };
    } catch (e) { J[id] = { err: String(e) }; }
  }

  function start(ids) {
    ids.filter(id => !J[id] || J[id].err).forEach(id => queue.push(id));
    total = ids.length;
    const n = queue.length;
    const worker = async () => { while (queue.length) await getOne(queue.shift()); };
    for (let i = 0; i < CONFIG.workers; i++) worker();          // background on purpose: do not await
    return `started ${n} of ${ids.length}`;
  }

  function status() {
    const v = Object.values(J);
    return JSON.stringify({ total, done: v.length,
      ok: v.filter(j => j.status === 200 && j.f).length,
      err: v.filter(j => j.err || (j.status && j.status !== 200)).length });
  }

  function groups(ids = Object.keys(J), labels = CONFIG.signatureLabels) {
    const g = {};
    ids.forEach(id => {
      const f = (J[id] && J[id].f) || {};
      const sig = labels.map(l => agg(f[l])).join('||') || agg(f._full);
      (g[sig] = g[sig] || []).push(id);
    });
    return Object.values(g).sort((a, b) => (J[a[0]].title || '').localeCompare(J[b[0]].title || ''));
  }

  function stage1(ids = Object.keys(J), opts = {}) {
    const dateRe = opts.dateRe || DATE_RE, eduRe = opts.eduRe || EDU_RE;
    const uniq = a => [...new Set(a)];
    return ids.map(id => {
      const sents = [];
      body((J[id] && J[id].f) || {}).forEach(([k, v]) =>
        v.split(/(?<=[.!?])\s+|\n/).forEach(s => { s = s.trim(); if (s) sents.push([k, s]); }));
      const d = uniq(sents.filter(([k, s]) => dateRe.test(s)).map(([k, s]) => s.slice(0, 200)));
      const e = uniq(sents.filter(([k, s]) => !/^Intro/i.test(k) && eduRe.test(s)).map(([k, s]) => s.slice(0, 200)));
      return `${id} | ${J[id].title} | ${meta(id)}\n  DATES: ${d.join(' ¦ ')}\n  EDU: ${e.join(' ¦ ')}`;
    });
  }

  function scan(re, ids = Object.keys(J)) {
    const rx = new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g');
    const out = [];
    ids.forEach(id => {
      const all = body((J[id] && J[id].f) || {}).map(([k, v]) => v).join('\n');
      const m = all.match(rx);
      if (m) out.push(`${id}: ${[...new Set(m.map(x => x.toLowerCase()))].join(',')}`);
    });
    return out;
  }

  function detail(ids, labels, maxChars = 1500) {
    const c = s => (s || '').replace(/\n+/g, ' • ').replace(/\s+/g, ' ').trim();
    return ids.map(id => {
      const f = (J[id] && J[id].f) || {};
      const parts = (labels || Object.keys(f).filter(k => !CONFIG.metaLabels.test(k))).map(l => `${l}: ${c(f[l]).slice(0, maxChars)}`);
      return `=== ${id} | ${J[id].title} | ${meta(id)}\n${parts.join('\n')}`;
    }).join('\n\n');
  }

  // Experience mentions, for the rule "cut anything asking for more than one year".
  const WORD_NUM = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 };
  function years(ids = Object.keys(J)) {
    const out = [];
    ids.forEach(id => {
      const txt = body((J[id] && J[id].f) || {}).filter(([k]) => !/^Intro/i.test(k)).map(([k, v]) => v).join('\n');
      const rx = /(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*\+?\s*(?:(?:-|to)\s*\d+\s*)?(years?|yrs?|months?)\b/gi;
      const hits = [];
      let m;
      while ((m = rx.exec(txt))) {
        const n = /^\d/.test(m[1]) ? parseFloat(m[1]) : WORD_NUM[m[1].toLowerCase()];
        const yrs = /^m/i.test(m[2]) ? n / 12 : n;              // ranges are judged by their lower bound
        const ctx = txt.slice(Math.max(0, m.index - 30), m.index + m[0].length + 15).replace(/\s+/g, ' ');
        hits.push(`${yrs > 1 ? '[>1y] ' : ''}...${ctx}...`);
      }
      if (hits.length) out.push(`${id}: ${[...new Set(hits)].join(' || ')}`);
    });
    return out;
  }

  function show(text) {
    const s = Array.isArray(text) ? text.join('\n') : String(text);
    document.body.innerHTML = '<article><pre id="ij-out" style="white-space:pre-wrap"></pre></article>';
    document.getElementById('ij-out').textContent = s;
    return `rendered ${s.length} chars; call get_page_text next`;
  }

  window.__ij = { CONFIG, J, start, status, groups, stage1, scan, years, detail, show, h2t, agg, DATE_RE, EDU_RE };
  return 'window.__ij ready';
})();
