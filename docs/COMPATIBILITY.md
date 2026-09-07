# Compatibility and release checklist

## Current evidence

| Component | Evidence | Status |
| --- | --- | --- |
| Local host | Hyprland 0.56.2, Quickshell 0.3.1, Python 3.14.7 | Installed versions inspected |
| Backend stable v0.1.5 | Source lacks password-file and session hooks | Incompatible |
| Backend commit 0474d7c9b6d7897895d758a28091d3368173e430 | SHA-256 checked archive; frozen Rust build; Arch package built successfully | Built on x86_64 |
| Backend local checks | Missing/empty secrets rejected; localhost listener; NLA selected; non-NLA negotiation rejected | Passed; no desktop session established |
| Helper security/lifecycle/installer | 35 tests, including real isolated stand-in processes and certificate persistence | Passed; not full RDP validation |
| UI | QML lint, 5 Qt test results, real Quickshell stdin transport, mock panel on Wayland | Passed |
| Windows mstsc | Requires a second machine | Pending, blocks release |
| macOS Windows App | No Mac available | Unverified |
| Server Mode / omaVNC | Source/documentation reviewed | Live coexistence pending |

## Windows acceptance (record client, host and backend versions)

- [ ] Fresh plugin install leaves no listener or autostart service enabled.
- [ ] Complete setup without editing config files; connect through mstsc.
- [ ] Exported connection file works and contains no secret.
- [ ] Wrong username/password fails; omitted credentials never bypass authentication.
- [ ] Missing, empty, unreadable or insecure password file blocks start.
- [ ] First certificate fingerprint matches; repeat connections retain identity.
- [ ] Selected monitor matches what is visible locally; keyboard and pointer work.
- [ ] Clipboard sharing and optional audio behave as disclosed.
- [ ] Connect while locked: no desktop content or input bypass; normal unlock works.
- [ ] Lock during an existing connection: same privacy and authentication boundary.
- [ ] Reconnect repeatedly; test client resize and non-US keyboard layouts.
- [ ] Test display power saving, disconnected monitor and sleep/resume.
- [ ] Shell reload preserves the connection; logout terminates it.
- [ ] Explicit off, plugin disable and plugin removal close access within five seconds.
- [ ] Loss of selected address stops access without falling back to another address.
- [ ] Optional startup works after desktop login, never before login.
- [ ] A busy port causes a useful error without affecting its owner.
- [ ] Existing WayVNC/RustDesk/Sunshine processes and configuration remain intact.
- [ ] Test LAN and an existing VPN path with intended firewall/VPN restrictions.
- [ ] Test alongside Server Mode, including lid close and battery safeguards.
- [ ] Complete cleanup removes only plugin-owned service/configuration/secrets.

## Mac acceptance

Repeat authentication, certificate, capture, lock and reconnect tests through
Microsoft Windows App. Also check Retina scaling, Command/Control/Option mapping,
clipboard, audio and full-screen behavior. Keep Mac support unverified until done.

## Publication gate

Authentication or lock bypass is a release blocker. Do not weaken the lock,
disable certificate validation or silently change capture mode to pass tests.
Keep the repository private until the owner reviews the results. Then prepare
screenshots, a versioned release and the marketplace's exact-commit security and
compatibility submission. Automated checks are not a complete security audit.
