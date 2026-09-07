"""User-owned RDP configuration and supervision. No shell for control commands.

The backend's two session hooks necessarily use its shell interface; their
arguments are generated internally and quoted, never supplied by configuration.
Same-user processes are inside the trust boundary of an unsandboxed shell plugin.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

PLUGIN = "kokd.remote-desktop"
UNIT = "omarchy-remote-desktop.service"
MARKER = "# Managed by kokd.remote-desktop\n"
MAX_IO = 65536
ROOT = Path(__file__).resolve().parent.parent
FLAGS = ("--password-file", "--output", "--cert", "--key", "--config",
         "--on-session-start", "--on-session-end", "--audio-mode", "--egfx-codec")


class Problem(Exception):
    """An actionable message safe to show without subprocess output or secrets."""


def run(args, timeout=3, limit=MAX_IO, check=True):
    """Bound output while it is produced, including children holding pipes open."""
    try:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, start_new_session=True,
                                env={**os.environ, "LC_ALL": "C"})
    except OSError:
        raise Problem(f"Cannot run {Path(args[0]).name}. Check its installation.") from None
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Problem(f"{Path(args[0]).name} took too long. Try again.")
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fd, 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        data.extend(chunk)
                        if len(data) > limit:
                            raise Problem(f"{Path(args[0]).name} returned too much data.")
            proc.wait(timeout=max(0.01, deadline - time.monotonic()))
        if check and proc.returncode:
            raise Problem(f"{Path(args[0]).name} failed. Check the service or installation.")
        return bytes(data).decode("utf-8", errors="replace").strip()
    except subprocess.TimeoutExpired:
        raise Problem(f"{Path(args[0]).name} took too long. Try again.") from None
    finally:
        # Also reap a descendant which held stdout after its parent exited.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        proc.stdout.close()


def plain_file(path, private=True, missing=False, limit=MAX_IO):
    if not safe_dir(path.parent, private=False):
        if missing:
            return None
        raise Problem(f"Missing {path.name}. Complete setup again.")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if missing:
            return None
        raise Problem(f"Missing {path.name}. Complete setup again.") from None
    except OSError:
        raise Problem(f"Unsafe or unreadable {path.name}.") from None
    with os.fdopen(fd, "rb") as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise Problem(f"Unsafe ownership or file type for {path.name}.")
        if info.st_nlink != 1 or info.st_mode & (0o077 if private else 0o022):
            raise Problem(f"Unsafe permissions for {path.name}.")
        value = file.read(limit + 1)
        if len(value) > limit:
            raise Problem(f"{path.name} is too large.")
        return value


def safe_dir(path, create=False, private=True):
    """Reject symlinks throughout the path; never chmod someone else's files."""
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for piece in path.parts[1:]:
        current /= piece
        if create:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
        try:
            info = current.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(info.st_mode):
            raise Problem("Configuration directories must not be symbolic links.")
        # Root-owned ancestors (including sticky /tmp in tests) are allowed.
        if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
            raise Problem("Configuration directory is writable by another user.")
    if info.st_uid != os.getuid() or (private and info.st_mode & 0o077):
        raise Problem(f"{path.name} must be owned by you with owner-only permissions.")
    return True


def write_file(path, data):
    safe_dir(path.parent, create=True)
    plain_file(path, missing=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data if isinstance(data, bytes) else data.encode())
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def read_json(path, missing=False, private=True):
    data = plain_file(path, private=private, missing=missing)
    if data is None:
        return None
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError):
        raise Problem(f"Invalid {path.name}. Complete setup again.") from None
    if not isinstance(result, dict):
        raise Problem(f"Invalid {path.name}.")
    return result


def save_json(path, data):
    write_file(path, json.dumps(data, ensure_ascii=True) + "\n")


def entry_enabled(config):
    if PLUGIN in config.get("disabledPlugins", []):
        return False
    layout = config.get("bar", {}).get("layout", {})
    entries = list(config.get("plugins", []))
    for section in ("left", "center", "right"):
        entries.extend(layout.get(section, []))
    return any((entry == PLUGIN if isinstance(entry, str) else
                isinstance(entry, dict) and entry.get("id") == PLUGIN) for entry in entries)


def validate(values):
    if not isinstance(values, dict):
        raise Problem("Settings must be an object.")
    address = values.get("address", "")
    try:
        ip = ipaddress.IPv4Address(address)
    except (ValueError, TypeError):
        raise Problem("Choose a local IPv4 address.") from None
    private = any(ip in ipaddress.ip_network(net) for net in
                  ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10"))
    if not private:
        raise Problem("Choose a private LAN or VPN address, not a public or wildcard address.")
    username = values.get("username", "")
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}", username):
        raise Problem("Username: use 1–64 letters, numbers, dots, @, underscores or hyphens.")
    output = values.get("output", "")
    if not isinstance(output, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", output):
        raise Problem("Choose a connected physical monitor.")
    port = values.get("port", 3389)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise Problem("Port must be a number between 1024 and 65535.")
    for key in ("autostart", "audio"):
        if type(values.get(key, False)) is not bool:
            raise Problem(f"Invalid {key} setting.")
    return dict(address=str(ip), port=port, username=username, output=output,
                autostart=values.get("autostart", False), audio=values.get("audio", False))


def validate_password(password):
    if not isinstance(password, str) or not 16 <= len(password) <= 256:
        raise Problem("Use a password between 16 and 256 characters.")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise Problem("Password must not contain line breaks or control characters.")
    return password


def inventory():
    try:
        monitors = json.loads(run(["hyprctl", "-j", "monitors"], timeout=1))
        interfaces = json.loads(run(["ip", "-j", "-4", "address", "show", "up"], timeout=1))
        outputs = [dict(name=m["name"], label=str(m.get("description") or m["name"])[:160])
                   for m in monitors[:32] if isinstance(m, dict)
                   and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", str(m.get("name", "")))
                   and not str(m["name"]).startswith(("HEADLESS-", "hypr-rdp-"))]
        addresses = []
        for interface in interfaces[:64]:
            for item in interface.get("addr_info", [])[:16]:
                address = item.get("local", "")
                try:
                    validate(dict(address=address, username="user", output="DP-1"))
                except Problem:
                    continue
                addresses.append(dict(address=address, interface=str(interface.get("ifname", ""))[:64]))
        return dict(outputs=outputs, addresses=addresses[:64])
    except (ValueError, KeyError, TypeError, AttributeError):
        raise Problem("Cannot read monitors or network addresses. Try refreshing.") from None


def check_backend():
    binary = shutil.which("hypr-rdp")
    if not binary:
        return dict(installed=False, compatible=False, message="Install hypr-rdp to continue.")
    help_text = run([binary, "--help"])
    compatible = all(flag in help_text for flag in FLAGS)
    return dict(installed=True, compatible=compatible,
                version=run([binary, "--version"])[:100],
                message="" if compatible else "This hypr-rdp version lacks required security features. A compatible release or reviewed pinned build is required.")


def systemctl(*args, check=True):
    return run(["systemctl", "--user", *args], timeout=12, check=check)


def unit_quote(value):
    # systemd's ExecStart parsing is not shell parsing.
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'


class App:
    def __init__(self, config_home=None, runtime=None, root=ROOT):
        self.base = Path(config_home or os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        self.data = self.base / "omarchy-remote-desktop"
        self.config = self.data / "settings.json"
        self.root = Path(root)
        self.unit = self.base / "systemd/user" / UNIT
        self.runtime_base = Path(runtime or os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        self.runtime = self.runtime_base / "omarchy-remote-desktop"

    def read_config(self, required=True):
        if not safe_dir(self.data):
            if required:
                raise Problem("Complete setup first.")
            return None
        value = read_json(self.config, missing=not required)
        if value is not None:
            clean = validate(value)
            clean["enabled"] = value.get("enabled") is True
            return clean
        return None

    def credential(self):
        try:
            return validate_password(plain_file(self.data / "password", limit=1024).decode("utf-8"))
        except UnicodeError:
            raise Problem("Stored password is invalid. Replace it in Settings.") from None

    def plugin_enabled(self):
        try:
            if not (self.root / "manifest.json").is_file():
                return False
            conf = read_json(self.base / "omarchy/shell.json", private=False)
            return entry_enabled(conf)
        except (Problem, TypeError, AttributeError):
            return False

    def prepare_runtime(self):
        if not safe_dir(self.runtime_base):
            raise Problem("No private desktop runtime directory. Sign into Omarchy first.")
        safe_dir(self.runtime, create=True)

    @contextlib.contextmanager
    def lock(self):
        self.prepare_runtime()
        path = self.runtime / "control.lock"
        plain_file(path, missing=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Problem("Another setup action is still running. Try again shortly.") from None
            yield
        finally:
            os.close(fd)

    def ensure_certificate(self):
        cert, key = self.data / "cert.pem", self.data / "key.pem"
        existing = [plain_file(p, missing=True) is not None for p in (cert, key)]
        if any(existing) and not all(existing):
            raise Problem("The TLS certificate is incomplete. Remove setup and configure it again.")
        if not any(existing):
            with tempfile.TemporaryDirectory(prefix=".tls-", dir=self.data) as directory:
                tmp = Path(directory)
                run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes",
                     "-days", "365", "-subj", "/CN=Omarchy Remote Desktop",
                     "-keyout", str(tmp / "key"), "-out", str(tmp / "cert")], timeout=15)
                write_file(key, (tmp / "key").read_bytes())
                write_file(cert, (tmp / "cert").read_bytes())
        run(["openssl", "x509", "-in", str(cert), "-checkend", "0", "-noout"])

    def install_unit(self):
        safe_dir(self.unit.parent, create=True, private=False)
        existing = plain_file(self.unit, private=False, missing=True)
        if existing is not None and not existing.startswith(MARKER.encode()):
            raise Problem("A different service uses our service name. It will not be overwritten.")
        command = " ".join(unit_quote(arg) for arg in
                           (sys.executable, self.root / "bin/remote-desktopctl", "supervise"))
        content = MARKER + f"""[Unit]
Description=Remote Desktop for Omarchy
PartOf=graphical-session.target
Requires=graphical-session.target
After=graphical-session.target
ConditionEnvironment=WAYLAND_DISPLAY

[Service]
Type=simple
ExecStart={command}
UMask=0077
NoNewPrivileges=yes
LimitCORE=0
KillMode=control-group
TimeoutStopSec=3
Restart=no
StandardOutput=null
StandardError=null

[Install]
WantedBy=graphical-session.target
"""
        # Unit directory can be 0755; all unit content is non-secret.
        fd, temp = tempfile.mkstemp(prefix=".remote-desktop-", dir=self.unit.parent)
        try:
            with os.fdopen(fd, "w") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.unit)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp)
        systemctl("daemon-reload")

    def owned_unit(self):
        value = plain_file(self.unit, private=False, missing=True)
        if value is None:
            return False
        if not value.startswith(MARKER.encode()):
            raise Problem("A different service uses our service name; refusing to control it.")
        return True

    def stop(self, cancel_startup=True):
        if self.owned_unit():
            systemctl("stop", UNIT)
            if cancel_startup:
                systemctl("disable", UNIT)

    def configure(self, request):
        values = validate(request)
        old = self.read_config(required=False)
        password = request.get("password", "")
        if password:
            validate_password(password)
        elif old:
            self.credential()
        else:
            raise Problem("Create an RDP password to finish setup.")
        live = inventory()
        self.match_inventory(values, live)
        self.stop()
        safe_dir(self.data, create=True)
        # Fail closed even if certificate creation or service installation fails.
        save_json(self.config, {**values, "enabled": False})
        if password:
            write_file(self.data / "password", password)
        self.ensure_certificate()
        self.install_unit()
        return {"message": "Settings saved. Remote access is off."}

    @staticmethod
    def match_inventory(conf, live):
        if conf["output"] not in [o["name"] for o in live["outputs"]]:
            raise Problem("The selected monitor is unavailable. Reconnect it or choose another.")
        if conf["address"] not in [a["address"] for a in live["addresses"]]:
            raise Problem("The selected network is unavailable. Reconnect or choose another address.")

    def preflight(self, conf):
        if not self.plugin_enabled():
            raise Problem("Enable the Remote Desktop plugin in Omarchy first.")
        if not os.environ.get("WAYLAND_DISPLAY"):
            raise Problem("Sign into the Omarchy desktop before enabling access.")
        version = json.loads(run(["hyprctl", "-j", "version"]))
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(version.get("version", "")))
        if not match or tuple(map(int, match.groups())) < (0, 54, 0):
            raise Problem("Hyprland 0.54 or newer is required.")
        backend = check_backend()
        if not backend["compatible"]:
            raise Problem(backend["message"])
        self.credential()
        self.ensure_certificate()
        self.match_inventory(conf, inventory())

    def enable(self):
        conf = self.read_config()
        self.preflight(conf)
        self.install_unit()
        if systemctl("is-active", UNIT, check=False) == "active":
            return {"message": "Remote Desktop is already enabled."}
        # Binding only checks availability; the backend must still acquire it.
        try:
            with socket.socket() as probe:
                probe.bind((conf["address"], conf["port"]))
        except OSError:
            raise Problem("That address or port is busy. Choose another port in Settings.") from None
        save_json(self.config, {**conf, "enabled": True})
        try:
            systemctl("enable" if conf["autostart"] else "disable", UNIT)
            systemctl("reset-failed", UNIT, check=False)
            systemctl("start", UNIT)
        except Problem:
            save_json(self.config, {**conf, "enabled": False, "autostart": False})
            with contextlib.suppress(Problem):
                self.stop()
            raise
        return {"message": "Starting Remote Desktop…"}

    def disable(self):
        conf = self.read_config(required=False)
        # Persist revocation before contacting systemd, so a failed stop cannot
        # cause the supervisor to continue serving or restart after login.
        if conf:
            save_json(self.config, {**conf, "enabled": False, "autostart": False})
        self.stop()
        return {"message": "Remote Desktop is off. Startup after login is off."}

    def status(self):
        conf = self.read_config(required=False)
        result = dict(configured=bool(conf), state="Off" if conf else "Setup required",
                      settings=conf or {}, experimental=True)
        if not conf:
            return result
        if self.owned_unit():
            active = systemctl("is-active", UNIT, check=False)
            runtime = read_json(self.runtime / "status.json", missing=True) if safe_dir(self.runtime) else None
            if active in ("active", "activating"):
                fresh = runtime and time.time() - runtime.get("at", 0) < 6
                result["state"] = runtime.get("state", "Starting") if fresh else "Starting"
                if fresh and runtime.get("error"):
                    result["error"] = runtime["error"][:300]
            elif active == "failed" or (conf["enabled"] and runtime and runtime.get("error")):
                result["state"] = "Error"
                result["error"] = (runtime or {}).get("error", "The server stopped. Check compatibility and try again.")[:300]
        result["address"] = f'{conf["address"]}:{conf["port"]}'
        if (self.data / "cert.pem").exists():
            plain_file(self.data / "cert.pem")
            result["fingerprint"] = run(["openssl", "x509", "-in", str(self.data / "cert.pem"),
                                         "-noout", "-fingerprint", "-sha256"]).split("=", 1)[-1][:100]
        return result

    def export(self):
        conf = self.read_config()
        directory = self.data / "exports"
        safe_dir(directory, create=True)
        path = directory / "Omarchy.rdp"
        text = (f'full address:s:{conf["address"]}:{conf["port"]}\r\n'
                f'username:s:{conf["username"]}\r\n'
                'prompt for credentials:i:1\r\nauthentication level:i:2\r\n'
                'enablecredsspsupport:i:1\r\nredirectclipboard:i:1\r\n'
                'screen mode id:i:2\r\n'
                f'audiomode:i:{0 if conf["audio"] else 2}\r\n')
        write_file(path, b"\xff\xfe" + text.encode("utf-16le"))
        return {"path": str(path), "message": "Connection file saved; it contains no password."}

    def remove(self):
        self.disable()
        if self.owned_unit():
            self.unit.unlink()
            systemctl("daemon-reload")
        # Only known owned files; never recursively delete a user's directory.
        for path in [self.data / name for name in ("password", "key.pem", "cert.pem", "backend.toml", "settings.json")]:
            if plain_file(path, missing=True) is not None:
                path.unlink()
        exported = self.data / "exports/Omarchy.rdp"
        if plain_file(exported, missing=True) is not None:
            exported.unlink()
        for directory in (self.data / "exports", self.data):
            with contextlib.suppress(OSError):
                directory.rmdir()
        return {"message": "Setup removed. Remote access is off."}

    def backend_args(self, conf, generation):
        write_file(self.data / "backend.toml", "# Deliberately empty; all options below are controlled by the helper.\n")
        callback = [sys.executable, str(self.root / "bin/remote-desktopctl"), "event"]
        return [shutil.which("hypr-rdp") or "hypr-rdp", "--config", str(self.data / "backend.toml"),
                "--bind", f'{conf["address"]}:{conf["port"]}', "--username", conf["username"],
                "--password-file", str(self.data / "password"), "--cert", str(self.data / "cert.pem"),
                "--key", str(self.data / "key.pem"), "--output", conf["output"], "--fps", "30",
                "--egfx-codec", "avc420", "--audio-mode", "redirect" if conf["audio"] else "off",
                "--on-session-start", shlex.join(callback + ["start", generation]),
                "--on-session-end", shlex.join(callback + ["end", generation])]

    def report(self, state, error=""):
        save_json(self.runtime / "status.json", dict(state=state, error=error, at=time.time()))

    def event(self, action, generation):
        self.prepare_runtime()
        state = read_json(self.runtime / "generation.json", missing=True)
        if state and secrets.compare_digest(str(state.get("id", "")), generation):
            save_json(self.runtime / "event.json", dict(generation=generation, connected=action == "start"))
        return {}

    def supervise(self):
        self.prepare_runtime()
        child = None
        stopped = False
        def stop_requested(*_):
            nonlocal stopped
            stopped = True
        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        generation = secrets.token_hex(16)
        self.report("Starting")
        try:
            conf = self.read_config()
            if not conf["enabled"]:
                raise Problem("Remote access is disabled.")
            self.preflight(conf)
            save_json(self.runtime / "generation.json", {"id": generation})
            child = subprocess.Popen(self.backend_args(conf, generation), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            started = time.monotonic()
            while not stopped:
                if child.poll() is not None:
                    raise Problem("The RDP server stopped. Check your backend version, monitor and graphics driver.")
                if not self.plugin_enabled():
                    child.terminate()
                    try:
                        child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                    # No control lock here: stop must never wait on a supervisor
                    # which is itself waiting for the caller's lock.
                    systemctl("disable", UNIT, check=False)
                    raise Problem("Remote Desktop plugin was disabled or removed. Enable access again after restoring it.")
                current = self.read_config()
                if not current["enabled"]:
                    break
                self.credential()
                self.match_inventory(conf, inventory())
                event = read_json(self.runtime / "event.json", missing=True)
                connected = bool(event and event.get("generation") == generation and event.get("connected"))
                # Inspect the child's socket ownership, not another server's port.
                ready = child_listens(child.pid, conf["address"], conf["port"])
                if not ready and time.monotonic() - started > 20:
                    raise Problem("The server did not start listening. Check capture support and your graphics driver.")
                self.report("Connected" if ready and connected else "Ready" if ready else "Starting")
                time.sleep(1)
            self.report("Off")
            return {}
        except (Problem, OSError, ValueError) as error:
            self.report("Error", str(error) if isinstance(error, Problem) else "Remote Desktop stopped unexpectedly.")
            return {"failed": True}
        finally:
            save_json(self.runtime / "generation.json", {"id": ""})
            if child and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def child_listens(pid, address, port):
    inodes = set()
    try:
        for path in list(Path(f"/proc/{pid}/fd").iterdir())[:512]:
            with contextlib.suppress(OSError):
                target = os.readlink(path)
                if target.startswith("socket:["):
                    inodes.add(target[8:-1])
        expected = socket.inet_aton(address)[::-1].hex().upper() + f":{port:04X}"
        with open(f"/proc/{pid}/net/tcp") as file:
            lines = file.read(MAX_IO + 1)
        if len(lines) > MAX_IO:
            return False
        return any(len(parts := line.split()) > 9 and parts[1] == expected
                   and parts[3] == "0A" and parts[9] in inodes for line in lines.splitlines()[1:])
    except OSError:
        return False


def input_json():
    # UI closes stdin after a single JSON document. Bound both size and time.
    data = bytearray()
    deadline = time.monotonic() + 5
    with selectors.DefaultSelector() as selector:
        selector.register(sys.stdin, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise Problem("Setup input timed out. Try again.")
            chunk = os.read(sys.stdin.fileno(), 4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 4096:
                raise Problem("Setup input is too large.")
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError):
        raise Problem("Invalid setup input.") from None
    if not isinstance(value, dict):
        raise Problem("Invalid setup input.")
    return value


def main():
    parser = argparse.ArgumentParser(description="Remote Desktop for Omarchy (experimental)")
    parser.add_argument("command", choices=("check", "inventory", "status", "generate-password", "configure",
                                            "enable", "disable", "export", "remove", "supervise", "event"))
    parser.add_argument("event_args", nargs="*")
    args = parser.parse_args()
    app = App()
    try:
        if args.command == "event":
            if len(args.event_args) != 2 or args.event_args[0] not in ("start", "end"):
                raise Problem("Invalid event.")
            result = app.event(*args.event_args)
        elif args.event_args:
            raise Problem("Settings and credentials are accepted only on standard input.")
        elif args.command == "check":
            result = check_backend()
            try:
                result["environment"] = inventory()
            except Problem as error:
                result["environment"] = {"outputs": [], "addresses": []}
                result["environmentError"] = str(error)
        elif args.command == "inventory":
            result = inventory()
        elif args.command == "generate-password":
            result = {"password": secrets.token_urlsafe(24)}
        elif args.command == "configure":
            request = input_json()
            with app.lock():
                result = app.configure(request)
        elif args.command in ("enable", "disable", "remove", "export"):
            with app.lock():
                result = getattr(app, args.command)()
        else:
            result = getattr(app, args.command)()
        print(json.dumps({"ok": True, **result}, ensure_ascii=True))
        if result.get("failed"):
            sys.exit(1)
    except (Problem, OSError, ValueError, TypeError, KeyError) as error:
        message = str(error) if isinstance(error, Problem) else "Cannot complete this action. Check installation and file permissions."
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=True))
        sys.exit(1)
