import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(root, "data");

function readJson(name) {
  return JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));
}

function writeJs(name, globalName, value) {
  fs.writeFileSync(
    path.join(dataDir, name),
    `window.${globalName} = ${JSON.stringify(value)};\n`,
  );
}

const president = readJson("president-county-results.json");
const labels = readJson("candidate-labels.json");
const wardAnalysis = readJson("ward-analysis.json");
const counties = readJson("wi-counties.geojson");

writeJs("app-data.js", "WI_ELECTION_APP_DATA", {
  presidentCountyResults: president,
  candidateLabels: labels,
});
writeJs("eta-data.js", "ETA_WARD_CHARTS", wardAnalysis);
writeJs("wi-counties.js", "WI_COUNTIES_GEOJSON", counties);

console.log(
  JSON.stringify(
    {
      presidentCountyResults: president.length,
      candidateLabels: labels.length,
      wardRows: wardAnalysis.metadata.wardRows,
      countyFeatures: counties.features.length,
    },
    null,
    2,
  ),
);
