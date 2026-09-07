# Reviewed implementation plan

Build a simple Omarchy RDP hosting plugin, with a compact native panel and a
three-step setup: dependencies, monitor/network, credentials and enable.

Use a Python standard-library helper and a graphical-session-bound user service
around hypr-rdp. Require credentials and TLS, private-address binding, protected
storage, bounded plain-text UI data and explicit lifecycle cleanup. Keep server
operation independent of shell reloads and never touch other remote-access servers.

Share one existing physical monitor. Support Windows Remote Desktop Connection
and document Mac Windows App, with each platform's support gated by actual tests.
Start after desktop login is optional/off initially. No pre-login access, virtual
desktop, VPN installation, automatic firewall changes or privacy blanking in v1.

Implementation order: backend compatibility research/prototype, helper/service,
UI, automated and real-client acceptance tests, documentation and private GitHub
repository. Identity: kokd.remote-desktop; MIT; main branch; separate private
kostadinkadiev/omarchy-remote-desktop repository. No changes to machine-map.

Server Mode is an optional companion for power protection; omaVNC remains an
independent VNC alternative. Differentiate through guided RDP setup and the native
Windows client workflow, without untested performance or security-superiority claims.

## Packaging finding during implementation

Stable backend v0.1.5 lacks password-file and session-hook interfaces. Upstream
commit `0474d7c9b6d7897895d758a28091d3368173e430` contains them. The helper checks
capabilities instead of pretending the stable package suffices. Publication stays
blocked pending a compatible backend and real Windows authentication/lock tests.

The experimental setup offers an opt-in terminal installer for that exact commit,
with a checked archive SHA-256 and frozen dependency build. It never silently
installs the moving AUR Git package. The normal package-manager transaction handles
dependencies and any conflicting hypr-rdp installation.
