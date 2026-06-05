import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "data" / "state-configs"
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def project_path(value):
    return ROOT / value


def display_path(path):
    return Path(path).as_posix()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def cell_value(cell, shared_strings):
    raw = cell.find("main:v", NS)
    if raw is None or raw.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(raw.text)]
    return raw.text


def worksheet_rows(archive, sheet_name, limit=25):
    shared_strings = read_shared_strings(archive)
    sheet_path = worksheet_path_for_name(archive, sheet_name)
    root = ElementTree.fromstring(archive.read(sheet_path))
    rows = []
    for row in root.findall("main:sheetData/main:row", NS):
        values = []
        for cell in row.findall("main:c", NS):
            index = column_number(cell.attrib["r"]) - 1
            while len(values) <= index:
                values.append("")
            values[index] = cell_value(cell, shared_strings)
        if any(str(value).strip() for value in values):
            rows.append(values)
        if len(rows) >= limit:
            break
    return rows


def workbook_sheets(path):
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheets = []
        for sheet in workbook.findall("main:sheets/main:sheet", NS):
            name = sheet.attrib["name"]
            rows = worksheet_rows(archive, name)
            sheets.append({
                "name": name,
                "headers": infer_header(rows),
                "columnHints": infer_columns(infer_header(rows)),
            })
        return sheets


def infer_header(rows):
    best = []
    best_score = -1
    for row in rows:
        labels = [str(value or "").strip() for value in row]
        score = sum(1 for value in labels if re.search(r"[A-Za-z]", value))
        if score > best_score:
            best = labels
            best_score = score
    return best


def infer_columns(headers):
    hints = {}
    patterns = {
        "county": r"\bcounty\b|countyname|cnty",
        "municipality": r"municip|city|town|jurisdiction",
        "precinct": r"precinct|ward|reporting",
        "totalVotes": r"\btotal\b|totvotes|totalvotes|votes cast",
        "trump": r"trump|donald",
        "harris": r"harris|kamala",
        "democratic": r"\bdem\b|democratic|dfl",
        "republican": r"\brep\b|republican|gop",
        "senate": r"senate|senator",
        "ballotsCast": r"ballots?\s*cast|totvoting|signatures",
        "registeredVoters": r"registered|reg7am|eligible",
        "electionDayRegistrations": r"\bedr\b|election day registration",
    }
    for index, header in enumerate(headers):
        normalized = re.sub(r"[^a-z0-9]+", " ", str(header or "").lower()).strip()
        for role, pattern in patterns.items():
            if re.search(pattern, normalized):
                hints.setdefault(role, []).append({"index": index, "header": header})
    return hints


def sniff_delimiter(sample):
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        if sample.count("\t") > sample.count(","):
            return "\t"
        if sample.count(";") > sample.count(","):
            return ";"
        return ","


def text_table(path):
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:100000]
    delimiter = sniff_delimiter(sample)
    rows = list(csv.reader(sample.splitlines(), delimiter=delimiter))[:250]
    header = infer_header(rows[:25])
    contests = []
    if header:
      lower_header = [str(item).lower() for item in header]
      for key in ("officedescription", "office", "contest", "race"):
          if key in lower_header:
              contest_index = lower_header.index(key)
              contests = sorted({row[contest_index] for row in rows[1:] if len(row) > contest_index and row[contest_index]})[:30]
              break
    if not contests and rows and len(rows[0]) >= 4:
        contests = sorted({row[0] for row in rows[1:] if row and row[0]})[:30]
    return {
        "delimiter": delimiter,
        "headers": header,
        "columnHints": infer_columns(header),
        "contestHints": contests,
    }


def zip_summary(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    lower_names = " ".join(names).lower()
    return {
        "entries": names[:50],
        "suggestedParser": "tabDelimitedZipComparison" if re.search(r"candidate|contest|office|vote|result", lower_names) else "",
    }


def html_summary(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.search(r"<title\b[^>]*>([\s\S]*?)</title>", text, re.I).group(1))).strip() if re.search(r"<title\b[^>]*>([\s\S]*?)</title>", text, re.I) else "",
        "hasViewState": "__VIEWSTATE" in text,
        "postbackTargets": sorted(set(re.findall(r"__doPostBack\('([^']+)'", text)))[:30],
        "suggestedParser": "htmlTurnoutOrPostbackSource" if re.search(r"turnout|ballots?\s+cast|registered", text, re.I) else "",
    }


def json_summary(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, dict) else []
    properties = features[0].get("properties", {}) if features else {}
    return {
        "type": payload.get("type", "") if isinstance(payload, dict) else "",
        "featureCount": len(features),
        "propertyNames": sorted(properties)[:40],
        "suggestedParser": "geojsonOrArcgisFeatureService" if features else "",
    }


def inspect_source(config, source):
    local_file = source.get("localFile", "")
    path = project_path(local_file)
    result = {
        "id": source.get("id", ""),
        "role": source.get("discovery", {}).get("role", ""),
        "localFile": local_file,
        "exists": path.exists(),
    }
    if not path.exists():
        result["nextStep"] = "Download or place the official source file before schema inference."
        return result
    with path.open("rb") as handle:
        signature = handle.read(4)
    try:
        if signature[:2] == b"PK":
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    if "xl/workbook.xml" in archive.namelist():
                        result["kind"] = "spreadsheet"
                        result["sheets"] = workbook_sheets(path)
                    else:
                        result["kind"] = "zip"
                        result["zip"] = zip_summary(path)
        elif signature == b"%PDF":
            result["kind"] = "pdf"
            result["nextStep"] = "Use the PDF text extractor or a source-specific parser to infer denominator or reference rows."
        elif signature[:1] in (b"{", b"["):
            result["kind"] = "json"
            result["json"] = json_summary(path)
        else:
            sample = path.read_text(encoding="utf-8", errors="replace")[:2000]
            if re.search(r"<!doctype html|<html\b|<form\b", sample, re.I):
                result["kind"] = "html"
                result["html"] = html_summary(path)
            else:
                result["kind"] = "textTable"
                result["table"] = text_table(path)
    except Exception as error:
        result["error"] = str(error)
    return result


def config_paths(args):
    if args.config:
        return [Path(item) for item in args.config]
    return sorted(path for path in CONFIG_DIR.glob("*.json") if not path.name.startswith("_"))


def main():
    parser = argparse.ArgumentParser(description="Inspect configured state source files and infer parser mapping hints.")
    parser.add_argument("config", nargs="*", help="State config path(s). Defaults to data/state-configs/*.json.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()
    reports = []
    for raw_path in config_paths(args):
        config_path = raw_path if raw_path.is_absolute() else project_path(raw_path)
        config = read_json(config_path)
        reports.append({
            "state": config.get("code", config_path.stem.upper()),
            "configPath": display_path(config_path.relative_to(ROOT)),
            "sources": [inspect_source(config, source) for source in config.get("sources", [])],
        })
    output = {"status": "passed", "states": reports}
    body = f"{json.dumps(output, indent=2)}\n"
    if args.output:
        output_path = project_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
    else:
        print(body, end="")


if __name__ == "__main__":
    main()
