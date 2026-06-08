import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(root, "data");
const captureDir = path.join(dataDir, "review-sources");
const auditPath = path.join(dataDir, "review-source-audit.json");
const checkedAt = "2026-06-08";

const directTargets = {
  AR: [
    {
      label: "Arkansas TotalResults app config",
      url: "https://enr.totalresults.com/arkansas/config.json",
      localFile: "data/review-sources/ar-config.json",
      minBytes: 500,
      dataKind: "source-page",
      notes: "Official Arkansas ENR config used to identify the TotalResults client id and API endpoints.",
    },
    {
      label: "Arkansas TotalResults election list",
      url: "https://enr-results-api.totalresults.com/Election/GetElectionList?cid=arkansas",
      localFile: "data/review-sources/ar-election-list.json",
      minBytes: 2000,
      dataKind: "source-page",
      notes: "Official TotalResults election list showing 1846 as the 2024 General election id.",
    },
    {
      label: "Arkansas TotalResults app bundle",
      url: "https://enr.totalresults.com/arkansas/assets/index-_rT17pbd.js",
      localFile: "data/review-sources/ar-index-_rT17pbd.js",
      minBytes: 1000000,
      dataKind: "source-page",
      notes: "Official Arkansas ENR app bundle containing the TotalResults API route definitions.",
    },
    {
      label: "Arkansas 2024 General election info",
      url: "https://enr-results-api.totalresults.com/Election/GetElectionInfo?cId=arkansas&electionID=1846",
      localFile: "data/review-sources/ar-2024-general-election-info.json",
      minBytes: 100000,
      dataKind: "source-page",
      notes: "Official TotalResults election metadata for the 2024 general election.",
    },
    {
      label: "Arkansas 2024 General contest search list",
      url: "https://enr-results-api.totalresults.com/Contest/GetContestSearchList?cid=arkansas&electionID=1846",
      localFile: "data/review-sources/ar-2024-general-contest-search-list.json",
      minBytes: 100000,
      dataKind: "source-page",
      notes: "Official TotalResults contest metadata for identifying President and U.S. House contests.",
    },
  ],
  ID: [
    {
      label: "Idaho 2024 President precinct results CSV",
      url: "https://canvass.sos.idaho.gov/eng/contests/download/19439/show_granularity_dt_id:7/.csv",
      localFile: "data/id-2024-president-precinct-results.csv",
      minBytes: 50000,
      notes: "Official Idaho SOS canvass export at precinct granularity.",
    },
    {
      label: "Idaho 2024 U.S. House District 1 precinct results CSV",
      url: "https://canvass.sos.idaho.gov/eng/contests/download/19440/show_granularity_dt_id:7/.csv",
      localFile: "data/id-2024-us-house-district-1-precinct-results.csv",
      minBytes: 20000,
      notes: "Official Idaho SOS canvass export at precinct granularity.",
    },
    {
      label: "Idaho 2024 U.S. House District 2 precinct results CSV",
      url: "https://canvass.sos.idaho.gov/eng/contests/download/19441/show_granularity_dt_id:7/.csv",
      localFile: "data/id-2024-us-house-district-2-precinct-results.csv",
      minBytes: 20000,
      notes: "Official Idaho SOS canvass export at precinct granularity.",
    },
  ],
  MD: [
    {
      label: "Maryland 2024 General Election all precinct results CSV",
      url: "https://elections.maryland.gov/elections/archive/2024/election_data/PG24_AllPrecincts.csv",
      localFile: "data/md-2024-general-all-precincts.csv",
      minBytes: 1000000,
      notes: "Official SBE raw election data file with precinct rows, contest names, candidates, parties, and vote-method columns.",
    },
    {
      label: "Maryland 2024 General Election state precinct reference",
      url: "https://elections.maryland.gov/elections/archive/2024/Polling%20Places%20AEMS%20PG24.xlsx",
      localFile: "data/md-2024-state-precinct-reference.xlsx",
      minBytes: 100000,
      notes: "Official SBE precinct reference workbook for the 2024 general election.",
    },
    {
      label: "Maryland 2024 election data index",
      url: "https://elections.maryland.gov/elections/archive/2024/election_data/index.html",
      localFile: "data/review-sources/md-election-data-index.html",
      minBytes: 20000,
      rejectIfContains: ["Page Not Found"],
      dataKind: "source-page",
      notes: "Official SBE page that links statewide and county raw election data files.",
    },
  ],
  NC: [
    {
      label: "North Carolina 2024 General Election precinct results ZIP",
      url: "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip",
      localFile: "data/nc-2024-general-results-precinct.zip",
      minBytes: 1000000,
      notes: "Official NCSBE results data file. Includes per-precinct vote counts by contest and voting method.",
    },
    {
      label: "North Carolina historical election results data page",
      url: "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data",
      localFile: "data/review-sources/nc-historical-election-results-data.html",
      minBytes: 20000,
      dataKind: "source-page",
      notes: "Official NCSBE source page documenting results data and precinct-sort limitations.",
    },
  ],
  OH: [
    {
      label: "Ohio statewide races precinct-level workbook",
      url: "https://web.archive.org/web/20241207004035if_/https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-races-precint-level.xlsx",
      localFile: "data/oh-2024-statewide-races-precinct-level.xlsx",
      minBytes: 100000,
      notes: "Archived binary capture of the official Ohio SOS precinct-level workbook; live asset currently redirects to the data portal shell.",
    },
  ],
};

const portalPageTargets = {
  AR: "https://enr.totalresults.com/arkansas",
  GA: "https://results.sos.ga.gov/results/public/Georgia/2024NovGen",
  ID: "https://canvass.sos.idaho.gov/eng/contests/view/19439/",
  IN: "https://enr.indianavoters.in.gov/archive/2024General/index.html",
  LA: "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/",
  OK: "https://results.okelections.gov/OKER/?elecDate=20241105",
  OR: "https://results.oregonvotes.gov/resultsSW.aspx?type=FED&map=CTY&eid=107",
  SC: "https://www.enr-scvotes.org/SC/122436/web.345435/",
  WA: "https://results.vote.wa.gov/results/20241105/president-vice-president_bycounty.html",
  WV: "https://results.enr.clarityelections.com/WV/122766/web.345435/#/summary",
};

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function localPath(file) {
  return path.join(root, file.replaceAll("/", path.sep));
}

function existingAuditFiles(row) {
  return String(row.local_file || "")
    .split(";")
    .map((file) => file.trim())
    .filter((file) => file.startsWith("data/") && !file.endsWith("app-data.js"))
    .map((file) => ({
      file,
      exists: fs.existsSync(localPath(file)),
      bytes: fs.existsSync(localPath(file)) ? fs.statSync(localPath(file)).size : 0,
    }));
}

function inferCollectionLane(row) {
  const status = row.collection_status || "";
  if (status.includes("local_row_source_collected")) return "already-local-row-source";
  if (status.includes("official_precinct_source_identified")) return "direct-official-target";
  if (status.includes("portal")) return "portal-capture";
  if (status.includes("county_local")) return "county-local-needed";
  if (status.includes("state_or_county")) return "source-discovery-needed";
  return "review-needed";
}

async function fetchTarget(target) {
  const output = localPath(target.localFile);
  if (fs.existsSync(output)) {
    const buffer = fs.readFileSync(output);
    const text = buffer.toString("utf8");
    const rejected = (target.rejectIfContains || []).find((needle) => text.includes(needle));
    if (buffer.length >= (target.minBytes || 1) && !rejected) {
      return {
        label: target.label,
        url: target.url,
        localFile: target.localFile,
        httpStatus: "local",
        finalUrl: target.url,
        contentType: "",
        bytes: buffer.length,
        captured: true,
        reason: "already captured",
        notes: target.notes || "",
        dataKind: target.dataKind || "data",
      };
    }
  }

  const response = await fetch(target.url, {
    headers: {
      "User-Agent": "Mozilla/5.0 review-source-collector/1.0",
      Accept: "*/*",
    },
    redirect: "follow",
  });
  const buffer = Buffer.from(await response.arrayBuffer());
  const contentType = response.headers.get("content-type") || "";
  const text = contentType.includes("text") || contentType.includes("html") ? buffer.toString("utf8") : "";
  const rejected = (target.rejectIfContains || []).find((needle) => text.includes(needle));
  const ok = response.ok && buffer.length >= (target.minBytes || 1) && !rejected;
  if (ok) {
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, buffer);
  }
  return {
    label: target.label,
    url: target.url,
    localFile: target.localFile,
    httpStatus: response.status,
    finalUrl: response.url,
    contentType,
    bytes: buffer.length,
    captured: ok,
    reason: ok
      ? "captured"
      : rejected
        ? `rejected content marker: ${rejected}`
        : response.ok
          ? `response too small: ${buffer.length} bytes`
          : `HTTP ${response.status}`,
    notes: target.notes || "",
    dataKind: target.dataKind || "data",
  };
}

function portalTargetFor(state, url) {
  return {
    label: `${state} official portal/source page capture`,
    url,
    localFile: `data/review-sources/${state.toLowerCase()}-official-review-source.html`,
    minBytes: state === "AR" ? 500 : 2000,
    rejectIfContains: ["403 ERROR", "403 - Forbidden", "Content not found"],
    dataKind: "source-page",
    notes: "Captured page shell/source page for endpoint inspection; may still require browser or API-specific extraction.",
  };
}

async function main() {
  fs.mkdirSync(captureDir, { recursive: true });
  const audit = readJson(auditPath);
  const rows = [];

  for (const row of audit.rows) {
    const state = row.state;
    const captures = [];
    const targets = [...(directTargets[state] || [])];
    if (portalPageTargets[state]) {
      targets.push(portalTargetFor(state, portalPageTargets[state]));
    }

    for (const target of targets) {
      try {
        captures.push(await fetchTarget(target));
      } catch (error) {
        captures.push({
          label: target.label,
          url: target.url,
          localFile: target.localFile,
          httpStatus: "",
          finalUrl: "",
          contentType: "",
          bytes: 0,
          captured: false,
          reason: error.message,
          notes: target.notes || "",
          dataKind: target.dataKind || "data",
        });
      }
    }

    const auditFiles = existingAuditFiles(row);
    const capturedFiles = captures.filter((capture) => capture.captured).map((capture) => capture.localFile);
    const capturedDataFiles = captures
      .filter((capture) => capture.captured && capture.dataKind !== "source-page")
      .map((capture) => capture.localFile);
    const capturedSourceFiles = captures
      .filter((capture) => capture.captured && capture.dataKind === "source-page")
      .map((capture) => capture.localFile);
    const hasExisting = auditFiles.some((file) => file.exists);
    let captureStatus;
    if (capturedDataFiles.length) {
      captureStatus = captures.some((capture) => !capture.captured) ? "data partially captured" : "data captured";
    } else if (capturedSourceFiles.length) {
      captureStatus = captures.some((capture) => !capture.captured) ? "source page partially captured" : "source page captured";
    } else if (captures.length) {
      captureStatus = "not captured";
    } else {
      captureStatus = hasExisting ? "already present or needs parser/source discovery" : "not captured";
    }
    rows.push({
      state,
      lane: inferCollectionLane(row),
      auditCollectionStatus: row.collection_status,
      rowLevel: row.row_level,
      existingLocalFiles: auditFiles.filter((file) => file.exists).map((file) => `${file.file} (${file.bytes} bytes)`).join("; "),
      capturedFiles: capturedFiles.join("; "),
      captureStatus,
      nextStep: row.next_step,
      captures,
    });
  }

  const summary = rows.reduce((acc, row) => {
    acc[row.captureStatus] = (acc[row.captureStatus] || 0) + 1;
    return acc;
  }, {});

  const manifest = { checkedAt, rows, summary };
  fs.writeFileSync(path.join(dataDir, "review-source-collection.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

  const headers = [
    "state",
    "lane",
    "audit_collection_status",
    "row_level",
    "capture_status",
    "existing_local_files",
    "captured_files",
    "next_step",
  ];
  const csvRows = [
    headers.join(","),
    ...rows.map((row) =>
      [
        row.state,
        row.lane,
        row.auditCollectionStatus,
        row.rowLevel,
        row.captureStatus,
        row.existingLocalFiles,
        row.capturedFiles,
        row.nextStep,
      ]
        .map(csvCell)
        .join(","),
    ),
  ];
  fs.writeFileSync(path.join(dataDir, "review-source-collection.csv"), `${csvRows.join("\n")}\n`, "utf8");

  const lines = [
    "# Review Source Collection",
    "",
    `Checked at: ${checkedAt}`,
    "",
    "This file tracks source files collected for the review-graph lane. It is intentionally separate from turnout collection.",
    "",
    "## Summary",
    "",
    ...Object.entries(summary).map(([status, count]) => `- ${status}: ${count}`),
    "",
    "## Captured Targets",
    "",
    "| State | Status | Captured files | Existing local files | Next step |",
    "| --- | --- | --- | --- | --- |",
    ...rows.map((row) =>
      [
        row.state,
        row.captureStatus,
        row.capturedFiles || "",
        row.existingLocalFiles || "",
        row.nextStep || "",
      ]
        .map((cell) => String(cell).replaceAll("|", "\\|"))
        .join(" | "),
    ).map((line) => `| ${line} |`),
  ];
  fs.writeFileSync(path.join(root, "docs", "review-source-collection.md"), `${lines.join("\n")}\n`, "utf8");

  process.stdout.write(`${JSON.stringify({ checkedAt, summary }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
