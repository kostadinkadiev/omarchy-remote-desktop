# Compatibility and release checklist

## Current evidence

| Component | Evidence | Status |
| --- | --- | --- |
| Local host | Hyprland 0.56.2, Quickshell 0.3.1, Python 3.14.7 | Installed versions inspected |
| Backend stable v0.1.5 | Source lacks password-file and session hooks | Incompatible |
| Backend v0.1.8 (AUR `hypr-rdp`) | Diffed against the previously pinned commit: every flag this plugin passes is unchanged, empty password files still rejected, still no login rate limiting; adds opt-in `--auth-mode pam` and `--domain` | Compatible; now the supported install path |
| Backend commit 0474d7c9b6d7897895d758a28091d3368173e430 | SHA-256 checked archive; frozen Rust build; Arch package built successfully | Built on x86_64 |
| Backend local checks | Missing/empty secrets rejected; localhost listener; NLA selected; non-NLA negotiation rejected | Passed; no desktop session established |
| Helper security/lifecycle | 48 tests, including real isolated stand-in processes and certificate persistence | Passed; not full RDP validation |
| Disconnect action | Helper cycles only the owned unit, refuses when off/stopped/foreign, and never rewrites settings | Unit-tested; live client disconnect not yet verified |
| UI | QML lint, 5 Qt test results, real Quickshell stdin transport, mock panel on Wayland | Passed on Omarchy 4.0.4 / Qt 6.11.2 |
| Android Windows App | Owner reports successful connection, reconnect, input, rotation, clipboard, lock, wrong-password rejection and Tailscale/mobile-data tests on 2026-09-08; exact client version not recorded | User-tested; audio delay reported |
| Windows RDP client | Owner reports successful Windows use on 2026-09-08; exact client/version and individual acceptance items not recorded | User-tested |
| Linux FreeRDP client | `xfreerdp3` 3.31.1 on Omarchy 4.0.4/Hyprland 0.56.2: fullscreen 2880x1800 virtual display, keyboard confirmed reaching the remote lock screen, pointer events observed | User-tested 2026-11-07 |
| `wlfreerdp3` / `sdl-freerdp3` | wlfreerdp3 crashes on the backend's `ResetGraphics` with `monitorCount[0]`; sdl-freerdp3 enumerates a 128x128 display and refuses fullscreen | Unusable on Hyprland; upstream issues |
| macOS Windows App | No Mac available; no Mac-specific blocker found in upstream issue search on 2026-09-08 | Expected compatible, untested |
| Server Mode / omaVNC | Source/documentation reviewed | Live coexistence pending |

## Detailed acceptance matrix (record client, host and backend versions)

Unchecked items are not individually recorded; the owner’s successful Windows
report above is not an assertion that every item below was tested.

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
- [ ] Persistent On resumes after desktop login, never before login.
- [ ] A busy port causes a useful error without affecting its owner.
- [ ] Existing WayVNC/RustDesk/Sunshine processes and configuration remain intact.
- [ ] Test LAN and an existing VPN path with intended firewall/VPN restrictions.
- [ ] Test alongside Server Mode, including lid close and battery safeguards.
- [ ] Disconnect ends the active session while the toggle stays On and startup after login is unchanged.
- [ ] After Disconnect the server listens again and the same client can reconnect.
- [ ] Disconnect is absent unless a client is connected, and a second client is also dropped.
- [ ] A password under 8 characters is refused, and no request field lowers that floor.
- [ ] An 8-character password survives a restart: the supervisor does not stop access on revalidation.
- [ ] A virtual display serves the chosen size and scale, and no local monitor content appears in it.
- [ ] A virtual display keeps serving with every physical monitor disconnected.
- [ ] Switching between a shared monitor and a virtual display restarts cleanly and records the right mode.
- [ ] Settings written before virtual displays existed still share their monitor after an update.
- [ ] Each offered frame rate reaches the backend and settings predating the setting still run at 30.
- [ ] Install RDP backend installs the AUR package and Check again then reports compatible.
- [ ] A pre-0.1.6 backend is refused with a message naming the missing interfaces.
- [ ] Complete cleanup removes only plugin-owned service/configuration/secrets.

## Mac acceptance

Repeat authentication, certificate, capture, lock and reconnect tests through
Microsoft Windows App. Also check Retina scaling, Command/Control/Option mapping,
clipboard, audio and full-screen behavior. Keep Mac labeled untested until done. Mac testing is a follow-up, not a blocker
for a release advertising Windows/Android as user-tested.

## Validation limits

Automated checks are not a complete security audit. Authentication or lock bypass
must be treated as a security defect, never worked around by weakening the lock
or certificate validation. Marketplace verification applies only to its reviewed
commit and does not replace client testing.

## Follow-up changes after Android testing

Owner confirmed audio mirroring plays on both devices and the logout/login test
passed on 2026-09-08. Disconnect audio restoration and separate Off-after-login
behavior were not individually reported.
The on/off port regression passed three live cycles and a TIME_WAIT socket test.
