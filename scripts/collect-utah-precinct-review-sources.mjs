import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = path.join(root, "data/review-sources/ut-2024-precinct-details");
const baseUrl = "https://electionresults.utah.gov/results/public/api";
const stateSlug = "utah";
const electionSlug = "general11052024";

function textValue(value) {
  if (Array.isArray(value)) {
    return value.find((item) => item.languageId === "en")?.text || value[0]?.text || "";
  }
  return String(value || "");
}

function slugFileName(slug, contest) {
  return `${slug}-${contest}.json`;
}

async function fetchJson(url) {
  let lastError = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(url, {
        headers: { "User-Agent": "state-election-data-builder/utah-review-source-collector" },
        signal: controller.signal,
      });
      if (response.ok) {
        return response.json();
      }
      lastError = new Error(`${response.status} ${response.statusText} for ${url}`);
    } catch (error) {
      lastError = error;
    } finally {
      clearTimeout(timeout);
    }
    await new Promise((resolve) => setTimeout(resolve, attempt * 500));
  }
  throw lastError;
}

async function fetchLocalBallotItem(slug, ballotItemId) {
  const directUrl = `${baseUrl}/elections/${slug}/${electionSlug}/ballot-items/${ballotItemId}`;
  try {
    return await fetchJson(directUrl);
  } catch (error) {
    const listUrl = `${baseUrl}/elections/${slug}/${electionSlug}/ballot-items`;
    const payload = await fetchJson(listUrl);
    const items = payload.data || payload;
    const item =
      items.find((entry) => entry.id === ballotItemId) ||
      items.find((entry) => textValue(entry.name).trim().toUpperCase() === "U.S. PRESIDENT");
    if (item?.breakdownResults?.length) {
      return item;
    }
    return null;
  }
}

function contestByName(items, label) {
  const normalized = label.toUpperCase();
  const item = items.find((entry) => textValue(entry.name).trim().toUpperCase() === normalized);
  if (!item) {
    throw new Error(`Could not find Utah state contest "${label}"`);
  }
  return item;
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const ballotItemsUrl = `${baseUrl}/elections/${stateSlug}/${electionSlug}/ballot-items`;
  const ballotItemsPayload = await fetchJson(ballotItemsUrl);
  const ballotItems = ballotItemsPayload.data || ballotItemsPayload;
  const president = contestByName(ballotItems, "U.S. President");
  const governor = contestByName(ballotItems, "Governor");

  const statePresident = await fetchJson(`${baseUrl}/elections/${stateSlug}/${electionSlug}/ballot-items/${president.id}`);
  const counties = [];
  const skippedCounties = [];

  for (const row of statePresident.breakdownResults) {
    const locality = row.locality;
    const county = textValue(locality.name).replace(/\s+County$/i, "");
    const presidentFile = slugFileName(locality.shortName, "president");
    let localPresident = null;
    try {
      localPresident = await fs.readFile(path.join(outputDir, presidentFile), "utf8").then(JSON.parse);
    } catch {
      localPresident = await fetchLocalBallotItem(locality.shortName, row.parentBallotItemId);
      if (!localPresident?.breakdownResults?.length) {
        skippedCounties.push({
          county,
          slug: locality.shortName,
          reason: "Official county API did not expose President precinct breakdown rows.",
          presidentVoteTotal: row.voteTotal,
          precinctReportingUnits: row.precinctReportingStatus?.totalUnits || null,
        });
        console.log(`${locality.shortName}: skipped, no President precinct breakdown`);
        continue;
      }
      await fs.writeFile(path.join(outputDir, presidentFile), `${JSON.stringify(localPresident, null, 2)}\n`);
    }
    counties.push({
      county,
      slug: locality.shortName,
      mapFeatureId: locality.mapFeatureId,
      presidentBallotItemId: row.parentBallotItemId,
      presidentFile,
      presidentVoteTotal: row.voteTotal,
      precinctReportingUnits: row.precinctReportingStatus?.totalUnits || null,
    });
    console.log(`${locality.shortName}: president ${localPresident.breakdownResults.length}`);
  }

  const manifest = {
    sourceAuthority: "Utah Lieutenant Governor / Vote.Utah.gov",
    sourceUrl: `https://electionresults.utah.gov/results/public/${stateSlug}/elections/${electionSlug}`,
    apiBaseUrl: baseUrl,
    electionSlug,
    stateContestIds: {
      president: president.id,
      governor: governor.id,
    },
    generatedAt: new Date().toISOString(),
    counties,
    skippedCounties,
  };
  await fs.writeFile(path.join(outputDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Wrote ${counties.length} Utah county source pairs to ${path.relative(root, outputDir)}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
