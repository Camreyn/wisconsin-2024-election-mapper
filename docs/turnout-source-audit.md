# Turnout Source Audit

Checked: 2026-06-08

This audit captures Leif's highest-priority missing data for all 50 states: ballots-cast turnout rows plus registered-voter or eligible-voter denominators, preferably at precinct/VTD/ward level. It now tracks both loaded app turnout sources and remaining source/parsing gaps.

## Coverage Summary

- Loaded: 35
- Loaded Partial: 3
- Loaded Statewide Only: 11
- Partial Loaded: 1

Known-good loaded states remain AL, FL, MI, MN, ND, and PA. Wisconsin is partial because the WEC statewide ward results do not include denominator fields and only some local turnout rows have been imported.

## Best Next Imports

The quickest wins are states marked `usable_candidate`: they appear to have official statewide or state-hosted county turnout denominator sources and mainly need download/parser work. States marked `parser_needed` already have strong official sources but need source-specific mapping. States marked `source_needs_review` need a scripted portal/export capture or field confirmation. States marked `county_local_required` likely need county-by-county official report collection.

## Loaded Or Partial

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |
| AK | Loaded | precinct plus district-level voting-method rows aggregated to house district | loaded: alaskaEnrHouseDistrictTurnout | App imports 40 mapped State House District turnout rows from the official ENR CSV. HD99 Federal Overseas Absentee is documented and excluded because it has no district polygon. |
| AL | Loaded | county | loaded: alabamaPrecinctZipTurnout | App already imports county turnout from official results plus registration workbook; precinct-level denominator support is not loaded. |
| AR | Loaded | statewide | loaded: arkansasTotalResultsStatewideJson | App imports the official statewide registered-voter and total-ballots-cast turnout object with warnings; county-level denominator rows still need a separate official source. |
| CA | Loaded | county | loaded: californiaParticipationPdf | Registered-voter totals are based on the 15-day Report of Registration and exclude later same-day registrations. |
| CO | Loaded | county | loaded: coloradoGeneralTurnoutPdf | App imports the 2024 General Election county turnout table calculated as a percentage of registered voters and validates the published statewide totals. |
| CT | Loaded | planningRegion | loaded: connecticutStatementTurnoutPdf | App parses 169 official town turnout columns from Statement of Vote pages 157-162 and rolls them up to Census planning-region geometry. Rows are warning-labeled because the denominator is the active official checklist while the turnout section also reports same-day registration activity. |
| DE | Loaded | statewide | loaded: delawareReportHtml | App imports the official report-page summary as a single statewide-only turnout row. County-level turnout denominator rows were not exposed in the loaded report, so rows are warning-labeled as statewide-only coverage. |
| FL | Loaded | precinct | loaded: floridaPrecinctZipTurnout | App already imports precinct turnout rows from official precinct-level results. |
| HI | Loaded | county | loaded: hawaiiCountySummaryPdfs | App imports county registration, turnout, mail turnout, and in-person turnout from the four official county summary PDFs; Kalawao is not a separate presidential county result row in the loaded Hawaii data. |
| IA | Loaded | county | loaded: iowaTurnoutCsv | App imports 99 county rows from a local CSV derived from the official PDF text, uses active plus inactive voters as the denominator, and validates county sums against the report Total row. Rows are warning-labeled because the denominator is an Election Day snapshot. |
| ID | Loaded | county | loaded: idahoTurnoutHtml | Official turnout table includes county election-day registrations, registered voters, ballots cast, and turnout. |
| IN | Loaded | county | loaded: indianaTurnoutPdf | Statewide official county report is available; precinct-level denominator source would need county-local reports. |
| KS | Loaded | state/county | loaded: kansasTurnoutXlsx | App imports county ballots cast, registered voters, and turnout percentage from the official workbook 2024 Turnout sheet; precinct-level denominator support is not loaded. |
| KY | Loaded | county | loaded: kentuckyTurnoutPdf | App imports 120 county rows with total registered voters, number voting, and party registration/voting columns. Rows are warning-labeled because SBE says turnout reports are run after registration rolls reopen. |
| LA | Loaded | county | loaded: louisianaPresidentParishJson | App imports 64 parish rows from official SOS presidential race JSON using VoterCountQualified and VoterCountVoted, and validates statewide denominator and ballots-cast totals. |
| MD | Loaded | county | loaded: marylandTurnoutPdf | App imports official county turnout rows from the SBE PDF with Election Day, early voting, vote-by-mail, and provisional counts. Rows are warning-labeled because the denominator is eligible voters rather than registered voters. |
| ME | Loaded | county join from municipality/voting district registration and county result totals | loaded: maineRegistrationTextJoin | App imports 16 county turnout rows by joining official active registered/enrolled voter counts as of November 5, 2024 to the official corrected presidential workbook TBC county totals. Rows are warning-labeled because this is a county-level join rather than precinct-level turnout. |
| MI | Loaded | county | loaded: michiganMvicCountyTurnout | App already joins official MVIC turnout export to SOS registration totals; source requires browser-backed download. |
| MN | Loaded | precinct | loaded: xlsxPrecinctRows | App already imports precinct turnout using REG7AM plus EDR as denominator and TOTVOTING as ballots cast. |
| MO | Loaded | county | loaded: missouriVoterTurnoutPdf | App imports county registered voters, active voters, inactive voters, actual voters, and turnout percentage; Kansas City is merged into Jackson County for county-geometry alignment. |
| MT | Loaded | county | loaded: montanaCanvassPdf | App imports county turnout rows from the official SOS canvass voting information table; precinct-level denominator support is not loaded. |
| NC | Loaded | precinct/VTD | loaded: northCarolinaVoterHistoryJoin | App joins official history_stats_20241105.zip to voter_stats_20241105.zip by county, precinct, and VTD. All rows are warning-labeled because voter_stats is a Nov. 5 registration snapshot. |
| ND | Loaded | county | loaded: northDakotaTurnoutHtml | App already imports county turnout rows from official SOS turnout detail page. |
| NE | Loaded | county | loaded: nebraskaCanvassPdf | App joins the canvass Voting Statistics registered-voter table to the Total Voting by Method table by county. |
| NJ | Loaded | county | loaded: newJerseyTurnoutPdf | Official PDF gives registered voters, ballots cast, rejected ballots, and election district count by county. |
| NY | Loaded | county | loaded: newYorkCountyEnrollmentJoin | App imports 62 county turnout rows by joining the official NYS BOE 11/01/2024 county enrollment workbook to the certified county presidential CSV Total Votes column. Rows are warning-labeled because the denominator is pre-election enrollment. |
| OH | Loaded | precinct | loaded: ohioPrecinctTurnoutXlsx | App imports 8,878 official precinct rows from the President and Vice President sheet and validates registered-voter and ballots-counted totals against the workbook Total row. |
| OK | Loaded | county | loaded: oklahomaEnrRegistrationPdf | App joins official OKER presidential race total votes and vote-method splits to the official November 1 county registration PDF; rows are warning-labeled because the denominator is pre-election and the numerator is presidential race votes. |
| OR | Loaded | county | loaded: oregonRegistrationTurnoutPdf | App imports county rows from the official Oregon SOS archive PDF. The county table column is labeled Eligible, but the statewide total matches the PDF's Total registered voters line; numerator is Ballots Returned. |
| PA | Loaded | county | loaded: pennsylvaniaVoteHistoryXlsx | App already imports county turnout rows from official vote-history/registration workbook. |
| RI | Loaded | precinct | loaded: rhodeIslandSummaryXlsx | App joins official workbook precinct labels from Reg_Voters and Ballots_Cast; statewide federal reporting rows in the results source remain separate from county geometry. |
| SD | Loaded | county | loaded: southDakotaElectionReturnsPdf | App imports county registered-voter and votes-cast rows from the official SOS Election Returns and Registration Figures PDF and validates the published statewide totals. |
| TN | Loaded | county | loaded: tennesseeTurnoutPdf | App imports 95 official county turnout rows with registered voters, total votes cast, absentee by mail voters, and early voters from the linked November 5, 2024 turnout PDF. |
| VT | Loaded | county | loaded: vermontVoterTurnoutPdf | App imports the official county summary table with registered voters, total votes cast including absentee, turnout, and absentee counts; town/district rows are available in the PDF but not imported yet. |
| WA | Loaded | county | loaded: washingtonReconciliationXlsx | App imports 39 county rows from the official reconciliation workbook using Active Voters as the denominator; the annual report's county turnout percentages reconcile to Ballots Counted divided by Active Voters, so rows carry an active-denominator warning. |
| WI | Partial Loaded | ward/reporting-unit/county mixed | partial loaded: import-turnout.py CSV path | Statewide WEC ward results lack denominator fields; more county/municipal canvass reports are needed for full turnout coverage. |

## Usable Candidates

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |

## Parser Needed

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |

## Needs Source Review

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |

## County-Local Collection

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |

## Files

- `data/turnout-source-audit.csv`
- `data/turnout-source-audit.json`
