from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path


def _index_rules(items: list[dict]) -> dict[str, dict]:
    """Index rules by normalized extension and reject duplicate entries."""
    indexed: dict[str, dict] = {}
    for item in items:
        extension = item["extension"].lower()
        if extension in indexed:
            raise ValueError(f"Duplicate scientific format rule extension: {extension}")
        indexed[extension] = item
    return indexed


def load_rules() -> dict[str, dict]:
    rule_path = files("labvault_scout").joinpath("rules/scientific_formats.json")
    rules = json.loads(rule_path.read_text(encoding="utf-8"))
    return _index_rules(rules)


def rules_sha256(rules: dict[str, dict]) -> str:
    """Return a deterministic fingerprint of the active preservation rules."""
    canonical = json.dumps(
        rules,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def matched_extension(path: Path, rules: dict[str, dict]) -> str:
    """Return the longest configured extension matching the file name."""
    name = path.name.lower()
    matches = [extension for extension in rules if name.endswith(extension)]
    if matches:
        return max(matches, key=len)
    return path.suffix.lower()


def classify(path: Path, rules: dict[str, dict]) -> dict:
    ext = matched_extension(path, rules)
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
