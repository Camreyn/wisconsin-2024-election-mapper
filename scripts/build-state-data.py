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

WASHINGTON_COUNTY_CODES = {
    "AD": "Adams",
    "AS": "Asotin",
    "BE": "Benton",
    "CH": "Chelan",
    "CM": "Clallam",
    "CR": "Clark",
    "CU": "Columbia",
    "CZ": "Cowlitz",
    "DG": "Douglas",
    "FE": "Ferry",
    "FR": "Franklin",
    "GA": "Garfield",
    "GR": "Grant",
    "GY": "Grays Harbor",
    "IS": "Island",
    "JE": "Jefferson",
    "KI": "King",
    "KL": "Klickitat",
    "KP": "Kitsap",
    "KT": "Kittitas",
    "LE": "Lewis",
    "LI": "Lincoln",
    "MA": "Mason",
    "OK": "Okanogan",
    "PA": "Pacific",
    "PE": "Pend Oreille",
    "PI": "Pierce",
    "SJ": "San Juan",
    "SK": "Skagit",
    "SM": "Skamania",
    "SN": "Snohomish",
    "SP": "Spokane",
    "ST": "Stevens",
    "TH": "Thurston",
    "WH": "Whatcom",
    "WK": "Wahkiakum",
    "WM": "Whitman",
    "WW": "Walla Walla",
    "YA": "Yakima",
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


def worksheet_names(workbook_path):
    with zipfile.ZipFile(workbook_path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        return [sheet.attrib["name"] for sheet in workbook.findall("main:sheets/main:sheet", NS)]


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


def civera_int_text(value):
    text = str(value or "0").replace(",", "").strip()
    if text == "*":
        return 0
    return int(text or 0)


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


def california_sov_county_candidate_totals(path, sheet, columns, state_totals_label="State Totals"):
    rows = list(iter_worksheet_rows(path, sheet))
    result = {}
    reported_totals = None
    for row in rows:
        county = str((row[0] if row else "") or "").strip()
        if not county or county == "Percent" or county.startswith("Percent"):
            continue
        totals = {
            key: xlsx_indexed_vote(row, index)
            for key, index in columns.items()
        }
        if county == state_totals_label:
            reported_totals = totals
            continue
        result[county] = totals
    if reported_totals:
        parsed_totals = {
            key: sum(row[key] for row in result.values())
            for key in columns
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"California SOV county totals do not match State Totals row: {parsed_totals} != {reported_totals}")
    return result


def california_swdb_int(value):
    text = str(value or "").replace(",", "").strip()
    return int(text) if re.fullmatch(r"-?\d+", text) else 0


def california_county_basename_by_fips(config):
    geometry = config.get("geometry", {})
    path = local_source(config, geometry["sourceId"])
    geojson = json.loads(path.read_text(encoding="utf-8"))
    names = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geoid = str(props.get("GEOID") or "").zfill(5)
        basename = props.get("BASENAME") or re.sub(r"\s+County$", "", str(props.get("NAME") or ""))
        if geoid and basename:
            names[geoid] = basename
    return names


def california_city_by_srprec(config, review):
    path = local_source(config, review["citySourceId"])
    city_by_srprec = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            n = california_swdb_int(row.get("N"))
            in_city = california_swdb_int(row.get("N_IN_CITY"))
            share = (in_city / n) if n else 0
            key = (row["FIPS"], row["SRPREC"])
            candidate = (title_city_name(row["CITY"]), share, in_city, n)
            previous = city_by_srprec.get(key)
            if not previous or candidate[1:] > previous[1:]:
                city_by_srprec[key] = candidate
    return city_by_srprec


def title_city_name(value):
    small_words = {"a", "an", "and", "at", "by", "for", "in", "of", "on", "the", "to"}
    parts = re.split(r"(\s+|-)", str(value or "").strip().lower())
    titled = []
    word_index = 0
    for part in parts:
        if not part or part.isspace() or part == "-":
            titled.append(part)
            continue
        if word_index > 0 and part in small_words:
            titled.append(part)
        elif part in {"la", "los", "san", "santa"}:
            titled.append(part.title())
        else:
            titled.append(part[:1].upper() + part[1:])
        word_index += 1
    return "".join(titled)


def review_charts_california_swdb_srprec(config):
    review = config["reviewCharts"]
    source = source_map(config)[review["sourceId"]]
    path = local_source(config, review["sourceId"])
    county_names = california_county_basename_by_fips(config)
    city_by_srprec = california_city_by_srprec(config, review)
    columns = review.get(
        "columns",
        {
            "harris": "PRSDEM01",
            "trump": "PRSREP01",
            "other": ["PRSAIP01", "PRSGRN01", "PRSLIB01", "PRSPAF01"],
            "senateDem": "USSDEM01",
            "senateRep": "USSREP01",
        },
    )
    minimum_city_share = review.get("minimumCityShare", 0.5)
    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    presidential_total = 0
    masked_or_incomplete_rows = 0

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError(f"California SWDB SR precinct zip should contain one CSV, found {names}")
        with archive.open(names[0]) as raw:
            reader = csv.DictReader(line.decode("utf-8-sig") for line in raw)
            for row in reader:
                county = county_names.get(row.get("FIPS"))
                if not county:
                    raise ValueError(f"Could not map California FIPS {row.get('FIPS')!r} to a county name")
                harris = california_swdb_int(row.get(columns["harris"]))
                trump = california_swdb_int(row.get(columns["trump"]))
                other = sum(california_swdb_int(row.get(column)) for column in columns["other"])
                senate_dem = california_swdb_int(row.get(columns["senateDem"]))
                senate_rep = california_swdb_int(row.get(columns["senateRep"]))
                president_total = harris + trump + other
                senate_total = senate_dem + senate_rep
                if not president_total or not senate_total:
                    masked_or_incomplete_rows += 1
                    continue

                city_entry = city_by_srprec.get((row["FIPS"], row["SRPREC"]))
                if city_entry and city_entry[1] >= minimum_city_share:
                    city = city_entry[0]
                    ward = f"City of {city} Precinct {row['SRPREC']}"
                else:
                    ward = f"{county} County outside mapped cities Precinct {row['SRPREC']}"

                presidential_total += president_total
                senate_dem_total += senate_dem
                senate_rep_total += senate_rep
                review_rows.append(
                    {
                        "county": county,
                        "ward": ward,
                        "total": president_total,
                        "harris": harris,
                        "trump": trump,
                        "harrisShare": round2((harris / president_total) * 100),
                        "trumpShare": round2((trump / president_total) * 100),
                        "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                        "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
                    }
                )

    expected_total = review.get("expectedCandidateTotal")
    tolerance = review.get("candidateTotalTolerance", 0)
    if expected_total is not None and abs(presidential_total - expected_total) > tolerance:
        raise ValueError(
            "California SWDB SR precinct presidential candidate total outside tolerance: "
            f"{presidential_total} vs {expected_total} +/- {tolerance}"
        )
    if not review_rows:
        raise ValueError(f"California SWDB SR precinct parser found no usable rows in {source['localFile']}")
    eta = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta["maskedOrIncompleteRows"] = masked_or_incomplete_rows
    eta["presidentialCandidateTotal"] = presidential_total
    return review_rows, eta


def review_charts_arizona_precinct_summary_pdfs(config):
    review = config["reviewCharts"]
    source_by_id = source_map(config)
    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    parsed_county_totals = {}

    def target_precinct_line(line, next_line, pattern):
        if not re.match(pattern, line, flags=re.IGNORECASE):
            return False
        return next_line.startswith("TOTAL") or re.match(
            r"^(Presidential Electors|U\.S\. Representative|State Senator|Corporation Commissioner)\b",
            next_line,
            flags=re.IGNORECASE,
        )

    def first_vote_number(line):
        match = re.search(r"\b([0-9][0-9,]*)\b", line)
        return int_text(match.group(1)) if match else 0

    for item in review["sources"]:
        county = item["county"]
        path = local_source(config, item["sourceId"])
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in extract_pdf_text(path).splitlines()
            if line.strip()
        ]
        precinct_pattern = item.get("precinctPattern", r"^\d+\b")
        precincts = {}
        current_precinct = None
        current_contest = None
        for index, line in enumerate(lines):
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if target_precinct_line(line, next_line, precinct_pattern):
                current_precinct = line
                precincts.setdefault(
                    current_precinct,
                    {"trump": 0, "harris": 0, "presidentTotal": 0, "senateRep": 0, "senateDem": 0, "senateTotal": 0},
                )
                current_contest = None
                continue
            if not current_precinct:
                continue
            if re.match(r"^Presidential Electors$", line, flags=re.IGNORECASE):
                current_contest = "president"
                continue
            if re.match(r"^U\.S\. Senator$", line, flags=re.IGNORECASE):
                current_contest = "senate"
                continue
            if line.startswith("Total Votes Cast") and current_contest:
                total = first_vote_number(re.sub(r"^Total Votes Cast\s+", "", line, flags=re.IGNORECASE))
                if current_contest == "president":
                    precincts[current_precinct]["presidentTotal"] = total
                else:
                    precincts[current_precinct]["senateTotal"] = total
                current_contest = None
                continue
            if current_contest == "president":
                if re.match(r"^REP\s+TRUMP/VANCE\b", line, flags=re.IGNORECASE):
                    precincts[current_precinct]["trump"] = first_vote_number(line)
                elif re.match(r"^DEM\s+HARRIS/WALZ\b", line, flags=re.IGNORECASE):
                    precincts[current_precinct]["harris"] = first_vote_number(line)
            elif current_contest == "senate":
                if re.match(r"^REP\s+LAKE,?\s+KARI\b", line, flags=re.IGNORECASE):
                    precincts[current_precinct]["senateRep"] = first_vote_number(line)
                elif re.match(r"^DEM\s+GALLEGO,?\s+RUBEN\b", line, flags=re.IGNORECASE):
                    precincts[current_precinct]["senateDem"] = first_vote_number(line)

        county_rows = []
        for precinct, values in sorted(precincts.items()):
            president_total = values["presidentTotal"]
            if not president_total:
                continue
            harris = values["harris"]
            trump = values["trump"]
            senate_dem = values["senateDem"]
            senate_rep = values["senateRep"]
            senate_dem_total += senate_dem
            senate_rep_total += senate_rep
            county_rows.append(
                {
                    "county": county,
                    "ward": precinct,
                    "total": president_total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / president_total) * 100),
                    "trumpShare": round2((trump / president_total) * 100),
                    "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                    "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
                    "sourceUrl": source_by_id[item["sourceId"]]["url"],
                }
            )
        if not county_rows:
            raise ValueError(f"Arizona precinct parser found no usable rows for {county} in {path}")
        parsed_county_totals[county] = {
            "trump": sum(row["trump"] for row in county_rows),
            "harris": sum(row["harris"] for row in county_rows),
            "total": sum(row["total"] for row in county_rows),
        }
        expected = item.get("expectedTotals", {})
        for key, expected_key in (("trump", "trump"), ("harris", "harris"), ("total", "totalVotesCast")):
            if expected_key in expected and parsed_county_totals[county][key] != int(expected[expected_key]):
                raise ValueError(
                    f"Arizona {county} precinct {key} total mismatch: "
                    f"{parsed_county_totals[county][key]} != {expected[expected_key]}"
                )
        review_rows.extend(county_rows)

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["coverageMode"] = review.get("coverageMode", "partialLocal")
    eta_analysis["partialCoverage"] = True
    eta_analysis["loadedCounties"] = sorted({row["county"] for row in review_rows})
    eta_analysis["parsedCountyTotals"] = parsed_county_totals
    if review.get("warning"):
        eta_analysis["warning"] = review["warning"]
    return review_rows, eta_analysis


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
            row = {str(key).replace("\r\n", "\n"): value for key, value in row.items()}
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
            if county == source.get("totalsLabel", "Totals"):
                reported_total = int_text(row.get(columns["totalVotesCast"]))
                reported_totals = {"total": reported_total} if total == 0 else {**totals, "total": reported_total}
                continue

            reported_total = int_text(row.get(columns["totalVotesCast"]))
            if reported_total and total != reported_total:
                raise ValueError(f"Idaho candidate total mismatch for {county}: {total} != {reported_total}")

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
    if set(reported_totals) == {"total"}:
        parsed_totals = {"total": parsed_totals["total"]}
    if parsed_totals != reported_totals:
        raise ValueError(f"Idaho parsed county totals do not match CSV totals: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_county_totals_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    columns = source["columns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", county.upper()): county
        for county in geometry_names_by_geoid(config).values()
    }
    reported_totals = None
    result_rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            raw_county = str(row.get(columns["county"], "") or "").strip()
            if not raw_county:
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
                raise ValueError(f"Candidate total mismatch for {raw_county}: {total} != {reported_total}")

            if raw_county == source.get("totalsLabel", "Totals"):
                reported_totals = {**totals, "total": reported_total or total}
                continue

            county_key = re.sub(r"[^A-Z0-9]+", "", raw_county.upper())
            county = county_lookup.get(county_key)
            if not county:
                raise ValueError(f"Could not match county totals CSV row {raw_county!r} to geometry")

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

    missing_counties = sorted(set(county_lookup.values()) - {row["county"] for row in result_rows})
    if missing_counties:
        raise ValueError(f"County totals CSV missing county rows: {', '.join(missing_counties)}")

    if reported_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
            "total": sum(row["total"] for row in result_rows),
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"Parsed county totals do not match CSV totals: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_georgia_total_votes_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    contest_name = source.get("contestName", "President of the US")
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", county.upper()): county
        for county in geometry_names_by_geoid(config).values()
    }
    by_county = defaultdict(lambda: defaultdict(int))
    reported_totals = defaultdict(int)

    total_column_index, total_rows = read_sheet_rows(path, source.get("totalsSheet", "Total Votes"))
    for row in total_rows:
        if str(row[total_column_index["Office Name"]] or "").strip() != contest_name:
            continue
        candidate = str(row[total_column_index["Ballot Name"]] or "").strip()
        votes = int_cell(row, total_column_index, "Total")
        if new_york_column_matches(candidate, "", source["majorCandidates"]["trump"]):
            reported_totals["trump"] += votes
        elif new_york_column_matches(candidate, "", source["majorCandidates"]["harris"]):
            reported_totals["harris"] += votes
        else:
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, "", item):
                    reported_totals[item["key"]] += votes
                    break

    column_index, rows = read_sheet_rows(path, source.get("countySheet", "County Results"))
    source_rows = 0
    for row in rows:
        if str(row[column_index["Office Name"]] or "").strip() != contest_name:
            continue
        candidate = str(row[column_index["Ballot Name"]] or "").strip()
        if candidate in {"Ballots Cast", "Total Votes"}:
            continue
        raw_county = str(row[column_index["County"]] or "").strip()
        county_key = re.sub(r"[^A-Z0-9]+", "", raw_county.upper())
        county = county_lookup.get(county_key)
        if not county:
            raise ValueError(f"Could not match Georgia county {raw_county!r} to geometry")
        votes = int_cell(row, column_index, "Total")
        source_rows += 1
        if new_york_column_matches(candidate, "", source["majorCandidates"]["trump"]):
            by_county[county]["trump"] += votes
        elif new_york_column_matches(candidate, "", source["majorCandidates"]["harris"]):
            by_county[county]["harris"] += votes
        else:
            matched = False
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, "", item):
                    by_county[county][item["key"]] += votes
                    matched = True
                    break
            if not matched:
                by_county[county]["unmappedOther"] += votes

    missing_counties = sorted(set(county_lookup.values()) - set(by_county))
    if missing_counties:
        raise ValueError(f"Georgia workbook missing county rows: {', '.join(missing_counties)}")

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
    }
    if dict(parsed_totals) != dict(reported_totals):
        raise ValueError(f"Georgia county totals do not match Total Votes sheet: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, source_rows


def certified_results_illinois_precinct_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", county, flags=re.IGNORECASE).upper()): county
        for county in geometry_names_by_geoid(config).values()
    }
    jurisdiction_aliases = {
        key.upper(): value
        for key, value in source.get("jurisdictionAliases", {}).items()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    excluded_candidates = [item.upper() for item in source.get("excludedCandidates", [])]
    by_county = defaultdict(lambda: defaultdict(int))
    source_rows = 0

    def candidate_key(name):
        upper_name = name.upper()
        if any(excluded in upper_name for excluded in excluded_candidates):
            return None
        if new_york_column_matches(name, "", source["majorCandidates"]["trump"]):
            return "trump"
        if new_york_column_matches(name, "", source["majorCandidates"]["harris"]):
            return "harris"
        for item in source.get("otherCandidates", []):
            if new_york_column_matches(name, "", item):
                return item["key"]
        return "unmappedOther"

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("ContestName") != source.get("contestName", "PRESIDENT AND VICE PRESIDENT"):
                continue
            source_rows += 1
            raw_jurisdiction = (row.get("JurisName") or "").strip()
            county_name = jurisdiction_aliases.get(raw_jurisdiction.upper(), raw_jurisdiction)
            county_key = re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", county_name, flags=re.IGNORECASE).upper())
            county = county_lookup.get(county_key)
            if not county:
                raise ValueError(f"Could not match Illinois jurisdiction {raw_jurisdiction!r} to county geometry")
            key = candidate_key(row.get("CandidateName") or "")
            if not key:
                continue
            by_county[county][key] += int_text(row.get("VoteCount"))

    missing_counties = sorted(set(county_lookup.values()) - set(by_county))
    if missing_counties:
        raise ValueError(f"Illinois CSV missing county rows: {', '.join(missing_counties)}")

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

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, source_rows


def certified_results_civera_contest_county_csv(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Civera contest results CSV has too few rows: {path}")

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
            raise ValueError(f"Civera candidate total mismatch for {row[1]}: {total} != {reported_total}")
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
        raise ValueError(f"Could not find Civera State row in {path}")

    parsed_totals = {
        "harris": sum(row["harris"] for row in result_rows),
        "trump": sum(row["trump"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "total": sum(row["total"] for row in result_rows),
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Civera parsed county totals do not match CSV state row: {parsed_totals} != {reported_totals}")

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


def normalize_maine_municipality(value):
    text = str(value or "").strip()
    text = re.sub(r"\bSt\.", "Saint", text)
    text = re.sub(r"\bPlt\b", "Plantation", text)
    text = re.sub(r"\bTwp\b", "Township", text)
    text = re.sub(r"\bTwps\b", "Townships", text)
    text = text.replace("'", "")
    key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return {
        "caribou connor township": "caribou connor",
        "medway townships": "medway molunkus township",
        "day block township": "wesley day block township",
        "wesley": "wesley day block township",
    }.get(key, key)


def maine_county_town_vote_rows(config, source_id, sheet, columns):
    path = local_source(config, source_id)
    column_index, rows = read_sheet_rows(path, sheet)
    county_codes = config["certifiedResults"]["countyCodes"]
    uocava_label = config["certifiedResults"].get("uocavaLabel", "STATE UOCAVA")
    uocava_county = config["certifiedResults"].get("uocavaCountyName", "State UOCAVA")
    output = {}
    for row in rows:
        county_code = str(row[column_index[columns["countyCode"]]] or "").strip()
        municipality = str(row[column_index[columns["municipality"]]] or "").strip()
        if county_code and municipality:
            county = county_codes.get(county_code)
            if not county:
                raise ValueError(f"Unknown Maine county code {county_code!r} for {municipality!r}")
        elif municipality == uocava_label:
            county = uocava_county
        else:
            continue
        values = {}
        for key, column_name in columns.items():
            if key in {"countyCode", "municipality"}:
                continue
            if isinstance(column_name, list):
                values[key] = sum(int_cell(row, column_index, item) for item in column_name)
            else:
                values[key] = int_cell(row, column_index, column_name)
        key = (county_code or "UOCAVA", normalize_maine_municipality(municipality))
        if key in output:
            for value_key, value in values.items():
                output[key][value_key] += value
            if municipality not in output[key]["municipality"].split(" / "):
                output[key]["municipality"] = f"{output[key]['municipality']} / {municipality}"
        else:
            output[key] = {
                "county": county,
                "municipality": municipality,
                **values,
            }
    return output


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


def new_york_county_candidate_totals(path, candidate_rules, excluded_columns=None):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"New York county results source has too few rows: {path}")

    header = rows[0]
    party_row = rows[1]
    excluded = set(excluded_columns or ["Blank", "Void", "Total Votes", ""])
    by_county = {}
    statewide_totals = defaultdict(int)
    for row in rows[2:]:
        if len(row) < 2 or row[0] not in {"State", "County"}:
            continue
        totals = defaultdict(int)
        for index, header_value in enumerate(header):
            if index >= len(row) or header_value in excluded:
                continue
            party_value = party_row[index] if index < len(party_row) else ""
            for key, rule in candidate_rules.items():
                if new_york_column_matches(header_value, party_value, rule):
                    totals[key] += int_text(row[index])
                    break
        if row[0] == "State":
            statewide_totals.update(totals)
        else:
            by_county[str(row[1]).strip()] = totals

    parsed_totals = {
        key: sum(totals[key] for totals in by_county.values())
        for key in candidate_rules
    }
    if statewide_totals and parsed_totals != dict(statewide_totals):
        raise ValueError(f"New York county candidate totals do not match State row: {parsed_totals} != {dict(statewide_totals)}")
    return by_county


NYC_ED_KEYS = [
    "AD",
    "ED",
    "County",
    "EDAD Status",
    "Event",
    "Party/Independent Body",
    "Office/Position Title",
    "District Key",
    "VoteFor",
    "Unit Name",
    "Tally",
]


def new_york_city_ed_candidate_totals(path, candidate_rules, excluded_units=None):
    excluded = set(
        excluded_units
        or [
            "Public Counter",
            "Manually Counted Emergency",
            "Absentee / Military",
            "Federal",
            "Affidavit",
        ]
    )
    by_ed = defaultdict(lambda: defaultdict(int))
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.reader(handle), 1):
            if len(row) != len(NYC_ED_KEYS) * 2:
                raise ValueError(f"NYC ED CSV row {row_number} has {len(row)} columns, expected 22: {path}")
            if row[: len(NYC_ED_KEYS)] != NYC_ED_KEYS:
                raise ValueError(f"NYC ED CSV row {row_number} has unexpected key columns: {path}")
            values = dict(zip(NYC_ED_KEYS, row[len(NYC_ED_KEYS) :]))
            county = str(values["County"]).strip()
            ad = str(values["AD"]).strip().zfill(2)
            ed = str(values["ED"]).strip().zfill(3)
            unit_name = str(values["Unit Name"]).strip()
            tally = int_text(values["Tally"])
            key = (county, ad, ed)
            totals = by_ed[key]
            totals["county"] = county
            totals["ward"] = f"AD {ad} ED {ed}"
            if unit_name in excluded:
                continue
            totals["total"] += tally
            matched = False
            for output_key, rule in candidate_rules.items():
                if rule.get("candidateContains") and rule["candidateContains"].lower() in unit_name.lower():
                    totals[output_key] += tally
                    matched = True
                    break
                if rule.get("unitName") and unit_name == rule["unitName"]:
                    totals[output_key] += tally
                    matched = True
                    break
            if not matched:
                totals["other"] += tally
    return by_ed


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


def certified_results_kentucky_certification_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    county_lookup = {
        re.sub(r"\s+county$", "", county, flags=re.IGNORECASE).lower(): county
        for county in geometry_names_by_geoid(config).values()
    }
    aliases = {key.lower(): value.lower() for key, value in source.get("countyAliases", {}).items()}
    candidate_columns = source["candidateColumns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = {}
    reported_totals = None
    in_president_section = False

    row_pattern = re.compile(r"^(.+?)\s+((?:[\d,]+\s+){%d}[\d,]+)$" % (len(candidate_columns) - 1))
    for raw_line in extract_pdf_text(path).splitlines():
        line = raw_line.strip()
        if line == "President and Vice President of the United States":
            in_president_section = True
            continue
        if not in_president_section:
            continue
        if line.startswith("United States Representative"):
            break
        match = row_pattern.match(line)
        if not match:
            continue
        raw_county = match.group(1).strip()
        values = [int_text(value) for value in match.group(2).split()]
        if raw_county == "Total Votes":
            reported_totals = dict(zip(candidate_columns, values))
            continue
        lookup_key = re.sub(r"\s+", " ", raw_county.lower())
        county = county_lookup.get(lookup_key) or county_lookup.get(aliases.get(lookup_key, ""))
        if not county:
            continue
        by_county[county] = dict(zip(candidate_columns, values))

    if reported_totals is None:
        raise ValueError(f"Could not find Kentucky presidential Total Votes row in {path}")
    missing_counties = sorted(set(county_lookup.values()) - set(by_county))
    if missing_counties:
        raise ValueError(f"Kentucky certification PDF missing county rows: {', '.join(missing_counties)}")

    parsed_totals = {
        key: sum(totals[key] for totals in by_county.values())
        for key in candidate_columns
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Kentucky county totals do not match PDF Total Votes row: {parsed_totals} != {reported_totals}")

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

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


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


def civera_result_totals_by_scope(path, candidate_rules, row_types, excluded_columns=None):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Civera results source has too few rows: {path}")
    header = rows[0]
    party_row = rows[1]
    excluded = set(excluded_columns or ["", "Total Votes Cast", "Total Ballots Cast"])
    output = {}
    state_totals = defaultdict(int)

    for row in rows[2:]:
        if len(row) < 2:
            continue
        row_type = str(row[0]).strip()
        if row_type != "State" and row_type not in row_types:
            continue
        totals = defaultdict(int)
        for index, header_value in enumerate(header):
            if index >= len(row) or header_value in excluded:
                continue
            party_value = party_row[index] if index < len(party_row) else ""
            for key, rule in candidate_rules.items():
                if new_york_column_matches(header_value, party_value, rule):
                    totals[key] += int_text(row[index])
                    break
        if row_type == "State":
            state_totals.update(totals)
        else:
            output[str(row[1]).strip()] = totals

    parsed_totals = {
        key: sum(totals[key] for totals in output.values())
        for key in candidate_rules
    }
    if state_totals and parsed_totals != dict(state_totals):
        raise ValueError(f"Civera parsed totals do not match State row in {path}: {parsed_totals} != {dict(state_totals)}")
    return output


def civera_precinct_president_rows(path, columns):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Civera precinct CSV has too few rows: {path}")
    header = rows[0]
    column_index = {name: index for index, name in enumerate(header)}
    current_county = ""
    output = defaultdict(lambda: defaultdict(int))
    county_totals = defaultdict(int)

    candidate_columns = [
        value
        for key, value in columns.items()
        if key not in {"totalVotesCast", "totalBallotsCast"}
    ]
    for row in rows[2:]:
        if len(row) < len(header):
            continue
        row_type = str(row[0] or "").strip()
        if row_type == "County":
            current_county = str(row[1] or "").strip()
            county_totals[current_county] = civera_int_text(row[column_index[columns["totalVotesCast"]]])
            continue
        if row_type != "Precinct" or not current_county:
            continue
        precinct = str(row[1] or "").strip()
        item = output[(current_county, precinct)]
        item["harris"] += civera_int_text(row[column_index[columns["harris"]]])
        item["trump"] += civera_int_text(row[column_index[columns["trump"]]])
        for column in candidate_columns:
            if column in {columns["harris"], columns["trump"]}:
                continue
            item["other"] += civera_int_text(row[column_index[column]])

    parsed_by_county = defaultdict(int)
    for (county, _precinct), item in output.items():
        parsed_by_county[county] += item["harris"] + item["trump"] + item["other"]
    mismatches = [
        (county, parsed_by_county[county], expected)
        for county, expected in county_totals.items()
        if parsed_by_county[county] != expected
    ]
    if mismatches:
        # Some Civera exports publish local rows that do not sum exactly to the
        # county summary row. Keep the local rows usable for review charts and
        # document those source caveats in state configs.
        pass
    return output


def civera_precinct_down_ballot_rows(path, candidate_rules):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Civera down-ballot precinct CSV has too few rows: {path}")
    header = rows[0]
    party_row = rows[1]
    current_county = ""
    output = defaultdict(lambda: defaultdict(int))
    county_totals = defaultdict(lambda: defaultdict(int))

    for row in rows[2:]:
        if len(row) < len(header):
            continue
        row_type = str(row[0] or "").strip()
        if row_type == "County":
            current_county = str(row[1] or "").strip()
            target = county_totals[current_county]
        elif row_type == "Precinct" and current_county:
            target = output[(current_county, str(row[1] or "").strip())]
        else:
            continue
        for index, header_value in enumerate(header):
            party_value = party_row[index] if index < len(party_row) else ""
            for key, rule in candidate_rules.items():
                if new_york_column_matches(header_value, party_value, rule):
                    target[key] += civera_int_text(row[index])
                    break

    parsed_by_county = defaultdict(lambda: defaultdict(int))
    for (county, _precinct), item in output.items():
        for key in candidate_rules:
            parsed_by_county[county][key] += item[key]
    mismatches = []
    for county, expected in county_totals.items():
        parsed = parsed_by_county[county]
        for key in candidate_rules:
            if parsed[key] != expected[key]:
                mismatches.append((county, key, parsed[key], expected[key]))
    if mismatches:
        # See civera_precinct_president_rows: county summary reconciliation is
        # advisory for review rows, not a reason to drop valid local reporting rows.
        pass
    return output


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


def connecticut_subdivision_lookup(config, map_source_id, aliases):
    map_path = local_source(config, map_source_id)
    county_names = geometry_names_by_geoid(config)
    subdivision_lookup = {}
    subdivision_geojson = json.loads(map_path.read_text(encoding="utf-8"))
    for feature in subdivision_geojson.get("features", []):
        props = feature.get("properties", {})
        state_code = str(props.get("STATE") or "")
        county_code = str(props.get("COUNTY") or "").zfill(3)
        county = county_names.get(f"{state_code}{county_code}")
        basename = props.get("BASENAME") or props.get("NAME")
        if not county or not basename or basename == "County subdivisions not defined":
            continue
        subdivision_lookup[normalize_connecticut_town(basename, aliases)] = {
            "county": county,
            "town": basename,
        }
    return subdivision_lookup


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


def vermont_municipality_vote_rows(config, source_id, columns):
    path = local_source(config, source_id)
    source = config["certifiedResults"]
    map_path = local_source(config, source["municipalityMapSourceId"])
    county_names = geometry_names_by_geoid(config)
    aliases = source.get("municipalityAliases", {})
    suffix_aliases = source.get("municipalitySuffixAliases", {})

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

    output = {}
    missing = []
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
            values = {
                key: int_text(row.get(column_name))
                for key, column_name in columns.items()
                if key not in {"municipality"}
            }
            output[(candidates[0]["county"], municipality)] = {
                "county": candidates[0]["county"],
                "municipality": municipality,
                **values,
            }
    if missing:
        raise ValueError(f"Vermont municipality rows could not be mapped to a county: {', '.join(sorted(missing))}")
    return output


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


def certified_results_texas_county_json(config):
    source = config["certifiedResults"]
    data = json.loads(local_source(config, source["sourceId"]).read_text(encoding="utf-8"))
    office_id = str(source.get("officeId", "1001"))
    geoid_names = geometry_names_by_geoid(config)
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    result_rows = []

    for geoid, county_data in data.items():
        race = county_data.get("Races", {}).get(office_id)
        if not race:
            continue
        county = geoid_names.get(str(geoid).zfill(5))
        if not county:
            raise ValueError(f"Could not match Texas county GEOID {geoid!r} to geometry")

        totals = defaultdict(int)
        for candidate in race.get("C", {}).values():
            name = str(candidate.get("N", ""))
            party = str(candidate.get("P", ""))
            votes = int_text(candidate.get("V"))
            if new_york_column_matches(name, party, source["majorCandidates"]["trump"]):
                totals["trump"] += votes
            elif new_york_column_matches(name, party, source["majorCandidates"]["harris"]):
                totals["harris"] += votes
            else:
                matched_other = False
                for item in source.get("otherCandidates", []):
                    if new_york_column_matches(name, party, item):
                        totals[item["key"]] += votes
                        matched_other = True
                        break
                if not matched_other:
                    totals["unmappedOther"] += votes

        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
        reported_total = int_text(race.get("T"))
        if reported_total and total != reported_total:
            raise ValueError(f"Texas candidate total mismatch for {county}: {total} != {reported_total}")
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

    missing_counties = sorted(set(geoid_names.values()) - {row["county"] for row in result_rows})
    if missing_counties:
        raise ValueError(f"Texas county JSON missing county rows: {', '.join(missing_counties)}")

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

    geometry_names = {}
    for name in geometry_names_by_geoid(config).values():
        geometry_names[name.lower()] = name
        geometry_names[re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower()] = name
    geometry_names["baltimore city"] = "Baltimore city"
    geometry_names["saint mary's"] = "St. Mary's County"
    geometry_names["saint mary's county"] = "St. Mary's County"
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


def massachusetts_pd43_county_votes(path, columns):
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
    required_columns = [columns["dem"], columns["rep"], "All Others", "Blanks", "Total Votes Cast"]
    missing_columns = [name for name in required_columns if name not in column_index]
    if missing_columns:
        raise ValueError(f"Massachusetts PD43+ table missing columns: {missing_columns}")

    by_county = {}
    reported_totals = None
    reported_blanks = 0
    reported_total_votes_cast = 0
    for cells in rows[1:]:
        if len(cells) < len(header):
            continue
        county = cells[0]
        dem = int_text(cells[column_index[columns["dem"]]])
        rep = int_text(cells[column_index[columns["rep"]]])
        blanks = int_text(cells[column_index["Blanks"]])
        total_votes_cast = int_text(cells[column_index["Total Votes Cast"]])
        candidate_total = total_votes_cast - blanks
        other = candidate_total - dem - rep
        if candidate_total + blanks != total_votes_cast:
            raise ValueError(f"Massachusetts PD43+ total mismatch for {county}: {candidate_total} + {blanks} != {total_votes_cast}")
        if county == "Totals":
            reported_totals = {"dem": dem, "rep": rep, "other": other, "total": candidate_total}
            reported_blanks = blanks
            reported_total_votes_cast = total_votes_cast
            continue
        by_county[county] = {"county": county, "dem": dem, "rep": rep, "other": other, "total": candidate_total}

    if reported_totals:
        parsed_totals = {
            "dem": sum(row["dem"] for row in by_county.values()),
            "rep": sum(row["rep"] for row in by_county.values()),
            "other": sum(row["other"] for row in by_county.values()),
            "total": sum(row["total"] for row in by_county.values()),
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"Massachusetts PD43+ county totals do not match Totals row: {parsed_totals} != {reported_totals}")
        if parsed_totals["total"] + reported_blanks != reported_total_votes_cast:
            raise ValueError(
                "Massachusetts PD43+ statewide candidate total plus blanks does not match Total Votes Cast: "
                f"{parsed_totals['total']} + {reported_blanks} != {reported_total_votes_cast}"
            )
    return by_county


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


def new_jersey_pdf_candidate_county_totals(config, path, candidate_rules):
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    counties = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    by_county = defaultdict(lambda: defaultdict(int))
    candidate_totals = defaultdict(int)
    current_key = None

    for line in lines:
        if line.startswith("Total "):
            if current_key:
                candidate_totals[current_key] += int_text(re.findall(r"\d[\d,]*", line)[-1])
            current_key = None
            continue

        for key, rule in candidate_rules.items():
            if rule.get("candidateContains") and rule["candidateContains"].lower() in line.lower():
                current_key = key
                break

        if not current_key:
            continue
        raw_county = next((name for name in counties if line.startswith(f"{name} ")), None)
        if not raw_county:
            continue
        by_county[counties[raw_county]][current_key] += int_text(re.findall(r"\d[\d,]*", line)[-1])

    parsed_candidate_totals = {
        key: sum(totals[key] for totals in by_county.values())
        for key in candidate_rules
    }
    if parsed_candidate_totals != dict(candidate_totals):
        raise ValueError(
            "New Jersey parsed county totals do not match PDF candidate totals: "
            f"{parsed_candidate_totals} != {dict(candidate_totals)}"
        )
    return by_county


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


def certified_results_nevada_statewide_html(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    document = path.read_text(encoding="utf-8")
    contest_heading = re.search(
        r"<strong>\s*President and Vice President of the United States\s*</strong>.*?"
        r"<table[^>]*>(?P<table>.*?)</table>",
        document,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not contest_heading:
        raise ValueError(f"Could not find Nevada presidential results table in {path}")

    table = contest_heading.group("table")
    header_match = re.search(r"<thead>.*?<tr>(?P<header>.*?)</tr>.*?</thead>", table, flags=re.DOTALL | re.IGNORECASE)
    if not header_match:
        raise ValueError(f"Nevada presidential results table missing header in {path}")
    headers = [clean_html_cell(value) for value in re.findall(r"<th[^>]*>(.*?)</th>", header_match.group("header"), flags=re.DOTALL)]
    county_headers = headers[3:]
    if not county_headers:
        raise ValueError(f"Nevada presidential results table missing county columns in {path}")

    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", name, flags=re.IGNORECASE).upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_columns = []
    for county in county_headers:
        key = re.sub(r"[^A-Z0-9]+", "", county.upper())
        county_name = county_lookup.get(key)
        if not county_name:
            raise ValueError(f"Could not match Nevada county column {county!r} to geometry")
        county_columns.append(county_name)

    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = {county: defaultdict(int) for county in county_columns}
    reported_totals = defaultdict(int)
    row_pattern = re.compile(r"<tr>\s*(?P<row>.*?)\s*</tr>", flags=re.DOTALL | re.IGNORECASE)
    for row_match in row_pattern.finditer(table):
        cells = [clean_html_cell(value) for value in re.findall(r"<td[^>]*>(.*?)</td>", row_match.group("row"), flags=re.DOTALL)]
        if len(cells) < len(headers):
            continue
        candidate = cells[0]
        votes = [int_text(value) for value in cells[2 : 3 + len(county_columns)]]
        statewide_total = votes[0]
        county_votes = votes[1:]
        if sum(county_votes) != statewide_total:
            raise ValueError(f"Nevada statewide total mismatch for {candidate}: {sum(county_votes)} != {statewide_total}")

        if new_york_column_matches(candidate, "", source["majorCandidates"]["trump"]):
            key = "trump"
        elif new_york_column_matches(candidate, "", source["majorCandidates"]["harris"]):
            key = "harris"
        else:
            key = "unmappedOther"
            for item in source.get("otherCandidates", []):
                if new_york_column_matches(candidate, "", item):
                    key = item["key"]
                    break

        reported_totals[key] += statewide_total
        for county, count in zip(county_columns, county_votes):
            by_county[county][key] += count

    result_rows = []
    for county in county_columns:
        totals = by_county[county]
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

    missing_counties = sorted(set(county_lookup.values()) - {row["county"] for row in result_rows})
    if missing_counties:
        raise ValueError(f"Nevada presidential results missing county rows: {', '.join(missing_counties)}")

    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "unmappedOther": sum(by_county[county]["unmappedOther"] for county in county_columns),
    }
    reported_totals = {
        "trump": reported_totals["trump"],
        "harris": reported_totals["harris"],
        **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": reported_totals["unmappedOther"],
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Nevada parsed county totals do not match table totals: {parsed_totals} != {reported_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_south_carolina_enr_json(config):
    source = config["certifiedResults"]
    details_path = local_source(config, source["sourceId"])
    sum_path = local_source(config, source["statewideSourceId"])
    details = json.loads(details_path.read_text(encoding="utf-8"))
    statewide = json.loads(sum_path.read_text(encoding="utf-8"))
    state_name = config["name"]
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
        raise ValueError(f"Could not find {state_name} ENR contest {contest_key!r}")

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
            f"{state_name} ENR county totals do not match statewide summary totals: "
            f"{parsed_totals} != {expected_totals}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_indiana_enr_json(config):
    source = config["certifiedResults"]
    result_path = local_source(config, source["sourceId"])
    settings_path = local_source(config, source["settingsSourceId"])
    payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
    settings = json.loads(settings_path.read_text(encoding="utf-8-sig")).get("Root", {})
    state_name = config["name"]

    if settings.get("Certified") != "T":
        raise ValueError(f"{state_name} ENR settings are not marked certified: {settings_path}")
    if settings.get("ElectionType") != "G" or settings.get("CurrentElection") != source.get("electionDate", "11/05/2024"):
        raise ValueError(f"{state_name} ENR settings do not describe the expected general election: {settings_path}")

    root = payload.get("Root", {})
    statewide_race = root.get("StatewideSummary", {}).get("Race", {})
    office_category = root.get("OfficeCategory", {})
    if str(office_category.get("OFFICECATEGORYID")) != str(source.get("officeCategoryId", "1019")):
        raise ValueError(f"{state_name} ENR office category does not match the configured presidential category")

    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]

    def as_list(value):
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    def candidate_key(candidate):
        name = str(candidate.get("NAME_ON_BALLOT") or candidate.get("CandidateName") or "")
        party = str(candidate.get("PARTY") or candidate.get("PARTY_ABBREV") or "")
        if new_york_column_matches(name, party, source["majorCandidates"]["trump"]):
            return "trump"
        if new_york_column_matches(name, party, source["majorCandidates"]["harris"]):
            return "harris"
        for item in source.get("otherCandidates", []):
            if new_york_column_matches(name, party, item):
                return item["key"]
        return "unmappedOther"

    reported_totals = defaultdict(int)
    for candidate in as_list(statewide_race.get("Candidates", {}).get("Candidate")):
        reported_totals[candidate_key(candidate)] += int(candidate.get("TOTAL") or candidate.get("TOTAL_VOTES") or 0)

    county_names = geometry_names_by_geoid(config)
    result_rows = []
    parsed_totals = defaultdict(int)
    for region in as_list(office_category.get("Regions", {}).get("Region")):
        geoid = str(region.get("MAP_FIPS") or "")
        county = county_names.get(geoid) or region.get("MAP_JURISDICTION_NAME")
        if not county:
            raise ValueError(f"{state_name} ENR region is missing a county name/FIPS")
        totals = defaultdict(int)
        candidates = as_list(region.get("RegionSummary", {}).get("Race", {}).get("Candidates", {}).get("Candidate"))
        for candidate in candidates:
            key = candidate_key(candidate)
            votes = int(candidate.get("TOTAL") or candidate.get("TOTAL_VOTES") or 0)
            totals[key] += votes
            parsed_totals[key] += votes

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
        "trump": parsed_totals["trump"],
        "harris": parsed_totals["harris"],
        **{item["key"]: parsed_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": parsed_totals["unmappedOther"],
    }
    reported_totals = {
        "trump": reported_totals["trump"],
        "harris": reported_totals["harris"],
        **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": reported_totals["unmappedOther"],
    }
    if parsed_totals != reported_totals:
        raise ValueError(
            f"{state_name} ENR county totals do not match statewide summary totals: "
            f"{parsed_totals} != {reported_totals}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_total_results_contest_json(config):
    source = config["certifiedResults"]
    result_path = local_source(config, source["sourceId"])
    contest_list_path = local_source(config, source["contestListSourceId"])
    election_info_path = local_source(config, source["electionInfoSourceId"])
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    contest_list = json.loads(contest_list_path.read_text(encoding="utf-8"))
    election_info = json.loads(election_info_path.read_text(encoding="utf-8"))
    state_name = config["name"]
    contest_id = str(source["contestId"])

    if not result_payload.get("isOfficial"):
        raise ValueError(f"{state_name} TotalResults result payload is not marked official: {result_path}")
    if not contest_list.get("isOfficial"):
        raise ValueError(f"{state_name} TotalResults contest list is not marked official: {contest_list_path}")
    if not election_info.get("isOfficial"):
        raise ValueError(f"{state_name} TotalResults election info is not marked official: {election_info_path}")

    contest_metadata = (contest_list.get("response", {}).get("contests", {}) or {}).get(contest_id)
    result_contest = (result_payload.get("response", {}).get("contests", {}) or {}).get(contest_id)
    if not contest_metadata or not result_contest:
        raise ValueError(f"Could not find {state_name} TotalResults contest {contest_id!r}")

    choices = contest_metadata.get("choices", {}) or {}
    choice_map = {
        str(source["majorCandidates"]["trump"]["choiceId"]): "trump",
        str(source["majorCandidates"]["harris"]["choiceId"]): "harris",
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    for item in source.get("otherCandidates", []):
        choice_map[str(item["choiceId"])] = item["key"]

    for choice_id, key in choice_map.items():
        if choice_id not in choices:
            raise ValueError(f"{state_name} TotalResults choice {choice_id!r} for {key} is missing from contest metadata")

    def location_key(value):
        base = re.sub(r"\s+county$", "", value, flags=re.IGNORECASE).upper()
        return re.sub(r"[^A-Z0-9]+", "", base)

    county_names = {
        location_key(name): name
        for name in geometry_names_by_geoid(config).values()
    }
    location_names = {
        str(location_id): str(location.get("locationName", "")).strip()
        for location_id, location in (election_info.get("response", {}).get("locations", {}) or {}).items()
    }

    result_rows = []
    reported_location_totals = defaultdict(int)
    for location_id, location in (result_contest.get("locations", {}) or {}).items():
        county_key = location_key(location_names.get(str(location_id), ""))
        county = county_names.get(county_key)
        if not county:
            raise ValueError(f"Could not match {state_name} TotalResults location {location_id!r} ({county_key!r}) to geometry")

        totals = defaultdict(int)
        for choice in location.get("choices", []) or []:
            key = choice_map.get(str(choice.get("choiceID")), "unmappedOther")
            votes = int(choice.get("totalVotes") or 0)
            totals[key] += votes
            reported_location_totals[key] += votes

        other = sum(totals[item["key"]] for item in candidate_labels) + totals["unmappedOther"]
        total = totals["trump"] + totals["harris"] + other
        if total != int(location.get("totalVotes") or 0):
            raise ValueError(f"{state_name} TotalResults county total mismatch for {county}: {total} != {location.get('totalVotes')}")
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

    missing_counties = sorted(set(county_names.values()) - {row["county"] for row in result_rows})
    if missing_counties:
        raise ValueError(f"{state_name} TotalResults payload missing county rows: {', '.join(missing_counties)}")

    reported_totals = defaultdict(int)
    for choice in result_contest.get("choices", []) or []:
        key = choice_map.get(str(choice.get("choiceID")), "unmappedOther")
        reported_totals[key] += int(choice.get("totalVotes") or 0)
    parsed_totals = {
        "trump": reported_location_totals["trump"],
        "harris": reported_location_totals["harris"],
        **{item["key"]: reported_location_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": reported_location_totals["unmappedOther"],
        "total": sum(row["total"] for row in result_rows),
    }
    expected_totals = {
        "trump": reported_totals["trump"],
        "harris": reported_totals["harris"],
        **{item["key"]: reported_totals[item["key"]] for item in candidate_labels},
        "unmappedOther": reported_totals["unmappedOther"],
        "total": int(result_contest.get("totalVotes") or 0),
    }
    if parsed_totals != expected_totals:
        raise ValueError(
            f"{state_name} TotalResults county totals do not match statewide totals: "
            f"{parsed_totals} != {expected_totals}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_new_hampshire_president_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    columns = source["columns"]
    row_pattern = re.compile(r"^(?P<label>[A-Za-z]+)\s+(?P<values>(?:\d+\s+){6}\d+)$")
    result_rows = []
    reported_totals = None

    def parse_values(raw_values):
        values = [int_text(value) for value in raw_values.split()]
        return {key: values[index] for key, index in columns.items()}

    for line in lines:
        match = row_pattern.match(line)
        if not match:
            continue
        label = match.group("label")
        totals = parse_values(match.group("values"))
        if label == "TOTALS":
            reported_totals = totals
            continue
        county = county_names.get(label.upper())
        if not county:
            continue
        other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
        other = sum(other_values.values())
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
                **other_values,
                "underVotes": totals["underVotes"],
                "overVotes": totals["overVotes"],
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    if not reported_totals:
        raise ValueError(f"New Hampshire PDF missing TOTALS row: {path}")

    parsed_totals = {
        "harris": sum(row["harris"] for row in result_rows),
        "trump": sum(row["trump"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        "underVotes": sum(row["underVotes"] for row in result_rows),
        "overVotes": sum(row["overVotes"] for row in result_rows),
    }
    expected_totals = {key: reported_totals[key] for key in parsed_totals}
    if parsed_totals != expected_totals:
        raise ValueError(f"New Hampshire county totals do not match PDF TOTALS row: {parsed_totals} != {expected_totals}")

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


def certified_results_ohio_statewide_race_summary_xlsx(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    rows = list(iter_worksheet_rows(path, source.get("sheetName", "President and Vice President")))
    if len(rows) < 5:
        raise ValueError(f"Ohio summary workbook has too few rows: {path}")

    header = rows[source.get("headerRow", 2) - 1]
    total_row = rows[source.get("totalRow", 3) - 1]
    counties = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }

    def find_column(rule):
        needle = rule["candidateContains"].lower()
        for index, value in enumerate(header):
            if value is not None and needle in str(value).lower():
                return index
        raise ValueError(f"Could not find Ohio candidate column containing {rule['candidateContains']!r}")

    candidate_rules = {
        "harris": source["majorCandidates"]["harris"],
        "trump": source["majorCandidates"]["trump"],
        **{item["key"]: item for item in source.get("otherCandidates", [])},
    }
    candidate_columns = {key: find_column(rule) for key, rule in candidate_rules.items()}
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    reported_totals = {key: int_text(total_row[index]) for key, index in candidate_columns.items()}
    result_rows = []

    for row in rows[source.get("dataStartRow", 5) - 1 :]:
        raw_county = row[0] if row else None
        if not raw_county:
            continue
        county = counties.get(str(raw_county).upper())
        if not county:
            continue

        values = {key: int_text(row[index]) for key, index in candidate_columns.items()}
        other_values = {item["key"]: values[item["key"]] for item in candidate_labels}
        other = sum(other_values.values())
        total = values["trump"] + values["harris"] + other
        margin = values["trump"] - values["harris"]
        result_rows.append(
            {
                "county": county,
                "trump": values["trump"],
                "trumpPct": pct(values["trump"], total),
                "harris": values["harris"],
                "harrisPct": pct(values["harris"], total),
                "other": other,
                "otherPct": pct(other, total),
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    parsed_totals = {
        "harris": sum(row["harris"] for row in result_rows),
        "trump": sum(row["trump"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Ohio county totals do not match workbook Total row: {parsed_totals} != {reported_totals}")

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
    number_pattern = re.compile(r"\d[\d,]*")

    for line in lines[county_start + 1 :]:
        if line.startswith(source.get("nextContest", "United States Representative")):
            break
        numbers = number_pattern.findall(line)
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

        if re.match(r"^\d", line):
            raw_county = pending_county
            pending_county = None
        else:
            raw_county = re.sub(r"(?:\s+\d[\d,]*){4}$", "", line).strip()
        if not raw_county:
            raise ValueError(f"South Dakota presidential row has votes without a county label: {line!r}")
        county = county_names.get(raw_county.upper())
        if not county:
            raise ValueError(f"South Dakota presidential row has unknown county label {raw_county!r}")
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

    expected_counties = set(geometry_names_by_geoid(config).values())
    parsed_counties = {row["county"] for row in result_rows}
    if parsed_counties != expected_counties:
        raise ValueError(
            "South Dakota presidential county labels do not match geometry counties: "
            f"missing={sorted(expected_counties - parsed_counties)} extra={sorted(parsed_counties - expected_counties)}"
        )

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


def certified_results_nebraska_canvass_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    contest = source.get("contest", "President and Vice President of the United States")
    starts = [index for index, line in enumerate(lines) if line == contest]
    start = next((index for index in starts if index > 100), None)
    if start is None:
        raise ValueError(f"Could not find Nebraska presidential contest table in {path}")

    next_contest = source.get("nextContest", "Results by Congressional District")
    end = next(
        (
            index
            for index in range(start + 1, len(lines) - 1)
            if lines[index] == contest and lines[index + 1].startswith(next_contest)
        ),
        None,
    )
    if end is None:
        raise ValueError(f"Could not find Nebraska presidential contest page boundary in {path}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    other_keys = [item["key"] for item in candidate_labels]
    number_pattern = re.compile(r"\d[\d,]*")
    header_lines = {
        "Cornel West Jill Stein",
        "County (Republican) (Democratic) (Libertarian) NOW) (BY PETITION) Scatterings",
    }
    result_rows = []
    reported_totals = None
    pending_county = None

    for line in lines[start + 1 : end]:
        numbers = number_pattern.findall(line)
        if line.startswith("Total") and len(numbers) == 6:
            reported_totals = {
                "trump": int_text(numbers[0]),
                "harris": int_text(numbers[1]),
                "oliver": int_text(numbers[2]),
                "west": int_text(numbers[3]),
                "stein": int_text(numbers[4]),
                "writeIn": int_text(numbers[5]),
            }
            continue

        if len(numbers) == 6:
            raw_county = (
                pending_county
                if re.match(r"^\d", line)
                else re.sub(r"\s+\d[\d,\s]*$", "", line).strip()
            )
            if not raw_county:
                raise ValueError(f"Nebraska presidential row has votes without a county label: {line!r}")
            county = county_names.get(raw_county.upper()) or raw_county
            totals = {
                "trump": int_text(numbers[0]),
                "harris": int_text(numbers[1]),
                "oliver": int_text(numbers[2]),
                "west": int_text(numbers[3]),
                "stein": int_text(numbers[4]),
                "writeIn": int_text(numbers[5]),
            }
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
            pending_county = None
            continue

        if (
            not numbers
            and line not in header_lines
            and "Donald J. Trump" not in line
            and "Kamala D. Harris" not in line
            and not line.startswith("& JD")
            and not line.startswith("County")
            and not line.startswith("General Election")
        ):
            pending_county = line

    if reported_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            **{key: sum(row[key] for row in result_rows) for key in other_keys},
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"Nebraska parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

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


def certified_results_oregon_map_data_json(config):
    source = config["certifiedResults"]
    with local_source(config, source["sourceId"]).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    records = payload.get("d", payload)
    if not isinstance(records, list):
        raise ValueError("Oregon map data JSON did not contain a result row list")

    candidate_rules = {
        "trump": source["majorCandidates"]["trump"],
        "harris": source["majorCandidates"]["harris"],
        **{item["key"]: item for item in source.get("otherCandidates", [])},
    }
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    by_county = defaultdict(lambda: defaultdict(int))

    for row in records:
        if row.get("RaceName") != source.get("contestName", "President"):
            continue
        county = f"{row['CountyName']} County"
        candidate_name = str(row.get("calcCandidate", "")).lower()
        matched_key = next(
            (
                key
                for key, rule in candidate_rules.items()
                if rule.get("candidateContains", "").lower() in candidate_name
            ),
            None,
        )
        if matched_key:
            by_county[county][matched_key] += int(row.get("calcCandidateVotes") or 0)

    result_rows = []
    for county, totals in by_county.items():
        other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
        other = sum(other_values.values())
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
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    statewide_source_id = source.get("statewideSourceId")
    if statewide_source_id:
        with local_source(config, statewide_source_id).open("r", encoding="utf-8-sig", newline="") as handle:
            statewide_totals = defaultdict(int)
            for row in csv.DictReader(handle):
                if row.get("ContestName") != source.get("contestName", "President"):
                    continue
                candidate_name = str(row.get("CandidateName", "")).lower()
                matched_key = next(
                    (
                        key
                        for key, rule in candidate_rules.items()
                        if rule.get("candidateContains", "").lower() in candidate_name
                    ),
                    None,
                )
                if matched_key:
                    statewide_totals[matched_key] += int_text(row.get("CandidateVotes"))
        parsed_totals = {
            "trump": sum(row["trump"] for row in result_rows),
            "harris": sum(row["harris"] for row in result_rows),
            **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
        }
        if parsed_totals != dict(statewide_totals):
            raise ValueError(f"Oregon county map totals do not match statewide export: {parsed_totals} != {dict(statewide_totals)}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def certified_results_utah_statewide_canvass_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = set(geometry_names_by_geoid(config).values())
    columns = source["columns"]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    expected_columns = source.get("expectedCandidateColumns", 10)
    result_rows = []
    pending_values = []
    in_contest = False
    contest_total = None
    saw_candidate_totals = False
    expecting_contest_total = False

    for line in lines:
        if line == source.get("contest", "U.S. President and Vice President"):
            in_contest = True
            continue
        if not in_contest:
            continue

        values = [int_text(value) for value in re.findall(r"\d[\d,]*", line)]
        if line == "Total Votes Cast":
            if not saw_candidate_totals:
                saw_candidate_totals = True
            else:
                expecting_contest_total = True
            continue
        if expecting_contest_total and len(values) == 1:
            contest_total = values[0]
            break
        if line.startswith("Per Candidate") or line.startswith("%"):
            continue

        county_match = re.match(r"^(?P<county>.+?(?:County|Counl\)))\s+", line)
        if county_match:
            county = county_match.group("county").replace("Counl)", "County")
            if county not in county_names:
                raise ValueError(f"Unexpected Utah county row {county!r} in {path}")
            if len(values) == expected_columns - 1 and pending_values:
                values.insert(source.get("orphanInsertIndex", 3), pending_values.pop(0))
            if len(values) != expected_columns:
                raise ValueError(f"Expected {expected_columns} Utah candidate values for {county}, found {len(values)}: {values}")
            totals = {
                "trump": values[columns["trump"]],
                "harris": values[columns["harris"]],
                **{item["key"]: values[item["column"]] for item in source.get("otherCandidates", [])},
            }
            other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
            other = sum(other_values.values())
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
                    **other_values,
                    "margin": margin,
                    "marginPct": round((margin / total) * 100, 4) if total else 0,
                    "total": total,
                }
            )
            continue

        if len(values) == 1 and not saw_candidate_totals:
            pending_values.append(values[0])

    if len(result_rows) != config["expected"]["countyRows"]:
        raise ValueError(f"Expected {config['expected']['countyRows']} Utah county rows, found {len(result_rows)}")
    if pending_values:
        raise ValueError(f"Unconsumed Utah orphan PDF values: {pending_values}")
    if contest_total != source.get("contestTotalVotes"):
        raise ValueError(f"Utah contest total mismatch: {contest_total} != {source.get('contestTotalVotes')}")

    expected_totals = source.get("statewideTotals", {})
    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
    }
    if expected_totals and parsed_totals != expected_totals:
        raise ValueError(f"Utah parsed county totals do not match PDF totals: {parsed_totals} != {expected_totals}")

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


def utah_canvass_contest_values(config, source):
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = set(geometry_names_by_geoid(config).values())
    expected_columns = source["expectedCandidateColumns"]
    output = {}
    pending_values = []
    in_contest = False
    contest_total = None
    saw_candidate_totals = False
    expecting_contest_total = False

    for line in lines:
        if line == source["contest"]:
            in_contest = True
            continue
        if not in_contest:
            continue
        values = [int_text(value) for value in re.findall(r"\d[\d,]*", line)]
        if line == "Total Votes Cast":
            if not saw_candidate_totals:
                saw_candidate_totals = True
            else:
                expecting_contest_total = True
            continue
        if expecting_contest_total and len(values) == 1:
            contest_total = values[0]
            break
        if line.startswith("Per Candidate") or line.startswith("%"):
            continue
        county_match = re.match(r"^(?P<county>.+?(?:County|Counl\)))\s+", line)
        if county_match:
            county = county_match.group("county").replace("Counl)", "County")
            if county not in county_names:
                raise ValueError(f"Unexpected Utah county row {county!r} in {path}")
            if len(values) == expected_columns - 1 and pending_values:
                values.insert(source.get("orphanInsertIndex", 0), pending_values.pop(0))
            if len(values) != expected_columns:
                raise ValueError(f"Expected {expected_columns} Utah candidate values for {county}, found {len(values)}: {values}")
            output[county] = values
            continue
        if len(values) == 1 and not saw_candidate_totals:
            pending_values.append(values[0])

    if len(output) != config["expected"]["countyRows"]:
        raise ValueError(f"Expected {config['expected']['countyRows']} Utah county rows for {source['contest']}, found {len(output)}")
    if pending_values:
        raise ValueError(f"Unconsumed Utah orphan PDF values for {source['contest']}: {pending_values}")
    if contest_total != source.get("contestTotalVotes"):
        raise ValueError(f"Utah {source['contest']} contest total mismatch: {contest_total} != {source.get('contestTotalVotes')}")
    return output


def certified_results_missouri_actual_results_pdf(config):
    source = config["certifiedResults"]
    path = local_source(config, source["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    candidate_labels = [{"key": item["key"], "label": item["label"]} for item in source.get("otherCandidates", [])]
    county_names = set(geometry_names_by_geoid(config).values())
    first_table = {}
    final_write_in = {}
    first_totals = None
    final_totals = None
    table = None
    first_row_pattern = re.compile(r"^(?P<name>[A-Za-z. ]+?)\s+(?P<values>(?:\d+\s+){6}\d+)$")
    final_row_pattern = re.compile(r"^(?P<name>[A-Za-z. ]+?)\s+(?P<write_in>\d+)\s+(?P<total>\d+)$")

    def county_name(raw_name):
        name = source.get("mergeRows", {}).get(raw_name, raw_name)
        if name == "St. Louis":
            return "St. Louis County"
        if name == "St. Louis City":
            return "St. Louis city"
        if name in county_names:
            return name
        return f"{name} County"

    for line in lines:
        if line == "U.S. President":
            if not first_totals:
                table = "first"
            elif not final_totals:
                table = "final"
            continue

        if table == "first":
            match = first_row_pattern.match(line)
            if not match:
                continue
            values = [int_text(value) for value in match.group("values").split()]
            if match.group("name") == "Total":
                first_totals = values
                table = None
                continue
            county = county_name(match.group("name"))
            if county not in county_names:
                raise ValueError(f"Unexpected Missouri county row {county!r} from {match.group('name')!r}")
            for key, value in zip(source["firstTableColumns"], values):
                first_table.setdefault(county, defaultdict(int))[key] += value
            continue

        if table == "final":
            match = final_row_pattern.match(line)
            if not match:
                continue
            if match.group("name") == "Total":
                final_totals = {
                    "madamPotus": int_text(match.group("write_in")),
                    "total": int_text(match.group("total")),
                }
                table = None
                break
            county = county_name(match.group("name"))
            if county not in county_names:
                raise ValueError(f"Unexpected Missouri final county row {county!r} from {match.group('name')!r}")
            final_write_in[county] = final_write_in.get(county, 0) + int_text(match.group("write_in"))

    if not first_totals or not final_totals:
        raise ValueError(f"Could not find Missouri presidential total rows in {path}")

    result_rows = []
    for county, totals in first_table.items():
        totals["madamPotus"] += final_write_in.get(county, 0)
        other_values = {item["key"]: totals[item["key"]] for item in candidate_labels}
        other = sum(other_values.values())
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
                **other_values,
                "margin": margin,
                "marginPct": round((margin / total) * 100, 4) if total else 0,
                "total": total,
            }
        )

    if len(result_rows) != config["expected"]["countyRows"]:
        raise ValueError(f"Expected {config['expected']['countyRows']} Missouri county rows, found {len(result_rows)}")

    expected_totals = {
        **{key: first_totals[index] for index, key in enumerate(source["firstTableColumns"])},
        "madamPotus": final_totals["madamPotus"],
    }
    parsed_totals = {
        "trump": sum(row["trump"] for row in result_rows),
        "harris": sum(row["harris"] for row in result_rows),
        **{item["key"]: sum(row[item["key"]] for row in result_rows) for item in candidate_labels},
    }
    parsed_total = sum(row["total"] for row in result_rows)
    if parsed_totals != expected_totals or parsed_total != final_totals["total"]:
        raise ValueError(
            "Missouri parsed county totals do not match PDF totals: "
            f"{parsed_totals} / {parsed_total} != {expected_totals} / {final_totals['total']}"
        )

    return sorted(result_rows, key=lambda item: item["county"]), candidate_labels, len(result_rows)


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


def kansas_house_county_totals(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    by_county = defaultdict(lambda: defaultdict(int))
    county_sheet_names = {item["county"] for item in review.get("countySheets", [])}

    main_sheet = review.get("mainSheet", "OfficialPrecinctLevelResults")
    columns = review.get(
        "columns",
        {
            "county": "County",
            "race": "Race",
            "party": "Party",
            "votes": "Votes",
        },
    )
    column_index, rows = read_sheet_rows(path, main_sheet)
    contest_prefix = review.get("downBallotContestPrefix", "United States House of Representatives")
    party_keys = review.get("partyKeys", {"Democratic": "dem", "Republican": "rep"})
    for row in rows:
        county = str(row[column_index[columns["county"]]] if len(row) > column_index[columns["county"]] else "").strip()
        if not county or county in county_sheet_names:
            continue
        race = str(row[column_index[columns["race"]]] if len(row) > column_index[columns["race"]] else "").strip()
        if not race.startswith(contest_prefix):
            continue
        party = str(row[column_index[columns["party"]]] if len(row) > column_index[columns["party"]] else "").strip()
        key = party_keys.get(party)
        if not key:
            continue
        by_county[county][key] += int_text(row[column_index[columns["votes"]]] if len(row) > column_index[columns["votes"]] else 0)

    for sheet in review.get("countySheets", []):
        county = sheet["county"]
        rows = list(iter_worksheet_rows(path, sheet["sheet"]))
        totals_row = next(
            (
                row
                for row in rows
                if any(str(value).strip().upper() == "COUNTY TOTALS" for value in row if value is not None)
            ),
            None,
        )
        if totals_row is None:
            totals = defaultdict(int)
            for row in rows[2:]:
                for column in sheet["columns"]:
                    totals[column["partyKey"]] += int_text(row[column["index"]] if len(row) > column["index"] else 0)
            for key, value in totals.items():
                by_county[county][key] += value
        else:
            for column in sheet["columns"]:
                by_county[county][column["partyKey"]] += int_text(totals_row[column["index"]] if len(totals_row) > column["index"] else 0)

    expected_totals = review.get("downBallotStatewideTotals")
    if expected_totals:
        parsed_totals = {
            key: sum(totals[key] for totals in by_county.values())
            for key in expected_totals
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Kansas House county totals do not match statewide totals: {parsed_totals} != {expected_totals}")
    return by_county


def review_charts_kansas_house_xlsx(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _row_count = certified_results_kansas_presidential_xlsx(config)
    president = {row["county"]: row for row in president_rows}
    house_by_county = kansas_house_county_totals(config)

    missing = sorted(set(president) - set(house_by_county))
    if missing:
        raise ValueError(f"Kansas House review source missing counties: {missing}")

    review_rows = []
    house_dem_total = 0
    house_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        house_row = house_by_county[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        house_dem = house_row["dem"]
        house_rep = house_row["rep"]
        house_dem_total += house_dem
        house_rep_total += house_rep
        review_rows.append(
            {
                "county": county,
                "ward": f"{county} County",
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], house_dem_total, house_rep_total)


def review_charts_kansas_presidential_precinct_vote_share(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    columns = review.get(
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
    column_index, rows = read_sheet_rows(path, review.get("sheet", "2024 Presidential Results"))
    by_precinct = defaultdict(lambda: defaultdict(int))
    contest_name = review.get("contestName", "President / Vice President").upper()

    for row in rows:
        race = str(row[column_index[columns["race"]]] if len(row) > column_index[columns["race"]] else "").strip()
        if race.upper() != contest_name:
            continue
        county = str(row[column_index[columns["county"]]] if len(row) > column_index[columns["county"]] else "").strip()
        precinct = str(row[column_index[columns["precinct"]]] if len(row) > column_index[columns["precinct"]] else "").strip()
        candidate = str(row[column_index[columns["candidate"]]] if len(row) > column_index[columns["candidate"]] else "").strip()
        party = str(row[column_index[columns["party"]]] if len(row) > column_index[columns["party"]] else "").strip()
        votes = int_text(row[column_index[columns["votes"]]] if len(row) > column_index[columns["votes"]] else 0)
        if not county or not precinct or not candidate:
            continue
        item = by_precinct[(county, precinct)]
        if new_york_column_matches(candidate, party, review["majorCandidates"]["trump"]):
            item["trump"] += votes
        elif new_york_column_matches(candidate, party, review["majorCandidates"]["harris"]):
            item["harris"] += votes
        else:
            item["other"] += votes

    review_rows = []
    for (county, precinct), totals in sorted(by_precinct.items()):
        total = totals["trump"] + totals["harris"] + totals["other"]
        if not total:
            continue
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": total,
                "harris": totals["harris"],
                "trump": totals["trump"],
                "harrisShare": round2((totals["harris"] / total) * 100),
                "trumpShare": round2((totals["trump"] / total) * 100),
                "demDropoff": 0,
                "repDropoff": 0,
            }
        )

    expected_totals = review.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in review_rows),
            "harris": sum(row["harris"] for row in review_rows),
            "other": sum(row["total"] - row["trump"] - row["harris"] for row in review_rows),
            "total": sum(row["total"] for row in review_rows),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Kansas precinct vote-share totals do not match expected totals: {parsed_totals} != {expected_totals}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["warning"] = review.get(
        "warning",
        "Kansas review rows use official presidential precinct vote share only; no same-row down-ballot comparison is mapped.",
    )
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


def review_charts_north_dakota_precinct_workbooks(config):
    review = config["reviewCharts"]
    president_path = local_source(config, review["sourceId"])
    senate_path = local_source(config, review["senateSourceId"])
    source = source_map(config)[review["sourceId"]]

    def key_for_candidate(candidate, rules):
        for key, rule in rules.items():
            if new_york_column_matches(str(candidate or ""), "", rule):
                return key
        return "other"

    def workbook_totals(path, rules):
        totals = defaultdict(lambda: defaultdict(int))
        for sheet in worksheet_names(path):
            county = sheet
            header = None
            for row in iter_worksheet_rows(path, sheet):
                if len(row) > 1 and row[1] == "Precinct":
                    header = row
                    continue
                if not header or len(row) < 2:
                    continue
                precinct = str(row[1] or "").strip()
                if not precinct or precinct.upper() == "TOTALS":
                    continue
                item = totals[(county, precinct)]
                for index, candidate in enumerate(header[2:], start=2):
                    if index >= len(row):
                        continue
                    key = key_for_candidate(candidate, rules)
                    item[key] += int_text(row[index])
            if header is None:
                raise ValueError(f"North Dakota precinct workbook missing header row for {sheet}")
        return totals

    president = workbook_totals(president_path, review["majorCandidates"])
    down_ballot = workbook_totals(senate_path, review["downBallotCandidates"])
    certified_rows, _candidate_labels, _precinct_rows = certified_results(config)
    certified_by_county = {row["county"]: row for row in certified_rows}

    parsed_by_county = defaultdict(lambda: defaultdict(int))
    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for key in sorted(president):
        county, precinct = key
        totals = president[key]
        harris = totals["harris"]
        trump = totals["trump"]
        other = totals["other"]
        president_total = harris + trump + other
        if not president_total:
            continue
        senate = down_ballot.get(key, {})
        senate_dem = senate["dem"]
        senate_rep = senate["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        parsed_by_county[county]["harris"] += harris
        parsed_by_county[county]["trump"] += trump
        parsed_by_county[county]["other"] += other
        parsed_by_county[county]["total"] += president_total
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
                "sourceUrl": source["url"],
            }
        )

    missing_counties = sorted(set(certified_by_county) - set(parsed_by_county))
    if missing_counties:
        raise ValueError(f"North Dakota precinct workbooks missing counties: {', '.join(missing_counties)}")
    for county, expected in certified_by_county.items():
        parsed = parsed_by_county[county]
        expected_totals = {
            "harris": expected["harris"],
            "trump": expected["trump"],
            "other": expected["other"],
            "total": expected["total"],
        }
        parsed_totals = {key: parsed[key] for key in expected_totals}
        if parsed_totals != expected_totals:
            raise ValueError(f"North Dakota precinct totals mismatch for {county}: {parsed_totals} != {expected_totals}")

    expected_rows = review.get("expectedRows")
    if expected_rows and len(review_rows) != expected_rows:
        raise ValueError(f"North Dakota precinct row count mismatch: {len(review_rows)} != {expected_rows}")
    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["coverageMode"] = "statewideLocal"
    eta_analysis["partialCoverage"] = False
    eta_analysis["warning"] = review.get(
        "warning",
        "North Dakota review rows use official SOS precinct workbooks for President and U.S. Senate.",
    )
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


def washington_precinct_county(code):
    return WASHINGTON_COUNTY_CODES.get(str(code or "").strip().upper(), f"{code} County")


def review_charts_washington_precinct_csv(config):
    review = config["reviewCharts"]
    precincts = defaultdict(lambda: defaultdict(int))
    senate_dem_total = 0
    senate_rep_total = 0

    with local_source(config, review["sourceId"]).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            race = str(row.get("Race", "")).strip()
            if race not in {review["presidentContestName"], review["downBallotContestName"]}:
                continue
            precinct_code = str(row.get("PrecinctCode", "")).strip()
            precinct_name = str(row.get("PrecinctName", "")).strip()
            if precinct_code == "-1" or precinct_name.upper() == "TOTAL":
                continue
            county_code = str(row.get("CountyCode", "")).strip()
            key = (county_code, precinct_code, precinct_name)
            item = precincts[key]
            item["county"] = washington_precinct_county(county_code)
            item["ward"] = f"{precinct_code} {precinct_name}".strip()
            votes = int_text(row.get("Votes"))
            candidate = str(row.get("Candidate", "")).strip()

            if race == review["presidentContestName"]:
                item["president_total"] += votes
                if new_york_column_matches(candidate, "", review["majorCandidates"]["harris"]):
                    item["harris"] += votes
                elif new_york_column_matches(candidate, "", review["majorCandidates"]["trump"]):
                    item["trump"] += votes
            elif race == review["downBallotContestName"]:
                if new_york_column_matches(candidate, "", review["downBallotCandidates"]["dem"]):
                    item["senate_dem"] += votes
                    senate_dem_total += votes
                elif new_york_column_matches(candidate, "", review["downBallotCandidates"]["rep"]):
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


def idaho_precinct_rows(config, source_id, columns):
    path = local_source(config, source_id)
    current_county = ""
    rows = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get(columns["county"], "")).strip()
            if not label or label == "Totals":
                continue
            if not label.upper().startswith("PRECINCT "):
                current_county = label
                continue
            if not current_county:
                raise ValueError(f"Idaho precinct row missing county context in {path}: {label}")
            rows[(current_county, label)] = row
    return rows


def review_charts_idaho_precinct_csv(config):
    review = config["reviewCharts"]
    columns = review["columns"]
    precincts = defaultdict(lambda: defaultdict(int))
    house_dem_total = 0
    house_rep_total = 0

    for key, row in idaho_precinct_rows(config, review["presidentSourceId"], columns).items():
        item = precincts[key]
        county, precinct = key
        item["county"] = county
        item["ward"] = precinct
        item["president_total"] += int_text(row.get(columns["presidentTotal"]))
        item["harris"] += int_text(row.get(columns["harris"]))
        item["trump"] += int_text(row.get(columns["trump"]))

    for source in review["downBallotSources"]:
        for key, row in idaho_precinct_rows(config, source["sourceId"], columns).items():
            item = precincts[key]
            county, precinct = key
            item["county"] = county
            item["ward"] = precinct
            dem_votes = int_text(row.get(source["demColumn"]))
            rep_votes = int_text(row.get(source["repColumn"]))
            item["house_dem"] += dem_votes
            item["house_rep"] += rep_votes
            house_dem_total += dem_votes
            house_rep_total += rep_votes

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


def georgia_enr_text(name_values):
    if isinstance(name_values, list):
        for item in name_values:
            text = str((item or {}).get("text", "")).strip()
            if text:
                return text
    return str(name_values or "").strip()


def georgia_enr_candidate_votes(ballot_options):
    votes = defaultdict(int)
    for option in ballot_options or []:
        party = normalize_party((option.get("party") or {}).get("abbreviation", ""))
        if party == "DEM":
            votes["dem"] += int_text(option.get("voteCount"))
        elif party == "REP":
            votes["rep"] += int_text(option.get("voteCount"))
    return votes


def review_charts_georgia_house_json(config):
    review = config["reviewCharts"]
    president_path = local_source(config, review["presidentSourceId"])
    with president_path.open("r", encoding="utf-8") as handle:
        president = json.load(handle)

    counties = {}
    for row in president.get("breakdownResults", []):
        locality = row.get("locality") or {}
        county = georgia_enr_text(locality.get("name"))
        if not county:
            continue
        votes = georgia_enr_candidate_votes(row.get("ballotOptions"))
        counties[county] = {
            "county": county,
            "ward": county,
            "president_total": int_text(row.get("voteTotal")),
            "harris": votes["dem"],
            "trump": votes["rep"],
            "house_dem": 0,
            "house_rep": 0,
        }

    house_dem_total = 0
    house_rep_total = 0
    for source in review["downBallotSources"]:
        path = local_source(config, source["sourceId"])
        with path.open("r", encoding="utf-8") as handle:
            contest = json.load(handle)
        for row in contest.get("breakdownResults", []):
            locality = row.get("locality") or {}
            county = georgia_enr_text(locality.get("name"))
            if not county:
                continue
            if county not in counties:
                raise ValueError(f"Georgia House source contains county not in President rows: {county}")
            votes = georgia_enr_candidate_votes(row.get("ballotOptions"))
            counties[county]["house_dem"] += votes["dem"]
            counties[county]["house_rep"] += votes["rep"]
            house_dem_total += votes["dem"]
            house_rep_total += votes["rep"]

    review_rows = []
    for county, item in sorted(counties.items()):
        president_total = item["president_total"]
        if not president_total:
            continue
        harris = item["harris"]
        trump = item["trump"]
        house_dem = item["house_dem"]
        house_rep = item["house_rep"]
        review_rows.append(
            {
                "county": county,
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

    expected_rows = config["expected"].get("countyRows")
    if expected_rows and len(review_rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} Georgia review rows, found {len(review_rows)}")

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Georgia review rows compare President to the aggregate of U.S. House district contests by county; counties split across districts are summed before comparison.",
    )
    return review_rows, eta_analysis


def review_charts_georgia_precinct_vote_share(config):
    review = config["reviewCharts"]
    manifest_path = local_source(config, review["sourceId"])
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    review_rows = []
    county_totals = defaultdict(lambda: defaultdict(int))
    for entry in manifest.get("counties", []):
        county = entry["county"].replace(" County", "")
        detail_path = ROOT / entry["localFile"]
        with detail_path.open("r", encoding="utf-8") as handle:
            detail = json.load(handle)
        for precinct_row in detail.get("breakdownResults", []):
            precinct = georgia_enr_text((precinct_row.get("precinct") or {}).get("name"))
            if not precinct:
                continue
            votes = georgia_enr_candidate_votes(precinct_row.get("ballotOptions"))
            president_total = int_text(precinct_row.get("voteTotal"))
            if not president_total:
                continue
            harris = votes["dem"]
            trump = votes["rep"]
            review_rows.append(
                {
                    "county": county,
                    "ward": precinct,
                    "total": president_total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / president_total) * 100),
                    "trumpShare": round2((trump / president_total) * 100),
                    "demDropoff": 0,
                    "repDropoff": 0,
                }
            )
            county_totals[county]["total"] += president_total
            county_totals[county]["harris"] += harris
            county_totals[county]["trump"] += trump

    expected_rows = review.get("expectedCountyCount") or config["expected"].get("countyRows")
    if expected_rows and len(county_totals) != expected_rows:
        raise ValueError(f"Expected {expected_rows} Georgia precinct counties, found {len(county_totals)}")

    expected_totals = review.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "harris": sum(item["harris"] for item in county_totals.values()),
            "trump": sum(item["trump"] for item in county_totals.values()),
            "total": sum(item["total"] for item in county_totals.values()),
        }
        for key, expected in expected_totals.items():
            if parsed_totals.get(key) != expected:
                raise ValueError(f"Georgia precinct {key} total mismatch: {parsed_totals.get(key)} != {expected}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["coverageNote"] = (
        "Official Georgia Secretary of State county-scoped precinct President rows are loaded for vote-share "
        "advisory review. Down-ballot advisory flags are suppressed until district-contest precinct rows are mapped safely."
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Georgia review rows are official presidential precinct vote-share rows only; down-ballot flags are suppressed.",
    )
    return review_rows, eta_analysis


def iowa_house_county_totals(config, review):
    path = local_source(config, review["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_prefixes = sorted(county_names, key=len, reverse=True)
    district_starts = []
    for index, line in enumerate(lines):
        if re.match(r"^United States Representative District \d+$", line):
            district_starts.append((int(line.rsplit(" ", 1)[1]), index))
    if len(district_starts) != len(review["districts"]):
        raise ValueError(f"Expected {len(review['districts'])} Iowa House district tables, found {len(district_starts)}")

    district_starts.sort()
    by_county = defaultdict(lambda: defaultdict(int))
    for district, start in district_starts:
        next_start = next((other_start for other_district, other_start in district_starts if other_district > district), len(lines))
        current_county = None
        for line in lines[start:next_start]:
            if re.match(r"^Page \d+ of \d+$", line):
                continue
            if line.startswith(("United States Representative", "DEM REP", "Write-in", "Jody Madlom", "Christina Bohannan", "Sarah Corkery", "Lanon Baccam", "Ryan Melton")):
                continue
            values_match = re.match(r"^Total\s+(?P<values>(?:\d[\d,]*\s+){4,}\d[\d,]*)$", line)
            if values_match and current_county:
                values = values_match.group("values").split()
                by_county[current_county]["dem"] += int_text(values[0])
                by_county[current_county]["rep"] += int_text(values[1])
                current_county = None
                continue
            upper_line = line.upper()
            for raw_county in county_prefixes:
                if upper_line.startswith(f"{raw_county} "):
                    current_county = county_names[raw_county]
                    break

    expected_counties = set(county_names.values())
    missing = sorted(expected_counties - set(by_county))
    if missing:
        raise ValueError(f"Iowa House tables missing counties: {', '.join(missing)}")
    return by_county


def review_charts_iowa_house_pdf(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _precinct_rows = certified_results_iowa_canvass_pdf(config)
    house_rows = iowa_house_county_totals(config, review)
    house_dem_total = sum(row["dem"] for row in house_rows.values())
    house_rep_total = sum(row["rep"] for row in house_rows.values())

    review_rows = []
    for row in president_rows:
        county = row["county"]
        house = house_rows[county]
        president_total = row["total"]
        harris = row["harris"]
        trump = row["trump"]
        review_rows.append(
            {
                "county": county,
                "ward": county,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house["dem"]) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house["rep"]) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Iowa review rows compare President to the aggregate of U.S. House district contests by county, not to a single statewide down-ballot race.",
    )
    return review_rows, eta_analysis


def oregon_map_data_party_totals(config, source_ids):
    by_county = defaultdict(lambda: defaultdict(int))
    for source_id in source_ids:
        with local_source(config, source_id).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        records = payload.get("d", payload)
        if not isinstance(records, list):
            raise ValueError(f"Oregon map data source {source_id} did not contain a result row list")
        for row in records:
            county = f"{row['CountyName']} County"
            party = normalize_party(row.get("PartyCode", ""))
            if party == "DEM":
                by_county[county]["dem"] += int_text(row.get("calcCandidateVotes"))
            elif party == "REP":
                by_county[county]["rep"] += int_text(row.get("calcCandidateVotes"))
    return by_county


def review_charts_oregon_house_map_data(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _precinct_rows = certified_results_oregon_map_data_json(config)
    house_rows = oregon_map_data_party_totals(config, review["downBallotSourceIds"])
    expected_counties = {row["county"] for row in president_rows}
    missing = sorted(expected_counties - set(house_rows))
    if missing:
        raise ValueError(f"Oregon House map data missing counties: {', '.join(missing)}")

    house_dem_total = sum(row["dem"] for row in house_rows.values())
    house_rep_total = sum(row["rep"] for row in house_rows.values())
    review_rows = []
    for row in president_rows:
        county = row["county"]
        house = house_rows[county]
        president_total = row["total"]
        harris = row["harris"]
        trump = row["trump"]
        review_rows.append(
            {
                "county": county,
                "ward": county,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house["dem"]) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house["rep"]) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Oregon review rows compare President to the aggregate of U.S. House district contests by county, not to a single statewide down-ballot race.",
    )
    return review_rows, eta_analysis


def south_carolina_enr_house_totals(config, review):
    details = json.loads(local_source(config, review["sourceId"]).read_text(encoding="utf-8"))
    statewide = json.loads(local_source(config, review["statewideSourceId"]).read_text(encoding="utf-8"))
    detail_contests = {str(contest.get("K")): contest for contest in details.get("Contests", [])}
    statewide_contests = {str(contest.get("K")): contest for contest in statewide.get("Contests", [])}
    county_names = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
        for name in geometry_names_by_geoid(config).values()
    }
    by_county = defaultdict(lambda: defaultdict(int))
    for contest_key in review["downBallotContestKeys"]:
        detail_contest = detail_contests.get(str(contest_key))
        statewide_contest = statewide_contests.get(str(contest_key))
        if not detail_contest or not statewide_contest:
            raise ValueError(f"Could not find South Carolina ENR House contest {contest_key!r}")
        parties = statewide_contest.get("P", [])
        for county, votes in zip(detail_contest.get("P", []), detail_contest.get("V", [])):
            county_name = county_names.get(str(county).lower()) or f"{county} County"
            for index, party in enumerate(parties):
                if index >= len(votes):
                    continue
                party = normalize_party(party)
                if party == "DEM":
                    by_county[county_name]["dem"] += int_text(votes[index])
                elif party == "REP":
                    by_county[county_name]["rep"] += int_text(votes[index])
    return by_county


def review_charts_south_carolina_house_enr(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _precinct_rows = certified_results_south_carolina_enr_json(config)
    house_rows = south_carolina_enr_house_totals(config, review)
    expected_counties = {row["county"] for row in president_rows}
    missing = sorted(expected_counties - set(house_rows))
    if missing:
        raise ValueError(f"South Carolina House detail missing counties: {', '.join(missing)}")

    house_dem_total = sum(row["dem"] for row in house_rows.values())
    house_rep_total = sum(row["rep"] for row in house_rows.values())
    review_rows = []
    for row in president_rows:
        county = row["county"]
        house = house_rows[county]
        president_total = row["total"]
        harris = row["harris"]
        trump = row["trump"]
        review_rows.append(
            {
                "county": county,
                "ward": county,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house["dem"]) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house["rep"]) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "South Carolina review rows compare President to the aggregate of U.S. House district contests by county, not to a single statewide down-ballot race.",
    )
    return review_rows, eta_analysis


def louisiana_candidate_party_lookup(config, source_id):
    races = json.loads(local_source(config, source_id).read_text(encoding="utf-8"))["Races"]["Race"]
    lookup = {}
    for race in races:
        race_id = str(race["ID"])
        lookup[race_id] = {}
        for choice in race.get("Choice", []):
            desc = str(choice.get("Desc", ""))
            party = ""
            paren_match = re.search(r"\(([^)]+)\)\s*$", desc)
            if paren_match:
                party = paren_match.group(1)
            elif desc.endswith(" Democratic"):
                party = "DEM"
            elif desc.endswith(" Republican"):
                party = "REP"
            lookup[race_id][str(choice["ID"])] = normalize_party(party)
    return lookup


def review_charts_louisiana_federal_precinct_json(config):
    review = config["reviewCharts"]
    payload = json.loads(local_source(config, review["sourceId"]).read_text(encoding="utf-8"))
    party_lookup = louisiana_candidate_party_lookup(config, review["candidateSourceId"])
    precincts = defaultdict(lambda: defaultdict(int))
    house_dem_total = 0
    house_rep_total = 0

    for race in payload.get("races", []):
        race_id = str(race.get("id"))
        is_president = race_id == str(review["presidentRaceId"])
        is_house = race_id in {str(item) for item in review["downBallotRaceIds"]}
        if not is_president and not is_house:
            continue
        candidate_parties = party_lookup.get(race_id, {})
        for parish in race.get("parishes", []):
            parish_name = f"{parish['parishName']} Parish"
            for row in (parish.get("payload", {}).get("Precincts", {}).get("Precinct", []) or []):
                precinct = str(row.get("Precinct", "")).strip()
                if not precinct:
                    continue
                item = precincts[(parish_name, precinct)]
                item["county"] = parish_name
                item["ward"] = precinct
                if is_president:
                    item["president_total"] += sum(int_text(choice.get("VoteTotal")) for choice in row.get("Choice", []))
                for choice in row.get("Choice", []):
                    party = candidate_parties.get(str(choice.get("ID")), "")
                    votes = int_text(choice.get("VoteTotal"))
                    if is_president:
                        if party == "DEM":
                            item["harris"] += votes
                        elif party == "REP":
                            item["trump"] += votes
                    elif is_house:
                        if party == "DEM":
                            item["house_dem"] += votes
                            house_dem_total += votes
                        elif party == "REP":
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

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Louisiana review rows compare President to aggregate U.S. House jungle-primary contests by precinct; some districts do not include both major parties.",
    )
    return review_rows, eta_analysis


def kentucky_house_totals_from_certification(config, review):
    lines = [line.strip() for line in extract_pdf_text(local_source(config, review["sourceId"])).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
        for name in geometry_names_by_geoid(config).values()
    }
    for alias, canonical in review.get("countyAliases", {}).items():
        county_names[alias.lower()] = county_names.get(canonical.lower(), f"{canonical} County")
    county_prefixes = sorted(county_names, key=len, reverse=True)
    district_columns = {str(item["district"]): item["columns"] for item in review["districts"]}
    by_county = defaultdict(lambda: defaultdict(int))
    current_columns = None

    for line in lines:
        district_match = re.match(r"^(?P<district>\d+)(?:st|nd|rd|th) Congressional District$", line)
        if district_match:
            current_columns = district_columns.get(district_match.group("district"))
            continue
        if line.startswith("State Senator"):
            break
        if not current_columns or line.startswith(("Commonwealth of Kentucky", "US Representative", "United States Representative", "Republican Party", "Democratic Party", "Write-In")):
            continue
        if line.startswith("Total Votes"):
            continue

        upper_line = line.upper()
        county = None
        raw_county = None
        for prefix in county_prefixes:
            if upper_line.startswith(f"{prefix.upper()} "):
                county = county_names[prefix]
                raw_county = line[: len(prefix)]
                break
        if not county or not raw_county:
            continue
        values = [int_text(value) for value in re.findall(r"\d[\d,]*", line[len(raw_county) :])]
        if not values:
            continue
        dem_index = current_columns.get("dem")
        rep_index = current_columns.get("rep")
        if dem_index is not None and dem_index < len(values):
            by_county[county]["dem"] += values[dem_index]
        if rep_index is not None and rep_index < len(values):
            by_county[county]["rep"] += values[rep_index]

    expected_counties = set(geometry_names_by_geoid(config).values())
    missing = sorted(expected_counties - set(by_county))
    if missing:
        raise ValueError(f"Kentucky House certification rows missing counties: {', '.join(missing)}")
    return by_county


def review_charts_kentucky_house_pdf(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _precinct_rows = certified_results_kentucky_certification_pdf(config)
    house_rows = kentucky_house_totals_from_certification(config, review)
    house_dem_total = sum(row["dem"] for row in house_rows.values())
    house_rep_total = sum(row["rep"] for row in house_rows.values())

    review_rows = []
    for row in president_rows:
        county = row["county"]
        house = house_rows[county]
        president_total = row["total"]
        harris = row["harris"]
        trump = row["trump"]
        review_rows.append(
            {
                "county": county,
                "ward": county,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house["dem"]) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house["rep"]) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Kentucky review rows compare President to aggregate U.S. House district contests by county; some districts do not include both major parties.",
    )
    return review_rows, eta_analysis


def total_results_location_counties(config, election_info):
    def location_key(value):
        base = re.sub(r"\s+county$", "", value, flags=re.IGNORECASE).upper()
        return re.sub(r"[^A-Z0-9]+", "", base)

    county_names = {
        location_key(name): name
        for name in geometry_names_by_geoid(config).values()
    }
    location_names = {
        str(location_id): str(location.get("locationName", "")).strip()
        for location_id, location in (election_info.get("response", {}).get("locations", {}) or {}).items()
    }
    return {
        str(location_id): county_names[location_key(name)]
        for location_id, name in location_names.items()
        if location_key(name) in county_names
    }


def review_charts_total_results_house_county(config):
    review = config["reviewCharts"]
    result_payload = json.loads(local_source(config, review["sourceId"]).read_text(encoding="utf-8"))
    contest_list = json.loads(local_source(config, review["contestListSourceId"]).read_text(encoding="utf-8"))
    election_info = json.loads(local_source(config, review["electionInfoSourceId"]).read_text(encoding="utf-8"))
    if not result_payload.get("isOfficial") or not contest_list.get("isOfficial") or not election_info.get("isOfficial"):
        raise ValueError(f"{config['name']} TotalResults review sources are not all marked official")

    president_rows, _candidate_labels, _precinct_rows = certified_results_total_results_contest_json(config)
    location_counties = total_results_location_counties(config, election_info)
    contests = result_payload.get("response", {}).get("contests", {}) or {}
    metadata_contests = contest_list.get("response", {}).get("contests", {}) or {}
    house_rows = defaultdict(lambda: defaultdict(int))
    for contest_id in review["downBallotContestIds"]:
        contest = contests.get(str(contest_id))
        metadata = metadata_contests.get(str(contest_id))
        if not contest or not metadata:
            raise ValueError(f"Could not find {config['name']} TotalResults House contest {contest_id!r}")
        choice_parties = {
            str(choice_id): str(choice.get("partyID", ""))
            for choice_id, choice in (metadata.get("choices", {}) or {}).items()
        }
        for location_id, location in (contest.get("locations", {}) or {}).items():
            county = location_counties.get(str(location_id))
            if not county:
                continue
            for choice in location.get("choices", []) or []:
                party_id = choice_parties.get(str(choice.get("choiceID")), "")
                votes = int_text(choice.get("totalVotes"))
                if party_id == str(review["partyIds"]["dem"]):
                    house_rows[county]["dem"] += votes
                elif party_id == str(review["partyIds"]["rep"]):
                    house_rows[county]["rep"] += votes

    expected_counties = {row["county"] for row in president_rows}
    missing = sorted(expected_counties - set(house_rows))
    if missing:
        raise ValueError(f"{config['name']} TotalResults House contests missing counties: {', '.join(missing)}")

    house_dem_total = sum(row["dem"] for row in house_rows.values())
    house_rep_total = sum(row["rep"] for row in house_rows.values())
    review_rows = []
    for row in president_rows:
        county = row["county"]
        house = house_rows[county]
        president_total = row["total"]
        harris = row["harris"]
        trump = row["trump"]
        review_rows.append(
            {
                "county": county,
                "ward": county,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - house["dem"]) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - house["rep"]) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        house_dem_total,
        house_rep_total,
    )
    eta_analysis["warning"] = review.get(
        "warning",
        f"{config['name']} review rows compare President to aggregate U.S. House district contests by county.",
    )
    return review_rows, eta_analysis


def review_charts_total_results_precinct_vote_share(config):
    review = config["reviewCharts"]
    payload = json.loads(local_source(config, review["sourceId"]).read_text(encoding="utf-8"))
    president_rows, _candidate_labels, _precinct_rows = certified_results_total_results_contest_json(config)
    certified_by_county = {row["county"]: row for row in president_rows}
    county_names = {
        re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", name, flags=re.IGNORECASE).upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    choice_map = {
        str(config["certifiedResults"]["majorCandidates"]["trump"]["choiceId"]): "trump",
        str(config["certifiedResults"]["majorCandidates"]["harris"]["choiceId"]): "harris",
    }

    review_rows = []
    parsed_by_county = defaultdict(lambda: defaultdict(int))
    for county_result in payload.get("countyResults", []):
        county_key = re.sub(r"[^A-Z0-9]+", "", str(county_result.get("county", "")).upper())
        county = county_names.get(county_key)
        if county not in certified_by_county:
            raise ValueError(f"{config['name']} precinct source has unexpected county {county!r}")
        contest = county_result.get("presidentContest") or {}
        for location_id, location in (contest.get("locations", {}) or {}).items():
            totals = defaultdict(int)
            for choice in location.get("choices", []) or []:
                key = choice_map.get(str(choice.get("choiceID")), "other")
                totals[key] += int_text(choice.get("totalVotes"))
            total = int_text(location.get("totalVotes"))
            if not total:
                continue
            harris = totals["harris"]
            trump = totals["trump"]
            review_rows.append(
                {
                    "county": county,
                    "ward": str(location_id),
                    "total": total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / total) * 100),
                    "trumpShare": round2((trump / total) * 100),
                    "demDropoff": 0,
                    "repDropoff": 0,
                }
            )
            parsed_by_county[county]["total"] += total
            parsed_by_county[county]["harris"] += harris
            parsed_by_county[county]["trump"] += trump

    expected_counties = set(certified_by_county)
    parsed_counties = set(parsed_by_county)
    if parsed_counties != expected_counties:
        raise ValueError(
            f"{config['name']} precinct source county coverage mismatch: "
            f"missing={sorted(expected_counties - parsed_counties)} extra={sorted(parsed_counties - expected_counties)}"
        )
    mismatches = []
    for county, certified in certified_by_county.items():
        parsed = parsed_by_county[county]
        for key in ("total", "harris", "trump"):
            if parsed[key] != certified[key]:
                mismatches.append((county, key, parsed[key], certified[key]))
    if mismatches:
        raise ValueError(f"{config['name']} precinct rows do not reconcile to certified counties: {mismatches[:10]}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["coverageNote"] = review.get(
        "coverageNote",
        f"Official {config['name']} TotalResults county-scoped President rows are loaded at local reporting-unit level for vote-share advisory review. Down-ballot advisory flags are suppressed until same-grain comparison rows are mapped.",
    )
    eta_analysis["warning"] = review.get(
        "warning",
        f"{config['name']} review rows are official presidential local reporting-unit vote-share rows only; down-ballot flags are suppressed.",
    )
    return review_rows, eta_analysis


def review_charts_ohio_precinct_vote_share(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    sheet_name = review.get("sheetName", "President and Vice President")
    rows = list(iter_worksheet_rows(path, sheet_name))
    header = rows[review.get("headerRow", 2) - 1]
    column_index = {str(name).strip(): index for index, name in enumerate(header) if name}

    def candidate_column(rule):
        for header_value, index in column_index.items():
            if rule.get("candidateContains", "").lower() in header_value.lower():
                return index
        raise ValueError(f"Ohio review source missing candidate column matching {rule}")

    trump_index = candidate_column(review["majorCandidates"]["trump"])
    harris_index = candidate_column(review["majorCandidates"]["harris"])
    total_index = column_index[review.get("totalColumn", "Ballots Counted")]
    county_index = column_index["County Name"]
    precinct_index = column_index["Precinct Name"]
    code_index = column_index["Precinct Code"]
    review_rows = []
    for row in rows[review.get("dataStartRow", 5) - 1 :]:
        county = str(row[county_index] if len(row) > county_index else "").strip()
        precinct = str(row[precinct_index] if len(row) > precinct_index else "").strip()
        code = str(row[code_index] if len(row) > code_index else "").strip()
        if not county or county in {"Total", "Percentage"}:
            continue
        total = int_text(row[total_index] if len(row) > total_index else 0)
        if not total:
            continue
        harris = int_text(row[harris_index] if len(row) > harris_index else 0)
        trump = int_text(row[trump_index] if len(row) > trump_index else 0)
        review_rows.append(
            {
                "county": county,
                "ward": f"{precinct} ({code})" if code else precinct,
                "total": total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / total) * 100),
                "trumpShare": round2((trump / total) * 100),
                "demDropoff": 0,
                "repDropoff": 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["warning"] = review.get(
        "warning",
        "Vote-share review is loaded, but no same-row down-ballot comparison contest is mapped yet.",
    )
    return review_rows, eta_analysis


def review_charts_oregon_precinct_vote_share(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    review_rows = []
    expected_total = review.get("expectedCandidateTotal")
    parsed_total = 0
    skipped_counties = []

    for sheet_name in review.get("sheets", first_worksheet_names(path)):
        rows = list(iter_worksheet_rows(path, sheet_name))
        header_index = None
        for index, row in enumerate(rows):
            if row and str(row[0] or "").strip() == review.get("contestHeader", "President"):
                header_index = index
                break
        if header_index is None:
            skipped_counties.append(sheet_name)
            continue
        header = rows[header_index]
        column_index = {str(name).strip(): index for index, name in enumerate(header) if name}
        precinct_index = column_index[review.get("precinctColumn", "Precinct")]
        harris_index = column_index[review["columns"]["harris"]]
        trump_index = column_index[review["columns"]["trump"]]
        other_indexes = [
            column_index[column]
            for column in review["columns"].get("other", [])
            if column in column_index
        ]
        county_rows = 0
        for row in rows[header_index + 1 :]:
            precinct = str(row[precinct_index] if len(row) > precinct_index else "").strip()
            if not precinct or precinct.lower() == "countywide" or precinct.upper() == "TOTALS":
                continue
            harris = int_text(row[harris_index] if len(row) > harris_index else 0)
            trump = int_text(row[trump_index] if len(row) > trump_index else 0)
            other = sum(int_text(row[index] if len(row) > index else 0) for index in other_indexes)
            total = harris + trump + other
            if not total:
                continue
            parsed_total += total
            county_rows += 1
            review_rows.append(
                {
                    "county": sheet_name,
                    "ward": precinct,
                    "total": total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / total) * 100),
                    "trumpShare": round2((trump / total) * 100),
                    "demDropoff": 0,
                    "repDropoff": 0,
                }
            )
        if not county_rows:
            skipped_counties.append(sheet_name)

    if expected_total is not None:
        minimum = expected_total - review.get("candidateTotalTolerance", 0)
        maximum = expected_total + review.get("candidateTotalTolerance", 0)
        if not (minimum <= parsed_total <= maximum):
            raise ValueError(f"Oregon precinct vote-share total {parsed_total} outside expected range {minimum}..{maximum}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["warning"] = review.get(
        "warning",
        "Oregon precinct vote-share rows are loaded where the official workbook publishes precinct candidate totals; no same-row down-ballot comparison is mapped.",
    )
    eta_analysis["partialReviewCoverage"] = {
        "skippedCountySheets": skipped_counties,
        "parsedCandidateTotal": parsed_total,
    }
    return review_rows, eta_analysis


def hawaii_media_county_for_precinct(prefix, county_prefixes):
    for county, ranges in county_prefixes.items():
        for item in ranges:
            if "-" in item:
                start, end = item.split("-", 1)
                if int(start) <= int(prefix) <= int(end):
                    return county
            elif prefix == item:
                return county
    raise ValueError(f"Hawaii media export precinct prefix {prefix} is not mapped to a county")


def review_charts_hawaii_media_precinct(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    county_prefixes = review["countyPrefixMap"]
    president_contest = review.get("presidentContestName", "President and Vice President")
    down_ballot_contest = review.get("downBallotContestName", "U.S. Senator")
    candidates = review["candidates"]
    by_precinct = defaultdict(lambda: defaultdict(int))
    skipped_summary_rows = 0

    with path.open("r", encoding=review.get("encoding", "utf-16"), newline="") as handle:
        next(handle, None)
        for row in csv.DictReader(handle):
            precinct = str(row.get('#"Precinct_Name"', "")).strip()
            match = re.match(r"^(\d{2})-", precinct)
            if not match:
                skipped_summary_rows += 1
                continue
            county = hawaii_media_county_for_precinct(match.group(1), county_prefixes)
            contest = str(row.get("Contest_title", "")).strip()
            candidate = str(row.get("Candidate_name", "")).upper()
            votes = int_text(row.get("Mail votes")) + int_text(row.get("In-Person votes"))
            item = by_precinct[(county, precinct)]
            if contest == president_contest:
                if candidates["harris"].upper() in candidate:
                    item["harris"] += votes
                elif candidates["trump"].upper() in candidate:
                    item["trump"] += votes
                else:
                    item["other"] += votes
            elif contest == down_ballot_contest:
                if candidates["senateDem"].upper() in candidate:
                    item["senateDem"] += votes
                elif candidates["senateRep"].upper() in candidate:
                    item["senateRep"] += votes

    review_rows = []
    county_totals = defaultdict(int)
    senate_dem_total = 0
    senate_rep_total = 0
    for (county, precinct), item in sorted(by_precinct.items()):
        harris = item["harris"]
        trump = item["trump"]
        total = harris + trump + item["other"]
        if not total:
            continue
        senate_dem = item["senateDem"]
        senate_rep = item["senateRep"]
        county_totals[county] += total
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / total) * 100),
                "trumpShare": round2((trump / total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    for county, expected_total in review.get("expectedCountyTotals", {}).items():
        actual_total = county_totals.get(county, 0)
        if actual_total != expected_total:
            raise ValueError(f"Hawaii media export {county} presidential total {actual_total} != expected {expected_total}")

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        senate_dem_total,
        senate_rep_total,
    )
    eta_analysis["sourceDetail"] = "Hawaii media export precinct rows, President compared with U.S. Senator by precinct."
    eta_analysis["mediaExportSkippedSummaryRows"] = skipped_summary_rows
    return review_rows, eta_analysis


def review_charts_illinois_precinct_vote_share(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    aliases = {
        key.upper(): value
        for key, value in config.get("certifiedResults", {}).get("jurisdictionAliases", {}).items()
    }
    contest_name = review.get("contestName", "PRESIDENT AND VICE PRESIDENT").upper()
    excluded_candidates = [name.upper() for name in review.get("excludedCandidates", [])]
    by_precinct = defaultdict(lambda: defaultdict(int))

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("ContestName", "")).strip().upper() != contest_name:
                continue
            county = aliases.get(str(row.get("JurisName", "")).strip().upper(), title_county(row.get("JurisName")))
            precinct = str(row.get("PrecinctName", "")).strip()
            candidate = str(row.get("CandidateName", "")).strip()
            candidate_upper = candidate.upper()
            if not county or not precinct:
                continue
            item = by_precinct[(county, precinct)]
            item["county"] = county
            item["ward"] = precinct
            votes = int_text(row.get("VoteCount"))
            item["total"] += votes
            if any(excluded in candidate_upper for excluded in excluded_candidates):
                continue
            if new_york_column_matches(candidate, "", review["majorCandidates"]["trump"]):
                item["trump"] += votes
            elif new_york_column_matches(candidate, "", review["majorCandidates"]["harris"]):
                item["harris"] += votes

    review_rows = []
    for (_county, _precinct), item in sorted(by_precinct.items()):
        total = item["total"]
        if not total:
            continue
        harris = item["harris"]
        trump = item["trump"]
        review_rows.append(
            {
                "county": item["county"],
                "ward": item["ward"],
                "total": total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / total) * 100),
                "trumpShare": round2((trump / total) * 100),
                "demDropoff": 0,
                "repDropoff": 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["warning"] = review.get(
        "warning",
        "Vote-share review is loaded, but no same-row down-ballot comparison contest is mapped yet.",
    )
    return review_rows, eta_analysis


def review_charts_tennessee_precinct_xlsx(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    columns = review["columns"]
    column_index, rows = read_sheet_rows(path, review.get("sheet", "SOFFICEL"))
    candidate_slots = int(review.get("candidateSlots", 10))
    by_precinct = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})

    def add_candidate_votes(target, row, candidate_rules):
        for slot in range(1, candidate_slots + 1):
            name_index = column_index.get(f"{columns['candidatePrefix']}{slot}")
            vote_index = column_index.get(f"{columns['votesPrefix']}{slot}")
            if name_index is None or vote_index is None or name_index >= len(row):
                continue
            candidate = row[name_index]
            if not candidate:
                continue
            votes = int_text(row[vote_index] if vote_index < len(row) else 0)
            target["total"] += votes
            matched = False
            for key, rule in candidate_rules.items():
                if new_york_column_matches(candidate, "", rule):
                    target[key] += votes
                    matched = True
                    break
            if not matched:
                target["other"] += votes

    for row in rows:
        office = str(row[column_index[columns["office"]]] or "").strip()
        if office not in {review["presidentOfficeName"], review["downBallotOfficeName"]}:
            continue
        county = str(row[column_index[columns["county"]]] or "").strip()
        precinct_code = str(row[column_index[columns["precinctCode"]]] or "").strip()
        precinct = str(row[column_index[columns["precinct"]]] or "").strip()
        if not county or not precinct:
            continue
        item = by_precinct[(f"{county} County", precinct_code, precinct)]
        item["county"] = f"{county} County"
        item["ward"] = f"{precinct_code} {precinct}".strip()
        if office == review["presidentOfficeName"]:
            add_candidate_votes(item["president"], row, review["majorCandidates"])
        else:
            add_candidate_votes(item["downBallot"], row, review["downBallotCandidates"])

    review_rows = []
    missing_down_ballot = []
    senate_dem_total = 0
    senate_rep_total = 0
    for (_county, _code, _precinct), item in sorted(by_precinct.items()):
        president_total = item["president"]["total"]
        if not president_total:
            continue
        down_ballot = item["downBallot"]
        if not down_ballot["dem"] and not down_ballot["rep"]:
            missing_down_ballot.append(item["ward"])
            continue
        harris = item["president"]["harris"]
        trump = item["president"]["trump"]
        senate_dem = down_ballot["dem"]
        senate_rep = down_ballot["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    if missing_down_ballot and review.get("requireDownBallot", True):
        examples = ", ".join(missing_down_ballot[:10])
        raise ValueError(f"Tennessee review rows missing U.S. Senate match for {len(missing_down_ballot)} precincts: {examples}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_maryland_precinct_csv(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    vote_columns = review.get(
        "voteColumns",
        [
            "Early Votes",
            "Election Night Votes",
            "Mail-In Ballot 1 Votes",
            "Provisional Votes",
            "Mail-In Ballot 2 Votes",
        ],
    )
    by_precinct = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})

    def row_votes(row):
        return sum(int_text(row.get(column)) for column in vote_columns)

    def add_candidate_votes(target, row, candidate_rules):
        votes = row_votes(row)
        target["total"] += votes
        candidate = row.get("Candidate Name", "")
        matched = False
        for key, rule in candidate_rules.items():
            if new_york_column_matches(candidate, row.get("Party", ""), rule):
                target[key] += votes
                matched = True
                break
        if not matched:
            target["other"] += votes

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            office = str(row.get("Office Name", "")).strip()
            if office not in {review["presidentOfficeName"], review["downBallotOfficeName"]}:
                continue
            county = str(row.get("County Name", "")).strip()
            precinct = str(row.get("Election District - Precinct", "")).strip()
            if not county or not precinct:
                continue
            item = by_precinct[(county, precinct)]
            item["county"] = county
            item["ward"] = precinct
            if office == review["presidentOfficeName"]:
                add_candidate_votes(item["president"], row, review["majorCandidates"])
            else:
                add_candidate_votes(item["downBallot"], row, review["downBallotCandidates"])

    review_rows = []
    missing_down_ballot = []
    senate_dem_total = 0
    senate_rep_total = 0
    for (_county, _precinct), item in sorted(by_precinct.items()):
        president_total = item["president"]["total"]
        if not president_total:
            continue
        down_ballot = item["downBallot"]
        if not down_ballot["dem"] and not down_ballot["rep"]:
            missing_down_ballot.append(f"{item['county']} {item['ward']}")
            continue
        harris = item["president"]["harris"]
        trump = item["president"]["trump"]
        senate_dem = down_ballot["dem"]
        senate_rep = down_ballot["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    if missing_down_ballot and review.get("requireDownBallot", True):
        examples = ", ".join(missing_down_ballot[:10])
        raise ValueError(f"Maryland review rows missing U.S. Senator match for {len(missing_down_ballot)} precincts: {examples}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_north_carolina_precinct_zip(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    member_name = review.get("member", "results_pct_20241105.txt")
    vote_columns = review.get(
        "voteColumns",
        ["Election Day", "Early Voting", "Absentee by Mail", "Provisional"],
    )
    by_precinct = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})

    def row_votes(row):
        return sum(int_text(row.get(column)) for column in vote_columns)

    def add_candidate_votes(target, row, candidate_rules):
        votes = row_votes(row)
        target["total"] += votes
        candidate = row.get("Choice", "")
        matched = False
        for key, rule in candidate_rules.items():
            if new_york_column_matches(candidate, row.get("Choice Party", ""), rule):
                target[key] += votes
                matched = True
                break
        if not matched:
            target["other"] += votes

    with zipfile.ZipFile(path) as archive:
        with archive.open(member_name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            for row in csv.DictReader(text, delimiter="\t"):
                contest = str(row.get("Contest Group ID", "")).strip()
                if contest not in {str(review["presidentContestId"]), str(review["downBallotContestId"])}:
                    continue
                county = title_county(row.get("County", ""))
                precinct = str(row.get("Precinct", "")).strip()
                if not county or not precinct:
                    continue
                item = by_precinct[(county, precinct)]
                item["county"] = county
                item["ward"] = precinct
                if contest == str(review["presidentContestId"]):
                    add_candidate_votes(item["president"], row, review["majorCandidates"])
                else:
                    add_candidate_votes(item["downBallot"], row, review["downBallotCandidates"])

    review_rows = []
    missing_down_ballot = []
    senate_dem_total = 0
    senate_rep_total = 0
    for (_county, _precinct), item in sorted(by_precinct.items()):
        president_total = item["president"]["total"]
        if not president_total:
            continue
        down_ballot = item["downBallot"]
        if not down_ballot["dem"] and not down_ballot["rep"]:
            missing_down_ballot.append(f"{item['county']} {item['ward']}")
            continue
        harris = item["president"]["harris"]
        trump = item["president"]["trump"]
        senate_dem = down_ballot["dem"]
        senate_rep = down_ballot["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    if missing_down_ballot and review.get("requireDownBallot", True):
        examples = ", ".join(missing_down_ballot[:10])
        raise ValueError(f"North Carolina review rows missing Governor match for {len(missing_down_ballot)} precincts: {examples}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_wyoming_precinct_xlsx(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    workbook_name = review["workbook"]
    with zipfile.ZipFile(path) as archive:
        workbook_bytes = archive.read(workbook_name)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
        handle.write(workbook_bytes)
        workbook_path = Path(handle.name)
    try:
        review_rows = []
        senate_dem_total = 0
        senate_rep_total = 0
        for sheet_name in review.get("sheets", first_worksheet_names(workbook_path)):
            rows = list(iter_worksheet_rows(workbook_path, sheet_name))
            if len(rows) <= review.get("dataStartRow", 5) - 1:
                continue
            for row in rows[review.get("dataStartRow", 5) - 1 :]:
                precinct = wyoming_precinct_label(row[review.get("precinctColumn", 0)] if row else "")
                if not precinct or precinct.lower() == "total":
                    break
                trump = int_text(row_value(row, review["columns"]["trump"]))
                harris = int_text(row_value(row, review["columns"]["harris"]))
                president_other = sum(int_text(row_value(row, index)) for index in review["columns"].get("presidentOther", []))
                president_total = trump + harris + president_other
                if not president_total:
                    continue
                senate_rep = int_text(row_value(row, review["columns"]["senateRep"]))
                senate_dem = int_text(row_value(row, review["columns"]["senateDem"]))
                senate_rep_total += senate_rep
                senate_dem_total += senate_dem
                review_rows.append(
                    {
                        "county": f"{sheet_name} County",
                        "ward": precinct,
                        "total": president_total,
                        "harris": harris,
                        "trump": trump,
                        "harrisShare": round2((harris / president_total) * 100),
                        "trumpShare": round2((trump / president_total) * 100),
                        "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                        "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
                    }
                )
    finally:
        workbook_path.unlink(missing_ok=True)

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def row_value(row, index):
    return row[index] if index < len(row) else 0


def wyoming_precinct_label(value):
    if not value:
        return ""
    if hasattr(value, "month") and hasattr(value, "day") and getattr(value, "year", None) == 2022:
        return f"{value.month:02d}-{value.day:02d}"
    return str(value).strip()


def review_charts_alaska_enr_precinct_csv(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    exclude_districts = set(str(value).zfill(2) for value in review.get("excludeDistricts", []))
    by_precinct = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})

    def district_code(row):
        precinct_id = str(row.get("Pct_Id") or "").strip()
        if precinct_id:
            return precinct_id.split("-")[0].zfill(2)
        match = re.match(r"District\s+(\d+)\s+-\s+", str(row.get("Precinct_name") or ""))
        return match.group(1).zfill(2) if match else ""

    def add_candidate_votes(target, row, candidate_rules):
        votes = int_text(row.get("total_votes"))
        target["total"] += votes
        candidate = row.get("candidate_name", "")
        matched = False
        for key, rule in candidate_rules.items():
            if new_york_column_matches(candidate, row.get("Party_Code", ""), rule):
                target[key] += votes
                matched = True
                break
        if not matched:
            target["other"] += votes

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            contest = str(row.get("Contest_title", "")).strip()
            if contest not in {review["presidentContestTitle"], review["downBallotContestTitle"]}:
                continue
            district = district_code(row)
            if not district or district in exclude_districts:
                continue
            precinct = str(row.get("Precinct_name", "")).strip()
            precinct_id = str(row.get("Pct_Id", "")).strip()
            if not precinct:
                continue
            item = by_precinct[(district, precinct_id, precinct)]
            item["county"] = f"State House District {int(district)}"
            item["ward"] = precinct
            if contest == review["presidentContestTitle"]:
                add_candidate_votes(item["president"], row, review["majorCandidates"])
            else:
                add_candidate_votes(item["downBallot"], row, review["downBallotCandidates"])

    review_rows = []
    missing_down_ballot = []
    senate_dem_total = 0
    senate_rep_total = 0
    for (_district, _precinct_id, _precinct), item in sorted(by_precinct.items()):
        president_total = item["president"]["total"]
        if not president_total:
            continue
        down_ballot = item["downBallot"]
        if not down_ballot["dem"] and not down_ballot["rep"]:
            missing_down_ballot.append(item["ward"])
            continue
        harris = item["president"]["harris"]
        trump = item["president"]["trump"]
        senate_dem = down_ballot["dem"]
        senate_rep = down_ballot["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    if missing_down_ballot and review.get("requireDownBallot", True):
        examples = ", ".join(missing_down_ballot[:10])
        raise ValueError(f"Alaska review rows missing U.S. Representative match for {len(missing_down_ballot)} precincts: {examples}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_rhode_island_summary_xlsx(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    column_index, rows = read_sheet_rows(path, review.get("sheet", "Candidate_Breakout"))
    town_county_map = review.get("townCountyMap") or config["certifiedResults"]["townCountyMap"]
    president_contest = review.get("presidentContest", "Presidential Electors For:")
    down_ballot_contest = review.get("downBallotContest", "Senator in Congress")
    contest_column = column_index["Contest"]
    label_column = column_index["City/Town - Precinct"]
    candidate_column = column_index["Candidate"]
    party_column = column_index["Party"]
    total_column = column_index["Total"]
    by_precinct = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})

    def add_candidate_votes(target, row, candidate_rules):
        votes = int_text(row_value(row, total_column))
        target["total"] += votes
        candidate = row_value(row, candidate_column)
        party = row_value(row, party_column)
        for key, rule in candidate_rules.items():
            if new_york_column_matches(candidate, party, rule):
                target[key] += votes
                return
        target["other"] += votes

    for row in rows:
        contest = str(row_value(row, contest_column) or "").strip()
        if contest not in {president_contest, down_ballot_contest}:
            continue
        precinct_label = str(row_value(row, label_column) or "").strip()
        if not precinct_label:
            continue
        town = rhode_island_town_from_precinct(precinct_label, town_county_map)
        if not town:
            continue
        county = town_county_map[town]
        item = by_precinct[(county, precinct_label)]
        item["county"] = county
        item["ward"] = precinct_label
        if contest == president_contest:
            add_candidate_votes(item["president"], row, review["majorCandidates"])
        else:
            add_candidate_votes(item["downBallot"], row, review["downBallotCandidates"])

    review_rows = []
    missing_down_ballot = []
    senate_dem_total = 0
    senate_rep_total = 0
    for (_county, _precinct_label), item in sorted(by_precinct.items()):
        president_total = item["president"]["total"]
        if not president_total:
            continue
        down_ballot = item["downBallot"]
        if not down_ballot["dem"] and not down_ballot["rep"]:
            missing_down_ballot.append(item["ward"])
            continue
        harris = item["president"]["harris"]
        trump = item["president"]["trump"]
        senate_dem = down_ballot["dem"]
        senate_rep = down_ballot["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    if missing_down_ballot and review.get("requireDownBallot", False):
        examples = ", ".join(missing_down_ballot[:10])
        raise ValueError(f"Rhode Island review rows missing U.S. Senate match for {len(missing_down_ballot)} precincts: {examples}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_indiana_enr_county_json(config):
    review = config["reviewCharts"]
    settings_path = local_source(config, review["settingsSourceId"])
    settings = json.loads(settings_path.read_text(encoding="utf-8-sig")).get("Root", {})
    if settings.get("Certified") != "T":
        raise ValueError(f"Indiana ENR settings are not marked certified: {settings_path}")
    if settings.get("ElectionType") != "G" or settings.get("CurrentElection") != review.get("electionDate", "11/05/2024"):
        raise ValueError(f"Indiana ENR settings do not describe the expected general election: {settings_path}")

    def as_list(value):
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    def candidate_key(candidate, candidate_rules):
        name = str(candidate.get("NAME_ON_BALLOT") or candidate.get("CandidateName") or "")
        party = str(candidate.get("PARTY") or candidate.get("PARTY_ABBREV") or "")
        for key, rule in candidate_rules.items():
            if new_york_column_matches(name, party, rule):
                return key
        return "other"

    def county_totals(source_id, office_category_id, candidate_rules):
        payload = json.loads(local_source(config, source_id).read_text(encoding="utf-8-sig"))
        office_category = payload.get("Root", {}).get("OfficeCategory", {})
        if str(office_category.get("OFFICECATEGORYID")) != str(office_category_id):
            raise ValueError(f"Indiana ENR office category does not match configured category {office_category_id}")
        county_names = geometry_names_by_geoid(config)
        totals_by_county = {}
        for region in as_list(office_category.get("Regions", {}).get("Region")):
            geoid = str(region.get("MAP_FIPS") or "")
            county = county_names.get(geoid) or region.get("MAP_JURISDICTION_NAME")
            if not county:
                raise ValueError("Indiana ENR region is missing a county name/FIPS")
            totals = defaultdict(int)
            candidates = as_list(region.get("RegionSummary", {}).get("Race", {}).get("Candidates", {}).get("Candidate"))
            for candidate in candidates:
                votes = int(candidate.get("TOTAL") or candidate.get("TOTAL_VOTES") or 0)
                totals["total"] += votes
                totals[candidate_key(candidate, candidate_rules)] += votes
            totals_by_county[county] = totals
        return totals_by_county

    president = county_totals(
        review["sourceId"],
        review.get("presidentOfficeCategoryId", "1019"),
        review["majorCandidates"],
    )
    down_ballot = county_totals(
        review["downBallotSourceId"],
        review.get("downBallotOfficeCategoryId", "1006"),
        review["downBallotCandidates"],
    )

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        if county not in down_ballot:
            continue
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = down_ballot[county]["dem"]
        senate_rep = down_ballot[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_clarity_enr_county_json(config):
    review = config["reviewCharts"]
    details_path = local_source(config, review["sourceId"])
    sum_path = local_source(config, review["statewideSourceId"])
    details = json.loads(details_path.read_text(encoding="utf-8"))
    statewide = json.loads(sum_path.read_text(encoding="utf-8"))
    state_name = config["name"]

    def contest(payload, contest_key, source_label):
        item = next(
            (contest for contest in payload.get("Contests", []) if str(contest.get("K")) == str(contest_key)),
            None,
        )
        if item is None:
            raise ValueError(f"Could not find {state_name} ENR {source_label} contest {contest_key!r}")
        return item

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }

    def candidate_keys(summary_contest, candidate_rules):
        keys = []
        for index, candidate in enumerate(summary_contest.get("CH", [])):
            party = summary_contest.get("P", [""])[index]
            key = "other"
            for candidate_key, rule in candidate_rules.items():
                if new_york_column_matches(candidate, party, rule):
                    key = candidate_key
                    break
            keys.append(key)
        return keys

    def county_totals(contest_key, candidate_rules, label):
        detail_contest = contest(details, contest_key, f"{label} detail")
        summary_contest = contest(statewide, contest_key, f"{label} summary")
        keys = candidate_keys(summary_contest, candidate_rules)
        totals_by_county = {}
        parsed_candidate_totals = [0 for _candidate in summary_contest.get("CH", [])]
        for county, votes in zip(detail_contest.get("P", []), detail_contest.get("V", [])):
            county_name = county_names.get(str(county).upper()) or f"{county} County"
            totals = defaultdict(int)
            for index, key in enumerate(keys):
                value = int(votes[index] or 0) if index < len(votes) else 0
                totals[key] += value
                if index < len(parsed_candidate_totals):
                    parsed_candidate_totals[index] += value
                totals["total"] += value
            totals_by_county[county_name] = totals

        reported_candidate_totals = [int(value or 0) for value in summary_contest.get("V", [])]
        if parsed_candidate_totals != reported_candidate_totals:
            raise ValueError(
                f"{state_name} ENR {label} county candidate totals do not match statewide summary: "
                f"{parsed_candidate_totals} != {reported_candidate_totals}"
            )
        reported_total = int(summary_contest.get("T") or 0)
        parsed_total = sum(item["total"] for item in totals_by_county.values())
        if parsed_total != reported_total:
            raise ValueError(
                f"{state_name} ENR {label} county total does not match statewide summary: "
                f"{parsed_total} != {reported_total}"
            )
        return totals_by_county

    president = county_totals(
        review["presidentContestKey"],
        review["majorCandidates"],
        "president",
    )
    down_ballot = county_totals(
        review["downBallotContestKey"],
        review["downBallotCandidates"],
        "down-ballot",
    )

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    missing_down_ballot = []
    for county in sorted(president):
        if county not in down_ballot:
            missing_down_ballot.append(county)
            continue
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = down_ballot[county]["dem"]
        senate_rep = down_ballot[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    if missing_down_ballot:
        examples = ", ".join(missing_down_ballot[:10])
        raise ValueError(f"{state_name} review rows missing down-ballot contest for {len(missing_down_ballot)} counties: {examples}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_nevada_statewide_html(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    document = path.read_text(encoding="utf-8")
    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", name, flags=re.IGNORECASE).upper()): name
        for name in geometry_names_by_geoid(config).values()
    }

    def contest_totals(contest_title, candidate_rules):
        contest_heading = re.search(
            rf"<strong>\s*{re.escape(contest_title)}\s*</strong>.*?"
            r"<table[^>]*>(?P<table>.*?)</table>",
            document,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not contest_heading:
            raise ValueError(f"Could not find Nevada {contest_title!r} results table in {path}")
        table = contest_heading.group("table")
        header_match = re.search(r"<thead>.*?<tr>(?P<header>.*?)</tr>.*?</thead>", table, flags=re.DOTALL | re.IGNORECASE)
        if not header_match:
            raise ValueError(f"Nevada {contest_title!r} table missing header in {path}")
        headers = [clean_html_cell(value) for value in re.findall(r"<th[^>]*>(.*?)</th>", header_match.group("header"), flags=re.DOTALL)]
        county_headers = headers[3:]
        county_columns = []
        for county in county_headers:
            key = re.sub(r"[^A-Z0-9]+", "", county.upper())
            county_name = county_lookup.get(key)
            if not county_name:
                raise ValueError(f"Could not match Nevada county column {county!r} to geometry")
            county_columns.append(county_name)

        totals_by_county = {county: defaultdict(int) for county in county_columns}
        row_pattern = re.compile(r"<tr>\s*(?P<row>.*?)\s*</tr>", flags=re.DOTALL | re.IGNORECASE)
        for row_match in row_pattern.finditer(table):
            cells = [clean_html_cell(value) for value in re.findall(r"<td[^>]*>(.*?)</td>", row_match.group("row"), flags=re.DOTALL)]
            if len(cells) < len(headers):
                continue
            candidate = cells[0]
            votes = [int_text(value) for value in cells[2 : 3 + len(county_columns)]]
            statewide_total = votes[0]
            county_votes = votes[1:]
            if sum(county_votes) != statewide_total:
                raise ValueError(f"Nevada statewide total mismatch for {contest_title} / {candidate}: {sum(county_votes)} != {statewide_total}")
            key = "other"
            for candidate_key, rule in candidate_rules.items():
                if new_york_column_matches(candidate, "", rule):
                    key = candidate_key
                    break
            for county, count in zip(county_columns, county_votes):
                totals_by_county[county][key] += count
                totals_by_county[county]["total"] += count

        missing_counties = sorted(set(county_lookup.values()) - set(totals_by_county))
        if missing_counties:
            raise ValueError(f"Nevada {contest_title!r} table missing county columns: {', '.join(missing_counties)}")
        return totals_by_county

    president = contest_totals(
        review.get("presidentContest", "President and Vice President of the United States"),
        review["majorCandidates"],
    )
    down_ballot = contest_totals(
        review.get("downBallotContest", "United States Senator"),
        review["downBallotCandidates"],
    )

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = down_ballot[county]["dem"]
        senate_rep = down_ballot[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_nevada_clark_cvr(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    source = source_map(config)[review["sourceId"]]
    county = review.get("county", "Clark County")
    certified_rows, _candidate_labels, _precinct_rows = certified_results_nevada_statewide_html(config)
    certified = next((row for row in certified_rows if row["county"] == county), None)
    if not certified:
        raise ValueError(f"Nevada Clark CVR parser could not find certified county row for {county}")

    def cvr_vote(value):
        value = str(value or "").strip()
        if value.startswith('="') and value.endswith('"'):
            value = value[2:-1]
        return int(value) if value in {"0", "1"} else 0

    def candidate_key(candidate, rules):
        for key, rule in rules.items():
            if new_york_column_matches(candidate, "", rule):
                return key
        return "other"

    by_precinct = defaultdict(lambda: defaultdict(int))
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Nevada Clark CVR ZIP should contain one CSV, found {csv_names}")
        with archive.open(csv_names[0]) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline=""))
            try:
                _election_row = next(reader)
                contest_row = next(reader)
                candidate_row = next(reader)
                header_row = next(reader)
            except StopIteration as error:
                raise ValueError(f"Nevada Clark CVR CSV is missing header rows: {csv_names[0]}") from error

            try:
                precinct_index = header_row.index("PrecinctPortion")
                counting_group_index = header_row.index("CountingGroup")
            except ValueError as error:
                raise ValueError("Nevada Clark CVR CSV missing PrecinctPortion or CountingGroup column") from error

            president_columns = []
            senate_columns = []
            for index, contest in enumerate(contest_row):
                if index >= len(candidate_row):
                    continue
                contest = str(contest or "")
                candidate = candidate_row[index]
                if contest.startswith("PRESIDENT"):
                    president_columns.append((index, candidate_key(candidate, review["majorCandidates"])))
                elif contest.startswith(review.get("downBallotContestPrefix", "United States Senate")):
                    senate_columns.append((index, candidate_key(candidate, review["downBallotCandidates"])))

            if not president_columns:
                raise ValueError("Nevada Clark CVR parser found no President columns")
            if not senate_columns:
                raise ValueError("Nevada Clark CVR parser found no Senate columns")

            for row in reader:
                if len(row) <= max(precinct_index, counting_group_index):
                    continue
                precinct = str(row[precinct_index] or "").strip()
                if not precinct:
                    continue
                item = by_precinct[precinct]
                item["ballots"] += 1
                counting_group = str(row[counting_group_index] or "").strip().lower()
                if "mail" in counting_group:
                    item["mailBallots"] += 1
                elif "early" in counting_group:
                    item["earlyVotingBallots"] += 1
                elif "election day" in counting_group:
                    item["electionDayBallots"] += 1
                for index, key in president_columns:
                    vote = cvr_vote(row[index] if index < len(row) else "")
                    if vote:
                        item[key] += vote
                for index, key in senate_columns:
                    vote = cvr_vote(row[index] if index < len(row) else "")
                    if vote and key in {"dem", "rep"}:
                        item[f"senate_{key}"] += vote

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for precinct, totals in sorted(by_precinct.items()):
        harris = totals["harris"]
        trump = totals["trump"]
        other = totals["other"]
        president_total = harris + trump + other
        if not president_total:
            continue
        senate_dem = totals["senate_dem"]
        senate_rep = totals["senate_rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
                "mailBallots": totals["mailBallots"],
                "earlyVotingBallots": totals["earlyVotingBallots"],
                "electionDayBallots": totals["electionDayBallots"],
                "sourceUrl": source["url"],
            }
        )

    expected_rows = review.get("expectedRows")
    if expected_rows and len(review_rows) != expected_rows:
        raise ValueError(f"Nevada Clark CVR row count mismatch: {len(review_rows)} != {expected_rows}")

    parsed = {
        "harris": sum(row["harris"] for row in review_rows),
        "trump": sum(row["trump"] for row in review_rows),
        "other": sum(row["total"] - row["harris"] - row["trump"] for row in review_rows),
        "total": sum(row["total"] for row in review_rows),
        "ballots": sum(row["mailBallots"] + row["earlyVotingBallots"] + row["electionDayBallots"] for row in review_rows),
    }
    expected_totals = review.get("expectedCvrTotals")
    if expected_totals and parsed != expected_totals:
        raise ValueError(f"Nevada Clark CVR totals mismatch: {parsed} != {expected_totals}")

    certified_gap = {
        "harris": certified["harris"] - parsed["harris"],
        "trump": certified["trump"] - parsed["trump"],
        "other": certified["other"] - parsed["other"],
        "total": certified["total"] - parsed["total"],
    }
    expected_gap = review.get("expectedCertifiedGap")
    if expected_gap and certified_gap != expected_gap:
        raise ValueError(f"Nevada Clark certified-vs-CVR gap mismatch: {certified_gap} != {expected_gap}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["coverageMode"] = review.get("coverageMode", "partialLocal")
    eta_analysis["loadedCounties"] = [county]
    eta_analysis["partialCoverage"] = True
    eta_analysis["certifiedGap"] = certified_gap
    eta_analysis["cvrTotals"] = parsed
    eta_analysis["warning"] = review.get(
        "warning",
        "Nevada review rows currently cover Clark County CVR precinct rows only; the official CVR aggregate is smaller than the certified Clark County canvass total.",
    )
    return review_rows, eta_analysis


def review_charts_texas_county_json(config):
    review = config["reviewCharts"]
    data = json.loads(local_source(config, review["sourceId"]).read_text(encoding="utf-8"))
    geoid_names = geometry_names_by_geoid(config)

    def race_totals(office_id, candidate_rules, label):
        totals_by_county = {}
        for geoid, county_data in data.items():
            race = county_data.get("Races", {}).get(str(office_id))
            if not race:
                continue
            county = geoid_names.get(str(geoid).zfill(5))
            if not county:
                raise ValueError(f"Could not match Texas county GEOID {geoid!r} to geometry")
            totals = defaultdict(int)
            for candidate in race.get("C", {}).values():
                name = str(candidate.get("N", ""))
                party = str(candidate.get("P", ""))
                votes = int_text(candidate.get("V"))
                key = "other"
                for candidate_key, rule in candidate_rules.items():
                    if new_york_column_matches(name, party, rule):
                        key = candidate_key
                        break
                totals[key] += votes
                totals["total"] += votes
            reported_total = int_text(race.get("T"))
            if reported_total and totals["total"] != reported_total:
                raise ValueError(f"Texas {label} candidate total mismatch for {county}: {totals['total']} != {reported_total}")
            totals_by_county[county] = totals
        missing_counties = sorted(set(geoid_names.values()) - set(totals_by_county))
        if missing_counties:
            raise ValueError(f"Texas {label} county JSON missing county rows: {', '.join(missing_counties)}")
        return totals_by_county

    president = race_totals(review.get("presidentOfficeId", "1001"), review["majorCandidates"], "president")
    down_ballot = race_totals(review["downBallotOfficeId"], review["downBallotCandidates"], "down-ballot")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = down_ballot[county]["dem"]
        senate_rep = down_ballot[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_texas_harris_canvass_pdf_vote_share(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    president_rows, _candidate_labels, _row_count = certified_results_texas_county_json(config)
    county = review.get("county", "Harris County")
    county_key = re.sub(r"\s+county$", "", county, flags=re.IGNORECASE).strip().upper()
    certified = next(
        (
            row
            for row in president_rows
            if re.sub(r"\s+county$", "", row["county"], flags=re.IGNORECASE).strip().upper() == county_key
        ),
        None,
    )
    if not certified:
        raise ValueError("Texas Harris canvass parser could not find Harris County in certified county rows")

    pages = extract_pdf_items(path, review.get("firstPage", 1), review.get("lastPage", 152))
    review_rows = []
    parsed_totals = defaultdict(int)

    def parse_number(value):
        value = str(value or "").strip().replace(",", "")
        return int(value) if re.fullmatch(r"\d+", value) else None

    for page in pages:
        items = page["items"]
        values = {item["value"] for item in items}
        if "President / Vice President" not in values or not any("TRUMP / JD VANCE" in item["value"] for item in items):
            continue
        for precinct_item in items:
            precinct = str(precinct_item["value"]).strip()
            if not re.fullmatch(r"\d{4}\s+-\s+.+", precinct):
                continue
            y = precinct_item["y"]
            row_values = [
                (item["x"], parse_number(item["value"]))
                for item in items
                if item["x"] > 100 and abs(item["y"] - y) < 0.05 and parse_number(item["value"]) is not None
            ]
            row_values = [value for _x, value in sorted(row_values)]
            if len(row_values) < 11:
                raise ValueError(f"Texas Harris canvass row has too few numeric columns on page {page['pageNumber']}: {precinct}")
            trump = row_values[0]
            harris = row_values[1]
            other = sum(row_values[2:10])
            total = row_values[10]
            if trump + harris + other != total:
                raise ValueError(
                    f"Texas Harris canvass candidate total mismatch for {precinct}: "
                    f"{trump + harris + other} != {total}"
                )
            if not total:
                continue
            method_values = row_values[13:19] if len(row_values) >= 19 else []
            row = {
                "county": certified["county"],
                "ward": precinct,
                "total": total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / total) * 100),
                "trumpShare": round2((trump / total) * 100),
                "demDropoff": 0,
                "repDropoff": 0,
            }
            if len(method_values) == 6:
                row.update(
                    {
                        "ballotByMailBallotsCast": method_values[0],
                        "earlyVotingBallotsCast": method_values[1],
                        "electionDayBallotsCast": method_values[2],
                        "evProvisionalBallotsCast": method_values[3],
                        "edProvisionalBallotsCast": method_values[4],
                        "totalBallotsCast": method_values[5],
                    }
                )
            review_rows.append(row)
            parsed_totals["trump"] += trump
            parsed_totals["harris"] += harris
            parsed_totals["other"] += other
            parsed_totals["total"] += total

    expected_rows = review.get("expectedRows")
    if expected_rows and len(review_rows) != expected_rows:
        raise ValueError(f"Texas Harris canvass row count mismatch: {len(review_rows)} != {expected_rows}")

    expected_totals = {
        "trump": certified["trump"],
        "harris": certified["harris"],
        "other": certified["other"],
        "total": certified["total"],
    }
    parsed = {key: parsed_totals[key] for key in expected_totals}
    if parsed != expected_totals:
        raise ValueError(f"Texas Harris canvass totals do not match certified Harris County totals: {parsed} != {expected_totals}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["coverageNote"] = review.get(
        "coverageNote",
        "Official Harris County canvass precinct rows are loaded for Texas vote-share advisory review; other Texas counties remain county-only.",
    )
    eta_analysis["warning"] = review.get(
        "warning",
        "Texas local review rows currently cover Harris County only and use presidential vote share; down-ballot flags are suppressed.",
    )
    return review_rows, eta_analysis


def review_charts_missouri_actual_results_pdf(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    president_rows, _candidate_labels, _row_count = certified_results_missouri_actual_results_pdf(config)
    president = {row["county"]: row for row in president_rows}
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = set(geometry_names_by_geoid(config).values())
    merge_rows = review.get("mergeRows", config.get("certifiedResults", {}).get("mergeRows", {}))

    def county_name(raw_name):
        name = merge_rows.get(raw_name, raw_name)
        if name == "St. Louis":
            return "St. Louis County"
        if name == "St. Louis City":
            return "St. Louis city"
        if name in county_names:
            return name
        return f"{name} County"

    table_active = False
    senate_by_county = defaultdict(lambda: defaultdict(int))
    reported_totals = None
    row_pattern = re.compile(r"^(?P<name>[A-Za-z. ]+?)\s+(?P<values>(?:\d+\s+){6}\d+)$")
    for line in lines:
        if line == review.get("downBallotContest", "U.S. Senator"):
            table_active = True
            continue
        if not table_active:
            continue
        match = row_pattern.match(line)
        if not match:
            continue
        values = [int_text(value) for value in match.group("values").split()]
        if match.group("name") == "Total":
            reported_totals = {
                "rep": values[0],
                "dem": values[1],
                "other": sum(values[2:6]),
                "total": values[6],
            }
            break
        county = county_name(match.group("name"))
        if county not in county_names:
            raise ValueError(f"Unexpected Missouri Senate county row {county!r} from {match.group('name')!r}")
        senate_by_county[county]["rep"] += values[0]
        senate_by_county[county]["dem"] += values[1]
        senate_by_county[county]["other"] += sum(values[2:6])
        senate_by_county[county]["total"] += values[6]

    if not reported_totals:
        raise ValueError(f"Could not find Missouri U.S. Senator total row in {path}")
    missing_counties = sorted(set(president) - set(senate_by_county))
    if missing_counties:
        raise ValueError(f"Missouri review rows missing U.S. Senator match for {len(missing_counties)} counties: {', '.join(missing_counties[:10])}")
    parsed_totals = {
        "rep": sum(row["rep"] for row in senate_by_county.values()),
        "dem": sum(row["dem"] for row in senate_by_county.values()),
        "other": sum(row["other"] for row in senate_by_county.values()),
        "total": sum(row["total"] for row in senate_by_county.values()),
    }
    if parsed_totals != reported_totals:
        raise ValueError(f"Missouri Senate parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = senate_by_county[county]["dem"]
        senate_rep = senate_by_county[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_mississippi_recap_csv(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    president_rows, _candidate_labels, _row_count = certified_results_county_totals_csv(config)
    president = {row["county"]: row for row in president_rows}
    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+County$", "", county, flags=re.IGNORECASE).upper()): county
        for county in geometry_names_by_geoid(config).values()
    }
    county_lookup["JEFFDAVIS"] = "Jefferson Davis County"
    down_ballot = defaultdict(lambda: defaultdict(int))
    reported_totals = defaultdict(int)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("Office", "")).strip() != review.get("downBallotOffice", "United States-Senate"):
                continue
            raw_county = str(row.get("County", "")).strip()
            county = county_lookup.get(re.sub(r"[^A-Z0-9]+", "", raw_county.upper()))
            if not county:
                raise ValueError(f"Could not match Mississippi recap county {raw_county!r} to geometry")
            candidate = str(row.get("Candidate", "")).strip()
            party = str(row.get("Party", "")).strip()
            votes = int_text(row.get("County Total"))
            key = "other"
            for candidate_key, rule in review["downBallotCandidates"].items():
                if new_york_column_matches(candidate, party, rule):
                    key = candidate_key
                    break
            down_ballot[county][key] += votes
            down_ballot[county]["total"] += votes
            reported_totals[key] = int_text(row.get("State Total"))

    missing_counties = sorted(set(president) - set(down_ballot))
    if missing_counties:
        raise ValueError(f"Mississippi review rows missing Senate match for {len(missing_counties)} counties: {', '.join(missing_counties[:10])}")
    parsed_totals = {
        "rep": sum(row["rep"] for row in down_ballot.values()),
        "dem": sum(row["dem"] for row in down_ballot.values()),
    }
    expected_totals = {"rep": reported_totals["rep"], "dem": reported_totals["dem"]}
    if parsed_totals != expected_totals:
        raise ValueError(f"Mississippi Senate parsed totals do not match recap State Total fields: {parsed_totals} != {expected_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = down_ballot[county]["dem"]
        senate_rep = down_ballot[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_connecticut_statement_text(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    path = local_source(config, review["sourceId"])
    aliases = certified.get("townAliases", {})
    subdivision_lookup = connecticut_subdivision_lookup(config, certified["townMapSourceId"], aliases)

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
        raise ValueError(f"Connecticut review source has no parsed town presidential rows: {path}")
    if set(major_rows) != set(write_in_five_rows) or set(major_rows) != set(write_in_continued_rows):
        raise ValueError("Connecticut review presidential write-in town rows do not match major-candidate town rows")

    senate_rows = {}
    senate_row_pattern = re.compile(r"^(.+?)\s+((?:[\d,]+\s+){5}[\d,]+)$")
    in_senate_town_table = False
    pending_header = False
    for line in lines[senate_index:]:
        text = line.strip()
        if text == "Election Results for Representative in Congress":
            break
        if text == "Election Results for United States Senator":
            pending_header = True
            in_senate_town_table = False
            continue
        if pending_header and text == "Summarized by Town":
            in_senate_town_table = True
            pending_header = False
            continue
        if pending_header and text.startswith("Summarized by"):
            pending_header = False
            continue
        if not in_senate_town_table or not text or text.startswith("Democratic Party") or text.startswith("Christopher S. Murphy"):
            continue
        if text.startswith("Total"):
            continue
        match = senate_row_pattern.match(text)
        if not match:
            continue
        town = match.group(1).strip()
        senate_rows[town] = [int_text(value) for value in match.group(2).split()]

    if set(major_rows) != set(senate_rows):
        missing = sorted(set(major_rows) - set(senate_rows))
        extra = sorted(set(senate_rows) - set(major_rows))
        raise ValueError(
            "Connecticut review Senate town rows do not match presidential town rows: "
            f"missing={missing[:10]} extra={extra[:10]}"
        )

    expected_totals = review.get("statewideTotals", {})
    parsed_totals = {
        "senateDem": sum(values[0] + values[2] for values in senate_rows.values()),
        "senateRep": sum(values[1] for values in senate_rows.values()),
    }
    if expected_totals and parsed_totals != expected_totals:
        raise ValueError(f"Connecticut Senate parsed totals do not match expected totals: {parsed_totals} != {expected_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    missing_regions = []
    for town in sorted(major_rows):
        lookup = subdivision_lookup.get(normalize_connecticut_town(town, aliases))
        if not lookup:
            missing_regions.append(town)
            continue
        major = major_rows[town]
        write_in_five = write_in_five_rows[town]
        write_in_continued = write_in_continued_rows[town]
        president_total = sum(major) + sum(write_in_five) + sum(write_in_continued)
        harris = major[0]
        trump = major[1]
        senate = senate_rows[town]
        senate_dem = senate[0] + senate[2]
        senate_rep = senate[1]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": lookup["county"],
                "ward": town,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    if missing_regions:
        raise ValueError(f"Connecticut review towns could not be mapped to planning regions: {', '.join(sorted(missing_regions))}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def hawaii_statewide_contest_totals(path, contest_title, candidate_rules):
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
            if row[column_index["Contest Title"]] != contest_title:
                continue
            candidate_name = re.sub(r"\s+", " ", row[column_index["Candidate Name"]]).upper()
            for key, rule in candidate_rules.items():
                if rule["contains"].upper() in candidate_name:
                    totals[key] += int_text(row[column_index["Total Votes"]])
                    break
        return dict(totals)


def review_charts_hawaii_county_summary_pdfs(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president_rows, _candidate_labels, _row_count = certified_results_hawaii_county_summary_pdfs(config)
    president = {row["county"]: row for row in president_rows}
    senate_rules = {
        "dem": {"contains": "HIRONO", "pattern": r"\(D\)\s+HIRONO,\s+Mazie K\.\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "rep": {"contains": "MCDERMOTT", "pattern": r"\(R\)\s+MCDERMOTT,\s+Bob\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "billionaire": {"contains": "BILLIONAIRE", "pattern": r"\(W\)\s+BILLIONAIRE,\s+Shelby Pikachu\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
        "pohlman": {"contains": "POHLMAN", "pattern": r"\(G\)\s+POHLMAN,\s+Emma Jane Avila\s+(\d[\d,]*)\s+\d+(?:\.\d+)?%"},
    }
    senate_by_county = {}
    for county_source in certified.get("countySources", []):
        path = local_source(config, county_source["sourceId"])
        text = re.sub(r"\s+", " ", extract_pdf_text(path))
        totals = {}
        for key, rule in senate_rules.items():
            match = re.search(rule["pattern"], text)
            if not match:
                raise ValueError(f"Could not find Hawaii U.S. Senate {key} total in {path}")
            totals[key] = int_text(match.group(1))
        senate_by_county[county_source["county"]] = totals

    statewide_source_id = review.get("statewideSummarySourceId", certified.get("statewideSummarySourceId"))
    if statewide_source_id:
        statewide_totals = hawaii_statewide_contest_totals(
            local_source(config, statewide_source_id),
            review.get("downBallotContest", "U.S. Senator"),
            senate_rules,
        )
        parsed_totals = {
            key: sum(row[key] for row in senate_by_county.values())
            for key in senate_rules
        }
        if parsed_totals != statewide_totals:
            raise ValueError(f"Hawaii county U.S. Senate totals do not match statewide summary: {parsed_totals} != {statewide_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = senate_by_county[county]["dem"]
        senate_rep = senate_by_county[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_vermont_municipality_csv(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president = vermont_municipality_vote_rows(config, review.get("presidentSourceId", certified["sourceId"]), certified["columns"])
    senate = vermont_municipality_vote_rows(config, review["downBallotSourceId"], review["downBallotColumns"])
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"Vermont review municipality mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for key in sorted(president):
        president_row = president[key]
        senate_row = senate[key]
        president_total = president_row.get("total") or (
            president_row["harris"] + president_row["trump"] + president_row.get("kennedy", 0)
            + president_row.get("oliver", 0) + president_row.get("deLaCruz", 0)
            + president_row.get("west", 0) + president_row.get("fruit", 0)
            + president_row.get("writeIns", 0)
        )
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate_row["dem"]
        senate_rep = senate_row["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": president_row["county"],
                "ward": president_row["municipality"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_massachusetts_county_html(config):
    review = config["reviewCharts"]
    president = massachusetts_pd43_county_votes(local_source(config, review.get("presidentSourceId", review["sourceId"])), review["presidentColumns"])
    senate = massachusetts_pd43_county_votes(local_source(config, review["downBallotSourceId"]), review["downBallotColumns"])
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"Massachusetts review county mismatch: missing={missing} extra={extra}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        senate_row = senate[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["dem"]
        trump = president_row["rep"]
        senate_dem = senate_row["dem"]
        senate_rep = senate_row["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def massachusetts_precinct_label(town, ward, precinct):
    parts = [town]
    if ward and ward != "-":
        parts.append(f"Ward {ward}")
    if precinct and precinct != "-":
        parts.append(f"Precinct {precinct}")
    return " - ".join(parts)


def massachusetts_precinct_csv_votes(config, source_id, columns, map_source_id, aliases):
    path = local_source(config, source_id)
    subdivision_lookup = connecticut_subdivision_lookup(config, map_source_id, aliases)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        next(reader, None)
        column_index = {name: index for index, name in enumerate(header)}
        output = {}
        missing = set()
        for row in reader:
            if len(row) < 3:
                continue
            town = str(row[column_index["City/Town"]] or "").strip()
            ward = str(row[column_index["Ward"]] or "").strip()
            precinct = str(row[column_index["Pct"]] or "").strip()
            if not town or town.lower().startswith("total"):
                continue
            lookup = subdivision_lookup.get(normalize_connecticut_town(town, aliases))
            if not lookup:
                missing.add(town)
                continue
            item = {
                "county": lookup["county"],
                "ward": massachusetts_precinct_label(town, ward, precinct),
                "dem": int_text(row[column_index[columns["dem"]]]),
                "rep": int_text(row[column_index[columns["rep"]]]),
                "other": 0,
            }
            for column in columns.get("other", []):
                item["other"] += int_text(row[column_index[column]])
            item["total"] = item["dem"] + item["rep"] + item["other"]
            output[(normalize_connecticut_town(town, aliases), ward, precinct)] = item
    if missing:
        raise ValueError(f"Massachusetts precinct rows could not be mapped to counties: {', '.join(sorted(missing))}")
    return output


def review_charts_massachusetts_precinct_csv(config):
    review = config["reviewCharts"]
    aliases = review.get("municipalityAliases", {})
    map_source_id = review["municipalityMapSourceId"]
    president = massachusetts_precinct_csv_votes(
        config,
        review.get("presidentSourceId", review["sourceId"]),
        review["presidentColumns"],
        map_source_id,
        aliases,
    )
    senate = massachusetts_precinct_csv_votes(
        config,
        review["downBallotSourceId"],
        review["downBallotColumns"],
        map_source_id,
        aliases,
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"Massachusetts review precinct mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for key in sorted(president, key=lambda item: (president[item]["county"], president[item]["ward"])):
        president_row = president[key]
        senate_row = senate[key]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["dem"]
        trump = president_row["rep"]
        senate_dem = senate_row["dem"]
        senate_rep = senate_row["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": president_row["county"],
                "ward": president_row["ward"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_new_jersey_senate_pdf(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _row_count = certified_results_new_jersey_president_pdf(config)
    president = {row["county"]: row for row in president_rows}
    senate = new_jersey_pdf_candidate_county_totals(
        config,
        local_source(config, review["downBallotSourceId"]),
        review["downBallotCandidates"],
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"New Jersey review county mismatch: missing={missing} extra={extra}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate[county]["dem"]
        senate_rep = senate[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def new_jersey_municipal_key(name):
    text = name.lower()
    text = text.replace("cinnnaminson", "cinnaminson")
    text = text.replace("sayerville", "sayreville")
    text = text.replace("townshp", "township")
    text = text.replace("voorhees borough", "voorhees township")
    if text.strip() == "parsippany-troy hills":
        text = "parsippany-troy hills township"
    if text.strip() == "greenbrook":
        text = "green brook township"
    text = re.sub(r"\bmt\b", "mount", text)
    text = re.sub(r",?\s*city of\b", " city", text)
    text = re.sub(r"\btownship\b", "twp", text)
    text = re.sub(r"\bborough\b", "boro", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def new_jersey_municipal_pdf_rows(path, county, candidate_keys, validate_keys=None):
    validate_keys = validate_keys or candidate_keys
    raw_lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    lines = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index]
        numbers = re.findall(r"\d[\d,]*", line)
        if not numbers and index + 1 < len(raw_lines):
            next_numbers = re.findall(r"\d[\d,]*", raw_lines[index + 1])
            if len(next_numbers) == len(candidate_keys) and re.fullmatch(r"[\d,\s]+", raw_lines[index + 1]):
                line = f"{line} {raw_lines[index + 1]}"
                index += 1
        elif 0 < len(numbers) < len(candidate_keys) and index + 1 < len(raw_lines):
            next_numbers = re.findall(r"\d[\d,]*", raw_lines[index + 1])
            if (
                next_numbers
                and len(numbers) + len(next_numbers) == len(candidate_keys)
                and re.fullmatch(r"[\d,\s]+", raw_lines[index + 1])
            ):
                line = f"{line} {raw_lines[index + 1]}"
                index += 1
        lines.append(line)
        index += 1

    rows = []
    parsed_totals = defaultdict(int)
    official_totals = None
    in_municipalities = False
    special_rows = {"HAND COUNTS"}
    has_incomplete_special_row = False

    for line in lines:
        if line == "MUNICIPALITIES":
            in_municipalities = True
            continue
        if not in_municipalities:
            continue
        if line.startswith("NJDOE"):
            continue

        numbers = re.findall(r"\d[\d,]*", line)
        if len(numbers) != len(candidate_keys):
            if numbers:
                first_number = line.find(numbers[0])
                name = line[:first_number].strip() if first_number > 0 else ""
                upper_name = name.upper()
                if upper_name.startswith("FEDERAL") or upper_name in special_rows:
                    has_incomplete_special_row = True
            continue
        first_number = line.find(numbers[0])
        if first_number < 1:
            continue
        name = line[:first_number].strip()
        values = {key: int_text(numbers[index]) for index, key in enumerate(candidate_keys)}

        if name.upper() in {"COUNTY TOTAL", "TOTAL"}:
            official_totals = values
            continue

        for key, votes in values.items():
            parsed_totals[key] += votes

        upper_name = name.upper()
        if upper_name.startswith("FEDERAL") or upper_name in special_rows:
            continue
        rows.append(
            {
                "county": county,
                "ward": name,
                "_wardKey": new_jersey_municipal_key(name),
                **values,
            }
        )

    if (
        official_totals
        and not has_incomplete_special_row
        and {key: parsed_totals[key] for key in validate_keys} != {
        key: official_totals[key] for key in validate_keys
        }
    ):
        raise ValueError(
            f"New Jersey municipal PDF totals mismatch for {county} {source_path(path)}: "
            f"{ {key: parsed_totals[key] for key in validate_keys} } != "
            f"{ {key: official_totals[key] for key in validate_keys} }"
        )
    if not rows:
        raise ValueError(f"New Jersey municipal PDF produced no local rows for {county}: {source_path(path)}")
    return rows


def review_charts_new_jersey_municipal_pdfs(config):
    review = config["reviewCharts"]
    president_keys = ["harris", "trump", "stein", "kennedy", "oliver", "deLaCruz", "terry", "kishore", "fruit"]
    senate_keys = ["dem", "rep", "green", "libertarian", "voteBetter", "socialistWorkers"]
    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0

    for county_source in review["countySources"]:
        county = county_source["county"]
        president_rows = new_jersey_municipal_pdf_rows(
            project_path(county_source["presidentLocalFile"]),
            county,
            president_keys,
        )
        senate_rows = new_jersey_municipal_pdf_rows(
            project_path(county_source["senateLocalFile"]),
            county,
            senate_keys,
            validate_keys=["dem", "rep"],
        )
        president = {row["_wardKey"]: row for row in president_rows}
        senate = {row["_wardKey"]: row for row in senate_rows}
        if set(president) != set(senate):
            missing = sorted(president[key]["ward"] for key in set(president) - set(senate))
            extra = sorted(senate[key]["ward"] for key in set(senate) - set(president))
            raise ValueError(f"New Jersey municipal review mismatch for {county}: missing={missing} extra={extra}")

        for ward_key in sorted(president, key=lambda key: president[key]["ward"]):
            president_row = president[ward_key]
            senate_row = senate[ward_key]
            president_total = sum(president_row[key] for key in president_keys)
            if not president_total:
                continue
            harris = president_row["harris"]
            trump = president_row["trump"]
            senate_dem = senate_row["dem"]
            senate_rep = senate_row["rep"]
            senate_dem_total += senate_dem
            senate_rep_total += senate_rep
            review_rows.append(
                {
                    "county": county,
                    "ward": senate_row["ward"] if senate_row["ward"] != president_row["ward"] else president_row["ward"],
                    "total": president_total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / president_total) * 100),
                    "trumpShare": round2((trump / president_total) * 100),
                    "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                    "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
                }
            )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["coverageMode"] = "localPresidentSenate"
    eta_analysis["coverageNote"] = (
        "Official New Jersey Division of Elections county PDFs parsed at municipality level; "
        "federal/overseas and hand-count rows are excluded from local advisory rows."
    )
    return review_rows, eta_analysis


def review_charts_new_york_county_csv(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _row_count = certified_results_new_york_county_csv(config)
    president = {row["county"]: row for row in president_rows}
    senate = new_york_county_candidate_totals(
        local_source(config, review["downBallotSourceId"]),
        review["downBallotCandidates"],
        config["certifiedResults"].get("excludeColumns"),
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"New York review county mismatch: missing={missing} extra={extra}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate[county]["dem"]
        senate_rep = senate[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_new_york_city_ed_csv(config):
    review = config["reviewCharts"]
    president = new_york_city_ed_candidate_totals(
        local_source(config, review["sourceId"]),
        review["majorCandidates"],
        review.get("excludedUnits"),
    )
    senate = new_york_city_ed_candidate_totals(
        local_source(config, review["downBallotSourceId"]),
        review["downBallotCandidates"],
        review.get("excludedUnits"),
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"New York City ED review mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for key in sorted(president):
        president_row = president[key]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate[key]["dem"]
        senate_rep = senate[key]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": president_row["county"],
                "ward": president_row["ward"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["coverageMode"] = "partialLocal"
    eta_analysis["coverageNote"] = (
        "Official New York City Board of Elections election-district CSVs are loaded for Bronx, Kings, "
        "New York, Queens, and Richmond counties only; the rest of New York remains county-level for review."
    )
    return review_rows, eta_analysis


def review_charts_california_sov_xlsx(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president_rows, _candidate_labels, _row_count = certified_results_california_president_xlsx(config)
    president = {row["county"]: row for row in president_rows}
    senate = california_sov_county_candidate_totals(
        local_source(config, review["downBallotSourceId"]),
        review.get("sheet", certified.get("sheet", "SOV Statewide Contest Details")),
        review["downBallotColumns"],
        review.get("stateTotalsLabel", certified.get("stateTotalsLabel", "State Totals")),
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"California review county mismatch: missing={missing} extra={extra}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate[county]["dem"]
        senate_rep = senate[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_civera_county_csv(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president_rows, _candidate_labels, _row_count = CERTIFIED_RESULT_PARSERS[certified["format"]](config)
    president = {row["county"]: row for row in president_rows}
    senate = civera_result_totals_by_scope(
        local_source(config, review["downBallotSourceId"]),
        review["downBallotCandidates"],
        set(review.get("rowTypes", ["County", "Locality"])),
        certified.get("excludeColumns"),
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"Civera review scope mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate[county]["dem"]
        senate_rep = senate[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        label = review.get("rowLabelTemplate", "{county}")
        review_rows.append(
            {
                "county": county,
                "ward": label.format(county=county),
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_civera_precinct_csv(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president = civera_precinct_president_rows(
        local_source(config, review["sourceId"]),
        certified["columns"],
    )
    down_ballot = civera_precinct_down_ballot_rows(
        local_source(config, review["downBallotSourceId"]),
        review["downBallotCandidates"],
    )
    if set(president) != set(down_ballot):
        missing = sorted(set(president) - set(down_ballot))
        extra = sorted(set(down_ballot) - set(president))
        raise ValueError(f"Civera precinct review mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    down_ballot_dem_total = 0
    down_ballot_rep_total = 0
    for county, precinct in sorted(president):
        president_row = president[(county, precinct)]
        harris = president_row["harris"]
        trump = president_row["trump"]
        other = president_row["other"]
        president_total = harris + trump + other
        if not president_total:
            continue
        down_ballot_row = down_ballot[(county, precinct)]
        down_ballot_dem = down_ballot_row["dem"]
        down_ballot_rep = down_ballot_row["rep"]
        down_ballot_dem_total += down_ballot_dem
        down_ballot_rep_total += down_ballot_rep
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - down_ballot_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - down_ballot_rep) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        down_ballot_dem_total,
        down_ballot_rep_total,
    )
    if review.get("warning"):
        eta_analysis["warning"] = review["warning"]
    return review_rows, eta_analysis


def review_charts_civera_precinct_vote_share(config):
    review = config["reviewCharts"]
    columns = review.get("columns") or config.get("certifiedResults", {}).get("columns")
    if not columns:
        raise ValueError("Civera precinct vote-share parser requires reviewCharts.columns or certifiedResults.columns")
    president = civera_precinct_president_rows(
        local_source(config, review["sourceId"]),
        columns,
    )

    review_rows = []
    for county, precinct in sorted(president):
        president_row = president[(county, precinct)]
        harris = president_row["harris"]
        trump = president_row["trump"]
        other = president_row["other"]
        president_total = harris + trump + other
        if not president_total:
            continue
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": 0,
                "repDropoff": 0,
            }
        )

    expected_totals = review.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "trump": sum(row["trump"] for row in review_rows),
            "harris": sum(row["harris"] for row in review_rows),
            "other": sum(row["total"] - row["trump"] - row["harris"] for row in review_rows),
            "total": sum(row["total"] for row in review_rows),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Civera precinct vote-share totals do not match expected totals: {parsed_totals} != {expected_totals}")

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], 0, 0)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["warning"] = review.get(
        "warning",
        "Review rows use official presidential precinct vote share only; no same-row down-ballot comparison is mapped.",
    )
    return review_rows, eta_analysis


def review_charts_electionware_precinct_summary(config):
    review = config["reviewCharts"]
    source_items = review.get("sources") or [{"sourceId": review["sourceId"], "county": review["county"]}]
    president_contest = review.get("presidentContestName", "FOR PRESIDENT").upper()
    down_ballot_contest = review.get("downBallotContestName", "FOR U.S. SENATOR").upper()
    summary_labels = {
        "",
        "TOTAL VOTES CAST",
        "OVERVOTES",
        "UNDERVOTES",
        "CONTEST TOTALS",
        "NO CANDIDATE(S) NOMINATED",
    }
    by_precinct = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})

    def add_votes(target, candidate, votes, candidate_rules, include_other):
        candidate_upper = candidate.upper()
        if candidate_upper in summary_labels:
            return
        for key, rule in candidate_rules.items():
            if new_york_column_matches(candidate, "", rule):
                target[key] += votes
                return
        if include_other:
            target["other"] += votes

    for source in source_items:
        county = source["county"]
        current_precinct = ""
        current_contest = None
        with local_source(config, source["sourceId"]).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.reader(handle):
                first = str(row[0] if row else "").strip()
                second = str(row[1] if len(row) > 1 else "").strip()
                if first.upper().startswith("PRECINCT "):
                    current_precinct = first
                    current_contest = None
                    continue
                if second.upper().startswith("FOR "):
                    contest = second.upper()
                    if contest == president_contest:
                        current_contest = "president"
                    elif contest == down_ballot_contest:
                        current_contest = "downBallot"
                    else:
                        current_contest = None
                    continue
                if not current_precinct or not current_contest or not first:
                    continue
                votes = int_text(row[2] if len(row) > 2 else 0)
                item = by_precinct[(county, current_precinct)]
                if current_contest == "president":
                    add_votes(item["president"], first, votes, review["majorCandidates"], True)
                else:
                    add_votes(item["downBallot"], first, votes, review["downBallotCandidates"], False)

    review_rows = []
    down_ballot_dem_total = 0
    down_ballot_rep_total = 0
    for county, precinct in sorted(by_precinct):
        item = by_precinct[(county, precinct)]
        harris = item["president"]["harris"]
        trump = item["president"]["trump"]
        other = item["president"]["other"]
        president_total = harris + trump + other
        if not president_total:
            continue
        down_ballot_dem = item["downBallot"]["dem"]
        down_ballot_rep = item["downBallot"]["rep"]
        if not down_ballot_dem and not down_ballot_rep:
            continue
        down_ballot_dem_total += down_ballot_dem
        down_ballot_rep_total += down_ballot_rep
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - down_ballot_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - down_ballot_rep) / trump) * 100) if trump else 0,
            }
        )

    expected = review.get("expectedCountyTotals")
    if expected:
        parsed = {}
        for row in review_rows:
            county = row["county"]
            target = parsed.setdefault(county, defaultdict(int))
            target["trump"] += row["trump"]
            target["harris"] += row["harris"]
            target["total"] += row["total"]
            target["other"] += row["total"] - row["trump"] - row["harris"]
        normalized = {county: dict(totals) for county, totals in parsed.items()}
        if normalized != expected:
            raise ValueError(f"Electionware precinct summary totals do not match expected county totals: {normalized} != {expected}")

    eta_analysis = eta_analysis_from_review_rows(
        review_rows,
        review["policy"],
        down_ballot_dem_total,
        down_ballot_rep_total,
    )
    if review.get("coverageMode"):
        eta_analysis["coverageMode"] = review["coverageMode"]
    if review.get("warning"):
        eta_analysis["warning"] = review["warning"]
    return review_rows, eta_analysis


def civera_precinct_totals_by_locality(path, candidate_rules, excluded_columns=None, skip_precincts=None):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"Civera precinct source has too few rows: {path}")
    header = rows[0]
    party_row = rows[1]
    excluded = set(excluded_columns or ["", "Total Votes Cast", "Total Ballots Cast"])
    output = defaultdict(lambda: defaultdict(int))
    state_totals = defaultdict(int)
    current_locality = ""
    skipped = {
        (item["locality"], item["precinct"])
        for item in (skip_precincts or [])
    }

    for row in rows[2:]:
        if len(row) < 2:
            continue
        row_type = str(row[0]).strip()
        if row_type == "Locality":
            current_locality = str(row[1]).strip()
            continue
        if row_type == "State":
            target = state_totals
        elif row_type == "Precinct" and current_locality:
            precinct = str(row[1]).strip()
            if (current_locality, precinct) in skipped:
                continue
            target = output[(current_locality, precinct)]
        else:
            continue

        for index, header_value in enumerate(header):
            if index >= len(row) or header_value in excluded:
                continue
            party_value = party_row[index] if index < len(party_row) else ""
            matched = False
            for key, rule in candidate_rules.items():
                if new_york_column_matches(header_value, party_value, rule):
                    target[key] += int_text(row[index])
                    matched = True
                    break
            if not matched and row_type == "Precinct" and header_value:
                target["other"] += int_text(row[index])

    if state_totals:
        parsed_totals = {
            key: sum(totals[key] for totals in output.values())
            for key in candidate_rules
        }
        expected_totals = {key: state_totals[key] for key in candidate_rules}
        if parsed_totals != expected_totals:
            raise ValueError(f"Civera precinct totals do not match State row in {path}: {parsed_totals} != {expected_totals}")
    return output


def review_charts_virginia_precinct_csv(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president_rows, _candidate_labels, _row_count = CERTIFIED_RESULT_PARSERS[certified["format"]](config)
    locality_totals = {row["county"]: row for row in president_rows}
    president = civera_precinct_totals_by_locality(
        local_source(config, review["sourceId"]),
        {
            "trump": certified["majorCandidates"]["trump"],
            "harris": certified["majorCandidates"]["harris"],
        },
        certified.get("excludeColumns"),
        review.get("skipPrecinctRows"),
    )
    senate = civera_precinct_totals_by_locality(
        local_source(config, review["downBallotSourceId"]),
        review["downBallotCandidates"],
        certified.get("excludeColumns"),
        review.get("skipPrecinctRows"),
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"Virginia precinct review mismatch: missing={missing[:10]} extra={extra[:10]}")

    parsed_by_locality = defaultdict(int)
    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for locality, precinct in sorted(president):
        president_row = president[(locality, precinct)]
        harris = president_row["harris"]
        trump = president_row["trump"]
        other = president_row["other"]
        president_total = harris + trump + other
        if not president_total:
            continue
        senate_row = senate[(locality, precinct)]
        senate_dem = senate_row["dem"]
        senate_rep = senate_row["rep"]
        parsed_by_locality[locality] += president_total
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": locality,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    mismatches = [
        (locality, parsed_by_locality[locality], row["total"])
        for locality, row in locality_totals.items()
        if parsed_by_locality[locality] != row["total"]
    ]
    if mismatches:
        raise ValueError(f"Virginia precinct totals do not reconcile to locality totals: {mismatches[:10]}")

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_utah_canvass_pdf(config):
    review = config["reviewCharts"]
    president_rows, _candidate_labels, _row_count = certified_results_utah_statewide_canvass_pdf(config)
    president = {row["county"]: row for row in president_rows}
    governor = utah_canvass_contest_values(config, review["downBallotContest"])
    columns = review["downBallotColumns"]
    expected_totals = review.get("statewideTotals", {})
    parsed_totals = {
        "dem": sum(values[columns["dem"]] for values in governor.values()),
        "rep": sum(values[columns["rep"]] for values in governor.values()),
    }
    if expected_totals and parsed_totals != expected_totals:
        raise ValueError(f"Utah Governor parsed totals do not match expected totals: {parsed_totals} != {expected_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        president_row = president[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        down_ballot_dem = governor[county][columns["dem"]]
        down_ballot_rep = governor[county][columns["rep"]]
        senate_dem_total += down_ballot_dem
        senate_rep_total += down_ballot_rep
        review_rows.append(
            {
                "county": county,
                "ward": f"{county} County",
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - down_ballot_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - down_ballot_rep) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["warning"] = review.get("warning", "Utah review rows compare President to Governor, not U.S. Senate.")
    return review_rows, eta_analysis


def review_charts_utah_precinct_vote_share(config):
    review = config["reviewCharts"]
    manifest_path = local_source(config, review["sourceId"])
    source = source_map(config)[review["sourceId"]]
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    def localized_text(value):
        if isinstance(value, list):
            for item in value:
                if item.get("languageId") == "en" and item.get("text"):
                    return " ".join(item["text"].split())
            return " ".join(str(value[0].get("text", "")).split()) if value else ""
        return " ".join(str(value or "").split())

    def candidate_key(option):
        name = localized_text(option.get("name")).upper()
        if "KAMALA" in name and "HARRIS" in name:
            return "harris"
        if "DONALD" in name and "TRUMP" in name:
            return "trump"
        return "other"

    review_rows = []
    loaded_counties = []
    total_mismatches = []
    for county_info in manifest.get("counties", []):
        county = county_info["county"]
        county_path = manifest_path.parent / county_info["presidentFile"]
        with county_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        county_total = 0
        for row in payload.get("breakdownResults", []):
            president_total = int_text(row.get("voteTotal"))
            if not president_total:
                continue
            totals = defaultdict(int)
            for option in row.get("ballotOptions", []):
                totals[candidate_key(option)] += int_text(option.get("voteCount"))
            harris = totals["harris"]
            trump = totals["trump"]
            county_total += president_total
            review_rows.append(
                {
                    "county": county,
                    "ward": localized_text(row.get("precinct", {}).get("name")),
                    "total": president_total,
                    "harris": harris,
                    "trump": trump,
                    "harrisShare": round2((harris / president_total) * 100),
                    "trumpShare": round2((trump / president_total) * 100),
                    "demDropoff": 0,
                    "repDropoff": 0,
                    "sourceUrl": source["url"],
                }
            )
        expected_total = int_text(county_info.get("presidentVoteTotal"))
        if expected_total and county_total != expected_total:
            total_mismatches.append(
                {
                    "county": county,
                    "precinctTotal": county_total,
                    "contestTotal": expected_total,
                }
            )
        loaded_counties.append(county)

    harris_total = sum(row["harris"] for row in review_rows)
    trump_total = sum(row["trump"] for row in review_rows)
    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], harris_total, trump_total)
    eta_analysis["coverageMode"] = "voteShareOnly"
    eta_analysis["warning"] = review.get(
        "warning",
        "Utah review rows use official President precinct vote-share rows only; down-ballot comparison flags are disabled.",
    )
    eta_analysis["loadedCounties"] = sorted(loaded_counties)
    eta_analysis["skippedCounties"] = manifest.get("skippedCounties", [])
    eta_analysis["totalMismatches"] = total_mismatches
    eta_analysis["partialCoverage"] = bool(manifest.get("skippedCounties"))
    eta_analysis["sourceUrl"] = source["url"]
    return review_rows, eta_analysis


def review_charts_maine_county_town_xlsx(config):
    review = config["reviewCharts"]
    certified = config["certifiedResults"]
    president = maine_county_town_vote_rows(
        config,
        review.get("presidentSourceId", certified["sourceId"]),
        review.get("presidentSheet", certified.get("sheet", "President & VP")),
        certified["columns"],
    )
    senate = maine_county_town_vote_rows(
        config,
        review["downBallotSourceId"],
        review.get("downBallotSheet", "UNITED STATES SENATOR"),
        review["downBallotColumns"],
    )
    if set(president) != set(senate):
        missing = sorted(set(president) - set(senate))
        extra = sorted(set(senate) - set(president))
        raise ValueError(f"Maine review municipality mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for key in sorted(president):
        president_row = president[key]
        senate_row = senate[key]
        president_total = president_row.get("tbc") or (
            president_row["harris"] + president_row["trump"] + president_row.get("oliver", 0)
            + president_row.get("stein", 0) + president_row.get("west", 0)
            + president_row.get("others", 0)
        )
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate_row["dem"]
        senate_rep = senate_row["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": president_row["county"],
                "ward": president_row["municipality"],
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)
    eta_analysis["warning"] = review.get(
        "warning",
        "Maine U.S. Senate comparison maps Democratic presidential votes to the Democratic Senate candidate, not independent incumbent Angus King.",
    )
    return review_rows, eta_analysis


def review_charts_oklahoma_enr_zip(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])

    def candidate_keys(race, candidate_rules):
        keys = []
        for candidate in race.get("raceCandidates", []):
            candidate_name = candidate.get("candName", "")
            key = "other"
            for candidate_key, rule in candidate_rules.items():
                if new_york_column_matches(candidate_name, "", rule):
                    key = candidate_key
                    break
            keys.append(key)
        return keys

    def race_totals(archive, county_code_names, election, statewide_results, race_id, candidate_rules, label):
        race = next((item for item in election.get("races", []) if int(item.get("raceID")) == int(race_id)), None)
        if not race:
            raise ValueError(f"Could not find Oklahoma review {label} race {race_id!r}")
        keys = candidate_keys(race, candidate_rules)
        totals_by_county = {}
        for county_code, county in sorted(county_code_names.items(), key=lambda item: item[1]):
            county_payload = json.loads(archive.read(f"results-cw-{county_code}.json").decode("utf-8-sig"))
            race_results = next(
                (item for item in county_payload.get("results", []) if int(item.get("raceID")) == int(race_id)),
                None,
            )
            if not race_results:
                raise ValueError(f"Could not find Oklahoma county review {label} race {race_id!r} in county {county_code}")
            totals = defaultdict(int)
            for index, result in enumerate(race_results.get("candResults", [])):
                key = keys[index] if index < len(keys) else "other"
                votes = int_text(result.get("totalVotes"))
                totals[key] += votes
                totals["total"] += votes
            reported_total = int_text(race_results.get("totResults", {}).get("totalVotes"))
            if totals["total"] != reported_total:
                raise ValueError(f"Oklahoma review {label} total mismatch for {county}: {totals['total']} != {reported_total}")
            totals_by_county[county] = totals

        statewide_race = next(
            (item for item in statewide_results.get("results", []) if int(item.get("raceID")) == int(race_id)),
            None,
        )
        if not statewide_race:
            raise ValueError(f"Could not find Oklahoma statewide review {label} race {race_id!r}")
        parsed_totals = defaultdict(int)
        for totals in totals_by_county.values():
            for key, value in totals.items():
                parsed_totals[key] += value
        expected_totals = defaultdict(int)
        for index, result in enumerate(statewide_race.get("candResults", [])):
            key = keys[index] if index < len(keys) else "other"
            expected_totals[key] += int_text(result.get("totalVotes"))
        expected_totals["total"] = int_text(statewide_race.get("totResults", {}).get("totalVotes"))
        if dict(parsed_totals) != dict(expected_totals):
            raise ValueError(f"Oklahoma review {label} county totals do not match statewide totals: {dict(parsed_totals)} != {dict(expected_totals)}")
        return totals_by_county

    with zipfile.ZipFile(path) as archive:
        config_data = json.loads(archive.read("config.json").decode("utf-8-sig"))
        election = json.loads(archive.read("election-sw.json").decode("utf-8-sig"))
        statewide_results = json.loads(archive.read("results-sw.json").decode("utf-8-sig"))
        county_names = {
            re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
            for name in geometry_names_by_geoid(config).values()
        }
        county_code_names = {
            str(code): county_names.get(str(name).lower()) or f"{name} County"
            for name, code in zip(config_data["counties"]["Options"], config_data["counties"]["Values"])
            if code
        }
        president = race_totals(
            archive,
            county_code_names,
            election,
            statewide_results,
            review.get("presidentRaceId", 10001),
            review["majorCandidates"],
            "president",
        )
        down_ballot = race_totals(
            archive,
            county_code_names,
            election,
            statewide_results,
            review["downBallotRaceId"],
            review["downBallotCandidates"],
            "down-ballot",
        )

    review_rows = []
    dem_total = 0
    rep_total = 0
    for county in sorted(president):
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        down_ballot_dem = down_ballot[county]["dem"]
        down_ballot_rep = down_ballot[county]["rep"]
        dem_total += down_ballot_dem
        rep_total += down_ballot_rep
        review_rows.append(
            {
                "county": county,
                "ward": f"{county} County",
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - down_ballot_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - down_ballot_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], dem_total, rep_total)


def review_charts_oklahoma_precinct_csv_zip(config):
    review = config["reviewCharts"]
    county_path = local_source(config, review["sourceId"])
    precinct_path = local_source(config, review["precinctSourceId"])

    with zipfile.ZipFile(county_path) as county_archive:
        config_data = json.loads(county_archive.read("config.json").decode("utf-8-sig"))
        county_names = {
            re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).lower(): name
            for name in geometry_names_by_geoid(config).values()
        }
        county_code_names = {
            str(code): county_names.get(str(name).lower()) or f"{name} County"
            for name, code in zip(config_data["counties"]["Options"], config_data["counties"]["Values"])
            if code
        }

    race_candidate_rules = {
        str(review.get("presidentRaceId", 10001)): review["majorCandidates"],
        str(review["downBallotRaceId"]): review["downBallotCandidates"],
    }
    race_labels = {
        str(review.get("presidentRaceId", 10001)): "president",
        str(review["downBallotRaceId"]): "downBallot",
    }
    race_totals = {race_id: defaultdict(int) for race_id in race_candidate_rules}
    precinct_totals = defaultdict(lambda: {"president": defaultdict(int), "downBallot": defaultdict(int)})
    precinct_county_codes = {}

    with zipfile.ZipFile(precinct_path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Expected one Oklahoma precinct CSV in {precinct_path}, found {csv_names}")
        with archive.open(csv_names[0]) as handle:
            reader = csv.DictReader((line.decode("utf-8-sig") for line in handle))
            for row in reader:
                race_id = str(row.get("race_number", "")).strip()
                if race_id not in race_candidate_rules:
                    continue
                precinct = str(row.get("precinct", "")).strip()
                if not precinct:
                    continue
                county_code = precinct[:2]
                county = county_code_names.get(county_code)
                if not county:
                    raise ValueError(f"Could not map Oklahoma precinct {precinct!r} to a county")

                candidate_name = row.get("cand_name", "")
                votes = int_text(row.get("cand_tot_votes"))
                key = "other"
                for candidate_key, rule in race_candidate_rules[race_id].items():
                    if new_york_column_matches(candidate_name, "", rule):
                        key = candidate_key
                        break

                contest_key = race_labels[race_id]
                totals = precinct_totals[(county, precinct)][contest_key]
                totals[key] += votes
                totals["total"] += votes
                race_totals[race_id][key] += votes
                race_totals[race_id]["total"] += votes
                precinct_county_codes[(county, precinct)] = county_code

    expected_totals = review.get("statewideTotals", {})
    for label, race_id in (("president", str(review.get("presidentRaceId", 10001))), ("downBallot", str(review["downBallotRaceId"]))):
        expected_total = expected_totals.get(label)
        if expected_total is not None and race_totals[race_id]["total"] != int(expected_total):
            raise ValueError(
                f"Oklahoma {label} precinct total mismatch: {race_totals[race_id]['total']} != {expected_total}"
            )

    review_rows = []
    dem_total = 0
    rep_total = 0
    for county, precinct in sorted(precinct_totals, key=lambda item: (item[0], precinct_county_codes[item], item[1])):
        contests = precinct_totals[(county, precinct)]
        president = contests["president"]
        down_ballot = contests["downBallot"]
        president_total = president["total"]
        if not president_total:
            continue
        harris = president["harris"]
        trump = president["trump"]
        down_ballot_dem = down_ballot["dem"]
        down_ballot_rep = down_ballot["rep"]
        dem_total += down_ballot_dem
        rep_total += down_ballot_rep
        review_rows.append(
            {
                "county": county,
                "ward": precinct,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - down_ballot_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - down_ballot_rep) / trump) * 100) if trump else 0,
            }
        )

    eta_analysis = eta_analysis_from_review_rows(review_rows, review["policy"], dem_total, rep_total)
    if review.get("warning"):
        eta_analysis["warning"] = review["warning"]
    return review_rows, eta_analysis


def review_charts_montana_canvass_pdf(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    president_rows, _candidate_labels, _row_count = certified_results_montana_canvass_pdf(config)
    president = {row["county"]: row for row in president_rows}
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    try:
        start = lines.index(review.get("downBallotContest", "UNITED STATES SENATOR"))
    except ValueError as error:
        raise ValueError(f"Could not find Montana U.S. Senate contest in {path}") from error
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith(review.get("endMarker", "Page 3 of"))),
        None,
    )
    if end is None:
        raise ValueError(f"Could not find Montana U.S. Senate contest page boundary in {path}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<county>[A-Z][A-Z\s]+?)\s+"
        r"(?P<tester>\d+)\s+(?P<green>\d+)\s+(?P<libertarian>\d+)\s+(?P<sheehy>\d+)$"
    )
    total_pattern = re.compile(
        r"^Total\s+(?P<tester>\d+)\s+(?P<green>\d+)\s+(?P<libertarian>\d+)\s+(?P<sheehy>\d+)$"
    )
    senate_by_county = {}
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
        senate_by_county[county] = {key: int_text(value) for key, value in match.groupdict().items() if key != "county"}

    if reported_totals:
        parsed_totals = {
            "tester": sum(row["tester"] for row in senate_by_county.values()),
            "green": sum(row["green"] for row in senate_by_county.values()),
            "libertarian": sum(row["libertarian"] for row in senate_by_county.values()),
            "sheehy": sum(row["sheehy"] for row in senate_by_county.values()),
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"Montana Senate parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        if county not in senate_by_county:
            continue
        president_row = president[county]
        senate_row = senate_by_county[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate_row["tester"]
        senate_rep = senate_row["sheehy"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_nebraska_canvass_pdf(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    president_rows, _candidate_labels, _row_count = certified_results_nebraska_canvass_pdf(config)
    president = {row["county"]: row for row in president_rows}
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    contest = review.get("downBallotContest", "Member of the United States Senate – Two Year Term")
    try:
        start = lines.index(contest)
    except ValueError as error:
        raise ValueError(f"Could not find Nebraska U.S. Senate contest in {path}") from error
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith(review.get("endMarker", "General Election – November 5, 2024 Page | 17"))
        ),
        None,
    )
    if end is None:
        raise ValueError(f"Could not find Nebraska U.S. Senate contest page boundary in {path}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    number_pattern = re.compile(r"\d[\d,]*")
    header_lines = {
        "Pete Ricketts – Preston Love Jr. Pete Ricketts – Preston Love Jr.",
        "County (Republican) (Democratic) County (Republican) (Democratic)",
    }
    senate_by_county = {}
    reported_totals = None
    pending_county = None
    total_pending = False

    for line in lines[start + 1 : end]:
        numbers = number_pattern.findall(line)
        if line == "Total":
            total_pending = True
            continue
        if total_pending and len(numbers) == 2 and re.match(r"^\d", line):
            reported_totals = {
                "ricketts": int_text(numbers[0]),
                "love": int_text(numbers[1]),
            }
            total_pending = False
            continue
        if line in header_lines:
            continue
        if len(numbers) == 2:
            if re.match(r"^\d", line):
                raw_county = pending_county
                pending_county = None
            else:
                raw_county = re.sub(r"\s+\d[\d,]*\s+\d[\d,]*$", "", line).strip()
            if not raw_county:
                raise ValueError(f"Nebraska Senate row has votes without a county label: {line!r}")
            county = county_names.get(raw_county.upper()) or raw_county
            senate_by_county[county] = {
                "ricketts": int_text(numbers[0]),
                "love": int_text(numbers[1]),
            }
            continue
        if not numbers and not line.startswith("Member"):
            pending_county = line

    if reported_totals:
        parsed_totals = {
            "ricketts": sum(row["ricketts"] for row in senate_by_county.values()),
            "love": sum(row["love"] for row in senate_by_county.values()),
        }
        if parsed_totals != reported_totals:
            raise ValueError(f"Nebraska Senate parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        if county not in senate_by_county:
            continue
        president_row = president[county]
        senate_row = senate_by_county[county]
        president_total = president_row["total"]
        if not president_total:
            continue
        harris = president_row["harris"]
        trump = president_row["trump"]
        senate_dem = senate_row["love"]
        senate_rep = senate_row["ricketts"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_south_dakota_canvass_pdf(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    number_pattern = re.compile(r"\d[\d,]*")

    def parse_county_table(start_marker, end_marker, width, headers):
        try:
            start = lines.index(start_marker)
        except ValueError as error:
            raise ValueError(f"Could not find South Dakota contest {start_marker!r} in {path}") from error
        end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith(end_marker)), None)
        if end is None:
            raise ValueError(f"Could not find South Dakota contest boundary {end_marker!r} in {path}")
        rows = {}
        totals = None
        pending_county = None
        for line in lines[start + 1 : end]:
            numbers = number_pattern.findall(line)
            if line.startswith("Total") and len(numbers) == width:
                totals = [int_text(value) for value in numbers]
                continue
            if line in headers:
                continue
            if len(numbers) == width:
                if re.match(r"^\d", line):
                    raw_county = pending_county
                    pending_county = None
                else:
                    raw_county = re.sub(rf"\s+(?:\d[\d,]*\s+){{{width - 1}}}\d[\d,]*$", "", line).strip()
                if not raw_county:
                    raise ValueError(f"South Dakota row has votes without a county label: {line!r}")
                county = county_names.get(raw_county.upper()) or f"{raw_county} County"
                rows[county] = [int_text(value) for value in numbers]
                continue
            if not numbers and line not in headers:
                pending_county = line
        return rows, totals

    president_values, president_totals = parse_county_table(
        review.get("presidentContest", "Presidential Electors"),
        review.get("presidentEndMarker", "United States Representative"),
        4,
        {
            "Kamala D. Harris Chase Oliver and Donald J. Trump Robert F. Kennedy,",
            "and Tim Walz - Mike ter Maat - and JD Vance - Jr. and Nicole",
            "DEM LIB REP Shanahan - IND",
            "County",
        },
    )
    house_by_county, reported_totals = parse_county_table(
        review.get("downBallotContest", "United States Representative"),
        review.get("endMarker", "Public Utilities Commissioner"),
        2,
        {"Sheryl Johnson - Dusty Johnson -", "County", "DEM REP"},
    )

    if president_totals:
        parsed_president_totals = [sum(row[index] for row in president_values.values()) for index in range(4)]
        if parsed_president_totals != president_totals:
            raise ValueError(f"South Dakota President parsed totals do not match PDF totals: {parsed_president_totals} != {president_totals}")

    if reported_totals:
        parsed_totals = {
            "dem": sum(row[0] for row in house_by_county.values()),
            "rep": sum(row[1] for row in house_by_county.values()),
        }
        reported_totals = {"dem": reported_totals[0], "rep": reported_totals[1]}
        if parsed_totals != reported_totals:
            raise ValueError(f"South Dakota House parsed totals do not match PDF totals: {parsed_totals} != {reported_totals}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president_values):
        if county not in house_by_county:
            continue
        president_row = president_values[county]
        house_row = house_by_county[county]
        harris = president_row[0]
        trump = president_row[2]
        president_total = sum(president_row)
        if not president_total:
            continue
        senate_dem = house_row[0]
        senate_rep = house_row[1]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
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

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def review_charts_delaware_county_html(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    document = path.read_text(encoding="utf-8")
    start = document.find(review.get("sectionMarker", 'id="bycounty"'))
    end = document.find(review.get("endMarker", 'id="bycountyw"'), start)
    if start < 0 or end < 0:
        raise ValueError(f"Could not find Delaware by-county results section in {path}")
    section = document[start:end]
    county_columns = review["countyColumns"]
    state_index = review.get("columnIndexes", {}).get(review.get("stateColumn", "State"))

    def contest_totals(contest_class, candidate_rules):
        contest_index = section.find(contest_class)
        if contest_index < 0:
            raise ValueError(f"Could not find Delaware contest {contest_class!r} in {path}")
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", section[contest_index:], flags=re.DOTALL | re.IGNORECASE)
        if not tbody_match:
            raise ValueError(f"Could not find Delaware by-county table body for {contest_class!r} in {path}")
        totals_by_county = defaultdict(lambda: defaultdict(int))
        for row_html in re.findall(r"<tr>(.*?)</tr>", tbody_match.group(1), flags=re.DOTALL | re.IGNORECASE):
            cells = [
                clean_html_cell(cell)
                for cell in re.findall(r"<td(?:\s[^>]*)?>(.*?)</td>", row_html, flags=re.DOTALL | re.IGNORECASE)
            ]
            if len(cells) < 4:
                continue
            candidate = cells[0]
            party = cells[1] if len(cells) > 1 else ""
            key = "other"
            for candidate_key, rule in candidate_rules.items():
                if new_york_column_matches(candidate, party, rule):
                    key = candidate_key
                    break
            county_sum = 0
            for county, column_index in county_columns.items():
                votes = int_text(cells[column_index])
                totals_by_county[county][key] += votes
                totals_by_county[county]["total"] += votes
                county_sum += votes
            if state_index is not None and state_index < len(cells):
                reported_state_total = int_text(cells[state_index])
                if county_sum != reported_state_total:
                    raise ValueError(
                        f"Delaware county totals for {candidate!r} do not match State column: "
                        f"{county_sum} != {reported_state_total}"
                    )
        return totals_by_county

    president = contest_totals(
        review.get("presidentContestClass", "PresidentandVicePresident"),
        review["majorCandidates"],
    )
    down_ballot = contest_totals(
        review.get("downBallotContestClass", "USSenator"),
        review["downBallotCandidates"],
    )

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county in sorted(president):
        if county not in down_ballot:
            continue
        president_total = president[county]["total"]
        if not president_total:
            continue
        harris = president[county]["harris"]
        trump = president[county]["trump"]
        senate_dem = down_ballot[county]["dem"]
        senate_rep = down_ballot[county]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": county,
                "ward": county,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def delaware_county_for_election_district(label):
    match = re.search(r"Election District\s+(\d+)-", label)
    if not match:
        raise ValueError(f"Delaware election district label is not recognized: {label!r}")
    representative_district = int(match.group(1))
    if representative_district <= 27:
        return "New Castle County"
    if representative_district <= 34:
        return "Kent County"
    return "Sussex County"


def delaware_election_district_totals(section, contest_class, candidate_rules):
    pattern = re.compile(
        rf"<h4[^>]*class=[\"'][^\"']*electiondistrict-title[^\"']*{re.escape(contest_class)}"
        rf"[^\"']*ElectionDistrict\d+[^\"']*[\"'][^>]*>(.*?)</h4>\s*"
        rf"<table[^>]*class=[\"'][^\"']*{re.escape(contest_class)}[^\"']*[\"'][^>]*>.*?"
        rf"<tbody>(.*?)</tbody>",
        flags=re.DOTALL | re.IGNORECASE,
    )
    output = defaultdict(lambda: defaultdict(int))
    for district_html, body_html in pattern.findall(section):
        label = clean_html_cell(district_html)
        county = delaware_county_for_election_district(label)
        item = output[(county, label)]
        for row_html in re.findall(r"<tr>(.*?)</tr>", body_html, flags=re.DOTALL | re.IGNORECASE):
            cells = [
                clean_html_cell(cell)
                for cell in re.findall(r"<td(?:\s[^>]*)?>(.*?)</td>", row_html, flags=re.DOTALL | re.IGNORECASE)
            ]
            if len(cells) < 6:
                continue
            candidate = cells[0]
            party = cells[1]
            key = "other"
            for candidate_key, rule in candidate_rules.items():
                if new_york_column_matches(candidate, party, rule):
                    key = candidate_key
                    break
            votes = int_text(cells[5])
            item[key] += votes
            item["total"] += votes
    return output


def review_charts_delaware_election_district_html(config):
    review = config["reviewCharts"]
    path = local_source(config, review["sourceId"])
    document = path.read_text(encoding="utf-8")
    start = document.find(review.get("sectionMarker", 'id="byelectiondist"'))
    end = document.find(review.get("endMarker", 'id="bycounty"'), start)
    if start < 0 or end < 0:
        raise ValueError(f"Could not find Delaware election-district results section in {path}")
    section = document[start:end]
    president = delaware_election_district_totals(
        section,
        review.get("presidentContestClass", "PresidentandVicePresident"),
        review["majorCandidates"],
    )
    president = {key: value for key, value in president.items() if value["total"]}
    down_ballot = delaware_election_district_totals(
        section,
        review.get("downBallotContestClass", "USSenator"),
        review["downBallotCandidates"],
    )
    down_ballot = {key: value for key, value in down_ballot.items() if key in president}
    if set(president) != set(down_ballot):
        missing = sorted(set(president) - set(down_ballot))
        extra = sorted(set(down_ballot) - set(president))
        raise ValueError(f"Delaware election-district review mismatch: missing={missing[:10]} extra={extra[:10]}")

    review_rows = []
    senate_dem_total = 0
    senate_rep_total = 0
    for county, district in sorted(president):
        president_total = president[(county, district)]["total"]
        if not president_total:
            continue
        harris = president[(county, district)]["harris"]
        trump = president[(county, district)]["trump"]
        senate_dem = down_ballot[(county, district)]["dem"]
        senate_rep = down_ballot[(county, district)]["rep"]
        senate_dem_total += senate_dem
        senate_rep_total += senate_rep
        review_rows.append(
            {
                "county": county,
                "ward": district,
                "total": president_total,
                "harris": harris,
                "trump": trump,
                "harrisShare": round2((harris / president_total) * 100),
                "trumpShare": round2((trump / president_total) * 100),
                "demDropoff": round2(((harris - senate_dem) / harris) * 100) if harris else 0,
                "repDropoff": round2(((trump - senate_rep) / trump) * 100) if trump else 0,
            }
        )

    return review_rows, eta_analysis_from_review_rows(review_rows, review["policy"], senate_dem_total, senate_rep_total)


def first_worksheet_names(workbook_path):
    with zipfile.ZipFile(workbook_path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        return [
            sheet.attrib["name"]
            for sheet in workbook.findall("main:sheets/main:sheet", NS)
            if sheet.attrib.get("name")
        ]


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


def turnout_data_alaska_enr_house_district(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    contest_title = turnout.get("contestTitle", "U.S. President / Vice President")
    district_label_prefix = turnout.get("districtLabelPrefix", "State House District")
    exclude_districts = set(str(value).zfill(2) for value in turnout.get("excludeDistricts", []))
    expected_districts = {str(index).zfill(2) for index in range(1, config.get("expected", {}).get("countyRows", 0) + 1)}
    method_columns = turnout.get(
        "methodColumns",
        {
            "electionDayBallots": "Election Day_ballots",
            "absenteeBallots": "Absentee_ballots",
            "earlyVotingBallots": "Early Voting_ballots",
            "questionBallots": "Question_ballots",
            "remoteBallots": "Remote_ballots",
        },
    )

    def district_code(row):
        precinct_id = str(row.get("Pct_Id") or "").strip()
        if precinct_id:
            return precinct_id.split("-")[0].zfill(2)
        match = re.match(r"District\s+(\d+)\s+-\s+", str(row.get("Precinct_name") or ""))
        return match.group(1).zfill(2) if match else ""

    by_district = defaultdict(lambda: defaultdict(int))
    excluded = defaultdict(lambda: defaultdict(int))
    seen_rows = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("Contest_title") != contest_title:
                continue
            district = district_code(row)
            if not district:
                raise ValueError(f"Alaska turnout row does not map to a district: {row.get('Precinct_name')!r}")
            row_key = (district, row.get("Pct_Id") or "", row.get("Precinct_name") or "")
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            target = excluded[district] if district in exclude_districts else by_district[district]
            target["registeredVoters"] += int_text(row.get("Reg_voters"))
            target["ballotsCast"] += int_text(row.get("total_ballots"))
            target["underVotes"] += int_text(row.get("total_under_votes"))
            target["overVotes"] += int_text(row.get("total_over_votes"))
            for output_key, column in method_columns.items():
                target[output_key] += int_text(row.get(column))

    missing = sorted(expected_districts - set(by_district))
    extra = sorted(set(by_district) - expected_districts)
    if missing or extra:
        raise ValueError(f"Alaska turnout district mismatch: missing={missing}; extra={extra}")

    output_rows = []
    for district in sorted(by_district, key=int):
        totals = by_district[district]
        district_name = f"{district_label_prefix} {int(district)}"
        row = {
            "county": district_name,
            "municipality": district_name,
            "ward": district_name,
            "ballotsCast": totals["ballotsCast"],
            "registeredVoters": totals["registeredVoters"],
            "turnoutPct": round2((totals["ballotsCast"] / totals["registeredVoters"]) * 100)
            if totals["registeredVoters"]
            else None,
            "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
            "denominatorType": turnout.get("denominatorType", "registeredVoters"),
            "sourceUrl": source["url"],
            "sourceLevel": turnout["sourceLevel"],
            "sourceTitle": turnout.get("sourceTitle"),
            "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
            "coverageStatus": turnout.get("coverageStatus", "loaded"),
            "voteMethodFields": turnout.get("voteMethodFields", []),
            "notes": turnout["notes"],
            "warningRequired": turnout["warningRequired"],
            "underVotes": totals["underVotes"],
            "overVotes": totals["overVotes"],
        }
        for output_key in method_columns:
            row[output_key] = totals[output_key]
        output_rows.append(row)

    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {key: sum(row[key] for row in output_rows) for key in expected_totals}
        if parsed_totals != expected_totals:
            raise ValueError(f"Alaska turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    excluded_totals = turnout.get("excludedDistrictTotals", {})
    if excluded_totals:
        parsed_excluded = {
            district: {key: values[key] for key in totals}
            for district, totals in excluded.items()
            if district in exclude_districts
            for values in [dict(totals)]
        }
        if parsed_excluded != excluded_totals:
            raise ValueError(f"Alaska excluded turnout totals do not match expected totals: {parsed_excluded} != {excluded_totals}")

    return turnout_payload(config, turnout, path, source, output_rows)


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


def turnout_data_montana_canvass_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    try:
        start = lines.index("Number of Registered Votes Voter")
    except ValueError as error:
        raise ValueError(f"Could not find Montana turnout table in {path}") from error

    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("Page 1 of")),
        None,
    )
    if end is None:
        raise ValueError(f"Could not find Montana turnout table boundary in {path}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<county>[A-Z][A-Z\s]+?)\s+"
        r"(?P<precincts>\d+)\s+(?P<registered>\d+)\s+(?P<ballots>\d+)\s+"
        r"(?P<turnout>\d+(?:\.\d+)?)%$"
    )
    total_pattern = re.compile(
        r"^Total\s+(?P<precincts>\d+)\s+(?P<registered>\d+)\s+(?P<ballots>\d+)\s+"
        r"(?P<turnout>\d+(?:\.\d+)?)%$"
    )
    output_rows = []
    reported_total = None

    for line in lines[start + 1 : end]:
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {key: int_text(value) for key, value in total_match.groupdict().items() if key != "turnout"}
            continue
        match = row_pattern.match(line)
        if not match:
            continue
        raw_county = match.group("county")
        county = county_names.get(raw_county) or f"{raw_county.title()} County"
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "precincts": int_text(match.group("precincts")),
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Montana turnout parsed {len(output_rows)} county rows")
    if reported_total:
        parsed_total = {
            "precincts": sum(row["precincts"] for row in output_rows),
            "registered": sum(row["registeredVoters"] for row in output_rows),
            "ballots": sum(row["ballotsCast"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"Montana turnout totals do not match PDF totals: {parsed_total} != {reported_total}")

    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": path.name,
            "sourceUrl": source["url"],
        },
        "rows": output_rows,
    }


def turnout_data_california_participation_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_prefixes = sorted(
        ((re.sub(r"\s+COUNTY$", "", name, flags=re.IGNORECASE), name) for name in geometry_names_by_geoid(config).values()),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    total_pattern = re.compile(
        r"^State Total\s+(?P<precincts>\d[\d,]*)\s+(?P<eligible>\d[\d,]*)\s+"
        r"(?P<registered>\d[\d,]*)\s+(?P<precinctVotes>\d[\d,]*)\s+"
        r"(?P<voteByMail>\d[\d,]*)\s+(?P<ballots>\d[\d,]*)$"
    )
    output_rows = []
    reported_total = None

    for line in lines:
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {key: int_text(value) for key, value in total_match.groupdict().items()}
            continue
        county = None
        values = []
        for bare_county, full_county in county_prefixes:
            normalized_line = line.upper()
            normalized_county = bare_county.upper()
            if not (normalized_line.startswith(f"{normalized_county} ") or normalized_line.startswith(f"{normalized_county} * ")):
                continue
            county = full_county
            remainder = line[len(bare_county) :].strip()
            if remainder.startswith("*"):
                remainder = remainder[1:].strip()
            values = re.findall(r"\d[\d,]*", remainder)
            break
        if county is None or len(values) < 6:
            continue
        precincts, eligible, registered, precinct_votes, vote_by_mail, ballots = [int_text(value) for value in values[:6]]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "eligibleVoters": eligible,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "precinctVotes": precinct_votes,
                "voteByMailVotes": vote_by_mail,
                "precincts": precincts,
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"California turnout parsed {len(output_rows)} county rows")
    if reported_total:
        parsed_total = {
            "precincts": sum(row["precincts"] for row in output_rows),
            "eligible": sum(row["eligibleVoters"] for row in output_rows),
            "registered": sum(row["registeredVoters"] for row in output_rows),
            "precinctVotes": sum(row["precinctVotes"] for row in output_rows),
            "voteByMail": sum(row["voteByMailVotes"] for row in output_rows),
            "ballots": sum(row["ballotsCast"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"California turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_colorado_general_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    try:
        start = next(
            index
            for index, line in enumerate(lines)
            if line == "2024 General Election Turnout"
            and index + 1 < len(lines)
            and lines[index + 1] == "(calculated as a percentage of registered voters)"
        )
        table_start = next(
            index
            for index in range(start, len(lines))
            if lines[index] == "County Registered Voters Ballots Cast Turnout %"
        )
        end = next(index for index in range(table_start + 1, len(lines)) if lines[index].startswith("Total "))
    except StopIteration as exc:
        raise ValueError(f"Could not locate Colorado general-election registered-voter turnout table in {path}") from exc

    county_lookup = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<county>[A-Za-z ]+?)\s+"
        r"(?P<registered>[\d,]+)\s+"
        r"(?P<ballots>[\d,]+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )
    total_pattern = re.compile(r"^Total\s+(?P<registered>[\d,]+)\s+(?P<ballots>[\d,]+)\s+(?P<pct>\d+(?:\.\d+)?)%$")
    reported_total_match = total_pattern.match(lines[end])
    reported_total = {
        "registeredVoters": int_text(reported_total_match.group("registered")),
        "ballotsCast": int_text(reported_total_match.group("ballots")),
    } if reported_total_match else None

    output_rows = []
    for line in lines[table_start + 1 : end]:
        match = row_pattern.match(line)
        if not match:
            continue
        county = county_lookup.get(match.group("county").upper())
        if not county:
            raise ValueError(f"Unexpected Colorado turnout county row {match.group('county')!r}")
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Colorado turnout parsed {len(output_rows)} county rows")
    if reported_total:
        parsed_total = {
            "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
            "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"Colorado turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
            "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Colorado turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_indiana_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<county>[A-Za-z][A-Za-z. ]+?)\s+(?P<registered>\d[\d,]*)\s+"
        r"(?P<ballots>\d[\d,]*)\s+\d+\s*%\s+(?P<electionDay>\d[\d,]*)\s+"
        r"(?P<absentee>\d[\d,]*)\s+\d+\s*%$"
    )
    output_rows = []
    for line in lines:
        match = row_pattern.match(line)
        if not match:
            continue
        raw_county = match.group("county").strip()
        county = county_names.get(raw_county.upper())
        if not county:
            continue
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "electionDayVotes": int_text(match.group("electionDay")),
                "absenteeVotes": int_text(match.group("absentee")),
            }
        )
    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Indiana turnout parsed {len(output_rows)} county rows")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_new_jersey_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name.upper()): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<county>[A-Za-z ]+?)\s+(?P<registered>\d[\d,]*)\s+"
        r"(?P<ballots>\d[\d,]*)\s+(?P<rejected>\d[\d,]*)\s+\d+%\s+"
        r"(?P<districts>\d[\d,]*)$"
    )
    total_rejected_pattern = re.compile(r"^(?P<rejected>\d[\d,]*)\s+\d+%$")
    total_pattern = re.compile(r"^TOTAL\s+(?P<registered>\d[\d,]*)\s+(?P<ballots>\d[\d,]*)\s+(?P<districts>\d[\d,]*)$")
    output_rows = []
    reported_total = None
    pending_total_rejected = None
    for line in lines:
        total_rejected_match = total_rejected_pattern.match(line)
        if total_rejected_match:
            pending_total_rejected = int_text(total_rejected_match.group("rejected"))
            continue
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {key: int_text(value) for key, value in total_match.groupdict().items()}
            if pending_total_rejected is not None:
                reported_total["rejected"] = pending_total_rejected
            continue
        match = row_pattern.match(line)
        if not match:
            continue
        raw_county = match.group("county").strip()
        county = county_names.get(raw_county.upper())
        if not county:
            continue
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "rejectedBallots": int_text(match.group("rejected")),
                "electionDistricts": int_text(match.group("districts")),
            }
        )
    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"New Jersey turnout parsed {len(output_rows)} county rows")
    if reported_total:
        parsed_total = {
            "registered": sum(row["registeredVoters"] for row in output_rows),
            "ballots": sum(row["ballotsCast"] for row in output_rows),
            "districts": sum(row["electionDistricts"] for row in output_rows),
            "rejected": sum(row["rejectedBallots"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"New Jersey turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_connecticut_statement_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    aliases = turnout.get("townAliases", {})
    subdivision_lookup = connecticut_subdivision_lookup(config, turnout["townMapSourceId"], aliases)
    town_lookup = {
        re.sub(r"[^a-z0-9]+", "", value["town"].lower()): value
        for value in subdivision_lookup.values()
    }

    pages = turnout.get("pages", [157, 158, 159, 160, 161, 162])
    pdf_pages = extract_pdf_items(path, min(pages), max(pages))
    page_map = {page["pageNumber"]: page["items"] for page in pdf_pages}
    town_rows = {}

    def numeric_value(value):
        return int_text(value.replace("%", ""))

    for page_number in pages:
        items = page_map.get(page_number)
        if not items:
            raise ValueError(f"Connecticut turnout page {page_number} was not extracted from {path}")
        town_columns = []
        for item in items:
            value = item["value"]
            town_key = re.sub(r"[^a-z0-9]+", "", value.lower())
            if 75 <= item["y"] <= 95 and town_key in town_lookup:
                town_columns.append({"x": item["x"], "town": town_lookup[town_key]["town"]})
        town_columns = sorted(town_columns, key=lambda item: item["x"])
        if not town_columns:
            raise ValueError(f"Connecticut turnout page {page_number} has no town columns")

        min_x = min(item["x"] for item in town_columns) - 1
        max_x = max(item["x"] for item in town_columns) + 1

        def values_by_column(y_min, y_max, *, percent=False):
            values = {}
            pattern = r"^\d+(?:\.\d+)?%$" if percent else r"^\d[\d,]*$"
            for item in items:
                if not (min_x <= item["x"] <= max_x and y_min <= item["y"] <= y_max):
                    continue
                if not re.match(pattern, item["value"]):
                    continue
                column = min(town_columns, key=lambda town: abs(town["x"] - item["x"]))
                if abs(column["x"] - item["x"]) > 1.5:
                    continue
                values[column["town"]] = float(item["value"].replace("%", "")) if percent else numeric_value(item["value"])
            missing = [column["town"] for column in town_columns if column["town"] not in values]
            if missing:
                raise ValueError(
                    f"Connecticut turnout page {page_number} missing values for: {', '.join(missing)}"
                )
            return values

        checked_by_town = values_by_column(205, 230)
        registered_by_town = values_by_column(155, 175)
        turnout_pct_by_town = values_by_column(265, 280, percent=True)
        for column in town_columns:
            town = column["town"]
            if town in town_rows:
                raise ValueError(f"Connecticut turnout town was parsed twice: {town}")
            checked = checked_by_town[town]
            registered = registered_by_town[town]
            reported_pct = turnout_pct_by_town[town]
            computed_pct = round2((checked / registered) * 100) if registered else None
            if computed_pct is not None and abs(computed_pct - reported_pct) > 0.01:
                raise ValueError(
                    f"Connecticut turnout percent mismatch for {town}: {computed_pct} != {reported_pct}"
                )
            town_rows[town] = {
                "ballotsCast": checked,
                "registeredVoters": registered,
            }

    if len(town_rows) != 169:
        raise ValueError(f"Connecticut turnout parsed {len(town_rows)} town rows")

    by_county = defaultdict(lambda: defaultdict(int))
    missing = []
    for town, row in town_rows.items():
        mapped = town_lookup.get(re.sub(r"[^a-z0-9]+", "", town.lower()))
        if not mapped:
            missing.append(town)
            continue
        totals = by_county[mapped["county"]]
        totals["ballotsCast"] += row["ballotsCast"]
        totals["registeredVoters"] += row["registeredVoters"]
        totals["townRows"] += 1
    if missing:
        raise ValueError(f"Connecticut turnout towns could not be mapped: {', '.join(sorted(missing))}")

    output_rows = []
    for county, totals in sorted(by_county.items()):
        registered = totals["registeredVoters"]
        ballots = totals["ballotsCast"]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": f"{county} planning region",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": config.get("authority"),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "townRows": totals["townRows"],
            }
        )

    expected_totals = turnout.get("statewideTotals", {})
    parsed_totals = {
        "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
        "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
    }
    if expected_totals and parsed_totals != expected_totals:
        raise ValueError(f"Connecticut turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")
    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Connecticut turnout rolled up to {len(output_rows)} planning-region rows")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_maryland_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_lookup = {}
    for name in geometry_names_by_geoid(config).values():
        bare_name = re.sub(r"\s+County$", "", name, flags=re.IGNORECASE)
        county_lookup[name.upper()] = name
        county_lookup[bare_name.upper()] = name
    county_lookup["BALTIMORE CITY"] = "Baltimore city"
    county_lookup["SAINT MARY'S"] = "St. Mary's County"

    row_pattern = re.compile(
        r"^(?P<county>[A-Za-z][A-Za-z' .]+?)\s+"
        r"(?P<electionDay>[\d,]+)\s+"
        r"(?P<early>[\d,]+)\s+"
        r"(?P<mail>[\d,]+)\s+"
        r"(?P<provisional>[\d,]+)\s+"
        r"(?P<eligible>[\d,]+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )
    total_pattern = re.compile(
        r"^TOTAL\s+"
        r"(?P<electionDay>[\d,]+)\s+"
        r"(?P<early>[\d,]+)\s+"
        r"(?P<mail>[\d,]+)\s+"
        r"(?P<provisional>[\d,]+)\s+"
        r"(?P<eligible>[\d,]+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )
    output_rows = []
    reported_total = None
    in_statewide_table = False

    for line in lines:
        if line == "Statewide":
            in_statewide_table = True
            continue
        if not in_statewide_table or line.startswith("LBE "):
            continue
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {key: int_text(total_match.group(key)) for key in ["electionDay", "early", "mail", "provisional", "eligible"]}
            break
        match = row_pattern.match(line)
        if not match:
            continue
        county = county_lookup.get(match.group("county").strip().upper())
        if not county:
            raise ValueError(f"Unexpected Maryland turnout county row {match.group('county')!r}")
        election_day = int_text(match.group("electionDay"))
        early = int_text(match.group("early"))
        mail = int_text(match.group("mail"))
        provisional = int_text(match.group("provisional"))
        eligible = int_text(match.group("eligible"))
        ballots = election_day + early + mail + provisional
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "eligibleVoters": eligible,
                "turnoutPct": round2((ballots / eligible) * 100) if eligible else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "eligibleVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "electionDayVotes": election_day,
                "earlyVotes": early,
                "voteByMailVotes": mail,
                "provisionalVotes": provisional,
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Maryland turnout parsed {len(output_rows)} county rows")
    if reported_total:
        parsed_total = {
            "electionDay": sum(row["electionDayVotes"] for row in output_rows),
            "early": sum(row["earlyVotes"] for row in output_rows),
            "mail": sum(row["voteByMailVotes"] for row in output_rows),
            "provisional": sum(row["provisionalVotes"] for row in output_rows),
            "eligible": sum(row["eligibleVoters"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"Maryland turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "eligibleVoters": sum(row["eligibleVoters"] for row in output_rows),
            "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
            "electionDayVotes": sum(row["electionDayVotes"] for row in output_rows),
            "earlyVotes": sum(row["earlyVotes"] for row in output_rows),
            "voteByMailVotes": sum(row["voteByMailVotes"] for row in output_rows),
            "provisionalVotes": sum(row["provisionalVotes"] for row in output_rows),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Maryland turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_south_dakota_election_returns_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    try:
        start = next(
            index
            for index, line in enumerate(lines)
            if line == "2024 GENERAL ELECTION" and index + 1 < len(lines) and lines[index + 1] == "Voter Turnout"
        )
        end = next(index for index in range(start, len(lines)) if lines[index].startswith("TOTAL "))
    except StopIteration as exc:
        raise ValueError(f"Could not locate South Dakota general-election turnout table in {path}") from exc

    section_lines = lines[start : end + 1]
    for index, line in enumerate(section_lines):
        if line == "Oglala":
            section_lines[index] = ""
            lakota_index = next(
                (
                    later_index
                    for later_index in range(index + 1, len(section_lines))
                    if section_lines[later_index].startswith("Lakota ")
                ),
                None,
            )
            if lakota_index is not None:
                section_lines[lakota_index] = f"Oglala {section_lines[lakota_index]}"
            break

    county_lookup = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_pattern = "|".join(re.escape(name) for name in sorted(county_lookup, key=len, reverse=True))
    row_pattern = re.compile(
        rf"(?P<county>{county_pattern})\s+"
        r"(?P<registered>[\d,]+)\s+"
        r"(?P<ballots>[\d,]+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%"
    )
    total_match = re.match(
        r"^TOTAL\s+(?P<registered>[\d,]+)\s+(?P<ballots>[\d,]+)\s+(?P<pct>\d+(?:\.\d+)?)%$",
        lines[end],
    )
    reported_total = {
        "registeredVoters": int_text(total_match.group("registered")),
        "ballotsCast": int_text(total_match.group("ballots")),
    } if total_match else None

    section_text = " ".join(line for line in section_lines if line)
    output_rows = []
    for match in row_pattern.finditer(section_text):
        county = county_lookup[match.group("county")]
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"South Dakota turnout parsed {len(output_rows)} county rows")
    if reported_total:
        parsed_total = {
            "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
            "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"South Dakota turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
            "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"South Dakota turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_idaho_turnout_html(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    text = path.read_text(encoding="utf-8", errors="replace")
    data_match = next(
        (
            match
            for match in re.finditer(r'"data":(\{.*?\}),"columns":', text, flags=re.DOTALL)
            if "Election Day Registrations" in match.group(1)
        ),
        None,
    )
    if not data_match:
        raise ValueError(f"Could not find Idaho turnout data table in {path}")
    data = json.loads(data_match.group(1))
    output_rows = []
    for index, county in enumerate(data["County"]):
        if county == "Statewide":
            continue
        registered = int_text(data["Registered Voters"][index])
        ballots = int_text(data["Ballots Cast"][index])
        output_rows.append(
            {
                "county": f"{county} County",
                "municipality": f"{county} County",
                "ward": f"{county} County",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "electionDayRegistrations": int_text(data["Election Day Registrations"][index]),
            }
        )
    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Idaho turnout parsed {len(output_rows)} county rows")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_iowa_turnout_csv(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    county_lookup = {
        re.sub(r"\s+COUNTY$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    output_rows = []
    reported_total = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            county_name = (row.get("county") or "").strip()
            if not county_name:
                continue
            values = {
                "electionDayVoters": int_text(row.get("electionDayVoters")),
                "absenteeVoters": int_text(row.get("absenteeVoters")),
                "ballotsCast": int_text(row.get("ballotsCast")),
                "activeVoters": int_text(row.get("activeVoters")),
                "inactiveVoters": int_text(row.get("inactiveVoters")),
                "totalRegisteredVoters": int_text(row.get("totalRegisteredVoters")),
            }
            if county_name.upper() == "TOTAL":
                reported_total = values
                continue
            county = county_lookup.get(county_name.upper())
            if not county:
                raise ValueError(f"Could not map Iowa turnout county {county_name!r}")
            if values["activeVoters"] + values["inactiveVoters"] != values["totalRegisteredVoters"]:
                raise ValueError(f"Iowa turnout registered-voter parts do not sum for {county}")
            if values["electionDayVoters"] + values["absenteeVoters"] != values["ballotsCast"]:
                raise ValueError(f"Iowa turnout vote-method parts do not sum for {county}")
            output_rows.append(
                {
                    "county": county,
                    "municipality": county,
                    "ward": county,
                    "ballotsCast": values["ballotsCast"],
                    "registeredVoters": values["totalRegisteredVoters"],
                    "turnoutPct": round2((values["ballotsCast"] / values["totalRegisteredVoters"]) * 100)
                    if values["totalRegisteredVoters"]
                    else None,
                    "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                    "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                    "sourceUrl": source["url"],
                    "sourceLevel": turnout["sourceLevel"],
                    "sourceTitle": turnout.get("sourceTitle"),
                    "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                    "coverageStatus": turnout.get("coverageStatus", "loaded"),
                    "voteMethodFields": turnout.get("voteMethodFields", []),
                    "notes": turnout["notes"],
                    "warningRequired": turnout["warningRequired"],
                    "electionDayVoters": values["electionDayVoters"],
                    "absenteeVoters": values["absenteeVoters"],
                    "activeVoters": values["activeVoters"],
                    "inactiveVoters": values["inactiveVoters"],
                    "activeTurnoutPct": float(row.get("activeTurnoutPct") or 0),
                    "publishedTotalTurnoutPct": float(row.get("totalTurnoutPct") or 0),
                }
            )

    expected_counties = set(geometry_names_by_geoid(config).values())
    parsed_counties = {row["county"] for row in output_rows}
    if parsed_counties != expected_counties:
        raise ValueError(
            f"Iowa turnout county mismatch: missing={sorted(expected_counties - parsed_counties)}; "
            f"extra={sorted(parsed_counties - expected_counties)}"
        )
    if not reported_total:
        raise ValueError("Iowa turnout CSV is missing the published Total row")
    parsed_total = {
        "electionDayVoters": sum(row["electionDayVoters"] for row in output_rows),
        "absenteeVoters": sum(row["absenteeVoters"] for row in output_rows),
        "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
        "activeVoters": sum(row["activeVoters"] for row in output_rows),
        "inactiveVoters": sum(row["inactiveVoters"] for row in output_rows),
        "totalRegisteredVoters": sum(row["registeredVoters"] for row in output_rows),
    }
    if parsed_total != reported_total:
        raise ValueError(f"Iowa turnout totals do not match CSV Total row: {parsed_total} != {reported_total}")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_expected = {
            "registeredVoters" if key == "totalRegisteredVoters" else key: parsed_total[key]
            for key in parsed_total
            if key in expected_totals or (key == "totalRegisteredVoters" and "registeredVoters" in expected_totals)
        }
        if parsed_expected != expected_totals:
            raise ValueError(f"Iowa turnout expected totals do not match: {parsed_expected} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_illinois_precinct_csv(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    county_lookup = {
        re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", county, flags=re.IGNORECASE).upper()): county
        for county in geometry_names_by_geoid(config).values()
    }
    jurisdiction_aliases = {
        key.upper(): value
        for key, value in config.get("certifiedResults", {}).get("jurisdictionAliases", {}).items()
    }
    by_precinct = defaultdict(lambda: {"registeredVoters": 0, "ballotsCast": 0, "rawJurisdiction": ""})
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("ContestName") != turnout.get("contestName", "PRESIDENT AND VICE PRESIDENT"):
                continue
            raw_jurisdiction = (row.get("JurisName") or "").strip()
            county_name = jurisdiction_aliases.get(raw_jurisdiction.upper(), raw_jurisdiction)
            county_key = re.sub(r"[^A-Z0-9]+", "", re.sub(r"\s+county$", "", county_name, flags=re.IGNORECASE).upper())
            county = county_lookup.get(county_key)
            if not county:
                raise ValueError(f"Could not match Illinois turnout jurisdiction {raw_jurisdiction!r} to county geometry")
            precinct = (row.get("PrecinctName") or "").strip()
            key = (county, raw_jurisdiction, precinct)
            by_precinct[key]["registeredVoters"] = max(
                by_precinct[key]["registeredVoters"],
                int_text(row.get("Registration")),
            )
            by_precinct[key]["ballotsCast"] += int_text(row.get("VoteCount"))
            by_precinct[key]["rawJurisdiction"] = raw_jurisdiction

    output_rows = []
    for (county, raw_jurisdiction, precinct), totals in by_precinct.items():
        registered = totals["registeredVoters"]
        ballots = totals["ballotsCast"]
        if not registered:
            continue
        output_rows.append(
            {
                "county": county,
                "municipality": raw_jurisdiction,
                "ward": precinct,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_total = {key: sum(row[key] for row in output_rows) for key in expected_totals}
        if parsed_total != expected_totals:
            raise ValueError(f"Illinois turnout expected totals do not match: {parsed_total} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, sorted(output_rows, key=lambda item: (item["county"], item["municipality"], item["ward"])))


def turnout_data_kansas_turnout_xlsx(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    columns = turnout.get(
        "columns",
        {
            "county": "County",
            "ballots": "Ballots Cast",
            "registered": "Registered Voters",
        },
    )
    column_index, rows = read_sheet_rows(path, turnout.get("sheet", "2024 Turnout"))
    output_rows = []
    for row in rows:
        county = str(row[column_index[columns["county"]]] if len(row) > column_index[columns["county"]] else "").strip()
        if not county or county.upper() == "TOTAL":
            continue
        ballots = int_text(row[column_index[columns["ballots"]]] if len(row) > column_index[columns["ballots"]] else 0)
        registered = int_text(row[column_index[columns["registered"]]] if len(row) > column_index[columns["registered"]] else 0)
        if ballots <= 0 and registered <= 0:
            continue
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Kansas turnout parsed {len(output_rows)} county rows")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_arkansas_total_results_statewide_json(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("isOfficial"):
        raise ValueError(f"Arkansas turnout payload is not marked official: {path}")

    totals = payload.get("turnout") or {}
    ballots = int_text(totals.get("totalBallotsCast"))
    registered = int_text(totals.get("registeredVoters"))
    if not ballots or not registered:
        raise ValueError(f"Arkansas turnout payload missing statewide ballots/registered totals: {path}")

    output_rows = [
        {
            "county": "Statewide",
            "municipality": "Statewide",
            "ward": "Statewide",
            "ballotsCast": ballots,
            "registeredVoters": registered,
            "turnoutPct": round2((ballots / registered) * 100) if registered else None,
            "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
            "denominatorType": turnout.get("denominatorType", "registeredVoters"),
            "coverageStatus": "statewide-only",
            "sourceUrl": source["url"],
            "sourceLevel": turnout["sourceLevel"],
            "notes": turnout["notes"],
            "warningRequired": turnout["warningRequired"],
        }
    ]
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_delaware_report_html(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    document = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r">(?P<ballots>[\d,]+)\s+of\s+(?P<registered>[\d,]+)\s+Registered Votes<",
        document,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Could not find Delaware statewide turnout line in {path}")
    ballots = int_text(match.group("ballots"))
    registered = int_text(match.group("registered"))
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {"registeredVoters": registered, "ballotsCast": ballots}
        if parsed_totals != expected_totals:
            raise ValueError(f"Delaware turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = [
        {
            "county": "Statewide",
            "municipality": "Statewide",
            "ward": "Statewide",
            "ballotsCast": ballots,
            "registeredVoters": registered,
            "turnoutPct": round2((ballots / registered) * 100) if registered else None,
            "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
            "denominatorType": turnout.get("denominatorType", "registeredVoters"),
            "coverageStatus": "statewide-only",
            "sourceUrl": source["url"],
            "sourceLevel": turnout["sourceLevel"],
            "notes": turnout["notes"],
            "warningRequired": turnout["warningRequired"],
        }
    ]
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_south_carolina_enr_statewide(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    contest_key = str(turnout["contestKey"])
    contest = next(
        (item for item in payload.get("Contests", []) if str(item.get("K")) == contest_key),
        None,
    )
    if not contest:
        raise ValueError(f"Could not find South Carolina turnout contest {contest_key} in {path}")

    ballots = int_text(contest.get("BC"))
    registered = int_text(contest.get("TV"))
    presidential_votes = int_text(contest.get("T"))
    if not ballots or not registered:
        raise ValueError(f"South Carolina turnout contest missing ballots/registered totals in {path}")

    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": registered,
            "ballotsCast": ballots,
            "presidentialVotes": presidential_votes,
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"South Carolina turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = [
        {
            "county": "Statewide",
            "municipality": "Statewide",
            "ward": "Statewide",
            "ballotsCast": ballots,
            "registeredVoters": registered,
            "turnoutPct": round2((ballots / registered) * 100) if registered else None,
            "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
            "denominatorType": turnout.get("denominatorType", "registeredVoters"),
            "coverageStatus": "statewide-only",
            "sourceUrl": source["url"],
            "sourceLevel": turnout["sourceLevel"],
            "sourceTitle": turnout.get("sourceTitle"),
            "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
            "notes": turnout["notes"],
            "warningRequired": turnout["warningRequired"],
            "presidentialVotes": presidential_votes,
        }
    ]
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_statewide_turnout_csv(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"Statewide turnout CSV must have exactly one data row: {path}")
    row = rows[0]
    ballots = int_text(row.get("ballotsCast"))
    registered = int_text(row.get("registeredVoters"))
    eligible = int_text(row.get("eligibleVoters"))
    denominator_type = turnout.get("denominatorType", "registeredVoters")
    denominator = eligible if denominator_type == "eligibleVoters" else registered
    if not ballots or not denominator:
        raise ValueError(f"Statewide turnout CSV missing ballotsCast or {denominator_type}: {path}")
    output_row = {
        "county": "Statewide",
        "municipality": "Statewide",
        "ward": "Statewide",
        "ballotsCast": ballots,
        "registeredVoters": registered or denominator,
        "eligibleVoters": eligible,
        "turnoutPct": round2((ballots / denominator) * 100) if denominator else None,
        "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
        "denominatorType": denominator_type,
        "sourceUrl": source["url"],
        "sourceLevel": turnout["sourceLevel"],
        "sourceTitle": turnout.get("sourceTitle"),
        "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
        "coverageStatus": turnout.get("coverageStatus", "statewide-only"),
        "voteMethodFields": turnout.get("voteMethodFields", []),
        "notes": turnout["notes"],
        "warningRequired": turnout["warningRequired"],
        "votingAgePopulation": int_text(row.get("votingAgePopulation")),
        "registeredVoterPct": float(row.get("registeredVoterPct") or 0),
        "publishedTurnoutPct": float(row.get("turnoutPct") or 0),
        "vapTurnoutPct": float(row.get("vapTurnoutPct") or 0),
    }
    for field in turnout.get("voteMethodFields", []):
        output_row[field] = int_text(row.get(field))
    output_rows = [output_row]
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_total = {key: output_rows[0][key] for key in expected_totals}
        if parsed_total != expected_totals:
            raise ValueError(f"Statewide turnout expected totals do not match: {parsed_total} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_county_turnout_csv(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    def text_value(value):
        return " ".join(str(value or "").split())

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output_rows = []
    for row in rows:
        county = text_value(row.get("county"))
        ballots = int_text(row.get("ballotsCast"))
        registered = int_text(row.get("registeredVoters"))
        eligible = int_text(row.get("eligibleVoters"))
        denominator_type = turnout.get("denominatorType", "registeredVoters")
        denominator = eligible if denominator_type == "eligibleVoters" else registered
        if not county or not ballots or not denominator:
            raise ValueError(f"County turnout CSV row missing county, ballotsCast, or {denominator_type}: {path}")
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered or denominator,
                "eligibleVoters": eligible,
                "turnoutPct": round2((ballots / denominator) * 100) if denominator else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": denominator_type,
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "sourceFile": text_value(row.get("sourceFile")),
                "extractionMethod": text_value(row.get("extractionMethod")),
            }
        )
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_total = {key: sum(row[key] for row in output_rows) for key in expected_totals}
        if parsed_total != expected_totals:
            raise ValueError(f"County turnout CSV expected totals do not match: {parsed_total} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_new_york_county_enrollment_join(config):
    turnout = config["turnout"]
    registration_path = local_source(config, turnout["sourceId"])
    result_path = local_source(config, turnout["resultSourceId"])
    registration_source = source_map(config)[turnout["sourceId"]]
    sheet_name = turnout.get("sheet") or first_worksheet_name(registration_path)
    aliases = {
        "St.Lawrence": "St. Lawrence",
        **turnout.get("countyAliases", {}),
    }

    registration_by_county = {}
    for row in iter_worksheet_rows(registration_path, sheet_name):
        if len(row) < 10:
            continue
        county = str(row[1] or "").strip()
        status = str(row[2] or "").strip().lower()
        if not county or status != "total":
            continue
        registration_by_county[aliases.get(county, county)] = int_text(row[9])

    ballots_by_county = {}
    with result_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"New York county result source has too few rows: {result_path}")
    header = rows[0]
    try:
        total_index = header.index(turnout.get("resultTotalColumn", "Total Votes"))
    except ValueError as error:
        raise ValueError(f"New York county result source missing Total Votes column: {result_path}") from error

    for row in rows[2:]:
        if len(row) <= total_index or row[0] != "County":
            continue
        county = str(row[1]).strip()
        ballots_by_county[county] = int_text(row[total_index])

    missing_registration = sorted(set(ballots_by_county) - set(registration_by_county))
    if missing_registration:
        raise ValueError(f"New York turnout join missing registration rows: {', '.join(missing_registration)}")

    output_rows = []
    for county, ballots in sorted(ballots_by_county.items()):
        registered = registration_by_county[county]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": registration_source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_total = {key: sum(row[key] for row in output_rows) for key in expected_totals}
        if parsed_total != expected_totals:
            raise ValueError(f"New York turnout expected totals do not match: {parsed_total} != {expected_totals}")

    return turnout_payload(config, turnout, registration_path, registration_source, output_rows)


def turnout_data_louisiana_president_parish_json(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    parish_rows = payload.get("Parishes", {}).get("Parish", [])
    if not parish_rows:
        raise ValueError(f"Louisiana turnout JSON has no parish rows: {path}")

    parish_names = sorted(geometry_names_by_geoid(config).values())
    expected_count = config.get("expected", {}).get("countyRows")
    if len(parish_rows) != expected_count or len(parish_names) != expected_count:
        raise ValueError(
            f"Louisiana turnout row count mismatch: source={len(parish_rows)}; geometry={len(parish_names)}; expected={expected_count}"
        )

    output_rows = []
    for parish_data, parish in zip(parish_rows, parish_names):
        registered = int_text(parish_data.get("VoterCountQualified"))
        ballots = int_text(parish_data.get("VoterCountVoted"))
        output_rows.append(
            {
                "county": parish,
                "municipality": parish,
                "ward": parish,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "precinctsReporting": int_text(parish_data.get("PrecinctsReporting")),
                "precinctsExpected": int_text(parish_data.get("PrecinctsExpected")),
                "absenteeReporting": int_text(parish_data.get("NumAbsenteeReporting")),
                "absenteeExpected": int_text(parish_data.get("NumAbsenteeExpected")),
            }
        )

    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_total = {key: sum(row[key] for row in output_rows) for key in expected_totals}
        if parsed_total != expected_totals:
            raise ValueError(f"Louisiana turnout expected totals do not match: {parsed_total} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_kentucky_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_lookup = {
        re.sub(r"\s+COUNTY$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<code>\d{3})\s+"
        r"(?P<county>[A-Z]+)\s+"
        r"(?P<registered>[\d,]+)\s+"
        r"(?P<ballots>[\d,]+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%\s+"
        r"(?P<dem_registered>[\d,]+)\s+"
        r"(?P<dem_voting>[\d,]+)\s+"
        r"(?P<dem_pct>\d+(?:\.\d+)?)%\s+"
        r"(?P<rep_registered>[\d,]+)\s+"
        r"(?P<rep_voting>[\d,]+)\s+"
        r"(?P<rep_pct>\d+(?:\.\d+)?)%\s+"
        r"(?P<other_registered>[\d,]+)\s+"
        r"(?P<other_voting>[\d,]+)\s+"
        r"(?P<other_pct>\d+(?:\.\d+)?)%$"
    )
    total_pattern = re.compile(
        r"^Totals\s+"
        r"(?P<registered>[\d,]+)\s+"
        r"(?P<ballots>[\d,]+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%\s+"
        r"(?P<dem_registered>[\d,]+)\s+"
        r"(?P<dem_voting>[\d,]+)\s+"
        r"(?P<dem_pct>\d+(?:\.\d+)?)%\s+"
        r"(?P<rep_registered>[\d,]+)\s+"
        r"(?P<rep_voting>[\d,]+)\s+"
        r"(?P<rep_pct>\d+(?:\.\d+)?)%\s+"
        r"(?P<other_registered>[\d,]+)\s+"
        r"(?P<other_voting>[\d,]+)\s+"
        r"(?P<other_pct>\d+(?:\.\d+)?)%$"
    )

    output_rows = []
    reported_total = None
    for line in lines:
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {
                "registeredVoters": int_text(total_match.group("registered")),
                "ballotsCast": int_text(total_match.group("ballots")),
                "demRegisteredVoters": int_text(total_match.group("dem_registered")),
                "demBallotsCast": int_text(total_match.group("dem_voting")),
                "repRegisteredVoters": int_text(total_match.group("rep_registered")),
                "repBallotsCast": int_text(total_match.group("rep_voting")),
                "otherRegisteredVoters": int_text(total_match.group("other_registered")),
                "otherBallotsCast": int_text(total_match.group("other_voting")),
            }
            continue

        match = row_pattern.match(line)
        if not match:
            continue
        county = county_lookup.get(match.group("county"))
        if not county:
            raise ValueError(f"Could not map Kentucky turnout county {match.group('county')!r}")
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "demRegisteredVoters": int_text(match.group("dem_registered")),
                "demBallotsCast": int_text(match.group("dem_voting")),
                "repRegisteredVoters": int_text(match.group("rep_registered")),
                "repBallotsCast": int_text(match.group("rep_voting")),
                "otherRegisteredVoters": int_text(match.group("other_registered")),
                "otherBallotsCast": int_text(match.group("other_voting")),
            }
        )

    expected_counties = set(geometry_names_by_geoid(config).values())
    parsed_counties = {row["county"] for row in output_rows}
    if parsed_counties != expected_counties:
        raise ValueError(
            f"Kentucky turnout county mismatch: missing={sorted(expected_counties - parsed_counties)}; "
            f"extra={sorted(parsed_counties - expected_counties)}"
        )
    if reported_total:
        parsed_total = {
            "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
            "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
            "demRegisteredVoters": sum(row["demRegisteredVoters"] for row in output_rows),
            "demBallotsCast": sum(row["demBallotsCast"] for row in output_rows),
            "repRegisteredVoters": sum(row["repRegisteredVoters"] for row in output_rows),
            "repBallotsCast": sum(row["repBallotsCast"] for row in output_rows),
            "otherRegisteredVoters": sum(row["otherRegisteredVoters"] for row in output_rows),
            "otherBallotsCast": sum(row["otherBallotsCast"] for row in output_rows),
        }
        if parsed_total != reported_total:
            raise ValueError(f"Kentucky turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_expected = {key: sum(row[key] for row in output_rows) for key in expected_totals}
        if parsed_expected != expected_totals:
            raise ValueError(f"Kentucky turnout expected totals do not match: {parsed_expected} != {expected_totals}")
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_ohio_precinct_turnout_xlsx(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    rows = list(iter_worksheet_rows(path, turnout.get("sheetName", "President and Vice President")))
    if len(rows) < 5:
        raise ValueError(f"Ohio precinct turnout workbook has too few rows: {path}")

    header = rows[turnout.get("headerRow", 2) - 1]
    total_row = rows[turnout.get("totalRow", 3) - 1]
    data_rows = rows[turnout.get("dataStartRow", 5) - 1 :]
    column_index = {str(name).strip(): index for index, name in enumerate(header) if name is not None}
    required_columns = ["County Name", "Precinct Name", "Precinct Code", "Registered Voters", "Ballots Counted"]
    missing_columns = [name for name in required_columns if name not in column_index]
    if missing_columns:
        raise ValueError(f"Ohio precinct turnout workbook missing columns: {', '.join(missing_columns)}")

    county_names = {
        re.sub(r"\s+COUNTY$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    output_rows = []
    for row in data_rows:
        raw_county = row[column_index["County Name"]] if len(row) > column_index["County Name"] else None
        if not raw_county:
            continue
        county = county_names.get(str(raw_county).strip().upper())
        if not county:
            raise ValueError(f"Could not map Ohio turnout county {raw_county!r}")
        precinct = str(row[column_index["Precinct Name"]] or "").strip()
        precinct_code = str(row[column_index["Precinct Code"]] or "").strip()
        registered = int_text(row[column_index["Registered Voters"]])
        ballots = int_text(row[column_index["Ballots Counted"]])
        ward = f"{precinct_code} - {precinct}" if precinct_code and precinct else precinct_code or precinct
        output_rows.append(
            {
                "county": county,
                "municipality": precinct or county,
                "ward": ward,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )

    expected_rows = config.get("expected", {}).get("turnoutRows")
    if expected_rows and len(output_rows) != expected_rows:
        raise ValueError(f"Ohio turnout parsed {len(output_rows)} rows, expected {expected_rows}")
    if len({row["county"] for row in output_rows}) != config.get("expected", {}).get("countyRows"):
        raise ValueError("Ohio turnout rows do not cover all expected counties")

    expected_totals = turnout.get("statewideTotals") or {
        "registeredVoters": int_text(total_row[column_index["Registered Voters"]]),
        "ballotsCast": int_text(total_row[column_index["Ballots Counted"]]),
    }
    parsed_totals = {key: sum(row[key] for row in output_rows) for key in expected_totals}
    if parsed_totals != expected_totals:
        raise ValueError(f"Ohio turnout totals do not match workbook Total row: {parsed_totals} != {expected_totals}")

    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_missouri_voter_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = set(geometry_names_by_geoid(config).values())
    row_pattern = re.compile(
        r"^(?P<name>[A-Za-z. ]+?)\s+"
        r"(?P<registered>\d+)\s+"
        r"(?P<active>\d+)\s+"
        r"(?P<inactive>\d+)\s+"
        r"(?P<actual>\d+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )
    total_pattern = re.compile(
        r"^(?P<registered>\d+)\s+"
        r"(?P<active>\d+)\s+"
        r"(?P<inactive>\d+)\s+"
        r"(?P<actual>\d+)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )
    by_county = defaultdict(lambda: defaultdict(int))
    reported_total = None

    def county_name(raw_name):
        name = turnout.get("mergeRows", {}).get(raw_name, raw_name)
        if name == "St. Louis":
            return "St. Louis County"
        if name == "St. Louis City":
            return "St. Louis city"
        if name in county_names:
            return name
        return f"{name} County"

    for line in lines:
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {key: int_text(total_match.group(key)) for key in ["registered", "active", "inactive", "actual"]}
            continue
        match = row_pattern.match(line)
        if not match:
            continue
        county = county_name(match.group("name"))
        if county not in county_names:
            raise ValueError(f"Unexpected Missouri turnout county row {county!r} from {match.group('name')!r}")
        by_county[county]["registered"] += int_text(match.group("registered"))
        by_county[county]["active"] += int_text(match.group("active"))
        by_county[county]["inactive"] += int_text(match.group("inactive"))
        by_county[county]["actual"] += int_text(match.group("actual"))

    if len(by_county) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Missouri turnout parsed {len(by_county)} county rows")
    if reported_total:
        parsed_total = {
            "registered": sum(row["registered"] for row in by_county.values()),
            "active": sum(row["active"] for row in by_county.values()),
            "inactive": sum(row["inactive"] for row in by_county.values()),
            "actual": sum(row["actual"] for row in by_county.values()),
        }
        if parsed_total != reported_total:
            raise ValueError(f"Missouri turnout totals do not match PDF totals: {parsed_total} != {reported_total}")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": sum(row["registered"] for row in by_county.values()),
            "activeVoters": sum(row["active"] for row in by_county.values()),
            "inactiveVoters": sum(row["inactive"] for row in by_county.values()),
            "ballotsCast": sum(row["actual"] for row in by_county.values()),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Missouri turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = []
    for county, totals in sorted(by_county.items()):
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": totals["actual"],
                "registeredVoters": totals["registered"],
                "turnoutPct": round2((totals["actual"] / totals["registered"]) * 100) if totals["registered"] else None,
                "activeVoters": totals["active"],
                "inactiveVoters": totals["inactive"],
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_vermont_voter_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_lookup = {
        re.sub(r"\s+county$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    same_line_pattern = re.compile(
        r"^(?P<county>[A-Z ]+?)\s+"
        r"(?P<registered>[\d,]+)\s+"
        r"(?P<ballots>[\d,]+)\s+"
        r"\d+%\s+"
        r"(?P<absentee>[\d,]+)\s+"
        r"[\d.]+%$"
    )
    values_pattern = re.compile(
        r"^(?P<registered>[\d,]+)\s+"
        r"(?P<ballots>[\d,]+)\s+"
        r"\d+%\s+"
        r"(?P<absentee>[\d,]+)\s+"
        r"[\d.]+%$"
    )
    county_pattern = re.compile(r"^[A-Z ]+$")
    by_county = {}
    pending_values = None
    in_summary = False

    def add_county(raw_county, values):
        county = county_lookup.get(raw_county.strip().upper())
        if not county:
            raise ValueError(f"Unexpected Vermont turnout county row {raw_county!r}")
        by_county[county] = values

    for line in lines:
        if line == "County":
            in_summary = True
            continue
        if not in_summary:
            continue
        if line == "State Total":
            break
        match = same_line_pattern.match(line)
        if match:
            add_county(
                match.group("county"),
                {
                    "registered": int_text(match.group("registered")),
                    "ballots": int_text(match.group("ballots")),
                    "absentee": int_text(match.group("absentee")),
                },
            )
            pending_values = None
            continue
        match = values_pattern.match(line)
        if match:
            pending_values = {
                "registered": int_text(match.group("registered")),
                "ballots": int_text(match.group("ballots")),
                "absentee": int_text(match.group("absentee")),
            }
            continue
        if pending_values and county_pattern.match(line):
            add_county(line, pending_values)
            pending_values = None

    if len(by_county) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Vermont turnout parsed {len(by_county)} county rows")
    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": sum(row["registered"] for row in by_county.values()),
            "ballotsCast": sum(row["ballots"] for row in by_county.values()),
            "absenteeVotesCast": sum(row["absentee"] for row in by_county.values()),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Vermont turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = []
    for county, totals in sorted(by_county.items()):
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": totals["ballots"],
                "registeredVoters": totals["registered"],
                "turnoutPct": round2((totals["ballots"] / totals["registered"]) * 100) if totals["registered"] else None,
                "absenteeVotesCast": totals["absentee"],
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_tennessee_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE): name
        for name in geometry_names_by_geoid(config).values()
    }
    county_prefixes = sorted(county_names, key=len, reverse=True)
    by_county = {}
    total_row = None

    number = r"[\d,]+"
    percentage = r"\d+(?:\.\d+)?%"
    for line in lines:
        if line.startswith("Total:"):
            values = re.findall(number, line)
            if len(values) >= 4:
                total_row = {
                    "registeredVoters": int_text(values[0]),
                    "ballotsCast": int_text(values[1]),
                    "absenteeByMailVotes": int_text(values[2]),
                    "earlyVotes": int_text(values[3]),
                }
            continue
        county_label = next((county for county in county_prefixes if line.startswith(f"{county} ")), None)
        if not county_label:
            continue
        county = county_names[county_label]
        rest = line[len(county_label) :].strip()
        match = re.match(
            rf"^(?P<registered>{number})\s+"
            rf"(?P<ballots>{number})\s+"
            rf"(?P<turnout>{percentage})\s+"
            rf"(?P<absentee>{number})\s+"
            rf"(?P<early>{number})\s+"
            rf"(?P<early_pct>{percentage})\s+"
            rf"(?P<absentee_pct>{percentage})$",
            rest,
        )
        if not match:
            raise ValueError(f"Could not parse Tennessee turnout row: {line}")
        by_county[county] = {
            "registeredVoters": int_text(match.group("registered")),
            "ballotsCast": int_text(match.group("ballots")),
            "absenteeByMailVotes": int_text(match.group("absentee")),
            "earlyVotes": int_text(match.group("early")),
        }

    expected_counties = set(geometry_names_by_geoid(config).values())
    if set(by_county) != expected_counties:
        missing = sorted(expected_counties - set(by_county))
        extra = sorted(set(by_county) - expected_counties)
        raise ValueError(f"Tennessee turnout county mismatch: missing={missing}; extra={extra}")

    parsed_totals = {
        "registeredVoters": sum(row["registeredVoters"] for row in by_county.values()),
        "ballotsCast": sum(row["ballotsCast"] for row in by_county.values()),
        "absenteeByMailVotes": sum(row["absenteeByMailVotes"] for row in by_county.values()),
        "earlyVotes": sum(row["earlyVotes"] for row in by_county.values()),
    }
    expected_totals = turnout.get("statewideTotals") or total_row
    if expected_totals and parsed_totals != expected_totals:
        raise ValueError(f"Tennessee turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = []
    for county, totals in sorted(by_county.items()):
        registered = totals["registeredVoters"]
        ballots = totals["ballotsCast"]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "absenteeByMailVotes": totals["absenteeByMailVotes"],
                "earlyVotes": totals["earlyVotes"],
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_oregon_registration_turnout_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_lookup = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    row_pattern = re.compile(
        r"^(?P<county>[A-Za-z ]+?)\s+"
        r"(?P<registered>\d[\d,]*)\s+"
        r"(?P<ballots>\d[\d,]*)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )
    total_pattern = re.compile(
        r"^(?P<registered>\d[\d,]*)\s+"
        r"(?P<ballots>\d[\d,]*)\s+"
        r"(?P<pct>\d+(?:\.\d+)?)%$"
    )

    try:
        table_start = next(
            index
            for index in range(len(lines) - 5)
            if lines[index] == "VOTER REGISTRATION AND PARTICIPATION BY COUNTY"
            and lines[index + 2] == "Total"
            and lines[index + 3] == "Number Ballots Percent"
            and lines[index + 4] == "County Eligible Returned Voting"
        )
    except StopIteration as exc:
        raise ValueError(f"Could not locate Oregon county turnout table in {path}") from exc

    output_rows = []
    reported_total = None
    for line in lines[table_start + 5 :]:
        total_match = total_pattern.match(line)
        if total_match:
            reported_total = {
                "registeredVoters": int_text(total_match.group("registered")),
                "ballotsCast": int_text(total_match.group("ballots")),
            }
            break
        match = row_pattern.match(line)
        if not match:
            continue
        county = county_lookup.get(match.group("county").upper())
        if not county:
            raise ValueError(f"Unexpected Oregon turnout county row {match.group('county')!r}")
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Oregon turnout parsed {len(output_rows)} county rows")
    if not reported_total:
        raise ValueError(f"Could not locate Oregon turnout total row in {path}")
    parsed_total = {
        "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
        "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
    }
    if parsed_total != reported_total:
        raise ValueError(f"Oregon turnout totals do not match PDF totals: {parsed_total} != {reported_total}")

    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_north_carolina_voter_history_join(config):
    turnout = config["turnout"]
    history_source = source_map(config)[turnout["sourceId"]]
    voter_source = source_map(config)[turnout["registrationSourceId"]]

    def read_zip_rows(source_id, member):
        path = local_source(config, source_id)
        with zipfile.ZipFile(path) as archive:
            with archive.open(member) as raw:
                text = (line.decode("utf-8-sig").replace("\0", "") for line in raw)
                yield from csv.DictReader(text, delimiter="\t")

    def row_key(row):
        return (
            str(row["county_desc"]).strip().upper(),
            str(row["precinct_abbrv"]).strip(),
            str(row["vtd_abbrv"]).strip(),
        )

    county_lookup = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE).upper(): name
        for name in geometry_names_by_geoid(config).values()
    }
    registered_by_key = defaultdict(int)
    for row in read_zip_rows(turnout["registrationSourceId"], turnout.get("registrationMember", "voter_stats_20241105.txt")):
        registered_by_key[row_key(row)] += int(row["total_voters"] or 0)

    ballots_by_key = defaultdict(int)
    methods_by_key = defaultdict(lambda: defaultdict(int))
    for row in read_zip_rows(turnout["sourceId"], turnout.get("historyMember", "history_stats_20241105.txt")):
        key = row_key(row)
        ballots = int(row["total_voters"] or 0)
        method = str(row.get("voting_method_desc") or "").strip().upper()
        ballots_by_key[key] += ballots
        methods_by_key[key][method] += ballots

    missing_denominators = sorted(set(ballots_by_key) - set(registered_by_key))
    if missing_denominators:
        raise ValueError(f"North Carolina turnout missing denominator rows for {len(missing_denominators)} keys")

    method_field_map = {
        "EARLYVOTE": "earlyVote",
        "EV-CURB": "earlyVotingCurbside",
        "ABS-MAIL": "absenteeByMail",
        "IN-PERSON": "electionDayInPerson",
        "CURBSIDE": "electionDayCurbside",
        "TRANSFER": "electionDayTransfer",
        "PROV": "provisional",
    }
    output_rows = []
    for county_raw, precinct, vtd in sorted(registered_by_key):
        county = county_lookup.get(county_raw)
        if not county:
            raise ValueError(f"Unexpected North Carolina county row {county_raw!r}")
        registered = registered_by_key[(county_raw, precinct, vtd)]
        ballots = ballots_by_key[(county_raw, precinct, vtd)]
        row = {
            "county": county,
            "municipality": county,
            "ward": f"Precinct {precinct} / VTD {vtd}",
            "precinct": precinct,
            "vtd": vtd,
            "ballotsCast": ballots,
            "registeredVoters": registered,
            "turnoutPct": round2((ballots / registered) * 100) if registered else None,
            "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
            "denominatorType": turnout.get("denominatorType", "registeredVoters"),
            "sourceUrl": f"{history_source['url']} ; {voter_source['url']}",
            "sourceLevel": turnout["sourceLevel"],
            "sourceTitle": turnout.get("sourceTitle"),
            "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
            "coverageStatus": turnout.get("coverageStatus", "loaded"),
            "voteMethodFields": turnout.get("voteMethodFields", []),
            "notes": turnout["notes"],
            "warningRequired": turnout["warningRequired"],
        }
        methods = methods_by_key[(county_raw, precinct, vtd)]
        for method_label, field in method_field_map.items():
            row[field] = methods[method_label]
        row["earlyVoting"] = row["earlyVote"] + row["earlyVotingCurbside"]
        row["electionDay"] = row["electionDayInPerson"] + row["electionDayCurbside"] + row["electionDayTransfer"]
        output_rows.append(row)

    expected_totals = turnout.get("statewideTotals", {})
    parsed_totals = {
        "registeredVoters": sum(row["registeredVoters"] for row in output_rows),
        "ballotsCast": sum(row["ballotsCast"] for row in output_rows),
        "earlyVoting": sum(row["earlyVoting"] for row in output_rows),
        "absenteeByMail": sum(row["absenteeByMail"] for row in output_rows),
        "electionDay": sum(row["electionDay"] for row in output_rows),
        "provisional": sum(row["provisional"] for row in output_rows),
    }
    if expected_totals and parsed_totals != expected_totals:
        raise ValueError(f"North Carolina turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")
    if len(output_rows) != config.get("expected", {}).get("turnoutRows"):
        raise ValueError(f"North Carolina turnout parsed {len(output_rows)} rows")

    return turnout_payload(config, turnout, local_source(config, turnout["sourceId"]), history_source, output_rows)


def turnout_data_oklahoma_enr_registration_pdf(config):
    turnout = config["turnout"]
    result_path = local_source(config, turnout["sourceId"])
    registration_path = local_source(config, turnout["registrationSourceId"])
    result_source = source_map(config)[turnout["sourceId"]]
    registration_source = source_map(config)[turnout["registrationSourceId"]]
    race_id = int(turnout["raceId"])

    registration_by_county = oklahoma_registration_by_county(config, registration_path)
    turnout_by_county = {}
    with zipfile.ZipFile(result_path) as archive:
        config_data = json.loads(archive.read("config.json").decode("utf-8-sig"))
        county_options = config_data["counties"]["Options"]
        county_values = config_data["counties"]["Values"]
        def county_key(value):
            return re.sub(r"[^A-Z0-9]+", "", value.upper())

        county_names = {
            county_key(re.sub(r"\s+County$", "", name, flags=re.IGNORECASE)): name
            for name in geometry_names_by_geoid(config).values()
        }
        county_code_names = {
            str(code): county_names.get(county_key(str(name))) or f"{name} County"
            for name, code in zip(county_options, county_values)
            if code
        }
        for county_code, county in county_code_names.items():
            county_payload = json.loads(archive.read(f"results-cw-{county_code}.json").decode("utf-8-sig"))
            race_results = next(
                (item for item in county_payload.get("results", []) if int(item.get("raceID")) == race_id),
                None,
            )
            if not race_results:
                raise ValueError(f"Could not find Oklahoma turnout race {race_id!r} in county {county_code}")
            totals = race_results.get("totResults") or {}
            turnout_by_county[county] = {
                "ballots": int_text(totals.get("totalVotes")),
                "absenteeVotes": int_text(totals.get("absVotes")),
                "earlyVotes": int_text(totals.get("earlyVotes")),
                "electionDayVotes": int_text(totals.get("elecDayVotes")),
            }

    if set(registration_by_county) != set(turnout_by_county):
        missing_registration = sorted(set(turnout_by_county) - set(registration_by_county))
        missing_turnout = sorted(set(registration_by_county) - set(turnout_by_county))
        raise ValueError(
            "Oklahoma turnout county mismatch: "
            f"missing registration={missing_registration}; missing turnout={missing_turnout}"
        )

    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": sum(row["total"] for row in registration_by_county.values()),
            "ballotsCast": sum(row["ballots"] for row in turnout_by_county.values()),
            "absenteeVotes": sum(row["absenteeVotes"] for row in turnout_by_county.values()),
            "earlyVotes": sum(row["earlyVotes"] for row in turnout_by_county.values()),
            "electionDayVotes": sum(row["electionDayVotes"] for row in turnout_by_county.values()),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Oklahoma turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = []
    for county, totals in sorted(turnout_by_county.items()):
        registered = registration_by_county[county]["total"]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": totals["ballots"],
                "registeredVoters": registered,
                "turnoutPct": round2((totals["ballots"] / registered) * 100) if registered else None,
                "absenteeVotes": totals["absenteeVotes"],
                "earlyVotes": totals["earlyVotes"],
                "electionDayVotes": totals["electionDayVotes"],
                "libertarianRegisteredVoters": registration_by_county[county]["libertarian"],
                "republicanRegisteredVoters": registration_by_county[county]["republican"],
                "democraticRegisteredVoters": registration_by_county[county]["democratic"],
                "independentRegisteredVoters": registration_by_county[county]["independent"],
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": f"{result_source['url']} ; {registration_source['url']}",
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return turnout_payload(config, turnout, result_path, result_source, output_rows)


def turnout_data_maine_registration_text_join(config):
    turnout = config["turnout"]
    result_path = local_source(config, turnout["sourceId"])
    registration_path = local_source(config, turnout["registrationSourceId"])
    result_source = source_map(config)[turnout["sourceId"]]
    registration_source = source_map(config)[turnout["registrationSourceId"]]
    county_codes = config["certifiedResults"]["countyCodes"]

    registration_by_county = defaultdict(int)
    with registration_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            county_code = str(row.get("COUNTY") or "").strip()
            county = county_codes.get(county_code)
            if not county:
                continue
            registration_by_county[county] += int_text(row.get("TOTAL"))

    columns = turnout["columns"]
    column_index, rows = read_sheet_rows(result_path, turnout.get("sheet", "President & VP"))
    ballots_by_county = {}
    for row in rows:
        municipality = str(row[column_index[columns["municipality"]]] or "").strip()
        if not municipality.endswith(" Total") or municipality == "Statewide Total":
            continue
        county_code = municipality.removesuffix(" Total").strip()
        county = county_codes.get(county_code)
        if county:
            ballots_by_county[county] = int_cell(row, column_index, columns["ballotsCast"])

    if set(registration_by_county) != set(ballots_by_county):
        missing_registration = sorted(set(ballots_by_county) - set(registration_by_county))
        missing_ballots = sorted(set(registration_by_county) - set(ballots_by_county))
        raise ValueError(
            "Maine turnout county mismatch: "
            f"missing registration={missing_registration}; missing ballots={missing_ballots}"
        )

    expected_totals = turnout.get("statewideTotals")
    if expected_totals:
        parsed_totals = {
            "registeredVoters": sum(registration_by_county.values()),
            "ballotsCast": sum(ballots_by_county.values()),
        }
        if parsed_totals != expected_totals:
            raise ValueError(f"Maine turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = []
    for county in sorted(ballots_by_county):
        ballots = ballots_by_county[county]
        registered = registration_by_county[county]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "registeredVoters"),
                "sourceUrl": f"{result_source['url']} ; {registration_source['url']}",
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
            }
        )
    return turnout_payload(config, turnout, result_path, result_source, output_rows)


def oklahoma_registration_by_county(config, path):
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    def county_key(value):
        return re.sub(r"[^A-Z0-9]+", "", value.upper())

    county_names = {
        county_key(re.sub(r"\s+County$", "", name, flags=re.IGNORECASE)): name
        for name in geometry_names_by_geoid(config).values()
    }
    full_pattern = re.compile(
        r"^\d{2}\s+(?P<county>[A-Z ]+?)\s+"
        r"(?P<libertarian>[\d,]+)\s+"
        r"(?P<republican>[\d,]+)\s+"
        r"(?P<democratic>[\d,]+)\s+"
        r"(?P<independent>[\d,]+)\s+"
        r"(?P<total>[\d,]+)$"
    )
    name_pattern = re.compile(r"^\d{2}\s+(?P<county>[A-Z ]+)$")
    values_pattern = re.compile(
        r"^(?P<libertarian>[\d,]+)\s+"
        r"(?P<republican>[\d,]+)\s+"
        r"(?P<democratic>[\d,]+)\s+"
        r"(?P<independent>[\d,]+)\s+"
        r"(?P<total>[\d,]+)$"
    )
    rows = {}
    pending_county = None
    pending_values = None

    def row_values(match):
        return {
            "libertarian": int_text(match.group("libertarian")),
            "republican": int_text(match.group("republican")),
            "democratic": int_text(match.group("democratic")),
            "independent": int_text(match.group("independent")),
            "total": int_text(match.group("total")),
        }

    def add_row(raw_county, values):
        county = county_names.get(county_key(raw_county.strip()))
        if not county:
            raise ValueError(f"Unexpected Oklahoma registration county row {raw_county!r}")
        if values["libertarian"] + values["republican"] + values["democratic"] + values["independent"] != values["total"]:
            raise ValueError(f"Oklahoma registration party total mismatch for {county}")
        rows[county] = values

    for line in lines:
        if line.startswith("vr2420") or line.startswith("MESA ") or line.startswith("County "):
            continue
        if line == "Grand Total":
            break
        match = full_pattern.match(line)
        if match:
            add_row(match.group("county"), row_values(match))
            pending_county = None
            pending_values = None
            continue
        match = name_pattern.match(line)
        if match:
            pending_county = match.group("county")
            if pending_values:
                add_row(pending_county, pending_values)
                pending_county = None
                pending_values = None
            continue
        match = values_pattern.match(line)
        if match:
            values = row_values(match)
            if pending_county:
                add_row(pending_county, values)
                pending_county = None
            else:
                pending_values = values

    if len(rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Oklahoma registration parsed {len(rows)} county rows")
    return rows


def turnout_data_hawaii_county_summary_pdfs(config):
    turnout = config["turnout"]
    sources = source_map(config)
    output_rows = []
    for county_source in config["certifiedResults"]["countySources"]:
        county = county_source["county"]
        source = sources[county_source["sourceId"]]
        path = local_source(config, county_source["sourceId"])
        text = extract_pdf_text(path)
        match = re.search(
            r"TOTAL REGISTRATION\s+(?P<registered>\d[\d,]*).*?"
            r"TOTAL TURNOUT\s+(?P<ballots>\d[\d,]*)\s+\d+(?:\.\d+)?%.*?"
            r"MAIL TURNOUT\s+(?P<mail>\d[\d,]*)\s+\d+(?:\.\d+)?%.*?"
            r"IN-PERSON TURNOUT\s+(?P<inPerson>\d[\d,]*)",
            text,
            flags=re.DOTALL,
        )
        if not match:
            raise ValueError(f"Could not find Hawaii turnout table in {path}")
        registered = int_text(match.group("registered"))
        ballots = int_text(match.group("ballots"))
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "mailTurnout": int_text(match.group("mail")),
                "inPersonTurnout": int_text(match.group("inPerson")),
            }
        )

    if len(output_rows) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Hawaii turnout parsed {len(output_rows)} county rows")
    return turnout_payload(config, turnout, Path("data/hi-2024-general-county-summary-pdfs"), sources[turnout["sourceId"]], output_rows)


def turnout_data_rhode_island_summary_xlsx(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    town_county = config["certifiedResults"]["townCountyMap"]
    registered = {}
    column_index, rows = read_sheet_rows(path, turnout.get("registrationSheet", "Reg_Voters"))
    for row in rows:
        label = str(row[column_index["City/Town - Precinct"]] or "").strip()
        precinct = str(row[column_index["Precinct"]] or "").strip()
        total = int_text(row[column_index["Total"]])
        if not label or total <= 0:
            continue
        registered[(label, precinct)] = total

    output_rows = []
    column_index, rows = read_sheet_rows(path, turnout.get("ballotsSheet", "Ballots_Cast"))
    for row in rows:
        if str(row[column_index["Contest"]] or "").strip() != "BALLOTS CAST - TOTAL":
            continue
        label = str(row[column_index["City/Town - Precinct"]] or "").strip()
        precinct = str(row[column_index["Precinct"]] or "").strip()
        key = (label, precinct)
        registered_voters = registered.get(key, 0)
        if not label or registered_voters <= 0:
            continue
        town = rhode_island_town_from_label(label, town_county)
        county = town_county[town]
        ballots = int_text(row[column_index["Total"]])
        output_rows.append(
            {
                "county": county,
                "municipality": town,
                "ward": label,
                "ballotsCast": ballots,
                "registeredVoters": registered_voters,
                "turnoutPct": round2((ballots / registered_voters) * 100) if registered_voters else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": "registeredVoters",
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "electionDayVotes": int_text(row[column_index["Election Day"]]),
                "mailVotes": int_text(row[column_index["Mail"]]),
                "earlyVotingVotes": int_text(row[column_index["Early Voting"]]),
            }
        )
    return turnout_payload(config, turnout, path, source, output_rows)


def turnout_data_washington_reconciliation_xlsx(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    column_index, rows = read_sheet_rows(path, turnout.get("sheet", "Data"))
    county_names = {
        re.sub(r"\s+County$", "", name, flags=re.IGNORECASE): name
        for name in geometry_names_by_geoid(config).values()
    }
    by_county = {}
    total_row = None

    def value(row, column):
        return int_text(row[column_index[column]])

    for row in rows:
        if row[column_index["Year"]] != turnout.get("year", config["electionYear"]):
            continue
        if str(row[column_index["Election Type"]] or "").strip() != turnout.get("electionType", "General"):
            continue
        county = str(row[column_index["County"]] or "").strip()
        if county == "z-Totals":
            total_row = row
            continue
        if county not in county_names:
            continue
        by_county[county_names[county]] = {
            "activeVoters": value(row, "Active Voters"),
            "inactiveVoters": value(row, "Inactive Voter"),
            "creditedVotersInEms": value(row, "Credited voters in EMS"),
            "validBallots": value(row, "Valid Ballots"),
            "ballotsIssued": value(row, "Ballots Issued"),
            "ballotsReturned": value(row, "Ballots Returned"),
            "ballotsCounted": value(row, "Ballots Counted"),
            "ballotsRejected": value(row, "Ballots Rejected"),
            "uocavaBallotsCounted": value(row, "UOCAVA Ballots Counted"),
            "provisionalBallotsCounted": value(row, "Provisional Ballots Counted"),
            "receivedByDropBox": value(row, " Received by dropbox"),
            "receivedByMail": value(row, "Received by mail"),
            "regularMailBallotsCounted": value(row, "Regular Mail Ballots Counted"),
            "pollsiteCounted": value(row, "Pollsite Counted"),
        }

    expected_counties = set(county_names.values())
    if set(by_county) != expected_counties:
        missing = sorted(expected_counties - set(by_county))
        extra = sorted(set(by_county) - expected_counties)
        raise ValueError(f"Washington turnout county mismatch: missing={missing}; extra={extra}")
    if total_row is None:
        raise ValueError("Washington turnout source is missing z-Totals row")

    expected_totals = turnout.get("statewideTotals") or {
        "activeVoters": value(total_row, "Active Voters"),
        "inactiveVoters": value(total_row, "Inactive Voter"),
        "ballotsCounted": value(total_row, "Ballots Counted"),
        "validBallots": value(total_row, "Valid Ballots"),
        "ballotsReturned": value(total_row, "Ballots Returned"),
        "ballotsRejected": value(total_row, "Ballots Rejected"),
        "receivedByDropBox": value(total_row, " Received by dropbox"),
        "receivedByMail": value(total_row, "Received by mail"),
    }
    parsed_totals = {key: sum(row[key] for row in by_county.values()) for key in expected_totals}
    if parsed_totals != expected_totals:
        raise ValueError(f"Washington turnout totals do not match expected totals: {parsed_totals} != {expected_totals}")

    output_rows = []
    for county, totals in sorted(by_county.items()):
        registered = totals["activeVoters"]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": county,
                "ballotsCast": totals["ballotsCounted"],
                "registeredVoters": registered,
                "turnoutPct": round2((totals["ballotsCounted"] / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "denominatorType": turnout.get("denominatorType", "activeRegisteredVoters"),
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "sourceTitle": turnout.get("sourceTitle"),
                "sourceAuthority": turnout.get("sourceAuthority", config.get("authority")),
                "coverageStatus": turnout.get("coverageStatus", "loaded"),
                "voteMethodFields": turnout.get("voteMethodFields", []),
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "inactiveRegisteredVoters": totals["inactiveVoters"],
                "creditedVotersInEms": totals["creditedVotersInEms"],
                "validBallots": totals["validBallots"],
                "ballotsIssued": totals["ballotsIssued"],
                "ballotsReturned": totals["ballotsReturned"],
                "ballotsRejected": totals["ballotsRejected"],
                "uocavaBallotsCounted": totals["uocavaBallotsCounted"],
                "provisionalBallotsCounted": totals["provisionalBallotsCounted"],
                "receivedByDropBox": totals["receivedByDropBox"],
                "receivedByMail": totals["receivedByMail"],
                "regularMailBallotsCounted": totals["regularMailBallotsCounted"],
                "pollsiteCounted": totals["pollsiteCounted"],
            }
        )
    return turnout_payload(config, turnout, path, source, output_rows)


def rhode_island_town_from_label(label, town_county):
    for town in sorted(town_county, key=len, reverse=True):
        if label == town or label.startswith(f"{town} "):
            return town
    raise ValueError(f"Could not map Rhode Island turnout row to town: {label}")


def turnout_payload(config, turnout, path, source, output_rows):
    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": path.name,
            "sourceUrl": source["url"],
        },
        "rows": output_rows,
    }


def turnout_data_nebraska_canvass_pdf(config):
    turnout = config["turnout"]
    path = local_source(config, turnout["sourceId"])
    source = source_map(config)[turnout["sourceId"]]
    lines = [line.strip() for line in extract_pdf_text(path).splitlines() if line.strip()]
    county_names = {
        re.sub(r"\s+COUNTY$", "", name, flags=re.IGNORECASE)
        for name in geometry_names_by_geoid(config).values()
    }

    registered_by_county, registered_total = nebraska_voting_statistics_table(
        lines,
        "Number of Registered Voters",
        "Total Voting by Method",
        county_names,
        expected_numbers=8,
    )
    ballots_by_county, ballots_total = nebraska_voting_statistics_table(
        lines,
        "Total Voting by Method",
        "President and Vice President of the United States",
        county_names,
        expected_numbers=7,
    )

    if set(registered_by_county) != set(ballots_by_county):
        missing_registered = sorted(set(ballots_by_county) - set(registered_by_county))
        missing_ballots = sorted(set(registered_by_county) - set(ballots_by_county))
        raise ValueError(
            "Nebraska turnout county mismatch: "
            f"missing registration={missing_registered}; missing ballots={missing_ballots}"
        )
    if len(registered_by_county) != config.get("expected", {}).get("countyRows"):
        raise ValueError(f"Nebraska turnout parsed {len(registered_by_county)} county rows")

    output_rows = []
    for county in sorted(registered_by_county):
        registered = registered_by_county[county]["total"]
        ballots = ballots_by_county[county]["total"]
        methods = ballots_by_county[county]
        output_rows.append(
            {
                "county": county,
                "municipality": county,
                "ward": f"{county} County",
                "ballotsCast": ballots,
                "registeredVoters": registered,
                "turnoutPct": round2((ballots / registered) * 100) if registered else None,
                "registrationDenominatorTiming": turnout["registrationDenominatorTiming"],
                "sourceUrl": source["url"],
                "sourceLevel": turnout["sourceLevel"],
                "notes": turnout["notes"],
                "warningRequired": turnout["warningRequired"],
                "pollingPlaceVoting": methods["pollingPlaceVoting"],
                "earlyVoting": methods["earlyVoting"],
                "allMailPrecincts": methods["allMailPrecincts"],
                "provisionalBallot": methods["provisionalBallot"],
                "militaryAndOverseas": methods["militaryAndOverseas"],
                "newFormerResidentVoting": methods["newFormerResidentVoting"],
            }
        )

    if sum(row["registeredVoters"] for row in output_rows) != registered_total["total"]:
        raise ValueError("Nebraska turnout registration total does not match statewide total")
    if sum(row["ballotsCast"] for row in output_rows) != ballots_total["total"]:
        raise ValueError("Nebraska turnout ballots total does not match statewide total")

    return {
        "metadata": {
            "rows": len(output_rows),
            "warningRows": sum(1 for row in output_rows if row["warningRequired"]),
            "source": path.name,
            "sourceUrl": source["url"],
        },
        "rows": output_rows,
    }


def nebraska_voting_statistics_table(lines, start_heading, end_heading, county_names, *, expected_numbers):
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line == start_heading and index + 1 < len(lines) and not lines[index + 1].startswith(".")
        ),
        None,
    )
    if start is None:
        raise ValueError(f"Could not find Nebraska voting statistics heading: {start_heading}")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith(end_heading)
        ),
        None,
    )
    if end is None:
        raise ValueError(f"Could not find Nebraska voting statistics end heading: {end_heading}")

    rows = {}
    statewide_total = None
    pending_county = None
    county_names_by_upper = {county.upper(): county for county in county_names}
    number_pattern = re.compile(r"\d[\d,]*")
    header_starts = (
        "County ",
        "General Election",
        "Legal",
        "Marijuana",
        "Polling ",
    )

    for line in lines[start + 1 : end]:
        if line.startswith(header_starts):
            continue
        numbers = number_pattern.findall(line)
        if not numbers:
            if line == "Statewide Total":
                pending_county = "__STATEWIDE__"
                continue
            if line.upper() in county_names_by_upper:
                pending_county = county_names_by_upper[line.upper()]
            continue
        if len(numbers) != expected_numbers:
            continue

        if line.startswith("Statewide Total") or pending_county == "__STATEWIDE__":
            statewide_total = nebraska_voting_statistics_values(numbers, expected_numbers)
            pending_county = None
            continue

        raw_county = pending_county if re.match(r"^\d", line) else re.sub(r"\s+\d[\d,\s]*$", "", line).strip()
        if not raw_county:
            continue
        county = county_names_by_upper.get(raw_county.upper())
        if not county:
            continue
        rows[county] = nebraska_voting_statistics_values(numbers, expected_numbers)
        pending_county = None

    if statewide_total is None:
        raise ValueError(f"Nebraska voting statistics table missing statewide total: {start_heading}")
    return rows, statewide_total


def nebraska_voting_statistics_values(numbers, expected_numbers):
    values = [int_text(value) for value in numbers]
    if expected_numbers == 8:
        return {
            "precincts": values[0],
            "republican": values[1],
            "democratic": values[2],
            "libertarian": values[3],
            "legalMarijuanaNow": values[4],
            "noLabelsNebraska": values[5],
            "nonpartisan": values[6],
            "total": values[7],
        }
    if expected_numbers == 7:
        return {
            "pollingPlaceVoting": values[0],
            "earlyVoting": values[1],
            "allMailPrecincts": values[2],
            "provisionalBallot": values[3],
            "militaryAndOverseas": values[4],
            "newFormerResidentVoting": values[5],
            "total": values[6],
        }
    raise ValueError(f"Unsupported Nebraska voting statistics width: {expected_numbers}")


def extract_pdf_text(path):
    completed = subprocess.run(
        ["node", "scripts/extract-pdf-text.mjs", str(path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    return completed.stdout


def extract_pdf_items(path, first_page=None, last_page=None):
    command = ["node", "scripts/extract-pdf-items.mjs", str(path)]
    if first_page is not None:
        command.append(str(first_page))
    if last_page is not None:
        command.append(str(last_page))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    return json.loads(completed.stdout)["pages"]


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
    "clarityEnrJson": certified_results_south_carolina_enr_json,
    "coloradoCiveraCsv": certified_results_civera_contest_county_csv,
    "civeraContestCountyCsv": certified_results_civera_contest_county_csv,
    "certifiedCountyTotalsCsv": certified_results_county_totals_csv,
    "connecticutStatementText": certified_results_connecticut_statement_text,
    "georgiaTotalVotesXlsx": certified_results_georgia_total_votes_xlsx,
    "delawareCountyHtml": certified_results_delaware_county_html,
    "floridaPrecinctZip": certified_results_florida_precinct_zip,
    "hawaiiCountySummaryPdfs": certified_results_hawaii_county_summary_pdfs,
    "idahoCountyCsv": certified_results_idaho_county_csv,
    "illinoisPrecinctCsv": certified_results_illinois_precinct_csv,
    "indianaEnrJson": certified_results_indiana_enr_json,
    "iowaCanvassPdf": certified_results_iowa_canvass_pdf,
    "kansasPresidentialXlsx": certified_results_kansas_presidential_xlsx,
    "kentuckyCertificationPdf": certified_results_kentucky_certification_pdf,
    "maineCountyTownXlsx": certified_results_maine_county_town_xlsx,
    "massachusettsCountyHtml": certified_results_massachusetts_county_html,
    "marylandCountyHtml": certified_results_maryland_county_html,
    "michiganCountyTab": certified_results_michigan_tab,
    "missouriActualResultsPdf": certified_results_missouri_actual_results_pdf,
    "montanaCanvassPdf": certified_results_montana_canvass_pdf,
    "nebraskaCanvassPdf": certified_results_nebraska_canvass_pdf,
    "nevadaStatewideHtml": certified_results_nevada_statewide_html,
    "nationalCountyBaselineCsv": certified_results_national_county_baseline_csv,
    "newHampshirePresidentPdf": certified_results_new_hampshire_president_pdf,
    "newJerseyPresidentPdf": certified_results_new_jersey_president_pdf,
    "northCarolinaEnrZip": certified_results_north_carolina_enr_zip,
    "newYorkCountyCsv": certified_results_new_york_county_csv,
    "northDakotaStatewideCsv": certified_results_north_dakota_csv,
    "ohioStatewideRaceSummaryXlsx": certified_results_ohio_statewide_race_summary_xlsx,
    "oklahomaEnrZip": certified_results_oklahoma_enr_zip,
    "oregonMapDataJson": certified_results_oregon_map_data_json,
    "pennsylvaniaBulkCsv": certified_results_pennsylvania_bulk_csv,
    "rhodeIslandSummaryXlsx": certified_results_rhode_island_summary_xlsx,
    "southCarolinaEnrJson": certified_results_south_carolina_enr_json,
    "southDakotaCanvassPdf": certified_results_south_dakota_canvass_pdf,
    "tennesseePrecinctXlsx": certified_results_tennessee_precinct_xlsx,
    "texasCountyJson": certified_results_texas_county_json,
    "totalResultsContestJson": certified_results_total_results_contest_json,
    "utahStatewideCanvassPdf": certified_results_utah_statewide_canvass_pdf,
    "vermontMunicipalityCsv": certified_results_vermont_municipality_csv,
    "virginiaLocalityCsv": certified_results_virginia_locality_csv,
    "washingtonCountyHtml": certified_results_washington_county_html,
    "wyomingStatewideSummaryXlsx": certified_results_wyoming_statewide_summary_xlsx,
}

REVIEW_CHART_PARSERS = {
    "notConfigured": review_charts_not_configured,
    "xlsxPrecinctComparison": review_charts_xlsx_precinct_comparison,
    "alaskaEnrPrecinctCsvComparison": review_charts_alaska_enr_precinct_csv,
    "alabamaPrecinctZipComparison": review_charts_alabama_precinct_zip,
    "arizonaPrecinctSummaryPdfs": review_charts_arizona_precinct_summary_pdfs,
    "californiaSovXlsxCountyComparison": review_charts_california_sov_xlsx,
    "californiaSwdbSrprecComparison": review_charts_california_swdb_srprec,
    "civeraCountyCsvComparison": review_charts_civera_county_csv,
    "civeraPrecinctCsvComparison": review_charts_civera_precinct_csv,
    "civeraPrecinctVoteShare": review_charts_civera_precinct_vote_share,
    "clarityEnrCountyJsonComparison": review_charts_clarity_enr_county_json,
    "connecticutStatementTextTownComparison": review_charts_connecticut_statement_text,
    "delawareCountyHtmlComparison": review_charts_delaware_county_html,
    "delawareElectionDistrictHtmlComparison": review_charts_delaware_election_district_html,
    "electionwarePrecinctSummaryComparison": review_charts_electionware_precinct_summary,
    "floridaPrecinctZipComparison": review_charts_florida_precinct_zip,
    "georgiaHouseJsonCountyComparison": review_charts_georgia_house_json,
    "georgiaPrecinctVoteShare": review_charts_georgia_precinct_vote_share,
    "hawaiiCountySummaryPdfCountyComparison": review_charts_hawaii_county_summary_pdfs,
    "hawaiiMediaPrecinctComparison": review_charts_hawaii_media_precinct,
    "idahoPrecinctCsvComparison": review_charts_idaho_precinct_csv,
    "illinoisPrecinctVoteShare": review_charts_illinois_precinct_vote_share,
    "indianaEnrCountyJsonComparison": review_charts_indiana_enr_county_json,
    "iowaHousePdfCountyComparison": review_charts_iowa_house_pdf,
    "kansasHouseXlsxCountyComparison": review_charts_kansas_house_xlsx,
    "kansasPresidentialPrecinctVoteShare": review_charts_kansas_presidential_precinct_vote_share,
    "kentuckyHousePdfCountyComparison": review_charts_kentucky_house_pdf,
    "louisianaFederalPrecinctJsonComparison": review_charts_louisiana_federal_precinct_json,
    "maineCountyTownXlsxComparison": review_charts_maine_county_town_xlsx,
    "marylandPrecinctCsvComparison": review_charts_maryland_precinct_csv,
    "mississippiRecapCsvCountyComparison": review_charts_mississippi_recap_csv,
    "missouriActualResultsPdfCountyComparison": review_charts_missouri_actual_results_pdf,
    "massachusettsCountyHtmlComparison": review_charts_massachusetts_county_html,
    "massachusettsPrecinctCsvComparison": review_charts_massachusetts_precinct_csv,
    "newJerseyMunicipalPdfComparison": review_charts_new_jersey_municipal_pdfs,
    "newJerseySenatePdfCountyComparison": review_charts_new_jersey_senate_pdf,
    "newYorkCountyCsvComparison": review_charts_new_york_county_csv,
    "newYorkCityEdCsvComparison": review_charts_new_york_city_ed_csv,
    "northCarolinaPrecinctZipComparison": review_charts_north_carolina_precinct_zip,
    "ohioPrecinctVoteShare": review_charts_ohio_precinct_vote_share,
    "tennesseePrecinctXlsxComparison": review_charts_tennessee_precinct_xlsx,
    "tabDelimitedZipComparison": review_charts_tab_delimited_zip,
    "totalResultsHouseCountyComparison": review_charts_total_results_house_county,
    "totalResultsPrecinctVoteShare": review_charts_total_results_precinct_vote_share,
    "michiganPrecinctZipComparison": review_charts_tab_delimited_zip,
    "michiganCountyTabComparison": review_charts_michigan_tab,
    "montanaCanvassPdfCountyComparison": review_charts_montana_canvass_pdf,
    "nebraskaCanvassPdfCountyComparison": review_charts_nebraska_canvass_pdf,
    "nevadaClarkCvrComparison": review_charts_nevada_clark_cvr,
    "nevadaStatewideHtmlCountyComparison": review_charts_nevada_statewide_html,
    "northDakotaPrecinctWorkbookComparison": review_charts_north_dakota_precinct_workbooks,
    "northDakotaStatewideCsvCountyComparison": review_charts_north_dakota_csv,
    "oklahomaEnrZipCountyComparison": review_charts_oklahoma_enr_zip,
    "oklahomaPrecinctCsvZipComparison": review_charts_oklahoma_precinct_csv_zip,
    "oregonHouseMapDataCountyComparison": review_charts_oregon_house_map_data,
    "oregonPrecinctVoteShare": review_charts_oregon_precinct_vote_share,
    "pennsylvaniaBulkCsvPrecinctComparison": review_charts_pennsylvania_bulk_csv,
    "rhodeIslandSummaryXlsxComparison": review_charts_rhode_island_summary_xlsx,
    "southCarolinaHouseEnrCountyComparison": review_charts_south_carolina_house_enr,
    "southDakotaCanvassPdfCountyComparison": review_charts_south_dakota_canvass_pdf,
    "texasCountyJsonComparison": review_charts_texas_county_json,
    "texasHarrisCanvassPdfVoteShare": review_charts_texas_harris_canvass_pdf_vote_share,
    "utahCanvassPdfCountyComparison": review_charts_utah_canvass_pdf,
    "utahPrecinctVoteShare": review_charts_utah_precinct_vote_share,
    "vermontMunicipalityCsvComparison": review_charts_vermont_municipality_csv,
    "virginiaPrecinctCsvComparison": review_charts_virginia_precinct_csv,
    "washingtonPrecinctCsvComparison": review_charts_washington_precinct_csv,
    "wyomingPrecinctXlsxComparison": review_charts_wyoming_precinct_xlsx,
}

TURNOUT_PARSERS = {
    "notConfigured": turnout_data_not_configured,
    "alaskaEnrHouseDistrictTurnout": turnout_data_alaska_enr_house_district,
    "alabamaPrecinctZipTurnout": turnout_data_alabama_precinct_zip,
    "arkansasTotalResultsStatewideJson": turnout_data_arkansas_total_results_statewide_json,
    "californiaParticipationPdf": turnout_data_california_participation_pdf,
    "connecticutStatementTurnoutPdf": turnout_data_connecticut_statement_turnout_pdf,
    "coloradoGeneralTurnoutPdf": turnout_data_colorado_general_turnout_pdf,
    "countyTurnoutCsv": turnout_data_county_turnout_csv,
    "delawareReportHtml": turnout_data_delaware_report_html,
    "floridaPrecinctZipTurnout": turnout_data_florida_precinct_zip,
    "hawaiiCountySummaryPdfs": turnout_data_hawaii_county_summary_pdfs,
    "idahoTurnoutHtml": turnout_data_idaho_turnout_html,
    "illinoisPrecinctCsv": turnout_data_illinois_precinct_csv,
    "indianaTurnoutPdf": turnout_data_indiana_turnout_pdf,
    "iowaTurnoutCsv": turnout_data_iowa_turnout_csv,
    "kansasTurnoutXlsx": turnout_data_kansas_turnout_xlsx,
    "kentuckyTurnoutPdf": turnout_data_kentucky_turnout_pdf,
    "louisianaPresidentParishJson": turnout_data_louisiana_president_parish_json,
    "marylandTurnoutPdf": turnout_data_maryland_turnout_pdf,
    "maineRegistrationTextJoin": turnout_data_maine_registration_text_join,
    "xlsxPrecinctRows": turnout_data_xlsx_precinct_rows,
    "michiganMvicCountyTurnout": turnout_data_michigan_mvic,
    "missouriVoterTurnoutPdf": turnout_data_missouri_voter_turnout_pdf,
    "montanaCanvassPdf": turnout_data_montana_canvass_pdf,
    "nebraskaCanvassPdf": turnout_data_nebraska_canvass_pdf,
    "newJerseyTurnoutPdf": turnout_data_new_jersey_turnout_pdf,
    "newYorkCountyEnrollmentJoin": turnout_data_new_york_county_enrollment_join,
    "northCarolinaVoterHistoryJoin": turnout_data_north_carolina_voter_history_join,
    "northDakotaTurnoutHtml": turnout_data_north_dakota_html,
    "ohioPrecinctTurnoutXlsx": turnout_data_ohio_precinct_turnout_xlsx,
    "oklahomaEnrRegistrationPdf": turnout_data_oklahoma_enr_registration_pdf,
    "oregonRegistrationTurnoutPdf": turnout_data_oregon_registration_turnout_pdf,
    "pennsylvaniaVoteHistoryXlsx": turnout_data_pennsylvania_vote_history_xlsx,
    "rhodeIslandSummaryXlsx": turnout_data_rhode_island_summary_xlsx,
    "southDakotaElectionReturnsPdf": turnout_data_south_dakota_election_returns_pdf,
    "southCarolinaEnrStatewideTurnout": turnout_data_south_carolina_enr_statewide,
    "statewideTurnoutCsv": turnout_data_statewide_turnout_csv,
    "tennesseeTurnoutPdf": turnout_data_tennessee_turnout_pdf,
    "vermontVoterTurnoutPdf": turnout_data_vermont_voter_turnout_pdf,
    "washingtonReconciliationXlsx": turnout_data_washington_reconciliation_xlsx,
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
    content = f"window.{geometry['outputGlobal']} = {json.dumps(geojson, separators=(',', ':'))};\n"
    if not output_file.exists() or output_file.read_text(encoding="utf-8") != content:
        output_file.write_text(content, encoding="utf-8")
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
