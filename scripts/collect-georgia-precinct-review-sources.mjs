import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const jurisdictionPath = path.join(root, "data", "review-sources", "ga-jurisdiction-georgia.json");
const outputDir = path.join(root, "data", "review-sources", "ga-2024-president-precinct-details");
const manifestPath = path.join(outputDir, "manifest.json");
const electionId = "2024NovGen";
const apiBase = "https://results.sos.ga.gov/results/public/api";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJson(url, attempt = 1) {
  const response = await fetch(url, {
    headers: {
      "user-agent": "Mozilla/5.0",
      accept: "application/json",
    },
  });
  if (!response.ok) {
    if (attempt < 3 && [429, 500, 502, 503, 504].includes(response.status)) {
      await sleep(1000 * attempt);
      return fetchJson(url, attempt + 1);
    }
    throw new Error(`HTTP ${response.status} from ${url}`);
  }
  return response.json();
}

function text(value) {
  if (Array.isArray(value)) {
    return value.map((item) => item?.text || "").find(Boolean) || "";
  }
  return value?.text || String(value || "");
}

function slugFile(shortName) {
  return `${shortName.replace(/[^a-z0-9-]+/gi, "-").toLowerCase()}-president.json`;
}

async function collectCounty(county) {
  const countyName = text(county.name);
  const shortName = county.shortName;
  const ballotItemsUrl = `${apiBase}/elections/${shortName}/${electionId}/ballot-items`;
  const ballotItems = await fetchJson(ballotItemsUrl);
  const president = (ballotItems.data || []).find((item) => text(item.name) === "President of the US");
  if (!president) {
    throw new Error(`No President ballot item found for ${countyName} (${shortName})`);
  }

  const detailUrl = `${apiBase}/elections/${shortName}/${electionId}/ballot-items/${president.id}`;
  const detail = await fetchJson(detailUrl);
  const fileName = slugFile(shortName);
  const outputPath = path.join(outputDir, fileName);
  await fs.writeFile(outputPath, `${JSON.stringify(detail)}\n`, "utf8");
  return {
    county: countyName,
    shortName,
    ballotItemId: president.id,
    sourceUrl: detailUrl,
    localFile: `data/review-sources/ga-2024-president-precinct-details/${fileName}`,
    precinctRows: detail.breakdownResults?.length || 0,
    voteTotal: detail.voteTotal || 0,
  };
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const jurisdiction = JSON.parse(await fs.readFile(jurisdictionPath, "utf8"));
  const counties = [...(jurisdiction.childLocalities || [])].sort((a, b) => text(a.name).localeCompare(text(b.name)));
  const results = [];
  const queue = [...counties];
  const workers = Array.from({ length: 8 }, async () => {
    while (queue.length) {
      const county = queue.shift();
      const result = await collectCounty(county);
      results.push(result);
      console.log(`${result.county}: ${result.precinctRows} precinct rows`);
    }
  });
  await Promise.all(workers);
  results.sort((a, b) => a.county.localeCompare(b.county));
  await fs.writeFile(
    manifestPath,
    `${JSON.stringify(
      {
        authority: "Georgia Secretary of State",
        electionId,
        sourcePage: "https://results.sos.ga.gov/results/public/Georgia/2024NovGen",
        rowLevel: "county official precinct",
        coverageStatus: "loaded",
        counties: results,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  console.log(`Wrote ${results.length} counties to ${path.relative(root, manifestPath)}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
