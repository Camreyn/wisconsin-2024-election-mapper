import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(root, "data");
const expectedTotals = { trump: 1697626, harris: 1668229, other: 57063, total: 3422918 };
const otherKeys = [
  "kennedy",
  "stein",
  "oliver",
  "terry",
  "west",
  "deLaCruz",
  "sonski",
  "fox",
  "kienitz",
  "jenkins",
  "futureMadamPotus",
  "mcneil",
  "scattering",
];

function readJson(name) {
  return JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));
}

function normalizeCounty(name) {
  return name.replace(/ County$/, "").replace("Fond Du Lac", "Fond du Lac");
}

function assertEqual(errors, label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    errors.push(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

const errors = [];
const counties = readJson("president-county-results.json");
const labels = readJson("candidate-labels.json");
const wardAnalysis = readJson("ward-analysis.json");
const geojson = readJson("wi-counties.geojson");
const turnout = readJson("turnout-data.json");

assertEqual(errors, "county row count", counties.length, 72);
assertEqual(errors, "candidate label count", labels.length, otherKeys.length);
assertEqual(errors, "county geometry count", geojson.features.length, 72);

const countyNames = [...new Set(counties.map((row) => row.county))].sort();
const geometryNames = [...new Set(geojson.features.map((feature) => normalizeCounty(feature.properties.NAME)))].sort();
assertEqual(errors, "county names match geometry names", countyNames, geometryNames);

for (const row of counties) {
  const rowOther = otherKeys.reduce((sum, key) => sum + row[key], 0);
  assertEqual(errors, `${row.county} other breakdown`, rowOther, row.other);
  assertEqual(errors, `${row.county} total`, row.trump + row.harris + row.other, row.total);
  assertEqual(errors, `${row.county} margin`, row.trump - row.harris, row.margin);
}

const totals = {
  trump: counties.reduce((sum, row) => sum + row.trump, 0),
  harris: counties.reduce((sum, row) => sum + row.harris, 0),
  other: counties.reduce((sum, row) => sum + row.other, 0),
  total: counties.reduce((sum, row) => sum + row.total, 0),
};
assertEqual(errors, "president statewide totals", totals, expectedTotals);

const wardRows = wardAnalysis.metadata.rows;
assertEqual(errors, "ward row count", wardRows.length, wardAnalysis.metadata.wardRows);
assertEqual(errors, "ward row count expected", wardRows.length, 3503);
const wardCounties = [...new Set(wardRows.map((row) => normalizeCounty(row.county)))].sort();
assertEqual(errors, "ward counties covered", wardCounties, countyNames);
assertEqual(
  errors,
  "ward president totals",
  {
    trump: wardRows.reduce((sum, row) => sum + row.trump, 0),
    harris: wardRows.reduce((sum, row) => sum + row.harris, 0),
    total: wardRows.reduce((sum, row) => sum + row.total, 0),
  },
  { trump: expectedTotals.trump, harris: expectedTotals.harris, total: expectedTotals.total },
);

assertEqual(errors, "turnout metadata row count", turnout.rows.length, turnout.metadata.rows);
for (const row of turnout.rows) {
  if (!countyNames.includes(normalizeCounty(row.county))) {
    errors.push(`turnout county not recognized: ${row.county}`);
  }
  if (typeof row.turnoutPct === "number" && row.registeredVoters > 0) {
    const expected = Math.round((row.ballotsCast / row.registeredVoters) * 10000) / 100;
    assertEqual(errors, `${row.county} ${row.ward} turnoutPct`, row.turnoutPct, expected);
  }
}

if (errors.length) {
  console.error("Validation failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(JSON.stringify({ status: "passed", countyRows: counties.length, wardRows: wardRows.length, countyFeatures: geojson.features.length, turnoutRows: turnout.rows.length, presidentTotals: totals }, null, 2));
