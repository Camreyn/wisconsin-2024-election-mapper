import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(root, "data");
const expectedTotals = { trump: 1697626, harris: 1668229, other: 57063, total: 3422918 };
const expectedMinnesotaTotals = { trump: 1519032, harris: 1656979, other: 77909, total: 3253920 };
const expectedMinnesotaHistoricalTotals = {
  "mn-sos-native-2012-president": { dem: 1546167, rep: 1320225, other: 70169, total: 2936561, rowCount: 87 },
  "mn-sos-native-2016-president": { dem: 1367716, rep: 1322951, other: 254146, total: 2944813, rowCount: 87 },
  "mn-sos-native-2020-president": { dem: 1717077, rep: 1484065, other: 76029, total: 3277171, rowCount: 87 },
  "mn-sos-native-2024-president": { dem: 1656979, rep: 1519032, other: 77909, total: 3253920, rowCount: 87 },
};
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

function readWindowPayload(name, globalName) {
  const text = fs.readFileSync(path.join(dataDir, name), "utf8").trim();
  const prefix = `window.${globalName} = `;
  if (!text.startsWith(prefix)) {
    throw new Error(`${name} does not start with ${prefix}`);
  }
  return JSON.parse(text.slice(prefix.length).replace(/;$/, ""));
}

function readConfigs() {
  const configDir = path.join(dataDir, "state-configs");
  return fs.readdirSync(configDir)
    .filter((name) => name.endsWith(".json") && !name.startsWith("_"))
    .map((name) => JSON.parse(fs.readFileSync(path.join(configDir, name), "utf8")));
}

function configBuildReady(config) {
  const capabilities = config.app?.capabilities || {};
  const requiredCapabilities = [
    "certifiedResults",
    "map",
    "reviewGraphs",
    "turnout",
    "historicalBaseline",
  ];
  if (!requiredCapabilities.every((capability) => capabilities[capability])) {
    return false;
  }
  if (!config.expected?.countyRows || !config.expected?.stateTotal) {
    return false;
  }
  return (config.sources || []).every((source) => source.url && source.url !== "TODO");
}

function normalizeCounty(name) {
  return name.replace(/ County$/, "").replace("Fond Du Lac", "Fond du Lac");
}

function assertEqual(errors, label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    errors.push(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function stateExpectedActual(payload, geometry) {
  return {
    countyRows: payload.presidentCountyResults.length,
    precinctRows: payload.metadata.precinctRows,
    stateTotal: payload.metadata.stateTotal,
    trump: payload.presidentCountyResults.reduce((sum, row) => sum + row.trump, 0),
    harris: payload.presidentCountyResults.reduce((sum, row) => sum + row.harris, 0),
    other: payload.presidentCountyResults.reduce((sum, row) => sum + row.other, 0),
    reviewRows: payload.reviewCharts.metadata.rows.length,
    turnoutRows: payload.turnoutData.rows.length,
    turnoutWarningRows: payload.turnoutData.metadata.warningRows,
    historicalSeries: payload.historicalBaseline.series.length,
    historicalRows: payload.historicalBaseline.series.reduce((sum, series) => sum + series.rowCount, 0),
    geometryFeatures: geometry.features.length,
  };
}

const errors = [];
const counties = readJson("president-county-results.json");
const labels = readJson("candidate-labels.json");
const wardAnalysis = readJson("ward-analysis.json");
const geojson = readJson("wi-counties.geojson");
const turnout = readJson("turnout-data.json");
const minnesota = readWindowPayload("mn-app-data.js", "MN_ELECTION_APP_DATA");
const minnesotaGeojson = readWindowPayload("mn-counties.js", "MN_COUNTIES_GEOJSON");
const stateRegistry = readWindowPayload("state-registry.js", "STATE_APP_REGISTRY");
const stateConfigs = readConfigs();
const buildReadyStateConfigs = stateConfigs.filter(configBuildReady);

assertEqual(errors, "county row count", counties.length, 72);
assertEqual(errors, "candidate label count", labels.length, otherKeys.length);
assertEqual(errors, "county geometry count", geojson.features.length, 72);
assertEqual(errors, "state registry config count", stateRegistry.states.length, buildReadyStateConfigs.length);

for (const config of buildReadyStateConfigs) {
  const registryEntry = stateRegistry.states.find((entry) => entry.code === config.code);
  if (!registryEntry) {
    errors.push(`Missing state registry entry for ${config.code}`);
    continue;
  }
  assertEqual(errors, `${config.code} registry app data file`, registryEntry.appDataFile, config.output.appDataFile);
  assertEqual(errors, `${config.code} registry app data global`, registryEntry.appDataGlobal, config.output.appDataGlobal);
  assertEqual(errors, `${config.code} registry geometry file`, registryEntry.geometryFile, config.geometry.outputFile);
  assertEqual(errors, `${config.code} registry geometry global`, registryEntry.geometryGlobal, config.geometry.outputGlobal);
  for (const source of config.sources) {
    if (!fs.existsSync(path.join(root, source.localFile))) {
      errors.push(`${config.code} missing configured source file: ${source.localFile}`);
    }
  }
  if (!fs.existsSync(path.join(root, config.output.appDataFile))) {
    errors.push(`${config.code} missing generated app data file: ${config.output.appDataFile}`);
  }
  if (!fs.existsSync(path.join(root, config.geometry.outputFile))) {
    errors.push(`${config.code} missing generated geometry file: ${config.geometry.outputFile}`);
  }
  if (fs.existsSync(path.join(root, config.output.appDataFile)) && fs.existsSync(path.join(root, config.geometry.outputFile))) {
    const payload = readWindowPayload(path.relative(dataDir, path.join(root, config.output.appDataFile)), config.output.appDataGlobal);
    const geometry = readWindowPayload(path.relative(dataDir, path.join(root, config.geometry.outputFile)), config.geometry.outputGlobal);
    assertEqual(errors, `${config.code} generated expected counts`, stateExpectedActual(payload, geometry), config.expected);
  }
}

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

const minnesotaCounties = minnesota.presidentCountyResults;
const minnesotaOtherKeys = minnesota.candidateLabels.map((candidate) => candidate.key);
assertEqual(errors, "Minnesota county row count", minnesotaCounties.length, 87);
assertEqual(errors, "Minnesota metadata county rows", minnesota.metadata.countyRows, 87);
assertEqual(errors, "Minnesota metadata precinct rows", minnesota.metadata.precinctRows, 4103);
assertEqual(errors, "Minnesota county geometry count", minnesotaGeojson.features.length, 87);

for (const row of minnesotaCounties) {
  const rowOther = minnesotaOtherKeys.reduce((sum, key) => sum + row[key], 0);
  assertEqual(errors, `Minnesota ${row.county} other breakdown`, rowOther, row.other);
  assertEqual(errors, `Minnesota ${row.county} total`, row.trump + row.harris + row.other, row.total);
  assertEqual(errors, `Minnesota ${row.county} margin`, row.trump - row.harris, row.margin);
}

const minnesotaTotals = {
  trump: minnesotaCounties.reduce((sum, row) => sum + row.trump, 0),
  harris: minnesotaCounties.reduce((sum, row) => sum + row.harris, 0),
  other: minnesotaCounties.reduce((sum, row) => sum + row.other, 0),
  total: minnesotaCounties.reduce((sum, row) => sum + row.total, 0),
};
assertEqual(errors, "Minnesota president statewide totals", minnesotaTotals, expectedMinnesotaTotals);

const minnesotaReviewRows = minnesota.reviewCharts.metadata.rows;
assertEqual(errors, "Minnesota review row metadata count", minnesota.reviewCharts.metadata.wardRows, minnesotaReviewRows.length);
assertEqual(errors, "Minnesota review row count expected", minnesotaReviewRows.length, 4075);
assertEqual(
  errors,
  "Minnesota review president totals",
  {
    trump: minnesotaReviewRows.reduce((sum, row) => sum + row.trump, 0),
    harris: minnesotaReviewRows.reduce((sum, row) => sum + row.harris, 0),
    total: minnesotaReviewRows.reduce((sum, row) => sum + row.total, 0),
  },
  { trump: expectedMinnesotaTotals.trump, harris: expectedMinnesotaTotals.harris, total: expectedMinnesotaTotals.total },
);

const minnesotaTurnout = minnesota.turnoutData;
assertEqual(errors, "Minnesota turnout metadata row count", minnesotaTurnout.rows.length, minnesotaTurnout.metadata.rows);
assertEqual(errors, "Minnesota turnout row count expected", minnesotaTurnout.rows.length, 4103);
for (const row of minnesotaTurnout.rows) {
  if (typeof row.turnoutPct === "number" && row.registeredVoters > 0) {
    const expected = Math.round((row.ballotsCast / row.registeredVoters) * 10000) / 100;
    assertEqual(errors, `Minnesota ${row.county} ${row.ward} turnoutPct`, row.turnoutPct, expected);
  }
}

const minnesotaHistorical = minnesota.historicalBaseline;
assertEqual(errors, "Minnesota historical series count", minnesotaHistorical.series.length, 4);
for (const series of minnesotaHistorical.series) {
  const expected = expectedMinnesotaHistoricalTotals[series.id];
  if (!expected) {
    errors.push(`Unexpected Minnesota historical series: ${series.id}`);
    continue;
  }
  assertEqual(errors, `${series.id} row count`, series.rows.length, expected.rowCount);
  assertEqual(errors, `${series.id} metadata row count`, series.rowCount, expected.rowCount);
  assertEqual(
    errors,
    `${series.id} statewide totals`,
    {
      dem: series.rows.reduce((sum, row) => sum + row.dem, 0),
      rep: series.rows.reduce((sum, row) => sum + row.rep, 0),
      other: series.rows.reduce((sum, row) => sum + row.other, 0),
      total: series.rows.reduce((sum, row) => sum + row.total, 0),
      rowCount: series.rows.length,
    },
    expected,
  );
}

if (errors.length) {
  console.error("Validation failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(JSON.stringify({
  status: "passed",
  countyRows: counties.length,
  wardRows: wardRows.length,
  countyFeatures: geojson.features.length,
  turnoutRows: turnout.rows.length,
  presidentTotals: totals,
  minnesotaCountyRows: minnesotaCounties.length,
  minnesotaCountyFeatures: minnesotaGeojson.features.length,
  minnesotaReviewRows: minnesotaReviewRows.length,
  minnesotaTurnoutRows: minnesotaTurnout.rows.length,
  minnesotaHistoricalRows: minnesotaHistorical.series.reduce((sum, series) => sum + series.rows.length, 0),
  minnesotaPresidentTotals: minnesotaTotals,
}, null, 2));
