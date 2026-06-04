import json
import math
import re
import csv
import zipfile
from collections import defaultdict
from xml.etree import ElementTree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE_WORKBOOK = DATA_DIR / "mn-2024-general-federal-state-results-by-precinct-official.xlsx"
OUTPUT_JS = DATA_DIR / "mn-app-data.js"
COUNTY_GEOJSON = DATA_DIR / "mn-counties.geojson"
COUNTY_OUTPUT_JS = DATA_DIR / "mn-counties.js"
SOURCE_URL = "https://www.sos.mn.gov/media/yt3llxwd/2024-general-federal-state-results-by-precinct-official.xlsx"
OUTLIER_THRESHOLD_PCT = 15
MIN_CANDIDATE_VOTES = 100
VOTE_SHARE_CORRELATION_THRESHOLD = 0.35

HISTORICAL_SOURCES = [
    {
        "year": 2012,
        "file": DATA_DIR / "mn-2012-us-president-by-county.txt",
        "sourceUrl": "https://electionresults.sos.mn.gov/Results/MediaFile_Archive/Index?erselectionId=1&mediafileid=51",
        "resultDateNote": "Official Minnesota SOS 2012 President by County text file.",
    },
    {
        "year": 2016,
        "file": DATA_DIR / "mn-2016-us-president-by-county.txt",
        "sourceUrl": "https://electionresultsfiles.sos.mn.gov/20161108/USPresCty.txt",
        "resultDateNote": "Official Minnesota SOS 2016 President by County text file.",
    },
    {
        "year": 2020,
        "file": DATA_DIR / "mn-2020-us-president-by-county.txt",
        "sourceUrl": "https://www.sos.mn.gov/media/4373/2020-general-federal-state-results-by-precinct-official.xlsx",
        "resultDateNote": "Official Minnesota SOS 2020 President by County text file.",
    },
    {
        "year": 2024,
        "file": DATA_DIR / "mn-2024-us-president-by-county.txt",
        "sourceUrl": SOURCE_URL,
        "resultDateNote": "Official Minnesota SOS 2024 President by County text file.",
    },
]

PRESIDENT_COLUMNS = {
    "trump": "USPRSR",
    "harris": "USPRSDFL",
    "libertarian": "USPRSLIB",
    "weThePeople": "USPRSWTP",
    "green": "USPRSG",
    "socialismLiberation": "USPRSSLP",
    "socialistWorkers": "USPRSSWP",
    "justiceForAll": "USPRSJFA",
    "independent": "USPRSIND",
    "writeIn": "USPRSWI",
}

CANDIDATE_LABELS = [
    {"key": "libertarian", "label": "Libertarian candidate"},
    {"key": "weThePeople", "label": "We The People candidate"},
    {"key": "green", "label": "Green candidate"},
    {"key": "socialismLiberation", "label": "Socialism and Liberation candidate"},
    {"key": "socialistWorkers", "label": "Socialist Workers candidate"},
    {"key": "justiceForAll", "label": "Justice For All candidate"},
    {"key": "independent", "label": "Independent candidate"},
    {"key": "writeIn", "label": "Write-in candidates"},
]

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def column_number(cell_ref):
    letters = re.match(r"([A-Z]+)", cell_ref).group(1)
    total = 0
    for letter in letters:
        total = total * 26 + (ord(letter) - ord("A") + 1)
    return total


def read_shared_strings(archive):
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings = []
    for item in root.findall("main:si", NS):
        strings.append("".join(text.text or "" for text in item.findall(".//main:t", NS)))
    return strings


def worksheet_path_for_name(archive, sheet_name):
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rel_id = None
    for sheet in workbook.findall("main:sheets/main:sheet", NS):
        if sheet.attrib.get("name") == sheet_name:
            rel_id = sheet.attrib[f"{{{NS['rel']}}}id"]
            break
    if not rel_id:
        raise ValueError(f"Could not find worksheet named {sheet_name}")

    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("pkgrel:Relationship", NS):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError(f"Could not find relationship target for {sheet_name}")


def cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", NS))

    raw = cell.find("main:v", NS)
    if raw is None or raw.text is None:
        return None
    if cell_type == "s":
        return shared_strings[int(raw.text)]
    value = raw.text
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def iter_worksheet_rows(workbook_path, sheet_name):
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = worksheet_path_for_name(archive, sheet_name)
        root = ElementTree.fromstring(archive.read(sheet_path))
        for row in root.findall("main:sheetData/main:row", NS):
            values = []
            for cell in row.findall("main:c", NS):
                index = column_number(cell.attrib["r"]) - 1
                while len(values) <= index:
                    values.append(None)
                values[index] = cell_value(cell, shared_strings)
            yield tuple(values)


def pct(votes, total):
    return round((votes / total) * 100, 4) if total else 0


def round2(value):
    return math.floor((value * 100) + 0.5) / 100


def average(values):
    values = list(values)
    return sum(values) / len(values) if values else 0


def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 2:
        return 0
    x_values = [pair[0] for pair in pairs]
    y_values = [pair[1] for pair in pairs]
    x_mean = average(x_values)
    y_mean = average(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    x_denominator = math.sqrt(sum((x - x_mean) ** 2 for x in x_values))
    y_denominator = math.sqrt(sum((y - y_mean) ** 2 for y in y_values))
    if not x_denominator or not y_denominator:
        return 0
    return numerator / (x_denominator * y_denominator)


def clean_precinct_label(row, column_index):
    municipality = row[column_index["MCDNAME"]] or ""
    precinct = row[column_index["PCTNAME"]] or ""
    if municipality and precinct and municipality != precinct:
        return f"{municipality} - {precinct}"
    return precinct or municipality or "Unnamed precinct"


def source_path(path):
    return path.as_posix().replace(str(ROOT).replace("\\", "/") + "/", "")


def historical_series():
    county_names_by_code = county_code_name_map()
    series = []
    for source in HISTORICAL_SOURCES:
        output_rows = []
        by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
        with source["file"].open("r", encoding="utf-8-sig", newline="") as handle:
            for fields in csv.reader(handle, delimiter=";"):
                if len(fields) < 16 or fields[4] != "U.S. President & Vice President":
                    continue
                county_code = fields[1]
                county = county_names_by_code.get(county_code.lstrip("0"), county_code)
                party = fields[10]
                votes = int(fields[13] or 0)
                by_county[county]["total"] = int(fields[15] or 0)
                if party == "DFL":
                    by_county[county]["dem"] += votes
                elif party == "R":
                    by_county[county]["rep"] += votes
                else:
                    by_county[county]["other"] += votes

        for county, totals in sorted(by_county.items()):
            total = totals["total"] or totals["dem"] + totals["rep"] + totals["other"]
            output_rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "reportingUnit": f"{county} County",
                    "ward": f"{county} County",
                    "dem": totals["dem"],
                    "rep": totals["rep"],
                    "other": total - totals["dem"] - totals["rep"],
                    "total": total,
                }
            )

        statewide = {
            "dem": sum(row["dem"] for row in output_rows),
            "rep": sum(row["rep"] for row in output_rows),
            "other": sum(row["other"] for row in output_rows),
            "total": sum(row["total"] for row in output_rows),
            "rowCount": len(output_rows),
        }
        series.append(
            {
                "id": f"mn-sos-native-{source['year']}-president",
                "electionYear": source["year"],
                "sourceId": f"mn-sos-{source['year']}-county-results",
                "sourceClass": "nativeOfficial",
                "sourceLevel": "county",
                "rowMethod": "officialCountyResultText",
                "rowCount": len(output_rows),
                "sourceUrl": source["sourceUrl"],
                "localFile": source_path(source["file"]),
                "sourceNote": source["resultDateNote"],
                "statewide": statewide,
                "rows": output_rows,
            }
        )
    return {
        "metadata": {
            "purpose": "Graph-ready Minnesota presidential-election baseline using native official Secretary of State county rows.",
            "seriesCount": len(series),
            "warning": "Minnesota historical rows are native official SOS county rows from each election year.",
            "sources": [
                {
                    "year": source["year"],
                    "localFile": source_path(source["file"]),
                    "sourceUrl": source["sourceUrl"],
                    "format": "semicolon-delimited President by County text",
                    "note": source["resultDateNote"],
                }
                for source in HISTORICAL_SOURCES
            ],
        },
        "series": series,
    }


def county_code_name_map():
    geojson = json.loads(COUNTY_GEOJSON.read_text(encoding="utf-8"))
    return {
        str(int(feature["properties"]["county_code"])): feature["properties"]["county_name"]
        for feature in geojson.get("features", [])
    }


def write_county_geometry_js():
    geojson = json.loads(COUNTY_GEOJSON.read_text(encoding="utf-8"))
    if len(geojson.get("features", [])) != 87:
        raise ValueError(f"Expected 87 Minnesota county geometry features, found {len(geojson.get('features', []))}")
    for feature in geojson["features"]:
        props = feature.setdefault("properties", {})
        props["NAME"] = props.get("county_name") or props.get("NAME")
    COUNTY_OUTPUT_JS.write_text(
        f"window.MN_COUNTIES_GEOJSON = {json.dumps(geojson, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


def main():
    rows = iter_worksheet_rows(SOURCE_WORKBOOK, "Precinct-Results")
    header = next(rows)
    column_index = {name: index for index, name in enumerate(header)}

    by_county = defaultdict(lambda: defaultdict(int))
    review_rows = []
    turnout_rows = []
    precinct_rows = 0
    senate_dfl_total = 0
    senate_r_total = 0
    for row in rows:
        if row[0] == "End of worksheet":
            break
        county = row[column_index["COUNTYNAME"]]
        if not county:
            continue
        precinct_rows += 1
        for output_key, source_column in PRESIDENT_COLUMNS.items():
            by_county[county][output_key] += int(row[column_index[source_column]] or 0)
        by_county[county]["total"] += int(row[column_index["USPRSTOTAL"]] or 0)
        by_county[county]["registered7Am"] += int(row[column_index["REG7AM"]] or 0)
        by_county[county]["electionDayRegistrations"] += int(row[column_index["EDR"]] or 0)
        by_county[county]["totalVoting"] += int(row[column_index["TOTVOTING"]] or 0)
        precinct_label = clean_precinct_label(row, column_index)
        trump = int(row[column_index["USPRSR"]] or 0)
        harris = int(row[column_index["USPRSDFL"]] or 0)
        president_total = int(row[column_index["USPRSTOTAL"]] or 0)
        senate_r = int(row[column_index["USSENR"]] or 0)
        senate_dfl = int(row[column_index["USSENDFL"]] or 0)
        senate_r_total += senate_r
        senate_dfl_total += senate_dfl
        registered_7am = int(row[column_index["REG7AM"]] or 0)
        edr = int(row[column_index["EDR"]] or 0)
        denominator = registered_7am + edr
        ballots_cast = int(row[column_index["TOTVOTING"]] or 0)

        if president_total:
            review_rows.append(
                {
                    "county": county,
                    "ward": precinct_label,
                    "total": president_total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / president_total) * 100),
                    "trumpShare": round2((trump / president_total) * 100),
                    "demDropoff": round2(((harris - senate_dfl) / harris) * 100) if harris else 0,
                    "repDropoff": round2(((trump - senate_r) / trump) * 100) if trump else 0,
                }
            )

        turnout_rows.append(
            {
                "county": county,
                "municipality": row[column_index["MCDNAME"]] or "Unknown municipality",
                "ward": precinct_label,
                "ballotsCast": ballots_cast,
                "registeredVoters": denominator,
                "turnoutPct": round2((ballots_cast / denominator) * 100) if denominator else None,
                "registrationDenominatorTiming": "electionDayPlusEDR",
                "sourceUrl": SOURCE_URL,
                "sourceLevel": "precinct",
                "notes": "Minnesota SOS precinct results spreadsheet. Denominator uses REG7AM plus EDR based on the SOS Fields sheet definitions.",
                "warningRequired": False,
            }
        )

    result_rows = []
    for county, totals in sorted(by_county.items()):
        total = totals["total"]
        other = sum(totals[item["key"]] for item in CANDIDATE_LABELS)
        margin = totals["trump"] - totals["harris"]
        result_rows.append(
            {
                "county": county,
                "trump": totals["trump"],
                "trumpPct": pct(totals["trump"], total),
                "harris": totals["harris"],
                "harrisPct": pct(totals["harris"], total),
                "other": other,
                "otherPct": pct(other, total),
                **{item["key"]: totals[item["key"]] for item in CANDIDATE_LABELS},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
                "registered7Am": totals["registered7Am"],
                "electionDayRegistrations": totals["electionDayRegistrations"],
                "totalVoting": totals["totalVoting"],
            }
        )

    state_total = sum(row["total"] for row in result_rows)
    candidate_total = sum(
        row["trump"] + row["harris"] + row["other"] for row in result_rows
    )
    if state_total != candidate_total:
        raise ValueError(
            f"Minnesota presidential candidate total mismatch: {candidate_total} vs {state_total}"
        )
    if len(result_rows) != 87:
        raise ValueError(f"Expected 87 Minnesota counties, found {len(result_rows)}")
    if len(review_rows) < 4000:
        raise ValueError(
            f"Expected at least 4,000 Minnesota review rows, found {len(review_rows)}"
        )

    dem_drop_votes = sum(row["harris"] for row in review_rows) - senate_dfl_total
    rep_drop_votes = sum(row["trump"] for row in review_rows) - senate_r_total
    harris_total = sum(row["harris"] for row in review_rows)
    trump_total = sum(row["trump"] for row in review_rows)
    dem_outliers = sum(
        1
        for row in review_rows
        if row["harris"] >= MIN_CANDIDATE_VOTES
        and abs(row["demDropoff"]) >= OUTLIER_THRESHOLD_PCT
    )
    rep_outliers = sum(
        1
        for row in review_rows
        if row["trump"] >= MIN_CANDIDATE_VOTES
        and abs(row["repDropoff"]) >= OUTLIER_THRESHOLD_PCT
    )
    eta_analysis = {
        "wardRows": len(review_rows),
        "downBallot": {
            "demDropVotes": dem_drop_votes,
            "demDropPct": round2((dem_drop_votes / harris_total) * 100) if harris_total else 0,
            "repDropVotes": rep_drop_votes,
            "repDropPct": round2((rep_drop_votes / trump_total) * 100) if trump_total else 0,
            "demOutlierWards": dem_outliers,
            "repOutlierWards": rep_outliers,
            "outlierThresholdPct": OUTLIER_THRESHOLD_PCT,
            "minCandidateVotes": MIN_CANDIDATE_VOTES,
        },
        "voteShare": {
            "trumpCorrelation": round(pearson(
                [row["trump"] for row in review_rows],
                [row["trumpShare"] for row in review_rows],
            ), 4),
            "harrisCorrelation": round(pearson(
                [row["harris"] for row in review_rows],
                [row["harrisShare"] for row in review_rows],
            ), 4),
            "threshold": VOTE_SHARE_CORRELATION_THRESHOLD,
        },
    }
    turnout_warning_rows = sum(1 for row in turnout_rows if row["warningRequired"])

    payload = {
        "metadata": {
            "sourceWorkbook": source_path(SOURCE_WORKBOOK),
            "precinctRows": precinct_rows,
            "countyRows": len(result_rows),
            "stateTotal": state_total,
            "notes": "Aggregated from the official Minnesota Secretary of State 2024 general federal/state precinct results spreadsheet.",
        },
        "presidentCountyResults": result_rows,
        "candidateLabels": CANDIDATE_LABELS,
        "reviewCharts": {
            "metadata": {
                "wardRows": len(review_rows),
                "source": SOURCE_WORKBOOK.name,
                "presidentSheet": "Precinct-Results",
                "senateSheet": "Precinct-Results",
                "rows": review_rows,
            }
        },
        "etaAnalysis": eta_analysis,
        "turnoutData": {
            "metadata": {
                "rows": len(turnout_rows),
                "warningRows": turnout_warning_rows,
                "source": SOURCE_WORKBOOK.name,
                "sourceUrl": SOURCE_URL,
            },
            "rows": turnout_rows,
        },
        "historicalBaseline": historical_series(),
    }
    OUTPUT_JS.write_text(
        f"window.MN_ELECTION_APP_DATA = {json.dumps(payload, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    write_county_geometry_js()
    print(
        json.dumps(
            {
                "precinctRows": precinct_rows,
                "countyRows": len(result_rows),
                "stateTotal": state_total,
                "trump": sum(row["trump"] for row in result_rows),
                "harris": sum(row["harris"] for row in result_rows),
                "other": sum(row["other"] for row in result_rows),
                "reviewRows": len(review_rows),
                "turnoutRows": len(turnout_rows),
                "turnoutWarningRows": turnout_warning_rows,
                "historicalSeries": len(payload["historicalBaseline"]["series"]),
                "historicalRows": sum(series["rowCount"] for series in payload["historicalBaseline"]["series"]),
                "countyGeometryFeatures": 87,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
