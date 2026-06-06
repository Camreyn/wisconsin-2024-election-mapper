import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PA_ELECTION_DATA_PAGE =
  "https://www.pa.gov/agencies/dos/resources/voting-and-elections-resources/voting-and-election-statistics/election-data";
const PA_GEOMETRY_URL =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2742%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY&returnGeometry=true&outSR=4326&f=geojson";

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
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function normalizePaUrl(url) {
  if (!url) return "";
  if (url.startsWith("https://")) return url;
  if (url.startsWith("/")) return `https://www.pa.gov${url}`;
  return url;
}

function resourceText(resource) {
  return String(resource.text || resource.note || "").replace(/\s+/g, " ").trim();
}

function findPaResourceUrl(report, pattern, fallback = "") {
  const resources = [...(report.resources || []), ...(report.likelyDownloads || [])];
  const byText = resources.find((resource) => pattern.test(resourceText(resource)));
  if (byText?.url) return normalizePaUrl(byText.url);
  const byUrl = resources.find((resource) => pattern.test(String(resource.url || resource.rawUrl || "")));
  return normalizePaUrl(byUrl?.url || fallback);
}

function upsertSource(config, source) {
  config.sources ||= [];
  const existing = config.sources.find((item) => item.id === source.id);
  if (existing) {
    Object.assign(existing, source);
    return { source: existing, added: false };
  }
  config.sources.push(source);
  return { source, added: true };
}

function upsertInventory(config, entry) {
  config.app ||= {};
  config.app.sourceInventory ||= [];
  const existing = config.app.sourceInventory.find((item) => item.category === entry.category && item.file === entry.file);
  if (existing) {
    Object.assign(existing, entry);
    return false;
  }
  config.app.sourceInventory.push(entry);
  return true;
}

function addChecked(config, entry) {
  config.app ||= {};
  config.app.checkedNotUsable ||= [];
  const exists = config.app.checkedNotUsable.some((item) => item.category === entry.category && item.sourceUrl === entry.sourceUrl);
  if (exists) return false;
  config.app.checkedNotUsable.push(entry);
  return true;
}

function paSourceDefinitions(report) {
  return [
    {
      id: "pa-2024-precinct-results",
      url: findPaResourceUrl(
        report,
        /Download the 2024 General Voter Election Returns Precinct Data|erstat_2024_g_268768_20250129/i,
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/2024-general-election/er/erstat_2024_g_268768_20250129.txt",
      ),
      localFile: "data/pa-2024-general-election-returns-precinct.txt",
    },
    {
      id: "pa-2024-precinct-results-readme",
      url: findPaResourceUrl(
        report,
        /Download the 2024 General Election Returns Data|erstat_2024_g_readme/i,
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/2024-general-election/er/erstat_2024_g_readme.txt",
      ),
      localFile: "data/pa-2024-general-election-returns-readme.txt",
    },
    {
      id: "pa-2024-vote-history-registration-summary",
      url: findPaResourceUrl(
        report,
        /Download the 2024 General Election Voter Registration Vote History|voter%20registration%20-%20vote%20history%20summary%20-%202024%20general/i,
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/2024-general-election/voter%20registration%20-%20vote%20history%20summary%20-%202024%20general.xlsx",
      ),
      localFile: "data/pa-2024-voter-registration-vote-history-summary.xlsx",
    },
    {
      id: "pa-2020-precinct-results",
      url: findPaResourceUrl(
        report,
        /Download the 2020 General Election Returns Precinct Data|ElectionReturns_2020_General_PrecinctReturns/i,
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/ElectionReturns_2020_General_PrecinctReturns.txt",
      ),
      localFile: "data/pa-2020-general-election-returns-precinct.txt",
    },
    {
      id: "pa-2016-precinct-results",
      url: findPaResourceUrl(
        report,
        /Download the 2016 General Election Returns Precinct Data|ElectionReturns_2016_General_PrecinctReturns/i,
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/ElectionReturns_2016_General_PrecinctReturns.txt",
      ),
      localFile: "data/pa-2016-general-election-returns-precinct.txt",
    },
    {
      id: "pa-2012-precinct-results",
      url: findPaResourceUrl(
        report,
        /Download the 2012 General Election Returns Precinct Data|ElectionReturns_2012_General_PrecinctReturns/i,
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/ElectionReturns_2012_General_PrecinctReturns.txt",
      ),
      localFile: "data/pa-2012-general-election-returns-precinct.txt",
    },
    {
      id: "pa-county-geometry",
      url: PA_GEOMETRY_URL,
      localFile: "data/pa-counties.geojson",
    },
  ];
}

function applyPennsylvaniaProfile(config, report = {}) {
  const addedSources = [];
  const updatedSources = [];
  for (const source of paSourceDefinitions(report)) {
    const result = upsertSource(config, source);
    (result.added ? addedSources : updatedSources).push(source.id);
  }

  config.geometry = {
    sourceId: "pa-county-geometry",
    outputFile: "data/pa-counties.js",
    outputGlobal: "PA_COUNTIES_GEOJSON",
    nameProperty: "NAME",
    codeProperty: "COUNTY",
    expectedFeatures: 67,
  };
  config.certifiedResults = {
    format: "pennsylvaniaBulkCsv",
    sourceId: "pa-2024-precinct-results",
    officeCode: "USP",
    majorCandidates: {
      trump: { partyCode: "REP", candidateContains: "TRUMP" },
      harris: { partyCode: "DEM", candidateContains: "HARRIS" },
    },
    otherCandidates: [
      { key: "stein", label: "Jill Stein", partyCode: "GRN", candidateContains: "STEIN" },
      { key: "oliver", label: "Chase Oliver", partyCode: "LIB", candidateContains: "OLIVER" },
    ],
  };
  config.reviewCharts = {
    format: "pennsylvaniaBulkCsvPrecinctComparison",
    sourceId: "pa-2024-precinct-results",
    presidentOfficeCode: "USP",
    downBallotOfficeCode: "USS",
    partyCodes: { dem: "DEM", rep: "REP" },
    policy: {
      outlierThresholdPct: 15,
      minCandidateVotes: 100,
      voteShareCorrelationThreshold: 0.35,
    },
  };
  config.turnout = {
    format: "pennsylvaniaVoteHistoryXlsx",
    sourceId: "pa-2024-vote-history-registration-summary",
    sheet: "By county",
    columns: {
      county: "County",
      ballotsCast: "Vote History",
      registeredVoters: "Registered voters",
    },
    registrationDenominatorTiming: "certifiedVoterRegistrationSummary",
    sourceLevel: "county",
    notes: "Pennsylvania DOS 2024 General Election Vote History & Voter Registration Summary workbook. Ballots cast use county vote-history rows; denominators use the workbook's registered-voter column.",
    warningRequired: false,
  };
  config.historicalBaseline = {
    format: "pennsylvaniaBulkCsv",
    sourceLevel: "county",
    rowMethod: "dosPrecinctReturnsAggregatedToCounty",
    officeCode: "USP",
    partyCodes: { dem: "DEM", rep: "REP" },
    contestName: "President Of The United States",
    sources: [
      {
        year: 2012,
        sourceId: "pa-2012-precinct-results",
        note: "Official Pennsylvania Department of State 2012 general election precinct returns aggregated to county presidential rows.",
      },
      {
        year: 2016,
        sourceId: "pa-2016-precinct-results",
        note: "Official Pennsylvania Department of State 2016 general election precinct returns aggregated to county presidential rows.",
      },
      {
        year: 2020,
        sourceId: "pa-2020-precinct-results",
        note: "Official Pennsylvania Department of State 2020 general election precinct returns aggregated to county presidential rows.",
      },
      {
        year: 2024,
        sourceId: "pa-2024-precinct-results",
        note: "Official Pennsylvania Department of State 2024 general election precinct returns aggregated to county presidential rows.",
      },
    ],
  };

  config.app ||= {};
  config.app.countyLabel = "County";
  config.app.exportsSlug = "pennsylvania-2024";
  config.app.capabilities = {
    sourcePlanner: true,
    certifiedResults: true,
    map: true,
    reviewGraphs: true,
    turnout: true,
    historicalBaseline: true,
  };
  config.app.sourcePlan = {
    ...(config.app.sourcePlan || {}),
    certifiedResults: {
      title: "Pennsylvania DOS precinct election returns bulk file",
      detail: "Presidential county totals are aggregated from the official Pennsylvania Department of State 2024 General Election Precinct Election Returns comma-delimited bulk file.",
      sourceUrl: PA_ELECTION_DATA_PAGE,
      localFile: "data/pa-2024-general-election-returns-precinct.txt; data/pa-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official readme says the data was extracted January 10, 2025; the direct bulk file name includes 20250129.",
      status: "Loaded",
    },
    wardDetail: {
      title: "Pennsylvania DOS precinct election returns bulk file",
      detail: "The official bulk file includes precinct-level President and U.S. Senate rows. The state builder groups rows by county, precinct code, municipality, ward, and precinct breakdown fields for President-vs-Senate review graphs.",
      sourceUrl: PA_ELECTION_DATA_PAGE,
      localFile: "data/pa-2024-general-election-returns-precinct.txt; data/pa-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official readme says the data was extracted January 10, 2025; the direct bulk file name includes 20250129.",
      status: "Loaded",
    },
    turnout: {
      title: "Pennsylvania DOS vote history and voter registration summary",
      detail: "County turnout rows use the official 2024 General Election Vote History & Voter Registration Summary workbook: Vote History divided by Registered voters on the By county sheet.",
      sourceUrl: PA_ELECTION_DATA_PAGE,
      localFile: "data/pa-2024-voter-registration-vote-history-summary.xlsx; data/pa-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official PA election data page and 2024 General Data Handbook identify the workbook as a post-election SURE summary.",
      status: "Loaded",
    },
  };
  config.app.turnoutPolicy = {
    route: "voteHistoryRegistrationSummaryWorkbook",
    status: "Loaded",
    acceptedSource: "Pennsylvania DOS 2024 General Election Vote History & Voter Registration Summary workbook.",
    warning: "Pennsylvania turnout uses vote-history rows and registered-voter denominators from the DOS summary workbook, not candidate vote totals from the election returns file.",
    requiredFields: ["county", "ballotsCast", "registeredVoters", "sourceUrl"],
  };
  config.app.historicalSummary =
    "Native official Pennsylvania Department of State precinct returns are aggregated to county presidential rows for each election year.";
  config.app.reviewRowLabel = "Pennsylvania DOS precinct row";
  config.app.reviewRowLabelPlural = "Pennsylvania DOS precinct rows";
  config.app.reviewGraphTitlePrefix = "Pennsylvania DOS precinct";
  config.app.mapLoadingText = "Loading local Pennsylvania county boundaries...";
  config.app.noGeometryText = "Pennsylvania county geometry is not loaded yet; showing the county tile fallback.";
  config.app.sourceInventory = [];
  config.app.checkedNotUsable = (config.app.checkedNotUsable || []).filter(
    (entry) => entry.category !== "Turnout denominator",
  );
  upsertInventory(config, {
    category: "Presidential county results",
    file: "data/pa-2024-general-election-returns-precinct.txt; data/pa-app-data.js",
    sourceUrl: PA_ELECTION_DATA_PAGE,
    usedFor: "Pennsylvania county table, statewide totals, candidate breakdown, CSV export, Source Planner rows, and precinct-level review graphs.",
    confidence: "Official Pennsylvania Department of State 2024 General Election Precinct Election Returns bulk file.",
  });
  upsertInventory(config, {
    category: "Turnout denominator source",
    file: "data/pa-2024-voter-registration-vote-history-summary.xlsx; data/pa-app-data.js",
    sourceUrl: PA_ELECTION_DATA_PAGE,
    usedFor: "Pennsylvania turnout graph and Source Planner turnout coverage.",
    confidence: "Official Pennsylvania Department of State Vote History & Voter Registration Summary workbook.",
  });
  upsertInventory(config, {
    category: "Historical presidential baseline",
    file: "data/pa-2012-general-election-returns-precinct.txt; data/pa-2016-general-election-returns-precinct.txt; data/pa-2020-general-election-returns-precinct.txt; data/pa-2024-general-election-returns-precinct.txt; data/pa-app-data.js",
    sourceUrl: PA_ELECTION_DATA_PAGE,
    usedFor: "Pennsylvania Historical Baseline tab: native DOS precinct returns aggregated to county presidential comparison rows for 2012, 2016, 2020, and 2024.",
    confidence: "Official Pennsylvania Department of State general election returns precinct files.",
  });
  upsertInventory(config, {
    category: "County boundaries",
    file: "data/pa-counties.geojson; data/pa-counties.js",
    sourceUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer",
    usedFor: "Pennsylvania county polygon map.",
    confidence: "U.S. Census TIGERweb county geography.",
  });
  addChecked(config, {
    category: "Protected election-results application",
    sourceUrl: "https://www.electionreturns.pa.gov/General/SummaryResults?ElectionID=18&ElectionType=G&IsActive=0",
    reason: "The fetched page is an Incapsula access-protection response, not the election-results application HTML.",
    status: "Blocked by incapsula",
    nextStep: "Use the official PA.gov bulk election data files or an interactive browser capture for the protected electionreturns.pa.gov application.",
  });
  config.expected = {
    countyRows: 67,
    precinctRows: 9187,
    stateTotal: 7031737,
    trump: 3543041,
    harris: 3420865,
    other: 67831,
    reviewRows: 9154,
    turnoutRows: 67,
    turnoutWarningRows: 0,
    historicalSeries: 4,
    historicalRows: 268,
    geometryFeatures: 67,
  };

  return {
    profile: "pennsylvaniaPaGovElectionData",
    status: "applied",
    addedSources,
    updatedSources,
    loadedCapabilities: Object.entries(config.app.capabilities)
      .filter(([, enabled]) => enabled)
      .map(([name]) => name),
  };
}

export function applyStateSourceProfile(config, report = {}) {
  const code = String(config.code || report.state || "").toUpperCase();
  const inputUrl = String(report.input?.url || "");
  const pageTitle = String(report.page?.title || "");
  const isPaElectionData =
    code === "PA" &&
    (inputUrl.includes("/voting-and-election-statistics/election-data") ||
      pageTitle.includes("Historical Elections Data"));
  if (!isPaElectionData) {
    return {
      profile: "",
      status: "not_applicable",
      addedSources: [],
      updatedSources: [],
      loadedCapabilities: [],
    };
  }
  return applyPennsylvaniaProfile(config, report);
}

export function applyStateSourceProfileToConfigFile({ configPath, reportPath, write = false }) {
  const config = readJson(configPath);
  const report = readJson(reportPath);
  const summary = applyStateSourceProfile(config, report);
  if (write && summary.status === "applied") {
    writeJson(configPath, config);
  }
  return { config, report, summary };
}

function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const configPath = args.get("config");
  const reportPath = args.get("report");
  const write = args.has("write");
  if (!configPath || !reportPath) {
    console.error("Usage: node scripts/apply-state-source-profile.mjs --config data/state-configs/xx.json --report outputs/xx-discovery.json [--write]");
    process.exit(2);
  }
  const { summary } = applyStateSourceProfileToConfigFile({ configPath, reportPath, write });
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
