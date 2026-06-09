const WI_RESULTS = window.WI_ELECTION_APP_DATA.presidentCountyResults;
const WI_CANDIDATE_LABELS = window.WI_ELECTION_APP_DATA.candidateLabels;
const WI_COUNTIES_GEOJSON = window.WI_COUNTIES_GEOJSON;
const WI_HISTORICAL_BASELINE = window.WI_HISTORICAL_BASELINE;
const WI_TURNOUT_DATA = window.WI_TURNOUT_DATA;
const MN_ELECTION_APP_DATA = window.MN_ELECTION_APP_DATA || { presidentCountyResults: [], candidateLabels: [] };
const MN_RESULTS = MN_ELECTION_APP_DATA.presidentCountyResults || [];
const MN_CANDIDATE_LABELS = MN_ELECTION_APP_DATA.candidateLabels || [];
const MN_REVIEW_CHARTS = MN_ELECTION_APP_DATA.reviewCharts || null;
const MN_ETA_ANALYSIS = MN_ELECTION_APP_DATA.etaAnalysis || null;
const MN_TURNOUT_DATA = MN_ELECTION_APP_DATA.turnoutData || { metadata: {}, rows: [] };
const MN_HISTORICAL_BASELINE = MN_ELECTION_APP_DATA.historicalBaseline || null;
const MN_COUNTIES_GEOJSON = window.MN_COUNTIES_GEOJSON || null;
const STATE_APP_REGISTRY = window.STATE_APP_REGISTRY?.states || [];
const STATE_REGISTRY_BY_CODE = new Map(STATE_APP_REGISTRY.map((entry) => [entry.code, entry]));
let activeStateCode = "WI";
let RESULTS = WI_RESULTS;
let CANDIDATE_LABELS = WI_CANDIDATE_LABELS;
let LOCAL_COUNTIES_GEOJSON = WI_COUNTIES_GEOJSON;
let HISTORICAL_BASELINE = WI_HISTORICAL_BASELINE;
let TURNOUT_DATA = WI_TURNOUT_DATA;
const HISTORICAL_PRIMARY_SERIES_IDS = [
  "ltsb-harmonized-2012-president",
  "ltsb-harmonized-2016-president",
  "ltsb-harmonized-2020-president",
  "ltsb-harmonized-2024-president",
];
const HISTORICAL_SERIES_LABELS = {
  "ltsb-harmonized-2012-president": "2012 LTSB harmonized wards",
  "ltsb-harmonized-2016-president": "2016 LTSB harmonized wards",
  "ltsb-harmonized-2020-president": "2020 LTSB harmonized wards",
  "ltsb-harmonized-2024-president": "2024 LTSB harmonized wards",
  "wec-native-2016-president-original": "2016 WEC native original canvass",
  "wec-native-2016-president-recount": "2016 WEC native recount",
  "wec-native-2024-president": "2024 WEC native reporting units",
  "mn-sos-native-2012-president": "2012 Minnesota SOS native precincts",
  "mn-sos-native-2016-president": "2016 Minnesota SOS native precincts",
  "mn-sos-native-2020-president": "2020 Minnesota SOS native precincts",
  "mn-sos-native-2024-president": "2024 Minnesota SOS native precincts",
};

const MN_HISTORICAL_PRIMARY_SERIES_IDS = [
  "mn-sos-native-2012-president",
  "mn-sos-native-2016-president",
  "mn-sos-native-2020-president",
  "mn-sos-native-2024-president",
];

const ETA_ANALYSIS = {
  wardRows: 3603,
  downBallot: {
    demDropVotes: -4548,
    demDropPct: -0.2726,
    repDropVotes: 53630,
    repDropPct: 3.1591,
    demOutlierWards: 15,
    repOutlierWards: 46,
    outlierThresholdPct: 15,
    minCandidateVotes: 100,
  },
  voteShare: {
    trumpCorrelation: 0.2143,
    harrisCorrelation: 0.4145,
    threshold: 0.35,
  },
};

const TURNOUT_SOURCE_POLICY = {
  route: "countyMunicipalPdfs",
  status: "Needs data",
  acceptedSource:
    "County or municipal ward-by-ward canvass reports with registered voters and ballots cast.",
  warning:
    "Warning: some local reports label registered-voter counts as the number registered before Election Day. Wisconsin allows Election Day registration, so those denominators can be too low and can produce turnout rates over 100% without implying excess ballots or fraud.",
  requiredFields: [
    "county",
    "municipality",
    "ward",
    "ballotsCast",
    "registeredVoters",
    "registrationDenominatorTiming",
    "sourceUrl",
  ],
};

const DATA_VERSION_LABEL = "June 2026 local bundle";

const WEC_2024_SOURCE_TIMESTAMPS = {
  countyPresidentLastModifiedUtc: "2024-11-27T21:31:27Z",
  countySenateLastModifiedUtc: "2024-11-27T21:31:28Z",
  wardFederalStateLastModifiedUtc: "2024-11-27T21:35:53Z",
  auditSelectionLastModifiedUtc: "2024-11-07T15:25:08Z",
  auditMarchMaterialsLastModifiedUtc: "2025-02-28T14:41:12Z",
  basis: "HTTP Last-Modified response header from the live WEC file URL; this confirms the file object timestamp, not necessarily the first public link date.",
};

const WEC_2024_WARD_SOURCE_URL =
  "https://elections.wi.gov/sites/default/files/documents/Ward%20by%20Ward%20Report%20by%20Congressional%20District_November%205%202024%20General%20Election_Federal%20and%20State%20Contests.xlsx";

const MN_2024_SOURCE_TIMESTAMPS = {
  precinctFederalStateLastModifiedUtc: "2025-02-14T17:22:26Z",
  basis:
    "HTTP Last-Modified response header from the live Minnesota Secretary of State file URL on a GET response; this confirms the file object timestamp, not necessarily the first public link date.",
};

const MN_2024_PRECINCT_SOURCE_URL =
  "https://www.sos.mn.gov/media/yt3llxwd/2024-general-federal-state-results-by-precinct-official.xlsx";

const SOURCE_INVENTORY = [
  {
    category: "Presidential county results",
    file: "data/County by County Report_POTUS.pdf; data/president-county-results.json",
    sourceUrl: "https://elections.wi.gov/sites/default/files/documents/County%20by%20County%20Report_POTUS.pdf",
    sourceLastModifiedUtc: WEC_2024_SOURCE_TIMESTAMPS.countyPresidentLastModifiedUtc,
    sourceTimestampBasis: WEC_2024_SOURCE_TIMESTAMPS.basis,
    usedFor: "Map shading, county table, statewide totals, candidate breakdown, CSV export, selected-county details.",
    confidence: "Official WEC certified county result report.",
  },
  {
    category: "U.S. Senate county results",
    file: "data/County by County Report_US Senate.pdf",
    sourceUrl: "https://elections.wi.gov/sites/default/files/documents/County%20by%20County%20Report_US%20Senate_1.pdf",
    sourceLastModifiedUtc: WEC_2024_SOURCE_TIMESTAMPS.countySenateLastModifiedUtc,
    sourceTimestampBasis: WEC_2024_SOURCE_TIMESTAMPS.basis,
    usedFor: "County-level verification context for down-ballot comparison.",
    confidence: "Official WEC certified county result report.",
  },
  {
    category: "Ward federal/state results",
    file: "data/Ward by Ward Report Federal and State Contests.xlsx; data/ward-analysis.json; data/eta-data.js",
    sourceUrl:
      "https://web.archive.org/web/20241130045633id_/https://elections.wi.gov/sites/default/files/documents/Ward%20by%20Ward%20Report%20by%20Congressional%20District_November%205%202024%20General%20Election_Federal%20and%20State%20Contests.xlsx",
    sourceLastModifiedUtc: WEC_2024_SOURCE_TIMESTAMPS.wardFederalStateLastModifiedUtc,
    sourceTimestampBasis: `Original WEC file URL HTTP Last-Modified response header: ${WEC_2024_WARD_SOURCE_URL}. The app links the archived copy for durability.`,
    usedFor: "Vote-share by vote-count scatterplots, presidential-versus-Senate drop-off histograms, selected-county graph filtering.",
    confidence: "Official WEC ward-level vote totals; graph interpretation remains a screening tool.",
  },
  {
    category: "County boundaries",
    file: "data/wi-counties.geojson; data/wi-counties.js",
    sourceUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer",
    usedFor: "County polygon map.",
    confidence: "U.S. Census TIGERweb geography.",
  },
  {
    category: "Turnout imported rows",
    file: "data/milwaukee-city-turnout.csv; data/dane-county-turnout.csv; data/jefferson-county-turnout.csv; data/oneida-county-turnout.csv; data/turnout-data.json/js",
    sourceUrl: "Multiple local county/municipal sources; see county coverage table.",
    usedFor: "Partial turnout histogram and denominator-warning labels.",
    confidence: "Partial coverage; warning-gated when denominator timing is pre-Election-Day or unknown.",
  },
  {
    category: "Historical presidential baseline",
    file: "data/historical-data.js; data/historical/generated/historical-presidential-summary.json; data/historical/generated/historical-reconciliation-report.json",
    sourceUrl: "https://geodiscovery.uwm.edu/catalog/317F4F49-5B17-43CC-9BCA-36ED25DC9E15",
    usedFor: "Historical Baseline tab: presidential vote-share comparisons across 2012, 2016, 2020, and 2024.",
    confidence: "The displayed multi-year trend uses LTSB harmonized comparison rows for every year. Native official WEC 2024 reporting-unit rows remain available as a separate selectable series.",
  },
  {
    category: "Historical 2024 LTSB comparison layer",
    file: "data/historical/raw/2024-ltsb-harmonized-wards.geojson.gz; data/historical/raw/ltsb-election-data-schema-definitions.pdf",
    sourceUrl: "https://www.arcgis.com/home/item.html?id=878d8826218f42509e07437a82ef6b6e",
    usedFor: "Apples-to-apples 2024 harmonized ward comparison in the Historical Baseline tab.",
    confidence: "Official LTSB comparison layer. Statewide and county totals reconcile to native WEC results; ward rows remain visibly labeled as population-allocated harmonized values.",
  },
  {
    category: "2024 post-election voting-equipment audit",
    file: "Official WEC March 7, 2025 meeting materials and October 4, 2024 adopted procedures",
    sourceUrl: "https://elections.wi.gov/sites/default/files/documents/OPEN%20Session%20Materials%20-March%207_FINAL%20for%20Web%20Posting_0.pdf#page=51",
    sourceLastModifiedUtc: WEC_2024_SOURCE_TIMESTAMPS.auditMarchMaterialsLastModifiedUtc,
    sourceTimestampBasis: WEC_2024_SOURCE_TIMESTAMPS.basis,
    usedFor: "Audit Simulator report summary, municipality-tier presets, and educational sampling-coverage model.",
    confidence: "Official WEC materials. Simulator scenarios are illustrative hypotheticals, not findings and not reconstructions of the actual audit sample.",
  },
];

const CHECKED_NOT_USABLE = [
  {
    county: "Waukesha",
    sourceUrl: "https://www.waukeshacounty.gov/media/tcgned1s/fed-state-official-results-detail.xlsx",
    reason: "Official detail file was checked, but it did not contain registered-voter or eligible-voter denominator fields needed for turnout analysis.",
    missingFields: "registeredVoters or eligibleVoters denominator; denominator timing",
  },
];

const MN_SOURCE_INVENTORY = [
  {
    category: "Presidential county results",
    file: "data/mn-2024-general-federal-state-results-by-precinct-official.xlsx; data/mn-app-data.js",
    sourceUrl: MN_2024_PRECINCT_SOURCE_URL,
    sourceLastModifiedUtc: MN_2024_SOURCE_TIMESTAMPS.precinctFederalStateLastModifiedUtc,
    sourceTimestampBasis: MN_2024_SOURCE_TIMESTAMPS.basis,
    usedFor: "Minnesota county table, statewide totals, candidate breakdown, review graphs, turnout graph, CSV export, and Source Planner readiness rows.",
    confidence: "Official Minnesota Secretary of State federal/state precinct results spreadsheet, aggregated to county totals by the local importer.",
  },
  {
    category: "Historical presidential baseline",
    file: "data/mn-2012-us-president-by-county.txt; data/mn-2016-us-president-by-county.txt; data/mn-2020-us-president-by-county.txt; data/mn-2024-us-president-by-county.txt; data/mn-app-data.js",
    sourceUrl: "https://www.sos.mn.gov/elections-voting/election-results/",
    usedFor: "Minnesota Historical Baseline tab: native SOS county presidential comparison rows for 2012, 2016, 2020, and 2024.",
    confidence: "Official Minnesota Secretary of State President-by-County text files.",
  },
  {
    category: "County boundaries",
    file: "data/mn-counties.geojson; data/mn-counties.js",
    sourceUrl: "https://feat.gisdata.mn.gov/arcgis/rest/services/MnGeo/mn_counties/FeatureServer/0",
    usedFor: "Minnesota county polygon map.",
    confidence: "MnGeo county boundary feature service, transformed to app-ready GeoJSON.",
  },
];

const MN_CHECKED_NOT_USABLE = [];

const MN_TURNOUT_SOURCE_POLICY = {
  route: "statePrecinctSpreadsheet",
  status: "Loaded",
  acceptedSource:
    "The Minnesota SOS precinct spreadsheet includes REG7AM, EDR, signatures, absentee/mail ballots, and total voting fields. The app uses REG7AM plus EDR as the registered-voter denominator for Minnesota turnout rows.",
  warning:
    "Minnesota turnout rows use SOS REG7AM plus EDR as the denominator. Compare with county records before treating any single precinct's turnout rate as a finding.",
  requiredFields: [
    "county",
    "precinct",
    "registeredVoters",
    "ballotsCast",
    "registrationDenominatorTiming",
    "sourceUrl",
  ],
};

const STATE_SOURCE_PLANS = {
  WI: {
    code: "WI",
    state: "Wisconsin",
    electionYear: 2024,
    office: "President",
    stateAuthority: "Wisconsin Elections Commission",
    countyLabel: "County",
    exportsSlug: "wisconsin-2024",
    resultRows: WI_RESULTS,
    certifiedResults: {
      title: "WEC certified county result report",
      detail:
        "Presidential county totals are imported from the Wisconsin Elections Commission certified County by County Report_POTUS PDF and reconciled into the app's county result bundle.",
      sourceUrl: "https://elections.wi.gov/sites/default/files/documents/County%20by%20County%20Report_POTUS.pdf",
      localFile: "data/County by County Report_POTUS.pdf; data/president-county-results.json",
      sourceLastModifiedUtc: WEC_2024_SOURCE_TIMESTAMPS.countyPresidentLastModifiedUtc,
      sourceTimestampBasis: WEC_2024_SOURCE_TIMESTAMPS.basis,
      status: "Loaded",
    },
    wardDetail: {
      title: "WEC ward federal/state contest spreadsheet",
      detail:
        "Ward and reporting-unit presidential and U.S. Senate rows come from the WEC federal/state contest spreadsheet, with app-ready analysis rows stored in ward-analysis and eta-data bundles.",
      sourceUrl:
        "https://web.archive.org/web/20241130045633id_/https://elections.wi.gov/sites/default/files/documents/Ward%20by%20Ward%20Report%20by%20Congressional%20District_November%205%202024%20General%20Election_Federal%20and%20State%20Contests.xlsx",
      localFile: "data/Ward by Ward Report Federal and State Contests.xlsx; data/ward-analysis.json; data/eta-data.js",
      sourceLastModifiedUtc: WEC_2024_SOURCE_TIMESTAMPS.wardFederalStateLastModifiedUtc,
      sourceTimestampBasis: `Original WEC file URL HTTP Last-Modified response header: ${WEC_2024_WARD_SOURCE_URL}. The app links the archived copy for durability.`,
      status: "Loaded",
    },
    turnout: {
      title: "County and municipal turnout denominator records",
      detail:
        "Turnout rows are imported only where local county or municipal sources include ballots-cast and registered-voter denominator fields. Wisconsin rows keep denominator timing warnings because Election Day registration can make preliminary denominators too low.",
      sourceUrl: "Multiple county and municipal sources; see county rows.",
      localFile: "data/turnout-data.json; data/turnout-data.js",
      sourceLastModifiedUtc: "",
      sourceTimestampBasis: "County and municipal turnout source timestamps are tracked per imported source when collected; not all local rows expose comparable HTTP metadata yet.",
      status: "Partial",
    },
  },
  MN: {
    code: "MN",
    state: "Minnesota",
    electionYear: 2024,
    office: "President",
    stateAuthority: "Minnesota Secretary of State",
    countyLabel: "County",
    exportsSlug: "minnesota-2024",
    resultRows: MN_RESULTS,
    certifiedResults: {
      title: "Minnesota SOS official federal/state precinct spreadsheet",
      detail:
        "Presidential county totals are aggregated from the official Minnesota Secretary of State 2024 general federal/state precinct results spreadsheet. The source workbook also includes precinct-level voter-stat fields and down-ballot columns for future review work.",
      sourceUrl: MN_2024_PRECINCT_SOURCE_URL,
      localFile: "data/mn-2024-general-federal-state-results-by-precinct-official.xlsx; data/mn-app-data.js",
      sourceLastModifiedUtc: MN_2024_SOURCE_TIMESTAMPS.precinctFederalStateLastModifiedUtc,
      sourceTimestampBasis: MN_2024_SOURCE_TIMESTAMPS.basis,
      status: MN_RESULTS.length ? "Loaded" : "Needs data",
    },
    wardDetail: {
      title: "Minnesota SOS precinct federal/state spreadsheet",
      detail:
        "The official spreadsheet contains precinct-level presidential and U.S. Senate columns. These rows are converted into the app's review graph schema for vote-share and President-vs-Senate same-party comparison.",
      sourceUrl: MN_2024_PRECINCT_SOURCE_URL,
      localFile: "data/mn-2024-general-federal-state-results-by-precinct-official.xlsx; data/mn-app-data.js",
      sourceLastModifiedUtc: MN_2024_SOURCE_TIMESTAMPS.precinctFederalStateLastModifiedUtc,
      sourceTimestampBasis: MN_2024_SOURCE_TIMESTAMPS.basis,
      status: MN_REVIEW_CHARTS ? "Loaded" : "Needs data",
    },
    turnout: {
      title: "Minnesota SOS precinct voter-stat fields",
      detail:
        "The official spreadsheet includes REG7AM, EDR, SIGNATURES, AB_MB, and TOTVOTING fields. Minnesota turnout rows use TOTVOTING divided by REG7AM plus EDR.",
      sourceUrl: MN_2024_PRECINCT_SOURCE_URL,
      localFile: "data/mn-2024-general-federal-state-results-by-precinct-official.xlsx; data/mn-app-data.js",
      sourceLastModifiedUtc: MN_2024_SOURCE_TIMESTAMPS.precinctFederalStateLastModifiedUtc,
      sourceTimestampBasis: MN_2024_SOURCE_TIMESTAMPS.basis,
      status: MN_TURNOUT_DATA?.rows?.length ? "Loaded" : "Needs data",
    },
  },
};
let ACTIVE_ETA_ANALYSIS = ETA_ANALYSIS;
let WARD_CHARTS = window.ETA_WARD_CHARTS;

const APP_STATES = {
  WI: {
    code: "WI",
    name: "Wisconsin",
    electionYear: 2024,
    office: "President",
    authority: "Wisconsin Elections Commission",
    countyLabel: "County",
    expectedCountyCount: 72,
    exportsSlug: "wisconsin-2024",
    capabilities: {
      sourcePlanner: true,
      certifiedResults: true,
      map: true,
      reviewGraphs: true,
      turnout: true,
      historicalBaseline: true,
    },
    resultRows: WI_RESULTS,
    candidateLabels: WI_CANDIDATE_LABELS,
    countyGeometry: WI_COUNTIES_GEOJSON,
    turnoutData: WI_TURNOUT_DATA,
    turnoutPolicy: TURNOUT_SOURCE_POLICY,
    etaAnalysis: ETA_ANALYSIS,
    wardCharts: window.ETA_WARD_CHARTS,
    historicalBaseline: WI_HISTORICAL_BASELINE,
    historicalPrimarySeriesIds: HISTORICAL_PRIMARY_SERIES_IDS,
    historicalSummary:
      "The multi-year comparison rows come from Wisconsin LTSB harmonized ward layers. Native official WEC 2024 reporting-unit rows remain available as a separate selectable series.",
    sourcePlan: STATE_SOURCE_PLANS.WI,
    sourceInventory: SOURCE_INVENTORY,
    checkedNotUsable: CHECKED_NOT_USABLE,
    reviewRowLabel: "WEC ward row",
    reviewRowLabelPlural: "WEC ward rows",
    reviewGraphTitlePrefix: "WEC ward",
    mapLoadingText: "Loading local Wisconsin county boundaries...",
    noGeometryText: "No local county geometry is loaded for this state yet; showing the county tile fallback.",
  },
  MN: {
    code: "MN",
    name: "Minnesota",
    electionYear: 2024,
    office: "President",
    authority: "Minnesota Secretary of State",
    countyLabel: "County",
    expectedCountyCount: 87,
    exportsSlug: "minnesota-2024",
    capabilities: {
      sourcePlanner: true,
      certifiedResults: true,
      map: true,
      reviewGraphs: true,
      turnout: true,
      historicalBaseline: true,
    },
    resultRows: MN_RESULTS,
    candidateLabels: MN_CANDIDATE_LABELS,
    countyGeometry: MN_COUNTIES_GEOJSON,
    turnoutData: MN_TURNOUT_DATA,
    turnoutPolicy: MN_TURNOUT_SOURCE_POLICY,
    etaAnalysis: MN_ETA_ANALYSIS,
    wardCharts: MN_REVIEW_CHARTS,
    historicalBaseline: MN_HISTORICAL_BASELINE,
    historicalPrimarySeriesIds: MN_HISTORICAL_PRIMARY_SERIES_IDS,
    historicalSummary:
      "Native official Minnesota Secretary of State county rows are shown for each election year.",
    sourcePlan: STATE_SOURCE_PLANS.MN,
    sourceInventory: MN_SOURCE_INVENTORY,
    checkedNotUsable: MN_CHECKED_NOT_USABLE,
    reviewRowLabel: "Minnesota SOS precinct row",
    reviewRowLabelPlural: "Minnesota SOS precinct rows",
    reviewGraphTitlePrefix: "Minnesota SOS precinct",
    mapLoadingText: "Loading local Minnesota county boundaries...",
    noGeometryText: "Minnesota county geometry is not loaded yet; showing the county tile fallback.",
  },
};

function configuredStateGlobalsReady(entry) {
  const hasData = Boolean(entry.appDataGlobal && window[entry.appDataGlobal]);
  return hasData;
}

function loadScriptOnce(src) {
  if (!src || document.querySelector(`script[src="${src}"], script[src="./${src}"]`)) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Unable to load configured state script: ${src}`));
    document.body.append(script);
  });
}

function loadConfiguredStateScripts() {
  return Promise.resolve();
}

function capabilityReady(declared, ready) {
  if (declared === false) {
    return false;
  }
  return Boolean(ready);
}

function configuredSourcePlan(entry, payload) {
  return {
    code: entry.code,
    state: entry.name,
    electionYear: entry.electionYear,
    office: entry.office,
    stateAuthority: entry.authority,
    countyLabel: entry.countyLabel || "County",
    exportsSlug: entry.exportsSlug,
    resultRows: payload.presidentCountyResults || [],
    ...entry.sourcePlan,
  };
}

function configuredStateFromRegistry(entry) {
  if (!configuredStateGlobalsReady(entry)) {
    return null;
  }
  const payload = window[entry.appDataGlobal];
  const geometry = entry.geometryGlobal ? window[entry.geometryGlobal] : null;
  const resultRows = payload.presidentCountyResults || [];
  const reviewCharts = payload.reviewCharts || null;
  const historicalBaseline = payload.historicalBaseline || null;
  const turnoutData = payload.turnoutData || { metadata: {}, rows: [] };
  const historicalPrimarySeriesIds = historicalBaseline?.series?.map((series) => series.id) || [];
  for (const series of historicalBaseline?.series || []) {
    HISTORICAL_SERIES_LABELS[series.id] ||= `${series.electionYear} ${entry.name} ${series.sourceLevel || "official"} rows`;
  }
  return {
    code: entry.code,
    name: entry.name,
    electionYear: entry.electionYear,
    office: entry.office,
    authority: entry.authority,
    countyLabel: entry.countyLabel || "County",
    expectedCountyCount: entry.expectedCountyCount || resultRows.length,
    exportsSlug: entry.exportsSlug,
    capabilities: {
      sourcePlanner: Boolean(entry.sourcePlan),
      certifiedResults: capabilityReady(entry.capabilities?.certifiedResults, resultRows.length),
      map: capabilityReady(entry.capabilities?.map, geometry || (entry.geometryFile && entry.geometryGlobal)),
      reviewGraphs: capabilityReady(entry.capabilities?.reviewGraphs, reviewCharts),
      turnout: capabilityReady(entry.capabilities?.turnout, turnoutData?.rows?.length),
      historicalBaseline: capabilityReady(entry.capabilities?.historicalBaseline, historicalBaseline?.series?.length),
    },
    resultRows,
    candidateLabels: payload.candidateLabels || [],
    countyGeometry: geometry,
    geometryFile: entry.geometryFile,
    geometryGlobal: entry.geometryGlobal,
    turnoutData,
    turnoutPolicy: entry.turnoutPolicy || {},
    etaAnalysis: payload.etaAnalysis || null,
    wardCharts: reviewCharts,
    historicalBaseline,
    historicalPrimarySeriesIds,
    historicalSummary: entry.historicalSummary,
    sourcePlan: configuredSourcePlan(entry, payload),
    sourceInventory: entry.sourceInventory || [],
    checkedNotUsable: entry.checkedNotUsable || [],
    reviewRowLabel: entry.reviewRowLabel,
    reviewRowLabelPlural: entry.reviewRowLabelPlural,
    reviewGraphTitlePrefix: entry.reviewGraphTitlePrefix,
    mapLoadingText: entry.mapLoadingText,
    noGeometryText: entry.noGeometryText,
  };
}

function registerConfiguredStates() {
  for (const entry of STATE_APP_REGISTRY) {
    const state = configuredStateFromRegistry(entry);
    if (state) {
      APP_STATES[state.code] = state;
    }
  }
}

async function ensureConfiguredStateLoaded(code) {
  const normalized = String(code || "").trim().toUpperCase();
  if (APP_STATES[normalized]) {
    return APP_STATES[normalized];
  }
  const entry = STATE_REGISTRY_BY_CODE.get(normalized);
  if (!entry?.appDataFile) {
    return null;
  }
  await loadScriptOnce(entry.appDataFile);
  const state = configuredStateFromRegistry(entry);
  if (state) {
    APP_STATES[state.code] = state;
  }
  return state;
}

const DEFAULT_REVIEW_POLICY = {
  minWardRows: 10,
  voteShareCorrelationThreshold: ETA_ANALYSIS.voteShare.threshold,
  downBallotAverageThresholdPct: 2,
  outlierThresholdPct: ETA_ANALYSIS.downBallot.outlierThresholdPct,
  minCandidateVotes: ETA_ANALYSIS.downBallot.minCandidateVotes,
};

const COUNTY_REVIEW_POLICY = { ...DEFAULT_REVIEW_POLICY };

const AUDIT_DISTRIBUTION_NOTES = {
  concentrated: "Yellow units are grouped together for an illustrative concentrated-area scenario. The grid is not a geographic map.",
  spread: "Yellow units are spaced across the modeled area. Under this simplified uniform sample, the exact miss probability depends on the number of affected units, not their spacing.",
  highVolume: "Concept only: yellow units represent hypothetical targeting of higher-volume locations. This static model does not contain WEC's exact reporting-unit volume metadata, so it cannot identify real high-volume audit units or calculate a volume-specific WEC detection rate.",
};

const AUDIT_DISTRIBUTION_LABELS = {
  concentrated: "concentrated-area",
  spread: "statewide-spread",
  highVolume: "high-volume-targeting concept",
};

const AUDIT_SIMULATOR_PRESETS = {
  statewide2024: {
    areaUnits: 3730,
    sampleUnits: 373,
    affectedUnits: 30,
    ballotsPerUnit: 877,
    candidateShare: 50,
    shiftPerUnit: 100,
    note: "Statewide 2024 WEC-reported configuration. WEC selected 373 reporting units under its adopted 10% rule; 12 selected no-voter units were excused. The displayed 3,730-unit statewide denominator and 877-ballot average are derived approximations. Affected units and shifted votes remain hypothetical assumptions.",
  },
  largest: {
    areaUnits: 100,
    sampleUnits: 4,
    affectedUnits: 8,
    ballotsPerUnit: 800,
    candidateShare: 50,
    shiftPerUnit: 100,
    note: "Illustrative largest-municipality tier. The adopted procedures allow Milwaukee and Madison to have up to four reporting units selected. This does not reconstruct either city's actual audit sample.",
  },
  next20: {
    areaUnits: 60,
    sampleUnits: 3,
    affectedUnits: 6,
    ballotsPerUnit: 800,
    candidateShare: 50,
    shiftPerUnit: 100,
    note: "Illustrative next-20-largest municipality tier. The adopted procedures allow up to three reporting units to be selected. This is not a reconstruction of any municipality's actual audit sample.",
  },
  other: {
    areaUnits: 20,
    sampleUnits: 1,
    affectedUnits: 3,
    ballotsPerUnit: 800,
    candidateShare: 50,
    shiftPerUnit: 100,
    note: "Illustrative other-municipality tier. The adopted procedures allow up to one reporting unit to be selected. This is not a reconstruction of any municipality's actual audit sample.",
  },
};

let byCounty = new Map(RESULTS.map((row) => [normalizeCounty(row.county), row]));
const countyReviewCache = new Map();
let stateTotals = calculateStateTotals(RESULTS);
let STATEWIDE_2024_PRESIDENTIAL_MARGIN = Math.abs(stateTotals.trump - stateTotals.harris);
let MIN_SWITCHES_TO_MOVE_STATEWIDE_MARGIN = Math.floor(STATEWIDE_2024_PRESIDENTIAL_MARGIN / 2) + 1;

let collected = [];
let map;
let geoLayer;
let colorMode = "winner";
let auditTrialBatchSeed = 20241106;
let auditTrialRunToken = 0;
let selectedCounty = null;
let citySplitData = [];
let flaggedAreaSummaryRows = [];
let auditSimulationSeed = 17;

const els = {
  appStateSelect: document.querySelector("#appStateSelect"),
  trumpTotal: document.querySelector("#trumpTotal"),
  harrisTotal: document.querySelector("#harrisTotal"),
  stateMargin: document.querySelector("#stateMargin"),
  countyCount: document.querySelector("#countyCount"),
  collectBtn: document.querySelector("#collectBtn"),
  mapBtn: document.querySelector("#mapBtn"),
  exportBtn: document.querySelector("#exportBtn"),
  coverageCsvBtn: document.querySelector("#coverageCsvBtn"),
  sourceCsvBtn: document.querySelector("#sourceCsvBtn"),
  darkModeToggle: document.querySelector("#darkModeToggle"),
  appTabs: document.querySelectorAll("[data-app-tab]"),
  tabPanels: document.querySelectorAll(".tab-panel"),
  openTabButtons: document.querySelectorAll("[data-open-tab]"),
  reviewScopeSelect: document.querySelector("#reviewScopeSelect"),
  exportReviewBtn: document.querySelector("#exportReviewBtn"),
  copyReviewLinkBtn: document.querySelector("#copyReviewLinkBtn"),
  copyReviewLinkStatus: document.querySelector("#copyReviewLinkStatus"),
  exportFlaggedAreasBtn: document.querySelector("#exportFlaggedAreasBtn"),
  flaggedAreasSummary: document.querySelector("#flaggedAreasSummary"),
  flaggedAreaRows: document.querySelector("#flaggedAreaRows"),
  flaggedSearchInput: document.querySelector("#flaggedSearchInput"),
  flaggedTypeFilter: document.querySelector("#flaggedTypeFilter"),
  flaggedReasonFilter: document.querySelector("#flaggedReasonFilter"),
  flaggedMinRowsInput: document.querySelector("#flaggedMinRowsInput"),
  flaggedSortSelect: document.querySelector("#flaggedSortSelect"),
  minWardRowsInput: document.querySelector("#minWardRowsInput"),
  voteShareThresholdInput: document.querySelector("#voteShareThresholdInput"),
  dropoffThresholdInput: document.querySelector("#dropoffThresholdInput"),
  outlierThresholdInput: document.querySelector("#outlierThresholdInput"),
  minCandidateVotesInput: document.querySelector("#minCandidateVotesInput"),
  resetSensitivityBtn: document.querySelector("#resetSensitivityBtn"),
  reviewSummaryGrid: document.querySelector("#reviewSummaryGrid"),
  recordsRequestText: document.querySelector("#recordsRequestText"),
  reviewWardRows: document.querySelector("#reviewWardRows"),
  search: document.querySelector("#countySearch"),
  progressBar: document.querySelector("#progressBar"),
  statusText: document.querySelector("#statusText"),
  collectorLog: document.querySelector("#collectorLog"),
  etaTests: document.querySelector("#etaTests"),
  coverageSummary: document.querySelector("#coverageSummary"),
  coverageList: document.querySelector("#coverageList"),
  dataVersionSummary: document.querySelector("#dataVersionSummary"),
  confidenceBadges: document.querySelector("#confidenceBadges"),
  coverageTableSummary: document.querySelector("#coverageTableSummary"),
  coverageTableRows: document.querySelector("#coverageTableRows"),
  checkedNotUsableList: document.querySelector("#checkedNotUsableList"),
  sourceStateSelect: document.querySelector("#sourceStateSelect"),
  sourceCountySearch: document.querySelector("#sourceCountySearch"),
  sourceStatusFilter: document.querySelector("#sourceStatusFilter"),
  sourcePlanCsvBtn: document.querySelector("#sourcePlanCsvBtn"),
  sourceStateTitle: document.querySelector("#sourceStateTitle"),
  sourceStateSummary: document.querySelector("#sourceStateSummary"),
  sourcePlanBadges: document.querySelector("#sourcePlanBadges"),
  sourceCertifiedTitle: document.querySelector("#sourceCertifiedTitle"),
  sourceCertifiedDetail: document.querySelector("#sourceCertifiedDetail"),
  sourceCertifiedLinks: document.querySelector("#sourceCertifiedLinks"),
  sourceWardTitle: document.querySelector("#sourceWardTitle"),
  sourceWardDetail: document.querySelector("#sourceWardDetail"),
  sourceWardLinks: document.querySelector("#sourceWardLinks"),
  sourceTurnoutTitle: document.querySelector("#sourceTurnoutTitle"),
  sourceTurnoutDetail: document.querySelector("#sourceTurnoutDetail"),
  sourceTurnoutLinks: document.querySelector("#sourceTurnoutLinks"),
  sourceCountySummary: document.querySelector("#sourceCountySummary"),
  sourceCountyRows: document.querySelector("#sourceCountyRows"),
  reviewFlagSummary: document.querySelector("#reviewFlagSummary"),
  voteShareGraphInfo: document.querySelector("#voteShareGraphInfo"),
  downBallotGraphInfo: document.querySelector("#downBallotGraphInfo"),
  voteShareGraph: document.querySelector("#voteShareGraph"),
  downBallotGraph: document.querySelector("#downBallotGraph"),
  turnoutGraph: document.querySelector("#turnoutGraph"),
  turnoutGraphNote: document.querySelector("#turnoutGraphNote"),
  citySplitSelect: document.querySelector("#citySplitSelect"),
  citySplitSummary: document.querySelector("#citySplitSummary"),
  cityVoteShareTitle: document.querySelector("#cityVoteShareTitle"),
  countyRestVoteShareTitle: document.querySelector("#countyRestVoteShareTitle"),
  cityDownBallotTitle: document.querySelector("#cityDownBallotTitle"),
  countyRestDownBallotTitle: document.querySelector("#countyRestDownBallotTitle"),
  cityVoteShareGraph: document.querySelector("#cityVoteShareGraph"),
  countyRestVoteShareGraph: document.querySelector("#countyRestVoteShareGraph"),
  cityDownBallotGraph: document.querySelector("#cityDownBallotGraph"),
  countyRestDownBallotGraph: document.querySelector("#countyRestDownBallotGraph"),
  countyRows: document.querySelector("#countyRows"),
  mapTitle: document.querySelector("#mapTitle"),
  map: document.querySelector("#map"),
  tileFallback: document.querySelector("#tileFallback"),
  selectedCounty: document.querySelector("#selectedCounty"),
  selectedWinner: document.querySelector("#selectedWinner"),
  selectedMargin: document.querySelector("#selectedMargin"),
  selectedTotal: document.querySelector("#selectedTotal"),
  breakdownTitle: document.querySelector("#breakdownTitle"),
  breakdownTotal: document.querySelector("#breakdownTotal"),
  candidateBreakdown: document.querySelector("#candidateBreakdown"),
  historicalCountySelect: document.querySelector("#historicalCountySelect"),
  historicalSeriesSelect: document.querySelector("#historicalSeriesSelect"),
  historicalScopeTitle: document.querySelector("#historicalScopeTitle"),
  historicalSummary: document.querySelector("#historicalSummary"),
  historicalTableRows: document.querySelector("#historicalTableRows"),
  historicalTrendGraph: document.querySelector("#historicalTrendGraph"),
  historicalScatterGraph: document.querySelector("#historicalScatterGraph"),
  historicalDistributionGraph: document.querySelector("#historicalDistributionGraph"),
  auditPreset: document.querySelector("#auditPreset"),
  auditPresetNote: document.querySelector("#auditPresetNote"),
  auditAreaUnits: document.querySelector("#auditAreaUnits"),
  auditAreaUnitsValue: document.querySelector("#auditAreaUnitsValue"),
  auditSampleUnits: document.querySelector("#auditSampleUnits"),
  auditSampleUnitsValue: document.querySelector("#auditSampleUnitsValue"),
  auditAffectedUnits: document.querySelector("#auditAffectedUnits"),
  auditAffectedUnitsValue: document.querySelector("#auditAffectedUnitsValue"),
  auditAffectedDistribution: document.querySelector("#auditAffectedDistribution"),
  auditDistributionNote: document.querySelector("#auditDistributionNote"),
  auditBallotsPerUnit: document.querySelector("#auditBallotsPerUnit"),
  auditBallotsPerUnitValue: document.querySelector("#auditBallotsPerUnitValue"),
  auditCandidateShare: document.querySelector("#auditCandidateShare"),
  auditCandidateShareValue: document.querySelector("#auditCandidateShareValue"),
  auditShiftPerUnit: document.querySelector("#auditShiftPerUnit"),
  auditShiftValue: document.querySelector("#auditShiftValue"),
  auditMinimumMarginMode: document.querySelector("#auditMinimumMarginMode"),
  auditMinimumMarginNote: document.querySelector("#auditMinimumMarginNote"),
  auditRerollBtn: document.querySelector("#auditRerollBtn"),
  auditRunTrialsBtn: document.querySelector("#auditRunTrialsBtn"),
  auditMissProbability: document.querySelector("#auditMissProbability"),
  auditTouchProbability: document.querySelector("#auditTouchProbability"),
  auditShiftedVotes: document.querySelector("#auditShiftedVotes"),
  auditDrawResult: document.querySelector("#auditDrawResult"),
  auditTrialMissRate: document.querySelector("#auditTrialMissRate"),
  auditTrialProgressWrap: document.querySelector("#auditTrialProgressWrap"),
  auditTrialProgress: document.querySelector("#auditTrialProgress"),
  auditTrialProgressText: document.querySelector("#auditTrialProgressText"),
  auditTrialSummary: document.querySelector("#auditTrialSummary"),
  auditUnitGrid: document.querySelector("#auditUnitGrid"),
  auditScenarioSummary: document.querySelector("#auditScenarioSummary"),
  auditVoteComparison: document.querySelector("#auditVoteComparison"),
};

async function init() {
  initializeThemeToggle();
  await initializeStateSelectors();
  organizeWorkspacePanels();
  renderSummary();
  renderEtaTests();
  renderCoverageTracker();
  renderConfidenceSummary();
  renderCoverageTable();
  renderCheckedNotUsable();
  renderSourcePlanner();
  renderReviewSourceCopy();
  renderEtaGraphs();
  renderCitySplitOptions();
  setReviewControlValues();
  renderFlaggedAreasSummary();
  renderReviewDrilldown();
  renderCandidateBreakdown();
  renderHistoricalComparison();
  applyAuditPreset("statewide2024");
  renderTable(RESULTS);
  wireControls();
  setAppTab(initialTabName(), { updateHash: false });
  initMap();
  applyInitialReviewRoute();
  if (!window.__STATIC_UI_VALIDATION__) {
    collectCounties({ quick: true });
  }
}

function wireControls() {
  els.appStateSelect.addEventListener("change", () => {
    switchActiveState(els.appStateSelect.value);
  });
  els.collectBtn.addEventListener("click", () => collectCounties({ quick: false }));
  els.mapBtn.addEventListener("click", loadCountyBoundaries);
  els.exportBtn.addEventListener("click", exportCsv);
  els.coverageCsvBtn.addEventListener("click", exportCoverageCsv);
  els.sourceCsvBtn.addEventListener("click", exportSourceCsv);
  els.sourceStateSelect.addEventListener("change", () => {
    switchActiveState(els.sourceStateSelect.value);
  });
  els.sourceCountySearch.addEventListener("input", renderSourceCountyRows);
  els.sourceStatusFilter.addEventListener("change", renderSourceCountyRows);
  els.sourcePlanCsvBtn.addEventListener("click", exportSourcePlanCsv);
  els.darkModeToggle.addEventListener("change", () => setTheme(els.darkModeToggle.checked ? "dark" : "light"));
  els.appTabs.forEach((button) => {
    button.addEventListener("click", () => setAppTab(button.dataset.appTab));
  });
  els.openTabButtons.forEach((button) => {
    button.addEventListener("click", () => setAppTab(button.dataset.openTab, { scrollTop: true }));
  });
  els.reviewScopeSelect.addEventListener("change", () => {
    renderReviewDrilldown();
    updateReviewRoute();
  });
  els.exportReviewBtn.addEventListener("click", exportCurrentReviewCsv);
  els.copyReviewLinkBtn.addEventListener("click", copyReviewLink);
  els.exportFlaggedAreasBtn.addEventListener("click", exportFlaggedAreasCsv);
  [
    els.flaggedSearchInput,
    els.flaggedTypeFilter,
    els.flaggedReasonFilter,
    els.flaggedMinRowsInput,
    els.flaggedSortSelect,
  ].forEach((input) => input.addEventListener("input", renderFlaggedAreasSummary));
  [
    els.minWardRowsInput,
    els.voteShareThresholdInput,
    els.dropoffThresholdInput,
    els.outlierThresholdInput,
    els.minCandidateVotesInput,
  ].forEach((input) => input.addEventListener("input", updateReviewPolicyFromControls));
  els.resetSensitivityBtn.addEventListener("click", resetReviewPolicy);
  els.search.addEventListener("input", () => {
    const query = els.search.value.trim().toLowerCase();
    const rows = RESULTS.filter((row) => row.county.toLowerCase().includes(query));
    renderTable(rows);
    renderTiles(rows);
  });

  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".mode-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      colorMode = button.dataset.mode;
      els.mapTitle.textContent =
        colorMode === "winner"
          ? "County winner shading"
          : colorMode === "margin"
            ? "Margin intensity shading"
            : "Total vote volume shading";
      refreshMapStyles();
      renderTiles(filteredRows());
    });
  });

  document.querySelectorAll(".graph-download").forEach((button) => {
    button.addEventListener("click", () => downloadGraph(button.dataset.graph));
  });

  els.citySplitSelect.addEventListener("change", () => {
    renderCitySplitGraphs();
    if (["city", "rest"].includes(els.reviewScopeSelect.value)) {
      renderReviewDrilldown();
      updateReviewRoute();
    }
  });
  els.historicalCountySelect.addEventListener("change", renderHistoricalComparison);
  els.historicalSeriesSelect.addEventListener("change", renderHistoricalComparison);
  els.auditPreset.addEventListener("change", () => applyAuditPreset(els.auditPreset.value));
  [els.auditAreaUnits, els.auditSampleUnits, els.auditAffectedUnits, els.auditBallotsPerUnit, els.auditCandidateShare, els.auditShiftPerUnit].forEach((input) => {
    input.addEventListener("input", () => {
      resetAuditTrials();
      renderAuditSimulator();
    });
  });
  els.auditAffectedDistribution.addEventListener("change", () => {
    resetAuditTrials();
    renderAuditSimulator();
  });
  els.auditMinimumMarginMode.addEventListener("change", () => {
    resetAuditTrials();
    renderAuditSimulator();
  });
  els.auditRerollBtn.addEventListener("click", () => {
    auditSimulationSeed += 41;
    renderAuditSimulator();
  });
  els.auditRunTrialsBtn.addEventListener("click", runAuditTrials);
}

function organizeWorkspacePanels() {
  const reviewPanel = document.querySelector("#reviewPanel");
  const dataPanel = document.querySelector("#dataPanel");
  [
    ".flagged-areas-panel",
    ".review-drilldown",
    ".eta-graphs",
    ".city-split-panel",
  ].forEach((selector) => reviewPanel.append(document.querySelector(selector)));
  dataPanel.insertBefore(document.querySelector(".coverage-table-panel"), dataPanel.querySelector(".source-note"));
}

function setAppTab(tabName, { scrollTop = false, updateHash = true } = {}) {
  els.appTabs.forEach((button) => {
    const isActive = button.dataset.appTab === tabName;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  els.tabPanels.forEach((panel) => {
    const isActive = panel.id === `${tabName}Panel`;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });

  if (tabName === "dashboard" && map) {
    setTimeout(() => map.invalidateSize(), 0);
  }
  if (updateHash && window.history?.replaceState) {
    const currentRoute = routeState();
    const params = tabName === "review" && currentRoute.tabName === "review"
      ? reviewRouteParamsFromCurrentRoute(currentRoute)
      : new URLSearchParams();
    replaceRoute(tabName, params);
  }
  if (scrollTop) {
    document.querySelector(".map-stage")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function initialTabName() {
  return routeState().tabName;
}

function routeState() {
  const [hashTab = "", query = ""] = window.location.hash.replace(/^#/, "").split("?");
  const validTabs = ["dashboard", "review", "history", "data", "sources", "methodology", "audit", "about"];
  const pageParams = new URLSearchParams(window.location.search || "");
  const hashParams = new URLSearchParams(query);
  const params = new URLSearchParams(pageParams);
  for (const [key, value] of hashParams.entries()) {
    params.set(key, value);
  }
  return {
    tabName: validTabs.includes(hashTab) ? hashTab : "dashboard",
    query,
    params,
    hashParams,
  };
}

function normalizedStateCode(code) {
  const normalized = String(code || "").trim().toUpperCase();
  return APP_STATES[normalized] || STATE_REGISTRY_BY_CODE.has(normalized) ? normalized : "";
}

function initialStateCode() {
  return normalizedStateCode(routeState().params.get("state")) || "WI";
}

function setRouteStateParam(params) {
  const code = normalizedStateCode(activeStateCode);
  if (code && code !== "WI") {
    params.set("state", code);
  } else {
    params.delete("state");
  }
}

function routeHash(tabName, params = new URLSearchParams()) {
  const query = params.toString();
  return `#${tabName}${query ? `?${query}` : ""}`;
}

function replaceRoute(tabName = activeTabName(), params = new URLSearchParams()) {
  if (!window.history?.replaceState) {
    return;
  }
  setRouteStateParam(params);
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.delete("state");
  nextUrl.hash = routeHash(tabName, params);
  window.history.replaceState(null, "", nextUrl.toString());
}

function reviewRouteParamsFromCurrentRoute(route = routeState()) {
  const params = new URLSearchParams();
  for (const key of ["scope", "county", "city"]) {
    const value = route.params.get(key);
    if (value) {
      params.set(key, value);
    }
  }
  return params;
}

function activeTabName() {
  return Array.from(els.appTabs).find((button) => button.classList.contains("active"))?.dataset.appTab || "dashboard";
}

function stateSelectorOptions() {
  const states = [
    ...Object.values(APP_STATES),
    ...STATE_APP_REGISTRY.filter((entry) => !APP_STATES[entry.code]).map((entry) => ({
      code: entry.code,
      name: entry.name,
      electionYear: entry.electionYear,
    })),
  ].sort((a, b) => a.code.localeCompare(b.code));
  return states
    .map((state) => `<option value="${escapeAttr(state.code)}">${escapeText(state.name)} ${state.electionYear}</option>`)
    .join("");
}

async function initializeStateSelectors() {
  const options = stateSelectorOptions();
  els.appStateSelect.innerHTML = options;
  els.sourceStateSelect.innerHTML = options;
  const initialCode = initialStateCode();
  await ensureConfiguredStateLoaded(initialCode);
  setActiveState(initialCode, { updateControls: true });
}

async function switchActiveState(code, { updateRoute = true } = {}) {
  await ensureConfiguredStateLoaded(code);
  if (!APP_STATES[code] || code === activeStateCode) {
    setActiveState(activeStateCode, { updateControls: true });
    renderSourcePlanner();
    if (updateRoute) {
      replaceRoute(activeTabName(), activeTabName() === "review" ? reviewRouteParamsFromCurrentRoute() : new URLSearchParams());
    }
    return;
  }

  setActiveState(code, { updateControls: true });
  selectedCounty = null;
  collected = [];
  citySplitData = [];
  flaggedAreaSummaryRows = [];
  auditTrialRunToken += 1;
  renderSummary();
  renderEtaTests();
  renderCoverageTracker();
  renderConfidenceSummary();
  renderCoverageTable();
  renderCheckedNotUsable();
  renderSourcePlanner();
  renderReviewSourceCopy();
  renderEtaGraphs();
  renderCitySplitOptions();
  renderFlaggedAreasSummary();
  renderReviewDrilldown();
  renderCandidateBreakdown();
  renderHistoricalComparison();
  renderTable(RESULTS);
  renderTiles(RESULTS);
  loadCountyBoundaries();
  collectCounties({ quick: true });
  if (updateRoute) {
    replaceRoute(activeTabName(), activeTabName() === "review" ? reviewRouteParamsFromCurrentRoute() : new URLSearchParams());
  }
}

function setActiveState(code, { updateControls = false } = {}) {
  const state = APP_STATES[code] || APP_STATES.WI;
  activeStateCode = state.code;
  RESULTS = state.resultRows || [];
  CANDIDATE_LABELS = state.candidateLabels || [];
  LOCAL_COUNTIES_GEOJSON = state.countyGeometry || null;
  HISTORICAL_BASELINE = state.historicalBaseline || null;
  TURNOUT_DATA = state.turnoutData || { metadata: {}, rows: [] };
  ACTIVE_ETA_ANALYSIS = state.etaAnalysis || null;
  WARD_CHARTS = state.wardCharts || null;
  els.historicalCountySelect.innerHTML = "";
  els.historicalSeriesSelect.innerHTML = "";
  if (!HISTORICAL_BASELINE?.series?.length) {
    els.historicalTableRows.innerHTML = "";
    els.historicalScopeTitle.textContent = `${state.name} comparison`;
  }
  byCounty = new Map(RESULTS.map((row) => [normalizeCounty(row.county), row]));
  stateTotals = calculateStateTotals(RESULTS);
  STATEWIDE_2024_PRESIDENTIAL_MARGIN = Math.abs(stateTotals.trump - stateTotals.harris);
  MIN_SWITCHES_TO_MOVE_STATEWIDE_MARGIN = Math.floor(STATEWIDE_2024_PRESIDENTIAL_MARGIN / 2) + 1;
  countyReviewCache.clear();

  if (updateControls) {
    els.appStateSelect.value = state.code;
    els.sourceStateSelect.value = state.code;
  }
}

function activeStateConfig() {
  return APP_STATES[activeStateCode] || APP_STATES.WI;
}

function activeSourcePlan() {
  return activeStateConfig().sourcePlan;
}

function activeSourceInventory() {
  return activeStateConfig().sourceInventory || [];
}

function activeCheckedNotUsable() {
  return activeStateConfig().checkedNotUsable || [];
}

function activeTurnoutPolicy() {
  return activeStateConfig().turnoutPolicy || TURNOUT_SOURCE_POLICY;
}

function activeReviewRowLabel({ plural = false } = {}) {
  const state = activeStateConfig();
  return plural
    ? state.reviewRowLabelPlural || `${state.countyLabel.toLowerCase()} local result rows`
    : state.reviewRowLabel || `${state.countyLabel.toLowerCase()} local result row`;
}

function activeReviewGraphTitlePrefix() {
  return activeStateConfig().reviewGraphTitlePrefix || activeReviewRowLabel();
}

function renderReviewSourceCopy() {
  const reviewSource = `Uses official ${activeReviewGraphTitlePrefix()} vote totals.`;
  if (els.voteShareGraphInfo) {
    const text = `${reviewSource} The calculation is accurate for the data shown, but a pattern or flagged result means review further, not proof by itself.`;
    els.voteShareGraphInfo.setAttribute("aria-label", `Vote share graph note: ${text}`);
    els.voteShareGraphInfo.setAttribute("title", text);
  }
  if (els.downBallotGraphInfo) {
    const text = `${reviewSource} The calculation is accurate for the data shown, but differences can come from normal split-ticket voting.`;
    els.downBallotGraphInfo.setAttribute("aria-label", `Down-ballot graph note: ${text}`);
    els.downBallotGraphInfo.setAttribute("title", text);
  }
}

function stateCapabilityLabel(capability) {
  const state = activeStateConfig();
  const labels = {
    map: state.capabilities?.map ? "Map ready" : "Map not ready",
    reviewGraphs: state.capabilities?.reviewGraphs ? "Review graphs ready" : "Review graphs need local detail",
    turnout: state.capabilities?.turnout ? "Turnout ready" : "Turnout not loaded",
    historicalBaseline: state.capabilities?.historicalBaseline ? "Historical baseline ready" : "Historical baseline not loaded",
  };
  return labels[capability] || capability;
}

function stateCapabilityTone(capability) {
  return activeStateConfig().capabilities?.[capability] ? "strong" : "missing";
}

function activeExportSlug() {
  return activeStateConfig().exportsSlug || `${activeStateCode.toLowerCase()}-${activeStateConfig().electionYear}`;
}

function calculateStateTotals(rows) {
  return rows.reduce(
    (acc, row) => {
      acc.trump += row.trump || 0;
      acc.harris += row.harris || 0;
      acc.other += row.other || 0;
      acc.total += row.total || 0;
      return acc;
    },
    { trump: 0, harris: 0, other: 0, total: 0 },
  );
}

function initializeThemeToggle() {
  els.darkModeToggle.checked = document.documentElement.dataset.theme === "dark";
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("wi-election-theme", theme);
  } catch {
    // The toggle still works when browser storage is unavailable.
  }
}

function applyInitialReviewRoute() {
  const route = routeState();
  if (route.tabName !== "review") {
    return;
  }

  const county = route.params.get("county");
  const scope = route.params.get("scope");
  if (!county || !["county", "city", "rest"].includes(scope)) {
    return;
  }

  selectCounty(county);
  if (scope === "city" || scope === "rest") {
    const city = route.params.get("city");
    const splitIndex = citySplitData.findIndex(
      (item) =>
        normalizeCounty(item.county) === normalizeCounty(county) &&
        (!city || item.city.toLowerCase() === city.toLowerCase()),
    );
    if (splitIndex >= 0) {
      els.citySplitSelect.value = String(splitIndex);
      renderCitySplitGraphs();
      els.reviewScopeSelect.value = scope;
    }
  } else {
    els.reviewScopeSelect.value = "county";
  }
  renderReviewDrilldown();
  updateReviewRoute();
}

function renderSummary() {
  const margin = stateTotals.trump - stateTotals.harris;
  const marginPct = (margin / stateTotals.total) * 100;
  els.trumpTotal.textContent = formatNumber(stateTotals.trump);
  els.harrisTotal.textContent = formatNumber(stateTotals.harris);
  els.stateMargin.textContent = `${margin > 0 ? "Trump +" : "Harris +"}${formatNumber(Math.abs(margin))} (${Math.abs(marginPct).toFixed(2)}%)`;
}

async function collectCounties({ quick }) {
  collected = [];
  els.collectBtn.disabled = true;
  els.collectorLog.innerHTML = "";
  updateProgress(0);

  const delay = quick ? 4 : 36;
  for (const [index, row] of RESULTS.entries()) {
    await sleep(delay);
    collected.push(row);
    if (!quick || index % 3 === 0 || index === RESULTS.length - 1) {
      addLog(`${row.county} County: ${winnerLabel(row)} by ${Math.abs(row.marginPct).toFixed(2)} points`);
    }
    updateProgress(collected.length);
  }

  els.statusText.textContent = `Collected ${RESULTS.length} county records from the certified county result table.`;
  els.collectBtn.disabled = false;
  renderTable(filteredRows());
  await loadCountyBoundaries();
}

function updateProgress(done) {
  const pct = (done / RESULTS.length) * 100;
  els.progressBar.style.width = `${pct}%`;
  els.countyCount.textContent = `${done} / ${RESULTS.length}`;
  if (done < RESULTS.length) {
    els.statusText.textContent = `Collecting county ${done + 1} of ${RESULTS.length}...`;
  }
}

function addLog(message) {
  const item = document.createElement("li");
  item.textContent = message;
  els.collectorLog.prepend(item);
  while (els.collectorLog.children.length > 9) {
    els.collectorLog.lastElementChild.remove();
  }
}

function initMap() {
  if (!window.L) {
    els.map.hidden = true;
    els.tileFallback.hidden = false;
    renderTiles(RESULTS);
    els.statusText.textContent = "Leaflet did not load, so the app is showing the county tile map.";
    return;
  }

  map = L.map("map", {
    attributionControl: false,
    zoomControl: true,
    scrollWheelZoom: true,
  }).setView([44.75, -89.85], 6);
}

async function loadCountyBoundaries() {
  if (!map) {
    renderTiles(filteredRows());
    return;
  }

  const state = activeStateConfig();
  els.statusText.textContent = state.mapLoadingText || `Loading local ${state.name} ${state.countyLabel.toLowerCase()} boundaries...`;
  if (!LOCAL_COUNTIES_GEOJSON && state.geometryFile && state.geometryGlobal) {
    try {
      await loadScriptOnce(state.geometryFile);
      state.countyGeometry = window[state.geometryGlobal] || null;
      LOCAL_COUNTIES_GEOJSON = state.countyGeometry;
    } catch (error) {
      console.warn(error);
    }
  }
  if (!LOCAL_COUNTIES_GEOJSON) {
    els.map.hidden = true;
    els.tileFallback.hidden = false;
    renderTiles(filteredRows());
    els.statusText.textContent = state.noGeometryText || "No local geometry is loaded for this state, so the tile map is active.";
    return;
  }
  try {
    drawGeoJson(LOCAL_COUNTIES_GEOJSON);
    els.map.hidden = false;
    els.tileFallback.hidden = true;
    els.statusText.textContent = "County boundaries loaded and joined to the 2024 results.";
  } catch (error) {
    console.warn(error);
    els.map.hidden = true;
    els.tileFallback.hidden = false;
    renderTiles(filteredRows());
    els.statusText.textContent =
      "Could not load local county boundaries, so the county tile map is active.";
  }
}

function drawGeoJson(geojson) {
  if (geoLayer) {
    geoLayer.remove();
  }

  geoLayer = L.geoJSON(geojson, {
    style: (feature) => {
      const row = resultForFeature(feature);
      return countyStyle(row);
    },
    onEachFeature: (feature, layer) => {
      const row = resultForFeature(feature);
      if (!row) {
        return;
      }
      layer.bindPopup(popupHtml(row), { className: "county-popup" });
      layer.on({
        click: () => selectCounty(row.county),
        mouseover: () => layer.setStyle({ weight: 3, color: "#1b222b" }),
        mouseout: () => geoLayer.resetStyle(layer),
      });
    },
  }).addTo(map);

  map.fitBounds(geoLayer.getBounds(), { padding: [14, 14] });
}

function refreshMapStyles() {
  if (geoLayer) {
    geoLayer.setStyle((feature) => countyStyle(resultForFeature(feature)));
  }
}

function resultForFeature(feature) {
  return byCounty.get(normalizeCounty(feature?.properties?.NAME));
}

function countyStyle(row) {
  return {
    color: "#ffffff",
    fillColor: row ? colorFor(row) : "#b7c0c9",
    fillOpacity: row ? 0.86 : 0.42,
    opacity: 1,
    weight: selectedCounty && row?.county === selectedCounty ? 3 : 1,
  };
}

function colorFor(row) {
  if (colorMode === "turnout") {
    const t = Math.min(1, Math.sqrt(row.total / Math.max(...RESULTS.map((item) => item.total))));
    return blend("#d8dee4", "#3f8068", t);
  }

  const winner = row.margin >= 0 ? "r" : "d";
  const base = winner === "r" ? ["#f4d1ce", "#a8302a"] : ["#d6e5f5", "#1458a8"];

  if (colorMode === "winner") {
    return winner === "r" ? "#c84c42" : "#3477bd";
  }

  const intensity = Math.min(1, Math.abs(row.marginPct) / 65);
  return blend(base[0], base[1], intensity);
}

function blend(start, end, amount) {
  const s = hexToRgb(start);
  const e = hexToRgb(end);
  const mixed = s.map((value, index) => Math.round(value + (e[index] - value) * amount));
  return `rgb(${mixed.join(", ")})`;
}

function hexToRgb(hex) {
  return [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16));
}

function renderTable(rows) {
  updateReviewFlagSummary(rows);
  els.countyRows.innerHTML = rows
    .map((row) => {
      const review = countyReviewSummary(row.county);
      return `
        <tr data-county="${row.county}" class="${selectedCounty === row.county ? "is-selected" : ""}">
          <td>${row.county}</td>
          <td class="review-cell">${review.flag ? `<span class="review-flag" title="${escapeAttr(review.title)}" aria-label="${escapeAttr(review.title)}">!</span>` : ""}</td>
          <td>${formatNumber(row.trump)} <span class="party-r">${row.trumpPct.toFixed(2)}%</span></td>
          <td>${formatNumber(row.harris)} <span class="party-d">${row.harrisPct.toFixed(2)}%</span></td>
          <td>${formatNumber(row.other)} (${row.otherPct.toFixed(2)}%)</td>
          <td>${winnerLabel(row)} +${Math.abs(row.marginPct).toFixed(2)}%</td>
          <td>${formatNumber(row.total)}</td>
        </tr>
      `;
    })
    .join("");

  els.countyRows.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => selectCounty(row.dataset.county));
  });
}

function updateReviewFlagSummary(rows) {
  const flagCount = rows.filter((row) => countyReviewSummary(row.county).flag).length;
  const countyWord = flagCount === 1 ? "county" : "counties";
  const scope = rows.length === RESULTS.length ? "statewide table" : "filtered table";
  els.reviewFlagSummary.innerHTML = `<i class="review-flag">!</i> ${formatNumber(flagCount)} ${countyWord} in this ${scope} have statistical review flags. Not proof of tampering. Hover over each icon for county-specific details.`;
}

function countyReviewSummary(county) {
  const key = normalizeCounty(county);
  if (countyReviewCache.has(key)) {
    return countyReviewCache.get(key);
  }

  const rows = WARD_CHARTS?.metadata?.rows?.filter((row) => normalizeCounty(row.county) === key) || [];
  const result = reviewSummaryForRows(`${county} County`, rows, "all");
  countyReviewCache.set(key, result);
  return result;
}

function reviewSummaryForRows(label, rows, mode = "all") {
  const rowLabel = mode === "voteShare" ? "vote-share graph" : mode === "downBallot" ? "down-ballot graph" : "review";
  const voteShareOnly = ACTIVE_ETA_ANALYSIS?.coverageMode === "voteShareOnly";
  if (rows.length < COUNTY_REVIEW_POLICY.minWardRows) {
    return {
      flag: false,
      title: `${label} has fewer than ${COUNTY_REVIEW_POLICY.minWardRows} ${activeReviewRowLabel({ plural: true })} in this analysis, so the app does not apply a ${rowLabel} flag.`,
      notes: `Not enough ${activeReviewRowLabel({ plural: true })} for ${rowLabel} flag`,
      reasons: [],
      metrics: {
        rowCount: rows.length,
        trumpCorrelation: 0,
        harrisCorrelation: 0,
        demAverageDropoff: 0,
        repAverageDropoff: 0,
        demOutliers: 0,
        repOutliers: 0,
        outlierTrigger: 0,
      },
    };
  }

  const trumpCorrelation = pearsonSafe(
    rows.map((row) => row.trump),
    rows.map((row) => row.trumpShare),
  );
  const harrisCorrelation = pearsonSafe(
    rows.map((row) => row.harris),
    rows.map((row) => row.harrisShare),
  );
  const demAverageDropoff = average(rows.map((row) => row.demDropoff));
  const repAverageDropoff = average(rows.map((row) => row.repDropoff));
  const demOutliers = rows.filter((row) => row.harris >= COUNTY_REVIEW_POLICY.minCandidateVotes && Math.abs(row.demDropoff) >= COUNTY_REVIEW_POLICY.outlierThresholdPct).length;
  const repOutliers = rows.filter((row) => row.trump >= COUNTY_REVIEW_POLICY.minCandidateVotes && Math.abs(row.repDropoff) >= COUNTY_REVIEW_POLICY.outlierThresholdPct).length;
  const outlierTrigger = Math.max(3, Math.ceil(rows.length * 0.05));

  const reasons = [];
  if (
    (mode === "all" || mode === "voteShare") &&
    (Math.abs(trumpCorrelation) >= COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold ||
      Math.abs(harrisCorrelation) >= COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold)
  ) {
    reasons.push({
      type: "Vote-share pattern",
      summary: `vote-share correlation crossed threshold: Trump r=${trumpCorrelation.toFixed(3)}, Harris r=${harrisCorrelation.toFixed(3)}`,
      plain:
        "Bigger ward vote totals move with candidate vote share strongly enough to pass the review threshold. This is the vote-share by vote-count scatterplot question: do larger reporting units lean differently than smaller ones?",
    });
  }
  if (
    !voteShareOnly &&
    (mode === "all" || mode === "downBallot") &&
    (Math.abs(demAverageDropoff) >= COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct ||
      Math.abs(repAverageDropoff) >= COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct)
  ) {
    reasons.push({
      type: "Average down-ballot difference",
      summary: `average President-vs-Senate drop-off crossed threshold: DEM ${demAverageDropoff.toFixed(2)}%, REP ${repAverageDropoff.toFixed(2)}%`,
      plain:
        "The average gap between presidential votes and same-party U.S. Senate votes is large enough to review. Split-ticket voting can explain some gap; this flag says the pattern deserves supporting records.",
    });
  }
  if (!voteShareOnly && (mode === "all" || mode === "downBallot") && demOutliers + repOutliers >= outlierTrigger) {
    reasons.push({
      type: "Down-ballot outliers",
      summary: `drop-off outlier count crossed threshold: DEM ${demOutliers}, REP ${repOutliers}, trigger ${outlierTrigger}`,
      plain:
        "Enough local result rows have unusually large President-versus-Senate differences to pass the outlier-count threshold. That does not prove anything by itself, but it identifies rows to inspect first.",
    });
  }

  return {
    flag: reasons.length > 0,
    title: reasons.length
      ? `Issues identified for review in ${label} (${rowLabel}): ${reasons.map((reason) => reason.summary).join("; ")}. This is not proof that tampering occurred; it means this area should be reviewed with records, ballots, or official explanations.`
      : `${label} does not cross this app's ${rowLabel} thresholds. This does not prove the absence of problems.`,
    notes: reasons.map((reason) => reason.summary).join(" | "),
    reasons,
    metrics: {
      rowCount: rows.length,
      trumpCorrelation,
      harrisCorrelation,
      demAverageDropoff,
      repAverageDropoff,
      demOutliers,
      repOutliers,
      outlierTrigger,
    },
  };
}

function reviewFlagIcon(review) {
  if (!review?.flag) {
    return "";
  }
  return `<span class="review-flag split-review-flag" title="${escapeAttr(review.title)}" aria-label="${escapeAttr(review.title)}">!</span>`;
}

function setReviewControlValues() {
  els.minWardRowsInput.value = COUNTY_REVIEW_POLICY.minWardRows;
  els.voteShareThresholdInput.value = COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold;
  els.dropoffThresholdInput.value = COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct;
  els.outlierThresholdInput.value = COUNTY_REVIEW_POLICY.outlierThresholdPct;
  els.minCandidateVotesInput.value = COUNTY_REVIEW_POLICY.minCandidateVotes;
}

function updateReviewPolicyFromControls() {
  COUNTY_REVIEW_POLICY.minWardRows = Math.max(2, Math.round(readControlNumber(els.minWardRowsInput, DEFAULT_REVIEW_POLICY.minWardRows)));
  COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold = clamp(readControlNumber(els.voteShareThresholdInput, DEFAULT_REVIEW_POLICY.voteShareCorrelationThreshold), 0, 1);
  COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct = Math.max(0, readControlNumber(els.dropoffThresholdInput, DEFAULT_REVIEW_POLICY.downBallotAverageThresholdPct));
  COUNTY_REVIEW_POLICY.outlierThresholdPct = Math.max(0, readControlNumber(els.outlierThresholdInput, DEFAULT_REVIEW_POLICY.outlierThresholdPct));
  COUNTY_REVIEW_POLICY.minCandidateVotes = Math.max(0, Math.round(readControlNumber(els.minCandidateVotesInput, DEFAULT_REVIEW_POLICY.minCandidateVotes)));
  countyReviewCache.clear();
  renderEtaTests();
  renderTable(filteredRows());
  renderCitySplitGraphs();
  renderFlaggedAreasSummary();
  renderReviewDrilldown();
}

function resetReviewPolicy() {
  Object.assign(COUNTY_REVIEW_POLICY, DEFAULT_REVIEW_POLICY);
  countyReviewCache.clear();
  setReviewControlValues();
  renderEtaTests();
  renderTable(filteredRows());
  renderCitySplitGraphs();
  renderFlaggedAreasSummary();
  renderReviewDrilldown();
}

function readControlNumber(input, fallback) {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function reviewScopeData() {
  const scope = els.reviewScopeSelect.value;
  const selectedSplit = citySplitData[Number(els.citySplitSelect.value) || 0];
  const allRows = WARD_CHARTS?.metadata?.rows || [];

  if (scope === "city" && selectedSplit) {
    return {
      scope,
      label: `${selectedSplit.city}, ${selectedSplit.county} County`,
      county: selectedSplit.county,
      city: selectedSplit.city,
      rows: selectedSplit.cityRows,
    };
  }

  if (scope === "rest" && selectedSplit) {
    return {
      scope,
      label: `${selectedSplit.county} County outside ${selectedSplit.city}`,
      county: selectedSplit.county,
      city: selectedSplit.city,
      rows: selectedSplit.restRows,
    };
  }

  const county = selectedCounty || firstFlaggedCounty() || RESULTS[0].county;
  return {
    scope: "county",
    label: `${county} County`,
    county,
    rows: allRows.filter((row) => normalizeCounty(row.county) === normalizeCounty(county)),
  };
}

function firstFlaggedCounty() {
  return RESULTS.find((row) => countyReviewSummary(row.county).flag)?.county;
}

function allReviewScopes() {
  const allRows = WARD_CHARTS?.metadata?.rows || [];
  const scopes = RESULTS.map((countyRow) => ({
    scope: "county",
    typeLabel: "County",
    label: `${countyRow.county} County`,
    county: countyRow.county,
    rows: allRows.filter((row) => normalizeCounty(row.county) === normalizeCounty(countyRow.county)),
  }));

  citySplitData.forEach((split, citySplitIndex) => {
    scopes.push({
      scope: "city",
      typeLabel: "Major city",
      label: `${split.city}, ${split.county} County`,
      county: split.county,
      city: split.city,
      citySplitIndex,
      rows: split.cityRows,
    });
    scopes.push({
      scope: "rest",
      typeLabel: "Rest of county",
      label: `${split.county} County outside ${split.city}`,
      county: split.county,
      city: split.city,
      citySplitIndex,
      rows: split.restRows,
    });
  });

  return scopes.map((scope) => {
    const review = reviewSummaryForRows(scope.label, scope.rows, "all");
    return {
      ...scope,
      review,
      severity: reviewSeverity(review),
    };
  });
}

function reviewSeverity(review) {
  const metrics = review.metrics;
  if (!review.flag || !metrics) {
    return 0;
  }
  const correlationScore =
    Math.max(Math.abs(metrics.trumpCorrelation), Math.abs(metrics.harrisCorrelation)) /
    Math.max(0.01, COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold);
  const averageDropoffScore =
    Math.max(Math.abs(metrics.demAverageDropoff), Math.abs(metrics.repAverageDropoff)) /
    Math.max(0.1, COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct);
  const outlierScore = (metrics.demOutliers + metrics.repOutliers) / Math.max(1, metrics.outlierTrigger);
  return correlationScore + averageDropoffScore + outlierScore;
}

function flaggedAreaRows({ applyFilters = true } = {}) {
  let rows = allReviewScopes().filter((scope) => scope.review.flag);
  if (applyFilters) {
    const query = els.flaggedSearchInput.value.trim().toLowerCase();
    const type = els.flaggedTypeFilter.value;
    const reason = els.flaggedReasonFilter.value;
    const minimumRows = Math.max(0, Number(els.flaggedMinRowsInput.value) || 0);
    const reasonLabels = {
      voteShare: "Vote-share pattern",
      dropoff: "Average down-ballot difference",
      outliers: "Down-ballot outliers",
    };
    rows = rows.filter((item) => {
      const matchesQuery = !query || item.label.toLowerCase().includes(query);
      const matchesType = type === "all" || item.scope === type;
      const matchesReason =
        reason === "all" || item.review.reasons.some((itemReason) => itemReason.type === reasonLabels[reason]);
      return matchesQuery && matchesType && matchesReason && item.review.metrics.rowCount >= minimumRows;
    });
  }

  const sort = els.flaggedSortSelect.value;
  const metric = (item, name) => {
    const metrics = item.review.metrics;
    if (name === "correlation") {
      return Math.max(Math.abs(metrics.trumpCorrelation), Math.abs(metrics.harrisCorrelation));
    }
    if (name === "dropoff") {
      return Math.max(Math.abs(metrics.demAverageDropoff), Math.abs(metrics.repAverageDropoff));
    }
    if (name === "outliers") {
      return metrics.demOutliers + metrics.repOutliers;
    }
    if (name === "rows") {
      return metrics.rowCount;
    }
    return item.severity;
  };
  return rows.sort((a, b) => {
    if (sort === "name") {
      return a.label.localeCompare(b.label);
    }
    return metric(b, sort) - metric(a, sort) || b.review.metrics.rowCount - a.review.metrics.rowCount || a.label.localeCompare(b.label);
  });
}

function renderFlaggedAreasSummary() {
  if (!els.flaggedAreaRows || !WARD_CHARTS) {
    flaggedAreaSummaryRows = [];
    if (els.flaggedAreasSummary) {
      els.flaggedAreasSummary.textContent = `No review rows are registered for ${activeStateConfig().name} yet.`;
    }
    if (els.flaggedAreaRows) {
      els.flaggedAreaRows.innerHTML = `
        <tr>
          <td colspan="8">Review graph data is not loaded for this state yet.</td>
        </tr>
      `;
    }
    return;
  }

  const allFlaggedRows = flaggedAreaRows({ applyFilters: false });
  flaggedAreaSummaryRows = flaggedAreaRows();
  const countyCount = flaggedAreaSummaryRows.filter((row) => row.scope === "county").length;
  const cityCount = flaggedAreaSummaryRows.filter((row) => row.scope === "city").length;
  const restCount = flaggedAreaSummaryRows.filter((row) => row.scope === "rest").length;
  els.flaggedAreasSummary.textContent = `${formatNumber(flaggedAreaSummaryRows.length)} of ${formatNumber(allFlaggedRows.length)} flagged areas shown: ${formatNumber(countyCount)} counties, ${formatNumber(cityCount)} major cities, and ${formatNumber(restCount)} rest-of-county areas.`;

  if (!flaggedAreaSummaryRows.length) {
    els.flaggedAreaRows.innerHTML = `
      <tr>
        <td colspan="8">No areas cross the current review thresholds. Lowering thresholds may show sensitivity-test candidates.</td>
      </tr>
    `;
    return;
  }

  els.flaggedAreaRows.innerHTML = flaggedAreaSummaryRows
    .map((item, index) => {
      const metrics = item.review.metrics;
      return `
        <tr>
          <td>
            <strong>${escapeText(item.label)}</strong>
            <span>${escapeText(item.review.reasons.map((reason) => reason.type).join(", "))}</span>
          </td>
          <td>${escapeText(item.typeLabel)}</td>
          <td>${escapeText(item.review.reasons.map((reason) => reason.summary).join("; "))}</td>
          <td>Trump ${metrics.trumpCorrelation.toFixed(3)}<br />Harris ${metrics.harrisCorrelation.toFixed(3)}</td>
          <td>DEM ${metrics.demAverageDropoff.toFixed(2)}%<br />REP ${metrics.repAverageDropoff.toFixed(2)}%</td>
          <td>DEM ${formatNumber(metrics.demOutliers)}<br />REP ${formatNumber(metrics.repOutliers)}</td>
          <td>${formatNumber(metrics.rowCount)}</td>
          <td><button class="mini-review-button" type="button" data-flagged-area-index="${index}">Review</button></td>
        </tr>
      `;
    })
    .join("");

  els.flaggedAreaRows.querySelectorAll("[data-flagged-area-index]").forEach((button) => {
    button.addEventListener("click", () => selectFlaggedArea(Number(button.dataset.flaggedAreaIndex)));
  });
}

function selectFlaggedArea(index) {
  const item = flaggedAreaSummaryRows[index];
  if (!item) {
    return;
  }

  if (item.scope === "county") {
    els.reviewScopeSelect.value = "county";
    selectCounty(item.county);
  } else {
    selectCounty(item.county);
    els.citySplitSelect.value = String(item.citySplitIndex);
    els.reviewScopeSelect.value = item.scope;
    renderCitySplitGraphs();
  }

  renderReviewDrilldown();
  updateReviewRoute();
  document.querySelector("#reviewDrilldown")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateReviewRoute(scope = reviewScopeData()) {
  if (!window.history?.replaceState) {
    return;
  }
  const params = new URLSearchParams({
    scope: scope.scope,
    county: scope.county,
  });
  if (scope.city) {
    params.set("city", scope.city);
  }
  replaceRoute("review", params);
}

async function copyReviewLink() {
  updateReviewRoute();
  const link = window.location.href;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(link);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = link;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.append(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    els.copyReviewLinkStatus.textContent = "Review link copied.";
  } catch (error) {
    els.copyReviewLinkStatus.textContent = `Copy failed. Use this link: ${link}`;
  }
}

function renderReviewDrilldown() {
  if (!els.reviewSummaryGrid || !WARD_CHARTS || !(WARD_CHARTS.metadata?.rows || []).length) {
    if (els.reviewSummaryGrid) {
      els.reviewSummaryGrid.innerHTML = `
        <article>
          <span class="eta-badge needs-data">Needs data</span>
          <strong>${escapeText(activeStateConfig().name)} review drilldown</strong>
          <p>Ward, precinct, or reporting-unit review rows are not registered for this state yet.</p>
        </article>
      `;
    }
    if (els.recordsRequestText) {
      els.recordsRequestText.textContent =
        "Review records request text will populate after this state has local result rows in the review graph schema.";
    }
    if (els.reviewWardRows) {
      els.reviewWardRows.innerHTML = "";
    }
    return;
  }

  const scope = reviewScopeData();
  const review = reviewSummaryForRows(scope.label, scope.rows, "all");
  const metrics = review.metrics;
  const flaggedText = review.flag ? "Flagged for review" : "No current review flag";
  const flaggedTone = review.flag ? "flag" : "pass";
  const whyHtml = review.reasons.length
    ? review.reasons
        .map(
          (reason) => `
            <li>
              <strong>${escapeText(reason.type)}:</strong>
              <span>${escapeText(reason.plain)}</span>
            </li>
          `,
        )
        .join("")
    : `<li><strong>No threshold crossed:</strong><span>This scope does not cross the current review thresholds. That is not proof there are no problems; it means this screen has no current statistical flag here.</span></li>`;

  els.reviewSummaryGrid.innerHTML = `
    <article>
      <span class="eta-badge ${flaggedTone}">${flaggedText}</span>
      <strong>${escapeText(scope.label)}</strong>
      <p>${formatNumber(metrics.rowCount)} ${escapeText(activeReviewRowLabel({ plural: true }))} under the current scope.</p>
    </article>
    <article>
      <strong>Vote-share pattern</strong>
      <p>Trump r=${metrics.trumpCorrelation.toFixed(3)}; Harris r=${metrics.harrisCorrelation.toFixed(3)}. Current flag threshold is |r| >= ${COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold.toFixed(2)}.</p>
    </article>
    <article>
      <strong>Down-ballot difference</strong>
      <p>DEM average ${metrics.demAverageDropoff.toFixed(2)}%; REP average ${metrics.repAverageDropoff.toFixed(2)}%. Current average threshold is ${COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct.toFixed(1)}%.</p>
    </article>
    <article>
      <strong>Outlier rows</strong>
      <p>DEM ${formatNumber(metrics.demOutliers)}; REP ${formatNumber(metrics.repOutliers)}. Current trigger is ${formatNumber(metrics.outlierTrigger)} rows at ${COUNTY_REVIEW_POLICY.outlierThresholdPct.toFixed(1)}%+ drop-off.</p>
    </article>
    <article class="review-why-card">
      <strong>Plain-English why</strong>
      <ul>${whyHtml}</ul>
    </article>
  `;

  els.recordsRequestText.textContent = recordsRequestText(scope, review);
  renderReviewWardRows(scope.rows);
}

function renderReviewWardRows(rows) {
  const scoredRows = rows
    .map((row) => ({ row, score: wardReviewScore(row) }))
    .sort((a, b) => b.score - a.score || b.row.total - a.row.total);

  els.reviewWardRows.innerHTML = scoredRows
    .map(({ row }) => {
      const note = wardReviewNote(row);
      return `
        <tr>
          <td>${escapeText(row.ward)}</td>
          <td>${formatNumber(row.trump)}</td>
          <td>${formatNumber(row.harris)}</td>
          <td>${formatNumber(row.total)}</td>
          <td>${row.trumpShare.toFixed(2)}%</td>
          <td>${row.harrisShare.toFixed(2)}%</td>
          <td>${row.demDropoff.toFixed(2)}%</td>
          <td>${row.repDropoff.toFixed(2)}%</td>
          <td>${escapeText(note)}</td>
        </tr>
      `;
    })
    .join("");
}

function wardReviewScore(row) {
  const demScore = row.harris >= COUNTY_REVIEW_POLICY.minCandidateVotes ? Math.abs(row.demDropoff) / Math.max(1, COUNTY_REVIEW_POLICY.outlierThresholdPct) : 0;
  const repScore = row.trump >= COUNTY_REVIEW_POLICY.minCandidateVotes ? Math.abs(row.repDropoff) / Math.max(1, COUNTY_REVIEW_POLICY.outlierThresholdPct) : 0;
  return Math.max(demScore, repScore) + Math.sqrt(row.total || 0) / 100;
}

function wardReviewNote(row) {
  const notes = [];
  if (row.harris >= COUNTY_REVIEW_POLICY.minCandidateVotes && Math.abs(row.demDropoff) >= COUNTY_REVIEW_POLICY.outlierThresholdPct) {
    notes.push(`DEM drop-off outlier (${row.demDropoff.toFixed(2)}%)`);
  }
  if (row.trump >= COUNTY_REVIEW_POLICY.minCandidateVotes && Math.abs(row.repDropoff) >= COUNTY_REVIEW_POLICY.outlierThresholdPct) {
    notes.push(`REP drop-off outlier (${row.repDropoff.toFixed(2)}%)`);
  }
  if (!notes.length && row.total >= 1000) {
    notes.push("High-volume ward row; useful for checking large reporting units");
  }
  return notes.join("; ") || "Context row for the selected scope";
}

function recordsRequestText(scope, review) {
  const base = `${scope.label}: request ward or reporting-unit canvass detail, tabulator tapes or results reports, ballot reconciliation forms, pollbook voter-number totals, absentee/central-count logs where applicable, and any audit hand-count or discrepancy records.`;
  if (!review.flag) {
    return `${base} This scope is not currently flagged, but these records are still the right way to verify the public totals.`;
  }
  return `${base} Because this scope is flagged, prioritize the ward rows marked as drop-off outliers or high-volume rows in the table below.`;
}

function renderTiles(rows) {
  els.tileFallback.innerHTML = rows
    .map(
      (row) => `
        <button class="county-tile" type="button" data-county="${row.county}" style="background:${colorFor(row)}">
          <strong>${row.county}</strong>
          <span>${winnerLabel(row)} +${Math.abs(row.marginPct).toFixed(2)}%</span>
          <span>${formatNumber(row.total)} votes</span>
        </button>
      `,
    )
    .join("");

  els.tileFallback.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => selectCounty(button.dataset.county));
  });
}

function selectCounty(county) {
  const row = byCounty.get(normalizeCounty(county));
  if (!row) {
    return;
  }
  selectedCounty = row.county;
  els.selectedCounty.textContent = `${row.county} County`;
  els.selectedWinner.textContent = winnerLabel(row);
  els.selectedMargin.textContent = `${formatNumber(Math.abs(row.margin))} votes (${Math.abs(row.marginPct).toFixed(2)}%)`;
  els.selectedTotal.textContent = formatNumber(row.total);
  renderCandidateBreakdown(row);
  renderEtaGraphs(row.county);
  if (els.historicalCountySelect) {
    els.historicalCountySelect.value = row.county;
    renderHistoricalComparison();
  }
  renderReviewDrilldown();
  renderTable(filteredRows());
  refreshMapStyles();
  if (activeTabName() === "review" && els.reviewScopeSelect.value === "county") {
    updateReviewRoute();
  }
}

function renderEtaTests() {
  const tests = etaTestResults();
  els.etaTests.innerHTML = tests
    .map(
      (test) => `
        <article class="eta-test">
          <span class="eta-badge ${test.statusClass}">${test.status}</span>
          <div>
            <strong>${technicalTerm(test.name, test.definition)}</strong>
            <p>${test.detail}</p>
            ${test.warning ? `<p class="eta-warning">${test.warning}</p>` : ""}
          </div>
        </article>
      `,
    )
    .join("");
}

function etaTestResults() {
  const analysis = ACTIVE_ETA_ANALYSIS;
  const turnoutPolicy = activeTurnoutPolicy();
  const hasReviewAnalysis = Boolean(analysis);
  const voteShareOnly = analysis?.coverageMode === "voteShareOnly";
  const voteShareFlagged =
    hasReviewAnalysis &&
    (Math.abs(analysis.voteShare.trumpCorrelation) >= COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold ||
      Math.abs(analysis.voteShare.harrisCorrelation) >= COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold);
  const downBallotFlagged =
    hasReviewAnalysis &&
    !voteShareOnly &&
    (Math.abs(analysis.downBallot.repDropPct) >= COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct ||
      Math.abs(analysis.downBallot.demDropPct) >= COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct ||
      analysis.downBallot.repOutlierWards + analysis.downBallot.demOutlierWards > 50);
  const turnoutCoverage = turnoutCoverageRows();
  const turnoutRows = TURNOUT_DATA?.metadata?.rows || 0;
  const turnoutWarningRows = TURNOUT_DATA?.metadata?.warningRows || 0;
  const completeCount = turnoutCoverage.filter((row) => row.status === "complete").length;
  const partialCount = turnoutCoverage.filter((row) => row.status === "partial").length;
  const statewideOnlyCount = turnoutCoverage.filter((row) => row.status === "statewide-only").length;
  const missingCount = turnoutCoverage.filter((row) => row.status === "missing").length;
  const turnoutStatus = turnoutRows ? (missingCount ? "Partial" : "Loaded") : turnoutPolicy.status;

  return [
    {
      name: "Down-ballot difference",
      definition: "Compares presidential votes with same-party U.S. Senate votes in each ward row. A larger gap can be reviewed, but normal split-ticket voting can also create differences.",
      status: hasReviewAnalysis && !voteShareOnly ? (downBallotFlagged ? "Flag" : "Pass") : "Needs data",
      statusClass: hasReviewAnalysis && !voteShareOnly ? (downBallotFlagged ? "flag" : "pass") : "needs-data",
      detail: hasReviewAnalysis && !voteShareOnly
        ? `President vs U.S. Senate check run on ${formatNumber(analysis.wardRows)} matched ${activeReviewRowLabel({ plural: true })}. DEM presidential-vs-Senate drop-off: ${formatSigned(analysis.downBallot.demDropVotes)} votes (${analysis.downBallot.demDropPct.toFixed(2)}%). REP presidential-vs-Senate drop-off: ${formatSigned(analysis.downBallot.repDropVotes)} votes (${analysis.downBallot.repDropPct.toFixed(2)}%). Outlier rows over ${analysis.downBallot.outlierThresholdPct}% drop-off with at least ${analysis.downBallot.minCandidateVotes} presidential votes: DEM ${analysis.downBallot.demOutlierWards}, REP ${analysis.downBallot.repOutlierWards}.`
        : voteShareOnly
        ? `Not run yet for ${activeStateConfig().name}; vote-share rows are loaded, but a same-row down-ballot comparison contest still needs to be mapped.`
        : "Not run for this state because no usable ward, precinct, or reporting-unit comparison rows are registered yet.",
      warning: voteShareOnly ? analysis.warning : "",
    },
    {
      name: "Vote share by vote count",
      definition: "Checks whether a candidate's vote share changes as ward or reporting-unit vote totals get larger. The correlation value describes the strength and direction of that relationship.",
      status: hasReviewAnalysis ? (voteShareFlagged ? "Flag" : "Pass") : "Needs data",
      statusClass: hasReviewAnalysis ? (voteShareFlagged ? "flag" : "pass") : "needs-data",
      detail: hasReviewAnalysis
        ? `Vote-share check run on ${formatNumber(analysis.wardRows)} ${activeReviewRowLabel({ plural: true })}. Trump r=${analysis.voteShare.trumpCorrelation.toFixed(3)}, Harris r=${analysis.voteShare.harrisCorrelation.toFixed(3)} between candidate vote count and candidate vote share; app review threshold is |r| >= ${COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold.toFixed(2)}.`
        : "Not run for this state because no usable ward, precinct, or reporting-unit comparison rows are registered yet.",
    },
    {
      name: "Turnout analysis",
      definition: "Compares ballots cast with a registered-voter or eligible-voter denominator. Turnout results remain partial when those denominators are missing or provisional.",
      status: turnoutStatus,
      statusClass: turnoutRows ? (missingCount ? "partial" : "pass") : "needs-data",
      detail: turnoutRows
        ? `Turnout analysis is running for ${formatNumber(turnoutRows)} imported source rows. Coverage: ${completeCount} complete ${completeCount === 1 ? "county" : "counties"}, ${partialCount} partial ${partialCount === 1 ? "county" : "counties"}, ${statewideOnlyCount} statewide-only ${statewideOnlyCount === 1 ? "county" : "counties"}, ${missingCount} counties still missing. Required fields for more imports: ${turnoutPolicy.requiredFields.join(", ")}.`
        : `Not run. ${turnoutPolicy.acceptedSource} Required fields: ${turnoutPolicy.requiredFields.join(", ")}.`,
      warning: turnoutWarningRows
        ? `${formatNumber(turnoutWarningRows)} imported turnout rows use pre-Election-Day or unknown registration denominators. ${turnoutPolicy.warning}`
        : turnoutPolicy.warning,
    },
    {
      name: "Official-result completeness",
      definition: `Checks whether the expected ${activeStateConfig().countyLabel.toLowerCase()} rows are present and whether the app's summed totals reconcile with the official ${activeStateConfig().authority} report.`,
      status: "Pass",
      statusClass: "pass",
      detail:
        `All ${formatNumber(RESULTS.length)} ${activeStateConfig().countyLabel.toLowerCase()} result rows are present, detailed candidate/write-in totals sum to each row's Other total, and statewide totals match the registered official source.`,
    },
  ];
}

function renderCoverageTracker() {
  const rows = turnoutCoverageRows();
  const partial = rows.filter((row) => row.status === "partial").length;
  const complete = rows.filter((row) => row.status === "complete").length;
  const statewideOnly = rows.filter((row) => row.status === "statewide-only").length;
  const missing = rows.filter((row) => row.status === "missing").length;
  const turnoutRows = TURNOUT_DATA?.metadata?.rows || 0;
  const warningRows = TURNOUT_DATA?.metadata?.warningRows || 0;

  els.coverageSummary.textContent = `${formatNumber(turnoutRows)} turnout source rows imported. ${complete} complete counties, ${partial} partial counties, ${statewideOnly} statewide-only counties, ${missing} missing counties. ${warningRows ? `${formatNumber(warningRows)} rows carry denominator warnings.` : ""}`;
  els.coverageList.innerHTML = rows
    .map(
      (row) => `
        <div class="coverage-row">
          <div>
            <strong>${row.county}</strong>
            <span>${row.detail}</span>
            ${row.sources?.length ? `<div class="coverage-sources">${row.sources.map((source, index) => `<a href="${source}" target="_blank" rel="noreferrer">Source ${index + 1}: ${formatSourceHost(source)}</a>`).join("")}</div>` : ""}
          </div>
          <em class="coverage-status ${row.status}">${row.status}</em>
        </div>
      `,
    )
    .join("");
}

function renderConfidenceSummary() {
  const rows = turnoutCoverageRows();
  const turnoutRows = TURNOUT_DATA?.metadata?.rows || 0;
  const warningRows = TURNOUT_DATA?.metadata?.warningRows || 0;
  const complete = rows.filter((row) => row.status === "complete").length;
  const partial = rows.filter((row) => row.status === "partial").length;
  const statewideOnly = rows.filter((row) => row.status === "statewide-only").length;
  const missing = rows.filter((row) => row.status === "missing").length;

  const wardRows = ACTIVE_ETA_ANALYSIS?.wardRows || 0;
  els.dataVersionSummary.textContent = `Data version: ${DATA_VERSION_LABEL}. Current bundle has ${formatNumber(RESULTS.length)} certified county result rows, ${formatNumber(wardRows)} ward-analysis rows, and ${formatNumber(turnoutRows)} imported turnout rows across ${complete + partial} counties, with ${statewideOnly} counties covered only by statewide turnout totals. ${missing} counties still need turnout denominators.`;
  els.confidenceBadges.innerHTML = [
    confidenceBadge(`Official ${activeStateConfig().authority} county totals`, "strong"),
    confidenceBadge(`Official ${activeReviewGraphTitlePrefix()} vote graphs`, "strong"),
    confidenceBadge("Accurate calculations, limited conclusions", "review"),
    confidenceBadge(`${formatNumber(turnoutRows)} turnout rows`, missing ? "partial" : "strong"),
    confidenceBadge(`${formatNumber(warningRows)} denominator-warning rows`, warningRows ? "warning" : "strong"),
    confidenceBadge(`${statewideOnly} statewide-only turnout counties`, statewideOnly ? "warning" : "strong"),
    confidenceBadge(`${missing} turnout counties missing`, missing ? "missing" : "strong"),
  ].join("");
}

function renderCoverageTable() {
  const rows = turnoutCoverageRows();
  const complete = rows.filter((row) => row.status === "complete").length;
  const partial = rows.filter((row) => row.status === "partial").length;
  const statewideOnly = rows.filter((row) => row.status === "statewide-only").length;
  const missing = rows.filter((row) => row.status === "missing").length;

  els.coverageTableSummary.textContent = `${complete} counties have complete turnout rows, ${partial} have partial turnout rows, ${statewideOnly} have statewide-only turnout, and ${missing} still need denominator data. Vote-result coverage is complete for all ${RESULTS.length} counties.`;
  els.coverageTableRows.innerHTML = rows
    .map((row) => {
      const sourceLinks = row.sources?.length
        ? row.sources.map((source, index) => `<a href="${source}" target="_blank" rel="noreferrer">Turnout ${index + 1}: ${formatSourceHost(source)}</a>`).join("")
        : "<span>No turnout denominator source imported</span>";
      const warning = row.status === "missing" ? "No turnout rows" : row.warnings ? `Yes - ${formatNumber(row.warnings)} row${row.warnings === 1 ? "" : "s"}` : "No warning rows";
      const statusTone = row.status === "missing" ? "missing" : row.status === "complete" ? "strong" : "partial";
      const statusLabel = row.status === "missing" ? "Missing" : row.status === "complete" ? "Complete" : row.status === "statewide-only" ? "Statewide only" : "Partial";
      return `
        <tr>
          <td>${row.county}</td>
          <td><span class="confidence-pill strong">Official</span></td>
          <td>
            <span class="confidence-pill ${statusTone}">${statusLabel}</span>
            <p class="coverage-cell-note">${row.status === "missing" ? "No turnout denominator rows imported" : row.detail}</p>
          </td>
          <td>${warning}</td>
          <td class="coverage-table-sources"><span>${escapeText(activeStateConfig().authority)} vote files</span>${sourceLinks}</td>
        </tr>
      `;
    })
    .join("");
}

function renderCheckedNotUsable() {
  els.checkedNotUsableList.innerHTML = activeCheckedNotUsable().map(
    (item) => `
      <article>
        <strong>${item.county} County</strong>
        <p>${item.reason}</p>
        <span>Missing: ${item.missingFields}</span>
        <a href="${item.sourceUrl}" target="_blank" rel="noreferrer">${formatSourceHost(item.sourceUrl)}</a>
      </article>
    `,
  ).join("");
}

function renderSourcePlanner() {
  if (!els.sourceStateSelect.options.length) {
    els.sourceStateSelect.innerHTML = Object.values(STATE_SOURCE_PLANS)
      .map((plan) => `<option value="${escapeAttr(plan.code)}">${escapeText(plan.state)} ${plan.electionYear}</option>`)
      .join("");
  }

  const plan = selectedSourcePlan();
  if (!plan) {
    els.sourceStateTitle.textContent = "State not loaded";
    els.sourceStateSummary.textContent = "No source plan is available for the selected state.";
    els.sourcePlanBadges.innerHTML = confidenceBadge("Not loaded", "missing");
    els.sourceCountyRows.innerHTML = "";
    return;
  }

  const rows = sourceCountyRows(plan);
  const imported = rows.filter((row) => row.turnoutStatus !== "missing").length;
  const checked = rows.filter((row) => row.checkedNotImported).length;
  const missing = rows.length - imported;

  els.sourceStateTitle.textContent = `${plan.state} ${plan.electionYear} ${plan.office}`;
  els.sourceStateSummary.textContent =
    `${plan.stateAuthority}: ${formatNumber(rows.length)} ${plan.countyLabel.toLowerCase()} result rows loaded. Certified county results and ward detail are statewide; turnout denominator imports are partial with ${formatNumber(imported)} counties imported, ${formatNumber(missing)} missing, and ${formatNumber(checked)} checked but not imported.`;
  els.sourcePlanBadges.innerHTML = [
    confidenceBadge(`${formatNumber(rows.length)} county result rows`, "strong"),
    confidenceBadge("Certified statewide source", "strong"),
    confidenceBadge(stateCapabilityLabel("map"), stateCapabilityTone("map")),
    confidenceBadge(stateCapabilityLabel("reviewGraphs"), stateCapabilityTone("reviewGraphs")),
    confidenceBadge(stateCapabilityLabel("turnout"), stateCapabilityTone("turnout")),
    confidenceBadge(stateCapabilityLabel("historicalBaseline"), stateCapabilityTone("historicalBaseline")),
    confidenceBadge(`${formatNumber(imported)} turnout counties imported`, imported ? "partial" : "missing"),
    confidenceBadge(`${formatNumber(missing)} turnout counties missing`, missing ? "missing" : "strong"),
  ].join("");

  renderSourceCategory("Certified", plan.certifiedResults);
  renderSourceCategory("Ward", plan.wardDetail);
  renderSourceCategory("Turnout", plan.turnout);
  renderSourceCountyRows();
}

function renderSourceCategory(kind, category) {
  const title = els[`source${kind}Title`];
  const detail = els[`source${kind}Detail`];
  const links = els[`source${kind}Links`];
  title.textContent = category.title;
  detail.textContent = category.detail;
  links.innerHTML = sourceCategoryLinks(category);
}

function renderSourceCountyRows() {
  const plan = selectedSourcePlan();
  if (!plan) {
    return;
  }

  const query = els.sourceCountySearch.value.trim().toLowerCase();
  const filter = els.sourceStatusFilter.value || "all";
  const allRows = sourceCountyRows(plan);
  const rows = allRows.filter((row) => {
    const matchesQuery = !query || row.county.toLowerCase().includes(query);
    const matchesStatus =
      filter === "all" ||
      (filter === "imported" && row.turnoutStatus !== "missing") ||
      (filter === "missing" && row.turnoutStatus === "missing") ||
      (filter === "checked" && row.checkedNotImported);
    return matchesQuery && matchesStatus;
  });

  const imported = allRows.filter((row) => row.turnoutStatus !== "missing").length;
  const missing = allRows.length - imported;
  els.sourceCountySummary.textContent =
    `${formatNumber(rows.length)} of ${formatNumber(allRows.length)} counties shown. Turnout denominator status: ${formatNumber(imported)} imported, ${formatNumber(missing)} missing.`;
  els.sourceCountyRows.innerHTML = rows.map(sourceCountyRowHtml).join("");
}

function sourceCountyRowHtml(row) {
  const turnoutClass = row.turnoutStatus === "missing" ? "missing" : "partial";
  const turnoutLabel = row.turnoutStatus === "missing" ? "Missing" : "Imported";
  const certifiedStatus = row.certifiedSource.status || "Needs data";
  const wardStatus = row.wardSource.status || "Needs data";
  const followUp = row.checkedNotImported
    ? `Checked but not imported: ${row.checkedNotImported.reason}`
    : row.turnoutStatus === "missing"
      ? "Collect county or municipal canvass rows with ballots cast, registered voters, denominator timing, and source URL."
      : row.turnoutWarnings
        ? `${formatNumber(row.turnoutWarnings)} imported denominator warning row${row.turnoutWarnings === 1 ? "" : "s"} need timing review.`
        : "No immediate turnout source follow-up logged.";

  return `
    <tr>
      <td><strong>${escapeText(row.county)}</strong></td>
      <td>
        <span class="confidence-pill ${sourceStatusTone(certifiedStatus)}">${escapeText(certifiedStatus)}</span>
        <p class="coverage-cell-note">${escapeText(row.certifiedSource.title)}</p>
        <div class="coverage-table-sources">${sourceCategoryLinks(row.certifiedSource)}</div>
      </td>
      <td>
        <span class="confidence-pill ${sourceStatusTone(wardStatus)}">${escapeText(wardStatus)}</span>
        <p class="coverage-cell-note">${escapeText(row.wardSource.title)}</p>
        <div class="coverage-table-sources">${sourceCategoryLinks(row.wardSource)}</div>
      </td>
      <td>
        <span class="confidence-pill ${turnoutClass}">${turnoutLabel}</span>
        <p class="coverage-cell-note">${escapeText(row.turnoutDetail)}</p>
        <div class="coverage-table-sources">${sourceLinks(row.turnoutSources, "Turnout")}</div>
      </td>
      <td>${escapeText(followUp)}</td>
    </tr>
  `;
}

function sourceStatusTone(status = "") {
  const normalized = status.toLowerCase();
  if (normalized === "loaded") {
    return "strong";
  }
  if (normalized.includes("partial") || normalized.includes("ready")) {
    return "partial";
  }
  return "missing";
}

function sourceCountyRows(plan = selectedSourcePlan()) {
  if (!plan) {
    return [];
  }
  const coverageByCounty = new Map(turnoutCoverageRows().map((row) => [normalizeCounty(row.county), row]));
  const checkedByCounty = new Map(activeCheckedNotUsable().map((row) => [normalizeCounty(row.county), row]));

  return plan.resultRows.map((countyRow) => {
    const coverage = coverageByCounty.get(normalizeCounty(countyRow.county));
    const checkedNotImported = checkedByCounty.get(normalizeCounty(countyRow.county));
    return {
      county: countyRow.county,
      certifiedSource: plan.certifiedResults,
      wardSource: plan.wardDetail,
      turnoutStatus: coverage?.status || "missing",
      turnoutDetail: coverage?.status === "missing" ? "No turnout denominator source imported." : coverage.detail,
      turnoutWarnings: coverage?.warnings || 0,
      turnoutSources: coverage?.sources || [],
      checkedNotImported,
    };
  });
}

function selectedSourcePlan() {
  const code = els.sourceStateSelect.value || activeStateCode;
  return APP_STATES[code]?.sourcePlan || STATE_SOURCE_PLANS[code];
}

function sourceCategoryLinks(category) {
  const links = [];
  if (category.sourceUrl && !category.sourceUrl.startsWith("Multiple ")) {
    links.push(`<a href="${escapeAttr(category.sourceUrl)}" target="_blank" rel="noreferrer">${escapeText(formatSourceHost(category.sourceUrl))}</a>`);
  }
  if (category.sourceLastModifiedUtc) {
    links.push(`<span>Last modified: ${escapeText(formatTimestampForDisplay(category.sourceLastModifiedUtc))}</span>`);
  }
  if (category.localFile) {
    links.push(`<span>${escapeText(category.localFile)}</span>`);
  }
  return links.join("");
}

function sourceLinks(sources, label) {
  if (!sources?.length) {
    return "<span>No source imported</span>";
  }
  return sources
    .map((source, index) => `<a href="${escapeAttr(source)}" target="_blank" rel="noreferrer">${escapeText(label)} ${index + 1}: ${escapeText(formatSourceHost(source))}</a>`)
    .join("");
}

function formatTimestampForDisplay(value) {
  if (!value) {
    return "Not captured";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toISOString().replace(".000Z", "Z")} (server Last-Modified)`;
}

function renderHistoricalComparison() {
  if (!HISTORICAL_BASELINE?.series?.length) {
    renderGraphMessage(els.historicalTrendGraph, "Historical baseline data is not loaded.");
    renderGraphMessage(els.historicalScatterGraph, "Historical baseline data is not loaded.");
    renderGraphMessage(els.historicalDistributionGraph, "Historical baseline data is not loaded.");
    els.historicalCountySelect.innerHTML = "";
    els.historicalSeriesSelect.innerHTML = "";
    els.historicalTableRows.innerHTML = "";
    els.historicalScopeTitle.textContent = `${activeStateConfig().name} comparison`;
    els.historicalSummary.textContent = "Historical comparison data is unavailable.";
    return;
  }

  if (!els.historicalCountySelect.options.length) {
    els.historicalCountySelect.innerHTML = [
      `<option value="">Statewide</option>`,
      ...RESULTS.map((row) => `<option value="${escapeAttr(row.county)}">${escapeText(row.county)} County</option>`),
    ].join("");
  }
  if (!els.historicalSeriesSelect.options.length) {
    els.historicalSeriesSelect.innerHTML = HISTORICAL_BASELINE.series
      .map((series) => `<option value="${escapeAttr(series.id)}">${escapeText(historicalSeriesLabel(series))}</option>`)
      .join("");
    els.historicalSeriesSelect.value = activeHistoricalPrimarySeriesIds()[0] || HISTORICAL_BASELINE.series[0]?.id || "";
  }

  const county = els.historicalCountySelect.value;
  const scopeLabel = county ? `${county} County` : "Statewide";
  const primarySeries = activeHistoricalPrimarySeriesIds().map((id) => historicalSeriesById(id)).filter(Boolean);
  els.historicalScopeTitle.textContent = `${scopeLabel} comparison`;
  els.historicalSummary.textContent = `${scopeLabel}: comparing ${primarySeries.length} presidential elections. ${activeStateConfig().historicalSummary || "Rows are visibly labeled by source type."}`;
  els.historicalTableRows.innerHTML = primarySeries.map((series) => historicalTableRow(series, county)).join("");
  renderHistoricalTrendGraph(primarySeries, county);
  renderHistoricalScatterGraph(historicalSeriesById(els.historicalSeriesSelect.value), county);
  renderHistoricalDistributionGraph(primarySeries, county);
}

function activeHistoricalPrimarySeriesIds() {
  return activeStateConfig().historicalPrimarySeriesIds || HISTORICAL_PRIMARY_SERIES_IDS;
}

function historicalSeriesById(id) {
  return HISTORICAL_BASELINE?.series?.find((series) => series.id === id);
}

function historicalSeriesLabel(series) {
  return HISTORICAL_SERIES_LABELS[series.id] || `${series.electionYear} presidential results`;
}

function historicalScopeRows(series, county) {
  if (!series) {
    return [];
  }
  if (!county) {
    return series.rows;
  }
  const normalized = normalizeCounty(county);
  return series.rows.filter((row) => normalizeCounty(row.county) === normalized);
}

function historicalScopeTotals(series, county) {
  return historicalScopeRows(series, county).reduce(
    (totals, row) => {
      totals.dem += row.dem;
      totals.rep += row.rep;
      totals.other += row.other;
      totals.total += row.total;
      totals.rowCount += 1;
      return totals;
    },
    { dem: 0, rep: 0, other: 0, total: 0, rowCount: 0 },
  );
}

function historicalShare(value, total) {
  return total ? (value / total) * 100 : 0;
}

function historicalTableRow(series, county) {
  const totals = historicalScopeTotals(series, county);
  const sourceClass = historicalSourceClassTone(series);
  const sourceLabel = historicalSourceLabel(series);
  return `
    <tr>
      <td>${series.electionYear}</td>
      <td><span class="history-source-pill ${sourceClass}">${sourceLabel}</span></td>
      <td>${formatNumber(totals.dem)}</td>
      <td>${formatNumber(totals.rep)}</td>
      <td>${formatNumber(totals.other)}</td>
      <td>${formatNumber(totals.total)}</td>
      <td class="party-d">${historicalShare(totals.dem, totals.total).toFixed(2)}%</td>
      <td class="party-r">${historicalShare(totals.rep, totals.total).toFixed(2)}%</td>
    </tr>
  `;
}

function historicalSourceClassTone(series) {
  return series.sourceClass === "nativeOfficial" ? "native" : "harmonized";
}

function historicalSourceLabel(series) {
  if (series.sourceClass !== "nativeOfficial") {
    return "LTSB harmonized";
  }
  if (series.sourceId?.startsWith("mn-sos-")) {
    return "Native official SOS";
  }
  return "Native official WEC";
}

function renderHistoricalTrendGraph(seriesList, county) {
  const width = 820;
  const height = 340;
  const margin = { left: 58, right: 26, top: 42, bottom: 58 };
  const points = seriesList.map((series, index) => {
    const totals = historicalScopeTotals(series, county);
    return {
      year: series.electionYear,
      x: margin.left + (index * (width - margin.left - margin.right)) / Math.max(1, seriesList.length - 1),
      dem: historicalShare(totals.dem, totals.total),
      rep: historicalShare(totals.rep, totals.total),
    };
  });
  const y = (value) => height - margin.bottom - (value / 100) * (height - margin.top - margin.bottom);
  const grid = [0, 25, 50, 75, 100]
    .map((tick) => `
      <line class="graph-grid" x1="${margin.left}" y1="${y(tick)}" x2="${width - margin.right}" y2="${y(tick)}"></line>
      <text class="graph-label" x="${margin.left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>
    `)
    .join("");
  const area = county ? `${county} County` : "Statewide";
  els.historicalTrendGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(area)} presidential vote share across years">
      ${grid}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      <text class="graph-title" x="${margin.left}" y="22">${escapeText(area)}: presidential share across elections</text>
      <polyline points="${points.map((point) => `${point.x},${y(point.dem)}`).join(" ")}" fill="none" stroke="#3477bd" stroke-width="4"></polyline>
      <polyline points="${points.map((point) => `${point.x},${y(point.rep)}`).join(" ")}" fill="none" stroke="#c84c42" stroke-width="4"></polyline>
      ${points.map((point) => `
        <circle cx="${point.x}" cy="${y(point.dem)}" r="5" fill="#3477bd"><title>${point.year} Democratic share: ${point.dem.toFixed(2)}%</title></circle>
        <circle cx="${point.x}" cy="${y(point.rep)}" r="5" fill="#c84c42"><title>${point.year} Republican share: ${point.rep.toFixed(2)}%</title></circle>
        <text class="graph-label" x="${point.x}" y="${height - 34}" text-anchor="middle">${point.year}</text>
      `).join("")}
      <circle cx="${width - 180}" cy="22" r="5" fill="#3477bd"></circle>
      <text class="graph-label" x="${width - 168}" y="26">Democratic</text>
      <circle cx="${width - 86}" cy="22" r="5" fill="#c84c42"></circle>
      <text class="graph-label" x="${width - 74}" y="26">Republican</text>
      ${axisLabel({ x: width / 2, y: height - 10, anchor: "middle", label: "Presidential election year", help: `Each x-axis value is one ${activeStateConfig().name} presidential general election year.` })}
      ${axisLabel({ transform: `translate(16 ${height / 2}) rotate(-90)`, anchor: "middle", label: "Candidate vote share", help: "The y-axis is the candidate's percent of presidential votes in the selected area." })}
    </svg>
  `;
}

function renderHistoricalScatterGraph(series, county) {
  const rows = historicalScopeRows(series, county).filter((row) => row.total > 0);
  if (!series || !rows.length) {
    renderGraphMessage(els.historicalScatterGraph, "No historical rows found for this area and series.");
    return;
  }
  const width = 820;
  const height = 340;
  const margin = { left: 58, right: 26, top: 42, bottom: 58 };
  const rep = rows.map((row) => [row.rep, historicalShare(row.rep, row.total)]);
  const dem = rows.map((row) => [row.dem, historicalShare(row.dem, row.total)]);
  const maxVotes = Math.max(1, ...rep.map((point) => point[0]), ...dem.map((point) => point[0]));
  const x = (value) => margin.left + (value / maxVotes) * (width - margin.left - margin.right);
  const y = (value) => height - margin.bottom - (value / 100) * (height - margin.top - margin.bottom);
  const yGrid = [0, 25, 50, 75, 100]
    .map((tick) => `
      <line class="graph-grid" x1="${margin.left}" y1="${y(tick)}" x2="${width - margin.right}" y2="${y(tick)}"></line>
      <text class="graph-label" x="${margin.left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>
    `)
    .join("");
  const xTicks = [0, 0.25, 0.5, 0.75, 1]
    .map((ratio) => `<text class="graph-label" x="${x(maxVotes * ratio)}" y="${height - 34}" text-anchor="middle">${formatNumber(Math.round(maxVotes * ratio))}</text>`)
    .join("");
  const area = county ? `${county} County` : "Statewide";
  const sourceNote = series.sourceClass === "nativeOfficial"
    ? historicalSourceLabel(series).toLowerCase().replace("native official", "native official") + " rows"
    : "LTSB harmonized comparison rows";
  els.historicalScatterGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(historicalSeriesLabel(series))} vote share by vote count">
      ${yGrid}
      ${xTicks}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      <text class="graph-title" x="${margin.left}" y="20">${escapeText(`${area}: ${series.electionYear} vote-share chart (${formatNumber(rows.length)} ${sourceNote})`)}</text>
      ${rep.map((point) => `<circle cx="${x(point[0])}" cy="${y(point[1])}" r="2" fill="#c84c42" opacity="0.34"><title>Republican: ${formatNumber(point[0])} votes, ${point[1].toFixed(2)}%</title></circle>`).join("")}
      ${dem.map((point) => `<circle cx="${x(point[0])}" cy="${y(point[1])}" r="2" fill="#3477bd" opacity="0.34"><title>Democratic: ${formatNumber(point[0])} votes, ${point[1].toFixed(2)}%</title></circle>`).join("")}
      ${rep.length > 1 ? regressionLine(rep, x, y, maxVotes, "#b53d34") : ""}
      ${dem.length > 1 ? regressionLine(dem, x, y, maxVotes, "#2368b4") : ""}
      <circle cx="${width - 164}" cy="22" r="5" fill="#c84c42"></circle>
      <text class="graph-label" x="${width - 152}" y="26">Republican</text>
      <circle cx="${width - 72}" cy="22" r="5" fill="#3477bd"></circle>
      <text class="graph-label" x="${width - 60}" y="26">Democratic</text>
      ${axisLabel({ x: width / 2, y: height - 10, anchor: "middle", label: "Candidate votes in source row", help: "The x-axis is how many votes the candidate received in one ward or reporting-unit row." })}
      ${axisLabel({ transform: `translate(16 ${height / 2}) rotate(-90)`, anchor: "middle", label: "Candidate vote share", help: "The y-axis is the candidate's percent of presidential votes in that source row." })}
    </svg>
  `;
}

function renderHistoricalDistributionGraph(seriesList, county) {
  const width = 1000;
  const height = 650;
  const panel = { width: 470, height: 265, gapX: 18, gapY: 22 };
  const margin = { left: 48, right: 14, top: 42, bottom: 48 };
  const binStep = 5;
  const plots = seriesList.map((series) => {
    const values = historicalScopeRows(series, county)
      .filter((row) => row.total > 0)
      .map((row) => historicalShare(row.rep, row.total));
    const bins = buildHistoricalShareBins(values, binStep);
    const mean = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
    const peak = bins.reduce((best, bin) => (bin.count > best.count ? bin : best), bins[0]);
    return { series, values, bins, mean, peak, skew: historicalSkewness(values) };
  });
  const globalMax = Math.max(1, ...plots.flatMap((plot) => plot.bins.map((bin) => bin.count)));
  const area = county ? `${county} County` : "Statewide";
  const distributionSourceLabel = activeStateCode === "WI" ? "LTSB harmonized rows" : "native official county rows";
  const panels = plots
    .map((plot, index) => {
      const originX = 18 + (index % 2) * (panel.width + panel.gapX);
      const originY = 58 + Math.floor(index / 2) * (panel.height + panel.gapY);
      const chartLeft = originX + margin.left;
      const chartRight = originX + panel.width - margin.right;
      const chartTop = originY + margin.top;
      const chartBottom = originY + panel.height - margin.bottom;
      const chartWidth = chartRight - chartLeft;
      const chartHeight = chartBottom - chartTop;
      const x = (value) => chartLeft + (value / 100) * chartWidth;
      const y = (value) => chartBottom - (value / globalMax) * chartHeight;
      const barWidth = chartWidth / plot.bins.length;
      const xTicks = [0, 25, 50, 75, 100]
        .map((tick) => `
          <line class="graph-grid" x1="${x(tick)}" y1="${chartTop}" x2="${x(tick)}" y2="${chartBottom}"></line>
          <text class="graph-label" x="${x(tick)}" y="${chartBottom + 18}" text-anchor="middle">${tick}%</text>
        `)
        .join("");
      const yTicks = [0, Math.round(globalMax / 2), globalMax]
        .map((tick) => `
          <line class="graph-grid" x1="${chartLeft}" y1="${y(tick)}" x2="${chartRight}" y2="${y(tick)}"></line>
          <text class="graph-label" x="${chartLeft - 7}" y="${y(tick) + 4}" text-anchor="end">${formatNumber(tick)}</text>
        `)
        .join("");
      const bars = plot.bins
        .map((bin, binIndex) => {
          const barX = chartLeft + binIndex * barWidth + 1;
          const barY = y(bin.count);
          return `<rect x="${barX}" y="${barY}" width="${Math.max(1, barWidth - 2)}" height="${chartBottom - barY}" fill="#c84c42" opacity="0.62"><title>${bin.start}-${bin.end}% Republican share: ${formatNumber(bin.count)} source rows</title></rect>`;
        })
        .join("");
      const curvePoints = plot.bins
        .map((bin, binIndex) => `${chartLeft + (binIndex + 0.5) * barWidth},${y(bin.count)}`)
        .join(" ");
      const peakMidpoint = plot.peak.start + binStep / 2;
      return `
        <g>
          <text class="graph-title" x="${originX}" y="${originY + 18}">${plot.series.electionYear}: ${formatNumber(plot.values.length)} rows | skew ${plot.skew.toFixed(2)}</text>
          ${xTicks}
          ${yTicks}
          ${bars}
          <polyline points="${curvePoints}" fill="none" stroke="#17202c" stroke-width="2.5" opacity="0.88"></polyline>
          <line x1="${x(plot.mean)}" y1="${chartTop}" x2="${x(plot.mean)}" y2="${chartBottom}" stroke="#3477bd" stroke-width="2.5" stroke-dasharray="7 5"><title>Average source-row Republican share: ${plot.mean.toFixed(2)}%</title></line>
          <line x1="${x(peakMidpoint)}" y1="${chartTop}" x2="${x(peakMidpoint)}" y2="${chartBottom}" stroke="#b7812d" stroke-width="2.5"><title>Most common range: ${plot.peak.start}-${plot.peak.end}% Republican share</title></line>
          <line class="graph-axis" x1="${chartLeft}" y1="${chartBottom}" x2="${chartRight}" y2="${chartBottom}"></line>
          <line class="graph-axis" x1="${chartLeft}" y1="${chartTop}" x2="${chartLeft}" y2="${chartBottom}"></line>
          <text class="graph-label" x="${(chartLeft + chartRight) / 2}" y="${originY + panel.height - 8}" text-anchor="middle">Republican vote share</text>
        </g>
      `;
    })
    .join("");
  els.historicalDistributionGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(area)} Republican presidential vote-share distributions across years">
      <text class="graph-title" x="18" y="25">${escapeText(area)}: Republican presidential vote-share distributions on ${escapeText(distributionSourceLabel)}</text>
      <line x1="${width - 268}" y1="20" x2="${width - 234}" y2="20" stroke="#3477bd" stroke-width="2.5" stroke-dasharray="7 5"></line>
      <text class="graph-label" x="${width - 226}" y="24">Average row</text>
      <line x1="${width - 128}" y1="20" x2="${width - 94}" y2="20" stroke="#b7812d" stroke-width="2.5"></line>
      <text class="graph-label" x="${width - 86}" y="24">Busiest bucket</text>
      ${panels}
      ${axisLabel({ transform: "translate(13 335) rotate(-90)", anchor: "middle", label: "Number of source rows", help: "The y-axis counts how many harmonized local result rows fall into each vote-share range." })}
    </svg>
  `;
}

function buildHistoricalShareBins(values, step) {
  const bins = Array.from({ length: Math.ceil(100 / step) }, (_, index) => ({
    start: index * step,
    end: (index + 1) * step,
    count: 0,
  }));
  values.forEach((value) => {
    const index = Math.min(bins.length - 1, Math.max(0, Math.floor(value / step)));
    bins[index].count += 1;
  });
  return bins;
}

function historicalSkewness(values) {
  if (values.length < 3) {
    return 0;
  }
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const deviation = Math.sqrt(variance);
  if (!deviation) {
    return 0;
  }
  return values.reduce((sum, value) => sum + ((value - mean) / deviation) ** 3, 0) / values.length;
}

function confidenceBadge(label, tone) {
  return `<span class="confidence-pill ${tone}">${label}</span>`;
}

function turnoutCoverageRows() {
  const rows = TURNOUT_DATA?.rows || [];
  const statewideRows = rows.filter((row) => row.sourceLevel === "statewide" || row.coverageStatus === "statewide-only");
  const statewideSources = [...new Set(statewideRows.map((row) => row.sourceUrl).filter(Boolean))];
  const statewideWarnings = statewideRows.filter((row) => row.warningRequired).length;
  const statewideDenominatorTypes = [...new Set(statewideRows.map((row) => row.denominatorType).filter(Boolean))];
  const statewideDenominatorTimings = [...new Set(statewideRows.map((row) => row.registrationDenominatorTiming).filter(Boolean))];
  const byCounty = new Map();
  rows.forEach((row) => {
    const key = normalizeCounty(row.county);
    const current = byCounty.get(key) || {
      rows: 0,
      municipalities: new Set(),
      warnings: 0,
      countyLevelRows: 0,
      sources: new Set(),
      sourceLevels: new Set(),
      denominatorTypes: new Set(),
      denominatorTimings: new Set(),
      coverageStatuses: new Set(),
    };
    current.rows += 1;
    current.municipalities.add(row.municipality || "Unknown municipality");
    if (row.sourceUrl) {
      current.sources.add(row.sourceUrl);
    }
    if (row.sourceLevel) {
      current.sourceLevels.add(row.sourceLevel);
    }
    if (row.denominatorType) {
      current.denominatorTypes.add(row.denominatorType);
    }
    if (row.registrationDenominatorTiming) {
      current.denominatorTimings.add(row.registrationDenominatorTiming);
    }
    if (row.coverageStatus) {
      current.coverageStatuses.add(row.coverageStatus);
    }
    if (row.warningRequired) {
      current.warnings += 1;
    }
    if (row.sourceLevel === "county") {
      current.countyLevelRows += 1;
    }
    byCounty.set(key, current);
  });

  return RESULTS.map((countyRow) => {
    const data = byCounty.get(normalizeCounty(countyRow.county));
    if (!data) {
      if (statewideRows.length) {
        const denominatorTypes = statewideDenominatorTypes.join(", ") || "registeredVoters";
        const denominatorTimings = statewideDenominatorTimings.join(", ") || "unknown";
        return {
          county: countyRow.county,
          status: "statewide-only",
          detail: `${formatNumber(statewideRows.length)} official statewide turnout row${statewideRows.length === 1 ? "" : "s"} available; no county-level turnout denominator row imported for this county; denominator ${denominatorTypes}, timing ${denominatorTimings}; ${formatNumber(statewideWarnings)} warning rows`,
          rows: 0,
          warnings: statewideWarnings,
          localAreaCount: 0,
          countyLevelRows: 0,
          sourceLevels: ["statewide"],
          denominatorTypes: statewideDenominatorTypes,
          denominatorTimings: statewideDenominatorTimings,
          sources: statewideSources,
        };
      }
      return {
        county: countyRow.county,
        status: "missing",
        detail: "No turnout denominator rows imported",
      };
    }
    const status = data.coverageStatuses.has("statewide-only") || data.sourceLevels.has("statewide") ? "statewide-only" : data.coverageStatuses.has("partial") ? "partial" : "complete";
    const sourceLevels = [...data.sourceLevels].join(", ") || "unknown";
    const denominatorTypes = [...data.denominatorTypes].join(", ") || "registeredVoters";
    const denominatorTimings = [...data.denominatorTimings].join(", ") || "unknown";
    return {
      county: countyRow.county,
      status,
      detail: `${formatNumber(data.rows)} turnout row${data.rows === 1 ? "" : "s"} from ${data.municipalities.size} local area${data.municipalities.size === 1 ? "" : "s"}${data.countyLevelRows ? `; ${formatNumber(data.countyLevelRows)} county-level row${data.countyLevelRows === 1 ? "" : "s"}` : ""}; source level ${sourceLevels}; denominator ${denominatorTypes}, timing ${denominatorTimings}; ${formatNumber(data.warnings)} warning rows`,
      rows: data.rows,
      warnings: data.warnings,
      localAreaCount: data.municipalities.size,
      countyLevelRows: data.countyLevelRows,
      sourceLevels: [...data.sourceLevels],
      denominatorTypes: [...data.denominatorTypes],
      denominatorTimings: [...data.denominatorTimings],
      sources: [...data.sources],
    };
  });
}

function renderEtaGraphs(county = selectedCounty) {
  if (!WARD_CHARTS) {
    renderGraphMessage(els.voteShareGraph, "Review chart data is not loaded.");
    renderGraphMessage(els.downBallotGraph, "Review chart data is not loaded.");
    renderGraphMessage(els.turnoutGraph, activeTurnoutPolicy().warning);
    return;
  }

  renderVoteShareGraph(county);
  renderDownBallotGraph(county);
  renderTurnoutGraph(county);
}

function chartScope(county) {
  const normalized = normalizeCounty(county || "");
  const metadata = WARD_CHARTS?.metadata || {};
  const rows = county
    ? metadata.rows.filter((row) => normalizeCounty(row.county) === normalized)
    : metadata.rows;

  return {
    rows,
    label: county ? `${county} County` : "Statewide",
  };
}

function renderCitySplitOptions() {
  citySplitData = majorCitySplits();
  if (!citySplitData.length) {
    els.citySplitSelect.innerHTML = "";
    els.citySplitSummary.textContent = `No city ward groups were found for ${activeStateConfig().name}.`;
    renderGraphMessage(els.cityVoteShareGraph, "City split review data is not loaded.");
    renderGraphMessage(els.countyRestVoteShareGraph, "City split review data is not loaded.");
    renderGraphMessage(els.cityDownBallotGraph, "City split review data is not loaded.");
    renderGraphMessage(els.countyRestDownBallotGraph, "City split review data is not loaded.");
    return;
  }

  els.citySplitSelect.innerHTML = citySplitData
    .map((split, index) => `<option value="${index}">${split.city}, ${split.county} County (${formatNumber(split.cityRows.length)} city rows)</option>`)
    .join("");
  els.citySplitSelect.value = "0";
  renderCitySplitGraphs();
}

function renderCitySplitGraphs() {
  const split = citySplitData[Number(els.citySplitSelect.value) || 0];
  if (!split) {
    return;
  }

  const cityLabel = `${split.city}, ${split.county} County`;
  const restLabel = `${split.county} County outside ${split.city}`;
  const cityVoteReview = reviewSummaryForRows(cityLabel, split.cityRows, "voteShare");
  const restVoteReview = reviewSummaryForRows(restLabel, split.restRows, "voteShare");
  const cityDownBallotReview = reviewSummaryForRows(cityLabel, split.cityRows, "downBallot");
  const restDownBallotReview = reviewSummaryForRows(restLabel, split.restRows, "downBallot");
  els.citySplitSummary.textContent = `${cityLabel}: ${formatNumber(split.cityRows.length)} city rows compared with ${formatNumber(split.restRows.length)} rest-of-county rows. Uses official ${activeReviewGraphTitlePrefix()} vote totals.`;
  els.cityVoteShareTitle.innerHTML = `${escapeText(split.city)}: vote-share ${reviewFlagIcon(cityVoteReview)}`;
  els.countyRestVoteShareTitle.innerHTML = `${escapeText(restLabel)}: vote-share ${reviewFlagIcon(restVoteReview)}`;
  els.cityDownBallotTitle.innerHTML = `${escapeText(split.city)}: down-ballot ${reviewFlagIcon(cityDownBallotReview)}`;
  els.countyRestDownBallotTitle.innerHTML = `${escapeText(restLabel)}: down-ballot ${reviewFlagIcon(restDownBallotReview)}`;

  renderVoteShareGraphForRows(els.cityVoteShareGraph, { rows: split.cityRows, label: split.city }, { height: 320 });
  renderVoteShareGraphForRows(els.countyRestVoteShareGraph, { rows: split.restRows, label: restLabel }, { height: 320 });
  renderDownBallotGraphForRows(els.cityDownBallotGraph, { rows: split.cityRows, label: split.city }, { height: 300 });
  renderDownBallotGraphForRows(els.countyRestDownBallotGraph, { rows: split.restRows, label: restLabel }, { height: 300 });
  renderReviewDrilldown();
}

function majorCitySplits() {
  const rows = WARD_CHARTS?.metadata?.rows || [];
  const byCity = new Map();

  rows.forEach((row) => {
    const city = cityNameForWard(row.ward);
    if (!city) {
      return;
    }
    const key = `${normalizeCounty(row.county)}|${normalizeCounty(city)}`;
    const current = byCity.get(key) || { city, county: row.county, cityRows: [] };
    current.cityRows.push(row);
    byCity.set(key, current);
  });

  return [...byCity.values()]
    .filter((split) => split.cityRows.length >= 10)
    .map((split) => {
      const cityKeys = new Set(split.cityRows.map((row) => row.ward));
      return {
        ...split,
        restRows: rows.filter((row) => row.county === split.county && !cityKeys.has(row.ward)),
      };
    })
    .filter((split) => split.restRows.length > 0)
    .sort((a, b) => b.cityRows.length - a.cityRows.length || a.city.localeCompare(b.city));
}

function cityNameForWard(ward) {
  const match = String(ward || "").match(/^\s*city of\s+(.+?)\s+(?:wards?|precincts?)\b/i);
  return match ? titleCase(match[1]) : null;
}

function titleCase(value) {
  return String(value)
    .toLowerCase()
    .split(/\s+/)
    .map((part) => (part.length <= 2 ? part.toUpperCase() : `${part[0].toUpperCase()}${part.slice(1)}`))
    .join(" ");
}

function renderVoteShareGraph(county) {
  renderVoteShareGraphForRows(els.voteShareGraph, chartScope(county));
}

function renderVoteShareGraphForRows(target, scope, options = {}) {
  const width = 760;
  const height = options.height || 360;
  const margin = { top: 24, right: 24, bottom: 54, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const trump = scope.rows.map((row) => [row.trump, row.trumpShare]);
  const harris = scope.rows.map((row) => [row.harris, row.harrisShare]);
  if (!scope.rows.length) {
    renderGraphMessage(target, `No review chart rows found for ${scope.label}.`);
    return;
  }
  const all = [...trump, ...harris];
  const xMax = Math.max(10, Math.ceil(Math.max(...all.map((point) => point[0])) / 100) * 100);
  const x = (value) => margin.left + (value / xMax) * plotWidth;
  const y = (value) => margin.top + ((100 - value) / 100) * plotHeight;

  const grid = [0, 25, 50, 75, 100]
    .map(
      (tick) => `
        <line class="graph-grid" x1="${margin.left}" y1="${y(tick)}" x2="${width - margin.right}" y2="${y(tick)}"></line>
        <text class="graph-label" x="${margin.left - 10}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>
      `,
    )
    .join("");
  const xTicks = [0, xMax / 2, xMax]
    .map(
      (tick) => `
        <line class="graph-grid" x1="${x(tick)}" y1="${margin.top}" x2="${x(tick)}" y2="${height - margin.bottom}"></line>
        <text class="graph-label" x="${x(tick)}" y="${height - 24}" text-anchor="middle">${formatNumber(Math.round(tick))}</text>
      `,
    )
    .join("");
  const points = [
    ...trump.map((point) => `<circle cx="${x(point[0])}" cy="${y(point[1])}" r="2" fill="#c84c42" opacity="0.34"><title>Trump: ${formatNumber(point[0])} votes, ${point[1].toFixed(2)}%</title></circle>`),
    ...harris.map((point) => `<circle cx="${x(point[0])}" cy="${y(point[1])}" r="2" fill="#3477bd" opacity="0.34"><title>Harris: ${formatNumber(point[0])} votes, ${point[1].toFixed(2)}%</title></circle>`),
  ].join("");
  const trendLines = [
    regressionLine(trump, x, y, xMax, "#a8302a"),
    regressionLine(harris, x, y, xMax, "#1458a8"),
  ].join("");

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Vote share by vote count scatterplot">
      <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
      ${grid}
      ${xTicks}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      ${points}
      ${trendLines}
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: ${escapeText(activeReviewGraphTitlePrefix())} vote-share chart (${formatNumber(scope.rows.length)} rows)</text>
      ${axisLabel({
        x: width / 2,
        y: height - 8,
        anchor: "middle",
        label: "Candidate votes in ward",
        help: "ELI5: this is how many votes one candidate got in one ward. Example: if Harris got 600 votes in Ward 12, that dot sits at 600 on this axis.",
      })}
      ${axisLabel({
        transform: `translate(16 ${height / 2}) rotate(-90)`,
        anchor: "middle",
        label: "Candidate vote share",
        help: "ELI5: this is the candidate's slice of that ward's vote. Example: 600 Harris votes out of 1,000 total votes is a 60% share.",
      })}
      <circle cx="${width - 150}" cy="18" r="5" fill="#c84c42"></circle>
      <text class="graph-label" x="${width - 139}" y="22">Trump</text>
      <circle cx="${width - 82}" cy="18" r="5" fill="#3477bd"></circle>
      <text class="graph-label" x="${width - 71}" y="22">Harris</text>
    </svg>
  `;
}

function renderDownBallotGraph(county) {
  renderDownBallotGraphForRows(els.downBallotGraph, chartScope(county));
}

function renderDownBallotGraphForRows(target, scope, options = {}) {
  const width = 760;
  const height = options.height || 340;
  const margin = { top: 24, right: 24, bottom: 54, left: 52 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  if (!scope.rows.length) {
    renderGraphMessage(target, `No review chart rows found for ${scope.label}.`);
    return;
  }
  const dropoffValues = scope.rows.flatMap((row) => [
    ["dem", row.demDropoff],
    ["rep", row.repDropoff],
  ]);
  const bins = buildDropoffBins(dropoffValues, -30, 30, 2);
  const maxCount = Math.max(...bins.map((bin) => Math.max(bin.dem, bin.rep)), 1);
  const x = (index) => margin.left + (index / bins.length) * plotWidth;
  const y = (value) => margin.top + (1 - value / maxCount) * plotHeight;
  const barWidth = Math.max(3, plotWidth / bins.length - 2);

  const bars = bins
    .map((bin, index) => {
      const baseX = x(index);
      const demHeight = height - margin.bottom - y(bin.dem);
      const repHeight = height - margin.bottom - y(bin.rep);
      return `
        <rect x="${baseX}" y="${y(bin.dem)}" width="${barWidth / 2}" height="${demHeight}" fill="#3477bd" opacity="0.72"><title>DEM ${bin.start}% to ${bin.start + 2}%: ${bin.dem} wards</title></rect>
        <rect x="${baseX + barWidth / 2}" y="${y(bin.rep)}" width="${barWidth / 2}" height="${repHeight}" fill="#c84c42" opacity="0.72"><title>REP ${bin.start}% to ${bin.start + 2}%: ${bin.rep} wards</title></rect>
      `;
    })
    .join("");
  const zeroX = x(bins.findIndex((bin) => bin.start === 0));
  const yTicks = [0, Math.round(maxCount / 2), maxCount]
    .map(
      (tick) => `
        <line class="graph-grid" x1="${margin.left}" y1="${y(tick)}" x2="${width - margin.right}" y2="${y(tick)}"></line>
        <text class="graph-label" x="${margin.left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>
      `,
    )
    .join("");

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Down-ballot drop-off histogram">
      <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
      ${yTicks}
      <line class="graph-grid" x1="${zeroX}" y1="${margin.top}" x2="${zeroX}" y2="${height - margin.bottom}" stroke-dasharray="5 5"></line>
      ${bars}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: ${escapeText(activeReviewGraphTitlePrefix())} President vs Senate drop-off rates</text>
      <text class="graph-label" x="${margin.left}" y="${height - 24}" text-anchor="start">-30%</text>
      <text class="graph-label" x="${zeroX}" y="${height - 24}" text-anchor="middle">0%</text>
      <text class="graph-label" x="${width - margin.right}" y="${height - 24}" text-anchor="end">+30%</text>
      ${axisLabel({
        x: width / 2,
        y: height - 8,
        anchor: "middle",
        label: "Presidential votes minus Senate votes, as % of presidential votes",
        help: "ELI5: this compares votes for the same party's presidential candidate and Senate candidate in one ward. Example: 1,000 Trump votes and 950 Hovde votes means a 50-vote, 5% drop-off.",
      })}
      ${axisLabel({
        transform: `translate(15 ${height / 2}) rotate(-90)`,
        anchor: "middle",
        label: "Ward count",
        help: "ELI5: this is how many wards landed in that drop-off bucket. Example: if the bar reaches 20, then 20 wards had about that level of drop-off.",
      })}
      <rect x="${width - 160}" y="12" width="12" height="12" fill="#3477bd" opacity="0.72"></rect>
      <text class="graph-label" x="${width - 142}" y="22">DEM</text>
      <rect x="${width - 96}" y="12" width="12" height="12" fill="#c84c42" opacity="0.72"></rect>
      <text class="graph-label" x="${width - 78}" y="22">REP</text>
    </svg>
  `;
}

function renderTurnoutGraph(county) {
  const rows = turnoutRowsForCounty(county);
  const label = turnoutGraphLabel(county, rows);
  if (rows.length) {
    const width = 760;
    const height = 340;
    const margin = { top: 24, right: 24, bottom: 88, left: 52 };
    const bins = buildTurnoutBins(rows);
    const maxCount = Math.max(...bins.map((bin) => bin.count), 1);
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const x = (index) => margin.left + (index / bins.length) * plotWidth;
    const y = (value) => margin.top + (1 - value / maxCount) * plotHeight;
    const barWidth = Math.max(5, plotWidth / bins.length - 3);
    const warningCount = rows.filter((row) => row.warningRequired).length;
    const countyLevelCount = rows.filter((row) => row.sourceLevel === "county").length;
    const graphNotes = [];
    if (warningCount) {
      graphNotes.push(`${formatNumber(warningCount)} rows have denominator warnings.`);
    }
    if (countyLevelCount) {
      graphNotes.push(`${formatNumber(countyLevelCount)} row${countyLevelCount === 1 ? "" : "s"} use county-level totals.`);
    }
    els.turnoutGraphNote.textContent = graphNotes.join(" ");
    const bars = bins
      .map((bin, index) => {
        const barHeight = height - margin.bottom - y(bin.count);
        return `<rect x="${x(index)}" y="${y(bin.count)}" width="${barWidth}" height="${barHeight}" fill="${bin.warning ? "#b7812d" : "#3f8068"}" opacity="0.82"><title>${bin.start}% to ${bin.start + 10}% turnout: ${bin.count} rows${bin.warning ? " with denominator warning" : ""}</title></rect>`;
      })
      .join("");

    els.turnoutGraph.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Turnout histogram">
        <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
        ${bars}
        <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
        <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
        <text class="graph-title" x="${margin.left}" y="18">${label}: turnout histogram (${formatNumber(rows.length)} source rows)</text>
        ${axisLabel({
          x: width / 2,
          y: height - 8,
          anchor: "middle",
          label: "Turnout percent bins",
          help: "ELI5: this groups places by turnout rate. Example: 900 ballots out of 1,000 registered voters goes in the 90% bin.",
        })}
        ${axisLabel({
          transform: `translate(15 ${height / 2}) rotate(-90)`,
          anchor: "middle",
          label: "Source row count",
          help: "ELI5: this is how many imported turnout rows landed in each turnout bucket. Example: if the bar is 12, then 12 wards or local rows had turnout in that range.",
        })}
        <text class="graph-label" x="${margin.left}" y="${height - 64}">0%</text>
        <text class="graph-label" x="${width - margin.right}" y="${height - 64}" text-anchor="end">120%+</text>
      </svg>
    `;
    return;
  }

  els.turnoutGraphNote.textContent =
    activeTurnoutPolicy().warning ||
    "Warning: turnout denominators may be pre-Election-Day or missing. Election Day registration can make those rates look too high.";
  const placeholderWarning = els.turnoutGraphNote.textContent
    ? `<text class="graph-label" x="52" y="244">${escapeText(els.turnoutGraphNote.textContent)}</text>`
    : "";

  els.turnoutGraph.innerHTML = `
    <svg viewBox="0 0 760 260" role="img" aria-label="Turnout histogram placeholder">
      <rect width="760" height="260" fill="#fbfcfd"></rect>
      ${[70, 115, 155, 190].map((x, index) => `<rect x="${x}" y="${160 - index * 25}" width="62" height="${50 + index * 25}" fill="#dce3e8"></rect>`).join("")}
      ${[250, 295, 340, 385].map((x, index) => `<rect x="${x}" y="${65 + index * 20}" width="62" height="${145 - index * 20}" fill="#dce3e8"></rect>`).join("")}
      <line class="graph-axis" x1="52" y1="210" x2="708" y2="210"></line>
      <line class="graph-axis" x1="52" y1="32" x2="52" y2="210"></line>
      <text class="graph-title" x="52" y="24">${label}: turnout histogram will render when denominator data is imported</text>
      ${placeholderWarning}
    </svg>
  `;
}

function turnoutRowsForCounty(county) {
  const data = TURNOUT_DATA;
  if (!data?.rows?.length) {
    return [];
  }
  const normalized = normalizeCounty(county || "");
  return county ? data.rows.filter((row) => normalizeCounty(row.county) === normalized) : data.rows;
}

function turnoutGraphLabel(county, rows) {
  if (!county) {
    return "Statewide imported turnout rows";
  }
  const localAreas = [...new Set(rows.map((row) => row.municipality).filter(Boolean))];
  if (localAreas.length === 1 && normalizeCounty(localAreas[0]) !== normalizeCounty(county)) {
    return `${county} County imported turnout rows (${localAreas[0]} only)`;
  }
  return `${county} County imported turnout rows`;
}

function buildTurnoutBins(rows) {
  const bins = Array.from({ length: 13 }, (_, index) => ({
    start: index * 10,
    count: 0,
    warning: false,
  }));
  rows.forEach((row) => {
    if (typeof row.turnoutPct !== "number") {
      return;
    }
    const index = Math.max(0, Math.min(bins.length - 1, Math.floor(row.turnoutPct / 10)));
    bins[index].count += 1;
    bins[index].warning = bins[index].warning || row.warningRequired;
  });
  return bins;
}

function renderGraphMessage(target, message) {
  target.innerHTML = `
    <svg viewBox="0 0 760 220" role="img" aria-label="Graph status">
      <rect width="760" height="220" fill="#fbfcfd"></rect>
      <text class="graph-warning-text" x="40" y="112">${message}</text>
    </svg>
  `;
}

function svgTextLines(text, { x, y, maxChars, className, lineHeight }) {
  if (!text) {
    return "";
  }
  const words = text.split(/\s+/);
  const lines = [];
  let current = "";

  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });

  if (current) {
    lines.push(current);
  }

  return lines
    .slice(0, 3)
    .map((line, index) => `<text class="${className}" x="${x}" y="${y + index * lineHeight}">${line}</text>`)
    .join("");
}

function axisLabel({ x, y, transform, anchor, label, help }) {
  const position = transform ? `transform="${escapeAttr(transform)}"` : `x="${x}" y="${y}"`;
  return `<text class="graph-label axis-help-label" ${position} text-anchor="${anchor}"><title>${escapeText(help)}</title>${escapeText(label)}</text>`;
}

function technicalTerm(label, definition) {
  return `<span class="technical-term" tabindex="0" data-definition="${escapeAttr(definition)}">${escapeText(label)}</span>`;
}

function applyAuditPreset(presetName) {
  const preset = AUDIT_SIMULATOR_PRESETS[presetName] || AUDIT_SIMULATOR_PRESETS.statewide2024;
  els.auditPreset.value = presetName in AUDIT_SIMULATOR_PRESETS ? presetName : "statewide2024";
  els.auditAreaUnits.value = String(preset.areaUnits);
  els.auditSampleUnits.value = String(preset.sampleUnits);
  els.auditAffectedUnits.value = String(preset.affectedUnits);
  els.auditBallotsPerUnit.value = String(preset.ballotsPerUnit);
  els.auditCandidateShare.value = String(preset.candidateShare);
  els.auditShiftPerUnit.value = String(preset.shiftPerUnit);
  els.auditMinimumMarginMode.checked = false;
  els.auditPresetNote.textContent = preset.note;
  auditSimulationSeed += 7;
  resetAuditTrials();
  renderAuditSimulator();
}

function resetAuditTrials() {
  auditTrialRunToken += 1;
  els.auditRunTrialsBtn.disabled = false;
  els.auditRunTrialsBtn.textContent = "Run 1,000 simplified trials";
  els.auditTrialMissRate.textContent = "Not run yet";
  els.auditTrialProgress.value = 0;
  els.auditTrialProgressWrap.hidden = true;
  els.auditTrialProgressText.textContent = "Ready";
  els.auditTrialSummary.textContent = 'Press "Run 1,000 simplified trials" to repeatedly draw an illustrative audit sample against the current hypothetical affected-unit pattern. This is a simplified model, not a reproduction of WEC\'s constrained selection software.';
}

function runAuditTrials() {
  const areaUnits = clamp(Math.round(Number(els.auditAreaUnits.value) || 4), 4, 4000);
  const sampleUnits = clamp(Math.round(Number(els.auditSampleUnits.value) || 1), 1, Math.min(500, areaUnits));
  const affectedUnits = clamp(Math.round(Number(els.auditAffectedUnits.value) || 1), 1, Math.min(500, areaUnits));
  const affected = new Set(auditAffectedIndices(areaUnits, affectedUnits, auditSimulationSeed, els.auditAffectedDistribution.value));
  const trialCount = 1000;
  let missedTrials = 0;
  let completedTrials = 0;
  auditTrialBatchSeed += 1009;
  auditTrialRunToken += 1;
  const runToken = auditTrialRunToken;
  els.auditRunTrialsBtn.disabled = true;
  els.auditRunTrialsBtn.textContent = "Running 1,000 trials...";
  els.auditTrialMissRate.textContent = "Running...";
  els.auditTrialProgress.value = 0;
  els.auditTrialProgressWrap.hidden = false;
  els.auditTrialProgressText.textContent = "0 of 1,000 trials complete";

  return new Promise((resolve) => {
    const runBatch = () => {
      if (runToken !== auditTrialRunToken) {
        resolve();
        return;
      }
      const batchEnd = Math.min(completedTrials + 20, trialCount);
      for (let trial = completedTrials; trial < batchEnd; trial += 1) {
        const sampled = auditSampleIndices(areaUnits, sampleUnits, auditTrialBatchSeed + trial * 7919);
        if (!sampled.some((index) => affected.has(index))) {
          missedTrials += 1;
        }
      }
      completedTrials = batchEnd;
      els.auditTrialProgress.value = completedTrials;
      els.auditTrialProgressText.textContent = `${formatNumber(completedTrials)} of ${formatNumber(trialCount)} trials complete`;
      if (completedTrials < trialCount) {
        setTimeout(runBatch, 0);
        return;
      }
      const missRate = (missedTrials / trialCount) * 100;
      els.auditTrialMissRate.textContent = `${missRate.toFixed(1)}%`;
      els.auditTrialSummary.textContent = `${formatNumber(missedTrials)} of ${formatNumber(trialCount)} simplified audit draws missed every one of the ${formatNumber(affectedUnits)} hypothetical affected units. ${formatNumber(trialCount - missedTrials)} draws touched at least one affected unit and would be marked for follow-up in this model.`;
      els.auditRunTrialsBtn.disabled = false;
      els.auditRunTrialsBtn.textContent = "Run 1,000 simplified trials";
      resolve();
    };
    setTimeout(runBatch, 0);
  });
}

function renderAuditSimulator() {
  const areaUnits = clamp(Math.round(Number(els.auditAreaUnits.value) || 4), 4, 4000);
  const sampleUnits = clamp(Math.round(Number(els.auditSampleUnits.value) || 1), 1, Math.min(500, areaUnits));
  const affectedUnits = clamp(Math.round(Number(els.auditAffectedUnits.value) || 1), 1, Math.min(500, areaUnits));
  const ballotsPerUnit = clamp(Math.round(Number(els.auditBallotsPerUnit.value) || 100), 100, 2000);
  const candidateShare = clamp(Math.round(Number(els.auditCandidateShare.value) || 50), 35, 65);
  const sliderShiftPerUnit = clamp(Math.round(Number(els.auditShiftPerUnit.value) || 0), 0, 500);
  const minimumShiftPerUnit = Math.ceil(MIN_SWITCHES_TO_MOVE_STATEWIDE_MARGIN / affectedUnits);
  const shiftPerUnit = els.auditMinimumMarginMode.checked ? minimumShiftPerUnit : sliderShiftPerUnit;
  const areaBallots = areaUnits * ballotsPerUnit;
  const candidateABaseline = Math.round(areaBallots * (candidateShare / 100));
  const candidateBBaseline = areaBallots - candidateABaseline;
  const candidateABaselinePerAffectedUnit = Math.round(ballotsPerUnit * (candidateShare / 100));
  const feasibleShiftPerUnit = Math.min(shiftPerUnit, candidateABaselinePerAffectedUnit);
  els.auditAreaUnits.value = String(areaUnits);
  els.auditSampleUnits.value = String(sampleUnits);
  els.auditAffectedUnits.value = String(affectedUnits);
  els.auditBallotsPerUnit.value = String(ballotsPerUnit);
  els.auditCandidateShare.value = String(candidateShare);
  els.auditShiftPerUnit.value = String(sliderShiftPerUnit);
  els.auditShiftPerUnit.disabled = els.auditMinimumMarginMode.checked;
  els.auditAreaUnitsValue.textContent = formatNumber(areaUnits);
  els.auditSampleUnitsValue.textContent = formatNumber(sampleUnits);
  els.auditAffectedUnitsValue.textContent = formatNumber(affectedUnits);
  els.auditBallotsPerUnitValue.textContent = formatNumber(ballotsPerUnit);
  els.auditCandidateShareValue.textContent = `${candidateShare}%`;
  els.auditShiftValue.textContent = els.auditMinimumMarginMode.checked
    ? `${formatNumber(shiftPerUnit)} needed`
    : formatNumber(shiftPerUnit);
  const minimumFeasibilityNote = shiftPerUnit > candidateABaselinePerAffectedUnit
    ? ` With the current ${formatNumber(ballotsPerUnit)} ballots per unit and ${candidateShare}% Candidate A baseline, each affected unit only has about ${formatNumber(candidateABaselinePerAffectedUnit)} Candidate A votes available to switch. Increase affected units, ballots per unit, or Candidate A baseline share to make this switch model feasible.`
    : "";
  els.auditMinimumMarginNote.textContent = els.auditMinimumMarginMode.checked
    ? `Minimum threshold mode is on: Wisconsin's certified Trump margin was ${formatNumber(STATEWIDE_2024_PRESIDENTIAL_MARGIN)} votes. Switching ${formatNumber(MIN_SWITCHES_TO_MOVE_STATEWIDE_MARGIN)} votes from Candidate A to Candidate B would move that margin by ${formatNumber(MIN_SWITCHES_TO_MOVE_STATEWIDE_MARGIN * 2)} votes. Spread equally across ${formatNumber(affectedUnits)} hypothetical affected units, that is ${formatNumber(shiftPerUnit)} switched vote${shiftPerUnit === 1 ? "" : "s"} per unit.${minimumFeasibilityNote}`
    : `Manual mode: use the slider to choose the hypothetical switched votes per affected unit. Turning on minimum threshold mode calculates the smallest equal per-unit amount needed to move the certified statewide margin.`;
  const distribution = els.auditAffectedDistribution.value in AUDIT_DISTRIBUTION_NOTES ? els.auditAffectedDistribution.value : "concentrated";
  els.auditAffectedDistribution.value = distribution;
  els.auditDistributionNote.textContent = AUDIT_DISTRIBUTION_NOTES[distribution];

  const missProbability = auditSampleMissProbability(areaUnits, sampleUnits, affectedUnits);
  const sampled = new Set(auditSampleIndices(areaUnits, sampleUnits, auditSimulationSeed));
  const affected = new Set(auditAffectedIndices(areaUnits, affectedUnits, auditSimulationSeed, distribution));
  const overlap = [...affected].filter((index) => sampled.has(index));
  const missed = overlap.length === 0;
  els.auditMissProbability.textContent = `${(missProbability * 100).toFixed(2)}%`;
  els.auditTouchProbability.textContent = `${((1 - missProbability) * 100).toFixed(2)}%`;
  const shiftedVotes = Math.min(affectedUnits * feasibleShiftPerUnit, candidateABaseline);
  const candidateAAltered = candidateABaseline - shiftedVotes;
  const candidateBAltered = candidateBBaseline + shiftedVotes;
  els.auditShiftedVotes.textContent = formatNumber(shiftedVotes);
  els.auditDrawResult.textContent = missed ? "Missed pattern" : "Touched pattern";
  els.auditDrawResult.className = missed ? "audit-missed" : "audit-touched";
  els.auditUnitGrid.classList.toggle("dense", areaUnits > 500);
  els.auditUnitGrid.innerHTML = Array.from({ length: areaUnits }, (_, index) => {
    const isSampled = sampled.has(index);
    const isAffected = affected.has(index);
    const state = isSampled && isAffected ? "overlap" : isAffected ? "affected" : isSampled ? "sampled" : "";
    const label = isSampled && isAffected
      ? "Sampled and hypothetical affected unit"
      : isAffected
        ? "Hypothetical affected unit, not sampled"
        : isSampled
          ? "Sampled unit"
          : "Unit not sampled";
    return `<span class="audit-unit ${state}" title="${label}" aria-label="${label}"></span>`;
  }).join("");
  const distributionLabel = AUDIT_DISTRIBUTION_LABELS[distribution];
  els.auditScenarioSummary.textContent = missed
    ? `In this one rerolled ${distributionLabel} illustration, none of the ${formatNumber(sampleUnits)} sampled units intersect the ${formatNumber(affectedUnits)} hypothetical affected units. The simplified model therefore marks this draw as missed.`
    : `In this one rerolled ${distributionLabel} illustration, ${formatNumber(overlap.length)} sampled unit${overlap.length === 1 ? "" : "s"} intersect the ${formatNumber(affectedUnits)} hypothetical affected units. The simplified model therefore marks this draw as detected for follow-up.`;
  els.auditVoteComparison.innerHTML = `
    <article>
      <span>Illustrative area ballots</span>
      <strong>${formatNumber(areaBallots)}</strong>
    </article>
    <article>
      <span>Paper-baseline Candidate A</span>
      <strong>${formatNumber(candidateABaseline)}</strong>
      <small>Candidate B: ${formatNumber(candidateBBaseline)}</small>
    </article>
    <article>
      <span>Hypothetical altered-report Candidate A</span>
      <strong>${formatNumber(candidateAAltered)}</strong>
      <small>Candidate B: ${formatNumber(candidateBAltered)}</small>
    </article>
    <article>
      <span>Illustrative margin movement</span>
      <strong>${formatNumber(shiftedVotes * 2)}</strong>
      <small>Each shifted vote changes the two-candidate margin by two votes.</small>
    </article>
  `;
}

function auditSampleMissProbability(areaUnits, sampleUnits, affectedUnits) {
  if (sampleUnits > areaUnits - affectedUnits) {
    return 0;
  }
  let probability = 1;
  for (let index = 0; index < sampleUnits; index += 1) {
    probability *= (areaUnits - affectedUnits - index) / (areaUnits - index);
  }
  return probability;
}

function auditAffectedIndices(areaUnits, affectedUnits, seed, distribution) {
  const offset = Math.floor(auditSeededValue(seed + 97) * areaUnits);
  if (distribution === "spread" || distribution === "highVolume") {
    return Array.from({ length: affectedUnits }, (_, index) =>
      Math.floor((offset + index * (areaUnits / affectedUnits)) % areaUnits),
    );
  }
  return Array.from({ length: affectedUnits }, (_, index) => (offset + index) % areaUnits);
}

function auditSampleIndices(areaUnits, sampleUnits, seed) {
  const indices = Array.from({ length: areaUnits }, (_, index) => index);
  const random = auditSeededRandom(seed);
  for (let index = indices.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [indices[index], indices[swapIndex]] = [indices[swapIndex], indices[index]];
  }
  return indices.slice(0, sampleUnits);
}

function auditSeededValue(seed) {
  return auditSeededRandom(seed)();
}

function auditSeededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let mixed = value;
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

function regressionLine(points, xScale, yScale, xMax, color) {
  const regression = linearRegression(points);
  const y1 = regression.intercept;
  const y2 = regression.intercept + regression.slope * xMax;
  return `<line x1="${xScale(0)}" y1="${yScale(y1)}" x2="${xScale(xMax)}" y2="${yScale(y2)}" stroke="${color}" stroke-width="3" opacity="0.92"></line>`;
}

function linearRegression(points) {
  const n = points.length;
  const meanX = points.reduce((sum, point) => sum + point[0], 0) / n;
  const meanY = points.reduce((sum, point) => sum + point[1], 0) / n;
  let numerator = 0;
  let denominator = 0;

  points.forEach((point) => {
    numerator += (point[0] - meanX) * (point[1] - meanY);
    denominator += (point[0] - meanX) ** 2;
  });

  const slope = denominator === 0 ? 0 : numerator / denominator;
  return { slope, intercept: meanY - slope * meanX };
}

function buildDropoffBins(values, min, max, step) {
  const bins = [];
  for (let start = min; start < max; start += step) {
    bins.push({ start, dem: 0, rep: 0 });
  }

  values.forEach(([party, value]) => {
    const clamped = Math.max(min, Math.min(max - 0.001, value));
    const index = Math.floor((clamped - min) / step);
    bins[index][party] += 1;
  });

  return bins;
}

function downloadGraph(graphId) {
  const svg = document.querySelector(`#${graphId} svg`);
  if (!svg) {
    return;
  }
  const blob = new Blob([svg.outerHTML], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${graphId}-${selectedCounty ? normalizeCounty(selectedCounty).replaceAll(" ", "-") : "statewide"}.svg`;
  link.click();
  URL.revokeObjectURL(url);
}

function voteShareByVoteCountProxy() {
  const threshold = 0.35;
  const trumpCorrelation = pearson(
    RESULTS.map((row) => row.trump),
    RESULTS.map((row) => row.trumpPct),
  );
  const harrisCorrelation = pearson(
    RESULTS.map((row) => row.harris),
    RESULTS.map((row) => row.harrisPct),
  );

  return {
    trumpCorrelation,
    harrisCorrelation,
    threshold,
    flagged: Math.abs(trumpCorrelation) >= threshold || Math.abs(harrisCorrelation) >= threshold,
  };
}

function renderCandidateBreakdown(row = null) {
  const title = row ? `${row.county} County` : "Statewide";
  const values = CANDIDATE_LABELS.map((candidate) => ({
    ...candidate,
    votes: row ? row[candidate.key] : sumCandidate(candidate.key),
  }));
  const total = values.reduce((sum, candidate) => sum + candidate.votes, 0);

  els.breakdownTitle.textContent = title;
  els.breakdownTotal.textContent = `${formatNumber(total)} other votes`;
  els.candidateBreakdown.innerHTML = values
    .map(
      (candidate) => `
        <div class="candidate-chip" title="${candidate.label}">
          <span>${candidate.label}</span>
          <strong>${formatNumber(candidate.votes)}</strong>
        </div>
      `,
    )
    .join("");
}

function popupHtml(row) {
  const otherCandidateRows = CANDIDATE_LABELS.map(
    (candidate) => `<dt>${escapeText(candidate.label)}</dt><dd>${formatNumber(row[candidate.key] || 0)}</dd>`,
  ).join("");
  return `
    <div class="county-popup">
      <h3>${escapeText(row.county)} County</h3>
      <dl>
        <dt>Winner</dt><dd>${winnerLabel(row)}</dd>
        <dt>Margin</dt><dd>${formatNumber(Math.abs(row.margin))}</dd>
        <dt>Trump</dt><dd>${formatNumber(row.trump)} (${row.trumpPct.toFixed(2)}%)</dd>
        <dt>Harris</dt><dd>${formatNumber(row.harris)} (${row.harrisPct.toFixed(2)}%)</dd>
        <dt>Other</dt><dd>${formatNumber(row.other)} (${row.otherPct.toFixed(2)}%)</dd>
        ${otherCandidateRows}
        <dt>Total</dt><dd>${formatNumber(row.total)}</dd>
      </dl>
    </div>
  `;
}

function exportCsv() {
  const sourcePlan = activeSourcePlan();
  const candidateHeaders = CANDIDATE_LABELS.map((candidate) => candidate.label);
  const headers = [
    "County",
    "Review Flag",
    "Review Notes",
    "Trump",
    "Trump %",
    "Harris",
    "Harris %",
    ...candidateHeaders,
    "Other",
    "Other %",
    "Margin",
    "Margin %",
    "Total",
    "Source URL",
    "Source Last Modified UTC",
    "Source Timestamp Basis",
  ];
  const rows = RESULTS.map((row) => {
    const review = countyReviewSummary(row.county);
    return [
      row.county,
      review.flag ? "Review flag" : "",
      review.notes,
      row.trump,
      row.trumpPct,
      row.harris,
      row.harrisPct,
      ...CANDIDATE_LABELS.map((candidate) => row[candidate.key]),
      row.other,
      row.otherPct,
      row.margin,
      row.marginPct,
      row.total,
      sourcePlan.certifiedResults.sourceUrl,
      sourcePlan.certifiedResults.sourceLastModifiedUtc,
      sourcePlan.certifiedResults.sourceTimestampBasis,
    ];
  });
  downloadCsv(`${activeExportSlug()}-president-county-results.csv`, headers, rows);
}

function exportCurrentReviewCsv() {
  const sourcePlan = activeSourcePlan();
  const scope = reviewScopeData();
  const review = reviewSummaryForRows(scope.label, scope.rows, "all");
  const headers = [
    "scope",
    "county",
    "review_flag",
    "review_notes",
    "ward",
    "trump",
    "harris",
    "total",
    "trump_share",
    "harris_share",
    "dem_dropoff",
    "rep_dropoff",
    "row_note",
    "ward_detail_source_url",
    "ward_detail_source_last_modified_utc",
    "ward_detail_source_timestamp_basis",
  ];
  const rows = scope.rows
    .map((row) => ({ row, score: wardReviewScore(row) }))
    .sort((a, b) => b.score - a.score || b.row.total - a.row.total)
    .map(({ row }) => [
      scope.label,
      row.county,
      review.flag ? "Flagged for review" : "No current review flag",
      review.notes,
      row.ward,
      row.trump,
      row.harris,
      row.total,
      row.trumpShare,
      row.harrisShare,
      row.demDropoff,
      row.repDropoff,
      wardReviewNote(row),
      sourcePlan.wardDetail.sourceUrl,
      sourcePlan.wardDetail.sourceLastModifiedUtc,
      sourcePlan.wardDetail.sourceTimestampBasis,
    ]);
  const filename = `${activeExportSlug()}-review-${slugify(scope.label)}.csv`;
  downloadCsv(filename, headers, rows);
}

function exportFlaggedAreasCsv() {
  const sourcePlan = activeSourcePlan();
  const headers = [
    "area",
    "type",
    "county",
    "ward_rows",
    "severity_score",
    "review_reasons",
    "trump_vote_share_r",
    "harris_vote_share_r",
    "dem_average_dropoff_pct",
    "rep_average_dropoff_pct",
    "dem_outlier_rows",
    "rep_outlier_rows",
    "outlier_trigger_rows",
    "not_proof_note",
    "ward_detail_source_url",
    "ward_detail_source_last_modified_utc",
    "ward_detail_source_timestamp_basis",
  ];
  const rows = flaggedAreaRows().map((item) => {
    const metrics = item.review.metrics;
    return [
      item.label,
      item.typeLabel,
      item.county,
      metrics.rowCount,
      item.severity.toFixed(3),
      item.review.notes,
      metrics.trumpCorrelation,
      metrics.harrisCorrelation,
      metrics.demAverageDropoff,
      metrics.repAverageDropoff,
      metrics.demOutliers,
      metrics.repOutliers,
      metrics.outlierTrigger,
      "Statistical review flag only; not proof of tampering.",
      sourcePlan.wardDetail.sourceUrl,
      sourcePlan.wardDetail.sourceLastModifiedUtc,
      sourcePlan.wardDetail.sourceTimestampBasis,
    ];
  });
  downloadCsv(`${activeExportSlug()}-flagged-areas-summary.csv`, headers, rows);
}

function exportCoverageCsv() {
  const sourcePlan = activeSourcePlan();
  const headers = [
    "county",
    "vote_results",
    "turnout_status",
    "turnout_rows",
    "local_area_count",
    "county_level_rows",
    "warning_rows",
    "turnout_sources",
    "certified_result_source_url",
    "certified_result_last_modified_utc",
    "ward_detail_source_url",
    "ward_detail_last_modified_utc",
    "source_timestamp_basis",
    "notes",
  ];
  const rows = turnoutCoverageRows().map((row) => [
    row.county,
    `Official ${activeStateConfig().authority} county and local vote totals present`,
    row.status,
    row.rows || 0,
    row.localAreaCount || 0,
    row.countyLevelRows || 0,
    row.warnings || 0,
    (row.sources || []).join(" "),
    sourcePlan.certifiedResults.sourceUrl,
    sourcePlan.certifiedResults.sourceLastModifiedUtc,
    sourcePlan.wardDetail.sourceUrl,
    sourcePlan.wardDetail.sourceLastModifiedUtc,
    sourcePlan.certifiedResults.sourceTimestampBasis,
    row.status === "missing" ? "No turnout denominator rows imported" : row.detail,
  ]);
  downloadCsv(`${activeExportSlug()}-data-coverage.csv`, headers, rows);
}

function exportSourceCsv() {
  const headers = [
    "category",
    "file_or_local_data",
    "source_url",
    "source_last_modified_utc",
    "source_timestamp_basis",
    "used_for",
    "confidence_or_status",
  ];
  const sourceRows = activeSourceInventory().map((source) => [
    source.category,
    source.file,
    source.sourceUrl,
    source.sourceLastModifiedUtc || "",
    source.sourceTimestampBasis || "",
    source.usedFor,
    source.confidence,
  ]);
  const checkedRows = activeCheckedNotUsable().map((item) => [
    `Checked but not imported - ${item.county}`,
    item.missingFields,
    item.sourceUrl,
    "",
    "Not captured",
    "Reviewed for turnout analysis but not imported.",
    item.reason,
  ]);
  downloadCsv(`${activeExportSlug()}-source-inventory.csv`, headers, [...sourceRows, ...checkedRows]);
}

function exportSourcePlanCsv() {
  const plan = selectedSourcePlan();
  if (!plan) {
    return;
  }
  const headers = [
    "state",
    "election_year",
    "office",
    "county",
    "certified_result_source",
    "certified_result_url",
    "certified_result_last_modified_utc",
    "certified_result_timestamp_basis",
    "ward_detail_source",
    "ward_detail_url",
    "ward_detail_last_modified_utc",
    "ward_detail_timestamp_basis",
    "turnout_status",
    "turnout_sources",
    "turnout_source_timestamp_basis",
    "turnout_warning_rows",
    "follow_up",
  ];
  const rows = sourceCountyRows(plan).map((row) => [
    plan.state,
    plan.electionYear,
    plan.office,
    row.county,
    row.certifiedSource.title,
    row.certifiedSource.sourceUrl,
    row.certifiedSource.sourceLastModifiedUtc,
    row.certifiedSource.sourceTimestampBasis,
    row.wardSource.title,
    row.wardSource.sourceUrl,
    row.wardSource.sourceLastModifiedUtc,
    row.wardSource.sourceTimestampBasis,
    row.turnoutStatus,
    row.turnoutSources.join(" "),
    plan.turnout.sourceTimestampBasis,
    row.turnoutWarnings,
    row.checkedNotImported
      ? `Checked but not imported: ${row.checkedNotImported.reason}`
      : row.turnoutStatus === "missing"
        ? "Needs county or municipal turnout denominator source"
        : "Imported",
  ]);
  downloadCsv(`${plan.code.toLowerCase()}-${plan.electionYear}-source-plan.csv`, headers, rows);
}

function downloadCsv(filename, headers, rows) {
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function filteredRows() {
  const query = els.search.value.trim().toLowerCase();
  return RESULTS.filter((row) => row.county.toLowerCase().includes(query));
}

function winnerLabel(row) {
  return row.margin >= 0 ? "Trump" : "Harris";
}

function sumCandidate(key) {
  return RESULTS.reduce((sum, row) => sum + row[key], 0);
}

function pearson(xs, ys) {
  const n = xs.length;
  const meanX = xs.reduce((sum, value) => sum + value, 0) / n;
  const meanY = ys.reduce((sum, value) => sum + value, 0) / n;
  let numerator = 0;
  let xDenominator = 0;
  let yDenominator = 0;

  for (let index = 0; index < n; index += 1) {
    const xDelta = xs[index] - meanX;
    const yDelta = ys[index] - meanY;
    numerator += xDelta * yDelta;
    xDenominator += xDelta * xDelta;
    yDenominator += yDelta * yDelta;
  }

  return numerator / Math.sqrt(xDenominator * yDenominator);
}

function pearsonSafe(xs, ys) {
  if (xs.length < 2 || ys.length < 2 || xs.length !== ys.length) {
    return 0;
  }
  const value = pearson(xs, ys);
  return Number.isFinite(value) ? value : 0;
}

function average(values) {
  const valid = values.filter((value) => typeof value === "number" && Number.isFinite(value));
  if (!valid.length) {
    return 0;
  }
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function normalizeCounty(name = "") {
  return name
    .toLowerCase()
    .replace(/\s+county$/, "")
    .replace(/\./g, "")
    .replace(/^saint\s+/, "st ")
    .replace(/\s+/g, " ")
    .trim();
}

function slugify(value) {
  return normalizeCounty(value).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "scope";
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatSigned(value) {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${formatNumber(Math.abs(value))}`;
}

function formatSourceHost(source) {
  try {
    return new URL(source).hostname.replace(/^www\./, "");
  } catch {
    return source;
  }
}

function escapeAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeText(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

loadConfiguredStateScripts()
  .then(() => {
    registerConfiguredStates();
    return init();
  })
  .catch((error) => {
    console.error(error);
    registerConfiguredStates();
    init();
  });
