import fs from "node:fs";
import { pathToFileURL } from "node:url";

globalThis.DOMMatrix = class {
  multiplySelf() { return this; }
  translateSelf() { return this; }
  scaleSelf() { return this; }
  rotateSelf() { return this; }
  invertSelf() { return this; }
  transformPoint(point) { return point; }
};
globalThis.ImageData = class {};
globalThis.Path2D = class {};

const input = process.argv[2];
if (!input) {
  console.error("Usage: node scripts/extract-pdf-text.mjs path/to/file.pdf");
  process.exit(2);
}

const pdfjsPath = "./node_modules/pdfjs-dist/legacy/build/pdf.mjs";
const pdfjs = await import(pathToFileURL(pdfjsPath));
const data = new Uint8Array(fs.readFileSync(input));
const document = await pdfjs.getDocument({ data, disableWorker: true }).promise;
const output = [];

for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
  const page = await document.getPage(pageNumber);
  const text = await page.getTextContent();
  const lines = new Map();
  for (const item of text.items) {
    const value = String(item.str || "").trim();
    if (!value) continue;
    const x = item.transform?.[4] || 0;
    const y = Math.round(item.transform?.[5] || 0);
    if (!lines.has(y)) lines.set(y, []);
    lines.get(y).push({ x, value });
  }
  for (const [, items] of [...lines.entries()].sort((a, b) => b[0] - a[0])) {
    output.push(items.sort((a, b) => a.x - b.x).map((item) => item.value).join(" "));
  }
}

process.stdout.write(`${output.join("\n")}\n`);
