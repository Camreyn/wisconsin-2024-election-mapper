import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import XLSX from "xlsx";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function parseArgs(argv = process.argv.slice(2)) {
  const args = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) continue;
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key.slice(2), "true");
    } else {
      args.set(key.slice(2), next);
      index += 1;
    }
  }
  return args;
}

function projectPath(value) {
  return path.isAbsolute(value) ? value : path.join(root, value);
}

function readWorkbook(item) {
  const workbook = XLSX.readFile(projectPath(item.path), { cellDates: false });
  const sheetName = item.sheet || workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) {
    throw new Error(`Could not find sheet "${sheetName}" in ${item.path}`);
  }
  const output = {
    id: item.id || path.basename(item.path),
    path: item.path,
    sheet: sheetName,
    rows: XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" }),
  };
  if (item.allSheets) {
    output.sheets = workbook.SheetNames.map((name) => ({
      name,
      rows: XLSX.utils.sheet_to_json(workbook.Sheets[name], { header: 1, defval: "" }),
    }));
  }
  return output;
}

function main() {
  const args = parseArgs();
  const manifestPath = args.get("manifest");
  if (!manifestPath) {
    console.error("Usage: node scripts/read-legacy-xls.mjs --manifest path/to/manifest.json");
    process.exit(2);
  }

  const manifest = JSON.parse(fs.readFileSync(projectPath(manifestPath), "utf8"));
  const workbooks = manifest.map(readWorkbook);
  process.stdout.write(`${JSON.stringify({ workbooks })}\n`);
}

main();
