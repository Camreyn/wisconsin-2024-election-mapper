# Methodology

This app is a local, auditable visualization of certified 2024 presidential
result data by state. It is not a fraud detector. A `Flag` means a chart or
metric crossed the review threshold used in this app and deserves inspection
against official source data.

## Data Sources

- Presidential county results come from state election authority files, official
  public results portals, or documented local source files configured per state.
- Review graphs use President plus a same-grain comparison contest only when
  both are mapped from official local rows.
- Turnout rows use official turnout or registration denominator sources where
  those sources have been imported and documented.
- County or district shapes generally come from U.S. Census TIGERweb geometry,
  with exceptions documented in the selected state's source inventory.

## Completeness Check

For each loaded state, the completeness check passes only when:

- the expected county or district rows are present,
- detailed candidate/write-in totals sum to each county's `Other` value,
- county totals sum to the official statewide presidential totals, and
- each mapped row has matching geometry.

## Down-Ballot Difference

Where review graphs are enabled, the app compares local President votes with a
same-grain comparison contest by party:

- Democratic drop-off: Harris votes minus the same-row Democratic comparison candidate.
- Republican drop-off: Trump votes minus the same-row Republican comparison candidate.

This is charted as a histogram of local-row drop-off percentages. Positive values
mean the presidential candidate received more votes than the comparison candidate;
negative values mean the comparison candidate received more votes.

## Vote Share by Vote Count

The app charts each loaded local result row as a point:

- x-axis: candidate vote count in the local row,
- y-axis: candidate vote share in the local row.

Separate Trump and Harris trend lines are drawn. The app flags the check when
the absolute Pearson correlation between candidate vote count and candidate vote
share crosses the configured review threshold.

## Turnout Analysis

Turnout coverage varies by state. Some states have county rows, some have
statewide-only rows, and some have local reporting-unit denominators. County-level
rows are useful for rough context, but they are not the same as precinct or ward
denominator data. Missing rows remain unavailable until official state, county,
or municipal canvass PDFs, spreadsheets, or web tables are collected and imported.

Turnout requires:

- ballots cast,
- registered voters or eligible voters,
- geography that matches ward/precinct result rows, and
- the timing of the registration denominator.

If a local report uses pre-election registered-voter counts, active-voter counts,
post-election counts, or otherwise limited denominators, the app labels those
rows with warnings. In states with same-day registration, a pre-Election-Day
denominator can be lower than the final registered-voter count and can show
apparent turnout above 100% without implying excess ballots.

## Reproducibility

Run:

```powershell
py scripts/build-data.py
py scripts/validate-data.py
```

Use `py scripts/import-turnout.py data/your-turnout-file.csv` when a county or
municipal turnout file has been converted to the required CSV format. Pass more
than one CSV to combine verified sources.
