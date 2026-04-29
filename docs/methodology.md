# Methodology

This app is a local, auditable visualization of Wisconsin 2024 certified result
data. It is not a fraud detector. A `Flag` means a chart or metric crossed the
review threshold used in this app and deserves inspection against source data.

## Data Sources

- Presidential county results come from WEC `data/County by County Report_POTUS.pdf`.
- U.S. Senate county results come from WEC `data/County by County Report_US Senate.pdf`.
- Ward-level President and U.S. Senate results come from WEC `data/Ward by Ward
  Report Federal and State Contests.xlsx`.
- County shapes come from the U.S. Census TIGERweb State/County layer, saved as
  `data/wi-counties.geojson`.

## Completeness Check

The completeness check passes only when:

- all 72 Wisconsin counties are present,
- detailed candidate/write-in totals sum to each county's `Other` value,
- county totals sum to the WEC statewide presidential totals, and
- each county has a matching county polygon.

## Down-Ballot Difference

The app compares ward-level President votes with ward-level U.S. Senate votes by
party:

- Democratic drop-off: Harris votes minus Baldwin votes.
- Republican drop-off: Trump votes minus Hovde votes.

This is charted as a histogram of ward drop-off percentages. Positive values
mean the presidential candidate received more votes than the Senate candidate;
negative values mean the Senate candidate received more votes.

## Vote Share by Vote Count

The app charts each ward as a point:

- x-axis: candidate vote count in the ward,
- y-axis: candidate vote share in the ward.

Separate Trump and Harris trend lines are drawn. The app flags the check when
the absolute Pearson correlation between candidate vote count and candidate vote
share crosses the configured review threshold.

## Turnout Analysis

The turnout analysis is currently partial. The app has official ward vote totals
statewide, City of Milwaukee ward-level turnout denominators from a free
official City of Milwaukee report, and a Dane County official county-level
turnout total. It also has Jefferson County ward/reporting-unit registered-voter
and ballots-cast rows from the county's 2024 results page plus Oneida County
reporting-unit rows from its county voter turnout table. County-level rows are
useful for rough context, but they are not the same as ward-level denominator
data. Other counties remain missing until county/municipal canvass PDFs or web
tables are collected and imported.

Turnout requires:

- ballots cast,
- registered voters or eligible voters,
- geography that matches ward/precinct result rows, and
- the timing of the registration denominator.

Wisconsin allows Election Day registration. If a local report uses
pre-Election-Day registered-voter counts, the denominator can be lower than the
final registered-voter count and can show apparent turnout above 100%. The app
therefore displays warnings for `preElectionDay` or `unknown` denominator
timing.

## Reproducibility

Run:

```powershell
py scripts/build-data.py
py scripts/validate-data.py
```

Use `py scripts/import-turnout.py data/your-turnout-file.csv` when a county or
municipal turnout file has been converted to the required CSV format. Pass more
than one CSV to combine verified sources.
