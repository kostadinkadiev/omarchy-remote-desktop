# Pre-publication review — 2026-09-08

## Decision

Release candidate prepared for owner review, not yet approved by the marketplace.
The repository remains private; no submission, public release or visibility
change was made. Removing the experimental label does not establish platform
compatibility or marketplace verification.

## Checks completed

- Omarchy manifest validation passed. Root manifest, README, MIT license,
  installation/removal instructions and dependency disclosure are present.
- 37 Python security/helper/lifecycle/installer tests passed.
- QML lint, 5 Qt results, isolated Quickshell secret-transport tests and real
  Wayland panel rendering passed. Known dynamic Qt property warnings remain.
- Actual pinned backend rejected missing/empty passwords, selected NLA and
  rejected non-NLA negotiation on a disposable localhost listener.
- Prior live toggle test passed three Enable/Ready/Disable/Off cycles. Socket
  regression reproduces TIME_WAIT and confirms a real listener still blocks start.
- Owner reported Android connection, input, rotation, clipboard, lock,
  bad-password rejection, reconnect and Tailscale/mobile-data checks successful.
  This is owner-reported evidence; exact Android/app versions were not recorded.
- Captured main/settings/help UI with sample data; root preview.png is the main
  panel. Settings capture exposed clipping; simplified its header and password
  control so Save settings is visible on the tested display.
- Local official baseline analysis: no findings; review-required for installer,
  privilege and service-management. See security-preflight.json for scanner SHA,
  file scope and measured evidence. This is a worktree preflight, NOT an official
  exact-commit marketplace scan. The scanner is deterministic, not a general audit.
- No plugin-ID collision found in the downloaded registry snapshot. Full intake
  must still check retired IDs and current marketplace state.

## Security source review

Reviewed subprocess inputs, private storage, credential transport, TLS identity,
network binding, service lifecycle, setup/removal, QML rendering, dependency build
and CI. No newly identified authentication bypass or arbitrary-command path was
found in the wrapper. This is not a guarantee about upstream protocol code.

Passwords are passed through stdin and a private file, not command-line values
or connection exports. Reads enforce ownership, size, regular-file and link
checks. UI data is plain text. Backend configuration and session hooks are fixed
by the helper. Setup uses a checksum-pinned source archive and locked/frozen Rust
build. No firewall/router changes, wildcard binding, sudoers changes, telemetry
or automatic dependency installation are implemented.

The source review found a failed-status refresh could immediately schedule
another failing subprocess. It now waits for the normal polling timer; the
Quickshell regression check covers the failure path.

The local scanner does not detect every capability: package management and a
remote source build are also present and must be disclosed to maintainers.
Privileged operations are limited to the explicit terminal installer and normal
package-manager prompts. Service control is scoped to the marked user unit.

Same-user processes/root can access desktop credentials; plugin execution is
unsandboxed. Private address ranges do not themselves restrict peers. Firewall
and VPN access policy remain necessary. Dependency vulnerability-database auditing,
fuzzing, penetration testing and an independent audit were not performed.

## Owner acceptance update

On 2026-09-08 the owner reported successful Windows use, audio playing on both
devices and a passing logout/login test. These close the corresponding broad
manual-test gaps. Exact Windows/app versions and per-item acceptance results
were not supplied; do not infer every checklist item passed.

Mac remains untested. Microsoft Windows App supports RDP remote-PC connections;
no Mac-specific blocker was found in an upstream issue search on 2026-09-08.
This supports an expectation, not verified compatibility. A Windows/Android
release can proceed with Mac clearly described as untested.

## Release follow-ups and limits

- Mac authentication, certificate, lock, keyboard mapping, scaling, clipboard,
  audio and reconnect tests remain community-validation follow-ups.
- Android audio delay remains an observed limitation; mirroring does not itself
  fix latency. Separate audio restoration after disconnect is not recorded.
- Real-backend plugin revocation under load, monitor/network loss, sleep/resume,
  a fresh installation on another host and explicit Off-after-login were not
  individually recorded. Automated lifecycle checks cover stand-in processes.
- Source, screenshots and tests are prepared for a private release-candidate
  commit. Check CI on that exact commit before publication.
- Making the repository public and submitting are separate publication actions.
  Marketplace intake must perform a fresh exact-commit scan and an authorized
  maintainer must approve the reported capabilities before listing.

## Official references

- https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md
- https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md
- https://plugins.omarchy.org/develop.html
