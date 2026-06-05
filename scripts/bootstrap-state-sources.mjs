import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { applyDiscovery, applyDiscoverySummary } from "./apply-source-discovery.mjs";
import { discoverSources, sourceDiscoverySummary } from "./discover-state-sources.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const templatePath = path.join(root, "data/state-configs/_template.json");

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

function stateSlug(code) {
  return String(code || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function normalizeStateCode(code) {
  const normalized = String(code || "").trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(normalized)) {
    throw new Error("State code must be two letters, such as MI or PA.");
  }
  return normalized;
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

export function scaffoldConfig({ state, name = "", authority = "" }) {
  const code = normalizeStateCode(state);
  const displayName = String(name || code).trim();
  const sourceAuthority = String(authority || `${displayName} election authority`).trim();
  const slug = stateSlug(code);
  let text = fs.readFileSync(templatePath, "utf8");
  const replacements = {
    "{{STATE_CODE}}": code,
    "{{STATE_NAME}}": displayName,
    "{{STATE_AUTHORITY}}": sourceAuthority,
    "{{state_slug}}": slug,
  };
  for (const [marker, value] of Object.entries(replacements)) {
    text = text.replaceAll(marker, value);
  }
  return JSON.parse(text);
}

export async function bootstrapStateSources({
  state,
  name = "",
  authority = "",
  url = "",
  htmlFile = "",
  configPath = "",
  reportPath = "",
  write = false,
  force = false,
  limit = 12,
}) {
  const code = normalizeStateCode(state);
  if (!url && !htmlFile) {
    throw new Error("Provide --url, --html-file, or both.");
  }

  const resolvedConfigPath = configPath || path.join(root, "data/state-configs", `${stateSlug(code)}.json`);
  const configExists = fs.existsSync(resolvedConfigPath);
  const shouldScaffold = !configExists || force;
  const config = shouldScaffold
    ? scaffoldConfig({ state: code, name, authority })
    : JSON.parse(fs.readFileSync(resolvedConfigPath, "utf8"));

  const report = await discoverSources({ state: code, url, htmlFile });
  const result = applyDiscovery(config, report, { limit });
  const applySummary = applyDiscoverySummary(result, {
    configPath: resolvedConfigPath,
    reportPath,
    write,
  });

  if (write) {
    writeJson(resolvedConfigPath, config);
    if (reportPath) {
      writeJson(reportPath, report);
    }
  }

  return {
    config,
    report,
    summary: {
      status: write ? "written" : "preview",
      state: code,
      config: resolvedConfigPath,
      configExisted: configExists,
      scaffolded: shouldScaffold,
      forcedScaffold: Boolean(force && configExists),
      report: reportPath || null,
      reportWritten: Boolean(write && reportPath),
      writeRequiredForMutation: !write,
      discovery: sourceDiscoverySummary(report),
      apply: applySummary,
    },
  };
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const state = args.get("state");
  const name = args.get("name") || "";
  const authority = args.get("authority") || "";
  const url = args.get("url") || "";
  const htmlFile = args.get("html-file") || "";
  const configPath = args.get("config") || "";
  const reportPath = args.get("report") || "";
  const write = args.has("write");
  const force = args.has("force");
  const limit = Number(args.get("limit") || 12);

  if (!state) {
    console.error(
      "Usage: node scripts/bootstrap-state-sources.mjs --state XX --name Name --authority Authority --url URL [--html-file PATH] [--config PATH] [--report PATH] [--write] [--force] [--limit N]",
    );
    process.exit(2);
  }

  const { summary } = await bootstrapStateSources({
    state,
    name,
    authority,
    url,
    htmlFile,
    configPath,
    reportPath,
    write,
    force,
    limit,
  });
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
