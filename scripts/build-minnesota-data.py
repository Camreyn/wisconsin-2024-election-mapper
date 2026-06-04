import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_BUILDER = ROOT / "scripts" / "build-state-data.py"
MINNESOTA_CONFIG = ROOT / "data" / "state-configs" / "mn.json"


def main():
    spec = importlib.util.spec_from_file_location("state_builder", STATE_BUILDER)
    state_builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(state_builder)
    config = state_builder.json.loads(MINNESOTA_CONFIG.read_text(encoding="utf-8"))
    summary = state_builder.build_state(config)
    print(state_builder.json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
