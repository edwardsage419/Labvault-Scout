from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

OPEN_COPY_EXTENSIONS = {".csv", ".tsv", ".txt", ".json", ".xml"}
SOURCE_RISKS = {"WATCH", "RESCUE"}
DERIVATIVE_SUFFIXES = ("export", "exported", "converted", "conversion", "copy")

_TOKEN_SPLIT = re.compile(r"[_\-. ]+")


def _family_stem(path: Path) -> tuple[str, bool]:
    """Return a conservative normalized stem and whether a derivative suffix was removed."""
    tokens = [token for token in _TOKEN_SPLIT.split(path.stem.lower()) if token]
    if len(tokens) >= 2 and tokens[-1] in DERIVATIVE_SUFFIXES:
        return "_".join(tokens[:-1]), True
    return "_".join(tokens), False


def detect_open_copies(rows: list[dict]) -> None:
    """Annotate likely open copies using exact or conservative derivative-family evidence."""
    exact: dict[tuple[str, str], list[dict]] = defaultdict(list)
    families: dict[tuple[str, str], list[tuple[dict, bool]]] = defaultdict(list)

    for row in rows:
        path = Path(row["path"])
        parent = str(path.parent)
        exact[(parent, path.stem.lower())].append(row)
        family, derivative = _family_stem(path)
        families[(parent, family)].append((row, derivative))

    for row in rows:
        row["open_copy"] = ""
        row["relationship_evidence"] = ""
        row["relationship_strength"] = ""
        if row["risk"] not in SOURCE_RISKS:
            continue

        path = Path(row["path"])
        parent = str(path.parent)
        exact_candidates = exact[(parent, path.stem.lower())]
        exact_matches = [
            item["path"]
            for item in exact_candidates
            if item["path"] != row["path"] and Path(item["path"]).suffix.lower() in OPEN_COPY_EXTENSIONS
        ]
        if exact_matches:
            row["open_copy"] = "; ".join(sorted(exact_matches))
            row["relationship_evidence"] = "same-directory same-stem open copy"
            row["relationship_strength"] = "EXACT"
            continue

        family, source_derivative = _family_stem(path)
        if source_derivative:
            continue
        family_matches = [
            item["path"]
            for item, derivative in families[(parent, family)]
            if derivative
            and item["path"] != row["path"]
            and Path(item["path"]).suffix.lower() in OPEN_COPY_EXTENSIONS
        ]
        if family_matches:
            row["open_copy"] = "; ".join(sorted(family_matches))
            row["relationship_evidence"] = "same-directory derivative-suffix open copy"
            row["relationship_strength"] = "DERIVATIVE"
