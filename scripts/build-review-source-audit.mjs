import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const configDir = path.join(root, "data", "state-configs");
const checkedAt = "2026-06-08";

const headers = [
  "state",
  "review_graph_status",
  "collection_status",
  "authority",
  "source_title",
  "source_url",
  "local_file",
  "row_level",
  "has_president_rows",
  "comparison_contest_status",
  "parser_fit",
  "next_step",
  "caveats",
  "checked_at",
];

const overrides = {
  AK: {
    collection_status: "local_row_source_collected",
    row_level: "precinct plus district-level rows",
    has_president_rows: true,
    comparison_contest_status: "comparison contest present in ENR CSV; needs mapping",
    parser_fit: "new Alaska ENR precinct review parser",
    next_step: "Map President and U.S. Representative rows from ENRbyPrecinct.csv into review rows.",
    caveats: "HD99 is non-geographic and should remain documented separately from mapped district rows.",
  },
  AR: {
    collection_status: "official_portal_identified_no_download",
    source_title: "Arkansas SOS 2024 General Election TotalResults portal",
    row_level: "county in current payload; precinct export not exposed",
    has_president_rows: false,
    comparison_contest_status: "needs precinct/export confirmation",
    parser_fit: "TotalResults portal inspection or SOS data request",
    next_step: "Inspect TotalResults network payloads for precinct endpoints; if unavailable, use SOS guidance to request 2024 precinct data.",
    caveats: "Arkansas SOS election-results page notes some downloads are temporarily unavailable during vendor transition.",
  },
  AZ: {
    collection_status: "county_local_sources_partially_collected",
    source_title: "Arizona county official precinct summary/canvass reports",
    source_url: "data/az-2024-county-source-manifest.json",
    local_file: "data/az-2024-county-source-manifest.json; data/az-2024-county-source-status.json",
    row_level: "county-local precinct/counting group",
    has_president_rows: true,
    comparison_contest_status: "varies by county report",
    parser_fit: "county PDF/HTML precinct parser family",
    next_step: "Complete county-by-county report collection and normalize report-specific precinct sections.",
    caveats: "No single statewide precinct results export has been identified; county report layouts vary.",
  },
  CA: {
    collection_status: "county_local_required",
    source_title: "California county official Statements of Vote / precinct reports",
    row_level: "county-local precinct",
    has_president_rows: true,
    comparison_contest_status: "varies by county SOV",
    parser_fit: "county PDF/CSV/XLS parser family",
    next_step: "Collect county SOV or precinct result files from county election offices; statewide SOS SOV is county-level.",
    caveats: "California SOS official statewide results page points to final official results but not a statewide precinct export.",
  },
  CO: {
    collection_status: "statewide_precinct_source_identified",
    source_title: "2024 General Election Precinct-Level Results",
    source_url: "https://redistrictingdatahub.org/state/colorado/",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "likely present; inspect fields after download",
    parser_fit: "Colorado SOS precinct results parser",
    next_step: "Download the Colorado Secretary of State precinct-level results package and map President plus a statewide/congressional comparison contest.",
    caveats: "RDH indexes the source as Colorado Secretary of State; prefer a direct SOS download URL if exposed during download.",
  },
  CT: {
    collection_status: "local_row_source_collected",
    row_level: "town",
    has_president_rows: true,
    comparison_contest_status: "town-level comparison contest needs mapping",
    parser_fit: "Connecticut Statement of Vote town comparison parser",
    next_step: "Map a statewide down-ballot contest from the Statement of Vote text to the same town rows.",
    caveats: "App geometry is planning-region level; review graph rows can be town-level source rows without polygon geometry.",
  },
  DE: {
    collection_status: "local_row_source_collected",
    row_level: "election district",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping",
    parser_fit: "Delaware report HTML election-district parser",
    next_step: "Map President and a statewide comparison race from the official report page election-district rows.",
    caveats: "County map remains county-level while review graph rows can use election-district labels.",
  },
  GA: {
    collection_status: "county_local_required",
    source_title: "Georgia county official Statement of Votes Cast reports",
    row_level: "county-local precinct",
    has_president_rows: true,
    comparison_contest_status: "varies by county SOV",
    parser_fit: "county SOV parser family",
    next_step: "Collect official county SOV reports or identify a statewide precinct export behind the SOS portal.",
    caveats: "Loaded Georgia workbook is county-level; county SOVs are the reliable precinct source identified so far.",
  },
  HI: {
    collection_status: "local_row_source_collected",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping",
    parser_fit: "Hawaii media/precinct file parser",
    next_step: "Map President and U.S. Senate or another statewide contest from media.txt/precinct.pdf.",
    caveats: "Hawaii county geometry does not include Kalawao as a separate presidential row.",
  },
  IA: {
    collection_status: "official_source_not_found",
    source_title: "Iowa precinct or reporting-unit results",
    row_level: "unknown",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search Iowa SOS and county auditor sites for official precinct-level general-election canvass/result exports.",
    caveats: "The loaded Iowa canvass PDF is county-level, and SOS PDF downloads are access-blocked in this environment.",
  },
  ID: {
    collection_status: "official_portal_identified_needs_capture",
    row_level: "portal result rows",
    has_president_rows: true,
    comparison_contest_status: "needs portal endpoint inspection",
    parser_fit: "Idaho Canvass portal export/parser",
    next_step: "Inspect canvass.sos.idaho.gov network exports for precinct or reporting-unit contest rows.",
    caveats: "Current app import uses county-level CSV from the official portal.",
  },
  IL: {
    collection_status: "local_row_source_collected",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "needs comparison contest source or columns",
    parser_fit: "Illinois precinct CSV comparison parser",
    next_step: "Collect/map a down-ballot contest at the same precinct grain.",
    caveats: "Presidential precinct rows are already local; review graph still needs same-row comparison votes.",
  },
  IN: {
    collection_status: "official_portal_identified_needs_capture",
    row_level: "unknown ENR detail",
    has_president_rows: false,
    comparison_contest_status: "needs endpoint inspection",
    parser_fit: "Indiana ENR archive parser",
    next_step: "Inspect Indiana ENR archive payloads for precinct/detail endpoints beyond the county presidential payload.",
    caveats: "Current official payload is county-level for this app import.",
  },
  KS: {
    collection_status: "local_row_source_collected",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping/source",
    parser_fit: "Kansas workbook precinct parser",
    next_step: "Map precinct President rows and collect a same-grain down-ballot workbook or sheet.",
    caveats: "Current local workbook is presidential results; comparison contest availability must be confirmed.",
  },
  KY: {
    collection_status: "state_or_county_source_needed",
    source_title: "Kentucky precinct results",
    row_level: "unknown",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search Kentucky SBE and county clerk/SBE result downloads for official precinct-level 2024 general files.",
    caveats: "Certification PDF is county-level.",
  },
  LA: {
    collection_status: "official_portal_identified_needs_capture",
    row_level: "precinct in GeauxVote portal",
    has_president_rows: true,
    comparison_contest_status: "likely present; needs JSON capture",
    parser_fit: "Louisiana GeauxVote race/precinct JSON parser",
    next_step: "Capture official precinct-level race JSON for President plus a comparison contest from the Voter Portal.",
    caveats: "Current local source is parish-level only.",
  },
  MA: {
    collection_status: "local_row_source_collected",
    row_level: "municipality/PD43+ rows",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping",
    parser_fit: "Massachusetts PD43+ municipal comparison parser",
    next_step: "Map President and U.S. Senate or another statewide race from PD43+ municipal rows.",
    caveats: "Precinct-level availability is not confirmed; municipality-level may be the practical review grain.",
  },
  MD: {
    collection_status: "official_precinct_source_identified",
    source_title: "Maryland 2024 General Election precinct results",
    source_url: "https://elections.maryland.gov/elections/2024/election_data/index.html",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "likely present; inspect export files",
    parser_fit: "Maryland precinct download parser",
    next_step: "Download official precinct-level 2024 general election files and map President plus Senate.",
    caveats: "Current local source is county breakdown HTML.",
  },
  ME: {
    collection_status: "local_row_source_collected",
    row_level: "municipality",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping/source",
    parser_fit: "Maine municipality workbook comparison parser",
    next_step: "Collect or map a same-municipality down-ballot workbook if available.",
    caveats: "Statewide UOCAVA is not county-assigned.",
  },
  MO: {
    collection_status: "state_or_county_source_needed",
    source_title: "Missouri precinct results",
    row_level: "unknown/county-local",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search Missouri SOS and county election authority result files for official precinct-level 2024 general data.",
    caveats: "SOS actual-results PDF is county-level.",
  },
  MS: {
    collection_status: "official_source_needs_review",
    row_level: "county in loaded recap; precinct source unknown",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Inspect Mississippi SOS downloads and county election commission files for precinct-level recap/reporting-unit data.",
    caveats: "Loaded recap sheet source is county-level.",
  },
  MT: {
    collection_status: "state_or_county_source_needed",
    source_title: "Montana precinct results",
    row_level: "unknown/county-local",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search Montana SOS and county election offices for precinct-level 2024 general returns.",
    caveats: "State canvass PDF is county-level.",
  },
  NC: {
    collection_status: "official_precinct_source_identified",
    source_title: "NCSBE Historical Election Results Data",
    source_url: "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data",
    row_level: "precinct sort",
    has_president_rows: true,
    comparison_contest_status: "likely present in precinct-sort files",
    parser_fit: "North Carolina precinct-sort parser",
    next_step: "Download official precinct-sort data and map President plus a statewide comparison contest.",
    caveats: "Current local ENR archive uses county result files; turnout ZIPs are separate and should not be modified here.",
  },
  NE: {
    collection_status: "state_or_county_source_needed",
    source_title: "Nebraska precinct results",
    row_level: "unknown/county-local",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search Nebraska SOS and county election offices for precinct-level 2024 general result files.",
    caveats: "Canvass book presidential table is county-level.",
  },
  NH: {
    collection_status: "official_town_source_needed",
    source_title: "New Hampshire town-level 2024 general results",
    row_level: "town",
    has_president_rows: false,
    comparison_contest_status: "needs town-level source capture",
    parser_fit: "New Hampshire town result parser",
    next_step: "Locate official SOS town-level general-election result files for President and a comparison contest.",
    caveats: "Loaded presidential summary PDF is county-level.",
  },
  NJ: {
    collection_status: "county_local_required",
    source_title: "New Jersey county official precinct/municipal results",
    row_level: "county-local precinct/municipality",
    has_president_rows: false,
    comparison_contest_status: "needs county source collection",
    parser_fit: "county report parser family",
    next_step: "Collect county official precinct/municipal result files; state official PDF is county-level.",
    caveats: "No statewide precinct export is identified in the app sources.",
  },
  NM: {
    collection_status: "local_row_source_collected",
    row_level: "precinct in Civera CSV",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping/source",
    parser_fit: "Civera contest precinct CSV comparison parser",
    next_step: "Map Civera precinct rows and collect a same-grain comparison contest export.",
    caveats: "Current app promotion imports county rows only from the contest CSV.",
  },
  NV: {
    collection_status: "county_local_or_archive_required",
    source_title: "Nevada precinct results",
    row_level: "unknown/county-local",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search Nevada SOS/county election offices or archived SOS downloads for precinct-level 2024 general data.",
    caveats: "Live Nevada SOS pages are protected by Incapsula in this environment.",
  },
  NY: {
    collection_status: "county_local_required",
    source_title: "New York county board official precinct/election-district results",
    row_level: "county-local precinct/election district",
    has_president_rows: false,
    comparison_contest_status: "needs county source collection",
    parser_fit: "county CSV/PDF parser family",
    next_step: "Collect county board precinct/election-district result files; NYS export currently loaded is county-level.",
    caveats: "No statewide precinct export is identified in the app sources.",
  },
  OH: {
    collection_status: "official_precinct_source_identified",
    source_title: "Ohio statewide races precinct-level workbook",
    source_url: "https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-races-precint-level.xlsx",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "likely present for statewide races",
    parser_fit: "Ohio statewide-races precinct workbook parser",
    next_step: "Download or archive-fetch the official workbook and map President plus Senate.",
    caveats: "The source filename uses 'precint' in the official URL.",
  },
  OK: {
    collection_status: "official_portal_identified_needs_capture",
    row_level: "unknown OKER detail",
    has_president_rows: false,
    comparison_contest_status: "needs endpoint inspection",
    parser_fit: "OKER precinct/detail parser",
    next_step: "Inspect OKER static files for precinct/detail results beyond county ENR payloads.",
    caveats: "Current local OKER payload is county-level for this app pass.",
  },
  OR: {
    collection_status: "official_export_needs_precinct_parameters",
    source_title: "Oregon election results export service",
    row_level: "unknown export grain",
    has_president_rows: false,
    comparison_contest_status: "needs export parameter inspection",
    parser_fit: "Oregon ResultsExport precinct parser",
    next_step: "Inspect Oregon ResultsExport/API parameters for precinct-level President and comparison contest rows.",
    caveats: "Current local map data is county-level.",
  },
  RI: {
    collection_status: "local_row_source_collected",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping",
    parser_fit: "Rhode Island summary workbook comparison parser",
    next_step: "Map Candidate_Breakout precinct rows to a comparison contest.",
    caveats: "Federal precinct rows may need special handling.",
  },
  SC: {
    collection_status: "official_portal_identified_needs_capture",
    row_level: "unknown ENR detail",
    has_president_rows: false,
    comparison_contest_status: "needs endpoint inspection",
    parser_fit: "South Carolina ENR precinct/detail parser",
    next_step: "Inspect ENR static JSON for precinct/detail records or collect county reports.",
    caveats: "Current official ENR promotion uses county-level detail rows.",
  },
  SD: {
    collection_status: "state_or_county_source_needed",
    source_title: "South Dakota precinct/reporting-unit results",
    row_level: "unknown",
    has_president_rows: false,
    comparison_contest_status: "needs source discovery",
    parser_fit: "TBD",
    next_step: "Search South Dakota SOS and county auditor files for precinct-level 2024 general returns.",
    caveats: "Canvass PDF presidential table is county-level.",
  },
  TN: {
    collection_status: "local_row_source_collected",
    row_level: "precinct",
    has_president_rows: true,
    comparison_contest_status: "comparison contest likely in workbook; needs mapping",
    parser_fit: "Tennessee precinct workbook comparison parser",
    next_step: "Map President and a down-ballot contest from the all-by-precinct workbook.",
    caveats: "Workbook is already used for certified presidential aggregation.",
  },
  TX: {
    collection_status: "county_local_required",
    source_title: "Texas county official precinct returns",
    row_level: "county-local precinct",
    has_president_rows: false,
    comparison_contest_status: "needs county source collection",
    parser_fit: "county report/parser family",
    next_step: "Collect county official precinct returns; statewide SOS data currently loaded is county-level.",
    caveats: "Texas statewide SOS results/data source does not expose an app-ready statewide precinct export in current sources.",
  },
  UT: {
    collection_status: "county_local_or_clarity_required",
    source_title: "Utah county Clarity/official precinct results",
    row_level: "county-local precinct",
    has_president_rows: false,
    comparison_contest_status: "needs county source collection",
    parser_fit: "county Clarity/report parser family",
    next_step: "Collect county Clarity exports or county official precinct reports for President and comparison contests.",
    caveats: "Statewide canvass PDF is county-level.",
  },
  VA: {
    collection_status: "local_row_source_collected",
    row_level: "precinct/locality",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping/source",
    parser_fit: "Virginia historical CSV precinct comparison parser",
    next_step: "Map precinct rows and collect/map a same-grain comparison contest export.",
    caveats: "Current parser uses official contest CSV but review graph is disabled pending comparison mapping.",
  },
  VT: {
    collection_status: "local_row_source_collected",
    row_level: "municipality",
    has_president_rows: true,
    comparison_contest_status: "comparison contest needs mapping/source",
    parser_fit: "Vermont municipality CSV comparison parser",
    next_step: "Collect/map a same-municipality statewide down-ballot contest.",
    caveats: "Municipality rows are retained from the official electionarchive export.",
  },
  WA: {
    collection_status: "county_local_required",
    source_title: "Washington county official precinct results",
    row_level: "county-local precinct",
    has_president_rows: false,
    comparison_contest_status: "needs county source collection",
    parser_fit: "county report/parser family",
    next_step: "Collect county official precinct result files; SOS page currently loaded is county-level.",
    caveats: "Statewide SOS county page does not expose precinct rows.",
  },
  WV: {
    collection_status: "official_portal_identified_needs_capture",
    row_level: "unknown ENR detail",
    has_president_rows: false,
    comparison_contest_status: "needs endpoint inspection",
    parser_fit: "West Virginia Clarity detail parser",
    next_step: "Inspect Clarity ENR static files for precinct/detail records or collect county files.",
    caveats: "Current loaded details JSON is county-level for this parser.",
  },
  WY: {
    collection_status: "local_row_source_collected",
    row_level: "precinct-by-precinct workbooks",
    has_president_rows: true,
    comparison_contest_status: "comparison contest likely present; needs workbook layout mapping",
    parser_fit: "Wyoming official ZIP precinct workbook parser",
    next_step: "Map county precinct-by-precinct workbooks inside the official ZIP to President plus comparison contest rows.",
    caveats: "Official ZIP is already local.",
  },
};

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function titleCaseStatus(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function configPaths() {
  return fs
    .readdirSync(configDir)
    .filter((name) => name.endsWith(".json") && !name.startsWith("_") && name !== "template.json")
    .map((name) => path.join(configDir, name))
    .sort();
}

const rows = [];
for (const configPath of configPaths()) {
  const config = readJson(configPath);
  const capabilities = config.app?.capabilities || {};
  if (capabilities.reviewGraphs) continue;
  const wardDetail = config.app?.sourcePlan?.wardDetail || {};
  const override = overrides[config.code] || {};
  rows.push({
    state: config.code,
    review_graph_status: "missing",
    collection_status: override.collection_status || "needs_review",
    authority: config.authority || "",
    source_title: override.source_title || wardDetail.title || "",
    source_url: override.source_url || wardDetail.sourceUrl || "",
    local_file: override.local_file || wardDetail.localFile || "",
    row_level: override.row_level || "unknown",
    has_president_rows: override.has_president_rows ? "true" : "false",
    comparison_contest_status: override.comparison_contest_status || "needs review",
    parser_fit: override.parser_fit || "TBD",
    next_step: override.next_step || "Review source and map President plus comparison contest rows.",
    caveats: override.caveats || wardDetail.detail || "",
    checked_at: checkedAt,
  });
}

rows.sort((left, right) => left.state.localeCompare(right.state));

fs.writeFileSync(
  path.join(root, "data", "review-source-audit.csv"),
  `${headers.join(",")}\n${rows.map((row) => headers.map((header) => csvCell(row[header])).join(",")).join("\n")}\n`,
  "utf8",
);

fs.writeFileSync(
  path.join(root, "data", "review-source-audit.json"),
  `${JSON.stringify({ checkedAt, rows }, null, 2)}\n`,
  "utf8",
);

const grouped = new Map();
for (const row of rows) {
  const key = titleCaseStatus(row.collection_status);
  if (!grouped.has(key)) grouped.set(key, []);
  grouped.get(key).push(row);
}

const lines = [
  "# Review Graph Source Audit",
  "",
  `Checked at: ${checkedAt}`,
  "",
  "This audit tracks the separate source-collection task for states that do not yet have review graphs enabled. It records whether an official precinct, reporting-unit, town, municipality, election-district, or county-local source has already been collected or still needs discovery/capture. It does not enable review graphs by itself.",
  "",
  "## Summary",
  "",
  `- Review-missing states audited: ${rows.length}`,
  ...[...grouped.entries()].map(([status, items]) => `- ${status}: ${items.length}`),
  "",
  "## State Rows",
  "",
  "| State | Collection status | Row level | Source | Parser fit | Next step |",
  "| --- | --- | --- | --- | --- | --- |",
  ...rows.map((row) => {
    const source = row.source_url ? `[${row.source_title || row.source_url}](${row.source_url})` : row.source_title;
    return `| ${row.state} | ${row.collection_status} | ${row.row_level} | ${source} | ${row.parser_fit} | ${row.next_step} |`;
  }),
  "",
];

fs.writeFileSync(path.join(root, "docs", "review-source-audit.md"), `${lines.join("\n")}\n`, "utf8");

console.log(JSON.stringify({ status: "written", rows: rows.length, groups: Object.fromEntries([...grouped.entries()].map(([key, value]) => [key, value.length])) }, null, 2));
