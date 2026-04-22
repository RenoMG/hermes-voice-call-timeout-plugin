import sys
from pathlib import Path
import unittest

# Add plugin directory to path so we can import __init__ as a flat module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import from the flat __init__ module
import __init__ as voice_timeout
from __init__ import (
    TimeoutSettingsStore,
    format_timeout,
    parse_timeout_spec,
)


class VoiceCallTimeoutPluginTests(unittest.TestCase):
    def test_parse_timeout_spec_supports_human_friendly_durations(self):
        self.assertEqual(parse_timeout_spec("20m"), 1200)
        self.assertEqual(parse_timeout_spec("1h 30m"), 5400)
        self.assertEqual(parse_timeout_spec("45"), 45)

    def test_parse_timeout_spec_can_disable_timeout(self):
        for value in ("off", "disable", "none"):
            self.assertIsNone(parse_timeout_spec(value))

    def test_parse_timeout_spec_rejects_bad_values(self):
        with self.assertRaises(ValueError):
            parse_timeout_spec("bananas")

    def test_settings_store_round_trip(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = TimeoutSettingsStore(Path(tmpdir) / "settings.json")
            self.assertEqual(store.load(), 300)
            store.save(1800)
            self.assertEqual(store.load(), 1800)
            store.save(None)
            self.assertIsNone(store.load())

    def test_format_timeout_is_human_readable(self):
        self.assertEqual(format_timeout(300), "5m")
        self.assertEqual(format_timeout(5400), "1h 30m")
        self.assertEqual(format_timeout(None), "disabled")

    def test_apply_timeout_to_live_adapters_cancels_tasks_when_disabled(self):
        """When disabling (None), existing timeout tasks must be cancelled."""
        class FakeTask:
            def __init__(self):
                self.cancelled = False
            def cancel(self):
                self.cancelled = True

        class FakeAdapter:
            def __init__(self):
                self.VOICE_TIMEOUT = 300
                self._voice_clients = {111: object()}
                self._voice_timeout_tasks = {111: FakeTask()}
                self.resets = []

            def _reset_voice_timeout(self, guild_id):
                self.resets.append(guild_id)

        adapter = FakeAdapter()
        task = adapter._voice_timeout_tasks[111]
        original = voice_timeout._LIVE_ADAPTERS
        try:
            voice_timeout._LIVE_ADAPTERS = {adapter}
            # Disabling should cancel tasks, NOT call _reset_voice_timeout
            voice_timeout.apply_timeout_to_live_adapters(None)
        finally:
            voice_timeout._LIVE_ADAPTERS = original

        self.assertEqual(adapter.VOICE_TIMEOUT, 0)
        # Task was cancelled
        self.assertTrue(task.cancelled)
        # Task was removed from the dict
        self.assertNotIn(111, adapter._voice_timeout_tasks)
        # _reset_voice_timeout should NOT have been called when disabling
        self.assertEqual(adapter.resets, [])

    def test_apply_timeout_to_live_adapters_resets_when_enabled(self):
        """When changing to a new timeout value, timers should be reset."""
        class FakeAdapter:
            def __init__(self):
                self.VOICE_TIMEOUT = 300
                self._voice_clients = {111: object(), 222: object()}
                self._voice_timeout_tasks = {}
                self.resets = []

            def _reset_voice_timeout(self, guild_id):
                self.resets.append(guild_id)

        adapter = FakeAdapter()
        original = voice_timeout._LIVE_ADAPTERS
        try:
            voice_timeout._LIVE_ADAPTERS = {adapter}
            voice_timeout.apply_timeout_to_live_adapters(1800)
        finally:
            voice_timeout._LIVE_ADAPTERS = original

        self.assertEqual(adapter.VOICE_TIMEOUT, 1800)
        self.assertEqual(adapter.resets, [111, 222])


if __name__ == "__main__":
    unittest.main()