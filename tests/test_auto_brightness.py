import unittest
from contextlib import nullcontext
from unittest.mock import Mock, call, patch

from auto_brightness import AutoBrightnessService


def make_service():
    service = object.__new__(AutoBrightnessService)
    service.config = {
        'displays': [],
        'update_interval': 300,
        'display_refresh_interval': 1800,
        'monitor_offsets': {},
    }
    hybrid = Mock()
    hybrid.monitors = {}
    hybrid.last_detection_succeeded = True
    service.hybrid_control = hybrid
    service._cached_displays = []
    service._display_cache_signature = ()
    service._display_cache_refreshed_at = 0.0
    service._last_brightness = {}
    return service, hybrid


class DisplayDiscoveryCacheTests(unittest.TestCase):
    def test_reuses_topology_until_refresh_interval(self):
        service, hybrid = make_service()
        hybrid.detect_monitors.return_value = {'1': {}, '2': {}}
        service._connected_display_signature = Mock(return_value=('card1-DP-1', 'card1-DP-2'))

        with patch('auto_brightness.time.monotonic', side_effect=[100.0, 200.0]):
            first = service.get_displays(force_refresh=True)
            second = service.get_displays()

        self.assertEqual(first, ['1', '2'])
        self.assertEqual(second, ['1', '2'])
        hybrid.detect_monitors.assert_called_once_with(
            include_capabilities=False,
            force_refresh=True,
        )

    def test_connector_change_invalidates_topology(self):
        service, hybrid = make_service()
        service._last_brightness = {'1': 50}
        hybrid.detect_monitors.side_effect = [
            {'1': {}},
            {'1': {}, '2': {}},
        ]
        service._connected_display_signature = Mock(
            side_effect=[('card1-DP-1',), ('card1-DP-1', 'card1-HDMI-A-1')]
        )

        with patch('auto_brightness.time.monotonic', side_effect=[100.0, 200.0]):
            first = service.get_displays(force_refresh=True)
            second = service.get_displays()

        self.assertEqual(first, ['1'])
        self.assertEqual(second, ['1', '2'])
        self.assertEqual(hybrid.detect_monitors.call_count, 2)
        self.assertEqual(service._last_brightness, {})

    def test_failed_refresh_retains_last_known_topology(self):
        service, hybrid = make_service()
        service._cached_displays = ['1', '2']
        service._display_cache_signature = ('card1-DP-1',)
        service._display_cache_refreshed_at = 1.0
        service._connected_display_signature = Mock(return_value=('card1-DP-1',))
        hybrid.detect_monitors.return_value = {}

        with patch('auto_brightness.time.monotonic', return_value=5000.0):
            displays = service.get_displays()

        self.assertEqual(displays, ['1', '2'])

    def test_incomplete_refresh_does_not_advance_cache_generation(self):
        service, hybrid = make_service()
        service._cached_displays = ['1', '2']
        service._display_cache_signature = ('card1-DP-1',)
        service._display_cache_refreshed_at = 1.0
        service._connected_display_signature = Mock(return_value=('card1-DP-1',))
        hybrid.detect_monitors.return_value = {'1': {}, '2': {}}
        hybrid.last_detection_succeeded = False

        with patch('auto_brightness.time.monotonic', return_value=5000.0):
            displays = service.get_displays()

        self.assertEqual(displays, ['1', '2'])
        self.assertEqual(service._display_cache_refreshed_at, 1.0)


class BrightnessWriteTests(unittest.TestCase):
    def test_unchanged_value_does_not_touch_monitor(self):
        service, hybrid = make_service()
        service._last_brightness['1'] = 50

        result = service.set_brightness('1', 0.5)

        self.assertTrue(result)
        hybrid.set_brightness.assert_not_called()

    def test_changed_value_updates_monitor_once(self):
        service, hybrid = make_service()
        hybrid.set_brightness.return_value = True

        result = service.set_brightness('1', 0.5)

        self.assertTrue(result)
        hybrid.set_brightness.assert_called_once_with('1', 50)
        self.assertEqual(service._last_brightness['1'], 50)

    def test_scheduled_generation_keeps_monitor_order(self):
        service, _ = make_service()
        service.set_brightness = Mock(side_effect=[True, True])

        with patch('auto_brightness.serialized_ddc_access', return_value=nullcontext()):
            results = service.set_brightness_targets({'2': 0.4, '1': 0.5})

        self.assertEqual(results, {'2': True, '1': True})
        self.assertEqual(
            service.set_brightness.call_args_list,
            [call('2', 0.4), call('1', 0.5)],
        )


if __name__ == '__main__':
    unittest.main()
