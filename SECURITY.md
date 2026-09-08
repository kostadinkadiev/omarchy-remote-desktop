# Security model

This plugin has undergone local source review and automated checks, not an
independent security audit. See docs/RELEASE-REVIEW.md for evidence and limits.

## Trust boundary

Omarchy plugins run unsandboxed as the desktop user. Other processes running as
that user, root, a compromised compositor or a compromised RDP backend can access
the same desktop and secrets. Owner-only storage protects against other ordinary
local users, not code already executing as you. The RDP protocol implementation
belongs to upstream hypr-rdp and its dependencies; the plugin does not replace its
authentication, cryptography or input handling.

## Credentials and configuration

- Both username and password are required. Custom passwords require 16–256
  characters; the generator uses the operating system cryptographic RNG.
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

Only an explicitly selected private IPv4 address is allowed. No public/wildcard
binding, router forwarding, firewall edits, SSH enabling or VPN setup occurs.
RFC1918 and carrier-grade NAT ranges are accepted; range membership alone is not
proof that a network is trusted. Users must apply suitable firewall/VPN policies.

A persistent self-signed RSA certificate secures transport; users compare its
SHA-256 fingerprint on first connection. Expired or partial certificates block
start. Never bypass certificate checks or trust a changed identity without review.

All owned labels use plain-text rendering. Monitor IDs and credential names are
validated, and external data/commands have byte limits and timeouts. Control
operations use argv arrays. Only the backend's documented session hooks use a
shell, with internally generated, quoted callback arguments and a per-run ID.
Callbacks carry no password and are ignored after that backend generation ends.

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

Dependency installation is an explicit terminal action and requires the normal
package-management privileges. Never add a curl-to-shell installer or execute a
moving Git checkout. A source build must be pinned to a full reviewed commit.
Marketplace publication requires its exact-commit review for installer,
package-management and service-management capabilities.

Report security concerns privately to the repository owner. Do not put passwords,
private keys, desktop captures or exploit details in public issues. Keep the
repository private until the release checks and review are complete.
