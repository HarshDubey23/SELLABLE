"""Assert MISSION_TEMPLATES in scripts/sign_mission.py stay in sync."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_signer_scenario_sync():
    repo = Path(__file__).resolve().parents[1]
    sign_script = repo / "scripts" / "sign_mission.py"
    scenarios_dir = repo / "missions"

    assert sign_script.exists(), "scripts/sign_mission.py missing"
    assert scenarios_dir.exists(), "missions/ dir missing"

    src = sign_script.read_text()
    template_ids = set(re.findall(r'"([a-z_]+)"\s*:\s*\{', src))

    mission_files = {f.stem for f in scenarios_dir.glob("*.json")}

    missing_files = template_ids - mission_files
    assert not missing_files, f"Templates without mission JSON files: {missing_files}"

    scenarios_py = repo / "apps" / "api" / "agent" / "scenarios.py"
    if scenarios_py.exists():
        sc_src = scenarios_py.read_text()
        # Match scenario ids in the SCENARIOS dict: keys whose value is a
        # nested dict (e.g. "happy_path": {). Plain string keys like
        # "title": "..." are not scenario ids.
        scenario_ids = set(re.findall(r'"([a-z_]+)"\s*:\s*\{', sc_src))
        missing_for_runner = scenario_ids - mission_files
        assert not missing_for_runner, f"Scenarios without mission JSON: {missing_for_runner}"


def test_mission_jsons_are_signed():
    """Every mission JSON must have a non-empty signature field."""
    repo = Path(__file__).resolve().parents[1]
    missions_dir = repo / "missions"
    for mf in missions_dir.glob("*.json"):
        # Mandate files are side-effects of agent runs (wallet_bridge), not missions
        if "_mandate" in mf.name:
            continue
        blob = json.loads(mf.read_text())
        assert blob.get("signature"), f"{mf.name}: missing or empty signature"
        assert blob.get("mission_id"), f"{mf.name}: missing mission_id"
        assert blob.get("expires_at", 0) > 0, f"{mf.name}: missing/invalid expires_at"
