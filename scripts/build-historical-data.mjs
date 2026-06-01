import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const historicalDir = path.join(root, "data", "historical", "generated");
const summary = JSON.parse(
  fs.readFileSync(path.join(historicalDir, "historical-presidential-summary.json"), "utf8"),
);
const reconciliation = JSON.parse(
  fs.readFileSync(path.join(historicalDir, "historical-reconciliation-report.json"), "utf8"),
);

const payload = {
  metadata: summary.metadata,
  reconciliation: {
    status: reconciliation.status,
    checks: reconciliation.checks,
    notes: reconciliation.notes,
  },
  series: summary.series.map((series) => ({
    id: series.id,
    electionYear: series.electionYear,
    sourceId: series.sourceId,
    sourceClass: series.sourceClass,
    sourceLevel: series.sourceLevel,
    rowMethod: series.rowMethod,
    rowCount: series.rowCount,
    statewide: series.statewide,
    rows: series.rows.map((row) => ({
      county: row.county,
      municipality: row.municipality,
      reportingUnit: row.reportingUnit,
      ward: row.ward,
      dem: row.dem,
      rep: row.rep,
      other: row.other,
      total: row.total,
    })),
  })),
};

const output = path.join(root, "data", "historical-data.js");
fs.writeFileSync(output, `window.WI_HISTORICAL_BASELINE = ${JSON.stringify(payload)};\n`);

console.log(
  JSON.stringify(
    {
      output: path.relative(root, output).replaceAll("\\", "/"),
      series: payload.series.length,
      rows: payload.series.reduce((sum, series) => sum + series.rows.length, 0),
      reconciliationChecks: payload.reconciliation.checks.length,
    },
    null,
    2,
  ),
);
