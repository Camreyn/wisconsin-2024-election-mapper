import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const electionInfoPath = path.join(root, "data/ar-2024-general-election-info.json");
const outputPath = path.join(root, "data/review-sources/ar-2024-general-federal-precinct-results.json");
const baseUrl = "https://enr-results-api.totalresults.com/Contest/GetContestResults";
const electionId = "1846";
const clientId = "arkansas";

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function countyEntries(electionInfo) {
  return Object.entries(electionInfo.response?.locations || {})
    .map(([locationId, location]) => ({
      locationId,
      county: String(location.locationName || "").trim(),
    }))
    .filter((entry) => entry.county)
    .sort((a, b) => a.county.localeCompare(b.county));
}

async function fetchCounty(entry) {
  const url = new URL(baseUrl);
  url.searchParams.set("cId", clientId);
  url.searchParams.set("electionID", electionId);
  url.searchParams.set("contestType", "FED");
  url.searchParams.set("locationID", entry.locationId);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Arkansas API returned ${response.status} for ${entry.county}`);
  }
  const payload = await response.json();
  if (!payload.isOfficial) {
    throw new Error(`Arkansas API payload for ${entry.county} is not marked official`);
  }
  const president = payload.response?.contests?.["366"];
  if (!president?.locations || !Object.keys(president.locations).length) {
    throw new Error(`Arkansas API payload for ${entry.county} has no presidential precinct rows`);
  }
  return {
    locationId: entry.locationId,
    county: entry.county,
    sourceUrl: url.toString(),
    lastUpdated: payload.lastUpdated,
    presidentContest: president,
  };
}

const electionInfo = readJson(electionInfoPath);
const counties = countyEntries(electionInfo);
const results = [];

for (let index = 0; index < counties.length; index += 1) {
  const county = counties[index];
  process.stdout.write(`[${index + 1}/${counties.length}] ${county.county}\n`);
  results.push(await fetchCounty(county));
}

const output = {
  checkedAt: new Date().toISOString(),
  authority: "Arkansas Secretary of State",
  sourceTitle: "Arkansas TotalResults federal contest results by county location",
  electionId,
  contestType: "FED",
  presidentContestId: "366",
  countyResults: results,
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`);
process.stdout.write(`Wrote ${outputPath}\n`);
