# Hermes Voice Call Timeout Plugin

A Hermes Agent plugin that lets you choose how long Hermes stays in a Discord voice call before leaving for inactivity.

## What it does

Hermes already has a hard-coded Discord voice inactivity timeout in the Discord platform adapter. This plugin makes that timeout configurable without editing Hermes core.

It patches `gateway.platforms.discord.DiscordAdapter` at startup so the adapter reads a persisted timeout value instead of relying on the built-in `VOICE_TIMEOUT = 300` default.

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

### Option 1: clone from GitHub (public)

```bash
cd ~/.hermes/plugins
git clone https://github.com/RenoMG/hermes-voice-call-timeout-plugin.git voice-call-timeout
```

### Option 2: clone from Gitea (local mirror)

```bash
cd ~/.hermes/plugins
git clone http://192.168.50.24:3000/Rikka/hermes-voice-call-timeout-plugin.git voice-call-timeout
```

### Option 3: copy the plugin directory manually

Copy this repository's contents into:

```text
~/.hermes/plugins/voice-call-timeout/
```

The directory must contain `plugin.yaml` and `__init__.py` at its root.

### Enable the plugin

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

## Repos

- **GitHub (public):** https://github.com/RenoMG/hermes-voice-call-timeout-plugin
- **Gitea (local mirror):** http://192.168.50.24:3000/Rikka/hermes-voice-call-timeout-plugin