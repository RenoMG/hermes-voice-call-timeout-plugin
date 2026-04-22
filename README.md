# Hermes Voice Call Timeout Plugin

A Hermes Agent plugin that lets you choose how long Hermes stays in a Discord voice call before leaving for inactivity.

## What it does

Hermes already has a hard-coded Discord voice inactivity timeout in the Discord platform adapter. This plugin makes that timeout configurable without editing Hermes core.

It patches three methods on `DiscordAdapter` (`discord.DiscordAdapter` in current Hermes, with fallback to `DiscordPlatformAdapter` on older builds) at startup:

- **`__init__`** — applies the saved timeout to each adapter instance and tracks live adapters
- **`_reset_voice_timeout`** — cancels the old inactivity task and recreates it using the saved timeout; skips recreation if timeout is disabled
- **`_voice_timeout_handler`** — replaces the core timeout handler so that when disabled, the task simply doesn't schedule a disconnect (instead of sleeping 0 seconds and immediately leaving)

Because the adapter's timer is reset whenever voice activity or playback happens, changing the timeout here affects the real auto-leave behavior without needing to fork Hermes itself.

## Features

- Set the Discord voice idle timeout with a simple slash-style command
- Accepts human-friendly values like `20m`, `1h 30m`, or raw seconds like `900`
- Supports disabling auto-leave with `off`
- Persists settings across restarts
- Re-applies the new timeout to active voice sessions immediately

## Commands

```text
/voice-timeout status
/voice-timeout 20m
/voice-timeout 1h 30m
/voice-timeout off
```

## Install

### Clone from GitHub

```bash
cd ~/.hermes/plugins
git clone https://github.com/RenoMG/hermes-voice-call-timeout-plugin.git voice-call-timeout
```

### Enable the plugin

Enable with ```hermes plugins``` and select voice-call-timeout

OR

Add to your Hermes config:

```yaml
plugins:
  enabled:
    - voice-call-timeout
```

Restart Hermes or the gateway after enabling it.

## How it stores settings

The timeout is saved to:

```text
$HERMES_HOME/plugin-data/voice-call-timeout/settings.json
```

Default when no settings file exists: `300` seconds (`5m`).

## Development

Run tests with:

```bash
python -m unittest tests/test_voice_call_timeout_plugin.py
```
