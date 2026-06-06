import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PA_ELECTION_DATA_PAGE =
  "https://www.pa.gov/agencies/dos/resources/voting-and-elections-resources/voting-and-election-statistics/election-data";
const PA_GEOMETRY_URL =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2742%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY&returnGeometry=true&outSR=4326&f=geojson";
const AL_ELECTION_DATA_PAGE = "https://www.sos.alabama.gov/alabama-votes/voter/election-data";
const AL_GEOMETRY_URL =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2701%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY&returnGeometry=true&outSR=4326&f=geojson";
const FL_PRECINCT_RESULTS_PAGE =
  "https://dos.fl.gov/elections/data-statistics/elections-data/precinct-level-election-results/";
const FL_VOTER_TURNOUT_PAGE = "https://dos.fl.gov/elections/data-statistics/elections-data/voter-turnout/";
const FL_GEOMETRY_URL =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2712%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY&returnGeometry=true&outSR=4326&f=geojson";
const AZ_RESULTS_APP_URL = "https://results.arizona.vote/#/featured/47/0";
const AZ_SOS_ELECTION_INFO_URL = "https://azsos.gov/events/local-elections/408";
const AZ_GEOMETRY_URL =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2704%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY&returnGeometry=true&outSR=4326&f=geojson";
const AZ_SOURCE_MANIFEST_FILE = "data/az-2024-county-source-manifest.json";

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

function alabamaSourceDefinitions() {
  return [
    {
      id: "al-2024-precinct-results",
      url: "https://www.sos.alabama.gov/sites/default/files/election-data/2024-12/2024-General%20Precinct%20Level%20Results.zip",
      localFile: "data/al-2024-general-precinct-level-results.zip",
    },
    {
      id: "al-2024-voter-registration",
      url: "https://www.sos.alabama.gov/sites/default/files/election-data/2025-01/ALVR-2024.xlsx",
      localFile: "data/al-2024-voter-registration.xlsx",
    },
    {
      id: "al-2020-precinct-results",
      url: "https://www.sos.alabama.gov/sites/default/files/election-data/2020-12/2020%20General%20Precinct%20Results.zip",
      localFile: "data/al-2020-general-precinct-level-results.zip",
    },
    {
      id: "al-2016-precinct-results",
      url: "https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/2016-General-PrecinctLevel.zip",
      localFile: "data/al-2016-general-precinct-level-results.zip",
    },
    {
      id: "al-2012-precinct-results",
      url: "https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/2012General-PrecinctLevel.zip",
      localFile: "data/al-2012-general-precinct-level-results.zip",
    },
    {
      id: "al-county-geometry",
      url: AL_GEOMETRY_URL,
      localFile: "data/al-counties.geojson",
    },
  ];
}

function floridaSourceDefinitions() {
  return [
    {
      id: "fl-2024-precinct-results",
      url: "https://dos.fl.gov/media/708761/2024-gen-outputofficial1.zip",
      localFile: "data/fl-2024-general-precinct-level-results.zip",
    },
    {
      id: "fl-2020-precinct-results",
      url: "https://fldoswebumbracoprod.blob.core.windows.net/media/703763/2020-general-election-rev.zip",
      localFile: "data/fl-2020-general-precinct-level-results.zip",
    },
    {
      id: "fl-2016-precinct-results",
      url: "https://dos.fl.gov/media/697454/precinctlevelelectionresults2016gen.zip",
      localFile: "data/fl-2016-general-precinct-level-results.zip",
    },
    {
      id: "fl-2012-precinct-results",
      url: "https://dos.fl.gov/media/697204/precinctlevelelectionresults2012gen.zip",
      localFile: "data/fl-2012-general-precinct-level-results.zip",
    },
    {
      id: "fl-precinct-results-data-definitions",
      url: "https://dos.fl.gov/media/709209/final-precinct-level-elections-data-definitions-and-field-codes_20250624.pdf",
      localFile: "data/fl-precinct-level-election-results-definitions.pdf",
    },
    {
      id: "fl-county-geometry",
      url: FL_GEOMETRY_URL,
      localFile: "data/fl-counties.geojson",
    },
  ];
}

function arizonaSourceDefinitions() {
  return [
    {
      id: "az-2024-county-source-manifest",
      url: AZ_SOS_ELECTION_INFO_URL,
      localFile: AZ_SOURCE_MANIFEST_FILE,
    },
    {
      id: "az-county-geometry",
      url: AZ_GEOMETRY_URL,
      localFile: "data/az-counties.geojson",
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

function applyAlabamaProfile(config) {
  const addedSources = [];
  const updatedSources = [];
  config.sources = (config.sources || []).filter((source) => !String(source.id || "").startsWith("al-discovered-"));
  for (const source of alabamaSourceDefinitions()) {
    const result = upsertSource(config, source);
    (result.added ? addedSources : updatedSources).push(source.id);
  }

  config.geometry = {
    sourceId: "al-county-geometry",
    outputFile: "data/al-counties.js",
    outputGlobal: "AL_COUNTIES_GEOJSON",
    nameProperty: "NAME",
    codeProperty: "COUNTY",
    expectedFeatures: 67,
  };
  config.certifiedResults = {
    format: "alabamaPrecinctZip",
    sourceId: "al-2024-precinct-results",
    contestName: "PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES",
    majorCandidates: {
      trump: { partyCode: "REP", candidateContains: "TRUMP" },
      harris: { partyCode: "DEM", candidateContains: "HARRIS" },
    },
    otherCandidates: [
      { key: "kennedy", label: "Robert F. Kennedy Jr.", partyCode: "IND", candidateContains: "KENNEDY" },
      { key: "oliver", label: "Chase Oliver", partyCode: "IND", candidateContains: "OLIVER" },
      { key: "stein", label: "Jill Stein", partyCode: "IND", candidateContains: "STEIN" },
      { key: "writeIn", label: "Write-In", partyCode: "NON", candidateContains: "WRITE" },
    ],
    excludeCandidatePatterns: ["OVER VOTES", "UNDER VOTES"],
  };
  config.reviewCharts = {
    format: "alabamaPrecinctZipComparison",
    sourceId: "al-2024-precinct-results",
    presidentContestName: "PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES",
    downBallotContestStartsWith: "UNITED STATES REPRESENTATIVE",
    partyCodes: { dem: "DEM", rep: "REP" },
    excludeCandidatePatterns: ["OVER VOTES", "UNDER VOTES"],
    policy: {
      outlierThresholdPct: 15,
      minCandidateVotes: 100,
      voteShareCorrelationThreshold: 0.35,
    },
  };
  config.turnout = {
    format: "alabamaPrecinctZipTurnout",
    sourceId: "al-2024-precinct-results",
    registrationSourceId: "al-2024-voter-registration",
    ballotsCastContestName: "BALLOTS CAST - TOTAL",
    registrationSheet: "December",
    registrationCountyColumn: 0,
    registeredVotersColumn: 1,
    registrationDenominatorTiming: "december2024VoterRegistrationWorkbook",
    sourceLevel: "county",
    notes: "Alabama SOS precinct-level results ZIP supplies county ballots-cast rows. Denominators use the December sheet total registered-voter column in the official ALVR-2024 workbook.",
    warningRequired: false,
  };
  config.historicalBaseline = {
    format: "alabamaPrecinctZip",
    sourceLevel: "county",
    rowMethod: "sosPrecinctZipCountyXlsAggregatedToCounty",
    contestName: "PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES",
    partyCodes: { dem: "DEM", rep: "REP" },
    excludeCandidatePatterns: ["OVER VOTES", "UNDER VOTES"],
    demCandidateContains: ["OBAMA"],
    repCandidateContains: ["ROMNEY"],
    sources: [
      {
        year: 2012,
        sourceId: "al-2012-precinct-results",
        wideContestName: "FOR PRESIDENT AND VICE-PRESIDENT OF THE UNITED STATES (Vote For 1)",
        demCandidateContains: ["OBAMA"],
        repCandidateContains: ["ROMNEY"],
        note: "Official Alabama Secretary of State 2012 general election precinct-level ZIP aggregated to county presidential rows.",
      },
      {
        year: 2016,
        sourceId: "al-2016-precinct-results",
        note: "Official Alabama Secretary of State 2016 general election precinct-level ZIP aggregated to county presidential rows.",
      },
      {
        year: 2020,
        sourceId: "al-2020-precinct-results",
        note: "Official Alabama Secretary of State 2020 general election precinct-level ZIP aggregated to county presidential rows.",
      },
      {
        year: 2024,
        sourceId: "al-2024-precinct-results",
        note: "Official Alabama Secretary of State 2024 general election precinct-level ZIP aggregated to county presidential rows.",
      },
    ],
  };

  config.app ||= {};
  config.app.countyLabel = "County";
  config.app.exportsSlug = "alabama-2024";
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
      title: "Alabama SOS 2024 General Precinct Level Results ZIP",
      detail: "Presidential county totals are aggregated from the official Alabama Secretary of State ZIP containing one county XLS workbook per county.",
      sourceUrl: AL_ELECTION_DATA_PAGE,
      localFile: "data/al-2024-general-precinct-level-results.zip; data/al-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official Alabama SOS election data downloads page groups the ZIP under 2024 election data.",
      status: "Loaded",
    },
    wardDetail: {
      title: "Alabama SOS county XLS precinct columns",
      detail: "The official ZIP contains county XLS workbooks with precinct columns. The state builder imports President rows and U.S. House rows for precinct-level review graphs.",
      sourceUrl: AL_ELECTION_DATA_PAGE,
      localFile: "data/al-2024-general-precinct-level-results.zip; data/al-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official Alabama SOS election data downloads page groups the ZIP under 2024 election data.",
      status: "Loaded",
    },
    turnout: {
      title: "Alabama SOS ballots-cast rows plus voter registration workbook",
      detail: "County turnout rows use BALLOTS CAST - TOTAL from the official precinct results ZIP divided by December total registered voters from ALVR-2024.xlsx.",
      sourceUrl: AL_ELECTION_DATA_PAGE,
      localFile: "data/al-2024-general-precinct-level-results.zip; data/al-2024-voter-registration.xlsx; data/al-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official Alabama SOS election data downloads page lists the precinct results ZIP and ALVR-2024 workbook.",
      status: "Loaded",
    },
  };
  config.app.turnoutPolicy = {
    route: "precinctZipBallotsCastAndRegistrationWorkbook",
    status: "Loaded",
    acceptedSource: "Alabama SOS 2024 General Precinct Level Results ZIP plus ALVR-2024 voter registration workbook.",
    warning: "Alabama turnout uses county ballots-cast rows from the official results ZIP and December total registered-voter denominators from ALVR-2024.xlsx.",
    requiredFields: ["county", "ballotsCast", "registeredVoters", "sourceUrl"],
  };
  config.app.historicalSummary =
    "Native official Alabama Secretary of State precinct-level ZIP workbooks are aggregated to county presidential rows for each election year.";
  config.app.reviewRowLabel = "Alabama SOS precinct column";
  config.app.reviewRowLabelPlural = "Alabama SOS precinct columns";
  config.app.reviewGraphTitlePrefix = "Alabama SOS precinct";
  config.app.mapLoadingText = "Loading local Alabama county boundaries...";
  config.app.noGeometryText = "Alabama county geometry is not loaded yet; showing the county tile fallback.";
  config.app.sourceInventory = [];
  config.app.checkedNotUsable = [];
  upsertInventory(config, {
    category: "Presidential county results",
    file: "data/al-2024-general-precinct-level-results.zip; data/al-app-data.js",
    sourceUrl: AL_ELECTION_DATA_PAGE,
    usedFor: "Alabama county table, statewide totals, candidate breakdown, CSV export, Source Planner rows, and precinct-level review graphs.",
    confidence: "Official Alabama Secretary of State 2024 General Precinct Level Results ZIP.",
  });
  upsertInventory(config, {
    category: "Turnout denominator source",
    file: "data/al-2024-voter-registration.xlsx; data/al-app-data.js",
    sourceUrl: AL_ELECTION_DATA_PAGE,
    usedFor: "Alabama turnout graph and Source Planner turnout coverage.",
    confidence: "Official Alabama Secretary of State ALVR-2024 voter registration workbook.",
  });
  upsertInventory(config, {
    category: "Historical presidential baseline",
    file: "data/al-2012-general-precinct-level-results.zip; data/al-2016-general-precinct-level-results.zip; data/al-2020-general-precinct-level-results.zip; data/al-2024-general-precinct-level-results.zip; data/al-app-data.js",
    sourceUrl: AL_ELECTION_DATA_PAGE,
    usedFor: "Alabama Historical Baseline tab: native SOS precinct ZIP rows aggregated to county presidential comparison rows for 2012, 2016, 2020, and 2024.",
    confidence: "Official Alabama Secretary of State general election precinct-level ZIP files.",
  });
  upsertInventory(config, {
    category: "County boundaries",
    file: "data/al-counties.geojson; data/al-counties.js",
    sourceUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer",
    usedFor: "Alabama county polygon map.",
    confidence: "U.S. Census TIGERweb county geography.",
  });
  config.expected = {
    countyRows: 67,
    precinctRows: 2083,
    stateTotal: 2265090,
    trump: 1462616,
    harris: 772412,
    other: 30062,
    reviewRows: 2083,
    turnoutRows: 67,
    turnoutWarningRows: 0,
    historicalSeries: 4,
    historicalRows: 268,
    geometryFeatures: 67,
  };

  return {
    profile: "alabamaSosElectionData",
    status: "applied",
    addedSources,
    updatedSources,
    loadedCapabilities: Object.entries(config.app.capabilities)
      .filter(([, enabled]) => enabled)
      .map(([name]) => name),
  };
}

function applyFloridaProfile(config) {
  const addedSources = [];
  const updatedSources = [];
  config.sources = (config.sources || []).filter((source) => !String(source.id || "").startsWith("fl-discovered-"));
  for (const source of floridaSourceDefinitions()) {
    const result = upsertSource(config, source);
    (result.added ? addedSources : updatedSources).push(source.id);
  }

  config.geometry = {
    sourceId: "fl-county-geometry",
    outputFile: "data/fl-counties.js",
    outputGlobal: "FL_COUNTIES_GEOJSON",
    nameProperty: "NAME",
    codeProperty: "COUNTY",
    expectedFeatures: 67,
  };
  config.certifiedResults = {
    format: "floridaPrecinctZip",
    sourceId: "fl-2024-precinct-results",
    contestName: "President and Vice President",
    majorCandidates: {
      trump: { partyCode: "REP", candidateContains: "TRUMP" },
      harris: { partyCode: "DEM", candidateContains: "HARRIS" },
    },
    otherCandidates: [
      { key: "stein", label: "Jill Stein / Butch Ware", partyCode: "GRE", candidateContains: "STEIN" },
      { key: "writeIn", label: "Write-In", candidateContains: "WRITE" },
      { key: "oliver", label: "Chase Oliver / Mike ter Maat", partyCode: "LPF", candidateContains: "OLIVER" },
      { key: "deLaCruz", label: "Claudia De la Cruz / Karina Garcia", partyCode: "PSL", candidateContains: "CRUZ" },
      { key: "sonski", label: "Peter Sonski / Lauren Onak", partyCode: "ASP", candidateContains: "SONSKI" },
      { key: "terry", label: "Randall Terry / Stephen Broden", partyCode: "CPF", candidateContains: "TERRY" },
    ],
    excludeCandidatePatterns: ["OverVotes", "UnderVotes"],
  };
  config.reviewCharts = {
    format: "floridaPrecinctZipComparison",
    sourceId: "fl-2024-precinct-results",
    presidentContestName: "President and Vice President",
    downBallotContestName: "United States Senator",
    majorCandidates: {
      trump: { partyCode: "REP", candidateContains: "TRUMP" },
      harris: { partyCode: "DEM", candidateContains: "HARRIS" },
    },
    partyCodes: { dem: "DEM", rep: "REP" },
    excludeCandidatePatterns: ["OverVotes", "UnderVotes"],
    policy: {
      outlierThresholdPct: 15,
      minCandidateVotes: 100,
      voteShareCorrelationThreshold: 0.35,
    },
  };
  config.turnout = {
    format: "floridaPrecinctZipTurnout",
    sourceId: "fl-2024-precinct-results",
    contestName: "President and Vice President",
    registrationDenominatorTiming: "officialPrecinctFileRegisteredVoters",
    sourceLevel: "precinct",
    notes: "Florida Division of Elections precinct-level file. Ballots cast are presidential-contest rows including candidate votes, write-ins, overvotes, and undervotes; denominators use the file's Total Registered voters field.",
    warningRequired: false,
  };
  config.historicalBaseline = {
    format: "floridaPrecinctZip",
    sourceLevel: "county",
    rowMethod: "doePrecinctZipAggregatedToCounty",
    contestName: "President and Vice President",
    partyCodes: { dem: "DEM", rep: "REP" },
    alternateRepPartyCodes: ["RPO"],
    excludeCandidatePatterns: ["OverVotes", "UnderVotes", "Times Blank Voted", "Times Over Voted", "Number of Under Votes"],
    sources: [
      {
        year: 2012,
        sourceId: "fl-2012-precinct-results",
        contestName: "President of the United States",
        note: "Official Florida Division of Elections 2012 general election precinct-level ZIP aggregated to county presidential rows.",
      },
      {
        year: 2016,
        sourceId: "fl-2016-precinct-results",
        contestName: "President of the United States",
        note: "Official Florida Division of Elections 2016 general election precinct-level ZIP aggregated to county presidential rows.",
      },
      {
        year: 2020,
        sourceId: "fl-2020-precinct-results",
        contestName: "President of the United States",
        note: "Official Florida Division of Elections 2020 general election precinct-level ZIP aggregated to county presidential rows.",
      },
      {
        year: 2024,
        sourceId: "fl-2024-precinct-results",
        contestName: "President and Vice President",
        note: "Official Florida Division of Elections 2024 general election precinct-level ZIP aggregated to county presidential rows.",
      },
    ],
  };

  config.app ||= {};
  config.app.countyLabel = "County";
  config.app.exportsSlug = "florida-2024";
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
      title: "Florida DOE 2024 precinct-level results ZIP",
      detail: "Presidential county totals are aggregated from the official Florida Division of Elections 2024 General Election precinct-level tab-delimited ZIP.",
      sourceUrl: FL_PRECINCT_RESULTS_PAGE,
      localFile: "data/fl-2024-general-precinct-level-results.zip; data/fl-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official Florida DOE precinct-level results page, updated June 2, 2026, links the 2024 General Election ZIP.",
      status: "Loaded",
    },
    wardDetail: {
      title: "Florida DOE precinct-level tab-delimited files",
      detail: "The official ZIP contains one county text file per county. The state builder imports President and U.S. Senate rows for precinct-level review graphs.",
      sourceUrl: FL_PRECINCT_RESULTS_PAGE,
      localFile: "data/fl-2024-general-precinct-level-results.zip; data/fl-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Official Florida DOE data-definition PDF maps the 19 tab-delimited fields used by the ZIP.",
      status: "Loaded",
    },
    turnout: {
      title: "Florida DOE precinct registered-voter and presidential participation rows",
      detail: "Precinct turnout rows use presidential-contest vote totals, including overvotes and undervotes, divided by the Total Registered voters field in the official precinct-level ZIP.",
      sourceUrl: `${FL_PRECINCT_RESULTS_PAGE}; ${FL_VOTER_TURNOUT_PAGE}`,
      localFile: "data/fl-2024-general-precinct-level-results.zip; data/fl-app-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Florida DOE voter-turnout page defines turnout against active registered voters and points to book-closing reports; the precinct ZIP includes registered-voter denominators by precinct.",
      status: "Loaded",
    },
  };
  config.app.turnoutPolicy = {
    route: "precinctFileRegisteredVotersAndPresidentContestParticipation",
    status: "Loaded",
    acceptedSource: "Florida Division of Elections 2024 General Election precinct-level results ZIP.",
    warning: "Florida turnout rows use presidential-contest participation including overvotes and undervotes divided by the precinct registered-voter field.",
    requiredFields: ["county", "ward", "ballotsCast", "registeredVoters", "sourceUrl"],
  };
  config.app.historicalSummary =
    "Native official Florida Division of Elections precinct-level ZIP files are aggregated to county presidential rows for each election year.";
  config.app.reviewRowLabel = "Florida DOE precinct row";
  config.app.reviewRowLabelPlural = "Florida DOE precinct rows";
  config.app.reviewGraphTitlePrefix = "Florida DOE precinct";
  config.app.mapLoadingText = "Loading local Florida county boundaries...";
  config.app.noGeometryText = "Florida county geometry is not loaded yet; showing the county tile fallback.";
  config.app.sourceInventory = [];
  config.app.checkedNotUsable = [];
  upsertInventory(config, {
    category: "Presidential county results",
    file: "data/fl-2024-general-precinct-level-results.zip; data/fl-app-data.js",
    sourceUrl: FL_PRECINCT_RESULTS_PAGE,
    usedFor: "Florida county table, statewide totals, candidate breakdown, CSV export, Source Planner rows, and precinct-level review graphs.",
    confidence: "Official Florida Division of Elections 2024 General Election precinct-level results ZIP.",
  });
  upsertInventory(config, {
    category: "Turnout denominator source",
    file: "data/fl-2024-general-precinct-level-results.zip; data/fl-app-data.js",
    sourceUrl: `${FL_PRECINCT_RESULTS_PAGE}; ${FL_VOTER_TURNOUT_PAGE}`,
    usedFor: "Florida turnout graph and Source Planner turnout coverage.",
    confidence: "Official Florida Division of Elections precinct-level ZIP fields plus DOE voter-turnout definition.",
  });
  upsertInventory(config, {
    category: "Historical presidential baseline",
    file: "data/fl-2012-general-precinct-level-results.zip; data/fl-2016-general-precinct-level-results.zip; data/fl-2020-general-precinct-level-results.zip; data/fl-2024-general-precinct-level-results.zip; data/fl-app-data.js",
    sourceUrl: FL_PRECINCT_RESULTS_PAGE,
    usedFor: "Florida Historical Baseline tab: native DOE precinct-level ZIP rows aggregated to county presidential comparison rows for 2012, 2016, 2020, and 2024.",
    confidence: "Official Florida Division of Elections general election precinct-level ZIP files.",
  });
  upsertInventory(config, {
    category: "County boundaries",
    file: "data/fl-counties.geojson; data/fl-counties.js",
    sourceUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer",
    usedFor: "Florida county polygon map.",
    confidence: "U.S. Census TIGERweb county geography.",
  });
  upsertInventory(config, {
    category: "Field definitions",
    file: "data/fl-precinct-level-election-results-definitions.pdf",
    sourceUrl: "https://dos.fl.gov/media/709209/final-precinct-level-elections-data-definitions-and-field-codes_20250624.pdf",
    usedFor: "Parser field mapping for Florida precinct-level results.",
    confidence: "Official Florida Division of Elections data-definition PDF.",
  });
  config.expected = {
    countyRows: 67,
    precinctRows: 5712,
    stateTotal: 10935466,
    trump: 6110126,
    harris: 4683038,
    other: 142302,
    reviewRows: 5620,
    turnoutRows: 5712,
    turnoutWarningRows: 0,
    historicalSeries: 4,
    historicalRows: 268,
    geometryFeatures: 67,
  };

  return {
    profile: "floridaDoePrecinctResults",
    status: "applied",
    addedSources,
    updatedSources,
    loadedCapabilities: Object.entries(config.app.capabilities)
      .filter(([, enabled]) => enabled)
      .map(([name]) => name),
  };
}

function applyArizonaProfile(config) {
  const addedSources = [];
  const updatedSources = [];
  config.sources = (config.sources || []).filter((source) => !String(source.id || "").startsWith("az-"));
  for (const source of arizonaSourceDefinitions()) {
    const result = upsertSource(config, source);
    (result.added ? addedSources : updatedSources).push(source.id);
  }

  config.geometry = {
    sourceId: "az-county-geometry",
    outputFile: "data/az-counties.js",
    outputGlobal: "AZ_COUNTIES_GEOJSON",
    nameProperty: "NAME",
    codeProperty: "COUNTY",
    expectedFeatures: 15,
  };
  config.certifiedResults = {
    format: "notConfigured",
    sourceId: "az-2024-county-source-manifest",
    otherCandidates: [],
    aggregateFields: {},
  };
  config.reviewCharts = {
    format: "notConfigured",
    sourceId: "az-2024-county-source-manifest",
    policy: {
      outlierThresholdPct: 15,
      minCandidateVotes: 100,
      voteShareCorrelationThreshold: 0.35,
    },
  };
  config.turnout = {
    format: "notConfigured",
    sourceId: "az-2024-county-source-manifest",
    registrationDenominatorTiming: "countyCanvassOrCountyExport",
    sourceLevel: "precinct",
    notes: "Arizona turnout is not loaded yet. The official statewide results app and SOS-hosted canvass PDFs are Cloudflare-protected from automated access; county canvass files use mixed PDF, SOV text, Excel, and HTML result-page formats.",
    warningRequired: true,
  };
  config.historicalBaseline = {
    sourceLevel: "county",
    rowMethod: "notConfigured",
    partyCodes: { dem: "DEM", rep: "REP" },
    contestName: "Presidential Electors",
    sources: [],
  };

  config.app ||= {};
  config.app.countyLabel = "County";
  config.app.exportsSlug = "az-2024";
  config.app.capabilities = {
    sourcePlanner: true,
    certifiedResults: false,
    map: false,
    reviewGraphs: false,
    turnout: false,
    historicalBaseline: false,
  };
  config.app.sourcePlan = {
    ...(config.app.sourcePlan || {}),
    certifiedResults: {
      title: "Arizona protected statewide results app",
      detail: "The official Arizona results application is the statewide public results surface, but automated headless and direct HTTP access returned Cloudflare verification pages instead of the application payload.",
      sourceUrl: AZ_RESULTS_APP_URL,
      localFile: `${AZ_SOURCE_MANIFEST_FILE}; data/az-app-data.js`,
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Checked by browser-backed snapshot and direct HTTP download attempts; both returned Cloudflare verification pages in this environment.",
      status: "Blocked by source protection",
    },
    wardDetail: {
      title: "Arizona county-source manifest",
      detail: "The scripted Arizona manifest records county canvass/source candidates and parser-family hints. Known candidates include Apache County's downloadable official PDF, Coconino's county results page, and Maricopa's official SOV text link discovered from its historic results page.",
      sourceUrl: AZ_SOS_ELECTION_INFO_URL,
      localFile: `${AZ_SOURCE_MANIFEST_FILE}; data/az-app-data.js`,
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Generated by scripts/build-arizona-source-manifest.mjs from official statewide, SOS, and county result surfaces discovered during source collection.",
      status: "Needs protected-download route",
    },
    turnout: {
      title: "Arizona mixed county turnout sources",
      detail: "Arizona turnout rows require county canvass/export parsing. Apache's PDF text exposes precinct registered-voter rows, while Maricopa's official SOV description defines text fields; most SOS-hosted county canvass PDFs remain protected.",
      sourceUrl: AZ_RESULTS_APP_URL,
      localFile: `${AZ_SOURCE_MANIFEST_FILE}; data/az-app-data.js`,
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "Manifest generated from official result-app, SOS election-info, and county result-page sources.",
      status: "Needs protected-download route",
    },
  };
  config.app.sourceManifest = {
    localFile: AZ_SOURCE_MANIFEST_FILE,
    buildCommand: "npm.cmd run build:arizona:sources",
    status: "Generated",
  };
  config.app.turnoutPolicy = {
    route: "countyCanvassOrCountyExport",
    status: "Needs protected-download route",
    acceptedSource: "Not loaded yet.",
    warning: "Arizona turnout should not be inferred until the mixed county canvass/export source set is scripted, locally available, and reconciled.",
    requiredFields: ["county", "ballotsCast", "registeredVoters", "sourceUrl"],
  };
  config.app.historicalSummary = "Historical comparison data is not loaded yet.";
  config.app.reviewRowLabel = "Arizona county source row";
  config.app.reviewRowLabelPlural = "Arizona county source rows";
  config.app.reviewGraphTitlePrefix = "Arizona county source";
  config.app.mapLoadingText = "Loading local Arizona county boundaries...";
  config.app.noGeometryText = "Arizona county geometry is not loaded yet; showing the county tile fallback.";
  config.app.sourceInventory = [];
  upsertInventory(config, {
    category: "County source manifest",
    file: AZ_SOURCE_MANIFEST_FILE,
    sourceUrl: AZ_SOS_ELECTION_INFO_URL,
    usedFor: "Arizona Source Planner discovery state, county source collection, parser-family hints, and protected-download follow-up tracking.",
    confidence: "Scripted manifest from official Arizona statewide, SOS, and county result surfaces.",
  });
  upsertInventory(config, {
    category: "County boundaries",
    file: "data/az-counties.geojson; data/az-counties.js",
    sourceUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer",
    usedFor: "Arizona county polygon map once Arizona app data is promoted.",
    confidence: "U.S. Census TIGERweb county geography.",
  });
  config.app.checkedNotUsable = [];
  addChecked(config, {
    category: "Protected election-results application",
    sourceUrl: AZ_RESULTS_APP_URL,
    reason: "The official statewide results application returned a Cloudflare verification page to headless browser snapshots and direct HTTP requests.",
    status: "Blocked by cloudflare",
    nextStep: "Find an official static export endpoint, use an allowed interactive capture, or build Arizona from county-hosted official canvass files.",
  });
  addChecked(config, {
    category: "Protected SOS county canvass PDFs",
    sourceUrl: "https://apps.azsos.gov/election/2024/ge/canvass/202411GeneralElectionCanvass-Gila.pdf",
    reason: "SOS-hosted county canvass PDF URLs returned Cloudflare verification pages to direct HTTP download attempts.",
    status: "Blocked by cloudflare",
    nextStep: "Prefer county-hosted official canvass files where available, or use an approved capture route for SOS-hosted PDFs.",
  });
  addChecked(config, {
    category: "County SOV text direct download",
    sourceUrl: "https://elections.maricopa.gov/results-and-data/historic-results.html?year=2024",
    reason: "Browser snapshot recovered Maricopa's official 2024 SOV text and file-description links, but direct headless file download from the county asset host returned Cloudflare verification.",
    status: "Discovery only",
    nextStep: "Add a protected-download strategy or request an allowed static mirror for the official Maricopa SOV text file.",
  });
  config.expected = {
    countyRows: 0,
    precinctRows: 0,
    stateTotal: 0,
    trump: 0,
    harris: 0,
    other: 0,
    reviewRows: 0,
    turnoutRows: 0,
    turnoutWarningRows: 0,
    historicalSeries: 0,
    historicalRows: 0,
    geometryFeatures: 0,
  };

  return {
    profile: "arizonaCountySourceManifest",
    status: "applied",
    addedSources,
    updatedSources,
    artifactCommands: [
      {
        name: "arizona-source-manifest",
        command: "node",
        args: ["scripts/build-arizona-source-manifest.mjs", "--output", AZ_SOURCE_MANIFEST_FILE],
      },
    ],
    loadedCapabilities: Object.entries(config.app.capabilities)
      .filter(([, enabled]) => enabled)
      .map(([name]) => name),
  };
}

export function applyStateSourceProfile(config, report = {}) {
  const code = String(config.code || report.state || "").toUpperCase();
  const inputUrl = String(report.input?.url || "");
  const pageTitle = String(report.page?.title || "");
  const isArizonaResultsSource =
    code === "AZ" &&
    (inputUrl.includes("results.arizona.vote") ||
      inputUrl.includes("azsos.gov/events/local-elections/408") ||
      pageTitle.includes("Just a moment"));
  if (isArizonaResultsSource) {
    return applyArizonaProfile(config, report);
  }
  const isFloridaPrecinctResults =
    code === "FL" &&
    (inputUrl.includes("/elections-data/precinct-level-election-results") ||
      pageTitle.includes("Precinct-Level Election Results"));
  if (isFloridaPrecinctResults) {
    return applyFloridaProfile(config, report);
  }
  const isAlabamaElectionData =
    code === "AL" &&
    (inputUrl.includes("sos.alabama.gov/alabama-votes/voter/election-data") ||
      pageTitle.includes("Elections Data Downloads"));
  if (isAlabamaElectionData) {
    return applyAlabamaProfile(config, report);
  }
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
