# Historical Presidential Baseline Collection Status

Collected on `2026-05-31` Central Time. The machine-readable source inventory is
in `source-manifest.json`.

## Ready For Import

### LTSB Harmonized Historical Baseline

Collected:

```text
raw/WI_20122020_Election_Data_Wards_2020.zip
```

Source:

<https://web.s3.wisc.edu/rml-gisdata/WI_20122020_Election_Data_Wards_2020.zip>

Catalog record:

<https://geodiscovery.uwm.edu/catalog/317F4F49-5B17-43CC-9BCA-36ED25DC9E15>

SHA-256:

```text
2d61638f5439c74ac47105e67e7f5a46d21151485ca2b25f087d6fab06ff08d1
```

Inspection result:

- Archive contains a shapefile package with `7,078` harmonized ward rows.
- It has presidential fields for all required historical baseline elections:
  - `2012`: `PRETOT12`, `PREDEM12`, `PREREP12`
  - `2016`: `PRETOT16`, `PREDEM16`, `PREREP16`
  - `2020`: `PRETOT20`, `PREDEM20`, `PREREP20`
- These rows are suitable for a historical comparison baseline.
- These rows must be labeled as LTSB harmonized comparison data. They are not
  interchangeable with exact native reporting-unit rows because LTSB documents
  population-based allocation for some source totals.

### 2016 Native WEC Presidential Workbook

Collected:

```text
raw/2016-wec-native-president-original-and-recount.xlsx
```

Source:

<https://web.archive.org/web/20161214185442id_/http://elections.wi.gov/sites/default/files/Ward%20by%20Ward%20Original%20and%20Recount%20President%20of%20the%20United%20States.xlsx>

Official archived landing page:

<https://web.archive.org/web/20161223044005id_/http://elections.wi.gov/elections-voting/results/2016/fall-general>

SHA-256:

```text
2fb106636e49ecd95a677499453d5c4cfdcc30028de37b92e229f24dd8b57715
```

Inspection result:

- Workbook opened successfully.
- Main sheet has `3,638` rows and `40` columns.
- It includes county, municipality, and reporting-unit identifiers.
- It includes separate original and recount canvass columns for presidential
  candidates.

### 2024 Native WEC Workbook

Frozen historical-reference copy:

```text
raw/2024-wec-native-ward-federal-state-contests.xlsx
```

Source:

<https://web.archive.org/web/20241130045633id_/https://elections.wi.gov/sites/default/files/documents/Ward%20by%20Ward%20Report%20by%20Congressional%20District_November%205%202024%20General%20Election_Federal%20and%20State%20Contests.xlsx>

SHA-256:

```text
d23ebca4e718274c3890bfc4db9454573ecb6e2048a58b18b70a57d4c6094c67
```

Inspection result:

- This is a copy of the native WEC workbook already used by the app.
- The existing app validator confirms `3,503` WEC ward/reporting-unit rows.

## Imported And Validated Baseline

Run:

```text
python scripts/import-historical-baseline.py
python scripts/validate-historical-baseline.py
```

Generated artifacts:

| File | Purpose |
| --- | --- |
| `generated/historical-presidential-results.csv.gz` | Normalized candidate-level rows with source URL, source class, row method, source filename, and SHA-256 provenance repeated on every record. |
| `generated/historical-presidential-summary.json` | Graph-ready rows plus statewide, county, and municipality aggregates. Native official and harmonized LTSB series remain separate. |
| `generated/historical-reconciliation-report.json` | Machine-readable reconciliation checks and documented caveats. |
| `generated/ltsb-masked-presidential-rows.json` | The `70` LTSB harmonized geography rows whose presidential values are masked as `****`. They are preserved as missing and excluded from graph-ready rows. |

Browser-ready app bundle:

```text
data/historical-data.js
```

The app's Historical Baseline tab displays the `2012`, `2016`, `2020`, and
`2024` presidential comparison series with visible source-row labels and a
ward-boundary disclosure. Run `npm.cmd run build:history` after regenerating the
historical artifacts.

Validation result:

```text
status: passed
normalized candidate rows: 95,397
analysis series: 6
reconciliation checks: 7
masked LTSB rows preserved: 70
```

Statewide presidential totals reconcile for:

| Series | Democratic | Republican | Other | Total |
| --- | ---: | ---: | ---: | ---: |
| `2012` LTSB harmonized | 1,620,985 | 1,407,966 | 39,483 | 3,068,434 |
| `2016` LTSB harmonized | 1,382,536 | 1,405,284 | 188,330 | 2,976,150 |
| `2016` WEC native recount | 1,382,536 | 1,405,284 | 188,330 | 2,976,150 |
| `2020` LTSB harmonized | 1,630,866 | 1,610,184 | 56,991 | 3,298,041 |
| `2024` WEC native | 1,668,229 | 1,697,626 | 57,063 | 3,422,918 |

The native WEC `2016` recount workbook and the LTSB harmonized `2016` layer
match statewide. They are still not interchangeable at county level: the LTSB
layer shifts `7` votes from Buffalo County to Trempealeau County relative to
the native workbook (`3` Democratic and `4` Republican votes). The importer
expects and reports this difference, and it fails if the observed difference
changes.

## Official Landing Pages Preserved

The archived official result pages are saved locally because they identify the
published attachment names and provide provenance even when spreadsheet bytes
are missing.

| Election | Local file | SHA-256 |
| --- | --- | --- |
| `2012` | `raw/2012-gab-official-results-page.html` | `a750be40970cea9a579a88e476c4f7a9fd498f00da923c71ef6d60303598683d` |
| `2016` | `raw/2016-wec-official-results-page.html` | `70c9670854a9228fda2543b08c079b24795b90dc67dfff6ed4d462770de9a7b3` |
| `2020` | `raw/2020-wec-official-results-page.html` | `e9f62f9e93538f68402be58b32f37f47f739edb5e8c4abf01e58b7884a202fde` |

## Missing Native Official Workbooks

### 2012

Missing native attachment:

```text
CanvassResults_Presidential_by_Assembly_Senate.xls
```

Also request if available:

```text
Ward by Ward_11.6.12 Gen Election_all offices.xls
```

The official archived G.A.B. landing page confirms that these files were
published:

<https://web.archive.org/web/20121208020848id_/http://gab.wi.gov:80/elections-voting/results/2012/fall-general>

The tested spreadsheet attachment URLs did not return spreadsheet bytes.

### 2020

Missing final recount-aware native attachment:

```text
Ward by Ward Report PRESIDENT OF THE UNITED STATES by State Representive
District - After Recount.xlsx
```

Also request the originally published workbook if available:

```text
Ward by Ward Report - President of the United States (under recount).xlsx
```

The official archived WEC landing page confirms that these files were
published:

<https://web.archive.org/web/20201214172750id_/https://elections.wi.gov/elections-voting/results/2020/fall-general>

The tested live attachment URLs and tested archive snapshots did not return
spreadsheet bytes.

A third-party page links to a mirror of the under-recount workbook, but its
download URL currently returns an HTML `404` page rather than spreadsheet
bytes. It is recorded as missing in the manifest and was not used.

The same third-party page still provides a real XLSX supplemental workbook with
registration, voter, and ballot fields:

```text
WISelectionDAYregistrantsCOLUMNiNOV3rd2020.xlsx
```

That supplemental workbook is preserved as
`raw/2020-election-day-registrants-third-party-mirror.xlsx`. It is retained for
evaluation only. It is not treated as verified official bytes and is not
imported into the app analysis unless WEC supplies the original or an official
hash match is established.

## What Is Still Needed

To build a clearly labeled first historical baseline:

- [x] Add a structured importer for the collected LTSB shapefile.
- [x] Validate LTSB statewide totals for `2012`, `2016`, and `2020`.
- [x] Import and validate the collected native `2016` WEC workbook separately.
- [x] Compare native and harmonized `2016` county totals and document the
      Buffalo County / Trempealeau County harmonization difference.
- [ ] Request the missing native official `2012` and `2020` workbooks from WEC.
- [ ] Keep native WEC rows and LTSB harmonized rows separate in all generated
      artifacts and future charts.

The imported LTSB archive is sufficient to begin a historical presidential
baseline now.
The missing native `2012` and `2020` files remain important because they would
strengthen the ward-level comparison and reduce reliance on harmonized values.
