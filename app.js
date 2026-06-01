const RESULTS = window.WI_ELECTION_APP_DATA.presidentCountyResults;
const CANDIDATE_LABELS = window.WI_ELECTION_APP_DATA.candidateLabels;
const LOCAL_COUNTIES_GEOJSON = window.WI_COUNTIES_GEOJSON;
const HISTORICAL_BASELINE = window.WI_HISTORICAL_BASELINE;
const HISTORICAL_PRIMARY_SERIES_IDS = [
  "ltsb-harmonized-2012-president",
  "ltsb-harmonized-2016-president",
  "ltsb-harmonized-2020-president",
  "wec-native-2024-president",
];
const HISTORICAL_SERIES_LABELS = {
  "ltsb-harmonized-2012-president": "2012 LTSB harmonized wards",
  "ltsb-harmonized-2016-president": "2016 LTSB harmonized wards",
  "ltsb-harmonized-2020-president": "2020 LTSB harmonized wards",
  "wec-native-2016-president-original": "2016 WEC native original canvass",
  "wec-native-2016-president-recount": "2016 WEC native recount",
  "wec-native-2024-president": "2024 WEC native reporting units",
};

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

const SOURCE_INVENTORY = [
  {
    category: "Presidential county results",
    file: "data/County by County Report_POTUS.pdf; data/president-county-results.json",
    sourceUrl: "https://elections.wi.gov/sites/default/files/documents/County%20by%20County%20Report_POTUS.pdf",
    usedFor: "Map shading, county table, statewide totals, candidate breakdown, CSV export, selected-county details.",
    confidence: "Official WEC certified county result report.",
  },
  {
    category: "U.S. Senate county results",
    file: "data/County by County Report_US Senate.pdf",
    sourceUrl: "https://elections.wi.gov/sites/default/files/documents/County%20by%20County%20Report_US%20Senate_1.pdf",
    usedFor: "County-level verification context for down-ballot comparison.",
    confidence: "Official WEC certified county result report.",
  },
  {
    category: "Ward federal/state results",
    file: "data/Ward by Ward Report Federal and State Contests.xlsx; data/ward-analysis.json; data/eta-data.js",
    sourceUrl:
      "https://web.archive.org/web/20241130045633id_/https://elections.wi.gov/sites/default/files/documents/Ward%20by%20Ward%20Report%20by%20Congressional%20District_November%205%202024%20General%20Election_Federal%20and%20State%20Contests.xlsx",
    usedFor: "ETA-style ward scatterplots, down-ballot histograms, selected-county graph filtering.",
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
    confidence: "Older LTSB rows are harmonized comparison rows; 2024 rows are native official WEC reporting-unit rows.",
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

const DEFAULT_REVIEW_POLICY = {
  minWardRows: 10,
  voteShareCorrelationThreshold: ETA_ANALYSIS.voteShare.threshold,
  downBallotAverageThresholdPct: 2,
  outlierThresholdPct: ETA_ANALYSIS.downBallot.outlierThresholdPct,
  minCandidateVotes: ETA_ANALYSIS.downBallot.minCandidateVotes,
};

const COUNTY_REVIEW_POLICY = { ...DEFAULT_REVIEW_POLICY };

const byCounty = new Map(RESULTS.map((row) => [normalizeCounty(row.county), row]));
const countyReviewCache = new Map();
const stateTotals = RESULTS.reduce(
  (acc, row) => {
    acc.trump += row.trump;
    acc.harris += row.harris;
    acc.other += row.other;
    acc.total += row.total;
    return acc;
  },
  { trump: 0, harris: 0, other: 0, total: 0 },
);

let collected = [];
let map;
let geoLayer;
let colorMode = "winner";
let selectedCounty = null;
let citySplitData = [];
let flaggedAreaSummaryRows = [];

const els = {
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
  reviewFlagSummary: document.querySelector("#reviewFlagSummary"),
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
};

function init() {
  initializeThemeToggle();
  organizeWorkspacePanels();
  renderSummary();
  renderEtaTests();
  renderCoverageTracker();
  renderConfidenceSummary();
  renderCoverageTable();
  renderCheckedNotUsable();
  renderEtaGraphs();
  renderCitySplitOptions();
  setReviewControlValues();
  renderFlaggedAreasSummary();
  renderReviewDrilldown();
  renderCandidateBreakdown();
  renderHistoricalComparison();
  renderTable(RESULTS);
  wireControls();
  setAppTab(initialTabName(), { updateHash: false });
  initMap();
  applyInitialReviewRoute();
  collectCounties({ quick: true });
}

function wireControls() {
  els.collectBtn.addEventListener("click", () => collectCounties({ quick: false }));
  els.mapBtn.addEventListener("click", loadCountyBoundaries);
  els.exportBtn.addEventListener("click", exportCsv);
  els.coverageCsvBtn.addEventListener("click", exportCoverageCsv);
  els.sourceCsvBtn.addEventListener("click", exportSourceCsv);
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
    const nextHash = tabName === "review" && currentRoute.tabName === "review" && currentRoute.query
      ? `#review?${currentRoute.query}`
      : `#${tabName}`;
    window.history.replaceState(null, "", nextHash);
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
  const validTabs = ["dashboard", "review", "history", "data", "methodology", "about"];
  return {
    tabName: validTabs.includes(hashTab) ? hashTab : "dashboard",
    query,
    params: new URLSearchParams(query),
  };
}

function activeTabName() {
  return Array.from(els.appTabs).find((button) => button.classList.contains("active"))?.dataset.appTab || "dashboard";
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

  els.statusText.textContent = "Loading local Wisconsin county boundaries...";
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

  const rows = window.ETA_WARD_CHARTS?.metadata?.rows?.filter((row) => normalizeCounty(row.county) === key) || [];
  const result = reviewSummaryForRows(`${county} County`, rows, "all");
  countyReviewCache.set(key, result);
  return result;
}

function reviewSummaryForRows(label, rows, mode = "all") {
  const rowLabel = mode === "voteShare" ? "vote-share graph" : mode === "downBallot" ? "down-ballot graph" : "review";
  if (rows.length < COUNTY_REVIEW_POLICY.minWardRows) {
    return {
      flag: false,
      title: `${label} has fewer than ${COUNTY_REVIEW_POLICY.minWardRows} WEC ward rows in this analysis, so the app does not apply a ${rowLabel} flag.`,
      notes: `Not enough ward rows for ${rowLabel} flag`,
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
        "Bigger ward vote totals move with candidate vote share strongly enough to pass the review threshold. This is the ETA-style scatterplot question: do larger reporting units lean differently than smaller ones?",
    });
  }
  if (
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
  if ((mode === "all" || mode === "downBallot") && demOutliers + repOutliers >= outlierTrigger) {
    reasons.push({
      type: "Down-ballot outliers",
      summary: `drop-off outlier count crossed threshold: DEM ${demOutliers}, REP ${repOutliers}, trigger ${outlierTrigger}`,
      plain:
        "Enough ward rows have unusually large President-versus-Senate differences to pass the outlier-count threshold. That does not prove anything by itself, but it identifies rows to inspect first.",
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
  const allRows = window.ETA_WARD_CHARTS?.metadata?.rows || [];

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
  const allRows = window.ETA_WARD_CHARTS?.metadata?.rows || [];
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
  if (!els.flaggedAreaRows || !window.ETA_WARD_CHARTS) {
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
  window.history.replaceState(null, "", `#review?${params.toString()}`);
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
  if (!els.reviewSummaryGrid || !window.ETA_WARD_CHARTS) {
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
      <p>${formatNumber(metrics.rowCount)} WEC ward rows under the current scope.</p>
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
            <strong>${test.name}</strong>
            <p>${test.detail}</p>
            ${test.warning ? `<p class="eta-warning">${test.warning}</p>` : ""}
          </div>
        </article>
      `,
    )
    .join("");
}

function etaTestResults() {
  const voteShareFlagged =
    Math.abs(ETA_ANALYSIS.voteShare.trumpCorrelation) >= COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold ||
    Math.abs(ETA_ANALYSIS.voteShare.harrisCorrelation) >= COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold;
  const downBallotFlagged =
    Math.abs(ETA_ANALYSIS.downBallot.repDropPct) >= COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct ||
    Math.abs(ETA_ANALYSIS.downBallot.demDropPct) >= COUNTY_REVIEW_POLICY.downBallotAverageThresholdPct ||
    ETA_ANALYSIS.downBallot.repOutlierWards + ETA_ANALYSIS.downBallot.demOutlierWards > 50;
  const turnoutCoverage = turnoutCoverageRows();
  const turnoutRows = window.WI_TURNOUT_DATA?.metadata?.rows || 0;
  const turnoutWarningRows = window.WI_TURNOUT_DATA?.metadata?.warningRows || 0;
  const partialCount = turnoutCoverage.filter((row) => row.status === "partial").length;
  const missingCount = turnoutCoverage.filter((row) => row.status === "missing").length;

  return [
    {
      name: "Down-ballot difference",
      status: downBallotFlagged ? "Flag" : "Pass",
      statusClass: downBallotFlagged ? "flag" : "pass",
      detail: `Ward-level President vs U.S. Senate check run on ${formatNumber(ETA_ANALYSIS.wardRows)} matched WEC ward rows. DEM presidential-vs-Senate drop-off: ${formatSigned(ETA_ANALYSIS.downBallot.demDropVotes)} votes (${ETA_ANALYSIS.downBallot.demDropPct.toFixed(2)}%). REP presidential-vs-Senate drop-off: ${formatSigned(ETA_ANALYSIS.downBallot.repDropVotes)} votes (${ETA_ANALYSIS.downBallot.repDropPct.toFixed(2)}%). Outlier wards over ${ETA_ANALYSIS.downBallot.outlierThresholdPct}% drop-off with at least ${ETA_ANALYSIS.downBallot.minCandidateVotes} presidential votes: DEM ${ETA_ANALYSIS.downBallot.demOutlierWards}, REP ${ETA_ANALYSIS.downBallot.repOutlierWards}.`,
    },
    {
      name: "Vote share by vote count",
      status: voteShareFlagged ? "Flag" : "Pass",
      statusClass: voteShareFlagged ? "flag" : "pass",
      detail: `Ward-level check run on ${formatNumber(ETA_ANALYSIS.wardRows)} WEC ward rows. Trump r=${ETA_ANALYSIS.voteShare.trumpCorrelation.toFixed(3)}, Harris r=${ETA_ANALYSIS.voteShare.harrisCorrelation.toFixed(3)} between candidate vote count and candidate vote share; app review threshold is |r| >= ${COUNTY_REVIEW_POLICY.voteShareCorrelationThreshold.toFixed(2)}.`,
    },
    {
      name: "Turnout analysis",
      status: turnoutRows ? "Partial" : TURNOUT_SOURCE_POLICY.status,
      statusClass: turnoutRows ? "partial" : "needs-data",
      detail: turnoutRows
        ? `Partial turnout analysis is running for ${formatNumber(turnoutRows)} imported source rows from county/municipal reports. Coverage: ${partialCount} partial ${partialCount === 1 ? "county" : "counties"}, ${missingCount} counties still missing. Required fields for more imports: ${TURNOUT_SOURCE_POLICY.requiredFields.join(", ")}.`
        : `Not run. The app has official ward vote totals, but it does not yet have registered-voter or eligible-voter counts needed to calculate turnout. County/municipal canvass PDFs are the planned free source for those denominators. Required fields: ${TURNOUT_SOURCE_POLICY.requiredFields.join(", ")}.`,
      warning: turnoutWarningRows
        ? `${formatNumber(turnoutWarningRows)} imported turnout rows use pre-Election-Day or unknown registration denominators. ${TURNOUT_SOURCE_POLICY.warning}`
        : TURNOUT_SOURCE_POLICY.warning,
    },
    {
      name: "Official-result completeness",
      status: "Pass",
      statusClass: "pass",
      detail:
        "All 72 counties are present, detailed candidate/write-in totals sum to each county's Other total, and statewide totals match the WEC report.",
    },
  ];
}

function renderCoverageTracker() {
  const rows = turnoutCoverageRows();
  const partial = rows.filter((row) => row.status === "partial").length;
  const complete = rows.filter((row) => row.status === "complete").length;
  const missing = rows.filter((row) => row.status === "missing").length;
  const turnoutRows = window.WI_TURNOUT_DATA?.metadata?.rows || 0;
  const warningRows = window.WI_TURNOUT_DATA?.metadata?.warningRows || 0;

  els.coverageSummary.textContent = `${formatNumber(turnoutRows)} turnout source rows imported. ${complete} complete counties, ${partial} partial counties, ${missing} missing counties. ${warningRows ? `${formatNumber(warningRows)} rows carry denominator warnings.` : ""}`;
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
  const turnoutRows = window.WI_TURNOUT_DATA?.metadata?.rows || 0;
  const warningRows = window.WI_TURNOUT_DATA?.metadata?.warningRows || 0;
  const partial = rows.filter((row) => row.status === "partial").length;
  const missing = rows.filter((row) => row.status === "missing").length;

  els.dataVersionSummary.textContent = `Data version: ${DATA_VERSION_LABEL}. Current bundle has ${formatNumber(RESULTS.length)} WEC county result rows, ${formatNumber(ETA_ANALYSIS.wardRows)} WEC ward-analysis rows, and ${formatNumber(turnoutRows)} imported turnout rows across ${partial} counties. ${missing} counties still need turnout denominators.`;
  els.confidenceBadges.innerHTML = [
    confidenceBadge("Official WEC county totals", "strong"),
    confidenceBadge("Official WEC ward vote graphs", "strong"),
    confidenceBadge("Accurate calculations, limited conclusions", "review"),
    confidenceBadge(`${formatNumber(turnoutRows)} partial turnout rows`, "partial"),
    confidenceBadge(`${formatNumber(warningRows)} denominator-warning rows`, warningRows ? "warning" : "strong"),
    confidenceBadge(`${missing} turnout counties missing`, missing ? "missing" : "strong"),
  ].join("");
}

function renderCoverageTable() {
  const rows = turnoutCoverageRows();
  const partial = rows.filter((row) => row.status === "partial").length;
  const missing = rows.filter((row) => row.status === "missing").length;

  els.coverageTableSummary.textContent = `${partial} counties have imported turnout rows; ${missing} still need denominator data. Vote-result coverage is complete for all ${RESULTS.length} counties.`;
  els.coverageTableRows.innerHTML = rows
    .map((row) => {
      const sourceLinks = row.sources?.length
        ? row.sources.map((source, index) => `<a href="${source}" target="_blank" rel="noreferrer">Turnout ${index + 1}: ${formatSourceHost(source)}</a>`).join("")
        : "<span>No turnout denominator source imported</span>";
      const warning = row.status === "missing" ? "No turnout rows" : row.warnings ? `Yes - ${formatNumber(row.warnings)} row${row.warnings === 1 ? "" : "s"}` : "No warning rows";
      return `
        <tr>
          <td>${row.county}</td>
          <td><span class="confidence-pill strong">Official WEC</span></td>
          <td>
            <span class="confidence-pill ${row.status === "missing" ? "missing" : "partial"}">${row.status === "missing" ? "Missing" : "Partial"}</span>
            <p class="coverage-cell-note">${row.status === "missing" ? "No turnout denominator rows imported" : row.detail}</p>
          </td>
          <td>${warning}</td>
          <td class="coverage-table-sources"><span>WEC vote files</span>${sourceLinks}</td>
        </tr>
      `;
    })
    .join("");
}

function renderCheckedNotUsable() {
  els.checkedNotUsableList.innerHTML = CHECKED_NOT_USABLE.map(
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

function renderHistoricalComparison() {
  if (!HISTORICAL_BASELINE?.series?.length) {
    renderGraphMessage(els.historicalTrendGraph, "Historical baseline data is not loaded.");
    renderGraphMessage(els.historicalScatterGraph, "Historical baseline data is not loaded.");
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
    els.historicalSeriesSelect.value = "ltsb-harmonized-2012-president";
  }

  const county = els.historicalCountySelect.value;
  const scopeLabel = county ? `${county} County` : "Statewide";
  const primarySeries = HISTORICAL_PRIMARY_SERIES_IDS.map((id) => historicalSeriesById(id)).filter(Boolean);
  els.historicalScopeTitle.textContent = `${scopeLabel} comparison`;
  els.historicalSummary.textContent = `${scopeLabel}: comparing ${primarySeries.length} presidential elections. Older years use visibly labeled LTSB harmonized ward rows; 2024 uses native official WEC reporting-unit rows.`;
  els.historicalTableRows.innerHTML = primarySeries.map((series) => historicalTableRow(series, county)).join("");
  renderHistoricalTrendGraph(primarySeries, county);
  renderHistoricalScatterGraph(historicalSeriesById(els.historicalSeriesSelect.value), county);
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
  const sourceClass = series.sourceClass === "nativeOfficial" ? "native" : "harmonized";
  const sourceLabel = sourceClass === "native" ? "Native official WEC" : "LTSB harmonized";
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
      ${axisLabel({ x: width / 2, y: height - 10, anchor: "middle", label: "Presidential election year", help: "Each x-axis value is one Wisconsin presidential general election year." })}
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
  const sourceNote = series.sourceClass === "nativeOfficial" ? "native official WEC rows" : "LTSB harmonized comparison rows";
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

function confidenceBadge(label, tone) {
  return `<span class="confidence-pill ${tone}">${label}</span>`;
}

function turnoutCoverageRows() {
  const rows = window.WI_TURNOUT_DATA?.rows || [];
  const byCounty = new Map();
  rows.forEach((row) => {
    const key = normalizeCounty(row.county);
    const current = byCounty.get(key) || { rows: 0, municipalities: new Set(), warnings: 0, countyLevelRows: 0, sources: new Set() };
    current.rows += 1;
    current.municipalities.add(row.municipality || "Unknown municipality");
    if (row.sourceUrl) {
      current.sources.add(row.sourceUrl);
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
      return {
        county: countyRow.county,
        status: "missing",
        detail: "No turnout denominator rows imported",
      };
    }
    return {
      county: countyRow.county,
      status: "partial",
      detail: `${formatNumber(data.rows)} turnout row${data.rows === 1 ? "" : "s"} from ${data.municipalities.size} local area${data.municipalities.size === 1 ? "" : "s"}${data.countyLevelRows ? `; ${formatNumber(data.countyLevelRows)} county-level row${data.countyLevelRows === 1 ? "" : "s"}` : ""}; ${formatNumber(data.warnings)} warning rows`,
      rows: data.rows,
      warnings: data.warnings,
      localAreaCount: data.municipalities.size,
      countyLevelRows: data.countyLevelRows,
      sources: [...data.sources],
    };
  });
}

function renderEtaGraphs(county = selectedCounty) {
  if (!window.ETA_WARD_CHARTS) {
    renderGraphMessage(els.voteShareGraph, "Ward-level chart data is not loaded.");
    renderGraphMessage(els.downBallotGraph, "Ward-level chart data is not loaded.");
    renderGraphMessage(els.turnoutGraph, TURNOUT_SOURCE_POLICY.warning);
    return;
  }

  renderVoteShareGraph(county);
  renderDownBallotGraph(county);
  renderTurnoutGraph(county);
}

function chartScope(county) {
  const normalized = normalizeCounty(county || "");
  const metadata = window.ETA_WARD_CHARTS?.metadata || {};
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
    els.citySplitSummary.textContent = "No city ward groups were found in the WEC ward-level data.";
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
  els.citySplitSummary.textContent = `${cityLabel}: ${formatNumber(split.cityRows.length)} city ward rows compared with ${formatNumber(split.restRows.length)} rest-of-county ward rows. Uses official WEC ward vote totals.`;
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
  const rows = window.ETA_WARD_CHARTS?.metadata?.rows || [];
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
  const match = String(ward || "").match(/^\s*city of\s+(.+?)\s+wards?\b/i);
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
    renderGraphMessage(target, `No ward-level chart rows found for ${scope.label}.`);
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
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: WEC ward vote-share chart (${formatNumber(scope.rows.length)} wards)</text>
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
    renderGraphMessage(target, `No ward-level chart rows found for ${scope.label}.`);
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
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: WEC ward President vs Senate drop-off rates</text>
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
    "Warning: turnout denominators may be pre-Election-Day or missing. Election Day registration can make those rates look too high.";

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
  const data = window.WI_TURNOUT_DATA;
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
  return `<text class="graph-label axis-help-label" ${position} text-anchor="${anchor}"><title>${escapeText(help)}</title>${escapeText(label)} ?</text>`;
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
  return `
    <div class="county-popup">
      <h3>${row.county} County</h3>
      <dl>
        <dt>Winner</dt><dd>${winnerLabel(row)}</dd>
        <dt>Margin</dt><dd>${formatNumber(Math.abs(row.margin))}</dd>
        <dt>Trump</dt><dd>${formatNumber(row.trump)} (${row.trumpPct.toFixed(2)}%)</dd>
        <dt>Harris</dt><dd>${formatNumber(row.harris)} (${row.harrisPct.toFixed(2)}%)</dd>
        <dt>Other</dt><dd>${formatNumber(row.other)} (${row.otherPct.toFixed(2)}%)</dd>
        <dt>Kennedy</dt><dd>${formatNumber(row.kennedy)}</dd>
        <dt>Stein</dt><dd>${formatNumber(row.stein)}</dd>
        <dt>Oliver</dt><dd>${formatNumber(row.oliver)}</dd>
        <dt>Total</dt><dd>${formatNumber(row.total)}</dd>
      </dl>
    </div>
  `;
}

function exportCsv() {
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
    ];
  });
  downloadCsv("wisconsin-2024-president-county-results.csv", headers, rows);
}

function exportCurrentReviewCsv() {
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
    ]);
  const filename = `wisconsin-2024-review-${slugify(scope.label)}.csv`;
  downloadCsv(filename, headers, rows);
}

function exportFlaggedAreasCsv() {
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
    ];
  });
  downloadCsv("wisconsin-2024-flagged-areas-summary.csv", headers, rows);
}

function exportCoverageCsv() {
  const headers = [
    "county",
    "vote_results",
    "turnout_status",
    "turnout_rows",
    "local_area_count",
    "county_level_rows",
    "warning_rows",
    "turnout_sources",
    "notes",
  ];
  const rows = turnoutCoverageRows().map((row) => [
    row.county,
    "Official WEC county and ward vote totals present",
    row.status,
    row.rows || 0,
    row.localAreaCount || 0,
    row.countyLevelRows || 0,
    row.warnings || 0,
    (row.sources || []).join(" "),
    row.status === "missing" ? "No turnout denominator rows imported" : row.detail,
  ]);
  downloadCsv("wisconsin-2024-data-coverage.csv", headers, rows);
}

function exportSourceCsv() {
  const headers = ["category", "file_or_local_data", "source_url", "used_for", "confidence_or_status"];
  const sourceRows = SOURCE_INVENTORY.map((source) => [
    source.category,
    source.file,
    source.sourceUrl,
    source.usedFor,
    source.confidence,
  ]);
  const checkedRows = CHECKED_NOT_USABLE.map((item) => [
    `Checked but not imported - ${item.county}`,
    item.missingFields,
    item.sourceUrl,
    "Reviewed for turnout analysis but not imported.",
    item.reason,
  ]);
  downloadCsv("wisconsin-2024-source-inventory.csv", headers, [...sourceRows, ...checkedRows]);
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
  return name.toLowerCase().replace(/\s+county$/, "").replace(/\./g, "").replace(/\s+/g, " ").trim();
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

init();
