# Review Source Collection

Checked at: 2026-06-08

This file tracks source files collected for the review-graph lane. It is intentionally separate from turnout collection.

## Summary

- already present or needs parser/source discovery: 30
- source page captured: 5
- data captured: 4
- not captured: 4

## Captured Targets

| State | Status | Captured files | Existing local files | Next step |
| --- | --- | --- | --- | --- |
| AK | already present or needs parser/source discovery |  | data/ak-2024-general-enr-by-precinct.csv (3645454 bytes) | Map President and U.S. Representative rows from ENRbyPrecinct.csv into review rows. |
| AR | source page captured | data/review-sources/ar-config.json; data/review-sources/ar-election-list.json; data/review-sources/ar-index-_rT17pbd.js; data/review-sources/ar-2024-general-election-info.json; data/review-sources/ar-2024-general-contest-search-list.json; data/review-sources/ar-official-review-source.html | data/ar-2024-general-fed-results.json (93794 bytes) | Inspect TotalResults network payloads for precinct endpoints; if unavailable, use SOS guidance to request 2024 precinct data. |
| AZ | already present or needs parser/source discovery |  | data/az-2024-county-source-manifest.json (20731 bytes); data/az-2024-county-source-status.json (23061 bytes) | Complete county-by-county report collection and normalize report-specific precinct sections. |
| CA | already present or needs parser/source discovery |  | data/ca-2024-president-by-county.xlsx (18188 bytes) | Collect county SOV or precinct result files from county election offices; statewide SOS SOV is county-level. |
| CO | already present or needs parser/source discovery |  | data/co-2024-president-county-results.csv (206269 bytes) | Download the Colorado Secretary of State precinct-level results package and map President plus a statewide/congressional comparison contest. |
| CT | already present or needs parser/source discovery |  | data/ct-2024-statement-of-vote.txt (227694 bytes) | Map a statewide down-ballot contest from the Statement of Vote text to the same town rows. |
| DE | already present or needs parser/source discovery |  | data/de-2024-general-election-report.html (5164476 bytes) | Map President and a statewide comparison race from the official report page election-district rows. |
| GA | source page captured | data/review-sources/ga-official-review-source.html | data/ga-2024-total-votes-results.xlsx (304640 bytes) | Collect official county SOV reports or identify a statewide precinct export behind the SOS portal. |
| HI | already present or needs parser/source discovery |  | data/hi-2024-general-media.txt (3950518 bytes); data/hi-2024-general-precinct.pdf (3370521 bytes) | Map President and U.S. Senate or another statewide contest from media.txt/precinct.pdf. |
| IA | already present or needs parser/source discovery |  | data/ia-2024-general-canvass-summary.pdf (644223 bytes) | Search Iowa SOS and county auditor sites for official precinct-level general-election canvass/result exports. |
| ID | data captured | data/id-2024-president-precinct-results.csv; data/id-2024-us-house-district-1-precinct-results.csv; data/id-2024-us-house-district-2-precinct-results.csv; data/review-sources/id-official-review-source.html | data/id-2024-president-county-results.csv (3756 bytes) | Inspect canvass.sos.idaho.gov network exports for precinct or reporting-unit contest rows. |
| IL | already present or needs parser/source discovery |  | data/il-2024-president-county-results.csv (5560651 bytes) | Collect/map a down-ballot contest at the same precinct grain. |
| IN | source page captured | data/review-sources/in-official-review-source.html | data/in-2024-general-president-results.json (760654 bytes) | Inspect Indiana ENR archive payloads for precinct/detail endpoints beyond the county presidential payload. |
| KS | already present or needs parser/source discovery |  | data/ks-2024-presidential-results.xlsx (773382 bytes) | Map precinct President rows and collect a same-grain down-ballot workbook or sheet. |
| KY | already present or needs parser/source discovery |  | data/ky-2024-general-election-certification.pdf (352441 bytes) | Search Kentucky SBE and county clerk/SBE result downloads for official precinct-level 2024 general files. |
| LA | not captured |  | data/la-2024-president-parish-results.csv (3974 bytes) | Capture official precinct-level race JSON for President plus a comparison contest from the Voter Portal. |
| MA | already present or needs parser/source discovery |  | data/ma-2024-president-general-election.html (264641 bytes) | Map President and U.S. Senate or another statewide race from PD43+ municipal rows. |
| MD | data captured | data/md-2024-general-all-precincts.csv; data/md-2024-state-precinct-reference.xlsx; data/review-sources/md-election-data-index.html | data/md-2024-president-county-breakdown.html (121600 bytes) | Download official precinct-level 2024 general election files and map President plus Senate. |
| ME | already present or needs parser/source discovery |  | data/me-2024-president-county-town-final-corrected.xlsx (60242 bytes) | Collect or map a same-municipality down-ballot workbook if available. |
| MO | already present or needs parser/source discovery |  | data/mo-2024-general-actual-results.pdf (2023297 bytes) | Search Missouri SOS and county election authority result files for official precinct-level 2024 general data. |
| MS | already present or needs parser/source discovery |  | data/ms-2024-election-recap-sheets.csv (176954 bytes) | Inspect Mississippi SOS downloads and county election commission files for precinct-level recap/reporting-unit data. |
| MT | already present or needs parser/source discovery |  | data/mt-2024-general-election-report-state-canvass.pdf (445925 bytes) | Search Montana SOS and county election offices for precinct-level 2024 general returns. |
| NC | data captured | data/nc-2024-general-results-precinct.zip; data/review-sources/nc-historical-election-results-data.html | data/nc-2024-general-enr-results.zip (466320 bytes) | Download official precinct-sort data and map President plus a statewide comparison contest. |
| NE | already present or needs parser/source discovery |  | data/ne-2024-general-canvass-book.pdf (3223182 bytes) | Search Nebraska SOS and county election offices for precinct-level 2024 general result files. |
| NH | already present or needs parser/source discovery |  | data/nh-2024-president-county-summary.pdf (17861 bytes) | Locate official SOS town-level general-election result files for President and a comparison contest. |
| NJ | already present or needs parser/source discovery |  | data/nj-2024-official-general-results-president.pdf (97746 bytes) | Collect county official precinct/municipal result files; state official PDF is county-level. |
| NM | already present or needs parser/source discovery |  | data/nm-2024-president-county-results.csv (88297 bytes) | Map Civera precinct rows and collect a same-grain comparison contest export. |
| NV | already present or needs parser/source discovery |  | data/nv-2024-official-statewide-general-election-results.html (145670 bytes) | Search Nevada SOS/county election offices or archived SOS downloads for precinct-level 2024 general data. |
| NY | already present or needs parser/source discovery |  | data/ny-2024-president-results-by-county.csv (5608 bytes) | Collect county board precinct/election-district result files; NYS export currently loaded is county-level. |
| OH | data captured | data/oh-2024-statewide-races-precinct-level.xlsx | data/oh-2024-statewide-race-summary.xlsx (259601 bytes) | Download or archive-fetch the official workbook and map President plus Senate. |
| OK | not captured |  | data/ok-2024-general-enr-results.zip (174695 bytes) | Inspect OKER static files for precinct/detail results beyond county ENR payloads. |
| OR | source page captured | data/review-sources/or-official-review-source.html | data/or-2024-president-county-mapdata.json (182863 bytes) | Inspect Oregon ResultsExport/API parameters for precinct-level President and comparison contest rows. |
| RI | already present or needs parser/source discovery |  | data/ri-2024-general-election-summary.xlsx (1128000 bytes) | Map Candidate_Breakout precinct rows to a comparison contest. |
| SC | not captured |  | data/sc-2024-general-election-details.json (55654 bytes) | Inspect ENR static JSON for precinct/detail records or collect county reports. |
| SD | already present or needs parser/source discovery |  | data/sd-2024-general-election-canvass-with-cert.pdf (801624 bytes) | Search South Dakota SOS and county auditor files for precinct-level 2024 general returns. |
| TN | already present or needs parser/source discovery |  | data/tn-2024-general-all-by-precinct.xlsx (1015612 bytes) | Map President and a down-ballot contest from the all-by-precinct workbook. |
| TX | already present or needs parser/source discovery |  | data/tx-2024-general-county.json (1818450 bytes) | Collect county official precinct returns; statewide SOS data currently loaded is county-level. |
| UT | already present or needs parser/source discovery |  | data/ut-2024-general-statewide-canvass.pdf (3087129 bytes) | Collect county Clarity exports or county official precinct reports for President and comparison contests. |
| VA | already present or needs parser/source discovery |  | data/va-2024-president-results.csv (148282 bytes) | Map precinct rows and collect/map a same-grain comparison contest export. |
| VT | already present or needs parser/source discovery |  | data/vt-2024-president-municipality-results.csv (11742 bytes) | Collect/map a same-municipality statewide down-ballot contest. |
| WA | source page captured | data/review-sources/wa-official-review-source.html | data/wa-2024-president-county-results.html (177283 bytes) | Collect county official precinct result files; SOS page currently loaded is county-level. |
| WV | not captured |  | data/wv-2024-general-election-details.json (53299 bytes) | Inspect Clarity ENR static files for precinct/detail records or collect county files. |
| WY | already present or needs parser/source discovery |  | data/wy-2024-general-results.zip (771175 bytes) | Map county precinct-by-precinct workbooks inside the official ZIP to President plus comparison contest rows. |
