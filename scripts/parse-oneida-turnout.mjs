import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const input = path.join(root, "data", "oneida-2024-general-result.html");
const output = path.join(root, "data", "oneida-county-turnout.csv");
const sourceUrl = "https://www.oneidacountywi.gov/election-results/";

const html = fs.readFileSync(input, "utf8");
const tableMatch = html.match(/<table id="table_2"[\s\S]*?<\/table>/);

if (!tableMatch) {
  throw new Error("Could not find Oneida turnout table_2 in source HTML.");
}

const table = tableMatch[0];
const headers = [...table.matchAll(/<th[\s\S]*?>([\s\S]*?)<\/th>/g)].map((match) => clean(match[1]));
const rows = [...table.matchAll(/<tr id="table_18_row_(\d+)"[\s\S]*?<\/tr>/g)].map((match) => {
  const cells = [...match[0].matchAll(/<td[\s\S]*?>([\s\S]*?)<\/td>/g)].map((cell) => clean(cell[1]));
  return { index: Number(match[1]), cells };
});

const registered = rows.find((row) => row.cells[0] === "Registered Voters as of 11/01/2024");
const voters = rows.find((row) => row.cells[0] === "Voters 11/5/2024");

if (!registered || !voters) {
  throw new Error("Could not find registered-voter and voter rows in Oneida source HTML.");
}

if (headers.length !== registered.cells.length || headers.length !== voters.cells.length) {
  throw new Error(`Header/cell mismatch: headers=${headers.length}, registered=${registered.cells.length}, voters=${voters.cells.length}`);
}

const dataRows = headers
  .map((header, index) => ({ header, index }))
  .filter((row) => row.header && row.header !== "Voter Turnout Info" && row.header !== "Totals")
  .map((row) => ({
    header: row.header,
    registeredVoters: toInt(registered.cells[row.index]),
    ballotsCast: toInt(voters.cells[row.index]),
  }))
  .map((row) => ({
    county: "Oneida",
    municipality: municipalityName(row.header),
    ward: normalizeWardLabel(row.header),
    ballots_cast: row.ballotsCast,
    registered_voters: row.registeredVoters,
    registration_denominator_timing: "preElectionDay",
    source_url: sourceUrl,
    source_level: "ward",
    notes: "Oneida County Nov. 5, 2024 voter turnout table. Registered-voter row is explicitly dated 11/01/2024, before Election Day, so these rows are warning-gated.",
  }));

const totalRegistered = toInt(registered.cells[headers.indexOf("Totals")]);
const totalVoters = toInt(voters.cells[headers.indexOf("Totals")]);
const summedRegistered = dataRows.reduce((total, row) => total + row.registered_voters, 0);
const summedVoters = dataRows.reduce((total, row) => total + row.ballots_cast, 0);

if (summedRegistered !== totalRegistered || summedVoters !== totalVoters) {
  throw new Error(`Oneida totals mismatch: registered ${summedRegistered}/${totalRegistered}, voters ${summedVoters}/${totalVoters}`);
}

const columns = [
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
const csv = [columns.join(","), ...dataRows.map((row) => columns.map((column) => csvEscape(row[column])).join(","))].join("\n") + "\n";

fs.writeFileSync(output, csv, "utf8");
console.log(JSON.stringify({ output: path.relative(root, output), rows: dataRows.length, totalRegistered, totalVoters }, null, 2));

function clean(value) {
  return value
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&#8211;/g, "-")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function toInt(value) {
  const parsed = Number(String(value).replace(/,/g, ""));
  if (!Number.isInteger(parsed)) {
    throw new Error(`Expected integer, got ${value}`);
  }
  return parsed;
}

function municipalityName(label) {
  return normalizeWardLabel(label).replace(/\s+W\s+\d.*$/i, "").trim();
}

function normalizeWardLabel(label) {
  return label
    .replace(/^T\.\s+/, "Town of ")
    .replace(/^C\.\s+/, "City of ")
    .replace(/\s+/g, " ")
    .trim();
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
