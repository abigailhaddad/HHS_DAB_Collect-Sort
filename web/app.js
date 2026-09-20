import { initDb, query, tableRef } from './db.js';

// Swap this for the R2 URL once the file is uploaded there (Cloudflare Pages
// caps a single static asset at 25 MiB on the Free plan; this file is ~63 MB,
// same reason usajobs_historical serves its Parquet from R2 instead of the
// Pages deploy itself). Relative path works for local dev via
// `python3 -m http.server`.
const PARQUET_URL = './data/decisions.parquet';

const TRIBUNAL_LABEL = { alj: 'ALJ (Civil Remedies)', dab: 'Appellate Division' };

const CATEGORY_COLUMNS = [
  { label: 'Decision #', field: 'decision_no', filterType: 'text', index: 0 },
  { label: 'Tribunal', field: 'corpus', filterType: 'multiselect', index: 1 },
  { label: 'Year', field: 'year', filterType: 'multiselect', index: 2 },
  { label: 'Respondent', field: 'respondent', filterType: 'text', index: 4 },
  { label: 'Category', field: 'categories', filterType: 'multiselect', index: 5 },
  { label: 'Disposition', field: 'dispositions', filterType: 'multiselect', index: 6 },
  { label: 'Judges', field: 'judges', filterType: 'multiselect', index: 7 },
  { label: 'Provider IDs', field: 'provider_ids', filterType: 'text', index: 8 },
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

async function main() {
  const conn = await initDb(PARQUET_URL);
  const t = tableRef(conn);

  const rows = await query(conn, `
    SELECT id, decision_no, corpus, year,
           CAST(decision_date AS VARCHAR) AS decision_date,
           respondent, judges, dispositions, provider_ids, categories, source_url
    FROM ${t}
    ORDER BY decision_date DESC NULLS LAST
  `);

  const tableData = rows.map((r) => [
    r.decision_no || '',
    TRIBUNAL_LABEL[r.corpus] || r.corpus,
    r.year,
    r.decision_date || '',
    r.respondent || '',
    joined(r.categories),
    joined(r.dispositions),
    joined(r.judges),
    toArr(r.provider_ids).join(', '),
    `<a class="view-link" data-id="${escapeHtml(r.id)}">View</a>`,
    r.source_url
      ? `<a href="${escapeHtml(r.source_url)}" target="_blank" rel="noopener">Source &#8599;</a>`
      : '',
  ]);

  const [stats] = await query(conn, `
    SELECT COUNT(*) AS total,
           COUNT(DISTINCT corpus) AS tribunals,
           CAST(MIN(decision_date) AS VARCHAR) AS min_date,
           CAST(MAX(decision_date) AS VARCHAR) AS max_date
    FROM ${t}
  `);
  const [{ n: categoryCount }] = await query(conn, `
    SELECT COUNT(DISTINCT c) AS n
    FROM ${t}, LATERAL (SELECT unnest(categories) AS c)
  `);
  document.getElementById('statTotal').textContent = Number(stats.total).toLocaleString();
  document.getElementById('statTribunals').textContent = stats.tribunals;
  document.getElementById('statCategories').textContent = categoryCount;
  document.getElementById('statDateRange').textContent =
    stats.min_date && stats.max_date ? `${stats.min_date} – ${stats.max_date}` : '–';

  initDataTableWithFilters({
    tableSelector: '#decisionsTable',
    tableOptions: {
      data: tableData,
      columns: [
        { data: 0 }, { data: 1 }, { data: 2 }, { data: 3 }, { data: 4 },
        { data: 5 }, { data: 6 }, { data: 7 }, { data: 8 },
        { data: 9, orderable: false }, { data: 10, orderable: false },
      ],
      order: [[3, 'desc']],
      pageLength: 25,
    },
    fieldTypes: Object.fromEntries(CATEGORY_COLUMNS.map((c) => [c.field, c.filterType])),
    columns: CATEGORY_COLUMNS,
    csvFilename: 'hhs_dab_decisions.csv',
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
}

main().catch((err) => {
  console.error(err);
  showToast('Failed to load decisions', true);
});
