import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function parseArgs(argv = process.argv.slice(2)) {
  const args = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key.startsWith("--")) {
      const next = argv[index + 1];
      if (!next || next.startsWith("--")) {
        args.set(key.slice(2), "true");
      } else {
        args.set(key.slice(2), next);
        index += 1;
      }
    }
  }
  return args;
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

const roleSignals = {
  certifiedResults: [
    [/certif|official|canvass|result|electionresult|getelectionresult|statewide|president/i, 4],
    [/county|precinct|ward/i, 2],
    [/turnout|registration|registered/i, -4],
    [/geojson|feature|mapserver|shape|boundary/i, -5],
  ],
  reviewCharts: [
    [/precinct|ward|reporting/i, 4],
    [/zip|getprecinctresults|detail|by[-_\s]?precinct/i, 4],
    [/senate|congress|down[-_\s]?ballot/i, 2],
    [/turnout|registration|registered/i, -3],
  ],
  turnout: [
    [/turnout|ballots?\s*cast|registered|registration|voterturnout|getvoterturnoutfile/i, 6],
    [/precinct|county|ward/i, 1],
    [/geojson|feature|mapserver|shape|boundary/i, -5],
  ],
  geometry: [
    [/geojson|featureserver|mapserver|arcgis|tigerweb|boundary|boundaries|shape/i, 8],
    [/county/i, 1],
    [/result|turnout|candidate|election/i, -4],
  ],
  historicalBaseline: [
    [/historical|past|archive|previous|20(12|16|20)|2012|2016|2020/i, 5],
    [/president|general/i, 2],
    [/turnout|registration|registered/i, -3],
  ],
};

function roleClassification(candidate) {
  const text = [
    candidate.type,
    candidate.url,
    candidate.rawUrl,
    candidate.source,
    candidate.note,
    candidate.text,
  ].join(" ");
  const scores = Object.entries(roleSignals).map(([role, signals]) => {
    const reasons = [];
    let score = 0;
    for (const [pattern, weight] of signals) {
      if (!pattern.test(text)) continue;
      score += weight;
      reasons.push(`${weight > 0 ? "+" : ""}${weight}: ${pattern.source}`);
    }
    if (candidate.type === "geometry" && role === "geometry") score += 8;
    if (candidate.type === "zip" && role === "reviewCharts") score += 4;
    if (candidate.type === "spreadsheet" && role === "certifiedResults") score += 2;
    if (candidate.type === "pdf" && role === "turnout") score += 1;
    return { role, score, reasons };
  }).sort((left, right) => right.score - left.score);
  const best = scores[0] || { role: "candidate", score: 0, reasons: [] };
  return {
    role: best.score > 0 ? best.role : "candidate",
    confidence: best.score >= 8 ? "high" : best.score >= 4 ? "medium" : best.score > 0 ? "low" : "unknown",
    scores: scores.filter((item) => item.score > 0).slice(0, 4),
  };
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
  const classification = roleClassification(candidate);
  const inference = {
    status: "",
    role: classification.role,
    roleConfidence: classification.confidence,
    roleScores: classification.scores,
    download: null,
    suggestedDownload: null,
    suggestedParser: null,
    notes: [],
  };

  if (loweredUrl.includes("mvic.sos.state.mi.us/votehistory/getelectionresultfile")) {
    inference.status = "Candidate";
    inference.role = "certifiedResults";
    inference.roleConfidence = "high";
    inference.download = { type: "browserDownload", headless: false, timeoutMs: 120000 };
    inference.suggestedParser = {
      certifiedResultsFormat: "michiganCountyTab",
      note: "MVIC county result export; configure contestName and candidate rules before marking Loaded.",
    };
    inference.notes.push("Protected MVIC endpoint; browser-backed download inferred.");
  } else if (loweredUrl.includes("mvic.sos.state.mi.us/votehistory/getvoterturnoutfile")) {
    inference.status = "Candidate";
    inference.role = "turnout";
    inference.roleConfidence = "high";
    inference.download = { type: "browserDownload", headless: false, timeoutMs: 120000 };
    inference.suggestedParser = {
      turnoutFormat: "michiganMvicCountyTurnout",
      note: "MVIC turnout export usually needs an official registration denominator source.",
    };
    inference.notes.push("Protected MVIC endpoint; browser-backed download inferred.");
  } else if (loweredUrl.includes("mvic.sos.state.mi.us/votehistory/getprecinctresultsfile")) {
    inference.status = "Candidate";
    inference.role = "reviewCharts";
    inference.roleConfidence = "high";
    inference.download = { type: "browserDownload", headless: false, timeoutMs: 180000 };
    inference.suggestedParser = {
      reviewChartsFormat: "tabDelimitedZipComparison",
      note: "Inspect ZIP lookup/vote files and configure zipTables, contest keys, party codes, and rowLabel.",
    };
    inference.notes.push("Protected MVIC precinct ZIP endpoint; browser-backed download inferred.");
  } else if (/results\.sos\.nd\.gov\/resultsexport\.aspx/i.test(url)) {
    inference.status = "Needs postback parameters";
    inference.role = "certifiedResults";
    inference.roleConfidence = "high";
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
    inference.role = inference.role === "candidate" ? "reviewCharts" : inference.role;
    inference.suggestedParser = {
      reviewChartsFormat: "tabDelimitedZipComparison",
      note: "Use this when the ZIP separates vote rows from lookup files; otherwise add a source-specific parser.",
    };
  } else if (candidate.type === "spreadsheet") {
    inference.role = inference.role === "candidate" ? "certifiedResults" : inference.role;
    inference.suggestedParser = {
      certifiedResultsFormat: "xlsxPrecinctAggregation",
      reviewChartsFormat: "xlsxPrecinctComparison",
      turnoutFormat: "xlsxPrecinctRows",
      historicalFormat: "officialCountyResultText",
      note: "Map sheet names and columns after inspecting the workbook.",
    };
  } else if (candidate.type === "csv") {
    inference.role = inference.role === "candidate" ? "certifiedResults" : inference.role;
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
      roleConfidence: inference.roleConfidence || "unknown",
      roleScores: inference.roleScores || [],
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

function accessBarrierEntry(report) {
  return {
    category: "Protected election-results application",
    sourceUrl: report.input?.url || report.input?.htmlFile || "",
    reason: report.accessBarrier?.message || "The discovery input was blocked by source-site access protection.",
    status: `Blocked by ${report.accessBarrier?.type || "access protection"}`,
    nextStep: report.accessBarrier?.nextStep || "Use an interactive browser capture or locate the official API/export endpoint.",
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

export function applyDiscovery(config, report, options = {}) {
  const limit = Number(options.limit || 12);
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

  if (report.accessBarrier?.status === "blocked") {
    const key = report.input?.url || report.input?.htmlFile || "";
    if (!hasChecked(config, key)) {
      const entry = accessBarrierEntry(report);
      config.app.checkedNotUsable.push(entry);
      addedChecked.push(entry);
    }
  }

  const accessBlocked = report.accessBarrier?.status === "blocked";
  config.app.sourcePlan.discoveryCandidates = {
    title: "Discovered source candidates",
    detail: accessBlocked
      ? `${report.accessBarrier.type} access protection blocked source discovery for ${report.input?.url || report.input?.htmlFile || "the discovery input"}. Use an interactive browser capture or official API/export endpoint before promoting sources.`
      : `${addedSources.length} source candidate(s) and ${addedChecked.length} scripted-export follow-up(s) were added from ${report.input?.url || report.input?.htmlFile || "a discovery report"}. Confirm download strategies and parser formats before marking any candidate Loaded.`,
    sourceUrl: report.input?.url || "",
    localFile: report.input?.htmlFile || "",
    sourceLastModifiedUtc: "",
    sourceTimestampBasis: "Generated by scripts/discover-state-sources.mjs and scripts/apply-source-discovery.mjs.",
    status: accessBlocked ? "Blocked by source protection" : addedSources.length || addedChecked.length ? "Candidate" : "No new candidates",
  };

  return {
    addedSources,
    addedInventory,
    addedChecked,
    sourcePlanStatus: config.app.sourcePlan.discoveryCandidates.status,
  };
}

export function applyDiscoverySummary(result, { configPath, reportPath, write }) {
  return {
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
      roleConfidence: source.discovery.roleConfidence || "unknown",
    })),
    addedInventory: result.addedInventory.length,
    addedCheckedNotUsable: result.addedChecked.length,
    sourcePlanStatus: result.sourcePlanStatus,
  };
}

export function applyDiscoveryToConfigFile({ configPath, reportPath, write = false, limit = 12 }) {
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
  const result = applyDiscovery(config, report, { limit });
  const summary = applyDiscoverySummary(result, { configPath, reportPath, write });
  if (write) {
    fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
  }
  return { config, report, result, summary };
}

function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const configPath = args.get("config");
  const reportPath = args.get("report");
  const write = args.has("write");
  const limit = Number(args.get("limit") || 12);

  if (!configPath || !reportPath) {
    console.error("Usage: node scripts/apply-source-discovery.mjs --config data/state-configs/xx.json --report report.json [--write] [--limit N]");
    process.exit(2);
  }

  const { summary } = applyDiscoveryToConfigFile({ configPath, reportPath, write, limit });
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
