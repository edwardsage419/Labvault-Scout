from __future__ import annotations

import hashlib
import json
import re
from importlib.resources import files
from pathlib import Path


RULE_FIELDS = {"extension", "name", "category", "risk", "reason", "preferred_exports"}
RULE_RISKS = {"SAFE", "WATCH", "RESCUE"}
RULE_EXTENSION_RE = re.compile(r"^\.[a-z0-9]+(?:\.[a-z0-9]+)*$")
RULE_CATEGORY_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
RULE_EXPORT_RE = re.compile(r"^[a-z0-9]+$")


def _validate_rule(item: object, index: int) -> dict:
    """Validate one packaged scientific-format rule."""
    prefix = f"Invalid scientific format rule at index {index}"
    if not isinstance(item, dict):
        raise ValueError(f"{prefix}: expected object")
    if set(item) != RULE_FIELDS:
        raise ValueError(f"{prefix}: invalid fields")

    extension = item["extension"]
    if (
        not isinstance(extension, str)
        or extension != extension.lower()
        or not RULE_EXTENSION_RE.fullmatch(extension)
    ):
        raise ValueError(f"{prefix}: invalid extension")

    if not isinstance(item["name"], str) or not item["name"].strip():
        raise ValueError(f"{prefix}: invalid name")
    if not isinstance(item["category"], str) or not RULE_CATEGORY_RE.fullmatch(item["category"]):
        raise ValueError(f"{prefix}: invalid category")
    if item["risk"] not in RULE_RISKS:
        raise ValueError(f"{prefix}: invalid risk")
    if not isinstance(item["reason"], str) or not item["reason"].strip():
        raise ValueError(f"{prefix}: invalid reason")

    exports = item["preferred_exports"]
    if (
        not isinstance(exports, list)
        or len(exports) != len(set(exports))
        or not all(isinstance(value, str) and RULE_EXPORT_RE.fullmatch(value) for value in exports)
    ):
        raise ValueError(f"{prefix}: invalid preferred_exports")
    return item


def _index_rules(items: object) -> dict[str, dict]:
    """Validate and index rules by normalized extension."""
    if not isinstance(items, list):
        raise ValueError("Scientific format rules must be a JSON array")

    indexed: dict[str, dict] = {}
    for index, raw_item in enumerate(items):
        item = _validate_rule(raw_item, index)
        extension = item["extension"]
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
