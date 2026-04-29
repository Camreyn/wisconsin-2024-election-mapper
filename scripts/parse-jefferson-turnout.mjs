import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const input = path.join(root, "data", "jefferson-2024-general-result.html");
const output = path.join(root, "data", "jefferson-county-turnout.csv");
const sourceUrl = "https://apps.jeffersoncountywi.gov/jc/election/results/11052024";
const note = "Jefferson County hosted 2024 Fall General Election results page. Registered-voter denominator timing is not stated, so the app treats it as unknown and warning-gated.";

const html = fs.readFileSync(input, "utf8");
const tableStart = html.indexOf("<td class=' '>Registered Voters</td>");
const tableEnd = html.indexOf("PROVISIONALS OUTSTANDING", tableStart);

if (tableStart === -1 || tableEnd === -1) {
  throw new Error("Could not locate Jefferson County ballot-total precinct table.");
}

const tableHtml = html.slice(tableStart, tableEnd);
const rowPattern = /<tr>\s*<td>([^<]+)<\/td>\s*<td class='text-right '>([\d,]+)<\/td>\s*<td class='text-right '>([\d,]+)<\/td>\s*<td class='text-right '>([\d.]+)%<\/td>\s*<\/tr>/g;

function csvEscape(value) {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

const rows = [];
let match;
while ((match = rowPattern.exec(tableHtml))) {
  const ward = match[1].trim().replace(/\s+/g, " ");
  rows.push({
    county: "Jefferson",
    municipality: ward.replace(/\s*\([^)]*\)\s*$/, ""),
    ward,
    ballots_cast: Number(match[3].replaceAll(",", "")),
    registered_voters: Number(match[2].replaceAll(",", "")),
    registration_denominator_timing: "unknown",
    source_url: sourceUrl,
    source_level: "ward",
    notes: note,
  });
}

if (rows.length !== 34) {
  throw new Error(`Expected 34 Jefferson turnout rows, found ${rows.length}.`);
}

const header = [
  "county",
  "municipality",
  "ward",
  "ballots_cast",
  "registered_voters",
  "registration_denominator_timing",
  "source_url",
  "source_level",
  "notes",
];

const csv = [
  header.join(","),
  ...rows.map((row) => header.map((field) => csvEscape(row[field])).join(",")),
].join("\n");

fs.writeFileSync(output, `${csv}\n`);
console.log(JSON.stringify({ output: path.relative(root, output), rows: rows.length }, null, 2));
