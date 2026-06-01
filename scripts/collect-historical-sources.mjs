import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const historicalDir = path.join(root, "data", "historical");
const rawDir = path.join(historicalDir, "raw");
const manifestPath = path.join(historicalDir, "source-manifest.json");
const collectedAt = new Date().toISOString();

const downloads = [
  {
    id: "ltsb-2012-2020-harmonized-wards",
    electionYears: [2012, 2016, 2020],
    sourceClass: "harmonizedLtsb",
    publisher: "Wisconsin Legislative Technology Services Bureau",
    title: "2012-2020 Election Data (with 2020 Wards)",
    sourceUrl: "https://web.s3.wisc.edu/rml-gisdata/WI_20122020_Election_Data_Wards_2020.zip",
    catalogUrl: "https://geodiscovery.uwm.edu/catalog/317F4F49-5B17-43CC-9BCA-36ED25DC9E15",
    localFile: "raw/WI_20122020_Election_Data_Wards_2020.zip",
    methodologyNote:
      "Harmonized comparison data. LTSB documents that some election totals were disaggregated from reporting units to wards and census blocks using population-based allocation.",
  },
  {
    id: "wec-2016-native-president-original-and-recount",
    electionYears: [2016],
    sourceClass: "nativeOfficial",
    publisher: "Wisconsin Elections Commission",
    title: "Ward by Ward Original and Recount President of the United States.xlsx",
    sourceUrl:
      "https://web.archive.org/web/20161214185442id_/http://elections.wi.gov/sites/default/files/Ward%20by%20Ward%20Original%20and%20Recount%20President%20of%20the%20United%20States.xlsx",
    landingPageUrl:
      "https://web.archive.org/web/20161223044005id_/http://elections.wi.gov/elections-voting/results/2016/fall-general",
    localFile: "raw/2016-wec-native-president-original-and-recount.xlsx",
    methodologyNote:
      "Native official WEC ward-level presidential workbook containing original and recount results.",
  },
  {
    id: "gab-2012-official-results-page",
    electionYears: [2012],
    sourceClass: "officialLandingPage",
    publisher: "Wisconsin Government Accountability Board",
    title: "2012 Fall General Election Results official archived page",
    sourceUrl:
      "https://web.archive.org/web/20121208020848id_/http://gab.wi.gov:80/elections-voting/results/2012/fall-general",
    localFile: "raw/2012-gab-official-results-page.html",
    methodologyNote:
      "Official archived landing page. It lists native ward-level presidential spreadsheets whose tested attachment bytes were not retrievable.",
  },
  {
    id: "wec-2016-official-results-page",
    electionYears: [2016],
    sourceClass: "officialLandingPage",
    publisher: "Wisconsin Elections Commission",
    title: "2016 Fall General Election Results official archived page",
    sourceUrl:
      "https://web.archive.org/web/20161223044005id_/http://elections.wi.gov/elections-voting/results/2016/fall-general",
    localFile: "raw/2016-wec-official-results-page.html",
    methodologyNote:
      "Official archived landing page for the native 2016 WEC workbook.",
  },
  {
    id: "wec-2020-official-results-page",
    electionYears: [2020],
    sourceClass: "officialLandingPage",
    publisher: "Wisconsin Elections Commission",
    title: "2020 Fall General Election Results official archived page",
    sourceUrl:
      "https://web.archive.org/web/20201214172750id_/https://elections.wi.gov/elections-voting/results/2020/fall-general",
    localFile: "raw/2020-wec-official-results-page.html",
    methodologyNote:
      "Official archived landing page. It lists native presidential spreadsheets whose tested attachment bytes were not retrievable.",
  },
  {
    id: "mirror-2020-native-president-under-recount",
    electionYears: [2020],
    sourceClass: "thirdPartyMirror",
    publisher: "Digital Poll Watchers mirror of a WEC workbook",
    title: "Ward by Ward Report - President of the United States (under recount).xlsx",
    sourceUrl:
      "https://digitalpollwatchers.org/wp-content/uploads/2021/08/Ward-by-Ward-Report-President-of-the-United-States-under-recount-1.xlsx",
    originalSourceUrl:
      "https://elections.wi.gov/sites/elections.wi.gov/files/Ward%20by%20Ward%20Report%20-%20President%20of%20the%20United%20States%20%28under%20recount%29.xlsx",
    landingPageUrl:
      "https://web.archive.org/web/20201214172750id_/https://elections.wi.gov/elections-voting/results/2020/fall-general",
    localFile: "raw/2020-president-under-recount-third-party-mirror.xlsx",
    optional: true,
    methodologyNote:
      "Third-party page links to a workbook named on the official WEC 2020 landing page. Preserve only if the linked URL returns workbook bytes. Do not treat as verified official bytes unless WEC supplies the original or an official hash match is established.",
  },
  {
    id: "mirror-2020-election-day-registrants",
    electionYears: [2020],
    sourceClass: "thirdPartySupplemental",
    publisher: "Digital Poll Watchers mirror of data attributed to Wisconsin Elections Commission",
    title: "WISelectionDAYregistrantsCOLUMNiNOV3rd2020.xlsx",
    sourceUrl:
      "https://digitalpollwatchers.org/wp-content/uploads/2021/08/WISelectionDAYregistrantsCOLUMNiNOV3rd2020.xlsx",
    landingPageUrl:
      "https://digitalpollwatchers.org/new-wi-2020-election-fingerprints-rev-2-0/",
    localFile: "raw/2020-election-day-registrants-third-party-mirror.xlsx",
    optional: true,
    methodologyNote:
      "Third-party supplemental mirror containing registration, voter, and ballot fields. Preserve for evaluation only. Do not treat as verified official bytes or import into app analysis unless WEC supplies the original or an official hash match is established.",
  },
];

const localSources = [
  {
    id: "wec-2024-native-federal-state-ward-report",
    electionYears: [2024],
    sourceClass: "nativeOfficial",
    publisher: "Wisconsin Elections Commission",
    title: "Ward by Ward Report Federal and State Contests.xlsx",
    sourceUrl:
      "https://web.archive.org/web/20241130045633id_/https://elections.wi.gov/sites/default/files/documents/Ward%20by%20Ward%20Report%20by%20Congressional%20District_November%205%202024%20General%20Election_Federal%20and%20State%20Contests.xlsx",
    sourceFile: path.join(root, "data", "Ward by Ward Report Federal and State Contests.xlsx"),
    localFile: "raw/2024-wec-native-ward-federal-state-contests.xlsx",
    methodologyNote:
      "Native official WEC ward/reporting-unit workbook already used by the app. Copied here to freeze the historical reference.",
  },
];

const unavailable = [
  {
    id: "gab-2012-native-president-ward-workbook",
    electionYears: [2012],
    sourceClass: "nativeOfficial",
    publisher: "Wisconsin Government Accountability Board",
    title: "CanvassResults_Presidential_by_Assembly_Senate.xls",
    originalSourceUrl:
      "http://gab.wi.gov/sites/default/files/CanvassResults_Presidential_by_Assembly_Senate.xls",
    landingPageUrl:
      "https://web.archive.org/web/20121208020848id_/http://gab.wi.gov:80/elections-voting/results/2012/fall-general",
    retrievalStatus: "missing",
    methodologyNote:
      "Official landing page confirms publication, but the tested live URL and tested archive snapshot did not return the spreadsheet bytes. Request from WEC.",
  },
  {
    id: "wec-2020-native-president-after-recount-workbook",
    electionYears: [2020],
    sourceClass: "nativeOfficial",
    publisher: "Wisconsin Elections Commission",
    title:
      "Ward by Ward Report PRESIDENT OF THE UNITED STATES by State Representive District - After Recount.xlsx",
    originalSourceUrl:
      "https://elections.wi.gov/sites/elections.wi.gov/files/Ward%20by%20Ward%20Report%20PRESIDENT%20OF%20THE%20UNITED%20STATES%20by%20State%20Representive%20District%20-%20After%20Recount.xlsx",
    landingPageUrl:
      "https://web.archive.org/web/20201214172750id_/https://elections.wi.gov/elections-voting/results/2020/fall-general",
    retrievalStatus: "missing",
    methodologyNote:
      "Official landing page confirms publication, but the tested live URL and tested archive snapshot did not return the spreadsheet bytes. A third-party mirror of the under-recount workbook was collected separately for reconciliation. Request the final official workbook from WEC.",
  },
];

async function sha256(filePath) {
  const bytes = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

async function ensureDirectory() {
  await fs.mkdir(rawDir, { recursive: true });
}

function validateDownloadedBytes(source, bytes) {
  const extension = path.extname(source.localFile).toLowerCase();
  if ((extension === ".xlsx" || extension === ".zip") && !bytes.subarray(0, 2).equals(Buffer.from("PK"))) {
    throw new Error(`${source.id}: expected ZIP-based ${extension} bytes`);
  }
}

async function download(source) {
  const destination = path.join(historicalDir, source.localFile);
  const response = await fetch(source.sourceUrl, { redirect: "follow" });
  if (!response.ok) {
    throw new Error(`${source.id}: HTTP ${response.status} ${response.statusText}`);
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  validateDownloadedBytes(source, bytes);
  await fs.writeFile(destination, bytes);
  return {
    ...source,
    retrievedAt: collectedAt,
    retrievalStatus: "collected",
    contentType: response.headers.get("content-type"),
    bytes: bytes.length,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
  };
}

async function copyLocalSource(source) {
  const destination = path.join(historicalDir, source.localFile);
  await fs.copyFile(source.sourceFile, destination);
  return {
    ...source,
    sourceFile: path.relative(root, source.sourceFile).replaceAll("\\", "/"),
    retrievedAt: collectedAt,
    retrievalStatus: "collected",
    bytes: (await fs.stat(destination)).size,
    sha256: await sha256(destination),
  };
}

async function main() {
  await ensureDirectory();
  const entries = [];
  for (const source of downloads) {
    console.log(`Collecting ${source.id}...`);
    try {
      entries.push(await download(source));
    } catch (error) {
      if (!source.optional) {
        throw error;
      }
      console.warn(`${source.id}: ${error.message}`);
      entries.push({
        ...source,
        retrievedAt: collectedAt,
        retrievalStatus: "missing",
        retrievalError: error.message,
      });
    }
  }
  for (const source of localSources) {
    console.log(`Freezing ${source.id}...`);
    entries.push(await copyLocalSource(source));
  }
  entries.push(...unavailable);

  const manifest = {
    generatedAt: collectedAt,
    purpose: "Historical presidential-election baseline source inventory",
    entries,
  };
  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  console.log(`Wrote ${path.relative(root, manifestPath)}`);
}

await main();
