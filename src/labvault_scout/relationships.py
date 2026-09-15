from __future__ import annotations

from collections import defaultdict
from pathlib import Path

OPEN_COPY_EXTENSIONS = {".csv", ".tsv", ".txt", ".json", ".xml"}
SOURCE_RISKS = {"WATCH", "RESCUE"}


def detect_open_copies(rows: list[dict]) -> None:
    """Annotate likely open copies using same-directory, same-stem evidence."""
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        path = Path(row["path"])
        index[(str(path.parent).lower(), path.stem.lower())].append(row)

    for row in rows:
        row["open_copy"] = ""
        if row["risk"] not in SOURCE_RISKS:
            continue
        path = Path(row["path"])
        candidates = index[(str(path.parent).lower(), path.stem.lower())]
        matches = [
            item["path"]
            for item in candidates
            if item["path"] != row["path"] and Path(item["path"]).suffix.lower() in OPEN_COPY_EXTENSIONS
        ]
        if matches:
            row["open_copy"] = "; ".join(sorted(matches))
