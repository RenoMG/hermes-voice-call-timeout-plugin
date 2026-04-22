from __future__ import annotations

import asyncio
import logging
import os
import weakref
from pathlib import Path
from typing import Optional

from .settings import DEFAULT_TIMEOUT_SECONDS, TimeoutSettingsStore, format_timeout, parse_timeout_spec

logger = logging.getLogger(__name__)
_PLUGIN_NAME = "voice-call-timeout"
_LIVE_ADAPTERS = weakref.WeakSet()
_PATCHED = False


def _get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()


def get_settings_store() -> TimeoutSettingsStore:
    return TimeoutSettingsStore(
        _get_hermes_home() / "plugin-data" / _PLUGIN_NAME / "settings.json",
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
        logger.debug("Discord adapter not available yet for %s: %s", _PLUGIN_NAME, exc)
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
    logger.info("Patched Discord voice timeout handling for %s", _PLUGIN_NAME)


def register(ctx) -> None:
    patch_discord_adapter()
    ctx.register_command(
        "voice-timeout",
        handle_voice_timeout_command,
        description="Set the Discord voice inactivity timeout (examples: /voice-timeout 20m, /voice-timeout off).",
    )
