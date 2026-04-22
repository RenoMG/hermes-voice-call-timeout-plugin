from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

DEFAULT_TIMEOUT_SECONDS = 300
_DISABLED_WORDS = {"off", "disable", "disabled", "none", "never"}
_DURATION_TOKEN_RE = re.compile(r"(\d+)([smhd]?)")
_UNIT_MULTIPLIERS = {
    "": 1,
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


def parse_timeout_spec(value: str) -> Optional[int]:
    text = (value or "").strip().lower()
    if not text:
        raise ValueError("Timeout value is required.")
    if text in _DISABLED_WORDS:
        return None

    compact = re.sub(r"\s+", "", text)
    if compact in _DISABLED_WORDS:
        return None

    total = 0
    position = 0
    for match in _DURATION_TOKEN_RE.finditer(compact):
        if match.start() != position:
            raise ValueError(f"Invalid timeout value: {value}")
        amount = int(match.group(1))
        unit = match.group(2)
        total += amount * _UNIT_MULTIPLIERS[unit]
        position = match.end()

    if position != len(compact) or total <= 0:
        raise ValueError(f"Invalid timeout value: {value}")

    return total


def format_timeout(seconds: Optional[int]) -> str:
    if seconds is None:
        return "disabled"
    remaining = int(seconds)
    parts = []
    for unit_seconds, suffix in ((86400, "d"), (3600, "h"), (60, "m"), (1, "s")):
        if remaining >= unit_seconds:
            count, remaining = divmod(remaining, unit_seconds)
            parts.append(f"{count}{suffix}")
    return " ".join(parts) if parts else "0s"


class TimeoutSettingsStore:
    def __init__(self, path: Path, default_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.path = Path(path)
        self.default_timeout_seconds = default_timeout_seconds

    def load(self) -> Optional[int]:
        if not self.path.exists():
            return self.default_timeout_seconds
        data = json.loads(self.path.read_text())
        value = data.get("voice_timeout_seconds", self.default_timeout_seconds)
        if value is None:
            return None
        return int(value)

    def save(self, seconds: Optional[int]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"voice_timeout_seconds": seconds}, indent=2, sort_keys=True) + "\n"
        )
