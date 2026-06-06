import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_OUTPUT = "data/az-2024-county-source-manifest.json";
const AZ_RESULTS_APP_URL = "https://results.arizona.vote/#/featured/47/0";
const AZ_SOS_ELECTION_INFO_URL = "https://azsos.gov/events/local-elections/408";
const AZ_SOS_CANVASS_BASE = "https://apps.azsos.gov/election/2024/ge/canvass";
const MARICOPA_ARCHIVE_URL = "https://elections.maricopa.gov/results-and-data/historic-results.html?year=2024";
const MARICOPA_SOV_TEXT_URL =
  "https://elections.maricopa.gov/asset/jcr:5c8a38fd-0d5a-4fa1-83cb-8b13e5ff089c/11-05-2024-2b%20Final%20SOV%20and%20Official%20Canvass%20Report.txt";
const MARICOPA_SOV_DESCRIPTION_URL =
  "https://elections.maricopa.gov/asset/jcr:7bd7f5df-392a-40c2-a236-2ecd5291ba60/11-05-2024-2c%20FILE%20DESCRIPTION-Final%20SOV%20and%20Official%20Canvass%20Report.pdf";
const APACHE_OFFICIAL_RESULTS_PDF =
  "https://ecs-cluster-bucket-wsos-prod-two.s3.us-west-2.amazonaws.com/uploads/sites/107/2024-General-Election-Official-Results.pdf";
const COCONINO_RESULTS_PAGE = "https://www.coconino.az.gov/205/Past-Election-Results";

const counties = [
  ["Apache", "001"],
  ["Cochise", "003"],
  ["Coconino", "005"],
  ["Gila", "007"],
  ["Graham", "009"],
  ["Greenlee", "011"],
  ["La Paz", "012"],
  ["Maricopa", "013"],
  ["Mohave", "015"],
  ["Navajo", "017"],
  ["Pima", "019"],
  ["Pinal", "021"],
  ["Santa Cruz", "023"],
  ["Yavapai", "025"],
  ["Yuma", "027"],
];

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

function sosCountyName(county) {
  return county.replace(/\s+/g, "");
}

function sosCanvassSource(county) {
  return {
    label: `${county} County SOS-hosted canvass PDF`,
    url: `${AZ_SOS_CANVASS_BASE}/202411GeneralElectionCanvass-${sosCountyName(county)}.pdf`,
    format: "pdf",
    access: "protected",
    parserHint: "arizonaCountyCanvassPdf",
    roles: ["countyTotals", "turnout"],
    note: "Arizona SOS county canvass PDF candidate. Direct automated fetches to apps.azsos.gov returned Cloudflare verification pages in this environment.",
  };
}

function countySpecificSources(county) {
  if (county === "Apache") {
    return [
      {
        label: "Apache County official results PDF",
        url: APACHE_OFFICIAL_RESULTS_PDF,
        format: "pdf",
        access: "downloadable",
        parserHint: "arizonaCountySummaryPdf",
        roles: ["countyTotals", "precinctResults", "turnout"],
        note: "Pipeline probe downloaded this county-hosted file and extracted official summary plus precinct sections from the PDF text.",
      },
      sosCanvassSource(county),
    ];
  }
  if (county === "Coconino") {
    return [
      {
        label: "Coconino County past election results page",
        url: COCONINO_RESULTS_PAGE,
        format: "html",
        access: "page",
        parserHint: "countyResultsPageDiscovery",
        roles: ["countyTotals", "precinctResults", "turnout"],
        note: "Official county page listing November 5, 2024 General Election result resources.",
      },
      sosCanvassSource(county),
    ];
  }
  if (county === "Maricopa") {
    return [
      {
        label: "Maricopa County historic results page",
        url: MARICOPA_ARCHIVE_URL,
        format: "html",
        access: "browserSnapshot",
        parserHint: "countyResultsPageDiscovery",
        roles: ["countyTotals", "precinctResults", "turnout"],
        note: "Browser snapshot recovered official 2024 SOV and file-description asset links from this page.",
      },
      {
        label: "Maricopa County final SOV text",
        url: MARICOPA_SOV_TEXT_URL,
        format: "text",
        access: "protected",
        parserHint: "maricopaSovText",
        roles: ["countyTotals", "precinctResults", "turnout"],
        note: "Official SOV text asset link discovered from the county archive. Direct automated download returned Cloudflare verification.",
      },
      {
        label: "Maricopa County final SOV file description",
        url: MARICOPA_SOV_DESCRIPTION_URL,
        format: "pdf",
        access: "protected",
        parserHint: "maricopaSovFileDescription",
        roles: ["schema"],
        note: "Official file description for Maricopa's SOV text format.",
      },
      sosCanvassSource(county),
    ];
  }
  return [sosCanvassSource(county)];
}

function countyStatus(county) {
  if (county === "Apache") return "downloadable-county-pdf-candidate";
  if (county === "Coconino") return "county-results-page-candidate";
  if (county === "Maricopa") return "protected-sov-text-discovered";
  return "sos-canvass-pdf-protected";
}

export function arizonaSourceManifest() {
  return {
    state: "AZ",
    name: "Arizona",
    electionYear: 2024,
    office: "President",
    authority: "Arizona Secretary of State",
    sourceStatus: "county-source-manifest-needed",
    statewideSources: [
      {
        label: "Arizona official results app",
        url: AZ_RESULTS_APP_URL,
        format: "webapp",
        access: "protected",
        roles: ["countyTotals", "precinctResults", "turnout"],
        note: "Headless browser snapshots and direct HTTP requests returned Cloudflare verification pages.",
      },
      {
        label: "Arizona SOS 2024 Election Info",
        url: AZ_SOS_ELECTION_INFO_URL,
        format: "html",
        access: "protected",
        roles: ["countyCanvassIndex"],
        note: "Searchable official page references county canvass links; direct automated fetches returned Cloudflare verification pages.",
      },
    ],
    parserFamilies: [
      {
        id: "arizonaCountySummaryPdf",
        status: "candidate",
        appliesTo: ["Apache"],
        nextStep: "Promote a PDF text parser for official county summary/precinct sections after reconciling Apache rows.",
      },
      {
        id: "maricopaSovText",
        status: "blocked-by-protected-download",
        appliesTo: ["Maricopa"],
        nextStep: "Add a protected-download or approved interactive capture route for the official SOV text file.",
      },
      {
        id: "countyResultsPageDiscovery",
        status: "candidate",
        appliesTo: ["Coconino", "Maricopa"],
        nextStep: "Snapshot county result pages, discover official files, then promote per-format parser hints.",
      },
      {
        id: "arizonaCountyCanvassPdf",
        status: "blocked-by-protected-download",
        appliesTo: counties.map(([county]) => county),
        nextStep: "Use county-hosted mirrors where available or an approved capture route for SOS-hosted canvass PDFs.",
      },
    ],
    counties: counties.map(([county, fips]) => ({
      county,
      fips,
      status: countyStatus(county),
      sourceCandidates: countySpecificSources(county),
    })),
    nextSteps: [
      "Resolve protected downloads for the statewide results app or SOS-hosted canvass PDFs.",
      "Promote a PDF text parser for county canvass files that include precinct sections.",
      "Promote Maricopa SOV text parsing once an approved source file is locally available.",
      "Reconcile county totals against the official statewide canvass before enabling Arizona app capabilities.",
    ],
  };
}

export function writeArizonaSourceManifest(output = DEFAULT_OUTPUT) {
  const resolvedOutput = path.resolve(root, output);
  fs.mkdirSync(path.dirname(resolvedOutput), { recursive: true });
  const manifest = arizonaSourceManifest();
  fs.writeFileSync(resolvedOutput, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  return { output: path.relative(root, resolvedOutput).replaceAll("\\", "/"), counties: manifest.counties.length };
}

function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const result = writeArizonaSourceManifest(args.get("output") || DEFAULT_OUTPUT);
  process.stdout.write(`${JSON.stringify({ status: "written", ...result }, null, 2)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
