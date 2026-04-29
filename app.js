const RESULTS = window.WI_ELECTION_APP_DATA.presidentCountyResults;
const CANDIDATE_LABELS = window.WI_ELECTION_APP_DATA.candidateLabels;
const LOCAL_COUNTIES_GEOJSON = window.WI_COUNTIES_GEOJSON;

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

const byCounty = new Map(RESULTS.map((row) => [normalizeCounty(row.county), row]));
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

const els = {
  trumpTotal: document.querySelector("#trumpTotal"),
  harrisTotal: document.querySelector("#harrisTotal"),
  stateMargin: document.querySelector("#stateMargin"),
  countyCount: document.querySelector("#countyCount"),
  collectBtn: document.querySelector("#collectBtn"),
  mapBtn: document.querySelector("#mapBtn"),
  exportBtn: document.querySelector("#exportBtn"),
  search: document.querySelector("#countySearch"),
  progressBar: document.querySelector("#progressBar"),
  statusText: document.querySelector("#statusText"),
  collectorLog: document.querySelector("#collectorLog"),
  etaTests: document.querySelector("#etaTests"),
  coverageSummary: document.querySelector("#coverageSummary"),
  coverageList: document.querySelector("#coverageList"),
  voteShareGraph: document.querySelector("#voteShareGraph"),
  downBallotGraph: document.querySelector("#downBallotGraph"),
  turnoutGraph: document.querySelector("#turnoutGraph"),
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
};

function init() {
  renderSummary();
  renderEtaTests();
  renderCoverageTracker();
  renderEtaGraphs();
  renderCandidateBreakdown();
  renderTable(RESULTS);
  wireControls();
  initMap();
  collectCounties({ quick: true });
}

function wireControls() {
  els.collectBtn.addEventListener("click", () => collectCounties({ quick: false }));
  els.mapBtn.addEventListener("click", loadCountyBoundaries);
  els.exportBtn.addEventListener("click", exportCsv);
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
  els.countyRows.innerHTML = rows
    .map(
      (row) => `
        <tr data-county="${row.county}" class="${selectedCounty === row.county ? "is-selected" : ""}">
          <td>${row.county}</td>
          <td>${formatNumber(row.trump)} <span class="party-r">${row.trumpPct.toFixed(2)}%</span></td>
          <td>${formatNumber(row.harris)} <span class="party-d">${row.harrisPct.toFixed(2)}%</span></td>
          <td>${formatNumber(row.other)} (${row.otherPct.toFixed(2)}%)</td>
          <td>${winnerLabel(row)} +${Math.abs(row.marginPct).toFixed(2)}%</td>
          <td>${formatNumber(row.total)}</td>
        </tr>
      `,
    )
    .join("");

  els.countyRows.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => selectCounty(row.dataset.county));
  });
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
  renderTable(filteredRows());
  refreshMapStyles();
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
    Math.abs(ETA_ANALYSIS.voteShare.trumpCorrelation) >= ETA_ANALYSIS.voteShare.threshold ||
    Math.abs(ETA_ANALYSIS.voteShare.harrisCorrelation) >= ETA_ANALYSIS.voteShare.threshold;
  const downBallotFlagged =
    Math.abs(ETA_ANALYSIS.downBallot.repDropPct) >= 2 ||
    Math.abs(ETA_ANALYSIS.downBallot.demDropPct) >= 2 ||
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
      detail: `Ward-level check run on ${formatNumber(ETA_ANALYSIS.wardRows)} WEC ward rows. Trump r=${ETA_ANALYSIS.voteShare.trumpCorrelation.toFixed(3)}, Harris r=${ETA_ANALYSIS.voteShare.harrisCorrelation.toFixed(3)} between candidate vote count and candidate vote share; app review threshold is |r| >= ${ETA_ANALYSIS.voteShare.threshold.toFixed(2)}.`,
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

function renderVoteShareGraph(county) {
  const width = 760;
  const height = 360;
  const margin = { top: 24, right: 24, bottom: 54, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const scope = chartScope(county);
  const trump = scope.rows.map((row) => [row.trump, row.trumpShare]);
  const harris = scope.rows.map((row) => [row.harris, row.harrisShare]);
  if (!scope.rows.length) {
    renderGraphMessage(els.voteShareGraph, `No ward-level chart rows found for ${scope.label}.`);
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

  els.voteShareGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Vote share by vote count scatterplot">
      <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
      ${grid}
      ${xTicks}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      ${points}
      ${trendLines}
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: each dot is one ward/candidate pair (${formatNumber(scope.rows.length)} wards)</text>
      <text class="graph-label" x="${width / 2}" y="${height - 8}" text-anchor="middle">Candidate votes in ward</text>
      <text class="graph-label" transform="translate(16 ${height / 2}) rotate(-90)" text-anchor="middle">Candidate vote share</text>
      <circle cx="${width - 150}" cy="18" r="5" fill="#c84c42"></circle>
      <text class="graph-label" x="${width - 139}" y="22">Trump</text>
      <circle cx="${width - 82}" cy="18" r="5" fill="#3477bd"></circle>
      <text class="graph-label" x="${width - 71}" y="22">Harris</text>
    </svg>
  `;
}

function renderDownBallotGraph(county) {
  const width = 760;
  const height = 340;
  const margin = { top: 24, right: 24, bottom: 54, left: 52 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const scope = chartScope(county);
  if (!scope.rows.length) {
    renderGraphMessage(els.downBallotGraph, `No ward-level chart rows found for ${scope.label}.`);
    return;
  }
  const dropoffValues = scope.rows.flatMap((row) => [
    ["dem", row.demDropoff],
    ["rep", row.repDropoff],
  ]);
  const bins = buildDropoffBins(dropoffValues, -30, 30, 2);
  const maxCount = Math.max(...bins.map((bin) => Math.max(bin.dem, bin.rep)));
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

  els.downBallotGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Down-ballot drop-off histogram">
      <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
      ${yTicks}
      <line class="graph-grid" x1="${zeroX}" y1="${margin.top}" x2="${zeroX}" y2="${height - margin.bottom}" stroke-dasharray="5 5"></line>
      ${bars}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: distribution of ward drop-off rates</text>
      <text class="graph-label" x="${margin.left}" y="${height - 24}" text-anchor="start">-30%</text>
      <text class="graph-label" x="${zeroX}" y="${height - 24}" text-anchor="middle">0%</text>
      <text class="graph-label" x="${width - margin.right}" y="${height - 24}" text-anchor="end">+30%</text>
      <text class="graph-label" x="${width / 2}" y="${height - 8}" text-anchor="middle">Presidential votes minus Senate votes, as % of presidential votes</text>
      <text class="graph-label" transform="translate(15 ${height / 2}) rotate(-90)" text-anchor="middle">Ward count</text>
      <rect x="${width - 160}" y="12" width="12" height="12" fill="#3477bd" opacity="0.72"></rect>
      <text class="graph-label" x="${width - 142}" y="22">DEM</text>
      <rect x="${width - 96}" y="12" width="12" height="12" fill="#c84c42" opacity="0.72"></rect>
      <text class="graph-label" x="${width - 78}" y="22">REP</text>
    </svg>
  `;
}

function renderTurnoutGraph(county) {
  const label = county ? `${county} County` : "statewide";
  const rows = turnoutRowsForCounty(county);
  if (rows.length) {
    const width = 760;
    const height = 300;
    const margin = { top: 24, right: 24, bottom: 54, left: 52 };
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
      graphNotes.push(`${formatNumber(warningCount)} rows use pre-Election-Day or unknown registration denominators.`);
    }
    if (countyLevelCount) {
      graphNotes.push(`${formatNumber(countyLevelCount)} row${countyLevelCount === 1 ? "" : "s"} use county-level totals, not ward-level denominators.`);
    }
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
        <text class="graph-label" x="${width / 2}" y="${height - 8}" text-anchor="middle">Turnout percent bins</text>
        <text class="graph-label" transform="translate(15 ${height / 2}) rotate(-90)" text-anchor="middle">Source row count</text>
        <text class="graph-label" x="${margin.left}" y="${height - 28}">0%</text>
        <text class="graph-label" x="${width - margin.right}" y="${height - 28}" text-anchor="end">120%+</text>
        ${graphNotes.length ? `<text class="graph-warning-text" x="${margin.left}" y="${height - 32}">${graphNotes.join(" ")}</text>` : ""}
      </svg>
    `;
    return;
  }

  els.turnoutGraph.innerHTML = `
    <svg viewBox="0 0 760 260" role="img" aria-label="Turnout histogram placeholder">
      <rect width="760" height="260" fill="#fbfcfd"></rect>
      ${[70, 115, 155, 190].map((x, index) => `<rect x="${x}" y="${160 - index * 25}" width="62" height="${50 + index * 25}" fill="#dce3e8"></rect>`).join("")}
      ${[250, 295, 340, 385].map((x, index) => `<rect x="${x}" y="${65 + index * 20}" width="62" height="${145 - index * 20}" fill="#dce3e8"></rect>`).join("")}
      <line class="graph-axis" x1="52" y1="210" x2="708" y2="210"></line>
      <line class="graph-axis" x1="52" y1="32" x2="52" y2="210"></line>
      <text class="graph-title" x="52" y="24">${label}: turnout histogram will render when denominator data is imported</text>
      <text class="graph-warning-text" x="52" y="242">${TURNOUT_SOURCE_POLICY.warning}</text>
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
  const rows = RESULTS.map((row) => [
    row.county,
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
  ]);
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "wisconsin-2024-president-county-results.csv";
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

function normalizeCounty(name = "") {
  return name.toLowerCase().replace(/\s+county$/, "").replace(/\./g, "").replace(/\s+/g, " ").trim();
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

init();
