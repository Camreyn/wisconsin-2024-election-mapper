import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(root, "data");
const captureDir = path.join(dataDir, "review-sources");
const auditPath = path.join(dataDir, "review-source-audit.json");
const checkedAt = "2026-06-08";

const gaFederalDetailTargets = [
  ["President of the US", "01000000-d884-2e72-6367-08dcda4b86b5", "president-of-the-us"],
  ["US House of Representatives - District 1", "01000000-d884-2e72-d102-08dcda4b86d5", "us-house-of-representatives-district-1"],
  ["US House of Representatives - District 2", "01000000-d884-2e72-591a-08dcda4b8737", "us-house-of-representatives-district-2"],
  ["US House of Representatives - District 3", "01000000-d884-2e72-563f-08dcda4b8b12", "us-house-of-representatives-district-3"],
  ["US House of Representatives - District 4", "01000000-d884-2e72-e484-08dcda4b9be1", "us-house-of-representatives-district-4"],
  ["US House of Representatives - District 5", "01000000-d884-2e72-8e53-08dcda4b8ff0", "us-house-of-representatives-district-5"],
  ["US House of Representatives - District 6", "01000000-d884-2e72-15bb-08dcda4b92f0", "us-house-of-representatives-district-6"],
  ["US House of Representatives - District 7", "01000000-d884-2e72-302d-08dcda4b8ddb", "us-house-of-representatives-district-7"],
  ["US House of Representatives - District 8", "01000000-d884-2e72-5082-08dcda4b86fd", "us-house-of-representatives-district-8"],
  ["US House of Representatives - District 9", "01000000-d884-2e72-803e-08dcda4b87d0", "us-house-of-representatives-district-9"],
  ["US House of Representatives - District 10", "01000000-d884-2e72-fd50-08dcda4b8827", "us-house-of-representatives-district-10"],
  ["US House of Representatives - District 11", "01000000-d884-2e72-605f-08dcda4b8884", "us-house-of-representatives-district-11"],
  ["US House of Representatives - District 12", "01000000-d884-2e72-8858-08dcda4b89eb", "us-house-of-representatives-district-12"],
  ["US House of Representatives - District 13", "01000000-d884-2e72-dbd0-08dcda4b8fe0", "us-house-of-representatives-district-13"],
  ["US House of Representatives - District 14", "01000000-d884-2e72-24df-08dcda4b8b5f", "us-house-of-representatives-district-14"],
].map(([name, id, slug]) => ({
  label: `Georgia 2024 ${name} county breakdown JSON`,
  url: `https://results.sos.ga.gov/results/public/api/elections/Georgia/2024NovGen/ballot-items/${id}`,
  localFile: `data/ga-2024-general-${slug}-detail.json`,
  minBytes: 5000,
  notes: "Official Georgia SOS public API ballot-item detail payload with county breakdown rows and vote-method splits.",
}));

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
      label: "Arkansas SOS election results page",
      url: "https://www.sos.arkansas.gov/elections/research/election-results",
      localFile: "data/review-sources/ar-sos-election-results-page.html",
      minBytes: 100000,
      dataKind: "source-page",
      notes: "Official Arkansas SOS results archive page. It links the 2024 General to TotalResults and states some downloads are temporarily unavailable during the election-night reporting vendor transition.",
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
    {
      label: "Arkansas 2024 General federal contest results",
      url: "https://enr-results-api.totalresults.com/Contest/GetContestResults?cId=arkansas&electionID=1846&contestType=FED",
      localFile: "data/review-sources/ar-federal-contest-results.json",
      minBytes: 50000,
      dataKind: "source-page",
      notes: "Official TotalResults federal contest payload. It exposes county-level locations and hasLocationResults=false for the federal contests checked.",
    },
    {
      label: "Arkansas 2024 President single-contest probe",
      url: "https://enr-results-api.totalresults.com/Contest/GetSingleContestResults?cId=arkansas&electionID=1846&contestType=FED&contestID=366",
      localFile: "data/review-sources/ar-president-single-contest-results.json",
      minBytes: 500,
      dataKind: "source-page",
      notes: "Official TotalResults single-contest probe for U.S. President. The response is valid JSON but has null choices/locations and zero precinct totals.",
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
  GA: [
    {
      label: "Georgia public results jurisdiction metadata",
      url: "https://results.sos.ga.gov/results/public/api/jurisdictions/Georgia",
      localFile: "data/review-sources/ga-jurisdiction-georgia.json",
      minBytes: 50000,
      dataKind: "source-page",
      notes: "Official Georgia SOS public API jurisdiction metadata, including county localities and election ids.",
    },
    {
      label: "Georgia 2024 General election metadata",
      url: "https://results.sos.ga.gov/results/public/api/elections/Georgia/2024NovGen",
      localFile: "data/review-sources/ga-2024novgen-election.json",
      minBytes: 1000,
      dataKind: "source-page",
      notes: "Official Georgia SOS public API election metadata identifying the 2024 November General election and public report exports.",
    },
    {
      label: "Georgia 2024 General ballot-item summary JSON",
      url: "https://results.sos.ga.gov/results/public/api/elections/Georgia/2024NovGen/ballot-items",
      localFile: "data/ga-2024-general-ballot-items.json",
      minBytes: 100000,
      notes: "Official Georgia SOS public API ballot-item payload covering statewide and district contests.",
    },
    ...gaFederalDetailTargets,
  ],
  IN: [
    {
      label: "Indiana 2024 General settings JSON",
      url: "https://enr.indianavoters.in.gov/archive/2024General/data/settings.json",
      localFile: "data/review-sources/in-settings.json",
      minBytes: 1000,
      dataKind: "source-page",
      notes: "Official Indiana ENR settings file identifying certified version A for the 2024 general election static JSON results.",
    },
    {
      label: "Indiana 2024 General statewide office index",
      url: "https://enr.indianavoters.in.gov/archive/2024General/data/statewideElectionsC_A.json",
      localFile: "data/review-sources/in-statewideElectionsC_A.json",
      minBytes: 10000,
      dataKind: "source-page",
      notes: "Official Indiana ENR statewide office/category index used to identify federal contest JSON files.",
    },
    {
      label: "Indiana 2024 President reporting-unit results JSON",
      url: "https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_1019_A.json",
      localFile: "data/in-2024-general-president-results.json",
      minBytes: 100000,
      notes: "Official Indiana ENR static JSON for President. Provides county/locality reporting-unit rows; no statewide precinct JSON was exposed in the archive app.",
    },
    {
      label: "Indiana 2024 U.S. Senate reporting-unit results JSON",
      url: "https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_1006_A.json",
      localFile: "data/in-2024-general-us-senate-office-category.json",
      minBytes: 100000,
      notes: "Official Indiana ENR static JSON for U.S. Senate, matching the President reporting-unit grain.",
    },
    {
      label: "Indiana 2024 U.S. House reporting-unit results JSON",
      url: "https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_1005_A.json",
      localFile: "data/in-2024-general-us-house-office-category.json",
      minBytes: 100000,
      notes: "Official Indiana ENR static JSON for U.S. House, matching the portal reporting-unit grain.",
    },
  ],
  LA: [
    {
      label: "Louisiana 2024 General static results page",
      url: "https://voterportal.sos.la.gov/static/2024-11-05",
      localFile: "data/review-sources/la-official-review-source.html",
      minBytes: 2000,
      rejectIfContains: ["Content not found"],
      dataKind: "source-page",
      notes: "Official Louisiana SOS static election results shell for the November 5, 2024 general election.",
    },
    {
      label: "Louisiana static results app bundle",
      url: "https://voterportal.sos.la.gov/bundles/staticresults?v=AmoBrbwPS5am6MfFwT0bgJ1AzLTkr6AiLoJGAdehvI41",
      localFile: "data/review-sources/la-staticresults-bundle.js",
      minBytes: 40000,
      dataKind: "source-page",
      notes: "Official Louisiana SOS bundle containing static API route templates for race, parish, and precinct payloads.",
    },
    {
      label: "Louisiana 2024 federal precinct results aggregate",
      url: "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=20241105/VotesRaceByPrecinct/Votes_67190_01.htm",
      localFile: "data/la-2024-general-federal-precinct-results.json",
      minBytes: 1000000,
      notes: "Official Louisiana SOS static API precinct JSON aggregated for President and all U.S. House races across their reporting parishes.",
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
  OK: [
    {
      label: "Oklahoma 2024 General official results page",
      url: "https://results.okelections.gov/OKER/?elecDate=20241105",
      localFile: "data/review-sources/ok-official-review-source.html",
      minBytes: 1000,
      dataKind: "source-page",
      notes: "Official OK Election Results app shell for the November 5, 2024 general election.",
    },
    {
      label: "Oklahoma OKER app config",
      url: "https://results.okelections.gov/OKER/assets/config.json",
      localFile: "data/review-sources/ok-config.json",
      minBytes: 100,
      dataKind: "source-page",
      notes: "Official OKER app config identifying the OKERS API base URL used by the live results app.",
    },
    {
      label: "Oklahoma OKER app bundle",
      url: "https://results.okelections.gov/OKER/main.c79774cb1fe93a6677b7.bundle.js",
      localFile: "data/review-sources/ok-main-bundle.js",
      minBytes: 1000000,
      dataKind: "source-page",
      notes: "Official OKER bundle showing the live export, county result, precinct result, and map API route templates.",
    },
    {
      label: "Oklahoma OKER rendered browser snapshot",
      url: "https://results.okelections.gov/OKER/?elecDate=20241105",
      localFile: "data/review-sources/ok-browser-snapshot.html",
      minBytes: 500000,
      dataKind: "source-page",
      notes: "Headless browser snapshot of the official OKER app. It confirms rendered precinct-level CSV/XML export controls and state race ids, including President race 10001.",
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
  OR: [
    {
      label: "Oregon 2024 Federal precinct-level results workbook",
      url: "https://results.oregonvotes.gov/resultsSW.aspx?type=FED&map=CTY&eid=107",
      localFile: "data/or-2024-general-federal-results-precinct.xlsx",
      minBytes: 50000,
      notes: "Official Oregon SOS Federal Precinct Level export workbook obtained from the resultsSW.aspx postback export button.",
    },
  ],
  WA: [
    {
      label: "Washington 2024 General export index",
      url: "https://results.vote.wa.gov/results/20241105/Export.html",
      localFile: "data/review-sources/wa-export-results.html",
      minBytes: 10000,
      dataKind: "source-page",
      notes: "Official Washington SOS export page listing statewide, federal, county, and participating-county precinct CSV files.",
    },
    {
      label: "Washington 2024 General all state precinct CSV",
      url: "https://results.vote.wa.gov/results/20241105/export/20241105_AllStatePrecincts.csv",
      localFile: "data/wa-2024-general-all-state-precincts.csv",
      minBytes: 1000000,
      notes: "Official Washington SOS CSV of participating-county precinct rows with race, county code, candidate, precinct name/code, and votes.",
    },
    {
      label: "Washington 2024 General federal offices CSV",
      url: "https://results.vote.wa.gov/results/20241105/export/20241105_Congressional.csv",
      localFile: "data/wa-2024-general-congressional.csv",
      minBytes: 1000,
      notes: "Official Washington SOS federal offices CSV for President and congressional comparison totals.",
    },
    {
      label: "Washington 2024 General all state contests CSV",
      url: "https://results.vote.wa.gov/results/20241105/export/20241105_AllState.csv",
      localFile: "data/wa-2024-general-all-state.csv",
      minBytes: 10000,
      notes: "Official Washington SOS statewide contests CSV for statewide comparison races.",
    },
  ],
  SC: [
    {
      label: "South Carolina 2024 General Clarity results page",
      url: "https://www.enr-scvotes.org/SC/122436/web.345435/",
      localFile: "data/review-sources/sc-official-review-source.html",
      minBytes: 10000,
      dataKind: "source-page",
      notes: "Official South Carolina Election Commission Clarity page for the 2024 statewide general election.",
    },
    {
      label: "South Carolina 2024 General Clarity detail XML",
      url: "https://www.enr-scvotes.org/SC/122436/359624/reports/detailxml.zip",
      localFile: "data/review-sources/sc-2024-general-detailxml.zip",
      minBytes: 50000,
      dataKind: "source-page",
      notes: "Official Clarity detail XML. It includes contest/county rows and precinct reporting counts, but no named precinct candidate rows were exposed in this ZIP.",
    },
    {
      label: "South Carolina 2024 President election-history page",
      url: "https://electionhistory.scvotes.gov/contest/7131",
      localFile: "data/review-sources/sc-electionhistory-president-page.html",
      minBytes: 50000,
      dataKind: "source-page",
      notes: "Official South Carolina Election Commission election-history contest page that exposes the downloadable Results CSV for the 2024 presidential contest.",
    },
    {
      label: "South Carolina 2024 President precinct CSV",
      url: "https://sc.elstats.civera.com/api/download_contest/7131_table.csv?split_party=false",
      localFile: "data/review-sources/sc-2024-president-electionhistory-table.csv",
      minBytes: 100000,
      dataKind: "data",
      notes: "Official election-history CSV with State, County, and Precinct rows for the 2024 presidential contest.",
    },
  ],
  WV: [
    {
      label: "West Virginia 2024 General Clarity results page",
      url: "https://results.enr.clarityelections.com/WV/122766/web.345435/",
      localFile: "data/review-sources/wv-official-review-source.html",
      minBytes: 1000,
      dataKind: "source-page",
      notes: "Official West Virginia Secretary of State Clarity page for the 2024 general election.",
    },
    {
      label: "West Virginia 2024 General Clarity detail XML",
      url: "https://results.enr.clarityelections.com/WV/122766/356048/reports/detailxml.zip",
      localFile: "data/review-sources/wv-2024-general-detailxml.zip",
      minBytes: 20000,
      dataKind: "source-page",
      notes: "Official Clarity detail XML. It includes contest/county rows and precinct reporting counts, but no named precinct candidate rows were exposed in this ZIP.",
    },
    {
      label: "West Virginia SOS historical results page",
      url: "https://sos.wv.gov/elections/election-data/historical-election-results-and-turnout",
      localFile: "data/review-sources/wv-sos-historical-results-page.html",
      minBytes: 50000,
      dataKind: "source-page",
      notes: "Official West Virginia SOS historical results page linking the 2024 General Election to the Clarity results portal.",
    },
    {
      label: "West Virginia Monongalia County 2024 results page",
      url: "https://www.monongaliacountyclerk.org/index.php/18-previous-elections",
      localFile: "data/review-sources/wv-monongalia-previous-elections-page.html",
      minBytes: 50000,
      dataKind: "source-page",
      notes: "Official Monongalia County Clerk page listing 2024 General precinct summary downloads in HTML, PDF, RTF, XLSX, and CSV formats.",
    },
    {
      label: "West Virginia Monongalia County 2024 precinct summary CSV",
      url: "https://www.monongaliacountyclerk.org/myfiles/elections/2024General/Precinct_Summary/24GeneralPrecinctSummary.csv",
      localFile: "data/review-sources/wv-monongalia-2024-general-precinct-summary.csv",
      minBytes: 500000,
      dataKind: "data",
      notes: "Official county-published Electionware precinct summary CSV with precinct sections, presidential rows, candidate totals, and vote-mode columns.",
    },
    {
      label: "West Virginia Wood County 2024 precinct results PDF",
      url: "https://woodcountywv.com/download/1283/general-2024/13138/declared-results-gen-2024-prct.pdf",
      localFile: "data/review-sources/wv-wood-2024-general-precinct-results.pdf",
      minBytes: 1000000,
      dataKind: "data",
      notes: "Official county-published declared precinct results PDF for the 2024 General Election.",
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
    minBytes: ["AR", "OK", "WV"].includes(state) ? 500 : 2000,
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
