"""Hermes voice-call-timeout plugin — configurable Discord voice inactivity timeout."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import weakref
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------
PLUGIN_NAME = "voice-call-timeout"
DEFAULT_TIMEOUT_SECONDS = 300
_DISABLED_WORDS = {"off", "disable", "disabled", "none", "never"}
_DURATION_TOKEN_RE = re.compile(r"(\d+)(s|m|h|d)?")
_UNIT_MULTIPLIERS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}

logger = logging.getLogger(__name__)
_LIVE_ADAPTERS: weakref.WeakSet = weakref.WeakSet()
_PATCHED = False


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
        unit = match.group(2) or ""
        if unit not in _UNIT_MULTIPLIERS:
            raise ValueError(f"Invalid timeout value: {value}")
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


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()


def get_settings_store() -> TimeoutSettingsStore:
    return TimeoutSettingsStore(
        _get_hermes_home() / "plugin-data" / PLUGIN_NAME / "settings.json",
        default_timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )


def get_current_timeout_seconds() -> Optional[int]:
    return get_settings_store().load()


def apply_timeout_to_live_adapters(timeout_seconds: Optional[int]) -> None:
    for adapter in list(_LIVE_ADAPTERS):
        try:
            adapter.VOICE_TIMEOUT = 0 if timeout_seconds is None else int(timeout_seconds)
            for guild_id in list(getattr(adapter, "_voice_clients", {}).keys()):
                adapter._reset_voice_timeout(guild_id)
        except Exception as exc:
            logger.debug("Failed applying timeout to live adapter: %s", exc)


def _build_status_message() -> str:
    timeout_seconds = get_current_timeout_seconds()
    store_path = get_settings_store().path
    return (
        "[voice-timeout] Discord voice inactivity timeout is "
        f"**{format_timeout(timeout_seconds)}**.\n"
        f"Settings file: `{store_path}`\n"
        "Use `/voice-timeout 20m` to change it or `/voice-timeout off` to disable auto-leave."
    )


def handle_voice_timeout_command(raw_args: str = "") -> str:
    text = (raw_args or "").strip()
    lowered = text.lower()
    if not text or lowered in {"status", "show"}:
        return _build_status_message()
    if lowered in {"help", "-h", "--help"}:
        return (
            "/voice-timeout — configure Discord voice inactivity timeout\n\n"
            "Examples:\n"
            "  /voice-timeout status\n"
            "  /voice-timeout 20m\n"
            "  /voice-timeout 1h 30m\n"
            "  /voice-timeout off\n"
        )
    if lowered.startswith("set "):
        text = text[4:].strip()

    timeout_seconds = parse_timeout_spec(text)
    get_settings_store().save(timeout_seconds)
    apply_timeout_to_live_adapters(timeout_seconds)
    return (
        "[voice-timeout] Updated Discord voice inactivity timeout to "
        f"**{format_timeout(timeout_seconds)}**."
    )


def patch_discord_adapter() -> None:
    global _PATCHED
    if _PATCHED:
        return
    try:
        from gateway.platforms.discord import DiscordPlatformAdapter
    except Exception as exc:
        logger.debug("Discord adapter not available yet for %s: %s", PLUGIN_NAME, exc)
        return

    original_init = DiscordPlatformAdapter.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        timeout_seconds = get_current_timeout_seconds()
        self.VOICE_TIMEOUT = 0 if timeout_seconds is None else int(timeout_seconds)
        try:
            _LIVE_ADAPTERS.add(self)
        except TypeError:
            pass

    def patched_reset_voice_timeout(self, guild_id: int) -> None:
        task = self._voice_timeout_tasks.pop(guild_id, None)
        if task:
            task.cancel()
        timeout_seconds = get_current_timeout_seconds()
        self.VOICE_TIMEOUT = 0 if timeout_seconds is None else int(timeout_seconds)
        if timeout_seconds is None or timeout_seconds <= 0:
            return
        self._voice_timeout_tasks[guild_id] = asyncio.ensure_future(
            self._voice_timeout_handler(guild_id)
        )

    DiscordPlatformAdapter.__init__ = patched_init
    DiscordPlatformAdapter._reset_voice_timeout = patched_reset_voice_timeout
    _PATCHED = True
    logger.info("Patched Discord voice timeout handling for %s", PLUGIN_NAME)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    patch_discord_adapter()
    ctx.register_command(
        "voice-timeout",
        handle_voice_timeout_command,
        description="Set the Discord voice inactivity timeout (examples: /voice-timeout 20m, /voice-timeout off).",
    )