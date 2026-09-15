from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path


def load_rules() -> dict[str, dict]:
    rule_path = files("labvault_scout").joinpath("rules/scientific_formats.json")
    rules = json.loads(rule_path.read_text(encoding="utf-8"))
    return {item["extension"].lower(): item for item in rules}


def classify(path: Path, rules: dict[str, dict]) -> dict:
    ext = path.suffix.lower()
    rule = rules.get(ext)
    if rule:
        return rule
    return {
        "extension": ext or "(none)",
        "name": "Unknown",
        "category": "unknown",
        "risk": "UNKNOWN",
        "reason": "No matching format rule.",
        "preferred_exports": [],
    }
