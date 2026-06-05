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
  if (candidate.type === "export-endpoint") return "Needs download strategy";
  return "Candidate";
}

function candidateSource(config, candidate, index) {
  const stateSlug = sourceSlug(config);
  const id = `${stateSlug}-discovered-${slugify(candidate.type)}-${index + 1}`;
  const ext = urlExtension(candidate.url, candidate.type);
  return {
    id,
    url: candidate.url,
    localFile: `data/${id}.${ext}`,
    discovery: {
      status: sourceStatus(candidate),
      confidence: candidate.confidence || "medium",
      source: candidate.source || "",
      note: candidate.note || "",
    },
  };
}

function inventoryEntry(source, candidate) {
  return {
    category: sourceCategory(candidate),
    file: source.localFile,
    sourceUrl: source.url,
    usedFor: "Candidate discovered by scripts/discover-state-sources.mjs. Confirm the download strategy, parser format, and reconciliation targets before using it in certified results, review graphs, turnout, or history.",
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
  })),
  addedInventory: result.addedInventory.length,
  addedCheckedNotUsable: result.addedChecked.length,
  sourcePlanStatus: result.sourcePlanStatus,
};

if (write) {
  fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
