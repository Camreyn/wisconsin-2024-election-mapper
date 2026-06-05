import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const indexHtml = fs.readFileSync(path.join(root, "index.html"), "utf8");
const publicCopy = [
  indexHtml,
  fs.readFileSync(path.join(root, "app.js"), "utf8"),
  fs.readFileSync(path.join(root, "README.md"), "utf8"),
  fs.readFileSync(path.join(root, "package.json"), "utf8"),
].join("\n");

class MockClassList {
  constructor(initial = []) {
    this.values = new Set(initial);
  }

  add(value) {
    this.values.add(value);
  }

  remove(value) {
    this.values.delete(value);
  }

  toggle(value, enabled) {
    if (enabled) this.add(value);
    else this.remove(value);
  }

  contains(value) {
    return this.values.has(value);
  }
}

let currentElementLookup = null;
let currentVmContext = null;

class MockElement {
  constructor(id = "") {
    this.id = id;
    this.attributes = new Map();
    this.children = [];
    this.classList = new MockClassList();
    this.dataset = {};
    this.hidden = false;
    this.options = [];
    this.style = {};
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this._innerHTML = "";
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this.options = [...this._innerHTML.matchAll(/<option value="([^"]*)"/g)].map((match) => ({ value: match[1] }));
    if (this.options.length && !this.options.some((option) => option.value === this.value)) {
      this.value = this.options[0].value;
    }
  }

  get innerHTML() {
    return this._innerHTML;
  }

  get lastElementChild() {
    return this.children.at(-1);
  }

  addEventListener() {}

  append(child) {
    this.children.push(child);
    if (child.src && currentVmContext) {
      const scriptPath = child.src.replace(/^\.\//, "");
      vm.runInContext(fs.readFileSync(path.join(root, scriptPath), "utf8"), currentVmContext, { filename: scriptPath });
      child.onload?.();
    }
  }

  insertBefore(child) {
    this.children.push(child);
  }

  prepend(child) {
    child.remove = () => {
      this.children = this.children.filter((item) => item !== child);
    };
    this.children.unshift(child);
  }

  querySelector(selector) {
    return currentElementLookup ? currentElementLookup(selector) : new MockElement(selector.replace(/^#/, ""));
  }

  querySelectorAll() {
    return [];
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  scrollIntoView() {}

  click() {}

  remove() {}
}

function createAppHarness({ hash = "", search = "" } = {}) {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) {
      elements.set(selector, new MockElement(selector.replace(/^#/, "")));
    }
    return elements.get(selector);
  }

  const appTabs = ["dashboard", "review", "history", "data", "sources", "methodology", "audit", "about"].map((name) => {
    const tab = new MockElement();
    tab.dataset.appTab = name;
    if (name === "dashboard") tab.classList.add("active");
    return tab;
  });
  const tabPanels = ["dashboard", "review", "history", "data", "sources", "methodology", "audit", "about"].map((name) => {
    const panel = new MockElement(`${name}Panel`);
    panel.hidden = name !== "dashboard";
    return panel;
  });
  const modeButtons = ["winner", "margin", "turnout"].map((mode) => {
    const button = new MockElement();
    button.dataset.mode = mode;
    return button;
  });
  const document = {
    body: new MockElement("body"),
    documentElement: { dataset: { theme: "light" } },
    createElement: () => new MockElement(),
    querySelector: (selector) => selector.startsWith("script[") ? null : element(selector),
    querySelectorAll: (selector) => {
      if (selector === "[data-app-tab]") return appTabs;
      if (selector === ".tab-panel") return tabPanels;
      if (selector === ".mode-button") return modeButtons;
      return [];
    },
  };
  currentElementLookup = element;
  const storage = new Map();
  const location = {
    hash,
    search,
    href: `file:///index.html${search}${hash}`,
  };
  const context = {
    Blob,
    URL,
    URLSearchParams,
    console,
    document,
    Intl,
    localStorage: {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
    },
    navigator: {},
    setTimeout,
    clearTimeout,
  };
  context.window = context;
  context.window.location = location;
  context.window.history = {
    replaceState: (_state, _title, url) => {
      const nextUrl = new URL(String(url), location.href);
      location.href = nextUrl.href;
      location.search = nextUrl.search;
      location.hash = nextUrl.hash;
    },
  };
  vm.createContext(context);
  currentVmContext = context;

  for (const file of [
    "data/app-data.js",
    "data/mn-app-data.js",
    "data/eta-data.js",
    "data/wi-counties.js",
    "data/mn-counties.js",
    "data/turnout-data.js",
    "data/historical-data.js",
    "data/state-registry.js",
    "app.js",
  ]) {
    vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), context, { filename: file });
  }

  return { context, element, document, storage, appTabs, tabPanels };
}

const wiHarness = createAppHarness({ hash: "#history" });
const { context, element, document, storage, tabPanels } = wiHarness;

await new Promise((resolve) => setTimeout(resolve, 400));
await vm.runInContext(`runAuditTrials()`, context);

const checks = {
  sidebarExplorerTitle: indexHtml.includes("Upper Midwest Presidential Results Explorer"),
  sidebarCurrentMapScope: indexHtml.includes("2024 certified results"),
  sidebarHistoricalAction: indexHtml.includes('data-open-tab="history">Compare years</button>'),
  plainLanguageGlossary: indexHtml.includes("What the technical terms mean"),
  harmonizedDefinition: indexHtml.includes("Adjusted onto one common map so different election years can be compared."),
  technicalTermTooltips: indexHtml.includes('class="technical-term"') && indexHtml.includes('data-definition='),
  noEtaStyleLabels: !publicCopy.toLowerCase().includes("eta-style"),
  historyTabVisible: tabPanels.find((panel) => panel.id === "historyPanel").hidden === false,
  countyOptions: element("#historicalCountySelect").options.length,
  seriesOptions: element("#historicalSeriesSelect").options.length,
  historicalTableRows: (element("#historicalTableRows").innerHTML.match(/<tr>/g) || []).length,
  trendGraphSvg: element("#historicalTrendGraph").innerHTML.includes("<svg"),
  scatterGraphSvg: element("#historicalScatterGraph").innerHTML.includes("<svg"),
  distributionGraphSvg: element("#historicalDistributionGraph").innerHTML.includes("<svg"),
  distributionGraphComesFirst: indexHtml.indexOf('id="historicalDistributionGraph"') < indexHtml.indexOf('id="historicalTrendGraph"'),
  historicalAxisLabelsAreClean: !element("#historicalTrendGraph").innerHTML.includes("year ?") && !element("#historicalScatterGraph").innerHTML.includes("row ?"),
  auditTabPresent: indexHtml.includes('data-app-tab="audit"') && indexHtml.includes('id="auditPanel"'),
  auditSidebarAction: indexHtml.includes('data-open-tab="audit">Open Audit Simulator</button>'),
  auditStatewidePreset: indexHtml.includes('<option value="statewide2024">Wisconsin 2024 statewide WEC configuration</option>'),
  auditTrialsButton: indexHtml.includes('id="auditRunTrialsBtn"') && indexHtml.includes("Run 1,000 simplified trials"),
  auditDistributionControl: indexHtml.includes('id="auditAffectedDistribution"')
    && indexHtml.includes('<option value="concentrated">')
    && indexHtml.includes('<option value="spread">')
    && indexHtml.includes('<option value="highVolume">'),
  appStateSelectorPresent: indexHtml.includes('id="appStateSelect"'),
  appStateOptions: element("#appStateSelect").options.length,
  appStateSyncedWithSourcePlanner: element("#appStateSelect").value === "WI" && element("#sourceStateSelect").value === "WI",
  sourcePlannerTabPresent: indexHtml.includes('data-app-tab="sources"') && indexHtml.includes('id="sourcesPanel"'),
  sourcePlannerSidebarAction: indexHtml.includes('data-open-tab="sources">Open Source Planner</button>'),
  sourcePlannerStateOptions: element("#sourceStateSelect").options.length,
  sourcePlannerWisconsinTitle: element("#sourceStateTitle").textContent === "Wisconsin 2024 President",
  sourcePlannerCountyRows: (element("#sourceCountyRows").innerHTML.match(/<tr>/g) || []).length,
  sourcePlannerWaukeshaChecked: element("#sourceCountyRows").innerHTML.includes("Checked but not imported")
    && element("#sourceCountyRows").innerHTML.includes("Waukesha"),
  sourcePlannerTimestamps: element("#sourceCountyRows").innerHTML.includes("2024-11-27T21:31:27Z")
    && element("#sourceCountyRows").innerHTML.includes("2024-11-27T21:35:53Z"),
  sourceTimestampNotesVisible: indexHtml.includes("WEC file Last-Modified header: 2024-11-27T21:31:27Z"),
  auditDistributionNote: element("#auditDistributionNote").textContent.includes("grid is not a geographic map"),
  auditSpreadPattern: vm.runInContext(`auditAffectedIndices(100, 8, 17, "spread").join(",") !== auditAffectedIndices(100, 8, 17, "concentrated").join(",")`, context),
  auditHighVolumeDisclaimer: vm.runInContext(`AUDIT_DISTRIBUTION_NOTES.highVolume.includes("cannot identify real high-volume audit units")`, context),
  auditMinimumMarginControl: indexHtml.includes('id="auditMinimumMarginMode"') && indexHtml.includes("Use minimum needed to move Wisconsin margin"),
  auditMissProbability: element("#auditMissProbability").textContent,
  auditTrialMissRate: /^\d+\.\d%$/.test(element("#auditTrialMissRate").textContent),
  auditTrialProgress: element("#auditTrialProgress").value,
  auditTrialProgressText: element("#auditTrialProgressText").textContent,
  auditTrialSummary: element("#auditTrialSummary").textContent.includes("of 1,000 simplified audit draws missed every one"),
  auditGridUnits: (element("#auditUnitGrid").innerHTML.match(/class="audit-unit/g) || []).length,
  auditVoteComparison: element("#auditVoteComparison").innerHTML.includes("3,271,210") && element("#auditVoteComparison").innerHTML.includes("Illustrative margin movement"),
};
const registryStates = context.window.STATE_APP_REGISTRY?.states || [];
checks.appStateOptionsMatchRegistry = element("#appStateSelect").options.length === registryStates.length + 1;
checks.sourcePlannerStateOptionsMatchRegistry = element("#sourceStateSelect").options.length === registryStates.length + 1;
vm.runInContext(`els.auditMinimumMarginMode.checked = true; renderAuditSimulator();`, context);
checks.auditMinimumMarginShift = element("#auditShiftValue").textContent === "490 needed";
checks.auditMinimumMarginNote = element("#auditMinimumMarginNote").textContent.includes("29,397")
  && element("#auditMinimumMarginNote").textContent.includes("14,699")
  && element("#auditMinimumMarginNote").textContent.includes("only has about 439");
checks.auditMinimumMarginTotal = element("#auditShiftedVotes").textContent === "13,170";
vm.runInContext(`
  setActiveState("MN", { updateControls: true });
  renderSourcePlanner();
  renderHistoricalComparison();
  renderFlaggedAreasSummary();
  renderReviewDrilldown();
  renderEtaGraphs();
  renderCitySplitOptions();
  renderEtaTests();
`, context);
checks.minnesotaStateSelected = element("#appStateSelect").value === "MN" && element("#sourceStateSelect").value === "MN";
checks.minnesotaSourcePlannerTitle = element("#sourceStateTitle").textContent === "Minnesota 2024 President";
checks.minnesotaSourcePlannerCountyRows = (element("#sourceCountyRows").innerHTML.match(/<tr>/g) || []).length;
checks.minnesotaSourcePlannerTimestamp = element("#sourceCountyRows").innerHTML.includes("2025-02-14T17:22:26Z");
checks.minnesotaSourcePlannerLoaded = element("#sourceCountyRows").innerHTML.includes("Loaded")
  && element("#sourceCountyRows").innerHTML.includes("Minnesota SOS precinct federal/state spreadsheet");
checks.minnesotaMapReady = element("#sourcePlanBadges").innerHTML.includes("Map ready");
checks.minnesotaHistoricalLoaded = (element("#historicalTableRows").innerHTML.match(/<tr>/g) || []).length === 4
  && element("#historicalSummary").textContent.toLowerCase().includes("native official minnesota secretary of state county rows")
  && element("#historicalTrendGraph").innerHTML.includes("<svg");
checks.minnesotaHistoricalCopyClean = element("#historicalDistributionGraph").innerHTML.includes("native official county rows")
  && !element("#historicalDistributionGraph").innerHTML.includes("LTSB harmonized rows");
checks.minnesotaHistoricalSeriesOptions = element("#historicalSeriesSelect").options.length === 4;
checks.minnesotaReviewRowsLoaded = element("#reviewSummaryGrid").innerHTML.includes("Minnesota SOS precinct rows");
checks.minnesotaVoteShareGraph = element("#voteShareGraph").innerHTML.includes("Minnesota SOS precinct vote-share chart");
checks.minnesotaDownBallotGraph = element("#downBallotGraph").innerHTML.includes("Minnesota SOS precinct President vs Senate drop-off rates");
checks.minnesotaTurnoutLoaded = element("#etaTests").innerHTML.includes("4,103 imported source rows")
  && element("#turnoutGraph").innerHTML.includes("turnout histogram");
checks.minnesotaStaticSourceTimestampVisible = indexHtml.includes("Minnesota SOS workbook Last-Modified header: 2025-02-14T17:22:26Z");
checks.minnesotaSaintLouisGeometryMatchesResults =
  vm.runInContext(`normalizeCounty("Saint Louis") === normalizeCounty("St. Louis")`, context);

const mnQueryHarness = createAppHarness({ search: "?state=MN" });
const ndQueryHarness = createAppHarness({ search: "?state=ND" });
const miQueryHarness = createAppHarness({ search: "?state=MI" });
const mnHashHarness = createAppHarness({ hash: "#sources?state=MN" });
await new Promise((resolve) => setTimeout(resolve, 450));
checks.directMinnesotaQuerySelected =
  mnQueryHarness.element("#appStateSelect").value === "MN" &&
  mnQueryHarness.element("#sourceStateSelect").value === "MN";
checks.directMinnesotaQuerySummary =
  mnQueryHarness.element("#sourceStateTitle").textContent === "Minnesota 2024 President" &&
  (mnQueryHarness.element("#sourceCountyRows").innerHTML.match(/<tr>/g) || []).length === 87;
checks.directMinnesotaHashSelected =
  mnHashHarness.element("#appStateSelect").value === "MN" &&
  mnHashHarness.element("#sourceStateSelect").value === "MN";
checks.directMinnesotaHashSourcesTab =
  mnHashHarness.tabPanels.find((panel) => panel.id === "sourcesPanel").hidden === false &&
  mnHashHarness.element("#sourceStateTitle").textContent === "Minnesota 2024 President";
checks.directNorthDakotaQuerySelected =
  ndQueryHarness.element("#appStateSelect").value === "ND" &&
  ndQueryHarness.element("#sourceStateSelect").value === "ND";
checks.directNorthDakotaQuerySummary =
  ndQueryHarness.element("#sourceStateTitle").textContent === "North Dakota 2024 President" &&
  (ndQueryHarness.element("#sourceCountyRows").innerHTML.match(/<tr>/g) || []).length === 53;
checks.directNorthDakotaMapReady = ndQueryHarness.element("#sourcePlanBadges").innerHTML.includes("Map ready");
checks.directNorthDakotaHistoricalLoaded =
  ndQueryHarness.element("#sourcePlanBadges").innerHTML.includes("Historical baseline ready") &&
  (ndQueryHarness.element("#historicalTableRows").innerHTML.match(/<tr>/g) || []).length === 4 &&
  ndQueryHarness.element("#historicalSummary").textContent.toLowerCase().includes("native official north dakota secretary of state county rows");
checks.directMichiganQuerySelected =
  miQueryHarness.element("#appStateSelect").value === "MI" &&
  miQueryHarness.element("#sourceStateSelect").value === "MI";
checks.directMichiganQuerySummary =
  miQueryHarness.element("#sourceStateTitle").textContent === "Michigan 2024 President" &&
  (miQueryHarness.element("#sourceCountyRows").innerHTML.match(/<tr>/g) || []).length === 83;
checks.directMichiganMapReady = miQueryHarness.element("#sourcePlanBadges").innerHTML.includes("Map ready");
checks.directMichiganTurnoutLoaded =
  miQueryHarness.element("#sourcePlanBadges").innerHTML.includes("Turnout ready") &&
  miQueryHarness.element("#sourcePlanBadges").innerHTML.includes("83 turnout counties imported") &&
  miQueryHarness.element("#turnoutGraph").innerHTML.includes("turnout histogram");
checks.directMichiganHistoricalLoaded =
  miQueryHarness.element("#sourcePlanBadges").innerHTML.includes("Historical baseline ready") &&
  (miQueryHarness.element("#historicalTableRows").innerHTML.match(/<tr>/g) || []).length === 4 &&
  miQueryHarness.element("#historicalSummary").textContent.toLowerCase().includes("native official michigan voter information center county rows");
checks.directMichiganReviewDatasetLoaded =
  vm.runInContext(`WARD_CHARTS.metadata.rows.length`, miQueryHarness.context) === 4428;
checks.directMichiganReviewRowsLoaded =
  miQueryHarness.element("#reviewSummaryGrid").innerHTML.includes("12 Michigan MVIC precinct rows");
checks.directMichiganReviewTableLoaded =
  miQueryHarness.element("#reviewWardRows").innerHTML.includes("Millen Township - Precinct 1");
checks.directMichiganVoteShareGraph =
  miQueryHarness.element("#voteShareGraph").innerHTML.includes("Michigan MVIC precinct vote-share chart");
checks.directMichiganDownBallotGraph =
  miQueryHarness.element("#downBallotGraph").innerHTML.includes("Michigan MVIC precinct President vs Senate drop-off rates");

async function collectRegistryDirectRouteChecks(states) {
  const routeChecks = {};
  for (const state of states) {
    const harness = createAppHarness({ search: `?state=${encodeURIComponent(state.code)}` });
    await new Promise((resolve) => setTimeout(resolve, 450));
    const badges = harness.element("#sourcePlanBadges").innerHTML;
    const countyRows = (harness.element("#sourceCountyRows").innerHTML.match(/<tr>/g) || []).length;
    const historicalRows = (harness.element("#historicalTableRows").innerHTML.match(/<tr>/g) || []).length;
    const capabilities = state.capabilities || {};
    routeChecks[state.code] = {
      selected: harness.element("#appStateSelect").value === state.code && harness.element("#sourceStateSelect").value === state.code,
      title: harness.element("#sourceStateTitle").textContent === `${state.name} ${state.electionYear} ${state.office}`,
      countyRows: countyRows === state.expectedCountyCount,
      mapReady: !capabilities.map || badges.includes("Map ready"),
      turnoutReady: !capabilities.turnout || (badges.includes("Turnout ready") && harness.element("#turnoutGraph").innerHTML.includes("turnout histogram")),
      historicalReady: !capabilities.historicalBaseline || (badges.includes("Historical baseline ready") && historicalRows > 0),
      reviewReady: !capabilities.reviewGraphs || harness.element("#voteShareGraph").innerHTML.includes("<svg"),
    };
  }
  return routeChecks;
}

checks.registryDirectRoutes = await collectRegistryDirectRouteChecks(registryStates);
checks.registryDirectRoutesAllReady = Object.values(checks.registryDirectRoutes).every((stateChecks) =>
  Object.values(stateChecks).every(Boolean),
);
vm.runInContext(`
  els.sourceStateSelect.value = "WI";
  switchActiveState(els.sourceStateSelect.value);
`, mnHashHarness.context);
checks.sourcePlannerSelectorSyncsGlobal =
  mnHashHarness.element("#appStateSelect").value === "WI" &&
  mnHashHarness.element("#sourceStateSelect").value === "WI" &&
  !mnHashHarness.context.window.location.href.includes("state=MN");
vm.runInContext(`
  els.appStateSelect.value = "MN";
  switchActiveState(els.appStateSelect.value);
`, mnHashHarness.context);
checks.globalSelectorSyncsSourcePlanner =
  mnHashHarness.element("#appStateSelect").value === "MN" &&
  mnHashHarness.element("#sourceStateSelect").value === "MN" &&
  mnHashHarness.context.window.location.hash.includes("state=MN");
vm.runInContext(`
  selectCounty("Hennepin");
  updateReviewRoute();
`, mnHashHarness.context);
checks.minnesotaReviewRouteKeepsState =
  mnHashHarness.context.window.location.hash.startsWith("#review?") &&
  mnHashHarness.context.window.location.hash.includes("county=Hennepin") &&
  mnHashHarness.context.window.location.hash.includes("state=MN");
vm.runInContext(`setTheme("dark")`, context);
checks.darkModeApplied = document.documentElement.dataset.theme === "dark";
checks.darkModeStored = storage.get("wi-election-theme") === "dark";

const expected = {
  sidebarExplorerTitle: true,
  sidebarCurrentMapScope: true,
  sidebarHistoricalAction: true,
  plainLanguageGlossary: true,
  harmonizedDefinition: true,
  technicalTermTooltips: true,
  noEtaStyleLabels: true,
  historyTabVisible: true,
  countyOptions: 73,
  seriesOptions: 7,
  historicalTableRows: 4,
  trendGraphSvg: true,
  scatterGraphSvg: true,
  distributionGraphSvg: true,
  distributionGraphComesFirst: true,
  historicalAxisLabelsAreClean: true,
  auditTabPresent: true,
  auditSidebarAction: true,
  auditStatewidePreset: true,
  auditTrialsButton: true,
  auditDistributionControl: true,
  appStateSelectorPresent: true,
  appStateOptions: registryStates.length + 1,
  appStateSyncedWithSourcePlanner: true,
  sourcePlannerTabPresent: true,
  sourcePlannerSidebarAction: true,
  sourcePlannerStateOptions: registryStates.length + 1,
  sourcePlannerWisconsinTitle: true,
  sourcePlannerCountyRows: 72,
  sourcePlannerWaukeshaChecked: true,
  sourcePlannerTimestamps: true,
  sourceTimestampNotesVisible: true,
  auditDistributionNote: true,
  auditSpreadPattern: true,
  auditHighVolumeDisclaimer: true,
  auditMinimumMarginControl: true,
  auditMissProbability: "4.18%",
  auditTrialMissRate: true,
  auditTrialProgress: 1000,
  auditTrialProgressText: "1,000 of 1,000 trials complete",
  auditTrialSummary: true,
  auditGridUnits: 3730,
  auditVoteComparison: true,
  appStateOptionsMatchRegistry: true,
  sourcePlannerStateOptionsMatchRegistry: true,
  auditMinimumMarginShift: true,
  auditMinimumMarginNote: true,
  auditMinimumMarginTotal: true,
  minnesotaStateSelected: true,
  minnesotaSourcePlannerTitle: true,
  minnesotaSourcePlannerCountyRows: 87,
  minnesotaSourcePlannerTimestamp: true,
  minnesotaSourcePlannerLoaded: true,
  minnesotaMapReady: true,
  minnesotaHistoricalLoaded: true,
  minnesotaHistoricalCopyClean: true,
  minnesotaHistoricalSeriesOptions: true,
  minnesotaReviewRowsLoaded: true,
  minnesotaVoteShareGraph: true,
  minnesotaDownBallotGraph: true,
  minnesotaTurnoutLoaded: true,
  minnesotaStaticSourceTimestampVisible: true,
  minnesotaSaintLouisGeometryMatchesResults: true,
  directMinnesotaQuerySelected: true,
  directMinnesotaQuerySummary: true,
  directMinnesotaHashSelected: true,
  directMinnesotaHashSourcesTab: true,
  directNorthDakotaQuerySelected: true,
  directNorthDakotaQuerySummary: true,
  directNorthDakotaMapReady: true,
  directNorthDakotaHistoricalLoaded: true,
  directMichiganQuerySelected: true,
  directMichiganQuerySummary: true,
  directMichiganMapReady: true,
  directMichiganTurnoutLoaded: true,
  directMichiganHistoricalLoaded: true,
  directMichiganReviewDatasetLoaded: true,
  directMichiganReviewRowsLoaded: true,
  directMichiganReviewTableLoaded: true,
  directMichiganVoteShareGraph: true,
  directMichiganDownBallotGraph: true,
  registryDirectRoutesAllReady: true,
  sourcePlannerSelectorSyncsGlobal: true,
  globalSelectorSyncsSourcePlanner: true,
  minnesotaReviewRouteKeepsState: true,
  darkModeApplied: true,
  darkModeStored: true,
};
const errors = Object.entries(expected)
  .filter(([key, value]) => checks[key] !== value)
  .map(([key, value]) => `${key}: expected ${JSON.stringify(value)}, got ${JSON.stringify(checks[key])}`);

if (errors.length) {
  console.error("Static UI validation failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(JSON.stringify({ status: "passed", ...checks }, null, 2));
