# Task: Collect Historical Baseline Data

## Purpose

Answer the question: **Were the patterns visible in the 2024 Wisconsin graphs
already present in earlier elections?**

This is a data-collection task only. Do not add historical charts to the web app
until the source files, provenance notes, and validation checks are complete.

The historical baseline should help distinguish:

- a pattern that is visible in 2024 but also common in earlier elections,
- a pattern that changed noticeably in 2024, and
- a pattern that cannot be compared reliably because the available source rows
  use different geography or were redistributed from reporting units.

It will not prove or disprove tampering by itself. It identifies where official
records review is most useful.

## Important Source Rule

Keep these source classes separate:

1. **Native official result rows**: the original reporting-unit or ward rows
   published for that election.
2. **Harmonized LTSB comparison rows**: historical results redistributed onto a
   common ward layer by the Wisconsin Legislative Technology Services Bureau
   (LTSB).

LTSB's public historical data is useful for comparisons across elections, but
LTSB documents that some election totals were disaggregated from reporting units
to wards using population-based allocation. Those rows may not equal the
original ward totals. The eventual app must label them as harmonized comparison
data, not as exact native ward records.

## Collection Matrix

| Priority | Election / source | What to collect | Can it be collected? | Collection path |
| --- | --- | --- | --- | --- |
| P0 | 2024 WEC native rows | President and U.S. Senate ward/reporting-unit rows already used by the app | Yes. Already collected. | Preserve `data/Ward by Ward Report Federal and State Contests.xlsx` and the generated `data/ward-analysis.json` as the native 2024 reference. |
| P0 | 2012, 2016, and 2020 LTSB historical rows | Harmonized presidential results, municipal identifiers, ward identifiers, reporting-unit notes, and geography fields | Yes. Public and free. | Download the LTSB `2012-2020 Election Data (with 2020 Wards)` dataset from the LTSB GIS Hub or its catalog record. Extract the 2012, 2016, and 2020 presidential fields. |
| P1 | 2016 native rows | Original and recount ward-level presidential workbook | Yes. Confirmed downloadable from an archived official WEC URL. | Download `Ward by Ward Original and Recount President of the United States.xlsx` from the archived WEC attachment URL listed below. |
| P1 | 2012 and 2020 native rows | Original or final recount-aware ward-level presidential workbooks | Official archive pages and attachment names were found. The tested spreadsheet bytes were not retrievable from the live URLs or the tested Internet Archive snapshots. | Request the named files from WEC. Use the archived official landing pages as evidence that the files were published. |
| P1 | 2024 LTSB comparison rows | Harmonized 2024 ward-level results and boundaries for an apples-to-apples LTSB comparison | Likely collectable. | Check the LTSB GIS Hub first. A public data index also lists Wisconsin State Legislature 2024 ward-level results and boundaries. Preserve the source URL and confirm the publisher before import. |
| P2 | Historical turnout denominators | Ballots cast, registered voters, denominator timing, municipality, and ward/reporting unit for each year | Partially collectable. Coverage will vary by county and year. | Reuse the current county-by-county local canvass workflow. Import only rows with a source URL and a denominator-timing label. Track missing counties explicitly. |
| P2 | Historical municipal boundaries | Election-year ward boundaries or crosswalk fields needed to explain changed wards | Yes for many snapshots. | Download LTSB municipal ward snapshots where needed. Use them for comparison notes and crosswalk work, not as a substitute for election-result records. |

## Recommended First Baseline

Build the first useful baseline with:

| Analysis | Elections | Reason |
| --- | --- | --- |
| Presidential vote-share by vote count | 2012, 2016, 2020, 2024 | Directly answers whether the visible presidential pattern existed before 2024. |
| County and major-city presidential totals | 2012, 2016, 2020, 2024 | Easier to compare than individual wards and less sensitive to ward-boundary changes. |
| President vs U.S. Senate difference | 2012, 2016, and 2024 | Secondary same-ballot check for presidential years that also included a Wisconsin U.S. Senate contest. |

Do **not** present a 2020 President-vs-Senate comparison: Wisconsin did not have a
U.S. Senate contest on the 2020 general-election ballot. An alternative such as
U.S. House totals could be explored later, but it is not directly equivalent and
must be labeled separately.

Do **not** add non-presidential control years to the first baseline. Keeping the
main comparison limited to presidential elections makes the result easier to
interpret and explain.

Turnout history is a separate workstream. It is valuable but should not block the
first vote-share baseline.

## Required Result Schema

Create a normalized historical results file with one row per source result row
and candidate:

```text
electionYear
electionDate
contestId
contestName
office
party
candidate
county
municipality
reportingUnit
ward
votes
sourceClass
sourceLevel
rowMethod
sourceUrl
sourceFile
sourceSha256
notes
```

Required controlled values:

```text
sourceClass: nativeOfficial | harmonizedLtsb
sourceLevel: ward | reportingUnit | municipality | county
rowMethod: original | ltsbPopulationAllocation | unknown
```

Never silently treat `harmonizedLtsb` rows as `nativeOfficial` rows.

## Required Source Manifest

Create `data/historical/source-manifest.json` with one entry for every downloaded
file:

```text
id
electionYear
sourceClass
publisher
title
sourceUrl
downloadedAt
localFile
sha256
licenseOrAccessNote
methodologyNote
```

Save raw downloads under:

```text
data/historical/raw/
```

Save generated normalized artifacts under:

```text
data/historical/generated/
```

## Collection Workflow

### Phase 1: Freeze And Describe The 2024 Reference

- [x] Preserve the existing WEC 2024 spreadsheet as the native reference file.
- [x] Add its source URL, local filename, SHA-256 hash, and row count to the
      historical source manifest.
- [x] Record that the current app uses the 2024 WEC ward/reporting-unit export,
      not an LTSB harmonized historical layer.

### Phase 2: Download Free LTSB Baseline Files

- [x] Download `2012-2020 Election Data (with 2020 Wards)`.
- [x] Inspect field definitions before writing an importer.
- [x] Identify the presidential fields for 2012, 2016, and 2020.
- [x] Identify the U.S. Senate fields for 2012 and 2016 as secondary
      same-ballot comparisons.
- [x] Record every collected file in `data/historical/source-manifest.json`.

### Phase 3: Add A Historical Importer

Add:

```text
scripts/import-historical-baseline.py
scripts/validate-historical-baseline.py
```

The importer should:

- [x] read downloaded LTSB files using a structured parser,
- [x] emit normalized artifacts rather than embedding source-specific column names in
      the app,
- [x] retain the original geographic identifiers,
- [x] mark LTSB rows as `harmonizedLtsb`,
- [x] set `rowMethod` from the source methodology,
- [x] emit row counts and aggregate totals by election, contest, county, and
      municipality, and
- [x] fail when required fields or provenance values are missing.

### Phase 4: Reuse Existing Build And Validation Patterns

Reuse the repo's current patterns:

- `scripts/build-data.mjs` already converts checked JSON artifacts into static
  browser-ready JavaScript.
- `scripts/validate-data.mjs` already verifies row counts, geography coverage,
  and statewide totals for 2024.
- `scripts/import-turnout.py` already enforces turnout source URLs and
  registration-denominator timing.

Extend these patterns later by:

- [x] adding a historical JSON-to-JS build output,
- [x] validating historical statewide totals against source totals and
      documenting the native-vs-harmonized `2016` county-level difference,
- [x] validating that every historical row declares `sourceClass` and
      `rowMethod`,
- [x] reporting county coverage for each generated series,
- [x] rejecting duplicate normalized keys, and
- [x] keeping native and harmonized analyses in separate result groups.

The current repo does **not** contain a general WEC spreadsheet parser. Reuse the
existing schemas and validators, but add a dedicated structured importer after
the historical column layout has been inspected.

### Phase 5: Request Native Historical Rows

The archive search found official landing pages for all three older
presidential elections. The `2016` native workbook is preserved and
downloadable. Request the `2012` and `2020` native files from WEC unless another
official byte-for-byte copy is located.

Request:

```text
For the November 6, 2012 general election, please provide the original file
published as "CanvassResults_Presidential_by_Assembly_Senate.xls" and, if
available, "Ward by Ward_11.6.12 Gen Election_all offices.xls".

For the November 3, 2020 general election, please provide the final
recount-aware ward-level presidential workbook published as "Ward by Ward
Report PRESIDENT OF THE UNITED STATES by State Representive District - After
Recount.xlsx". Please also provide the originally published workbook "Ward by
Ward Report - President of the United States (under recount).xlsx" if it remains
available.

For each file, please include any field definitions, identifiers for combined
wards or reporting units, and methodology notes describing aggregation or
later corrections.
```

- [ ] Track the request date, contact, response date, source URL or attachment,
      and outcome.
- [ ] Preserve received files unchanged under `data/historical/raw/`.
- [ ] Import received native rows separately from LTSB harmonized rows.

### Phase 6: Optional Historical Turnout Collection

Repeat the 2024 local workflow one election year and one county at a time:

- [ ] Search county and municipal canvass archives.
- [ ] Collect `county`, `municipality`, `ward`, `ballots_cast`,
      `registered_voters`, `registration_denominator_timing`, and `source_url`.
- [ ] Add `election_year` to a historical turnout template before importing.
- [ ] Mark pre-Election-Day or unknown denominators with the existing warning
      rule.
- [ ] Maintain a missing-county tracker for every historical year.

## Validation Checklist

Before historical charts are added:

- [x] Source manifest exists and every collected raw file has a SHA-256 hash.
- [x] Every normalized row has a source URL, source class, source level, and row
      method.
- [x] Statewide totals reconcile to the source datasets.
- [x] Native-vs-harmonized county-level differences are documented and kept in
      separate result groups.
- [x] Any total that does not reconcile is documented and excluded from graphs
      until resolved.
- [x] Historical ward-boundary changes are disclosed.
- [x] LTSB harmonized rows are labeled as redistributed comparison data in the
      generated artifacts.
- [x] Native official rows and harmonized LTSB rows can be analyzed separately.
- [x] The initial generated baseline covers the 2012, 2016, 2020, and 2024 presidential
      elections as described above.

## Deliverable Before Web-App Work

Produce a short collection report containing:

1. downloaded source files and hashes,
2. import results and row counts,
3. missing files or open WEC requests,
4. totals-reconciliation results,
5. known limitations, and
6. a recommendation on which historical comparisons are ready to display.

## Verified Starting Links

- LTSB GIS Hub download page:
  <https://gis-ltsb.hub.arcgis.com/pages/download-data>
- Public catalog record for LTSB `2012-2020 Election Data (with 2020 Wards)`:
  <https://geodiscovery.uwm.edu/catalog/317F4F49-5B17-43CC-9BCA-36ED25DC9E15>
- LTSB-linked January 2024 municipal ward snapshot:
  <https://data-ltsb.opendata.arcgis.com/datasets/LTSB::wi-municipal-wards-jan-2024>
- WEC website:
  <https://elections.wi.gov/>
- Wisconsin MyVote result-reporting explanation:
  <https://myvote.wi.gov/en-us/Election-Results>

## Native Historical Source Discovery

These official pages and filenames were verified during the archive search.

### 2012

Archived official Wisconsin Government Accountability Board landing page:

<https://web.archive.org/web/20121208020848id_/http://gab.wi.gov:80/elections-voting/results/2012/fall-general>

The page states that the November 6, 2012 results were certified on November
29, 2012. It lists:

- `Ward by Ward_11.6.12 Gen Election_President.pdf`
- `Ward by Ward_11.6.12 Gen Election_all offices.xls`
- `CanvassResults_Presidential_by_Assembly_Senate.xls`

The final workbook is labeled on the page as:

```text
Ward-by-Ward Canvass Results for President with State Senate and Assembly
Districts.xls
```

Status: **official landing page confirmed; tested spreadsheet attachment bytes
not retrieved from the archive snapshot. Request the original files from WEC.**

### 2016

Archived official WEC landing page:

<https://web.archive.org/web/20161223044005id_/http://elections.wi.gov/elections-voting/results/2016/fall-general>

Preferred native workbook:

<https://web.archive.org/web/20161214185442id_/http://elections.wi.gov/sites/default/files/Ward%20by%20Ward%20Original%20and%20Recount%20President%20of%20the%20United%20States.xlsx>

Status: **confirmed downloadable**. The archive returned an XLSX file with
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` content type
and `739628` bytes.

### 2020

Archived official WEC landing page:

<https://web.archive.org/web/20201214172750id_/https://elections.wi.gov/elections-voting/results/2020/fall-general>

The page lists:

- `Ward by Ward Report - President of the United States (under recount).xlsx`
- `Ward by Ward Report by Congressional District - President of the United
  States (under recount).xlsx`
- `Ward by Ward Report PRESIDENT OF THE UNITED STATES by State Representive
  District - After Recount.xlsx`

Status: **official landing page confirmed; tested spreadsheet attachment bytes
not retrieved from the live URL or the tested archive snapshot. Request the
final recount-aware workbook from WEC.**
