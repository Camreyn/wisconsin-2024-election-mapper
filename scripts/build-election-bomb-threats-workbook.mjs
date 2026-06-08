import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const csvPath = path.join(root, "data", "2024-election-bomb-threats-by-state.csv");
const outputDir = path.join(root, "outputs", "election-bomb-threats-2024");
const outputPath = path.join(outputDir, "2024-election-bomb-threats-by-state.xlsx");
const previewPath = path.join(outputDir, "2024-election-bomb-threats-by-state-summary.png");
const dataPreviewPath = path.join(outputDir, "2024-election-bomb-threats-by-state-data.png");
const sourcesPreviewPath = path.join(outputDir, "2024-election-bomb-threats-by-state-sources.png");

const csvText = await fs.readFile(csvPath, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "State Data" });
const summary = workbook.worksheets.add("Summary");
const sources = workbook.worksheets.add("Sources");
const stateData = workbook.worksheets.getItem("State Data");
stateData.getRange("B2:D11").values = stateData
  .getRange("B2:D11")
  .values.map((row) => row.map((value) => Number(value)));

summary.showGridLines = false;
summary.mergeCells("A1:G1");
summary.getRange("A1").values = [["2024 November Election Bomb Threats by State"]];
summary.getRange("A2").values = [["Publicly confirmed minimums from the Brennan Center tracker, split between Election Day and later election-processing threats."]];
summary.mergeCells("A2:G2");

summary.getRange("A4:F4").values = [[
  "Election Day minimum",
  null,
  "Post-election processing minimum",
  null,
  "Tracker minimum total",
  null,
]];
summary.getRange("A5:F5").values = [[null, null, null, null, null, null]];
summary.getRange("A5").formulas = [["=SUM(B8:B16)"]];
summary.getRange("C5").formulas = [["=SUM(C8:C16)"]];
summary.getRange("E5").formulas = [["=SUM(D8:D16)"]];

summary.getRange("A7:D7").values = [[
  "State",
  "Election Day: Nov. 5",
  "Later processing: Nov. 8-9",
  "Tracker minimum total",
]];
summary.getRange("A8:A16").formulas = [
  ["='State Data'!A2"],
  ["='State Data'!A3"],
  ["='State Data'!A4"],
  ["='State Data'!A5"],
  ["='State Data'!A6"],
  ["='State Data'!A7"],
  ["='State Data'!A8"],
  ["='State Data'!A9"],
  ["='State Data'!A10"],
];
summary.getRange("B8:D16").formulas = [
  ["='State Data'!B2", "='State Data'!C2", "='State Data'!D2"],
  ["='State Data'!B3", "='State Data'!C3", "='State Data'!D3"],
  ["='State Data'!B4", "='State Data'!C4", "='State Data'!D4"],
  ["='State Data'!B5", "='State Data'!C5", "='State Data'!D5"],
  ["='State Data'!B6", "='State Data'!C6", "='State Data'!D6"],
  ["='State Data'!B7", "='State Data'!C7", "='State Data'!D7"],
  ["='State Data'!B8", "='State Data'!C8", "='State Data'!D8"],
  ["='State Data'!B9", "='State Data'!C9", "='State Data'!D9"],
  ["='State Data'!B10", "='State Data'!C10", "='State Data'!D10"],
];
summary.getRange("A17:D17").values = [["TOTAL", null, null, null]];
summary.getRange("B17").formulas = [["=SUM(B8:B16)"]];
summary.getRange("C17").formulas = [["=SUM(C8:C16)"]];
summary.getRange("D17").formulas = [["=SUM(D8:D16)"]];

summary.getRange("F7:G16").values = [
  ["State", "Tracker minimum total"],
  ["Arizona", 16],
  ["California", 6],
  ["Georgia", 60],
  ["Maryland", 15],
  ["Michigan", 4],
  ["Minnesota", 47],
  ["Oregon", 36],
  ["Pennsylvania", 41],
  ["Wisconsin", 2],
];
const chart = summary.charts.add("bar", summary.getRange("F7:G16"));
chart.title = "Tracker Minimum Threats by State";
chart.hasLegend = false;
chart.setPosition("I4", "R21");

summary.getRange("A19:G19").values = [["Scope note"]];
summary.mergeCells("A19:G19");
summary.mergeCells("A20:G20");
summary.getRange("A20").values = [["These are publicly confirmed minimums. The tracker notes that its public-information research may not be exhaustive. Counts describe documented threats or targeted election facilities, not necessarily unique polling places."]];
summary.mergeCells("A21:G21");
summary.getRange("A21").values = [["Michigan note: the tracker records 4 county polling-location threats. CNN reporting citing Secretary Jocelyn Benson described 5 Michigan locations when the Lansing Secretary of State office is included."]];

summary.getRange("A1:G1").format = {
  fill: "#17324D",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  horizontalAlignment: "center",
};
summary.getRange("A2:G2").format = {
  fill: "#DCE8F2",
  font: { italic: true, color: "#17324D" },
  wrapText: true,
};
summary.getRange("A4:F4").format = {
  fill: "#D9EAD3",
  font: { bold: true, color: "#17324D" },
};
summary.getRange("A5:F5").format = {
  fill: "#EEF5EB",
  font: { bold: true, color: "#17324D", size: 15 },
};
summary.getRange("A7:D7").format = {
  fill: "#376B8C",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};
summary.getRange("A17:D17").format = {
  fill: "#D9EAD3",
  font: { bold: true, color: "#17324D" },
};
summary.getRange("A19:G19").format = {
  fill: "#EAD9B8",
  font: { bold: true, color: "#5B4322" },
};
summary.getRange("A20:G21").format = {
  fill: "#FFF7E8",
  wrapText: true,
};
summary.getRange("B8:D17").format.numberFormat = "0";
summary.getRange("A1:Q21").format.verticalAlignment = "center";
summary.getRange("A1:Q21").format.wrapText = true;
summary.getRange("A1").format.rowHeightPx = 30;
summary.getRange("A2").format.rowHeightPx = 34;
summary.getRange("A20:A21").format.rowHeightPx = 42;
summary.getRange("A:A").format.columnWidthPx = 130;
summary.getRange("B:C").format.columnWidthPx = 155;
summary.getRange("D:D").format.columnWidthPx = 135;
summary.getRange("E:E").format.columnWidthPx = 135;
summary.getRange("F:G").format.columnWidthPx = 145;
summary.freezePanes.freezeRows(7);

stateData.showGridLines = false;
const dataTable = stateData.tables.add("A1:F11", true, "ElectionBombThreatsByState");
dataTable.style = "TableStyleMedium2";
stateData.getRange("A:F").format.wrapText = true;
stateData.getRange("A:A").format.columnWidthPx = 115;
stateData.getRange("B:D").format.columnWidthPx = 150;
stateData.getRange("E:E").format.columnWidthPx = 470;
stateData.getRange("F:F").format.columnWidthPx = 520;
stateData.freezePanes.freezeRows(1);

sources.showGridLines = false;
sources.getRange("A1:B1").values = [["Source", "URL / note"]];
sources.getRange("A2:B6").values = [
  ["Brennan Center tracker", "https://www.brennancenter.org/sites/default/files/2025-03/bcj-2024-election-bomb-threat-tracker_0.pdf"],
  ["Brennan Center analysis", "https://www.brennancenter.org/our-work/analysis-opinion/preparation-kept-bomb-threats-disrupting-2024-elections"],
  ["FBI statement", "https://www.fbi.gov/news/press-releases/fbi-statement-on-bomb-threats-to-polling-locations"],
  ["Supplemental Michigan reporting", "https://ktvz.com/politics/cnn-us-politics/2024/11/05/battleground-states-rush-to-count-ballots-after-mostly-smooth-election-day-vote/"],
  ["Scope reminder", "Brennan Center tracker last updated March 28, 2025. Tracker minimum total: 227. FBI stated on November 5, 2024 that many polling-location threats appeared to originate from Russian email domains and none had been determined credible at that time."],
];
sources.getRange("A1:B1").format = {
  fill: "#17324D",
  font: { bold: true, color: "#FFFFFF" },
};
sources.getRange("A:B").format.wrapText = true;
sources.getRange("A:A").format.columnWidthPx = 210;
sources.getRange("B:B").format.columnWidthPx = 680;
sources.getRange("A2:B6").format.rowHeightPx = 36;
sources.tables.add("A1:B6", true, "ElectionBombThreatSources").style = "TableStyleMedium2";
sources.freezePanes.freezeRows(1);

await fs.mkdir(outputDir, { recursive: true });
const workbookBlob = await SpreadsheetFile.exportXlsx(workbook);
await workbookBlob.save(outputPath);

const preview = await workbook.render({ sheetName: "Summary", range: "A1:R21", scale: 1.4 });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const dataPreview = await workbook.render({ sheetName: "State Data", range: "A1:F11", scale: 1.1 });
await fs.writeFile(dataPreviewPath, new Uint8Array(await dataPreview.arrayBuffer()));
const sourcesPreview = await workbook.render({ sheetName: "Sources", range: "A1:B6", scale: 1.1 });
await fs.writeFile(sourcesPreviewPath, new Uint8Array(await sourcesPreview.arrayBuffer()));

const summaryCheck = await workbook.inspect({
  kind: "table",
  range: "Summary!A7:D17",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 4,
});
const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});

console.log(summaryCheck.ndjson);
console.log(errorCheck.ndjson);
console.log(JSON.stringify({ outputPath, previewPath, dataPreviewPath, sourcesPreviewPath }, null, 2));
