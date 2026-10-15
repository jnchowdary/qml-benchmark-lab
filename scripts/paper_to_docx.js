#!/usr/bin/env node
/**
 * Turn docs/paper.md into the .docx that gets read in Word.
 *
 * WHY A SECOND GENERATOR AND NOT A FLAG ON THE FIRST
 * --------------------------------------------------
 * `scripts/report_to_docx.js` was written for a weekly record: one `#` title,
 * then `##` sections mapped to Word's Heading 1 and `###` to Heading 2. The
 * assembled paper is a different shape. It has ten `#` parts (the title, the
 * abstract, seven sections and the references), 44 `##` subsections and five
 * `###` sub-subsections, so it needs three heading levels where a weekly record
 * needs two.
 *
 * Giving the weekly generator a level offset would have shifted every heading in
 * the ten existing exports by one. That matters more than it looks: a change to
 * the generator is invisible to `scripts/check_docx_fresh.py`, which hashes the
 * SOURCE markdown and not the generator, so all ten would still have been
 * reported CURRENT while their output had silently changed. A separate entry
 * point leaves them alone.
 *
 * It is not a copy. `runs()`, `cells()`, `buildTable()` and
 * `recordProvenance()` are imported from `report_to_docx.js`, so the escaped-pipe
 * fix, the no-underscore-italics rule and the provenance format live in one
 * place. Only the block loop differs, because only the block structure differs.
 *
 * WHAT report_to_docx.js WOULD HAVE DONE TO THIS PAPER
 * ----------------------------------------------------
 * Run unchanged on `docs/paper.md` it does not fail. It produces a document
 * that is quietly wrong in two ways, which is worse:
 *
 *   * Only the first `#` becomes a title. The other nine fall through to the
 *     paragraph branch and are typeset as body text reading `# Abstract`,
 *     `# Section 1 - Introduction` and so on: no heading style, no navigation
 *     pane, no table of contents.
 *   * There is no image rule, so each of the three figure lines is typeset as
 *     its own markdown source, `![Figure 2 - ...](../results/figures/...png)`.
 *     The figures do not appear and the lines read as typing errors.
 *
 * Both are the same failure: markdown syntax surviving into the document. So
 * this file checks for exactly that before writing anything -- see
 * `assertNoLeaks` -- and exits naming the source line rather than handing over a
 * document a reader has to proofread for markup.
 *
 * WHAT IT DOES NOT DO
 * -------------------
 * It adds no author line, no date and no affiliation. `docs/paper.md` carries
 * none, and a generator that invents them makes the document assert something
 * its source does not. If the paper should carry an author block, it belongs in
 * the markdown, where `scripts/assemble_paper.py --check` can see it.
 *
 * Usage:
 *   node scripts/paper_to_docx.js docs/paper.md "QML-Benchmark-Lab-Paper.docx"
 */

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  ImageRun, TableOfContents, Footer, PageNumber, BorderStyle,
} = require('docx');

const {
  runs, cells, buildTable, recordProvenance, PAGE, CONTENT_WIDTH,
} = require('./report_to_docx.js');

// 6.5in of content at 96 px/in. docx takes ImageRun dimensions in pixels.
const IMG_MAX_PX = Math.round((CONTENT_WIDTH / 1440) * 96);

/* ------------------------------------------------------------------ *
 * The leak check.
 *
 * Every construct this file does not recognise falls through to the
 * paragraph branch and is typeset verbatim. That is how nine headings
 * and three figures would have become literal markup. So each piece of
 * text that reaches a paragraph is recorded with its source line, and
 * the markers below are refused before the file is written. A missing
 * figure is then a build failure rather than something a reader finds.
 * ------------------------------------------------------------------ */
const LEAKS = [
  [/!\[/,                 'image markup'],
  [/^\s{0,3}#{1,6}\s/,    'heading markup'],
  [/^\s*```/,             'fenced code block'],
  [/\]\(/,                'link markup'],
];

const emitted = [];
function emit(lineNo, text) { emitted.push([lineNo, text]); return text; }

function assertNoLeaks(mdPath) {
  const bad = [];
  for (const [lineNo, text] of emitted) {
    for (const [re, what] of LEAKS) {
      if (re.test(text)) {
        bad.push(`    line ${lineNo}: ${what} survived into the document\n` +
                 `      ${text.slice(0, 100)}`);
        break;
      }
    }
  }
  if (bad.length) {
    console.error(
      `\n  MARKUP LEAK in ${mdPath}: ${bad.length} place(s) would have been\n` +
      `  typeset as markdown source rather than rendered. Nothing was written.\n\n` +
      bad.join('\n') + '\n');
    process.exit(2);
  }
}

/** Width and height from a PNG's IHDR, or null if it is not a PNG. */
function pngSize(buf) {
  if (buf.length < 24 || buf.readUInt32BE(0) !== 0x89504e47) return null;
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

/**
 * An image line becomes the picture, scaled to the text width, followed by its
 * alt text as a centred caption. The alt text in docs/paper-results.md already
 * reads "Figure 2 - ...", so the caption is the alt text and not a number this
 * script invents; renumbering a figure in the markdown renumbers it here.
 */
function imageBlocks(alt, url, mdDir, lineNo) {
  const abs = path.resolve(mdDir, url);
  if (!fs.existsSync(abs)) {
    console.error(`\n  MISSING FIGURE referenced on line ${lineNo}: ${url}\n` +
                  `  resolved to ${abs}\n  Nothing was written. Re-run ` +
                  `scripts/make_figures.py.\n`);
    process.exit(2);
  }
  const data = fs.readFileSync(abs);
  const size = pngSize(data);
  if (!size) {
    console.error(`\n  NOT A PNG: ${url} (line ${lineNo}). Only PNG is ` +
                  `embedded; the .svg companions are not.\n`);
    process.exit(2);
  }
  const w = Math.min(IMG_MAX_PX, size.w);
  const h = Math.round(size.h * (w / size.w));
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 80 },
      children: [new ImageRun({ type: 'png', data, transformation: { width: w, height: h } })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
      children: runs(alt, { size: 18, italics: true, color: '444444' }),
    }),
  ];
}

function convertPaper(md, mdDir) {
  const lines = md.split('\n');
  const body = [];
  let i = 0, titleDone = false, tocDone = false;

  const tocBlock = () => [
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      pageBreakBefore: true,
      spacing: { after: 200 },
      children: [new TextRun({ text: 'Contents', bold: true, size: 26 })],
    }),
    new TableOfContents('Contents', { hyperlinks: true, headingStyleRange: '1-3' }),
  ];

  while (i < lines.length) {
    const line = lines[i];
    const lineNo = i + 1;

    if (/^\s*$/.test(line)) { i++; continue; }

    if (/^---+\s*$/.test(line)) {
      body.push(new Paragraph({ spacing: { before: 120, after: 120 }, children: [] }));
      i++; continue;
    }

    // figures. Must precede the paragraph branch, which is what currently
    // swallows these lines in the weekly generator.
    const img = line.match(/^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$/);
    if (img) {
      body.push(...imageBlocks(img[1], img[2], mdDir, lineNo));
      i++; continue;
    }

    // tables (shared with the weekly generator, escaped-pipe handling included)
    if (/^\s*\|/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const headerLine = i + 1;
      const header = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(cells(lines[i])); i++; }
      header.forEach(c => emit(headerLine, c));
      rows.forEach(r => r.forEach(c => emit(headerLine, c)));
      body.push(buildTable(header, rows, headerLine));
      body.push(new Paragraph({ spacing: { after: 160 }, children: [] }));
      continue;
    }

    const h1 = line.match(/^#\s+(.*)$/);
    const h2 = line.match(/^##\s+(.*)$/);
    const h3 = line.match(/^###\s+(.*)$/);

    // the paper title, split at the colon as the weekly documents do
    if (h1 && !h2 && !titleDone) {
      const [lead, ...rest] = h1[1].split(':');
      body.push(new Paragraph({
        spacing: { after: 0 },
        children: [new TextRun({ text: emit(lineNo, lead.trim()), bold: true, size: 36 })],
      }));
      if (rest.length) {
        body.push(new Paragraph({
          spacing: { after: 360 },
          children: [new TextRun({ text: emit(lineNo, rest.join(':').trim()), size: 26 })],
        }));
      }
      titleDone = true; i++; continue;
    }

    // every later `#` is a part of the paper: a real Heading 1, on a new page.
    // The table of contents goes in front of the first of them, so page one
    // stays the title and the provenance block that follows it in the markdown.
    if (h1 && !h2) {
      if (!tocDone) { body.push(...tocBlock()); tocDone = true; }
      body.push(new Paragraph({
        heading: HeadingLevel.HEADING_1,
        pageBreakBefore: true,
        spacing: { before: 0, after: 200 },
        children: runs(emit(lineNo, h1[1]), { bold: true, size: 26, color: '000000' }),
      }));
      i++; continue;
    }

    if (h3) {
      body.push(new Paragraph({
        heading: HeadingLevel.HEADING_3,
        spacing: { before: 200, after: 100 },
        children: runs(emit(lineNo, h3[1]), { bold: true, size: 21, color: '000000' }),
      }));
      i++; continue;
    }

    if (h2) {
      body.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 280, after: 140 },
        children: runs(emit(lineNo, h2[1]), { bold: true, size: 23, color: '000000' }),
      }));
      i++; continue;
    }

    const q = line.match(/^>\s?(.*)$/);
    if (q) {
      const parts = [q[1]];
      i++;
      while (i < lines.length && /^>/.test(lines[i])) { parts.push(lines[i].replace(/^>\s?/, '')); i++; }
      body.push(new Paragraph({
        indent: { left: 360 },
        spacing: { before: 120, after: 120 },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: '999999', space: 8 } },
        children: runs(emit(lineNo, parts.join(' ')), { italics: true }),
      }));
      continue;
    }

    const b = line.match(/^(\s*)[-*]\s+(.*)$/);
    const nlist = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
    if (b || nlist) {
      const text = b ? b[2] : `${nlist[2]}.  ${nlist[3]}`;
      body.push(new Paragraph({
        bullet: b ? { level: 0 } : undefined,
        indent: nlist ? { left: 360, hanging: 240 } : undefined,
        spacing: { after: 80 },
        children: runs(emit(lineNo, text)),
      }));
      i++; continue;
    }

    // four-space indented block: equations and identifiers, monospace, unwrapped
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
    const startedAt = lineNo;
    i++;
    while (i < lines.length && lines[i].trim() &&
           !/^[#>|-]|^\s*[-*]\s|^\s*\d+\.\s|^\s*!\[/.test(lines[i])) {
      parts.push(lines[i].trim()); i++;
    }
    body.push(new Paragraph({
      spacing: { after: 140 },
      alignment: AlignmentType.LEFT,
      children: runs(emit(startedAt, parts.join(' '))),
    }));
  }

  if (!titleDone) {
    console.error('\n  No `# ` title found. Is this docs/paper.md?\n');
    process.exit(2);
  }
  return body;
}

const [, , mdPath, outPath] = process.argv;
if (!mdPath || !outPath) {
  console.error('usage: node scripts/paper_to_docx.js <paper.md> <output.docx>');
  process.exit(1);
}

const md = fs.readFileSync(mdPath, 'utf8');
const children = convertPaper(md, path.dirname(path.resolve(mdPath)));
assertNoLeaks(mdPath);

const doc = new Document({
  // Word then offers to update the table of contents on open, instead of
  // showing an empty one until somebody presses F9.
  features: { updateFields: true },
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
      heading1: { run: { font: 'Calibri', size: 26, bold: true, color: '000000' } },
      heading2: { run: { font: 'Calibri', size: 23, bold: true, color: '000000' } },
      heading3: { run: { font: 'Calibri', size: 21, bold: true, color: '000000' } },
    },
  },
  sections: [{
    properties: { page: { size: PAGE, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '777777' })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  const nImg = emitted.length;   // only used to keep the summary honest below
  console.log(`${outPath}  ${buf.length} bytes`);
  console.log(`  ${children.length} blocks from ${md.split('\n').length} ` +
              `source lines; ${nImg} text pieces checked for leaked markup`);
  recordProvenance(mdPath, outPath);
});
