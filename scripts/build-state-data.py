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


def parser_for(registry, key, feature_name):
    try:
        return registry[key]
    except KeyError as error:
        supported = ", ".join(sorted(registry))
        raise ValueError(f"Unsupported {feature_name} parser format {key!r}. Supported formats: {supported}") from error


CERTIFIED_RESULT_PARSERS = {
    "xlsxPrecinctAggregation": certified_results_xlsx_precinct_aggregation,
    "michiganCountyTab": certified_results_michigan_tab,
    "northDakotaStatewideCsv": certified_results_north_dakota_csv,
}

REVIEW_CHART_PARSERS = {
    "xlsxPrecinctComparison": review_charts_xlsx_precinct_comparison,
    "tabDelimitedZipComparison": review_charts_tab_delimited_zip,
    "michiganPrecinctZipComparison": review_charts_tab_delimited_zip,
    "michiganCountyTabComparison": review_charts_michigan_tab,
    "northDakotaStatewideCsvCountyComparison": review_charts_north_dakota_csv,
}

TURNOUT_PARSERS = {
    "notConfigured": turnout_data_not_configured,
    "xlsxPrecinctRows": turnout_data_xlsx_precinct_rows,
    "michiganMvicCountyTurnout": turnout_data_michigan_mvic,
    "northDakotaTurnoutHtml": turnout_data_north_dakota_html,
}

HISTORICAL_BASELINE_PARSERS = {
    "officialCountyResultText": historical_baseline_official_county_result_text,
    "michiganCountyTab": historical_baseline_michigan_tab,
    "northDakotaStatewideCsv": historical_baseline_north_dakota_csv,
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
            "notes": f"Aggregated from configured official {config['authority']} source files.",
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


def main():
    parser = argparse.ArgumentParser(description="Build configured state election app data bundles.")
    parser.add_argument("config", nargs="*", help="Path to one or more state config JSON files. Defaults to data/state-configs/*.json.")
    parser.add_argument("--download", action="store_true", help="Download any missing configured source files before building.")
    parser.add_argument("--force-download", action="store_true", help="Download configured source files even when local files exist.")
    args = parser.parse_args()

    summaries = {}
    configs = []
    for config_path in config_paths(args):
        config = read_config(config_path)
        configs.append(config)
        summaries[config["code"]] = build_state(
            config,
            download=args.download,
            force_download=args.force_download,
        )
    write_state_registry(all_real_configs())
    print(json.dumps({"status": "passed", "states": summaries}, indent=2))


if __name__ == "__main__":
    main()
