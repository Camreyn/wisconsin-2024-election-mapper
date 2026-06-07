import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const configDir = path.join(root, "data/state-configs");
const nationalResultsFile = "data/national-2024-county-president-results.csv";
const nationalResultsUrl =
  "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/master/2024_US_County_Level_Presidential_Results.csv";
const alaskaHouseDistrictUrl =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/2/query?where=STATE%3D%2702%27&outFields=NAME,BASENAME,GEOID,STATE,SLDL&returnGeometry=true&outSR=4326&f=geojson";
const geometryFeatureOverrides = {
  HI: 5,
};

const states = [
  ["AL", "Alabama", "01"],
  ["AK", "Alaska", "02"],
  ["AZ", "Arizona", "04"],
  ["AR", "Arkansas", "05"],
  ["CA", "California", "06"],
  ["CO", "Colorado", "08"],
  ["CT", "Connecticut", "09"],
  ["DE", "Delaware", "10"],
  ["FL", "Florida", "12"],
  ["GA", "Georgia", "13"],
  ["HI", "Hawaii", "15"],
  ["ID", "Idaho", "16"],
  ["IL", "Illinois", "17"],
  ["IN", "Indiana", "18"],
  ["IA", "Iowa", "19"],
  ["KS", "Kansas", "20"],
  ["KY", "Kentucky", "21"],
  ["LA", "Louisiana", "22"],
  ["ME", "Maine", "23"],
  ["MD", "Maryland", "24"],
  ["MA", "Massachusetts", "25"],
  ["MI", "Michigan", "26"],
  ["MN", "Minnesota", "27"],
  ["MS", "Mississippi", "28"],
  ["MO", "Missouri", "29"],
  ["MT", "Montana", "30"],
  ["NE", "Nebraska", "31"],
  ["NV", "Nevada", "32"],
  ["NH", "New Hampshire", "33"],
  ["NJ", "New Jersey", "34"],
  ["NM", "New Mexico", "35"],
  ["NY", "New York", "36"],
  ["NC", "North Carolina", "37"],
  ["ND", "North Dakota", "38"],
  ["OH", "Ohio", "39"],
  ["OK", "Oklahoma", "40"],
  ["OR", "Oregon", "41"],
  ["PA", "Pennsylvania", "42"],
  ["RI", "Rhode Island", "44"],
  ["SC", "South Carolina", "45"],
  ["SD", "South Dakota", "46"],
  ["TN", "Tennessee", "47"],
  ["TX", "Texas", "48"],
  ["UT", "Utah", "49"],
  ["VT", "Vermont", "50"],
  ["VA", "Virginia", "51"],
  ["WA", "Washington", "53"],
  ["WV", "West Virginia", "54"],
  ["WI", "Wisconsin", "55"],
  ["WY", "Wyoming", "56"],
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

function readCsv(file) {
  const [headerLine, ...lines] = fs.readFileSync(path.join(root, file), "utf8").trim().split(/\r?\n/);
  const headers = headerLine.split(",");
  return lines.map((line) => {
    const values = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, values[index] || ""]));
  });
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function hasBaselineFloor(config) {
  const capabilities = config.app?.capabilities || {};
  return Boolean(capabilities.certifiedResults && capabilities.map);
}

function sumRows(rows) {
  return rows.reduce(
    (totals, row) => {
      const trump = Number(row.votes_gop || 0);
      const harris = Number(row.votes_dem || 0);
      const total = Number(row.total_votes || 0);
      totals.trump += trump;
      totals.harris += harris;
      totals.other += Math.max(0, total - trump - harris);
      totals.total += total;
      return totals;
    },
    { trump: 0, harris: 0, other: 0, total: 0 },
  );
}

function censusCountyUrl(fips) {
  return `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%27${fips}%27&outFields=NAME,BASENAME,GEOID,STATE,COUNTY&returnGeometry=true&outSR=4326&f=geojson`;
}

function geometrySource(code, fips) {
  const slug = code.toLowerCase();
  if (code === "AK") {
    return {
      id: "ak-house-district-geometry",
      url: alaskaHouseDistrictUrl,
      localFile: "data/ak-house-districts.geojson",
      outputFile: "data/ak-house-districts.js",
      outputGlobal: "AK_HOUSE_DISTRICTS_GEOJSON",
      sourceLabel: "House District",
      inventoryUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer",
    };
  }
  return {
    id: `${slug}-county-geometry`,
    url: censusCountyUrl(fips),
    localFile: `data/${slug}-counties.geojson`,
    outputFile: `data/${slug}-counties.js`,
    outputGlobal: `${code}_COUNTIES_GEOJSON`,
    sourceLabel: code === "LA" ? "Parish" : "County",
    inventoryUrl: "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer",
  };
}

function baselineConfig({ code, name, fips, rows }) {
  const slug = code.toLowerCase();
  const totals = sumRows(rows);
  const geometry = geometrySource(code, fips);
  const countyLabel = geometry.sourceLabel;
  const authority = `${name} election authorities via national county baseline`;
  return {
    code,
    name,
    authority,
    electionYear: 2024,
    office: "President",
    output: {
      appDataFile: `data/${slug}-app-data.js`,
      appDataGlobal: `${code}_ELECTION_APP_DATA`,
    },
    sources: [
      {
        id: "national-2024-county-president-results",
        url: nationalResultsUrl,
        localFile: nationalResultsFile,
      },
      {
        id: geometry.id,
        url: geometry.url,
        localFile: geometry.localFile,
      },
    ],
    geometry: {
      sourceId: geometry.id,
      outputFile: geometry.outputFile,
      outputGlobal: geometry.outputGlobal,
      nameProperty: "NAME",
      codeProperty: "GEOID",
      expectedFeatures: geometryFeatureOverrides[code] || rows.length,
    },
    certifiedResults: {
      format: "nationalCountyBaselineCsv",
      sourceId: "national-2024-county-president-results",
      stateName: name,
      majorCandidates: {
        trump: { candidateContains: "votes_gop" },
        harris: { candidateContains: "votes_dem" },
      },
      metadataNotes:
        "Aggregated from the national 2024 county presidential baseline CSV. Source Planner marks this as a baseline import pending replacement by a native official state export where available.",
      otherCandidates: [{ key: "nationalOther", label: "Other candidates" }],
    },
    reviewCharts: {
      format: "notConfigured",
      sourceId: "national-2024-county-president-results",
      policy: {
        outlierThresholdPct: 15,
        minCandidateVotes: 100,
        voteShareCorrelationThreshold: 0.35,
      },
    },
    turnout: {
      format: "notConfigured",
      sourceId: "national-2024-county-president-results",
      registrationDenominatorTiming: "notLoaded",
      sourceLevel: "county",
      notes: "Turnout is not loaded in the baseline import because the national county results file does not include registered-voter denominators.",
      warningRequired: true,
    },
    historicalBaseline: {
      sourceLevel: "county",
      rowMethod: "notConfigured",
      partyCodes: { dem: "DEM", rep: "REP" },
      contestName: "President",
      sources: [],
    },
    app: {
      countyLabel,
      exportsSlug: `${slug}-2024`,
      capabilities: {
        sourcePlanner: true,
        certifiedResults: true,
        map: true,
        reviewGraphs: false,
        turnout: false,
        historicalBaseline: false,
      },
      sourcePlan: {
        certifiedResults: {
          title: `${name} national baseline presidential ${countyLabel.toLowerCase()} results`,
          detail:
            "County-level presidential rows are imported from the public national 2024 county results baseline. This is the app floor for broad state coverage and should be replaced by a native official state export/parser when one is collected.",
          sourceUrl: nationalResultsUrl,
          localFile: `${nationalResultsFile}; data/${slug}-app-data.js`,
          sourceLastModifiedUtc: "",
          sourceTimestampBasis:
            "Downloaded from tonmcg/US_County_Level_Election_Results_08-24; repository README says the data are compiled from reputable public sources but are not authoritative.",
          status: "Loaded",
        },
        wardDetail: {
          title: `${name} precinct or reporting-unit detail`,
          detail:
            "The baseline import is county-level only. Review drilldowns need an official precinct, ward, or reporting-unit source before they can be enabled.",
          sourceUrl: nationalResultsUrl,
          localFile: `${nationalResultsFile}; data/${slug}-app-data.js`,
          sourceLastModifiedUtc: "",
          sourceTimestampBasis: "Baseline source checked during broad state import.",
          status: "Needs precinct source",
        },
        turnout: {
          title: `${name} turnout denominator`,
          detail:
            "The baseline import does not include registered-voter denominators. Turnout remains disabled until an official turnout or registration source is mapped.",
          sourceUrl: nationalResultsUrl,
          localFile: `${nationalResultsFile}; data/${slug}-app-data.js`,
          sourceLastModifiedUtc: "",
          sourceTimestampBasis: "Baseline source lacks registered-voter denominator fields.",
          status: "Needs denominator source",
        },
      },
      sourceInventory: [
        {
          category: "Baseline presidential county results",
          file: `${nationalResultsFile}; data/${slug}-app-data.js`,
          sourceUrl: nationalResultsUrl,
          usedFor: `${name} 2024 presidential ${countyLabel.toLowerCase()} result baseline.`,
          confidence: "Public national county-level results baseline; not a substitute for a native official state parser.",
        },
        {
          category: `${countyLabel} boundaries`,
          file: `${geometry.localFile}; ${geometry.outputFile}`,
          sourceUrl: geometry.inventoryUrl,
          usedFor: `${name} ${countyLabel.toLowerCase()} polygon map.`,
          confidence: "U.S. Census TIGERweb geography.",
        },
      ],
      checkedNotUsable: [
        {
          category: "National county baseline",
          sourceUrl: nationalResultsUrl,
          reason:
            "Useful for broad app coverage, but the repository itself notes that the compiled results are not authoritative. Promote this state to a native official source when possible.",
          status: "Baseline only",
          nextStep: "Collect a native official state export, add a parser if needed, and reconcile totals.",
        },
      ],
      turnoutPolicy: {
        route: "officialRegistrationOrTurnoutDenominator",
        status: "Needs denominator source",
        acceptedSource: "Not loaded yet.",
        warning: `${name} turnout should not be inferred from the baseline county results file because it lacks registered-voter denominators.`,
        requiredFields: ["county", "ballotsCast", "registeredVoters", "sourceUrl"],
      },
      historicalSummary: "Historical comparison data is not loaded yet.",
      reviewRowLabel: `${name} reporting-unit row`,
      reviewRowLabelPlural: `${name} reporting-unit rows`,
      reviewGraphTitlePrefix: `${name} reporting unit`,
      mapLoadingText: `Loading local ${name} ${countyLabel.toLowerCase()} boundaries...`,
      noGeometryText: `${name} ${countyLabel.toLowerCase()} geometry is not loaded yet; showing the tile fallback.`,
    },
    expected: {
      countyRows: rows.length,
      precinctRows: rows.length,
      stateTotal: totals.total,
      trump: totals.trump,
      harris: totals.harris,
      other: totals.other,
      reviewRows: 0,
      turnoutRows: 0,
      turnoutWarningRows: 0,
      historicalSeries: 0,
      historicalRows: 0,
      geometryFeatures: geometryFeatureOverrides[code] || rows.length,
    },
  };
}

function main() {
  const args = parseArgs();
  const force = args.has("force");
  const includeAlaska = args.has("include-alaska");
  const requested = new Set(
    (args.get("states") || "")
      .split(",")
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean),
  );
  const rows = readCsv(nationalResultsFile);
  const rowsByState = new Map();
  for (const row of rows) {
    const stateRows = rowsByState.get(row.state_name) || [];
    stateRows.push(row);
    rowsByState.set(row.state_name, stateRows);
  }

  const written = [];
  const skipped = [];
  fs.mkdirSync(configDir, { recursive: true });
  for (const [code, name, fips] of states) {
    if (code === "WI") {
      skipped.push({ code, reason: "Wisconsin is the built-in reference state." });
      continue;
    }
    if (code === "AK" && !includeAlaska) {
      skipped.push({ code, reason: "Alaska needs state House district geometry, not Census county geometry." });
      continue;
    }
    if (requested.size && !requested.has(code)) continue;
    const configPath = path.join(configDir, `${code.toLowerCase()}.json`);
    if (!force && fs.existsSync(configPath) && hasBaselineFloor(readJson(configPath))) {
      skipped.push({ code, reason: "Already has certifiedResults and map capabilities." });
      continue;
    }
    const stateRows = rowsByState.get(name);
    if (!stateRows?.length) {
      skipped.push({ code, reason: "No national baseline rows found." });
      continue;
    }
    fs.writeFileSync(configPath, `${JSON.stringify(baselineConfig({ code, name, fips, rows: stateRows }), null, 2)}\n`);
    written.push(code);
  }

  process.stdout.write(`${JSON.stringify({ status: "passed", written, skipped }, null, 2)}\n`);
}

main();
