# Turnout Source Packages

Checked at: 2026-06-16

This file summarizes turnout source packages that can be used by Civic Result Maps native ETL. The package is intentionally source-first: native importers should parse the listed official artifacts or normalized CSV files directly, not generated app bundles.

## Wisconsin

Status: partial official local sources available

Wisconsin has native results/review data available, but a statewide ward-level turnout denominator source is not currently present. The legacy repo has a partial turnout package covering four counties:

| County | Level | Rows | Denominator Timing | Warning Rows |
| --- | --- | ---: | --- | ---: |
| Milwaukee | ward | 355 | preElectionDay | 355 |
| Dane | county | 1 | final | 0 |
| Jefferson | ward | 34 | unknown | 34 |
| Oneida | ward | 22 | preElectionDay | 22 |

Expected package totals:

| Metric | Value |
| --- | ---: |
| Covered counties | 4 |
| Missing counties | 68 |
| Rows | 412 |
| Ward-level rows | 411 |
| County-level rows | 1 |
| Warning rows | 411 |
| Partial ballots-cast total | 691,073 |
| Partial registered-voter total | 769,431 |

Source artifacts:

- `data/wi-2024-turnout-source-package.json`
- `data/wi-2024-turnout-partial.csv`
- `data/milwaukee-city-turnout.csv`
- `data/City of Milwaukee 2024 General Election Ward by Ward Results.pdf`
- `data/dane-county-turnout.csv`
- `data/dane-2024-general-result.html`
- `data/jefferson-county-turnout.csv`
- `data/jefferson-2024-general-result.html`
- `data/oneida-county-turnout.csv`
- `data/oneida-2024-general-result.html`

Reference generated output:

- `data/turnout-data.json`
- `data/turnout-data.js`

Parser contract:

- Primary native artifact: `data/wi-2024-turnout-partial.csv`
- State-specific manifest: `data/wi-2024-turnout-source-package.json`
- Format: normalized turnout CSV
- Required columns: `state`, `county`, `municipality`, `ward`, `source_level`, `ballots_cast`, `registered_voters`, `registration_denominator_timing`, `denominator_type`, `coverage_status`, `warning_required`, `source_url`
- Optional columns: `notes`
- Warning required when denominator timing is `preElectionDay` or `unknown`
- Ward-level join keys: `county`, `municipality`, `ward`
- Dane join key: `county`

Important caveats:

- This package is not statewide Wisconsin turnout coverage.
- The WEC ward-by-ward federal/state results workbook does not include registered-voter denominators.
- Wisconsin same-day registration means pre-Election-Day denominators can understate final registered voters.
- Jefferson denominator timing is not stated and must be warning-gated.
- Dane is county-level only, not ward-level.
- Ward labels need normalization before joining to WEC ward result rows.

Native ETL should import these rows as partial Wisconsin turnout and expose missing counties explicitly.
