# Next-State Source Collection Prompt

Use this prompt when collecting 2024 election source metadata for another state.
The current web app can accept additional states in the Source Planner registry,
certified county result views, precinct/reporting-unit review graphs, and
turnout rows when source data can be normalized into the app schemas. County
geometry and historical baseline views still need state-specific imports.

```text
Collect the 2024 presidential election source plan for [STATE].

Goal:
- Build a county-level source ledger that can be added to this app's Source
  Planner, modeled after the Wisconsin `STATE_SOURCE_PLANS.WI` entry in
  `app.js`.
- Capture where each election number comes from, when each source file appears
  to have been posted or modified, and what confidence caveats apply.

Required state-level fields:
- state code
- state name
- election year
- office or contest
- state election authority
- county-equivalent label, such as County, Parish, Borough, Municipality, or
  Election District

For certified county-level presidential results:
- Official source title
- Direct source URL
- Local filename to save under `data/`
- Whether the file is official, certified, unofficial, amended, or archived
- HTTP `Last-Modified` header from the live source URL, if exposed
- Any page-level posted date shown by the election authority
- Internet Archive first 200 capture date, if available
- Timestamp basis note, distinguishing exact posted date from HTTP file
  metadata or archive capture metadata
- Column/schema notes needed to normalize county rows into:
  `county`, `trump`, `harris`, `other`, `total`, candidate/write-in columns,
  `margin`, and vote-share fields

For ward, precinct, or reporting-unit detail:
- Official source title
- Direct source URL
- Local filename to save under `data/`
- Whether the row level is ward, precinct, reporting unit, municipality, county,
  or mixed
- HTTP `Last-Modified` header, page posted date, and archive first capture date
  when available
- Timestamp basis note
- Contest columns available, especially President and U.S. Senate or another
  statewide down-ballot contest
- Any known row aggregation caveats, split precinct caveats, or amended-file
  caveats

For turnout denominator sources:
- County or local source URL for ballots cast and registered-voter or
  eligible-voter denominator data
- Source level: ward, precinct, municipality, county, or mixed
- Whether denominator timing is final, pre-election, Election Day, unknown, or
  not stated
- HTTP `Last-Modified` header, page posted date, and archive first capture date
  when available
- Import status: imported, missing, checked-but-not-imported, or unusable
- Missing fields if unusable
- Warning note if the denominator can produce misleading turnout rates

Deliverables:
- A proposed `STATE_SOURCE_PLANS.[STATE_CODE]` object for `app.js`.
- A source inventory row list with:
  `category`, `file_or_local_data`, `source_url`,
  `source_last_modified_utc`, `source_timestamp_basis`, `used_for`,
  and `confidence_or_status`.
- A county source-plan CSV-ready table with:
  `state`, `election_year`, `office`, `county`,
  `certified_result_source`, `certified_result_url`,
  `certified_result_last_modified_utc`,
  `certified_result_timestamp_basis`, `ward_detail_source`,
  `ward_detail_url`, `ward_detail_last_modified_utc`,
  `ward_detail_timestamp_basis`, `turnout_status`, `turnout_sources`,
  `turnout_source_timestamp_basis`, `turnout_warning_rows`, and `follow_up`.
- A short readiness note saying which capability tier the state can enter:
  Source Planner only, certified county results, review graphs, turnout rows,
  county map geometry, or historical baseline.

Do not infer exact public posting dates from HTTP headers. Label them as server
file metadata unless the election authority page itself provides a posted date.
```

## Current Integration Point

Add source-ledger-only states to `STATE_SOURCE_PLANS` in `app.js`. That will
populate the Source Planner state dropdown, summary cards, county table, and
Source Plan CSV export. Add states with app data to `APP_STATES` and wire each
capability flag to only the normalized bundles that actually exist.

Full app support for a new state also needs separate work:

- State-specific county result data in the app result schema.
- County boundary geometry for the map.
- Ward/reporting-unit analysis rows for review graphs.
- Optional turnout imports using state-specific denominator rules.
- UI copy and route naming that no longer assumes one state everywhere.
- Validation rules for the new state's source totals and geography.
