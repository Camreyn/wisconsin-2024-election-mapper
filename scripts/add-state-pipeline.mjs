import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { bootstrapStateSources } from "./bootstrap-state-sources.mjs";
import { validateStateConfigFile } from "./validate-state-config.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

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

function displayPath(file) {
  return path.relative(root, path.resolve(file)).replaceAll("\\", "/");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function sourceFiles(config) {
  return (config.sources || [])
    .map((source) => source.localFile)
    .filter(Boolean)
    .filter((file) => fs.existsSync(path.join(root, file)));
}

function outputFiles(config) {
  return [
    config.output?.appDataFile,
    config.geometry?.outputFile,
    "data/state-registry.js",
  ].filter(Boolean)
    .filter((file) => fs.existsSync(path.join(root, file)));
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function run(command, args, { allowFailure = false } = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: "utf8",
    shell: false,
  });
  const summary = {
    command: [command, ...args].join(" "),
    status: result.status ?? 1,
    stdout: result.stdout?.trim() || "",
    stderr: result.stderr?.trim() || "",
  };
  if (summary.status && !allowFailure) {
    const output = [summary.stderr, summary.stdout].filter(Boolean).join("\n");
    throw new Error(`${summary.command} failed with exit ${summary.status}${output ? `\n${output}` : ""}`);
  }
  return summary;
}

function gitAddCommand(files) {
  if (!files.length) return "";
  const [first, ...rest] = files;
  if (!rest.length) return `git add ${first}`;
  return [
    `git add ${first} \\`,
    ...rest.map((file, index) => `  ${file}${index === rest.length - 1 ? "" : " \\"}`),
  ].join("\n");
}

export async function runAddStatePipeline({
  state,
  name = "",
  authority = "",
  url = "",
  htmlFile = "",
  configPath = "",
  reportPath = "",
  write = true,
  force = false,
  limit = 12,
  download = false,
  forceDownload = false,
  build = false,
  inspect = true,
  validate = true,
  strictGaps = false,
}) {
  if (!state) throw new Error("State code is required.");
  if (!url && !htmlFile) throw new Error("Provide url or htmlFile.");
  const code = String(state).toUpperCase();
  const resolvedConfigPath = configPath || path.join(root, "data/state-configs", `${stateSlug(code)}.json`);
  const resolvedReportPath = reportPath || path.join(root, "outputs", `${stateSlug(code)}-source-discovery.json`);
  const bootstrap = await bootstrapStateSources({
    state: code,
    name,
    authority,
    url,
    htmlFile,
    configPath: resolvedConfigPath,
    reportPath: resolvedReportPath,
    write,
    force,
    limit,
  });

  const steps = [];
  const configExists = fs.existsSync(resolvedConfigPath);
  let config = configExists ? readJson(resolvedConfigPath) : bootstrap.config;
  const readiness = configExists ? validateStateConfigFile(resolvedConfigPath) : null;
  steps.push({
    name: "bootstrap",
    status: bootstrap.summary.status,
    config: displayPath(resolvedConfigPath),
    report: displayPath(resolvedReportPath),
    addedSources: bootstrap.summary.apply.addedSources.length,
  });
  if (readiness) {
    steps.push({
      name: "readiness",
      status: readiness.status,
      errors: readiness.counts.errors,
      gaps: readiness.counts.gaps,
    });
  }

  if (write && (download || forceDownload || build)) {
    const buildArgs = ["-3", "scripts/build-state-data.py"];
    if (download) buildArgs.push("--download");
    if (forceDownload) buildArgs.push("--force-download");
    buildArgs.push(displayPath(resolvedConfigPath));
    steps.push({ name: "build", ...run("py", buildArgs) });
    config = readJson(resolvedConfigPath);
  }

  if (write && inspect) {
    steps.push({
      name: "inspect:sources",
      ...run("py", ["-3", "scripts/inspect-state-sources.py", displayPath(resolvedConfigPath)], { allowFailure: true }),
    });
  }

  if (write && validate) {
    const validateArgs = ["scripts/validate-state-config.mjs", "--config", displayPath(resolvedConfigPath)];
    if (strictGaps) validateArgs.push("--strict-gaps");
    steps.push({ name: "validate:state-config", ...run("node", validateArgs, { allowFailure: !strictGaps }) });
  }

  const candidateFiles = unique([
    displayPath(resolvedConfigPath),
    fs.existsSync(resolvedReportPath) ? displayPath(resolvedReportPath) : "",
    ...sourceFiles(config),
    ...outputFiles(config),
  ]);

  return {
    status: steps.some((step) => step.status && step.status !== "preview" && step.status !== "written" && step.status !== "ready" && step.status !== "valid_with_gaps")
      ? "failed"
      : "completed",
    state: code,
    steps,
    readiness: configExists ? validateStateConfigFile(resolvedConfigPath) : null,
    filesToReview: candidateFiles,
    gitAddCommand: gitAddCommand(candidateFiles),
    note: "A newly discovered state may correctly finish as valid_with_gaps until source roles, parser mappings, and expected reconciliation counts are promoted from discovery candidates.",
  };
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const summary = await runAddStatePipeline({
    state: args.get("state"),
    name: args.get("name") || "",
    authority: args.get("authority") || "",
    url: args.get("url") || "",
    htmlFile: args.get("html-file") || "",
    configPath: args.get("config") || "",
    reportPath: args.get("report") || "",
    write: !args.has("preview"),
    force: args.has("force"),
    limit: Number(args.get("limit") || 12),
    download: args.has("download"),
    forceDownload: args.has("force-download"),
    build: args.has("build"),
    inspect: !args.has("no-inspect"),
    validate: !args.has("no-validate"),
    strictGaps: args.has("strict-gaps"),
  });
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
