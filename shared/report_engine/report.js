/*
 * Laighthouse report renderer (standalone).
 *
 * Renders a report payload — the same shape the Laighthouse web app reads from
 * `/api/analysis-artifact/{report_id}` — into the exact DOM/CSS structure of the
 * web app's report page (app.laight.ai/m/report/{id}). It is a vanilla-JS port of
 * the app's React section components (sections-*.js / TreeMap-*.js /
 * ActionCardMarkdown-*.js), so class names, labels, number formats, chart options
 * and interactions match the app.
 *
 * Input:  window.__LH_REPORT__ = {
 *   meta:  { type: "daily"|"mtd"|"monthly", name, reference_date, created, author,
 *            published, brand: { name, advertiser, color, initials } },
 *   items: [ { order, analysis_artifact_id?, analysis_artifact: { type, data } } ]
 * }
 * Requires: Chart.js 4 (window.Chart), chartjs-plugin-datalabels (window.ChartDataLabels),
 *           marked (window.marked), echarts (window.echarts, only when a tree_map exists).
 */
(function () {
  'use strict';

  // ───────────────────────────── i18n (ko catalog subset of the web app) ─────────────────────────────
  var T = {
    empty: '표시할 데이터가 없습니다',
    noResult: '조회된 결과가 없습니다.',
    search: '검색',
    tableSearch: '표 검색',
    rowsPerPage: '페이지당 행 수',
    nRows: function (n) { return n + '개'; },
    collapseAll: '모두 접기',
    expand: '펼치기',
    collapse: '접기',
    prev: '이전',
    next: '다음',
    all: '전체',
    legendGroup: '표시할 항목',
    period: '기간 진척률',
    target: '목표',
    current: '현재',
    monthTarget: '월 목표',
    spent: '소진비용',
    monthRevenue: '월 매출',
    monthRoas: '월 ROAS',
    days: function (a, b) { return a + '/' + b + '일'; },
    media: '매체',
    burnRate: '예산 소진율',
    monthBudget: '월 예산',
    expectedSpend: '예상 소진예산',
    actualSpend: '실 소진예산',
    remaining: '잔여 예산',
    sum: '합계',
    other: '기타',
    date: '일자',
    rowCount: function (n) { return n + '행'; },
    promoInfo: '프로모션 정보',
    schedule: '일정',
    close: '닫기',
    periodLabel: '기간',
    detail: '상세 정보',
    owner: '담당자',
    salesChannel: '판매 채널',
    link: '링크',
    competitor: '경쟁사',
    competitorName: '경쟁사명',
    actions: '권장 액션',
    background: '배경 및 근거',
    aiTitle: 'AI 제안',
    aiHint: '이 보고서에서 AI가 만든 제안입니다. 다른 화면으로 이동하면 사라집니다.',
    tmAll: '트리맵 전체 보기',
    tmAllTitle: '전체 보기',
    tmBack: '상위 트리맵으로 이동',
    tmItem: function (n) { return '항목 ' + n; },
    sales: '매출',
    adCost: '광고비',
    roas: 'ROAS',
    ctr: '클릭률',
    month: function (m) { return m + '월'; },
    year: function (y) { return y + '년'; },
    calUnavailable: '캘린더 데이터를 표시할 수 없습니다.',
    noBody: '보고서 개요 데이터가 준비 중입니다.',
    optimalSpendHelp: '적정 광고비란?\n설정된 목표 ROAS를 달성하기 위해 제안되는 최적의 일일 예산입니다.\n- 계산 방식: (최근 7일 평균 전환 가치 / 목표 ROAS) × 시즌 가중치를 바탕으로 산출되었습니다.',
    tpTitle: '목표 달성 현황',
    budgetSum: '월 예산대비 소진율',
    revenueSum: '월 목표 매출 대비 달성률',
    roasSum: '월 누적 ROAS',
    published: '공개',
    unpublished: '미공개',
    kind: { daily: '일간', mtd: 'MTD', monthly: '월 마감' },
    reportKind: function (k) { return k + ' 성과 보고서'; },
    created: function (at, who) { return '생성 ' + at + ' · ' + who; },
    weekday: ['일', '월', '화', '수', '목', '금', '토'],
    sheetSub: function (y, m, last, prev) { return y + '년 ' + m + '월 1일 – ' + m + '월 ' + last + '일 · 전월(' + prev + ') 대비'; },
    sheetFoot: function (day, who) { return 'Laighthouse · 생성 ' + day + ' · ' + who; },
    rawNotice: '이 항목은 아직 화면에 표시할 수 없어 원본 데이터로 보여 줍니다.',
    rawToggle: '데이터 원본 보기'
  };
  var SECTION_TYPE_LABEL = { ai_suggestion: 'AI 제안', target_progression: '목표 달성 현황' };
  var SALES_CHANNEL = { ownMall: '자사몰', coupang: '쿠팡', naver: '네이버', elevenst: '11번가', other: '기타' };
  var CHANNEL_CODE_LABEL = { BRS: '브랜드 검색', PLINK: '파워링크', NVSHOP: '쇼핑검색' };

  // Tree-map labels (MO / AO in the app)
  var TM_LABELS = {
    campaign_name: '캠페인 명', cost: '일일 광고비', impression: '일일 노출수', click: '일일 클릭수',
    revenue: '일일 매출액', ctr: '일일 CTR', cvr: '일일 CVR', revenue_average: '최근 7일 평균 일매출액',
    ctr_average: '최근 7일 평균 CTR', cvr_average: '최근 7일 평균 CVR', revenue_ratio: '7일 평균 대비 매출 비율',
    ctr_ratio: '7일 평균 대비 CTR 비율', cvr_ratio: '7일 평균 대비 CVR 비율'
  };
  var TM_RATIO_FALLBACK = '최근 7일 평균 대비 진단';
  var TM_BANDS = [
    { min: 1.3, color: '#0394AD', label: '매우 우수' },
    { min: 1.1, max: 1.3, color: '#46B4CF', label: '우수' },
    { min: 0.9, max: 1.1, color: '#E2E4E9', label: '평이' },
    { min: 0.7, max: 0.9, color: '#F7AA9A', label: '악화' },
    { max: 0.7, color: '#EF7A68', label: '매우 악화' }
  ];

  // ───────────────────────────── DOM helpers ─────────────────────────────
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
        var v = attrs[k];
        if (v === undefined || v === null || v === false) continue;
        if (k === 'className') el.className = v;
        else if (k === 'style' && typeof v === 'object') {
          for (var s in v) { if (v[s] !== undefined && v[s] !== null) { if (s.indexOf('--') === 0) el.style.setProperty(s, v[s]); else el.style[s] = v[s]; } }
        } else if (k === 'html') el.innerHTML = v;
        else if (k.indexOf('on') === 0 && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
        else if (v === true) el.setAttribute(k, '');
        else el.setAttribute(k, String(v));
      }
    }
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function append(el, c) {
    if (c === null || c === undefined || c === false || c === '') return;
    if (Array.isArray(c)) { c.forEach(function (x) { append(el, x); }); return; }
    if (typeof c === 'string' || typeof c === 'number') el.appendChild(document.createTextNode(String(c)));
    else el.appendChild(c);
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  var ICONS = {
    'refresh': '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path><path d="M8 16H3v5"></path>',
    'chevron-left': '<path d="m15 18-6-6 6-6"></path>',
    'chevron-right': '<path d="m9 18 6-6-6-6"></path>',
    'x': '<path d="M18 6 6 18"></path><path d="m6 6 12 12"></path>',
    'sparkles': '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"></path><path d="M20 2v4"></path><path d="M22 4h-4"></path><circle cx="4" cy="20" r="2"></circle>',
    'arrow-left': '<path d="m12 19-7-7 7-7"></path><path d="M19 12H5"></path>',
    'info': '<circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path>'
  };
  var ICON_CLASS = { refresh: 'lucide-refresh-cw', sparkles: 'lucide-sparkles' };
  function icon(name, size) {
    size = size || 16;
    var span = document.createElement('span');
    span.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="lucide ' + (ICON_CLASS[name] || ('lucide-' + name)) + '" aria-hidden="true">' + (ICONS[name] || '') + '</svg>';
    return span.firstChild;
  }
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
  function loc(n) { return Number(n).toLocaleString('ko-KR'); }
  function locU(n) { return Number(n).toLocaleString(); }

  var MOUNT_QUEUE = [];
  function onMount(fn) { MOUNT_QUEUE.push(fn); }

  // ───────────────────────────── common pieces ─────────────────────────────
  function Empty(text) { return h('div', { className: 'empty empty-compact' }, h('div', { className: 'e-title t-sm' }, text || T.empty)); }

  // sortable header cell (L)
  function SortTh(label, key, sort, onSort, className, style) {
    var active = sort && sort.key === key;
    return h('th', {
      className: 'sortable ' + (active ? 'sorted' : '') + ' ' + (className || ''),
      style: style, 'aria-sort': active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none',
      onClick: function () { onSort(key); }
    }, label, h('span', { className: 'sort', 'aria-hidden': 'true' }, active ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'));
  }
  function nextSort(cur, key) { return cur && cur.key === key ? (cur.dir === 'asc' ? { key: key, dir: 'desc' } : null) : { key: key, dir: 'asc' }; }
  function isEmptyVal(e) { return e == null || e === '' || e === '-' || e === '—'; }
  function sortVal(e) {
    if (isEmptyVal(e)) return { kind: 'empty' };
    if (typeof e === 'number') return { kind: 'number', value: e };
    var t = String(e).trim();
    if (isEmptyVal(t)) return { kind: 'empty' };
    var n = t.replace(/,/g, '').replace(/^[₩$]/, '').replace(/%$/, '');
    return /^-?\d+(\.\d+)?$/.test(n) ? { kind: 'number', value: Number(n) } : { kind: 'string', value: t.toLowerCase() };
  }
  function cmp(a, b, dir) {
    var r = sortVal(a), i = sortVal(b);
    if (r.kind === 'empty' && i.kind === 'empty') return 0;
    if (r.kind === 'empty') return 1;
    if (i.kind === 'empty') return -1;
    if (r.kind === 'number' && i.kind === 'number') return dir === 'desc' ? i.value - r.value : r.value - i.value;
    var c = String(r.value).localeCompare(String(i.value), undefined, { numeric: true, sensitivity: 'base' });
    return dir === 'desc' ? -c : c;
  }
  var ARROW = { up: '▲', down: '▼', flat: '' };
  function parseDelta(e) {
    var t = e.trim(), signed = /^[+\-−]/.test(t), r = signed ? t.slice(1).trim() : t,
      i = Number.parseFloat(r.replace(/,/g, '')),
      dir = !signed || !Number.isFinite(i) || i === 0 ? 'flat' : (t.charAt(0) === '+' ? 'up' : 'down');
    return { direction: dir, value: r, marked: dir === 'flat' ? r : ARROW[dir] + ' ' + r };
  }

  function Pager(page, pages, onPage) {
    if (pages <= 1) return null;
    var start = Math.max(1, Math.min(page - 2, pages - 4)), btns = [];
    for (var k = 0; k < Math.min(5, pages); k++) {
      (function (p) {
        btns.push(h('button', { 'aria-current': p === page ? 'page' : undefined, onClick: function () { onPage(p); } }, String(p)));
      })(start + k);
    }
    return h('div', { className: 'pager' },
      h('button', { 'aria-label': T.prev, disabled: page <= 1, onClick: function () { onPage(page - 1); } }, icon('chevron-left', 14)),
      btns,
      h('button', { 'aria-label': T.next, disabled: page >= pages, onClick: function () { onPage(page + 1); } }, icon('chevron-right', 14)));
  }

  function Modal(content, onClose) {
    var scrim = h('div', { className: 'scrim' }, content);
    scrim.addEventListener('mousedown', function (ev) { if (ev.target === scrim) onClose(); });
    function onKey(ev) { if (ev.key === 'Escape') { onClose(); document.removeEventListener('keydown', onKey); } }
    document.addEventListener('keydown', onKey);
    return scrim;
  }

  // ───────────────────────────── markdown (ActionCardMarkdown) ─────────────────────────────
  var md = null;
  function mdEngine() {
    if (md) return md;
    var M = window.marked;
    var esc2 = esc;
    var tex = function (e) { return e.replace(/\\text\{([^}]*)\}/g, '$1').replace(/\\times/g, '×').replace(/\\div/g, '÷').replace(/\\approx/g, '≈').replace(/\\[,;]/g, ' '); };
    var isTex = function (e) { return /\\[a-zA-Z]+|[{}^_=]/.test(e.trim()); };
    var safeHref = function (e) { return /^(https?:|mailto:)/i.test((e || '').trim()); };
    md = new M.Marked({ gfm: true, breaks: true, async: false });
    md.use({
      tokenizer: { del: function () { } },
      extensions: [{
        name: 'mathBlock', level: 'inline', start: function (e) { return e.indexOf('$$'); },
        tokenizer: function (e) { var t = /^\$\$([\s\S]+?)\$\$/.exec(e); if (t && isTex(t[1])) return { type: 'mathBlock', raw: t[0], text: t[1] }; },
        renderer: function (e) { return '<div class="math-block">' + esc2(tex(String(e.text).trim())) + '</div>'; }
      }, {
        name: 'mathInline', level: 'inline', start: function (e) { return e.indexOf('$'); },
        tokenizer: function (e) { var t = /^\$([^\n$]+?)\$/.exec(e); if (t && isTex(t[1])) return { type: 'mathInline', raw: t[0], text: t[1] }; },
        renderer: function (e) { return '<span class="math-inline">' + esc2(tex(String(e.text).trim())) + '</span>'; }
      }, {
        name: 'looseStrong', level: 'inline', start: function (e) { return e.indexOf('**'); },
        tokenizer: function (e) { var t = /^\*\*(.+?)\*\*/.exec(e); if (t) return { type: 'looseStrong', raw: t[0], tokens: this.lexer.inlineTokens(t[1]) }; },
        renderer: function (e) { return '<strong>' + this.parser.parseInline(e.tokens || []) + '</strong>'; }
      }],
      renderer: {
        html: function (e) { return esc2(e.text); },
        link: function (e) { var t = this.parser.parseInline(e.tokens); return safeHref(e.href) ? '<a href="' + esc2(e.href) + '">' + t + '</a>' : t; },
        image: function (e) { return safeHref(e.href) ? '<img src="' + esc2(e.href) + '" alt="' + esc2(e.text || '') + '">' : esc2(e.text || ''); }
      }
    });
    return md;
  }
  function mdBlock(items) {
    var src = items.map(function (e) { return e == null ? '' : String(e); }).join('\n\n');
    var html = mdEngine().parse(src).replace(/<table>/g, '<div class="sec-md-table"><table>').replace(/<\/table>/g, '</table></div>');
    return h('div', { className: 'sec-md', html: html });
  }
  function mdInline(s) { return mdEngine().parseInline(s == null ? '' : String(s)); }

  function TextSection(s) {
    return s.items && s.items.length ? mdBlock(s.items) : h('p', { className: 't-sm fg-3' }, T.noBody);
  }
  function ActionCardBody(card) {
    var bg = Array.isArray(card.background) ? card.background : (card.background ? [card.background] : []);
    return [
      card.actions && card.actions.length ? h('div', null,
        h('div', { className: 'eyebrow mb-2' }, T.actions),
        h('ol', { className: 'sec-ol' }, card.actions.map(function (a) { return h('li', { html: mdInline(a) }); }))) : null,
      bg.length ? h('div', null, h('div', { className: 'eyebrow mb-2' }, T.background), mdBlock(bg)) : null
    ];
  }
  function ActionCardSection(c) {
    return h('div', { className: 'stack gap-3' },
      c.tags && c.tags.length ? h('div', { className: 'row gap-1' }, c.tags.map(function (t) { return h('span', { className: 'badge badge-pending' }, t); })) : null,
      h('p', { className: 't-sm fg-2 sec-p' }, c.description),
      ActionCardBody(c));
  }

  // ───────────────────────────── target progression (qn / or / sr) ─────────────────────────────
  var lower = function (e) { return e.toLowerCase(); };
  var isRatioName = function (e) { return ['roas', 'roas%', '율', '%'].some(function (t) { return lower(e).indexOf(t) >= 0; }); };
  var isRoas = function (e) { return lower(e).indexOf('roas') >= 0; };
  var isCountName = function (e) { return ['impression', 'click', 'reach', 'session', 'user', 'order', 'purchase', 'conversion', 'view', 'count'].some(function (t) { return lower(e).indexOf(t) >= 0; }); };
  var pct100 = function (e) { return Number(((e || 0) * 100).toFixed(0)); };
  var rate = function (a, b) { return b ? Number((a / b * 100).toFixed(1)) : 0; };
  var isSnake = function (e) { return /^[a-z0-9]+(?:_[a-z0-9]+)+$/i.test(e); };
  var symFromName = function (e) { return isRatioName(e) || isCountName(e) ? '' : (isSnake(e) ? '$' : '₩'); };
  var UNIT_FMT = {
    KRW: { currencySymbol: '₩', valueSuffix: '', changeRateSuffix: '%' },
    PERCENT: { currencySymbol: '', valueSuffix: '%', changeRateSuffix: '%p' },
    COUNT: { currencySymbol: '', valueSuffix: '', changeRateSuffix: '%' }
  };
  var unitFmt = function (e) { return typeof e === 'string' ? UNIT_FMT[e.trim()] : undefined; };
  var symFor = function (name, unit) { return unit === '%' ? '' : unit === '$' ? '$' : (unit === '₩' || unit === 'KRW') ? '₩' : unit === '' ? '' : symFromName(name); };
  var num = function (e) { var t = typeof e === 'number' ? e : Number(e); return Number.isFinite(t) ? t : 0; };
  var numOrNull = function (e) { return typeof e === 'number' && Number.isFinite(e) ? e : null; };

  function normTP(e) {
    var n = e.target_progression && typeof e.target_progression === 'object' ? e.target_progression : e;
    var per = n.period && typeof n.period === 'object' ? n.period : {};
    var items = (Array.isArray(n.items) ? n.items : []).filter(function (x) { return x && typeof x === 'object'; }).map(function (x) {
      return {
        name: String(x.name == null ? '' : x.name), display: typeof x.display === 'string' ? x.display : undefined,
        unit: typeof x.unit === 'string' ? x.unit : undefined, target: num(x.target), hasTarget: x.target !== null && x.target !== undefined,
        expected: num(x.expected), actual: num(x.actual), changeRate: numOrNull(x.change_rate)
      };
    }).filter(function (x) { return x.name.length > 0; });
    return { name: typeof n.name === 'string' ? n.name : '', period: { current: num(per.current), total: num(per.total) }, items: items };
  }
  function TargetProgression(e, ctx) {
    var t = normTP(e);
    var metrics = t.items.map(function (x) {
      var amount = x.target === 0 ? x.actual : x.target, uf = unitFmt(x.unit);
      return uf ? { title: x.name, amount: amount, currencySymbol: uf.currencySymbol, valueSuffix: uf.valueSuffix, changeRateSuffix: uf.changeRateSuffix, changeRate: x.changeRate }
        : { title: x.name, amount: isRoas(x.name) ? pct100(amount) : amount, changeRateSuffix: '%', currencySymbol: symFor(x.name, x.unit), valueSuffix: isRatioName(x.name) ? '%' : '', changeRate: x.changeRate };
    });
    var sums = t.items.map(function (x) {
      var tr = rate(x.expected, x.target), cr = rate(x.actual, x.target);
      return {
        title: x.display || x.name, metricName: x.name, percentage: cr,
        diff: isRoas(x.name) ? (x.actual - x.expected) * 100 : Number((cr - tr).toFixed(1)),
        targetAmount: x.target, currentAmount: x.actual, targetRate: tr, currentRate: cr, currencySymbol: symFor(x.name, x.unit)
      };
    });
    if (!sums.length) return Empty();
    var periodPct = t.period.total ? Number((t.period.current / t.period.total * 100).toFixed(1)) : 0;
    var anyTarget = sums.some(function (x) { return x.targetAmount !== 0; });
    var monthly = ctx.reportType === 'monthly';
    var grid = h('div', { className: 'tp-grid', style: { '--tp-cols': String(Math.max(metrics.length, 1)) } }, metrics.map(TPMetric));
    if (t.period.total > 0 && anyTarget) {
      grid.appendChild(monthly ? TPMonthlyCard(t.name, sums) : TPCard(t.name, periodPct, t.period.current, t.period.total, sums));
    }
    return grid;
  }
  function TPMetric(m) {
    var hasChange = typeof m.changeRate === 'number' && Number.isFinite(m.changeRate);
    var dir = !Number.isFinite(m.changeRate) || m.changeRate === 0 ? 'flat' : (m.changeRate > 0 ? 'up' : 'down');
    return h('article', { className: 'tp-metric' },
      h('p', { className: 'tp-metric-title' }, m.title),
      h('div', { className: 'tp-metric-body' },
        h('div', { className: 'tp-metric-amount' },
          m.currencySymbol ? h('span', null, m.currencySymbol) : null,
          h('span', null, loc(m.amount)),
          m.valueSuffix ? h('span', null, m.valueSuffix) : null),
        hasChange ? h('span', { className: 'tp-change ' + (dir === 'up' ? 'is-up' : dir === 'down' ? 'is-down' : '') },
          (dir === 'flat' ? '' : ARROW[dir] + ' ') + Math.abs(m.changeRate).toFixed(2) + m.changeRateSuffix) : null));
  }
  var metricNameOf = function (e) { return e.metricName != null ? e.metricName : e.title; };
  var fmtPctFromRatio = function (e) { return Number(((e || 0) * 100).toFixed(0)).toLocaleString('ko-KR') + '%'; };
  function sumValueText(e) { return isRoas(metricNameOf(e)) ? fmtPctFromRatio(e.currentAmount) : Number(e.percentage).toFixed(1) + '%'; }
  function sumAmountText(e, v) { return isRoas(metricNameOf(e)) ? fmtPctFromRatio(v) : e.currencySymbol === '' ? (v || 0).toLocaleString('ko-KR') : (e.currencySymbol == null ? '₩' : e.currencySymbol) + (v || 0).toLocaleString('ko-KR'); }
  function TPCard(title, percentage, done, total, sums) {
    var d = Number.isNaN(Number(percentage)) ? 0 : Math.min(100, Math.max(0, Number(percentage || 0)));
    var f = total ? Number((done / total * 100).toFixed(1)) : 0;
    var diffOf = function (e) {
      return isRoas(metricNameOf(e)) ? Number((e.currentAmount * 100).toFixed(0)) - Number((e.targetAmount * 100).toFixed(0))
        : Number(e.currentRate.toFixed(1)) - Number((100 * done / (total || 1)).toFixed(1));
    };
    var decs = function (e) { return isRoas(metricNameOf(e)) ? 0 : 1; };
    return h('article', { className: 'tp-card' },
      title ? h('header', { className: 'tp-card-head' }, h('p', { className: 'tp-card-title' }, title)) : null,
      h('div', { className: 'tp-panel' },
        h('div', { className: 'tp-panel-stats' },
          h('span', { className: 'tp-panel-label' }, T.period),
          h('span', { className: 'tp-panel-values' },
            h('span', { className: 'tp-panel-percent' }, f + '%'),
            h('span', { className: 'tp-panel-days' }, T.days(done, total)))),
        h('div', { className: 'tp-bar-row' },
          h('span', { className: 'tp-bar-end' }, '0%'),
          h('div', { className: 'tp-bar', role: 'progressbar', 'aria-label': T.period, 'aria-valuenow': d, 'aria-valuemin': 0, 'aria-valuemax': 100 },
            h('span', { className: 'tp-bar-marker', style: { left: d + '%' } }, d + '%'),
            h('span', { className: 'tp-bar-fill', style: { width: d + '%' } })),
          h('span', { className: 'tp-bar-end' }, '100%'))),
      h('div', { className: 'tp-sum-list' }, sums.map(function (e) {
        var t = Number(diffOf(e).toFixed(decs(e)));
        return h('div', { className: 'tp-sum' },
          h('p', { className: 'tp-sum-title' }, e.title),
          h('div', { className: 'tp-sum-percent' },
            h('span', { className: 'tp-sum-value' }, sumValueText(e)),
            h('span', { className: 'tp-sum-diff ' + (t < 0 ? 'is-negative' : '') }, (t >= 0 ? '+' : '') + t.toFixed(decs(e)), h('span', { className: 'tp-sum-diff-unit' }, '%p'))),
          h('div', { className: 'tp-sum-pair tp-sum-labels' }, h('span', null, T.target), h('span', null, T.current)),
          h('div', { className: 'tp-sum-pair tp-sum-amounts' }, h('span', null, sumAmountText(e, e.targetAmount)), h('span', null, sumAmountText(e, e.currentAmount))));
      })));
  }
  function TPMonthlyCard(title, sums) {
    var curLabel = function (t) { return t.indexOf('소진') >= 0 ? T.spent : t.indexOf('매출') >= 0 ? T.monthRevenue : t.indexOf('ROAS') >= 0 ? T.monthRoas : T.current; };
    return h('article', { className: 'tp-card' },
      title ? h('header', { className: 'tp-card-head' }, h('p', { className: 'tp-card-title is-big' }, title)) : null,
      h('div', { className: 'tp-msum-list' }, sums.map(function (e) {
        return h('div', { className: 'tp-msum' },
          h('p', { className: 'tp-msum-title' }, e.title),
          h('span', { className: 'tp-msum-value' }, sumValueText(e)),
          h('div', { className: 'tp-msum-pair' },
            h('div', null, h('p', { className: 'tp-msum-label' }, T.monthTarget), h('p', { className: 'tp-msum-amount' }, sumAmountText(e, e.targetAmount))),
            h('span', { className: 'tp-msum-line', 'aria-hidden': 'true' }),
            h('div', null, h('p', { className: 'tp-msum-label' }, curLabel(e.title)), h('p', { className: 'tp-msum-amount' }, sumAmountText(e, e.currentAmount)))));
      })));
  }

  // ───────────────────────────── source progression (Qe) ─────────────────────────────
  function SourceProgression(e, ctx) {
    var items = e.items || [];
    if (!items.length) return Empty();
    var groups = new Map(), total = { name: T.sum, progress: 0, target: 0, expected: 0, actual: 0, remaining: 0, summary: true };
    items.forEach(function (x) {
      var parts = String(x.display != null ? x.display : x.name).split(':');
      var g = (parts[0] || '').trim() || T.other;
      var nm = parts.length === 1 ? x.name : (parts.slice(1).join(':').trim() || x.name);
      var a = num(x.target), o = num(x.actual), s = num(x.expected);
      var row = { name: nm, progress: a > 0 ? Number((o / a * 100).toFixed(1)) : 0, target: a, expected: s, actual: o, remaining: a - o };
      total.target += a; total.actual += o; total.expected += s; total.remaining += row.remaining;
      groups.set(g, (groups.get(g) || []).concat([row]));
    });
    total.progress = total.target > 0 ? Number((total.actual / total.target * 100).toFixed(1)) : 0;
    var per = ctx.period, marker = per && per.total ? 100 * per.current / per.total : null;
    var COLS = [{ key: 'target', label: T.monthBudget }, { key: 'expected', label: T.expectedSpend }, { key: 'actual', label: T.actualSpend }, { key: 'remaining', label: T.remaining }];
    var fmt = function (r, v) { return isRoas(r.name) ? Number((v * 100).toFixed(0)).toLocaleString() + '%' : '₩' + v.toLocaleString(); };
    var root = h('div', { className: 'stack gap-4' }), sort = null;
    function bar(r) {
      return h('div', { className: 'sec-mb-bar' },
        h('span', { className: 'sec-mb-fill', style: { width: Math.max(0, Math.min(100, r.progress)) + '%' } }),
        marker != null ? h('span', { className: 'sec-mb-marker', style: { left: marker + '%' } }) : null,
        h('span', { className: 'sec-mb-text' }, r.progress.toFixed(1), '%'));
    }
    function table(rows, withHead) {
      var onSort = function (k) { sort = nextSort(sort, k); render(); };
      return h('div', { className: 'table-wrap', style: { overflowX: 'auto' } },
        h('table', { className: 'data-table table-dense sec-table sec-mb' },
          withHead ? h('thead', null, h('tr', null,
            SortTh(T.media, 'name', sort, onSort),
            SortTh(T.burnRate, 'progress', sort, onSort, '', { minWidth: '180px' }),
            COLS.map(function (c) { return SortTh(c.label, c.key, sort, onSort, 'num'); }))) : null,
          h('tbody', null, rows.map(function (r) {
            return h('tr', { className: r.summary ? 'sec-total' : undefined },
              h('td', { className: 'cell-title' }, r.name), h('td', null, bar(r)),
              COLS.map(function (c) { return h('td', { className: 'num' }, fmt(r, r[c.key])); }));
          }))));
    }
    function sorted(rows) { return sort ? rows.slice().sort(function (a, b) { return cmp(a[sort.key], b[sort.key], sort.dir); }) : rows; }
    function render() {
      clear(root);
      groups.forEach(function (rows, g) {
        root.appendChild(h('div', { className: 'stack gap-2' }, h('div', { className: 'section-title' }, g), table(sorted(rows), true)));
      });
      root.appendChild(table([total], false));
    }
    render();
    return root;
  }

  // ───────────────────────────── daily contribution (xo) & table (wn) ─────────────────────────────
  var isNumLike = function (e) { return typeof e === 'number' || (typeof e === 'string' && /^[-−+]?[₩$]?[\d,]+(\.\d+)?\s?(%|[a-zA-Z가-힣]{0,3})$/.test(e.trim())); };
  var isNumCell = function (e) { return !e || e === '-' || /^-?\d+(\.\d+)?$/.test(String(e).replace(/,/g, '').replace(/%$/, '')); };
  function DailyContribution(e) {
    var withDates = !!e.dates && e.dates.length === (e.items || []).length;
    var cols = withDates ? [T.date].concat(e.cols) : e.cols;
    var rows = (e.items || []).map(function (r, i) { return withDates ? [e.dates[i]].concat(r) : r; });
    if (!rows.length) return Empty();
    return h('div', { className: 'table-wrap' },
      h('table', { className: 'data-table table-dense' },
        h('thead', null, h('tr', null, cols.map(function (c, n) {
          return h('th', { className: n > 0 && rows.every(function (r) { return r[n] == null || r[n] === '' || isNumLike(r[n]); }) ? 'num' : undefined }, c);
        }))),
        h('tbody', null, rows.map(function (r) {
          return h('tr', null, cols.map(function (c, n) { return h('td', { className: isNumLike(r[n]) ? 'num' : undefined }, r[n] == null ? '—' : r[n]); }));
        }))),
      h('div', { className: 'table-foot' }, h('span', null, T.rowCount(rows.length))));
  }
  function PlainTable(e) {
    var cols = e.cols || [], rows = e.items || [];
    if (!rows.length) return Empty();
    var numCol = cols.map(function (c, i) { return rows.every(function (r) { return isNumCell(r[i] == null ? '' : r[i]); }); });
    return [h('div', { className: 'table-wrap', style: { overflowX: 'auto' } },
      h('table', { className: 'data-table table-dense sec-table' },
        h('thead', null, h('tr', null, cols.map(function (c, i) { return h('th', { className: numCol[i] ? 'num' : undefined }, c); }))),
        h('tbody', null, rows.map(function (r) { return h('tr', null, cols.map(function (c, i) { return h('td', { className: numCol[i] ? 'num' : undefined }, r[i] == null ? '' : r[i]); })); })))),
    e.description ? h('p', { className: 'hint mt-2' }, e.description) : null];
  }

  // ───────────────────────────── paged table (Cn) ─────────────────────────────
  var CH_COLS = ['네이버 광고 채널명', '광고채널', '광고 채널', '광고 채널명', '매체'];
  var CAMP_COLS = ['캠페인', '캠페인명', '캠페인 명', 'campaign_name'];
  var GRP_COLS = ['광고그룹', '광고그룹명', '광고 그룹', '광고 그룹명', 'ad_group_name'];
  var CH_DEFAULT = '네이버 광고 채널명';
  var TREE_NAMES = ['캠페인 별 성과', '캠페인/광고그룹/키워드 성과'];
  var TREE_FULL = '캠페인/광고그룹/키워드 성과';
  var RATIO_TREE = new Set(['CTR', 'ROAS']);
  var RATIO_CH = new Set(['일ROAS', '월누적ROAS']);
  var OPTIMAL = '적정 광고비';
  var PAGE_SIZES = [10, 20, 30, 40, 50];
  var MEDIA_SORTED = new Set(['Sales campaign: performance by media source', 'Branding campaign: performance by media source']);
  var ALL = '전체';
  var findCol = function (cols, cands) { for (var i = 0; i < cands.length; i++) if (cols.indexOf(cands[i]) >= 0) return cands[i]; return ''; };
  var trimS = function (e) { return String(e == null ? '' : e).trim(); };
  var isAll = function (e) { var t = trimS(e); return !t || t === ALL; };
  var treeId = function () { return Array.prototype.slice.call(arguments).map(encodeURIComponent).join('::'); };
  function unitLabel(e) { var t = (e || '').trim(), m = { KRW: '원', '원': '원', '₩': '원', PERCENT: '%', '%': '%', COUNT: '' }; return t in m ? m[t] : t; }
  function rowsOf(e) {
    var cols = e.cols || [];
    var rows = (e.items || []).map(function (r) { var o = {}; cols.forEach(function (c, i) { o[c] = r[i] == null ? '' : r[i]; }); return o; });
    if (!MEDIA_SORTED.has((e.name || '').trim())) return rows;
    var m = findCol(cols, ['Media', '매체', '매체명']), p = findCol(cols, ['Month', '월', '기간']);
    return !m || !p ? rows : rows.sort(function (a, b) { return a[m].localeCompare(b[m]) || b[p].localeCompare(a[p]); });
  }
  function aggregate(rows, cols, fixed) {
    var o = {};
    cols.forEach(function (c) {
      if (fixed[c] !== undefined) { o[c] = fixed[c]; return; }
      var vals = rows.map(function (r) { return trimS(r[c]); }).filter(Boolean);
      if (!vals.length || vals.some(function (v) { return !/^-?\d+(\.\d+)?$/.test(v.replace(/,/g, '')); })) { o[c] = '-'; return; }
      var s = vals.reduce(function (a, v) { return a + Number(v.replace(/,/g, '')); }, 0);
      o[c] = Number.isInteger(s) ? s.toLocaleString() : s.toLocaleString(undefined, { maximumFractionDigits: 2 });
    });
    return o;
  }
  function buildTree(rows, cols, k) {
    var val = function (r, c) { return trimS(r[c]); };
    var chans = []; rows.forEach(function (r) { if (!isAll(r[k.channel])) { var v = val(r, k.channel); if (v && chans.indexOf(v) < 0) chans.push(v); } });
    return chans.map(function (ch) {
      var inCh = rows.filter(function (r) { return val(r, k.channel) === ch; });
      var camps = []; inCh.forEach(function (r) { var v = val(r, k.campaign); if (!isAll(v) && camps.indexOf(v) < 0) camps.push(v); });
      var children = camps.map(function (cp) {
        var inCp = inCh.filter(function (r) { return val(r, k.campaign) === cp; });
        var leaves = inCp.filter(function (r) { return !isAll(r[k.adGroup]); });
        var cid = treeId(ch, cp);
        var kids = leaves.map(function (r, i) {
          var ag = val(r, k.adGroup), id = treeId(ch, cp, ag, String(i)), row = Object.assign({}, r);
          row[k.channel] = ch; row[k.campaign] = cp; row[k.adGroup] = ag; row._treeId = id; row._depth = 3; row._hasChildren = false;
          return { id: id, row: row, children: [] };
        });
        var fixed = {}; fixed[k.channel] = ch; fixed[k.campaign] = cp; fixed[k.adGroup] = ALL;
        var own = rows.find(function (r) { return val(r, k.channel) === ch && val(r, k.campaign) === cp && isAll(r[k.adGroup]); });
        var row = Object.assign({}, own || aggregate(inCp, cols, fixed), fixed, { _treeId: cid, _depth: 2, _hasChildren: kids.length > 0, _expandColumn: k.campaign });
        return { id: cid, row: row, children: kids };
      });
      var id = treeId(ch), fixed = {}; fixed[k.channel] = ch; fixed[k.campaign] = ALL; fixed[k.adGroup] = ALL;
      var own = rows.find(function (r) { return val(r, k.channel) === ch && isAll(r[k.campaign]) && isAll(r[k.adGroup]); });
      var row = Object.assign({}, own || aggregate(inCh, cols, fixed), fixed, { _treeId: id, _depth: 1, _hasChildren: children.length > 0, _expandColumn: k.channel });
      return { id: id, row: row, children: children };
    });
  }
  function flatten(nodes, open, all) {
    var out = [];
    (function walk(list) { list.forEach(function (n) { out.push(Object.assign({}, n.row, { _hasChildren: n.children.length > 0 })); if (all || open.has(n.id)) walk(n.children); }); })(nodes);
    return out;
  }
  var rowHas = function (r, cols, q) { return cols.some(function (c) { return trimS(r[c]).toLowerCase().indexOf(q) >= 0; }); };
  var nodeHas = function (n, cols, q) { return rowHas(n.row, cols, q) || n.children.some(function (c) { return nodeHas(c, cols, q); }); };
  function filterTree(nodes, cols, q) {
    var out = [];
    nodes.forEach(function (n) { var kids = filterTree(n.children, cols, q); if (rowHas(n.row, cols, q) || kids.length) out.push(Object.assign({}, n, { children: kids })); });
    return out;
  }
  function PagedTable(e, inGroup, ancestors) {
    ancestors = ancestors || [];
    var cols = e.cols || [], name = (e.name || '').trim();
    var k = { channel: findCol(cols, CH_COLS), campaign: findCol(cols, CAMP_COLS), adGroup: findCol(cols, GRP_COLS) };
    var nKeys = [k.channel, k.campaign, k.adGroup].filter(Boolean).length;
    var d = inGroup && TREE_NAMES.indexOf(e.name || '') >= 0;
    var tree = inGroup ? (d && nKeys === 3) : nKeys >= 2;
    var channelSelect = d && !tree;
    var inDetail = ancestors.some(function (a) { return a.indexOf('전체 광고 성과 세부 데이터') >= 0; });
    var paginate0 = !(inDetail && name === TREE_FULL);
    var chanTable = inDetail && name.indexOf('광고 채널 성과') >= 0;
    var isFullTree = name === TREE_FULL;
    var chanLike = name.indexOf('광고 채널 성과') >= 0 || name.indexOf('채널 성과') >= 0;
    var rows = rowsOf(e);
    if (!rows.length) return Empty();
    var st = { channel: '', q: '', size: 10, page: 1, sort: null, open: new Set() };
    var chKey = k.channel || CH_DEFAULT;
    var numCols = new Set(cols.filter(function (c, i) { return (e.items || []).every(function (r) { return isNumCell(r[i] == null ? '' : r[i]); }); }));
    var shown = channelSelect ? cols.filter(function (c) { return c !== CH_DEFAULT; }) : cols;
    var numClass = function (c) { return numCols.has(c) && (!tree || (c !== k.channel && c !== k.campaign && c !== k.adGroup)) ? 'num' : undefined; };
    var suffix = function (c) { var t = c.replace(/\s/g, ''); return (tree && RATIO_TREE.has(t)) || (chanLike && RATIO_CH.has(t)) ? '%' : ''; };
    var withSuffix = function (v, s) { return !v || !s || v === '-' || v.slice(-s.length) === s ? v : v + s; };
    var root = h('div', { className: 'stack gap-3' });
    var head = function (c) {
      var u = unitLabel((e.units || [])[cols.indexOf(c)]);
      return [u ? c + ' (' + u + ')' : c, c === OPTIMAL ? h('span', { className: 'sec-help', title: T.optimalSpendHelp, 'aria-label': T.optimalSpendHelp }, '?') : null];
    };
    function hierCell(r, c) {
      var lvl = c === k.channel ? 1 : c === k.campaign ? 2 : 3;
      var text = (r._depth === 2 && (c === k.channel || c === k.adGroup)) || (r._depth === 3 && (c === k.channel || c === k.campaign)) ? '' : trimS(r[c]);
      var isExp = r._expandColumn === c, hasBtn = !!r._hasChildren && isExp;
      var open = !!r._treeId && (st.open.has(r._treeId) || !!st.q.trim());
      return h('span', { className: 'sec-hcell' },
        hasBtn ? h('button', {
          type: 'button', className: 'sec-caret', 'aria-expanded': String(open), 'aria-label': open ? T.collapse : T.expand,
          onClick: function () { if (st.open.has(r._treeId)) st.open.delete(r._treeId); else st.open.add(r._treeId); render(); }
        }, h('span', { className: open ? 'is-open' : undefined })) : (lvl === 1 || isExp ? h('span', { className: 'sec-caret-ph' }) : null),
        h('span', { className: lvl > 1 && text === ALL ? 'fg-3 truncate' : 'truncate', title: text }, text));
    }
    function cell(r, c) {
      if (tree && (c === k.channel || c === k.campaign || c === k.adGroup)) return hierCell(r, c);
      var v = String(r[c] == null ? '' : r[c]), s = suffix(c);
      if (v.indexOf('\n') < 0) return withSuffix(v, s);
      var parts = v.split('\n'), first = parts.shift() || '', delta = parseDelta(parts.join(' '));
      return h('span', { className: 'sec-vc' }, h('span', null, withSuffix(first.trim(), s)),
        parts.join(' ').trim() ? h('span', { className: 'sec-vc-delta ' + (delta.direction === 'up' ? 'is-up' : delta.direction === 'down' ? 'is-down' : '') }, delta.marked) : null);
    }
    function render() {
      clear(root);
      var q = st.q.trim().toLowerCase();
      var base = channelSelect && st.channel ? rows.filter(function (r) { return trimS(r[chKey]) === st.channel; }) : rows;
      var nodes = tree ? buildTree(base, cols, k) : [];
      var fnodes = tree && q ? filterTree(nodes, cols, q) : nodes;
      var flat = [];
      if (!tree) {
        flat = q ? base.filter(function (r) { return rowHas(r, cols, q); }) : base;
        if (st.sort) {
          var first = function (x) { return String(x == null ? '' : x).split('\n')[0]; };
          flat = flat.map(function (r, i) { return { r: r, i: i }; }).sort(function (a, b) { return cmp(first(a.r[st.sort.key]), first(b.r[st.sort.key]), st.sort.dir) || a.i - b.i; }).map(function (x) { return x.r; });
        }
      }
      var count = tree ? (q ? nodes.filter(function (n) { return nodeHas(n, cols, q); }).length : nodes.length) : flat.length;
      var paged = paginate0 && (!chanTable || count > st.size);
      var pages = Math.max(1, Math.ceil(count / st.size)), page = Math.min(st.page, pages), off = (page - 1) * st.size;
      var view = tree ? flatten(paged ? fnodes.slice(off, off + st.size) : fnodes, st.open, !!q) : (paged ? flat.slice(off, off + st.size) : flat);

      var bar = h('div', { className: 'sec-toolbar' });
      if (channelSelect) {
        var opts = []; rows.forEach(function (r) { var v = trimS(r[chKey]); if (v && opts.indexOf(v) < 0) opts.push(v); });
        opts = opts.map(function (v) { return { value: v, label: CHANNEL_CODE_LABEL[v] || v }; }).sort(function (a, b) { return a.label.localeCompare(b.label, undefined, { numeric: true, sensitivity: 'base' }); });
        var sel = h('select', { className: 'select select-sm', style: { width: '180px' }, 'aria-label': CH_DEFAULT, onChange: function (ev) { st.channel = ev.target.value; st.page = 1; render(); } },
          h('option', { value: '' }, ALL), opts.map(function (o) { return h('option', { value: o.value }, o.label); }));
        sel.value = st.channel; bar.appendChild(sel);
      }
      var input = h('input', { className: 'input input-sm input-search', style: { width: '200px' }, placeholder: T.search, 'aria-label': T.tableSearch, value: st.q });
      input.addEventListener('input', function (ev) { st.q = ev.target.value; st.page = 1; var pos = ev.target.selectionStart; render(); var ni = root.querySelector('.input-search'); if (ni) { ni.focus(); try { ni.setSelectionRange(pos, pos); } catch (x) { } } });
      bar.appendChild(input);
      if (!isFullTree && paged) {
        var ps = h('select', { className: 'select select-sm', style: { width: '84px' }, 'aria-label': T.rowsPerPage, onChange: function (ev) { st.size = Number(ev.target.value); st.page = 1; render(); } },
          PAGE_SIZES.map(function (n) { return h('option', { value: n }, T.nRows(n)); }));
        ps.value = String(st.size); bar.appendChild(ps);
      }
      if (isFullTree) bar.appendChild(h('button', { type: 'button', className: 'btn btn-ghost btn-icon btn-sm', 'aria-label': T.collapseAll, title: T.collapseAll, onClick: function () { st.open = new Set(); render(); } }, icon('refresh')));
      root.appendChild(bar);

      var onSort = function (key) { st.sort = nextSort(st.sort, key); st.page = 1; render(); };
      var table = h('table', { className: 'data-table table-dense sec-table' },
        h('thead', null, h('tr', null, shown.map(function (c) { return tree ? h('th', { className: numClass(c) }, head(c)) : SortTh(head(c), c, st.sort, onSort, numClass(c)); }))),
        h('tbody', null, view.length ? view.map(function (r) {
          return h('tr', { className: tree && (r._depth || 1) > 1 ? 'sec-subrow' : undefined }, shown.map(function (c) { return h('td', { className: numClass(c) }, cell(r, c)); }));
        }) : h('tr', null, h('td', { colSpan: shown.length }, Empty(T.noResult)))));
      root.appendChild(h('div', { className: 'table-wrap', style: tree && paged ? { maxHeight: '520px', overflow: 'auto' } : { overflowX: 'auto' } }, table));
      if (paged && pages > 1) root.appendChild(h('div', { className: 'row', style: { justifyContent: 'center' } }, Pager(page, pages, function (p) { st.page = p; render(); })));
      if (e.description) root.appendChild(h('p', { className: 'hint' }, e.description));
    }
    render();
    return root;
  }

  // ───────────────────────────── calendar (ot) ─────────────────────────────
  var parseYmd = function (e) { var t = /^(\d{4})-(\d{2})-(\d{2})/.exec(e || ''); return t ? new Date(+t[1], t[2] - 1, +t[3]) : null; };
  var ymd = function (d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
  var dayDiff = function (a, b) { return Math.round((b.getTime() - a.getTime()) / 864e5); };
  var isHoliday = function (e) { var t = String(e.type == null ? '' : e.type).trim().toUpperCase(); return t === 'HOLIDAY' || t === 'HOLYDAY'; };
  var rangeText = function (e) { var a = parseYmd(e.start_date), b = parseYmd(e.end_date); if (!a || !b) return '-'; var f = function (d) { return (d.getMonth() + 1) + '/' + d.getDate(); }; return dayDiff(a, b) === 0 ? f(a) : f(a) + '~' + f(b); };
  function Calendar(s, ctx) {
    var a = parseYmd(s.start_date), b = parseYmd(s.end_date);
    if (!a || !b) return h('p', { className: 't-sm fg-3' }, T.calUnavailable);
    if (b < a) { var tmp = a; a = b; b = tmp; }
    var promos = ctx.promotionItems;
    var evs = (s.events || []).filter(isHoliday).concat(promos || (s.events || []).filter(function (x) { return !isHoliday(x); }))
      .reduce(function (acc, e) {
        var n = parseYmd(e.start_date), r = parseYmd(e.end_date);
        if (!n || !r) return acc;
        var nm = String(e.name == null ? '' : e.name).trim() || T.schedule;
        acc.push(r < n ? Object.assign({}, e, { name: nm, start_date: ymd(r), end_date: ymd(n) }) : Object.assign({}, e, { name: nm }));
        return acc;
      }, []).sort(function (x, y) { return parseYmd(x.start_date) - parseYmd(y.start_date) || parseYmd(x.end_date) - parseYmd(y.end_date); });
    var days = [];
    for (var d = new Date(a); d <= b; d.setDate(d.getDate() + 1)) {
      var key = ymd(d), hol = evs.find(function (e) { return isHoliday(e) && e.start_date <= key && key <= e.end_date; }) || null;
      days.push({ key: key, label: d.getDate() + '(' + T.weekday[d.getDay()] + ')', sun: d.getDay() === 0, sat: d.getDay() === 6, holiday: hol });
    }
    var lanes = [], bars = [];
    evs.filter(function (e) { return !isHoliday(e); }).forEach(function (e, i) {
      var n = parseYmd(e.start_date), r = parseYmd(e.end_date);
      if (r < a || n > b) return;
      var s0 = n < a ? a : n, e0 = r > b ? b : r, col = dayDiff(a, s0) + 1, span = dayDiff(s0, e0) + 1;
      var lane = lanes.findIndex(function (x) { return x < col; });
      if (lane === -1) { lane = lanes.length; lanes.push(col + span - 1); } else lanes[lane] = col + span - 1;
      bars.push({ ev: e, col: col, span: span, lane: lane, range: rangeText(e) });
    });
    var nLanes = Math.max.apply(null, [1].concat(bars.map(function (x) { return x.lane + 1; })));
    var gcols = 'repeat(' + Math.max(days.length, 1) + ', minmax(0, 1fr))';
    var isComp = function (e) { return e.promotion_type === 'competitor'; };
    var tip = null;
    function showTip(x, y, ev) {
      hideTip();
      tip = h('div', { className: 'sec-cal-tip', role: 'tooltip', style: { left: (x + 14) + 'px', top: (y + 14) + 'px' } },
        h('p', { className: 'font-bold' }, T.promoInfo),
        isComp(ev) && ev.competitor_name ? h('p', null, '경쟁사명: ' + ev.competitor_name) : null,
        ev.owner_name ? h('p', null, '담당자: ' + ev.owner_name) : null,
        h('p', { className: 'fg-2' }, ev.description || '-'));
      document.body.appendChild(tip);
    }
    function hideTip() { if (tip && tip.parentNode) tip.parentNode.removeChild(tip); tip = null; }
    function openModal(ev) {
      var close = function () { if (m.parentNode) m.parentNode.removeChild(m); };
      var dl = h('dl', { className: 'dl' },
        h('dt', null, T.periodLabel), h('dd', null, ev.start_date, ' ~ ', ev.end_date),
        isComp(ev) && ev.competitor_name ? [h('dt', null, T.competitorName), h('dd', null, ev.competitor_name)] : null,
        ev.owner_name ? [h('dt', null, T.owner), h('dd', null, ev.owner_name)] : null,
        ev.sales_channel ? [h('dt', null, T.salesChannel), h('dd', null, SALES_CHANNEL[ev.sales_channel] || ev.sales_channel)] : null,
        ev.link ? [h('dt', null, T.link), h('dd', null, h('a', { className: 'btn-link', href: ev.link, target: '_blank', rel: 'noopener noreferrer' }, ev.link))] : null,
        h('dt', null, T.detail), h('dd', { style: { whiteSpace: 'pre-wrap' } }, ev.description || '-'));
      var m = Modal(h('div', { className: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'sec-cal-title' },
        h('div', { className: 'modal-head' },
          h('div', { className: 'row gap-2' }, h('span', { className: 'sec-cal-dot', style: { background: ev.color || 'var(--blue-500)' } }), h('h2', { id: 'sec-cal-title' }, ev.name),
            isComp(ev) ? h('span', { className: 'badge badge-warning' }, T.competitor) : null),
          h('button', { type: 'button', className: 'btn btn-ghost btn-sm btn-icon', 'aria-label': T.close, onClick: function () { close(); } }, icon('x'))),
        h('div', { className: 'modal-body' }, dl),
        h('div', { className: 'modal-foot' }, h('button', { type: 'button', className: 'btn btn-secondary', onClick: function () { close(); } }, T.close))), close);
      document.body.appendChild(m);
    }
    return h('div', { className: 'sec-cal', style: { '--cal-days': String(days.length) } },
        h('div', { className: 'sec-cal-head', style: { gridTemplateColumns: gcols } }, days.map(function (x) {
          return h('div', { className: 'sec-cal-hcell ' + (x.holiday || x.sun ? 'is-accent' : '') + ' ' + (x.sat ? 'is-sat' : '') },
            h('span', null, x.label), x.holiday ? h('span', { className: 'sec-cal-holiday' }, x.holiday.name) : null);
        })),
        h('div', { className: 'sec-cal-body', style: { gridTemplateColumns: gcols, gridTemplateRows: 'repeat(' + nLanes + ', 76px)' } },
          days.map(function (x, i) { return h('div', { className: 'sec-cal-cell', style: { gridColumn: String(i + 1), gridRow: '1 / span ' + nLanes } }); }),
          bars.map(function (x) {
            var st = { gridColumn: x.col + ' / span ' + x.span, gridRow: String(x.lane + 1) };
            if (x.ev.color) { st.borderLeftColor = x.ev.color; st.borderLeftWidth = '4px'; }
            return h('button', {
              type: 'button', className: 'sec-cal-ev ' + (isComp(x.ev) ? 'is-competitor' : ''), style: st,
              onMouseenter: function (ev) { showTip(ev.clientX, ev.clientY, x.ev); },
              onMousemove: function (ev) { if (tip) { tip.style.left = (ev.clientX + 14) + 'px'; tip.style.top = (ev.clientY + 14) + 'px'; } },
              onMouseleave: hideTip, onBlur: hideTip,
              onClick: function () { hideTip(); openModal(x.ev); }
            }, h('strong', { className: 'truncate' }, x.ev.name), h('span', null, x.range));
          })));
  }

  // ───────────────────────────── charts (Chart.js presets) ─────────────────────────────
  var chartsReady = false;
  function chartSetup() {
    if (chartsReady || !window.Chart) return;
    chartsReady = true;
    Chart.defaults.font.family = cssVar('--font-body');
    Chart.defaults.color = cssVar('--fg-secondary');
  }
  var customBackground = {
    id: 'customBackground',
    beforeDraw: function (chart, args, opts) {
      var ctx = chart.ctx, a = chart.chartArea;
      if (!a) return;
      ctx.save(); ctx.fillStyle = (opts && opts.color) || cssVar('--ink-50'); ctx.fillRect(a.left, a.top, a.width, a.height); ctx.restore();
    }
  };
  function legendVarsPlugin(id, el, wVar, lVar) {
    return { id: id, afterLayout: function (chart) { var a = chart.chartArea; if (el && a) { el.style.setProperty(wVar, (a.right - a.left) + 'px'); el.style.setProperty(lVar, a.left + 'px'); } } };
  }
  function mountChart(canvasHost, config) {
    var canvas = h('canvas', { role: 'img' });
    canvasHost.appendChild(canvas);
    var chart = null;
    onMount(function () { chartSetup(); chart = new Chart(canvas, config); canvasHost.__chart = chart; });
    return function () { return chart; };
  }
  var DOW = ['일', '월', '화', '수', '목', '금', '토'];
  var parseLoose = function (e) {
    var t = /^(\d{4})[-/]?(\d{1,2})?[-/]?(\d{0,2})[Tt\s]*(\d{1,2})?:?(\d{1,2})?:?(\d{1,2})?[.:]?(\d+)?$/.exec(e);
    var n = t && !/Z$/i.test(e) ? new Date(+t[1], (t[2] ? +t[2] : 1) - 1, t[3] ? +t[3] : 1, +(t[4] || 0), +(t[5] || 0), +(t[6] || 0)) : new Date(e);
    return Number.isNaN(n.getTime()) ? null : n;
  };
  var niceStep = function (e, fallback) { if (!Number.isFinite(e) || e <= 0) return fallback; var t = Math.pow(10, Math.floor(Math.log10(e))), n = e / t; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * t; };
  var niceStep2 = function (e) { if (!Number.isFinite(e) || e <= 0) return 1; var t = Math.pow(10, Math.floor(Math.log10(e))), n = e / t; return n <= 1 ? t : n <= 2 ? 2 * t : n <= 5 ? 5 * t : 10 * t; };
  var amountAxis = function (mx) { var t = Math.max(mx, 0); if (!t) return { step: 1, axisMax: 5 }; var n = t * 1.08, r = niceStep2(n / 4); return { step: r, axisMax: Math.ceil(n / r) * r }; };
  var pctAxis = function (mx) { var t = Math.max(mx, 0), n = t <= 200 ? 20 : 50; return { step: n, axisMax: Math.max(n * 4, Math.ceil(t * 1.08 / n) * n) }; };
  var seriesMax = function (list) { return list.length ? Math.max.apply(null, [0].concat(list.reduce(function (a, e) { return a.concat((e.items || []).map(function (x) { return x.y; })); }, []))) : 0; };
  var valuesAt = function (s, labels) { var m = new Map((s.items || []).map(function (x) { return [x.x, x.y]; })); return labels.map(function (l) { return m.has(l) ? m.get(l) : null; }); };

  function normChart(e) {
    var src = Array.isArray(e.chartSeries) ? e.chartSeries : Array.isArray(e.chart_series) ? e.chart_series : Array.isArray(e.chart_components) ? e.chart_components : [];
    var series = src.filter(function (x) { return x && typeof x === 'object'; }).map(function (x) {
      return {
        name: typeof x.name === 'string' ? x.name : '', label: typeof x.label === 'string' ? x.label : (typeof x.name === 'string' ? x.name : ''),
        unit: typeof x.unit === 'string' ? x.unit : '',
        items: (Array.isArray(x.items) ? x.items : []).filter(function (p) { return p && typeof p === 'object'; }).map(function (p) { var y = typeof p.y === 'number' ? p.y : Number(p.y); return { x: String(p.x == null ? '' : p.x), y: Number.isFinite(y) ? y : 0 }; }).filter(function (p) { return p.x.length > 0; })
      };
    }).filter(function (x) { return x.items.length > 0; });
    return series.length ? { name: typeof e.name === 'string' ? e.name : '', chart_series: series, slot_key: e.slot_key } : null;
  }

  // daily_performance (Wr) — 최근 7일 일별 광고 성과
  var DP_BAR = ['#739FE2', '#8D96A0', '#8CCDB9', '#F4C77F', '#9F9CF1'], DP_LINE = ['#EF7A68', '#6AC7D6'];
  var DP_COLOR = { sales: '#8D96A0', adCost: '#739FE2' }, DP_HOVER = { sales: '#3C4650', adCost: '#4583E1' };
  var DP_KEYS = ['sales', 'adCost', 'roas', 'ctr'], DP_LABEL = { sales: T.sales, adCost: T.adCost, roas: T.roas, ctr: T.ctr };
  var lbl = function (e) { return (e.name + ' ' + e.label).trim().toLowerCase(); };
  var dpIsLine = function (e) { return e.unit === 'PERCENT' || e.unit === '%' || (e.name + ' ' + e.label).toLowerCase().indexOf('roas') >= 0; };
  var dpKey = function (e) { var t = lbl(e); return t.indexOf('클릭률') >= 0 || t.indexOf('ctr') >= 0 ? 'ctr' : e.unit === '%' || t.indexOf('roas') >= 0 ? 'roas' : t.indexOf('매출') >= 0 || t.indexOf('sales') >= 0 ? 'sales' : t.indexOf('광고비') >= 0 || t.indexOf('광고 비용') >= 0 || t.indexOf('ad cost') >= 0 || t.indexOf('ad spend') >= 0 ? 'adCost' : null; };
  var dpLabel = function (e) { var k = dpKey(e); return k ? DP_LABEL[k] : (e.label || e.name); };
  var dpAxis = function (mx, fb) { var n = Math.max(mx, 0); if (!n) return fb; var r = n * 1.02, i = niceStep(r / 5, 1e6); return { step: i, axisMax: Math.ceil(r / i) * i }; };
  function DailyPerformance(c, ctx) {
    var series = c.chart_series, hidden = new Set();
    var labels = (function () {
      var xs = []; series.forEach(function (s) { s.items.forEach(function (p) { if (xs.indexOf(p.x) < 0) xs.push(p.x); }); });
      var ds = xs.map(parseLoose);
      return ds.every(Boolean) ? xs.map(function (x, i) { return { label: x, at: ds[i].getTime() }; }).sort(function (a, b) { return a.at - b.at; }).map(function (x) { return x.label; }) : xs;
    })();
    var monthly = labels.length > 0 && labels.every(function (x) { return /^\d{4}-\d{2}$/.test(x); });
    var bars = series.filter(function (s) { return !dpIsLine(s); }), lines = series.filter(dpIsLine);
    var krw = bars.some(function (s) { return s.unit === 'KRW'; });
    var g = seriesMax(bars), ax = dpAxis(g, { step: 100, axisMax: 500 }), px = dpAxis(seriesMax(lines), { step: 20, axisMax: 80 });
    var keys = new Set(series.map(dpKey).filter(Boolean)), legendKeys = DP_KEYS.filter(function (k) { return keys.has(k); });
    var bi = 0, li = 0;
    var datasets = series.map(function (s, idx) {
      var k = dpKey(s);
      if (!dpIsLine(s)) {
        var col = DP_BAR[bi++ % DP_BAR.length], kk = k === 'sales' || k === 'adCost' ? k : null;
        return { type: 'bar', label: dpLabel(s), data: valuesAt(s, labels), yAxisID: 'yAmount', hidden: false, _key: k, backgroundColor: kk ? DP_COLOR[kk] : col, hoverBackgroundColor: kk ? DP_HOVER[kk] : col, borderRadius: { topLeft: 3, topRight: 3, bottomLeft: 0, bottomRight: 0 }, borderSkipped: false, order: 10, categoryPercentage: 0.72, barPercentage: 0.82 };
      }
      var lc = DP_LINE[li++ % DP_LINE.length];
      return { type: 'line', label: dpLabel(s), data: valuesAt(s, labels), yAxisID: 'yPercent', hidden: false, _key: k, borderColor: lc, backgroundColor: lc, tension: 0.35, borderWidth: 2, pointRadius: 5, pointHoverRadius: 6, pointBackgroundColor: lc, pointBorderColor: lc, order: idx };
    });
    var tick = function (v) {
      var n = String(v == null ? '' : v), d = parseLoose(n);
      if (!d) return n;
      return /^\d{4}-\d{2}$/.test(n) ? [T.month(d.getMonth() + 1), T.year(d.getFullYear())] : (d.getMonth() + 1) + '/' + d.getDate() + '(' + DOW[d.getDay()] + ')';
    };
    var amt = function (v) { var t = Number(v); if (!Number.isFinite(t)) return String(v); if (t === 0) return '₩0'; if (g < 1e6) return '₩' + t.toLocaleString(); var n = t / 1e6; return '₩' + (Number.isInteger(n) ? n : n.toFixed(1)) + 'M'; };
    var wrap = h('div', { className: 'dpc-wrap' });
    var legend = h('div', { className: 'dpc-legend', role: 'group', 'aria-label': T.legendGroup });
    var canvasHost = h('div', { className: 'dpc-canvas' });
    wrap.appendChild(legend); wrap.appendChild(canvasHost);
    var getChart;
    function drawLegend() {
      clear(legend);
      legendKeys.forEach(function (k) {
        legend.appendChild(h('button', { type: 'button', className: hidden.has(k) ? 'is-off' : undefined, 'aria-pressed': String(!hidden.has(k)), onClick: function () { if (hidden.has(k)) hidden.delete(k); else hidden.add(k); drawLegend(); var ch = getChart(); if (ch) { ch.data.datasets.forEach(function (ds) { ds.hidden = !!ds._key && hidden.has(ds._key); }); ch.update(); } } },
          h('span', { className: 'dpc-swatch dpc-swatch-' + (k === 'roas' || k === 'ctr' ? 'dot' : 'bar'), style: { backgroundColor: k === 'roas' || k === 'ctr' ? DP_LINE[0] : DP_COLOR[k] } }),
          h('span', null, DP_LABEL[k])));
      });
    }
    drawLegend();
    var font = { family: cssVar('--font-body'), size: 12, weight: 500, lineHeight: '18px' };
    getChart = mountChart(canvasHost, {
      type: 'bar', data: { labels: labels, datasets: datasets }, plugins: [legendVarsPlugin('dailyPerformanceChartLegendBoxMetrics', wrap, '--dpc-legend-width', '--dpc-legend-left')],
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { display: false }, border: { display: true, color: cssVar('--border-strong') }, ticks: { color: cssVar('--fg-secondary'), maxRotation: 0, autoSkip: false, padding: 8, callback: function (v, i) { return tick(labels[i]); }, font: { family: cssVar('--font-body'), size: 13, weight: 600 } } },
          yAmount: { type: 'linear', position: 'left', beginAtZero: true, max: ax.axisMax, ticks: { padding: 10, stepSize: ax.step, color: cssVar('--fg-secondary'), callback: amt, font: font }, grid: { color: cssVar('--border-subtle'), drawTicks: false }, border: { display: false } },
          yPercent: { type: 'linear', position: 'right', beginAtZero: true, max: px.axisMax, ticks: { padding: 10, stepSize: px.step, color: cssVar('--fg-secondary'), callback: function (v) { return Number(v).toLocaleString() + '%'; }, font: font }, grid: { drawOnChartArea: false, drawTicks: false }, border: { display: false } }
        },
        plugins: {
          legend: { display: false }, datalabels: { display: false },
          tooltip: { padding: 12, bodySpacing: 6, boxPadding: 4, caretPadding: 8, cornerRadius: 8, displayColors: true, titleMarginBottom: 8,
            callbacks: { label: function (e) { var t = e.dataset.label || '', n = Number(e.parsed.y || 0), r = e.dataset.yAxisID; return r === 'yPercent' ? t + ': ' + n.toLocaleString() + '%' : r === 'yAmount' ? t + ': ' + (krw ? '₩' : '') + n.toLocaleString() : t + ': ' + n.toLocaleString(); } } }
        }
      }
    });
    var cal = labels.length && !monthly ? Calendar({ type: 'calendar', name: T.promoInfo, slot_key: '', start_date: String(labels[0]), end_date: String(labels[labels.length - 1]), events: [] }, ctx) : null;
    return h('div', { className: 'stack gap-4' }, wrap, cal);
  }

  // performance (Yi) — MTD 월별 광고 성과
  var PERF_COLOR = { adBar: 'rgb(115, 159, 226)', salesBar: '#8d96a0', roas: 'rgb(239, 122, 104)' };
  var nl = function (e) { return (e.name + ' ' + e.label).toLowerCase(); };
  var pIsRoas = function (e) { return e.unit === '%' || nl(e).indexOf('roas') >= 0; };
  var pIsCost = function (e) { var t = nl(e); return t.indexOf('광고비') >= 0 || t.indexOf('cost') >= 0 || t.indexOf('ad spend') >= 0 || t.indexOf('ad cost') >= 0; };
  var pIsRev = function (e) { var t = nl(e); return t.indexOf('매출') >= 0 || t.indexOf('revenue') >= 0; };
  var pLabel = function (e) { return pIsCost(e) ? (e.unit === '$' || nl(e).indexOf('cost') >= 0 ? 'Cost' : T.adCost) : pIsRev(e) ? (e.unit === '$' || nl(e).indexOf('revenue') >= 0 ? 'Revenue' : T.sales) : (e.label || e.name); };
  var COMPACT = ['최근 7일 일별 광고 성과', '일별 광고 성과', 'Sales campaign: Daily performance in the last 7 days'];
  function Performance(c) {
    var series = c.chart_series, hidden = new Set();
    var labels = ((series.find(function (s) { return s.items.length > 0; }) || {}).items || []).map(function (p) { return p.x; });
    var roas = series.find(pIsRoas) || null, others = series.filter(function (s) { return s !== roas; });
    var cur = others.some(function (s) { return s.unit === '$'; }) ? '$' : others.some(function (s) { return s.unit === 'KRW' || s.unit === '₩'; }) ? 'KRW' : null;
    var prefix = cur === '$' ? '$' : cur === 'KRW' ? '₩' : '';
    var maxBar = seriesMax(others), compact = COMPACT.indexOf(c.name || '') >= 0;
    var amount = amountAxis(maxBar), percent = pctAxis(roas ? seriesMax([roas]) : 0);
    var font = cssVar('--font-body'), fg = cssVar('--fg-secondary');
    var datasets = series.map(function (s, t) {
      return s === roas ? { type: 'line', label: 'ROAS', data: valuesAt(s, labels), yAxisID: 'yPercent', borderColor: PERF_COLOR.roas, backgroundColor: PERF_COLOR.roas, tension: 0.35, borderWidth: 3, pointRadius: 5, pointHoverRadius: 6, pointBackgroundColor: PERF_COLOR.roas, pointBorderColor: PERF_COLOR.roas, order: 0, hidden: false }
        : { type: 'bar', label: pLabel(s), data: valuesAt(s, labels), yAxisID: 'yAmount', backgroundColor: pIsCost(s) ? PERF_COLOR.adBar : pIsRev(s) ? PERF_COLOR.salesBar : PERF_COLOR.adBar, borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 }, borderSkipped: false, order: 10, categoryPercentage: 0.72, barPercentage: 0.82, hidden: false };
    });
    var dateTick = function (v) { var n = String(v == null ? '' : v); if (!compact) return n; var t = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(n.trim()), d = t ? new Date(+t[1], +t[2] - 1, +t[3]) : new Date(n); return Number.isNaN(d.getTime()) ? n : (d.getMonth() + 1) + '/' + d.getDate() + '(' + DOW[d.getDay()] + ')'; };
    var amt = function (v) { var i = Number(v); if (!Number.isFinite(i)) return String(v); if (!compact || maxBar < 1e6) return prefix + i.toLocaleString(); var a = i / 1e6; return prefix + (Number.isInteger(a) ? a : a.toFixed(1)) + 'M'; };
    var wrap = h('div', { className: 'perf-chart' });
    var legend = h('div', { className: 'perf-chart-legend', role: 'group', 'aria-label': T.legendGroup });
    var host = h('div', { className: 'perf-chart-canvas' });
    wrap.appendChild(legend); wrap.appendChild(host);
    var getChart;
    function drawLegend() {
      clear(legend);
      series.forEach(function (s, t) {
        var key = s === roas ? 'roas' : pIsCost(s) ? 'adBar' : pIsRev(s) ? 'salesBar' : 'adBar';
        legend.appendChild(h('button', { type: 'button', className: hidden.has(t) ? 'is-off' : undefined, 'aria-pressed': String(!hidden.has(t)), onClick: function () { if (hidden.has(t)) hidden.delete(t); else hidden.add(t); drawLegend(); var ch = getChart(); if (ch) { ch.data.datasets.forEach(function (ds, i) { ds.hidden = hidden.has(i); }); ch.update(); } } },
          h('span', { className: 'perf-chart-swatch ' + (key === 'roas' ? 'is-dot' : 'is-bar'), style: { backgroundColor: PERF_COLOR[key] } }), s === roas ? 'ROAS' : pLabel(s)));
      });
    }
    drawLegend();
    getChart = mountChart(host, {
      type: 'bar', data: { labels: labels, datasets: datasets }, plugins: [legendVarsPlugin('performanceChartLegendBoxMetrics', wrap, '--perf-legend-width', '--perf-legend-offset')],
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { display: false }, border: { display: true, color: cssVar('--border-strong') }, ticks: { color: fg, maxRotation: 0, autoSkip: false, padding: 8, callback: function (v, i) { return dateTick(labels[i]); }, font: { family: font, size: compact ? 13 : 16, weight: 600 } } },
          yAmount: { type: 'linear', position: 'left', beginAtZero: true, max: amount.axisMax, ticks: { padding: 10, stepSize: amount.step, color: fg, callback: amt, font: { family: font, size: 14, weight: 500 } }, grid: { color: cssVar('--border-subtle'), drawTicks: false }, border: { display: false } },
          yPercent: { type: 'linear', position: 'right', beginAtZero: true, max: percent.axisMax, ticks: { padding: 10, stepSize: percent.step, color: fg, callback: function (v) { return Number(v).toLocaleString() + '%'; }, font: { family: font, size: 14, weight: 500 } }, grid: { drawOnChartArea: false, drawTicks: false }, border: { display: false } }
        },
        plugins: {
          legend: { display: false }, datalabels: { display: false },
          tooltip: { padding: 12, bodySpacing: 6, boxPadding: 4, caretPadding: 8, cornerRadius: 8, displayColors: true, titleMarginBottom: 8, titleFont: { family: font, size: 16, weight: 600 }, bodyFont: { family: font, size: 16, weight: 700 },
            callbacks: { label: function (e) { var t = e.dataset.label || '', n = Number(e.parsed.y || 0), r = e.dataset.yAxisID; return r === 'yPercent' ? t + ': ' + n.toLocaleString() + '%' : r === 'yAmount' ? t + ': ' + prefix + n.toLocaleString() : t + ': ' + n.toLocaleString(); } } }
        }
      }
    });
    return wrap;
  }

  // monthly_performance (li) — 월 마감 월별 광고 성과
  var MP_COLORS = ['#739FE2', '#8D96A0', '#EF7A68', '#63C7A9', '#8B82EA'];
  var mpIsLine = function (e) { if (e.unit === 'PERCENT') return true; var t = lbl(e); return e.unit === '%' || t.indexOf('roas') >= 0 || t.indexOf('cpm') >= 0 || t.indexOf('conversion rate') >= 0; };
  var mpCost = function (e) { var t = lbl(e); return t.indexOf('광고비') >= 0 || t.indexOf('광고 비용') >= 0 || t.indexOf('ad cost') >= 0 || t.indexOf('ad spend') >= 0; };
  var mpRev = function (e) { var t = lbl(e); return t.indexOf('매출') >= 0 || t.indexOf('sales') >= 0 || t.indexOf('revenue') >= 0; };
  var mpClk = function (e) { var t = lbl(e); return t.indexOf('clicks') >= 0 || t.indexOf('클릭') >= 0; };
  var mpRatio = function (e) { var t = lbl(e); return t.indexOf('roas') >= 0 || t.indexOf('cpm') >= 0 || t.indexOf('conversion rate') >= 0; };
  var mpColor = function (e, i) { return mpCost(e) ? '#739FE2' : mpRev(e) || mpClk(e) ? '#8D96A0' : mpRatio(e) ? '#EF7A68' : MP_COLORS[i % MP_COLORS.length]; };
  var mpHover = function (e, c) { return mpRev(e) || mpClk(e) ? '#3C4650' : mpCost(e) ? '#4583E1' : c; };
  var mpLabel = function (e) { return mpCost(e) ? T.adCost : mpRev(e) ? T.sales : lbl(e).indexOf('roas') >= 0 ? 'ROAS' : (e.label || e.name); };
  function MonthlyPerformance(c) {
    var series = c.chart_series, hidden = new Set();
    var xs = []; series.forEach(function (s) { s.items.forEach(function (p) { if (xs.indexOf(p.x) < 0) xs.push(p.x); }); });
    var labels = xs.every(function (x) { return !Number.isNaN(Date.parse(x)); }) ? xs.slice().sort(function (a, b) { return Date.parse(a) - Date.parse(b); }) : xs;
    var lineS = series.filter(mpIsLine), barS = series.filter(function (s) { return !mpIsLine(s); });
    var hasBar = barS.length > 0, hasLine = lineS.length > 0, lu = (lineS[0] || {}).unit || '', isPct = lu === '%' || lu === 'PERCENT';
    var bp = barS.some(function (s) { return s.unit === '$'; }) ? '$' : barS.some(function (s) { return s.unit === 'KRW' || s.unit === '₩'; }) ? '₩' : '';
    var lp = lu === '$' ? '$' : lu === 'KRW' || lu === '₩' ? '₩' : '';
    var fa = function (v) { var t = Number(v); return Number.isFinite(t) ? bp + t.toLocaleString() : String(v); };
    var fl = function (v) { var t = Number(v); return Number.isFinite(t) ? (isPct ? t.toLocaleString() + '%' : lp + t.toLocaleString()) : String(v); };
    var ga = amountAxis(seriesMax(barS)), la = isPct ? pctAxis(seriesMax(lineS)) : amountAxis(seriesMax(lineS));
    var fg = cssVar('--fg-secondary'), font = cssVar('--font-body');
    var tickFont = { family: font, size: 14, weight: 500, lineHeight: '22px' };
    var datasets = series.map(function (s, t) {
      var col = mpColor(s, t);
      return mpIsLine(s) ? { type: 'line', label: mpLabel(s), data: valuesAt(s, labels), yAxisID: 'yPercent', borderColor: col, backgroundColor: col, tension: 0.35, borderWidth: 2, pointRadius: 5, pointHoverRadius: 6, pointBackgroundColor: col, pointBorderColor: col, order: 0, hidden: false }
        : { type: 'bar', label: mpLabel(s), data: valuesAt(s, labels), yAxisID: 'yAmount', backgroundColor: col, hoverBackgroundColor: mpHover(s, col), borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 }, borderSkipped: false, order: 10, categoryPercentage: 0.72, barPercentage: 0.82, hidden: false };
    });
    var mtick = function (n) { var t = /^(\d{4})-(\d{2})$/.exec(n); return t ? [T.month(Number(t[2])), T.year(t[1])] : n; };
    var wrap = h('div', { className: 'mpc-wrap' });
    var legend = h('div', { className: 'mpc-legend', role: 'group', 'aria-label': T.legendGroup });
    var host = h('div', { className: 'mpc-canvas' });
    wrap.appendChild(legend); wrap.appendChild(host);
    var getChart;
    function drawLegend() {
      clear(legend);
      series.forEach(function (s, t) {
        legend.appendChild(h('button', { type: 'button', className: hidden.has(t) ? 'is-off' : undefined, 'aria-pressed': String(!hidden.has(t)), onClick: function () { if (hidden.has(t)) hidden.delete(t); else hidden.add(t); drawLegend(); var ch = getChart(); if (ch) { ch.data.datasets.forEach(function (ds, i) { ds.hidden = hidden.has(i); }); ch.update(); } } },
          h('i', { className: mpIsLine(s) ? 'is-line' : 'is-bar', style: { background: mpColor(s, t) } }), mpLabel(s)));
      });
    }
    drawLegend();
    getChart = mountChart(host, {
      type: 'bar', data: { labels: labels, datasets: datasets }, plugins: [legendVarsPlugin('monthlyPerformanceLegendBox', wrap, '--mpc-legend-width', '--mpc-legend-left')],
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { display: false }, border: { display: true, color: cssVar('--border-strong') }, ticks: { color: fg, maxRotation: 0, autoSkip: false, padding: 8, callback: function (v, i) { return mtick(String(labels[i] == null ? '' : labels[i])); }, font: { family: font, size: 16, weight: 600, lineHeight: '24px' } } },
          yAmount: { type: 'linear', position: 'left', display: hasBar, beginAtZero: true, max: ga.axisMax, ticks: { padding: 10, color: fg, font: tickFont, stepSize: ga.step, callback: fa }, grid: { color: cssVar('--border-subtle'), drawTicks: false }, border: { display: false } },
          yPercent: { type: 'linear', position: hasBar ? 'right' : 'left', display: hasLine, beginAtZero: true, max: la.axisMax, ticks: { padding: 10, color: fg, font: tickFont, stepSize: la.step, callback: fl }, grid: { drawOnChartArea: !hasBar, drawTicks: false }, border: { display: false } }
        },
        plugins: {
          legend: { display: false }, datalabels: { display: false },
          tooltip: { padding: 12, bodySpacing: 6, boxPadding: 4, caretPadding: 8, cornerRadius: 8, displayColors: true, titleMarginBottom: 8,
            callbacks: { label: function (e) { return (e.dataset.label || '') + ': ' + (e.dataset.yAxisID === 'yPercent' ? fl(Number(e.parsed.y || 0)) : fa(Number(e.parsed.y || 0))); } } }
        }
      }
    });
    return wrap;
  }

  // category_sales_comparison (yr)
  var MONTH_ABBR = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  var monthKey = function (e) {
    var t = String(e == null ? '' : e).trim(), n = t.match(/^([A-Za-z]{3})\s+(\d{2,4})$/);
    if (n) { var m = MONTH_ABBR[(n[1] || '').toLowerCase()], y = Number(n[2] || ''); if (m && Number.isFinite(y)) { if (y < 100) y += 2000; return y * 12 + m; } }
    var r = t.match(/(\d{2,4})\D+(\d{1,2})/); if (!r) return null;
    var i = Number(r[1]), a = Number(r[2]); if (!Number.isFinite(i) || !Number.isFinite(a)) return null; if (i < 100) i += 2000; return i * 12 + a;
  };
  var monthCmp = function (a, b) { var n = monthKey(a), r = monthKey(b); return n != null && r != null && n !== r ? n - r : a.localeCompare(b, 'ko'); };
  var wrapLabel = function (e) {
    var t = String(e == null ? '' : e).trim(); if (!t) return [''];
    var out = [], cur = '';
    t.split(/(\s+|-)/).filter(Boolean).forEach(function (p) { var j = (cur + p).trim(); if (!cur || j.length <= 22) { cur = j; return; } out.push(cur); cur = p.trim(); });
    if (cur) out.push(cur);
    if (out.length <= 2) return out;
    var two = out.slice(0, 2), b = two[1] || ''; two[1] = b.length >= 22 ? b.slice(0, 21).trimEnd() + '…' : b + '…'; return two;
  };
  var LABEL_ANCHOR = '__label_anchor__';
  function CategoryComparison(c) {
    var rows = c.chart_series.map(function (s) {
      var it = (s.items || []).slice().sort(function (a, b) { return monthCmp(a.x, b.x); }), f = it[0], l = it[it.length - 1] || f;
      var p = Number(f ? f.y : 0), q = Number(l ? l.y : p);
      return { category: String(s.label || s.name || '-'), previousLabel: String(f ? f.x : '-'), currentLabel: String(l ? l.x : (f ? f.x : '-')), previous: p, current: q, changePercent: p === 0 ? 0 : (q - p) / p * 100 };
    });
    var all = []; rows.forEach(function (r) { [r.previousLabel, r.currentLabel].forEach(function (x) { if (x && all.indexOf(x) < 0) all.push(x); }); }); all.sort(monthCmp);
    var prevL = all[0] || T.prev, curL = all[all.length - 1] || prevL;
    var unitS = c.chart_series.find(function (s) { return s.unit; }), unit = String(unitS ? unitS.unit : '').trim();
    var mx = rows.length ? Math.max.apply(null, [0].concat(rows.map(function (r) { return Math.max(r.previous, r.current); }))) : 0;
    var axis = unit === '%' ? pctAxis(mx) : amountAxis(mx);
    var labels = rows.map(function (r) { return wrapLabel(r.category); });
    var extra = Math.min(18, Math.max(0, labels.reduce(function (a, l) { return Math.max(a, l.length); }, 1) - 1) * 9);
    var fmt = function (v) { var t = Number(v); return Number.isFinite(t) ? (unit === '%' ? t.toLocaleString() + '%' : unit === '$' ? '$' + t.toLocaleString() : unit === '₩' || unit === 'KRW' ? '₩' + t.toLocaleString() : unit ? t.toLocaleString() + unit : t.toLocaleString()) : String(v); };
    var font = cssVar('--font-body'), fg = cssVar('--fg-secondary'), fp = cssVar('--fg-primary');
    var common = { borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 }, borderSkipped: false, categoryPercentage: 0.72, barPercentage: 0.82, order: 10 };
    var hidden = new Set();
    var datasets = [
      Object.assign({ type: 'bar', label: prevL, data: rows.map(function (r) { return r.previous; }), backgroundColor: '#739fe2', hoverBackgroundColor: '#4583E1', hidden: false, _key: 'previous' }, common),
      Object.assign({ type: 'bar', label: curL, data: rows.map(function (r) { return r.current; }), backgroundColor: '#f49786', hoverBackgroundColor: '#D05B5B', hidden: false, _key: 'current' }, common),
      { type: 'line', label: LABEL_ANCHOR, data: rows.map(function (r) { return Math.max(r.previous, r.current); }), yAxisID: 'y', borderColor: 'rgba(0,0,0,0)', backgroundColor: 'rgba(0,0,0,0)', pointBackgroundColor: 'rgba(0,0,0,0)', pointBorderColor: 'rgba(0,0,0,0)', pointRadius: 0, pointHoverRadius: 0, borderWidth: 0, showLine: false, order: 0,
        datalabels: { anchor: 'end', align: 'top', offset: 8, color: function (e) { var t = rows[e.dataIndex] ? rows[e.dataIndex].changePercent : 0; return t > 0 ? '#4583E1' : t < 0 ? '#D05B5B' : fp; }, backgroundColor: '#ffffff', borderColor: '#D7DADF', borderWidth: 1, borderRadius: 4, padding: { top: 4, right: 8, bottom: 4, left: 8 }, font: { family: font, size: 16, weight: 700 },
          formatter: function (v, ctx) { var n = rows[ctx.dataIndex] ? rows[ctx.dataIndex].changePercent : 0, r = Number(Math.abs(n).toFixed(1)); return (n > 0 ? '+' : n < 0 ? '-' : '') + (Number.isInteger(r) ? String(r) : r.toFixed(1)) + '%'; }, clip: false, clamp: true } }
    ];
    var wrap = h('div', { className: 'csc-wrap', style: { height: (480 + extra) + 'px' } });
    var legend = h('div', { className: 'csc-legend', role: 'group', 'aria-label': T.legendGroup });
    var host = h('div', { className: 'csc-canvas' });
    wrap.appendChild(legend); wrap.appendChild(host);
    var getChart;
    var items = [{ key: 'previous', label: prevL, color: '#739fe2' }, { key: 'current', label: curL, color: '#f49786' }];
    function drawLegend() {
      clear(legend);
      items.forEach(function (it) {
        legend.appendChild(h('button', { type: 'button', className: hidden.has(it.key) ? 'is-off' : undefined, 'aria-pressed': String(!hidden.has(it.key)), onClick: function () { if (hidden.has(it.key)) hidden.delete(it.key); else hidden.add(it.key); drawLegend(); var ch = getChart(); if (ch) { ch.data.datasets.forEach(function (ds) { if (ds._key) ds.hidden = hidden.has(ds._key); }); ch.update(); } } },
          h('i', { style: { background: it.color } }), it.label));
      });
    }
    drawLegend();
    getChart = mountChart(host, {
      type: 'bar', data: { labels: labels, datasets: datasets }, plugins: [window.ChartDataLabels, legendVarsPlugin('categorySalesComparisonLegendMetrics', wrap, '--csc-legend-width', '--csc-legend-left')].filter(Boolean),
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', axis: 'x', intersect: false }, hover: { mode: 'index', axis: 'x', intersect: false },
        layout: { padding: { bottom: 6 + extra } },
        scales: {
          x: { grid: { display: false }, border: { display: true, color: cssVar('--border-strong') }, ticks: { color: fg, minRotation: 15, maxRotation: 15, autoSkip: false, font: { family: font, size: 16, weight: 600 } } },
          y: { beginAtZero: true, max: axis.axisMax, ticks: { padding: 10, stepSize: axis.step, color: fg, callback: fmt, font: { family: font, size: 14, weight: 500 } }, grid: { color: cssVar('--border-subtle'), drawTicks: false }, border: { display: false } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { padding: 12, bodySpacing: 6, boxPadding: 4, caretPadding: 8, cornerRadius: 8, displayColors: true, titleMarginBottom: 8, titleFont: { family: font, size: 16, weight: 600 }, bodyFont: { family: font, size: 16, weight: 700 },
            filter: function (e) { return !e.dataset || e.dataset.label !== LABEL_ANCHOR; },
            callbacks: { title: function (e) { var i = e[0] ? e[0].dataIndex : -1; return rows[i] ? rows[i].category : ''; }, label: function (e) { return (e.dataset ? e.dataset.label : '') + ': ' + fmt(Number(e.parsed ? e.parsed.y : 0)); } } },
          datalabels: { display: function (e) { return e.dataset && e.dataset.label === LABEL_ANCHOR; } }
        }
      }
    });
    return wrap;
  }

  // daily_category_sales (Er)
  var DCS = ['#739FE2', '#F49786', '#8CCDB9', '#F4C77F', '#9F9CF1', '#6AC7D6'];
  function DailyCategorySales(c) {
    var series = c.chart_series.filter(function (s) { return (s.label || '').trim().toLowerCase() !== 'promotion'; });
    var unit = (series[0] && series[0].unit ? series[0].unit.trim() : '') || '₩';
    var fmt = function (v) { return unit + Number(v == null ? 0 : v).toLocaleString(); };
    var nameOf = function (s) { return s.label || s.name; };
    var short = function (s) { return s.length > 7 ? s.slice(0, 7) + '...' : s; };
    var labels = (series[0] ? series[0].items : []).map(function (p) { return p.x; });
    var hidden = new Set();
    var datasets = series.map(function (s, n) { var m = new Map(s.items.map(function (p) { return [p.x, p.y]; })); var col = DCS[n % DCS.length] || '#739FE2'; return { label: nameOf(s), data: labels.map(function (l) { return m.has(l) ? m.get(l) : null; }), borderColor: col, backgroundColor: col, tension: 0.25, hidden: false }; });
    var wrap = h('div', { className: 'dcs-chart' });
    var legend = h('div', { className: 'dcs-legend', role: 'group', 'aria-label': T.legendGroup });
    var host = h('div', { className: 'dcs-canvas' });
    var tip = null;
    var showTip = function (label, btn) { hideTip(); var r = wrap.getBoundingClientRect(), a = btn.getBoundingClientRect(); tip = h('div', { className: 'dcs-legend-tip', style: { left: (a.left - r.left + a.width / 2) + 'px', top: (a.top - r.top - 8) + 'px' } }, label); wrap.insertBefore(tip, host); };
    var hideTip = function () { if (tip && tip.parentNode) tip.parentNode.removeChild(tip); tip = null; };
    wrap.appendChild(legend); wrap.appendChild(host);
    var getChart;
    function drawLegend() {
      clear(legend);
      series.forEach(function (s, t) {
        var b = h('button', { type: 'button', className: hidden.has(t) ? 'is-off' : undefined, 'aria-pressed': String(!hidden.has(t)), 'aria-label': nameOf(s),
          onClick: function () { if (hidden.has(t)) hidden.delete(t); else hidden.add(t); drawLegend(); var ch = getChart(); if (ch) { ch.data.datasets.forEach(function (ds, i) { ds.hidden = hidden.has(i); }); ch.update(); } } },
          h('i', { style: { background: DCS[t % DCS.length] || '#739FE2' } }), h('span', null, short(nameOf(s))));
        b.addEventListener('mouseenter', function () { showTip(nameOf(s), b); });
        b.addEventListener('mouseleave', hideTip); b.addEventListener('focus', function () { showTip(nameOf(s), b); }); b.addEventListener('blur', hideTip);
        legend.appendChild(b);
      });
    }
    drawLegend();
    var f = { size: 14, weight: 500 };
    getChart = mountChart(host, {
      type: 'line', data: { labels: labels, datasets: datasets }, plugins: [customBackground, legendVarsPlugin('dailyCategorySalesChartLegendBoxMetrics', wrap, '--dcs-legend-width', '--dcs-legend-offset-left')],
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12, font: f } }, y: { beginAtZero: true, ticks: { padding: 10, callback: fmt, font: f }, grid: { drawTicks: false } } },
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false }, datalabels: { display: false },
          tooltip: { padding: 12, bodySpacing: 6, boxPadding: 4, caretPadding: 8, cornerRadius: 8, displayColors: true, titleMarginBottom: 8, titleFont: { size: 16, weight: 600 }, bodyFont: { size: 16, weight: 700 }, callbacks: { label: function (e) { return e.dataset.label + ': ' + fmt(e.parsed.y); } } },
          customBackground: {} }
      }
    });
    return wrap;
  }

  // generic chart fallback (simple line chart)
  var GEN_COLORS = ['#739FE2', '#F49786', '#8CCDB9', '#F4C77F', '#9F9CF1', '#6AC7D6'];
  function GenericChart(c) {
    var labels = (c.chart_series[0] ? c.chart_series[0].items : []).map(function (p) { return p.x; });
    var unit = (c.chart_series[0] || {}).unit || '';
    var host = h('div', { style: { height: '360px', width: '100%' } });
    mountChart(host, {
      type: 'line', data: { labels: labels, datasets: c.chart_series.map(function (s, i) { var col = GEN_COLORS[i % GEN_COLORS.length]; return { label: s.label || s.name, data: valuesAt(s, labels), borderColor: col, backgroundColor: col, tension: 0.25 }; }) },
      plugins: [customBackground],
      options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12 } }, y: { beginAtZero: true, ticks: { padding: 10, callback: function (v) { return unit === 'KRW' ? '₩' + Number(v).toLocaleString() : Number(v).toLocaleString() + (unit === '%' ? '%' : ''); } }, grid: { drawTicks: false, color: cssVar('--border-subtle') } } },
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, color: cssVar('--fg-primary'), boxWidth: 32, boxHeight: 10, padding: 20 } }, datalabels: { display: false }, customBackground: {} } }
    });
    return host;
  }

  // chart preset resolution (Di / ki / Oi)
  var DAILY_CAT = ['일일 카테고리별 매출 현황', 'Daily Revenue in DTC'];
  var PERF_NAMES = ['월별 광고 성과', '최근 7일 일별 광고 성과', '일별 광고 성과', 'Sales campaign: Month-over-Month performance', 'Sales campaign: Daily performance in the last 7 days', 'Branding campaign: Month-over-Month performance'];
  var SKU_REV = ['Month-over-month Revenue by top 5 SKU and others'], SKU_CVR = ['Month-over-month Conversion rate by top 5 SKU(Product detail page > purchase)'];
  var CAT_CMP = '카테고리별 매출액 비교', TREND_SLOT = 'elt.chart.trend';
  var isChartType = function (e) { return e === 'chart' || e === 'Chart' || e === 'chart_component_group'; };
  function presetOf(e, reportType) {
    var n = typeof e.type === 'string' ? e.type : '', r = typeof e.name === 'string' ? e.name : '', monthly = reportType === 'monthly';
    if (isChartType(n)) {
      var a = normChart(e); if (!a) return null;
      var o = n !== 'Chart';
      if (o && (r === CAT_CMP || SKU_REV.indexOf(r) >= 0 || SKU_CVR.indexOf(r) >= 0)) return { kind: 'category_sales_comparison', chart: a };
      if (o && DAILY_CAT.indexOf(r) >= 0) return { kind: 'daily_category_sales', chart: a };
      if (a.slot_key === TREND_SLOT) return { kind: 'daily_performance', chart: a, title: (a.name || '').trim() || '최근 7일 광고 성과' };
      if (o && PERF_NAMES.indexOf(r) >= 0) return reportType === 'daily' ? { kind: 'daily_performance', chart: a, title: '최근 7일 광고 성과' } : { kind: monthly ? 'monthly_performance' : 'performance', chart: a };
      return { kind: 'generic', chart: a };
    }
    if (n === 'component_group' && monthly && PERF_NAMES.indexOf(r) >= 0 && e.slot_key !== 'elt.trend_section') {
      var comps = (Array.isArray(e.components) ? e.components : []).filter(function (x) { return x && typeof x === 'object'; });
      if (comps.length !== 1) return null;
      var c0 = normChart(comps[0]);
      return c0 ? { kind: 'monthly_performance', chart: Object.assign({}, c0, { name: r }) } : null;
    }
    return null;
  }
  function presetInGroup(e) {
    var t = typeof e.type === 'string' ? e.type : '';
    if (t !== 'chart' && t !== 'Chart') return null;
    var n = normChart(e); if (!n) return null;
    var r = n.name || '';
    if (PERF_NAMES.indexOf(r) >= 0) return { kind: COMPACT.indexOf(r) >= 0 ? 'daily_performance' : 'performance', chart: n };
    if (DAILY_CAT.indexOf(r) >= 0) return { kind: 'daily_category_sales', chart: n };
    return { kind: 'generic', chart: n };
  }
  function renderPreset(p, ctx) {
    switch (p.kind) {
      case 'daily_performance': return DailyPerformance(p.chart, ctx);
      case 'monthly_performance': return MonthlyPerformance(p.chart);
      case 'performance': return Performance(p.chart);
      case 'category_sales_comparison': return CategoryComparison(p.chart);
      case 'daily_category_sales': return DailyCategorySales(p.chart);
      default: return GenericChart(p.chart);
    }
  }

  // ───────────────────────────── tree map (UO / WO) ─────────────────────────────
  var toNum = function (e) { var t = Number(typeof e === 'string' ? e.split(',').join('').trim() : e); return Number.isFinite(t) ? t : 0; };
  var toNumOrNull = function (e) { var t = typeof e === 'string' ? e.split(',').join('').trim() : e; if (t === '' || t == null) return null; var n = Number(t); return Number.isFinite(n) ? n : null; };
  function normTreeMap(e) {
    var name = e.name || '', cols = (e.cols || []).map(String);
    if (cols.length < 2) return null;
    var units = (e.units || []).map(function (u) { return typeof u === 'string' ? u : null; });
    var rows = (e.items || []).filter(Array.isArray);
    var cells = function (r) { return cols.map(function (c, i) { return { key: c, value: String(r[i] == null ? '' : r[i]).trim(), unit: units[i] == null ? null : units[i] }; }); };
    var desc = (e.description || '').trim() || null, ci = cols.indexOf('campaign_name'), gi = cols.indexOf('ad_group_name');
    if (ci === -1 || gi === -1) {
      var flat = rows.map(function (r, i) { var cs = cells(r), lab = (cs[0] && cs[0].value) || T.tmItem(i + 1); return { key: name + '-' + lab + '-' + i, label: lab, labelKey: cols[0] || 'name', size: toNum(r[1]), colorValue: toNumOrNull(r[cols.length - 1]), cells: cs }; }).filter(function (x) { return x.cells.length >= 2; });
      return flat.length ? { name: name, description: desc, items: flat } : null;
    }
    var si = cols.findIndex(function (c, i) { return i !== ci && i !== gi; });
    if (si === -1) return null;
    var last = cols.length - 1;
    var recs = rows.map(function (r, i) {
      var cs = cells(r), camp = cs[ci] ? cs[ci].value : '', grp = cs[gi] ? cs[gi].value : '';
      return { key: name + '-' + camp + '-' + (grp || 'total') + '-' + i, label: grp || camp || T.tmItem(i + 1), labelKey: grp ? cols[gi] : cols[ci], campaign: camp, adGroup: grp, size: toNum(r[si]), colorValue: toNumOrNull(r[last]), cells: cs };
    }).filter(function (x) { return x.cells.length >= 3 && x.campaign; });
    var map = new Map();
    recs.forEach(function (x) {
      var cur = map.get(x.campaign);
      if (!x.adGroup) { map.set(x.campaign, { key: x.key, label: x.label, labelKey: x.labelKey, size: x.size, colorValue: x.colorValue, cells: x.cells, children: cur ? cur.children : [], agg: true }); return; }
      var leaf = { key: x.key, label: x.label, labelKey: x.labelKey, size: x.size, colorValue: x.colorValue, cells: x.cells };
      if (cur) cur.children.push(leaf); else map.set(x.campaign, { key: x.key, label: x.campaign, labelKey: cols[ci], size: 0, colorValue: x.colorValue, cells: x.cells, children: [leaf], agg: false });
    });
    var items = Array.from(map.values()).map(function (n) {
      var o = { key: n.key, label: n.label, labelKey: n.labelKey, size: n.agg ? n.size : (n.children || []).reduce(function (a, c) { return a + c.size; }, 0), colorValue: n.colorValue, cells: n.cells };
      if (n.children && n.children.length) o.children = n.children;
      return o;
    });
    if (items.length) return { name: name, description: desc, items: items };
    return null;
  }
  var band = function (e) { return e == null || !Number.isFinite(e) ? null : (TM_BANDS.find(function (t) { return (t.min == null || e >= t.min) && (t.max == null || e < t.max); }) || null); };
  function tmValue(v, unit) {
    var n = String(v == null ? '' : v).trim(); if (!n) return '-';
    var r = toNumOrNull(n); if (r == null) return n;
    var u = String(unit == null ? '' : unit).trim().toUpperCase(), d = Math.min((n.split('.')[1] || '').length, 4);
    var o = r.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
    return u ? (u === '%' ? o + '%' : o + ' ' + unit) : o;
  }
  var TM_PLAIN = { color: function () { return '#d7dde4'; }, label: function (e) { return e; }, value: function (e) { return tmValue(e.value, e.unit); }, legend: function () { return []; } };
  var TM_DIAG = {
    color: function (e) { var b = band(e); return b ? b.color : '#E2E4E9'; },
    label: function (e) { return e in TM_LABELS ? TM_LABELS[e] : (/_ratio$/.test(e) ? TM_RATIO_FALLBACK : e); },
    value: function (e) { var t = tmValue(e.value, e.unit); if (!/_ratio$/.test(e.key)) return t; var b = band(Number(e.value)); return b ? t + ' (' + b.label + ')' : t; },
    legend: function () { return TM_BANDS.map(function (b) { return { color: b.color, label: b.label }; }); }
  };
  var textOn = function (e) { return ['#E2E4E9', '#D7DDE4', '#D7DBE3'].indexOf(e.toUpperCase()) >= 0 ? '#3c4650' : '#fff'; };
  var tmLabel = function (color) { return { color: color, fontFamily: cssVar('--font-body'), fontSize: 12, fontWeight: 700, lineHeight: 18, silent: true, width: '90%', height: 36, align: 'left', verticalAlign: 'top', overflow: 'break', lineOverflow: 'truncate', ellipsis: '..' }; };
  var TM_EMPH = { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(16, 24, 40, 0.18)' } };
  function tmNode(e, r, border) {
    var col = r.color(e.colorValue);
    var o = { id: e.key, name: e.label, value: Math.max(e.size, 0), rawCells: e.cells, labelKey: e.labelKey, itemStyle: { color: col, borderColor: border || '#ffffff', borderWidth: 1, gapWidth: 1 }, label: tmLabel(textOn(col)), emphasis: TM_EMPH };
    if (e.children && e.children.length) o.children = e.children.map(function (c) { return tmNode(c, r, col); });
    return o;
  }
  function TreeMapGroup(tables, ctx) {
    var maps = tables.map(normTreeMap).filter(Boolean);
    if (!maps.length) return Empty();
    var r = ctx.reportType === 'daily' ? TM_DIAG : ctx.reportType ? TM_PLAIN : (maps.some(function (m) { return m.items.some(function (i) { var c = i.cells[i.cells.length - 1]; return c && /_ratio$/.test(c.key); }); }) ? TM_DIAG : TM_PLAIN);
    var multi = maps.length > 1, legend = r.legend(), resets = [];
    return h('div', { className: 'stack gap-3' },
      h('div', { className: 'sec-toolbar' }, h('span', { className: 'flex-auto min-w-0' }),
        h('button', { type: 'button', className: 'btn btn-ghost btn-icon btn-sm', 'aria-label': T.tmAll, title: T.tmAllTitle, onClick: function () { resets.forEach(function (f) { f(); }); } }, icon('refresh'))),
      legend.length ? h('div', { className: 'sec-tm-legend' }, legend.map(function (l) { return h('span', { className: 'row gap-1' }, h('i', { style: { background: l.color } }), l.label); })) : null,
      h('div', { className: 'sec-tm-group', style: { gridTemplateColumns: 'repeat(' + maps.length + ', minmax(0, 1fr))' } }, maps.map(function (m) { return TreeMapBlock(m, r, multi, multi, resets); })));
  }
  function TreeMapBlock(s, r, multi, showTitle, resets) {
    var stack = [], chart = null, nodes = s.items.map(function (e) { return tmNode(e, r); });
    var byId = new Map(); (function walk(list) { list.forEach(function (n) { byId.set(n.id, n); if (n.children) walk(n.children); }); })(nodes);
    var canvas = h('div', { className: 'sec-tm-canvas' });
    var frame = h('div', { className: 'sec-tm-frame', style: { height: (multi ? 320 : 420) + 'px', borderColor: 'var(--border-default)', background: 'transparent', color: 'inherit' } }, canvas);
    function draw() {
      var top = stack[stack.length - 1] || null, border = top ? top.itemStyle.color : '#ffffff';
      var active = frame.querySelector('.sec-tm-active'); if (active) frame.removeChild(active);
      frame.style.borderColor = top ? top.itemStyle.color : 'var(--border-default)';
      frame.style.background = top ? top.itemStyle.color : 'transparent';
      frame.style.color = top ? textOn(top.itemStyle.color) : 'inherit';
      if (top) frame.insertBefore(h('div', { className: 'sec-tm-active' }, h('span', { className: 'truncate font-bold t-xs' }, top.name),
        h('button', { type: 'button', className: 'sec-tm-back', 'aria-label': T.tmBack, onClick: function () { stack.pop(); draw(); } }, icon('arrow-left', 14))), canvas);
      if (!chart) return;
      var kids = (top && top.children && top.children.length ? top.children : nodes).map(function (n) { var o = Object.assign({}, n); delete o.children; o.itemStyle = Object.assign({}, n.itemStyle, { borderColor: border }); return o; });
      var root = { id: s.name + '-root', name: T.all, value: kids.reduce(function (a, n) { return a + Math.max(n.value, 0); }, 0), itemStyle: { color: '#E2E4E9', borderColor: '#ffffff', borderWidth: 1, gapWidth: 1 }, label: tmLabel('#3c4650'), children: kids };
      chart.setOption({
        animation: false,
        tooltip: { appendTo: 'body', className: 'sec-tm-tip-layer', confine: false, extraCssText: 'box-shadow: none; border: none; padding: 0; z-index: 3000;',
          formatter: function (p) { var x = Array.isArray(p) ? p[0] : p, n = byId.get(x && x.data ? x.data.id : ''); if (!n) return ''; var rows = n.rawCells.filter(function (c) { return c.key !== n.labelKey; }).map(function (c) { return '<div class="sec-tm-tip-row"><span>' + esc(r.label(c.key)) + '</span><strong>' + esc(r.value(c)) + '</strong></div>'; }).join(''); return '<div class="sec-tm-tip"><p class="sec-tm-tip-title">' + esc(n.name) + '</p>' + rows + '</div>'; } },
        series: [{ type: 'treemap', name: s.name, animation: false, data: [root], nodeClick: false, roam: false, left: 0, top: 0, right: 0, bottom: 0, breadcrumb: { show: false },
          label: { show: true, silent: true, formatter: '{b}', position: 'insideTopLeft', padding: [10, 10, 0, 10] }, upperLabel: { show: false },
          itemStyle: { borderColor: border, borderWidth: 1, gapWidth: 1 }, levels: [{ itemStyle: { borderColor: border, borderWidth: 1, gapWidth: 1 } }] }]
      }, { notMerge: true });
    }
    resets.push(function () { stack = []; draw(); });
    onMount(function () {
      if (!window.echarts) return;
      chart = window.echarts.init(canvas, null, { renderer: 'canvas' });
      if (window.ResizeObserver) new ResizeObserver(function () { chart.resize(); }).observe(canvas);
      chart.on('click', function (p) { var n = byId.get(p.data ? p.data.id : ''); var top = stack[stack.length - 1]; if (n && n.children && n.children.length && (!top || n.id !== top.id)) { stack.push(n); draw(); } });
      draw();
    });
    return h('section', { className: 'stack gap-2' },
      showTitle && s.name ? h('p', { className: 'section-title row gap-1' }, s.name, s.description ? h('span', { className: 'sec-help', title: s.description, 'aria-label': s.description }, '?') : null) : null,
      frame,
      !showTitle && s.description ? h('p', { className: 'hint' }, s.description) : null);
  }

  // ───────────────────────────── component group & dispatcher (po) ─────────────────────────────
  var KW_TREE = '캠페인/광고그룹/키워드 성과', KW_NAMES = [KW_TREE, '키워드 성과', '광고그룹 성과', '캠페인 성과'];
  function groupTransform(groupName, comps) {
    var nm = function (c) { return ('name' in c && c.name ? String(c.name).trim() : '') || ''; };
    var isPT = function (c) { return c.type === 'paged_table'; };
    var pick = KW_NAMES.map(function (n) { return comps.find(function (c) { return nm(c) === n && isPT(c); }); }).find(Boolean);
    if (pick) {
      var done = false;
      return comps.reduce(function (acc, c) { if (KW_NAMES.indexOf(nm(c)) >= 0) { if (!done) { done = true; acc.push(Object.assign({}, pick, { name: KW_TREE })); } } else acc.push(c); return acc; }, []);
    }
    if ((groupName || '').trim().indexOf('광고 채널 성과') < 0) return comps;
    var ch = comps.find(function (c) { return isPT(c) && /광고 채널 성과$/.test(nm(c)); });
    return ch ? [Object.assign({}, ch, { name: KW_TREE })] : comps;
  }
  function nameInGroup(groupName, c) {
    if (c.type !== 'chart' && c.type !== 'Chart') return c;
    var n = (groupName || '').trim();
    return (c.name || '').trim() || PERF_NAMES.indexOf(n) < 0 ? c : Object.assign({}, c, { name: n });
  }
  function sectionTitle(e) { return e.type === 'action_card' ? e.title : (('name' in e ? e.name : null) || SECTION_TYPE_LABEL[e.type] || e.type || ''); }
  function RawFallback(e) {
    return [h('div', { className: 'banner banner-muted' }, icon('info'), h('div', { className: 'b-body t-xs' }, T.rawNotice)),
      h('details', { className: 'mt-2' }, h('summary', { className: 't-xs fg-2', style: { cursor: 'pointer' } }, T.rawToggle), h('pre', { className: 'mono surface-sunken mt-2 sec-raw' }, JSON.stringify(e, null, 2)))];
  }
  function renderSection(e, ctx, ancestors) {
    var inGroup = ancestors !== undefined;
    var p = inGroup ? presetInGroup(e) : presetOf(e, ctx.reportType);
    if (p) return renderPreset(p, ctx);
    switch (e.type) {
      case 'target_progression': case 'branding_target_progression': return TargetProgression(e, ctx);
      case 'source_progression': return SourceProgression(e, ctx);
      case 'text': return TextSection(e);
      case 'action_card': return ActionCardSection(e);
      case 'daily_contribution': return DailyContribution(e);
      case 'paged_table': return PagedTable(e, inGroup, ancestors);
      case 'table': return PlainTable(e);
      case 'tree_map': return TreeMapGroup([e], ctx);
      case 'chart': case 'Chart': case 'chart_component_group': { var c = normChart(e); return c ? GenericChart(c) : Empty(); }
      case 'calendar': return Calendar(e, ctx);
      case 'component_group': {
        var comps = (e.components || []).map(function (c) { return nameInGroup(e.name, c); });
        if (comps.length && comps.every(function (c) { return c.type === 'tree_map'; })) return TreeMapGroup(comps, ctx);
        var anc = (ancestors || []).concat(e.name && e.name.trim() ? [e.name.trim()] : []);
        return h('div', { className: 'stack gap-5' }, groupTransform(e.name, comps).filter(function (c) { return c.type !== 'calendar'; }).map(function (c) {
          return h('div', null, h('h4', { className: 'section-title mb-2' }, sectionTitle(c)), renderSection(c, ctx, anc));
        }));
      }
      default: return RawFallback(e);
    }
  }

  // ───────────────────────────── page ─────────────────────────────
  var HIDDEN_TYPES = new Set(['promotion', 'metadata', 'workflow_metadata']);
  var NO_CARD = new Set(['target_progression', 'branding_target_progression']);
  function prepare(items) {
    return (items || []).filter(function (e) { return !HIDDEN_TYPES.has(e.analysis_artifact.type); })
      .sort(function (a, b) { return (a.order == null ? Number.MAX_SAFE_INTEGER : a.order) - (b.order == null ? Number.MAX_SAFE_INTEGER : b.order); })
      .map(function (e) { return Object.assign({}, e.analysis_artifact.data, { uid: e.analysis_artifact_id || e.analysis_artifact.id, type: e.analysis_artifact.type }); });
  }
  function promotionItems(items) {
    var p = (items || []).find(function (e) { return e.analysis_artifact.type === 'promotion'; });
    var list = p && p.analysis_artifact.data ? p.analysis_artifact.data.items : undefined;
    if (!Array.isArray(list)) return undefined;
    return list.map(function (e) {
      return { id: e.id, name: e.title || '', start_date: e.start_date || e.date_begin || '', end_date: e.end_date || e.date_end || '', type: 'promotion', color: e.color || undefined,
        description: e.analysis_result || e.info || undefined, owner_name: e.owner_name || undefined, sales_channel: e.sales_channel || undefined, link: e.link || undefined,
        promotion_type: e.promotion_type === '타사' ? 'competitor' : (e.promotion_type || undefined), competitor_name: e.competitor_name || undefined };
    });
  }
  function Body(sections, variant, ctx) {
    var root = h('div', { className: variant === 'paper' ? undefined : 'stack gap-4' });
    sections.forEach(function (e, i) {
      var p = presetOf(e, ctx.reportType), title = (p && p.title) || sectionTitle(e), content = renderSection(e, ctx);
      if (variant === 'paper') root.appendChild(h('section', { className: 'sheet-section' }, h('h2', { className: 'sheet-h2' }, h('span', { className: 'sheet-no' }, String(i + 1).padStart(2, '0')), ' ', title), content));
      else if (NO_CARD.has(e.type)) root.appendChild(h('section', null, h('h2', { className: 'section-title mb-3' }, title), content));
      else root.appendChild(h('section', { className: 'card' }, h('div', { className: 'card-head' }, h('h3', null, title)), h('div', { className: 'card-body' }, content)));
    });
    return root;
  }
  var refDate = function (r) { var parts = String(r || '').split('~'); return parts[parts.length - 1].trim(); };
  function Header(meta) {
    var kind = T.kind[meta.type] || meta.type;
    var badge = 'badge ' + (meta.type === 'daily' ? 'badge-info' : meta.type === 'mtd' ? 'badge-pending' : meta.type === 'monthly' ? 'badge-success' : '');
    return [h('div', { className: 'row gap-2 mb-2' },
      h('span', { className: badge }, T.reportKind(kind)),
      meta.published === false ? h('span', { className: 'badge badge-warning' }, T.unpublished) : h('span', { className: 'badge badge-success badge-dot' }, T.published),
      h('span', { className: 't-xs fg-3' }, T.created(meta.created || '', meta.author || ''))),
      h('h1', null, meta.name)];
  }
  function CardPage(meta, body) {
    var ref = refDate(meta.reference_date), d = new Date(ref + 'T00:00:00'), prev = new Date(d.getTime() - 864e5);
    var period;
    if (meta.type === 'mtd') {
      var s = String(meta.reference_date || '').split('~')[0].trim() || (ref.slice(0, 8) + '01');
      period = '기간 ' + s + ' ~ ' + ref.slice(5);
    } else period = '전일 ' + ymd(prev) + ' 대비';
    return h('div', { className: 'page' },
      h('div', { className: 'page-head', style: { marginBottom: 'var(--sp-5)' } },
        h('div', null, Header(meta),
          h('p', { className: 'desc' }, '기준일 ', h('b', { className: 'font-semibold', style: { color: 'var(--fg-primary)' } }, d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월 ' + d.getDate() + '일 (' + T.weekday[d.getDay()] + ')'), ' · ' + period))),
      body);
  }
  function PaperPage(meta, body) {
    var ym = String(meta.reference_date || '').slice(0, 7).split('-').map(Number), y = ym[0], m = ym[1];
    var last = new Date(y, m, 0).getDate(), prev = m === 1 ? (y - 1) + '년 12월' : y + '년 ' + (m - 1) + '월';
    var brand = meta.brand || {};
    return h('div', { className: 'page paper-page pg-report-monthly' },
      h('div', { className: 'paper-toolbar' }, h('div', { className: 'row gap-2' }, h('div', { style: { display: 'contents' } }, Header(meta)))),
      h('article', { className: 'sheet' },
        h('header', { className: 'sheet-cover' },
          h('div', { className: 'row-between' },
            h('div', { className: 'row gap-3' },
              brand.name ? h('span', { className: 'brand-tile', style: { background: brand.color || 'rgb(63, 143, 115)', width: '40px', height: '40px', fontSize: '15px' } }, brand.initials || brand.name.slice(0, 2)) : null,
              h('div', null, h('div', { className: 't-sm font-semibold' }, brand.name || ''), h('div', { className: 't-xs fg-3' }, brand.advertiser || ''))),
            h('div', { className: 'eyebrow' }, 'Monthly Performance Report')),
          h('h1', { className: 'sheet-title' }, meta.name),
          h('p', { className: 'sheet-sub' }, T.sheetSub(y, m, last, prev)),
          h('div', { className: 'sheet-rule' })),
        body,
        h('footer', { className: 'sheet-foot' }, h('span', null, (brand.name || ''), ' · ', meta.name), h('span', null, T.sheetFoot(String(meta.created || '').slice(0, 10), meta.author || '')))));
  }
  function AiPanel(cards, onClose) {
    var aside = h('aside', { className: 'ai-panel', 'aria-label': T.aiTitle });
    var body = h('div', { className: 'ai-panel-body' });
    function open(card) {
      var close = function () { if (m.parentNode) m.parentNode.removeChild(m); };
      var m = Modal(h('div', { className: 'modal modal-lg', role: 'dialog', 'aria-modal': 'true' },
        h('div', { className: 'modal-head' },
          h('div', null, card.tags && card.tags.length ? h('div', { className: 'row gap-1 mb-2' }, card.tags.map(function (t) { return h('span', { className: 'badge badge-pending' }, t); })) : null, h('h2', null, card.title)),
          h('button', { className: 'btn btn-ghost btn-sm btn-icon', 'aria-label': T.close, onClick: close }, icon('x'))),
        h('div', { className: 'modal-body stack gap-4' }, ActionCardBody(card)),
        h('div', { className: 'modal-foot' }, h('button', { className: 'btn btn-secondary', onClick: close }, T.close))), close);
      aside.appendChild(m);
    }
    cards.forEach(function (c) {
      body.appendChild(h('button', { className: 'ai-card ', onClick: function () { open(c); } },
        h('div', { className: 'tags' }, (c.tags || []).map(function (t) { return h('span', { className: 'badge badge-pending' }, t); })),
        h('div', { className: 't' }, c.title),
        c.description ? h('div', { className: 'd' }, c.description) : null));
    });
    body.appendChild(h('p', { className: 'hint', style: { padding: '8px 4px 0px' } }, T.aiHint));
    aside.appendChild(h('div', { className: 'ai-panel-head' },
      h('h3', null, icon('sparkles', 18), ' ' + T.aiTitle + ' ', h('span', { className: 'badge badge-pill', style: { marginLeft: '2px' } }, String(cards.length))),
      h('button', { className: 'btn btn-ghost btn-sm btn-icon', 'aria-label': T.close, onClick: onClose }, icon('x'))));
    aside.appendChild(body);
    return aside;
  }

  function render(report, mountEl) {
    var meta = report.meta || {}, items = report.items || [];
    var all = prepare(items);
    var sections = all.filter(function (e) { return e.type !== 'action_card'; });
    var cards = meta.type === 'daily' || meta.type === 'mtd' ? all.filter(function (e) { return e.type === 'action_card'; }) : [];
    var tp = sections.find(function (e) { return e.type === 'target_progression'; });
    var ctx = { reportType: meta.type, period: tp ? ((tp.target_progression || tp).period || null) : null, promotionItems: promotionItems(items) };
    var paper = meta.type === 'monthly';
    var body = Body(sections, paper ? 'paper' : 'card', ctx);
    var page = paper ? PaperPage(meta, body) : CardPage(meta, body);
    var content = h('div', { className: 'content ' + (paper ? 'is-paper' : '') + ' ' }, page);
    var row = h('div', { className: 'content-row' }, content);
    var toggle = null;
    if (cards.length) {
      var panel = AiPanel(cards, function () { panel.style.display = 'none'; toggle.style.display = ''; });
      toggle = h('button', { className: 'btn btn-secondary btn-sm ai-toggle lh-ai-reopen', 'aria-pressed': 'false', style: { display: 'none' }, onClick: function () { panel.style.display = ''; toggle.style.display = 'none'; } }, icon('sparkles'), ' ' + T.aiTitle);
      row.appendChild(panel);
    }
    var app = h('div', { className: 'app' }, h('div', { className: 'main' }, row));
    if (toggle) app.appendChild(toggle);
    clear(mountEl);
    mountEl.appendChild(app);
    document.title = meta.name || document.title;
    var q = MOUNT_QUEUE.splice(0);
    q.forEach(function (fn) { try { fn(); } catch (err) { console.error(err); } });
  }

  window.LaighthouseReport = { render: render };
  function boot() { if (window.__LH_REPORT__) render(window.__LH_REPORT__, document.getElementById('app')); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
