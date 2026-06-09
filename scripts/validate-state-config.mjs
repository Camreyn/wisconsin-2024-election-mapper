import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const configDir = path.join(root, "data/state-configs");

const supportedDownloads = new Set(["browserDownload", "northDakotaResultsExport"]);
const supportedCertifiedFormats = new Set([
  "notConfigured",
  "xlsxPrecinctAggregation",
  "alabamaPrecinctZip",
  "californiaPresidentXlsx",
  "certifiedCountyTotalsCsv",
  "clarityEnrJson",
  "coloradoCiveraCsv",
  "civeraContestCountyCsv",
  "connecticutStatementText",
  "delawareCountyHtml",
  "floridaPrecinctZip",
  "georgiaTotalVotesXlsx",
  "hawaiiCountySummaryPdfs",
  "idahoCountyCsv",
  "illinoisPrecinctCsv",
  "indianaEnrJson",
  "iowaCanvassPdf",
  "kansasPresidentialXlsx",
  "kentuckyCertificationPdf",
  "maineCountyTownXlsx",
  "massachusettsCountyHtml",
  "marylandCountyHtml",
  "michiganCountyTab",
  "missouriActualResultsPdf",
  "montanaCanvassPdf",
  "nebraskaCanvassPdf",
  "nevadaStatewideHtml",
  "nationalCountyBaselineCsv",
  "newHampshirePresidentPdf",
  "newJerseyPresidentPdf",
  "northCarolinaEnrZip",
  "newYorkCountyCsv",
  "northDakotaStatewideCsv",
  "ohioStatewideRaceSummaryXlsx",
  "oklahomaEnrZip",
  "oregonMapDataJson",
  "pennsylvaniaBulkCsv",
  "rhodeIslandSummaryXlsx",
  "southCarolinaEnrJson",
  "southDakotaCanvassPdf",
  "tennesseePrecinctXlsx",
  "texasCountyJson",
  "totalResultsContestJson",
  "utahStatewideCanvassPdf",
  "vermontMunicipalityCsv",
  "virginiaLocalityCsv",
  "washingtonCountyHtml",
  "wyomingStatewideSummaryXlsx",
]);
const supportedReviewFormats = new Set([
  "notConfigured",
  "xlsxPrecinctComparison",
  "alaskaEnrPrecinctCsvComparison",
  "alabamaPrecinctZipComparison",
  "arizonaPrecinctSummaryPdfs",
  "californiaSovXlsxCountyComparison",
  "californiaSwdbSrprecComparison",
  "civeraCountyCsvComparison",
  "civeraPrecinctCsvComparison",
  "civeraPrecinctVoteShare",
  "clarityEnrCountyJsonComparison",
  "connecticutStatementTextTownComparison",
  "delawareCountyHtmlComparison",
  "delawareElectionDistrictHtmlComparison",
  "electionwarePrecinctSummaryComparison",
  "floridaPrecinctZipComparison",
  "georgiaHouseJsonCountyComparison",
  "georgiaPrecinctVoteShare",
  "hawaiiCountySummaryPdfCountyComparison",
  "hawaiiMediaPrecinctComparison",
  "idahoPrecinctCsvComparison",
  "illinoisPrecinctVoteShare",
  "indianaEnrCountyJsonComparison",
  "iowaHousePdfCountyComparison",
  "kansasHouseXlsxCountyComparison",
  "kansasPresidentialPrecinctVoteShare",
  "kentuckyHousePdfCountyComparison",
  "louisianaFederalPrecinctJsonComparison",
  "maineCountyTownXlsxComparison",
  "marylandPrecinctCsvComparison",
  "mississippiRecapCsvCountyComparison",
  "missouriActualResultsPdfCountyComparison",
  "massachusettsCountyHtmlComparison",
  "massachusettsPrecinctCsvComparison",
  "newJerseyMunicipalPdfComparison",
  "newJerseySenatePdfCountyComparison",
  "newYorkCountyCsvComparison",
  "newYorkCityEdCsvComparison",
  "northCarolinaPrecinctZipComparison",
  "ohioPrecinctVoteShare",
  "tennesseePrecinctXlsxComparison",
  "tabDelimitedZipComparison",
  "totalResultsHouseCountyComparison",
  "totalResultsPrecinctVoteShare",
  "michiganPrecinctZipComparison",
  "michiganCountyTabComparison",
  "montanaCanvassPdfCountyComparison",
  "nebraskaCanvassPdfCountyComparison",
  "nevadaClarkCvrComparison",
  "nevadaStatewideHtmlCountyComparison",
  "northDakotaStatewideCsvCountyComparison",
  "oklahomaEnrZipCountyComparison",
  "oklahomaPrecinctCsvZipComparison",
  "oregonHouseMapDataCountyComparison",
  "oregonPrecinctVoteShare",
  "pennsylvaniaBulkCsvPrecinctComparison",
  "rhodeIslandSummaryXlsxComparison",
  "southCarolinaHouseEnrCountyComparison",
  "southDakotaCanvassPdfCountyComparison",
  "texasCountyJsonComparison",
  "texasHarrisCanvassPdfVoteShare",
  "utahCanvassPdfCountyComparison",
  "utahPrecinctVoteShare",
  "vermontMunicipalityCsvComparison",
  "virginiaPrecinctCsvComparison",
  "washingtonPrecinctCsvComparison",
  "wyomingPrecinctXlsxComparison",
]);
const supportedTurnoutFormats = new Set([
  "alaskaEnrHouseDistrictTurnout",
  "alabamaPrecinctZipTurnout",
  "arkansasTotalResultsStatewideJson",
  "californiaParticipationPdf",
  "connecticutStatementTurnoutPdf",
  "coloradoGeneralTurnoutPdf",
  "countyTurnoutCsv",
  "delawareReportHtml",
  "floridaPrecinctZipTurnout",
  "hawaiiCountySummaryPdfs",
  "idahoTurnoutHtml",
  "illinoisPrecinctCsv",
  "indianaTurnoutPdf",
  "iowaTurnoutCsv",
  "kansasTurnoutXlsx",
  "kentuckyTurnoutPdf",
  "louisianaPresidentParishJson",
  "marylandTurnoutPdf",
  "maineRegistrationTextJoin",
  "xlsxPrecinctRows",
  "notConfigured",
  "michiganMvicCountyTurnout",
  "missouriVoterTurnoutPdf",
  "montanaCanvassPdf",
  "nebraskaCanvassPdf",
  "newJerseyTurnoutPdf",
  "newYorkCountyEnrollmentJoin",
  "northCarolinaVoterHistoryJoin",
  "northDakotaTurnoutHtml",
  "ohioPrecinctTurnoutXlsx",
  "oklahomaEnrRegistrationPdf",
  "oregonRegistrationTurnoutPdf",
  "pennsylvaniaVoteHistoryXlsx",
  "rhodeIslandSummaryXlsx",
  "southDakotaElectionReturnsPdf",
  "southCarolinaEnrStatewideTurnout",
  "statewideTurnoutCsv",
  "tennesseeTurnoutPdf",
  "vermontVoterTurnoutPdf",
  "washingtonReconciliationXlsx",
]);
const supportedHistoricalFormats = new Set([
  "officialCountyResultText",
  "alabamaPrecinctZip",
  "floridaPrecinctZip",
  "michiganCountyTab",
  "northDakotaStatewideCsv",
  "pennsylvaniaBulkCsv",
]);

function parseArgs(argv = process.argv.slice(2)) {
  const args = new Map();
  const positional = [];
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) {
      positional.push(key);
      continue;
    }
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key.slice(2), "true");
    } else if (args.has(key.slice(2))) {
      args.set(key.slice(2), `${args.get(key.slice(2))},${next}`);
      index += 1;
    } else {
      args.set(key.slice(2), next);
      index += 1;
    }
  }
  return { args, positional };
}

function projectPath(value) {
  return path.join(root, value || "");
}

function displayPath(value) {
  return String(value || "").replaceAll("\\", "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function isTodo(value) {
  return typeof value === "string" && (value.trim() === "TODO" || value.includes("{{") || value.includes("}}"));
}

function collectTodos(value, trail = "") {
  if (isTodo(value)) return [trail || "$"];
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => collectTodos(item, `${trail}[${index}]`));
  }
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([key, item]) => collectTodos(item, trail ? `${trail}.${key}` : key));
  }
  return [];
}

function isLoadedStatus(value) {
  return String(value || "").toLowerCase() === "loaded";
}

function configPaths({ config = "", state = "" } = {}) {
  if (config) {
    return config.split(",").filter(Boolean).map((item) => path.resolve(root, item));
  }
  const requestedStates = new Set(
    state
      .split(",")
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean),
  );
  return fs
    .readdirSync(configDir)
    .filter((file) => file.endsWith(".json") && !file.startsWith("_"))
    .map((file) => path.join(configDir, file))
    .filter((file) => !requestedStates.size || requestedStates.has(readJson(file).code));
}

function sourceLookup(config) {
  return new Map((config.sources || []).map((source) => [source.id, source]));
}

function issue(severity, code, message, details = {}) {
  return { severity, code, message, ...details };
}

function requireSourceReference(report, sourceId, featurePath, message) {
  if (!sourceId) {
    report.errors.push(issue("error", "missing-source-reference", message, { path: featurePath }));
    return null;
  }
  const source = report.sourceById.get(sourceId);
  if (!source) {
    report.errors.push(
      issue("error", "unknown-source-reference", `${message}: sourceId "${sourceId}" is not listed in sources.`, {
        path: featurePath,
      }),
    );
  }
  return source || null;
}

function addTodoIssues(report, section, featureName, loaded) {
  const todos = collectTodos(section);
  if (!todos.length) return;
  const target = loaded ? report.errors : report.gaps;
  target.push(
    issue(
      loaded ? "error" : "gap",
      loaded ? "loaded-feature-has-placeholders" : "feature-has-placeholders",
      `${featureName} still has placeholder values to replace.`,
      { paths: todos.slice(0, 12), remainingPaths: Math.max(0, todos.length - 12) },
    ),
  );
}

function addCapabilityGap(report, capability, nextStep, details = {}) {
  report.gaps.push(
    issue("gap", "capability-not-loaded", `${capability} is not marked loaded for ${report.config.code}.`, {
      capability,
      nextStep,
      ...details,
    }),
  );
}

function validateSources(report) {
  const seen = new Set();
  for (const [index, source] of (report.config.sources || []).entries()) {
    const pathPrefix = `sources[${index}]`;
    if (!source.id) {
      report.errors.push(issue("error", "source-missing-id", "Every source needs an id.", { path: pathPrefix }));
    } else if (seen.has(source.id)) {
      report.errors.push(issue("error", "duplicate-source-id", `Duplicate source id "${source.id}".`, { path: pathPrefix }));
    }
    seen.add(source.id);

    if (!source.url || isTodo(source.url)) {
      report.gaps.push(
        issue("gap", "source-url-missing", `Source "${source.id || index}" needs an official URL.`, {
          path: `${pathPrefix}.url`,
          nextStep: "Attach the official results, turnout, geometry, or historical source URL.",
        }),
      );
    }
    if (!source.localFile || isTodo(source.localFile)) {
      report.gaps.push(
        issue("gap", "source-local-file-missing", `Source "${source.id || index}" needs a localFile path.`, {
          path: `${pathPrefix}.localFile`,
          nextStep: "Choose the file path the downloader/importer should use.",
        }),
      );
    } else if (!fs.existsSync(projectPath(source.localFile))) {
      report.gaps.push(
        issue("gap", "source-local-file-not-present", `Local source file is not present for "${source.id}".`, {
          localFile: displayPath(source.localFile),
          nextStep: source.download ? "Run npm.cmd run build:states:download for this state." : "Add a download strategy or place the official file at localFile.",
        }),
      );
    }

    const downloadType = source.download?.type;
    if (downloadType && !supportedDownloads.has(downloadType)) {
      report.errors.push(
        issue("error", "unsupported-download-type", `Source "${source.id}" uses unsupported download type "${downloadType}".`, {
          path: `${pathPrefix}.download.type`,
        }),
      );
    }
    if (downloadType === "northDakotaResultsExport") {
      if (!source.download.fileType) {
        report.errors.push(
          issue("error", "download-parameter-missing", `North Dakota export source "${source.id}" is missing download.fileType.`, {
            path: `${pathPrefix}.download.fileType`,
          }),
        );
      }
      if (!source.download.eventTarget && !source.download.buttonName) {
        report.errors.push(
          issue("error", "download-parameter-missing", `North Dakota export source "${source.id}" needs either download.eventTarget or download.buttonName.`, {
            path: `${pathPrefix}.download`,
          }),
        );
      }
      if (source.download.buttonName && !source.download.buttonValue) {
        report.errors.push(
          issue("error", "download-parameter-missing", `North Dakota export source "${source.id}" is missing download.buttonValue.`, {
            path: `${pathPrefix}.download.buttonValue`,
          }),
        );
      }
    }
    if (source.discovery && !isLoadedStatus(source.discovery.status)) {
      report.gaps.push(
        issue("gap", "discovered-source-needs-review", `Discovered source "${source.id}" still needs review before it can be treated as loaded.`, {
          status: source.discovery.status || "Candidate",
          role: source.discovery.role || "candidate",
          nextStep: "Confirm the download strategy, parser mapping, and reconciliation target, then promote it into the relevant config section.",
        }),
      );
    }
  }
}

function validateGeometry(report) {
  const geometry = report.config.geometry || {};
  const loaded = Boolean(report.capabilities.map);
  addTodoIssues(report, geometry, "Map geometry", loaded);
  requireSourceReference(report, geometry.sourceId, "geometry.sourceId", "Geometry must point to a configured source");
  if (!geometry.outputFile || isTodo(geometry.outputFile)) {
    (loaded ? report.errors : report.gaps).push(issue(loaded ? "error" : "gap", "geometry-output-missing", "Geometry needs an outputFile."));
  }
  if (!geometry.nameProperty || !geometry.codeProperty || isTodo(geometry.nameProperty) || isTodo(geometry.codeProperty)) {
    (loaded ? report.errors : report.gaps).push(
      issue(loaded ? "error" : "gap", "geometry-properties-missing", "Geometry needs source nameProperty and codeProperty mappings."),
    );
  }
  if (loaded && Number(report.config.expected?.geometryFeatures || 0) <= 0) {
    report.errors.push(issue("error", "expected-geometry-count-missing", "Map capability is loaded but expected.geometryFeatures is not positive."));
  }
  if (!loaded) {
    addCapabilityGap(report, "map", "Set geometry.sourceId, nameProperty, codeProperty, expectedFeatures, then enable app.capabilities.map.");
  }
}

function validateCertifiedResults(report) {
  const certified = report.config.certifiedResults || {};
  const loaded = Boolean(report.capabilities.certifiedResults);
  const format = certified.format || "xlsxPrecinctAggregation";
  if (!supportedCertifiedFormats.has(format)) {
    report.errors.push(issue("error", "unsupported-certified-format", `Unsupported certifiedResults.format "${format}".`));
  }
  if (loaded && format === "notConfigured") {
    report.errors.push(issue("error", "loaded-certified-not-configured", "Certified results capability is loaded but certifiedResults.format is notConfigured."));
  }
  addTodoIssues(report, certified, "Certified results", loaded);
  requireSourceReference(report, certified.sourceId, "certifiedResults.sourceId", "Certified results must point to a configured source");
  if (format === "xlsxPrecinctAggregation" && !certified.columns) {
    report.errors.push(issue("error", "certified-columns-missing", "XLSX certified results need certifiedResults.columns."));
  }
  if (
    format !== "notConfigured" &&
    format !== "xlsxPrecinctAggregation" &&
    format !== "californiaPresidentXlsx" &&
    format !== "coloradoCiveraCsv" &&
    format !== "civeraContestCountyCsv" &&
    format !== "connecticutStatementText" &&
    format !== "hawaiiCountySummaryPdfs" &&
    format !== "idahoCountyCsv" &&
    format !== "iowaCanvassPdf" &&
    format !== "kansasPresidentialXlsx" &&
    format !== "kentuckyCertificationPdf" &&
    format !== "massachusettsCountyHtml" &&
    !certified.majorCandidates
  ) {
    report.errors.push(issue("error", "certified-candidates-missing", `${format} certified results need majorCandidates rules.`));
  }
  if (loaded && Number(report.config.expected?.countyRows || 0) <= 0) {
    report.errors.push(issue("error", "expected-county-count-missing", "Certified results are loaded but expected.countyRows is not positive."));
  }
  if (loaded && !isLoadedStatus(report.config.app?.sourcePlan?.certifiedResults?.status)) {
    report.errors.push(issue("error", "source-plan-not-loaded", "Certified results capability is loaded but Source Planner certifiedResults status is not Loaded."));
  }
  if (!loaded) {
    addCapabilityGap(report, "certifiedResults", "Map the presidential contest/candidate columns, set expected county totals, and enable app.capabilities.certifiedResults.");
  }
}

function validateReviewCharts(report) {
  const review = report.config.reviewCharts || {};
  const loaded = Boolean(report.capabilities.reviewGraphs);
  const format = review.format || "xlsxPrecinctComparison";
  if (!supportedReviewFormats.has(format)) {
    report.errors.push(issue("error", "unsupported-review-format", `Unsupported reviewCharts.format "${format}".`));
  }
  if (loaded && format === "notConfigured") {
    report.errors.push(issue("error", "loaded-review-not-configured", "Review graph capability is loaded but reviewCharts.format is notConfigured."));
  }
  addTodoIssues(report, review, "Review graphs", loaded);
  requireSourceReference(report, review.sourceId, "reviewCharts.sourceId", "Review graphs must point to a configured source");
  if (format === "xlsxPrecinctComparison" && (!review.columns || !review.rowLabelColumns)) {
    report.errors.push(issue("error", "review-columns-missing", "XLSX review graphs need columns and rowLabelColumns mappings."));
  }
  if (format === "tabDelimitedZipComparison" && (!review.zipTables || !review.presidentContest || !review.downBallotContest || !review.partyCodes)) {
    report.errors.push(issue("error", "review-zip-mapping-missing", "Tab-delimited ZIP review graphs need zipTables, contest mappings, and partyCodes."));
  }
  if (loaded && Number(report.config.expected?.reviewRows || 0) <= 0) {
    report.errors.push(issue("error", "expected-review-count-missing", "Review graphs are loaded but expected.reviewRows is not positive."));
  }
  if (loaded && !isLoadedStatus(report.config.app?.sourcePlan?.wardDetail?.status)) {
    report.errors.push(issue("error", "source-plan-not-loaded", "Review graph capability is loaded but Source Planner wardDetail status is not Loaded."));
  }
  if (!loaded) {
    addCapabilityGap(report, "reviewGraphs", "Choose a review parser, map the down-ballot contest, set expected reviewRows, and enable app.capabilities.reviewGraphs.");
  }
}

function validateTurnout(report) {
  const turnout = report.config.turnout || {};
  const loaded = Boolean(report.capabilities.turnout);
  const format = turnout.format || "xlsxPrecinctRows";
  if (!supportedTurnoutFormats.has(format)) {
    report.errors.push(issue("error", "unsupported-turnout-format", `Unsupported turnout.format "${format}".`));
  }
  addTodoIssues(report, turnout, "Turnout", loaded);
  if (format !== "notConfigured") {
    requireSourceReference(report, turnout.sourceId, "turnout.sourceId", "Turnout must point to a configured source");
  }
  if (format === "michiganMvicCountyTurnout") {
    requireSourceReference(report, turnout.registrationSourceId, "turnout.registrationSourceId", "Michigan turnout must point to a registration source");
  }
  if (format === "alabamaPrecinctZipTurnout") {
    requireSourceReference(report, turnout.registrationSourceId, "turnout.registrationSourceId", "Alabama turnout must point to a registration source");
  }
  if (loaded && format === "notConfigured") {
    report.errors.push(issue("error", "loaded-turnout-not-configured", "Turnout capability is loaded but turnout.format is notConfigured."));
  }
  if (loaded && Number(report.config.expected?.turnoutRows || 0) <= 0) {
    report.errors.push(issue("error", "expected-turnout-count-missing", "Turnout is loaded but expected.turnoutRows is not positive."));
  }
  if (loaded && !isLoadedStatus(report.config.app?.sourcePlan?.turnout?.status)) {
    report.errors.push(issue("error", "source-plan-not-loaded", "Turnout capability is loaded but Source Planner turnout status is not Loaded."));
  }
  if (loaded && !isLoadedStatus(report.config.app?.turnoutPolicy?.status)) {
    report.errors.push(issue("error", "turnout-policy-not-loaded", "Turnout capability is loaded but app.turnoutPolicy.status is not Loaded."));
  }
  if (!loaded) {
    addCapabilityGap(report, "turnout", "Map a turnout source and denominator timing, set expected turnoutRows, and enable app.capabilities.turnout.");
  }
}

function validateHistorical(report) {
  const historical = report.config.historicalBaseline || {};
  const loaded = Boolean(report.capabilities.historicalBaseline);
  const format = historical.format || historical.rowMethod || "officialCountyResultText";
  if (!supportedHistoricalFormats.has(format) && format !== "notConfigured" && historical.rowMethod !== "notConfigured") {
    report.errors.push(issue("error", "unsupported-historical-format", `Unsupported historical baseline format/rowMethod "${format}".`));
  }
  addTodoIssues(report, historical, "Historical baseline", loaded);
  for (const [index, source] of (historical.sources || []).entries()) {
    requireSourceReference(report, source.sourceId, `historicalBaseline.sources[${index}].sourceId`, "Historical baseline source must point to a configured source");
  }
  if (loaded && !(historical.sources || []).length) {
    report.errors.push(issue("error", "historical-sources-missing", "Historical baseline capability is loaded but no historical sources are configured."));
  }
  if (loaded && Number(report.config.expected?.historicalSeries || 0) <= 0) {
    report.errors.push(issue("error", "expected-historical-count-missing", "Historical baseline is loaded but expected.historicalSeries is not positive."));
  }
  if (loaded && Number(report.config.expected?.historicalRows || 0) <= 0) {
    report.errors.push(issue("error", "expected-historical-row-count-missing", "Historical baseline is loaded but expected.historicalRows is not positive."));
  }
  if (!loaded) {
    addCapabilityGap(report, "historicalBaseline", "Add historical source files, map party/contest rules, set expected historical counts, and enable app.capabilities.historicalBaseline.");
  }
}

function validateOutput(report) {
  const output = report.config.output || {};
  for (const field of ["appDataFile", "appDataGlobal"]) {
    if (!output[field] || isTodo(output[field])) {
      report.errors.push(issue("error", "output-field-missing", `output.${field} is required.`, { path: `output.${field}` }));
    }
  }
  if (report.config.app?.capabilities?.sourcePlanner && !report.config.app?.sourcePlan) {
    report.errors.push(issue("error", "source-plan-missing", "Source Planner capability is enabled but app.sourcePlan is missing."));
  }
}

export function validateStateConfig(config, { configPath = "" } = {}) {
  const report = {
    state: config.code || path.basename(configPath, ".json").toUpperCase(),
    name: config.name || "",
    configPath: displayPath(path.relative(root, configPath || "")),
    config,
    capabilities: config.app?.capabilities || {},
    sourceById: sourceLookup(config),
    errors: [],
    gaps: [],
    warnings: [],
  };

  for (const field of ["code", "name", "authority", "electionYear", "office"]) {
    if (!config[field] || isTodo(config[field])) {
      report.errors.push(issue("error", "top-level-field-missing", `${field} is required.`, { path: field }));
    }
  }
  if (!Array.isArray(config.sources)) {
    report.errors.push(issue("error", "sources-missing", "sources must be an array."));
  }

  validateOutput(report);
  validateSources(report);
  validateGeometry(report);
  validateCertifiedResults(report);
  validateReviewCharts(report);
  validateTurnout(report);
  validateHistorical(report);

  const loadedCapabilities = Object.entries(report.capabilities)
    .filter(([, enabled]) => enabled)
    .map(([name]) => name);

  return {
    state: report.state,
    name: report.name,
    configPath: report.configPath,
    status: report.errors.length ? "failed" : report.gaps.length ? "valid_with_gaps" : "ready",
    loadedCapabilities,
    counts: {
      sources: (config.sources || []).length,
      errors: report.errors.length,
      gaps: report.gaps.length,
      warnings: report.warnings.length,
    },
    errors: report.errors,
    gaps: report.gaps,
    warnings: report.warnings,
  };
}

export function validateStateConfigFile(configPath) {
  return validateStateConfig(readJson(configPath), { configPath });
}

function summaryFor(results) {
  return {
    status: results.some((result) => result.status === "failed") ? "failed" : results.some((result) => result.status === "valid_with_gaps") ? "valid_with_gaps" : "ready",
    states: results.length,
    errors: results.reduce((total, result) => total + result.counts.errors, 0),
    gaps: results.reduce((total, result) => total + result.counts.gaps, 0),
    warnings: results.reduce((total, result) => total + result.counts.warnings, 0),
  };
}

function main(argv = process.argv.slice(2)) {
  const { args, positional } = parseArgs(argv);
  const paths = [...configPaths({ config: args.get("config") || positional.join(","), state: args.get("state") || "" })];
  const strictGaps = args.has("strict-gaps");
  if (!paths.length) {
    console.error("No state config files matched. Use --state XX or --config data/state-configs/xx.json.");
    process.exit(2);
  }
  const results = paths.map(validateStateConfigFile);
  const output = {
    summary: summaryFor(results),
    results,
  };
  process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
  if (output.summary.errors || (strictGaps && output.summary.gaps)) {
    process.exit(1);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
