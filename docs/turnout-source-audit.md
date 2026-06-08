# Turnout Source Audit

Checked: 2026-06-07

This audit captures Leif's highest-priority missing data for all 50 states: ballots-cast turnout rows plus registered-voter or eligible-voter denominators, preferably at precinct/VTD/ward level. It is a handoff pack only; no state config capabilities were changed.

## Coverage Summary

- County Local Required: 4
- Loaded: 30
- Partial Loaded: 1
- Source Needs Review: 9
- Usable Candidate: 6

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
| ID | Loaded | county | loaded: idahoTurnoutHtml | Official turnout table includes county election-day registrations, registered voters, ballots cast, and turnout. |
| IN | Loaded | county | loaded: indianaTurnoutPdf | Statewide official county report is available; precinct-level denominator source would need county-local reports. |
| KS | Loaded | state/county | loaded: kansasTurnoutXlsx | App imports county ballots cast, registered voters, and turnout percentage from the official workbook 2024 Turnout sheet; precinct-level denominator support is not loaded. |
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
| IA | Usable Candidate | county | new pdf table parser | Report distinguishes active and inactive voter denominators; choose denominator policy before enabling turnout. |
| KY | Usable Candidate | county | new parser after direct 2024 file is selected | SBE warns turnout reports are run after registration rolls reopen, so denominator timing should be labeled postElectionDay. |
| MA | Usable Candidate | state/city-town linked downloads | new parser; collect detailed early/mail download | Statewide turnout table is obvious; detailed city/town vote-method files should be downloaded from the early voting statistics page. |
| NV | Usable Candidate | county/state | download final official turnout file | Search result came through a UAT host, but the path identifies the SOS 2024 Turnout Reporting page; verify production URL and final file link. |
| NY | Usable Candidate | county | join enrollment county file to certified county results | Enrollment file provides denominator; ballots-cast totals must be joined from certified result/source already loaded for county results. |
| WV | Usable Candidate | county | collect direct 2024 turnout file and parse | SOS certification notes county turnout rates and Election Day registration totals; direct source file URL should be captured. |

## Parser Needed

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |

## Needs Source Review

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |
| LA | Source Needs Review | state/parish candidate | browser/scripted export required | Portal exposes voters, voted, and turnout but needs election/parish URL parameters or browser capture before importer work. |
| MS | Source Needs Review | county | source review before parser | Official results page is identified, but search did not confirm registered-voter denominator fields in the county recapitulation report. |
| NH | Source Needs Review | town | collect direct 2024 turnout chart file | SOS election page links voter turnout charts, but direct 2024 file URL was not captured in this pass. |
| NM | Source Needs Review | state/county dashboard | export inspection needed | Official dashboard exposes voter turnout; media/result export endpoint needs inspection for machine-readable denominator rows. |
| SC | Source Needs Review | county-local or ENR county | inspect ENR turnout fields or collect county PDFs | SEC annual report and county PDFs confirm statewide turnout/registered-voter data exists; exact statewide machine-readable source still needs capture. |
| TX | Source Needs Review | county/state split across reports | join early/election-day turnout with registration figures; county-level completeness needs review | SOS provides registration and turnout figures, but county-level final turnout may require combining multiple official reports or county canvass files. |
| UT | Source Needs Review | county dashboard/pdf candidate | inspect county Clarity statistics panels or certification attachments | County Clarity summaries expose registered voters and turnout for some Utah counties; statewide official file location needs direct capture. |
| VA | Source Needs Review | locality/precinct candidate | join ENR turnout/statistics to registration counts | Official ENR and registration PDFs are available, but the exact app-ready turnout export needs inspection. |
| WY | Source Needs Review | county/precinct candidate | inspect official PbP workbooks for registered-voter denominator fields | Official ZIP has precinct-by-precinct workbooks, but this pass did not confirm denominator fields inside those workbooks. |

## County-Local Collection

| State | Status | Source Level | Parser Fit | Caveat |
| --- | --- | --- | --- | --- |
| AZ | County Local Required | county-local summary, sometimes precinct/counting group | county-local collection; no single statewide parser identified | State canvass loaded in app is county-level and lacks denominators; official county reports can satisfy turnout but must be collected county by county. |
| GA | County Local Required | county-local precinct | county-local collection; no single statewide denominator file identified | State ENR source is official but county SOV reports, such as Fulton, expose precinct registered voters and cards/voters cast. |
| IL | County Local Required | county-local precinct | county-local collection | A statewide precinct denominator file was not found; official county abstracts can expose precinct registered voters and vote-method ballots. |
| OH | County Local Required | county-local precinct | county-local collection | Ohio SOS has official results, but precinct registered-voter turnout appears in county board SOV PDFs rather than one statewide file. |

## Files

- `data/turnout-source-audit.csv`
- `data/turnout-source-audit.json`
