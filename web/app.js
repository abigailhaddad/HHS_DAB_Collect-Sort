import { initDb, query, tableRef } from './db.js';

// Served from R2, not the Pages deploy: Cloudflare Pages caps a single
// static asset at 25 MiB on the Free plan, and this file is ~63 MB -- the
// same reason usajobs_historical serves its Parquet from R2 too. Re-upload
// with `python3 build_web_data.py && python3 upload_web_data.py` whenever
// the corpus changes; this URL doesn't need to.
const PARQUET_URL = 'https://pub-c5d2b03a812741a9b9281604ce41cf7b.r2.dev/decisions.parquet';

const TRIBUNAL_LABEL = { alj: 'ALJ (Civil Remedies)', dab: 'Appellate Division' };

// "Party" (party_name, from the Board's own index caption) is who the case is
// actually about -- a doctor, a facility, a retailer. "Federal Office"
// (respondent) is only ever one of ~7 government offices (CMS, the Inspector
// General, FDA's tobacco arm, ...) -- a useful secondary filter, never the
// answer to "who is this case about".
const CATEGORY_COLUMNS = [
  { label: 'Decision #', field: 'decision_no', filterType: 'text', index: 0 },
  { label: 'Tribunal', field: 'corpus', filterType: 'multiselect', index: 1 },
  { label: 'Year', field: 'year', filterType: 'multiselect', index: 2 },
  { label: 'Party', field: 'party_name', filterType: 'text', index: 4 },
  { label: 'Federal Office', field: 'respondent', filterType: 'multiselect', index: 5 },
  { label: 'Category', field: 'categories', filterType: 'multiselect', index: 6 },
  { label: 'Disposition', field: 'dispositions', filterType: 'multiselect', index: 7 },
  { label: 'Judges', field: 'judges', filterType: 'multiselect', index: 8 },
  { label: 'Provider IDs', field: 'provider_ids', filterType: 'text', index: 9 },
];

// DuckDB-WASM hands back Arrow list columns as Vector-like objects, not plain
// arrays -- Array.isArray() is false on them, and String(vector) stringifies
// as "[a,b,c]" instead of throwing, so a naive check silently wraps the whole
// vector as one bogus element ("[a,b,c]") rather than failing loudly.
const toArr = (v) => {
  if (v == null) return [];
  if (Array.isArray(v)) return v;
  if (typeof v.toArray === 'function') return v.toArray();
  if (typeof v[Symbol.iterator] === 'function') return Array.from(v);
  return [v];
};
const joined = (v) => toArr(v).join(' | ');

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// Stat cards and both panels describe "the rows currently on screen", not
// the whole corpus -- same call dod's site makes -- so they're recomputed
// from the DataTable's own filtered row set (rows({search:'applied'}),
// already in memory, the same array the table itself draws from) on every
// filter change, rather than re-queried from DuckDB. One pass over the
// filtered rows computes all of it at once instead of three separate
// queries, and it stays correct by construction: whatever the table shows
// IS the aggregate.
function computeAggregates(table) {
  const rows = table.rows({ search: 'applied' }).data().toArray();
  const categorySet = new Set();
  const corpusSet = new Set();
  const outcomeCounts = new Map();
  const yearCounts = new Map();
  let reviewed = 0;
  let minDate = null, maxDate = null;

  for (const r of rows) {
    // r[6] is the rendered "A | B" string, not a real list -- split it back
    // apart the same way the multiselect filter dialog already does.
    (r[6] || '').split(' | ').forEach((c) => c && categorySet.add(c));
    if (r[1]) corpusSet.add(r[1]);
    if (r[3]) {
      if (minDate === null || r[3] < minDate) minDate = r[3];
      if (maxDate === null || r[3] > maxDate) maxDate = r[3];
    }
    if (r[16] === 'dab' && r[17]) {
      reviewed += 1;
      (r[7] || '').split(' | ').forEach((o) => {
        if (o) outcomeCounts.set(o, (outcomeCounts.get(o) || 0) + 1);
      });
    }
    if (r[2]) yearCounts.set(r[2], (yearCounts.get(r[2]) || 0) + 1);
  }

  return { total: rows.length, categorySet, corpusSet, outcomeCounts,
          yearCounts, reviewed, minDate, maxDate };
}

function renderStats(agg) {
  document.getElementById('statTotal').textContent = agg.total.toLocaleString();
  document.getElementById('statTribunals').textContent = agg.corpusSet.size;
  document.getElementById('statCategories').textContent = agg.categorySet.size;
  document.getElementById('statDateRange').textContent =
    agg.minDate && agg.maxDate ? `${agg.minDate} – ${agg.maxDate}` : '–';
}

// "How often does the Appellate Division reverse the ALJ?" is answerable
// from a dispositions column that's already loaded -- but nothing on the
// page ever asked it. Coverage is the same 29.6% dispositions has
// everywhere else (fields.py only labels a decision from unambiguous
// first-person language, "we affirm"/"we reverse", never from a mention of
// the word), so the caveat travels with the number rather than presenting a
// rate over an unstated denominator.
function renderAppealOutcomes(agg) {
  const el = document.getElementById('appealOutcomes');
  if (!el) return;
  if (!agg.reviewed) {
    el.innerHTML = '<h3>Appeal outcomes</h3><p class="text-muted small">No Appellate decisions among the current filter name the ALJ decision they reviewed.</p>';
    return;
  }
  const rows = Array.from(agg.outcomeCounts.entries()).sort((a, b) => b[1] - a[1]);
  const labeled = rows.reduce((s, [, n]) => s + n, 0);
  const unclear = agg.reviewed - labeled;
  // Not a real disposition -- the tribunal didn't say anything ambiguous
  // enough to skip labeling, fields.py just found no unambiguous first-person
  // language to label it from. Kept last regardless of count, the same way
  // an "Other"/"Unknown" bucket sits apart from the real categories it sums
  // against, rather than sorted in among them by size.
  if (unclear > 0) rows.push(['Unclear', unclear]);
  el.innerHTML = `
    <h3>Appeal outcomes</h3>
    <ul class="outcome-list">
      ${rows.map(([outcome, n]) => `<li><span class="outcome-label">${escapeHtml(outcome)}</span>
        <span class="outcome-count">${n.toLocaleString()}</span></li>`).join('')}
    </ul>
    <p class="text-muted small">${agg.reviewed.toLocaleString()} Appellate decisions (matching
      the current filter) name the ALJ decision they reviewed. "Unclear" means the decision
      doesn't use first-person language ("we affirm"/"we reverse") unambiguous enough to
      label -- not necessarily an unstated outcome.</p>
  `;
}

// "Is the Board issuing fewer decisions in recent years" needs a per-year
// breakdown the stat cards don't give on their own. A plain CSS bar chart --
// div heights scaled to the max -- needs nothing this static site doesn't
// already have.
function renderVolumeByYear(agg) {
  const el = document.getElementById('volumeByYear');
  if (!el) return;
  const years = Array.from(agg.yearCounts.entries()).sort((a, b) => a[0] - b[0]);
  if (!years.length) {
    el.innerHTML = '<h3>Decisions by year</h3><p class="text-muted small">No decisions match the current filter.</p>';
    return;
  }
  const max = Math.max(...years.map(([, n]) => n));
  el.innerHTML = `
    <h3>Decisions by year</h3>
    <div class="year-bars">
      ${years.map(([year, n]) => {
        const pct = Math.max(2, Math.round((n / max) * 100));
        return `<div class="year-bar" title="${year}: ${n.toLocaleString()}">
          <div class="year-bar-fill" style="height:${pct}%"></div>
          <div class="year-bar-label">${String(year).slice(2)}</div>
        </div>`;
      }).join('')}
    </div>
  `;
}

function renderAggregates(table) {
  const agg = computeAggregates(table);
  renderStats(agg);
  renderAppealOutcomes(agg);
  renderVolumeByYear(agg);
}

async function main() {
  const conn = await initDb(PARQUET_URL);
  const t = tableRef(conn);

  const rows = await query(conn, `
    SELECT id, decision_no, corpus, year,
           CAST(decision_date AS VARCHAR) AS decision_date,
           party_name, respondent, judges, dispositions, provider_ids,
           categories, source_url, reviews_decision_no, appealed_in
    FROM ${t}
    ORDER BY decision_date DESC NULLS LAST
  `);

  // "Related Decisions": an ALJ decision's own reviews_decision_no (the
  // Appellate decision reviewing it) plus an Appellate decision's own
  // appealed_in (the ALJ decisions it names) -- link_corpora.py computed both
  // exactly, from an actual match rather than a heuristic, but neither was
  // reachable from the UI before. Each number is a live link: clicking it
  // reuses the existing Decision # text filter rather than a new query.
  const relatedNumbers = (r) => {
    const nums = new Set(toArr(r.appealed_in));
    if (r.reviews_decision_no) nums.add(r.reviews_decision_no);
    return Array.from(nums);
  };
  const relatedHtml = (nums) => nums.map((n) =>
    `<a class="related-link" data-no="${escapeHtml(n)}">${escapeHtml(n)}</a>`).join(' | ');

  const tableData = rows.map((r) => {
    const related = relatedNumbers(r);
    return [
      r.decision_no || '',
      TRIBUNAL_LABEL[r.corpus] || r.corpus,
      r.year,
      r.decision_date || '',
      r.party_name || '',
      r.respondent || '',
      joined(r.categories),
      joined(r.dispositions),
      joined(r.judges),
      toArr(r.provider_ids).join(', '),
      relatedHtml(related),
      `<a class="view-link" data-id="${escapeHtml(r.id)}">View</a>`,
      r.source_url
        ? `<a href="${escapeHtml(r.source_url)}" target="_blank" rel="noopener">Source &#8599;</a>`
        : '',
      // Plain-text shadow copies for CSV export -- not rendered, not given a
      // <th> or a `columns:` entry below, so DataTables never shows them,
      // but table.row(node).data() still returns them by index. The last
      // two (raw corpus, raw reviews_decision_no) are what computeAggregates
      // needs and the rendered columns don't carry: index 1 is the display
      // label ("Appellate Division"), not the raw 'dab'/'alj' the appeal-
      // outcomes filter checks against, and reviews_decision_no is folded
      // into the merged "Related Decisions" display at index 10/13.
      related.join('; '),
      r.source_url || '',
      r.id,
      r.corpus,
      r.reviews_decision_no || '',
    ];
  });
  const ID_COLUMN = 15;

  // Full-text search behaves like every other filter -- it's in "+ Add
  // Filter", it gets a chip in the filter bar, it survives Clear/copy-link
  // -- rather than a box of its own, even though there's no real column
  // behind it: the decision text is already resident in the in-browser
  // DuckDB table (it's in the Parquet; the main SELECT above just never
  // asked for it), so this is one query away rather than a new feature.
  // shared.js's 'fulltext' filter type exists for exactly this case: a
  // filter whose match can't be a synchronous per-cell substring test, so
  // its dialog calls onApply(value) instead of table.column(i).search(value).
  // `let table` (not `const`) because onApply is defined, and can be handed
  // to initDataTableWithFilters, before the table it closes over exists --
  // by the time onApply's body runs past its `await`, table is assigned.
  let table;
  let fulltextIds = null; // null = no full-text filter active
  const FULLTEXT_INDEX = 100; // bookkeeping key only; no such DataTables column
  async function applyFulltextFilter(term) {
    if (!term) {
      fulltextIds = null;
      table.draw();
      return;
    }
    const matches = await query(conn,
      `SELECT id FROM ${t} WHERE text ILIKE '%' || ? || '%' LIMIT 2000`, [term]);
    fulltextIds = new Set(matches.map((m) => m.id));
    table.draw();
  }
  // `data` (2nd param) only covers the columns configured below (13 of
  // them); the shadow columns (id at 15) only survive on `rowData` (4th
  // param), the untouched original array from tableData.
  $.fn.dataTable.ext.search.push((settings, data, index, rowData) => {
    // DataTables runs an internal draw as part of its own construction --
    // before initDataTableWithFilters below has returned and assigned
    // `table` here. Nothing could be filtered yet at that point anyway.
    if (!table || settings.nTable !== table.table().node()) return true;
    return fulltextIds === null || fulltextIds.has(rowData[ID_COLUMN]);
  });

  const allColumns = [
    ...CATEGORY_COLUMNS,
    { label: 'Full Text', field: '_fulltext', filterType: 'fulltext',
      index: FULLTEXT_INDEX, onApply: applyFulltextFilter },
  ];

  ({ table } = initDataTableWithFilters({
    tableSelector: '#decisionsTable',
    // Without this, shared.js falls back to a random id and silently builds
    // a second filter bar right above the table instead of using the one
    // already in index.html -- chips render into that orphan, invisible
    // wherever the page actually points a reader to look for them.
    filterBarId: 'filtersBar',
    tableOptions: {
      data: tableData,
      columns: [
        { data: 0 }, { data: 1 }, { data: 2 }, { data: 3 }, { data: 4 },
        { data: 5 }, { data: 6 }, { data: 7 }, { data: 8 }, { data: 9 },
        { data: 10, orderable: false }, { data: 11, orderable: false },
        { data: 12, orderable: false },
      ],
      order: [[3, 'desc']],
      pageLength: 25,
    },
    fieldTypes: Object.fromEntries(allColumns.map((c) => [c.field, c.filterType])),
    columns: allColumns,
    csvFilename: 'hhs_dab_decisions.csv',
    csvColumns: [
      { header: 'Decision #', getData: (n, d) => d[0] },
      { header: 'Tribunal', getData: (n, d) => d[1] },
      { header: 'Year', getData: (n, d) => d[2] },
      { header: 'Date', getData: (n, d) => d[3] },
      { header: 'Party', getData: (n, d) => d[4] },
      { header: 'Federal Office', getData: (n, d) => d[5] },
      { header: 'Category', getData: (n, d) => d[6] },
      { header: 'Disposition', getData: (n, d) => d[7] },
      { header: 'Judges', getData: (n, d) => d[8] },
      { header: 'Provider IDs', getData: (n, d) => d[9] },
      { header: 'Related Decisions', getData: (n, d) => d[13] },
      { header: 'Source URL', getData: (n, d) => d[14] },
    ],
  }));

  renderAggregates(table);
  // search.dt fires when the filtered row set actually changes; plain 'draw'
  // also fires on pagination and page-length changes, where the row set is
  // identical and recomputing would be wasted work -- verified the same way
  // dod's site did: 3 "next page" clicks fired draw 3 times, search.dt 0.
  table.on('search.dt', () => renderAggregates(table));

  // Clicking a related-decision number jumps to it via the Decision # text
  // filter that already exists -- no new query, no new UI, just reusing the
  // filter the column-search box already drives.
  $('#decisionsTable tbody').on('click', 'a.related-link', (e) => {
    table.column(0).search(e.target.getAttribute('data-no')).draw();
    document.querySelector('.table-scroll-wrapper')?.scrollIntoView({ behavior: 'smooth' });
  });

  // PDF extraction preserves the source layout verbatim: "Page 2" etc. gets
  // injected wherever the PDF paginated, mid-sentence as often as not, and a
  // centered cover page turns into a dozen blank lines before the decision
  // actually starts.
  const stripPageBreaks = (text) =>
    (text || '')
      .replace(/\n{1,2}Page \d+\n{1,2}/g, ' ')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();

  // Footnotes aren't lost, just relocated: pypdf pulls them out of their
  // per-page position and appends them as their own run of paragraphs, each
  // one a bare number alone on a line followed by the footnote's text on the
  // next -- "10\nWe also disagree that the IDFPR did not..." Left alone that
  // reads as an ordinary paragraph with no visual distinction from the body.
  // This pulls anything matching that shape out and renders it as an actual
  // footnote list. What it can't do: the superscript reference marks inline
  // in the body ("...ALJ Decision).1 The ALJ...") aren't reliably
  // distinguishable from a citation's own digits, so this doesn't try to
  // link body text to its footnote -- the footnotes just move to their own
  // section instead of masquerading as body paragraphs.
  function splitFootnotes(text) {
    const paras = text.split(/\n{2,}/);
    const body = [];
    const footnotes = [];
    for (const p of paras) {
      const m = p.match(/^(\d{1,3})\n([\s\S]+)$/);
      if (m && Number(m[1]) <= 200) {
        footnotes.push({ n: Number(m[1]), text: m[2].trim() });
      } else if (/^footnotes?$/i.test(p.trim())) {
        // The source PDF's own "Footnotes" section title, extracted as an
        // ordinary paragraph since it doesn't match the numbered-entry shape
        // above. Dropped rather than kept as a body heading: the synthetic
        // footnotes section below already has its own "Footnotes" <hr>.
      } else {
        body.push(p);
      }
    }
    footnotes.sort((a, b) => a.n - b.n);
    return { body: body.join('\n\n'), footnotes };
  }

  // Section headers ("Legal Background", "II. Discussion", "C. Findings of
  // Fact, Conclusions of Law, and Analysis") are just short paragraphs with
  // no trailing punctuation -- the PDF's bold/larger type doesn't survive
  // text extraction, so nothing marks them as headings once the layout is
  // gone. A body sentence this short still ends in a period, comma, colon,
  // or citation punctuation ("42 C.F.R. § 1001.2007(a)(1)."); a heading
  // doesn't. That's the whole test -- short, no trailing punctuation, has a
  // letter in it (so a bare page/paragraph number isn't mistaken for one).
  const HEADING_MAX_LEN = 90;
  const isHeading = (p) => {
    const flat = p.replace(/\s+/g, ' ').trim();
    return flat.length > 0 && flat.length <= HEADING_MAX_LEN &&
      /[A-Za-z]/.test(flat) &&
      !/[.,;:]$/.test(flat);
  };

  function renderBody(text) {
    return text.split(/\n{2,}/).map((p) => {
      const escaped = escapeHtml(p);
      return isHeading(p) ? `<strong class="section-heading">${escaped}</strong>` : escaped;
    }).join('\n\n');
  }

  // A modal is the wrong container for a document that can run 30+ pages --
  // no browser find-in-page, no bookmarking one decision, a fixed-height
  // scroll box. A new tab gets native search/print/copy for free. This is a
  // Blob URL, not a stable link -- the shareable-permalink version is a real
  // per-decision static page generated at build time, not done here yet.
  $('#decisionsTable tbody').on('click', 'a.view-link', async (e) => {
    const id = e.target.getAttribute('data-id');
    const [row] = await query(conn,
      `SELECT decision_no, respondent, text FROM ${t} WHERE id = ? LIMIT 1`, [id]);
    if (!row) return;
    const { body, footnotes } = splitFootnotes(stripPageBreaks(row.text));
    const footnotesHtml = footnotes.length ? `
      <hr>
      <p class="section-heading">Footnotes</p>
      <ol class="footnotes">
        ${footnotes.map((f) => `<li value="${f.n}">${escapeHtml(f.text)}</li>`).join('')}
      </ol>` : '';
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8">
      <title>${escapeHtml(row.decision_no)}</title>
      <style>
        body { max-width: 760px; margin: 2rem auto; padding: 0 1.5rem;
               font-family: 'Source Sans 3', sans-serif; line-height: 1.6;
               color: #3D2B1F; white-space: pre-wrap; }
        h1 { font-family: 'DM Sans', sans-serif; font-size: 1.25rem; }
        hr { margin: 2.5rem 0 1rem; border: none; border-top: 1px solid #E8DDD0; }
        .footnotes { font-size: 0.85rem; color: #7A6E62; white-space: normal; padding-left: 1.5rem; }
        .footnotes li { margin-bottom: 0.75rem; }
        .section-heading { font-family: 'DM Sans', sans-serif; display: inline-block; margin-top: 0.5rem; }
      </style></head>
      <body><h1>${escapeHtml(row.decision_no)} &mdash; ${escapeHtml(row.respondent || '')}</h1>
      ${renderBody(body)}${footnotesHtml}</body></html>`;
    const blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    window.open(blobUrl, '_blank');
  });

  document.getElementById('loadingBanner')?.remove();
}

main().catch((err) => {
  console.error(err);
  showToast('Failed to load decisions', true);
  const banner = document.getElementById('loadingBanner');
  if (banner) {
    banner.classList.add('error');
    banner.innerHTML = '<span>Failed to load decisions. Try refreshing the page.</span>';
  }
});
