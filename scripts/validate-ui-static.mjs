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
    return element(selector);
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

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) {
    elements.set(selector, new MockElement(selector.replace(/^#/, "")));
  }
  return elements.get(selector);
}

const appTabs = ["dashboard", "review", "history", "data", "methodology", "audit", "about"].map((name) => {
  const tab = new MockElement();
  tab.dataset.appTab = name;
  if (name === "dashboard") tab.classList.add("active");
  return tab;
});
const tabPanels = ["dashboard", "review", "history", "data", "methodology", "audit", "about"].map((name) => {
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
  querySelector: element,
  querySelectorAll: (selector) => {
    if (selector === "[data-app-tab]") return appTabs;
    if (selector === ".tab-panel") return tabPanels;
    if (selector === ".mode-button") return modeButtons;
    return [];
  },
};
const storage = new Map();
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
context.window.location = { hash: "#history", href: "file:///index.html#history" };
context.window.history = { replaceState: () => {} };
vm.createContext(context);

for (const file of [
  "data/app-data.js",
  "data/eta-data.js",
  "data/wi-counties.js",
  "data/turnout-data.js",
  "data/historical-data.js",
  "app.js",
]) {
  vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), context, { filename: file });
}

await new Promise((resolve) => setTimeout(resolve, 400));
await vm.runInContext(`runAuditTrials()`, context);

const checks = {
  sidebarExplorerTitle: indexHtml.includes("Wisconsin Presidential Results Explorer"),
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
  auditDistributionNote: element("#auditDistributionNote").textContent.includes("grid is not a geographic map"),
  auditSpreadPattern: vm.runInContext(`auditAffectedIndices(100, 8, 17, "spread").join(",") !== auditAffectedIndices(100, 8, 17, "concentrated").join(",")`, context),
  auditHighVolumeDisclaimer: vm.runInContext(`AUDIT_DISTRIBUTION_NOTES.highVolume.includes("cannot identify real high-volume audit units")`, context),
  auditMissProbability: element("#auditMissProbability").textContent,
  auditTrialMissRate: /^\d+\.\d%$/.test(element("#auditTrialMissRate").textContent),
  auditTrialProgress: element("#auditTrialProgress").value,
  auditTrialProgressText: element("#auditTrialProgressText").textContent,
  auditTrialSummary: element("#auditTrialSummary").textContent.includes("of 1,000 simplified audit draws missed every one"),
  auditGridUnits: (element("#auditUnitGrid").innerHTML.match(/class="audit-unit/g) || []).length,
  auditVoteComparison: element("#auditVoteComparison").innerHTML.includes("3,271,210") && element("#auditVoteComparison").innerHTML.includes("Illustrative margin movement"),
};
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
  auditDistributionNote: true,
  auditSpreadPattern: true,
  auditHighVolumeDisclaimer: true,
  auditMissProbability: "4.18%",
  auditTrialMissRate: true,
  auditTrialProgress: 1000,
  auditTrialProgressText: "1,000 of 1,000 trials complete",
  auditTrialSummary: true,
  auditGridUnits: 3730,
  auditVoteComparison: true,
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
