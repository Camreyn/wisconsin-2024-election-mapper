import fs from "node:fs";
import path from "node:path";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index];
  if (key.startsWith("--")) {
    const next = process.argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key.slice(2), "true");
    } else {
      args.set(key.slice(2), next);
      index += 1;
    }
  }
}

const configPath = args.get("config");
const reportPath = args.get("report");
const write = args.has("write");
const limit = Number(args.get("limit") || 12);

if (!configPath || !reportPath) {
  console.error("Usage: node scripts/apply-source-discovery.mjs --config data/state-configs/xx.json --report report.json [--write] [--limit N]");
  process.exit(2);
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "source";
}

function sourceSlug(config) {
  return slugify(config.code || config.name || "state");
}

function urlExtension(url, fallback) {
  const inferred = inferredLocalExtension(url, fallback);
  if (inferred) return inferred;
  try {
    const pathname = new URL(url).pathname;
    const rawExt = path.extname(pathname).replace(/^\./, "").toLowerCase();
    const ext = ["aspx", "ashx", "php"].includes(rawExt) ? "html" : rawExt;
    if (ext) return ext;
  } catch {
    // Fall through to type-based defaults.
  }
  if (fallback === "spreadsheet") return "xlsx";
  if (fallback === "zip") return "zip";
  if (fallback === "pdf") return "pdf";
  if (fallback === "csv") return "csv";
  if (fallback === "text") return "txt";
  if (fallback === "geometry") return "geojson";
  if (["aspx", "ashx", "php"].includes(fallback)) return "html";
  return "html";
}

function inferredLocalExtension(url, fallback) {
  const text = String(url || "").toLowerCase();
  if (text.includes("getprecinctresultsfile")) return "zip";
  if (text.includes("getelectionresultfile") || text.includes("getvoterturnoutfile")) return "txt";
  if (fallback === "spreadsheet") return "xlsx";
  if (fallback === "geometry") return "geojson";
  return "";
}

function isScriptOrStyle(url) {
  return /\.(js|css)(\?|#|$)/i.test(url);
}

function isImportableDownload(candidate) {
  if (!candidate.url || candidate.url.startsWith("javascript:")) return false;
  if (isScriptOrStyle(candidate.url)) return false;
  return ["csv", "spreadsheet", "zip", "pdf", "text", "geometry", "export-endpoint"].includes(candidate.type);
}

function isPostbackOrScript(candidate) {
  return candidate.type === "postback-export" || candidate.url?.startsWith("javascript:");
}

function sourceCategory(candidate) {
  if (candidate.type === "geometry") return "Discovered geometry candidate";
  if (candidate.type === "pdf") return "Discovered PDF candidate";
  if (candidate.type === "zip") return "Discovered ZIP candidate";
  if (candidate.type === "spreadsheet") return "Discovered spreadsheet candidate";
  if (candidate.type === "csv") return "Discovered CSV candidate";
  return "Discovered export candidate";
}

function sourceStatus(candidate) {
  const inference = inferCandidateConfig(candidate);
  if (inference.status) return inference.status;
  if (candidate.type === "export-endpoint") return "Needs download strategy";
  return "Candidate";
}

function inferCandidateConfig(candidate) {
  const url = String(candidate.url || "");
  const loweredUrl = url.toLowerCase();
  const inference = {
    status: "",
    role: "",
    download: null,
    suggestedDownload: null,
    suggestedParser: null,
    notes: [],
  };

  if (loweredUrl.includes("mvic.sos.state.mi.us/votehistory/getelectionresultfile")) {
    inference.status = "Candidate";
    inference.role = "certifiedResults";
    inference.download = { type: "browserDownload", headless: false, timeoutMs: 120000 };
    inference.suggestedParser = {
      certifiedResultsFormat: "michiganCountyTab",
      note: "MVIC county result export; configure contestName and candidate rules before marking Loaded.",
    };
    inference.notes.push("Protected MVIC endpoint; browser-backed download inferred.");
  } else if (loweredUrl.includes("mvic.sos.state.mi.us/votehistory/getvoterturnoutfile")) {
    inference.status = "Candidate";
    inference.role = "turnout";
    inference.download = { type: "browserDownload", headless: false, timeoutMs: 120000 };
    inference.suggestedParser = {
      turnoutFormat: "michiganMvicCountyTurnout",
      note: "MVIC turnout export usually needs an official registration denominator source.",
    };
    inference.notes.push("Protected MVIC endpoint; browser-backed download inferred.");
  } else if (loweredUrl.includes("mvic.sos.state.mi.us/votehistory/getprecinctresultsfile")) {
    inference.status = "Candidate";
    inference.role = "reviewCharts";
    inference.download = { type: "browserDownload", headless: false, timeoutMs: 180000 };
    inference.suggestedParser = {
      reviewChartsFormat: "tabDelimitedZipComparison",
      note: "Inspect ZIP lookup/vote files and configure zipTables, contest keys, party codes, and rowLabel.",
    };
    inference.notes.push("Protected MVIC precinct ZIP endpoint; browser-backed download inferred.");
  } else if (/results\.sos\.nd\.gov\/resultsexport\.aspx/i.test(url)) {
    inference.status = "Needs postback parameters";
    inference.role = "certifiedResults";
    inference.suggestedDownload = {
      type: "northDakotaResultsExport",
      requiredFields: ["fileType", "buttonName", "buttonValue"],
      note: "Discovery found the export page, but a config must choose the ASP.NET export button parameters.",
    };
    inference.suggestedParser = {
      certifiedResultsFormat: "northDakotaStatewideCsv",
      reviewChartsFormat: "northDakotaStatewideCsvCountyComparison",
    };
  } else if (candidate.type === "zip") {
    inference.role = "reviewCharts";
    inference.suggestedParser = {
      reviewChartsFormat: "tabDelimitedZipComparison",
      note: "Use this when the ZIP separates vote rows from lookup files; otherwise add a source-specific parser.",
    };
  } else if (candidate.type === "spreadsheet") {
    inference.role = "certifiedResults";
    inference.suggestedParser = {
      certifiedResultsFormat: "xlsxPrecinctAggregation",
      reviewChartsFormat: "xlsxPrecinctComparison",
      turnoutFormat: "xlsxTurnoutRows",
      note: "Map sheet names and columns after inspecting the workbook.",
    };
  } else if (candidate.type === "csv") {
    inference.role = "certifiedResults";
    inference.suggestedParser = {
      parserFormat: "csv",
      note: "CSV formats vary; inspect headers before selecting or adding a parser format.",
    };
  } else if (candidate.type === "geometry") {
    inference.status = "Candidate";
    inference.role = "geometry";
    inference.suggestedParser = {
      geometryFormat: "geojsonOrArcgisFeatureService",
      note: "Map this through the config geometry block and set name/code properties plus expectedFeatures.",
    };
  }

  return inference;
}

function candidateSource(config, candidate, index) {
  const stateSlug = sourceSlug(config);
  const id = `${stateSlug}-discovered-${slugify(candidate.type)}-${index + 1}`;
  const ext = urlExtension(candidate.url, candidate.type);
  const inference = inferCandidateConfig(candidate);
  const source = {
    id,
    url: candidate.url,
    localFile: `data/${id}.${ext}`,
    discovery: {
      status: sourceStatus(candidate),
      confidence: candidate.confidence || "medium",
      source: candidate.source || "",
      note: candidate.note || "",
      role: inference.role || "candidate",
      suggestedDownload: inference.suggestedDownload || undefined,
      suggestedParser: inference.suggestedParser || undefined,
      inferenceNotes: inference.notes,
    },
  };
  if (inference.download) {
    source.download = inference.download;
  }
  return source;
}

function inventoryEntry(source, candidate) {
  return {
    category: sourceCategory(candidate),
    file: source.localFile,
    sourceUrl: source.url,
    usedFor: `Candidate discovered by scripts/discover-state-sources.mjs for ${source.discovery.role || "source review"}. Confirm the download strategy, parser format, and reconciliation targets before using it in certified results, review graphs, turnout, or history.`,
    confidence: `Discovery confidence: ${candidate.confidence || "unknown"}. Status: ${source.discovery.status}.`,
  };
}

function checkedEntry(candidate) {
  return {
    category: "Discovered scripted export",
    sourceUrl: candidate.url || candidate.source || "",
    reason: candidate.note || "This candidate needs a scripted postback or browser automation step before it can become a local source file.",
    status: "Needs download strategy",
  };
}

function hasSource(config, url) {
  return (config.sources || []).some((source) => source.url === url);
}

function hasInventory(config, url) {
  return (config.app?.sourceInventory || []).some((entry) => entry.sourceUrl === url);
}

function hasChecked(config, key) {
  return (config.app?.checkedNotUsable || []).some((entry) => entry.sourceUrl === key || entry.sourceUrl === String(key || ""));
}

function applyDiscovery(config, report) {
  config.sources ||= [];
  config.app ||= {};
  config.app.sourcePlan ||= {};
  config.app.sourceInventory ||= [];
  config.app.checkedNotUsable ||= [];

  const downloads = (report.likelyDownloads || []).filter(isImportableDownload).slice(0, limit);
  const scripted = (report.likelyDownloads || []).filter(isPostbackOrScript).slice(0, limit);
  const addedSources = [];
  const addedInventory = [];
  const addedChecked = [];
  let nextSourceIndex = config.sources.length;

  for (const candidate of downloads) {
    if (hasSource(config, candidate.url)) continue;
    const source = candidateSource(config, candidate, nextSourceIndex);
    nextSourceIndex += 1;
    config.sources.push(source);
    addedSources.push(source);
    if (!hasInventory(config, candidate.url)) {
      const entry = inventoryEntry(source, candidate);
      config.app.sourceInventory.push(entry);
      addedInventory.push(entry);
    }
  }

  for (const candidate of scripted) {
    const key = candidate.url || candidate.source;
    if (!key || hasChecked(config, key)) continue;
    const entry = checkedEntry(candidate);
    config.app.checkedNotUsable.push(entry);
    addedChecked.push(entry);
  }

  config.app.sourcePlan.discoveryCandidates = {
    title: "Discovered source candidates",
    detail: `${addedSources.length} source candidate(s) and ${addedChecked.length} scripted-export follow-up(s) were added from ${report.input?.url || report.input?.htmlFile || "a discovery report"}. Confirm download strategies and parser formats before marking any candidate Loaded.`,
    sourceUrl: report.input?.url || "",
    localFile: report.input?.htmlFile || "",
    sourceLastModifiedUtc: "",
    sourceTimestampBasis: "Generated by scripts/discover-state-sources.mjs and scripts/apply-source-discovery.mjs.",
    status: addedSources.length || addedChecked.length ? "Candidate" : "No new candidates",
  };

  return {
    addedSources,
    addedInventory,
    addedChecked,
    sourcePlanStatus: config.app.sourcePlan.discoveryCandidates.status,
  };
}

const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const result = applyDiscovery(config, report);

const summary = {
  status: write ? "written" : "preview",
  config: configPath,
  report: reportPath,
  writeRequiredForMutation: !write,
  addedSources: result.addedSources.map((source) => ({
    id: source.id,
    url: source.url,
    localFile: source.localFile,
    status: source.discovery.status,
    role: source.discovery.role,
    download: source.download || source.discovery.suggestedDownload || null,
    parser: source.discovery.suggestedParser || null,
  })),
  addedInventory: result.addedInventory.length,
  addedCheckedNotUsable: result.addedChecked.length,
  sourcePlanStatus: result.sourcePlanStatus,
};

if (write) {
  fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
