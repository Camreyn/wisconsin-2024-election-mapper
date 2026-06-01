import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

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

const appTabs = ["dashboard", "review", "history", "data", "methodology", "about"].map((name) => {
  const tab = new MockElement();
  tab.dataset.appTab = name;
  if (name === "dashboard") tab.classList.add("active");
  return tab;
});
const tabPanels = ["dashboard", "review", "history", "data", "methodology", "about"].map((name) => {
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

const checks = {
  historyTabVisible: tabPanels.find((panel) => panel.id === "historyPanel").hidden === false,
  countyOptions: element("#historicalCountySelect").options.length,
  seriesOptions: element("#historicalSeriesSelect").options.length,
  historicalTableRows: (element("#historicalTableRows").innerHTML.match(/<tr>/g) || []).length,
  trendGraphSvg: element("#historicalTrendGraph").innerHTML.includes("<svg"),
  scatterGraphSvg: element("#historicalScatterGraph").innerHTML.includes("<svg"),
};
vm.runInContext(`setTheme("dark")`, context);
checks.darkModeApplied = document.documentElement.dataset.theme === "dark";
checks.darkModeStored = storage.get("wi-election-theme") === "dark";

const expected = {
  historyTabVisible: true,
  countyOptions: 73,
  seriesOptions: 6,
  historicalTableRows: 4,
  trendGraphSvg: true,
  scatterGraphSvg: true,
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
