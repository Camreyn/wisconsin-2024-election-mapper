import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_MANIFEST = "data/az-2024-county-source-manifest.json";
const DEFAULT_OUTPUT = "data/az-2024-county-source-status.json";
const DEFAULT_CACHE_DIR = "outputs/az-county-sources";

function parseArgs(argv = process.argv.slice(2)) {
  const args = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) continue;
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key.slice(2), "true");
    } else {
      args.set(key.slice(2), next);
      index += 1;
    }
  }
  return args;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.resolve(root, file), "utf8"));
}

function writeJson(file, value) {
  const resolved = path.resolve(root, file);
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  fs.writeFileSync(resolved, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function slug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function sourceCachePath(cacheDir, county, source) {
  const extension = source.format === "pdf" ? ".pdf" : source.format === "html" ? ".html" : ".dat";
  return path.resolve(root, cacheDir, `${slug(county)}-${slug(source.label)}${extension}`);
}

async function download(url, output) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 state-election-data-builder",
    },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(output, bytes);
  return bytes.length;
}

function extractPdfText(file) {
  const result = spawnSync("node", ["scripts/extract-pdf-text.mjs", file], {
    cwd: root,
    encoding: "utf8",
    shell: false,
  });
  if (result.status) {
    throw new Error([result.stderr, result.stdout].filter(Boolean).join("\n").trim() || `pdf extraction failed with exit ${result.status}`);
  }
  return result.stdout;
}

function numberText(value) {
  const normalized = String(value || "").replace(/,/g, "");
  return normalized ? Number(normalized) : 0;
}

function firstNumber(line) {
  const match = String(line || "").match(/([0-9][0-9,]*)/);
  return match ? numberText(match[1]) : 0;
}

function candidateVotes(lines, matcher) {
  const line = lines.find((item) => matcher.test(item));
  return firstNumber(line);
}

export function parsePresidentialSummary(text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  const start = lines.findIndex((line) => /^Presidential Electors$/i.test(line));
  if (start < 0) {
    throw new Error("Presidential Electors section not found");
  }
  const end = lines.findIndex((line, index) => index > start && /^Precincts Reporting\b/i.test(line));
  const section = lines.slice(start, end > start ? end : start + 80);
  const trump = candidateVotes(section, /\b(REP|Republican)\b.*Trump\/?Vance|Trump\/?Vance/i);
  const harris = candidateVotes(section, /\b(DEM|Democratic)\b.*Harris\/?Walz|Harris\/?Walz/i);
  const totalVotesCast = candidateVotes(section, /^Total Votes Cast\b/i);
  const overvotes = candidateVotes(section, /^Overvotes\b/i);
  const undervotes = candidateVotes(section, /^Undervotes\b/i);
  const contestTotals = candidateVotes(section, /^Contest Totals\b/i);
  const registeredVoters = candidateVotes(lines.slice(0, start), /^Registered Voters - Total\b/i);
  const ballotsCast = candidateVotes(lines.slice(0, start), /^Ballots Cast - Total\b/i) || contestTotals;
  if (!trump || !harris || !totalVotesCast) {
    throw new Error("Presidential summary totals are incomplete");
  }
  return {
    trump,
    harris,
    other: Math.max(0, totalVotesCast - trump - harris),
    totalVotesCast,
    overvotes,
    undervotes,
    contestTotals,
    ballotsCast,
    registeredVoters,
  };
}

async function probeSource({ county, source, cacheDir, downloadFiles }) {
  const output = sourceCachePath(cacheDir, county, source);
  const summary = {
    label: source.label,
    url: source.url,
    format: source.format,
    access: source.access,
    parserHint: source.parserHint,
    roles: source.roles || [],
    cacheFile: path.relative(root, output).replaceAll("\\", "/"),
    status: "skipped",
  };
  if (source.access !== "downloadable" || source.format !== "pdf" || !(source.roles || []).includes("countyTotals")) {
    summary.reason = "Source is not a downloadable county-total PDF candidate.";
    return summary;
  }
  try {
    if (downloadFiles || !fs.existsSync(output)) {
      summary.bytes = await download(source.url, output);
    } else {
      summary.bytes = fs.statSync(output).size;
    }
    const text = extractPdfText(output);
    summary.presidential = parsePresidentialSummary(text);
    summary.status = "parsed";
    return summary;
  } catch (error) {
    summary.status = "failed";
    summary.error = error.message;
    return summary;
  }
}

export async function probeArizonaCountySources({
  manifestFile = DEFAULT_MANIFEST,
  outputFile = DEFAULT_OUTPUT,
  cacheDir = DEFAULT_CACHE_DIR,
  downloadFiles = false,
} = {}) {
  const manifest = readJson(manifestFile);
  const counties = [];
  for (const county of manifest.counties || []) {
    const sources = [];
    for (const source of county.sourceCandidates || []) {
      sources.push(await probeSource({ county: county.county, source, cacheDir, downloadFiles }));
    }
    const parsed = sources.find((source) => source.status === "parsed" && source.presidential);
    counties.push({
      county: county.county,
      fips: county.fips,
      manifestStatus: county.status,
      status: parsed ? "parsed" : sources.some((source) => source.status === "failed") ? "needs-review" : "not-probed",
      presidential: parsed?.presidential || null,
      sources,
    });
  }
  const parsedCounties = counties.filter((county) => county.status === "parsed");
  const totals = parsedCounties.reduce(
    (accumulator, county) => {
      accumulator.trump += county.presidential.trump;
      accumulator.harris += county.presidential.harris;
      accumulator.other += county.presidential.other;
      accumulator.totalVotesCast += county.presidential.totalVotesCast;
      return accumulator;
    },
    { trump: 0, harris: 0, other: 0, totalVotesCast: 0 },
  );
  const report = {
    state: manifest.state,
    generatedAtUtc: new Date().toISOString(),
    manifestFile,
    cacheDir,
    downloadFiles,
    parsedCountyCount: parsedCounties.length,
    countyCount: counties.length,
    totals,
    counties,
  };
  writeJson(outputFile, report);
  return report;
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const report = await probeArizonaCountySources({
    manifestFile: args.get("manifest") || DEFAULT_MANIFEST,
    outputFile: args.get("output") || DEFAULT_OUTPUT,
    cacheDir: args.get("cache-dir") || DEFAULT_CACHE_DIR,
    downloadFiles: args.has("download"),
  });
  process.stdout.write(
    `${JSON.stringify(
      {
        status: "written",
        output: args.get("output") || DEFAULT_OUTPUT,
        parsedCountyCount: report.parsedCountyCount,
        countyCount: report.countyCount,
        totals: report.totals,
      },
      null,
      2,
    )}\n`,
  );
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
