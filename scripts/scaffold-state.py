import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "state-configs" / "_template.json"


def state_slug(code):
    return re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")


def title_from_code(code):
    return code.upper()


def main():
    parser = argparse.ArgumentParser(description="Create a starter state config from data/state-configs/_template.json.")
    parser.add_argument("code", help="Two-letter state code, such as MI or PA.")
    parser.add_argument("--name", help="State display name. Defaults to the upper-case code.")
    parser.add_argument("--authority", help="Election authority display name. Defaults to '<name> election authority'.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing scaffolded config.")
    args = parser.parse_args()

    code = args.code.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise SystemExit("State code must be two letters, such as MI or PA.")

    name = args.name.strip() if args.name else title_from_code(code)
    authority = args.authority.strip() if args.authority else f"{name} election authority"
    slug = state_slug(code)
    output = ROOT / "data" / "state-configs" / f"{slug}.json"
    if output.exists() and not args.force:
        raise SystemExit(f"{output.relative_to(ROOT)} already exists. Pass --force to overwrite it.")

    text = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{STATE_CODE}}": code,
        "{{STATE_NAME}}": name,
        "{{STATE_AUTHORITY}}": authority,
        "{{state_slug}}": slug,
    }
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    output.write_text(text, encoding="utf-8")
    print(output.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
