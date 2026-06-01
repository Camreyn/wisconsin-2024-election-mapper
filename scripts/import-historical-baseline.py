"""Import historical Wisconsin presidential results into normalized artifacts."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import struct
import sys
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORICAL = DATA / "historical"
RAW = HISTORICAL / "raw"
GENERATED = HISTORICAL / "generated"
MANIFEST = HISTORICAL / "source-manifest.json"

ELECTION_DATES = {
    2012: "2012-11-06",
    2016: "2016-11-08",
    2020: "2020-11-03",
    2024: "2024-11-05",
}
EXPECTED_STATEWIDE = {
    2012: {"dem": 1_620_985, "rep": 1_407_966, "other": 39_483, "total": 3_068_434},
    2016: {"dem": 1_382_536, "rep": 1_405_284, "other": 188_330, "total": 2_976_150},
    2020: {"dem": 1_630_866, "rep": 1_610_184, "other": 56_991, "total": 3_298_041},
    2024: {"dem": 1_668_229, "rep": 1_697_626, "other": 57_063, "total": 3_422_918},
}
EXPECTED_2016_LTSB_NATIVE_COUNTY_DELTAS = {
    "Buffalo": {"dem": -3, "rep": -4, "other": 0, "total": -7},
    "Trempealeau": {"dem": 3, "rep": 4, "other": 0, "total": 7},
}
CSV_FIELDS = [
    "electionYear",
    "electionDate",
    "contestId",
    "contestName",
    "office",
    "party",
    "candidate",
    "county",
    "municipality",
    "reportingUnit",
    "ward",
    "votes",
    "sourceClass",
    "sourceLevel",
    "rowMethod",
    "sourceUrl",
    "sourceFile",
    "sourceSha256",
    "notes",
    "sourceId",
    "countyFips",
    "geoid",
    "canvassStage",
]
PARTIES = {
    "dem": "Democratic",
    "rep": "Republican",
    "other": "Other",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_json(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload, *, compact: bool = False) -> None:
    rendered = json.dumps(payload, separators=(",", ":")) if compact else json.dumps(payload, indent=2)
    path.write_text(f"{rendered}\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_text(value, label: str) -> str:
    text = str(value or "").strip()
    require(bool(text), f"Missing required value: {label}")
    return text


def normalize_county(value) -> str:
    return require_text(value, "county").title().replace("Fond Du Lac", "Fond du Lac")


def source_by_id(manifest: dict, source_id: str) -> dict:
    source = next((entry for entry in manifest["entries"] if entry["id"] == source_id), None)
    require(source is not None, f"Source manifest entry missing: {source_id}")
    require(source.get("retrievalStatus") == "collected", f"Source is not collected: {source_id}")
    local_file = HISTORICAL / require_text(source.get("localFile"), f"{source_id}.localFile")
    require(local_file.exists(), f"Source file missing: {local_file}")
    require(sha256(local_file) == source.get("sha256"), f"Source hash mismatch: {source_id}")
    return {**source, "path": local_file}


def parse_dbf_scalar(raw: bytes, field_type: str):
    text = raw.decode("latin1").strip()
    if not text:
        return None
    if field_type in {"N", "F"}:
        if set(text) == {"*"}:
            return None
        return int(float(text))
    return text


def read_dbf_rows(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as archive:
        dbf_name = next(name for name in archive.namelist() if name.lower().endswith(".dbf"))
        content = archive.read(dbf_name)

    record_count = struct.unpack("<I", content[4:8])[0]
    header_length = struct.unpack("<H", content[8:10])[0]
    record_length = struct.unpack("<H", content[10:12])[0]
    fields = []
    offset = 32
    while content[offset] != 13:
        descriptor = content[offset : offset + 32]
        fields.append(
            (
                descriptor[:11].decode("ascii", "ignore").rstrip("\0").strip(),
                chr(descriptor[11]),
                descriptor[16],
            )
        )
        offset += 32

    rows = []
    for index in range(record_count):
        record = content[header_length + index * record_length : header_length + (index + 1) * record_length]
        if record[:1] == b"*":
            continue
        position = 1
        row = {}
        for name, field_type, width in fields:
            row[name] = parse_dbf_scalar(record[position : position + width], field_type)
            position += width
        rows.append(row)
    return rows


def xlsx_col_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group(0)
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def read_xlsx_rows(path: Path, sheet_name: str) -> list[list]:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{{{main_ns}}}si"):
                shared_strings.append("".join(node.text or "" for node in item.iter(f"{{{main_ns}}}t")))

        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = next(
            sheet
            for sheet in workbook.find(f"{{{main_ns}}}sheets")
            if sheet.attrib["name"] == sheet_name
        )
        relationship_id = sheet.attrib[f"{{{rel_ns}}}id"]
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationship = next(
            rel for rel in relationships if rel.attrib["Id"] == relationship_id
        )
        sheet_path = relationship.attrib["Target"].lstrip("/")
        if not sheet_path.startswith("xl/"):
            sheet_path = f"xl/{sheet_path}"

        root = ElementTree.fromstring(archive.read(sheet_path))
        rows = []
        for row_node in root.iter(f"{{{main_ns}}}row"):
            cells = {}
            for cell in row_node.findall(f"{{{main_ns}}}c"):
                value_node = cell.find(f"{{{main_ns}}}v")
                inline_node = cell.find(f"{{{main_ns}}}is")
                value = None
                if cell.attrib.get("t") == "s" and value_node is not None:
                    value = shared_strings[int(value_node.text)]
                elif cell.attrib.get("t") == "inlineStr" and inline_node is not None:
                    value = "".join(node.text or "" for node in inline_node.iter(f"{{{main_ns}}}t"))
                elif value_node is not None and value_node.text is not None:
                    raw_value = value_node.text
                    try:
                        number = float(raw_value)
                        value = int(number) if number.is_integer() else number
                    except ValueError:
                        value = raw_value
                cells[xlsx_col_index(cell.attrib["r"])] = value
            if cells:
                width = max(cells) + 1
                rows.append([cells.get(index) for index in range(width)])
    return rows


def vote_values(total: int, dem: int, rep: int) -> dict[str, int]:
    other = total - dem - rep
    require(other >= 0, f"Candidate subtotal exceeds total: total={total}, dem={dem}, rep={rep}")
    return {"dem": dem, "rep": rep, "other": other, "total": total}


def make_candidate_rows(
    *,
    wide_row: dict,
    candidates: dict[str, str],
    source: dict,
    notes: str,
) -> list[dict]:
    rows = []
    for key in ("dem", "rep", "other"):
        rows.append(
            {
                "electionYear": wide_row["electionYear"],
                "electionDate": ELECTION_DATES[wide_row["electionYear"]],
                "contestId": wide_row["contestId"],
                "contestName": "President of the United States",
                "office": "President",
                "party": PARTIES[key],
                "candidate": candidates[key],
                "county": wide_row["county"],
                "municipality": wide_row["municipality"],
                "reportingUnit": wide_row["reportingUnit"],
                "ward": wide_row["ward"],
                "votes": wide_row[key],
                "sourceClass": wide_row["sourceClass"],
                "sourceLevel": wide_row["sourceLevel"],
                "rowMethod": wide_row["rowMethod"],
                "sourceUrl": source["sourceUrl"],
                "sourceFile": source["localFile"],
                "sourceSha256": source["sha256"],
                "notes": notes,
                "sourceId": source["id"],
                "countyFips": wide_row.get("countyFips", ""),
                "geoid": wide_row.get("geoid", ""),
                "canvassStage": wide_row.get("canvassStage", ""),
            }
        )
    return rows


def aggregate(rows: list[dict], group_fields: tuple[str, ...]) -> list[dict]:
    groups = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0, "rowCount": 0})
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        group = groups[key]
        for value in ("dem", "rep", "other", "total"):
            group[value] += row[value]
        group["rowCount"] += 1
    return [
        {**dict(zip(group_fields, key)), **values}
        for key, values in sorted(groups.items())
    ]


def summarize_series(series_id: str, rows: list[dict], *, include_rows: bool = True) -> dict:
    source_classes = sorted({row["sourceClass"] for row in rows})
    row_methods = sorted({row["rowMethod"] for row in rows})
    require(len(source_classes) == 1, f"{series_id}: mixed source classes")
    require(len(row_methods) == 1, f"{series_id}: mixed row methods")
    payload = {
        "id": series_id,
        "electionYear": rows[0]["electionYear"],
        "contestId": rows[0]["contestId"],
        "sourceId": rows[0]["sourceId"],
        "sourceClass": source_classes[0],
        "sourceLevel": rows[0]["sourceLevel"],
        "rowMethod": row_methods[0],
        "rowCount": len(rows),
        "statewide": aggregate(rows, ())[0],
        "countyTotals": aggregate(rows, ("county",)),
        "municipalityTotals": aggregate(rows, ("county", "municipality")),
    }
    if include_rows:
        payload["rows"] = rows
    return payload


def import_ltsb(source: dict) -> tuple[list[dict], list[dict], list[dict]]:
    raw_rows = read_dbf_rows(source["path"])
    required = ["GEOID", "CNTY_FIPS", "CNTY_NAME", "MCD_NAME", "LABEL", "STR_WARDS"]
    masked = []
    wide_rows = []
    candidate_rows = []
    for row_index, row in enumerate(raw_rows, start=1):
        for field in required:
            require_text(row.get(field), f"LTSB row {row_index} {field}")
        presidential_values = []
        for year in (2012, 2016, 2020):
            suffix = str(year)[2:]
            values = [row.get(f"PRETOT{suffix}"), row.get(f"PREDEM{suffix}"), row.get(f"PREREP{suffix}")]
            if all(value is None for value in values):
                presidential_values.append(None)
                continue
            require(all(isinstance(value, int) for value in values), f"LTSB row {row_index} has partial presidential values for {year}")
            presidential_values.append(vote_values(values[0], values[1], values[2]))

        if all(value is None for value in presidential_values):
            masked.append(
                {
                    "sourceRow": row_index,
                    "geoid": row["GEOID"],
                    "countyFips": row["CNTY_FIPS"],
                    "county": normalize_county(row["CNTY_NAME"]),
                    "municipality": row["MCD_NAME"],
                    "reportingUnit": row["LABEL"],
                    "ward": row["STR_WARDS"],
                    "reason": "LTSB DBF stores masked presidential values as **** for this harmonized geography row.",
                }
            )
            continue
        require(all(value is not None for value in presidential_values), f"LTSB row {row_index} has inconsistent year coverage")

        for year, values in zip((2012, 2016, 2020), presidential_values, strict=True):
            wide_row = {
                "electionYear": year,
                "contestId": f"{year}-president-ltsb-harmonized",
                "sourceId": source["id"],
                "sourceClass": "harmonizedLtsb",
                "sourceLevel": "ward",
                "rowMethod": "ltsbPopulationAllocation",
                "county": normalize_county(row["CNTY_NAME"]),
                "countyFips": row["CNTY_FIPS"],
                "municipality": row["MCD_NAME"],
                "reportingUnit": row["LABEL"],
                "ward": row["STR_WARDS"],
                "geoid": row["GEOID"],
                **values,
            }
            wide_rows.append(wide_row)
            candidate_rows.extend(
                make_candidate_rows(
                    wide_row=wide_row,
                    candidates={
                        "dem": "Democratic presidential ticket",
                        "rep": "Republican presidential ticket",
                        "other": "Other presidential candidates combined",
                    },
                    source=source,
                    notes="Harmonized LTSB comparison row. Some source totals were allocated to wards using population-based methods. Other combines all non-Democratic and non-Republican presidential votes.",
                )
            )
    require(len(raw_rows) == 7_078, f"Unexpected LTSB DBF row count: {len(raw_rows)}")
    require(len(masked) == 70, f"Unexpected LTSB masked row count: {len(masked)}")
    return wide_rows, candidate_rows, masked


def import_ltsb_2024(source: dict) -> tuple[list[dict], list[dict], list[dict]]:
    features = read_gzip_json(source["path"])["features"]
    wide_rows = []
    candidate_rows = []
    missing_rows = []
    for row_index, feature in enumerate(features, start=1):
        row = feature["properties"]
        for field in ("GEOID", "CNTY_FIPS", "CNTY_NAME", "MCD_NAME", "LABEL", "WARDID"):
            require_text(row.get(field), f"LTSB 2024 row {row_index} {field}")
        raw_values = [row.get("PRETOT24"), row.get("PREDEM24"), row.get("PREREP24")]
        if all(value is None for value in raw_values):
            missing_rows.append(
                {
                    "sourceRow": row_index,
                    "geoid": row["GEOID"],
                    "countyFips": row["CNTY_FIPS"],
                    "county": normalize_county(row["CNTY_NAME"]),
                    "municipality": row["MCD_NAME"],
                    "reportingUnit": row["LABEL"],
                    "ward": row["WARDID"],
                    "reason": "LTSB 2024 feature has no presidential values. Preserve as missing and exclude from graph-ready rows.",
                }
            )
            continue
        require(all(isinstance(value, (int, float)) for value in raw_values), f"LTSB 2024 row {row_index} has partial presidential values")
        require(all(float(value).is_integer() for value in raw_values), f"LTSB 2024 row {row_index} has fractional presidential values")
        values = vote_values(*(int(value) for value in raw_values))
        wide_row = {
            "electionYear": 2024,
            "contestId": "2024-president-ltsb-harmonized",
            "sourceId": source["id"],
            "sourceClass": "harmonizedLtsb",
            "sourceLevel": "ward",
            "rowMethod": "ltsbPopulationAllocation",
            "county": normalize_county(row["CNTY_NAME"]),
            "countyFips": row["CNTY_FIPS"],
            "municipality": row["MCD_NAME"],
            "reportingUnit": row["LABEL"],
            "ward": row["WARDID"],
            "geoid": row["GEOID"],
            **values,
        }
        wide_rows.append(wide_row)
        candidate_rows.extend(
            make_candidate_rows(
                wide_row=wide_row,
                candidates={
                    "dem": "Kamala Harris / Tim Walz",
                    "rep": "Donald Trump / JD Vance",
                    "other": "Other presidential candidates combined",
                },
                source=source,
                notes="Harmonized LTSB comparison row. LTSB documents that 2024 WEC reporting-unit totals were allocated to wards and census blocks using population-based methods, then aggregated to January 2025 wards. Other combines all non-Democratic and non-Republican presidential votes.",
            )
        )
    require(len(features) == 7_086, f"Unexpected LTSB 2024 GeoJSON feature count: {len(features)}")
    require(len(missing_rows) == 140, f"Unexpected LTSB 2024 missing row count: {len(missing_rows)}")
    require(len(wide_rows) == 6_946, f"Unexpected LTSB 2024 graph-ready row count: {len(wide_rows)}")
    return wide_rows, candidate_rows, missing_rows


def import_native_2016(source: dict) -> tuple[list[dict], list[dict]]:
    rows = read_xlsx_rows(source["path"], "Sheet1")
    require(len(rows) == 3_638, f"Unexpected native 2016 row count including headers: {len(rows)}")
    wide_rows = []
    candidate_rows = []
    for row_index, row in enumerate(rows[2:], start=3):
        require(len(row) >= 40, f"Native 2016 row {row_index} is too short")
        county = normalize_county(row[0])
        municipality = require_text(row[1], f"native 2016 row {row_index} municipality")
        reporting_unit = require_text(row[2], f"native 2016 row {row_index} reporting unit")
        for stage, base in (("original", 3), ("recount", 22)):
            total = int(row[base] or 0)
            rep = int(row[base + 1] or 0)
            dem = int(row[base + 2] or 0)
            values = vote_values(total, dem, rep)
            wide_row = {
                "electionYear": 2016,
                "contestId": f"2016-president-wec-native-{stage}",
                "sourceId": source["id"],
                "sourceClass": "nativeOfficial",
                "sourceLevel": "reportingUnit",
                "rowMethod": "original",
                "county": county,
                "municipality": municipality,
                "reportingUnit": reporting_unit,
                "ward": reporting_unit,
                "canvassStage": stage,
                **values,
            }
            wide_rows.append(wide_row)
            candidate_rows.extend(
                make_candidate_rows(
                    wide_row=wide_row,
                    candidates={
                        "dem": "Hillary Clinton / Tim Kaine",
                        "rep": "Donald Trump / Michael Pence",
                        "other": "Other presidential candidates combined",
                    },
                    source=source,
                    notes=f"Native official WEC reporting-unit row from the {stage} canvass block. Other combines all non-Democratic and non-Republican presidential votes.",
                )
            )
    require(len(wide_rows) == 7_272, f"Unexpected native 2016 imported row count: {len(wide_rows)}")
    return wide_rows, candidate_rows


def infer_municipality(reporting_unit: str) -> str:
    return re.split(r"\s+Wards?\b", reporting_unit, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def import_native_2024(source: dict) -> tuple[list[dict], list[dict]]:
    ward_analysis = read_json(DATA / "ward-analysis.json")
    raw_rows = ward_analysis["metadata"]["rows"]
    require(len(raw_rows) == ward_analysis["metadata"]["wardRows"] == 3_503, "Unexpected native 2024 ward row count")
    wide_rows = []
    candidate_rows = []
    for row_index, row in enumerate(raw_rows, start=1):
        reporting_unit = require_text(row.get("ward"), f"native 2024 row {row_index} ward")
        values = vote_values(int(row["total"]), int(row["harris"]), int(row["trump"]))
        wide_row = {
            "electionYear": 2024,
            "contestId": "2024-president-wec-native",
            "sourceId": source["id"],
            "sourceClass": "nativeOfficial",
            "sourceLevel": "reportingUnit",
            "rowMethod": "original",
            "county": normalize_county(row.get("county")),
            "municipality": infer_municipality(reporting_unit),
            "reportingUnit": reporting_unit,
            "ward": reporting_unit,
            **values,
        }
        wide_rows.append(wide_row)
        candidate_rows.extend(
            make_candidate_rows(
                wide_row=wide_row,
                candidates={
                    "dem": "Kamala Harris / Tim Walz",
                    "rep": "Donald Trump / JD Vance",
                    "other": "Other presidential candidates combined",
                },
                source=source,
                notes="Native official WEC ward/reporting-unit row already used by the app. Other combines all non-Democratic and non-Republican presidential votes.",
            )
        )
    return wide_rows, candidate_rows


def statewide(rows: list[dict]) -> dict:
    return aggregate(rows, ())[0]


def totals_match(actual: dict, expected: dict) -> bool:
    return all(actual[key] == expected[key] for key in ("dem", "rep", "other", "total"))


def keyed_totals(rows: list[dict], group_field: str) -> dict[str, dict]:
    return {item[group_field]: item for item in aggregate(rows, (group_field,))}


def main() -> int:
    GENERATED.mkdir(parents=True, exist_ok=True)
    manifest = read_json(MANIFEST)
    ltsb_source = source_by_id(manifest, "ltsb-2012-2020-harmonized-wards")
    ltsb_2024_source = source_by_id(manifest, "ltsb-2024-harmonized-wards")
    native_2016_source = source_by_id(manifest, "wec-2016-native-president-original-and-recount")
    native_2024_source = source_by_id(manifest, "wec-2024-native-federal-state-ward-report")

    ltsb_rows, ltsb_candidates, masked_rows = import_ltsb(ltsb_source)
    ltsb_2024_rows, ltsb_2024_candidates, ltsb_2024_missing_rows = import_ltsb_2024(ltsb_2024_source)
    native_2016_rows, native_2016_candidates = import_native_2016(native_2016_source)
    native_2024_rows, native_2024_candidates = import_native_2024(native_2024_source)

    ltsb_by_year = {
        year: [row for row in ltsb_rows if row["electionYear"] == year]
        for year in (2012, 2016, 2020)
    }
    native_2016_by_stage = {
        stage: [row for row in native_2016_rows if row["canvassStage"] == stage]
        for stage in ("original", "recount")
    }
    series = [
        summarize_series("ltsb-harmonized-2012-president", ltsb_by_year[2012]),
        summarize_series("ltsb-harmonized-2016-president", ltsb_by_year[2016]),
        summarize_series("ltsb-harmonized-2020-president", ltsb_by_year[2020]),
        summarize_series("ltsb-harmonized-2024-president", ltsb_2024_rows),
        summarize_series("wec-native-2016-president-original", native_2016_by_stage["original"]),
        summarize_series("wec-native-2016-president-recount", native_2016_by_stage["recount"]),
        summarize_series("wec-native-2024-president", native_2024_rows),
    ]

    checks = []
    for year in (2012, 2016, 2020):
        actual = statewide(ltsb_by_year[year])
        checks.append(
            {
                "id": f"ltsb-{year}-statewide-official-total",
                "status": "passed" if totals_match(actual, EXPECTED_STATEWIDE[year]) else "failed",
                "actual": actual,
                "expected": EXPECTED_STATEWIDE[year],
            }
        )
    native_recount = statewide(native_2016_by_stage["recount"])
    checks.append(
        {
            "id": "native-2016-recount-statewide-official-total",
            "status": "passed" if totals_match(native_recount, EXPECTED_STATEWIDE[2016]) else "failed",
            "actual": native_recount,
            "expected": EXPECTED_STATEWIDE[2016],
        }
    )
    checks.append(
        {
            "id": "native-2016-recount-matches-ltsb-2016",
            "status": "passed" if totals_match(native_recount, statewide(ltsb_by_year[2016])) else "failed",
            "nativeWecRecount": native_recount,
            "harmonizedLtsb": statewide(ltsb_by_year[2016]),
        }
    )
    native_2016_counties = keyed_totals(native_2016_by_stage["recount"], "county")
    ltsb_2016_counties = keyed_totals(ltsb_by_year[2016], "county")
    county_mismatches = [
        {
            "county": county,
            "nativeWecRecount": native_2016_counties.get(county),
            "harmonizedLtsb": ltsb_2016_counties.get(county),
            "ltsbMinusNative": {
                field: ltsb_2016_counties.get(county, {}).get(field, 0)
                - native_2016_counties.get(county, {}).get(field, 0)
                for field in ("dem", "rep", "other", "total")
            },
        }
        for county in sorted(set(native_2016_counties) | set(ltsb_2016_counties))
        if county not in native_2016_counties
        or county not in ltsb_2016_counties
        or not totals_match(native_2016_counties[county], ltsb_2016_counties[county])
    ]
    observed_county_deltas = {
        mismatch["county"]: mismatch["ltsbMinusNative"]
        for mismatch in county_mismatches
    }
    checks.append(
        {
            "id": "native-2016-recount-county-differences-are-documented",
            "status": "passed"
            if observed_county_deltas == EXPECTED_2016_LTSB_NATIVE_COUNTY_DELTAS
            else "failed",
            "countiesCompared": len(set(native_2016_counties) | set(ltsb_2016_counties)),
            "mismatchedCounties": county_mismatches,
            "interpretation": "LTSB harmonization shifts seven votes from Buffalo County to Trempealeau County relative to the native WEC recount workbook. Statewide totals remain identical. Keep native and harmonized county analyses separate.",
        }
    )
    native_2024_total = statewide(native_2024_rows)
    ltsb_2024_total = statewide(ltsb_2024_rows)
    checks.append(
        {
            "id": "ltsb-2024-statewide-official-total",
            "status": "passed" if totals_match(ltsb_2024_total, EXPECTED_STATEWIDE[2024]) else "failed",
            "actual": ltsb_2024_total,
            "expected": EXPECTED_STATEWIDE[2024],
        }
    )
    checks.append(
        {
            "id": "native-2024-matches-ltsb-2024-statewide",
            "status": "passed" if totals_match(native_2024_total, ltsb_2024_total) else "failed",
            "nativeWec": native_2024_total,
            "harmonizedLtsb": ltsb_2024_total,
        }
    )
    native_2024_counties = keyed_totals(native_2024_rows, "county")
    ltsb_2024_counties = keyed_totals(ltsb_2024_rows, "county")
    county_names_2024 = sorted(set(native_2024_counties) | set(ltsb_2024_counties))
    county_mismatches_2024 = [
        county
        for county in county_names_2024
        if county not in native_2024_counties
        or county not in ltsb_2024_counties
        or not totals_match(native_2024_counties[county], ltsb_2024_counties[county])
    ]
    checks.append(
        {
            "id": "native-2024-matches-ltsb-2024-counties",
            "status": "passed" if not county_mismatches_2024 else "failed",
            "countiesCompared": len(county_names_2024),
            "mismatchedCounties": county_mismatches_2024,
            "interpretation": "The harmonized LTSB 2024 layer preserves the native WEC presidential totals at county level. Ward values remain comparison rows because LTSB documents population-based disaggregation.",
        }
    )
    checks.append(
        {
            "id": "native-2024-statewide-official-total",
            "status": "passed" if totals_match(native_2024_total, EXPECTED_STATEWIDE[2024]) else "failed",
            "actual": native_2024_total,
            "expected": EXPECTED_STATEWIDE[2024],
        }
    )
    failed = [check for check in checks if check["status"] != "passed"]
    require(not failed, f"Historical reconciliation failed: {[check['id'] for check in failed]}")

    generated_at = datetime.now(UTC).isoformat()
    normalized_rows = ltsb_candidates + ltsb_2024_candidates + native_2016_candidates + native_2024_candidates
    normalized_csv = GENERATED / "historical-presidential-results.csv.gz"
    with gzip.open(normalized_csv, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(normalized_rows)
    legacy_csv = GENERATED / "historical-presidential-results.csv"
    if legacy_csv.exists():
        legacy_csv.unlink()

    summary = {
        "metadata": {
            "generatedAt": generated_at,
            "purpose": "Graph-ready Wisconsin presidential-election baseline with native official and LTSB harmonized series kept separate.",
            "normalizedCsv": "historical-presidential-results.csv.gz",
            "seriesCount": len(series),
            "normalizedCandidateRows": len(normalized_rows),
            "maskedLtsbRows": len(masked_rows),
            "missingLtsb2024Rows": len(ltsb_2024_missing_rows),
            "warning": "LTSB rows are harmonized comparison data. Some source totals were redistributed using population-based allocation and must not be labeled as exact native ward totals.",
        },
        "series": series,
    }
    reconciliation = {
        "generatedAt": generated_at,
        "status": "passed",
        "checks": checks,
        "notes": [
            "All statewide presidential totals reconcile for the imported LTSB 2012, 2016, 2020, and 2024 series.",
            "The native WEC 2016 recount totals match the LTSB 2016 statewide totals.",
            "The existing native WEC 2024 app rows reconcile to the certified statewide presidential totals.",
            "The harmonized LTSB 2024 statewide totals match the existing native WEC 2024 app totals.",
            "Seventy LTSB geography rows contain masked presidential values represented as ****. They are listed separately and excluded from chart-ready rows rather than treated as zero-vote rows.",
            "One hundred forty LTSB 2024 ward features contain no presidential values. They are listed separately and excluded from chart-ready rows rather than treated as zero-vote rows.",
        ],
    }
    write_json(GENERATED / "historical-presidential-summary.json", summary, compact=True)
    write_json(GENERATED / "historical-reconciliation-report.json", reconciliation)
    write_json(
        GENERATED / "ltsb-masked-presidential-rows.json",
        {
            "metadata": {
                "generatedAt": generated_at,
                "sourceId": ltsb_source["id"],
                "rows": len(masked_rows),
                "reason": "Masked LTSB presidential values are preserved as missing and excluded from graph-ready rows.",
            },
            "rows": masked_rows,
        },
    )
    write_json(
        GENERATED / "ltsb-2024-missing-presidential-rows.json",
        {
            "metadata": {
                "generatedAt": generated_at,
                "sourceId": ltsb_2024_source["id"],
                "rows": len(ltsb_2024_missing_rows),
                "reason": "LTSB 2024 features without presidential values are preserved as missing and excluded from graph-ready rows.",
            },
            "rows": ltsb_2024_missing_rows,
        },
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "normalizedCandidateRows": len(normalized_rows),
                "series": [{"id": item["id"], "rows": item["rowCount"], "statewide": item["statewide"]} for item in series],
                "maskedLtsbRows": len(masked_rows),
                "missingLtsb2024Rows": len(ltsb_2024_missing_rows),
                "reconciliationChecks": len(checks),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, StopIteration) as error:
        print(f"Historical import failed: {error}", file=sys.stderr)
        sys.exit(1)
