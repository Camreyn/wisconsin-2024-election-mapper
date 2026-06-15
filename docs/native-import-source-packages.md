# Native Import Source Packages

Checked at: 2026-06-15

This is a handoff package for the next native ETL states after Ohio and Wisconsin. It intentionally points to official source artifacts already stored in this repository. Generated `*-app-data.js` files are listed only as reference outputs; the native importer should parse the official artifacts directly.

## Recommended Order

1. Minnesota
2. Michigan
3. Pennsylvania

These states have county geometry, official presidential result artifacts, local review rows, same-grain comparison contest data, turnout sources, and expected validation totals already represented in `data/state-configs/`.

## Minnesota

- Config: `data/state-configs/mn.json`
- Reference bundle: `data/mn-app-data.js`
- Authority: Minnesota Secretary of State
- County results source: `data/mn-2024-general-federal-state-results-by-precinct-official.xlsx`
- Local review source: `data/mn-2024-general-federal-state-results-by-precinct-official.xlsx`
- Comparison contest: U.S. Senate, same precinct rows
- Turnout source: `data/mn-2024-general-federal-state-results-by-precinct-official.xlsx`
- Turnout denominator: `REG7AM + EDR`
- County boundary: `data/mn-counties.geojson`

Expected validation:

| Metric | Value |
| --- | ---: |
| County rows | 87 |
| County geometry features | 87 |
| Trump | 1,519,032 |
| Harris | 1,656,979 |
| Other | 77,909 |
| State total | 3,253,920 |
| Local review rows | 4,075 |
| Turnout rows | 4,103 |

Caveat: precinct boundary GeoJSON is not included. County map joins are ready.

## Michigan

- Config: `data/state-configs/mi.json`
- Reference bundle: `data/mi-app-data.js`
- Authority: Michigan Secretary of State
- County results source: `data/mi-2024-general-election-results.txt`
- Local review source: `data/mi-2024-precinct-results.zip`
- Comparison contest: U.S. Senate, same precinct ZIP tables
- Turnout source: `data/mi-2024-voter-turnout.txt` plus `data/mi-2024-registered-voter-count.pdf`
- Turnout denominator: November active registered voters
- County boundary: `data/mi-counties.geojson`

Expected validation:

| Metric | Value |
| --- | ---: |
| County rows | 83 |
| County geometry features | 83 |
| Trump | 2,816,636 |
| Harris | 2,736,533 |
| Other | 111,017 |
| State total | 5,664,186 |
| Local review rows | 4,428 |
| Turnout rows | 83 |

Caveats: MVIC live download endpoints are browser-protected, but the official downloaded artifacts are present. Turnout is county-level. Precinct boundary GeoJSON is not included.

## Pennsylvania

- Config: `data/state-configs/pa.json`
- Reference bundle: `data/pa-app-data.js`
- Authority: Pennsylvania Department of State
- County results source: `data/pa-2024-general-election-returns-precinct.txt`
- Local review source: `data/pa-2024-general-election-returns-precinct.txt`
- Comparison contest: U.S. Senate, same precinct returns file
- Turnout source: `data/pa-2024-voter-registration-vote-history-summary.xlsx`
- Turnout denominator: registered voters
- County boundary: `data/pa-counties.geojson`

Expected validation:

| Metric | Value |
| --- | ---: |
| County rows | 67 |
| County geometry features | 67 |
| Trump | 3,543,041 |
| Harris | 3,420,865 |
| Other | 67,831 |
| State total | 7,031,737 |
| Local review rows | 9,154 |
| Turnout rows | 67 |

Caveats: the official readme says the election returns data was extracted January 10, 2025; the direct file name includes `20250129`. Turnout is county-level. Precinct boundary GeoJSON is not included.

## Native ETL Acceptance Criteria

For each state, the native importer should fail before promotion if:

- Any listed local artifact is missing.
- County row count does not match the expected count.
- County geometry feature count does not match the expected count.
- `trump + harris + other` does not equal state total.
- Local review rows fail to produce county-normalized groups.
- President-vs-Senate comparison rows fail to join at the local reporting-unit grain.
- Turnout rows fail to join to county names used by county results.
- Source URL, local artifact path, parser name, and validation totals are not recorded in import provenance.

