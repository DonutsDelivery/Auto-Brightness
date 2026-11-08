import os
import multiprocessing
import subprocess
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import monitor_control


def lock_process(lock_path, queue, label, hold_seconds):
    os.environ['AUTO_BRIGHTNESS_DDC_LOCK'] = lock_path
    with monitor_control.serialized_ddc_access(timeout=2.0):
        queue.put((label, 'enter', time.monotonic()))
        time.sleep(hold_seconds)
        queue.put((label, 'exit', time.monotonic()))


class SerializedDDCAccessTests(unittest.TestCase):
    def test_lock_is_reentrant_in_one_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                with monitor_control.serialized_ddc_access(timeout=0.2):
                    with monitor_control.serialized_ddc_access(timeout=0.2):
                        self.assertTrue(os.path.exists(lock_path))

    def test_lock_serializes_threads(self):
        active = 0
        maximum_active = 0
        state_lock = threading.Lock()

        def worker():
            nonlocal active, maximum_active
            with monitor_control.serialized_ddc_access(timeout=1.0):
                with state_lock:
                    active += 1
                    maximum_active = max(maximum_active, active)
                time.sleep(0.03)
                with state_lock:
                    active -= 1

        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                threads = [threading.Thread(target=worker) for _ in range(3)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

        self.assertEqual(maximum_active, 1)

    def test_lock_serializes_processes_and_recovers(self):
        context = multiprocessing.get_context('fork')
        queue = context.Queue()
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            first = context.Process(target=lock_process, args=(lock_path, queue, 'first', 0.2))
            first.start()
            first_enter = queue.get(timeout=2)
            self.assertEqual(first_enter[:2], ('first', 'enter'))

            second = context.Process(target=lock_process, args=(lock_path, queue, 'second', 0.0))
            second.start()
            first_exit = queue.get(timeout=2)
            second_enter = queue.get(timeout=2)
            second_exit = queue.get(timeout=2)
            first.join(timeout=2)
            second.join(timeout=2)

            self.assertEqual(first_exit[:2], ('first', 'exit'))
            self.assertEqual(second_enter[:2], ('second', 'enter'))
            self.assertGreaterEqual(second_enter[2], first_exit[2])
            self.assertEqual(second_exit[:2], ('second', 'exit'))
            self.assertEqual(first.exitcode, 0)
            self.assertEqual(second.exitcode, 0)

            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                with monitor_control.serialized_ddc_access(timeout=0.2):
                    pass

    @patch('monitor_control.subprocess.run')
    def test_run_ddcutil_is_bounded(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout='', stderr='')
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                monitor_control.run_ddcutil(['detect', '--brief'], timeout=7)

        run.assert_called_once_with(
            ['ddcutil', 'detect', '--brief'],
            capture_output=True,
            text=True,
            check=True,
            timeout=7,
        )

    def test_timed_out_ddcutil_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            executable = os.path.join(directory, 'ddcutil')
            with open(executable, 'w') as script:
                script.write('#!/bin/sh\nexec sleep 2\n')
            os.chmod(executable, 0o755)
            environment = {
                'AUTO_BRIGHTNESS_DDC_LOCK': lock_path,
                'PATH': f"{directory}:{os.environ['PATH']}",
            }
            with patch.dict(os.environ, environment):
                with self.assertRaises(subprocess.TimeoutExpired):
                    monitor_control.run_ddcutil(['detect'], timeout=0.05)

                with open(executable, 'w') as script:
                    script.write('#!/bin/sh\nexit 0\n')
                os.chmod(executable, 0o755)
                result = monitor_control.run_ddcutil(['detect'], timeout=0.2)
                self.assertEqual(result.returncode, 0)


class DDCIMonitorControlTests(unittest.TestCase):
    DETECT_OUTPUT = """Display 1
   I2C bus:  /dev/i2c-6
   Monitor:  DEL:P2418D:SERIAL
Display 2
   I2C bus:  /dev/i2c-7
   Monitor:  PHL:245E1:SERIAL
"""

    @patch('monitor_control.run_ddcutil')
    def test_service_detection_skips_capability_queries(self, run_ddcutil):
        run_ddcutil.return_value = SimpleNamespace(stdout=self.DETECT_OUTPUT)
        control = monitor_control.DDCIMonitorControl()
        control.get_monitor_capabilities = Mock(return_value={'features': {'10': {}}})

        monitors = control.detect_monitors(include_capabilities=False)

        self.assertEqual(list(monitors), ['1', '2'])
        self.assertEqual(monitors['1']['i2c_bus'], '6')
        control.get_monitor_capabilities.assert_not_called()

    @patch('monitor_control.run_ddcutil')
    def test_gui_detection_can_request_capabilities(self, run_ddcutil):
        run_ddcutil.return_value = SimpleNamespace(stdout=self.DETECT_OUTPUT)
        control = monitor_control.DDCIMonitorControl()
        control.get_monitor_capabilities = Mock(return_value={'features': {'10': {}}})

        control.detect_monitors(include_capabilities=True)

        self.assertEqual(control.get_monitor_capabilities.call_count, 2)


class HybridMonitorControlCacheTests(unittest.TestCase):
    def make_control(self):
        control = monitor_control.HybridMonitorControl()
        control.kde = Mock()
        control.kde.is_available.return_value = False
        ddc = Mock()
        ddc.detect_monitors.return_value = {
            '1': {'i2c_bus': '6', 'model': 'DEL:P2418D:SERIAL'}
        }
        control.ddc = ddc
        raw_ddc = Mock()
        raw_ddc.detect_unmapped_monitors.return_value = {}
        control.raw_ddc = raw_ddc
        return control, ddc, raw_ddc

    def test_duplicate_detection_reuses_recent_topology(self):
        control, ddc, _ = self.make_control()
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                first = control.detect_monitors(include_capabilities=False)
                second = control.detect_monitors(include_capabilities=False)

        self.assertIs(first, second)
        ddc.detect_monitors.assert_called_once_with(include_capabilities=False)

    def test_force_refresh_bypasses_recent_topology(self):
        control, ddc, _ = self.make_control()
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                control.detect_monitors(include_capabilities=False)
                control.detect_monitors(include_capabilities=False, force_refresh=True)

        self.assertEqual(ddc.detect_monitors.call_count, 2)

    def test_incomplete_refresh_preserves_routing_snapshot(self):
        control, ddc, raw_ddc = self.make_control()
        with tempfile.TemporaryDirectory() as directory:
            lock_path = os.path.join(directory, 'ddc.lock')
            with patch.dict(os.environ, {'AUTO_BRIGHTNESS_DDC_LOCK': lock_path}):
                original = control.detect_monitors(include_capabilities=False)
                original_route = dict(original['1'])
                ddc.detect_monitors.return_value = {}
                raw_ddc.detect_unmapped_monitors.return_value = {}
                refreshed = control.detect_monitors(
                    include_capabilities=False,
                    cache_ttl=0.0,
                )

        self.assertIs(refreshed, original)
        self.assertEqual(refreshed['1'], original_route)
        self.assertFalse(control.last_detection_succeeded)


if __name__ == '__main__':
    unittest.main()
