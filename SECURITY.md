# Security model

This plugin has undergone local source review and automated checks, not an
independent security audit. See [compatibility](docs/COMPATIBILITY.md) for test
evidence and remaining validation gaps.

## Trust boundary

Omarchy plugins run unsandboxed as the desktop user. Other processes running as
that user, root, a compromised compositor or a compromised RDP backend can access
the same desktop and secrets. Owner-only storage protects against other ordinary
local users, not code already executing as you. The RDP protocol implementation
belongs to upstream hypr-rdp and its dependencies; the plugin does not replace its
authentication, cryptography or input handling.

## Credentials and configuration

- Both username and password are required. Passwords must be 8–256 characters, and
  control characters are always rejected. The floor is not configurable and no
  setting waives it: with no credentials at all the backend drops to TLS-only with
  no network authentication, so an empty secret must stay unreachable through
  configuration. The generator uses the operating system cryptographic RNG and
  produces far longer passwords than the floor.
- The backend performs no login rate limiting, lockout or failed-attempt backoff, so
  password length is the only defence against online brute force. Eight characters is
  a floor, not a recommendation; prefer the generator, and treat a short password as
  acceptable only on a network you already trust.
- Plaintext password storage is necessary for the backend password-file API.
  Storage lives outside the plugin repository under an owner-only directory;
  sensitive files are 0600. No shell.json, argument, export or log carries it.
- QML sends setup JSON through a private subprocess stdin pipe and clears the
  field/payload after use. Python/Qt managed strings cannot guarantee memory zeroing.
- Core dumps are disabled for the managed service. Backend stdout/stderr are
  discarded so backend changes cannot accidentally log a password. Error messages
  expose controlled diagnostics, not raw backend data. This reduces troubleshooting
  detail; reproduce backend problems separately using disposable test credentials.
- Reads reject symlinks, nonregular files, hardlinks, unsafe ownership/permissions
  and oversized data. Ancestor directories are checked, and writes use private
  temporary files plus atomic replacement. Same-user filesystem races are outside
  the isolation guarantee.
- An explicit, empty backend config prevents inheriting an independently configured
  hypr-rdp config or arbitrary hooks. Generated arguments specify credentials,
  certificates, monitor, address and audio policy explicitly.

## Network and UI

A virtual display shows only its own contents: the local monitors are never
captured in that mode, and the backend creates the screen rather than the plugin
reading an existing one. Its size and scale are validated against fixed bounds
and passed as separate arguments, never interpolated into a command line.

Only an explicitly selected private IPv4 address is allowed. No public/wildcard
binding, router forwarding, firewall edits, SSH enabling or VPN setup occurs.
RFC1918 and carrier-grade NAT ranges are accepted; range membership alone is not
proof that a network is trusted. Users must apply suitable firewall/VPN policies.

Restricting who can reach the port matters beyond authentication. On the
previously pinned backend build, a single TCP connection that never
authenticates blocked every valid login for as long as it stayed open, and the
server never timed it out, so any peer able to reach the port could keep the
owner out without credentials. `tests/backend-smoke <binary> --live` reproduces
this against a localhost listener. Upstream has since reworked connection
handling and this has not yet been re-measured on 0.1.8. Until it is, allow only
the intended client through your firewall or VPN policy (for Tailscale, an ACL
naming that device).

A persistent self-signed RSA certificate secures transport; users compare its
SHA-256 fingerprint on first connection. Expired or partial certificates block
start. Never bypass certificate checks or trust a changed identity without review.

All owned labels use plain-text rendering. Monitor IDs and credential names are
validated, and external data/commands have byte limits and timeouts. Control
operations use argv arrays. Only the backend's documented session hooks use a
shell, with internally generated, quoted callback arguments and a per-run ID.
Callbacks carry no password and are ignored after that backend generation ends.

The shell never reads the clipboard. Qt's native paste fetches it synchronously
inside the one shell process shared by every plugin, with no aggregate size or
time limit, so a hostile clipboard owner could stall the whole shell during a
paste. Every native path is closed on the plugin's text fields: paste shortcuts,
middle-click primary selection, and the context menu by mouse or Menu key. The
username and password fields instead ask the helper, which reads the clipboard
with `wl-paste` in a child process killed past 1 KiB or one second; the worst
case is a refused paste. Qt releases through at least 6.12.0 also fetch the full
clipboard payload on every clipboard change, for any writable text input, to
decide whether pasting is possible (fixed upstream in qtdeclarative `ef692a52`,
cherry-picked as `bcbfae6`). The plugin's fields are therefore read-only except
while the setup form is open in front of the user, which is the one window that
remains on an unfixed Qt.

## Service lifecycle

Only the plugin's marked user unit is managed. It uses NoNewPrivileges, a private
umask, graphical-session binding and systemd control-group termination. No sudoers
rules, shared temporary PID files or privileged process control are used.

The supervisor checks plugin presence/enabled configuration and current monitor,
address and credentials every cycle. Discovery commands each have a one-second
deadline. A failing check stops the backend; service-stop has a three-second
systemd deadline. Automated tests exercise revocation with real stand-in processes;
the five-second removal target still needs real-backend verification under load.
There is no shell heartbeat dependency, so ordinary shell reloads preserve access.

Neither screen blanking nor a VPN replaces authentication or the compositor lock.
No promises about remote unlocking or privacy on a locked screen may be published
until the acceptance matrix is completed. Remote desktop remains unavailable
before local desktop login and while the machine sleeps.

## Dependencies and reporting

The backend is not bundled, built or vendored here. Installing it is an explicit
terminal action that hands `hypr-rdp` to Omarchy's own AUR helper; this plugin
ships no installer, no build recipe and no privileged command, and never installs
anything on its own. Never add a curl-to-shell installer, execute a moving Git
checkout, or run a package manager outside that explicit action.

The AUR package is maintained by the upstream hypr-rdp author. Its recipe for
0.1.8 fetches the upstream release tag `v0.1.8` (commit `2c6be385`) and pins its
SHA-256, `755903df…a3efa`; that archive was re-downloaded independently and
matched on 2026-11-17. This is not a pin reviewed in this repository, so a later
AUR update could change what is installed: review the recipe when updating, as
with any AUR package. What the plugin itself guarantees is capability, not
origin — it inspects the binary for the password-file and session-hook
interfaces and refuses to run anything lacking them.

Report security concerns privately to the repository owner. Do not put passwords,
private keys, desktop captures or exploit details in public issues.
