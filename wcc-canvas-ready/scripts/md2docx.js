// Build an accessible .docx from the tagged markdown produced by pdf2md/build_manual.
// Usage: node md2docx.js input.md output.docx "Document title" "Description" [imgBaseDir]
// Follows wcc-canvas-ready: real headings, real lists, 12 pt minimum,
// inline images with alt text, data tables with header rows + visible captions,
// callouts as shaded bordered paragraphs (never layout tables), left aligned.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, AlignmentType, LevelFormat,
} = require('docx');

const [, , inPath, outPath, title, description, baseDir = path.dirname(inPath)] = process.argv;
const md = fs.readFileSync(inPath, 'utf8').split(/\n\n+/).map(b => b.replace(/\s+$/, '')).filter(Boolean);

const FONT = 'Arial';
const SIZE = 24; // 12 pt
const HEAD = '1F4E79';

// inline markup: ***bi***, **b**, *i*, ^sup^
// A literal asterisk is written \* in the Markdown (the German gender star: Schüler\*innen). Without the
// backslash the * is read as italic markup and dropped (found on a bilingual GAPP form, Nov 16, 2026).
const STAR = '\uE000';
const lit = s => s.replace(new RegExp(STAR, 'g'), '*');
function runs(text, base = {}) {
  text = text.replace(/\\\*/g, STAR);
  const out = [];
  const re = /(\*\*\*[^*]+?\*\*\*|\*\*[^*]+?\*\*|\*[^*]+?\*|\^[^^\s]+\^|~[^~\s]+~)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: lit(text.slice(last, m.index)), ...base }));
    const t = m[0];
    if (t.startsWith('***')) out.push(...runs(t.slice(3, -3), { ...base, bold: true, italics: true }));
    else if (t.startsWith('**')) out.push(...runs(t.slice(2, -2), { ...base, bold: true }));
    // Panorama-safe: Unicode sub/superscript characters at full size, never vertAlign
    // (vertAlign shrinks glyphs to ~7 pt in the PDF and trips the size and reading-order checks)
    else if (t.startsWith('^')) out.push(new TextRun({ text: lit(uni(t.slice(1, -1), '⁰¹²³⁴⁵⁶⁷⁸⁹')), ...base }));
    else if (t.startsWith('~')) out.push(new TextRun({ text: lit(uni(t.slice(1, -1), '₀₁₂₃₄₅₆₇₈₉')), ...base }));
    else out.push(...runs(t.slice(1, -1), { ...base, italics: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: lit(text.slice(last).replace(/\*/g, '')), ...base }));
  return out;
}

function uni(t, set) { return t.replace(/[0-9]/g, d => set[+d]); }

const callout = {
  margin: { fill: 'E2EFDA', border: '3C5A1E' },   // glossary terms
  lo:     { fill: 'DEEAF6', border: '1F4E79' },   // learning-objective tabs
  media:  { fill: 'F2F2F2', border: '595959' },   // MyPoliSciLab notes
  box:    { fill: 'FFF2CC', border: '7A5C00' },   // feature boxes
  note:   { fill: 'FFFFFF', border: '595959' },   // footnotes
};

function calloutPara(kind, text) {
  const c = callout[kind];
  const b = { style: BorderStyle.SINGLE, size: 6, color: c.border, space: 4 };
  return new Paragraph({
    children: runs(text),
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: c.fill },
    border: { top: b, bottom: b, left: { ...b, size: 24 }, right: b },
    indent: { left: 240, right: 240 },
    spacing: { before: 120, after: 120 },
  });
}

const children = [];
let pendingDesc = null, pendingCaption = null, subGroup = 0;
const tableMeta = [];   // [caption, description] in order, for post-processing

for (let i = 0; i < md.length; i++) {
  const b = md[i];
  let m;
  if ((m = b.match(/^(#{1,4}) (.*)$/))) {
    const lv = m[1].length;
    children.push(new Paragraph({ heading: [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3, HeadingLevel.HEADING_4][lv - 1], children: runs(m[2]) }));
  } else if ((m = b.match(/^!img (\S+) \| (.*)$/))) {
    const file = path.join(baseDir, m[1]);
    const buf = fs.readFileSync(file);
    const { w, h } = jpegSize(buf);
    const maxW = 576; // 6 in at 96 px/in
    const width = Math.min(maxW, w), height = Math.round(h * width / w);
    children.push(new Paragraph({ children: [new ImageRun({ type: 'jpg', data: buf, transformation: { width, height },
      altText: { title: '', description: m[2], name: path.basename(m[1]) } })] }));
  } else if ((m = b.match(/^!caption (.*)$/))) {
    if (/^Table/.test(m[1])) pendingCaption = m[1];
    children.push(new Paragraph({ style: 'Caption', children: [new TextRun(m[1].replace(/\\\*/g, '*'))], keepNext: true }));
  } else if ((m = b.match(/^!tabledesc (.*)$/))) {
    pendingDesc = m[1];
  } else if (b.startsWith('|')) {
    const rows = b.split('\n').filter(r => !/^\|[-| ]+\|$/.test(r)).map(r => r.slice(1, -1).split('|').map(c => c.trim()));
    const ncol = rows[0].length;
    const total = 9360;
    const widths = ncol === 2 ? [3600, 5760] : colWidths(rows, total);
    const cellB = { style: BorderStyle.SINGLE, size: 4, color: '595959' };
    children.push(new Table({
      width: { size: widths.reduce((a, c) => a + c, 0), type: WidthType.DXA },
      columnWidths: widths,
      rows: rows.map((r, ri) => new TableRow({
        tableHeader: ri === 0,
        children: r.map((c, ci) => new TableCell({
          width: { size: widths[ci], type: WidthType.DXA },
          borders: { top: cellB, bottom: cellB, left: cellB, right: cellB },
          shading: ri === 0 ? { type: ShadingType.CLEAR, color: 'auto', fill: 'DEEAF6' } : undefined,
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
          children: [new Paragraph({ children: runs(c, ri === 0 ? { bold: true } : {}) })],
        })),
      })),
    }));
    tableMeta.push([pendingCaption || 'Table', pendingDesc || '']);
    pendingCaption = pendingDesc = null;
  } else if ((m = b.match(/^> \[(quote)\] (.*)$/s))) {
    children.push(new Paragraph({ style: 'Quote', children: runs(m[2]) }));
  } else if ((m = b.match(/^> \[(margin|lo|media|box|note)\] (.*)$/s))) {
    children.push(calloutPara(m[1], m[2]));
  } else if ((m = b.match(/^\s+\d+[.)] (.*)$/s))) {
    // indented "1." under a bullet: a nested numbered list that restarts for each group
    if (!(i > 0 && /^\s+\d+[.)] /.test(md[i - 1]))) subGroup++;
    children.push(new Paragraph({ numbering: { reference: 'sub', level: 0, instance: subGroup }, children: runs(m[1]) }));
  } else if ((m = b.match(/^\s+[-*] (.*)$/s))) {
    children.push(new Paragraph({ numbering: { reference: 'bullets', level: 1 }, children: runs(m[1]) }));
  } else if ((m = b.match(/^- (.*)$/s))) {
    children.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: runs(m[1]) }));
  } else if ((m = b.match(/^1\. (.*)$/s))) {
    // a "1." block followed by lettered options is a quiz question; LO items start with **2.x**
    if (/^\*\*\d\.\d\*\*/.test(m[1])) children.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: runs(m[1]) }));
    else children.push(new Paragraph({ numbering: { reference: 'quiz', level: 0 }, children: runs(m[1]) }));
  } else if ((m = b.match(/^\s+a\) (.*)$/s))) {
    children.push(new Paragraph({ numbering: { reference: 'quiz', level: 1 }, children: runs(m[1]) }));
  } else {
    children.push(new Paragraph({ children: runs(b.replace(/\n/g, ' ')) }));
  }
}

// Column widths from the content (3+ columns). Equal widths split long words mid-word in narrow columns
// ("Sportveranstaltung|en", "sometim|es" in a check-box grid), which changes the words a screen reader hears.
// Each column gets at least its longest word (bold header words count wider); the rest of the width goes
// to the columns with the most text. Twips: about 135 per character at 12 pt Arial, 150 bold, plus cell margins.
function colWidths(rows, total) {
  const clean = c => c.replace(/\\\*/g, '*').replace(/\*+/g, '');
  const ncol = rows[0].length;
  const need = Array(ncol).fill(0), text = Array(ncol).fill(0);
  rows.forEach((r, ri) => r.forEach((c, ci) => {
    const words = clean(c).split(/\s+/).filter(Boolean);
    const longest = Math.max(0, ...words.map(w => w.length));
    need[ci] = Math.max(need[ci], longest * (ri === 0 ? 150 : 135) + 260);
    text[ci] += clean(c).length;
  }));
  let w = need.map(n => Math.max(n, 900));
  const spare = total - w.reduce((a, c) => a + c, 0);
  if (spare > 0) {
    const sumT = text.reduce((a, c) => a + c, 0) || 1;
    w = w.map((x, i) => x + Math.floor(spare * text[i] / sumT));
  } else {
    w = w.map(x => Math.floor(x * total / (total - spare)));   // too wide: shrink evenly (rare)
  }
  return w;
}

function jpegSize(buf) {
  let i = 2;
  while (i < buf.length) {
    if (buf[i] !== 0xFF) { i++; continue; }
    const marker = buf[i + 1];
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xC0 && marker <= 0xC3) return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
    i += 2 + len;
  }
  throw new Error('no JPEG size');
}

const hStyle = (id, name, size, before) => ({
  id, name, basedOn: 'Normal', next: 'Normal', quickFormat: true,
  run: { font: FONT, size, bold: true, color: HEAD },
  paragraph: { spacing: { before, after: 120 }, keepNext: true, outlineLevel: Number(id.slice(-1)) - 1 },
});

const doc = new Document({
  title, description, creator: ' ', lastModifiedBy: ' ',
  styles: {
    default: { document: { run: { font: FONT, size: SIZE }, paragraph: { spacing: { after: 160, line: 288, lineRule: 'auto' } } } },
    paragraphStyles: [
      hStyle('Heading1', 'Heading 1', 40, 240), hStyle('Heading2', 'Heading 2', 32, 360),
      hStyle('Heading3', 'Heading 3', 28, 280), hStyle('Heading4', 'Heading 4', 24, 200),
      { id: 'Caption', name: 'Caption', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: '262626' }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true } },
      { id: 'Quote', name: 'Quote', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 24, italics: true, color: '262626' },
        paragraph: { indent: { left: 720, right: 720 }, spacing: { before: 120, after: 160 } } },
    ],
  },
  numbering: { config: [
    { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } }, run: { size: SIZE } } },
      { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 1440, hanging: 360 } }, run: { size: SIZE } } }] },
    { reference: 'sub', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 1440, hanging: 360 } }, run: { size: SIZE } } }] },
    { reference: 'quiz', levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } }, run: { size: SIZE } } },
      { level: 1, format: LevelFormat.LOWER_LETTER, text: '%2.', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1440, hanging: 360 } }, run: { size: SIZE } } },
    ] },
  ] },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } }, children }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  fs.writeFileSync(outPath + '.tables.json', JSON.stringify(tableMeta));
  console.log('wrote', outPath, 'blocks', md.length, 'tables', tableMeta.length);
});
