import argparse
import csv
import html
import io
import json
import math
import re
import urllib.request
import urllib.parse
import zipfile
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "data" / "state-configs"

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

PENNSYLVANIA_COUNTY_NAMES = {
    "01": "Adams",
    "02": "Allegheny",
    "03": "Armstrong",
    "04": "Beaver",
    "05": "Bedford",
    "06": "Berks",
    "07": "Blair",
    "08": "Bradford",
    "09": "Bucks",
    "10": "Butler",
    "11": "Cambria",
    "12": "Cameron",
    "13": "Carbon",
    "14": "Centre",
    "15": "Chester",
    "16": "Clarion",
    "17": "Clearfield",
    "18": "Clinton",
    "19": "Columbia",
    "20": "Crawford",
    "21": "Cumberland",
    "22": "Dauphin",
    "23": "Delaware",
    "24": "Elk",
    "25": "Erie",
    "26": "Fayette",
    "27": "Forest",
    "28": "Franklin",
    "29": "Fulton",
    "30": "Greene",
    "31": "Huntingdon",
    "32": "Indiana",
    "33": "Jefferson",
    "34": "Juniata",
    "35": "Lackawanna",
    "36": "Lancaster",
    "37": "Lawrence",
    "38": "Lebanon",
    "39": "Lehigh",
    "40": "Luzerne",
    "41": "Lycoming",
    "42": "McKean",
    "43": "Mercer",
    "44": "Mifflin",
    "45": "Monroe",
    "46": "Montgomery",
    "47": "Montour",
    "48": "Northampton",
    "49": "Northumberland",
    "50": "Perry",
    "51": "Philadelphia",
    "52": "Pike",
    "53": "Potter",
    "54": "Schuylkill",
    "55": "Snyder",
    "56": "Somerset",
    "57": "Sullivan",
    "58": "Susquehanna",
    "59": "Tioga",
    "60": "Union",
    "61": "Venango",
    "62": "Warren",
    "63": "Washington",
    "64": "Wayne",
    "65": "Westmoreland",
    "66": "Wyoming",
    "67": "York",
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
    return [
        "".join(text.text or "" for text in item.findall(".//main:t", NS))
        for item in root.findall("main:si", NS)
    ]


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


def first_worksheet_name(workbook_path):
    with zipfile.ZipFile(workbook_path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = workbook.find("main:sheets/main:sheet", NS)
        if sheet is None:
            raise ValueError(f"Could not find worksheet in {workbook_path}")
        return sheet.attrib["name"]


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


def read_sheet_rows(workbook_path, sheet_name):
    rows = iter_worksheet_rows(workbook_path, sheet_name)
    header = next(rows)
    column_index = {name: index for index, name in enumerate(header)}
    return column_index, rows


def source_path(path):
    return path.as_posix().replace(str(ROOT).replace("\\", "/") + "/", "")


def project_path(value):
    return ROOT / value


def source_map(config):
    return {source["id"]: source for source in config["sources"]}


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def local_source(config, source_id):
    source = source_map(config)[source_id]
    return project_path(source["localFile"])


def maybe_download_sources(config, *, force=False):
    downloaded = []
    for source in config.get("sources", []):
        path = project_path(source["localFile"])
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        download = source.get("download", {})
        if download.get("type") == "northDakotaResultsExport":
            path.write_bytes(download_north_dakota_export(source, download))
        elif download.get("type") == "browserDownload":
            download_with_browser(source, path, download)
        else:
            request = urllib.request.Request(
                source["url"],
                headers={"User-Agent": "Mozilla/5.0 state-election-data-builder"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                path.write_bytes(response.read())
        downloaded.append(source["id"])
    return downloaded


def download_with_browser(source, path, download):
    command = [
        "node",
        "scripts/browser-download.mjs",
        "--url",
        source["url"],
        "--output",
        str(path),
        "--timeout-ms",
        str(download.get("timeoutMs", 120000)),
    ]
    if download.get("headless") is False:
        command.extend(["--headless", "false"])
    browser = download.get("browser")
    if browser:
        command.extend(["--browser", browser])
    subprocess.run(command, cwd=ROOT, check=True)


def hidden_input_value(page, input_id):
    match = re.search(rf'id="{re.escape(input_id)}"\s+value="([^"]*)"', page)
    return html.unescape(match.group(1)) if match else ""


def download_north_dakota_export(source, download):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "Mozilla/5.0 state-election-data-builder"},
    )
    with opener.open(request, timeout=120) as response:
        page = response.read().decode("utf-8", errors="replace")

    form = {
        "__EVENTTARGET": download.get("eventTarget", ""),
        "__EVENTARGUMENT": download.get("eventArgument", ""),
        "__VIEWSTATE": hidden_input_value(page, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": hidden_input_value(page, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": hidden_input_value(page, "__EVENTVALIDATION"),
        "ctl00$hidElectionType": hidden_input_value(page, "hidElectionType"),
        "ctl00$hidElectionDate": hidden_input_value(page, "hidElectionDate"),
        "ctl00$hidPrecinctsReported": hidden_input_value(page, "hidPrecinctsReported"),
        "ctl00$hidPrecinctsNotReported": hidden_input_value(page, "hidPrecinctsNotReported"),
        "ctl00$hidPrecinctsPartial": hidden_input_value(page, "hidPrecinctsPartial"),
        "ctl00$hidVoterTurnout": hidden_input_value(page, "hidVoterTurnout"),
        "ctl00$hidVoterTotal": hidden_input_value(page, "hidVoterTotal"),
        "ctl00$MainContent$hidCountyID": "",
        "ctl00$txtQuickSearch": "",
        "ctl00$txtQuickSearchSide": "",
        "ctl00$MainContent$rblTypes": download.get("fileType", "1"),
    }
    if download.get("buttonName"):
        form[download["buttonName"]] = download["buttonValue"]
    post = urllib.parse.urlencode(form).encode("utf-8")
    post_request = urllib.request.Request(
        source["url"],
        data=post,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 state-election-data-builder",
        },
    )
    with opener.open(post_request, timeout=120) as response:
        return response.read()


def int_cell(row, column_index, column_name):
    value = row[column_index[column_name]]
    return int(value or 0)


def int_text(value):
    return int(str(value or "0").replace(",", "").strip() or 0)


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


def row_label(row, column_index, row_label_columns):
    municipality = row[column_index[row_label_columns["municipality"]]] or ""
    precinct = row[column_index[row_label_columns["precinct"]]] or ""
    if municipality and precinct and municipality != precinct:
        return f"{municipality} - {precinct}"
    return precinct or municipality or "Unnamed precinct"


def certified_results(config):
    source = config["certifiedResults"]
    parser = parser_for(CERTIFIED_RESULT_PARSERS, source.get("format", "xlsxPrecinctAggregation"), "certified results")
    return parser(config)


def certified_results_not_configured(config):
    return [], [{"key": item["key"], "label": item["label"]} for item in config["certifiedResults"].get("otherCandidates", [])], 0


def certified_results_xlsx_precinct_aggregation(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    columns = source["columns"]
    column_index, rows = read_sheet_rows(path, source["sheet"])
    by_county = defaultdict(lambda: defaultdict(int))
    precinct_rows = 0

    for row in rows:
        if row[0] == "End of worksheet":
            break
        county = row[column_index[columns["county"]]]
        if not county:
            continue
        precinct_rows += 1
        by_county[county]["trump"] += int_cell(row, column_index, columns["trump"])
        by_county[county]["harris"] += int_cell(row, column_index, columns["harris"])
        by_county[county]["total"] += int_cell(row, column_index, columns["total"])
        for candidate in source.get("otherCandidates", []):
            by_county[county][candidate["key"]] += int_cell(row, column_index, candidate["column"])
        for output_key, column_name in source.get("aggregateFields", {}).items():
            by_county[county][output_key] += int_cell(row, column_index, column_name)

    result_rows = []
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    for county, totals in sorted(by_county.items()):
        total = totals["total"]
        other = sum(totals[item["key"]] for item in candidate_labels)
        margin = totals["trump"] - totals["harris"]
        row = {
            "county": county,
            "trump": totals["trump"],
            "trumpPct": pct(totals["trump"], total),
            "harris": totals["harris"],
            "harrisPct": pct(totals["harris"], total),
            "other": other,
            "otherPct": pct(other, total),
            **{item["key"]: totals[item["key"]] for item in candidate_labels},
            "margin": margin,
            "marginPct": round((margin / total) * 100, 4) if total else 0,
            "total": total,
        }
        for output_key in source.get("aggregateFields", {}):
            row[output_key] = totals[output_key]
        result_rows.append(row)

    return result_rows, candidate_labels, precinct_rows


def xlsx_indexed_vote(row, index):
    return int_text(row[index] if index < len(row) else 0)


def certified_results_california_president_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    rows = list(iter_worksheet_rows(path, source.get("sheet", "SOV Statewide Contest Details")))
    columns = source["columns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []
    reported_totals = None

    for row in rows:
        county = str((row[0] if row else "") or "").strip()
        if not county or county == "Percent" or county.startswith("Percent"):
            continue
        if county == source.get("stateTotalsLabel", "State Totals"):
            reported_totals = {
                "harris": xlsx_indexed_vote(row, columns["harris"]),
                "trump": xlsx_indexed_vote(row, columns["trump"]),
                **{
                    item["key"]: xlsx_indexed_vote(row, columns[item["column"]])
                    for item in source.get("otherCandidates", [])
                },
            }
            continue

        harris = xlsx_indexed_vote(row, columns["harris"])
        trump = xlsx_indexed_vote(row, columns["trump"])
        other_values = {
            item["key"]: xlsx_indexed_vote(row, columns[item["column"]])
            for item in source.get("otherCandidates", [])
        }
        other = sum(other_values.values())
        total = trump + harris + other
        margin = trump - harris
        result_rows.append(
            {
                "county": county,
                "trump": trump,
                "trumpPct": pct(trump, total),
                "harris": harris,
                "harrisPct": pct(harris, total),
                "other": other,
                "otherPct": pct(other, total),
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    if reported_totals:
        parsed_totals = {
            "harris": sum(row["harris"] for row in result_rows),
            "trump": sum(row["trump"] for row in result_rows),
            **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"California county totals do not match State Totals row: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_iowa_canvass_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_prefixes = sorted(county_names, key=len, reverse=True)
    columns = source["columns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []
    current_county = None
    reported_totals = None
    statewide_pending = False
    total_pattern = re.compile(r"^Total\s+(?P<values>(?:\d[\d,]*\s+){10}\d[\d,]*)$")

    def row_totals(values):
        parsed = {key: int_text(values[index]) for key, index in columns.items()}
        candidate_total = parsed["harris"] + parsed["trump"] + sum(parsed[item["key"]] for item in candidate_labels)
        if candidate_total + parsed["underVotes"] + parsed["overVotes"] != parsed["ballotsTotal"]:
            raise ValueError(
                "Iowa PDF row candidate, under-vote, and over-vote totals do not match row total: "
                f"{candidate_total} + {parsed['underVotes']} + {parsed['overVotes']} != {parsed['ballotsTotal']}"
            )
        return parsed

    for line in lines:
        if line == source.get("contest", "President and Vice President"):
            current_county = None
            statewide_pending = False
            continue
        if line.startswith("TOTAL Election"):
            current_county = None
            statewide_pending = True
            continue
        if re.match(r"^Page \d+ of \d+$", line):
            continue

        match = total_pattern.match(line)
        if match:
            totals = row_totals(match.group("values").split())
            if statewide_pending:
                reported_totals = totals
                break
            if current_county:
                other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
                other = sum(other_values.values())
                total = totals["trump"] + totals["harris"] + other
                margin = totals["trump"] - totals["harris"]
                result_rows.append(
                    {
                        "county": current_county,
                        "trump": totals["trump"],
                        "trumpPct": pct(totals["trump"], total),
                        "harris": totals["harris"],
                        "harrisPct": pct(totals["harris"], total),
                        "other": other,
                        "otherPct": pct(other, total),
                        **other_values,
                        "margin": margin,
                        "marginPct": round((margin / total) * 100, 4) if total else 0,
                        "total": total,
                    }
                )
                current_county = None
            continue

        upper_line = line.upper()
        for raw_county in county_prefixes:
            if upper_line.startswith(f"{raw_county} "):
                current_county = county_names[raw_county]
                break

    if not reported_totals:
        raise ValueError(f"Could not find Iowa statewide presidential totals in {path}")

    parsed_totals = {
        "harris": sum(row["harris"] for row in result_rows),
        "trump": sum(row["trump"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
    }
    reported_candidate_totals = {
        "harris": reported_totals["harris"],
        "trump": reported_totals["trump"],
        **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
    }
    if parsed_totals != reported_candidate_totals:
        raise ValueError(f"Iowa parsed county totals do not match PDF totals: {parsed_totals} != {reported_candidate_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_idaho_county_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    columns = source["columns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []
    reported_totals = None

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            county = str(row.get(columns["county"], "") or "").strip()
            if not county:
                continue

            totals = {
                "trump": int_text(row.get(columns["trump"])),
                "harris": int_text(row.get(columns["harris"])),
                **{item["key"]: int_text(row.get(columns[item["column"]])) for item in source.get("otherCandidates", [])},
            }
            other = sum(totals[item["key"]] for item in candidate_labels)
            total = totals["trump"] + totals["harris"] + other
            reported_total = int_text(row.get(columns["totalVotesCast"]))
            if reported_total and total != reported_total:
                raise ValueError(f"Idaho candidate total mismatch for {county}: {total} != {reported_total}")

            if county == source.get("totalsLabel", "Totals"):
                reported_totals = {**totals, "total": reported_total}
                continue

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
                    **{item["key"]: totals[item["key"]] for item in candidate_labels},
                    "margin": margin,
                    "marginPct": round((margin / total) * 100, 4) if total else 0,
                    "total": total,
                }
            )

    if not reported_totals:
        raise ValueError(f"Could not find Idaho Totals row in {path}")

    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "total": sum(row["total"] for row in result_rows),
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Idaho parsed county totals do not match CSV totals: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_colorado_civera_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Colorado results CSV has too few rows: {path}")

    header = rows[0]
    columns = source["columns"]
    column_index = {name: index for index, name in enumerate(header)}
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []
    reported_totals = None

    def row_totals(row):
        totals = {
            "harris": int_text(row[column_index[columns["harris"]]]),
            "trump": int_text(row[column_index[columns["trump"]]]),
            **{
                item["key"]: int_text(row[column_index[columns[item["column"]]]])
                for item in source.get("otherCandidates", [])
            },
        }
        other = sum(totals[item["key"]] for item in candidate_labels)
        total = totals["harris"] + totals["trump"] + other
        reported_total = int_text(row[column_index[columns["totalVotesCast"]]])
        if total != reported_total:
            raise ValueError(f"Colorado candidate total mismatch for {row[1]}: {total} != {reported_total}")
        return totals, total

    for row in rows[2:]:
        if len(row) < len(header):
            continue
        row_type = str(row[0] or "").strip()
        county = str(row[1] or "").strip()
        if row_type not in {"State", "County"}:
            continue
        totals, total = row_totals(row)
        if row_type == "State":
            reported_totals = {**totals, "total": total}
            continue

        other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
        other = sum(other_values.values())
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
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    if not reported_totals:
        raise ValueError(f"Could not find Colorado State row in {path}")

    parsed_totals = {
        "harris": sum(row["harris"] for row in result_rows),
        "trump": sum(row["trump"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "total": sum(row["total"] for row in result_rows),
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Colorado parsed county totals do not match CSV state row: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_maine_county_town_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    columns = source["columns"]
    column_index, rows = read_sheet_rows(path, source.get("sheet", "President & VP"))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    county_codes = source["countyCodes"]
    result_rows = []
    precinct_rows = 0

    for row in rows:
        county_code = str(row[column_index[columns["countyCode"]]] or "").strip()
        municipality = str(row[column_index[columns["municipality"]]] or "").strip()
        if county_code and municipality:
            precinct_rows += 1
            continue
        if municipality == source.get("uocavaLabel", "STATE UOCAVA"):
            county = source.get("uocavaCountyName", "State UOCAVA")
            precinct_rows += 1
        elif municipality.endswith(" Total") and municipality != "Statewide Total":
            code = municipality.removesuffix(" Total").strip()
            county = county_codes.get(code)
            if not county:
                continue
        else:
            continue
        trump = int_cell(row, column_index, columns["trump"])
        harris = int_cell(row, column_index, columns["harris"])
        other_values = {
            item["key"]: int_cell(row, column_index, columns.get(item["column"], item["column"]))
            for item in source.get("otherCandidates", [])
        }
        other = sum(other_values.values())
        total = trump + harris + other
        margin = trump - harris
        result_rows.append(
            {
                "county": county,
                "trump": trump,
                "trumpPct": pct(trump, total),
                "harris": harris,
                "harrisPct": pct(harris, total),
                "other": other,
                "otherPct": pct(other, total),
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, precinct_rows


def certified_results_tennessee_precinct_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    columns = source["columns"]
    column_index, rows = read_sheet_rows(path, source.get("sheet", "SOFFICEL"))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = defaultdict(lambda: defaultdict(int))
    precinct_rows = 0

    for row in rows:
        if row[column_index[columns["office"]]] != source["officeName"]:
            continue
        county = row[column_index[columns["county"]]]
        if not county:
            continue
        precinct_rows += 1
        totals = by_county[f"{county} County"]
        for slot in range(1, int(source.get("candidateSlots", 10)) + 1):
            name_column = f"{columns['candidatePrefix']}{slot}"
            vote_column = f"{columns['votesPrefix']}{slot}"
            name_index = column_index.get(name_column)
            vote_index = column_index.get(vote_column)
            if name_index is None or vote_index is None or name_index >= len(row):
                continue
            candidate = row[name_index]
            if not candidate:
                continue
            votes = int_text(row[vote_index] if vote_index < len(row) else 0)
            if new_york_column_matches(candidate, "", source["majorCandidates"]["trump"]):
                totals["trump"] += votes
            elif new_york_column_matches(candidate, "", source["majorCandidates"]["harris"]):
                totals["harris"] += votes
            else:
                key = "unmappedOther"
                for item in source.get("otherCandidates", []):
                    if new_york_column_matches(candidate, "", item):
                        key = item["key"]
                        break
                totals[key] += votes

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, precinct_rows


def new_york_column_matches(header_value, party_value, rule):
    if rule.get("columnHeader") and str(header_value).strip() != rule["columnHeader"]:
        return False
    if rule.get("candidateContains") and rule["candidateContains"].lower() not in str(header_value).lower():
        return False
    if rule.get("partyCode") and normalize_party(party_value) != normalize_party(rule["partyCode"]):
        return False
    return True


def certified_results_new_york_county_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"New York county results source has too few rows: {path}")

    header = rows[0]
    party_row = rows[1]
    excluded_columns = set(source.get("excludeColumns", ["Blank", "Void", "Total Votes", ""]))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []

    for row in rows[2:]:
        if len(row) < 2 or row[0] != "County":
            continue
        county = str(row[1]).strip()
        totals = defaultdict(int)
        for index, header_value in enumerate(header):
            if index >= len(row) or header_value in excluded_columns:
                continue
            party_value = party_row[index] if index < len(party_row) else ""
            votes = int_text(row[index])
            if new_york_column_matches(header_value, party_value, source["majorCandidates"]["trump"]):
                totals["trump"] += votes
            elif new_york_column_matches(header_value, party_value, source["majorCandidates"]["harris"]):
                totals["harris"] += votes
            else:
                matched_other = False
                for candidate in source.get("otherCandidates", []):
                    if new_york_column_matches(header_value, party_value, candidate):
                        totals[candidate["key"]] += votes
                        matched_other = True
                        break
                if not matched_other and header_value:
                    totals["unmappedOther"] += votes

        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_kansas_presidential_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    columns = source.get(
        "columns",
        {
            "county": "County",
            "precinct": "Precinct",
            "race": "Race",
            "candidate": "Candidate",
            "party": "Party",
            "votes": "Votes",
        },
    )
    column_index, rows = read_sheet_rows(path, source.get("sheet", "2024 Presidential Results"))
    by_county = defaultdict(lambda: defaultdict(int))
    precinct_keys = set()
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    contest_name = source.get("contestName", "President / Vice President").upper()

    for row in rows:
        race = str(row[column_index[columns["race"]]] if len(row) > column_index[columns["race"]] else "").strip()
        if race.upper() != contest_name:
            continue
        county = str(row[column_index[columns["county"]]] if len(row) > column_index[columns["county"]] else "").strip()
        precinct = str(row[column_index[columns["precinct"]]] if len(row) > column_index[columns["precinct"]] else "").strip()
        candidate = str(row[column_index[columns["candidate"]]] if len(row) > column_index[columns["candidate"]] else "").strip()
        party = str(row[column_index[columns["party"]]] if len(row) > column_index[columns["party"]] else "").strip()
        votes = int_text(row[column_index[columns["votes"]]] if len(row) > column_index[columns["votes"]] else 0)
        if not county or not candidate:
            continue
        precinct_keys.add((county, precinct))

        if new_york_column_matches(candidate, party, source["majorCandidates"]["trump"]):
            by_county[county]["trump"] += votes
        elif new_york_column_matches(candidate, party, source["majorCandidates"]["harris"]):
            by_county[county]["harris"] += votes
        else:
            matched_other = False
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, party, item):
                    by_county[county][item["key"]] += votes
                    matched_other = True
                    break
            if not matched_other:
                by_county[county]["unmappedOther"] += votes

    result_rows = []
    for county, totals in sorted(by_county.items()):
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    expected_totals = source.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            "other": sum(row["other"] for row in result_rows),
            "total": sum(row["total"] for row in result_rows),
        }
        for item in candidate_labels:
            parsed_totals[item["key"]] = sum(row[item["key"]] for row in result_rows)
        if parsed_totals != expected_totals:
            raise ValueError(f"Kansas presidential workbook totals do not match expected totals: {parsed_totals} != {expected_totals}")

    return result_rows, candidate_labels, len(precinct_keys)


def certified_results_virginia_locality_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Virginia locality results source has too few rows: {path}")

    header = rows[0]
    party_row = rows[1]
    excluded_columns = set(source.get("excludeColumns", ["", "Total Votes Cast"]))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []
    reported_totals = None

    for row in rows[2:]:
        if len(row) < 2:
            continue
        row_type = str(row[0]).strip()
        if row_type not in {"State", "Locality"}:
            continue

        totals = defaultdict(int)
        for index, header_value in enumerate(header):
            if index >= len(row) or header_value in excluded_columns:
                continue
            party_value = party_row[index] if index < len(party_row) else ""
            votes = int_text(row[index])
            if new_york_column_matches(header_value, party_value, source["majorCandidates"]["trump"]):
                totals["trump"] += votes
            elif new_york_column_matches(header_value, party_value, source["majorCandidates"]["harris"]):
                totals["harris"] += votes
            else:
                matched_other = False
                for candidate in source.get("otherCandidates", []):
                    if new_york_column_matches(header_value, party_value, candidate):
                        totals[candidate["key"]] += votes
                        matched_other = True
                        break
                if not matched_other and header_value:
                    totals["unmappedOther"] += votes

        if row_type == "State":
            reported_totals = totals
            continue

        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
        margin = totals["trump"] - totals["harris"]
        result_rows.append(
            {
                "county": str(row[1]).strip(),
                "trump": totals["trump"],
                "trumpPct": pct(totals["trump"], total),
                "harris": totals["harris"],
                "harrisPct": pct(totals["harris"], total),
                "other": other,
                "otherPct": pct(other, total),
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    if reported_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
            "unmappedOther": sum(
                row["other"] - sum(row[item["key"]] for item in candidate_labels)
                for row in result_rows
            ),
        }
        expected_totals = {
            "trump": reported_totals["trump"],
            "harris": reported_totals["harris"],
            **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
            "unmappedOther": reported_totals["unmappedOther"],
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Virginia locality totals do not match State row: {parsed_totals} != {expected_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def normalize_connecticut_town(value, aliases):
    value = aliases.get(value, value)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def parse_connecticut_town_sections(lines, section_kind):
    town_rows = {}
    first_header = {
        "major": "Harris and Walz",
        "writeInFive": "Ayyadurai and Ellis",
        "writeInContinued": "Sonski and Onak",
    }[section_kind]
    number_count = 5 if section_kind in {"major", "writeInFive"} else 2
    row_pattern = re.compile(rf"^(.+?)\s+((?:[\d,]+\s+){{{number_count - 1}}}[\d,]+)$")

    for index, line in enumerate(lines):
        if line.strip() != "Summarized by Town":
            continue
        context = " ".join(item.strip() for item in lines[max(0, index - 2) : index + 6])
        if section_kind == "major":
            if "Write-In" in context:
                continue
        elif section_kind == "writeInFive":
            if "Write-In's Continued" in context or first_header not in context:
                continue
        elif section_kind == "writeInContinued":
            if first_header not in context:
                continue

        start = None
        for header_index in range(index + 1, min(index + 8, len(lines))):
            if first_header in lines[header_index]:
                start = header_index + 1
                break
        if start is None:
            continue

        for row_line in lines[start:]:
            row_line = row_line.strip()
            if not row_line:
                continue
            if row_line.startswith("Election Results for"):
                break
            if row_line.startswith("Total"):
                break
            match = row_pattern.match(row_line)
            if not match:
                continue
            town = match.group(1).strip()
            values = [int_text(value) for value in match.group(2).split()]
            town_rows[town] = values

    return town_rows


def certified_results_connecticut_statement_text(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    map_path = local_source(config, source["townMapSourceId"])
    county_names = geometry_names_by_geoid(config)
    aliases = source.get("townAliases", {})
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]

    subdivision_lookup = {}
    subdivision_geojson = json.loads(map_path.read_text(encoding="utf-8"))
    for feature in subdivision_geojson.get("features", []):
        props = feature.get("properties", {})
        state_code = str(props.get("STATE") or "")
        county_code = str(props.get("COUNTY") or "").zfill(3)
        county = county_names.get(f"{state_code}{county_code}")
        basename = props.get("BASENAME") or props.get("NAME")
        if county and basename:
            subdivision_lookup[normalize_connecticut_town(basename, aliases)] = county

    try:
        statement_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        statement_text = path.read_text(encoding="utf-16")
    lines = statement_text.splitlines()
    senate_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "Election Results for United States Senator"),
        len(lines),
    )
    presidential_lines = lines[:senate_index]
    major_rows = parse_connecticut_town_sections(presidential_lines, "major")
    write_in_five_rows = parse_connecticut_town_sections(presidential_lines, "writeInFive")
    write_in_continued_rows = parse_connecticut_town_sections(presidential_lines, "writeInContinued")

    if not major_rows:
        raise ValueError(f"Connecticut statement source has no parsed town presidential rows: {path}")
    if set(major_rows) != set(write_in_five_rows) or set(major_rows) != set(write_in_continued_rows):
        raise ValueError("Connecticut statement write-in town rows do not match major-candidate town rows")

    by_county = defaultdict(lambda: defaultdict(int))
    missing = []
    for town, values in major_rows.items():
        county = subdivision_lookup.get(normalize_connecticut_town(town, aliases))
        if not county:
            missing.append(town)
            continue
        totals = by_county[county]
        totals["harris"] += values[0]
        totals["trump"] += values[1]
        totals["stein"] += values[2]
        totals["oliver"] += values[3]
        totals["kennedy"] += values[4]
        write_in_five = write_in_five_rows[town]
        totals["ayyadurai"] += write_in_five[0]
        totals["deLaCruz"] += write_in_five[1]
        totals["fox"] += write_in_five[2]
        totals["mcneil"] += write_in_five[3]
        totals["futureMadamPotus"] += write_in_five[4]
        write_in_continued = write_in_continued_rows[town]
        totals["sonski"] += write_in_continued[0]
        totals["west"] += write_in_continued[1]

    if missing:
        raise ValueError(f"Connecticut town rows could not be mapped to a planning region: {', '.join(sorted(missing))}")

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels)
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(major_rows)


def normalize_vermont_municipality(value, aliases):
    value = aliases.get(value, value)
    value = value.replace("St.", "Saint").replace("W.", "West")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def certified_results_vermont_municipality_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    map_source = source["municipalityMapSourceId"]
    map_path = local_source(config, map_source)
    county_names = geometry_names_by_geoid(config)
    aliases = source.get("municipalityAliases", {})
    suffix_aliases = source.get("municipalitySuffixAliases", {})
    columns = source["columns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]

    subdivision_lookup = defaultdict(list)
    subdivision_geojson = json.loads(map_path.read_text(encoding="utf-8"))
    for feature in subdivision_geojson.get("features", []):
        props = feature.get("properties", {})
        county_code = str(props.get("COUNTY") or "").zfill(3)
        state_code = str(props.get("STATE") or "")
        county = county_names.get(f"{state_code}{county_code}")
        basename = props.get("BASENAME")
        full_name = props.get("NAME") or ""
        if county and basename:
            key = normalize_vermont_municipality(basename, aliases)
            subdivision_lookup[key].append({"county": county, "name": full_name.lower()})

    by_county = defaultdict(lambda: defaultdict(int))
    missing = []
    precinct_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            municipality = str(row.get(columns["municipality"], "")).strip()
            if not municipality or municipality == source.get("partyRowLabel", ""):
                continue
            if municipality in source.get("skipRows", []):
                continue
            candidates = subdivision_lookup.get(normalize_vermont_municipality(municipality, aliases), [])
            suffix = suffix_aliases.get(municipality)
            if suffix:
                candidates = [item for item in candidates if item["name"].endswith(suffix)]
            if len(candidates) != 1:
                missing.append(municipality)
                continue

            precinct_rows += 1
            totals = by_county[candidates[0]["county"]]
            totals["trump"] += int_text(row.get(columns["trump"]))
            totals["harris"] += int_text(row.get(columns["harris"]))
            for candidate in source.get("otherCandidates", []):
                totals[candidate["key"]] += int_text(row.get(columns[candidate["column"]]))

    if missing:
        raise ValueError(f"Vermont municipality rows could not be mapped to a county: {', '.join(sorted(missing))}")

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels)
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, precinct_rows


def geometry_names_by_geoid(config):
    geometry = config.get("geometry", {})
    source_id = geometry.get("sourceId")
    if not source_id:
        return {}
    path = local_source(config, source_id)
    if not path.exists():
        return {}
    geojson = json.loads(path.read_text(encoding="utf-8"))
    code_property = geometry.get("codeProperty", "GEOID")
    name_property = geometry.get("nameProperty", "NAME")
    names = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geoid = str(props.get(code_property) or props.get("GEOID") or "").zfill(5)
        name = props.get(name_property) or props.get("NAME")
        if geoid and name:
            names[geoid] = name
    return names


def national_county_baseline_name(row):
    name = str(row.get("county_name", "")).strip()
    return re.sub(
        r"\s+(County|Parish|Borough|Census Area|Municipality|city)$",
        "",
        name,
        flags=re.IGNORECASE,
    )


def certified_results_national_county_baseline_csv(config):
    source = config["certifiedResults"]
    state_name = source.get("stateName", config["name"]).lower()
    geoid_names = geometry_names_by_geoid(config)
    candidate_labels = [{"key": "nationalOther", "label": "Other candidates"}]
    result_rows = []
    with local_source(config, source["sourceId"]).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("state_name", "")).lower() != state_name:
                continue
            geoid = str(row.get("county_fips", "")).zfill(5)
            trump = int_text(row.get("votes_gop"))
            harris = int_text(row.get("votes_dem"))
            total = int_text(row.get("total_votes"))
            other = max(0, total - trump - harris)
            margin = trump - harris
            result_rows.append(
                {
                    "county": geoid_names.get(geoid) or national_county_baseline_name(row),
                    "trump": trump,
                    "trumpPct": pct(trump, total),
                    "harris": harris,
                    "harrisPct": pct(harris, total),
                    "other": other,
                    "otherPct": pct(other, total),
                    "nationalOther": other,
                    "margin": margin,
                    "marginPct": round((margin / total) * 100, 4) if total else 0,
                    "total": total,
                }
            )
    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_wyoming_statewide_summary_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    workbook_name = source.get("workbook")

    if workbook_name:
        with zipfile.ZipFile(path) as archive:
            workbook_bytes = archive.read(workbook_name)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
            handle.write(workbook_bytes)
            workbook_path = Path(handle.name)
        try:
            rows = list(iter_worksheet_rows(workbook_path, source["sheet"]))
        finally:
            workbook_path.unlink(missing_ok=True)
    else:
        rows = list(iter_worksheet_rows(path, source["sheet"]))

    contest = source.get("contest", config["office"])
    contest_row_index = next(
        (
            index
            for index, row in enumerate(rows)
            if any(str(value or "").strip() == contest for value in row)
        ),
        None,
    )
    if contest_row_index is None or contest_row_index + 1 >= len(rows):
        raise ValueError(f"Could not find Wyoming contest {contest!r} in {path}")

    candidate_row = rows[contest_row_index + 1]
    county_column = source.get("countyColumn", 0)
    candidate_column_start = source.get("candidateColumnStart", county_column + 1)
    candidate_column_end = source.get("candidateColumnEnd", len(candidate_row))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []

    for row in rows[contest_row_index + 2 :]:
        if len(row) <= county_column:
            continue
        county = str(row[county_column] or "").strip()
        if not county:
            continue
        if county.lower() == "total":
            break

        totals = defaultdict(int)
        for index, header_value in enumerate(candidate_row):
            if index < candidate_column_start or index >= candidate_column_end:
                continue
            if index >= len(row):
                continue
            if new_york_column_matches(header_value, "", source["majorCandidates"]["trump"]):
                totals["trump"] += int_text(row[index])
            elif new_york_column_matches(header_value, "", source["majorCandidates"]["harris"]):
                totals["harris"] += int_text(row[index])
            else:
                for candidate in source.get("otherCandidates", []):
                    if new_york_column_matches(header_value, "", candidate):
                        totals[candidate["key"]] += int_text(row[index])
                        break

        other = sum(totals[item["key"]] for item in candidate_labels)
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_montana_canvass_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    try:
        start = lines.index(source.get("contest", "PRESIDENT & VICE PRESIDENT"))
    except ValueError as error:
        raise ValueError(f"Could not find Montana presidential contest in {path}") from error

    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith(source.get("endMarker", "Page 2 of"))),
        None,
    )
    if end is None:
        raise ValueError(f"Could not find Montana presidential contest page boundary in {path}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    other_keys = [item["key"] for item in candidate_labels]
    row_pattern = re.compile(
        r"^(?P<county>[A-Z][A-Z\s]+?)\s+"
        r"(?P<harris>\d+)\s+(?P<green>\d+)\s+(?P<libertarian>\d+)\s+"
        r"(?P<trump>\d+)\s+(?P<kennedy>\d+)$"
    )
    total_pattern = re.compile(
        r"^Total\s+(?P<harris>\d+)\s+(?P<green>\d+)\s+(?P<libertarian>\d+)\s+"
        r"(?P<trump>\d+)\s+(?P<kennedy>\d+)$"
    )
    result_rows = []
    reported_totals = None

    for line in lines[start + 1 : end]:
        total_match = total_pattern.match(line)
        if total_match:
            reported_totals = {key: int_text(value) for key, value in total_match.groupdict().items()}
            continue
        match = row_pattern.match(line)
        if not match:
            continue

        raw_county = "LEWIS AND CLARK" if match.group("county") == "LEWIS AND" else match.group("county")
        county = county_names.get(raw_county) or f"{raw_county.title()} County"
        totals = {key: int_text(value) for key, value in match.groupdict().items() if key != "county"}
        other = sum(totals[key] for key in other_keys)
        total = totals["trump"] + totals["harris"] + other
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
                **{key: totals[key] for key in other_keys},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    if reported_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            **{key: sum(row[key] for row in result_rows) for key in other_keys},
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"Montana parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def clean_html_cell(value):
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def certified_results_delaware_county_html(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    document = path.read_text(encoding="utf-8")
    start = document.find(source.get("sectionMarker", 'id="bycounty"'))
    end = document.find(source.get("endMarker", 'id="bycountyw"'), start)
    if start < 0 or end < 0:
        raise ValueError(f"Could not find Delaware by-county results section in {path}")

    section = document[start:end]
    contest_index = section.find(source.get("contestClass", "PresidentandVicePresident"))
    if contest_index < 0:
        raise ValueError(f"Could not find Delaware presidential contest table in {path}")
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", section[contest_index:], flags=re.DOTALL | re.IGNORECASE)
    if not tbody_match:
        raise ValueError(f"Could not find Delaware presidential by-county table body in {path}")

    county_columns = source["countyColumns"]
    state_column = source.get("stateColumn", "State")
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = defaultdict(lambda: defaultdict(int))

    for row_html in re.findall(r"<tr>(.*?)</tr>", tbody_match.group(1), flags=re.DOTALL | re.IGNORECASE):
        cells = [
            clean_html_cell(cell)
            for cell in re.findall(r"<td(?:\s[^>]*)?>(.*?)</td>", row_html, flags=re.DOTALL | re.IGNORECASE)
        ]
        if len(cells) < 4:
            continue
        candidate = cells[0]
        party = cells[1] if len(cells) > 1 else ""
        if new_york_column_matches(candidate, party, source["majorCandidates"]["trump"]):
            key = "trump"
        elif new_york_column_matches(candidate, party, source["majorCandidates"]["harris"]):
            key = "harris"
        else:
            key = "unmappedOther"
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, party, item):
                    key = item["key"]
                    break

        county_sum = 0
        for county_name, column_index in county_columns.items():
            votes = int_text(cells[column_index])
            by_county[county_name][key] += votes
            county_sum += votes
        state_index = source.get("columnIndexes", {}).get(state_column)
        if state_index is not None and state_index < len(cells):
            reported_state_total = int_text(cells[state_index])
            if county_sum != reported_state_total:
                raise ValueError(
                    f"Delaware county totals for {candidate!r} do not match State column: "
                    f"{county_sum} != {reported_state_total}"
                )

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_maryland_county_html(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    document = path.read_text(encoding="utf-8", errors="replace").replace("\n", " ")
    table_matches = list(re.finditer(r"<table[^>]*>(.*?)</table>", document, flags=re.DOTALL | re.IGNORECASE))
    if not table_matches:
        raise ValueError(f"Could not find Maryland county breakdown table in {path}")

    geometry_names = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
        for name in geometry_names_by_geoid(config).values()
    }
    geometry_names["baltimore city"] = "Baltimore city"
    rows = []
    current_header = None
    for table_match in table_matches:
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.DOTALL | re.IGNORECASE):
            cells = [
                clean_html_cell(cell)
                for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, flags=re.DOTALL | re.IGNORECASE)
            ]
            if not cells:
                continue
            if cells[0] == "Jurisdiction":
                current_header = cells
                continue
            if cells[0] == "Totals":
                continue
            if not current_header:
                raise ValueError(f"Maryland county row appeared before a header: {cells}")
            rows.append((current_header, cells))

    by_county = defaultdict(lambda: defaultdict(int))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    for header, cells in rows:
        raw_county = cells[0]
        county = geometry_names.get(raw_county.lower()) or f"{raw_county} County"
        for index, header_value in enumerate(header[1:], start=1):
            votes = int_text(cells[index] if index < len(cells) else 0)
            if new_york_column_matches(header_value, "", source["majorCandidates"]["trump"]):
                key = "trump"
            elif new_york_column_matches(header_value, "", source["majorCandidates"]["harris"]):
                key = "harris"
            else:
                key = "unmappedOther"
                for item in source.get("otherCandidates", []):
                    if new_york_column_matches(header_value, "", item):
                        key = item["key"]
                        break
                if "(Write In)" in header_value and source.get("writeInKey"):
                    key = source["writeInKey"]
            by_county[county][key] += votes

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    expected_totals = source.get("expectedTotals")
    if expected_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            "other": sum(row["other"] for row in result_rows),
            "total": sum(row["total"] for row in result_rows),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Maryland parsed totals do not match expected totals: {parsed_totals} != {expected_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_massachusetts_county_html(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    document = path.read_text(encoding="utf-8", errors="replace").replace("\n", " ")
    table_match = re.search(
        r"<table[^>]*id=[\"']precinct_data[\"'][^>]*>(.*?)</table>",
        document,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        raise ValueError(f"Could not find Massachusetts PD43+ county table in {path}")

    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.DOTALL | re.IGNORECASE):
        cells = [
            clean_html_cell(cell)
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, flags=re.DOTALL | re.IGNORECASE)
        ]
        if cells:
            rows.append(cells)
    if not rows:
        raise ValueError(f"Could not find Massachusetts PD43+ table rows in {path}")

    header = rows[0]
    column_index = {name: index for index, name in enumerate(header)}
    required_columns = ["Harris/ Walz", "Trump/ Vance", "All Others", "Blanks", "Total Votes Cast"]
    missing_columns = [name for name in required_columns if name not in column_index]
    if missing_columns:
        raise ValueError(f"Massachusetts PD43+ table missing columns: {missing_columns}")

    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []
    reported_totals = None
    reported_blanks = 0
    reported_total_votes_cast = 0

    for cells in rows[1:]:
        if len(cells) < len(header):
            continue
        county = cells[0]
        totals = {
            "harris": int_text(cells[column_index["Harris/ Walz"]]),
            "trump": int_text(cells[column_index["Trump/ Vance"]]),
            "allOthers": int_text(cells[column_index["All Others"]]),
        }
        for item in source.get("otherCandidates", []):
            totals[item["key"]] = int_text(cells[column_index[item["columnHeader"]]])
        blanks = int_text(cells[column_index["Blanks"]])
        total_votes_cast = int_text(cells[column_index["Total Votes Cast"]])
        other = totals["allOthers"] + sum(totals[item["key"]] for item in candidate_labels if item["key"] != "allOthers")
        candidate_total = totals["trump"] + totals["harris"] + other
        if candidate_total + blanks != total_votes_cast:
            raise ValueError(
                f"Massachusetts PD43+ total mismatch for {county}: "
                f"{candidate_total} + {blanks} != {total_votes_cast}"
            )

        if county == "Totals":
            reported_totals = {**totals, "other": other, "total": candidate_total}
            reported_blanks = blanks
            reported_total_votes_cast = total_votes_cast
            continue

        margin = totals["trump"] - totals["harris"]
        result_rows.append(
            {
                "county": county,
                "trump": totals["trump"],
                "trumpPct": pct(totals["trump"], candidate_total),
                "harris": totals["harris"],
                "harrisPct": pct(totals["harris"], candidate_total),
                "other": other,
                "otherPct": pct(other, candidate_total),
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / candidate_total) * 100, 4) if candidate_total else 0,
                "total": candidate_total,
            }
        )

    if reported_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            "other": sum(row["other"] for row in result_rows),
            "total": sum(row["total"] for row in result_rows),
            **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        }
        expected_totals = {
            "trump": reported_totals["trump"],
            "harris": reported_totals["harris"],
            "other": reported_totals["other"],
            "total": reported_totals["total"],
            **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Massachusetts county totals do not match PD43+ totals row: {parsed_totals} != {expected_totals}")
        if parsed_totals["total"] + reported_blanks != reported_total_votes_cast:
            raise ValueError(
                "Massachusetts PD43+ statewide candidate total plus blanks does not match Total Votes Cast: "
                f"{parsed_totals['total']} + {reported_blanks} != {reported_total_votes_cast}"
            )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def hawaii_statewide_presidential_totals(path, candidate_rules):
    with path.open("r", encoding="utf-16", newline="") as handle:
        rows = csv.reader(handle)
        try:
            next(rows)
            header = next(rows)
        except StopIteration as error:
            raise ValueError(f"Could not read Hawaii statewide summary header from {path}") from error

        column_index = {name.lstrip("#"): index for index, name in enumerate(header)}
        required_columns = ["Contest Title", "Candidate Name", "Total Votes"]
        missing_columns = [name for name in required_columns if name not in column_index]
        if missing_columns:
            raise ValueError(f"Hawaii statewide summary missing columns: {missing_columns}")

        totals = defaultdict(int)
        for row in rows:
            if len(row) <= max(column_index.values()):
                continue
            if row[column_index["Contest Title"]] != "President and Vice President":
                continue
            candidate_name = re.sub(r"\s+", " ", row[column_index["Candidate Name"]]).upper()
            matched_key = next(
                (
                    key
                    for key, rule in candidate_rules.items()
                    if rule["contains"].upper() in candidate_name
                ),
                None,
            )
            if matched_key:
                totals[matched_key] += int_text(row[column_index["Total Votes"]])
        return dict(totals)


def certified_results_hawaii_county_summary_pdfs(config):
    source = config["certifiedResults"]
    candidate_rules = {
        "harris": {"contains": "HARRIS", "pattern": r"\(D\)\s+HARRIS,\s+Kamala D\.\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "trump": {"contains": "TRUMP", "pattern": r"\(R\)\s+TRUMP,\s+Donald J\.\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "stein": {"contains": "STEIN", "pattern": r"\(G\)\s+STEIN,\s+Jill\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "oliver": {"contains": "OLIVER", "pattern": r"\(L\)\s+OLIVER,\s+Chase\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "deLaCruz": {"contains": "DE LA CRUZ", "pattern": r"\(SL\)\s+DE LA CRUZ,\s+Claudia\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "sonski": {"contains": "SONSKI", "pattern": r"\(S\)\s+SONSKI,\s+Peter\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []

    for county_source in source.get("countySources", []):
        path = local_source(config, county_source["sourceId"])
        text = re.sub(r"\s+", " ", extract_pdf_text(path))
        totals = {}
        for key, rule in candidate_rules.items():
            match = re.search(rule["pattern"], text)
            if not match:
                raise ValueError(f"Could not find Hawaii {key} total in {path}")
            totals[key] = int_text(match.group(1))

        other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
        other = sum(other_values.values())
        total = totals["trump"] + totals["harris"] + other
        margin = totals["trump"] - totals["harris"]
        result_rows.append(
            {
                "county": county_source["county"],
                "trump": totals["trump"],
                "trumpPct": pct(totals["trump"], total),
                "harris": totals["harris"],
                "harrisPct": pct(totals["harris"], total),
                "other": other,
                "otherPct": pct(other, total),
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    statewide_source_id = source.get("statewideSummarySourceId")
    if statewide_source_id:
        statewide_totals = hawaii_statewide_presidential_totals(local_source(config, statewide_source_id), candidate_rules)
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        }
        if parsed_totals != statewide_totals:
            raise ValueError(f"Hawaii county PDF totals do not match statewide summary: {parsed_totals} != {statewide_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_new_jersey_president_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    counties = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = defaultdict(lambda: defaultdict(int))
    candidate_totals = defaultdict(int)
    current_key = None

    for line in lines:
        if line.startswith("Total "):
            if current_key:
                candidate_totals[current_key] += int_text(re.findall(r"\d[\d,]*", line)[-1])
            current_key = None
            continue

        for key, rule in {
            "trump": source["majorCandidates"]["trump"],
            "harris": source["majorCandidates"]["harris"],
            **{item["key"]: item for item in source.get("otherCandidates", [])},
        }.items():
            if rule.get("candidateContains") and rule["candidateContains"].lower() in line.lower():
                current_key = key
                break

        if not current_key:
            continue
        raw_county = next((name for name in counties if line.startswith(f"{name} ")), None)
        if not raw_county:
            continue
        by_county[counties[raw_county]][current_key] += int_text(re.findall(r"\d[\d,]*", line)[-1])

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    parsed_candidate_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
    }
    if parsed_candidate_totals != dict(candidate_totals):
        raise ValueError(
            "New Jersey parsed county totals do not match PDF candidate totals: "
            f"{parsed_candidate_totals} != {dict(candidate_totals)}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_washington_county_html(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    document = path.read_text(encoding="utf-8")
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_pattern = re.compile(
        r'<td class="CountyName" rowspan="\d+">(?P<county>[^<]+)</td>'
        r"(?P<body>.*?)(?=<tr><td colspan=\"4\" class=\"Seperator\"></td></tr>)",
        flags=re.DOTALL,
    )
    row_pattern = re.compile(
        r'<div class="CandidateName">(?P<candidate>[^<]+)</div>.*?'
        r'<td class="CandidateVotes">(?P<votes>[\d,]+)</td>',
        flags=re.DOTALL,
    )
    total_pattern = re.compile(r'<td class="TotalVotes">Total Votes</td><td>(?P<votes>[\d,]+)</td>')
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []

    for county_match in county_pattern.finditer(document):
        raw_county = clean_html_cell(county_match.group("county"))
        county = county_names.get(raw_county.upper()) or f"{raw_county} County"
        totals = defaultdict(int)
        candidate_sum = 0
        for candidate_match in row_pattern.finditer(county_match.group("body")):
            candidate = clean_html_cell(candidate_match.group("candidate"))
            votes = int_text(candidate_match.group("votes"))
            candidate_sum += votes
            if new_york_column_matches(candidate, "", source["majorCandidates"]["trump"]):
                totals["trump"] += votes
            elif new_york_column_matches(candidate, "", source["majorCandidates"]["harris"]):
                totals["harris"] += votes
            else:
                matched_other = False
                for item in source.get("otherCandidates", []):
                    if new_york_column_matches(candidate, "", item):
                        totals[item["key"]] += votes
                        matched_other = True
                        break
                if not matched_other:
                    totals["unmappedOther"] += votes

        total_match = total_pattern.search(county_match.group("body"))
        if not total_match:
            raise ValueError(f"Washington county block missing Total Votes row: {county}")
        reported_total = int_text(total_match.group("votes"))
        if candidate_sum != reported_total:
            raise ValueError(f"Washington county total mismatch for {county}: {candidate_sum} != {reported_total}")

        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_south_carolina_enr_json(config):
    source = config["certifiedResults"]
    details_path = local_source(config, source["sourceId"])
    sum_path = local_source(config, source["statewideSourceId"])
    details = json.loads(details_path.read_text(encoding="utf-8"))
    statewide = json.loads(sum_path.read_text(encoding="utf-8"))
    contest_key = source["contestKey"]
    detail_contest = next(
        (contest for contest in details.get("Contests", []) if str(contest.get("K")) == str(contest_key)),
        None,
    )
    statewide_contest = next(
        (contest for contest in statewide.get("Contests", []) if str(contest.get("K")) == str(contest_key)),
        None,
    )
    if not detail_contest or not statewide_contest:
        raise ValueError(f"Could not find South Carolina ENR contest {contest_key!r}")

    county_names = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
        for name in geometry_names_by_geoid(config).values()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    candidate_keys = []
    for index, candidate in enumerate(statewide_contest.get("CH", [])):
        party = statewide_contest.get("P", [""])[index]
        if new_york_column_matches(candidate, party, source["majorCandidates"]["trump"]):
            candidate_keys.append("trump")
        elif new_york_column_matches(candidate, party, source["majorCandidates"]["harris"]):
            candidate_keys.append("harris")
        else:
            key = "unmappedOther"
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, party, item):
                    key = item["key"]
                    break
            candidate_keys.append(key)

    by_county = defaultdict(lambda: defaultdict(int))
    for county, votes in zip(detail_contest.get("P", []), detail_contest.get("V", [])):
        county_name = county_names.get(str(county).lower()) or f"{county} County"
        for index, key in enumerate(candidate_keys):
            if index < len(votes):
                by_county[county_name][key] += int(votes[index] or 0)

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "unmappedOther": sum(
            row["other"] - sum(row[item["key"]] for item in candidate_labels)
            for row in result_rows
        ),
        "total": sum(row["total"] for row in result_rows),
    }
    reported_totals = defaultdict(int)
    for key, votes in zip(candidate_keys, statewide_contest.get("V", [])):
        reported_totals[key] += int(votes or 0)
    expected_totals = {
        "trump": reported_totals["trump"],
        "harris": reported_totals["harris"],
        **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": reported_totals["unmappedOther"],
        "total": int(statewide_contest.get("T") or 0),
    }
    if parsed_totals != expected_totals:
        raise ValueError(
            "South Carolina ENR county totals do not match statewide summary totals: "
            f"{parsed_totals} != {expected_totals}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_north_carolina_enr_zip(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    contest_key = str(source["contestKey"])
    with zipfile.ZipFile(path) as archive:
        counties = json.loads(archive.read("county.txt").decode("utf-8"))
        statewide_results = json.loads(archive.read("results_0.txt").decode("utf-8"))

        county_names = {
            re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).upper(): name
            for name in geometry_names_by_geoid(config).values()
        }
        candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
        result_rows = []
        for county_info in counties:
            county_id = str(county_info.get("cid"))
            if county_id == "0":
                continue
            raw_county = str(county_info.get("cnm") or "").strip()
            county = county_names.get(raw_county.upper()) or f"{raw_county.title()} County"
            rows = json.loads(archive.read(f"results_{county_id}.txt").decode("utf-8"))
            totals = defaultdict(int)
            for row in rows:
                if str(row.get("lid")) != contest_key:
                    continue
                candidate = row.get("bnm", "")
                party = row.get("pty", "")
                votes = int_text(row.get("vct"))
                if new_york_column_matches(candidate, party, source["majorCandidates"]["trump"]):
                    totals["trump"] += votes
                elif new_york_column_matches(candidate, party, source["majorCandidates"]["harris"]):
                    totals["harris"] += votes
                else:
                    key = "unmappedOther"
                    for item in source.get("otherCandidates", []):
                        if new_york_column_matches(candidate, party, item):
                            key = item["key"]
                            break
                    totals[key] += votes

            other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
            total = totals["trump"] + totals["harris"] + other
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
                    **{item["key"]: totals[item["key"]] for item in candidate_labels},
                    "margin": margin,
                    "marginPct": round((margin / total) * 100, 4) if total else 0,
                    "total": total,
                }
            )

    statewide_totals = defaultdict(int)
    for row in statewide_results:
        if str(row.get("lid")) != contest_key:
            continue
        candidate = row.get("bnm", "")
        party = row.get("pty", "")
        votes = int_text(row.get("vct"))
        if new_york_column_matches(candidate, party, source["majorCandidates"]["trump"]):
            statewide_totals["trump"] += votes
        elif new_york_column_matches(candidate, party, source["majorCandidates"]["harris"]):
            statewide_totals["harris"] += votes
        else:
            key = "unmappedOther"
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, party, item):
                    key = item["key"]
                    break
            statewide_totals[key] += votes

    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "unmappedOther": sum(
            row["other"] - sum(row[item["key"]] for item in candidate_labels)
            for row in result_rows
        ),
    }
    expected_totals = {
        "trump": statewide_totals["trump"],
        "harris": statewide_totals["harris"],
        **{item["key"]: statewide_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": statewide_totals["unmappedOther"],
    }
    if parsed_totals != expected_totals:
        raise ValueError(
            "North Carolina ENR county totals do not match statewide result totals: "
            f"{parsed_totals} != {expected_totals}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_oklahoma_enr_zip(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    race_id = int(source["raceId"])
    with zipfile.ZipFile(path) as archive:
        config_data = json.loads(archive.read("config.json").decode("utf-8-sig"))
        election = json.loads(archive.read("election-sw.json").decode("utf-8-sig"))
        statewide_results = json.loads(archive.read("results-sw.json").decode("utf-8-sig"))

        county_options = config_data["counties"]["Options"]
        county_values = config_data["counties"]["Values"]
        county_names = {
            re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
            for name in geometry_names_by_geoid(config).values()
        }
        county_code_names = {
            str(code): county_names.get(str(name).lower()) or f"{name} County"
            for name, code in zip(county_options, county_values)
            if code
        }
        race = next((item for item in election.get("races", []) if int(item.get("raceID")) == race_id), None)
        if not race:
            raise ValueError(f"Could not find Oklahoma ENR race {race_id!r}")

        candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
        candidate_keys = []
        for candidate in race.get("raceCandidates", []):
            candidate_name = candidate.get("candName", "")
            if new_york_column_matches(candidate_name, "", source["majorCandidates"]["trump"]):
                candidate_keys.append("trump")
            elif new_york_column_matches(candidate_name, "", source["majorCandidates"]["harris"]):
                candidate_keys.append("harris")
            else:
                key = "unmappedOther"
                for item in source.get("otherCandidates", []):
                    if new_york_column_matches(candidate_name, "", item):
                        key = item["key"]
                        break
                candidate_keys.append(key)

        result_rows = []
        for county_code, county in sorted(county_code_names.items(), key=lambda item: item[1]):
            county_payload = json.loads(archive.read(f"results-cw-{county_code}.json").decode("utf-8-sig"))
            race_results = next(
                (item for item in county_payload.get("results", []) if int(item.get("raceID")) == race_id),
                None,
            )
            if not race_results:
                raise ValueError(f"Could not find Oklahoma county race {race_id!r} in county {county_code}")

            totals = defaultdict(int)
            for index, result in enumerate(race_results.get("candResults", [])):
                if index < len(candidate_keys):
                    totals[candidate_keys[index]] += int_text(result.get("totalVotes"))

            other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
            total = totals["trump"] + totals["harris"] + other
            reported_total = int_text(race_results.get("totResults", {}).get("totalVotes"))
            if total != reported_total:
                raise ValueError(
                    f"Oklahoma county total mismatch for {county}: parsed {total} != reported {reported_total}"
                )
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
                    **{item["key"]: totals[item["key"]] for item in candidate_labels},
                    "margin": margin,
                    "marginPct": round((margin / total) * 100, 4) if total else 0,
                    "total": total,
                }
            )

    statewide_race = next(
        (item for item in statewide_results.get("results", []) if int(item.get("raceID")) == race_id),
        None,
    )
    if not statewide_race:
        raise ValueError(f"Could not find Oklahoma statewide race {race_id!r}")
    statewide_totals = defaultdict(int)
    for index, result in enumerate(statewide_race.get("candResults", [])):
        if index < len(candidate_keys):
            statewide_totals[candidate_keys[index]] += int_text(result.get("totalVotes"))

    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "unmappedOther": sum(
            row["other"] - sum(row[item["key"]] for item in candidate_labels)
            for row in result_rows
        ),
    }
    expected_totals = {
        "trump": statewide_totals["trump"],
        "harris": statewide_totals["harris"],
        **{item["key"]: statewide_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": statewide_totals["unmappedOther"],
    }
    if parsed_totals != expected_totals:
        raise ValueError(
            "Oklahoma ENR county totals do not match statewide result totals: "
            f"{parsed_totals} != {expected_totals}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def rhode_island_town_from_precinct(value, town_county_map):
    text = str(value or "").strip()
    for town in sorted(town_county_map, key=len, reverse=True):
        if text == town or text.startswith(f"{town} "):
            return town
    return None


def certified_results_rhode_island_summary_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    column_index, rows = read_sheet_rows(path, source.get("sheet", "Candidate_Breakout"))
    contest_name = source.get("contest", "Presidential Electors For:")
    town_county_map = source["townCountyMap"]
    federal_row_name = source.get("federalPrecinctRowName", "Federal Precincts")
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = defaultdict(lambda: defaultdict(int))

    for row in rows:
        contest = row[column_index["Contest"]] if len(row) > column_index["Contest"] else ""
        if contest != contest_name:
            continue
        precinct_name = row[column_index["City/Town - Precinct"]] if len(row) > column_index["City/Town - Precinct"] else ""
        candidate = row[column_index["Candidate"]] if len(row) > column_index["Candidate"] else ""
        party = row[column_index["Party"]] if len(row) > column_index["Party"] else ""
        votes = int_text(row[column_index["Total"]] if len(row) > column_index["Total"] else 0)
        town = rhode_island_town_from_precinct(precinct_name, town_county_map)
        if town:
            county = town_county_map[town]
        elif str(precinct_name).startswith("Federal Precinct"):
            county = federal_row_name
        else:
            raise ValueError(f"Rhode Island precinct row does not map to a town or federal row: {precinct_name!r}")

        if new_york_column_matches(candidate, party, source["majorCandidates"]["trump"]):
            key = "trump"
        elif new_york_column_matches(candidate, party, source["majorCandidates"]["harris"]):
            key = "harris"
        else:
            key = "unmappedOther"
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, party, item):
                    key = item["key"]
                    break
        by_county[county][key] += votes

    result_rows = []
    for county, totals in by_county.items():
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_south_dakota_canvass_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    try:
        start = lines.index(source.get("contest", "Presidential Electors"))
    except ValueError as error:
        raise ValueError(f"Could not find South Dakota presidential electors table in {path}") from error

    county_start = next((index for index in range(start, len(lines)) if lines[index] == "County"), None)
    if county_start is None:
        raise ValueError(f"Could not find South Dakota presidential county header in {path}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    pending_county = None
    result_rows = []
    reported_totals = None

    for line in lines[county_start + 1 :]:
        if line.startswith(source.get("nextContest", "United States Representative")):
            break
        numbers = re.findall(r"\d[\d,]*", line)
        if not numbers:
            pending_county = line
            continue
        if len(numbers) != 4:
            continue

        if line.startswith("Total"):
            reported_totals = {
                "harris": int_text(numbers[0]),
                "libertarian": int_text(numbers[1]),
                "trump": int_text(numbers[2]),
                "independent": int_text(numbers[3]),
            }
            break

        county_part = re.sub(r"\s+\d[\d,\s]*$", "", line).strip()
        raw_county = county_part or pending_county
        if not raw_county:
            raise ValueError(f"South Dakota presidential row has votes without a county label: {line!r}")
        county = county_names.get(raw_county.upper()) or raw_county
        harris = int_text(numbers[0])
        libertarian = int_text(numbers[1])
        trump = int_text(numbers[2])
        independent = int_text(numbers[3])
        other = libertarian + independent
        total = trump + harris + other
        margin = trump - harris
        result_rows.append(
            {
                "county": county,
                "trump": trump,
                "trumpPct": pct(trump, total),
                "harris": harris,
                "harrisPct": pct(harris, total),
                "other": other,
                "otherPct": pct(other, total),
                "libertarian": libertarian,
                "independent": independent,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )
        pending_county = None

    if reported_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            "libertarian": sum(row["libertarian"] for row in result_rows),
            "independent": sum(row["independent"] for row in result_rows),
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"South Dakota parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def michigan_result_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
        if not first_line.startswith("TOTAL VOTER TURNOUT:"):
            handle.seek(0)
        for row in csv.DictReader(handle, delimiter="\t"):
            yield {
                "contest": row["OfficeDescription"],
                "party": row["PartyDescription"],
                "candidate": " ".join(
                    part.strip()
                    for part in (
                        row["CandidateLastName"],
                        row["CandidateFirstName"],
                        row["CandidateMiddleName"],
                    )
                    if part and part.strip()
                ),
                "votes": int_text(row["CandidateVotes"]),
                "county": title_county(row["CountyName"]),
            }


def title_county(value):
    return " ".join(part.capitalize() for part in str(value).split())


def alabama_county_name(value):
    normalized = re.sub(r"[^a-z0-9]", "", str(value or "").lower())
    overrides = {
        "dekalb": "DeKalb",
        "stclair": "St. Clair",
    }
    if normalized in overrides:
        return overrides[normalized]
    return title_county(re.sub(r"\s+county$", "", str(value or ""), flags=re.IGNORECASE))


def michigan_county_name(value):
    text = re.sub(r"\s+county$", "", str(value or ""), flags=re.IGNORECASE)
    return title_county(text.replace(".", ""))


def north_dakota_export_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.reader(handle)
        next(rows)
        for row in rows:
            if len(row) < 9:
                continue
            yield {
                "contest": row[0],
                "party": row[1],
                "candidate": row[3].strip(),
                "votes": int_text(row[5]),
                "precinctsReporting": row[7],
                "county": row[8].strip(),
            }


def pennsylvania_county_name(county_code):
    normalized = str(int_text(county_code)).zfill(2)
    return PENNSYLVANIA_COUNTY_NAMES.get(normalized, f"County {normalized}")


def pennsylvania_precinct_label(row):
    parts = [row["municipality"]]
    if row["breakdown1Code"] and row["breakdown1Name"]:
        parts.append(f"{row['breakdown1Code']} {row['breakdown1Name']}")
    if row["breakdown2Code"] and row["breakdown2Name"]:
        parts.append(f"{row['breakdown2Code']} {row['breakdown2Name']}")
    if len(parts) == 1 and row["precinctCode"]:
        parts.append(f"Precinct {int_text(row['precinctCode'])}")
    return " - ".join(part for part in parts if part) or "Unnamed precinct"


def pennsylvania_precinct_key(row, fields=None):
    key_fields = fields or [
        "countyCode",
        "precinctCode",
        "municipality",
        "breakdown1Code",
        "breakdown1Name",
        "breakdown2Code",
        "breakdown2Name",
    ]
    return tuple(str(row.get(field, "")) for field in key_fields)


def pennsylvania_bulk_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 33:
                continue
            has_yes_no_columns = len(row) >= 37
            municipal_offset = 2 if has_yes_no_columns else 0
            candidate = " ".join(
                part.strip()
                for part in (row[11], row[12], row[13], row[14])
                if part and part.strip()
            )
            yield {
                "year": row[0],
                "electionType": row[1],
                "countyCode": str(int_text(row[2])).zfill(2),
                "county": pennsylvania_county_name(row[2]),
                "precinctCode": str(row[3]).strip(),
                "officeCode": row[8].strip(),
                "party": row[9].strip(),
                "candidate": candidate,
                "votes": int_text(row[15]),
                "municipality": row[20 + municipal_offset].strip(),
                "breakdown1Code": row[21 + municipal_offset].strip(),
                "breakdown1Name": row[22 + municipal_offset].strip(),
                "breakdown2Code": row[23 + municipal_offset].strip(),
                "breakdown2Name": row[24 + municipal_offset].strip(),
                "vtdCode": str(row[28 + municipal_offset]).strip(),
            }


def florida_precinct_rows(path, *, include_recounts=False):
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            lowered = member.lower()
            if not lowered.endswith(".txt"):
                continue
            if not include_recounts and "recount" in lowered:
                continue
            text = archive.read(member).decode("utf-8-sig", errors="replace")
            for raw_row in csv.reader(io.StringIO(text), delimiter="\t"):
                if len(raw_row) < 19:
                    continue
                yield {
                    "countyCode": raw_row[0].strip(),
                    "county": title_county(raw_row[1].strip()),
                    "electionNumber": raw_row[2].strip(),
                    "electionDate": raw_row[3].strip(),
                    "electionName": raw_row[4].strip(),
                    "precinctId": raw_row[5].strip(),
                    "precinct": raw_row[6].strip(),
                    "registeredVoters": int_text(raw_row[7]),
                    "registeredRepublicans": int_text(raw_row[8]),
                    "registeredDemocrats": int_text(raw_row[9]),
                    "registeredOther": int_text(raw_row[10]),
                    "contest": raw_row[11].strip(),
                    "district": raw_row[12].strip(),
                    "contestCode": raw_row[13].strip(),
                    "candidate": raw_row[14].strip(),
                    "party": raw_row[15].strip(),
                    "candidateId": raw_row[16].strip(),
                    "candidateNumber": raw_row[17].strip(),
                    "votes": int_text(raw_row[18]),
                }


def florida_contest_matches(row, contest_name):
    return normalize_party(row["contest"]) == normalize_party(contest_name)


def florida_excluded_candidate(row, config_section):
    candidate = row["candidate"]
    return any(re.search(pattern, candidate, flags=re.IGNORECASE) for pattern in config_section.get("excludeCandidatePatterns", []))


def legacy_xls_workbooks(paths, *, all_sheets=False):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        manifest_path = Path(handle.name)
        json.dump(
            [{"id": path.name, "path": str(path), "allSheets": all_sheets} for path in paths],
            handle,
        )
    try:
        completed = subprocess.run(
            ["node", "scripts/read-legacy-xls.mjs", "--manifest", str(manifest_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)["workbooks"]
    finally:
        manifest_path.unlink(missing_ok=True)


def legacy_xls_workbooks_from_zip(path, *, all_sheets=False):
    with tempfile.TemporaryDirectory(prefix="state-xls-") as temp_dir:
        temp_root = Path(temp_dir)
        extracted = []
        with zipfile.ZipFile(path) as archive:
            for member in sorted(archive.namelist()):
                if not member.lower().endswith((".xls", ".xlsx")):
                    continue
                output = temp_root / Path(member).name
                output.write_bytes(archive.read(member))
                extracted.append(output)
        return legacy_xls_workbooks(extracted, all_sheets=all_sheets)


def alabama_county_from_workbook(workbook):
    raw = Path(workbook["id"]).stem
    raw = re.sub(r"^\d{4}-General-", "", raw, flags=re.IGNORECASE)
    return alabama_county_name(raw)


def alabama_precinct_columns(header):
    return [
        (index, str(name).strip())
        for index, name in enumerate(header)
        if index >= 3 and str(name or "").strip() and str(name or "").strip().upper() not in {"TOTAL", "TOTALS"}
    ]


def alabama_excluded_candidate(candidate, config_section):
    return any(re.search(pattern, candidate, flags=re.IGNORECASE) for pattern in config_section.get("excludeCandidatePatterns", []))


def alabama_precinct_zip_workbooks(config_section, config, *, all_sheets=False):
    return legacy_xls_workbooks_from_zip(local_source(config, config_section["sourceId"]), all_sheets=all_sheets)


def certified_results_alabama_precinct_zip(config):
    source = config["certifiedResults"]
    by_county = defaultdict(lambda: defaultdict(int))
    precinct_keys = set()
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]

    for workbook in alabama_precinct_zip_workbooks(source, config):
        county = alabama_county_from_workbook(workbook)
        rows = workbook["rows"]
        if not rows:
            continue
        columns = alabama_precinct_columns(rows[0])
        for row in rows[1:]:
            contest = str(row[0] if len(row) > 0 else "").strip()
            if contest.upper() != source["contestName"].upper():
                continue
            party = str(row[1] if len(row) > 1 else "").strip()
            candidate = str(row[2] if len(row) > 2 else "").strip()
            if alabama_excluded_candidate(candidate, source):
                continue
            row_votes = sum(int_text(row[index] if index < len(row) else 0) for index, _name in columns)
            if row_votes <= 0:
                continue
            for index, precinct in columns:
                votes = int_text(row[index] if index < len(row) else 0)
                if votes:
                    precinct_keys.add((county, precinct))
            candidate_row = {"party": party, "candidate": candidate}
            if candidate_matches(candidate_row, source["majorCandidates"]["trump"]):
                by_county[county]["trump"] += row_votes
            elif candidate_matches(candidate_row, source["majorCandidates"]["harris"]):
                by_county[county]["harris"] += row_votes
            else:
                matched_other = False
                for candidate_rule in source.get("otherCandidates", []):
                    if candidate_matches(candidate_row, candidate_rule):
                        by_county[county][candidate_rule["key"]] += row_votes
                        matched_other = True
                        break
                if not matched_other:
                    by_county[county]["unmappedOther"] += row_votes

    result_rows = []
    for county, totals in sorted(by_county.items()):
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )
    return result_rows, candidate_labels, len(precinct_keys)


def is_xlsx_file(path):
    with path.open("rb") as handle:
        return handle.read(2) == b"PK"


def north_dakota_xlsx_historical_rows(path):
    sheet_name = first_worksheet_name(path)
    rows = iter_worksheet_rows(path, sheet_name)
    header = None
    for row in rows:
        if "County" in row:
            header = row
            break
    if not header:
        raise ValueError(f"Could not find County header in {path}")
    county_index = header.index("County")
    candidate_columns = [
        (index, str(name or ""))
        for index, name in enumerate(header)
        if index > county_index and name not in (None, "Number of Precincts")
    ]
    by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
    for row in rows:
        if len(row) <= county_index or not row[county_index]:
            continue
        county = str(row[county_index]).strip()
        if county.lower() in ("total", "totals", "statewide", "state of north dakota"):
            continue
        for index, header_text in candidate_columns:
            votes = int_text(row[index] if index < len(row) else 0)
            header_lower = header_text.lower()
            by_county[county]["total"] += votes
            if "democratic" in header_lower:
                by_county[county]["dem"] += votes
            elif "republican" in header_lower:
                by_county[county]["rep"] += votes
            else:
                by_county[county]["other"] += votes
    return by_county


def candidate_matches(row, rule):
    if rule.get("partyCode") and normalize_party(row["party"]) != normalize_party(rule["partyCode"]):
        return False
    if rule.get("candidateContains") and rule["candidateContains"].lower() not in row["candidate"].lower():
        return False
    return True


def normalize_party(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def certified_results_north_dakota_csv(config):
    source = config["certifiedResults"]
    rows = [
        row
        for row in north_dakota_export_rows(local_source(config, source["sourceId"]))
        if row["contest"] == source["contestName"]
    ]
    by_county = defaultdict(lambda: defaultdict(int))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    for row in rows:
        county = row["county"]
        if candidate_matches(row, source["majorCandidates"]["trump"]):
            by_county[county]["trump"] += row["votes"]
        elif candidate_matches(row, source["majorCandidates"]["harris"]):
            by_county[county]["harris"] += row["votes"]
        else:
            matched_other = False
            for candidate in source.get("otherCandidates", []):
                if candidate_matches(row, candidate):
                    by_county[county][candidate["key"]] += row["votes"]
                    matched_other = True
                    break
            if not matched_other:
                by_county[county]["unmappedOther"] += row["votes"]
        if "/" in row["precinctsReporting"]:
            by_county[county]["precinctRows"] = max(by_county[county]["precinctRows"], int_text(row["precinctsReporting"].split("/")[-1]))

    result_rows = []
    for county, totals in sorted(by_county.items()):
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )
    precinct_rows = sum(totals["precinctRows"] for totals in by_county.values())
    return result_rows, candidate_labels, precinct_rows


def certified_results_pennsylvania_bulk_csv(config):
    source = config["certifiedResults"]
    office_code = source.get("officeCode", "USP")
    by_county = defaultdict(lambda: defaultdict(int))
    precinct_keys = set()
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]

    for row in pennsylvania_bulk_rows(local_source(config, source["sourceId"])):
        if row["officeCode"] != office_code:
            continue
        county = row["county"]
        precinct_keys.add(pennsylvania_precinct_key(row, source.get("precinctKeyFields")))
        if candidate_matches(row, source["majorCandidates"]["trump"]):
            by_county[county]["trump"] += row["votes"]
        elif candidate_matches(row, source["majorCandidates"]["harris"]):
            by_county[county]["harris"] += row["votes"]
        else:
            matched_other = False
            for candidate in source.get("otherCandidates", []):
                if candidate_matches(row, candidate):
                    by_county[county][candidate["key"]] += row["votes"]
                    matched_other = True
                    break
            if not matched_other:
                by_county[county]["unmappedOther"] += row["votes"]

    result_rows = []
    for county, totals in sorted(by_county.items()):
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )
    return result_rows, candidate_labels, len(precinct_keys)


def certified_results_florida_precinct_zip(config):
    source = config["certifiedResults"]
    by_county = defaultdict(lambda: defaultdict(int))
    precinct_keys = set()
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]

    for row in florida_precinct_rows(local_source(config, source["sourceId"])):
        if not florida_contest_matches(row, source["contestName"]):
            continue
        precinct_keys.add((row["countyCode"], row["precinctId"]))
        if florida_excluded_candidate(row, source):
            continue
        county = row["county"]
        if candidate_matches(row, source["majorCandidates"]["trump"]):
            by_county[county]["trump"] += row["votes"]
        elif candidate_matches(row, source["majorCandidates"]["harris"]):
            by_county[county]["harris"] += row["votes"]
        else:
            matched_other = False
            for candidate in source.get("otherCandidates", []):
                if candidate_matches(row, candidate):
                    by_county[county][candidate["key"]] += row["votes"]
                    matched_other = True
                    break
            if not matched_other:
                by_county[county]["unmappedOther"] += row["votes"]

    result_rows = []
    for county, totals in sorted(by_county.items()):
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )
    return result_rows, candidate_labels, len(precinct_keys)


def certified_results_michigan_tab(config):
    source = config["certifiedResults"]
    rows = [
        row
        for row in michigan_result_rows(local_source(config, source["sourceId"]))
        if row["contest"] == source["contestName"]
    ]
    by_county = defaultdict(lambda: defaultdict(int))
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    for row in rows:
        county = row["county"]
        if candidate_matches(row, source["majorCandidates"]["trump"]):
            by_county[county]["trump"] += row["votes"]
        elif candidate_matches(row, source["majorCandidates"]["harris"]):
            by_county[county]["harris"] += row["votes"]
        else:
            matched_other = False
            for candidate in source.get("otherCandidates", []):
                if candidate_matches(row, candidate):
                    by_county[county][candidate["key"]] += row["votes"]
                    matched_other = True
                    break
            if not matched_other:
                by_county[county]["unmappedOther"] += row["votes"]

    result_rows = []
    for county, totals in sorted(by_county.items()):
        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
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
                **{item["key"]: totals[item["key"]] for item in candidate_labels},
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )
    return result_rows, candidate_labels, len(result_rows)


def review_charts(config):
    review = config["reviewCharts"]
    parser = parser_for(REVIEW_CHART_PARSERS, review.get("format", "xlsxPrecinctComparison"), "review charts")
    return parser(config)


def review_charts_not_configured(config):
    policy = {
        "outlierThresholdPct": 15,
        "minCandidateVotes": 100,
        "voteShareCorrelationThreshold": 0.35,
        **config["reviewCharts"].get("policy", {}),
    }
    return [], eta_analysis_from_review_rows([], policy, 0, 0)


def review_charts_xlsx_precinct_comparison(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    columns = review["columns"]
    column_index, rows = read_sheet_rows(path, review["sheet"])
    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0

    for row in rows:
        if row[0] == "End of worksheet":
            break
        county = row[column_index[columns["county"]]]
        if not county:
            continue
        trump = int_cell(row, column_index, columns["trump"])
        harris = int_cell(row, column_index, columns["harris"])
        president_total = int_cell(row, column_index, columns["presidentTotal"])
        senate_rep = int_cell(row, column_index, columns["senateR"])
        senate_dem = int_cell(row, column_index, columns["senateDem"])
        senate_rep_total += senate_rep
        senate_dem_total += senate_dem
        if not president_total:
            continue
        review_rows.append(
            {
                "county": county,
                "ward": row_label(row, column_index, review["rowLabelColumns"]),
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    policy = review["policy"]
    harris_total = sum(row["harris"] for row in review_rows)
    trump_total = sum(row["trump"] for row in review_rows)
    dem_drop_votes = harris_total - senate_dem_total
    rep_drop_votes = trump_total - senate_rep_total
    dem_outliers = sum(
        1
        for row in review_rows
        if row["harris"] >= policy["minCandidateVotes"]
        and abs(row["demDropoff"]) >= policy["outlierThresholdPct"]
    )
    rep_outliers = sum(
        1
        for row in review_rows
        if row["trump"] >= policy["minCandidateVotes"]
        and abs(row["repDropoff"]) >= policy["outlierThresholdPct"]
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
            "outlierThresholdPct": policy["outlierThresholdPct"],
            "minCandidateVotes": policy["minCandidateVotes"],
        },
        "voteShare": {
            "trumpCorrelation": round(
                pearson([row["trump"] for row in review_rows], [row["trumpShare"] for row in review_rows]),
                4,
            ),
            "harrisCorrelation": round(
                pearson([row["harris"] for row in review_rows], [row["harrisShare"] for row in review_rows]),
                4,
            ),
            "threshold": policy["voteShareCorrelationThreshold"],
        },
    }
    return review_rows, eta_analysis


def contest_party_votes(rows, contest_name):
    by_county = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if row["contest"] == contest_name:
            by_county[row["county"]][row["party"]] += row["votes"]
    return by_county


def eta_analysis_from_review_rows(review_rows, policy, senate_dem_total, senate_rep_total):
    harris_total = sum(row["harris"] for row in review_rows)
    trump_total = sum(row["trump"] for row in review_rows)
    dem_drop_votes = harris_total - senate_dem_total
    rep_drop_votes = trump_total - senate_rep_total
    return {
        "wardRows": len(review_rows),
        "downBallot": {
            "demDropVotes": dem_drop_votes,
            "demDropPct": round2((dem_drop_votes / harris_total) * 100) if harris_total else 0,
            "repDropVotes": rep_drop_votes,
            "repDropPct": round2((rep_drop_votes / trump_total) * 100) if trump_total else 0,
            "demOutlierWards": sum(
                1
                for row in review_rows
                if row["harris"] >= policy["minCandidateVotes"]
                and abs(row["demDropoff"]) >= policy["outlierThresholdPct"]
            ),
            "repOutlierWards": sum(
                1
                for row in review_rows
                if row["trump"] >= policy["minCandidateVotes"]
                and abs(row["repDropoff"]) >= policy["outlierThresholdPct"]
            ),
            "outlierThresholdPct": policy["outlierThresholdPct"],
            "minCandidateVotes": policy["minCandidateVotes"],
        },
        "voteShare": {
            "trumpCorrelation": round(
                pearson([row["trump"] for row in review_rows], [row["trumpShare"] for row in review_rows]),
                4,
            ),
            "harrisCorrelation": round(
                pearson([row["harris"] for row in review_rows], [row["harrisShare"] for row in review_rows]),
                4,
            ),
            "threshold": policy["voteShareCorrelationThreshold"],
        },
    }


def normalize_zip_value(value, normalizer=None):
    text = str(value or "").strip()
    if normalizer == "michiganCountyName":
        return michigan_county_name(text)
    if normalizer == "titleCase":
        return title_county(text)
    return text


def tab_rows_from_zip(archive, table_config):
    text = archive.read(table_config["path"]).decode(table_config.get("encoding", "utf-8-sig"))
    delimiter = table_config.get("delimiter", "\t")
    columns = table_config["columns"]
    normalizers = table_config.get("normalizers", {})
    minimum_columns = max(columns.values()) + 1
    required_digit_column = table_config.get("requireDigitColumn")
    for raw_row in csv.reader(io.StringIO(text), delimiter=delimiter):
        if len(raw_row) < minimum_columns:
            continue
        if required_digit_column and not raw_row[columns[required_digit_column]].strip().isdigit():
            continue
        yield {
            key: normalize_zip_value(raw_row[index], normalizers.get(key))
            for key, index in columns.items()
        }


def zip_key(row, fields):
    return tuple(row.get(field, "") for field in fields)


def zip_lookup(archive, table_config):
    key_fields = table_config["keyFields"]
    value_fields = table_config["valueFields"]
    lookup = {}
    for row in tab_rows_from_zip(archive, table_config):
        values = {field: row.get(field, "") for field in value_fields}
        lookup[zip_key(row, key_fields)] = values[value_fields[0]] if len(value_fields) == 1 else values
    return lookup


def configured_zip_key(rule, fields):
    return tuple(str(rule[field]) for field in fields)


def row_label_part(item, part):
    value = item.get(part["field"], "")
    if value in part.get("omitValues", []):
        return ""
    if part.get("integer") and value:
        value = str(int_text(value))
    if not value and not part.get("showWhenBlank", False):
        return ""
    text = f"{part.get('prefix', '')}{value}{part.get('suffix', '')}"
    append_value = item.get(part.get("appendField", ""), "")
    if append_value:
        text = f"{text}{part.get('appendSeparator', ' ')}{append_value}"
    return text


def zip_review_row_label(item, label_config):
    parts = [row_label_part(item, part) for part in label_config["parts"]]
    parts = [part for part in parts if part]
    return label_config.get("separator", " - ").join(parts) or label_config.get("fallback", "Unnamed reporting unit")


def review_charts_tab_delimited_zip(config):
    review = config["reviewCharts"]
    tables = review["zipTables"]
    contest_key_fields = review.get("contestKeyFields", ["officeCode", "districtCode", "statusCode"])
    candidate_key_fields = review.get(
        "candidateKeyFields",
        [*contest_key_fields, "candidateCode"],
    )
    reporting_unit_key_fields = review.get(
        "reportingUnitKeyFields",
        ["countyCode", "municipalityCode", "wardCode", "precinctCode", "precinctLabel"],
    )
    president_key = configured_zip_key(review["presidentContest"], contest_key_fields)
    down_ballot_key = configured_zip_key(review["downBallotContest"], contest_key_fields)
    party_codes = review["partyCodes"]
    precincts = defaultdict(lambda: defaultdict(int))
    senate_dem_total = 0
    senate_rep_total = 0

    with zipfile.ZipFile(local_source(config, review["sourceId"])) as archive:
        counties = zip_lookup(archive, tables["countyLookup"]) if "countyLookup" in tables else {}
        municipalities = zip_lookup(archive, tables["municipalityLookup"]) if "municipalityLookup" in tables else {}
        candidates = zip_lookup(archive, tables["candidateLookup"])

        for row in tab_rows_from_zip(archive, tables["votes"]):
            office_key = zip_key(row, contest_key_fields)
            if office_key not in (president_key, down_ballot_key):
                continue
            candidate_key = zip_key(row, candidate_key_fields)
            party = candidates.get(candidate_key)
            votes = int_text(row["votes"])
            row_key = zip_key(row, reporting_unit_key_fields)
            item = precincts[row_key]
            county_code = row.get("countyCode", "")
            municipality_code = row.get("municipalityCode", "")
            item["county"] = counties.get((county_code,), f"County {county_code}")
            item["municipality"] = municipalities.get(
                (county_code, municipality_code),
                f"Municipality {municipality_code}",
            )
            for field in reporting_unit_key_fields:
                item[field] = row.get(field, "")
            if office_key == president_key:
                item["president_total"] += votes
                if party == party_codes["dem"]:
                    item["harris"] += votes
                elif party == party_codes["rep"]:
                    item["trump"] += votes
            elif office_key == down_ballot_key:
                if party == party_codes["dem"]:
                    item["senate_dem"] += votes
                    senate_dem_total += votes
                elif party == party_codes["rep"]:
                    item["senate_rep"] += votes
                    senate_rep_total += votes

    review_rows = []
    for _key, item in sorted(
        precincts.items(),
        key=lambda pair: (
            pair[1]["county"],
            pair[1]["municipality"],
            int_text(pair[1].get("wardCode", "")),
            int_text(pair[1].get("precinctCode", "")),
            pair[1].get("precinctLabel", ""),
        ),
    ):
        president_total = item["president_total"]
        if not president_total:
            continue
        harris = item["harris"]
        trump = item["trump"]
        senate_dem = item["senate_dem"]
        senate_rep = item["senate_rep"]
        review_rows.append(
            {
                "county": item["county"],
                "ward": zip_review_row_label(item, review["rowLabel"]),
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        senate_dem_total,
        senate_rep_total,
    )


def review_charts_north_dakota_csv(config):
    review = config["reviewCharts"]
    rows = list(north_dakota_export_rows(local_source(config, review["sourceId"])))
    president = contest_party_votes(rows, review["presidentContestName"])
    down_ballot = contest_party_votes(rows, review["downBallotContestName"])
    review_rows = []
    for county in sorted(president):
        trump = president[county][review["partyCodes"]["rep"]]
        harris = president[county][review["partyCodes"]["dem"]]
        president_total = sum(president[county].values())
        senate_rep = down_ballot[county][review["partyCodes"]["rep"]]
        senate_dem = down_ballot[county][review["partyCodes"]["dem"]]
        if not president_total:
            continue
        review_rows.append(
            {
                "county": county,
                "ward": f"{county} County",
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )
    policy = review["policy"]
    eta_analysis = {
        "wardRows": len(review_rows),
        "downBallot": {
            "demDropVotes": sum(row["harris"] for row in review_rows) - sum(down_ballot[county][review["partyCodes"]["dem"]] for county in president),
            "demDropPct": round2(average(row["demDropoff"] for row in review_rows)),
            "repDropVotes": sum(row["trump"] for row in review_rows) - sum(down_ballot[county][review["partyCodes"]["rep"]] for county in president),
            "repDropPct": round2(average(row["repDropoff"] for row in review_rows)),
            "demOutlierWards": sum(1 for row in review_rows if abs(row["demDropoff"]) >= policy["outlierThresholdPct"] and row["harris"] >= policy["minCandidateVotes"]),
            "repOutlierWards": sum(1 for row in review_rows if abs(row["repDropoff"]) >= policy["outlierThresholdPct"] and row["trump"] >= policy["minCandidateVotes"]),
            "outlierThresholdPct": policy["outlierThresholdPct"],
            "minCandidateVotes": policy["minCandidateVotes"],
        },
        "voteShare": {
            "trumpCorrelation": round(pearson([row["trump"] for row in review_rows], [row["trumpShare"] for row in review_rows]), 4),
            "harrisCorrelation": round(pearson([row["harris"] for row in review_rows], [row["harrisShare"] for row in review_rows]), 4),
            "threshold": policy["voteShareCorrelationThreshold"],
        },
    }
    return review_rows, eta_analysis


def review_charts_michigan_tab(config):
    review = config["reviewCharts"]
    rows = list(michigan_result_rows(local_source(config, review["sourceId"])))
    president = contest_party_votes(rows, review["presidentContestName"])
    down_ballot = contest_party_votes(rows, review["downBallotContestName"])
    review_rows = []
    for county in sorted(president):
        trump = president[county][review["partyCodes"]["rep"]]
        harris = president[county][review["partyCodes"]["dem"]]
        president_total = sum(president[county].values())
        senate_rep = down_ballot[county][review["partyCodes"]["rep"]]
        senate_dem = down_ballot[county][review["partyCodes"]["dem"]]
        if not president_total:
            continue
        review_rows.append(
            {
                "county": county,
                "ward": f"{county} County",
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )
    policy = review["policy"]
    eta_analysis = {
        "wardRows": len(review_rows),
        "downBallot": {
            "demDropVotes": sum(row["harris"] for row in review_rows) - sum(down_ballot[county][review["partyCodes"]["dem"]] for county in president),
            "demDropPct": round2(average(row["demDropoff"] for row in review_rows)),
            "repDropVotes": sum(row["trump"] for row in review_rows) - sum(down_ballot[county][review["partyCodes"]["rep"]] for county in president),
            "repDropPct": round2(average(row["repDropoff"] for row in review_rows)),
            "demOutlierWards": sum(1 for row in review_rows if abs(row["demDropoff"]) >= policy["outlierThresholdPct"] and row["harris"] >= policy["minCandidateVotes"]),
            "repOutlierWards": sum(1 for row in review_rows if abs(row["repDropoff"]) >= policy["outlierThresholdPct"] and row["trump"] >= policy["minCandidateVotes"]),
            "outlierThresholdPct": policy["outlierThresholdPct"],
            "minCandidateVotes": policy["minCandidateVotes"],
        },
        "voteShare": {
            "trumpCorrelation": round(pearson([row["trump"] for row in review_rows], [row["trumpShare"] for row in review_rows]), 4),
            "harrisCorrelation": round(pearson([row["harris"] for row in review_rows], [row["harrisShare"] for row in review_rows]), 4),
            "threshold": policy["voteShareCorrelationThreshold"],
        },
    }
    return review_rows, eta_analysis


def review_charts_pennsylvania_bulk_csv(config):
    review = config["reviewCharts"]
    president_office = review.get("presidentOfficeCode", "USP")
    down_ballot_office = review.get("downBallotOfficeCode", "USS")
    party_codes = review["partyCodes"]
    precincts = defaultdict(lambda: defaultdict(int))
    senate_dem_total = 0
    senate_rep_total = 0

    for row in pennsylvania_bulk_rows(local_source(config, review["sourceId"])):
        office = row["officeCode"]
        if office not in (president_office, down_ballot_office):
            continue
        key = pennsylvania_precinct_key(row, review.get("precinctKeyFields"))
        item = precincts[key]
        item["county"] = row["county"]
        item["ward"] = pennsylvania_precinct_label(row)
        votes = row["votes"]
        party = normalize_party(row["party"])
        if office == president_office:
            item["president_total"] += votes
            if party == normalize_party(party_codes["dem"]):
                item["harris"] += votes
            elif party == normalize_party(party_codes["rep"]):
                item["trump"] += votes
        elif office == down_ballot_office:
            if party == normalize_party(party_codes["dem"]):
                item["senate_dem"] += votes
                senate_dem_total += votes
            elif party == normalize_party(party_codes["rep"]):
                item["senate_rep"] += votes
                senate_rep_total += votes

    review_rows = []
    for _key, item in sorted(precincts.items(), key=lambda pair: (pair[1]["county"], pair[1]["ward"])):
        president_total = item["president_total"]
        if not president_total:
            continue
        harris = item["harris"]
        trump = item["trump"]
        senate_dem = item["senate_dem"]
        senate_rep = item["senate_rep"]
        review_rows.append(
            {
                "county": item["county"],
                "ward": item["ward"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        senate_dem_total,
        senate_rep_total,
    )


def review_charts_florida_precinct_zip(config):
    review = config["reviewCharts"]
    precincts = defaultdict(lambda: defaultdict(int))
    senate_dem_total = 0
    senate_rep_total = 0

    for row in florida_precinct_rows(local_source(config, review["sourceId"])):
        is_president = florida_contest_matches(row, review["presidentContestName"])
        is_down_ballot = florida_contest_matches(row, review["downBallotContestName"])
        if not is_president and not is_down_ballot:
            continue
        key = (row["countyCode"], row["precinctId"])
        item = precincts[key]
        item["county"] = row["county"]
        item["ward"] = f"{row['precinctId']} {row['precinct']}".strip()
        if is_president:
            item["president_total"] += row["votes"]
            if florida_excluded_candidate(row, review):
                continue
            if candidate_matches(row, review["majorCandidates"]["trump"]):
                item["trump"] += row["votes"]
            elif candidate_matches(row, review["majorCandidates"]["harris"]):
                item["harris"] += row["votes"]
        elif is_down_ballot:
            if row["party"] == review["partyCodes"]["dem"]:
                item["senate_dem"] += row["votes"]
                senate_dem_total += row["votes"]
            elif row["party"] == review["partyCodes"]["rep"]:
                item["senate_rep"] += row["votes"]
                senate_rep_total += row["votes"]

    review_rows = []
    for _key, item in sorted(precincts.items(), key=lambda pair: (pair[1]["county"], pair[1]["ward"])):
        president_total = item["president_total"]
        if not president_total:
            continue
        harris = item["harris"]
        trump = item["trump"]
        senate_dem = item["senate_dem"]
        senate_rep = item["senate_rep"]
        review_rows.append(
            {
                "county": item["county"],
                "ward": item["ward"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        senate_dem_total,
        senate_rep_total,
    )


def review_charts_alabama_precinct_zip(config):
    review = config["reviewCharts"]
    party_codes = review["partyCodes"]
    precincts = defaultdict(lambda: defaultdict(int))
    house_dem_total = 0
    house_rep_total = 0

    for workbook in alabama_precinct_zip_workbooks(review, config):
        county = alabama_county_from_workbook(workbook)
        rows = workbook["rows"]
        if not rows:
            continue
        columns = alabama_precinct_columns(rows[0])
        for row in rows[1:]:
            contest = str(row[0] if len(row) > 0 else "").strip()
            party = normalize_party(row[1] if len(row) > 1 else "")
            candidate = str(row[2] if len(row) > 2 else "").strip()
            is_president = contest.upper() == review["presidentContestName"].upper()
            is_down_ballot = contest.upper().startswith(review["downBallotContestStartsWith"].upper())
            if not is_president and not is_down_ballot:
                continue
            if is_president and alabama_excluded_candidate(candidate, review):
                continue
            for index, precinct in columns:
                votes = int_text(row[index] if index < len(row) else 0)
                item = precincts[(county, precinct)]
                item["county"] = county
                item["ward"] = precinct
                if is_president:
                    item["president_total"] += votes
                    if party == normalize_party(party_codes["dem"]):
                        item["harris"] += votes
                    elif party == normalize_party(party_codes["rep"]):
                        item["trump"] += votes
                elif is_down_ballot:
                    if party == normalize_party(party_codes["dem"]):
                        item["house_dem"] += votes
                        house_dem_total += votes
                    elif party == normalize_party(party_codes["rep"]):
                        item["house_rep"] += votes
                        house_rep_total += votes

    review_rows = []
    for _key, item in sorted(precincts.items(), key=lambda pair: (pair[1]["county"], pair[1]["ward"])):
        president_total = item["president_total"]
        if not president_total:
            continue
        harris = item["harris"]
        trump = item["trump"]
        house_dem = item["house_dem"]
        house_rep = item["house_rep"]
        review_rows.append(
            {
                "county": item["county"],
                "ward": item["ward"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )


def turnout_data(config):
    turnout = config["turnout"]
    parser = parser_for(TURNOUT_PARSERS, turnout.get("format", "xlsxPrecinctRows"), "turnout")
    return parser(config)


def turnout_data_not_configured(config):
    turnout = config["turnout"]
    return {
        "metadata": {
            "rows": 0,
            "warningRows": 0,
            "source": "",
            "sourceUrl": "",
            "warning": turnout.get("notes", "Turnout rows are not loaded for this state yet."),
        },
        "rows": [],
    }


def turnout_data_xlsx_precinct_rows(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    columns = turnout["columns"]
    column_index, rows = read_sheet_rows(path, turnout["sheet"])
    output_rows = []

    for row in rows:
        if row[0] == "End of worksheet":
            break
        county = row[column_index[columns["county"]]]
        if not county:
            continue
        registered = int_cell(row, column_index, columns["registered7Am"]) + int_cell(
            row,
            column_index,
            columns["electionDayRegistrations"],
        )
        ballots = int_cell(row, column_index, columns["ballotsCast"])
        output_rows.append(
            {
                "county": county,
                "municipality": row[column_index[columns["municipality"]]] or "Unknown municipality",
                "ward": row_label(row, column_index, turnout["rowLabelColumns"]),
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": source_map(config)[turnout["sourceId"]]["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": local_source(config, turnout["sourceId"]).name,
            "sourceUrl": source_map(config)[turnout["sourceId"]]["url"],
        },
        "rows": output_rows,
    }


def turnout_data_michigan_mvic(config):
    turnout = config["turnout"]
    turnout_source = source_map(config)[turnout["sourceId"]]
    registration_source = source_map(config)[turnout["registrationSourceId"]]
    voters_by_county = {}
    with local_source(config, turnout["sourceId"]).open("r", encoding="utf-8-sig", newline="") as handle:
        first = handle.readline()
        if not first.startswith("TOTAL VOTER TURNOUT:"):
            handle.seek(0)
        for row in csv.DictReader(handle, delimiter="\t"):
            if not re.match(r"^\d+$", row.get("County Code", "")):
                continue
            county = michigan_county_name(row["County Name"])
            voters_by_county[county] = int_text(row["County Voters"])

    registration_by_county = michigan_registration_totals_from_pdf(local_source(config, turnout["registrationSourceId"]))
    missing_registration = sorted(set(voters_by_county) - set(registration_by_county))
    if missing_registration:
        raise ValueError(f"Michigan turnout registration rows missing for: {', '.join(missing_registration)}")

    output_rows = []
    for county, ballots in sorted(voters_by_county.items()):
        registration = registration_by_county[county]
        registered = registration[turnout.get("denominatorField", "novemberActiveRegisteredVoters")]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": f"{county} County",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": f"{turnout_source['url']} ; {registration_source['url']}",
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": f"{local_source(config, turnout['sourceId']).name}; {local_source(config, turnout['registrationSourceId']).name}",
            "sourceUrl": f"{turnout_source['url']} ; {registration_source['url']}",
        },
        "rows": output_rows,
    }


def extract_pdf_text(path):
    completed = subprocess.run(
        ["node", "scripts/extract-pdf-text.mjs", str(path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def michigan_registration_totals_from_pdf(path):
    rows = {}
    pending_county = None
    pending_numbers = []
    orphan_numbers = []
    for raw_line in extract_pdf_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("2024 ") or line in {"May August November", "Active All Active All Active All"}:
            continue
        if line.startswith("County ") or line.startswith("Voters ") or line.startswith("* "):
            continue
        if line.startswith("Total*"):
            continue
        numbers = re.findall(r"\d[\d,]*", line)
        if not numbers:
            continue
        county_part = "" if re.match(r"^\d", line) else re.sub(r"\s+\d[\d,\s]*$", "", line).strip()
        if county_part:
            if pending_county and len(pending_numbers) != 6:
                raise ValueError(f"Incomplete Michigan registration row for {pending_county}: {pending_numbers}")
            pending_county = michigan_county_name(county_part)
            pending_numbers = orphan_numbers + [int_text(value) for value in numbers]
            orphan_numbers = []
        elif pending_county:
            pending_numbers.extend(int_text(value) for value in numbers)
        else:
            orphan_numbers = [int_text(value) for value in numbers]

        if pending_county and len(pending_numbers) >= 6:
            if len(pending_numbers) != 6:
                raise ValueError(f"Unexpected Michigan registration row for {pending_county}: {pending_numbers}")
            rows[pending_county] = {
                "mayActiveRegisteredVoters": pending_numbers[0],
                "mayAllRegisteredVoters": pending_numbers[1],
                "augustActiveRegisteredVoters": pending_numbers[2],
                "augustAllRegisteredVoters": pending_numbers[3],
                "novemberActiveRegisteredVoters": pending_numbers[4],
                "novemberAllRegisteredVoters": pending_numbers[5],
            }
            pending_county = None
            pending_numbers = []
    if pending_county:
        raise ValueError(f"Incomplete Michigan registration row for {pending_county}: {pending_numbers}")
    return rows


def turnout_data_north_dakota_html(config):
    turnout = config["turnout"]
    text = local_source(config, turnout["sourceId"]).read_text(encoding="utf-8", errors="replace")
    output_rows = []
    for chunk in text.split('<div class="wrapper-turnout">')[1:]:
        name_match = re.search(r"<h1>([^<]+)</h1>", chunk)
        pct_match = re.search(r'<div class="dough-inner"><span class="int">(\d+)</span><span class="dec">([^<]+)</span>', chunk)
        if not name_match or not pct_match:
            continue
        county = html.unescape(name_match.group(1)).strip()
        turnout_pct = float(f"{pct_match.group(1)}{pct_match.group(2).replace('%', '')}")
        precinct_cast = [int_text(value) for value in re.findall(r'<div class="county-cast [^"]+">([0-9,]+)</div>', chunk)]
        ballots = sum(precinct_cast)
        registered = round(ballots / (turnout_pct / 100)) if turnout_pct else 0
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": f"{county} County",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2(turnout_pct),
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": source_map(config)[turnout["sourceId"]]["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": local_source(config, turnout["sourceId"]).name,
            "sourceUrl": source_map(config)[turnout["sourceId"]]["url"],
        },
        "rows": output_rows,
    }


def turnout_data_pennsylvania_vote_history_xlsx(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    columns = turnout.get(
        "columns",
        {
            "county": "County",
            "ballotsCast": "Vote History",
            "registeredVoters": "Registered voters",
        },
    )
    column_index, rows = read_sheet_rows(path, turnout.get("sheet", "By county"))
    output_rows = []

    for row in rows:
        county_raw = str(row[column_index[columns["county"]]] or "").strip()
        if not county_raw or county_raw.upper() == "TOTAL":
            continue
        county = title_county(county_raw)
        ballots = int_text(row[column_index[columns["ballotsCast"]]])
        registered = int_text(row[column_index[columns["registeredVoters"]]])
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": f"{county} County",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": source_map(config)[turnout["sourceId"]]["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": local_source(config, turnout["sourceId"]).name,
            "sourceUrl": source_map(config)[turnout["sourceId"]]["url"],
        },
        "rows": output_rows,
    }


def turnout_data_florida_precinct_zip(config):
    turnout = config["turnout"]
    precincts = defaultdict(lambda: defaultdict(int))
    source = source_map(config)[turnout["sourceId"]]
    for row in florida_precinct_rows(local_source(config, turnout["sourceId"])):
        if not florida_contest_matches(row, turnout["contestName"]):
            continue
        key = (row["countyCode"], row["precinctId"])
        item = precincts[key]
        item["county"] = row["county"]
        item["ward"] = f"{row['precinctId']} {row['precinct']}".strip()
        item["registeredVoters"] = max(item["registeredVoters"], row["registeredVoters"])
        item["ballotsCast"] += row["votes"]

    output_rows = []
    for _key, item in sorted(precincts.items(), key=lambda pair: (pair[1]["county"], pair[1]["ward"])):
        registered = item["registeredVoters"]
        ballots = item["ballotsCast"]
        output_rows.append(
            {
                "county": item["county"],
                "municipality": item["county"],
                "ward": item["ward"],
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": local_source(config, turnout["sourceId"]).name,
            "sourceUrl": source["url"],
        },
        "rows": output_rows,
    }


def alabama_registration_rows(path, turnout):
    rows = list(iter_worksheet_rows(path, turnout.get("registrationSheet", "December")))
    county_column = turnout.get("registrationCountyColumn", 0)
    registered_column = turnout.get("registeredVotersColumn", 1)
    output = {}
    for row in rows:
        if len(row) <= registered_column:
            continue
        county_raw = str(row[county_column] or "").strip()
        if not county_raw or county_raw.upper() == "TOTAL":
            continue
        registered = int_text(row[registered_column])
        if registered:
            output[alabama_county_name(county_raw)] = registered
    return output


def turnout_data_alabama_precinct_zip(config):
    turnout = config["turnout"]
    turnout_source = source_map(config)[turnout["sourceId"]]
    registration_source = source_map(config)[turnout["registrationSourceId"]]
    ballots_by_county = defaultdict(int)

    for workbook in alabama_precinct_zip_workbooks(turnout, config):
        county = alabama_county_from_workbook(workbook)
        rows = workbook["rows"]
        if not rows:
            continue
        columns = alabama_precinct_columns(rows[0])
        for row in rows[1:]:
            contest = str(row[0] if len(row) > 0 else "").strip()
            if contest.upper() != turnout["ballotsCastContestName"].upper():
                continue
            ballots_by_county[county] += sum(int_text(row[index] if index < len(row) else 0) for index, _name in columns)
            break

    registered_by_county = alabama_registration_rows(local_source(config, turnout["registrationSourceId"]), turnout)
    missing_registration = sorted(set(ballots_by_county) - set(registered_by_county))
    if missing_registration:
        raise ValueError(f"Alabama turnout registration rows missing for: {', '.join(missing_registration)}")

    output_rows = []
    for county, ballots in sorted(ballots_by_county.items()):
        registered = registered_by_county[county]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": f"{county} County",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": f"{turnout_source['url']} ; {registration_source['url']}",
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": f"{local_source(config, turnout['sourceId']).name}; {local_source(config, turnout['registrationSourceId']).name}",
            "sourceUrl": f"{turnout_source['url']} ; {registration_source['url']}",
        },
        "rows": output_rows,
    }


def county_code_name_map(config):
    geometry = config["geometry"]
    geojson = json.loads(local_source(config, geometry["sourceId"]).read_text(encoding="utf-8"))
    code_property = geometry["codeProperty"]
    name_property = geometry["nameProperty"]
    return {
        str(int(feature["properties"][code_property])): feature["properties"][name_property]
        for feature in geojson.get("features", [])
    }


def historical_baseline(config):
    historical = config["historicalBaseline"]
    if not historical.get("sources"):
        return {
            "metadata": {
                "purpose": f"{config['name']} historical presidential baseline is not configured yet.",
                "seriesCount": 0,
                "warning": "Historical rows are not loaded for this state yet.",
                "sources": [],
            },
            "series": [],
        }
    parser = parser_for(
        HISTORICAL_BASELINE_PARSERS,
        historical.get("format") or historical.get("rowMethod", "officialCountyResultText"),
        "historical baseline",
    )
    return parser(config)


def historical_baseline_official_county_result_text(config):
    historical = config["historicalBaseline"]
    county_names = county_code_name_map(config)
    series = []
    for item in historical["sources"]:
        source = source_map(config)[item["sourceId"]]
        by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
        with project_path(source["localFile"]).open("r", encoding="utf-8-sig", newline="") as handle:
            for fields in csv.reader(handle, delimiter=";"):
                if len(fields) < 16 or fields[4] != historical["contestName"]:
                    continue
                county_code = fields[1]
                county = county_names.get(county_code.lstrip("0"), county_code)
                party = fields[10]
                votes = int(fields[13] or 0)
                by_county[county]["total"] = int(fields[15] or 0)
                if party == historical["partyCodes"]["dem"]:
                    by_county[county]["dem"] += votes
                elif party == historical["partyCodes"]["rep"]:
                    by_county[county]["rep"] += votes
                else:
                    by_county[county]["other"] += votes

        rows = []
        for county, totals in sorted(by_county.items()):
            total = totals["total"] or totals["dem"] + totals["rep"] + totals["other"]
            rows.append(
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
            "dem": sum(row["dem"] for row in rows),
            "rep": sum(row["rep"] for row in rows),
            "other": sum(row["other"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "rowCount": len(rows),
        }
        series.append(
            {
                "id": f"{config['code'].lower()}-sos-native-{item['year']}-president",
                "electionYear": item["year"],
                "sourceId": f"{config['code'].lower()}-sos-{item['year']}-county-results",
                "sourceClass": "nativeOfficial",
                "sourceLevel": historical["sourceLevel"],
                "rowMethod": historical["rowMethod"],
                "rowCount": len(rows),
                "sourceUrl": source["url"],
                "localFile": source["localFile"],
                "sourceNote": item["note"],
                "statewide": statewide,
                "rows": rows,
            }
        )
    return {
        "metadata": {
            "purpose": f"Graph-ready {config['name']} presidential-election baseline using native official county rows.",
            "seriesCount": len(series),
            "warning": f"{config['name']} historical rows are native official county rows from each election year.",
            "sources": [
                {
                    "year": item["year"],
                    "localFile": source_map(config)[item["sourceId"]]["localFile"],
                    "sourceUrl": source_map(config)[item["sourceId"]]["url"],
                    "format": "semicolon-delimited President by County text",
                    "note": item["note"],
                }
                for item in historical["sources"]
            ],
        },
        "series": series,
    }


def historical_baseline_michigan_tab(config):
    historical = config["historicalBaseline"]
    series = []
    for item in historical["sources"]:
        source = source_map(config)[item["sourceId"]]
        by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
        for row in michigan_result_rows(project_path(source["localFile"])):
            if row["contest"] != item["contestName"]:
                continue
            party = normalize_party(row["party"])
            county = row["county"]
            votes = row["votes"]
            by_county[county]["total"] += votes
            if party == normalize_party(historical["partyCodes"]["dem"]):
                by_county[county]["dem"] += votes
            elif party == normalize_party(historical["partyCodes"]["rep"]):
                by_county[county]["rep"] += votes
            else:
                by_county[county]["other"] += votes

        rows = []
        for county, totals in sorted(by_county.items()):
            rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "reportingUnit": f"{county} County",
                    "ward": f"{county} County",
                    "dem": totals["dem"],
                    "rep": totals["rep"],
                    "other": totals["other"],
                    "total": totals["total"],
                }
            )
        statewide = {
            "dem": sum(row["dem"] for row in rows),
            "rep": sum(row["rep"] for row in rows),
            "other": sum(row["other"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "rowCount": len(rows),
        }
        series.append(
            {
                "id": f"{config['code'].lower()}-mvic-native-{item['year']}-president",
                "electionYear": item["year"],
                "sourceId": item["sourceId"],
                "sourceClass": "nativeOfficial",
                "sourceLevel": historical["sourceLevel"],
                "rowMethod": historical["rowMethod"],
                "rowCount": len(rows),
                "sourceUrl": source["url"],
                "localFile": source["localFile"],
                "sourceNote": item["note"],
                "statewide": statewide,
                "rows": rows,
            }
        )

    return {
        "metadata": {
            "purpose": f"Graph-ready {config['name']} presidential-election baseline using native official MVIC county rows.",
            "seriesCount": len(series),
            "warning": f"{config['name']} historical rows are native official county rows from each election year.",
            "sources": [
                {
                    "year": item["year"],
                    "localFile": source_map(config)[item["sourceId"]]["localFile"],
                    "sourceUrl": source_map(config)[item["sourceId"]]["url"],
                    "format": "Michigan MVIC tab-delimited county election result export",
                    "note": item["note"],
                }
                for item in historical["sources"]
            ],
        },
        "series": series,
    }


def historical_baseline_north_dakota_csv(config):
    historical = config["historicalBaseline"]
    series = []
    for item in historical["sources"]:
        source = source_map(config)[item["sourceId"]]
        contest_name = item.get("contestName", historical["contestName"])
        source_file = project_path(source["localFile"])
        if is_xlsx_file(source_file):
            by_county = north_dakota_xlsx_historical_rows(source_file)
        else:
            by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
            for row in north_dakota_export_rows(source_file):
                if row["contest"] != contest_name:
                    continue
                county = row["county"]
                votes = row["votes"]
                party = normalize_party(row["party"])
                by_county[county]["total"] += votes
                if party == normalize_party(historical["partyCodes"]["dem"]):
                    by_county[county]["dem"] += votes
                elif party == normalize_party(historical["partyCodes"]["rep"]):
                    by_county[county]["rep"] += votes
                else:
                    by_county[county]["other"] += votes

        rows = []
        for county, totals in sorted(by_county.items()):
            rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "reportingUnit": f"{county} County",
                    "ward": f"{county} County",
                    "dem": totals["dem"],
                    "rep": totals["rep"],
                    "other": totals["other"],
                    "total": totals["total"],
                }
            )
        statewide = {
            "dem": sum(row["dem"] for row in rows),
            "rep": sum(row["rep"] for row in rows),
            "other": sum(row["other"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "rowCount": len(rows),
        }
        series.append(
            {
                "id": f"{config['code'].lower()}-sos-native-{item['year']}-president",
                "electionYear": item["year"],
                "sourceId": item["sourceId"],
                "sourceClass": "nativeOfficial",
                "sourceLevel": historical["sourceLevel"],
                "rowMethod": historical["rowMethod"],
                "rowCount": len(rows),
                "sourceUrl": source["url"],
                "localFile": source["localFile"],
                "sourceNote": item["note"],
                "statewide": statewide,
                "rows": rows,
            }
        )

    return {
        "metadata": {
            "purpose": f"Graph-ready {config['name']} presidential-election baseline using native official SOS county rows.",
            "seriesCount": len(series),
            "warning": f"{config['name']} historical rows are native official county rows from each election year.",
            "sources": [
                {
                    "year": item["year"],
                    "localFile": source_map(config)[item["sourceId"]]["localFile"],
                    "sourceUrl": source_map(config)[item["sourceId"]]["url"],
                    "format": "North Dakota SOS All Statewide CSV export",
                    "note": item["note"],
                }
                for item in historical["sources"]
            ],
        },
        "series": series,
    }


def historical_baseline_pennsylvania_bulk_csv(config):
    historical = config["historicalBaseline"]
    series = []
    for item in historical["sources"]:
        source = source_map(config)[item["sourceId"]]
        office_code = item.get("officeCode", historical.get("officeCode", "USP"))
        by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
        for row in pennsylvania_bulk_rows(project_path(source["localFile"])):
            if row["officeCode"] != office_code:
                continue
            county = row["county"]
            votes = row["votes"]
            party = normalize_party(row["party"])
            by_county[county]["total"] += votes
            if party == normalize_party(historical["partyCodes"]["dem"]):
                by_county[county]["dem"] += votes
            elif party == normalize_party(historical["partyCodes"]["rep"]):
                by_county[county]["rep"] += votes
            else:
                by_county[county]["other"] += votes

        rows = []
        for county, totals in sorted(by_county.items()):
            rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "reportingUnit": f"{county} County",
                    "ward": f"{county} County",
                    "dem": totals["dem"],
                    "rep": totals["rep"],
                    "other": totals["other"],
                    "total": totals["total"],
                }
            )
        statewide = {
            "dem": sum(row["dem"] for row in rows),
            "rep": sum(row["rep"] for row in rows),
            "other": sum(row["other"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "rowCount": len(rows),
        }
        series.append(
            {
                "id": f"{config['code'].lower()}-dos-native-{item['year']}-president",
                "electionYear": item["year"],
                "sourceId": item["sourceId"],
                "sourceClass": "nativeOfficial",
                "sourceLevel": historical["sourceLevel"],
                "rowMethod": historical["rowMethod"],
                "rowCount": len(rows),
                "sourceUrl": source["url"],
                "localFile": source["localFile"],
                "sourceNote": item["note"],
                "statewide": statewide,
                "rows": rows,
            }
        )

    return {
        "metadata": {
            "purpose": f"Graph-ready {config['name']} presidential-election baseline using native official Department of State county rows.",
            "seriesCount": len(series),
            "warning": f"{config['name']} historical rows are native official precinct returns aggregated to county rows by election year.",
            "sources": [
                {
                    "year": item["year"],
                    "localFile": source_map(config)[item["sourceId"]]["localFile"],
                    "sourceUrl": source_map(config)[item["sourceId"]]["url"],
                    "format": "Pennsylvania Department of State comma-delimited precinct election returns",
                    "note": item["note"],
                }
                for item in historical["sources"]
            ],
        },
        "series": series,
    }


def historical_baseline_florida_precinct_zip(config):
    historical = config["historicalBaseline"]
    series = []
    for item in historical["sources"]:
        source = source_map(config)[item["sourceId"]]
        contest_name = item.get("contestName", historical["contestName"])
        by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
        section = {
            **historical,
            "excludeCandidatePatterns": item.get("excludeCandidatePatterns", historical.get("excludeCandidatePatterns", [])),
        }
        for row in florida_precinct_rows(project_path(source["localFile"])):
            if not florida_contest_matches(row, contest_name):
                continue
            if florida_excluded_candidate(row, section):
                continue
            county = row["county"]
            votes = row["votes"]
            by_county[county]["total"] += votes
            if row["party"] == historical["partyCodes"]["dem"]:
                by_county[county]["dem"] += votes
            elif row["party"] in {historical["partyCodes"]["rep"], *historical.get("alternateRepPartyCodes", [])}:
                by_county[county]["rep"] += votes
            else:
                by_county[county]["other"] += votes

        rows = []
        for county, totals in sorted(by_county.items()):
            rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "reportingUnit": f"{county} County",
                    "ward": f"{county} County",
                    "dem": totals["dem"],
                    "rep": totals["rep"],
                    "other": totals["other"],
                    "total": totals["total"],
                }
            )
        statewide = {
            "dem": sum(row["dem"] for row in rows),
            "rep": sum(row["rep"] for row in rows),
            "other": sum(row["other"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "rowCount": len(rows),
        }
        series.append(
            {
                "id": f"{config['code'].lower()}-doe-native-{item['year']}-president",
                "electionYear": item["year"],
                "sourceId": item["sourceId"],
                "sourceClass": "nativeOfficial",
                "sourceLevel": historical["sourceLevel"],
                "rowMethod": historical["rowMethod"],
                "rowCount": len(rows),
                "sourceUrl": source["url"],
                "localFile": source["localFile"],
                "sourceNote": item["note"],
                "statewide": statewide,
                "rows": rows,
            }
        )

    return {
        "metadata": {
            "purpose": f"Graph-ready {config['name']} presidential-election baseline using native official precinct rows.",
            "seriesCount": len(series),
            "warning": f"{config['name']} historical rows are native official precinct returns aggregated to county rows by election year.",
            "sources": [
                {
                    "year": item["year"],
                    "localFile": source_map(config)[item["sourceId"]]["localFile"],
                    "sourceUrl": source_map(config)[item["sourceId"]]["url"],
                    "format": "Florida Division of Elections tab-delimited precinct-level results ZIP",
                    "note": item["note"],
                }
                for item in historical["sources"]
            ],
        },
        "series": series,
    }


def historical_baseline_alabama_precinct_zip(config):
    historical = config["historicalBaseline"]
    series = []
    for item in historical["sources"]:
        source = source_map(config)[item["sourceId"]]
        section = {
            **historical,
            "sourceId": item["sourceId"],
            "excludeCandidatePatterns": historical.get("excludeCandidatePatterns", []),
        }
        by_county = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
        for workbook in alabama_precinct_zip_workbooks(section, config, all_sheets=True):
            county = alabama_county_from_workbook(workbook)
            if workbook.get("sheets") and alabama_historical_wide_sheet_rows(workbook, item, historical, by_county[county]):
                continue
            rows = workbook["rows"]
            if not rows:
                continue
            columns = alabama_precinct_columns(rows[0])
            for row in rows[1:]:
                contest = str(row[0] if len(row) > 0 else "").strip()
                contest_name = item.get("contestName", historical.get("contestName", ""))
                if contest_name and contest.upper() != contest_name.upper():
                    continue
                if not contest_name and not re.search(item.get("contestPattern", historical["contestPattern"]), contest, flags=re.IGNORECASE):
                    continue
                candidate = str(row[2] if len(row) > 2 else "").strip()
                if alabama_excluded_candidate(candidate, section):
                    continue
                party = normalize_party(row[1] if len(row) > 1 else "")
                votes = sum(int_text(row[index] if index < len(row) else 0) for index, _name in columns)
                by_county[county]["total"] += votes
                if party == normalize_party(historical["partyCodes"]["dem"]):
                    by_county[county]["dem"] += votes
                elif party == normalize_party(historical["partyCodes"]["rep"]):
                    by_county[county]["rep"] += votes
                else:
                    by_county[county]["other"] += votes

        rows = []
        for county, totals in sorted(by_county.items()):
            rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "reportingUnit": f"{county} County",
                    "ward": f"{county} County",
                    "dem": totals["dem"],
                    "rep": totals["rep"],
                    "other": totals["other"],
                    "total": totals["total"],
                }
            )
        statewide = {
            "dem": sum(row["dem"] for row in rows),
            "rep": sum(row["rep"] for row in rows),
            "other": sum(row["other"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "rowCount": len(rows),
        }
        series.append(
            {
                "id": f"{config['code'].lower()}-sos-native-{item['year']}-president",
                "electionYear": item["year"],
                "sourceId": item["sourceId"],
                "sourceClass": "nativeOfficial",
                "sourceLevel": historical["sourceLevel"],
                "rowMethod": historical["rowMethod"],
                "rowCount": len(rows),
                "sourceUrl": source["url"],
                "localFile": source["localFile"],
                "sourceNote": item["note"],
                "statewide": statewide,
                "rows": rows,
            }
        )

    return {
        "metadata": {
            "purpose": f"Graph-ready {config['name']} presidential-election baseline using native official SOS precinct rows aggregated to counties.",
            "seriesCount": len(series),
            "warning": f"{config['name']} historical rows are native official precinct returns aggregated to county rows by election year.",
            "sources": [
                {
                    "year": item["year"],
                    "localFile": source_map(config)[item["sourceId"]]["localFile"],
                    "sourceUrl": source_map(config)[item["sourceId"]]["url"],
                    "format": "Alabama Secretary of State county XLS files inside precinct-level ZIP archives",
                    "note": item["note"],
                }
                for item in historical["sources"]
            ],
        },
        "series": series,
    }


def alabama_historical_wide_sheet_rows(workbook, item, historical, totals):
    contest_name = item.get("wideContestName")
    if not contest_name:
        return False
    contest_sheet = None
    for sheet in workbook.get("sheets", []):
        first_value = str((sheet.get("rows") or [[""]])[0][0] or "").strip()
        if first_value.upper() == contest_name.upper():
            contest_sheet = sheet
            break
    if not contest_sheet:
        return False

    rows = contest_sheet["rows"]
    if len(rows) < 4:
        return True
    candidate_row = rows[1]
    header_row = rows[2]
    candidate_columns = []
    for index, value in enumerate(candidate_row):
        candidate = str(value or "").strip()
        if not candidate:
            continue
        total_index = index + 1 if index + 1 < len(header_row) and str(header_row[index + 1]).strip().upper() == "TOTAL VOTES" else index
        candidate_columns.append((total_index, candidate))

    for row in rows[3:]:
        precinct = str(row[0] if len(row) > 0 else "").strip()
        if not precinct or precinct.upper().startswith("TOTAL"):
            continue
        for index, candidate in candidate_columns:
            votes = int_text(row[index] if index < len(row) else 0)
            totals["total"] += votes
            candidate_upper = candidate.upper()
            if any(name in candidate_upper for name in item.get("demCandidateContains", historical.get("demCandidateContains", []))):
                totals["dem"] += votes
            elif any(name in candidate_upper for name in item.get("repCandidateContains", historical.get("repCandidateContains", []))):
                totals["rep"] += votes
            else:
                totals["other"] += votes
    return True


def parser_for(registry, key, feature_name):
    try:
        return registry[key]
    except KeyError as error:
        supported = ", ".join(sorted(registry))
        raise ValueError(f"Unsupported {feature_name} parser format {key!r}. Supported formats: {supported}") from error


CERTIFIED_RESULT_PARSERS = {
    "notConfigured": certified_results_not_configured,
    "xlsxPrecinctAggregation": certified_results_xlsx_precinct_aggregation,
    "alabamaPrecinctZip": certified_results_alabama_precinct_zip,
    "californiaPresidentXlsx": certified_results_california_president_xlsx,
    "coloradoCiveraCsv": certified_results_colorado_civera_csv,
    "connecticutStatementText": certified_results_connecticut_statement_text,
    "delawareCountyHtml": certified_results_delaware_county_html,
    "floridaPrecinctZip": certified_results_florida_precinct_zip,
    "hawaiiCountySummaryPdfs": certified_results_hawaii_county_summary_pdfs,
    "idahoCountyCsv": certified_results_idaho_county_csv,
    "iowaCanvassPdf": certified_results_iowa_canvass_pdf,
    "kansasPresidentialXlsx": certified_results_kansas_presidential_xlsx,
    "maineCountyTownXlsx": certified_results_maine_county_town_xlsx,
    "massachusettsCountyHtml": certified_results_massachusetts_county_html,
    "marylandCountyHtml": certified_results_maryland_county_html,
    "michiganCountyTab": certified_results_michigan_tab,
    "montanaCanvassPdf": certified_results_montana_canvass_pdf,
    "nationalCountyBaselineCsv": certified_results_national_county_baseline_csv,
    "newJerseyPresidentPdf": certified_results_new_jersey_president_pdf,
    "northCarolinaEnrZip": certified_results_north_carolina_enr_zip,
    "newYorkCountyCsv": certified_results_new_york_county_csv,
    "northDakotaStatewideCsv": certified_results_north_dakota_csv,
    "oklahomaEnrZip": certified_results_oklahoma_enr_zip,
    "pennsylvaniaBulkCsv": certified_results_pennsylvania_bulk_csv,
    "rhodeIslandSummaryXlsx": certified_results_rhode_island_summary_xlsx,
    "southCarolinaEnrJson": certified_results_south_carolina_enr_json,
    "southDakotaCanvassPdf": certified_results_south_dakota_canvass_pdf,
    "tennesseePrecinctXlsx": certified_results_tennessee_precinct_xlsx,
    "vermontMunicipalityCsv": certified_results_vermont_municipality_csv,
    "virginiaLocalityCsv": certified_results_virginia_locality_csv,
    "washingtonCountyHtml": certified_results_washington_county_html,
    "wyomingStatewideSummaryXlsx": certified_results_wyoming_statewide_summary_xlsx,
}

REVIEW_CHART_PARSERS = {
    "notConfigured": review_charts_not_configured,
    "xlsxPrecinctComparison": review_charts_xlsx_precinct_comparison,
    "alabamaPrecinctZipComparison": review_charts_alabama_precinct_zip,
    "floridaPrecinctZipComparison": review_charts_florida_precinct_zip,
    "tabDelimitedZipComparison": review_charts_tab_delimited_zip,
    "michiganPrecinctZipComparison": review_charts_tab_delimited_zip,
    "michiganCountyTabComparison": review_charts_michigan_tab,
    "northDakotaStatewideCsvCountyComparison": review_charts_north_dakota_csv,
    "pennsylvaniaBulkCsvPrecinctComparison": review_charts_pennsylvania_bulk_csv,
}

TURNOUT_PARSERS = {
    "notConfigured": turnout_data_not_configured,
    "alabamaPrecinctZipTurnout": turnout_data_alabama_precinct_zip,
    "floridaPrecinctZipTurnout": turnout_data_florida_precinct_zip,
    "xlsxPrecinctRows": turnout_data_xlsx_precinct_rows,
    "michiganMvicCountyTurnout": turnout_data_michigan_mvic,
    "northDakotaTurnoutHtml": turnout_data_north_dakota_html,
    "pennsylvaniaVoteHistoryXlsx": turnout_data_pennsylvania_vote_history_xlsx,
}

HISTORICAL_BASELINE_PARSERS = {
    "officialCountyResultText": historical_baseline_official_county_result_text,
    "alabamaPrecinctZip": historical_baseline_alabama_precinct_zip,
    "floridaPrecinctZip": historical_baseline_florida_precinct_zip,
    "michiganCountyTab": historical_baseline_michigan_tab,
    "northDakotaStatewideCsv": historical_baseline_north_dakota_csv,
    "pennsylvaniaBulkCsv": historical_baseline_pennsylvania_bulk_csv,
}


def write_geometry(config):
    geometry = config["geometry"]
    geojson = json.loads(local_source(config, geometry["sourceId"]).read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    if len(features) != geometry["expectedFeatures"]:
        raise ValueError(f"Expected {geometry['expectedFeatures']} geometry features, found {len(features)}")
    for feature in features:
        props = feature.setdefault("properties", {})
        props["NAME"] = props.get(geometry["nameProperty"]) or props.get("NAME")
    output_file = project_path(geometry["outputFile"])
    output_file.write_text(
        f"window.{geometry['outputGlobal']} = {json.dumps(geojson, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    return len(features)


def assert_expected(config, payload, geometry_features):
    expected = config["expected"]
    actual = {
        "countyRows": len(payload["presidentCountyResults"]),
        "precinctRows": payload["metadata"]["precinctRows"],
        "stateTotal": payload["metadata"]["stateTotal"],
        "trump": sum(row["trump"] for row in payload["presidentCountyResults"]),
        "harris": sum(row["harris"] for row in payload["presidentCountyResults"]),
        "other": sum(row["other"] for row in payload["presidentCountyResults"]),
        "reviewRows": len(payload["reviewCharts"]["metadata"]["rows"]),
        "turnoutRows": len(payload["turnoutData"]["rows"]),
        "turnoutWarningRows": payload["turnoutData"]["metadata"]["warningRows"],
        "historicalSeries": len(payload["historicalBaseline"]["series"]),
        "historicalRows": sum(series["rowCount"] for series in payload["historicalBaseline"]["series"]),
        "geometryFeatures": geometry_features,
    }
    errors = [
        f"{key}: expected {value}, got {actual.get(key)}"
        for key, value in expected.items()
        if actual.get(key) != value
    ]
    if errors:
        raise ValueError("State build expectation mismatch:\n- " + "\n- ".join(errors))
    return actual


def build_state(config, *, download=False, force_download=False):
    if download or force_download:
        maybe_download_sources(config, force=force_download)

    result_rows, candidate_labels, precinct_rows = certified_results(config)
    review_rows, eta_analysis = review_charts(config)
    turnout = turnout_data(config)
    historical = historical_baseline(config)
    geometry_features = write_geometry(config)

    payload = {
        "metadata": {
            "sourceWorkbook": source_map(config)[config["certifiedResults"]["sourceId"]]["localFile"],
            "precinctRows": precinct_rows,
            "countyRows": len(result_rows),
            "stateTotal": sum(row["total"] for row in result_rows),
            "notes": (
                "Certified result rows are not loaded for this state yet; source planner data is available."
                if config["certifiedResults"].get("format") == "notConfigured"
                else config["certifiedResults"].get("metadataNotes")
                if config["certifiedResults"].get("metadataNotes")
                else f"Aggregated from configured official {config['authority']} source files."
            ),
        },
        "presidentCountyResults": result_rows,
        "candidateLabels": candidate_labels,
        "reviewCharts": {
            "metadata": {
                "wardRows": len(review_rows),
                "source": local_source(config, config["reviewCharts"]["sourceId"]).name,
                "presidentSheet": config["reviewCharts"].get("sheet") or config["reviewCharts"].get("presidentContestName", ""),
                "senateSheet": config["reviewCharts"].get("sheet") or config["reviewCharts"].get("downBallotContestName", ""),
                "rows": review_rows,
            }
        },
        "etaAnalysis": eta_analysis,
        "turnoutData": turnout,
        "historicalBaseline": historical,
    }
    output = project_path(config["output"]["appDataFile"])
    output.write_text(
        f"window.{config['output']['appDataGlobal']} = {json.dumps(payload, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    return assert_expected(config, payload, geometry_features)


def build_state_geometry(config, *, download=False, force_download=False):
    if download or force_download:
        maybe_download_sources(config, force=force_download)
    return {"geometryFeatures": write_geometry(config)}


def registry_entry(config):
    app = config.get("app", {})
    geometry = config.get("geometry", {})
    output = config["output"]
    return {
        "code": config["code"],
        "name": config["name"],
        "authority": config["authority"],
        "electionYear": config["electionYear"],
        "office": config["office"],
        "countyLabel": app.get("countyLabel", "County"),
        "expectedCountyCount": config.get("expected", {}).get("countyRows"),
        "exportsSlug": app.get("exportsSlug", f"{slugify(config['name'])}-{config['electionYear']}"),
        "appDataFile": output["appDataFile"],
        "appDataGlobal": output["appDataGlobal"],
        "geometryFile": geometry.get("outputFile"),
        "geometryGlobal": geometry.get("outputGlobal"),
        "capabilities": app.get("capabilities", {}),
        "sourcePlan": app.get("sourcePlan", {}),
        "sourceInventory": app.get("sourceInventory", []),
        "checkedNotUsable": app.get("checkedNotUsable", []),
        "turnoutPolicy": app.get("turnoutPolicy", {}),
        "historicalSummary": app.get("historicalSummary", ""),
        "reviewRowLabel": app.get("reviewRowLabel", "local result row"),
        "reviewRowLabelPlural": app.get("reviewRowLabelPlural", "local result rows"),
        "reviewGraphTitlePrefix": app.get("reviewGraphTitlePrefix", "Local result"),
        "mapLoadingText": app.get(
            "mapLoadingText",
            f"Loading local {config['name']} county boundaries...",
        ),
        "noGeometryText": app.get(
            "noGeometryText",
            f"No local county geometry is loaded for {config['name']} yet; showing the county tile fallback.",
        ),
    }


def registry_ready(config):
    output_ready = project_path(config["output"]["appDataFile"]).exists()
    geometry_file = config.get("geometry", {}).get("outputFile")
    geometry_ready = not geometry_file or project_path(geometry_file).exists()
    return output_ready and geometry_ready


def write_state_registry(configs):
    entries = [
        registry_entry(config)
        for config in sorted(configs, key=lambda item: item["code"])
        if registry_ready(config)
    ]
    output = ROOT / "data" / "state-registry.js"
    output.write_text(
        f"window.STATE_APP_REGISTRY = {json.dumps({'states': entries}, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


def config_paths(args):
    if args.config:
        return [Path(item) for item in args.config]
    return sorted(path for path in CONFIG_DIR.glob("*.json") if not path.name.startswith("_"))


def read_config(config_path):
    path = config_path if config_path.is_absolute() else project_path(config_path)
    return json.loads(path.read_text(encoding="utf-8"))


def all_real_configs():
    return [read_config(path) for path in sorted(CONFIG_DIR.glob("*.json")) if not path.name.startswith("_")]


def config_build_ready(config):
    capabilities = config.get("app", {}).get("capabilities", {})
    required_capabilities = [
        "certifiedResults",
        "map",
        "reviewGraphs",
        "turnout",
        "historicalBaseline",
    ]
    if not all(capabilities.get(capability) for capability in required_capabilities):
        return False
    expected = config.get("expected", {})
    if not expected.get("countyRows") or not expected.get("stateTotal"):
        return False
    for source in config.get("sources", []):
        if source.get("url") in {"", "TODO"}:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Build configured state election app data bundles.")
    parser.add_argument("config", nargs="*", help="Path to one or more state config JSON files. Defaults to data/state-configs/*.json.")
    parser.add_argument("--download", action="store_true", help="Download any missing configured source files before building.")
    parser.add_argument("--force-download", action="store_true", help="Download configured source files even when local files exist.")
    parser.add_argument("--geometry-only", action="store_true", help="Build only configured county geometry artifacts.")
    args = parser.parse_args()

    explicit_configs = bool(args.config)
    summaries = {}
    configs = []
    for config_path in config_paths(args):
        config = read_config(config_path)
        configs.append(config)
        if args.geometry_only:
            summaries[config["code"]] = build_state_geometry(
                config,
                download=args.download,
                force_download=args.force_download,
            )
            continue
        if not explicit_configs and not config_build_ready(config):
            summaries[config["code"]] = {
                "status": "skipped",
                "reason": "State config is not fully promoted yet.",
            }
            continue
        summaries[config["code"]] = build_state(
            config,
            download=args.download,
            force_download=args.force_download,
        )
    write_state_registry(all_real_configs())
    print(json.dumps({"status": "passed", "states": summaries}, indent=2))


if __name__ == "__main__":
    main()
