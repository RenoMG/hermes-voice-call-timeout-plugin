# About

## Purpose

This plugin exists to solve one very specific annoyance: Hermes leaves a Discord voice call after a fixed inactivity timeout, and there was no user-facing way to change it.

Hermes core currently defines this in the Discord adapter as a class-level timeout used by the voice auto-disconnect task. The plugin turns that fixed value into a configurable setting.

## How it works

At plugin registration time, the plugin patches `DiscordPlatformAdapter` in two places:

1. `__init__` — applies the saved timeout to each adapter instance and tracks live adapters.
2. `_reset_voice_timeout` — cancels the old inactivity task and recreates it using the saved timeout value, or skips recreation if the timeout is disabled.

Because the adapter's timer is reset whenever voice activity or playback happens, changing the timeout here affects the real auto-leave behavior without needing to fork Hermes itself.

## Runtime behavior

- If no config file exists, the plugin uses Hermes' current default behavior: `5m`
- If you run `/voice-timeout 20m`, future resets use `20 minutes`
- If you run `/voice-timeout off`, the plugin stops scheduling inactivity auto-disconnect tasks
- When the value changes, all live Discord adapters are updated and active guild voice timers are reset immediately

## Why a plugin instead of a core patch?

Because this is a clean user-land extension:

- no need to maintain a custom Hermes fork
- no direct edits to upstream source
- easy to disable or remove
- good proof-of-concept for a future upstream config option

## Files

- `plugin.yaml` — Hermes plugin manifest
- `__init__.py` — single-file plugin: entry point, settings, command handling, Discord adapter patching (flat structure required by Hermes plugin loader)
- `tests/test_voice_call_timeout_plugin.py` — regression tests for parsing, persistence, and live adapter updates

## Limitations

This version sets a global timeout for Discord voice calls handled by the running Hermes profile. It does not currently store separate timeout values per server, per channel, or per user.

That said… for the actual problem you described, this gets the job done nicely ★
