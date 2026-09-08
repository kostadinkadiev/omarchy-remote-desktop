import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import remote_desktop as rd


GOOD = dict(address="192.168.1.5", port=3389, output="DP-1", username="alice",
            autostart=False, audio=False)
PASSWORD = "a-safe-example-password"
LIVE = dict(outputs=[dict(name="DP-1", label="Display")],
            addresses=[dict(address="192.168.1.5", interface="eth0")])


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.runtime = self.base / "run"
        self.runtime.mkdir(mode=0o700)
        self.root = self.base / "plugin"
        self.root.mkdir()
        (self.root / "manifest.json").write_text('{}')
        self.app = rd.App(self.base / "config", self.runtime, root=self.root)
        self.app.prepare_runtime()

    def configured(self):
        rd.save_json(self.app.config, {**GOOD, "enabled": True})
        rd.write_file(self.app.data / "password", PASSWORD)

    def test_address_and_injection_validation(self):
        for address in ("0.0.0.0", "127.0.0.1", "8.8.8.8", "::1", "192.168.1.5\nfoo", "169.254.1.2"):
            with self.subTest(address=address), self.assertRaises(rd.Problem):
                rd.validate({**GOOD, "address": address})
        for key, value in (("username", "bob\npassword:s:bad"), ("output", "DP-1; touch /tmp/no"),
                           ("port", True), ("port", 22), ("port", "3389"), ("audio", "false")):
            with self.subTest(key=key), self.assertRaises(rd.Problem):
                rd.validate({**GOOD, key: value})
        self.assertEqual(rd.validate({**GOOD, "address": "100.90.1.3"})["address"], "100.90.1.3")

    def test_complete_password_required(self):
        for password in ("", "short", "x" * 300, "long-password\nwith-break", "x" * 16 + "\0"):
            with self.subTest(password=repr(password)), self.assertRaises(rd.Problem):
                rd.validate_password(password)
        self.assertEqual(rd.validate_password(PASSWORD), PASSWORD)

    def test_safe_files_reject_symlink_fifo_permissions_hardlink_and_size(self):
        path = self.base / "secret"
        path.symlink_to(self.base / "elsewhere")
        with self.assertRaises(rd.Problem):
            rd.plain_file(path)
        path.unlink()
        os.mkfifo(path, 0o600)
        with self.assertRaises(rd.Problem):
            rd.plain_file(path)
        path.unlink()
        path.write_text(PASSWORD)
        path.chmod(0o644)
        with self.assertRaises(rd.Problem):
            rd.plain_file(path)
        path.chmod(0o600)
        os.link(path, self.base / "hardlink")
        with self.assertRaises(rd.Problem):
            rd.plain_file(path)
        (self.base / "hardlink").unlink()
        with self.assertRaises(rd.Problem):
            rd.plain_file(path, limit=3)

    def test_private_atomic_storage_and_symlink_parent(self):
        self.configured()
        self.assertEqual(self.app.data.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.app.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.app.credential(), PASSWORD)
        alias = self.base / "alias"
        alias.symlink_to(self.app.data, target_is_directory=True)
        with self.assertRaises(rd.Problem):
            rd.safe_dir(alias)
        password = self.app.data / "password"
        password.unlink()
        password.symlink_to(self.base / "unrelated")
        with self.assertRaises(rd.Problem):
            rd.write_file(password, PASSWORD)
        self.assertFalse((self.base / "unrelated").exists())

    def test_shell_enable_detection(self):
        for entry in (rd.PLUGIN, {"id": rd.PLUGIN}):
            conf = {"bar": {"layout": {"right": [entry]}}}
            self.assertTrue(rd.entry_enabled(conf))
            self.assertFalse(rd.entry_enabled({**conf, "disabledPlugins": [rd.PLUGIN]}))
        self.assertTrue(rd.entry_enabled({"plugins": [{"id": rd.PLUGIN}]}))
        self.assertFalse(rd.entry_enabled({}))

    def test_no_backend_default_config_or_password_arguments(self):
        self.configured()
        args = self.app.backend_args(GOOD, "generation")
        self.assertNotIn(PASSWORD, " ".join(args))
        self.assertNotIn("--password", args)
        self.assertEqual(args[args.index("--password-file") + 1], str(self.app.data / "password"))
        self.assertEqual(args[args.index("--output") + 1], "DP-1")
        self.assertEqual(args[args.index("--bind") + 1], "192.168.1.5:3389")
        self.assertIn("--config", args)
        self.assertEqual(args[args.index("--audio-mode") + 1], "off")
        mirrored = self.app.backend_args({**GOOD, "audio": True}, "generation")
        self.assertEqual(mirrored[mirrored.index("--audio-mode") + 1], "mirror")

    def test_export_keeps_authentication_and_no_secret(self):
        self.configured()
        output = self.app.export()
        text = Path(output["path"]).read_bytes().decode("utf-16")
        self.assertIn("enablecredsspsupport:i:1", text)
        self.assertIn("authentication level:i:2", text)
        self.assertIn("192.168.1.5:3389", text)
        self.assertNotIn(PASSWORD, text)
        self.assertNotIn("password", text)

    def test_inventory_disappearance_never_falls_back(self):
        self.app.match_inventory(GOOD, LIVE)
        for missing in (dict(outputs=[], addresses=LIVE["addresses"]),
                        dict(outputs=LIVE["outputs"], addresses=[])):
            with self.assertRaises(rd.Problem):
                self.app.match_inventory(GOOD, missing)

    def test_disable_revokes_before_systemctl_failure(self):
        self.configured()
        with patch.object(self.app, "stop", side_effect=rd.Problem("systemd unavailable")):
            with self.assertRaises(rd.Problem):
                self.app.disable()
        self.assertFalse(self.app.read_config()["enabled"])
        self.assertFalse(self.app.read_config()["autostart"])

    def test_configure_validates_before_stopping_and_preserves_existing_secret(self):
        self.configured()
        with patch.object(self.app, "stop") as stop, patch.object(self.app, "ensure_certificate"), \
             patch.object(self.app, "install_unit"), patch.object(rd, "inventory", return_value=LIVE):
            with self.assertRaises(rd.Problem):
                self.app.configure({**GOOD, "password": "short"})
            stop.assert_not_called()
            self.app.configure({**GOOD, "password": ""})
            stop.assert_called_once()
        self.assertEqual(self.app.credential(), PASSWORD)
        self.assertFalse(self.app.read_config()["enabled"])

    def test_certificate_failure_leaves_access_off(self):
        self.configured()
        with patch.object(self.app, "stop"), patch.object(rd, "inventory", return_value=LIVE), \
             patch.object(self.app, "ensure_certificate", side_effect=rd.Problem("TLS failed")):
            with self.assertRaises(rd.Problem):
                self.app.configure({**GOOD, "password": PASSWORD})
        self.assertFalse(self.app.read_config()["enabled"])

    def test_event_from_previous_backend_is_ignored(self):
        rd.save_json(self.app.runtime / "generation.json", {"id": "current"})
        self.app.event("start", "previous")
        self.assertFalse((self.app.runtime / "event.json").exists())
        self.app.event("start", "current")
        self.assertTrue(rd.read_json(self.app.runtime / "event.json")["connected"])
        self.app.event("end", "current")
        self.assertFalse(rd.read_json(self.app.runtime / "event.json")["connected"])

    def test_other_service_is_not_overwritten_or_stopped(self):
        self.app.unit.parent.mkdir(parents=True)
        self.app.unit.write_text("[Service]\nExecStart=/usr/bin/other\n")
        with patch.object(rd, "systemctl") as control:
            with self.assertRaises(rd.Problem):
                self.app.install_unit()
            with self.assertRaises(rd.Problem):
                self.app.stop()
            control.assert_not_called()

    def test_unit_escaping(self):
        value = rd.unit_quote('/tmp/some space/100%/"$HOME"')
        self.assertEqual(value, '"/tmp/some space/100%%/\\"$$HOME\\""')

    def test_remove_only_owned_files(self):
        self.configured()
        keep = self.app.data / "my-notes"
        keep.write_text("keep")
        with patch.object(self.app, "stop"):
            self.app.remove()
        self.assertTrue(keep.exists())
        self.assertFalse(self.app.config.exists())
        self.assertFalse((self.app.data / "password").exists())

    def test_output_is_bounded_at_producer_and_timed(self):
        with self.assertRaises(rd.Problem):
            rd.run([sys.executable, "-c", "print('x' * 1000000)"], limit=1024)
        started = time.monotonic()
        with self.assertRaises(rd.Problem):
            rd.run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)
        self.assertLess(time.monotonic() - started, 2)

    def test_socket_readiness_requires_correct_process(self):
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            port = server.getsockname()[1]
            self.assertTrue(rd.child_listens(os.getpid(), "127.0.0.1", port))
            self.assertFalse(rd.child_listens(99999999, "127.0.0.1", port))
            self.assertFalse(rd.child_listens(os.getpid(), "127.0.0.2", port))

    def test_status_cannot_claim_ready_from_stale_state(self):
        self.configured()
        rd.save_json(self.app.runtime / "status.json", dict(state="Connected", at=time.time() - 60))
        with patch.object(self.app, "owned_unit", return_value=True), \
             patch.object(rd, "systemctl", return_value="active"):
            self.assertEqual(self.app.status()["state"], "Starting")

    def test_control_lock_excludes_concurrent_mutations(self):
        with self.app.lock():
            with self.assertRaises(rd.Problem):
                with self.app.lock():
                    pass

    def test_certificate_identity_is_retained_and_private(self):
        self.configured()
        self.app.ensure_certificate()
        cert = rd.plain_file(self.app.data / "cert.pem")
        key = rd.plain_file(self.app.data / "key.pem")
        self.app.ensure_certificate()
        self.assertEqual(rd.plain_file(self.app.data / "cert.pem"), cert)
        self.assertEqual(rd.plain_file(self.app.data / "key.pem"), key)
        self.assertNotIn(PASSWORD, cert.decode())
        (self.app.data / "cert.pem").unlink()
        with self.assertRaises(rd.Problem):
            self.app.ensure_certificate()

    def test_backend_capability_gate_rejects_old_release(self):
        with patch.object(rd.shutil, "which", return_value="/usr/bin/hypr-rdp"), \
             patch.object(rd, "run", side_effect=["--output --password --config", "hypr-rdp 0.1.5"]):
            self.assertFalse(rd.check_backend()["compatible"])
        with patch.object(rd.shutil, "which", return_value="/usr/bin/hypr-rdp"), \
             patch.object(rd, "run", side_effect=[" ".join(rd.FLAGS), "hypr-rdp test"]):
            self.assertTrue(rd.check_backend()["compatible"])

    def test_restart_after_closed_connection_and_reject_live_listener(self):
        self.configured()
        self.addCleanup(patch.stopall)
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            address, port = server.getsockname()
            server.listen()
            patch.object(self.app, "read_config", return_value={**GOOD, "address": address, "port": port, "enabled": False}).start()
            with patch.object(self.app, "preflight"), patch.object(self.app, "install_unit"), \
                 patch.object(rd, "systemctl", return_value="inactive"):
                with self.assertRaises(rd.Problem):
                    self.app.enable()
            with socket.create_connection((address, port)) as client:
                connection, _ = server.accept()
                connection.close()  # Server actively closes: leaves TIME_WAIT.
                self.assertEqual(client.recv(1), b"")
        with socket.socket() as old_probe:
            with self.assertRaises(OSError):
                old_probe.bind((address, port))
        with patch.object(self.app, "preflight"), patch.object(self.app, "install_unit"), \
             patch.object(rd, "systemctl", return_value="inactive"):
            self.app.enable()
        self.assertTrue(rd.read_json(self.app.config)["enabled"])

    def test_enable_persists_login_startup_even_with_old_preference_off(self):
        for state in ("inactive", "active"):
            with self.subTest(state=state):
                self.configured()
                with patch.object(self.app, "preflight"), patch.object(self.app, "install_unit"), \
                     patch.object(rd.socket, "socket"), \
                     patch.object(rd, "systemctl", return_value=state) as ctl:
                    self.app.enable()
                self.assertTrue(self.app.read_config()["enabled"])
                self.assertTrue(self.app.read_config()["autostart"])
                self.assertTrue(any(call.args == ("enable", rd.UNIT) for call in ctl.call_args_list))

    def test_enable_failed_service_clears_desired_access_and_startup(self):
        self.configured()
        with patch.object(self.app, "preflight"), patch.object(self.app, "install_unit"), \
             patch.object(rd.socket, "socket"), patch.object(self.app, "stop") as stop, \
             patch.object(rd, "systemctl", side_effect=["inactive", "", "", rd.Problem("failed")]):
            with self.assertRaises(rd.Problem):
                self.app.enable()
        self.assertFalse(self.app.read_config()["enabled"])
        self.assertFalse(self.app.read_config()["autostart"])
        stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
