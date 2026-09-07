"""Real process lifecycle tests with a local stand-in, never the user's desktop."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = self.base / "config/omarchy-remote-desktop"
        self.data.mkdir(parents=True, mode=0o700)
        self.runtime = self.base / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.flags = self.base / "flags"
        self.flags.mkdir()
        for name in ("enabled", "plugin", "network", "monitor"):
            (self.flags / name).touch()
        settings = dict(address="192.168.1.5", port=3389, output="DP-1", username="alice", enabled=True)
        self.write(self.data / "settings.json", json.dumps(settings))
        self.write(self.data / "password", "test-password-not-a-real-secret")
        self.child_script = self.base / "child.py"
        self.child_script.write_text("import os,time,pathlib\npathlib.Path(__file__).with_suffix('.pid').write_text(str(os.getpid()))\ntime.sleep(60)\n")
        # Patch only environmental discovery and the RDP engine. All supervision,
        # filesystem validation, credential checks and termination are real.
        driver = self.base / "driver.py"
        driver.write_text('''
import sys,os,json
from pathlib import Path
sys.path.insert(0, sys.argv[1] + '/lib')
import remote_desktop as rd
base = Path(sys.argv[2])
app = rd.App(base/'config', base/'runtime')
app.plugin_enabled = lambda: (base/'flags/plugin').exists()
app.preflight = lambda conf: app.credential()
rd.systemctl = lambda *args, **kwargs: ''
rd.child_listens = lambda *args: True
rd.inventory = lambda: dict(outputs=[dict(name='DP-1')] if (base/'flags/monitor').exists() else [], addresses=[dict(address='192.168.1.5')] if (base/'flags/network').exists() else [])
app.backend_args = lambda *args: [sys.executable, str(base/'child.py')]
result = app.supervise()
sys.exit(1 if result.get('failed') else 0)
''')
        self.proc = subprocess.Popen([sys.executable, str(driver), str(ROOT), str(self.base)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup_proc)
        self.wait_for(lambda: self.child_script.with_suffix('.pid').exists())
        self.pid = int(self.child_script.with_suffix('.pid').read_text())

    def write(self, path, text):
        path.write_text(text)
        path.chmod(0o600)

    def cleanup_proc(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc.stderr.close()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            if self.proc.poll() is not None:
                self.fail(self.proc.stderr.read().decode())
            time.sleep(0.05)
        self.fail("Supervisor did not reach expected state")

    def assert_stopped(self):
        self.proc.wait(timeout=5)
        with self.assertRaises(ProcessLookupError):
            os.kill(self.pid, 0)

    def test_plugin_removal_stops_backend(self):
        (self.flags / "plugin").unlink()
        self.assert_stopped()

    def test_network_loss_stops_backend(self):
        (self.flags / "network").unlink()
        self.assert_stopped()

    def test_monitor_loss_stops_backend(self):
        (self.flags / "monitor").unlink()
        self.assert_stopped()

    def test_deleted_password_stops_backend(self):
        (self.data / "password").unlink()
        self.assert_stopped()

    def test_disabled_config_stops_backend(self):
        path = self.data / "settings.json"
        data = json.loads(path.read_text())
        data["enabled"] = False
        self.write(path, json.dumps(data))
        self.assert_stopped()

    def test_stop_signal_reaps_backend(self):
        self.proc.terminate()
        self.assert_stopped()

    def test_backend_crash_reports_error(self):
        os.kill(self.pid, signal.SIGKILL)
        self.assert_stopped()
        status = json.loads((self.runtime / "omarchy-remote-desktop/status.json").read_text())
        self.assertEqual(status["state"], "Error")
        self.assertIn("server stopped", status["error"])

    def test_backend_survives_without_any_shell_heartbeat(self):
        time.sleep(1.2)
        self.assertIsNone(self.proc.poll())
        os.kill(self.pid, 0)
        self.proc.terminate()
        self.assert_stopped()


if __name__ == "__main__":
    unittest.main()
