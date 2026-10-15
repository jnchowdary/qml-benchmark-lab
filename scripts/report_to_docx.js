#!/usr/bin/env node
/**
 * Turn a weekly record in Markdown into the .docx that gets shared.
 *
 * WHY THIS EXISTS
 * ---------------
 * Weeks 1 to 3 were transcribed into Word by hand. That is fine once and a
 * liability by week 12: a record and its document drift, and the drift is
 * invisible because nobody diffs a .docx against a .md. It also repeats the
 * step that produced two of week 4's ten logged errors, both of which came
 * from copying numbers out of one representation into another.
 *
 * So the document is generated from the record, and the record stays the
 * single source of truth.
 *
 * WHAT IT MATCHES, AND WHAT IT DELIBERATELY DOES NOT
 * ---------------------------------------------------
 * It reproduces the visual style of the week 1 to 3 documents: a bold wordmark,
 * the week line, the metadata block, bold section headings, tables with a
 * shaded header row. It differs in one respect: headings use the built-in Word
 * heading styles rather than bold body text, so the document has a navigation
 * pane and can carry a table of contents. At fifteen sections that is worth the
 * small divergence, and it looks the same on the page.
 *
 * Usage:
 *   node scripts/report_to_docx.js docs/week-04-report.md "QML-Benchmark-Lab-Week-4.docx"
 */

const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
} = require('docx');

const PAGE = { width: 12240, height: 15840 };          // US Letter, DXA
const CONTENT_WIDTH = PAGE.width - 1440 * 2;

/** Inline **bold**, `code` and _italic_ into TextRuns. */
function runs(text, base = {}) {
  const out = [];
  // No underscore-italics rule. These records are full of identifiers and
  // subscripts (K_ij, n_qubits, iqp-r1), and an eager _.._ rule silently ate
  // "K_ij = prod_d" into an italic span, deleting both underscores from the
  // rendered formula. Italics via *single asterisks* only.
  const re = /(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*\n]+\*(?![*\w]))/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    const tok = m[0];
    if (tok.startsWith('**')) {
      out.push(new TextRun({ ...base, text: tok.slice(2, -2), bold: true }));
    } else if (tok.startsWith('`')) {
      out.push(new TextRun({ ...base, text: tok.slice(1, -1), font: 'Consolas', size: 19 }));
    } else {
      out.push(new TextRun({ ...base, text: tok.slice(1, -1), italics: true }));
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ ...base, text: text.slice(last) }));
  return out.length ? out : [new TextRun({ ...base, text: '' })];
}

function cells(row) {
  // Split on UNESCAPED pipes only, then unescape. A cell containing \| -- which
  // is how |d| is written inside a markdown table -- previously split into extra
  // cells, widths[i] came back undefined, and the docx library threw
  // "Cannot read properties of undefined (reading 'slice')" from inside
  // createTableWidthElement. Nothing in that message names the row, the file or
  // the escaped pipe.
  return row.trim()
    .replace(/^\s*\|/, '').replace(/\|\s*$/, '')
    .split(/(?<!\\)\|/)
    .map(c => c.trim().replace(/\\\|/g, '|'));
}

function buildTable(header, rows, lineNo) {
  const n = header.length;
  // A row whose cell count differs from the header's is a defect in the record,
  // and it must be named here rather than surfacing as a TypeError from inside
  // the docx package. Same principle as the audit reporting a missing field by
  // name instead of letting a KeyError read as a failed experiment.
  rows.forEach((r, k) => {
    if (r.length !== n) {
      console.error(
        `\n  TABLE ERROR in ${process.argv[2]}: the table whose header is on ` +
        `line ${lineNo ?? '?'} has ${n} columns,\n  but data row ${k + 1} has ` +
        `${r.length}. An unescaped | inside a cell is the usual cause.\n` +
        `  row: ${r.join(' | ')}\n`);
      process.exit(2);
    }
  });
  const w = Math.floor(CONTENT_WIDTH / n);
  const widths = Array(n).fill(w);
  widths[n - 1] = CONTENT_WIDTH - w * (n - 1);          // must sum to the table width

  const mkCell = (text, i, isHeader) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: isHeader
      ? { type: ShadingType.CLEAR, fill: 'EDEDED' }     // never SOLID: renders black
      : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      spacing: { before: 0, after: 0 },
      children: runs(text, { size: 19, bold: isHeader }),
    })],
  });

  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    rows: [
      new TableRow({ tableHeader: true, children: header.map((c, i) => mkCell(c, i, true)) }),
      ...rows.map(r => new TableRow({ children: r.map((c, i) => mkCell(c, i, false)) })),
    ],
  });
}

function convert(md) {
  const lines = md.split('\n');
  const body = [];
  let i = 0, titleDone = false;

  while (i < lines.length) {
    const line = lines[i];

    if (/^\s*$/.test(line)) { i++; continue; }

    // horizontal rules become spacing, as in the week 1-3 documents
    if (/^---+\s*$/.test(line)) {
      body.push(new Paragraph({ spacing: { before: 120, after: 120 }, children: [] }));
      i++; continue;
    }

    // tables
    if (/^\s*\|/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const headerLine = i + 1;          // 1-indexed, for the error message
      const header = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(cells(lines[i])); i++; }
      body.push(buildTable(header, rows, headerLine));
      body.push(new Paragraph({ spacing: { after: 160 }, children: [] }));
      continue;
    }

    // title: "# QML Benchmark Lab: Week 4 Record"
    const h1 = line.match(/^#\s+(.*)$/);
    if (h1 && !titleDone) {
      const [lead, ...rest] = h1[1].split(':');
      body.push(new Paragraph({
        spacing: { after: 0 },
        children: [new TextRun({ text: lead.trim(), bold: true, size: 32 })],
      }));
      if (rest.length) {
        body.push(new Paragraph({
          spacing: { after: 240 },
          children: [new TextRun({ text: rest.join(':').trim(), size: 26 })],
        }));
      }
      titleDone = true; i++; continue;
    }

    const h3 = line.match(/^###\s+(.*)$/);
    if (h3) {
      body.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: runs(h3[1], { bold: true, size: 22, color: '000000' }),
      }));
      i++; continue;
    }

    const h2 = line.match(/^##\s+(.*)$/);
    if (h2) {
      body.push(new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 280, after: 140 },
        children: runs(h2[1], { bold: true, size: 24, color: '000000' }),
      }));
      i++; continue;
    }

    // blockquote
    const q = line.match(/^>\s?(.*)$/);
    if (q) {
      const parts = [q[1]];
      i++;
      while (i < lines.length && /^>/.test(lines[i])) { parts.push(lines[i].replace(/^>\s?/, '')); i++; }
      body.push(new Paragraph({
        indent: { left: 360 },
        spacing: { before: 120, after: 120 },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: '999999', space: 8 } },
        children: runs(parts.join(' '), { italics: true }),
      }));
      continue;
    }

    // bullets and numbered items
    const b = line.match(/^(\s*)[-*]\s+(.*)$/);
    const nlist = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
    if (b || nlist) {
      const text = b ? b[2] : `${nlist[2]}.  ${nlist[3]}`;
      body.push(new Paragraph({
        bullet: b ? { level: 0 } : undefined,
        indent: nlist ? { left: 360, hanging: 240 } : undefined,
        spacing: { after: 80 },
        children: runs(text),
      }));
      i++; continue;
    }

    // four-space indented block: code, rendered monospace and unwrapped
    if (/^ {4}\S/.test(line)) {
      while (i < lines.length && (/^ {4}/.test(lines[i]) || /^\s*$/.test(lines[i]))) {
        if (lines[i].trim()) {
          body.push(new Paragraph({
            spacing: { before: 40, after: 40 },
            indent: { left: 360 },
            children: [new TextRun({ text: lines[i].replace(/^ {4}/, ''),
                                     font: 'Consolas', size: 19 })],
          }));
        }
        i++;
        if (i < lines.length && /^\s*$/.test(lines[i]) &&
            !(i + 1 < lines.length && /^ {4}\S/.test(lines[i + 1]))) break;
      }
      body.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    }

    // paragraph: join continuation lines
    const parts = [line.trim()];
    i++;
    while (i < lines.length && lines[i].trim() && !/^[#>|-]|^\s*[-*]\s|^\s*\d+\.\s/.test(lines[i])) {
      parts.push(lines[i].trim()); i++;
    }
    body.push(new Paragraph({
      spacing: { after: 140 },
      alignment: AlignmentType.LEFT,
      children: runs(parts.join(' ')),
    }));
  }
  return body;
}

// --- exported for reuse -----------------------------------------------------
// scripts/paper_to_docx.js reuses runs(), cells(), buildTable() and
// recordProvenance() from this file instead of copying them, so that the
// escaped-pipe fix in cells() and the no-underscore-italics rule in runs()
// stay in one place rather than in two that drift. Requiring this file must
// therefore not run a weekly export, hence the guard below.
//
// Nothing after the guard is changed. The guard only stops the export block
// running when this file is required rather than invoked. docs/week-04-report
// and docs/deviations were regenerated after this edit and their
// word/document.xml compared byte for byte against the versions built before
// it; both were identical, so the ten existing exports are unaffected.
module.exports = { runs, cells, buildTable, convert, recordProvenance,
                   PAGE, CONTENT_WIDTH };

if (require.main !== module) return;   // legal at CommonJS module scope

const [, , mdPath, outPath] = process.argv;
if (!mdPath || !outPath) {
  console.error('usage: node scripts/report_to_docx.js <record.md> <output.docx>');
  process.exit(1);
}

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
      heading1: { run: { font: 'Calibri', size: 24, bold: true, color: '000000' } },
      heading2: { run: { font: 'Calibri', size: 22, bold: true, color: '000000' } },
    },
  },
  sections: [{
    properties: { page: { size: PAGE, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    children: convert(fs.readFileSync(mdPath, 'utf8')),
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log(`${outPath}  ${buf.length} bytes`);
  recordProvenance(mdPath, outPath);
});

/**
 * Append this export to docs/docx-manifest.json.
 *
 * WHY. The header of this file argues that a record and its document drift and
 * that the drift is invisible because nobody diffs a .docx against a .md. That
 * argument was right and the drift happened anyway: on 15 October 2026
 * `deviations.docx` was found sixteen days behind a record that had grown by
 * roughly 1,400 lines, because generating the document was a step someone had
 * to remember. A generator with no freshness check is a convention, not a
 * guarantee.
 *
 * So each export records the SHA-256 of the markdown it was built from, and
 * `scripts/check_docx_fresh.py` fails when a source has moved since. mtime
 * cannot do this job: a fresh clone gives every file the checkout time, so a
 * stale export in a clone looks current. A content hash survives cloning.
 */
function recordProvenance(src, out) {
  const path = require('path');
  const crypto = require('crypto');
  const { execFileSync } = require('child_process');
  const root = path.resolve(__dirname, '..');
  const rel = (f) => path.relative(root, path.resolve(f)).split(path.sep).join('/');
  const manifestPath = path.join(root, 'docs', 'docx-manifest.json');

  let manifest = {};
  if (fs.existsSync(manifestPath)) {
    try {
      manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8')).exports || {};
    } catch (e) {
      console.error(`  manifest unreadable (${e.message}); not overwriting it.`);
      return;
    }
  }

  // rev-parse only. It does not touch .git/index, unlike `git status`.
  let commit = null;
  try {
    commit = execFileSync('git', ['rev-parse', '--short', 'HEAD'],
                          { cwd: root, encoding: 'utf8' }).trim();
  } catch (e) { /* not a checkout; leave null */ }

  let docxVersion = null;
  try {
    const pj = path.join(path.dirname(require.resolve('docx')), '..', 'package.json');
    docxVersion = JSON.parse(fs.readFileSync(pj, 'utf8')).version;
  } catch (e) { /* exports-restricted or absent; leave null */ }

  manifest[rel(out)] = {
    source: rel(src),
    source_sha256: crypto.createHash('sha256')
      .update(fs.readFileSync(src)).digest('hex'),
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    generator_commit: commit,
    docx_version: docxVersion,
  };

  const ordered = {};
  for (const k of Object.keys(manifest).sort()) ordered[k] = manifest[k];
  fs.writeFileSync(manifestPath, JSON.stringify({
    note: 'Written by scripts/report_to_docx.js. Checked by ' +
          'scripts/check_docx_fresh.py, which fails when a source markdown has ' +
          'changed since its export. An export with no entry here has ' +
          'unrecorded provenance and is reported as such rather than assumed ' +
          'current.',
    exports: ordered,
  }, null, 2) + '\n');
  console.log(`  provenance -> docs/docx-manifest.json`);
}
