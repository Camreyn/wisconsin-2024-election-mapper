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
const firstPage = process.argv[3] ? Number(process.argv[3]) : null;
const lastPage = process.argv[4] ? Number(process.argv[4]) : firstPage;

if (!input) {
  console.error("Usage: node scripts/extract-pdf-items.mjs path/to/file.pdf [firstPage] [lastPage]");
  process.exit(2);
}

const pdfjsPath = "./node_modules/pdfjs-dist/legacy/build/pdf.mjs";
const pdfjs = await import(pathToFileURL(pdfjsPath));
const data = new Uint8Array(fs.readFileSync(input));
const document = await pdfjs.getDocument({ data, disableWorker: true }).promise;
const pages = [];
const start = firstPage || 1;
const end = lastPage || document.numPages;

for (let pageNumber = start; pageNumber <= Math.min(end, document.numPages); pageNumber += 1) {
  const page = await document.getPage(pageNumber);
  const text = await page.getTextContent();
  pages.push({
    pageNumber,
    items: text.items
      .map((item) => {
        const value = String(item.str || "").trim();
        if (!value) return null;
        return {
          value,
          x: item.transform?.[4] || 0,
          y: item.transform?.[5] || 0,
          width: item.width || 0,
        };
      })
      .filter(Boolean),
  });
}

process.stdout.write(`${JSON.stringify({ pages })}\n`);
